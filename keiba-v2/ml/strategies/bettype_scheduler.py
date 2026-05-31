#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""multi-bettype 当日スケジューラ (Session 140 / 全レース multi-bettype 自動投票 v1)

freebudget_scheduler (単勝のみ) の安全機構を ★import 流用★ し、 候補生成・投票だけを
multi-bettype 化したスケジューラ。 単発パス方式 (Task Scheduler から 1-2 分ごと)。

差し替えは 3 点のみ (安全ロジック=timing/lock/state/halt/鮮度/cap/連続失敗 は freebudget と同一):
  ① 候補生成 = bettype_selection で各レースの券種を選び bettype_sizing で amount 付与
  ② filter = build が race_id→RaceSizing を返すので不要
  ③ 投票 = runner を ★--bet 群★ で起動 (--from-json は bet_type を tansho に潰すため不可)

state/lock は freebudget と別ファイル (bettype_scheduler*) で衝突回避。

CLI:
    python -m ml.strategies.bettype_scheduler --date today --strategy concentrate       # dry
    python -m ml.strategies.bettype_scheduler --date 2026-05-31 --now 14:50              # 時刻擬似
    python -m ml.strategies.bettype_scheduler --date today --confirm --i-understand-live # 実弾
    python -m ml.strategies.bettype_scheduler --date today --halt                        # 当日停止
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ★freebudget の安全機構を import 流用 (戦略中立・100% 再利用)★
from ml.strategies.freebudget_scheduler import (  # noqa: E402
    HALT_EXIT_CODES,
    MAX_CONSECUTIVE_FAILURES,
    ODDS_STALE_MIN,
    DEFAULT_PER_DAY_MAX_YEN,
    acquire_lock,
    release_lock,
    save_state,
    load_state,
    read_per_race_cap,
    parse_now,
)
from ml.strategies.freebudget_race import load_post_times, race_timing  # noqa: E402
from ml.strategies.freebudget import resolve_date  # noqa: E402
from ml.strategies.bettype_selection import evaluate_and_select, STRATEGIES  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies.bettype_sizing import get_sizer, DEFAULT_SIZER, SIZERS  # noqa: E402
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402

DEFAULT_BANKROLL = 10000
DEFAULT_STRATEGY = "concentrate"
DEFAULT_EV_FLOOR = 1.0
# multi-bettype 初日 (ふくだ判断): per_day を上げて多くカバー (per_race=3000 は据え置き=檻維持)。
DEFAULT_BETTYPE_PER_DAY_MAX_YEN = 30000


# ---------------------------------------------------------------------------
# state / lock (freebudget と別ファイル)
# ---------------------------------------------------------------------------

def lock_path(day_dir: Path) -> Path:
    return Path(day_dir) / "bettype_scheduler.lock"


def state_path(day_dir: Path, *, live: bool) -> Path:
    name = "bettype_scheduler_state.json" if live \
        else "bettype_scheduler_state_dryrun.json"
    return Path(day_dir) / name


def halt_day(date_str: str, *, live: bool, reason: str) -> dict:
    """当日の bettype state に halted=True (web/CLI「停止」)。 freebudget state は汚さない。
    冪等: 既 halted なら理由を保つ。 dir 未作成でも書けるよう親 dir 確保。"""
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    sp = state_path(day_dir, live=live)
    sp.parent.mkdir(parents=True, exist_ok=True)
    state = load_state(sp, date_str, "live" if live else "dry-run")
    already = bool(state.get("halted"))
    if not already:
        state["halted"] = True
        state["halt_reason"] = reason
        state["halted_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(sp, state)
    return {"halted": True, "already_halted": already,
            "halt_reason": state.get("halt_reason"), "state_path": str(sp)}


# ---------------------------------------------------------------------------
# 候補生成 (差し替え①): bettype_selection + bettype_sizing
# ---------------------------------------------------------------------------

def size_one_race(pred_race: dict, *, strategy: str, ev_floor: float, sizing: str,
                  bankroll: int, per_race_cap: int):
    """1 レースの pred_race → RaceSizing (amount 付き) or None。

    軸は evaluate_and_select の選定軸を be.process_race に明示で渡す (hole_seeker の
    軸差し替えと sizing を必ず一致させる)。 fund 対象 0 件なら None。
    """
    sel = evaluate_and_select(pred_race, strategy=strategy, ev_floor=ev_floor)
    if sel is None or not sel.selected_plans:
        return None
    race_eff = be.process_race(pred_race, axis=sel.axis_umaban)
    if race_eff is None:
        return None
    rs = get_sizer(sizing)(race_eff, sel, bankroll=bankroll, per_race_cap=per_race_cap)
    return rs if rs.legs else None


def build_votable_races(predictions: dict, *, strategy: str, ev_floor: float,
                        sizing: str, bankroll: int, per_race_cap: int) -> dict:
    """全レースを評価 (bettype_race CLI 用)。 scheduler は窓内のみ on-demand で評価する。"""
    out: dict = {}
    for pr in predictions.get("races", []) or []:
        rs = size_one_race(pr, strategy=strategy, ev_floor=ev_floor, sizing=sizing,
                           bankroll=bankroll, per_race_cap=per_race_cap)
        if rs:
            out[str(pr.get("race_id"))] = rs
    return out


# ---------------------------------------------------------------------------
# 投票 (差し替え③): runner を --bet 群で起動
# ---------------------------------------------------------------------------

def build_bet_specs(race_id: str, race_sizing) -> list:
    """RaceSizing → runner --bet 引数文字列群 (ff_writer.parse_bet_spec 形式)。
    馬単/三連単は horses 順序保持。"""
    return [f"{race_id}:{l.bet_type}:" + "/".join(str(h) for h in l.horses) + f":{l.amount}"
            for l in race_sizing.legs]


def notify_skip(label: str, reason: str) -> None:
    """レースを見送った時の音声通知 (ふくだ要望: 動いてないのか見送りか区別できるように)。
    notify 失敗はスケジューラを止めない (try/except)。 import は遅延 (GUI/TTS 依存回避)。"""
    try:
        from ml.target_clicker.notify import speak
        speak(f"{label} 見送り。{reason}", async_=True)
    except Exception as e:  # noqa: BLE001 (通知失敗は致命でない)
        print(f"[bettype] skip notify failed: {e}", file=sys.stderr)


def vote_one_race_multi(day_dir: Path, race_id: str, race_sizing, *,
                        live: bool, login_timeout: int = 180,
                        per_race_cap: int = 0, per_day_remaining: int = 0) -> dict:
    """1 レースを multi-bettype で投票 (live) / 予定をログ (dry-run)。 結果 dict を返す。"""
    legs = race_sizing.legs
    amount = race_sizing.total_yen
    bet_specs = build_bet_specs(race_id, race_sizing)
    leg_summary = [{"bet_type": l.bet_type, "horses": l.horses, "amount": l.amount,
                    "leg_odds": l.leg_odds, "ev": l.ev, "plan_label": l.plan_label}
                   for l in legs]
    base = {"amount": amount, "bet_count": len(legs), "bet_specs": bet_specs,
            "legs": leg_summary, "anchor_yen": race_sizing.anchor_yen,
            "combo_yen": race_sizing.combo_yen}

    if not live:
        return {**base, "mode": "dry-run", "exit_code": 0, "note": "WOULD VOTE (dry-run)"}

    # 二次防御: --max-yen を ★per_race かつ 日次残予算★ で min キャップ (シズネ Session140 🔴-1)。
    #   runner の per_day(config) は subprocess 単位 (per-race) しか見ず累積を止めないため、
    #   scheduler が「日次残予算 per_day_remaining」を --max-yen に織り込み、 境界レースの
    #   投票額がダイアログ層でも日次上限を超えないようにする (累積上限の per-call 番人)。
    bounds = [amount]
    if per_race_cap > 0:
        bounds.append(per_race_cap)
    if per_day_remaining > 0:
        bounds.append(per_day_remaining)
    max_yen = min(bounds)
    cmd = [sys.executable, "-m", "ml.target_clicker.runner"]
    for spec in bet_specs:
        cmd += ["--bet", spec]
    cmd += ["--max-yen", str(max_yen), "--max-bets", str(len(legs)),
            "--login-timeout", str(login_timeout), "--confirm"]
    proc = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[2]))
    return {**base, "mode": "live", "exit_code": proc.returncode,
            "note": "voted" if proc.returncode == 0 else "vote error"}


# ---------------------------------------------------------------------------
# パス実行 (freebudget_scheduler._run_pass_inner と同骨格・3点差し替え)
# ---------------------------------------------------------------------------

def run_pass(date_str: str, *, now: datetime, live: bool, bankroll: int,
             strategy: str, ev_floor: float, sizing: str, per_day_max_yen: int,
             login_timeout: int, notify_on_skip: bool = True,
             verbose: bool = True) -> dict:
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    lp = lock_path(day_dir)
    if not acquire_lock(lp):
        if verbose:
            print(f"[bettype] 別パスが実行中 (lock={lp.name}) → 何もしない", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False, "locked_out": True}
    try:
        return _run_pass_inner(
            date_str, day_dir, now=now, live=live, bankroll=bankroll,
            strategy=strategy, ev_floor=ev_floor, sizing=sizing,
            per_day_max_yen=per_day_max_yen, login_timeout=login_timeout,
            notify_on_skip=notify_on_skip, verbose=verbose)
    finally:
        release_lock(lp)


def _run_pass_inner(date_str: str, day_dir: Path, *, now: datetime, live: bool,
                    bankroll: int, strategy: str, ev_floor: float, sizing: str,
                    per_day_max_yen: int, login_timeout: int,
                    notify_on_skip: bool = True, verbose: bool = True) -> dict:
    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print(f"[bettype] predictions.json なし → 何もしない", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False}

    post_times = load_post_times(day_dir, date_str=date_str)
    per_race_cap = read_per_race_cap()

    sp = state_path(day_dir, live=live)
    state = load_state(sp, date_str, "live" if live else "dry-run")
    if state.get("halted"):
        if verbose:
            print(f"[bettype] HALTED ({state.get('halt_reason')}) — 当日は停止中。 "
                  f"手動確認が必要", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": True}

    voted_yen = sum(v.get("amount", 0) for v in state["votes"].values()
                    if v.get("exit_code") == 0)
    notified_skips = state.setdefault("notified_skips", [])  # 見送り通知済 race_id (重複防止)

    races = predictions.get("races", []) or []
    pred_by_id = {str(r.get("race_id")): r for r in races if r.get("race_id")}

    newly_voted, skipped = [], []
    vb_ref = predictions.get("vb_refreshed_at")

    if verbose:
        print(f"[bettype] {date_str} now={now.strftime('%H:%M')} "
              f"mode={'LIVE' if live else 'dry-run'} strategy={strategy} sizing={sizing} "
              f"odds={vb_ref} レース={len(pred_by_id)} 既投票={voted_yen}円")

    # オッズ鮮度ガード (freebudget と同一: live のみ作動)
    if live and vb_ref:
        try:
            age_min = (now - datetime.fromisoformat(vb_ref)).total_seconds() / 60.0
            if age_min > ODDS_STALE_MIN:
                msg = (f"オッズ鮮度 {age_min:.0f}分 > {ODDS_STALE_MIN}分 "
                       f"(vb_refresh 停止疑い) → このパスは投票せずスキップ")
                if verbose:
                    print(f"[bettype] ⚠ {msg}", file=sys.stderr)
                save_state(sp, state)
                return {"voted": [], "skipped": [("*", msg)], "halted": False}
        except ValueError:
            pass

    for race_id in sorted(pred_by_id):
        if race_id in state["votes"] and state["votes"][race_id].get("exit_code") == 0:
            continue  # 投票済み (冪等)
        pr = pred_by_id[race_id]
        st = post_times.get(race_id, "")
        t = race_timing(date_str, st, now)
        label = f"{pr.get('venue_name') or '?'} {pr.get('race_number') or '?'}R"

        if t["deadline"] is None:
            skipped.append((race_id, "発走時刻不明"))
            continue
        if now < t["vote_at"]:
            continue  # まだウィンドウ前 (静かに待つ)
        if now > t["deadline"]:
            if race_id not in state["votes"]:
                skipped.append((race_id, f"{label} 締切超過 (発走{st})"))
                state["votes"][race_id] = {"mode": "missed", "amount": 0,
                                           "bet_count": 0, "exit_code": -1,
                                           "note": "deadline passed before vote",
                                           "at": now.isoformat(timespec="seconds")}
            continue

        # --- ウィンドウ内: ここで初めて重い評価 (DB) を回す ---
        rs = size_one_race(pr, strategy=strategy, ev_floor=ev_floor, sizing=sizing,
                           bankroll=bankroll, per_race_cap=per_race_cap)
        # ★見送り通知 (ふくだ要望): 窓内で評価したが投票しないレースを1回だけ音声通知する。
        #   「動いてない」のか「評価して見送った」のか区別できるように。 notified_skips で
        #   毎パス再通知を防ぐ (オッズ変動で後に fund 可能になれば通常通り投票する)。
        if rs is None or not rs.legs:
            skipped.append((race_id, f"{label} fund 対象なし"))
            if live and notify_on_skip and race_id not in notified_skips:
                notify_skip(label, "買い目なし")
                notified_skips.append(race_id)
            continue
        if voted_yen + rs.total_yen > per_day_max_yen:
            skipped.append((race_id, f"{label} 日次キャップ超過 "
                            f"({voted_yen}+{rs.total_yen}>{per_day_max_yen})"))
            if live and notify_on_skip and race_id not in notified_skips:
                notify_skip(label, "日次予算上限")
                notified_skips.append(race_id)
            continue

        if verbose:
            specs = " ".join(build_bet_specs(race_id, rs))
            print(f"  🔵 {label} 締切{t['deadline'].strftime('%H:%M')} "
                  f"{len(rs.legs)}点 {rs.total_yen}円 (◎{rs.anchor_yen}+複合{rs.combo_yen}) → "
                  f"{'投票実行' if live else 'WOULD VOTE'}")
            print(f"     {specs}")

        res = vote_one_race_multi(day_dir, race_id, rs, live=live,
                                  login_timeout=login_timeout, per_race_cap=per_race_cap,
                                  per_day_remaining=max(0, per_day_max_yen - voted_yen))
        res["at"] = now.isoformat(timespec="seconds")
        res["label"] = label
        res["strategy"] = strategy
        res["sizing"] = sizing
        if rs.warnings:
            res["sizing_warnings"] = rs.warnings
        state["votes"][race_id] = res
        newly_voted.append((race_id, res))
        if res["exit_code"] == 0:
            voted_yen += res["amount"]
            state["consecutive_failures"] = 0
        elif res["exit_code"] in HALT_EXIT_CODES:
            state["halted"] = True
            state["halt_reason"] = (f"{label} runner exit={res['exit_code']} "
                                    f"(セッション切れ/想定外) → 当日停止")
            if verbose:
                print(f"  ⛔ {state['halt_reason']}", file=sys.stderr)
            break
        else:
            state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
            if state["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                state["halted"] = True
                state["halt_reason"] = (f"連続失敗 {state['consecutive_failures']} 回 "
                                        f"(直近 {label} exit={res['exit_code']}) → 当日停止")
                if verbose:
                    print(f"  ⛔ {state['halt_reason']}", file=sys.stderr)
                break

    save_state(sp, state)
    if verbose:
        print(f"[bettype] 今パス: 投票{len(newly_voted)}件 / "
              f"skip{len(skipped)}件 / halted={state.get('halted')}")
        for rid, reason in skipped:
            print(f"    skip {rid}: {reason}")
    return {"voted": newly_voted, "skipped": skipped,
            "halted": state.get("halted", False)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--date", default="today")
    p.add_argument("--now", default=None, help="擬似時刻 HH:MM (テスト用)")
    p.add_argument("--confirm", action="store_true", help="実 click (live)")
    p.add_argument("--i-understand-live", action="store_true",
                   help="実弾を承認 (--confirm と両方必須 = 金経路の二重フラグ)")
    p.add_argument("--halt", action="store_true",
                   help="当日 state を halted=True にして以降のパスを停止")
    p.add_argument("--halt-reason", default="manual_stop")
    p.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=STRATEGIES)
    p.add_argument("--ev-floor", type=float, default=DEFAULT_EV_FLOOR)
    p.add_argument("--sizing", default=DEFAULT_SIZER, choices=tuple(SIZERS))
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    p.add_argument("--per-day-max-yen", type=int, default=DEFAULT_BETTYPE_PER_DAY_MAX_YEN)
    p.add_argument("--login-timeout", type=int, default=180)
    p.add_argument("--no-skip-notify", action="store_true",
                   help="見送り時の音声通知を抑止 (既定は通知ON)")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    live = bool(args.confirm)

    if args.halt:
        date_str = resolve_date(args.date)
        out_live = halt_day(date_str, live=True, reason=args.halt_reason)
        out_dry = halt_day(date_str, live=False, reason=args.halt_reason)
        print(f"[bettype] HALTED {date_str}: live={out_live['halt_reason']} "
              f"(already={out_live['already_halted']}) / dry={out_dry['already_halted']}")
        return 0

    if live and not args.i_understand_live:
        print("[bettype] --confirm には --i-understand-live も必須 (実弾の二重フラグ)。 中止。",
              file=sys.stderr)
        return 2
    date_str = resolve_date(args.date)
    now = parse_now(args.now, date_str)
    out = run_pass(
        date_str, now=now, live=live, bankroll=args.bankroll, strategy=args.strategy,
        ev_floor=args.ev_floor, sizing=args.sizing, per_day_max_yen=args.per_day_max_yen,
        login_timeout=args.login_timeout, notify_on_skip=not args.no_skip_notify,
        verbose=not args.quiet)
    return 3 if out.get("halted") else 0


if __name__ == "__main__":
    sys.exit(main())

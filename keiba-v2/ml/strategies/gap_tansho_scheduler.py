#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gap5単勝エッジ 当日スケジューラ (Session 176 / gap単勝を最初の収益源として本投票化)

freebudget_scheduler の安全機構 (timing/lock/state/halt/鮮度/連続失敗) と bettype_scheduler の
投票経路 (runner --bet 群) を ★import 流用★ し、選定・サイジングだけを gap単勝に差し替えた
専用スケジューラ。器 (TARGET/IPAT 実行) は共有、★口座 (state/lock/cage/bankroll) は隔離★。

bettype_scheduler (combo) とは別ファイル state/lock = ★完全分離★ (manual-auto-bet-coexistence の
檻リスク回避)。combo は止め、bettype_auto.bat の向き先をこのスケジューラに替える。

差し替えは 2 点のみ (安全ロジックは freebudget/bettype と同一):
  ① 選定+サイジング = gap_tansho_live.size_gap_race (select_gap_tansho broad → 残高×比率)
  ② bankroll = gap 口座残高 (初期30万 + 過去実現PnL・当日開始時で凍結)・日次cage = 残高×day_pct%

★master switch★: config.json settings.gap_enabled が True のときだけ投票する (web で ON)。
  False (既定) なら静かに no-op = bat を切り替えても ふくだが web で有効化するまで1円も賭けない。

CLI:
    python -m ml.strategies.gap_tansho_scheduler --date today                       # dry
    python -m ml.strategies.gap_tansho_scheduler --date 2026-06-28 --now 14:50      # 時刻擬似
    python -m ml.strategies.gap_tansho_scheduler --date today --confirm --i-understand-live  # 実弾
    python -m ml.strategies.gap_tansho_scheduler --date today --halt                # 当日停止
    python -m ml.strategies.gap_tansho_scheduler --date today --settle              # 夜: 実払戻で台帳更新
    python -m ml.strategies.gap_tansho_scheduler --report                           # 口座サマリ
"""
from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ★freebudget の安全機構を import 流用 (戦略中立・100% 再利用)★
from ml.strategies.freebudget_scheduler import (  # noqa: E402
    HALT_EXIT_CODES,
    MAX_CONSECUTIVE_FAILURES,
    ODDS_STALE_MIN,
    acquire_lock,
    release_lock,
    save_state,
    load_state,
    read_per_race_cap,
    parse_now,
)
from ml.strategies.freebudget_race import load_post_times, race_timing  # noqa: E402
from ml.strategies.freebudget import resolve_date  # noqa: E402
from ml.strategies.day_recovery import compute_recovery  # noqa: E402
# ★bettype の投票経路 (runner --bet 群) を流用 = 投票/通知は同一実装★
from ml.strategies.bettype_scheduler import (  # noqa: E402
    build_bet_specs, vote_one_race_multi, notify_skip,
)
from ml.strategies import gap_tansho_live as gl  # noqa: E402
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402

DEFAULT_LOGIN_TIMEOUT = 180


# ---------------------------------------------------------------------------
# state / lock (gap 専用ファイル = combo/freebudget と衝突しない)
# ---------------------------------------------------------------------------

def lock_path(day_dir: Path) -> Path:
    return Path(day_dir) / "gap_tansho_scheduler.lock"


def state_path(day_dir: Path, *, live: bool) -> Path:
    name = "gap_tansho_scheduler_state.json" if live \
        else "gap_tansho_scheduler_state_dryrun.json"
    return Path(day_dir) / name


def halt_day(date_str: str, *, live: bool, reason: str) -> dict:
    """当日の gap state に halted=True (web/CLI「停止」)。 combo/freebudget state は汚さない。"""
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


def resume_day(date_str: str, *, live: bool) -> dict:
    """当日の gap state の halted を解除して再開 (halt の対・consecutive_failures も 0 に戻す)。"""
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    sp = state_path(day_dir, live=live)
    if not sp.exists():
        return {"resumed": False, "was_halted": False, "state_path": str(sp),
                "note": "state なし (未投票/非開催) → 再開対象なし"}
    state = load_state(sp, date_str, "live" if live else "dry-run")
    was_halted = bool(state.get("halted"))
    prev_reason = state.get("halt_reason")
    state["halted"] = False
    state["halt_reason"] = None
    state["halted_at"] = None
    state["consecutive_failures"] = 0
    state["resumed_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(sp, state)
    return {"resumed": True, "was_halted": was_halted, "prev_halt_reason": prev_reason,
            "state_path": str(sp)}


# ---------------------------------------------------------------------------
# パス実行
# ---------------------------------------------------------------------------

def run_pass(date_str: str, *, now: datetime, live: bool,
             login_timeout: int = DEFAULT_LOGIN_TIMEOUT,
             notify_on_skip: bool = True, verbose: bool = True) -> dict:
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    lp = lock_path(day_dir)
    if not acquire_lock(lp):
        if verbose:
            print(f"[gap] 別パスが実行中 (lock={lp.name}) → 何もしない", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False, "locked_out": True}
    try:
        return _run_pass_inner(date_str, day_dir, now=now, live=live,
                               login_timeout=login_timeout,
                               notify_on_skip=notify_on_skip, verbose=verbose)
    finally:
        release_lock(lp)


def _run_pass_inner(date_str: str, day_dir: Path, *, now: datetime, live: bool,
                    login_timeout: int, notify_on_skip: bool, verbose: bool) -> dict:
    # ★master switch★: web の gap_enabled が False なら静かに no-op (bat 切替後も賭けない)。
    cfg = gl.read_gap_config()
    if not cfg.enabled:
        if verbose:
            print(f"[gap] gap_enabled=False ({cfg.source}) → 無効。 web の資金管理で有効化要",
                  file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False, "disabled": True}

    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print(f"[gap] predictions.json なし → 何もしない", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False}

    post_times = load_post_times(day_dir, date_str=date_str)
    # per_race 上限 = runner の番人 (_check_per_race_limits) と同値 (config per_race_max_yen)。
    #   複数点レースはこの cap で fit_legs_to_cap し runner 拒否を回避する。
    per_race_cap = read_per_race_cap()

    sp = state_path(day_dir, live=live)
    state = load_state(sp, date_str, "live" if live else "dry-run")
    if state.get("halted"):
        if verbose:
            print(f"[gap] HALTED ({state.get('halt_reason')}) — 当日は停止中。 手動確認が必要",
                  file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": True}

    # ★bankroll を当日開始時に1回だけ凍結 (memory: 更新は日次で可)★。 初期30万 + 過去実現PnL。
    #   日次cage = 残高 × day_pct% (gap 口座の暴走ガード・combo の per_day とは別)。
    if "gap_bankroll_yen" not in state:
        bal = gl.account_balance(cfg)
        state["gap_bankroll_yen"] = bal
        state["gap_bet_pct"] = cfg.bet_pct
        day_cap = int(bal * cfg.day_pct / 100 // 100 * 100)
        state["gap_day_cap_yen"] = max(gl.MIN_BET_YEN, day_cap)
        state["gap_bankroll_source"] = cfg.source
    bankroll = int(state["gap_bankroll_yen"])
    bet_pct = float(state.get("gap_bet_pct", cfg.bet_pct))
    day_cap = int(state["gap_day_cap_yen"])

    voted_yen = sum(v.get("amount", 0) for v in state["votes"].values()
                    if v.get("exit_code") == 0)
    # 日次ゲートは「収支 (純損失) ベース」(combo と同じ・day_recovery 流用)。 回収分は上限に余裕。
    rec = compute_recovery(date_str, state["votes"])
    recovered_yen = int(rec.get("recovered_yen", 0) or 0)
    state["recovered_yen"] = recovered_yen
    notified_skips = state.setdefault("notified_skips", [])
    skip_reasons = state.setdefault("skips", {})

    races = predictions.get("races", []) or []
    pred_by_id = {str(r.get("race_id")): r for r in races if r.get("race_id")}
    newly_voted, skipped = [], []
    vb_ref = predictions.get("vb_refreshed_at")

    if verbose:
        print(f"[gap] {date_str} now={now.strftime('%H:%M')} "
              f"mode={'LIVE' if live else 'dry-run'} bankroll={bankroll:,} "
              f"1点={gl.stake_for(bankroll, bet_pct)}({bet_pct}%) odds={vb_ref} "
              f"レース={len(pred_by_id)} 既投票={voted_yen} 回収={recovered_yen} "
              f"純投資={voted_yen - recovered_yen}/日次cap{day_cap}")

    # オッズ鮮度ガード (freebudget と同一: live のみ作動)
    if live and vb_ref:
        try:
            age_min = (now - datetime.fromisoformat(vb_ref)).total_seconds() / 60.0
            if age_min > ODDS_STALE_MIN:
                msg = (f"オッズ鮮度 {age_min:.0f}分 > {ODDS_STALE_MIN}分 → このパスは投票せずスキップ")
                if verbose:
                    print(f"[gap] ⚠ {msg}", file=sys.stderr)
                save_state(sp, state)
                return {"voted": [], "skipped": [("*", msg)], "halted": False}
        except ValueError:
            pass

    for race_id in sorted(pred_by_id):
        if race_id in state["votes"] and state["votes"][race_id].get("exit_code") == 0:
            continue
        pr = pred_by_id[race_id]
        st = post_times.get(race_id, "")
        t = race_timing(date_str, st, now)
        label = f"{pr.get('venue_name') or '?'} {pr.get('race_number') or '?'}R"

        if t["deadline"] is None:
            skipped.append((race_id, "発走時刻不明"))
            continue
        if now < t["vote_at"]:
            continue
        if now > t["deadline"]:
            if race_id not in state["votes"]:
                skipped.append((race_id, f"{label} 締切超過 (発走{st})"))
                state["votes"][race_id] = {"mode": "missed", "amount": 0, "bet_count": 0,
                                           "exit_code": -1, "note": "deadline passed",
                                           "at": now.isoformat(timespec="seconds")}
            continue

        # --- ウィンドウ内: gap単勝候補をサイジング ---
        rs = gl.size_gap_race(pr, balance=bankroll, bet_pct=bet_pct,
                              per_race_cap=per_race_cap)
        if rs is None or not rs.legs:
            # gap 候補なしは ★通常 (大半のレース)★ なので通知しない (ノイズ回避)。
            continue

        # 日次キャップは ★純投資 (純損失) ベース★ (voted_yen はパス内で増える・recovered は頭で凍結)。
        net_spent = voted_yen - recovered_yen
        if net_spent + rs.total_yen > day_cap:
            skipped.append((race_id, f"{label} 日次cap超過 "
                            f"(純投資{net_spent}+{rs.total_yen}>{day_cap})"))
            if live and notify_on_skip and race_id not in notified_skips:
                notify_skip(label, "gap日次予算上限")
                notified_skips.append(race_id)
            continue

        if verbose:
            specs = " ".join(build_bet_specs(race_id, rs))
            print(f"  🔵 {label} 締切{t['deadline'].strftime('%H:%M')} "
                  f"{len(rs.legs)}点 {rs.total_yen}円 → {'投票実行' if live else 'WOULD VOTE'}")
            print(f"     {specs}")

        res = vote_one_race_multi(day_dir, race_id, rs, live=live,
                                  login_timeout=login_timeout, per_race_cap=per_race_cap,
                                  per_day_remaining=max(0, day_cap - net_spent))
        res["at"] = now.isoformat(timespec="seconds")
        res["label"] = label
        res["sizing"] = "gap_tansho"
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

    for rid, reason in skipped:
        if rid != "*":
            skip_reasons[rid] = reason
    for rid, v in state["votes"].items():
        if v.get("exit_code") == 0:
            skip_reasons.pop(rid, None)

    state["voted_yen"] = voted_yen
    state["net_spent_yen"] = voted_yen - recovered_yen
    save_state(sp, state)
    if verbose:
        print(f"[gap] 今パス: 投票{len(newly_voted)}件 / skip{len(skipped)}件 / "
              f"halted={state.get('halted')}")
        for rid, reason in skipped:
            print(f"    skip {rid}: {reason}")
    return {"voted": newly_voted, "skipped": skipped, "halted": state.get("halted", False)}


# ---------------------------------------------------------------------------
# settle (夜): 当日 gap-live 実投票を実払戻で精算 → 台帳に蓄積 (= 翌日以降の残高)
# ---------------------------------------------------------------------------

def settle_day(date_str: str, *, live: bool = True) -> dict:
    """当日の gap state の実投票を haraimodoshi で精算し gap-live 台帳に記録 (冪等・確定後再実行可)。"""
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    sp = state_path(day_dir, live=live)
    if not sp.exists():
        return {"date": date_str, "skip": "state なし (未投票/非開催)"}
    state = load_state(sp, date_str, "live" if live else "dry-run")
    day = gl.settle_gap_day(date_str, state.get("votes", {}))
    return {"date": date_str, **day}


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
    p.add_argument("--halt", action="store_true", help="当日 state を halted=True に")
    p.add_argument("--halt-reason", default="manual_stop")
    p.add_argument("--resume", action="store_true", help="当日 state の halted を解除")
    p.add_argument("--settle", action="store_true",
                   help="夜: 当日 gap実投票を実払戻で精算し台帳更新 (残高に反映)")
    p.add_argument("--report", action="store_true", help="gap 口座サマリを表示")
    p.add_argument("--login-timeout", type=int, default=DEFAULT_LOGIN_TIMEOUT)
    p.add_argument("--no-skip-notify", action="store_true")
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

    if args.report:
        r = gl.report()
        print(f"\n=== gap単勝 本投票 口座サマリ ===")
        print(f"  enabled={r['enabled']} 初期{r['initial_bankroll_yen']:,}円 "
              f"1点{r['bet_pct']}% 日次cap{r['day_pct']}%")
        print(f"  残高 {r['balance']:,}円 (実現PnL {r['pnl']:+,}円) / "
              f"{r['settled_days']}開催 {r['n_bet']}本 / ROI {r['roi']:.1f}% / 的中 {r['hit']:.1f}%")
        for d, v in r["days"].items():
            print(f"    {d}: {v['n']}本 cost{v['cost']} payout{v['payout']} "
                  f"pnl{v['pnl']:+} hit{v['hit']}")
        return 0

    live = bool(args.confirm)

    if args.halt:
        date_str = resolve_date(args.date)
        out_live = halt_day(date_str, live=True, reason=args.halt_reason)
        out_dry = halt_day(date_str, live=False, reason=args.halt_reason)
        print(f"[gap] HALTED {date_str}: live(already={out_live['already_halted']}) / "
              f"dry(already={out_dry['already_halted']})")
        return 0

    if args.resume:
        date_str = resolve_date(args.date)
        out_live = resume_day(date_str, live=True)
        out_dry = resume_day(date_str, live=False)
        print(f"[gap] RESUMED {date_str}: live(was_halted={out_live.get('was_halted')}) / "
              f"dry(was_halted={out_dry.get('was_halted')})")
        return 0

    if args.settle:
        date_str = resolve_date(args.date)
        print(f"[gap] settle {date_str}:", settle_day(date_str, live=True))
        return 0

    if live and not args.i_understand_live:
        print("[gap] --confirm には --i-understand-live も必須 (実弾の二重フラグ)。 中止。",
              file=sys.stderr)
        return 2
    date_str = resolve_date(args.date)
    now = parse_now(args.now, date_str)
    out = run_pass(date_str, now=now, live=live, login_timeout=args.login_timeout,
                   notify_on_skip=not args.no_skip_notify, verbose=not args.quiet)
    return 3 if out.get("halted") else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""スリーブ・オーケストレーター (Session 176 / §8-1)。

複数の買い目スリーブ (sleeves/registry) を ★並行に買い目生成 → 集約 → 投票は1本化★ する当日
スケジューラ。freebudget の安全機構と bettype の投票経路を import 流用し (gap_tansho_scheduler と
同じパターン)、選定/サイズを「全 enabled スリーブのループ＋B別建てマージ」に一般化する。

★§8-1 の不変条件★: enabled が gap_tansho 1本だけのとき、現 `gap_tansho_scheduler` と
**買い目・amount・bet_spec が完全一致** (挙動不変)。検証 = `ml/analyze/verify_sleeve_parity.py`。

予算 (§5・§11): スリーブ別 day_cap (隔離残高×day_pct%) ＋ 全体 day_cap (専用キー or Σ)。純損失
ベース (回収差引)。全体cap超過時は ★登録順=優先度の逆順 (低優先から) で決定的に脚を落とす★ (§11-3)。
マージ = B別建て (§4・ふくだ確定): 脚にスリーブkeyタグ、settle は当該スリーブ分にフィルタして精算。

CLI:
    python -m ml.strategies.sleeve_orchestrator --date today                    # dry
    python -m ml.strategies.sleeve_orchestrator --date 2026-06-28 --now 14:50   # 時刻擬似
    python -m ml.strategies.sleeve_orchestrator --date today --confirm --i-understand-live
    python -m ml.strategies.sleeve_orchestrator --date today --halt
    python -m ml.strategies.sleeve_orchestrator --date today --settle           # 夜: スリーブ別精算
    python -m ml.strategies.sleeve_orchestrator --report
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.freebudget_scheduler import (  # noqa: E402
    HALT_EXIT_CODES, MAX_CONSECUTIVE_FAILURES, ODDS_STALE_MIN,
    acquire_lock, release_lock, save_state, load_state, parse_now,
)
from ml.strategies.freebudget_race import load_post_times, race_timing  # noqa: E402
from ml.strategies.freebudget import resolve_date  # noqa: E402
from ml.strategies.day_recovery import compute_recovery  # noqa: E402
from ml.strategies.bettype_scheduler import (  # noqa: E402
    build_bet_specs, vote_one_race_multi, notify_skip,
)
from ml.strategies.bettype_sizing import RaceSizing, SizedLeg, MIN_BET_YEN  # noqa: E402
from ml.strategies.sleeves import enabled_sleeves, get_sleeve, SLEEVES  # noqa: E402
from ml.strategies import gap_tansho_live as gl  # noqa: E402 (config 直読み用)
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402

DEFAULT_LOGIN_TIMEOUT = 180


# ---------------------------------------------------------------------------
# state / lock (orchestrator 専用ファイル)
# ---------------------------------------------------------------------------

def lock_path(day_dir: Path) -> Path:
    return Path(day_dir) / "sleeve_orchestrator.lock"


def state_path(day_dir: Path, *, live: bool) -> Path:
    name = "sleeve_orchestrator_state.json" if live \
        else "sleeve_orchestrator_state_dryrun.json"
    return Path(day_dir) / name


# ---------------------------------------------------------------------------
# config: 全体 day_cap (専用キー sleeve_total_day_cap_yen・無ければ Σ sleeve day_cap)
# ---------------------------------------------------------------------------

def read_total_day_cap() -> int:
    """config.json settings.sleeve_total_day_cap_yen (専用キー・ハード上限)。 無ければ 0 (= Σ にフォールバック)。"""
    try:
        p = gl.BANKROLL_CONFIG_PATH
        if not p.exists():
            return 0
        s = (json.loads(p.read_text(encoding="utf-8")).get("settings") or {})
        return int(s.get("sleeve_total_day_cap_yen", 0) or 0)
    except (OSError, ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# config: レース合算 per_race cap (案A・二段化の合算上限。 ★runner per_race_max_yen と一致必須★)
# ---------------------------------------------------------------------------

def _settings() -> dict:
    """bankroll/config.json の settings dict (無ければ空)。"""
    try:
        p = gl.BANKROLL_CONFIG_PATH
        if not p.exists():
            return {}
        return (json.loads(p.read_text(encoding="utf-8")).get("settings") or {})
    except (OSError, ValueError, TypeError):
        return {}


def read_per_race_max_yen() -> int:
    """runner `_check_per_race_limits` が直読みする per_race_max_yen を ★同じ条件で★ 返す。

    runner は ★limit_mode=='absolute' のときのみ★ per_race_max_yen を番人にする
    (`runner._read_bankroll_limits`)。 それ以外は 0 (= runner 無制限)。 ★shobu 換算の
    read_per_race_cap (= base×勝負レート) は combo 用なので使わない★。 これにより orchestrator の
    合算cap が runner の番人と「同じ値・同じ条件」で一致する (案A の合算上限=runner一致)。
    """
    s = _settings()
    if s.get("limit_mode") != "absolute":
        return 0
    try:
        return int(s.get("per_race_max_yen", 0) or 0)
    except (ValueError, TypeError):
        return 0


def resolve_per_race_cap() -> tuple:
    """レース合算 per_race cap を解決する (案A 二段化の ★合算上限★・§11-7-7/§11-8)。

    戻り: (combined_cap, ok, source)。
      combined_cap = 専用キー sleeve_per_race_cap_yen ・無ければ runner per_race_max_yen。
      ok = ★合算cap が runner の番人(per_race_max_yen)と一致★ なら True。 専用キーを立てたのに
           per_race_max_yen と食い違うときだけ False (★fail-safe: 投票しない★)。 orchestrator が
           size する上限と runner が弾く上限が食い違うと merge 溢れ→runner exit5→day-halt するため
           (§11-8 実害バグ)。 専用キー未設定なら per_race_max_yen をそのまま採用 (不一致は起きない)。
    """
    runner_cap = read_per_race_max_yen()                   # runner の番人 (absolute 時のみ>0)
    try:
        sleeve_cap = int(_settings().get("sleeve_per_race_cap_yen", 0) or 0)
    except (ValueError, TypeError):
        sleeve_cap = 0
    if sleeve_cap > 0 and runner_cap > 0 and sleeve_cap != runner_cap:
        # ★保守側に倒す★: 小さい方を採るが ok=False で投票自体を止める (賭けすぎを作らない)。
        return (min(sleeve_cap, runner_cap), False,
                f"不一致 sleeve_per_race_cap_yen={sleeve_cap} != per_race_max_yen={runner_cap} "
                f"(web 資金管理で両者を一致させること)")
    combined = sleeve_cap if sleeve_cap > 0 else runner_cap
    src = ("専用キー sleeve_per_race_cap_yen" if sleeve_cap > 0
           else "per_race_max_yen (専用キー未設定・runner と同値)")
    return (combined, True, src)


# ---------------------------------------------------------------------------
# 帰属ヘルパ (B別建て): votes を スリーブ key でフィルタ / スリーブ別 voted 集計
# ---------------------------------------------------------------------------

def _legs_of(v: dict) -> list:
    return v.get("legs") or []


def filter_votes_for_sleeve(votes: dict, key: str) -> dict:
    """exit_code==0 の vote から ★当該スリーブの脚だけ★ を残した votes を作る (settle/recovery 用)。

    各 vote の legs を sleeve==key で絞り、amount を絞った脚の合計に置換。脚が残らない vote は除外。
    """
    out = {}
    for rid, v in (votes or {}).items():
        if not isinstance(v, dict) or v.get("exit_code") != 0:
            continue
        legs = [lg for lg in _legs_of(v) if lg.get("sleeve") == key]
        if not legs:
            continue
        out[rid] = {**v, "legs": legs, "amount": sum(int(lg.get("amount", 0) or 0) for lg in legs)}
    return out


def sleeve_voted_yen(votes: dict, key: str) -> int:
    """exit_code==0 の vote の脚のうち sleeve==key の amount 合計。"""
    return sum(int(lg.get("amount", 0) or 0)
               for v in (votes or {}).values()
               if isinstance(v, dict) and v.get("exit_code") == 0
               for lg in _legs_of(v) if lg.get("sleeve") == key)


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
            print(f"[orch] 別パスが実行中 (lock={lp.name}) → 何もしない", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False, "locked_out": True}
    try:
        return _run_pass_inner(date_str, day_dir, now=now, live=live,
                               login_timeout=login_timeout,
                               notify_on_skip=notify_on_skip, verbose=verbose)
    finally:
        release_lock(lp)


def _run_pass_inner(date_str: str, day_dir: Path, *, now: datetime, live: bool,
                    login_timeout: int, notify_on_skip: bool, verbose: bool) -> dict:
    sleeves = enabled_sleeves()
    if not sleeves:
        if verbose:
            print("[orch] 有効スリーブなし (全 <key>_enabled=False) → no-op。 web で有効化要",
                  file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False, "disabled": True}

    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print("[orch] predictions.json なし → 何もしない", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False}

    post_times = load_post_times(day_dir, date_str=date_str)
    # ★案A 合算上限★: orchestrator が merge を収める per_race cap (= runner 番人と一致必須)。
    per_race_cap, cap_ok, cap_src = resolve_per_race_cap()
    if not cap_ok:
        # ★fail-safe★: size 上限と runner の番人が食い違う → 投票せずスキップ (賭けすぎを作らない)。
        if verbose:
            print(f"[orch] ⛔ per_race cap {cap_src} → ★このパスは投票しない★", file=sys.stderr)
        return {"voted": [], "skipped": [("*", f"per_race cap 不整合: {cap_src}")],
                "halted": False, "cap_mismatch": True}

    sp = state_path(day_dir, live=live)
    state = load_state(sp, date_str, "live" if live else "dry-run")
    if state.get("halted"):
        if verbose:
            print(f"[orch] HALTED ({state.get('halt_reason')}) — 当日停止中。 手動確認要",
                  file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": True}

    # ★当日開始時に各スリーブの凍結スナップショット + 全体cap を凍結 (日次・gap と同パターン)★
    sl_state = state.setdefault("sleeves", {})
    for s in sleeves:
        if s.key not in sl_state:
            sl_state[s.key] = {"snapshot": s.freeze(per_race_cap=per_race_cap)}
    if "total_day_cap_yen" not in state:
        total_cfg = read_total_day_cap()
        sum_caps = sum(sl_state[s.key]["snapshot"]["day_cap"] for s in sleeves)
        # 専用キーがあればそれをハード上限、無ければ Σ sleeve day_cap (単一スリーブ時 = そのスリーブの cap)。
        state["total_day_cap_yen"] = total_cfg if total_cfg > 0 else sum_caps
        state["total_day_cap_source"] = ("専用キー sleeve_total_day_cap_yen"
                                         if total_cfg > 0 else "Σ sleeve day_cap (専用キー未設定)")
    total_day_cap = int(state["total_day_cap_yen"])

    votes = state.setdefault("votes", {})
    notified_skips = state.setdefault("notified_skips", [])
    skip_reasons = state.setdefault("skips", {})

    # 純損失ベースの予算 (全体 + スリーブ別) を ★パス頭で凍結★ (recovered はパス内不変・gap と同)
    total_voted = sum(v.get("amount", 0) for v in votes.values() if v.get("exit_code") == 0)
    total_recovered = int(compute_recovery(date_str, votes).get("recovered_yen", 0) or 0)
    sl_voted = {s.key: sleeve_voted_yen(votes, s.key) for s in sleeves}
    sl_recovered = {s.key: int(compute_recovery(date_str, filter_votes_for_sleeve(votes, s.key))
                               .get("recovered_yen", 0) or 0) for s in sleeves}
    state["recovered_yen"] = total_recovered

    races = predictions.get("races", []) or []
    pred_by_id = {str(r.get("race_id")): r for r in races if r.get("race_id")}
    newly_voted, skipped = [], []
    vb_ref = predictions.get("vb_refreshed_at")

    if verbose:
        names = ", ".join(s.key for s in sleeves)
        print(f"[orch] {date_str} now={now.strftime('%H:%M')} "
              f"mode={'LIVE' if live else 'dry-run'} sleeves=[{names}] "
              f"odds={vb_ref} レース={len(pred_by_id)} "
              f"既投票={total_voted} 回収={total_recovered} "
              f"純投資={total_voted - total_recovered}/全体cap{total_day_cap} "
              f"レース合算cap{per_race_cap}({cap_src})")

    # オッズ鮮度ガード (共有・live のみ)
    if live and vb_ref:
        try:
            age_min = (now - datetime.fromisoformat(vb_ref)).total_seconds() / 60.0
            if age_min > ODDS_STALE_MIN:
                msg = f"オッズ鮮度 {age_min:.0f}分 > {ODDS_STALE_MIN}分 → このパス投票せずスキップ"
                if verbose:
                    print(f"[orch] ⚠ {msg}", file=sys.stderr)
                save_state(sp, state)
                return {"voted": [], "skipped": [("*", msg)], "halted": False}
        except ValueError:
            pass

    for race_id in sorted(pred_by_id):
        if race_id in votes and votes[race_id].get("exit_code") == 0:
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
            if race_id not in votes:
                skipped.append((race_id, f"{label} 締切超過 (発走{st})"))
                votes[race_id] = {"mode": "missed", "amount": 0, "bet_count": 0,
                                  "exit_code": -1, "note": "deadline passed",
                                  "at": now.isoformat(timespec="seconds")}
            continue

        # --- ウィンドウ内: 全スリーブで買い目生成 → スリーブ別cage → 全体cap → マージ ---
        per_sleeve_rs = {}
        for s in sleeves:
            rs = s.size_race(pr, sl_state[s.key]["snapshot"])
            if rs is None or not rs.legs:
                continue
            # スリーブ別 day_cap (純損失ベース)
            sl_net = sl_voted[s.key] - sl_recovered[s.key]
            cap = int(sl_state[s.key]["snapshot"]["day_cap"])
            if sl_net + rs.total_yen > cap:
                skip_reasons[f"{race_id}#{s.key}"] = (
                    f"{label} {s.key} スリーブ日次cap超過 (純投資{sl_net}+{rs.total_yen}>{cap})")
                continue
            per_sleeve_rs[s.key] = rs

        if not per_sleeve_rs:
            continue  # 候補なし or 全スリーブ cap → 静かにスキップ (gap と同じ・通知しない)

        # ★案A 二段化★: 全体cap(日次・純投資) ＋ レース合算cap(per_race) を ★登録順=優先度の高い順に
        #   決定的に★ 満たすスリーブだけ残す。 超過するスリーブは ★レース単位で丸ごと見送り★
        #   (按分しない＝§11-1c 破産ガード維持・§11-3 固定順・§11-8 案A)。 各スリーブは自分の脚を
        #   既に per_race_cap で fit 済 (スリーブ別上限) なので、 最優先スリーブが per_race_cap で
        #   落ちることはなく (running_race=0+rs≤cap)、 レース合算cap が落とすのは ★低優先の被り★ だけ。
        order = [s.key for s in sleeves if s.key in per_sleeve_rs]  # 高優先→低優先
        total_net = total_voted - total_recovered
        kept, running_day, running_race = [], total_net, 0
        for key in order:
            rs = per_sleeve_rs[key]
            over_day = running_day + rs.total_yen > total_day_cap
            over_race = per_race_cap > 0 and running_race + rs.total_yen > per_race_cap
            if over_day or over_race:
                why, lim, base = (("全体日次cap", total_day_cap, running_day) if over_day
                                  else ("レース合算cap", per_race_cap, running_race))
                skip_reasons[f"{race_id}#{key}"] = (
                    f"{label} {key} {why}超過 ({base}+{rs.total_yen}>{lim}) → レース丸ごと見送り")
                continue
            kept.append(key)
            running_day += rs.total_yen
            running_race += rs.total_yen
        if not kept:
            if live and notify_on_skip and race_id not in notified_skips:
                notify_skip(label, "日次予算上限")
                notified_skips.append(race_id)
            skipped.append((race_id, f"{label} 全体cap超過"))
            continue

        # マージ (B別建て): kept スリーブの脚を連結 (脚は size_race で sleeve タグ済)
        legs: list[SizedLeg] = []
        for key in kept:
            legs.extend(per_sleeve_rs[key].legs)
        total = sum(l.amount for l in legs)
        # ★防御ネット (最終層)★: 万一 merge 合計が合算cap を超えていたら ★固定順で末尾(低優先)スリーブを
        #   丸ごと落とす★ (按分しない＝§11-1c)。 上の loop で保証済のため通常は発火しないが、 将来
        #   per_race_cap を fit しないスリーブが入っても runner exit5→day-halt を構造的に防ぐ最終ガード。
        while per_race_cap > 0 and total > per_race_cap and len(kept) > 1:
            drop = kept.pop()
            legs = [l for l in legs if l.sleeve != drop]
            total = sum(l.amount for l in legs)
            skip_reasons[f"{race_id}#{drop}"] = (
                f"{label} {drop} 合算cap最終ガードで見送り (合計>{per_race_cap})")
        merged = RaceSizing(race_id=race_id, legs=legs, total_yen=total, anchor_yen=total,
                            combo_yen=0, per_race_cap=per_race_cap,
                            warnings=[f"sleeves={kept}"])

        if verbose:
            specs = " ".join(build_bet_specs(race_id, merged))
            print(f"  🔵 {label} 締切{t['deadline'].strftime('%H:%M')} "
                  f"{len(legs)}点 {total}円 sleeves={kept} → "
                  f"{'投票実行' if live else 'WOULD VOTE'}")
            print(f"     {specs}")

        res = vote_one_race_multi(day_dir, race_id, merged, live=live,
                                  login_timeout=login_timeout, per_race_cap=per_race_cap,
                                  per_day_remaining=max(0, total_day_cap - total_net))
        res["at"] = now.isoformat(timespec="seconds")
        res["label"] = label
        res["sleeves"] = kept
        votes[race_id] = res
        newly_voted.append((race_id, res))
        if res["exit_code"] == 0:
            total_voted += res["amount"]
            for key in kept:
                sl_voted[key] += sum(l.amount for l in per_sleeve_rs[key].legs)
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
    for rid, v in votes.items():
        if v.get("exit_code") == 0:
            skip_reasons.pop(rid, None)

    state["voted_yen"] = total_voted
    state["net_spent_yen"] = total_voted - total_recovered
    save_state(sp, state)
    if verbose:
        print(f"[orch] 今パス: 投票{len(newly_voted)}件 / skip{len(skipped)}件 / "
              f"halted={state.get('halted')}")
    return {"voted": newly_voted, "skipped": skipped, "halted": state.get("halted", False)}


# ---------------------------------------------------------------------------
# halt / resume / settle / report
# ---------------------------------------------------------------------------

def halt_day(date_str: str, *, live: bool, reason: str) -> dict:
    date_str = resolve_date(date_str)
    sp = state_path(date_dir_for(date_str), live=live)
    sp.parent.mkdir(parents=True, exist_ok=True)
    state = load_state(sp, date_str, "live" if live else "dry-run")
    already = bool(state.get("halted"))
    if not already:
        state["halted"] = True
        state["halt_reason"] = reason
        state["halted_at"] = datetime.now().isoformat(timespec="seconds")
    save_state(sp, state)
    return {"halted": True, "already_halted": already}


def resume_day(date_str: str, *, live: bool) -> dict:
    date_str = resolve_date(date_str)
    sp = state_path(date_dir_for(date_str), live=live)
    if not sp.exists():
        return {"resumed": False, "was_halted": False}
    state = load_state(sp, date_str, "live" if live else "dry-run")
    was = bool(state.get("halted"))
    state.update({"halted": False, "halt_reason": None, "halted_at": None,
                  "consecutive_failures": 0,
                  "resumed_at": datetime.now().isoformat(timespec="seconds")})
    save_state(sp, state)
    return {"resumed": True, "was_halted": was}


def settle_day(date_str: str, *, live: bool = True) -> dict:
    """各スリーブを ★当該スリーブ分の votes だけ★ で精算 (B別建て・二重計上なし)。"""
    date_str = resolve_date(date_str)
    sp = state_path(date_dir_for(date_str), live=live)
    if not sp.exists():
        return {"date": date_str, "skip": "state なし (未投票/非開催)"}
    state = load_state(sp, date_str, "live" if live else "dry-run")
    votes = state.get("votes", {})
    out = {}
    for key in SLEEVES:
        fv = filter_votes_for_sleeve(votes, key)
        if not fv:
            continue
        out[key] = get_sleeve(key).settle_day(date_str, fv)
    return {"date": date_str, "sleeves": out}


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default="today")
    ap.add_argument("--now", default=None)
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--i-understand-live", action="store_true")
    ap.add_argument("--halt", action="store_true")
    ap.add_argument("--halt-reason", default="manual_stop")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--settle", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--login-timeout", type=int, default=DEFAULT_LOGIN_TIMEOUT)
    ap.add_argument("--no-skip-notify", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.report:
        for key in SLEEVES:
            s = get_sleeve(key)
            print(f"[orch] sleeve {key}: enabled={s.is_enabled()} {s.display.label}")
        return 0

    live = bool(args.confirm)
    if args.halt:
        d = resolve_date(args.date)
        halt_day(d, live=True, reason=args.halt_reason)
        halt_day(d, live=False, reason=args.halt_reason)
        print(f"[orch] HALTED {d}")
        return 0
    if args.resume:
        d = resolve_date(args.date)
        rl = resume_day(d, live=True)
        resume_day(d, live=False)
        print(f"[orch] RESUMED {d} (was_halted={rl.get('was_halted')})")
        return 0
    if args.settle:
        print(f"[orch] settle:", settle_day(resolve_date(args.date), live=True))
        return 0
    if live and not args.i_understand_live:
        print("[orch] --confirm には --i-understand-live も必須。 中止。", file=sys.stderr)
        return 2
    d = resolve_date(args.date)
    out = run_pass(d, now=parse_now(args.now, d), live=live,
                   login_timeout=args.login_timeout,
                   notify_on_skip=not args.no_skip_notify, verbose=not args.quiet)
    return 3 if out.get("halted") else 0


if __name__ == "__main__":
    sys.exit(main())

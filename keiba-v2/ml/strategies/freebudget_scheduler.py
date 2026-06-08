#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Freebudget 当日スケジューラ (Session 135 / 「朝ON→各レース締切前に自動投票」)

単発パス方式 (vb_refresh と同思想)。 Task Scheduler から 1-2 分ごとに叩かれる想定。
各パスで「freebudget 候補のうち 投票ウィンドウ内 [投票時刻, 締切] かつ 未投票」 の
レースを投票し、 状態ファイルで冪等性 (二重投票防止) を担保する。

時刻定義 (ふくだ Session 135):
    締切     = 発走時刻 − 2 分
    投票推奨 = 締切 − 4 分 = 発走時刻 − 6 分
    投票ウィンドウ = [発走−6分, 発走−2分] の 4 分間

安全機構:
  - デフォルト DRY-RUN。 実弾は --confirm + --i-understand-live の二重フラグ必須
  - 状態ファイルで冪等 (同レース二重投票しない)
  - 日次累計キャップ (per_day_max_yen 到達で以後の投票を停止)
  - safe-fail: runner が exit 5/7/8 (セッション切れ/想定外ダイアログ/二重投票防止) を
    返したら halted=True にして当日それ以降の投票を全停止 (無人暴走防止)
  - 人ゲート 2 つは別レイヤで維持: ① IPAT 入金 (物理) ② arm (これを叩く判断)

CLI:
    # dry-run 単発パス (今どのレースがウィンドウ内か / 何を投票するか)
    python -m ml.strategies.freebudget_scheduler --date today

    # 時刻を擬似化して発火を検証 (3時間待たずにテスト)
    python -m ml.strategies.freebudget_scheduler --date 2026-05-30 --now 13:49

    # 実弾 (シズネレビュー後 / 武装後のみ)
    python -m ml.strategies.freebudget_scheduler --date today --confirm --i-understand-live

状態ファイル: <day_dir>/freebudget_scheduler_state[_dryrun].json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.freebudget import (  # noqa: E402
    DEFAULT_BANKROLL,
    DEFAULT_KELLY_FRACTION,
    DEFAULT_PER_BET_CAP_PCT,
    DEFAULT_PRESET,
    extract_freebudget_bets,
    resolve_date,
    write_freebudget_bets,
)
from ml.strategies.freebudget_race import (  # noqa: E402
    filter_result_by_race,
    load_post_times,
    race_timing,
)
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402

# runner が「無人で継続してはいけない」 系のエラーで返す exit code
HALT_EXIT_CODES = {5, 7, 8}      # 5=投票後セッション切れ / 7=起動/preflight NG / 8=直近切れ
DEFAULT_PER_DAY_MAX_YEN = 10000  # config.json と整合 (bankroll と同値で運用)

# シズネ Session 135 レビュー対応 (無人 arming 前提の安全機構)
LOCK_STALE_SEC = 600             # 🔴-1: ロックがこの秒数より古ければ stale (前パスのクラッシュ) とみなし上書き
MAX_CONSECUTIVE_FAILURES = 2     # 🔴-4: 連続失敗がこの回数で当日 halt (config consecutive_loss_limit 3 と整合的に厳しめ)
ODDS_STALE_MIN = 10              # 🟡-3: predictions.vb_refreshed_at がこの分を超えたら投票せずスキップ

# bankroll config (runner._read_bankroll_limits と同じパス・同じ意味)。
# runner を直 import すると GUI 依存 (pyautogui 等) を引くため、 config を軽量に直読みする。
BANKROLL_CONFIG_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "bankroll" / "config.json"


def read_per_race_cap() -> int:
    """config.json から per_race_max_yen を返す (limit_mode=absolute のときのみ)。

    取れない/無効なら 0 (= キャップ無し扱い)。 runner の _check_per_race_limits が
    config を直読みする正本だが、 scheduler 側でも同値を読んで ① 投票前に over-cap
    レースを skip (day-halt 回避) ② --max-yen を per_race で min キャップ (二次防御) する。
    """
    try:
        if not BANKROLL_CONFIG_PATH.exists():
            return 0
        cfg = json.loads(BANKROLL_CONFIG_PATH.read_text(encoding="utf-8"))
        settings = cfg.get("settings", {}) or {}
        if settings.get("limit_mode") != "absolute":
            return 0
        return int(settings.get("per_race_max_yen", 0) or 0)
    except (OSError, ValueError, TypeError):
        return 0


def read_day_budget() -> tuple[int, str]:
    """config.json の daily_start_balance_yen を「当日の投資額上限(=最大損失)」として返す。

    ふくだ運用ルール (Session 145): 資金管理メニューで「本日のスタート額(入金額)」を設定し、
    原則その額を入金する。 入金額 = その日に賭ける総額の上限 = 最大負け額。 これは入金という
    人間の行為そのものが安全弁になっている (残高を下げたい週は入金額=設定を下げるだけ)。

    朝に1回読んで凍結する (= 呼び出し側 run_pass が state["day_budget_yen"] に保存) ことで、
    午前の払戻で残高が増えても上限は動かず「最大損失=入金時点で確定」の性質を保つ。
    ★Kelly の賭け額 (bankroll) はここでは触らない (資金配分=別テーマ Session145 論点2)。

    戻り: (yen, source)。 daily_start_balance_yen が未設定/0/不正なら (0, "") を返し、
    呼び出し側は従来の per_day_max_yen (CLI/既定) にフォールバックする (後方互換)。
    """
    try:
        if not BANKROLL_CONFIG_PATH.exists():
            return 0, ""
        cfg = json.loads(BANKROLL_CONFIG_PATH.read_text(encoding="utf-8"))
        settings = cfg.get("settings", {}) or {}
        start = int(settings.get("daily_start_balance_yen", 0) or 0)
        if start <= 0:
            return 0, ""
        return start, f"本日のスタート額 {start:,}円 (入金額=日次上限)"
    except (OSError, ValueError, TypeError):
        return 0, ""


def lock_path(day_dir: Path) -> Path:
    return Path(day_dir) / "freebudget_scheduler.lock"


def acquire_lock(path: Path, *, stale_sec: int = LOCK_STALE_SEC) -> bool:
    """多重起動防止ロック (🔴-1)。 取得できれば True。

    Task Scheduler が前パスの投票サブプロセス (ログイン待ち最大180秒) 実行中に
    次パスを起動しても、 ロックがあれば即 return させて二重投票を防ぐ。
    前パスがクラッシュして残った stale ロック (stale_sec 超) は上書きする。
    """
    if path.exists():
        try:
            age = time.time() - path.stat().st_mtime
            if age < stale_sec:
                return False        # 別パスが実行中
        except OSError:
            return False
        # stale ロック → 上書き取得
    try:
        path.write_text(f"{os.getpid()} {datetime.now().isoformat(timespec='seconds')}",
                        encoding="utf-8")
        return True
    except OSError:
        return False


def release_lock(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def state_path(day_dir: Path, *, live: bool) -> Path:
    name = "freebudget_scheduler_state.json" if live \
        else "freebudget_scheduler_state_dryrun.json"
    return Path(day_dir) / name


def _fresh_state(date_str: str, mode: str) -> dict:
    return {"date": date_str, "mode": mode, "halted": False,
            "halt_reason": None, "consecutive_failures": 0, "votes": {}}


def load_state(path: Path, date_str: str, mode: str) -> dict:
    """状態ファイルを読む。 🔴-4(b): 破損時は静かに初期化せず halted=True にして人を呼ぶ。

    破損を握りつぶして真っさらな state で再開すると、 その日に投票済みのレースを
    全部もう一度投票する経路 (二重投票) になるため、 破損 = 危険シグナルとして停止する。
    """
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("consecutive_failures", 0)
            return data
        except (OSError, json.JSONDecodeError) as e:
            st = _fresh_state(date_str, mode)
            st["halted"] = True
            st["halt_reason"] = (f"状態ファイル破損 ({type(e).__name__}): {path.name} — "
                                 f"投票済みが不明のため自動継続せず停止。 手動確認要")
            return st
    return _fresh_state(date_str, mode)


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def parse_now(now_str: Optional[str], date_str: str) -> datetime:
    """--now 'HH:MM' を当日 datetime に。 未指定なら実時刻"""
    if not now_str:
        return datetime.now()
    y, mo, d = (int(x) for x in date_str.split("-"))
    hh, mm = (int(x) for x in now_str.split(":"))
    return datetime(y, mo, d, hh, mm)


def fit_result_to_cap(sub, cap: int, *, unit: int = 100):
    """over-cap の 1 レース結果を per_race cap 以内に ★按分 (比例縮小)★ する。
    (シズネ Session139 残課題② / ふくだ判断 Session140 = day-halt でも skip でもなく按分)。

    各 bet を total に対する比率 factor=cap/total で縮小し unit(100円)単位に floor、 最低 unit。
    floor+最低 unit でも cap を超える場合 (極端に多点) のみ ★低 win_ev 順に drop★ して収める。
    縮小のみ (amount は元値以下) なので per_bet_cap は決して超えない。 戻り: (新 result, info)。
    """
    total = sub.total_yen
    if cap <= 0 or total <= cap:
        return sub, {"before": total, "after": total, "scaled": False, "dropped": 0}
    factor = cap / total
    items = []  # [scaled_amount, win_ev, bet]
    for b in sub.bets:
        s = int((b.amount * factor) // unit * unit)
        s = max(unit, s)                       # 最低 1 単位 (100円)
        items.append([s, (b.win_ev or 0.0), b])
    cur = sum(s for s, _, _ in items)
    if cur > cap:                              # 最低 unit 制約で超過 → 低EV順に drop
        for it in sorted(items, key=lambda x: x[1]):   # win_ev 昇順
            if cur <= cap:
                break
            cur -= it[0]
            it[0] = 0
    new_bets = [dc_replace(b, amount=s) for s, _, b in items if s > 0]
    new_total = sum(b.amount for b in new_bets)
    dropped = len(sub.bets) - len(new_bets)
    new_sub = dc_replace(sub, bets=new_bets, total_yen=new_total,
                         n_funded=len(new_bets),
                         n_truncated=sub.n_truncated + dropped)
    return new_sub, {"before": total, "after": new_total, "scaled": True,
                     "dropped": dropped}


def vote_one_race(day_dir: Path, race_id: str, sub_result, *,
                  live: bool, login_timeout: int = 180,
                  per_race_cap: int = 0) -> dict:
    """1 レースを投票 (live) または投票予定をログ (dry-run)。 結果 dict を返す"""
    umaban = [b.umaban for b in sub_result.bets]
    amount = sub_result.total_yen
    if not live:
        return {"mode": "dry-run", "amount": amount, "umaban": umaban,
                "exit_code": 0, "note": "WOULD VOTE (dry-run)"}

    # live: filtered JSON を書いて runner --confirm をサブプロセス起動 (テスト済経路)
    out = write_freebudget_bets(day_dir, sub_result,
                                filename=f"freebudget_bets_{race_id}.json")
    # 🔴-2 + 🟡-1 (Session135): このレースの期待値 (再計算後の sub.total_yen / 件数) を
    #   --max-yen / --max-bets で渡す = 「想定外の上乗せが起きたら reject」 の二次確認
    #   (leftover/idempotency ガード)。 投票ダイアログは「どのレースか」 を露出しない
    #   (Session 135 実機確認) ため、 買い目残り (TARGET 警告) で件数/金額が増えたら弾く。
    # シズネ Session139 残課題①対応 (Session140): --max-yen を per_race_max_yen で min
    #   キャップする = ダイアログ層でも per_race 上限を独立に効かせる二次防御。 通常 amount
    #   は per_race 以下 (scheduler 側が over-cap レースを事前 skip する) ので min=amount で
    #   挙動不変。 per_race ハードキャップの正本は依然 runner の _check_per_race_limits。
    max_yen = min(amount, per_race_cap) if per_race_cap > 0 else amount
    cmd = [sys.executable, "-m", "ml.target_clicker.runner",
           "--from-json", str(out), "--login-timeout", str(login_timeout),
           "--max-yen", str(max_yen), "--max-bets", str(len(sub_result.bets)),
           "--confirm"]
    proc = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[2]))
    return {"mode": "live", "amount": amount, "umaban": umaban,
            "exit_code": proc.returncode,
            "note": "voted" if proc.returncode == 0 else "vote error"}


def run_pass(date_str: str, *, now: datetime, live: bool,
             bankroll: int, kelly_fraction: float, per_bet_cap_pct: float,
             preset: str, per_day_max_yen: int, login_timeout: int,
             verbose: bool = True) -> dict:
    """1 パス実行。 🔴-1: 多重起動ロックで囲い、 同時実行 (前パスの投票サブプロセス
    実行中に次パスが起動) による二重投票を防ぐ。"""
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    lp = lock_path(day_dir)
    if not acquire_lock(lp):
        if verbose:
            print(f"[scheduler] 別パスが実行中 (lock={lp.name}) → このパスは何もしない",
                  file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False, "locked_out": True}
    try:
        return _run_pass_inner(
            date_str, day_dir, now=now, live=live, bankroll=bankroll,
            kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct,
            preset=preset, per_day_max_yen=per_day_max_yen,
            login_timeout=login_timeout, verbose=verbose)
    finally:
        release_lock(lp)


def _run_pass_inner(date_str: str, day_dir: Path, *, now: datetime, live: bool,
                    bankroll: int, kelly_fraction: float, per_bet_cap_pct: float,
                    preset: str, per_day_max_yen: int, login_timeout: int,
                    verbose: bool = True) -> dict:
    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print(f"[scheduler] predictions.json なし → 何もしない", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": False}

    result = extract_freebudget_bets(
        predictions, bankroll=bankroll, kelly_fraction=kelly_fraction,
        per_bet_cap_pct=per_bet_cap_pct, preset=preset)
    post_times = load_post_times(day_dir, date_str=date_str)

    sp = state_path(day_dir, live=live)
    state = load_state(sp, date_str, "live" if live else "dry-run")

    if state.get("halted"):
        if verbose:
            print(f"[scheduler] HALTED ({state.get('halt_reason')}) — "
                  f"当日は停止中。 手動確認が必要", file=sys.stderr)
        return {"voted": [], "skipped": [], "halted": True}

    # 既投票の累計額 (idempotency + cap)
    voted_yen = sum(v.get("amount", 0) for v in state["votes"].values()
                    if v.get("exit_code") == 0)

    # per_race ハードキャップ (config per_race_max_yen)。 0 = キャップ無し扱い。
    per_race_cap = read_per_race_cap()

    # race_id ごとに candidate をまとめる
    by_race: dict[str, list] = {}
    for b in result.bets:
        by_race.setdefault(str(b.race_id), []).append(b)

    newly_voted, skipped = [], []
    vb_ref = predictions.get("vb_refreshed_at")

    if verbose:
        print(f"[scheduler] {date_str} now={now.strftime('%H:%M')} "
              f"mode={'LIVE' if live else 'dry-run'} "
              f"odds={vb_ref} 候補={len(by_race)} 既投票={voted_yen}円")

    # 🟡-3: オッズ鮮度ガード。 vb_refresh が止まり古いオッズで投票するのを防ぐ。
    #   live のみ作動 (dry-run は鮮度に関わらず予定を表示)。 stale なら投票せず次パスに委ねる。
    if live and vb_ref:
        try:
            age_min = (now - datetime.fromisoformat(vb_ref)).total_seconds() / 60.0
            if age_min > ODDS_STALE_MIN:
                msg = (f"オッズ鮮度 {age_min:.0f}分 > {ODDS_STALE_MIN}分 "
                       f"(vb_refresh 停止疑い) → このパスは投票せずスキップ")
                if verbose:
                    print(f"[scheduler] ⚠ {msg}", file=sys.stderr)
                save_state(sp, state)
                return {"voted": [], "skipped": [("*", msg)], "halted": False}
        except ValueError:
            pass

    for race_id in sorted(by_race):
        if race_id in state["votes"] and state["votes"][race_id].get("exit_code") == 0:
            continue  # 投票済み (冪等)
        st = post_times.get(race_id, "")
        t = race_timing(date_str, st, now)
        head = by_race[race_id][0]
        label = f"{head.venue_name or '?'} {head.race_number or '?'}R"

        if t["deadline"] is None:
            skipped.append((race_id, "発走時刻不明"))
            continue
        if now < t["vote_at"]:
            continue  # まだウィンドウ前 (静かに待つ)
        if now > t["deadline"]:
            # ウィンドウを逃した (起動遅れ等) — 二重投票しないため投票しない
            if race_id not in state["votes"]:
                skipped.append((race_id, f"{label} 締切超過 (発走{st})"))
                state["votes"][race_id] = {"mode": "missed", "amount": 0,
                                           "umaban": [], "exit_code": -1,
                                           "note": "deadline passed before vote",
                                           "at": now.isoformat(timespec="seconds")}
            continue

        # --- ウィンドウ内 [vote_at, deadline] ---
        sub = filter_result_by_race(result, race_id)
        if not sub.bets:
            continue
        # シズネ Session139 残課題②対応 / ふくだ判断 Session140: 1 レース合計が per_race を
        #   超えたら ★day-halt でも skip でもなく per_race 以内に「按分 (比例縮小)」★ して買う。
        #   over-cap は異常でなく単なるサイジング (強い馬が多い) なので、 上限内に収めて投票する。
        #   per_race ハードキャップの正本は runner 側 (_check_per_race_limits) で不変。
        #   per_day チェックより前に縮小し、 日次累計には縮小後の額を使う。
        adj_note = None
        if per_race_cap > 0 and sub.total_yen > per_race_cap:
            before = sub.total_yen
            sub, info = fit_result_to_cap(sub, per_race_cap)
            adj_note = info
            if not sub.bets:
                skipped.append((race_id, f"{label} per_race按分で全0 → skip"))
                continue
            if verbose:
                print(f"  ⚖ {label} per_race按分 {before}→{sub.total_yen}円 "
                      f"(cap {per_race_cap}, drop {info['dropped']})", file=sys.stderr)
        if voted_yen + sub.total_yen > per_day_max_yen:
            skipped.append((race_id, f"{label} 日次キャップ超過 "
                            f"({voted_yen}+{sub.total_yen}>{per_day_max_yen})"))
            continue

        if verbose:
            umaban = "/".join(str(b.umaban) for b in sub.bets)
            print(f"  🔵 {label} 締切{t['deadline'].strftime('%H:%M')} "
                  f"単勝{umaban} {sub.total_yen}円 → "
                  f"{'投票実行' if live else 'WOULD VOTE'}")

        res = vote_one_race(day_dir, race_id, sub, live=live,
                            login_timeout=login_timeout, per_race_cap=per_race_cap)
        res["at"] = now.isoformat(timespec="seconds")
        res["label"] = label
        if adj_note:                           # 按分した事実を監査用に記録 (シズネ🟡-1)
            res["per_race_adjusted"] = adj_note
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
            # 🔴-4: その他の失敗 (exit 1/4 等)。 連続失敗を数え、 閾値で当日 halt。
            #   無人運用で失敗が黙って累積する経路を塞ぐ (観察者不在対策)。
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
        print(f"[scheduler] 今パス: 投票{len(newly_voted)}件 / "
              f"skip{len(skipped)}件 / halted={state.get('halted')}")
        for rid, reason in skipped:
            print(f"    skip {rid}: {reason}")
    return {"voted": newly_voted, "skipped": skipped,
            "halted": state.get("halted", False)}


def halt_day(date_str: str, *, live: bool, reason: str) -> dict:
    """当日の state に halted=True を立てて以降のパスを全停止する (web「停止」用)。

    ★state ファイル書き込みは Python 側に集約★ (SoT 単一窓口。 web から JSON を
    直接書かない)。 単発パスは即終了型のため「停止」= 以後のパスを halt で弾く意味。
    冪等: 既に halted でも reason を上書きしない (最初の halt 理由を保つ)。
    """
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    sp = state_path(day_dir, live=live)
    # 安全ブレーキは必ず効くべき: 当日 dir が未作成 (準備前の日付を停止) でも書けるよう
    # 親 dir を確保してから書く (save_state の FileNotFoundError で halt が不発になるのを防ぐ)。
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


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--date", default="today")
    p.add_argument("--now", default=None, help="擬似時刻 HH:MM (テスト用)")
    p.add_argument("--confirm", action="store_true", help="実 click (live)")
    p.add_argument("--i-understand-live", action="store_true",
                   help="実弾を承認 (--confirm と両方必須 = 金経路の二重フラグ)")
    p.add_argument("--halt", action="store_true",
                   help="当日 state を halted=True にして以降のパスを停止 (web「停止」)")
    p.add_argument("--halt-reason", default="manual_stop_via_web",
                   help="--halt 時の停止理由")
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    p.add_argument("--kelly-fraction", type=float, default=DEFAULT_KELLY_FRACTION)
    p.add_argument("--per-bet-cap-pct", type=float, default=DEFAULT_PER_BET_CAP_PCT)
    p.add_argument("--preset", default=DEFAULT_PRESET)
    p.add_argument("--per-day-max-yen", type=int, default=DEFAULT_PER_DAY_MAX_YEN)
    p.add_argument("--login-timeout", type=int, default=180)
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    live = bool(args.confirm)

    # --halt: 当日の自動投票を停止 (web「停止」)。 live/dry 両方の state を halt する
    # (どちらのモードで動いていても止める。 二重フラグ不要 = 停止は安全側の操作)。
    if args.halt:
        date_str = resolve_date(args.date)
        out_live = halt_day(date_str, live=True, reason=args.halt_reason)
        out_dry = halt_day(date_str, live=False, reason=args.halt_reason)
        print(f"[scheduler] HALTED {date_str}: live={out_live['halt_reason']} "
              f"(already={out_live['already_halted']}) / "
              f"dry={out_dry['already_halted']}")
        return 0

    if live and not args.i_understand_live:
        print("[scheduler] --confirm には --i-understand-live も必須 "
              "(実弾の二重フラグ)。 中止。", file=sys.stderr)
        return 2
    date_str = resolve_date(args.date)
    now = parse_now(args.now, date_str)
    out = run_pass(
        date_str, now=now, live=live,
        bankroll=args.bankroll, kelly_fraction=args.kelly_fraction,
        per_bet_cap_pct=args.per_bet_cap_pct, preset=args.preset,
        per_day_max_yen=args.per_day_max_yen, login_timeout=args.login_timeout,
        verbose=not args.quiet)
    return 3 if out.get("halted") else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Freebudget レース単位ヘルパー (Session 135 / 締切前 レース単位投票テスト用)

freebudget.py の日次 Kelly 案分ロジックをそのまま使い、 発走時刻 (race_info.json)
と突き合わせて「いつ・どのレースを投票すべきか」 を一覧表示する。 指定レースだけを
切り出して freebudget_bets_<race_id>.json を書き出し、 runner.py --from-json で
1 レースだけ投票する (テスト済み経路)。

時刻定義 (ふくだ運用、 Session 135):
    締切     = 発走時刻 − 2 分
    投票推奨 = 締切 − 4 分 = 発走時刻 − 6 分

CLI:
    # ① 当日の候補レース一覧 (発走/締切/投票時刻 + あと何分 + race_id)
    python -m ml.strategies.freebudget_race --date today

    # ② 指定レースだけ freebudget_bets_<race_id>.json を生成 (投票準備)
    python -m ml.strategies.freebudget_race --date today --race-id 2026053008031109

設計 (Session 135):
  - 日次 bankroll (default 10000) で Kelly 案分 → 指定レースの funded bets を抽出
  - 1 レースの amount 合計は per_race_max_yen (3000) 以下になる設計 (cap 10% × ≤数頭)
  - odds 鮮度 = predictions.vb_refreshed_at を表示 (vb_refresh 5 分ごと自動更新)
  - 投票は runner.py --from-json freebudget_bets_<race_id>.json --confirm (別工程 / bat)
  - 発走時刻が無いレースは「時刻不明」 と表示 (投票自体は可能)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.freebudget import (  # noqa: E402
    DEFAULT_BANKROLL,
    DEFAULT_KELLY_FRACTION,
    DEFAULT_PER_BET_CAP_PCT,
    DEFAULT_PRESET,
    FreebudgetResult,
    extract_freebudget_bets,
    resolve_date,
    write_freebudget_bets,
)
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402


DEADLINE_BEFORE_POST_MIN = 2     # 締切 = 発走 − 2 分 (JRA 一般)
VOTE_BEFORE_DEADLINE_MIN = 4     # 投票推奨 = 締切 − 4 分 (ふくだ Session 135)
VOTE_BEFORE_POST_MIN = DEADLINE_BEFORE_POST_MIN + VOTE_BEFORE_DEADLINE_MIN  # = 6


def _load_post_times_from_file(date_dir: Path) -> dict[str, str]:
    """race_info.json (昨夜 keibabook スクレイプ) から race_id_16 → '9:50' を構築"""
    p = Path(date_dir) / "race_info.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, str] = {}
    for _venue, races in (data.get("kaisai_data") or {}).items():
        for r in races or []:
            rid = str(r.get("race_id_16") or "")
            st = str(r.get("start_time") or "")
            if rid and st:
                out[rid] = st
    return out


def load_post_times_from_db(date_str: str) -> dict[str, str]:
    """mykeibadb RACE_SHOSAI.HASSO_JIKOKU (HHmm) を race_id_16 → 'HH:MM' で取得 (正本)。

    🔴-3 (シズネ Session 135): race_info.json は昨夜スクレイプで当日の発走時刻変更
    (繰上げ等) に弱い。 mykeibadb は raceday_odds タスクが 30 分毎に更新し
    TC(変更情報・発走時刻) も取り込むため当日変更に追従する = 正本。 RACE_CODE は
    16 桁 race_id と同一 (predict.py の RACE_SHOSAI クエリと同じ前提)。
    DB 不通時は {} を返し、 呼び出し側が race_info.json にフォールバックする。
    """
    yyyymmdd = date_str.replace("-", "")
    out: dict[str, str] = {}
    try:
        from core.db import get_connection
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT RACE_CODE, HASSO_JIKOKU FROM RACE_SHOSAI "
                "WHERE RACE_CODE LIKE %s ORDER BY RACE_CODE",
                (f"{yyyymmdd}%",))
            for rc, hj in cur.fetchall():
                rc = str(rc or "").strip()
                hj = str(hj or "").strip()
                if rc and len(hj) == 4 and hj.isdigit():
                    out[rc] = f"{hj[:2]}:{hj[2:]}"
    except Exception as e:                       # DB 不通でも本体を止めない
        print(f"[freebudget_race] mykeibadb 発走時刻取得失敗 "
              f"(race_info.json にフォールバック): {type(e).__name__}: {e}",
              file=sys.stderr)
    return out


def load_post_times(date_dir: Path, *, date_str: Optional[str] = None,
                    prefer_db: bool = True) -> dict[str, str]:
    """race_id_16 → 'HH:MM' の発走時刻 dict。

    🔴-3: DB(正本) 優先 + race_info.json フォールバック/補完。 date_str を渡すと
    mykeibadb から当日の HASSO_JIKOKU を引き、 file 値を上書き (DB が当日変更に追従)。
    DB が引けない race は file 値で補完。 date_str 無しは従来通り file のみ。
    """
    file_times = _load_post_times_from_file(date_dir)
    if not (prefer_db and date_str):
        return file_times
    db_times = load_post_times_from_db(date_str)
    merged = dict(file_times)
    merged.update(db_times)        # DB(正本) で上書き
    return merged


def parse_post_dt(date_str: str, start_time: str) -> Optional[datetime]:
    """'YYYY-MM-DD' + '9:50' → datetime (ローカル = JST 前提)"""
    try:
        y, mo, d = (int(x) for x in date_str.split("-"))
        hh, mm = (int(x) for x in start_time.split(":"))
        return datetime(y, mo, d, hh, mm)
    except (ValueError, AttributeError):
        return None


def _fmt_hhmm(dt: Optional[datetime]) -> str:
    return dt.strftime("%H:%M") if dt else "--:--"


def race_timing(date_str: str, start_time: str, now: datetime) -> dict:
    """発走/締切/投票時刻 + 状態 + 残り分を計算"""
    post = parse_post_dt(date_str, start_time)
    if post is None:
        return {"post": None, "deadline": None, "vote_at": None,
                "status": "時刻不明", "mins_to_deadline": None}
    deadline = post - timedelta(minutes=DEADLINE_BEFORE_POST_MIN)
    vote_at = deadline - timedelta(minutes=VOTE_BEFORE_DEADLINE_MIN)
    mins_to_deadline = (deadline - now).total_seconds() / 60.0
    if now >= post:
        status = "発走済"
    elif now >= deadline:
        status = "締切済(発走前)"
    elif now >= vote_at:
        status = "🔵投票WINDOW"
    else:
        status = f"待機 (投票まで{int((vote_at - now).total_seconds() // 60)}分)"
    return {"post": post, "deadline": deadline, "vote_at": vote_at,
            "status": status, "mins_to_deadline": mins_to_deadline}


def filter_result_by_race(result: FreebudgetResult, race_id: str) -> FreebudgetResult:
    """FreebudgetResult を 1 レースだけに絞った新 result を返す"""
    bets = [b for b in result.bets if str(b.race_id) == str(race_id)]
    total = sum(b.amount for b in bets)
    return replace(
        result,
        bets=bets,
        total_yen=total,
        n_funded=len(bets),
        n_eligible=len(bets),
        n_truncated=0,
    )


def print_schedule(result: FreebudgetResult, post_times: dict[str, str],
                   date_str: str, now: datetime,
                   vb_refreshed_at: Optional[str]) -> None:
    """候補レースを発走時刻順に一覧表示 (ライブ監視ダッシュボード)"""
    # race_id ごとに bets をまとめる
    by_race: dict[str, list] = {}
    for b in result.bets:
        by_race.setdefault(str(b.race_id), []).append(b)

    # 表示行を組み立て (発走時刻でソート)
    rows = []
    for rid, bets in by_race.items():
        st = post_times.get(rid, "")
        t = race_timing(date_str, st, now)
        sort_key = t["post"] or datetime.max
        rows.append((sort_key, rid, bets, st, t))
    rows.sort(key=lambda x: x[0])

    print("=" * 78)
    age = ""
    if vb_refreshed_at:
        try:
            ref = datetime.fromisoformat(vb_refreshed_at)
            age = f" (オッズ鮮度: {int((now - ref).total_seconds() // 60)}分前)"
        except ValueError:
            age = f" (vb_refreshed_at={vb_refreshed_at})"
    print(f"freebudget 候補レース  {date_str}  現在 {now.strftime('%H:%M:%S')}{age}")
    print(f"  締切=発走-{DEADLINE_BEFORE_POST_MIN}分 / 投票推奨=締切-{VOTE_BEFORE_DEADLINE_MIN}分"
          f"(=発走-{VOTE_BEFORE_POST_MIN}分)  合計 {result.total_yen}円 / {len(by_race)}レース")
    print("=" * 78)
    if not rows:
        print("  候補なし (VB Floor を通過した単勝候補が 0 件)")
        print("=" * 78)
        return

    for _sk, rid, bets, st, t in rows:
        head = bets[0]
        print(f"\n● {head.venue_name or '?'} {head.race_number or '?'}R "
              f"{head.grade or ''}  発走 {st or '--:--'}  "
              f"締切 {_fmt_hhmm(t['deadline'])}  投票 {_fmt_hhmm(t['vote_at'])}  "
              f"[{t['status']}]")
        print(f"   race_id={rid}  (このレースだけ投票: "
              f"freebudget_race.bat {date_str} {rid} --confirm)")
        race_total = 0
        for b in bets:
            race_total += b.amount
            ev = f"EV={b.win_ev:.2f}" if b.win_ev else "EV=?"
            print(f"     {b.umaban:>2}番 {b.horse_name}  odds={b.odds:.1f}  "
                  f"{ev}  → {b.amount}円")
        flag = "  ★per_race超過!" if race_total > 3000 else ""
        print(f"     race計 {race_total}円{flag}")
    print("\n" + "=" * 78)


def process(date_str: str, *, race_id: Optional[str],
            bankroll: int, kelly_fraction: float,
            per_bet_cap_pct: float, preset: str,
            dry_run: bool) -> int:
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    predictions = load_predictions(day_dir)
    if predictions is None:
        print(f"  [{date_str}] predictions.json なし → スキップ", file=sys.stderr)
        return 1

    result = extract_freebudget_bets(
        predictions, bankroll=bankroll, kelly_fraction=kelly_fraction,
        per_bet_cap_pct=per_bet_cap_pct, preset=preset,
    )
    post_times = load_post_times(day_dir, date_str=date_str)
    now = datetime.now()
    vb_refreshed_at = predictions.get("vb_refreshed_at")

    # --- モード ① 一覧 (race_id 指定なし) ---
    if not race_id:
        print_schedule(result, post_times, date_str, now, vb_refreshed_at)
        return 0

    # --- モード ② 指定レースを切り出し ---
    sub = filter_result_by_race(result, race_id)
    if not sub.bets:
        print(f"  [{date_str}] race_id={race_id} は freebudget 候補に無い "
              f"(VB Floor 未通過 / 別レース)", file=sys.stderr)
        return 2

    st = post_times.get(str(race_id), "")
    t = race_timing(date_str, st, now)
    head = sub.bets[0]
    print(f"● {head.venue_name or '?'} {head.race_number or '?'}R  "
          f"発走 {st or '--:--'}  締切 {_fmt_hhmm(t['deadline'])}  "
          f"投票 {_fmt_hhmm(t['vote_at'])}  [{t['status']}]")
    race_total = 0
    for b in sub.bets:
        race_total += b.amount
        ev = f"EV={b.win_ev:.2f}" if b.win_ev else "EV=?"
        print(f"   {b.umaban:>2}番 {b.horse_name}  odds={b.odds:.1f}  {ev}  → {b.amount}円")
    print(f"   race計 {race_total}円" + ("  ★per_race超過!" if race_total > 3000 else ""))

    if dry_run:
        print(f"   (--dry-run: ファイル書かず)")
        return 0

    out = write_freebudget_bets(day_dir, sub,
                                filename=f"freebudget_bets_{race_id}.json")
    print(f"   → {out}")
    print(f"   投票: python -m ml.target_clicker.runner "
          f"--from-json {out} --confirm")
    return 0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--date", default="today", help="YYYY-MM-DD または today")
    p.add_argument("--race-id", default=None,
                   help="指定すると そのレースだけ freebudget_bets_<id>.json を生成")
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    p.add_argument("--kelly-fraction", type=float, default=DEFAULT_KELLY_FRACTION)
    p.add_argument("--per-bet-cap-pct", type=float, default=DEFAULT_PER_BET_CAP_PCT)
    p.add_argument("--preset", default=DEFAULT_PRESET)
    p.add_argument("--dry-run", action="store_true",
                   help="--race-id 時にファイルを書かず内容だけ表示")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    return process(
        args.date, race_id=args.race_id, bankroll=args.bankroll,
        kelly_fraction=args.kelly_fraction, per_bet_cap_pct=args.per_bet_cap_pct,
        preset=args.preset, dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())

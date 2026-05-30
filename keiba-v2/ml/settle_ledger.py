#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ledger v2 決済 (settlement) — purchase_ledger/{date}.json の ticket を精算

mykeibadb の確定配当 (odds1_tansho/fukusho, haraimodoshi) から各 ticket の payout を
計算し、 ml.purchase_ledger.writer.record_settlement() 経由で ledger に
payout / settled_at / payout_source / reconciled / portfolio_pnl / portfolio_roi /
SETTLED イベントを書き込む。

settle_purchases.py (purchases/{date}.json 用) の払戻取得ロジックを流用するが、
書き込み先は ledger v2 (races→portfolios→tickets) であり purchases とは独立。
ledger I/O は writer.record_settlement() に集約 (単一窓口)。

対応券種 (現状): 単勝/複勝/馬連/ワイド/馬単 の formation_type=single のみ。
  box/formation/三連系は skip+warning。

精算しない (SUBMITTED 据え置き) ケース:
  - 着順未確定 (pending): レース結果待ち。 後で再実行で拾う。
  - 的中だが DB 配当未取得 (payout_unavailable): シズネ 🔴-2。 不正確な暫定値 (元返し等) を
    税務 SoT に書かない。 確定配当が取れるまで settle を見送る (翌日 DB 更新後に再 settle)。

税務 SoT 信頼性 (シズネ 🔴-1/-3):
  - reconcile (13章 IPAT CSV 突合) 本体は未実装。 現状は全 settle が pre-reconcile =
    reconciled=False (暫定) として記録される。 ticket.reconciled / SETTLED.source で明示。
  - reconcile 実装後は reconciled=True (確定) で再 settle する。

Usage:
    python -m ml.settle_ledger --date 2026-05-30
    python -m ml.settle_ledger --date 2026-05-30 --force          # settle 済も再計算
    python -m ml.settle_ledger --date 2026-05-30 --dry-run        # 計算のみ
    python -m ml.settle_ledger --date 2026-05-30 --allow-pre-reconcile  # 突合前 settle を明示許可
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.odds_db import get_final_win_odds, get_final_place_odds
from ml.settle_purchases import (
    get_umaren_payouts,
    get_umatan_payouts,
    get_wide_payouts,
    get_db_finish_positions,
    get_db_num_runners,
    load_race_data,
)
from ml.purchase_ledger.writer import record_settlement, LEDGER_DIR


# formation_type=="single" かつこの集合に含まれる bet_type のみ settle 対象
SUPPORTED_SINGLE_BET_TYPES = {"tansho", "fukusho", "umaren", "wide", "umatan"}

# compute_payout の status
ST_OK = "ok"                          # settle 可
ST_PENDING = "pending"                # 着順未確定 (取消含む)
ST_PAYOUT_UNAVAILABLE = "payout_unavailable"  # 的中だが DB 配当未取得 → settle 見送り
ST_UNSUPPORTED = "unsupported"        # 未対応券種/形式
ST_INVALID = "invalid"               # raw_legs 不正


def get_finish_positions(race_id: str, races_dir: Path) -> Tuple[Dict[int, int], int]:
    """着順 + 出走頭数を取得 (race JSON → DB フォールバック)。 settle_purchases と同ロジック。"""
    race_data = load_race_data(race_id, races_dir)
    fps: Dict[int, int] = {}
    num_runners = 18
    if race_data:
        entries = race_data.get("entries", [])
        fps = {e["umaban"]: e.get("finish_position", 0)
               for e in entries if e.get("umaban") is not None}
        num_runners = race_data.get("num_runners", len(entries))
    if not fps or all(fp == 0 for fp in fps.values()):
        db_fps = get_db_finish_positions(race_id)
        if db_fps:
            fps = db_fps
            num_runners = get_db_num_runners(race_id) or len(db_fps)
    return fps, num_runners


def _place_limit(num_runners: int) -> int:
    """複勝・ワイドの的中圏 (3 着まで / 7 頭以下は 2 着 / 4 頭以下は 1 着)。"""
    return 3 if num_runners >= 8 else (2 if num_runners >= 5 else 1)


def _legs_horses(raw_legs: dict) -> list:
    """raw_legs から馬番リストを取得 (single 形式 = {"horses": [...]} のみ)。"""
    horses = raw_legs.get("horses")
    if isinstance(horses, list) and all(isinstance(h, int) for h in horses):
        return horses
    return []


def compute_payout(ticket: dict, fps: Dict[int, int], num_runners: int,
                   race_id: str, caches: dict) -> Tuple[Optional[dict], str]:
    """1 ticket の払戻を計算。

    Returns:
        (result, status)
        result: {"ticket_id","payout","won","payout_source"} or None
        status: ST_OK / ST_PENDING / ST_PAYOUT_UNAVAILABLE / ST_UNSUPPORTED / ST_INVALID

    シズネ 🔴-2: 元返しフォールバックは廃止。 的中だが DB 配当が取れない時は
    payout を捏造せず None + ST_PAYOUT_UNAVAILABLE を返し、 settle を見送る
    (SUBMITTED 据え置き → 翌日 DB 更新後に再 settle で拾う)。
    """
    bet_type = ticket.get("bet_type", "")
    formation_type = ticket.get("formation_type", "single")
    amount = ticket.get("total_amount", 0)
    ticket_id = ticket.get("ticket_id")
    raw_legs = ticket.get("raw_legs", {})

    if formation_type != "single" or bet_type not in SUPPORTED_SINGLE_BET_TYPES:
        return None, ST_UNSUPPORTED

    horses = _legs_horses(raw_legs)
    if not horses:
        return None, ST_INVALID

    pl = _place_limit(num_runners)

    def won(payout: int):
        return {"ticket_id": ticket_id, "payout": payout, "won": payout > 0,
                "payout_source": "db"}, ST_OK

    def lose():
        return {"ticket_id": ticket_id, "payout": 0, "won": False,
                "payout_source": "db"}, ST_OK

    def deferred(label: str):
        print(f"  [DEFER] {label}的中だが DB 配当未取得 → settle 見送り (SUBMITTED 据置): {race_id}",
              file=sys.stderr)
        return None, ST_PAYOUT_UNAVAILABLE

    # --- 単勝 ---
    if bet_type == "tansho":
        uma = horses[0]
        fp = fps.get(uma, 0)
        if fp == 0:
            return None, ST_PENDING
        if fp != 1:
            return lose()
        odds_map = caches.setdefault("win", {})
        if race_id not in odds_map:
            odds_map[race_id] = get_final_win_odds(race_id)
        odds = odds_map[race_id].get(uma, {}).get("odds")
        if not odds:
            return deferred("単勝")
        return won(int(amount / 100 * odds * 100))

    # --- 複勝 ---
    if bet_type == "fukusho":
        uma = horses[0]
        fp = fps.get(uma, 0)
        if fp == 0:
            return None, ST_PENDING
        if fp > pl:
            return lose()
        odds_map = caches.setdefault("place", {})
        if race_id not in odds_map:
            odds_map[race_id] = get_final_place_odds(race_id)
        odds_low = odds_map[race_id].get(uma, {}).get("odds_low")
        if not odds_low:
            return deferred("複勝")
        return won(int(amount / 100 * odds_low * 100))

    # --- 2 頭券種 (馬連 / ワイド / 馬単) ---
    if len(horses) < 2:
        return None, ST_INVALID
    u1, u2 = horses[0], horses[1]
    fp1, fp2 = fps.get(u1, 0), fps.get(u2, 0)
    if fp1 == 0 or fp2 == 0:
        return None, ST_PENDING

    if bet_type == "umaren":
        if set([fp1, fp2]) != {1, 2}:
            return lose()
        pay_map = caches.setdefault("umaren", {})
        if race_id not in pay_map:
            pay_map[race_id] = get_umaren_payouts(race_id)
        pay = pay_map[race_id].get((min(u1, u2), max(u1, u2)))
        if not pay:
            return deferred("馬連")
        return won(int(amount / 100 * pay))

    if bet_type == "wide":
        if not (fp1 <= pl and fp2 <= pl):
            return lose()
        pay_map = caches.setdefault("wide", {})
        if race_id not in pay_map:
            pay_map[race_id] = get_wide_payouts(race_id)
        pay = pay_map[race_id].get((min(u1, u2), max(u1, u2)))
        if not pay:
            return deferred("ワイド")
        return won(int(amount / 100 * pay))

    if bet_type == "umatan":
        # raw_legs.horses = [1着候補, 2着候補] の順 (順序あり)
        if not (fp1 == 1 and fp2 == 2):
            return lose()
        pay_map = caches.setdefault("umatan", {})
        if race_id not in pay_map:
            pay_map[race_id] = get_umatan_payouts(race_id)
        pay = pay_map[race_id].get((u1, u2))
        if not pay:
            return deferred("馬単")
        return won(int(amount / 100 * pay))

    return None, ST_UNSUPPORTED


def settle(date: str, force: bool = False, dry_run: bool = False,
           reconciled: bool = False) -> dict:
    """ledger {date}.json の settle 対象 ticket を精算。

    Args:
        reconciled: 13章突合済として確定 settle するなら True。 未突合 (pre-reconcile) は
                    False (暫定 = ticket.reconciled=False で記録)。 reconcile 本体未実装の
                    現状は常に False で運用される。
    """
    ledger_path = LEDGER_DIR / f"{date}.json"
    if not ledger_path.exists():
        return {"error": f"ledger not found: {ledger_path}"}

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    y, m, d = date.split("-")
    races_dir = config.races_dir() / y / m / d

    caches: dict = {}
    results = []
    skipped = 0              # 未対応券種 / raw_legs 不正
    pending = 0              # 着順未確定
    payout_unavailable = 0   # 的中だが DB 配当未取得 → settle 見送り (🔴-2)

    for race in ledger.get("races", []):
        race_id = race.get("race_id")
        tickets = [t for pf in race.get("portfolios", [])
                   for t in pf.get("tickets", [])]
        if not tickets:
            continue
        targets = [t for t in tickets if force or t.get("settled_at") is None]
        if not targets:
            continue

        fps, num_runners = get_finish_positions(race_id, races_dir)
        if not fps or all(fp == 0 for fp in fps.values()):
            pending += len(targets)
            print(f"  [PENDING] 着順未確定: {race_id} ({len(targets)} tickets)",
                  file=sys.stderr)
            continue

        for tk in targets:
            r, status = compute_payout(tk, fps, num_runners, race_id, caches)
            if r is not None:
                results.append(r)
            elif status == ST_PAYOUT_UNAVAILABLE:
                payout_unavailable += 1
            elif status == ST_PENDING:
                pending += 1
            else:  # unsupported / invalid
                skipped += 1

    won = sum(1 for r in results if r["won"])
    total_payout = sum(r["payout"] for r in results)

    if dry_run:
        return {
            "success": True, "dry_run": True, "reconciled": reconciled,
            "computed": len(results), "won": won,
            "skipped": skipped, "pending": pending,
            "payout_unavailable": payout_unavailable,
            "total_payout": total_payout,
            "results": results,
        }

    if not results:
        return {"success": True, "settled": 0, "won": 0, "reconciled": reconciled,
                "skipped": skipped, "pending": pending,
                "payout_unavailable": payout_unavailable,
                "message": "no settleable tickets"}

    sr = record_settlement(date=date, results=results, force=force, reconciled=reconciled)
    out = {
        "success": sr.success,
        "settled": sr.settled_tickets,
        "won": sr.won_tickets,
        "total_payout": sr.total_payout,
        "races_settled": sr.races_settled,
        "reconciled": reconciled,
        "skipped": skipped,
        "pending": pending,
        "payout_unavailable": payout_unavailable,
        "reason": sr.reason,
    }
    invested = sum(
        t.get("total_amount", 0)
        for race in ledger.get("races", [])
        for pf in race.get("portfolios", [])
        for t in pf.get("tickets", [])
        if t.get("ticket_id") in {r["ticket_id"] for r in results}
    )
    print(f"\n[SettleLedger] {date} "
          f"({'CONFIRMED (reconciled)' if reconciled else '⚠ PROVISIONAL (pre-reconcile)'})")
    print(f"  Settled: {sr.settled_tickets} tickets / {sr.races_settled} races, "
          f"Wins: {sr.won_tickets}")
    print(f"  Invested(settled): {invested:,}")
    print(f"  Payout:  {sr.total_payout:,}")
    if invested:
        print(f"  Profit:  {sr.total_payout - invested:+,}  "
              f"(recovery {sr.total_payout / invested * 100:.1f}%)")
    if skipped:
        print(f"  Skipped (未対応券種): {skipped}")
    if pending:
        print(f"  Pending (着順未確定): {pending}")
    if payout_unavailable:
        print(f"  Deferred (的中だが配当未取得→次回再settle): {payout_unavailable}")
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Settle ledger v2 tickets with confirmed mykeibadb payouts")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--force", action="store_true",
                    help="re-settle already settled tickets")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute only, do not write ledger")
    ap.add_argument("--allow-pre-reconcile", action="store_true",
                    help="(明示) IPAT 突合前の暫定 settle を許可。 現状は reconcile 本体未実装の"
                         "ため有無に関わらず暫定 (reconciled=False) で進むが、 将来突合を"
                         "前提条件化したとき confirmed settle と区別するためのゲート。")
    args = ap.parse_args()
    # reconcile 本体未実装 = 常に pre-reconcile (reconciled=False)。
    # --allow-pre-reconcile は将来の前提条件化に向けた意思表示ゲート (現状は挙動不変)。
    result = settle(args.date, force=args.force, dry_run=args.dry_run, reconciled=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

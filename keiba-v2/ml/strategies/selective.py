#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Selective 戦略 (Session 122 Phase 4 で発見)

「重賞 (G1/G2/G3/Listed) のみ rank_p==1 を 100円単勝買い」 戦略。
バックテスト (2025-05〜2026-03 / 2,934 races) で:
    166 bets / 勝率 22.9% / ROI 203.1% / P&L +¥17,110 / MaxDD -¥1,060

実戦投入用に predictions.json から該当馬を抽出し、selective_bets.json として保存する。
Web UI の予測表示でバッジ表示するため。

Usage:
    python -m ml.strategies.selective --date 2026-05-17
    python -m ml.strategies.selective --date 2026-05-17 --dry-run    # 出力せず stdout のみ
    python -m ml.strategies.selective --start 2026-05-01 --end 2026-05-31  # 期間バッチ
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import config
from ml.utils.race_io import iter_predictions, date_dir_for, load_predictions


# Selective 採用グレード
SELECTIVE_GRADES = {"G1", "G2", "G3", "Listed"}


@dataclass
class SelectiveBet:
    race_id: str
    race_number: Optional[int]
    venue_name: Optional[str]
    grade: str
    track_type: Optional[str]
    distance: Optional[int]
    num_runners: Optional[int]
    umaban: int
    horse_name: str
    odds: float
    rank_p: int
    pred_proba_p_raw: Optional[float]
    win_ev: Optional[float]
    confidence: Optional[float]  # race_confidence
    odds_rank: Optional[int] = None  # 人気順 (Sel_v3 not_fav1 等のフィルタ用)
    vb_gap: Optional[int] = None     # odds_rank - rank_p (市場乖離度、Sel_v3 gap>=N 用)


def is_selective_race(race: dict) -> bool:
    """Selective 対象レースか判定 (重賞のみ)"""
    grade = (race.get("grade") or "").strip()
    if grade not in SELECTIVE_GRADES:
        return False
    # 障害は除外
    if race.get("track_type") == "obstacle":
        return False
    if "障" in (race.get("race_name") or ""):
        return False
    return True


def find_top_p_horse(race: dict) -> Optional[dict]:
    """rank_p == 1 の馬を返す (odds > 0 のもののみ)"""
    for e in race.get("entries", []):
        if e.get("rank_p") == 1 and (e.get("odds") or 0) > 0:
            return e
    return None


def extract_selective_bets(predictions: dict) -> list[SelectiveBet]:
    """predictions.json から Selective 候補馬を抽出"""
    bets: list[SelectiveBet] = []
    for race in predictions.get("races", []):
        if not is_selective_race(race):
            continue
        horse = find_top_p_horse(race)
        if horse is None:
            continue
        bets.append(SelectiveBet(
            race_id=str(race.get("race_id", "")),
            race_number=race.get("race_number"),
            venue_name=race.get("venue_name"),
            grade=race.get("grade", ""),
            track_type=race.get("track_type"),
            distance=race.get("distance"),
            num_runners=race.get("num_runners"),
            umaban=int(horse.get("umaban") or 0),
            horse_name=str(horse.get("horse_name") or ""),
            odds=float(horse.get("odds") or 0),
            rank_p=int(horse.get("rank_p") or 0),
            pred_proba_p_raw=horse.get("pred_proba_p_raw"),
            win_ev=horse.get("win_ev"),
            confidence=race.get("race_confidence"),
            odds_rank=horse.get("odds_rank"),
            vb_gap=horse.get("vb_gap"),
        ))
    return bets


def write_selective_bets(date_dir: Path, bets: list[SelectiveBet]) -> Path:
    """selective_bets.json を date_dir に書き出し"""
    out_path = date_dir / "selective_bets.json"
    payload = {
        "strategy": "selective",
        "version": "1.0",
        "description": "重賞のみ rank_p==1 単勝 (BT ROI 203%)",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_bets": len(bets),
        "bets": [asdict(b) for b in bets],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return out_path


def process_date(date_str: str, *, dry_run: bool = False, verbose: bool = True) -> dict:
    """1 日を処理"""
    day_dir = date_dir_for(date_str)
    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print(f"  [{date_str}] predictions.json なし → スキップ")
        return {"date": date_str, "n_bets": 0, "n_races": 0, "skipped": True}

    bets = extract_selective_bets(predictions)
    n_races = len(predictions.get("races", []))

    if verbose:
        if bets:
            print(f"  [{date_str}] {len(bets)} bets / {n_races} races (重賞ヒット)")
            for b in bets:
                ev_str = f"EV={b.win_ev:.2f}" if b.win_ev else ""
                print(f"    {b.race_id} {b.venue_name or '?'} {b.race_number}R "
                      f"{b.grade} / {b.umaban}番 {b.horse_name} "
                      f"odds={b.odds:.1f}  {ev_str}")
        else:
            print(f"  [{date_str}] 重賞対象なし ({n_races} races)")

    if not dry_run and bets:
        out_path = write_selective_bets(day_dir, bets)
        if verbose:
            print(f"    → {out_path}")

    return {
        "date": date_str,
        "n_bets": len(bets),
        "n_races": n_races,
        "skipped": False,
    }


def process_range(start: Optional[str], end: Optional[str], *,
                  dry_run: bool = False, verbose: bool = True) -> list[dict]:
    """期間バッチ処理"""
    summary: list[dict] = []
    for day_dir in iter_predictions(start, end):
        # iter_predictions returns (date_dir, predictions_data) tuples
        # but we want date_str — extract from path
        dir_path, _ = day_dir if isinstance(day_dir, tuple) else (day_dir, None)
        parts = dir_path.parts
        date_str = f"{parts[-3]}-{parts[-2]}-{parts[-1]}"
        summary.append(process_date(date_str, dry_run=dry_run, verbose=verbose))
    return summary


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--date", default=None,
                   help="単日処理 (YYYY-MM-DD)")
    p.add_argument("--start", default=None, help="期間バッチ開始 (YYYY-MM)")
    p.add_argument("--end", default=None, help="期間バッチ終了 (YYYY-MM)")
    p.add_argument("--dry-run", action="store_true",
                   help="ファイル書かず stdout のみ")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    verbose = not args.quiet

    if args.date:
        result = process_date(args.date, dry_run=args.dry_run, verbose=verbose)
        if verbose:
            print(f"\n[Done] {result['n_bets']} bets generated")
        return 0
    elif args.start or args.end:
        results = process_range(args.start, args.end,
                                dry_run=args.dry_run, verbose=verbose)
        total_bets = sum(r["n_bets"] for r in results)
        if verbose:
            print(f"\n[Done] {len(results)} days, {total_bets} bets total")
        return 0
    else:
        print("Specify --date YYYY-MM-DD or --start/--end YYYY-MM", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

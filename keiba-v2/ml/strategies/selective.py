#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Selective 戦略 (Session 122 Phase 4 + Session 123 Phase 1.5 拡張)

v1.0 (Session 122):
  「重賞 (G1/G2/G3/Listed) のみ rank_p==1 を 100円単勝買い」
  BT: 166 bets / 勝率 22.9% / ROI 203.1% / P&L +¥17,110

v2.0 (Session 123 Phase 1.5):
  上記に加えて「1勝クラスのみ rank_w==1 かつ odds_rank>2 (3番人気以下)」 を追加。
  1勝クラス BT (2025-05〜2026-03 / 92 bets): ROI 115.7% / hit 17.4%
  → 「重賞の本命級」 + 「1勝クラスの中穴」 のハイブリッド黒字戦略

bets[].source で抽出ロジックを識別:
  - "grade_top_p"           : 重賞 rank_p==1 (v1.0 と同じ)
  - "emerging_w_not_top2"   : 1勝クラス rank_w==1 && odds_rank>2 (v2.0 新規)

実戦投入用に predictions.json から該当馬を抽出し、selective_bets.json として保存する。

Usage:
    python -m ml.strategies.selective --date 2026-05-17
    python -m ml.strategies.selective --date 2026-05-17 --dry-run
    python -m ml.strategies.selective --start 2026-05-01 --end 2026-05-31
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


# Selective 採用グレード (v1.0 重賞)
SELECTIVE_GRADES = {"G1", "G2", "G3", "Listed"}
# v2.0 新規: 1勝クラスは rank_w + not_top2 で抽出
EMERGING_GRADE = "1勝クラス"


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
    rank_p: Optional[int]            # v2.0: rank_w 戦略では参考値
    pred_proba_p_raw: Optional[float]
    win_ev: Optional[float]
    confidence: Optional[float]  # race_confidence
    odds_rank: Optional[int] = None  # 人気順 (Sel_v3 not_fav1 等のフィルタ用)
    vb_gap: Optional[int] = None     # odds_rank - rank_p (市場乖離度、Sel_v3 gap>=N 用)
    source: str = "grade_top_p"      # v2.0: 抽出ロジック識別
    rank_w: Optional[int] = None     # v2.0: rank_w 戦略時のランク


def is_grade_selective(race: dict) -> bool:
    """v1.0: Selective 対象レース判定 (重賞)"""
    grade = (race.get("grade") or "").strip()
    if grade not in SELECTIVE_GRADES:
        return False
    if race.get("track_type") == "obstacle":
        return False
    if "障" in (race.get("race_name") or ""):
        return False
    return True


def is_emerging_selective(race: dict) -> bool:
    """v2.0: 1勝クラス特化レース判定 (障害除外)"""
    grade = (race.get("grade") or "").strip()
    if grade != EMERGING_GRADE:
        return False
    if race.get("track_type") == "obstacle":
        return False
    if "障" in (race.get("race_name") or ""):
        return False
    return True


# v1.0 互換 alias
is_selective_race = is_grade_selective


def find_top_p_horse(race: dict) -> Optional[dict]:
    """rank_p == 1 の馬を返す (odds > 0 のもののみ)"""
    for e in race.get("entries", []):
        if e.get("rank_p") == 1 and (e.get("odds") or 0) > 0:
            return e
    return None


def find_top_w_not_top2_horse(race: dict) -> Optional[dict]:
    """rank_w==1 && odds_rank>2 の馬を返す (v2.0)。
    1勝クラスでは「rank_w 1番の馬が 3番人気以下」 のときだけ買う。"""
    for e in race.get("entries", []):
        if e.get("rank_w") != 1:
            continue
        if (e.get("odds") or 0) <= 0:
            continue
        odds_rank = e.get("odds_rank")
        if odds_rank is None or int(odds_rank) <= 2:
            return None  # 1〜2番人気なので不採用
        return e
    return None


def _build_bet(race: dict, horse: dict, source: str) -> SelectiveBet:
    rank_p = horse.get("rank_p")
    rank_w = horse.get("rank_w")
    return SelectiveBet(
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
        rank_p=int(rank_p) if rank_p is not None else None,
        pred_proba_p_raw=horse.get("pred_proba_p_raw"),
        win_ev=horse.get("win_ev"),
        confidence=race.get("race_confidence"),
        odds_rank=horse.get("odds_rank"),
        vb_gap=horse.get("vb_gap"),
        source=source,
        rank_w=int(rank_w) if rank_w is not None else None,
    )


def extract_selective_bets(predictions: dict) -> list[SelectiveBet]:
    """predictions.json から Selective 候補馬を抽出 (v2.0: 重賞 + 1勝クラス)"""
    bets: list[SelectiveBet] = []
    for race in predictions.get("races", []):
        # v1.0: 重賞 rank_p==1
        if is_grade_selective(race):
            horse = find_top_p_horse(race)
            if horse is not None:
                bets.append(_build_bet(race, horse, source="grade_top_p"))
            continue  # 重賞は重賞戦略のみ
        # v2.0: 1勝クラス rank_w==1 && odds_rank>2
        if is_emerging_selective(race):
            horse = find_top_w_not_top2_horse(race)
            if horse is not None:
                bets.append(_build_bet(race, horse, source="emerging_w_not_top2"))
    return bets


def write_selective_bets(date_dir: Path, bets: list[SelectiveBet]) -> Path:
    """selective_bets.json を date_dir に書き出し"""
    out_path = date_dir / "selective_bets.json"
    n_grade = sum(1 for b in bets if b.source == "grade_top_p")
    n_emerging = sum(1 for b in bets if b.source == "emerging_w_not_top2")
    payload = {
        "strategy": "selective",
        "version": "2.0",
        "description": (
            "重賞 rank_p==1 (BT ROI 203%) + "
            "1勝クラス rank_w==1 && odds_rank>2 (BT ROI 115.7%)"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_bets": len(bets),
        "n_grade_top_p": n_grade,
        "n_emerging_w_not_top2": n_emerging,
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
            n_grade = sum(1 for b in bets if b.source == "grade_top_p")
            n_emerging = sum(1 for b in bets if b.source == "emerging_w_not_top2")
            print(f"  [{date_str}] {len(bets)} bets / {n_races} races "
                  f"(重賞 {n_grade} + 1勝穴 {n_emerging})")
            for b in bets:
                ev_str = f"EV={b.win_ev:.2f}" if b.win_ev else ""
                src_tag = "🏆" if b.source == "grade_top_p" else "💎"
                print(f"    {src_tag} {b.race_id} {b.venue_name or '?'} {b.race_number}R "
                      f"{b.grade} / {b.umaban}番 {b.horse_name} "
                      f"odds={b.odds:.1f}  {ev_str}")
        else:
            print(f"  [{date_str}] 対象なし ({n_races} races)")

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

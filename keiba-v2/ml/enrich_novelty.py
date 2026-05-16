#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
過去 predictions.json に novelty_* / ar_deviation_adj を後付するスクリプト。

predict.py を全期間再実行せず、compute_career_features だけ走らせて
未知数度フィールドを既存 predictions.json に追記する。

Usage:
    python -m ml.enrich_novelty
    python -m ml.enrich_novelty --start 2025-05 --end 2026-04
    python -m ml.enrich_novelty --dry-run   # 書き込まず統計のみ
"""

import argparse
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.features.career_features import compute_career_features
from ml.bet_engine import (
    passes_novelty_filter,
    VB_FLOOR_MIN_WIN_EV, VB_FLOOR_MIN_ARD,
    VB_FLOOR_ARD_VB_MIN_ARD, VB_FLOOR_ARD_VB_MIN_ODDS,
    VB_FLOOR_MIN_DEV_GAP, VB_FLOOR_DEV_MIN_ARD,
)

NOVELTY_DECAY = 0.05  # predict.py と一致させる


def recompute_is_value_bet(entry: dict) -> bool:
    """predict.py の is_value_bet 判定と同じロジックで再計算"""
    ev_ok = (entry.get("win_ev") or 0) >= VB_FLOOR_MIN_WIN_EV
    ard_ok = (entry.get("ar_deviation") or 0) >= VB_FLOOR_MIN_ARD
    ard_vb_ok = (
        (entry.get("ar_deviation") or 0) >= VB_FLOOR_ARD_VB_MIN_ARD
        and (entry.get("odds") or 0) >= VB_FLOOR_ARD_VB_MIN_ODDS
    )
    dev_ok = (
        (entry.get("dev_gap") or 0) >= VB_FLOOR_MIN_DEV_GAP
        and (entry.get("ar_deviation") or 0) >= VB_FLOOR_DEV_MIN_ARD
    )
    novelty_ok = passes_novelty_filter(entry)
    return bool(((ev_ok and ard_ok) or ard_vb_ok or dev_ok) and novelty_ok)


def load_indexes():
    print("[Load] horse_history_cache + jrdb_sed_index...")
    hh_path = config.ml_dir() / "horse_history_cache.json"
    with open(hh_path, encoding="utf-8") as f:
        history_cache = json.load(f)
    print(f"  History: {len(history_cache):,} horses")

    sed_path = config.indexes_dir() / "jrdb_sed_index.json"
    jrdb_sed_index = {}
    if sed_path.exists():
        with open(sed_path, encoding="utf-8") as f:
            jrdb_sed_index = json.load(f)
        print(f"  JRDB SED: {len(jrdb_sed_index):,} entries")
    return history_cache, jrdb_sed_index


from ml.utils.race_io import iter_date_dirs  # noqa: E402,F401


def build_race_meta(date_dir: Path) -> dict:
    """{race_id: {umaban: {ketto_num, jockey_code, venue_code, distance, track_type}}}"""
    meta = {}
    for rf in date_dir.glob("race_[0-9]*.json"):
        try:
            with open(rf, encoding="utf-8") as f:
                rd = json.load(f)
        except Exception:
            continue
        race_id = rd.get("race_id")
        if not race_id:
            continue
        venue = rd.get("venue_code", "")
        dist = rd.get("distance", 0) or 0
        tt = rd.get("track_type", "") or ""
        emap = {}
        for e in rd.get("entries", []):
            um = e.get("umaban")
            if um is None:
                continue
            emap[um] = {
                "ketto_num": e.get("ketto_num", ""),
                "jockey_code": e.get("jockey_code", ""),
                "venue_code": venue,
                "distance": dist,
                "track_type": tt,
            }
        meta[race_id] = emap
    return meta


def enrich_predictions(
    pred_path: Path,
    history_cache: dict,
    jrdb_sed_index: dict,
    dry_run: bool = False,
    reapply_vb: bool = False,
) -> dict:
    """1ファイル処理。返り値は統計 dict。"""
    stats = defaultdict(int)
    try:
        with open(pred_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as ex:
        stats["error"] += 1
        print(f"  [SKIP] {pred_path}: {ex}")
        return stats

    date_dir = pred_path.parent
    race_meta = build_race_meta(date_dir)

    races = data.get("races", [])
    for race in races:
        race_id = race.get("race_id")
        race_date = race.get("date") or ""
        rmeta = race_meta.get(race_id, {})
        if not race_date or not rmeta:
            stats["race_no_meta"] += 1
            continue

        for entry in race.get("entries", []):
            um = entry.get("umaban")
            em = rmeta.get(um)
            if not em or not em.get("ketto_num"):
                stats["entry_no_meta"] += 1
                continue

            cf = compute_career_features(
                ketto_num=em["ketto_num"],
                race_date=race_date,
                history_cache=history_cache,
                jrdb_sed_index=jrdb_sed_index,
                current_track_type=em["track_type"],
                current_distance=em["distance"],
                current_venue_code=em["venue_code"],
                current_jockey_code=em["jockey_code"],
            )

            score = int(cf.get("uncertainty_score", 0) or 0)
            entry["novelty_score"] = score
            entry["novelty_career_short"] = int(cf.get("uncertainty_career_short", 0) or 0)
            entry["novelty_first_surface"] = int(cf.get("uncertainty_first_surface", 0) or 0)
            entry["novelty_first_distance"] = int(cf.get("uncertainty_first_distance", 0) or 0)
            entry["novelty_first_venue"] = int(cf.get("uncertainty_first_venue", 0) or 0)
            entry["novelty_long_layoff"] = int(cf.get("uncertainty_long_layoff", 0) or 0)
            entry["novelty_jockey_change"] = int(cf.get("uncertainty_jockey_change", 0) or 0)

            ard = entry.get("ar_deviation")
            if ard is not None:
                decay = max(0.0, 1.0 - NOVELTY_DECAY * score)
                entry["ar_deviation_adj"] = round(50 + (ard - 50) * decay, 1)
            else:
                entry["ar_deviation_adj"] = None

            if reapply_vb:
                old_vb = bool(entry.get("is_value_bet", False))
                new_vb = recompute_is_value_bet(entry)
                entry["is_value_bet"] = new_vb
                if old_vb and not new_vb:
                    stats["vb_removed"] += 1
                elif new_vb and not old_vb:
                    stats["vb_added"] += 1

            stats["entries_enriched"] += 1
            stats[f"novelty_{score}"] += 1

        stats["races"] += 1

    if not dry_run:
        with open(pred_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="", help="YYYY-MM")
    ap.add_argument("--end", default="", help="YYYY-MM")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reapply-vb", action="store_true",
                    help="is_value_bet を novelty フィルタ込みで再計算")
    ap.add_argument("--pattern", default="predictions.json",
                    help="filename to enrich (predictions.json by default)")
    args = ap.parse_args()

    history_cache, jrdb_sed_index = load_indexes()

    total = defaultdict(int)
    files_done = 0
    for day_dir in iter_date_dirs(args.start, args.end):
        pred_path = day_dir / args.pattern
        if not pred_path.exists():
            continue
        stats = enrich_predictions(
            pred_path, history_cache, jrdb_sed_index,
            dry_run=args.dry_run, reapply_vb=args.reapply_vb,
        )
        for k, v in stats.items():
            total[k] += v
        files_done += 1
        if files_done % 20 == 0:
            print(f"  ... {files_done} files, {total['entries_enriched']:,} entries")

    print("\n=== Summary ===")
    print(f"Files processed: {files_done}")
    print(f"Races: {total['races']}")
    print(f"Entries enriched: {total['entries_enriched']:,}")
    if total["race_no_meta"]:
        print(f"Races without meta: {total['race_no_meta']}")
    if total["entry_no_meta"]:
        print(f"Entries without meta: {total['entry_no_meta']}")
    print("\nNovelty score distribution:")
    for s in range(7):
        n = total.get(f"novelty_{s}", 0)
        if n:
            pct = 100 * n / max(1, total["entries_enriched"])
            print(f"  score={s}: {n:>7,}  ({pct:5.1f}%)")
    if args.reapply_vb:
        print(f"\nVB recompute:  removed={total['vb_removed']:,}  added={total['vb_added']:,}")
    if args.dry_run:
        print("\n[DRY RUN] No files written.")


if __name__ == "__main__":
    main()

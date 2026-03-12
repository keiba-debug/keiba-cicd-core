#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backtest_cache.json に新しい日付のデータを追加する

predictions.json + race_{id}.json から backtest_cache 形式に変換して追記。
既存のキャッシュにない日付のみ追加する。

Usage:
    python -m ml.extend_backtest_cache                    # 自動検出（cache範囲外の日付を追加）
    python -m ml.extend_backtest_cache --dates 20260301 20260307 20260308
"""

import argparse
import json
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CACHE_PATH = Path("C:/KEIBA-CICD/data3/ml/backtest_cache.json")
RACES_DIR = Path("C:/KEIBA-CICD/data3/races")


def load_cache() -> list:
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def find_available_dates() -> list[str]:
    """predictions.json が存在する全日付を返す"""
    dates = []
    for year_dir in sorted(RACES_DIR.iterdir()):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue
                if (day_dir / "predictions.json").exists():
                    dates.append(f"{year_dir.name}{month_dir.name}{day_dir.name}")
    return dates


def load_results_from_race_json(day_dir: Path, race_id: str) -> dict:
    """race_{id}.json から馬番→結果データを取得"""
    race_path = day_dir / f"race_{race_id}.json"
    if not race_path.exists():
        return {}
    try:
        with open(race_path, encoding="utf-8") as f:
            rj = json.load(f)
        result = {}
        for e in rj.get("entries", []):
            uma = e.get("umaban")
            fp = e.get("finish_position")
            result[uma] = {
                "finish_position": fp,
                "is_win": 1 if fp == 1 else 0,
                "is_top3": 1 if fp is not None and fp <= 3 else 0,
                "place_odds_min": None,  # race JSONにはplace_oddsがない場合あり
            }
        return result
    except Exception as ex:
        print(f"  [WARN] Failed to load {race_path}: {ex}")
        return {}


def pred_to_cache_race(race: dict, day_dir: Path) -> dict | None:
    """predictions.json の 1 race → backtest_cache 形式に変換"""
    race_id = race.get("race_id", "")
    results = load_results_from_race_json(day_dir, race_id)

    if not results:
        return None  # 結果データなし → スキップ

    # 全馬の結果が0（未確定）なら skip
    has_valid = any(r["finish_position"] and r["finish_position"] > 0 for r in results.values())
    if not has_valid:
        return None

    entries = []
    for e in race.get("entries", []):
        uma = e.get("umaban")
        res = results.get(uma, {})
        fp = res.get("finish_position") or 0

        entries.append({
            "umaban": uma,
            "horse_name": e.get("horse_name", ""),
            "odds": e.get("odds", 0),
            "vb_gap": e.get("vb_gap", 0),
            "win_vb_gap": e.get("win_vb_gap", 0),
            "rank_p": e.get("rank_p", 99),
            "rank_w": e.get("rank_w", 99),
            "odds_rank": e.get("odds_rank", 99),
            "place_odds_min": e.get("place_odds_min"),
            "pred_proba_p_raw": e.get("pred_proba_p_raw") or e.get("pred_proba_p", 0),
            "predicted_margin": e.get("predicted_margin"),
            "win_ev": e.get("win_ev", 0),
            "place_ev": e.get("place_ev", 0),
            "comment_memo_trouble_score": e.get("comment_memo_trouble_score", 0),
            "closing_strength": e.get("closing_strength", 0),
            "horse_slow_start_rate": e.get("avg_first_corner_ratio", 0),  # predictions.json名
            "last_race_corner1_ratio": e.get("avg_first_corner_ratio", 0),
            "finish_position": fp,
            "is_win": 1 if fp == 1 else 0,
            "is_top3": 1 if fp > 0 and fp <= 3 else 0,
            "ar_deviation": e.get("ar_deviation"),
            "dev_gap": e.get("dev_gap", 0),
        })

    return {
        "race_id": race_id,
        "track_type": race.get("track_type", ""),
        "grade": race.get("grade", ""),
        "age_class": race.get("age_class", ""),
        "grade_offset": 0,  # predictions.jsonにはgrade_offsetがない
        "closing_race_proba": race.get("closing_race_proba", 0),
        "entries": entries,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="*", help="追加する日付 (YYYYMMDD)")
    parser.add_argument("--dry-run", action="store_true", help="実際には書き込まない")
    args = parser.parse_args()

    # 既存cache読み込み
    print(f"[Load] {CACHE_PATH}")
    cache = load_cache()
    existing_ids = {r["race_id"] for r in cache}
    existing_dates = sorted(set(r["race_id"][:8] for r in cache))
    print(f"  {len(cache)} races, {len(existing_dates)} dates")
    print(f"  Range: {existing_dates[0]} - {existing_dates[-1]}")

    # 追加対象の日付決定
    if args.dates:
        target_dates = args.dates
    else:
        all_dates = find_available_dates()
        target_dates = [d for d in all_dates if d not in existing_dates]

    if not target_dates:
        print("\n[INFO] 追加対象の日付がありません")
        return

    print(f"\n[Target] {len(target_dates)} dates: {target_dates}")

    # 各日付のpredictions.jsonを変換
    added_races = []
    skipped = 0
    for date_str in sorted(target_dates):
        year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
        day_dir = RACES_DIR / year / month / day
        pred_path = day_dir / "predictions.json"

        if not pred_path.exists():
            print(f"  {date_str}: predictions.json not found - skip")
            continue

        with open(pred_path, encoding="utf-8") as f:
            pred_data = json.load(f)

        date_added = 0
        date_skipped = 0
        for race in pred_data.get("races", []):
            rid = race.get("race_id", "")
            if rid in existing_ids:
                date_skipped += 1
                continue

            cache_race = pred_to_cache_race(race, day_dir)
            if cache_race:
                added_races.append(cache_race)
                existing_ids.add(rid)
                date_added += 1
            else:
                skipped += 1
                date_skipped += 1

        print(f"  {date_str}: +{date_added} races (skipped {date_skipped})")

    if not added_races:
        print("\n[INFO] 追加するレースがありません")
        return

    print(f"\n[Summary] +{len(added_races)} races to add (skipped {skipped} without results)")

    if args.dry_run:
        print("[DRY-RUN] 書き込みスキップ")
        return

    # 追記して保存
    cache.extend(added_races)
    # race_id順でソート
    cache.sort(key=lambda r: r["race_id"])

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    final_dates = sorted(set(r["race_id"][:8] for r in cache))
    print(f"\n[Saved] {CACHE_PATH}")
    print(f"  Total: {len(cache)} races, {len(final_dates)} dates")
    print(f"  Range: {final_dates[0]} - {final_dates[-1]}")


if __name__ == "__main__":
    main()

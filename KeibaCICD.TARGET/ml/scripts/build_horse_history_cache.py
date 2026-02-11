# -*- coding: utf-8 -*-
"""
馬の過去走キャッシュ構築

horse_race_index.json → integrated JSONを一括スキャン
→ 馬ごとの出走履歴をフラット化して保存

Output: data2/target/ml/horse_history_cache.json

Usage:
    cd KeibaCICD.TARGET
    python ml/scripts/build_horse_history_cache.py
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from common.config import get_keiba_data_root


def safe_float(val, default=None):
    """文字列を安全にfloatへ変換"""
    if val is None or val == "":
        return default
    try:
        return round(float(val), 1)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=None):
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def date_str_to_compact(date_str: str) -> str:
    """'2025/01/05' → '20250105'"""
    return date_str.replace("/", "")


def extract_entries_from_file(filepath: Path) -> list:
    """1つのintegrated JSONから全馬のレース結果を抽出"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    race_info = data.get("race_info", {})
    meta = data.get("meta", {})
    race_id = meta.get("race_id", "")
    date_str = race_info.get("date", "")
    if not date_str or not race_id:
        return []

    race_date = date_str_to_compact(date_str)
    venue = race_info.get("venue", "")
    track = race_info.get("track", "")
    distance = race_info.get("distance", 0)
    if not isinstance(distance, (int, float)):
        distance = 0
    track_condition = race_info.get("track_condition", "")
    entry_count = len(data.get("entries", []))

    rows = []
    for e in data.get("entries", []):
        horse_id = e.get("horse_id", "")
        if not horse_id:
            continue

        result = e.get("result", {})
        fp_str = result.get("finish_position", "")
        try:
            finish_pos = int(fp_str)
        except (ValueError, TypeError):
            continue  # 取消・除外はスキップ

        ed = e.get("entry_data", {})

        rows.append({
            "horse_id": horse_id,
            "race_id": race_id,
            "race_date": race_date,
            "finish_position": finish_pos,
            "last_3f": safe_float(result.get("last_3f")),
            "time": result.get("time", ""),
            "passing_orders": result.get("passing_orders", ""),
            "rating": safe_float(ed.get("rating")),
            "odds": safe_float(ed.get("odds")),
            "odds_rank": safe_int(ed.get("odds_rank")),
            "venue": venue,
            "track": track,
            "distance": int(distance),
            "track_condition": track_condition,
            "entry_count": entry_count,
            "horse_weight": safe_int(ed.get("horse_weight")),
            "trainer": ed.get("trainer", ""),
        })

    return rows


def main():
    print("=" * 60)
    print("馬の過去走キャッシュ構築")
    print("=" * 60)

    data_root = get_keiba_data_root()
    index_path = data_root / "cache" / "horse_race_index.json"
    output_path = data_root / "target" / "ml" / "horse_history_cache.json"

    # 1. horse_race_index 読み込み
    print("\n[1/4] horse_race_index.json 読み込み中...")
    with open(index_path, "r", encoding="utf-8") as f:
        horse_race_index = json.load(f)
    print(f"  馬数: {len(horse_race_index):,}")

    # 2. ユニークなファイルパスを収集
    print("\n[2/4] ユニークファイルパス収集中...")
    all_paths = set()
    for paths in horse_race_index.values():
        for p in paths:
            all_paths.add(p)
    print(f"  ユニークファイル数: {len(all_paths):,}")

    # 3. 全ファイルをスキャンし、馬ごとにグルーピング
    print("\n[3/4] integrated JSONスキャン中...")
    horse_history = defaultdict(list)
    total_entries = 0
    error_count = 0

    for i, filepath_str in enumerate(sorted(all_paths)):
        filepath = Path(filepath_str)
        if not filepath.exists():
            error_count += 1
            continue

        entries = extract_entries_from_file(filepath)
        for entry in entries:
            horse_id = entry.pop("horse_id")
            horse_history[horse_id].append(entry)
            total_entries += 1

        if (i + 1) % 2000 == 0:
            print(f"  {i+1:,}/{len(all_paths):,} files processed ({total_entries:,} entries)")

    print(f"  完了: {total_entries:,} entries from {len(all_paths):,} files")
    if error_count > 0:
        print(f"  ファイル不在: {error_count:,}")

    # 4. 日付順ソート + 出力
    print("\n[4/4] ソート + JSON出力中...")
    for horse_id in horse_history:
        horse_history[horse_id].sort(key=lambda x: x["race_date"])

    output = {
        "meta": {
            "created_at": datetime.now().isoformat(),
            "total_horses": len(horse_history),
            "total_entries": total_entries,
        },
        "horses": dict(horse_history),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n  Output: {output_path}")
    print(f"  Size: {file_size_mb:.1f} MB")
    print(f"  Horses: {len(horse_history):,}")
    print(f"  Entries: {total_entries:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()

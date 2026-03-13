#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レース検索インデックス生成 (v2)

race_date_index.json + 個別レースJSONから race_search_index.json を生成。
Web の /races-search ページで使用。

Usage:
    python -m builders.build_race_search_index
"""

import json
import sys
import glob
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# keiba-v2/ をルートに
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.config import data_root, indexes_dir, races_dir
from ml.features.baba_features import load_baba_index, race_id_to_baba_key

INDEXES_DIR = indexes_dir()
RACES_DIR = races_dir()

TRACK_TYPE_MAP = {"turf": "芝", "dirt": "ダ", "hurdle": "障"}

# race JSONのgrade値 → 検索フィルタ用の正規化値
GRADE_NORMALIZE = {
    "1勝クラス": "1勝",
    "2勝クラス": "2勝",
    "3勝クラス": "3勝",
    "Listed": "L",
    "障害OP": "OP",
    "障害G3": "G3",
    "S": "OP",
}


def load_race_date_index():
    """race_date_index.json をフラットなレース配列に展開"""
    idx_path = INDEXES_DIR / "race_date_index.json"
    if not idx_path.exists():
        print(f"[ERROR] {idx_path} not found")
        return []

    with open(idx_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    races = []
    for date_key, day_data in data.items():
        date_str = day_data.get("date", date_key)
        for track_data in day_data.get("tracks", []):
            venue = track_data.get("track", "")
            for race in track_data.get("races", []):
                races.append({
                    "raceId": race.get("id", ""),
                    "date": date_str,
                    "venue": venue,
                    "raceNumber": race.get("raceNumber", 0),
                    "raceName": race.get("raceName", ""),
                    "className": race.get("className", ""),
                    "distanceRaw": race.get("distance", ""),
                    "rpci": race.get("rpci"),
                    "paceType": race.get("paceType", ""),
                })
    return races


def parse_distance(raw: str):
    """'芝外・1600m' → ('芝', 1600)"""
    import re
    track = ""
    if "芝" in raw:
        track = "芝"
    elif "ダ" in raw:
        track = "ダ"
    elif "障" in raw:
        track = "障"
    m = re.search(r'(\d{3,4})', raw)
    dist = int(m.group(1)) if m else 0
    return track, dist


def load_race_json_data():
    """races/ ディレクトリの個別レースJSONから補足データを取得"""
    result = {}
    count = 0

    for year_dir in sorted(RACES_DIR.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue
                for f in day_dir.glob("race_[0-9]*.json"):
                    try:
                        with open(f, 'r', encoding='utf-8') as fh:
                            data = json.load(fh)

                        race_id = data.get("race_id", f.stem.replace("race_", ""))

                        # 勝ち馬 + タイム + 上がり3F
                        winner = ""
                        winner_time = ""
                        winner_last3f = None
                        entries = data.get("entries", [])
                        for e in entries:
                            fp = e.get("finish_position", e.get("result", {}).get("finish_position", ""))
                            if str(fp) == "1":
                                winner = e.get("horse_name", "")
                                winner_time = e.get("time", "")
                                winner_last3f = e.get("last_3f")
                                break

                        # 馬場状態
                        track_condition = data.get("track_condition", "")

                        # トラック種別
                        track_type_raw = data.get("track_type", "")
                        track_type = TRACK_TYPE_MAP.get(track_type_raw, track_type_raw)

                        # 天候
                        weather = data.get("weather", "")

                        # race_name, grade, distance, num_runners
                        # ペースv2分類（pace.race_trend_v2）
                        pace_data = data.get("pace") or {}
                        race_trend_v2 = pace_data.get("race_trend_v2", "")

                        result[race_id] = {
                            "raceName": data.get("race_name", ""),
                            "grade": data.get("grade", ""),
                            "trackType": track_type,
                            "distance": data.get("distance", 0),
                            "trackCondition": track_condition,
                            "entryCount": data.get("num_runners", len(entries)),
                            "winnerName": winner,
                            "winnerTime": winner_time,
                            "winnerLast3f": winner_last3f,
                            "weather": weather,
                            "raceTrendV2": race_trend_v2,
                        }
                        count += 1
                    except Exception:
                        continue

    print(f"  {count} race JSON files loaded")
    return result


def main():
    print("=" * 60)
    print("Build Race Search Index (v2)")
    print("=" * 60)
    start = datetime.now()

    # 1. race_date_index.json
    print("\n[1/3] Loading race_date_index.json...")
    races = load_race_date_index()
    print(f"  {len(races)} races from index")

    if not races:
        print("[ERROR] No races found. Abort.")
        return

    # 2. 個別レースJSON（勝ち馬・馬場状態・grade補完）
    print("\n[2/3] Loading race JSON files...")
    race_json_map = load_race_json_data()

    # 3. 馬場データ（含水率・クッション値）
    print("\n[3/3] Loading baba index (cushion/moisture)...")
    baba_index = load_baba_index()
    print(f"  {len(baba_index)} baba entries loaded")

    # マージ
    print("\nMerging...")
    output_races = []
    grade_stats = defaultdict(int)

    for race in races:
        race_id = race["raceId"]
        if not race_id:
            continue

        # race_date_index からの基本データ
        track_from_idx, dist_from_idx = parse_distance(race["distanceRaw"])

        # レースJSON からの補完データ
        rj = race_json_map.get(race_id, {})

        # race_name: JSONが持ってればそちら優先（より正確）
        race_name = rj.get("raceName") or race["raceName"]

        # grade: JSONが持ってればそちら（className → grade変換済み）
        grade_raw = rj.get("grade", "") or race["className"] or ""
        grade = GRADE_NORMALIZE.get(grade_raw, grade_raw)

        # track/distance: JSON優先
        track_type = rj.get("trackType", "") or track_from_idx
        distance = rj.get("distance", 0) or dist_from_idx

        # 馬場状態、頭数、勝ち馬: JSONのみ
        track_condition = rj.get("trackCondition", "")
        entry_count = rj.get("entryCount", 0)
        winner_name = rj.get("winnerName", "")
        winner_time = rj.get("winnerTime", "")
        winner_last3f = rj.get("winnerLast3f")
        weather = rj.get("weather", "")

        if grade:
            grade_stats[grade] += 1

        # ペース分類: race_trend_v2 があればそちら優先、なければ paceType フォールバック
        race_trend_v2 = rj.get("raceTrendV2", "")

        # 馬場データ（含水率・クッション値）
        baba_key = race_id_to_baba_key(race_id) if race_id else ""
        baba = baba_index.get(baba_key, {})
        cushion_value = baba.get("cushion")
        moisture_rate = baba.get("moisture_turf") if baba.get("moisture_turf") is not None else baba.get("moisture_dirt")

        output_races.append({
            "raceId": race_id,
            "date": race["date"],
            "venue": race["venue"],
            "raceNumber": race["raceNumber"],
            "raceName": race_name,
            "grade": grade,
            "track": track_type,
            "distance": distance,
            "trackCondition": track_condition,
            "entryCount": entry_count,
            "winnerName": winner_name,
            "winnerTime": winner_time,
            "winnerLast3f": winner_last3f,
            "weather": weather,
            "paceType": race["paceType"],
            "rpci": race["rpci"],
            "raceTrendV2": race_trend_v2,
            "cushionValue": cushion_value,
            "moistureRate": moisture_rate,
        })

    # ソート（日付降順）
    output_races.sort(key=lambda r: (r["date"], r["venue"], r["raceNumber"]), reverse=True)

    # 出力
    output_path = INDEXES_DIR / "race_search_index.json"
    output = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "version": "2.0",
            "race_count": len(output_races),
        },
        "races": output_races,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    elapsed = (datetime.now() - start).total_seconds()

    print(f"\nOutput: {output_path}")
    print(f"  Total races: {len(output_races)}")
    print(f"  With winner: {sum(1 for r in output_races if r['winnerName'])}")
    print(f"  With winner time: {sum(1 for r in output_races if r['winnerTime'])}")
    print(f"  With winner last3f: {sum(1 for r in output_races if r.get('winnerLast3f'))}")
    print(f"  With track condition: {sum(1 for r in output_races if r['trackCondition'])}")
    print(f"  With weather: {sum(1 for r in output_races if r['weather'])}")
    print(f"  With paceType: {sum(1 for r in output_races if r['paceType'])}")

    print(f"\nGrade distribution:")
    for k, v in sorted(grade_stats.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print(f"\nCompleted in {elapsed:.1f}s")


if __name__ == "__main__":
    main()

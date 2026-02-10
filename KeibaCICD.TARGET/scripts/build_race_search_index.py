#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レース検索インデックス生成スクリプト

race_date_index.json をベースに、以下のデータを結合してリッチなレース検索インデックスを生成:
  - race_trend_index.json  (5段階レース傾向)
  - grade_master.json      (G1/G2/G3判定)
  - SR_DATA                (馬場状態・頭数)
  - integrated_*.json      (勝ち馬名・出走頭数)

Usage:
    python build_race_search_index.py
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.config import get_keiba_data_root, get_jv_data_root, get_jv_se_data_path, get_target_data_dir

DATA_ROOT = get_keiba_data_root()
JV_DATA_ROOT = get_jv_data_root()
SE_DATA_PATH = get_jv_se_data_path()

SR_RECORD_LEN = 1272

TRACK_NAMES_JP = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}

BABA_LABELS = {"1": "良", "2": "稍重", "3": "重", "4": "不良"}


def decode_sjis(data: bytes) -> str:
    return data.decode('shift_jis', errors='replace').strip().replace('\u3000', '').replace('@', '')


# ── Step 1: race_date_index.json のフラット化 ──

def load_race_date_index() -> List[dict]:
    """race_date_index.json をフラットなレース配列に展開"""
    index_path = DATA_ROOT / "cache" / "race_date_index.json"
    if not index_path.exists():
        print(f"[ERROR] {index_path} not found")
        return []

    with open(index_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    races = []
    for date_key, date_entry in data.items():
        date_str = date_entry.get("date", date_key)
        for track_entry in date_entry.get("tracks", []):
            venue = track_entry.get("track", "")
            for race in track_entry.get("races", []):
                races.append({
                    "raceId": race.get("id", ""),
                    "date": date_str,
                    "venue": venue,
                    "raceNumber": race.get("raceNumber", 0),
                    "raceName": race.get("raceName", ""),
                    "className": race.get("className", ""),
                    "distanceRaw": race.get("distance", ""),
                    "rpci": race.get("rpci"),
                })
    return races


# ── Step 2: race_trend_index.json ──

def load_race_trend_index() -> Dict[str, str]:
    """raceId → trend マップ"""
    path = get_target_data_dir() / "race_trend_index.json"
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {rid: entry.get("trend", "") for rid, entry in data.get("races", {}).items()}


# ── Step 3: grade_master.json ──

def load_grade_master() -> Dict[str, List[str]]:
    path = get_target_data_dir() / "grade_master.json"
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_race_name(name: str) -> str:
    """全角英数→半角に正規化してグレードプレフィックスを除去"""
    n = name
    n = re.sub(r'[Ｇｇ][１1]', '', n)
    n = re.sub(r'[Ｇｇ][２2]', '', n)
    n = re.sub(r'[Ｇｇ][３3]', '', n)
    n = re.sub(r'^[Ｌ]', '', n)
    return n.strip()


def classify_grade(race_name: str, class_name: str, grade_master: dict) -> str:
    """レース名とクラス名からグレードを判定"""
    cleaned = normalize_race_name(race_name)

    for g1_name in grade_master.get("g1_races", []):
        if g1_name in cleaned or g1_name in race_name:
            return "G1"
    for g2_name in grade_master.get("g2_races", []):
        if g2_name in cleaned or g2_name in race_name:
            return "G2"
    for g3_name in grade_master.get("g3_races", []):
        if g3_name in cleaned or g3_name in race_name:
            return "G3"

    # raceNameにG1/G2/G3が直接含まれる場合
    if re.search(r'[Gg][Ｇ]?[1１]', race_name):
        return "G1"
    if re.search(r'[Gg][Ｇ]?[2２]', race_name):
        return "G2"
    if re.search(r'[Gg][Ｇ]?[3３]', race_name):
        return "G3"

    # リステッド
    if 'Ｌ' in race_name or '(L)' in race_name:
        return "L"

    # クラスから判定
    cn = class_name or race_name
    if 'オープン' in cn or 'OP' in cn:
        return "OP"
    if '3勝' in cn:
        return "3勝"
    if '2勝' in cn:
        return "2勝"
    if '1勝' in cn:
        return "1勝"
    if '未勝利' in cn:
        return "未勝利"
    if '新馬' in cn:
        return "新馬"

    # 特別戦（クラス不明だが名前付き）
    return ""


# ── Step 4: distance パース ──

def parse_distance_field(distance_str: str) -> Tuple[str, int]:
    """'芝外・1600m' → ('芝', 1600)"""
    track = ""
    if "芝" in distance_str:
        track = "芝"
    elif "ダ" in distance_str:
        track = "ダ"

    m = re.search(r'(\d{3,4})', distance_str)
    dist = int(m.group(1)) if m else 0
    return track, dist


# ── Step 5: SR_DATA スキャン（馬場状態・頭数） ──

def scan_sr_data_for_baba_and_runners(years: List[int]) -> Dict[str, dict]:
    """SR_DATAからraceId → {trackCondition, entryCount} を構築"""
    result = {}
    total = 0

    for year in years:
        year_dir = SE_DATA_PATH / str(year)
        if not year_dir.exists():
            continue

        sr_files = list(year_dir.glob("SR*.DAT"))
        for sr_file in sr_files:
            try:
                file_data = sr_file.read_bytes()
            except Exception:
                continue

            file_len = len(file_data)
            pos = 0
            while pos + SR_RECORD_LEN <= file_len:
                record = file_data[pos:pos + SR_RECORD_LEN]
                pos += SR_RECORD_LEN

                try:
                    rec_type = decode_sjis(record[0:2])
                    if rec_type != "RA":
                        continue
                    data_kubun = decode_sjis(record[2:3])
                    if data_kubun != "7":
                        continue

                    year_str = decode_sjis(record[11:15])
                    jyo_cd = decode_sjis(record[19:21])
                    kaiji = decode_sjis(record[21:23])
                    nichiji = decode_sjis(record[23:25])
                    race_num = decode_sjis(record[25:27])

                    if not year_str.isdigit():
                        continue

                    race_id = f"{year_str}{kaiji}{jyo_cd}{nichiji}{race_num}"

                    # 頭数
                    syusso_str = decode_sjis(record[883:885])
                    num_runners = int(syusso_str) if syusso_str.isdigit() else 0

                    # track type for baba selection
                    track_cd = decode_sjis(record[705:707])
                    is_turf = track_cd.startswith("1")

                    # 馬場状態
                    siba_baba_cd = decode_sjis(record[888:889])
                    dirt_baba_cd = decode_sjis(record[889:890])
                    baba_cd = siba_baba_cd if is_turf else dirt_baba_cd
                    track_condition = BABA_LABELS.get(baba_cd, "")

                    result[race_id] = {
                        "trackCondition": track_condition,
                        "entryCount": num_runners,
                    }
                    total += 1
                except Exception:
                    continue

    print(f"  SR_DATA: {total} races loaded")
    return result


# ── Step 6: integrated_*.json スキャン（勝ち馬名） ──

def scan_integrated_for_winners() -> Dict[str, dict]:
    """integrated_*.json から raceId → {winnerName, entryCount}"""
    result = {}
    races_dir = DATA_ROOT / "races"
    if not races_dir.exists():
        return result

    count = 0
    for year_dir in sorted(races_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue
                temp_dir = day_dir / "temp"
                if not temp_dir.exists():
                    continue
                for f in temp_dir.glob("integrated_*.json"):
                    try:
                        race_id = f.stem.replace("integrated_", "")
                        with open(f, 'r', encoding='utf-8') as fh:
                            data = json.load(fh)

                        winner_name = ""
                        entry_count = 0

                        entries = data.get("entries", [])
                        entry_count = data.get("analysis", {}).get("entry_count", len(entries))

                        for entry in entries:
                            res = entry.get("result", {})
                            pos = res.get("finish_position", "")
                            if str(pos) == "1":
                                winner_name = entry.get("horse_name", "")
                                break

                        result[race_id] = {
                            "winnerName": winner_name,
                            "entryCount": entry_count,
                        }
                        count += 1
                    except Exception:
                        continue

    print(f"  integrated: {count} files loaded")
    return result


# ── メイン処理 ──

def main():
    print("=" * 60)
    print("Build Race Search Index")
    print("=" * 60)
    start_time = datetime.now()

    # 1. race_date_index.json
    print("\n[1/5] Loading race_date_index.json...")
    races = load_race_date_index()
    print(f"  {len(races)} races loaded")

    if not races:
        print("[ERROR] No races found")
        return

    # 2. race_trend_index.json
    print("\n[2/5] Loading race_trend_index.json...")
    trend_map = load_race_trend_index()
    print(f"  {len(trend_map)} trends loaded")

    # 3. grade_master.json
    print("\n[3/5] Loading grade_master.json...")
    grade_master = load_grade_master()
    g_count = sum(len(v) for k, v in grade_master.items() if k.endswith("_races"))
    print(f"  {g_count} graded race names loaded")

    # 4. SR_DATA (馬場状態・頭数)
    print("\n[4/5] Scanning SR_DATA for track condition & runners...")
    years_in_data = set()
    for r in races:
        y = r["date"][:4]
        if y.isdigit():
            years_in_data.add(int(y))
    sr_map = scan_sr_data_for_baba_and_runners(sorted(years_in_data))

    # 5. integrated_*.json (勝ち馬名)
    print("\n[5/5] Scanning integrated_*.json for winners...")
    winner_map = scan_integrated_for_winners()

    # 結合
    print("\nMerging data...")
    output_races = []
    stats = defaultdict(int)

    for race in races:
        race_id = race["raceId"]
        if not race_id:
            continue

        # distance parse
        track_type, distance = parse_distance_field(race["distanceRaw"])

        # grade
        grade = classify_grade(race["raceName"], race["className"], grade_master)
        if grade:
            stats[f"grade_{grade}"] += 1

        # trend
        race_trend = trend_map.get(race_id, "")
        if race_trend:
            stats[f"trend_{race_trend}"] += 1

        # SR_DATA: trackCondition, entryCount
        sr_info = sr_map.get(race_id, {})
        track_condition = sr_info.get("trackCondition", "")
        entry_count = sr_info.get("entryCount", 0)

        # integrated: winnerName (entryCount fallback)
        int_info = winner_map.get(race_id, {})
        winner_name = int_info.get("winnerName", "")
        if entry_count == 0:
            entry_count = int_info.get("entryCount", 0)

        output_races.append({
            "raceId": race_id,
            "date": race["date"],
            "venue": race["venue"],
            "raceNumber": race["raceNumber"],
            "raceName": race["raceName"],
            "grade": grade,
            "track": track_type,
            "distance": distance,
            "trackCondition": track_condition,
            "entryCount": entry_count,
            "winnerName": winner_name,
            "raceTrend": race_trend,
            "rpci": race["rpci"],
        })

    # 日付降順ソート
    output_races.sort(key=lambda r: (r["date"], r["venue"], r["raceNumber"]), reverse=True)

    # 出力
    output_path = DATA_ROOT / "cache" / "race_search_index.json"
    output = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "race_count": len(output_races),
            "sources": [
                "race_date_index.json",
                "race_trend_index.json",
                "grade_master.json",
                "SR_DATA",
                "integrated_*.json",
            ],
        },
        "races": output_races,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\nOutput: {output_path}")
    print(f"  Total races: {len(output_races)}")
    print(f"  With winner: {sum(1 for r in output_races if r['winnerName'])}")
    print(f"  With track condition: {sum(1 for r in output_races if r['trackCondition'])}")
    print(f"  With trend: {sum(1 for r in output_races if r['raceTrend'])}")
    print(f"\nGrade distribution:")
    for k, v in sorted(stats.items()):
        if k.startswith("grade_"):
            print(f"  {k[6:]}: {v}")
    print(f"\nTrend distribution:")
    for k, v in sorted(stats.items()):
        if k.startswith("trend_"):
            print(f"  {k[6:]}: {v}")
    print(f"\nCompleted in {elapsed:.1f}s")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN JV-Data RAレコード解析スクリプト

DE_DATAのDRファイル（出馬表レース情報）からRAレコードを解析し、
発走時刻などのレース詳細情報を抽出します。

Usage:
    python parse_jv_race_data.py --date 2026-01-24
    python parse_jv_race_data.py --date 2026-01-24 --output race_times.json
"""

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# JRA-VAN データパス（Yドライブ）
JV_DATA_ROOT = Path("Y:/")
DE_DATA_PATH = JV_DATA_ROOT / "DE_DATA"

# 競馬場コード対応表
TRACK_CODES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}

# 逆引き辞書
TRACK_NAMES_TO_CODES = {v: k for k, v in TRACK_CODES.items()}


@dataclass
class RaceRecord:
    """RAレコードのパース結果"""
    year: str  # 開催年
    month_day: str  # 開催月日 (MMDD)
    track_code: str  # 競馬場コード
    track_name: str  # 競馬場名
    kaiji: str  # 回次
    nichiji: str  # 日次
    race_num: str  # レース番号
    hasso_time: str  # 発走時刻 (HHMM)
    hasso_time_formatted: str  # 発走時刻 (HH:MM)
    race_name: str  # レース名
    distance: str  # 距離
    track_type: str  # トラックコード
    
    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month_day": self.month_day,
            "date": f"{self.year}-{self.month_day[:2]}-{self.month_day[2:]}",
            "track_code": self.track_code,
            "track_name": self.track_name,
            "kaiji": int(self.kaiji),
            "nichiji": int(self.nichiji),
            "race_num": int(self.race_num),
            "hasso_time": self.hasso_time_formatted,
            "race_name": self.race_name.strip(),
            "distance": int(self.distance) if self.distance.strip().isdigit() else 0,
            "track_type": self.track_type,
        }


def parse_ra_record(line: bytes) -> Optional[RaceRecord]:
    """
    RAレコードを解析
    
    TARGETのDRファイル形式:
    - レコード長: 約751バイト
    - 発走時刻: 末尾から13-16番目の4桁 (HHMM形式)
    
    RACE_ID構造 (offset 12-27, 16バイト):
    - Year: offset 12-15 (4バイト)
    - MonthDay: offset 16-19 (4バイト)
    - JyoCD: offset 20-21 (2バイト)
    - Kaiji: offset 22-23 (2バイト)
    - Nichiji: offset 24-25 (2バイト)
    - RaceNum: offset 26-27 (2バイト)
    """
    try:
        # Shift-JISでデコード（改行コードを除去）
        content = line.rstrip(b'\r\n').decode('shift_jis', errors='replace')
        
        # RAレコードかチェック（先頭2バイト）
        if not content.startswith("RA"):
            return None
        
        # レコード長チェック（最低限のサイズ）
        if len(content) < 100:
            return None
        
        # Python indexは0-based
        year = content[11:15]  # offset 12-15
        month_day = content[15:19]  # offset 16-19
        track_code = content[19:21]  # offset 20-21
        kaiji = content[21:23]  # offset 22-23
        nichiji = content[23:25]  # offset 24-25
        race_num = content[25:27]  # offset 26-27
        
        # レース名: offset 28以降 (60バイト程度)
        # @記号（全角スペース）で埋められている
        race_name_raw = content[27:87]
        # 全角スペース(＠)を除去してトリム
        race_name = race_name_raw.replace('＠', '').replace('@', ' ').strip()
        
        # 発走時刻: 末尾から17番目から4桁
        # 例: ...00000000000000000000000000000000009550000160000000
        #                                        ^^^^
        # index -17 から -13 がHHMM形式の発走時刻
        hasso_time = content[-17:-13]
        
        # 4桁の数値かチェック、無効な場合は末尾から探す
        if not (hasso_time.isdigit() and len(hasso_time) == 4):
            # 末尾から探す
            last_part = content[-50:]
            hasso_time = "0000"
            # 4桁の数字を探す
            for i in range(len(last_part) - 4):
                candidate = last_part[i:i+4]
                if candidate.isdigit():
                    hour = int(candidate[:2])
                    minute = int(candidate[2:])
                    if 6 <= hour <= 18 and 0 <= minute <= 59:
                        hasso_time = candidate
                        break
        
        # 時刻フォーマット
        hasso_time_formatted = ""
        if hasso_time and len(hasso_time) >= 4 and hasso_time.isdigit():
            hasso_time_formatted = f"{hasso_time[:2]}:{hasso_time[2:]}"
        
        # 距離を抽出（末尾のデータから）
        # パターン: ...180000002400... で 2400 が距離
        distance = ""
        # 複数のパターンを試す
        for i in range(-50, -10):
            if i + 4 <= len(content):
                candidate = content[i:i+4]
                if candidate.isdigit():
                    d = int(candidate)
                    if 800 <= d <= 4000:  # 距離の妥当な範囲
                        distance = candidate
                        break
        
        track_type = ""
        track_name = TRACK_CODES.get(track_code, f"Unknown({track_code})")
        
        return RaceRecord(
            year=year,
            month_day=month_day,
            track_code=track_code,
            track_name=track_name,
            kaiji=kaiji,
            nichiji=nichiji,
            race_num=race_num,
            hasso_time=hasso_time,
            hasso_time_formatted=hasso_time_formatted,
            race_name=race_name,
            distance=distance,
            track_type=track_type,
        )
        
    except Exception as e:
        print(f"解析エラー: {e}")
        return None


def parse_dr_file(file_path: Path) -> List[RaceRecord]:
    """
    DRファイル（出馬表レース情報）を解析
    """
    records = []
    
    if not file_path.exists():
        print(f"ファイルが見つかりません: {file_path}")
        return records
    
    try:
        with open(file_path, 'rb') as f:
            for line in f:
                record = parse_ra_record(line)
                if record:
                    records.append(record)
    except Exception as e:
        print(f"ファイル読み込みエラー: {e}")
    
    return records


def get_race_times_for_date(date_str: str) -> Dict[str, List[dict]]:
    """
    指定日付のレース発走時刻を取得
    
    Args:
        date_str: 日付文字列 (YYYY-MM-DD形式)
        
    Returns:
        競馬場ごとの発走時刻データ
    """
    # 日付をパース
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    year = dt.strftime("%Y")
    file_date = dt.strftime("%Y%m%d")
    
    # DRファイルパス
    dr_file = DE_DATA_PATH / year / f"DR{file_date}.DAT"
    
    print(f"データファイル: {dr_file}")
    
    # 解析
    records = parse_dr_file(dr_file)
    
    # 競馬場ごとにグループ化
    result: Dict[str, List[dict]] = {}
    for record in records:
        track = record.track_name
        if track not in result:
            result[track] = []
        result[track].append(record.to_dict())
    
    # レース番号順にソート
    for track in result:
        result[track].sort(key=lambda x: x["race_num"])
    
    return result


def update_race_info_json(date_str: str, race_times: Dict[str, List[dict]], dry_run: bool = False) -> int:
    """
    race_info.jsonに発走時刻を追加
    
    Returns:
        更新したレース数
    """
    # KEIBA-CICD データパス
    keiba_cicd_data = Path("Z:/KEIBA-CICD/data2/races")
    
    parts = date_str.split("-")
    year, month, day = parts[0], parts[1], parts[2]
    
    race_info_path = keiba_cicd_data / year / month / day / "race_info.json"
    
    if not race_info_path.exists():
        print(f"race_info.jsonが見つかりません: {race_info_path}")
        return 0
    
    # 発走時刻の辞書を作成 (競馬場名, レース番号) -> 発走時刻
    time_map = {}
    for track, races in race_times.items():
        for race in races:
            key = (track, race["race_num"])
            time_map[key] = race["hasso_time"]
    
    # race_info.jsonを読み込み
    with open(race_info_path, 'r', encoding='utf-8') as f:
        race_info = json.load(f)
    
    updated_count = 0
    kaisai_data = race_info.get("kaisai_data", {})
    
    for kaisai_key, races in kaisai_data.items():
        # kaisai_keyから競馬場名を抽出 (例: "1回中山8日目" -> "中山")
        track_name = ""
        for name in TRACK_CODES.values():
            if name in kaisai_key:
                track_name = name
                break
        
        if not track_name:
            continue
        
        for race in races:
            race_no_str = race.get("race_no", "")
            if not race_no_str:
                continue
            
            race_num = int(race_no_str.replace("R", ""))
            key = (track_name, race_num)
            
            if key in time_map:
                new_time = time_map[key]
                old_time = race.get("start_time", "")
                
                if old_time != new_time:
                    print(f"  {track_name} {race_num}R: {old_time or '(なし)'} -> {new_time}")
                    race["start_time"] = new_time
                    updated_count += 1
    
    if updated_count == 0:
        print("更新対象のレースがありませんでした")
        return 0
    
    print(f"\n{updated_count} レースの発走時刻を更新")
    
    if dry_run:
        print("[DRY RUN] ファイル更新をスキップ")
        return updated_count
    
    # ファイルを書き込み
    with open(race_info_path, 'w', encoding='utf-8') as f:
        json.dump(race_info, f, ensure_ascii=False, indent=2)
    
    print(f"更新完了: {race_info_path}")
    return updated_count


def main():
    parser = argparse.ArgumentParser(
        description="JRA-VAN JV-DataからRAレコードを解析し発走時刻を取得"
    )
    parser.add_argument(
        "--date", "-d",
        type=str,
        required=True,
        help="対象日付 (YYYY-MM-DD形式)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="出力ファイルパス (JSON形式)"
    )
    parser.add_argument(
        "--update-race-info",
        action="store_true",
        help="race_info.jsonに発走時刻を追加"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイル更新を実行しない (--update-race-info用)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細出力"
    )
    
    args = parser.parse_args()
    
    # 発走時刻取得
    race_times = get_race_times_for_date(args.date)
    
    if not race_times:
        print(f"データが見つかりませんでした: {args.date}")
        return
    
    # 結果表示
    print(f"\n[DATE] {args.date} の発走時刻一覧")
    print("=" * 60)
    
    for track, races in race_times.items():
        print(f"\n[TRACK] {track}競馬場 ({len(races)}レース)")
        print("-" * 40)
        for race in races:
            time_str = race.get('hasso_time', '--:--')
            race_name = race.get('race_name', '')[:20]
            print(f"  {race['race_num']:2d}R  {time_str}  {race_name}")
    
    # race_info.json更新
    if args.update_race_info:
        print("\n" + "=" * 60)
        print("[UPDATE] race_info.json を更新")
        print("-" * 40)
        update_race_info_json(args.date, race_times, args.dry_run)
    
    # ファイル出力
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(race_times, f, ensure_ascii=False, indent=2)
        print(f"\n出力ファイル: {args.output}")
    
    # JSON形式で標準出力
    if args.verbose:
        print("\n[JSON]:")
        print(json.dumps(race_times, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

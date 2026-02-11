#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN CK_DATA（調教データ）パーサー

JV-Data仕様書に基づき、CK_DATA/HCxx (坂路) および CK_DATA/WCxx (コース) から
調教データを解析し、馬ごとの調教履歴を抽出します。

【JV_HC_HANRO 構造体（坂路調教：60バイト）】
- 1-11: head（レコードヘッダー）
- 12: TresenKubun（トレセン区分: 1=美浦, 2=栗東）
- 13-20: ChokyoDate（調教年月日: YYYYMMDD）
- 21-24: ChokyoTime（調教時刻: HHMM）
- 25-34: KettoNum（血統登録番号: 10桁）
- 35-38: HaronTime4（4Fタイム合計: 10分の1秒単位）
- 39-41: LapTime4（ラップタイム 4F-3F）
- 42-45: HaronTime3（3Fタイム合計）
- 46-48: LapTime3（ラップタイム 3F-2F）
- 49-52: HaronTime2（2Fタイム合計）
- 53-55: LapTime2（ラップタイム 2F-1F）
- 56-58: LapTime1（ラップタイム 1F）
- 59-60: crlf

データファイル命名規則（実データはJRA-VAN同様）:
- HC0YYYYMMDD.DAT: 美浦坂路
- HC1YYYYMMDD.DAT: 栗東坂路
- WC0YYYYMMDD.DAT: 美浦コース（ウッド）
- WC1YYYYMMDD.DAT: 栗東コース（ウッド）

Usage:
    python parse_ck_data.py --debug  # フォーマット解析
    python parse_ck_data.py --horse 2023101234 --date 20260125
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# UTF-8出力
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 共通設定モジュールをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.config import get_jv_ck_data_path

# CK_DATAパス
CK_DATA_ROOT = get_jv_ck_data_path()

# トレセン名
TRAINING_CENTER = {
    "1": "美浦",
    "2": "栗東",
}

# 調教場所（HC=坂路, WC/WD=コース/ウッド）。ファイル名は大文字で照合。
TRAINING_TYPE = {
    "HC": "坂路",
    "WC": "コース",
    "WD": "コース",
}

# 好タイム基準（設定可能にする）
# キー: (トレセン, 場所)
DEFAULT_GOOD_TIME_THRESHOLDS = {
    ("美浦", "坂路"): {"4F": 52.9, "lap": 13.4},
    ("栗東", "坂路"): {"4F": 53.9, "lap": 13.9},
    ("美浦", "コース"): {"4F": 52.2, "lap": 12.6},
    ("栗東", "コース"): {"4F": 52.2, "lap": 12.8},
}


@dataclass
class TrainingConfig:
    """好タイム判定の設定"""
    good_time_thresholds: Dict[Tuple[str, str], Dict[str, float]] = field(
        default_factory=lambda: DEFAULT_GOOD_TIME_THRESHOLDS.copy()
    )
    
    @classmethod
    def load_from_file(cls, filepath: Path) -> 'TrainingConfig':
        """設定ファイルから読み込み"""
        config = cls()
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, val in data.get('good_time_thresholds', {}).items():
                        parts = key.split('_')
                        if len(parts) == 2:
                            config.good_time_thresholds[(parts[0], parts[1])] = val
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
        return config
    
    def save_to_file(self, filepath: Path):
        """設定ファイルに保存"""
        data = {
            'good_time_thresholds': {
                f"{k[0]}_{k[1]}": v
                for k, v in self.good_time_thresholds.items()
            }
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# グローバル設定
_config = TrainingConfig()


@dataclass
class TrainingRecord:
    """調教レコード"""
    date: str              # 調教日 YYYYMMDD
    time: str              # 時刻 HHMM
    center: str            # トレセン（美浦/栗東）
    location: str          # 場所（坂路/コース）
    horse_id: str          # 馬ID（血統登録番号10桁）
    time_4f: float         # 4Fタイム（秒）
    time_3f: float         # 3Fタイム（秒）
    time_2f: float         # 2Fタイム（秒）
    lap_4: float           # ラップ 4F-3F（1F）
    lap_3: float           # ラップ 3F-2F（1F）
    lap_2: float           # ラップ 2F-1F（1F）
    lap_1: float           # ラップ 1F（最終1F）
    
    @property
    def is_good_time(self) -> bool:
        """好タイム判定"""
        threshold = _config.good_time_thresholds.get(
            (self.center, self.location),
            {"4F": 54.0, "lap": 14.0}
        )
        return self.time_4f <= threshold["4F"]
    
    @property
    def has_good_lap(self) -> bool:
        """好ラップ判定（終い1F）"""
        threshold = _config.good_time_thresholds.get(
            (self.center, self.location),
            {"4F": 54.0, "lap": 14.0}
        )
        return self.lap_1 <= threshold["lap"]
    
    @property
    def acceleration(self) -> str:
        """加速評価（+/=/-)"""
        # 終い2Fのラップと終い1Fのラップを比較
        if self.lap_1 < self.lap_2:
            return "+"  # 加速
        elif self.lap_1 > self.lap_2:
            return "-"  # 減速
        else:
            return "="  # 同じ
    
    @property
    def speed_class(self) -> str:
        """スピード分類（S/A/B/C/D）"""
        threshold = _config.good_time_thresholds.get(
            (self.center, self.location),
            {"4F": 54.0}
        )
        base = threshold["4F"]
        
        if self.time_4f <= base - 2.0:
            return "S"  # 好タイム
        elif self.time_4f <= base:
            return "A"  # やや好タイム
        elif self.time_4f <= base + 2.0:
            return "B"  # 標準
        elif self.time_4f <= base + 4.0:
            return "C"  # やや遅め
        else:
            return "D"  # 遅い
    
    @property
    def lap_class(self) -> str:
        """ラップ分類（S/A/B/C/D + 加速）"""
        threshold = _config.good_time_thresholds.get(
            (self.center, self.location),
            {"lap": 14.0}
        )
        base = threshold["lap"]
        
        if self.lap_1 <= base - 1.5:
            letter = "S"
        elif self.lap_1 <= base - 0.5:
            letter = "A"
        elif self.lap_1 <= base + 0.5:
            letter = "B"
        elif self.lap_1 <= base + 1.0:
            letter = "C"
        else:
            letter = "D"
        
        return f"{letter}{self.acceleration}"

    @property
    def upgraded_lap_class(self) -> str:
        """
        ラップ分類のSS昇格版
        好タイム + S分類 + (加速or同タイム) → SS
        """
        # 好タイムでない場合は通常のlap_class
        if not self.is_good_time:
            return self.lap_class

        # S+, S= の場合のみSS昇格
        if self.lap_class in ("S+", "S="):
            return "SS"

        return self.lap_class

    def __str__(self):
        return (
            f"{self.date} {self.time} {self.center}{self.location} "
            f"4F={self.time_4f:.1f} 3F={self.time_3f:.1f} 1F={self.lap_1:.1f} "
            f"[{self.speed_class}] [{self.lap_class}]"
            f"{' ★' if self.is_good_time else ''}"
        )
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "date": self.date,
            "time": self.time,
            "center": self.center,
            "location": self.location,
            "horse_id": self.horse_id,
            "time_4f": self.time_4f,
            "time_3f": self.time_3f,
            "time_2f": self.time_2f,
            "lap_4": self.lap_4,
            "lap_3": self.lap_3,
            "lap_2": self.lap_2,
            "lap_1": self.lap_1,
            "is_good_time": self.is_good_time,
            "has_good_lap": self.has_good_lap,
            "speed_class": self.speed_class,
            "lap_class": self.lap_class,
            "upgraded_lap_class": self.upgraded_lap_class,
            "acceleration": self.acceleration,
        }


def _make_record(
    raw_line: str, center: str, location: str,
    time_4f: float, time_3f: float, time_2f: float,
    lap_4: float, lap_3: float, lap_2: float, lap_1: float,
) -> Optional[TrainingRecord]:
    """共通ヘッダー抽出＋TrainingRecord生成"""
    try:
        date = raw_line[1:9].strip()
        time = raw_line[9:13].strip()
        horse_id = raw_line[13:23].strip()  # 前後空白を除去（HC/WCでマッチするように）
        if time_4f < 40.0 or time_4f > 80.0:
            return None
        if lap_1 < 10.0 or lap_1 > 20.0:
            return None
        return TrainingRecord(
            date=date,
            time=time,
            center=center,
            location=location,
            horse_id=horse_id,
            time_4f=time_4f,
            time_3f=time_3f,
            time_2f=time_2f,
            lap_4=lap_4,
            lap_3=lap_3,
            lap_2=lap_2,
            lap_1=lap_1,
        )
    except (ValueError, IndexError):
        return None


def parse_hc_record(raw_line: str, center: str, location: str) -> Optional[TrainingRecord]:
    """
    HC*.DAT（坂路・47バイト）をパース。
    実際の仕様: 0 RecordType, 1-8 Date, 9-12 Time, 13-22 KettoNum,
    23-26 Time4F(4桁), 27-29 Lap4(3桁), 30-33 Time3F(4桁), 34-36 Lap3(3桁),
    37-40 Time2F(4桁), 41-43 Lap2(3桁), 44-46 Lap1(3桁)（0.1秒単位）
    """
    try:
        if len(raw_line) < 47:
            return None
        time_4f = int(raw_line[23:27]) / 10.0
        lap_4 = int(raw_line[27:30]) / 10.0
        time_3f = int(raw_line[30:34]) / 10.0
        lap_3 = int(raw_line[34:37]) / 10.0
        time_2f = int(raw_line[37:41]) / 10.0
        lap_2 = int(raw_line[41:44]) / 10.0
        lap_1 = int(raw_line[44:47]) / 10.0
        return _make_record(
            raw_line, center, location,
            time_4f, time_3f, time_2f, lap_4, lap_3, lap_2, lap_1,
        )
    except (ValueError, IndexError):
        return None


def parse_wc_record(raw_line: str, center: str, location: str) -> Optional[TrainingRecord]:
    """
    WC*.DAT（コース・92バイト）をパース。
    実際の仕様: 0 RecordType, 1-8 Date, 9-12 Time, 13-22 KettoNum,
    61-65 Time5F(4桁), 68-72 Time4F(4桁), 72-75 Lap4(3桁),
    75-79 Time3F(4桁), 79-82 Lap3(3桁), 82-86 Time2F(4桁),
    86-89 Lap2(3桁), 89-92 Lap1(3桁)（0.1秒単位）
    """
    try:
        if len(raw_line) < 92:
            return None
        time_4f = int(raw_line[68:72]) / 10.0
        lap_4 = int(raw_line[72:75]) / 10.0
        time_3f = int(raw_line[75:79]) / 10.0
        lap_3 = int(raw_line[79:82]) / 10.0
        time_2f = int(raw_line[82:86]) / 10.0
        lap_2 = int(raw_line[86:89]) / 10.0
        lap_1 = int(raw_line[89:92]) / 10.0
        return _make_record(
            raw_line, center, location,
            time_4f, time_3f, time_2f, lap_4, lap_3, lap_2, lap_1,
        )
    except (ValueError, IndexError):
        return None


def parse_hc_47_record(raw_line: str, center: str, location: str) -> Optional[TrainingRecord]:
    """
    HC*.DAT（坂路・47バイト）実データ用パース。
    実際の仕様: 0 RecordType, 1-8 Date, 9-12 Time, 13-22 KettoNum,
    23-26 Time4F(4桁), 27-29 Lap4(3桁), 30-33 Time3F(4桁), 34-36 Lap3(3桁),
    37-40 Time2F(4桁), 41-43 Lap2(3桁), 44-46 Lap1(3桁)（0.1秒単位）
    実サンプル: 12026020407522023106359054914504041380266136130
    23-26=0549(54.9), 27-29=145(14.5), 30-33=0404(40.4), 34-36=138(13.8),
    37-40=0266(26.6), 41-43=136(13.6), 44-46=130(13.0)
    """
    try:
        if len(raw_line) < 47:
            return None
        time_4f = int(raw_line[23:27]) / 10.0
        lap_4 = int(raw_line[27:30]) / 10.0
        time_3f = int(raw_line[30:34]) / 10.0
        lap_3 = int(raw_line[34:37]) / 10.0
        time_2f = int(raw_line[37:41]) / 10.0
        lap_2 = int(raw_line[41:44]) / 10.0
        lap_1 = int(raw_line[44:47]) / 10.0
        return _make_record(
            raw_line, center, location,
            time_4f, time_3f, time_2f, lap_4, lap_3, lap_2, lap_1,
        )
    except (ValueError, IndexError):
        return None


def parse_ck_file(filepath: Path) -> List[TrainingRecord]:
    """CK_DATAファイルをパース。場所はファイル名のみで判定: HC*=坂路, WC*/WD*=コース"""
    records = []
    
    # ファイル名のみで判定（.name で確実にディスク上の名前を参照）
    name_upper = filepath.name.upper()
    if not name_upper.endswith(".DAT") or len(name_upper) < 15:
        return records
    # HC020260124.DAT / WC120260124.DAT -> 先頭2文字が種別
    file_type = name_upper[0:2]
    center_code = name_upper[2:3]
    location = TRAINING_TYPE.get(file_type, "不明")
    if os.environ.get("CK_DEBUG"):
        print(f"  [CK] {filepath.name} -> {file_type} -> {location}", file=sys.stderr)
    
    # ファイル名のセンターコードでトレセンを判別
    if center_code == "0":
        center = "美浦"
    elif center_code == "1":
        center = "栗東"
    else:
        center = "不明"
    
    # 場所はファイル名のみで判定: HC*.DAT=坂路, WC*.DAT/WD*.DAT=コース
    # パーサーはファイルタイプとレコード長で切り替え
    min_len = 47

    try:
        with open(filepath, 'r', encoding='shift_jis', errors='replace') as f:
            for line in f:
                line = line.strip()
                if len(line) < min_len:
                    continue

                # ファイルタイプに応じて適切なパーサーを選択
                if file_type == "HC":
                    # HC_DATA（坂路）: 47バイト形式
                    if len(line) >= 47:
                        record = parse_hc_record(line, center, location)
                    else:
                        record = None
                elif file_type in ("WC", "WD"):
                    # WC_DATA/WD_DATA（コース）: 92バイト形式
                    if len(line) >= 92:
                        record = parse_wc_record(line, center, location)
                    else:
                        record = None
                else:
                    record = None

                if record:
                    records.append(record)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    # HCファイルで0件のときのみ警告（坂路が全部コースになる原因切り分け用）
    if file_type == "HC" and len(records) == 0 and os.environ.get("CK_DEBUG"):
        print(f"  [CK] WARN: HC file yielded 0 records: {filepath.name}", file=sys.stderr)
    
    return records


def get_training_files(year: int, month: int) -> List[Path]:
    """指定年月のCK_DATAファイルリストを取得"""
    files = []
    year_dir = CK_DATA_ROOT / str(year)
    
    if not year_dir.exists():
        return files
    
    month_str = f"{year}{month:02d}"
    
    for month_dir in year_dir.iterdir():
        if not month_dir.is_dir():
            continue
        if month_dir.name.startswith(month_str):
            for f in month_dir.glob("*.DAT"):
                files.append(f)
    
    return sorted(files)


def get_recent_training_files(race_date: str, days_back: int = 14) -> List[Path]:
    """レース日からN日前までのCK_DATAファイルを取得。
    ファイル名のみで判定: HC*→坂路, WC*/WD*→コース。サブフォルダも rglob で検索。
    """
    files = []
    seen = set()  # 同一パス重複防止
    
    try:
        base_date = datetime.strptime(race_date, "%Y%m%d")
    except ValueError:
        return files
    
    for i in range(days_back):
        target_date = base_date - timedelta(days=i)
        year = target_date.year
        month = target_date.month
        date_str = target_date.strftime("%Y%m%d")
        
        year_dir = CK_DATA_ROOT / str(year)
        if not year_dir.exists():
            continue
        
        month_dir = year_dir / f"{year}{month:02d}"
        if not month_dir.exists():
            continue
        
        # 1) 月直下の HC0/HC1/WC0/WC1/WD0/WD1 + YYYYMMDD.DAT
        for prefix in ["HC0", "HC1", "WC0", "WC1", "WD0", "WD1"]:
            filepath = month_dir / f"{prefix}{date_str}.DAT"
            if filepath.exists():
                key = filepath.resolve()
                if key not in seen:
                    seen.add(key)
                    files.append(filepath)
        
        # 2) サブフォルダ内の HC*/WC*/WD* で日付が一致するものを追加
        for pattern in ["HC*.DAT", "WC*.DAT", "WD*.DAT"]:
            for f in month_dir.rglob(pattern):
                if not f.is_file():
                    continue
                stem = f.stem.upper()
                if len(stem) < 11:
                    continue
                file_date = stem[3:11]  # HC0YYYYMMDD / WC1YYYYMMDD
                if file_date == date_str:
                    key = f.resolve()
                    if key not in seen:
                        seen.add(key)
                        files.append(f)
    
    if os.environ.get("CK_DEBUG") and files:
        hc_count = sum(1 for p in files if p.name.upper().startswith("HC"))
        wc_count = sum(1 for p in files if p.name.upper().startswith("WC") or p.name.upper().startswith("WD"))
        print(f"  [CK] get_recent_training_files: {len(files)} files (HC={hc_count}, WC/WD={wc_count})", file=sys.stderr)
    
    return sorted(files)


def analyze_horse_training(horse_id: str, race_date: str, days_back: int = 14) -> Dict:
    """馬の調教履歴を分析"""
    files = get_recent_training_files(race_date, days_back)
    
    all_records = []
    horse_id_norm = (horse_id or "").strip()
    for f in files:
        records = parse_ck_file(f)
        for r in records:
            if (r.horse_id or "").strip() == horse_id_norm:
                all_records.append(r)
    
    if not all_records:
        return {"error": "No training data found", "horse_id": horse_id}
    
    if os.environ.get("CK_DEBUG"):
        n_saka = sum(1 for r in all_records if r.location == "坂路")
        n_course = sum(1 for r in all_records if r.location == "コース")
        print(f"  [CK] horse {horse_id}: {len(all_records)} records (坂路={n_saka}, コース={n_course})", file=sys.stderr)
    
    # 日付でソート（新しい順）
    all_records.sort(key=lambda x: (x.date, x.time), reverse=True)
    
    # 本数カウント
    total_count = len(all_records)
    if total_count >= 8:
        count_label = "多"
    elif total_count >= 4:
        count_label = "普"
    else:
        count_label = "少"
    
    # レース日ベースで「当週」「前週」の水・木・土・日を算出
    try:
        base_date = datetime.strptime(race_date, "%Y%m%d").date()
    except ValueError:
        base_date = None
    
    final = None       # 最終追切: 当週の水曜か木曜
    weekend = None     # 土日追切: 前週の土曜か日曜（両方あればタイムが早いほう）
    week_ago = None    # 一週前追切: 前週の水曜か木曜
    
    if base_date is not None:
        # 当週の月曜 → 水曜(2), 木曜(3)
        this_week_monday = base_date - timedelta(days=base_date.weekday())
        this_wed = this_week_monday + timedelta(days=2)
        this_thu = this_week_monday + timedelta(days=3)
        # 前週の月曜 → 水(2), 木(3), 土(5), 日(6)
        last_week_monday = this_week_monday - timedelta(days=7)
        last_wed = last_week_monday + timedelta(days=2)
        last_thu = last_week_monday + timedelta(days=3)
        last_sat = last_week_monday + timedelta(days=5)
        last_sun = last_week_monday + timedelta(days=6)
        
        dates_final = {this_wed.strftime("%Y%m%d"), this_thu.strftime("%Y%m%d")}
        dates_weekend = {last_sat.strftime("%Y%m%d"), last_sun.strftime("%Y%m%d")}
        dates_week_ago = {last_wed.strftime("%Y%m%d"), last_thu.strftime("%Y%m%d")}
        
        # 最終追切: 当週の水曜か木曜（あれば木曜優先で直近1本）
        candidates_final = [r for r in all_records if r.date in dates_final]
        if candidates_final:
            candidates_final.sort(key=lambda x: (x.date, x.time), reverse=True)
            final = candidates_final[0]
        
        # 土日追切: 前週の土曜か日曜、両方あれば4Fタイムが早いほう
        candidates_weekend = [r for r in all_records if r.date in dates_weekend]
        if candidates_weekend:
            weekend = min(candidates_weekend, key=lambda x: x.time_4f)
        
        # 一週前追切: 前週の水曜か木曜（あれば木曜優先で1本）
        candidates_week_ago = [r for r in all_records if r.date in dates_week_ago]
        if candidates_week_ago:
            candidates_week_ago.sort(key=lambda x: (x.date, x.time), reverse=True)
            week_ago = candidates_week_ago[0]
    
    # 好タイム判定
    has_good_time = any(r.is_good_time for r in all_records)
    has_sakamichi_good = any(r.is_good_time and r.location == "坂路" for r in all_records)
    has_course_good = any(r.is_good_time and r.location == "コース" for r in all_records)
    
    # 調教タイム分類記号
    if has_sakamichi_good and has_course_good:
        time_class = "両"
    elif has_sakamichi_good:
        time_class = "坂"
    elif has_course_good:
        time_class = "コ"
    else:
        time_class = ""
    
    n_sakamichi = sum(1 for r in all_records if r.location == "坂路")
    n_course = sum(1 for r in all_records if r.location == "コース")
    
    return {
        "horse_id": horse_id,
        "race_date": race_date,
        "total_count": total_count,
        "count_label": count_label,
        "time_class": time_class,
        "has_good_time": has_good_time,
        "n_sakamichi": n_sakamichi,
        "n_course": n_course,
        "final": final.to_dict() if final else None,
        "weekend": weekend.to_dict() if weekend else None,
        "week_ago": week_ago.to_dict() if week_ago else None,
        "all_records": [r.to_dict() for r in all_records],
    }


def debug_format(filepath: Path, max_records: int = 10):
    """フォーマット解析用デバッグ（TARGET CK_DATA形式）"""
    print(f"File: {filepath}")
    print(f"Name: {filepath.name}")
    print()
    
    # ファイル名からメタデータ
    filename = filepath.stem
    file_type = filename[0:2]   # HC or WC
    center_code = filename[2]   # 0 or 1
    file_date = filename[3:11]  # YYYYMMDD
    print(f"Type: {file_type} ({TRAINING_TYPE.get(file_type, '?')})")
    print(f"Center code in filename: {center_code}")
    print(f"Date: {file_date}")
    print()
    
    try:
        with open(filepath, 'rb') as f:
            for i, line in enumerate(f):
                if i >= max_records:
                    break
                
                line = line.rstrip(b'\r\n')
                raw = line.decode('shift_jis', errors='replace')
                print(f"[{i+1}] Length={len(raw)} chars")
                print(f"    Raw: {raw}")
                
                # TARGET CK_DATA形式（47文字）
                # 0: トレセン区分 (1=美浦, 2=栗東?)
                # 1-8: 日付 (20260124)
                # 9-12: 時刻 (0500)
                # 13-22: 馬ID (2020104764)
                # 23-46: タイムデータ (24文字)
                
                if len(raw) >= 47:
                    tresen = raw[0]
                    date = raw[1:9]
                    time = raw[9:13]
                    horse_id = raw[13:23]
                    time_data = raw[23:]
                    
                    print(f"    Tresen: {tresen}")
                    print(f"    Date: {date}")
                    print(f"    Time: {time}")
                    print(f"    HorseID: {horse_id}")
                    print(f"    TimeData: {time_data} (len={len(time_data)})")
                    
                    # タイムデータ解析（4桁+3桁+3桁+3桁+3桁+3桁+3桁+2桁 = 24文字?）
                    # 試行: 4F(4) + Lap4(3) + 3F(3) + Lap3(3) + 2F(3) + Lap2(3) + Lap1(3) = 22
                    # 残り2文字?
                    
                    # 別の解釈: すべて3桁
                    # 0599 168 043 114 602 851 421 43
                    # 3桁ずつ: 059 916 804 311 460 285 142 143
                    
                    # 正しい解釈: 4桁+3桁+4桁+3桁+4桁+3桁+3桁 = 24文字
                    # 4F(4) + Lap4(3) + 3F(4) + Lap3(3) + 2F(4) + Lap2(3) + Lap1(3)
                    if len(time_data) >= 24:
                        t4f = int(time_data[0:4]) / 10.0    # 0599 = 59.9秒
                        lap4 = int(time_data[4:7]) / 10.0   # 168 = 16.8秒
                        t3f = int(time_data[7:11]) / 10.0   # 0431 = 43.1秒
                        lap3 = int(time_data[11:14]) / 10.0 # 146 = 14.6秒
                        t2f = int(time_data[14:18]) / 10.0  # 0285 = 28.5秒
                        lap2 = int(time_data[18:21]) / 10.0 # 142 = 14.2秒
                        lap1 = int(time_data[21:24]) / 10.0 # 143 = 14.3秒
                        
                        print(f"    ★正しい解釈★")
                        print(f"    4F={t4f:.1f}s (800M-0M)")
                        print(f"    3F={t3f:.1f}s (600M-0M)")
                        print(f"    2F={t2f:.1f}s (400M-0M)")
                        print(f"    Lap4={lap4:.1f}s (800M-600M)")
                        print(f"    Lap3={lap3:.1f}s (600M-400M)")
                        print(f"    Lap2={lap2:.1f}s (400M-200M)")
                        print(f"    Lap1={lap1:.1f}s (200M-0M)")
                        
                        # 検証: 4F - 3F = Lap4 になるはず
                        calc_lap4 = t4f - t3f
                        print(f"    [検証] 4F-3F={calc_lap4:.1f} vs Lap4={lap4:.1f} {'✓' if abs(calc_lap4-lap4) < 0.2 else '×'}")
                print()
    except Exception as e:
        print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Parse CK_DATA training data")
    parser.add_argument("--debug", action="store_true", help="Debug format analysis")
    parser.add_argument("--file", type=str, help="Specific file to analyze")
    parser.add_argument("--horse", type=str, help="Horse ID to search")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y%m%d"),
                        help="Race date (YYYYMMDD)")
    parser.add_argument("--days", type=int, default=14, help="Days to look back")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("CK_DATA Training Parser (JV-Data Spec Compliant)")
    print("=" * 70)
    print(f"CK_DATA root: {CK_DATA_ROOT}")
    print()
    
    if args.debug:
        # デバッグモード
        if args.file:
            filepath = Path(args.file)
        else:
            # 最新のファイルを探す
            files = get_recent_training_files(args.date, 1)
            if not files:
                print("No files found")
                return 1
            filepath = files[0]
        
        debug_format(filepath)
        return 0
    
    if args.horse:
        # 馬の調教履歴を分析
        print(f"Analyzing horse: {args.horse}")
        print(f"Race date: {args.date}")
        print()
        
        result = analyze_horse_training(args.horse, args.date, args.days)
        
        if "error" in result and result.get("final") is None:
            print(f"Error: {result['error']}")
            return 1
        
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Total workouts: {result['total_count']} ({result['count_label']})")
            print(f"Time class: {result['time_class'] or 'なし'}")
            print()
            
            if result.get('final'):
                final = result['final']
                print("最終追切（当週水・木）:")
                print(f"  {final['date']} {final['time']} {final['center']}{final['location']}")
                print(f"  4F={final['time_4f']:.1f}s [{final['speed_class']}] Lap1={final['lap_1']:.1f}s [{final['lap_class']}]")
            
            if result.get('weekend'):
                we = result['weekend']
                print("\n土日追切（前週土・日）:")
                print(f"  {we['date']} {we['time']} {we['center']}{we['location']}")
                print(f"  4F={we['time_4f']:.1f}s [{we['speed_class']}] Lap1={we['lap_1']:.1f}s [{we['lap_class']}]")
            
            if result.get('week_ago'):
                wa = result['week_ago']
                print("\n一週前追切（前週水・木）:")
                print(f"  {wa['date']} {wa['time']} {wa['center']}{wa['location']}")
                print(f"  4F={wa['time_4f']:.1f}s [{wa['speed_class']}] Lap1={wa['lap_1']:.1f}s [{wa['lap_class']}]")
            
            print("\n全調教:")
            for r in result.get('all_records', []):
                good_mark = "★" if r['is_good_time'] else ""
                print(f"  {r['date']} {r['time']} {r['center']}{r['location']} "
                      f"4F={r['time_4f']:.1f}s [{r['speed_class']}] 1F={r['lap_1']:.1f}s [{r['lap_class']}] {good_mark}")
        
        return 0
    
    # ファイルリスト表示
    files = get_recent_training_files(args.date, args.days)
    print(f"Found {len(files)} files:")
    for f in files[:20]:
        print(f"  {f.name}")
    
    return 0


if __name__ == "__main__":
    exit(main())

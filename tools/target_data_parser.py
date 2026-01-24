"""
TARGET frontier JV データファイルパーサー

TARGETが保存するJRA-VANデータファイルを読み込み、
JSON/CSV形式に変換するユーティリティ。

使用例:
    python target_data_parser.py --type hc --date 20260116 --output json
    python target_data_parser.py --type hc --ketto 2020101174 --output csv
"""

import argparse
import json
import csv
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime


# TARGETデータのルートパス（設定可能）
TARGET_DATA_ROOT = Path("Y:/")


@dataclass
class HanroTraining:
    """坂路調教データ (HCファイル)"""
    tresen: str           # トレセン (1=栗東, 0=美浦)
    date: str             # 調教日 (YYYYMMDD)
    time: str             # 調教時刻 (HHMM)
    ketto_num: str        # 血統登録番号
    time_4f: float        # 4F(800m)合計タイム（秒）
    lap_4: float          # 800m-600mラップ（秒）
    time_3f: float        # 3F(600m)合計タイム（秒）
    lap_3: float          # 600m-400mラップ（秒）
    time_2f: float        # 2F(400m)合計タイム（秒）
    lap_2: float          # 400m-200mラップ（秒）
    lap_1: float          # 最終1F(200m-0m)ラップ（秒）
    
    @property
    def tresen_name(self) -> str:
        return "栗東" if self.tresen == "1" else "美浦"
    
    @property
    def formatted_date(self) -> str:
        return f"{self.date[:4]}/{self.date[4:6]}/{self.date[6:8]}"
    
    @property
    def formatted_time(self) -> str:
        return f"{self.time[:2]}:{self.time[2:]}"


def parse_hc_line(line: str) -> HanroTraining:
    """
    HCファイルの1行をパースして HanroTraining オブジェクトを返す
    
    フォーマット（47バイト）:
    - 位置1: トレセン区分 (1バイト)
    - 位置2-9: 調教日 (8バイト)
    - 位置10-13: 調教時刻 (4バイト)
    - 位置14-23: 血統登録番号 (10バイト)
    - 位置24-27: 4F合計タイム (4バイト, 1/10秒)
    - 位置28-30: 800m-600mラップ (3バイト, 1/10秒)
    - 位置31-34: 3F合計タイム (4バイト)
    - 位置35-37: 600m-400mラップ (3バイト)
    - 位置38-41: 2F合計タイム (4バイト)
    - 位置42-44: 400m-200mラップ (3バイト)
    - 位置45-47: 最終1Fラップ (3バイト)
    """
    if len(line) < 47:
        raise ValueError(f"Invalid line length: {len(line)} (expected 47)")
    
    def parse_time(s: str) -> float:
        """1/10秒単位の文字列を秒に変換"""
        try:
            return int(s) / 10.0
        except ValueError:
            return 0.0
    
    return HanroTraining(
        tresen=line[0],
        date=line[1:9],
        time=line[9:13],
        ketto_num=line[13:23],
        time_4f=parse_time(line[23:27]),
        lap_4=parse_time(line[27:30]),
        time_3f=parse_time(line[30:34]),
        lap_3=parse_time(line[34:37]),
        time_2f=parse_time(line[37:41]),
        lap_2=parse_time(line[41:44]),
        lap_1=parse_time(line[44:47]),
    )


def get_hc_file_path(date: str, tresen: str = "both") -> List[Path]:
    """
    日付とトレセンからHCファイルのパスを取得
    
    Args:
        date: 日付 (YYYYMMDD)
        tresen: "0" (美浦), "1" (栗東), "both" (両方)
    
    Returns:
        ファイルパスのリスト
    """
    year = date[:4]
    month = date[:6]
    
    base_dir = TARGET_DATA_ROOT / "CK_DATA" / year / month
    paths = []
    
    if tresen in ("0", "both"):
        paths.append(base_dir / f"HC0{date}.DAT")
    if tresen in ("1", "both"):
        paths.append(base_dir / f"HC1{date}.DAT")
    
    return [p for p in paths if p.exists()]


def load_hc_data(date: str, tresen: str = "both") -> List[HanroTraining]:
    """
    指定日の坂路調教データを読み込む
    
    Args:
        date: 日付 (YYYYMMDD)
        tresen: "0" (美浦), "1" (栗東), "both" (両方)
    
    Returns:
        HanroTrainingオブジェクトのリスト
    """
    results = []
    paths = get_hc_file_path(date, tresen)
    
    for path in paths:
        try:
            with open(path, 'r', encoding='cp932') as f:
                for line in f:
                    line = line.rstrip('\r\n')
                    if len(line) >= 47:
                        try:
                            results.append(parse_hc_line(line))
                        except ValueError as e:
                            print(f"Warning: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)
    
    return results


def search_by_ketto(data: List[HanroTraining], ketto_num: str) -> List[HanroTraining]:
    """血統登録番号で検索"""
    return [d for d in data if d.ketto_num == ketto_num]


def output_json(data: List[HanroTraining], file: Optional[str] = None):
    """JSON形式で出力"""
    result = [asdict(d) for d in data]
    # 追加フィールドを含める
    for i, d in enumerate(data):
        result[i]['tresen_name'] = d.tresen_name
        result[i]['formatted_date'] = d.formatted_date
        result[i]['formatted_time'] = d.formatted_time
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    
    if file:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Output written to {file}")
    else:
        print(output)


def output_csv(data: List[HanroTraining], file: Optional[str] = None):
    """CSV形式で出力"""
    if not data:
        print("No data to output")
        return
    
    fieldnames = [
        'tresen_name', 'date', 'time', 'ketto_num',
        'time_4f', 'lap_4', 'time_3f', 'lap_3', 'time_2f', 'lap_2', 'lap_1'
    ]
    
    rows = []
    for d in data:
        rows.append({
            'tresen_name': d.tresen_name,
            'date': d.formatted_date,
            'time': d.formatted_time,
            'ketto_num': d.ketto_num,
            'time_4f': d.time_4f,
            'lap_4': d.lap_4,
            'time_3f': d.time_3f,
            'lap_3': d.lap_3,
            'time_2f': d.time_2f,
            'lap_2': d.lap_2,
            'lap_1': d.lap_1,
        })
    
    if file:
        with open(file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Output written to {file}")
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description='TARGET frontier JV データファイルパーサー'
    )
    parser.add_argument(
        '--type', '-t',
        choices=['hc', 'wc'],
        default='hc',
        help='データタイプ (hc=坂路調教, wc=ウッドチップ調教)'
    )
    parser.add_argument(
        '--date', '-d',
        help='調教日 (YYYYMMDD)'
    )
    parser.add_argument(
        '--ketto', '-k',
        help='血統登録番号でフィルタ'
    )
    parser.add_argument(
        '--tresen',
        choices=['0', '1', 'both'],
        default='both',
        help='トレセン (0=美浦, 1=栗東, both=両方)'
    )
    parser.add_argument(
        '--output', '-o',
        choices=['json', 'csv'],
        default='json',
        help='出力形式'
    )
    parser.add_argument(
        '--file', '-f',
        help='出力ファイル（省略時は標準出力）'
    )
    
    args = parser.parse_args()
    
    if not args.date:
        # デフォルトは今日
        args.date = datetime.now().strftime('%Y%m%d')
    
    if args.type == 'hc':
        data = load_hc_data(args.date, args.tresen)
        
        if args.ketto:
            data = search_by_ketto(data, args.ketto)
        
        if args.output == 'json':
            output_json(data, args.file)
        else:
            output_csv(data, args.file)
    else:
        print("WCパーサーは未実装です", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

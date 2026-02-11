# -*- coding: utf-8 -*-
"""
レース特性基準値算出スクリプト

TARGETデータから瞬発戦/持続戦の基準値を統計的に算出
- RPCI基準値（コース・距離・クラス別）
- 上がり3F基準値
- レースタイプ別のサンプル数

使用方法:
  python calculate_race_type_standards.py --input <TARGETエクスポートCSV> --output <出力JSON>
  python calculate_race_type_standards.py --scan-dir <ディレクトリ> --output <出力JSON>
"""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 出力先のデフォルトパス
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "race_type_standards.json"


def parse_time_to_seconds(time_str: str) -> Optional[float]:
    """走破タイムを秒に変換 (例: 1.10.3 -> 70.3)"""
    if not time_str:
        return None
    try:
        parts = time_str.replace(' ', '').split('.')
        if len(parts) == 3:
            minutes = int(parts[0])
            seconds = int(parts[1])
            tenths = int(parts[2])
            return minutes * 60 + seconds + tenths / 10
        elif len(parts) == 2:
            seconds = int(parts[0])
            tenths = int(parts[1])
            return seconds + tenths / 10
    except:
        pass
    return None


def parse_last3f(last3f_str: str) -> Optional[float]:
    """上がり3Fを秒に変換 (例: 33.7 -> 33.7, 333 -> 33.3)"""
    if not last3f_str:
        return None
    try:
        # 小数点がない場合（333 -> 33.3）
        cleaned = last3f_str.strip()
        if '.' not in cleaned and len(cleaned) == 3:
            return float(cleaned) / 10
        return float(cleaned)
    except:
        return None


def classify_class_group(class_name: str) -> str:
    """クラス名からクラスグループを判定"""
    if not class_name:
        return "中級"
    
    if '新馬' in class_name or '未勝利' in class_name:
        return "下級"
    elif '1勝' in class_name or '2勝' in class_name or '3勝' in class_name:
        return "中級"
    elif 'OP' in class_name or 'オープン' in class_name or 'L' in class_name or 'G' in class_name:
        return "上級"
    else:
        return "中級"


def detect_course_from_filename(csv_path: str) -> Tuple[str, str, str]:
    """ファイル名からコース情報を検出"""
    import re
    filename = Path(csv_path).stem.lower()
    
    # 競馬場検出
    track = None
    tracks = ["東京", "中山", "阪神", "京都", "中京", "新潟", "小倉", "福島", "札幌", "函館"]
    for t in tracks:
        if t.lower() in filename or t in filename:
            track = t
            break
    
    # コース（芝/ダート）検出
    if "芝" in filename or "turf" in filename:
        surface = "芝"
    elif "ダート" in filename or "dirt" in filename:
        surface = "ダート"
    else:
        surface = None
    
    # 距離検出
    distance_match = re.search(r'(\d{3,4})', filename)
    distance = distance_match.group(1) if distance_match else None
    
    return track, surface, distance


def analyze_csv_file(csv_path: str, stats: Dict) -> int:
    """CSVファイルを分析してstatsに追加"""
    
    # ファイル名からコース情報を検出
    detected_track, detected_surface, detected_distance = detect_course_from_filename(csv_path)
    
    # エンコーディング検出
    encoding = 'utf-8-sig'
    for enc in ['utf-8-sig', 'utf-8', 'cp932', 'shift_jis']:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                f.read(1000)
                encoding = enc
                break
        except UnicodeDecodeError:
            continue
    
    processed = 0
    seen_races = set()
    
    try:
        with open(csv_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # レースIDを取得（重複防止）
                race_id_col = 'レースID(新)' if 'レースID(新)' in row else list(row.keys())[0]
                race_id_full = row.get(race_id_col, '')
                race_id = race_id_full[:-2] if len(race_id_full) >= 2 else race_id_full
                
                # 同一レースは1着馬のみ使用（レース全体の上がり3FはPCI3/RPCIで代用）
                finish_str = row.get('着順', '').strip()
                try:
                    finish_str = finish_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                    finish = int(finish_str)
                except:
                    continue
                
                if race_id in seen_races:
                    continue
                if finish != 1:
                    continue
                seen_races.add(race_id)
                
                # 必要データ取得
                try:
                    rpci = float(row.get('RPCI', ''))
                except:
                    continue
                
                try:
                    pci3 = float(row.get('PCI3', ''))
                except:
                    pci3 = rpci
                
                last3f = parse_last3f(row.get('上がり', '') or row.get('上り3F', ''))
                if last3f is None:
                    continue
                
                # コース情報（CSVから取得、なければファイル名から）
                track = row.get('競馬場', detected_track)
                surface = row.get('コース', detected_surface)
                if surface and ('芝' in surface or 'turf' in surface.lower()):
                    surface = '芝'
                elif surface and ('ダ' in surface or 'dirt' in surface.lower()):
                    surface = 'ダート'
                
                distance = row.get('距離', detected_distance)
                if distance:
                    distance = str(distance).replace('m', '').strip()
                
                if not track or not surface or not distance:
                    continue
                
                class_name = row.get('クラス名', '')
                class_group = classify_class_group(class_name)
                track_condition = row.get('馬場', '') or row.get('馬場状態', '')
                
                # キー作成
                key = (track, surface, distance, class_group)
                
                # 統計データ追加
                if key not in stats:
                    stats[key] = {
                        'rpci_values': [],
                        'pci3_values': [],
                        'last3f_values': [],
                        'track_conditions': defaultdict(int)
                    }
                
                stats[key]['rpci_values'].append(rpci)
                stats[key]['pci3_values'].append(pci3)
                stats[key]['last3f_values'].append(last3f)
                if track_condition:
                    stats[key]['track_conditions'][track_condition] += 1
                
                processed += 1
    
    except Exception as e:
        print(f"  エラー: {csv_path}: {e}")
    
    return processed


def calculate_standards(stats: Dict) -> Dict:
    """統計データから基準値を算出"""
    
    result = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "description": "レース特性分類の基準値（瞬発戦/持続戦）",
            "version": "1.0"
        },
        "global_thresholds": {
            "description": "大串広氏の基準に基づく全体閾値",
            "shunpatsu_last3f": {
                "default": 34.4,
                "niigata_outer": 33.7,
                "description": "これ以下なら瞬発戦寄り"
            },
            "jizokusen_last3f": {
                "default": 35.5,
                "tokyo_niigata": 35.1,
                "description": "これ以上なら持続戦寄り"
            },
            "rpci_thresholds": {
                "tokyo_niigata_1600m": 50,
                "other_1600m_or_less": 48,
                "sprint_1200m": 45,
                "description": "これ以下なら持続戦"
            }
        },
        "tracks": {}
    }
    
    for (track, surface, distance, class_group), data in stats.items():
        rpci_values = data['rpci_values']
        pci3_values = data['pci3_values']
        last3f_values = data['last3f_values']
        
        if len(rpci_values) < 5:
            continue
        
        # 統計計算
        rpci_mean = statistics.mean(rpci_values)
        rpci_stdev = statistics.stdev(rpci_values) if len(rpci_values) > 1 else 0
        rpci_median = statistics.median(rpci_values)
        
        last3f_mean = statistics.mean(last3f_values)
        last3f_stdev = statistics.stdev(last3f_values) if len(last3f_values) > 1 else 0
        last3f_median = statistics.median(last3f_values)
        
        # 瞬発戦/持続戦の閾値計算
        # 平均から±1標準偏差を基準にする
        shunpatsu_rpci = rpci_mean + rpci_stdev * 0.5  # 高RPCIが瞬発戦
        jizokusen_rpci = rpci_mean - rpci_stdev * 0.5  # 低RPCIが持続戦
        
        shunpatsu_last3f = last3f_mean - last3f_stdev * 0.5  # 速い上がりが瞬発戦
        jizokusen_last3f = last3f_mean + last3f_stdev * 0.5  # 遅い上がりが持続戦
        
        # 結果格納
        if track not in result["tracks"]:
            result["tracks"][track] = {}
        if surface not in result["tracks"][track]:
            result["tracks"][track][surface] = {}
        if distance not in result["tracks"][track][surface]:
            result["tracks"][track][surface][distance] = {}
        
        result["tracks"][track][surface][distance][class_group] = {
            "sample_count": len(rpci_values),
            "rpci": {
                "mean": round(rpci_mean, 2),
                "stdev": round(rpci_stdev, 2),
                "median": round(rpci_median, 2),
                "shunpatsu_threshold": round(shunpatsu_rpci, 2),
                "jizokusen_threshold": round(jizokusen_rpci, 2)
            },
            "last3f": {
                "mean": round(last3f_mean, 2),
                "stdev": round(last3f_stdev, 2),
                "median": round(last3f_median, 2),
                "shunpatsu_threshold": round(shunpatsu_last3f, 2),
                "jizokusen_threshold": round(jizokusen_last3f, 2)
            },
            "track_conditions": dict(data['track_conditions'])
        }
    
    return result


def scan_directory(directory: str) -> List[str]:
    """ディレクトリ内のCSVファイルを検索"""
    csv_files = []
    for path in Path(directory).rglob('*.csv'):
        csv_files.append(str(path))
    return csv_files


def main():
    parser = argparse.ArgumentParser(description='レース特性基準値を算出')
    parser.add_argument('--input', '-i', help='入力CSVファイル')
    parser.add_argument('--scan-dir', '-d', help='CSVファイルを検索するディレクトリ')
    parser.add_argument('--output', '-o', default=str(DEFAULT_OUTPUT_PATH), help='出力JSONファイル')
    parser.add_argument('--min-samples', type=int, default=5, help='最小サンプル数（デフォルト: 5）')
    
    args = parser.parse_args()
    
    if not args.input and not args.scan_dir:
        print("エラー: --input または --scan-dir を指定してください")
        return 1
    
    # 統計データ収集
    stats = {}
    total_processed = 0
    
    if args.input:
        print(f"ファイル処理: {args.input}")
        count = analyze_csv_file(args.input, stats)
        total_processed += count
        print(f"  処理レース数: {count}")
    
    if args.scan_dir:
        csv_files = scan_directory(args.scan_dir)
        print(f"ディレクトリスキャン: {args.scan_dir}")
        print(f"  CSVファイル数: {len(csv_files)}")
        
        for csv_file in csv_files:
            print(f"  処理中: {Path(csv_file).name}")
            count = analyze_csv_file(csv_file, stats)
            total_processed += count
    
    print(f"\n総処理レース数: {total_processed}")
    print(f"コース・距離・クラス組み合わせ: {len(stats)}")
    
    # 基準値算出
    result = calculate_standards(stats)
    
    # 出力
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n基準値を出力: {output_path}")
    
    # サマリー表示
    track_count = len(result.get("tracks", {}))
    print(f"\n=== サマリー ===")
    print(f"競馬場数: {track_count}")
    
    for track, surfaces in result.get("tracks", {}).items():
        for surface, distances in surfaces.items():
            print(f"  {track} {surface}: {len(distances)}距離")
    
    return 0


if __name__ == '__main__':
    exit(main())

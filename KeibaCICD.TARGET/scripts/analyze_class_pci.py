# -*- coding: utf-8 -*-
"""クラス別PCI3分析スクリプト"""

import glob
import csv
from collections import defaultdict
import statistics
import sys

def analyze_class_pci(csv_path: str):
    """クラス別のPCI3を分析"""
    
    print(f"入力ファイル: {csv_path}")
    
    class_pci3 = defaultdict(list)
    seen_races = set()
    
    # エンコーディング検出
    for enc in ['utf-8-sig', 'utf-8', 'cp932']:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    race_id = row.get('レースID(新)', '')[:16]
                    if race_id in seen_races:
                        continue
                    seen_races.add(race_id)
                    
                    class_name = row.get('クラス名', '').strip()
                    try:
                        pci3 = float(row.get('PCI3', ''))
                    except:
                        continue
                    
                    # クラス分類（3分類）
                    if '新馬' in class_name or '未勝利' in class_name:
                        cat = '下級'  # 新馬・未勝利
                    elif '1勝' in class_name or '2勝' in class_name or '3勝' in class_name:
                        cat = '中級'  # 1勝〜3勝
                    elif 'OP' in class_name or 'オープン' in class_name or 'L' in class_name or 'G' in class_name:
                        cat = '上級'  # OP以上
                    else:
                        cat = '中級'  # その他は中級扱い
                    
                    class_pci3[cat].append(pci3)
                break
        except UnicodeDecodeError:
            continue
    
    print()
    print("=" * 60)
    print("クラス別PCI3分析")
    print("=" * 60)
    print(f"{'クラス':<12} {'n':>5} {'平均':>8} {'標準偏差':>8} {'H境界':>8} {'S境界':>8}")
    print("-" * 60)
    
    total_avg = None
    total_count = 0
    
    for cat in ['下級', '中級', '上級']:
        vals = class_pci3.get(cat, [])
        if len(vals) >= 3:
            avg = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 0
            total_count += len(vals)
            print(f"{cat:<12} {len(vals):>5} {avg:>8.2f} {std:>8.2f} {avg-std:>8.1f} {avg+std:>8.1f}")
    
    print("-" * 60)
    
    # 全体
    all_vals = [v for vals in class_pci3.values() for v in vals]
    if all_vals:
        avg = statistics.mean(all_vals)
        std = statistics.stdev(all_vals) if len(all_vals) > 1 else 0
        print(f"{'全体':<12} {len(all_vals):>5} {avg:>8.2f} {std:>8.2f} {avg-std:>8.1f} {avg+std:>8.1f}")
    
    # JSON形式で出力
    print()
    print("【JSON形式】")
    for cat in ['下級', '中級', '上級']:
        vals = class_pci3.get(cat, [])
        if len(vals) >= 3:
            avg = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 0
            print(f'"{cat}": {{ "standard": {avg:.1f}, "h_threshold": {avg-std:.1f}, "s_threshold": {avg+std:.1f}, "sample_count": {len(vals)} }},')


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # ワイルドカードの場合はglobで解決
        if '*' in arg:
            files = glob.glob(arg)
            csv_path = files[0] if files else None
        else:
            csv_path = arg
    else:
        # デフォルト: 1200のPCIファイルを検索
        files = glob.glob('Y:/TXT/*1200*PCI*.csv')
        csv_path = files[0] if files else None
    
    if csv_path:
        analyze_class_pci(csv_path)
    else:
        print("ファイルが見つかりません")

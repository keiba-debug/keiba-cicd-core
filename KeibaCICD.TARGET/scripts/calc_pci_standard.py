# -*- coding: utf-8 -*-
"""
PCI基準値算出スクリプト
CSVファイルからPCI3の平均と標準偏差を算出
"""

import csv
import glob
import statistics
import sys
from pathlib import Path


def calc_pci_standard(csv_path: str):
    """PCI基準値を算出"""
    
    print(f"入力ファイル: {csv_path}")
    
    # エンコーディング検出
    encoding = None
    for enc in ['utf-8-sig', 'utf-8', 'cp932']:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                if headers and any('PCI' in str(h) for h in headers):
                    encoding = enc
                    print(f"エンコーディング: {enc}")
                    break
        except UnicodeDecodeError:
            continue
    
    if not encoding:
        print("エンコーディングを検出できませんでした")
        return
    
    # PCI3を収集（レースごとにユニーク）
    pci3_values = []
    seen_races = set()
    
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # レースID取得（馬番除去）
            race_id_col = None
            for key in row.keys():
                if 'レースID' in key or 'ID' in key:
                    race_id_col = key
                    break
            
            if not race_id_col:
                race_id_col = list(row.keys())[0]
            
            race_id_full = row.get(race_id_col, '')
            race_id = race_id_full[:-2] if len(race_id_full) >= 2 else race_id_full
            
            if race_id in seen_races:
                continue
            seen_races.add(race_id)
            
            # PCI3取得
            pci3 = None
            for key in row.keys():
                if key == 'PCI3':
                    try:
                        pci3 = float(row[key])
                    except:
                        pass
                    break
            
            if pci3 is not None:
                pci3_values.append(pci3)
    
    if not pci3_values:
        print("PCI3データが見つかりませんでした")
        return
    
    # 統計計算
    mean = statistics.mean(pci3_values)
    stdev = statistics.stdev(pci3_values) if len(pci3_values) > 1 else 0
    h_threshold = round(mean - stdev, 1)
    s_threshold = round(mean + stdev, 1)
    
    print()
    print("=" * 50)
    print("PCI基準値 算出結果")
    print("=" * 50)
    print(f"レース数: {len(pci3_values)}")
    print(f"PCI3平均: {mean:.2f}")
    print(f"標準偏差: {stdev:.2f}")
    print(f"H境界 (平均-1σ): {h_threshold}")
    print(f"S境界 (平均+1σ): {s_threshold}")
    print(f"最小値: {min(pci3_values):.2f}")
    print(f"最大値: {max(pci3_values):.2f}")
    print()
    print("【JSON形式】")
    print(f'"距離": {{')
    print(f'  "standard": {round(mean, 1)},')
    print(f'  "h_threshold": {h_threshold},')
    print(f'  "s_threshold": {s_threshold},')
    print(f'  "sample_count": {len(pci3_values)}')
    print(f'}}')


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if '*' in arg:
            matches = glob.glob(arg)
            csv_path = matches[0] if matches else arg
        else:
            csv_path = arg
    else:
        # デフォルト: 1800を検索
        matches = glob.glob('Y:/TXT/*1800*.csv')
        if matches:
            csv_path = matches[0]
        else:
            print("ファイルが見つかりません")
            sys.exit(1)
    
    calc_pci_standard(csv_path)

# -*- coding: utf-8 -*-
"""
中山ダート1200m PCI基準値算出スクリプト
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path


def analyze_nakayama_dirt_1200(csv_path: str):
    """
    中山ダート1200mのCSVを分析してPCI基準値を算出
    """
    races = defaultdict(list)  # race_id -> [(着順, PCI)]
    
    # エンコーディングを試す
    encodings = ["utf-8-sig", "utf-8", "cp932", "shift_jis"]
    
    for encoding in encodings:
        try:
            with open(csv_path, encoding=encoding) as f:
                reader = csv.reader(f)
                headers = next(reader)
                
                # 列インデックスを特定
                order_idx = None
                pci_idx = None
                race_id_idx = None
                r_mark2_idx = None  # 含水率
                r_mark3_idx = None  # クッション値
                
                for i, h in enumerate(headers):
                    if "確定着順" in h:
                        order_idx = i
                    elif h == "PCI":
                        pci_idx = i
                    elif "レースID(新)" in h:
                        race_id_idx = i
                    elif "馬印2" in h or h == "R印2":
                        r_mark2_idx = i
                    elif "馬印3" in h or h == "R印3":
                        r_mark3_idx = i
                
                print(f"エンコーディング: {encoding}")
                print(f"確定着順: 列{order_idx}, PCI: 列{pci_idx}, レースID: 列{race_id_idx}")
                print(f"R印2(含水率): 列{r_mark2_idx}, R印3(クッション): 列{r_mark3_idx}")
                print()
                
                if order_idx is None or pci_idx is None or race_id_idx is None:
                    print("必要な列が見つかりません")
                    continue
                
                # データ読み込み
                row_count = 0
                for row in reader:
                    try:
                        order = int(row[order_idx])
                        pci = float(row[pci_idx])
                        race_id_full = row[race_id_idx]
                        
                        # レースIDの末尾2桁(馬番)を除いた16桁でグルーピング
                        race_id = race_id_full[:16] if len(race_id_full) >= 16 else race_id_full
                        
                        # 含水率を取得（あれば）
                        moisture = None
                        if r_mark2_idx and r_mark2_idx < len(row):
                            moisture_str = row[r_mark2_idx].strip()
                            if moisture_str:
                                try:
                                    moisture = float(moisture_str.replace("%", ""))
                                except:
                                    pass
                        
                        races[race_id].append({
                            "order": order,
                            "pci": pci,
                            "moisture": moisture
                        })
                        row_count += 1
                    except (ValueError, IndexError):
                        continue
                
                print(f"読み込み行数: {row_count}")
                print(f"レース数: {len(races)}")
                break
                
        except UnicodeDecodeError:
            continue
    
    if not races:
        print("データを読み込めませんでした")
        return
    
    # PCI3を算出（各レースの上位3頭のPCI平均）
    pci3_list = []
    pci3_by_moisture = defaultdict(list)
    
    for race_id, horses in races.items():
        # 着順でソート
        sorted_horses = sorted(horses, key=lambda x: x["order"])
        
        # 1〜3着を取得
        top3 = [h for h in sorted_horses if 1 <= h["order"] <= 3]
        
        if len(top3) == 3:
            pci3 = sum(h["pci"] for h in top3) / 3
            pci3_list.append(pci3)
            
            # 含水率別に分類
            moisture = top3[0].get("moisture")
            if moisture is not None:
                if moisture < 8:
                    pci3_by_moisture["乾燥(<8%)"].append(pci3)
                elif moisture < 12:
                    pci3_by_moisture["標準(8-12%)"].append(pci3)
                else:
                    pci3_by_moisture["湿潤(12%<)"].append(pci3)
    
    # 統計算出
    print("\n" + "=" * 50)
    print("中山ダート1200m PCI基準値")
    print("=" * 50)
    
    if pci3_list:
        mean = statistics.mean(pci3_list)
        stdev = statistics.stdev(pci3_list) if len(pci3_list) > 1 else 0
        
        print(f"\n【全体】")
        print(f"  レース数: {len(pci3_list)}")
        print(f"  PCI3平均: {mean:.2f}")
        print(f"  標準偏差: {stdev:.2f}")
        print(f"  H境界: {mean - stdev:.2f}")
        print(f"  S境界: {mean + stdev:.2f}")
        print(f"  最小値: {min(pci3_list):.2f}")
        print(f"  最大値: {max(pci3_list):.2f}")
        
        # JSON形式で出力
        print(f"\n【JSON形式】")
        print(f'  "1200": {{')
        print(f'    "standard": {mean:.1f},')
        print(f'    "h_threshold": {mean - stdev:.1f},')
        print(f'    "s_threshold": {mean + stdev:.1f},')
        print(f'    "sample_count": {len(pci3_list)}')
        print(f'  }}')
        
        # 含水率別
        if pci3_by_moisture:
            print(f"\n【含水率別】")
            for moisture_cat, values in sorted(pci3_by_moisture.items()):
                if len(values) >= 5:
                    m = statistics.mean(values)
                    s = statistics.stdev(values) if len(values) > 1 else 0
                    print(f"  {moisture_cat}: 平均={m:.2f}, 標準偏差={s:.2f}, レース数={len(values)}")
    else:
        print("PCI3を算出できるレースがありませんでした")


if __name__ == "__main__":
    import sys
    import glob
    
    if len(sys.argv) > 1:
        # 引数でファイル指定
        arg = sys.argv[1]
        if '*' in arg:
            matches = glob.glob(arg)
            csv_path = matches[0] if matches else arg
        else:
            csv_path = arg
    else:
        # デフォルト: 1800を優先、なければ1200
        matches = glob.glob('Y:/TXT/*1800*.csv')
        if not matches:
            matches = glob.glob('Y:/TXT/*1200*.csv')
        csv_path = matches[0] if matches else r"Y:\TXT\PCI中山ダート1200.csv"
    
    print(f"入力ファイル: {csv_path}")
    analyze_nakayama_dirt_1200(csv_path)

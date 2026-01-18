# -*- coding: utf-8 -*-
"""
含水率別PCI分析スクリプト
中山ダート1200mのデータを含水率で分類し、PCI傾向を分析
"""

import csv
from collections import defaultdict
import statistics

def analyze_moisture_pci(csv_path: str):
    """含水率別にPCI3を分析"""
    
    # レース単位でデータを集約
    races = defaultdict(list)
    
    # エンコーディングを自動検出（utf-8-sig, utf-8, cp932の順で試す）
    for enc in ['utf-8-sig', 'utf-8', 'cp932']:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                if headers and len(headers) > 0:
                    # 文字化けチェック（レースIDが読めるか）
                    if any('レース' in h or 'PCI' in h for h in headers):
                        encoding = enc
                        break
        except UnicodeDecodeError:
            continue
    else:
        encoding = 'cp932'  # フォールバック
    
    # 新フォーマット判定（PCI3カラムがあるかどうか）
    is_new_format = 'PCI3' in headers if headers else False
    
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # レースIDを抽出（馬番を除く）
            race_id_col = 'レースID(新)' if 'レースID(新)' in row else list(row.keys())[0]
            race_id_full = row.get(race_id_col, '')
            if len(race_id_full) >= 2:
                race_id = race_id_full[:-2]  # 馬番（末尾2桁）を除去
            else:
                continue
            
            if is_new_format:
                # 新フォーマット: PCI3が直接ある
                try:
                    pci3 = float(row.get('PCI3', ''))
                except:
                    pci3 = None
                
                # 含水率（レース印２ - 全角数字）
                try:
                    moisture_val = row.get('レース印２', row.get('レース印2', row.get('R印2', '')))
                    moisture = float(moisture_val) if moisture_val else None
                except:
                    moisture = None
                
                # 馬場状態
                track_condition = row.get('馬場状態', '').strip()
                
                races[race_id].append({
                    'pci3': pci3,
                    'moisture': moisture,
                    'track_condition': track_condition
                })
            else:
                # 旧フォーマット: PCIから計算
                try:
                    pci = float(row.get('PCI', ''))
                except:
                    continue
                
                try:
                    finish = int(row.get('確定着順', ''))
                except:
                    continue
                
                try:
                    moisture = float(row.get('R印2', ''))
                except:
                    moisture = None
                
                races[race_id].append({
                    'pci': pci,
                    'finish': finish,
                    'moisture': moisture
                })
    
    # レースごとにPCI3と含水率を算出
    moisture_pci_data = defaultdict(list)
    track_condition_data = defaultdict(list)
    
    for race_id, horses in races.items():
        if not horses:
            continue
        
        # 新フォーマットの場合（PCI3が直接ある）
        if 'pci3' in horses[0]:
            first = horses[0]
            pci3 = first.get('pci3')
            moisture = first.get('moisture')
            track_condition = first.get('track_condition', '')
        else:
            # 旧フォーマット: 着順でソートしてPCI3を計算
            sorted_horses = sorted(horses, key=lambda x: x.get('finish', 999))
            top3 = sorted_horses[:3]
            if len(top3) < 3:
                continue
            pci3 = sum(h['pci'] for h in top3) / 3
            moisture = top3[0].get('moisture')
            track_condition = ''
        
        if pci3 is None or moisture is None:
            continue
        
        # 含水率で分類
        if moisture < 5:
            category = '0-5%'
        elif moisture < 10:
            category = '5-10%'
        elif moisture < 15:
            category = '10-15%'
        elif moisture < 20:
            category = '15-20%'
        else:
            category = '20%以上'
        
        moisture_pci_data[category].append({
            'pci3': pci3,
            'moisture': moisture
        })
        
        # 馬場状態別にも集計
        if track_condition:
            track_condition_data[track_condition].append(pci3)
    
    # 結果を出力
    print("=" * 60)
    print("中山ダート1200m - 含水率別PCI3分析")
    print("=" * 60)
    print()
    
    # 含水率の分布確認
    total_races = sum(len(v) for v in moisture_pci_data.values())
    print(f"分析対象レース数: {total_races}")
    print()
    
    print("■ 含水率区分別の統計")
    print("-" * 60)
    print(f"{'区分':<10} {'レース数':>8} {'PCI3平均':>10} {'標準偏差':>10} {'傾向':>8}")
    print("-" * 60)
    
    categories = ['0-5%', '5-10%', '10-15%', '15-20%', '20%以上']
    results = []
    
    for cat in categories:
        data = moisture_pci_data.get(cat, [])
        if len(data) >= 3:  # 最低3レース以上
            pci3_values = [d['pci3'] for d in data]
            avg = statistics.mean(pci3_values)
            std = statistics.stdev(pci3_values) if len(pci3_values) > 1 else 0
            
            # 基準値(42.4)との比較で傾向判定
            if avg < 40.5:
                trend = 'ハイ傾向'
            elif avg < 42.0:
                trend = 'やや前傾'
            elif avg < 43.0:
                trend = '平均'
            elif avg < 44.5:
                trend = 'ややスロー'
            else:
                trend = 'スロー傾向'
            
            results.append({
                'category': cat,
                'count': len(data),
                'avg': avg,
                'std': std,
                'trend': trend
            })
            print(f"{cat:<10} {len(data):>8} {avg:>10.2f} {std:>10.2f} {trend:>8}")
        else:
            print(f"{cat:<10} {len(data):>8} {'データ不足':>20}")
    
    print("-" * 60)
    print()
    
    # 詳細な含水率範囲でも分析
    print("■ 含水率を細分化した分析")
    print("-" * 60)
    
    # 2%刻みで分析
    fine_data = defaultdict(list)
    for cat, data_list in moisture_pci_data.items():
        for d in data_list:
            m = d['moisture']
            fine_cat = f"{int(m//2)*2}-{int(m//2)*2+2}%"
            fine_data[fine_cat].append(d['pci3'])
    
    # ソートして出力
    sorted_cats = sorted(fine_data.keys(), key=lambda x: int(x.split('-')[0]))
    print(f"{'含水率':<12} {'n':>6} {'PCI3平均':>10}")
    print("-" * 30)
    
    for cat in sorted_cats:
        values = fine_data[cat]
        if len(values) >= 2:
            avg = statistics.mean(values)
            print(f"{cat:<12} {len(values):>6} {avg:>10.2f}")
    
    print()
    
    # 馬場状態別の分析
    if track_condition_data:
        print("■ 馬場状態別PCI3")
        print("-" * 60)
        print(f"{'馬場':<8} {'レース数':>8} {'PCI3平均':>10} {'標準偏差':>10}")
        print("-" * 40)
        
        for cond in ['良', '稍', '稍重', '重', '不', '不良']:
            if cond in track_condition_data:
                vals = track_condition_data[cond]
                avg = statistics.mean(vals)
                std = statistics.stdev(vals) if len(vals) > 1 else 0
                print(f"{cond:<8} {len(vals):>8} {avg:>10.2f} {std:>10.2f}")
        print()
    
    print("■ 考察")
    print("-" * 60)
    
    if results:
        # 最もハイペースになりやすい区分
        min_pci = min(results, key=lambda x: x['avg'])
        max_pci = max(results, key=lambda x: x['avg'])
        
        print(f"・含水率 {min_pci['category']} が最もハイペースになりやすい")
        print(f"  （PCI3平均: {min_pci['avg']:.2f}）")
        print()
        print(f"・含水率 {max_pci['category']} が最もスローになりやすい")
        print(f"  （PCI3平均: {max_pci['avg']:.2f}）")
        print()
        
        diff = max_pci['avg'] - min_pci['avg']
        print(f"・含水率によるPCI差: {diff:.2f}")
        if diff > 3:
            print("  → 含水率はペースに明確な影響あり")
        elif diff > 1.5:
            print("  → 含水率はペースにやや影響あり")
        else:
            print("  → 含水率の影響は限定的")


if __name__ == '__main__':
    import sys
    import glob
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # ファイル名のエンコーディング問題を回避するためglobで検索
        pattern = 'Y:/TXT/PCI*1200.csv'
        matches = glob.glob(pattern)
        if matches:
            csv_path = matches[0]
            print(f"ファイル検出: {csv_path}")
        else:
            print(f"ファイルが見つかりません: {pattern}")
            sys.exit(1)
    
    analyze_moisture_pci(csv_path)

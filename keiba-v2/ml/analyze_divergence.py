"""
V×AR乖離分析スクリプト
- V1位なのにARd下位のケース
- ARd1位なのにV下位のケース
- 各パターンの勝率・複勝率を比較
"""
import json
import sys
from collections import defaultdict

CACHE_PATH = "C:/KEIBA-CICD/data3/ml/backtest_cache.json"

def load_cache():
    with open(CACHE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_divergence(races):
    """V×AR乖離パターン分析"""

    # パターン分類
    patterns = {
        'v1_ard_high': [],    # V1位 & ARd>=55 (一致)
        'v1_ard_mid': [],     # V1位 & 45<=ARd<55 (やや乖離)
        'v1_ard_low': [],     # V1位 & ARd<45 (大乖離)
        'ard_top_v_high': [], # ARd1位 & rank_p<=3 (一致)
        'ard_top_v_low': [],  # ARd1位 & rank_p>=5 (大乖離)
        'both_top': [],       # V1位 & ARd1位 (完全一致)
    }

    for race in races:
        entries = race['entries']
        if len(entries) < 5:
            continue

        # ARdランク計算
        sorted_by_ard = sorted(entries, key=lambda e: -(e.get('ar_deviation') or 0))
        ard_ranks = {}
        for i, e in enumerate(sorted_by_ard):
            ard_ranks[e['umaban']] = i + 1

        for e in entries:
            rv = e.get('rank_p')
            ard = e.get('ar_deviation') or 0
            ard_rank = ard_ranks.get(e['umaban'], 99)

            info = {
                'race_id': race['race_id'],
                'horse_name': e['horse_name'],
                'umaban': e['umaban'],
                'rank_p': rv,
                'ard_rank': ard_rank,
                'ar_deviation': round(ard, 1),
                'odds': e['odds'],
                'odds_rank': e['odds_rank'],
                'vb_gap': e['vb_gap'],
                'finish': e['finish_position'],
                'is_win': e['is_win'],
                'is_top3': e['is_top3'],
                'pred_p_raw': round(e.get('pred_proba_p_raw', 0), 4),
                'win_ev': round(e.get('win_ev', 0) or 0, 2),
                'grade': race['grade'],
            }

            # V1位パターン
            if rv == 1:
                if ard >= 55:
                    patterns['v1_ard_high'].append(info)
                elif ard >= 45:
                    patterns['v1_ard_mid'].append(info)
                else:
                    patterns['v1_ard_low'].append(info)

                if ard_rank == 1:
                    patterns['both_top'].append(info)

            # ARd1位パターン
            if ard_rank == 1:
                if rv is not None and rv <= 3:
                    patterns['ard_top_v_high'].append(info)
                elif rv is not None and rv >= 5:
                    patterns['ard_top_v_low'].append(info)

    return patterns

def print_stats(name, items):
    if not items:
        print(f"\n{'='*60}")
        print(f"  {name}: 0件")
        return

    n = len(items)
    wins = sum(1 for x in items if x['is_win'])
    top3 = sum(1 for x in items if x['is_top3'])
    avg_odds = sum(x['odds'] for x in items) / n
    avg_ard = sum(x['ar_deviation'] for x in items) / n

    # ROI計算
    win_return = sum(x['odds'] for x in items if x['is_win'])
    win_roi = win_return / n * 100 if n > 0 else 0

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  件数: {n}")
    print(f"  勝率: {wins}/{n} = {wins/n*100:.1f}%")
    print(f"  複勝率: {top3}/{n} = {top3/n*100:.1f}%")
    print(f"  単勝ROI: {win_roi:.1f}%")
    print(f"  平均オッズ: {avg_odds:.1f}")
    print(f"  平均ARd: {avg_ard:.1f}")
    print(f"{'='*60}")

def print_examples(name, items, limit=10):
    """乖離ケースの具体例"""
    if not items:
        return

    # 乖離が大きい順（V1位×ARd低い or ARd1位×V低い）
    if 'v1_ard_low' in name:
        items_sorted = sorted(items, key=lambda x: x['ar_deviation'])
    elif 'ard_top_v_low' in name:
        items_sorted = sorted(items, key=lambda x: x['rank_p'], reverse=True)
    else:
        items_sorted = items[:limit]

    print(f"\n  【{name} 具体例 TOP{limit}】")
    print(f"  {'馬名':<12} {'rank_p':>6} {'ARd':>5} {'ARd順':>5} {'odds':>6} {'着順':>4} {'VBgap':>5} {'grade':<8}")
    print(f"  {'-'*60}")
    for x in items_sorted[:limit]:
        marker = '★' if x['is_win'] else ('○' if x['is_top3'] else '  ')
        print(f"  {x['horse_name']:<12} {x['rank_p']:>6} {x['ar_deviation']:>5.1f} {x['ard_rank']:>5} {x['odds']:>6.1f} {x['finish']:>3}{marker} {x['vb_gap']:>5} {x['grade']:<8}")

def analyze_feature_correlation(races):
    """V確率とAR偏差値の相関を見る"""
    v_vals = []
    ard_vals = []
    for race in races:
        for e in race['entries']:
            v = e.get('pred_proba_p_raw', 0)
            ard = e.get('ar_deviation', 0) or 0
            if v > 0 and ard > 0:
                v_vals.append(v)
                ard_vals.append(ard)

    n = len(v_vals)
    mean_v = sum(v_vals) / n
    mean_a = sum(ard_vals) / n
    cov = sum((v - mean_v) * (a - mean_a) for v, a in zip(v_vals, ard_vals)) / n
    std_v = (sum((v - mean_v)**2 for v in v_vals) / n) ** 0.5
    std_a = (sum((a - mean_a)**2 for a in ard_vals) / n) ** 0.5
    corr = cov / (std_v * std_a) if std_v > 0 and std_a > 0 else 0

    print(f"\n{'='*60}")
    print(f"  V確率(raw) × ARd の相関")
    print(f"  データ数: {n}")
    print(f"  相関係数: {corr:.4f}")
    print(f"{'='*60}")

def analyze_odds_band(patterns):
    """オッズ帯別の乖離パターン分析"""
    bands = [(1, 5, '1-5倍'), (5, 10, '5-10倍'), (10, 30, '10-30倍'), (30, 999, '30倍+')]

    print(f"\n{'='*60}")
    print(f"  V1位馬のオッズ帯別 ARd分布")
    print(f"  {'帯':<10} {'V1&ARd高':>10} {'V1&ARd中':>10} {'V1&ARd低':>10}")
    print(f"  {'-'*45}")

    for lo, hi, label in bands:
        h = len([x for x in patterns['v1_ard_high'] if lo <= x['odds'] < hi])
        m = len([x for x in patterns['v1_ard_mid'] if lo <= x['odds'] < hi])
        l = len([x for x in patterns['v1_ard_low'] if lo <= x['odds'] < hi])
        total = h + m + l
        if total > 0:
            print(f"  {label:<10} {h:>5}({h/total*100:4.0f}%) {m:>5}({m/total*100:4.0f}%) {l:>5}({l/total*100:4.0f}%)")

def main():
    print("Loading backtest cache...")
    races = load_cache()
    print(f"Loaded {len(races)} races")

    # 平地のみ
    flat_races = [r for r in races if r.get('track_type', '') != 'obstacle']
    print(f"Flat races: {len(flat_races)}")

    patterns = analyze_divergence(flat_races)

    # 各パターンの統計
    print_stats("V1位 & ARd>=55（V=AR一致型）", patterns['v1_ard_high'])
    print_stats("V1位 & 45<=ARd<55（やや乖離型）", patterns['v1_ard_mid'])
    print_stats("V1位 & ARd<45（大乖離型: Vは高いがAR低い）", patterns['v1_ard_low'])
    print_stats("ARd1位 & rank_p<=3（AR=V一致型）", patterns['ard_top_v_high'])
    print_stats("ARd1位 & rank_p>=5（大乖離型: ARは高いがV低い）", patterns['ard_top_v_low'])
    print_stats("V1位 & ARd1位（完全一致型）", patterns['both_top'])

    # 具体例
    print_examples("v1_ard_low", patterns['v1_ard_low'])
    print_examples("ard_top_v_low", patterns['ard_top_v_low'])

    # 相関分析
    analyze_feature_correlation(flat_races)

    # オッズ帯分析
    analyze_odds_band(patterns)

if __name__ == '__main__':
    main()

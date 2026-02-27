#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ARd × オッズ 価値分析

現行システムの盲点を調査:
  Gap = rank_v vs odds_rank (確率ランク vs 市場ランク)
  → ARd高いのにV%ランクが低い馬は Gap が小さくなり漏れる

新軸の仮説:
  ARd = 能力偏差値 vs odds (能力 vs 市場の直接比較)
  → 「能力は飛び抜けてるのに人気がない」馬に価値があるか？
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main():
    cache_path = Path('C:/KEIBA-CICD/data3/ml/backtest_cache.json')
    print(f'Loading: {cache_path}')
    with open(cache_path, 'r', encoding='utf-8') as f:
        race_preds = json.load(f)
    print(f'  {len(race_preds)} races\n')

    # 全エントリをフラット化
    all_entries = []
    for race in race_preds:
        n_runners = len(race['entries'])
        for e in race['entries']:
            e['_race_id'] = race['race_id']
            e['_grade'] = race.get('grade', '')
            e['_n_runners'] = n_runners
            all_entries.append(e)

    print(f'  Total entries: {len(all_entries):,}\n')

    # =====================================================================
    # 1. ARd帯別の基本統計（全馬、フィルタなし）
    # =====================================================================
    print('=' * 90)
    print('  1. ARd帯別 基本統計（全馬）')
    print('=' * 90)
    print(f'  {"ARd帯":>12} {"N":>6} {"Wins":>5} {"WinRate":>8} {"Top3":>5} {"Top3Rate":>8} '
          f'{"AvgOdds":>8} {"WinROI":>8}')
    print(f'  {"-" * 75}')

    ard_bins = [
        (70, 100, 'ARd>=70'),
        (65, 70, 'ARd 65-69'),
        (60, 65, 'ARd 60-64'),
        (55, 60, 'ARd 55-59'),
        (50, 55, 'ARd 50-54'),
        (45, 50, 'ARd 45-49'),
        (0, 45, 'ARd<45'),
    ]

    for lo, hi, label in ard_bins:
        subset = [e for e in all_entries if lo <= (e.get('ar_deviation') or 0) < hi]
        n = len(subset)
        if n == 0:
            continue
        wins = sum(1 for e in subset if e.get('is_win'))
        top3 = sum(1 for e in subset if e.get('is_top3'))
        avg_odds = np.mean([e.get('odds', 0) for e in subset])
        bet = n * 100
        win_ret = sum(e.get('odds', 0) * 100 for e in subset if e.get('is_win'))
        win_roi = win_ret / bet * 100
        top3_rate = top3 / n * 100
        win_rate = wins / n * 100
        marker = ' ***' if win_roi >= 100 else ''
        print(f'  {label:>12} {n:>6} {wins:>5} {win_rate:>7.1f}% {top3:>5} {top3_rate:>7.1f}% '
              f'{avg_odds:>8.1f} {win_roi:>7.1f}%{marker}')

    # =====================================================================
    # 2. ARd>=65 × オッズ帯別（核心分析）
    # =====================================================================
    print(f'\n{"=" * 90}')
    print('  2. ARd>=65 × オッズ帯別 成績（Gap無視、純粋に能力 vs 市場）')
    print('=' * 90)
    print(f'  {"ARd":>10} {"Odds帯":>12} {"N":>5} {"Wins":>4} {"WinRate":>8} '
          f'{"Top3":>4} {"Top3Rate":>8} {"AvgOdds":>8} {"WinROI":>8} {"PlcROI":>8}')
    print(f'  {"-" * 95}')

    for ard_lo, ard_hi, ard_label in [(70, 100, 'ARd>=70'), (65, 70, 'ARd65-69'), (65, 100, 'ARd>=65')]:
        for odds_lo, odds_hi, odds_label in [
            (1, 3, '1-3倍'),
            (3, 5, '3-5倍'),
            (5, 10, '5-10倍'),
            (10, 20, '10-20倍'),
            (20, 50, '20-50倍'),
            (50, 999, '50倍+'),
            (5, 999, '5倍+'),
            (10, 999, '10倍+'),
        ]:
            subset = [e for e in all_entries
                      if ard_lo <= (e.get('ar_deviation') or 0) < ard_hi
                      and odds_lo <= (e.get('odds') or 0) < odds_hi]
            n = len(subset)
            if n < 3:
                continue
            wins = sum(1 for e in subset if e.get('is_win'))
            top3 = sum(1 for e in subset if e.get('is_top3'))
            avg_odds = np.mean([e.get('odds', 0) for e in subset])
            bet = n * 100
            win_ret = sum(e.get('odds', 0) * 100 for e in subset if e.get('is_win'))
            plc_ret = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                          for e in subset if e.get('is_top3'))
            win_roi = win_ret / bet * 100
            plc_roi = plc_ret / bet * 100
            win_rate = wins / n * 100
            top3_rate = top3 / n * 100
            marker = ' ***' if win_roi >= 100 else ''
            print(f'  {ard_label:>10} {odds_label:>12} {n:>5} {wins:>4} {win_rate:>7.1f}% '
                  f'{top3:>4} {top3_rate:>7.1f}% {avg_odds:>8.1f} {win_roi:>7.1f}%{marker} {plc_roi:>7.1f}%')
        print()

    # =====================================================================
    # 3. ARd vs Gap 相関分析
    # =====================================================================
    print(f'\n{"=" * 90}')
    print('  3. ARd>=65 × Gap クロス分析（ARdが高いのにGapが低い馬）')
    print('=' * 90)
    print(f'  {"ARd":>10} {"Gap":>5} {"N":>5} {"Wins":>4} {"WinRate":>8} '
          f'{"Top3":>4} {"Top3Rate":>8} {"AvgOdds":>8} {"WinROI":>8}')
    print(f'  {"-" * 75}')

    for ard_lo, ard_hi, ard_label in [(70, 100, 'ARd>=70'), (65, 70, 'ARd65-69')]:
        for gap_lo, gap_hi, gap_label in [
            (-99, 0, '<=0'),
            (0, 1, '0'),
            (1, 2, '+1'),
            (2, 3, '+2'),
            (3, 4, '+3'),
            (4, 99, '>=4'),
            (0, 3, '0-2'),  # Gap低い帯 = 今の盲点
        ]:
            subset = [e for e in all_entries
                      if ard_lo <= (e.get('ar_deviation') or 0) < ard_hi
                      and gap_lo <= (e.get('vb_gap') or 0) < gap_hi]
            n = len(subset)
            if n < 3:
                continue
            wins = sum(1 for e in subset if e.get('is_win'))
            top3 = sum(1 for e in subset if e.get('is_top3'))
            avg_odds = np.mean([e.get('odds', 0) for e in subset])
            bet = n * 100
            win_ret = sum(e.get('odds', 0) * 100 for e in subset if e.get('is_win'))
            win_roi = win_ret / bet * 100
            win_rate = wins / n * 100
            top3_rate = top3 / n * 100
            marker = ' ***' if win_roi >= 100 else ''
            print(f'  {ard_label:>10} {gap_label:>5} {n:>5} {wins:>4} {win_rate:>7.1f}% '
                  f'{top3:>4} {top3_rate:>7.1f}% {avg_odds:>8.1f} {win_roi:>7.1f}%{marker}')
        print()

    # =====================================================================
    # 4. 新指標: ARd-based Gap (ARdランク vs odds_rank)
    # =====================================================================
    print(f'\n{"=" * 90}')
    print('  4. 新指標: ARd Gap = odds_rank - ARdランク（能力 vs 市場の乖離）')
    print('=' * 90)

    # 各レース内でARdランクを計算
    for race in race_preds:
        entries = race['entries']
        # ARd降順でランク付け
        sorted_by_ard = sorted(entries, key=lambda e: -(e.get('ar_deviation') or 0))
        for rank, e in enumerate(sorted_by_ard, 1):
            e['ard_rank'] = rank
            e['ard_gap'] = (e.get('odds_rank') or 0) - rank

    # ARd Gap帯別成績
    print(f'\n  {"ARd Gap":>8} {"N":>6} {"Wins":>5} {"WinRate":>8} {"Top3":>5} '
          f'{"Top3Rate":>8} {"AvgOdds":>8} {"WinROI":>8} {"PlcROI":>8} {"AvgARd":>7}')
    print(f'  {"-" * 95}')

    for gap_lo, gap_hi, gap_label in [
        (-99, -2, '<=-2'),
        (-2, 0, '-1~0'),
        (0, 1, '0'),
        (1, 2, '+1'),
        (2, 3, '+2'),
        (3, 4, '+3'),
        (4, 6, '+4~5'),
        (6, 99, '>=6'),
        (2, 99, '>=2'),  # 累積
        (3, 99, '>=3'),
        (4, 99, '>=4'),
    ]:
        subset = [e for e in all_entries
                  if gap_lo <= e.get('ard_gap', 0) < gap_hi]
        n = len(subset)
        if n < 5:
            continue
        wins = sum(1 for e in subset if e.get('is_win'))
        top3 = sum(1 for e in subset if e.get('is_top3'))
        avg_odds = np.mean([e.get('odds', 0) for e in subset])
        avg_ard = np.mean([e.get('ar_deviation', 50) for e in subset])
        bet = n * 100
        win_ret = sum(e.get('odds', 0) * 100 for e in subset if e.get('is_win'))
        plc_ret = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                      for e in subset if e.get('is_top3'))
        win_roi = win_ret / bet * 100
        plc_roi = plc_ret / bet * 100
        win_rate = wins / n * 100
        top3_rate = top3 / n * 100
        marker = ' ***' if win_roi >= 100 else ''
        print(f'  {gap_label:>8} {n:>6} {wins:>5} {win_rate:>7.1f}% {top3:>5} '
              f'{top3_rate:>7.1f}% {avg_odds:>8.1f} {win_roi:>7.1f}%{marker} {plc_roi:>7.1f}% {avg_ard:>7.1f}')

    # =====================================================================
    # 5. ARd Gap × ARd帯 クロス（最重要）
    # =====================================================================
    print(f'\n{"=" * 90}')
    print('  5. ARd Gap × ARd帯 クロス分析（新VBルート候補）')
    print('=' * 90)
    print(f'  {"ARd帯":>10} {"ARdGap":>7} {"N":>5} {"Wins":>4} {"WinRate":>8} '
          f'{"Top3":>4} {"Top3Rate":>8} {"AvgOdds":>8} {"WinROI":>8} {"PlcROI":>8}')
    print(f'  {"-" * 90}')

    for ard_lo, ard_hi, ard_label in [
        (70, 100, 'ARd>=70'),
        (65, 70, 'ARd65-69'),
        (60, 65, 'ARd60-64'),
        (55, 60, 'ARd55-59'),
    ]:
        for min_ard_gap in [1, 2, 3, 4, 5]:
            subset = [e for e in all_entries
                      if ard_lo <= (e.get('ar_deviation') or 0) < ard_hi
                      and e.get('ard_gap', 0) >= min_ard_gap]
            n = len(subset)
            if n < 3:
                continue
            wins = sum(1 for e in subset if e.get('is_win'))
            top3 = sum(1 for e in subset if e.get('is_top3'))
            avg_odds = np.mean([e.get('odds', 0) for e in subset])
            bet = n * 100
            win_ret = sum(e.get('odds', 0) * 100 for e in subset if e.get('is_win'))
            plc_ret = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                          for e in subset if e.get('is_top3'))
            win_roi = win_ret / bet * 100
            plc_roi = plc_ret / bet * 100
            win_rate = wins / n * 100
            top3_rate = top3 / n * 100
            marker = ' ***' if win_roi >= 100 else ''
            print(f'  {ard_label:>10} {">=" + str(min_ard_gap):>7} {n:>5} {wins:>4} {win_rate:>7.1f}% '
                  f'{top3:>4} {top3_rate:>7.1f}% {avg_odds:>8.1f} {win_roi:>7.1f}%{marker} {plc_roi:>7.1f}%')
        print()

    # =====================================================================
    # 6. 現行VB Gap と ARd Gap の重複・排他分析
    # =====================================================================
    print(f'\n{"=" * 90}')
    print('  6. 現行VB(Gap>=3,ARd>=65) vs 新ARdGap(ard_gap>=3,ARd>=65) 排他分析')
    print('=' * 90)

    current_vb = [e for e in all_entries
                  if (e.get('ar_deviation') or 0) >= 65
                  and (e.get('vb_gap') or 0) >= 3]
    new_route = [e for e in all_entries
                 if (e.get('ar_deviation') or 0) >= 65
                 and e.get('ard_gap', 0) >= 3]

    current_keys = {(e['_race_id'], e['umaban']) for e in current_vb}
    new_keys = {(e['_race_id'], e['umaban']) for e in new_route}

    both = current_keys & new_keys
    only_current = current_keys - new_keys
    only_new = new_keys - current_keys

    print(f'  現行VB (Gap>=3, ARd>=65): {len(current_vb)}件')
    print(f'  新ルート (ARdGap>=3, ARd>=65): {len(new_route)}件')
    print(f'  重複: {len(both)}件')
    print(f'  現行のみ: {len(only_current)}件')
    print(f'  新ルートのみ: {len(only_new)}件')

    # 新ルートのみの馬の成績
    if only_new:
        new_only_entries = [e for e in all_entries
                           if (e['_race_id'], e['umaban']) in only_new]
        n = len(new_only_entries)
        wins = sum(1 for e in new_only_entries if e.get('is_win'))
        top3 = sum(1 for e in new_only_entries if e.get('is_top3'))
        avg_odds = np.mean([e.get('odds', 0) for e in new_only_entries])
        bet = n * 100
        win_ret = sum(e.get('odds', 0) * 100 for e in new_only_entries if e.get('is_win'))
        plc_ret = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                      for e in new_only_entries if e.get('is_top3'))
        win_roi = win_ret / bet * 100
        plc_roi = plc_ret / bet * 100
        print(f'\n  --- 新ルートのみの馬 ({n}件) ---')
        print(f'  勝率: {wins}/{n} = {wins/n*100:.1f}%')
        print(f'  複勝率: {top3}/{n} = {top3/n*100:.1f}%')
        print(f'  平均オッズ: {avg_odds:.1f}')
        print(f'  単勝ROI: {win_roi:.1f}%')
        print(f'  複勝ROI: {plc_roi:.1f}%')

        # Gap分布
        gap_dist = {}
        for e in new_only_entries:
            g = e.get('vb_gap', 0)
            gap_dist[g] = gap_dist.get(g, 0) + 1
        print(f'  Gap分布: {dict(sorted(gap_dist.items()))}')

        # 勝ち馬リスト
        winners = [e for e in new_only_entries if e.get('is_win')]
        if winners:
            print(f'\n  勝ち馬一覧:')
            for e in sorted(winners, key=lambda x: -x.get('odds', 0)):
                print(f'    {e["_race_id"]} 馬番{e["umaban"]} {e.get("horse_name",""):12} '
                      f'ARd={e.get("ar_deviation",0):.0f} ARdGap={e.get("ard_gap",0):+d} '
                      f'Gap={e.get("vb_gap",0):+d} odds={e.get("odds",0):.1f} {e["_grade"]}')

    # =====================================================================
    # 7. ヨウシタンレイ型: ARd>=65 & Gap<=2 & odds>=10 （現行で漏れる馬）
    # =====================================================================
    print(f'\n{"=" * 90}')
    print('  7. 現行で漏れる「高能力・低Gap・高オッズ」馬')
    print('     条件: ARd>=65 & Gap<=2 & odds>=10')
    print('=' * 90)

    leaked = [e for e in all_entries
              if (e.get('ar_deviation') or 0) >= 65
              and (e.get('vb_gap') or 0) <= 2
              and (e.get('odds') or 0) >= 10]

    n = len(leaked)
    if n > 0:
        wins = sum(1 for e in leaked if e.get('is_win'))
        top3 = sum(1 for e in leaked if e.get('is_top3'))
        avg_odds = np.mean([e.get('odds', 0) for e in leaked])
        bet = n * 100
        win_ret = sum(e.get('odds', 0) * 100 for e in leaked if e.get('is_win'))
        plc_ret = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                      for e in leaked if e.get('is_top3'))
        win_roi = win_ret / bet * 100
        plc_roi = plc_ret / bet * 100

        print(f'  該当馬: {n}件')
        print(f'  勝率: {wins}/{n} = {wins/n*100:.1f}%')
        print(f'  複勝率: {top3}/{n} = {top3/n*100:.1f}%')
        print(f'  平均オッズ: {avg_odds:.1f}')
        print(f'  単勝ROI: {win_roi:.1f}%')
        print(f'  複勝ROI: {plc_roi:.1f}%')

        # さらにARd>=70で絞る
        leaked70 = [e for e in leaked if (e.get('ar_deviation') or 0) >= 70]
        if leaked70:
            n70 = len(leaked70)
            wins70 = sum(1 for e in leaked70 if e.get('is_win'))
            top370 = sum(1 for e in leaked70 if e.get('is_top3'))
            avg70 = np.mean([e.get('odds', 0) for e in leaked70])
            bet70 = n70 * 100
            wr70 = sum(e.get('odds', 0) * 100 for e in leaked70 if e.get('is_win'))
            pr70 = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                       for e in leaked70 if e.get('is_top3'))
            print(f'\n  うちARd>=70: {n70}件')
            print(f'  勝率: {wins70}/{n70} = {wins70/n70*100:.1f}%')
            print(f'  複勝率: {top370}/{n70} = {top370/n70*100:.1f}%')
            print(f'  平均オッズ: {avg70:.1f}')
            print(f'  単勝ROI: {wr70/bet70*100:.1f}%')
            print(f'  複勝ROI: {pr70/bet70*100:.1f}%')

        # 勝ち馬
        winners = [e for e in leaked if e.get('is_win')]
        if winners:
            print(f'\n  勝ち馬:')
            for e in sorted(winners, key=lambda x: -x.get('odds', 0)):
                print(f'    {e["_race_id"]} 馬番{e["umaban"]} {e.get("horse_name",""):12} '
                      f'ARd={e.get("ar_deviation",0):.0f} Gap={e.get("vb_gap",0):+d} '
                      f'ARdGap={e.get("ard_gap",0):+d} odds={e.get("odds",0):.1f} {e["_grade"]}')

    print('\nDone.')


if __name__ == '__main__':
    main()

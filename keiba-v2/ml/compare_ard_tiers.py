#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ARd gap tier比較バックテスト

現在: [(65,3), (55,4), (45,5)]
提案: [(65,3), (60,3), (55,4), (45,5)]   ← ARd>=60をgap>=3に緩和

backtest_cache.json を使ってフル学習なしで即比較。
"""

import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from ml.bet_engine import (
    PRESETS, BetStrategyParams,
    generate_recommendations, calc_bet_engine_roi,
)


def main():
    # === キャッシュロード ===
    cache_path = Path('C:/KEIBA-CICD/data3/ml/backtest_cache.json')
    print(f'Loading backtest cache: {cache_path}')
    with open(cache_path, 'r', encoding='utf-8') as f:
        race_preds = json.load(f)
    total_entries = sum(len(r['entries']) for r in race_preds)
    print(f'  {len(race_preds)} races, {total_entries:,} entries\n')

    # === ティア定義 ===
    current_tiers = [(65, 3), (55, 4), (45, 5)]
    proposed_tiers = [(65, 3), (60, 3), (55, 4), (45, 5)]

    # もう一つ: (60, 4) — ARd 60は緩和するが gap>=3 は攻めすぎかも
    alt_tiers_60_4 = [(65, 3), (60, 4), (55, 4), (45, 5)]  # 60帯だけgap=4のまま（変化なし確認用）
    # ARd 60 → gap=3（提案）、さらに ARd 55 → gap=3 も（積極的）
    aggressive_tiers = [(65, 3), (60, 3), (55, 3), (45, 5)]

    tier_configs = [
        ('Current [(65,3),(55,4),(45,5)]', current_tiers),
        ('Proposed [(65,3),(60,3),(55,4),(45,5)]', proposed_tiers),
        ('Alt60_4 [(65,3),(60,4),(55,4),(45,5)]', alt_tiers_60_4),
        ('Aggr55_3 [(65,3),(60,3),(55,3),(45,5)]', aggressive_tiers),
    ]

    # =====================================================================
    # 1. 全プリセット×全ティア比較
    # =====================================================================
    print('=' * 90)
    print('  ARd Gap Tier 比較バックテスト')
    print('=' * 90)

    header = (f'  {"Preset":>12} {"Tiers":>38} {"Bets":>5} {"TotBet":>9} '
              f'{"TotRet":>9} {"ROI":>7} {"WinBet":>8} {"WinRet":>8} '
              f'{"WinROI":>7} {"WHit":>4} {"PlcBet":>8} {"PlcRet":>8} {"PlcROI":>7}')
    print(header)
    print(f'  {"-" * 125}')

    for preset_name in ['standard', 'wide', 'aggressive']:
        base_params = deepcopy(PRESETS[preset_name])

        for tier_label, tiers in tier_configs:
            params = deepcopy(base_params)
            params.win_ard_gap_tiers = list(tiers)

            recs = generate_recommendations(race_preds, params, budget=30000)
            roi = calc_bet_engine_roi(recs, race_preds)

            marker = ' ***' if roi['total_roi'] >= 100 else ''
            print(f'  {preset_name:>12} {tier_label:>38} {roi["num_bets"]:>5} '
                  f'{roi["total_bet"]:>9,} {roi["total_return"]:>9,} {roi["total_roi"]:>6.1f}%{marker}'
                  f' {roi["win_bet"]:>8,} {roi["win_return"]:>8,} {roi["win_roi"]:>6.1f}%'
                  f' {roi["win_hits"]:>4}'
                  f' {roi["place_bet"]:>8,} {roi["place_return"]:>8,} {roi["place_roi"]:>6.1f}%')
        print()

    # =====================================================================
    # 2. 差分分析: Proposed で追加される馬リスト
    # =====================================================================
    print('\n' + '=' * 90)
    print('  差分分析: Proposed で追加される馬 (wide preset, EVフィルタなし)')
    print('=' * 90)

    # wide preset (EV filter disabled) で差分が最もわかりやすい
    params_current = deepcopy(PRESETS['wide'])
    params_current.win_ard_gap_tiers = list(current_tiers)
    recs_current = generate_recommendations(race_preds, params_current, budget=30000)

    params_proposed = deepcopy(PRESETS['wide'])
    params_proposed.win_ard_gap_tiers = list(proposed_tiers)
    recs_proposed = generate_recommendations(race_preds, params_proposed, budget=30000)

    current_set = {(r.race_id, r.umaban) for r in recs_current}
    proposed_set = {(r.race_id, r.umaban) for r in recs_proposed}

    added = proposed_set - current_set
    removed = current_set - proposed_set

    # エントリ検索用 lookup
    entry_lookup = {}
    race_lookup = {}
    for race in race_preds:
        race_lookup[race['race_id']] = race
        for e in race['entries']:
            entry_lookup[(race['race_id'], e['umaban'])] = e

    print(f'\n  追加: {len(added)}件, 削除: {len(removed)}件')

    if added:
        # 追加馬の成績集計
        added_wins = 0
        added_top3 = 0
        added_total_odds = 0
        added_entries = []

        for race_id, umaban in sorted(added):
            e = entry_lookup.get((race_id, umaban))
            if e is None:
                continue
            is_win = e.get('is_win', 0)
            is_top3 = e.get('is_top3', 0)
            if is_win:
                added_wins += 1
            if is_top3:
                added_top3 += 1
            added_total_odds += e.get('odds', 0)
            added_entries.append((race_id, umaban, e))

        n = len(added_entries)
        avg_odds = added_total_odds / n if n > 0 else 0
        win_rate = added_wins / n * 100 if n > 0 else 0
        top3_rate = added_top3 / n * 100 if n > 0 else 0

        # ROI計算（100円均一）
        bet_amount = n * 100
        win_return = sum(e.get('odds', 0) * 100 for _, _, e in added_entries if e.get('is_win'))
        place_return = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                           for _, _, e in added_entries if e.get('is_top3'))
        win_roi = win_return / bet_amount * 100 if bet_amount > 0 else 0
        place_roi = place_return / bet_amount * 100 if bet_amount > 0 else 0

        print(f'\n  --- 追加馬 集計 ({n}件) ---')
        print(f'  勝率: {added_wins}/{n} = {win_rate:.1f}%')
        print(f'  複勝率: {added_top3}/{n} = {top3_rate:.1f}%')
        print(f'  平均オッズ: {avg_odds:.1f}')
        print(f'  単勝100円均一ROI: {win_roi:.1f}%')
        print(f'  複勝100円均一ROI: {place_roi:.1f}%')

        print(f'\n  {"race_id":>18} {"馬番":>4} {"馬名":>12} {"ARd":>5} {"Gap":>4} '
              f'{"Odds":>6} {"WinEV":>6} {"着順":>4} {"結果":>6}')
        print(f'  {"-" * 80}')

        # gap降順でソート
        added_entries.sort(key=lambda x: -(x[2].get('vb_gap', 0)))

        for race_id, umaban, e in added_entries:
            ard = e.get('ar_deviation', 0) or 0
            gap = e.get('vb_gap', 0) or 0
            odds = e.get('odds', 0) or 0
            win_ev = e.get('win_ev', 0) or 0
            finish = e.get('finish_position', 0)
            is_win = e.get('is_win', 0)
            is_top3 = e.get('is_top3', 0)
            result = '1着!' if is_win else ('3着内' if is_top3 else '-')
            horse = e.get('horse_name', '')[:10]
            race = race_lookup.get(race_id, {})
            grade = race.get('grade', '')

            print(f'  {race_id:>18} {umaban:>4} {horse:>12} {ard:>5.1f} {gap:>+4} '
                  f'{odds:>6.1f} {win_ev:>6.2f} {finish:>4} {result:>6} {grade}')

    if removed:
        print(f'\n  --- 削除馬 ({len(removed)}件) ---')
        for race_id, umaban in sorted(removed)[:10]:
            e = entry_lookup.get((race_id, umaban))
            if e:
                ard = e.get('ar_deviation', 0) or 0
                gap = e.get('vb_gap', 0) or 0
                horse = e.get('horse_name', '')[:10]
                print(f'    {race_id} 馬番{umaban} {horse} ARd={ard:.1f} Gap={gap}')
        if len(removed) > 10:
            print(f'    ... and {len(removed)-10} more')

    # =====================================================================
    # 3. ARd帯別の詳細統計 (gap別 勝率/ROI)
    # =====================================================================
    print('\n' + '=' * 90)
    print('  ARd帯 × Gap別 統計 (V%比率>=0.75 通過馬のみ)')
    print('=' * 90)

    # V%比率通過馬の中でARd帯×Gap別の成績を見る
    params_all = deepcopy(PRESETS['wide'])
    params_all.win_ard_gap_tiers = [(65, 0), (60, 0), (55, 0), (45, 0), (0, 0)]
    params_all.win_min_ev = 0.0
    params_all.max_win_per_race = 0  # 制限なし

    # V%比率フィルタを通した全馬のGap+ARd+成績
    print(f'\n  {"ARd帯":>10} {"Gap":>4} {"N":>5} {"Wins":>4} {"WinRate":>8} {"Top3":>4} {"Top3Rate":>8} '
          f'{"AvgOdds":>8} {"WinROI":>8} {"PlcROI":>8}')
    print(f'  {"-" * 85}')

    ard_bins = [(65, 100, 'ARd>=65'), (60, 65, 'ARd 60-64'), (55, 60, 'ARd 55-59'),
                (45, 55, 'ARd 45-54'), (0, 45, 'ARd<45')]

    for ard_lo, ard_hi, ard_label in ard_bins:
        for gap_val in [3, 4, 5, 6, 7]:
            entries_in_bin = []
            for race in race_preds:
                # V%比率計算
                v_pcts = [(e.get('pred_proba_p_raw') or 0) for e in race['entries']]
                race_max_v = max(v_pcts) if v_pcts else 0

                for e in race['entries']:
                    ard = e.get('ar_deviation') or 0
                    gap = e.get('vb_gap', 0) or 0
                    v_raw = e.get('pred_proba_p_raw') or 0
                    v_ratio = v_raw / race_max_v if race_max_v > 0 else 0

                    if (ard_lo <= ard < ard_hi and gap == gap_val and v_ratio >= 0.75):
                        entries_in_bin.append(e)

            n = len(entries_in_bin)
            if n == 0:
                continue

            wins = sum(1 for e in entries_in_bin if e.get('is_win'))
            top3 = sum(1 for e in entries_in_bin if e.get('is_top3'))
            avg_odds = sum(e.get('odds', 0) for e in entries_in_bin) / n
            bet = n * 100
            win_ret = sum(e.get('odds', 0) * 100 for e in entries_in_bin if e.get('is_win'))
            plc_ret = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                          for e in entries_in_bin if e.get('is_top3'))
            win_roi = win_ret / bet * 100 if bet > 0 else 0
            plc_roi = plc_ret / bet * 100 if bet > 0 else 0
            win_rate = wins / n * 100
            top3_rate = top3 / n * 100

            marker = ' ***' if win_roi >= 100 else ''
            print(f'  {ard_label:>10} {gap_val:>+4} {n:>5} {wins:>4} {win_rate:>7.1f}% '
                  f'{top3:>4} {top3_rate:>7.1f}% {avg_odds:>8.1f} {win_roi:>7.1f}%{marker} {plc_roi:>7.1f}%')

    # =====================================================================
    # 4. ARd 60-64 帯の累積Gap統計
    # =====================================================================
    print('\n' + '=' * 90)
    print('  ARd 60-64帯 累積Gap統計 (gap>=N の場合の合計成績)')
    print('=' * 90)

    print(f'\n  {"Gap>=":>6} {"N":>5} {"Wins":>4} {"WinRate":>8} {"Top3":>4} {"Top3Rate":>8} '
          f'{"AvgOdds":>8} {"WinROI":>8} {"PlcROI":>8}')
    print(f'  {"-" * 70}')

    for min_gap in [2, 3, 4, 5, 6, 7]:
        entries_in_bin = []
        for race in race_preds:
            v_pcts = [(e.get('pred_proba_p_raw') or 0) for e in race['entries']]
            race_max_v = max(v_pcts) if v_pcts else 0
            for e in race['entries']:
                ard = e.get('ar_deviation') or 0
                gap = e.get('vb_gap', 0) or 0
                v_raw = e.get('pred_proba_p_raw') or 0
                v_ratio = v_raw / race_max_v if race_max_v > 0 else 0
                if 60 <= ard < 65 and gap >= min_gap and v_ratio >= 0.75:
                    entries_in_bin.append(e)

        n = len(entries_in_bin)
        if n == 0:
            continue

        wins = sum(1 for e in entries_in_bin if e.get('is_win'))
        top3 = sum(1 for e in entries_in_bin if e.get('is_top3'))
        avg_odds = sum(e.get('odds', 0) for e in entries_in_bin) / n
        bet = n * 100
        win_ret = sum(e.get('odds', 0) * 100 for e in entries_in_bin if e.get('is_win'))
        plc_ret = sum((e.get('place_odds_min') or e.get('odds', 0) / 3.5) * 100
                      for e in entries_in_bin if e.get('is_top3'))
        win_roi = win_ret / bet * 100 if bet > 0 else 0
        plc_roi = plc_ret / bet * 100 if bet > 0 else 0
        win_rate = wins / n * 100
        top3_rate = top3 / n * 100
        marker = ' ***' if win_roi >= 100 else ''
        print(f'  {min_gap:>6} {n:>5} {wins:>4} {win_rate:>7.1f}% '
              f'{top3:>4} {top3_rate:>7.1f}% {avg_odds:>8.1f} {win_roi:>7.1f}%{marker} {plc_roi:>7.1f}%')

    print('\nDone.')


if __name__ == '__main__':
    main()

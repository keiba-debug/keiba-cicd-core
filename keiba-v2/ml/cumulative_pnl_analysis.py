#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cumulative P&L Analysis: 時系列での損益推移とドローダウン分析

value_bet_picksから各戦略の累積損益を時系列で計算し、
- 累積P&Lの推移パターン（単調増加 or 偏り）
- 最大ドローダウン
- 月別損益
- gap>=6のレース種別偏り
を分析する。
"""

import json
import sys
import io
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_picks():
    result_path = Path("C:/KEIBA-CICD/data3/ml/ml_experiment_v3_result.json")
    with open(result_path, encoding='utf-8') as f:
        data = json.load(f)
    return data['value_bet_picks'], data.get('gap_margin_grid', [])


def filter_picks(picks, min_gap, max_margin=None):
    """gap/margin条件でフィルタ"""
    result = []
    for p in picks:
        if p['gap'] < min_gap:
            continue
        if max_margin is not None and p.get('predicted_margin', 999) > max_margin:
            continue
        result.append(p)
    return result


def compute_cumulative_pnl(picks, bet_unit=100):
    """日付順にソートして累積P&Lを計算（単勝のみ）"""
    sorted_picks = sorted(picks, key=lambda x: (x['date'], x['race_id']))
    cum_pnl = 0
    peak = 0
    max_dd = 0  # max drawdown
    timeline = []  # [(date, cum_pnl, drawdown)]

    for p in sorted_picks:
        is_win = 1 if p['actual_position'] == 1 else 0
        pnl = (p['odds'] * bet_unit - bet_unit) if is_win else -bet_unit
        cum_pnl += pnl
        peak = max(peak, cum_pnl)
        dd = peak - cum_pnl
        max_dd = max(max_dd, dd)
        timeline.append({
            'date': p['date'],
            'race_id': p['race_id'],
            'horse': p['horse_name'],
            'odds': p['odds'],
            'is_win': is_win,
            'pnl': pnl,
            'cum_pnl': cum_pnl,
            'drawdown': dd,
        })

    return timeline, max_dd


def monthly_summary(timeline):
    """月別の損益サマリー"""
    monthly = defaultdict(lambda: {'bets': 0, 'wins': 0, 'pnl': 0})
    for t in timeline:
        month = t['date'][:7]  # YYYY-MM
        monthly[month]['bets'] += 1
        monthly[month]['wins'] += t['is_win']
        monthly[month]['pnl'] += t['pnl']
    return dict(monthly)


def analyze_race_bias(picks, label=""):
    """レース種別・venue・gradeの偏りを分析"""
    venue_counts = defaultdict(int)
    grade_counts = defaultdict(int)
    odds_ranges = defaultdict(int)

    for p in picks:
        venue_counts[p.get('venue', '?')] += 1
        grade_counts[p.get('grade', '?')] += 1
        odds = p.get('odds', 0)
        if odds < 10:
            odds_ranges['<10'] += 1
        elif odds < 30:
            odds_ranges['10-30'] += 1
        elif odds < 100:
            odds_ranges['30-100'] += 1
        else:
            odds_ranges['>=100'] += 1

    print(f"\n  --- レース偏り分析: {label} ({len(picks)}件) ---")
    print(f"  Venue分布:")
    for v, c in sorted(venue_counts.items(), key=lambda x: -x[1]):
        pct = c / len(picks) * 100
        print(f"    {v}: {c} ({pct:.1f}%)")

    print(f"  Grade分布:")
    for g, c in sorted(grade_counts.items(), key=lambda x: -x[1]):
        pct = c / len(picks) * 100
        print(f"    {g}: {c} ({pct:.1f}%)")

    print(f"  Odds分布:")
    for r in ['<10', '10-30', '30-100', '>=100']:
        c = odds_ranges.get(r, 0)
        pct = c / len(picks) * 100
        print(f"    {r}: {c} ({pct:.1f}%)")


def print_pnl_chart(timeline, width=60):
    """簡易ASCII累積P&Lチャート（月単位）"""
    if not timeline:
        return

    monthly_cum = {}
    for t in timeline:
        month = t['date'][:7]
        monthly_cum[month] = t['cum_pnl']

    months = sorted(monthly_cum.keys())
    values = [monthly_cum[m] for m in months]
    min_v = min(values)
    max_v = max(values)
    range_v = max_v - min_v if max_v != min_v else 1

    print(f"\n  Cumulative P&L chart (min={min_v:,.0f}, max={max_v:,.0f}):")
    for m in months:
        v = monthly_cum[m]
        pos = int((v - min_v) / range_v * width)
        zero_pos = int((0 - min_v) / range_v * width) if min_v < 0 else 0
        bar = list(' ' * (width + 1))

        if min_v < 0:
            bar[zero_pos] = '|'

        if v >= 0:
            for i in range(zero_pos, pos + 1):
                bar[i] = '#'
        else:
            for i in range(pos, zero_pos + 1):
                bar[i] = '-'

        print(f"  {m} {''.join(bar)} {v:>+8,.0f}")


def main():
    picks, grid = load_picks()
    print("=" * 80)
    print("Cumulative P&L Analysis - Session 45")
    print(f"Data: {len(picks)} VB picks (Place model, gap>=3)")
    print("=" * 80)

    # 分析対象の戦略定義（重要度順に絞る）
    strategies = [
        ("gap>=5, margin<=1.2", 5, 1.2),
        ("gap>=5, margin<=0.8", 5, 0.8),
        ("gap>=6, margin<=1.2", 6, 1.2),
        ("gap>=6, margin<=0.8", 6, 0.8),
    ]

    for label, min_gap, max_margin in strategies:
        filtered = filter_picks(picks, min_gap, max_margin)
        if not filtered:
            print(f"\n### {label}: 0 picks, skipping")
            continue

        timeline, max_dd = compute_cumulative_pnl(filtered)
        monthly = monthly_summary(timeline)

        total_bets = len(filtered)
        total_wins = sum(1 for t in timeline if t['is_win'])
        final_pnl = timeline[-1]['cum_pnl'] if timeline else 0
        win_rate = total_wins / total_bets * 100 if total_bets > 0 else 0
        roi = (final_pnl + total_bets * 100) / (total_bets * 100) * 100

        print(f"\n{'='*80}")
        print(f"### {label}")
        print(f"{'='*80}")
        print(f"  Bets: {total_bets}, Wins: {total_wins} ({win_rate:.1f}%)")
        print(f"  Final P&L: {final_pnl:+,.0f}, ROI: {roi:.1f}%")
        print(f"  Max Drawdown: {max_dd:,.0f}")
        print(f"  DD/Total Bet: {max_dd / (total_bets * 100) * 100:.1f}%")

        # P&L chart
        print_pnl_chart(timeline)

        # 月別サマリー
        print(f"\n  Monthly P&L:")
        print(f"  {'Month':>8} {'Bets':>5} {'Wins':>5} {'P&L':>8} {'CumP&L':>9}")
        print(f"  {'-'*40}")
        cum = 0
        months_sorted = sorted(monthly.keys())
        positive_months = 0
        for m in months_sorted:
            d = monthly[m]
            cum += d['pnl']
            if d['pnl'] > 0:
                positive_months += 1
            print(f"  {m:>8} {d['bets']:>5} {d['wins']:>5} {d['pnl']:>+8,.0f} {cum:>+9,.0f}")
        print(f"  Positive months: {positive_months}/{len(months_sorted)} ({positive_months/len(months_sorted)*100:.0f}%)")

    # gap>=6 レース偏り分析
    print("\n" + "=" * 80)
    print("### レース偏り分析")
    print("=" * 80)

    # 全体 vs gap>=6 の比較
    all_gap3 = filter_picks(picks, 3)
    gap6_m12 = filter_picks(picks, 6, 1.2)
    gap5_m12 = filter_picks(picks, 5, 1.2)

    analyze_race_bias(all_gap3, "全体 gap>=3")
    analyze_race_bias(gap5_m12, "gap>=5 margin<=1.2")
    analyze_race_bias(gap6_m12, "gap>=6 margin<=1.2")

    # 勝ち馬の特徴
    print("\n" + "=" * 80)
    print("### 勝ちパターン分析 (gap>=5 margin<=1.2)")
    print("=" * 80)
    gap5_filtered = filter_picks(picks, 5, 1.2)
    winners = [p for p in gap5_filtered if p['actual_position'] == 1]
    if winners:
        print(f"  Wins: {len(winners)}/{len(gap5_filtered)} ({len(winners)/len(gap5_filtered)*100:.1f}%)")
        avg_odds = sum(w['odds'] for w in winners) / len(winners)
        print(f"  平均勝ちオッズ: {avg_odds:.1f}")
        print(f"  勝ちオッズ分布:")
        for w in sorted(winners, key=lambda x: x['odds']):
            print(f"    {w['date']} {w['venue']} {w['horse']} odds={w['odds']:.1f} gap={w['gap']} margin={w.get('predicted_margin', '?')}")


if __name__ == '__main__':
    main()

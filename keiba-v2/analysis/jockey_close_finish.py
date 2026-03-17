#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
騎手接戦分析 — jockeys.json から接戦勝率の分析データを生成

出力: data3/analysis/jockey_close_finish.json
Webの /analysis/jockey-close-finish ページで表示する。

Usage:
    python -m analysis.jockey_close_finish
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config

MIN_CLOSE_TOTAL = 10   # ランキング表示の最低接戦数
MIN_YEAR_TOTAL = 5     # 年度別トレンドの最低接戦数


def load_jockeys():
    path = config.masters_dir() / "jockeys.json"
    return json.loads(path.read_text(encoding='utf-8'))


def build_ranking(jockeys: list) -> list:
    """接戦勝率ランキング（サンプル数>=MIN_CLOSE_TOTAL）"""
    candidates = [j for j in jockeys if j.get('close_total', 0) >= MIN_CLOSE_TOTAL]
    ranked = sorted(candidates, key=lambda x: x['close_win_rate'], reverse=True)
    return [
        {
            'rank': i + 1,
            'code': j['code'],
            'name': j['name'],
            'total_runs': j['total_runs'],
            'wins': j['wins'],
            'win_rate': j['win_rate'],
            'top3_rate': j['top3_rate'],
            'close_wins': j['close_wins'],
            'close_seconds': j['close_seconds'],
            'close_total': j['close_total'],
            'close_win_rate': j['close_win_rate'],
            'close_by_track': j.get('close_by_track', {}),
            'close_by_distance': j.get('close_by_distance', {}),
        }
        for i, j in enumerate(ranked)
    ]


def build_growth_trends(jockeys: list) -> list:
    """騎手ごとの年度別接戦勝率トレンド（成長/衰退の可視化用）"""
    trends = []
    for j in jockeys:
        if j.get('close_total', 0) < MIN_CLOSE_TOTAL:
            continue

        year_data = {}
        for y, ys in sorted(j.get('year_stats', {}).items()):
            ct = ys.get('close_total', 0)
            if ct < MIN_YEAR_TOTAL:
                year_data[y] = {
                    'close_total': ct,
                    'close_win_rate': None,  # サンプル不足
                    'win_rate': round(ys['wins'] / ys['runs'], 4) if ys['runs'] > 0 else 0,
                    'runs': ys['runs'],
                }
            else:
                year_data[y] = {
                    'close_total': ct,
                    'close_win_rate': ys.get('close_win_rate', 0),
                    'win_rate': round(ys['wins'] / ys['runs'], 4) if ys['runs'] > 0 else 0,
                    'runs': ys['runs'],
                }

        # 成長スコア: 直近2年の平均 - 過去の平均
        years_sorted = sorted(year_data.keys())
        valid_years = [y for y in years_sorted if year_data[y]['close_win_rate'] is not None]
        growth_score = None
        if len(valid_years) >= 3:
            recent = valid_years[-2:]
            older = valid_years[:-2]
            recent_avg = sum(year_data[y]['close_win_rate'] for y in recent) / len(recent)
            older_avg = sum(year_data[y]['close_win_rate'] for y in older) / len(older)
            growth_score = round(recent_avg - older_avg, 4)

        trends.append({
            'code': j['code'],
            'name': j['name'],
            'total_runs': j['total_runs'],
            'close_total': j['close_total'],
            'close_win_rate': j['close_win_rate'],
            'growth_score': growth_score,
            'years': year_data,
        })

    # growth_scoreがある騎手をスコア順にソート
    trends.sort(key=lambda x: (x['growth_score'] is not None, x['growth_score'] or 0),
                reverse=True)
    return trends


def build_condition_analysis(jockeys: list) -> dict:
    """条件別（芝/ダ、距離帯）の全体傾向"""
    # 芝/ダ別の集計
    track_agg = {}
    for track in ['turf', 'dirt']:
        total_wins = 0
        total_seconds = 0
        for j in jockeys:
            bt = j.get('close_by_track', {}).get(track, {})
            total_wins += bt.get('close_wins', 0)
            total_seconds += bt.get('close_seconds', 0)
        total = total_wins + total_seconds
        track_agg[track] = {
            'close_wins': total_wins,
            'close_seconds': total_seconds,
            'close_total': total,
            'close_win_rate': round(total_wins / total, 4) if total > 0 else 0,
        }

    # 距離帯別の集計
    dist_agg = {}
    for dist in ['sprint', 'mile', 'intermediate', 'long', 'extended']:
        total_wins = 0
        total_seconds = 0
        for j in jockeys:
            bd = j.get('close_by_distance', {}).get(dist, {})
            total_wins += bd.get('close_wins', 0)
            total_seconds += bd.get('close_seconds', 0)
        total = total_wins + total_seconds
        dist_agg[dist] = {
            'close_wins': total_wins,
            'close_seconds': total_seconds,
            'close_total': total,
            'close_win_rate': round(total_wins / total, 4) if total > 0 else 0,
        }

    return {
        'by_track': track_agg,
        'by_distance': dist_agg,
    }


def build_summary(jockeys: list, ranking: list) -> dict:
    """全体サマリ統計"""
    all_close = sum(j.get('close_total', 0) for j in jockeys)
    all_close_wins = sum(j.get('close_wins', 0) for j in jockeys)
    qualified = [j for j in jockeys if j.get('close_total', 0) >= MIN_CLOSE_TOTAL]
    rates = [j['close_win_rate'] for j in qualified]

    # 集計期間をyear_statsから算出
    all_years = set()
    total_races = 0
    for j in jockeys:
        for y, ys in j.get('year_stats', {}).items():
            all_years.add(y)
            total_races += ys.get('runs', 0)

    return {
        'total_jockeys': len(jockeys),
        'qualified_jockeys': len(qualified),
        'total_close_finishes': all_close,
        'total_races': total_races,
        'overall_close_win_rate': round(all_close_wins / all_close, 4) if all_close > 0 else 0,
        'avg_close_win_rate': round(sum(rates) / len(rates), 4) if rates else 0,
        'median_close_win_rate': round(sorted(rates)[len(rates) // 2], 4) if rates else 0,
        'year_from': min(all_years) if all_years else '',
        'year_to': max(all_years) if all_years else '',
        'min_close_total': MIN_CLOSE_TOTAL,
        'min_year_total': MIN_YEAR_TOTAL,
    }


def main():
    print("=" * 60)
    print("  KeibaCICD - Jockey Close Finish Analysis")
    print("=" * 60)

    jockeys = load_jockeys()
    print(f"  Loaded {len(jockeys)} jockeys from master")

    ranking = build_ranking(jockeys)
    print(f"  Ranking: {len(ranking)} qualified jockeys (>= {MIN_CLOSE_TOTAL} close finishes)")

    trends = build_growth_trends(jockeys)
    print(f"  Growth trends: {len(trends)} jockeys")

    conditions = build_condition_analysis(jockeys)
    summary = build_summary(jockeys, ranking)

    result = {
        'created_at': datetime.now().isoformat(),
        'summary': summary,
        'ranking': ranking,
        'growth_trends': trends,
        'conditions': conditions,
    }

    out_dir = config.data_root() / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "jockey_close_finish.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    print(f"\n  Output: {out_path}")
    print(f"  Summary: {summary['qualified_jockeys']} qualified, "
          f"avg close_win_rate={summary['avg_close_win_rate']:.1%}")

    # Top 5
    print(f"\n  Top 5 close win rate:")
    for r in ranking[:5]:
        print(f"    {r['rank']:>2}. {r['name']:>8}: {r['close_win_rate']:.1%} "
              f"({r['close_wins']}/{r['close_total']})")

    # Top 5 growth
    growers = [t for t in trends if t['growth_score'] is not None]
    if growers:
        print(f"\n  Top 5 growth (recent vs older):")
        for t in growers[:5]:
            print(f"    {t['name']:>8}: growth={t['growth_score']:+.1%} "
                  f"(overall {t['close_win_rate']:.1%})")

    print(f"\n{'=' * 60}")


if __name__ == '__main__':
    main()

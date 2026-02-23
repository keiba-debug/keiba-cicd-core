"""市場乖離スコア分析

margin×oddsの市場乖離スコアが的中馬の弁別に有効かを検証。
v5.5 liveモデル + テスト期間(2025/01-2026/02)で分析。再学習なし。

候補スコア:
  1. margin / odds  — 低いほど「モデル自信あり × 市場オッズ高い」
  2. gap × (1 / odds) — ランク差 × 配当の逆数
  3. gap × margin / odds — 複合スコア

Usage:
    python -m ml.market_divergence_analysis
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from ml.monthly_analysis import (
    load_data, build_dataset, load_v55_models, predict_on_df,
    filter_win_only, bootstrap_roi_ci,
    FEATURE_COLS_ALL, FEATURE_COLS_VALUE,
)


def main():
    print('=' * 70)
    print('  市場乖離スコア分析')
    print('=' * 70)

    # === データロード ===
    print('\n[Load] Loading data...')
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index) = load_data()

    print('\n[Build] Building test dataset (2025-2026)...')
    df_test = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index,
        min_year=2025, max_year=2026,
        training_summary_index=training_summary_index,
    )

    # === モデル予測 ===
    print('\n[Model] Loading v5.5 and predicting...')
    model_a, model_b, model_w, model_wv, model_reg_b, calibrators = load_v55_models()
    df_test = predict_on_df(df_test, model_a, model_b, model_w, model_wv, model_reg_b, calibrators)

    # === Wide条件(gap>=5 m<=1.2)のbet対象馬を抽出 ===
    bets = filter_win_only(df_test, min_gap=5, max_margin=1.2)
    print(f'\n[Data] Wide条件: {len(bets)}件, 的中={int(bets["is_win"].sum())}件')

    # === スコア計算 ===
    bets = bets.copy()
    bets['margin_div_odds'] = bets['margin'] / bets['odds']
    bets['inv_odds'] = 1.0 / bets['odds']
    bets['gap_inv_odds'] = bets['win_gap'] * bets['inv_odds']
    bets['gap_margin_odds'] = bets['win_gap'] * bets['margin'] / bets['odds']

    hits = bets[bets['is_win'] == 1]
    misses = bets[bets['is_win'] == 0]

    # ============================================================
    # 1. 的中馬 vs 非的中馬のスコア分布
    # ============================================================
    print('\n' + '=' * 70)
    print('  1. 的中馬 vs 非的中馬のスコア分布')
    print('=' * 70)

    scores = ['margin', 'odds', 'margin_div_odds', 'win_gap', 'gap_inv_odds', 'gap_margin_odds', 'win_ev']
    labels = ['margin(s)', 'odds', 'm/odds', 'win_gap', 'gap/odds', 'gap*m/odds', 'win_ev']

    print(f'\n{"スコア":>14} | {"的中 mean":>10} {"的中 med":>10} | {"非的中 mean":>10} {"非的中 med":>10} | {"差(mean)":>10}')
    print('-' * 90)

    for score, label in zip(scores, labels):
        h_mean = hits[score].mean()
        h_med = hits[score].median()
        m_mean = misses[score].mean()
        m_med = misses[score].median()
        diff = h_mean - m_mean
        print(f'{label:>14} | {h_mean:>10.4f} {h_med:>10.4f} | {m_mean:>10.4f} {m_med:>10.4f} | {diff:>+10.4f}')

    # ============================================================
    # 2. margin/odds 帯別ROI
    # ============================================================
    print('\n' + '=' * 70)
    print('  2. margin/odds 帯別ROI')
    print('=' * 70)

    # margin/odds の分位点でビン分け
    bets['mdo_q'] = pd.qcut(bets['margin_div_odds'], q=5, duplicates='drop')
    print(f'\n{"m/odds帯":>20} | {"件数":>6} | {"的中":>4} | {"的中率":>6} | {"ROI":>8} | {"P&L":>8}')
    print('-' * 70)
    for q, g in bets.groupby('mdo_q', observed=True):
        n = len(g)
        wins = int(g['is_win'].sum())
        wr = wins / n * 100
        cost = n * 100
        ret = (g['is_win'] * g['odds'] * 100).sum()
        roi = ret / cost * 100
        pnl = ret - cost
        print(f'{str(q):>20} | {n:>6} | {wins:>4} | {wr:>5.1f}% | {roi:>7.1f}% | {pnl:>+7.0f}')

    # ============================================================
    # 3. gap帯別 × margin/odds高低のROI
    # ============================================================
    print('\n' + '=' * 70)
    print('  3. gap帯別 × margin/odds高低のROI (中央値で2分割)')
    print('=' * 70)

    mdo_median = bets['margin_div_odds'].median()
    print(f'  m/odds中央値: {mdo_median:.4f}')

    bets['mdo_half'] = np.where(bets['margin_div_odds'] <= mdo_median, 'low(おいしい)', 'high')

    print(f'\n{"gap帯":>10} {"m/odds":>12} | {"件数":>6} {"的中":>4} {"的中率":>6} {"ROI":>8} {"P&L":>8}')
    print('-' * 70)

    for gap_min in [5, 6, 7]:
        gap_label = f'gap={gap_min}' if gap_min < 7 else f'gap>={gap_min}'
        if gap_min < 7:
            sub = bets[(bets['win_gap'] == gap_min)]
        else:
            sub = bets[(bets['win_gap'] >= gap_min)]

        for half in ['low(おいしい)', 'high']:
            g = sub[sub['mdo_half'] == half]
            if len(g) == 0:
                continue
            n = len(g)
            wins = int(g['is_win'].sum())
            wr = wins / n * 100
            cost = n * 100
            ret = (g['is_win'] * g['odds'] * 100).sum()
            roi = ret / cost * 100
            pnl = ret - cost
            marker = ' ***' if roi > 100 else ''
            print(f'{gap_label:>10} {half:>12} | {n:>6} {wins:>4} {wr:>5.1f}% {roi:>7.1f}%{marker} {pnl:>+7.0f}')

    # ============================================================
    # 4. 複合スコア上位 vs 下位のROI
    # ============================================================
    print('\n' + '=' * 70)
    print('  4. gap帯別 × オッズ高低のROI (中央値で2分割)')
    print('=' * 70)

    odds_median = bets['odds'].median()
    print(f'  オッズ中央値: {odds_median:.1f}')

    bets['odds_half'] = np.where(bets['odds'] >= odds_median, 'high(穴)', 'low(人気)')

    print(f'\n{"gap帯":>10} {"odds帯":>12} | {"件数":>6} {"的中":>4} {"的中率":>6} {"ROI":>8} {"P&L":>8}')
    print('-' * 70)

    for gap_min in [5, 6, 7]:
        gap_label = f'gap={gap_min}' if gap_min < 7 else f'gap>={gap_min}'
        if gap_min < 7:
            sub = bets[(bets['win_gap'] == gap_min)]
        else:
            sub = bets[(bets['win_gap'] >= gap_min)]

        for half in ['high(穴)', 'low(人気)']:
            g = sub[sub['odds_half'] == half]
            if len(g) == 0:
                continue
            n = len(g)
            wins = int(g['is_win'].sum())
            wr = wins / n * 100
            cost = n * 100
            ret = (g['is_win'] * g['odds'] * 100).sum()
            roi = ret / cost * 100
            pnl = ret - cost
            marker = ' ***' if roi > 100 else ''
            print(f'{gap_label:>10} {half:>12} | {n:>6} {wins:>4} {wr:>5.1f}% {roi:>7.1f}%{marker} {pnl:>+7.0f}')

    # ============================================================
    # 5. 的中馬リスト(全件)
    # ============================================================
    print('\n' + '=' * 70)
    print('  5. 的中馬リスト (Wide条件, 的中のみ)')
    print('=' * 70)

    cols = ['date', 'race_id', 'horse_name', 'umaban', 'win_gap', 'margin', 'odds',
            'margin_div_odds', 'win_ev']
    hits_sorted = hits.sort_values('margin_div_odds')
    print(f'\n{"日付":>12} {"R":>5} {"馬名":>10} {"番":>3} {"gap":>4} {"m":>6} {"odds":>7} {"m/odds":>8} {"winEV":>7}')
    print('-' * 75)
    for _, r in hits_sorted.iterrows():
        print(f'{r["date"]:>12} {str(r["race_id"])[-4:]:>5} {str(r["horse_name"])[:10]:>10} '
              f'{int(r["umaban"]):>3} {int(r["win_gap"]):>4} {r["margin"]:>6.2f} '
              f'{r["odds"]:>7.1f} {r["margin_div_odds"]:>8.4f} {r["win_ev"]:>7.2f}')

    # ============================================================
    # 6. Bootstrap CI: m/odds上位半分 vs 下位半分
    # ============================================================
    print('\n' + '=' * 70)
    print('  6. Bootstrap CI: m/odds低い(おいしい)半分 vs 高い半分')
    print('=' * 70)

    low_half = bets[bets['mdo_half'] == 'low(おいしい)']
    high_half = bets[bets['mdo_half'] == 'high']

    ci_low = bootstrap_roi_ci(low_half)
    ci_high = bootstrap_roi_ci(high_half)

    print(f'\n{"条件":>20} | {"件数":>5} {"ROI":>7} {"CI_low":>8} {"CI_high":>8} {"CI幅":>7} {"的中率":>6}')
    print('-' * 70)
    print(f'{"m/odds低い(おいしい)":>20} | {ci_low["count"]:>5} {ci_low["roi"]:>6.1f}% {ci_low["ci_low"]:>7.1f}% {ci_low["ci_high"]:>7.1f}% {ci_low["ci_width"]:>6.1f} {ci_low["win_rate"]:>5.1f}%')
    print(f'{"m/odds高い":>20} | {ci_high["count"]:>5} {ci_high["roi"]:>6.1f}% {ci_high["ci_low"]:>7.1f}% {ci_high["ci_high"]:>7.1f}% {ci_high["ci_width"]:>6.1f} {ci_high["win_rate"]:>5.1f}%')

    # Standard条件でも同じ分析
    std = filter_win_only(df_test, min_gap=6, max_margin=1.2).copy()
    std['margin_div_odds'] = std['margin'] / std['odds']
    std_med = std['margin_div_odds'].median()
    std['mdo_half'] = np.where(std['margin_div_odds'] <= std_med, 'low(おいしい)', 'high')

    std_low = std[std['mdo_half'] == 'low(おいしい)']
    std_high = std[std['mdo_half'] == 'high']
    ci_std_low = bootstrap_roi_ci(std_low)
    ci_std_high = bootstrap_roi_ci(std_high)

    print(f'\n--- Standard (gap>=6) ---')
    print(f'  m/odds中央値: {std_med:.4f}')
    print(f'{"m/odds低い(おいしい)":>20} | {ci_std_low["count"]:>5} {ci_std_low["roi"]:>6.1f}% {ci_std_low["ci_low"]:>7.1f}% {ci_std_low["ci_high"]:>7.1f}% {ci_std_low["ci_width"]:>6.1f} {ci_std_low["win_rate"]:>5.1f}%')
    print(f'{"m/odds高い":>20} | {ci_std_high["count"]:>5} {ci_std_high["roi"]:>6.1f}% {ci_std_high["ci_low"]:>7.1f}% {ci_std_high["ci_high"]:>7.1f}% {ci_std_high["ci_width"]:>6.1f} {ci_std_high["win_rate"]:>5.1f}%')

    print('\n\nDone.')


if __name__ == '__main__':
    main()

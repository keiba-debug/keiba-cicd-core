"""累積P&L + 連敗分析スクリプト

v5.8月別分析の追加分析。3条件の累積P&Lチャートと連敗統計を出力。
"""

import sys
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config
from ml.experiment import (
    load_data,
    build_dataset,
    FEATURE_COLS_VALUE,
)


def load_v55_models():
    import lightgbm as lgb
    model_dir = config.ml_dir() / "versions" / "v5.5"
    model_p = lgb.Booster(model_file=str(model_dir / "model_p.txt"))
    model_w = lgb.Booster(model_file=str(model_dir / "model_w.txt"))
    model_ar = lgb.Booster(model_file=str(model_dir / "model_ar.txt"))
    with open(model_dir / "calibrators.pkl", 'rb') as f:
        calibrators = pickle.load(f)
    return model_p, model_w, model_ar, calibrators


def predict_on_df(df, model_p, model_w, model_ar, calibrators):
    pred_p = model_p.predict(df[FEATURE_COLS_VALUE])
    pred_w = model_w.predict(df[FEATURE_COLS_VALUE])
    pred_reg = model_ar.predict(df[FEATURE_COLS_VALUE])

    cal_p = calibrators.get('cal_p')
    cal_w = calibrators.get('cal_w')

    df['pred_proba_p'] = cal_p.predict(pred_p) if cal_p else pred_p
    df['pred_proba_w'] = cal_w.predict(pred_w) if cal_w else pred_w
    df['pred_margin_ar'] = pred_reg

    df['pred_rank_p'] = df.groupby('race_id')['pred_proba_p'].rank(ascending=False, method='min')
    df['pred_rank_w'] = df.groupby('race_id')['pred_proba_w'].rank(ascending=False, method='min')
    df['win_gap'] = (df['odds_rank'] - df['pred_rank_w']).clip(lower=0).astype(int)
    df['win_ev'] = df['pred_proba_w'] * df['odds']
    df['margin'] = pred_reg
    df['month'] = df['date'].str[:7]
    return df


def filter_bets(df, min_gap=5, max_margin=1.2):
    mask = (
        (df['pred_rank_w'] <= 3) &
        (df['win_gap'] >= min_gap) &
        (df['margin'] <= max_margin) &
        (df['odds'] > 0)
    )
    return df[mask].copy()


def calc_pnl_series(bets_df):
    """日付順にbet-by-betのP&Lを計算（均一100円）"""
    bets = bets_df.sort_values(['date', 'race_id', 'umaban']).copy()
    bets['pnl'] = bets['is_win'] * bets['odds'] * 100 - 100
    bets['cum_pnl'] = bets['pnl'].cumsum()
    return bets


def calc_monthly_pnl(bets_df):
    """月別P&L"""
    bets = bets_df.copy()
    bets['pnl'] = bets['is_win'] * bets['odds'] * 100 - 100
    monthly = bets.groupby('month').agg(
        count=('pnl', 'size'),
        pnl=('pnl', 'sum'),
        wins=('is_win', 'sum'),
    ).reset_index()
    monthly['cum_pnl'] = monthly['pnl'].cumsum()
    return monthly


def calc_max_drawdown(cum_pnl_series):
    """最大ドローダウン（円 & ピークからの%）"""
    peak = cum_pnl_series.cummax()
    drawdown = cum_pnl_series - peak
    max_dd = drawdown.min()
    peak_at_dd = peak[drawdown.idxmin()]
    dd_pct = (max_dd / peak_at_dd * 100) if peak_at_dd > 0 else 0
    return max_dd, dd_pct


def calc_losing_streaks(bets_df):
    """連敗分析"""
    bets = bets_df.sort_values(['date', 'race_id', 'umaban'])
    results = bets['is_win'].values

    streaks = []
    current_streak = 0
    current_loss = 0
    for won in results:
        if won == 0:
            current_streak += 1
            current_loss += 100
        else:
            if current_streak > 0:
                streaks.append((current_streak, current_loss))
            current_streak = 0
            current_loss = 0
    if current_streak > 0:
        streaks.append((current_streak, current_loss))

    if not streaks:
        return {
            'max_streak': 0, 'avg_streak': 0,
            'streak_10plus': 0, 'max_streak_loss': 0,
        }

    return {
        'max_streak': max(s[0] for s in streaks),
        'avg_streak': round(np.mean([s[0] for s in streaks]), 1),
        'streak_10plus': sum(1 for s in streaks if s[0] >= 10),
        'max_streak_loss': max(s[1] for s in streaks),
    }


def calc_consecutive_loss_months(monthly_df):
    """最長連続マイナス月"""
    max_consec = 0
    current = 0
    for _, row in monthly_df.iterrows():
        if row['pnl'] < 0:
            current += 1
            max_consec = max(max_consec, current)
        else:
            current = 0
    return max_consec


def main():
    t0 = time.time()
    print("=" * 60)
    print("  Cumulative P&L + Losing Streak Analysis")
    print("  2025/01 - 2026/02 | Model v5.5")
    print("=" * 60)

    print("\n[1] Loading data...")
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index) = load_data()

    print("\n[2] Building dataset...")
    df = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, 2025, 2026, use_db_odds=True,
        training_summary_index=training_summary_index,
    )
    df = df[(df['date'] >= '2025-01-01') & (df['date'] <= '2026-02-28')].copy()
    print(f"  {len(df):,} entries, {df['race_id'].nunique():,} races")

    print("\n[3] Loading models and predicting...")
    models = load_v55_models()
    df = predict_on_df(df, *models)

    # 3条件
    conditions = {
        'A: gap>=5 m<=1.2': filter_bets(df, 5, 1.2),
        'B: gap>=6 m<=1.2': filter_bets(df, 6, 1.2),
        'C: gap>=6 m<=0.8': filter_bets(df, 6, 0.8),
    }

    # --- サマリー ---
    print("\n" + "=" * 60)
    print("  Summary Table")
    print("=" * 60)

    summary_rows = []
    for label, bets in conditions.items():
        monthly = calc_monthly_pnl(bets)
        pnl_series = calc_pnl_series(bets)
        cum_pnl = pnl_series['cum_pnl']
        max_dd, dd_pct = calc_max_drawdown(cum_pnl)
        losing = calc_losing_streaks(bets)
        positive_months = int((monthly['pnl'] > 0).sum())
        consec_loss = calc_consecutive_loss_months(monthly)
        total_pnl = int((bets['is_win'] * bets['odds'] * 100).sum() - len(bets) * 100)

        row = {
            'label': label,
            'count': len(bets),
            'total_pnl': total_pnl,
            'max_dd': int(max_dd),
            'max_dd_pct': round(dd_pct, 1),
            'positive_months': positive_months,
            'total_months': len(monthly),
            'consec_loss_months': consec_loss,
            **losing,
        }
        summary_rows.append(row)

    # P&L指標
    print(f"\n{'指標':>24} | {'条件A':>14} | {'条件B':>14} | {'条件C':>14}")
    print("-" * 74)
    metrics = [
        ('総件数', 'count'),
        ('総P&L（円）', 'total_pnl'),
        ('Max DD（円）', 'max_dd'),
        ('Max DD（%）', 'max_dd_pct'),
        ('黒字月数/14', 'positive_months'),
        ('最長連続マイナス月', 'consec_loss_months'),
    ]
    for name, key in metrics:
        vals = []
        for r in summary_rows:
            if key == 'positive_months':
                vals.append(f"{r[key]}/14")
            elif key == 'max_dd_pct':
                vals.append(f"{r[key]}%")
            elif isinstance(r[key], int):
                vals.append(f"{r[key]:,}")
            else:
                vals.append(str(r[key]))
        print(f"{name:>24} | {vals[0]:>14} | {vals[1]:>14} | {vals[2]:>14}")

    # 連敗分析
    print(f"\n{'連敗指標':>24} | {'条件A':>14} | {'条件B':>14} | {'条件C':>14}")
    print("-" * 74)
    streak_metrics = [
        ('最大連敗数', 'max_streak'),
        ('平均連敗数', 'avg_streak'),
        ('10連敗以上回数', 'streak_10plus'),
        ('最長連敗中損失（円）', 'max_streak_loss'),
    ]
    for name, key in streak_metrics:
        vals = []
        for r in summary_rows:
            v = r[key]
            vals.append(f"{v:,}" if isinstance(v, int) else str(v))
        print(f"{name:>24} | {vals[0]:>14} | {vals[1]:>14} | {vals[2]:>14}")

    # 理論最大連敗
    print("\n[理論値比較]")
    for r in summary_rows:
        n = r['count']
        bets = conditions[r['label']]
        wins = int(bets['is_win'].sum())
        win_rate = wins / n if n > 0 else 0
        if 0 < win_rate < 1:
            expected_max = np.log(n) / np.log(1 / (1 - win_rate))
        else:
            expected_max = 0
        print(f"  {r['label']}: 勝率={win_rate*100:.1f}%, "
              f"理論最大連敗~{expected_max:.0f}, 実測={r['max_streak']}")

    # --- 月別詳細 ---
    print("\n" + "=" * 60)
    print("  Monthly Cumulative P&L")
    print("=" * 60)

    monthly_data = {}
    for label, bets in conditions.items():
        monthly_data[label] = calc_monthly_pnl(bets)

    months = sorted(df['month'].unique())

    print(f"\n{'月':>8}", end='')
    for label in conditions:
        print(f" | {label:>22}", end='')
    print()
    print("-" * 80)

    for m in months:
        print(f"{m:>8}", end='')
        for label in conditions:
            md = monthly_data[label]
            row = md[md['month'] == m]
            if len(row) > 0:
                pnl = int(row['pnl'].iloc[0])
                cum = int(row['cum_pnl'].iloc[0])
                sign = '+' if pnl >= 0 else ''
                print(f" | {sign}{pnl:>6} (cum:{cum:>7})", end='')
            else:
                print(f" | {'N/A':>22}", end='')
        print()

    # --- チャート生成 ---
    print("\n[Chart] Generating...")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10),
                                    gridspec_kw={'height_ratios': [3, 1]})

    colors = {
        'A: gap>=5 m<=1.2': '#2196F3',
        'B: gap>=6 m<=1.2': '#FF5722',
        'C: gap>=6 m<=0.8': '#4CAF50',
    }
    styles = {
        'A: gap>=5 m<=1.2': '-',
        'B: gap>=6 m<=1.2': '-',
        'C: gap>=6 m<=0.8': '--',
    }

    # 上: bet-by-bet累積P&L
    for label, bets in conditions.items():
        pnl = calc_pnl_series(bets)
        ax1.plot(range(len(pnl)), pnl['cum_pnl'].values,
                 color=colors[label], linestyle=styles[label],
                 linewidth=1.5, label=label, alpha=0.85)

    ax1.axhline(y=0, color='gray', linewidth=0.5)
    ax1.set_ylabel('Cumulative P&L (JPY)', fontsize=12)
    ax1.set_xlabel('Bet number', fontsize=11)
    ax1.legend(fontsize=11, loc='upper left')
    ax1.set_title('Cumulative P&L by Bet (2025/01 - 2026/02, 100 JPY/bet)', fontsize=13)
    ax1.grid(True, alpha=0.3)

    # 下: 月別P&Lバー
    x = np.arange(len(months))
    width = 0.25
    for i, (label, md) in enumerate(monthly_data.items()):
        pnls = []
        for m in months:
            row = md[md['month'] == m]
            pnls.append(int(row['pnl'].iloc[0]) if len(row) > 0 else 0)
        ax2.bar(x + i * width - width, pnls, width,
                label=label, color=colors[label], alpha=0.7)

    ax2.set_xticks(x)
    ax2.set_xticklabels([m[5:] for m in months], fontsize=9)
    ax2.set_xlabel('Month (2025-2026)', fontsize=11)
    ax2.set_ylabel('Monthly P&L (JPY)', fontsize=11)
    ax2.axhline(y=0, color='gray', linewidth=0.5)
    ax2.legend(fontsize=9, loc='upper left')
    ax2.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    chart_path = (Path(__file__).resolve().parent.parent /
                  "docs" / "ml-experiments" / "v5.8_cumulative_pnl.png")
    fig.savefig(str(chart_path), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Chart saved: {chart_path}")

    elapsed = time.time() - t0
    print(f"\n[Done] {elapsed:.1f}s")


if __name__ == '__main__':
    main()

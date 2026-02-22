"""月別実績分析スクリプト

v5.5 liveモデルを使って2025/01-2026/02の月別ROI・条件別成績・当たり馬分布を分析。
再学習なし — 保存済みモデル+calibratorを読み込んで予測するだけ。
"""

import sys
import os
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

# keiba-v2をパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config
from ml.experiment import (
    load_data,
    build_dataset,
    FEATURE_COLS_ALL,
    FEATURE_COLS_VALUE,
)
from ml.features.margin_target import add_margin_target_to_df


def load_race_json(race_id: str) -> dict:
    """experiment.pyと同じrace JSON読み込み"""
    from ml.experiment import load_race_json as _load
    return _load(race_id)


def load_v55_models():
    """v5.5モデルとcalibratorsを読み込み"""
    import lightgbm as lgb

    model_dir = config.ml_dir() / "versions" / "v5.5"
    print(f"[Model] Loading v5.5 from {model_dir}")

    model_a = lgb.Booster(model_file=str(model_dir / "model_a.txt"))
    model_b = lgb.Booster(model_file=str(model_dir / "model_b.txt"))
    model_w = lgb.Booster(model_file=str(model_dir / "model_w.txt"))
    model_wv = lgb.Booster(model_file=str(model_dir / "model_wv.txt"))
    model_reg_b = lgb.Booster(model_file=str(model_dir / "model_reg_b.txt"))

    with open(model_dir / "calibrators.pkl", 'rb') as f:
        calibrators = pickle.load(f)

    print(f"  Models: A, B, W, WV, Reg_B loaded")
    print(f"  Calibrators: {list(calibrators.keys())}")
    return model_a, model_b, model_w, model_wv, model_reg_b, calibrators


def predict_on_df(df, model_a, model_b, model_w, model_wv, model_reg_b, calibrators):
    """DataFrameにモデル予測を追加"""
    # 分類モデル予測
    pred_a = model_a.predict(df[FEATURE_COLS_ALL])
    pred_b = model_b.predict(df[FEATURE_COLS_VALUE])
    pred_w = model_w.predict(df[FEATURE_COLS_ALL])
    pred_wv = model_wv.predict(df[FEATURE_COLS_VALUE])
    pred_reg = model_reg_b.predict(df[FEATURE_COLS_VALUE])

    # calibrated
    cal_a = calibrators.get('cal_a')
    cal_b = calibrators.get('cal_b')
    cal_w = calibrators.get('cal_w')
    cal_wv = calibrators.get('cal_wv')

    pred_a_cal = cal_a.predict(pred_a) if cal_a else pred_a
    pred_b_cal = cal_b.predict(pred_b) if cal_b else pred_b
    pred_w_cal = cal_w.predict(pred_w) if cal_w else pred_w
    pred_wv_cal = cal_wv.predict(pred_wv) if cal_wv else pred_wv

    df['pred_proba_a'] = pred_a_cal
    df['pred_proba_v'] = pred_b_cal
    df['pred_proba_w'] = pred_w_cal
    df['pred_proba_wv'] = pred_wv_cal
    df['pred_margin_b'] = pred_reg

    # ランク
    df['pred_rank_a'] = df.groupby('race_id')['pred_proba_a'].rank(ascending=False, method='min')
    df['pred_rank_v'] = df.groupby('race_id')['pred_proba_v'].rank(ascending=False, method='min')
    df['pred_rank_w'] = df.groupby('race_id')['pred_proba_w'].rank(ascending=False, method='min')
    df['pred_rank_wv'] = df.groupby('race_id')['pred_proba_wv'].rank(ascending=False, method='min')

    # VB gap (win_gap = odds_rank - pred_rank_wv)
    df['win_gap'] = (df['odds_rank'] - df['pred_rank_wv']).clip(lower=0).astype(int)
    df['gap'] = (df['odds_rank'] - df['pred_rank_v']).clip(lower=0).astype(int)

    # EV
    df['win_ev'] = pred_wv_cal * df['odds']

    # margin (predicted)
    df['margin'] = pred_reg

    # 月カラム
    df['month'] = df['date'].str[:7]  # YYYY-MM

    return df


def bootstrap_roi_ci(bets_df, n_bootstrap=2000, ci_level=0.95):
    """レース単位Bootstrap CIでWin ROIを計算

    Args:
        bets_df: bet対象馬のDataFrame (columns: race_id, odds, is_win)

    Returns:
        dict: {count, roi, ci_low, ci_high, ci_width, wins, win_rate}
    """
    if len(bets_df) == 0:
        return {'count': 0, 'roi': 0, 'ci_low': 0, 'ci_high': 0, 'ci_width': 0,
                'wins': 0, 'win_rate': 0}

    # 実績
    n = len(bets_df)
    cost = n * 100
    returns = (bets_df['is_win'] * bets_df['odds'] * 100).sum()
    roi = returns / cost * 100
    wins = int(bets_df['is_win'].sum())
    win_rate = wins / n * 100

    # レース単位リサンプリング
    rng = np.random.default_rng(42)
    alpha = (1 - ci_level) / 2

    race_groups = {}
    for race_id, group in bets_df.groupby('race_id'):
        race_groups[race_id] = group

    race_ids = list(race_groups.keys())
    n_races = len(race_ids)

    bootstrap_rois = []
    for _ in range(n_bootstrap):
        sampled = rng.choice(race_ids, size=n_races, replace=True)
        total_cost = 0
        total_return = 0
        for rid in sampled:
            g = race_groups[rid]
            total_cost += len(g) * 100
            total_return += (g['is_win'] * g['odds'] * 100).sum()
        if total_cost > 0:
            bootstrap_rois.append(total_return / total_cost * 100)

    bootstrap_rois = np.array(bootstrap_rois)
    ci_low = float(np.percentile(bootstrap_rois, alpha * 100))
    ci_high = float(np.percentile(bootstrap_rois, (1 - alpha) * 100))

    return {
        'count': n,
        'roi': round(roi, 1),
        'ci_low': round(ci_low, 1),
        'ci_high': round(ci_high, 1),
        'ci_width': round(ci_high - ci_low, 1),
        'wins': wins,
        'win_rate': round(win_rate, 1),
    }


def filter_win_only(df, min_gap=5, max_margin=1.2):
    """win_only条件でフィルタ: win_gap >= min_gap, margin <= max_margin, pred_rank_wv <= 3"""
    mask = (
        (df['pred_rank_wv'] <= 3) &
        (df['win_gap'] >= min_gap) &
        (df['margin'] <= max_margin) &
        (df['odds'] > 0)
    )
    return df[mask].copy()


def filter_selective(df, min_gap=6, min_ev=1.2, max_margin=0.8):
    """selective条件: win_gap >= min_gap, win_ev >= min_ev, margin <= max_margin"""
    mask = (
        (df['pred_rank_wv'] <= 3) &
        (df['win_gap'] >= min_gap) &
        (df['win_ev'] >= min_ev) &
        (df['margin'] <= max_margin) &
        (df['odds'] > 0)
    )
    return df[mask].copy()


def calc_roi(bets_df):
    """シンプルなROI計算"""
    if len(bets_df) == 0:
        return 0.0
    cost = len(bets_df) * 100
    returns = (bets_df['is_win'] * bets_df['odds'] * 100).sum()
    return returns / cost * 100


def main():
    t0 = time.time()
    print("=" * 60)
    print("  Monthly Analysis: 2025/01 - 2026/02")
    print("  Model: v5.5 (live)")
    print("=" * 60)

    # --- データ読み込み ---
    print("\n[1] Loading data...")
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index) = load_data()

    # 2025-2026のデータセット構築
    print("\n[2] Building dataset for 2025-2026...")
    df = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, 2025, 2026, use_db_odds=True,
        training_summary_index=training_summary_index,
    )
    print(f"  Dataset: {len(df):,} entries from {df['race_id'].nunique():,} races")

    # 2025/01 - 2026/02にフィルタ
    df = df[df['date'] >= '2025-01-01'].copy()
    df = df[df['date'] <= '2026-02-28'].copy()
    print(f"  After date filter: {len(df):,} entries from {df['race_id'].nunique():,} races")

    # --- モデル読み込み & 予測 ---
    print("\n[3] Loading v5.5 models and predicting...")
    model_a, model_b, model_w, model_wv, model_reg_b, calibrators = load_v55_models()
    df = predict_on_df(df, model_a, model_b, model_w, model_wv, model_reg_b, calibrators)

    # === Step 1: 月別ROI推移 ===
    print("\n" + "=" * 60)
    print("  Step 1: 月別ROI推移")
    print("=" * 60)

    months = sorted(df['month'].unique())
    print(f"\n{'月':>8} | {'win_only件数':>12} | {'win_only ROI':>12} | {'selective件数':>13} | {'selective ROI':>13}")
    print("-" * 70)

    monthly_data = []
    for m in months:
        df_m = df[df['month'] == m]
        wo = filter_win_only(df_m)
        sel = filter_selective(df_m)
        wo_roi = calc_roi(wo)
        sel_roi = calc_roi(sel)
        wo_wins = int(wo['is_win'].sum()) if len(wo) > 0 else 0
        sel_wins = int(sel['is_win'].sum()) if len(sel) > 0 else 0
        print(f"{m:>8} | {len(wo):>6} ({wo_wins}勝) | {wo_roi:>10.1f}% | {len(sel):>7} ({sel_wins}勝) | {sel_roi:>11.1f}%")
        monthly_data.append({
            'month': m,
            'wo_count': len(wo), 'wo_wins': wo_wins, 'wo_roi': round(wo_roi, 1),
            'sel_count': len(sel), 'sel_wins': sel_wins, 'sel_roi': round(sel_roi, 1),
        })

    # 合計
    wo_all = filter_win_only(df)
    sel_all = filter_selective(df)
    wo_roi_all = calc_roi(wo_all)
    sel_roi_all = calc_roi(sel_all)
    wo_wins_all = int(wo_all['is_win'].sum())
    sel_wins_all = int(sel_all['is_win'].sum())
    print("-" * 70)
    print(f"{'合計':>8} | {len(wo_all):>6} ({wo_wins_all}勝) | {wo_roi_all:>10.1f}% | {len(sel_all):>7} ({sel_wins_all}勝) | {sel_roi_all:>11.1f}%")

    # === Step 2: 条件別Bootstrap CI ===
    print("\n" + "=" * 60)
    print("  Step 2: 条件別の通年成績 (Bootstrap CI)")
    print("=" * 60)

    n_months = len(months)

    conditions = [
        ('gap>=5 m<=1.2 (win_only)', lambda d: filter_win_only(d, 5, 1.2)),
        ('gap>=5 m<=0.8', lambda d: filter_win_only(d, 5, 0.8)),
        ('gap>=6 m<=1.2', lambda d: filter_win_only(d, 6, 1.2)),
        ('gap>=6 m<=0.8', lambda d: filter_win_only(d, 6, 0.8)),
        ('gap>=6+EV>=1.2 m<=0.8', lambda d: filter_selective(d, 6, 1.2, 0.8)),
        ('gap>=7 m<=0.8', lambda d: filter_win_only(d, 7, 0.8)),
    ]

    print(f"\n{'条件':>25} | {'件数':>5} | {'月平均':>6} | {'ROI':>7} | {'CI(95%)':>20} | {'CI幅':>6}")
    print("-" * 80)

    ci_results = []
    for label, filt in conditions:
        bets = filt(df)
        ci = bootstrap_roi_ci(bets)
        monthly_avg = round(ci['count'] / n_months, 1)
        ci_str = f"[{ci['ci_low']:.1f}% - {ci['ci_high']:.1f}%]"
        print(f"{label:>25} | {ci['count']:>5} | {monthly_avg:>6.1f} | {ci['roi']:>6.1f}% | {ci_str:>20} | {ci['ci_width']:>5.1f}%")
        ci_results.append({
            'label': label,
            **ci,
            'monthly_avg': monthly_avg,
        })

    # === Step 3: 当たり馬の条件分布 ===
    print("\n" + "=" * 60)
    print("  Step 3: 当たり馬の条件分布")
    print("=" * 60)

    # win_only条件(gap>=5, m<=1.2)の中から的中馬を抽出
    wo_all_bets = filter_win_only(df)
    winners = wo_all_bets[wo_all_bets['is_win'] == 1]
    total_wins = len(winners)

    print(f"\nwin_only全体: {len(wo_all_bets)}件中 {total_wins}勝\n")

    # gap帯別
    print("--- gap帯別 (win_gap) ---")
    print(f"{'gap帯':>10} | {'的中数':>6} | {'構成比':>7} | {'該当件数':>8} | {'的中率':>6}")
    print("-" * 50)
    for gap_min, gap_max, label in [(5, 5, '5'), (6, 6, '6'), (7, 8, '7-8'), (9, 99, '9+')]:
        mask = (winners['win_gap'] >= gap_min) & (winners['win_gap'] <= gap_max)
        wins = mask.sum()
        total_mask = (wo_all_bets['win_gap'] >= gap_min) & (wo_all_bets['win_gap'] <= gap_max)
        total_in_band = total_mask.sum()
        pct = wins / total_wins * 100 if total_wins > 0 else 0
        hit_rate = wins / total_in_band * 100 if total_in_band > 0 else 0
        print(f"{label:>10} | {wins:>6} | {pct:>6.1f}% | {total_in_band:>8} | {hit_rate:>5.1f}%")

    # margin帯別
    print("\n--- margin帯別 (predicted_margin) ---")
    print(f"{'margin帯':>10} | {'的中数':>6} | {'構成比':>7} | {'該当件数':>8} | {'的中率':>6}")
    print("-" * 50)
    for m_min, m_max, label in [(None, 0.8, '<=0.8'), (0.8, 1.0, '0.8-1.0'), (1.0, 1.2, '1.0-1.2')]:
        if m_min is None:
            w_mask = winners['margin'] <= m_max
            t_mask = wo_all_bets['margin'] <= m_max
        else:
            w_mask = (winners['margin'] > m_min) & (winners['margin'] <= m_max)
            t_mask = (wo_all_bets['margin'] > m_min) & (wo_all_bets['margin'] <= m_max)
        wins = w_mask.sum()
        total_in_band = t_mask.sum()
        pct = wins / total_wins * 100 if total_wins > 0 else 0
        hit_rate = wins / total_in_band * 100 if total_in_band > 0 else 0
        print(f"{label:>10} | {wins:>6} | {pct:>6.1f}% | {total_in_band:>8} | {hit_rate:>5.1f}%")

    # EV帯別
    print("\n--- EV帯別 (win_ev) ---")
    print(f"{'EV帯':>10} | {'的中数':>6} | {'構成比':>7} | {'該当件数':>8} | {'的中率':>6}")
    print("-" * 50)
    for e_min, e_max, label in [(None, 1.0, '<1.0'), (1.0, 1.2, '1.0-1.2'),
                                 (1.2, 1.5, '1.2-1.5'), (1.5, None, '>=1.5')]:
        if e_min is None:
            w_mask = winners['win_ev'] < e_max
            t_mask = wo_all_bets['win_ev'] < e_max
        elif e_max is None:
            w_mask = winners['win_ev'] >= e_min
            t_mask = wo_all_bets['win_ev'] >= e_min
        else:
            w_mask = (winners['win_ev'] >= e_min) & (winners['win_ev'] < e_max)
            t_mask = (wo_all_bets['win_ev'] >= e_min) & (wo_all_bets['win_ev'] < e_max)
        wins = w_mask.sum()
        total_in_band = t_mask.sum()
        pct = wins / total_wins * 100 if total_wins > 0 else 0
        hit_rate = wins / total_in_band * 100 if total_in_band > 0 else 0
        print(f"{label:>10} | {wins:>6} | {pct:>6.1f}% | {total_in_band:>8} | {hit_rate:>5.1f}%")

    # gap × margin クロス集計
    print("\n--- gap × margin クロス集計 (件数 / 的中数 / ROI) ---")
    print(f"{'':>10} | {'m<=0.8':>18} | {'0.8<m<=1.0':>18} | {'1.0<m<=1.2':>18}")
    print("-" * 70)
    for gap_min, gap_max, label in [(5, 5, 'gap=5'), (6, 6, 'gap=6'), (7, 8, 'gap=7-8'), (9, 99, 'gap=9+')]:
        cells = []
        for m_min, m_max in [(None, 0.8), (0.8, 1.0), (1.0, 1.2)]:
            gap_mask = (wo_all_bets['win_gap'] >= gap_min) & (wo_all_bets['win_gap'] <= gap_max)
            if m_min is None:
                m_mask = wo_all_bets['margin'] <= m_max
            else:
                m_mask = (wo_all_bets['margin'] > m_min) & (wo_all_bets['margin'] <= m_max)
            cell = wo_all_bets[gap_mask & m_mask]
            n = len(cell)
            w = int(cell['is_win'].sum())
            roi = calc_roi(cell)
            cells.append(f"{n:>3}/{w}勝/{roi:>5.0f}%")
        print(f"{label:>10} | {cells[0]:>18} | {cells[1]:>18} | {cells[2]:>18}")

    # 的中馬の詳細リスト
    print("\n--- 的中馬リスト (Top 50) ---")
    print(f"{'日付':>12} | {'馬名':>14} | {'オッズ':>6} | {'win_gap':>7} | {'margin':>7} | {'EV':>5}")
    print("-" * 65)
    winners_sorted = winners.sort_values('date')
    for _, row in winners_sorted.head(50).iterrows():
        print(f"{row['date']:>12} | {row['horse_name']:>14} | {row['odds']:>6.1f} | "
              f"{row['win_gap']:>7} | {row['margin']:>7.2f} | {row['win_ev']:>5.2f}")

    elapsed = time.time() - t0
    print(f"\n[Done] Elapsed: {elapsed:.1f}s")

    # 結果をJSONで保存
    result = {
        'period': '2025-01 to 2026-02',
        'model': 'v5.5',
        'monthly': monthly_data,
        'conditions': ci_results,
        'total_entries': len(df),
        'total_races': int(df['race_id'].nunique()),
        'n_months': n_months,
    }
    out_path = Path(__file__).resolve().parent.parent / "docs" / "ml-experiments" / "monthly_analysis_result.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[Output] {out_path}")


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
バックテストスクリプト

訓練済みモデルを使って過去データでシミュレーションを行い、回収率を計算します。
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def load_model_and_info(model_dir: Path, model_name: str = "lightgbm_model"):
    """
    モデルとモデル情報を読み込む

    Args:
        model_dir: モデルディレクトリ
        model_name: モデル名

    Returns:
        model, model_info
    """
    model_path = model_dir / f"{model_name}.pkl"
    info_path = model_dir / f"{model_name}_info.json"

    print(f"モデル読み込み中: {model_path}")
    model = joblib.load(model_path)

    print(f"モデル情報読み込み中: {info_path}")
    with open(info_path, "r", encoding="utf-8") as f:
        model_info = json.load(f)

    return model, model_info


def predict_with_model(
    model,
    X: pd.DataFrame,
    threshold: float = 0.5
) -> tuple[np.ndarray, np.ndarray]:
    """
    モデルで予測

    Args:
        model: 訓練済みモデル
        X: 特徴量DataFrame
        threshold: しきい値

    Returns:
        pred_proba, pred_class
    """
    # LightGBMの場合
    if hasattr(model, 'predict'):
        pred_proba = model.predict(X)
    else:
        pred_proba = model.predict_proba(X)[:, 1]

    pred_class = (pred_proba >= threshold).astype(int)

    return pred_proba, pred_class


def simulate_betting(
    df: pd.DataFrame,
    pred_proba: np.ndarray,
    threshold: float = 0.6,
    bet_amount: int = 100
) -> pd.DataFrame:
    """
    賭けをシミュレーション

    Args:
        df: レース結果DataFrame（オッズ情報を含む）
        pred_proba: 予測確率
        threshold: 購入しきい値
        bet_amount: 1点あたりの賭け金（円）

    Returns:
        賭け結果DataFrame
    """
    print(f"賭けシミュレーション（しきい値={threshold}, 賭け金={bet_amount}円/点）...")

    bet_df = df.copy()
    bet_df['pred_proba'] = pred_proba

    # しきい値以上を購入
    bet_df = bet_df[bet_df['pred_proba'] >= threshold].copy()

    if len(bet_df) == 0:
        print("⚠️ 購入対象が0件です。しきい値を下げてください。")
        return bet_df

    print(f"購入点数: {len(bet_df)}点")

    # 的中判定
    bet_df['is_hit'] = (bet_df['target'] == 1).astype(int)

    # 払戻計算（単勝オッズがある場合）
    if 'win_odds' in bet_df.columns:
        bet_df['return'] = bet_df.apply(
            lambda row: row['win_odds'] * bet_amount if row['is_hit'] else 0,
            axis=1
        )
    else:
        # オッズ情報がない場合は仮定（平均5倍）
        print("⚠️ オッズ情報がないため、的中時は仮に5倍として計算します。")
        bet_df['return'] = bet_df['is_hit'] * bet_amount * 5

    bet_df['bet_amount'] = bet_amount

    return bet_df


def calculate_metrics(bet_df: pd.DataFrame) -> dict:
    """
    賭け結果の指標を計算

    Args:
        bet_df: 賭け結果DataFrame

    Returns:
        指標辞書
    """
    total_bets = len(bet_df)
    total_bet_amount = bet_df['bet_amount'].sum()
    total_return = bet_df['return'].sum()
    total_hits = bet_df['is_hit'].sum()

    hit_rate = total_hits / total_bets if total_bets > 0 else 0
    recovery_rate = (total_return / total_bet_amount * 100) if total_bet_amount > 0 else 0
    profit = total_return - total_bet_amount

    metrics = {
        'total_bets': total_bets,
        'total_bet_amount': total_bet_amount,
        'total_return': total_return,
        'total_hits': total_hits,
        'hit_rate': hit_rate,
        'recovery_rate': recovery_rate,
        'profit': profit
    }

    return metrics


def print_backtest_summary(metrics: dict):
    """
    バックテスト結果を表示

    Args:
        metrics: 指標辞書
    """
    print("\n=== バックテスト結果サマリー ===")
    print(f"購入点数: {metrics['total_bets']:,}点")
    print(f"投資額: {metrics['total_bet_amount']:,}円")
    print(f"払戻額: {metrics['total_return']:,.0f}円")
    print(f"的中数: {metrics['total_hits']:,}回")
    print(f"的中率: {metrics['hit_rate']:.1%}")
    print(f"回収率: {metrics['recovery_rate']:.1f}%")
    print(f"収支: {metrics['profit']:+,.0f}円")

    if metrics['recovery_rate'] >= 100:
        print("\n✅ プラス収支達成!")
    else:
        print("\n❌ マイナス収支")


def analyze_by_month(bet_df: pd.DataFrame):
    """
    月次収支を分析

    Args:
        bet_df: 賭け結果DataFrame
    """
    print("\n=== 月次収支分析 ===")

    bet_df['race_month'] = pd.to_datetime(bet_df['race_date'], format='%Y%m%d').dt.to_period('M')

    monthly_stats = bet_df.groupby('race_month').apply(
        lambda g: pd.Series({
            'bet_count': len(g),
            'hit_count': g['is_hit'].sum(),
            'total_return': g['return'].sum(),
            'total_bet': g['bet_amount'].sum()
        })
    ).reset_index()

    monthly_stats['hit_rate'] = (monthly_stats['hit_count'] / monthly_stats['bet_count'] * 100).fillna(0)
    monthly_stats['recovery_rate'] = (monthly_stats['total_return'] / monthly_stats['total_bet'] * 100).fillna(0)
    monthly_stats['profit'] = monthly_stats['total_return'] - monthly_stats['total_bet']

    print(monthly_stats.to_string(index=False))

    # 可視化
    visualize_monthly_stats(monthly_stats)

    return monthly_stats


def visualize_monthly_stats(monthly_stats: pd.DataFrame):
    """
    月次統計を可視化

    Args:
        monthly_stats: 月次統計DataFrame
    """
    # 日本語フォント設定
    plt.rcParams['font.sans-serif'] = ['MS Gothic']
    plt.rcParams['axes.unicode_minus'] = False

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # 1. 回収率の推移
    ax1 = axes[0, 0]
    ax1.bar(range(len(monthly_stats)), monthly_stats['recovery_rate'], alpha=0.7)
    ax1.axhline(y=100, color='r', linestyle='--', label='損益分岐点')
    ax1.set_xlabel('月')
    ax1.set_ylabel('回収率 (%)')
    ax1.set_title('月次回収率の推移')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. 的中率の推移
    ax2 = axes[0, 1]
    ax2.plot(range(len(monthly_stats)), monthly_stats['hit_rate'], marker='o', linestyle='-')
    ax2.set_xlabel('月')
    ax2.set_ylabel('的中率 (%)')
    ax2.set_title('月次的中率の推移')
    ax2.grid(True, alpha=0.3)

    # 3. 収支の推移
    ax3 = axes[1, 0]
    colors = ['red' if p < 0 else 'blue' for p in monthly_stats['profit']]
    ax3.bar(range(len(monthly_stats)), monthly_stats['profit'], color=colors, alpha=0.7)
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax3.set_xlabel('月')
    ax3.set_ylabel('収支 (円)')
    ax3.set_title('月次収支の推移')
    ax3.grid(True, alpha=0.3)

    # 4. 買い目数と的中数
    ax4 = axes[1, 1]
    x = range(len(monthly_stats))
    width = 0.35
    ax4.bar([i - width/2 for i in x], monthly_stats['bet_count'], width, alpha=0.7, label='買い目数')
    ax4.bar([i + width/2 for i in x], monthly_stats['hit_count'], width, alpha=0.7, label='的中数')
    ax4.set_xlabel('月')
    ax4.set_ylabel('件数')
    ax4.set_title('月次買い目数と的中数')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


def threshold_optimization(df: pd.DataFrame, pred_proba: np.ndarray):
    """
    最適なしきい値を探索

    Args:
        df: レース結果DataFrame
        pred_proba: 予測確率
    """
    print("\n=== しきい値最適化 ===")

    thresholds = np.arange(0.3, 0.9, 0.05)
    results = []

    for threshold in thresholds:
        bet_df = simulate_betting(df, pred_proba, threshold=threshold, bet_amount=100)

        if len(bet_df) > 0:
            metrics = calculate_metrics(bet_df)
            results.append({
                'threshold': threshold,
                'bets': metrics['total_bets'],
                'hit_rate': metrics['hit_rate'] * 100,
                'recovery_rate': metrics['recovery_rate']
            })

    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))

    # 最適しきい値（回収率が最大）
    best_row = results_df.loc[results_df['recovery_rate'].idxmax()]
    print(f"\n🎯 最適しきい値: {best_row['threshold']:.2f}")
    print(f"   回収率: {best_row['recovery_rate']:.1f}%")
    print(f"   的中率: {best_row['hit_rate']:.1f}%")
    print(f"   買い目数: {best_row['bets']:.0f}点")

    return results_df


def main():
    """メイン処理"""
    print("=== バックテスト開始 ===\n")

    # パス設定
    data_dir = project_root / "data"
    model_dir = project_root / "ml" / "models"

    data_path = data_dir / "training" / "race_results_featured.csv"

    # データ読み込み
    print(f"データ読み込み中: {data_path}")
    df = pd.read_csv(data_path)

    # テストデータのみ使用（2025年以降）
    test_df = df[df['race_date'] > "2024-12-31"].copy()
    print(f"テストデータ: {len(test_df)}件")

    # モデル読み込み
    model, model_info = load_model_and_info(model_dir, model_name="lightgbm_model")

    feature_cols = model_info['features']
    X_test = test_df[feature_cols].fillna(0)

    # 予測
    print("\n予測実行中...")
    pred_proba, pred_class = predict_with_model(model, X_test, threshold=0.5)

    # バックテスト（デフォルトしきい値=0.6）
    bet_df = simulate_betting(test_df, pred_proba, threshold=0.6, bet_amount=100)

    if len(bet_df) > 0:
        # 結果集計
        metrics = calculate_metrics(bet_df)
        print_backtest_summary(metrics)

        # 月次分析
        monthly_stats = analyze_by_month(bet_df)

        # しきい値最適化
        threshold_results = threshold_optimization(test_df, pred_proba)

        # 結果保存
        output_dir = project_root / "ml" / "data" / "backtest"
        output_dir.mkdir(parents=True, exist_ok=True)

        bet_df.to_csv(output_dir / "backtest_results.csv", index=False, encoding="utf-8-sig")
        monthly_stats.to_csv(output_dir / "monthly_stats.csv", index=False, encoding="utf-8-sig")
        threshold_results.to_csv(output_dir / "threshold_optimization.csv", index=False, encoding="utf-8-sig")

        print(f"\n✓ 結果保存: {output_dir}")

    print("\n=== バックテスト完了 ===")


if __name__ == "__main__":
    main()

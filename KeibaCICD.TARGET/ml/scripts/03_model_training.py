# -*- coding: utf-8 -*-
"""
モデル訓練スクリプト

ロジスティック回帰とLightGBMで予測モデルを訓練します。
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
from datetime import datetime

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report
)
import lightgbm as lgb
import joblib

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def load_data(data_path: Path) -> pd.DataFrame:
    """データを読み込む"""
    print(f"データ読み込み中: {data_path}")
    df = pd.read_csv(data_path)
    print(f"読み込み完了: {len(df)}件")
    return df


def split_data_by_date(
    df: pd.DataFrame,
    split_date: str = "2024-12-31"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    時系列でデータを分割

    Args:
        df: DataFrame
        split_date: 分割日（この日までが学習データ）

    Returns:
        train_df, test_df
    """
    print(f"データを時系列分割中（基準日: {split_date}）...")

    df = df.sort_values('race_date')

    train_df = df[df['race_date'] <= split_date].copy()
    test_df = df[df['race_date'] > split_date].copy()

    print(f"学習データ: {len(train_df)}件 ({train_df['race_date'].min()} ～ {train_df['race_date'].max()})")
    print(f"テストデータ: {len(test_df)}件 ({test_df['race_date'].min()} ～ {test_df['race_date'].max()})")

    return train_df, test_df


def prepare_features(
    df: pd.DataFrame,
    feature_cols: list
) -> tuple[pd.DataFrame, pd.Series]:
    """
    特徴量と目的変数を分離

    Args:
        df: DataFrame
        feature_cols: 特徴量カラムリスト

    Returns:
        X (特徴量), y (目的変数)
    """
    X = df[feature_cols].fillna(0)
    y = df['target']

    return X, y


def train_logistic_regression(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series
) -> dict:
    """
    ロジスティック回帰モデルを訓練

    Returns:
        結果辞書（モデル、評価指標）
    """
    print("\n=== ロジスティック回帰 訓練開始 ===")

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train, y_train)

    print("✓ 訓練完了")

    # 予測
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    # 評価
    metrics = {
        'model_name': 'LogisticRegression',
        'accuracy': accuracy_score(y_test, y_pred),
        'auc': roc_auc_score(y_test, y_pred_proba),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1': f1_score(y_test, y_pred)
    }

    print(f"正解率: {metrics['accuracy']:.4f}")
    print(f"AUC: {metrics['auc']:.4f}")
    print(f"適合率: {metrics['precision']:.4f}")
    print(f"再現率: {metrics['recall']:.4f}")
    print(f"F1スコア: {metrics['f1']:.4f}")

    # 詳細レポート
    print("\n分類レポート:")
    print(classification_report(y_test, y_pred, target_names=['圏外', '圏内']))

    return {
        'model': model,
        'metrics': metrics,
        'predictions': y_pred_proba
    }


def train_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    params: dict = None
) -> dict:
    """
    LightGBMモデルを訓練

    Args:
        X_train, y_train: 学習データ
        X_test, y_test: テストデータ
        params: LightGBMパラメータ

    Returns:
        結果辞書（モデル、評価指標）
    """
    print("\n=== LightGBM 訓練開始 ===")

    # デフォルトパラメータ
    if params is None:
        params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'min_child_samples': 20,
            'verbose': -1
        }

    # データセット作成
    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    # 訓練
    gbm = lgb.train(
        params,
        train_data,
        num_boost_round=1000,
        valid_sets=[test_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=100)
        ]
    )

    print("✓ 訓練完了")

    # 予測
    y_pred_proba = gbm.predict(X_test, num_iteration=gbm.best_iteration)
    y_pred = (y_pred_proba > 0.5).astype(int)

    # 評価
    metrics = {
        'model_name': 'LightGBM',
        'accuracy': accuracy_score(y_test, y_pred),
        'auc': roc_auc_score(y_test, y_pred_proba),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1': f1_score(y_test, y_pred),
        'best_iteration': gbm.best_iteration
    }

    print(f"正解率: {metrics['accuracy']:.4f}")
    print(f"AUC: {metrics['auc']:.4f}")
    print(f"適合率: {metrics['precision']:.4f}")
    print(f"再現率: {metrics['recall']:.4f}")
    print(f"F1スコア: {metrics['f1']:.4f}")
    print(f"最適イテレーション: {metrics['best_iteration']}")

    # 詳細レポート
    print("\n分類レポート:")
    print(classification_report(y_test, y_pred, target_names=['圏外', '圏内']))

    # 特徴量重要度
    print("\n特徴量重要度 Top 10:")
    importance = pd.DataFrame({
        'feature': X_train.columns,
        'importance': gbm.feature_importance(importance_type='gain')
    }).sort_values('importance', ascending=False)

    print(importance.head(10).to_string(index=False))

    return {
        'model': gbm,
        'metrics': metrics,
        'predictions': y_pred_proba,
        'feature_importance': importance
    }


def save_model(
    model,
    metrics: dict,
    feature_cols: list,
    model_dir: Path,
    model_name: str = "lightgbm_model"
):
    """
    モデルと関連情報を保存

    Args:
        model: 訓練済みモデル
        metrics: 評価指標
        feature_cols: 特徴量カラムリスト
        model_dir: 保存先ディレクトリ
        model_name: モデル名
    """
    model_dir.mkdir(parents=True, exist_ok=True)

    # モデル保存
    model_path = model_dir / f"{model_name}.pkl"
    joblib.dump(model, model_path)
    print(f"✓ モデル保存: {model_path}")

    # モデル情報保存
    info = {
        'model_name': metrics.get('model_name'),
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'features': feature_cols,
        'metrics': metrics,
        'threshold': 0.5  # デフォルトしきい値
    }

    info_path = model_dir / f"{model_name}_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"✓ モデル情報保存: {info_path}")


def compare_models(results: dict):
    """
    複数モデルの性能を比較

    Args:
        results: {model_name: result_dict}
    """
    print("\n=== モデル性能比較 ===\n")

    comparison = []
    for name, result in results.items():
        metrics = result['metrics']
        comparison.append({
            'モデル': metrics['model_name'],
            '正解率': f"{metrics['accuracy']:.4f}",
            'AUC': f"{metrics['auc']:.4f}",
            '適合率': f"{metrics['precision']:.4f}",
            '再現率': f"{metrics['recall']:.4f}",
            'F1': f"{metrics['f1']:.4f}"
        })

    comparison_df = pd.DataFrame(comparison)
    print(comparison_df.to_string(index=False))

    # 最良モデルを判定（AUCで比較）
    best_model = max(results.items(), key=lambda x: x[1]['metrics']['auc'])
    print(f"\n🏆 最良モデル: {best_model[1]['metrics']['model_name']} (AUC={best_model[1]['metrics']['auc']:.4f})")


def main():
    """メイン処理"""
    print("=== モデル訓練開始 ===\n")

    # パス設定
    data_dir = project_root / "data"
    model_dir = project_root / "ml" / "models"

    data_path = data_dir / "training" / "race_results_featured.csv"
    feature_cols_path = data_dir / "training" / "feature_columns.txt"

    # 特徴量リスト読み込み
    with open(feature_cols_path, "r", encoding="utf-8") as f:
        feature_cols = [line.strip() for line in f.readlines()]

    print(f"使用する特徴量: {len(feature_cols)}個\n")

    # データ読み込み
    df = load_data(data_path)

    # データ分割
    train_df, test_df = split_data_by_date(df, split_date="2024-12-31")

    # 特徴量と目的変数を分離
    X_train, y_train = prepare_features(train_df, feature_cols)
    X_test, y_test = prepare_features(test_df, feature_cols)

    # モデル訓練
    results = {}

    # 1. ロジスティック回帰
    lr_result = train_logistic_regression(X_train, y_train, X_test, y_test)
    results['LogisticRegression'] = lr_result

    # 2. LightGBM
    lgbm_result = train_lightgbm(X_train, y_train, X_test, y_test)
    results['LightGBM'] = lgbm_result

    # モデル性能比較
    compare_models(results)

    # 最良モデルを保存（AUCが最も高いモデル）
    best_model_name = max(results.items(), key=lambda x: x[1]['metrics']['auc'])[0]
    best_result = results[best_model_name]

    save_model(
        best_result['model'],
        best_result['metrics'],
        feature_cols,
        model_dir,
        model_name=f"best_model_{best_model_name.lower()}"
    )

    # LightGBMは常に保存（実運用想定）
    if 'LightGBM' in results:
        save_model(
            results['LightGBM']['model'],
            results['LightGBM']['metrics'],
            feature_cols,
            model_dir,
            model_name="lightgbm_model"
        )

        # 特徴量重要度も保存
        importance_path = model_dir / "feature_importance.csv"
        results['LightGBM']['feature_importance'].to_csv(
            importance_path, index=False, encoding="utf-8-sig"
        )
        print(f"✓ 特徴量重要度保存: {importance_path}")

    print("\n=== モデル訓練完了 ===")


if __name__ == "__main__":
    main()

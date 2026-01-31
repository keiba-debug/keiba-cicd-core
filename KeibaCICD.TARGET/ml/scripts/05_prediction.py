# -*- coding: utf-8 -*-
"""
予測スクリプト

訓練済みモデルを使って新しいレースの予測を行います。
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json
import joblib
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from common.jravan import analyze_horse_training, get_horse_info


def load_model_and_info(model_dir: Path, model_name: str = "lightgbm_model"):
    """モデルとモデル情報を読み込む"""
    model_path = model_dir / f"{model_name}.pkl"
    info_path = model_dir / f"{model_name}_info.json"
    scaler_path = model_dir / "scaler.pkl"

    print(f"モデル読み込み中: {model_path}")
    model = joblib.load(model_path)

    print(f"モデル情報読み込み中: {info_path}")
    with open(info_path, "r", encoding="utf-8") as f:
        model_info = json.load(f)

    # スケーラー読み込み
    scaler = None
    if scaler_path.exists():
        print(f"スケーラー読み込み中: {scaler_path}")
        scaler = joblib.load(scaler_path)

    return model, model_info, scaler


def prepare_race_data(race_df: pd.DataFrame) -> pd.DataFrame:
    """
    レースデータを予測用に準備

    Args:
        race_df: レース出走馬DataFrame

    Returns:
        準備されたDataFrame
    """
    print("レースデータを準備中...")

    # 必要な特徴量をチェック
    required_cols = [
        'horse_id', 'race_date', 'age', 'weight', 'distance',
        'popularity', 'track_condition', 'race_class'
    ]

    missing_cols = [col for col in required_cols if col not in race_df.columns]
    if missing_cols:
        print(f"⚠️ 不足しているカラム: {missing_cols}")

    # 調教データを追加
    race_df = add_training_features(race_df)

    # 特徴量エンジニアリング（簡易版）
    race_df = create_basic_features(race_df)

    return race_df


def add_training_features(df: pd.DataFrame) -> pd.DataFrame:
    """調教データの特徴量を追加"""
    print("調教データを取得中...")

    training_features = []

    for idx, row in df.iterrows():
        horse_id = row.get("horse_id")
        race_date = str(row.get("race_date", datetime.now().strftime("%Y%m%d")))

        features = {
            "training_count": 0,
            "final_4f_time": 0,
            "final_lap_1": 0,
            "has_good_time": 0,
            "n_sakamichi": 0,
            "n_course": 0,
            "training_score": 0,
        }

        try:
            if horse_id:
                training = analyze_horse_training(horse_id, race_date, days_back=14)

                if "error" not in training:
                    features["training_count"] = training.get("total_count", 0)
                    features["has_good_time"] = int(training.get("has_good_time", False))
                    features["n_sakamichi"] = training.get("n_sakamichi", 0)
                    features["n_course"] = training.get("n_course", 0)

                    if training.get("final"):
                        final = training["final"]
                        features["final_4f_time"] = final.get("time_4f", 0)
                        features["final_lap_1"] = final.get("lap_1", 0)

                    features["training_score"] = features["has_good_time"] * features["n_sakamichi"]

        except Exception as e:
            print(f"調教データ取得エラー (horse_id={horse_id}): {e}")

        training_features.append(features)

    training_df = pd.DataFrame(training_features)
    result_df = pd.concat([df.reset_index(drop=True), training_df], axis=1)

    return result_df


def create_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """基本的な特徴量を作成"""
    print("基本特徴量を作成中...")

    # 馬場状態エンコーディング
    condition_map = {'良': 0, '稍重': 1, '重': 2, '不良': 3}
    df['track_condition_encoded'] = df.get('track_condition', '良').map(condition_map).fillna(0)

    # 不足している特徴量をデフォルト値で埋める
    default_features = {
        'distance_change': 0,
        'weight_change': 0,
        'is_after_rest': 0,
        'is_class_up': 0,
        'avg_popularity': df.get('popularity', 5),
        'popularity_change': 0,
        'recent_win_rate': 0,
        'distance_win_rate': 0,
        'track_win_rate': 0,
    }

    for col, default_value in default_features.items():
        if col not in df.columns:
            df[col] = default_value

    return df


def predict_race(
    model,
    race_df: pd.DataFrame,
    feature_cols: list,
    threshold: float = 0.6
) -> pd.DataFrame:
    """
    レースを予測

    Args:
        model: 訓練済みモデル
        race_df: レースDataFrame
        feature_cols: 特徴量カラムリスト
        threshold: 購入しきい値

    Returns:
        予測結果を含むDataFrame
    """
    print("予測実行中...")

    # 特徴量を準備
    X = race_df[feature_cols].fillna(0)

    # 予測
    if hasattr(model, 'predict'):
        pred_proba = model.predict(X)
    else:
        pred_proba = model.predict_proba(X)[:, 1]

    pred_class = (pred_proba >= threshold).astype(int)

    # 結果を追加
    result = race_df.copy()
    result['pred_proba'] = pred_proba
    result['pred_class'] = pred_class
    result['recommended'] = (pred_proba >= threshold)

    return result


def generate_prediction_report(
    predictions: pd.DataFrame,
    race_info: dict
) -> str:
    """
    予測レポートを生成

    Args:
        predictions: 予測結果DataFrame
        race_info: レース情報辞書

    Returns:
        Markdown形式のレポート
    """
    # 推奨買い目のみ抽出
    recommendations = predictions[predictions['recommended']].sort_values('pred_proba', ascending=False)

    report = f"""# 競馬予測レポート

## レース情報
- **日付**: {race_info.get('date', 'N/A')}
- **競馬場**: {race_info.get('track', 'N/A')}
- **レース番号**: {race_info.get('race_num', 'N/A')}R
- **距離**: {race_info.get('distance', 'N/A')}m
- **馬場状態**: {race_info.get('track_condition', 'N/A')}

## 推奨買い目（{len(recommendations)}点）

"""

    if len(recommendations) == 0:
        report += "該当なし（しきい値を満たす馬がいません）\n"
    else:
        for idx, row in recommendations.iterrows():
            report += f"""### {row.get('umaban', 'N/A')}番 {row.get('horse_name', 'N/A')}
- **予測確率**: {row['pred_proba']:.1%}
- **性齢**: {row.get('sex', 'N/A')}{row.get('age', 'N/A')}歳
- **斤量**: {row.get('weight', 'N/A')}kg
- **人気**: {row.get('popularity', 'N/A')}番人気
- **調教評価**: {row.get('training_score', 0):.1f}
- **最終追切**: {row.get('final_4f_time', 0):.1f}秒

"""

    report += f"""
## 全出走馬の予測確率

| 馬番 | 馬名 | 予測確率 | 推奨 |
|------|------|----------|------|
"""

    for idx, row in predictions.sort_values('umaban').iterrows():
        recommended_mark = "✓" if row['recommended'] else ""
        report += f"| {row.get('umaban', 'N/A')} | {row.get('horse_name', 'N/A')} | {row['pred_proba']:.1%} | {recommended_mark} |\n"

    report += f"""
---
*予測モデル: LightGBM*
*予測日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return report


def save_predictions(
    predictions: pd.DataFrame,
    report: str,
    output_dir: Path,
    race_id: str = None
):
    """
    予測結果を保存

    Args:
        predictions: 予測結果DataFrame
        report: レポート文字列
        output_dir: 出力ディレクトリ
        race_id: レースID
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    race_suffix = f"_{race_id}" if race_id else ""

    # CSV保存
    csv_path = output_dir / f"predictions{race_suffix}_{timestamp}.csv"
    predictions.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✓ 予測結果保存: {csv_path}")

    # レポート保存
    report_path = output_dir / f"report{race_suffix}_{timestamp}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✓ レポート保存: {report_path}")


def main():
    """メイン処理"""
    print("=== 予測開始 ===\n")

    # パス設定
    model_dir = project_root / "ml" / "models"
    output_dir = project_root / "ml" / "data" / "predictions"

    # モデル読み込み
    model, model_info, scaler = load_model_and_info(model_dir, model_name="lightgbm_model")

    feature_cols = model_info['features']
    threshold = model_info.get('threshold', 0.6)

    print(f"使用モデル: {model_info['model_name']}")
    print(f"しきい値: {threshold}\n")

    # TODO: 実際のレースデータを読み込む
    # 以下はサンプルデータ
    sample_race_df = pd.DataFrame({
        'umaban': [1, 2, 3, 4, 5],
        'horse_name': ['サンプル馬A', 'サンプル馬B', 'サンプル馬C', 'サンプル馬D', 'サンプル馬E'],
        'horse_id': ['2020101234', '2020101235', '2020101236', '2020101237', '2020101238'],
        'race_date': ['20260201'] * 5,
        'age': [4, 3, 5, 4, 3],
        'sex': ['牡', '牡', '牝', '牡', '牡'],
        'weight': [56.0, 54.0, 54.0, 57.0, 56.0],
        'distance': [2000, 2000, 2000, 2000, 2000],
        'popularity': [3, 1, 5, 2, 7],
        'track_condition': ['良', '良', '良', '良', '良'],
        'race_class': ['3勝', '3勝', '3勝', '3勝', '3勝'],
    })

    race_info = {
        'date': '2026-02-01',
        'track': '東京',
        'race_num': 11,
        'distance': 2000,
        'track_condition': '良'
    }

    print("⚠️ サンプルデータを使用しています。実際のデータに置き換えてください。\n")

    # データ準備
    race_df = prepare_race_data(sample_race_df)

    # 予測
    predictions = predict_race(model, race_df, feature_cols, threshold=threshold)

    # レポート生成
    report = generate_prediction_report(predictions, race_info)

    # 結果表示
    print("\n" + report)

    # 保存
    save_predictions(predictions, report, output_dir, race_id=race_info.get('race_id'))

    print("\n=== 予測完了 ===")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
データ準備スクリプト

JRA-VANと競馬ブックのデータを統合し、機械学習用のデータセットを作成します。
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tqdm import tqdm

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from common.jravan import (
    get_horse_id_by_name,
    analyze_horse_training,
    get_horse_info,
    get_trainer_jvn_code,
)


def load_race_results(data_path: Path) -> pd.DataFrame:
    """
    レース結果データを読み込む

    Args:
        data_path: レース結果CSVファイルのパス

    Returns:
        レース結果DataFrame
    """
    print(f"レース結果を読み込み中: {data_path}")

    # TODO: 実際のデータパスに応じて調整
    # 想定カラム: race_id, race_date, horse_id, horse_name, umaban,
    #            着順, 人気, 単勝オッズ, 性別, 年齢, 斤量, 距離, 馬場状態, etc.

    df = pd.read_csv(data_path)

    print(f"読み込み完了: {len(df)}件")
    return df


def add_training_features(df: pd.DataFrame, race_date_col: str = "race_date") -> pd.DataFrame:
    """
    調教データの特徴量を追加

    Args:
        df: レース結果DataFrame
        race_date_col: レース日付のカラム名

    Returns:
        調教特徴量を追加したDataFrame
    """
    print("調教データを取得中...")

    training_features = []

    for idx, row in tqdm(df.iterrows(), total=len(df)):
        horse_id = row.get("horse_id")
        race_date = str(row[race_date_col])

        # デフォルト値
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

                    # 調教スコア（好タイム×坂路本数）
                    features["training_score"] = features["has_good_time"] * features["n_sakamichi"]

        except Exception as e:
            print(f"調教データ取得エラー (horse_id={horse_id}): {e}")

        training_features.append(features)

    # DataFrameに変換して結合
    training_df = pd.DataFrame(training_features)
    result_df = pd.concat([df, training_df], axis=1)

    print(f"調教データ追加完了: {len(training_df.columns)}列追加")
    return result_df


def create_target_variable(df: pd.DataFrame, target_col: str = "着順") -> pd.DataFrame:
    """
    目的変数を作成（馬券圏内=1, 圏外=0）

    Args:
        df: DataFrame
        target_col: 着順カラム名

    Returns:
        目的変数を追加したDataFrame
    """
    print("目的変数を作成中...")

    df["target"] = (df[target_col] <= 3).astype(int)

    print(f"目的変数の分布:")
    print(df["target"].value_counts())

    return df


def save_prepared_data(df: pd.DataFrame, output_path: Path):
    """
    準備したデータを保存

    Args:
        df: 準備済みDataFrame
        output_path: 出力先パス
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"データ保存完了: {output_path}")


def main():
    """メイン処理"""
    print("=== データ準備開始 ===\n")

    # パス設定
    data_dir = project_root / "data"
    input_file = data_dir / "race_results.csv"  # TODO: 実際のファイル名に変更
    output_file = data_dir / "training" / "race_results_prepared.csv"

    # 1. データ読み込み
    df = load_race_results(input_file)

    # 2. 調教データ追加
    df = add_training_features(df)

    # 3. 目的変数作成
    df = create_target_variable(df)

    # 4. データ保存
    save_prepared_data(df, output_file)

    print("\n=== データ準備完了 ===")
    print(f"総件数: {len(df)}")
    print(f"カラム数: {len(df.columns)}")
    print(f"\nカラム一覧:")
    print(df.columns.tolist())


if __name__ == "__main__":
    main()

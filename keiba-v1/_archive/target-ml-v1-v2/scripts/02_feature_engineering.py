# -*- coding: utf-8 -*-
"""
特徴量エンジニアリング

機械学習モデルへの入力となる特徴量を設計・作成します。
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def create_distance_change(df: pd.DataFrame) -> pd.DataFrame:
    """
    距離変化量特徴量を作成

    前走からの距離差を計算
    """
    print("距離変化量を作成中...")
    df = df.sort_values(['horse_id', 'race_date'])
    df['distance_change'] = df.groupby('horse_id')['distance'].diff().fillna(0)
    return df


def create_weight_change(df: pd.DataFrame) -> pd.DataFrame:
    """
    斤量変化量特徴量を作成

    前走からの斤量差を計算
    """
    print("斤量変化量を作成中...")
    df = df.sort_values(['horse_id', 'race_date'])
    df['weight_change'] = df.groupby('horse_id')['weight'].diff().fillna(0)
    return df


def create_rest_flag(df: pd.DataFrame, threshold_days: int = 30) -> pd.DataFrame:
    """
    休み明けフラグを作成

    Args:
        df: DataFrame
        threshold_days: 休み明けと判定する日数

    Returns:
        休み明けフラグを追加したDataFrame
    """
    print(f"休み明けフラグを作成中（{threshold_days}日以上）...")

    df['race_date_dt'] = pd.to_datetime(df['race_date'], format='%Y%m%d')
    df = df.sort_values(['horse_id', 'race_date_dt'])

    df['days_since_last'] = df.groupby('horse_id')['race_date_dt'].diff().dt.days.fillna(0)
    df['is_after_rest'] = (df['days_since_last'] >= threshold_days).astype(int)

    return df


def create_class_up_flag(df: pd.DataFrame) -> pd.DataFrame:
    """
    昇級戦フラグを作成

    前走よりクラスが上がった場合に1
    """
    print("昇級戦フラグを作成中...")

    # クラスの順序定義
    class_order = {
        '新馬': 0,
        '未勝利': 1,
        '1勝': 2,
        '2勝': 3,
        '3勝': 4,
        'オープン': 5,
        'G3': 6,
        'G2': 7,
        'G1': 8
    }

    df['class_code'] = df['race_class'].map(class_order).fillna(0)
    df = df.sort_values(['horse_id', 'race_date'])
    df['prev_class'] = df.groupby('horse_id')['class_code'].shift(1).fillna(0)
    df['is_class_up'] = (df['class_code'] > df['prev_class']).astype(int)

    return df


def create_track_condition_encoding(df: pd.DataFrame) -> pd.DataFrame:
    """
    馬場状態をエンコーディング

    良 < 稍重 < 重 < 不良 の順序でエンコード
    """
    print("馬場状態をエンコーディング中...")

    condition_map = {'良': 0, '稍重': 1, '重': 2, '不良': 3}
    df['track_condition_encoded'] = df['track_condition'].map(condition_map).fillna(0)

    return df


def create_popularity_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    人気に関する統計特徴量を作成

    - 平均人気
    - 人気の標準偏差
    - 前走人気との差
    """
    print("人気統計特徴量を作成中...")

    df = df.sort_values(['horse_id', 'race_date'])

    # 平均人気（直近5走）
    df['avg_popularity'] = df.groupby('horse_id')['popularity'].transform(
        lambda x: x.rolling(window=5, min_periods=1).mean()
    )

    # 前走人気との差
    df['popularity_change'] = df.groupby('horse_id')['popularity'].diff().fillna(0)

    return df


def create_win_rate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    勝率に関する特徴量を作成

    - 直近勝率（直近5走で圏内に入った割合）
    - 同距離での勝率
    - 同競馬場での勝率
    """
    print("勝率特徴量を作成中...")

    df = df.sort_values(['horse_id', 'race_date'])

    # 直近5走の圏内率
    df['recent_win_rate'] = df.groupby('horse_id')['target'].transform(
        lambda x: x.rolling(window=5, min_periods=1).mean()
    )

    # 同距離での勝率（これまでの全レース）
    distance_win_rate = df.groupby(['horse_id', 'distance'])['target'].expanding().mean().reset_index(level=[0, 1], drop=True)
    df['distance_win_rate'] = distance_win_rate.fillna(0)

    # 同競馬場での勝率
    track_win_rate = df.groupby(['horse_id', 'track_code'])['target'].expanding().mean().reset_index(level=[0, 1], drop=True)
    df['track_win_rate'] = track_win_rate.fillna(0)

    return df


def standardize_numerical_features(
    df: pd.DataFrame,
    numerical_cols: list,
    scaler_path: Path = None
) -> pd.DataFrame:
    """
    数値特徴量を標準化

    Args:
        df: DataFrame
        numerical_cols: 標準化する数値カラムのリスト
        scaler_path: スケーラーの保存先パス

    Returns:
        標準化されたDataFrame
    """
    print(f"数値特徴量を標準化中（{len(numerical_cols)}列）...")

    scaler = StandardScaler()
    df[numerical_cols] = scaler.fit_transform(df[numerical_cols])

    # スケーラーを保存
    if scaler_path:
        scaler_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(scaler, scaler_path)
        print(f"スケーラー保存: {scaler_path}")

    return df


def select_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """
    最終的な特徴量を選択

    Returns:
        特徴量DataFrame, 特徴量カラムリスト
    """
    print("最終特徴量を選択中...")

    # 使用する特徴量を定義
    feature_cols = [
        # 基本情報
        'age',
        'weight',
        'distance',
        'popularity',
        'track_condition_encoded',

        # 調教データ
        'training_count',
        'final_4f_time',
        'final_lap_1',
        'has_good_time',
        'n_sakamichi',
        'n_course',
        'training_score',

        # エンジニアリング特徴量
        'distance_change',
        'weight_change',
        'is_after_rest',
        'is_class_up',
        'avg_popularity',
        'popularity_change',
        'recent_win_rate',
        'distance_win_rate',
        'track_win_rate',
    ]

    # 欠損値を0で埋める
    df[feature_cols] = df[feature_cols].fillna(0)

    print(f"選択された特徴量: {len(feature_cols)}個")
    return df, feature_cols


def save_featured_data(df: pd.DataFrame, feature_cols: list, output_path: Path):
    """
    特徴量を追加したデータを保存

    Args:
        df: DataFrame
        feature_cols: 特徴量カラムリスト
        output_path: 出力先パス
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"データ保存完了: {output_path}")

    # 特徴量リストも保存
    feature_info_path = output_path.parent / "feature_columns.txt"
    with open(feature_info_path, "w", encoding="utf-8") as f:
        f.write("\n".join(feature_cols))
    print(f"特徴量リスト保存: {feature_info_path}")


def main():
    """メイン処理"""
    print("=== 特徴量エンジニアリング開始 ===\n")

    # パス設定
    data_dir = project_root / "data"
    input_file = data_dir / "training" / "race_results_prepared.csv"
    output_file = data_dir / "training" / "race_results_featured.csv"
    scaler_path = project_root / "ml" / "models" / "scaler.pkl"

    # データ読み込み
    print(f"データ読み込み中: {input_file}")
    df = pd.read_csv(input_file)
    print(f"読み込み完了: {len(df)}件\n")

    # 特徴量作成
    df = create_distance_change(df)
    df = create_weight_change(df)
    df = create_rest_flag(df)
    df = create_class_up_flag(df)
    df = create_track_condition_encoding(df)
    df = create_popularity_stats(df)
    df = create_win_rate_features(df)

    # 特徴量選択
    df, feature_cols = select_features(df)

    # 数値特徴量の標準化
    numerical_cols = [
        'age', 'weight', 'distance', 'popularity',
        'training_count', 'final_4f_time', 'final_lap_1',
        'distance_change', 'weight_change'
    ]
    df = standardize_numerical_features(df, numerical_cols, scaler_path)

    # データ保存
    save_featured_data(df, feature_cols, output_file)

    print("\n=== 特徴量エンジニアリング完了 ===")
    print(f"総件数: {len(df)}")
    print(f"特徴量数: {len(feature_cols)}")


if __name__ == "__main__":
    main()

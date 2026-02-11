# -*- coding: utf-8 -*-
"""
ML Experiment v1: 3着以内予測 (LightGBM)

integrated JSON → 特徴量抽出 → LightGBM学習 → 評価 → JSON出力

v1.1: レーティング派生特徴量追加 + 回収率分析

Usage:
    cd KeibaCICD.TARGET
    python ml/scripts/ml_experiment_v1.py
"""

import sys
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd
from datetime import datetime

import lightgbm as lgb
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    log_loss,
)

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from common.config import get_keiba_data_root, get_races_dir, get_target_data_dir, ensure_dir


# =============================================================================
# 定数
# =============================================================================

FEATURE_COLS = [
    "rating",
    "rating_deviation",
    "rating_vs_odds",
    "odds_rank",
    "age",
    "weight",
    "waku",
    "mark_point",
    "aggregate_mark_point",
    "ai_index",
    "distance",
    "track_type",
    "track_condition",
    "entry_count",
    "rpci",
    "training_arrow",
    "sex",
]

FEATURE_LABELS = {
    "rating": "レーティング",
    "rating_deviation": "レーティング偏差",
    "rating_vs_odds": "Rating×人気乖離",
    "odds_rank": "人気順",
    "age": "年齢",
    "weight": "斤量",
    "waku": "枠番",
    "mark_point": "本誌印ポイント",
    "aggregate_mark_point": "総合印ポイント",
    "ai_index": "AI指数",
    "distance": "距離",
    "track_type": "芝/ダート",
    "track_condition": "馬場状態",
    "entry_count": "出走頭数",
    "rpci": "RPCI",
    "training_arrow": "調教矢印",
    "sex": "性別",
}


# =============================================================================
# ユーティリティ
# =============================================================================


def safe_float(val, default=np.nan) -> float:
    """文字列を安全にfloatへ変換"""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_age(age_str: str) -> tuple:
    """'牝3' → ('牝', 3)"""
    if not age_str:
        return "", 0
    m = re.match(r"(牡|牝|セン)(\d+)", age_str)
    if m:
        return m.group(1), int(m.group(2))
    return "", 0


# =============================================================================
# Step 1: データ読み込み
# =============================================================================


def find_integrated_jsons(races_dir: Path, years: list) -> list:
    """指定年のintegrated JSONファイルを全走査"""
    files = []
    for year in years:
        year_dir = races_dir / str(year)
        if year_dir.exists():
            files.extend(year_dir.rglob("integrated_*.json"))
    return sorted(files)


def extract_entries_from_race(data: dict) -> list:
    """1レースのJSONから馬ごとのフラットなdictリストを生成"""
    race_info = data.get("race_info", {})
    meta = data.get("meta", {})
    race_id = meta.get("race_id", "")

    date_str = race_info.get("date", "")  # "2025/01/05"
    entries = data.get("entries", [])
    if not entries:
        return []

    # 結果がないレースはスキップ
    has_results = any(
        e.get("result", {}).get("finish_position", "") != "" for e in entries
    )
    if not has_results:
        return []

    entry_count = len(entries)
    distance = race_info.get("distance", 0)
    track = race_info.get("track", "")
    track_condition = race_info.get("track_condition", "")
    venue = race_info.get("venue", "")
    grade = race_info.get("grade", "")

    # エンコーディング
    track_type_val = 1 if track == "芝" else 0
    cond_map = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
    track_cond_val = cond_map.get(track_condition, -1)
    arrow_map = {"↑": 2, "↗": 1, "→": 0, "↘": -1, "↓": -2}

    rows = []
    for e in entries:
        ed = e.get("entry_data", {})
        result = e.get("result", {})
        td = e.get("training_data", {})

        # 着順が数値でない馬はスキップ（取消・中止・除外）
        fp_str = result.get("finish_position", "")
        try:
            finish_pos = int(fp_str)
        except (ValueError, TypeError):
            continue

        sex, age_num = parse_age(ed.get("age", ""))
        sex_val = {"牡": 0, "牝": 1, "セン": 2}.get(sex, 0)
        training_arrow_val = arrow_map.get(td.get("training_arrow", ""), 0)

        rows.append(
            {
                "race_id": race_id,
                "date": date_str,
                "venue": venue,
                "grade": grade,
                "horse_number": e.get("horse_number", 0),
                "horse_name": e.get("horse_name", ""),
                "finish_position": finish_pos,
                "target": 1 if finish_pos <= 3 else 0,
                # --- 特徴量 ---
                "rating": safe_float(ed.get("rating")),
                "odds_rank": safe_float(ed.get("odds_rank")),
                "age": age_num,
                "weight": safe_float(ed.get("weight")),
                "waku": safe_float(ed.get("waku")),
                "mark_point": ed.get("mark_point", 0) or 0,
                "aggregate_mark_point": ed.get("aggregate_mark_point", 0) or 0,
                "ai_index": safe_float(ed.get("ai_index")),
                "distance": distance if isinstance(distance, (int, float)) else 0,
                "track_type": track_type_val,
                "track_condition": track_cond_val,
                "entry_count": entry_count,
                "training_arrow": training_arrow_val,
                "sex": sex_val,
                # 回収率計算用（特徴量にはしない）
                "odds": safe_float(ed.get("odds")),
            }
        )

    return rows


# =============================================================================
# Step 2: RPCI結合 + レーティング派生特徴量
# =============================================================================


def load_rpci_index(target_dir: Path) -> dict:
    """race_trend_index.json からraceId→rpciのマッピングを生成"""
    path = target_dir / "race_trend_index.json"
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v.get("rpci") for k, v in data.get("races", {}).items()}


def add_rating_features(df: pd.DataFrame) -> pd.DataFrame:
    """レーティング派生特徴量を追加"""
    # レース内平均レーティングとの偏差（高いほどそのレースで能力上位）
    race_mean_rating = df.groupby("race_id")["rating"].transform("mean")
    df["rating_deviation"] = df["rating"] - race_mean_rating

    # レーティング順位 vs 人気順の乖離
    # rating_rank を小さい方が上位（1=最高）で計算
    df["rating_rank"] = df.groupby("race_id")["rating"].rank(
        ascending=False, method="min"
    )
    # 乖離 = 人気順 - レーティング順位 （正=レーティングの割に人気薄＝お買い得）
    df["rating_vs_odds"] = df["odds_rank"] - df["rating_rank"]

    # 作業列を削除
    df.drop(columns=["rating_rank"], inplace=True)
    return df


# =============================================================================
# Step 3: 時系列分割
# =============================================================================


def time_split(df: pd.DataFrame, split_year: int = 2025):
    """年でtrain/testに分割"""
    df["year"] = df["date"].str[:4].astype(int)
    train = df[df["year"] < split_year].copy()
    test = df[df["year"] >= split_year].copy()
    return train, test


# =============================================================================
# Step 4: モデル学習
# =============================================================================


def train_model(X_train, y_train, X_test, y_test):
    """LightGBMで学習"""
    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 20,
        "verbose": -1,
    }

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    model = lgb.train(
        params,
        train_data,
        num_boost_round=1000,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=100),
        ],
    )
    return model


# =============================================================================
# Step 5: 回収率分析
# =============================================================================


def calc_roi_analysis(result_df: pd.DataFrame) -> dict:
    """
    しきい値別の回収率シミュレーション
    - 単勝: モデルTop1が1着なら単勝オッズ×100円回収
    - 複勝: モデルTop1が3着以内なら複勝オッズ（概算: 単勝オッズ/3〜/4）×100円回収
            ※ 正確な複勝オッズがないため、簡易的に単勝を使って「3着以内的中率×平均配当」で計算
    """
    analysis = {}

    # --- 全レースの単勝回収率 (Top1予測を毎レース100円買い) ---
    races = result_df.groupby("race_id")
    win_bets = 0
    win_return = 0
    place_bets = 0
    place_hits = 0
    place_return_sum = 0

    for _, group in races:
        top1 = group.sort_values("pred_proba", ascending=False).iloc[0]
        odds = top1["odds"]
        if pd.isna(odds) or odds <= 0:
            continue

        # 単勝
        win_bets += 100
        if top1["finish_position"] == 1:
            win_return += odds * 100

        # 複勝（概算: 単勝オッズ / 3.5 でざっくり近似）
        place_bets += 100
        if top1["target"] == 1:
            place_hits += 1
            estimated_place_odds = max(odds / 3.5, 1.1)
            place_return_sum += estimated_place_odds * 100

    analysis["top1_win"] = {
        "total_bet": win_bets,
        "total_return": round(win_return),
        "roi": round(win_return / win_bets * 100, 1) if win_bets > 0 else 0,
        "bet_count": win_bets // 100,
    }
    analysis["top1_place"] = {
        "total_bet": place_bets,
        "total_return": round(place_return_sum),
        "roi": round(place_return_sum / place_bets * 100, 1)
        if place_bets > 0
        else 0,
        "hit_rate": round(place_hits / (place_bets // 100) * 100, 1)
        if place_bets > 0
        else 0,
        "bet_count": place_bets // 100,
    }

    # --- しきい値別回収率 ---
    threshold_analysis = []
    for threshold in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        bets = 0
        win_ret = 0
        place_ret = 0
        hits_win = 0
        hits_place = 0
        total_selected = 0

        for _, group in races:
            selected = group[group["pred_proba"] >= threshold]
            for _, row in selected.iterrows():
                odds = row["odds"]
                if pd.isna(odds) or odds <= 0:
                    continue
                total_selected += 1
                bets += 100

                if row["finish_position"] == 1:
                    hits_win += 1
                    win_ret += odds * 100
                if row["target"] == 1:
                    hits_place += 1
                    est_place_odds = max(odds / 3.5, 1.1)
                    place_ret += est_place_odds * 100

        threshold_analysis.append(
            {
                "threshold": threshold,
                "bet_count": total_selected,
                "win_hits": hits_win,
                "win_roi": round(win_ret / bets * 100, 1) if bets > 0 else 0,
                "place_hits": hits_place,
                "place_roi": round(place_ret / bets * 100, 1) if bets > 0 else 0,
                "place_hit_rate": round(
                    hits_place / total_selected * 100, 1
                )
                if total_selected > 0
                else 0,
            }
        )

    analysis["by_threshold"] = threshold_analysis
    return analysis


# =============================================================================
# Step 6: 評価 + JSON出力
# =============================================================================


def evaluate_and_export(model, X_test, y_test, test_df, train_size, output_path):
    """モデルを評価し結果JSONを出力"""
    y_proba = model.predict(X_test, num_iteration=model.best_iteration)
    y_pred = (y_proba > 0.5).astype(int)

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "log_loss": round(float(log_loss(y_test, y_proba)), 4),
        "best_iteration": int(model.best_iteration),
        "train_size": train_size,
        "test_size": len(y_test),
    }

    # 特徴量重要度
    importance = pd.DataFrame(
        {
            "feature": FEATURE_COLS,
            "importance": model.feature_importance(importance_type="gain"),
        }
    ).sort_values("importance", ascending=False)

    feature_importance = [
        {
            "feature": row["feature"],
            "label": FEATURE_LABELS.get(row["feature"], row["feature"]),
            "importance": round(float(row["importance"]), 2),
        }
        for _, row in importance.iterrows()
    ]

    # レースごとの予測結果
    result_df = test_df.copy()
    result_df["pred_proba"] = y_proba
    result_df["pred_top3"] = y_pred

    # --- 回収率分析 ---
    roi_analysis = calc_roi_analysis(result_df)

    race_predictions = []
    for race_id, group in result_df.groupby("race_id"):
        horses = []
        for _, row in group.iterrows():
            horses.append(
                {
                    "horse_number": int(row["horse_number"]),
                    "horse_name": row["horse_name"],
                    "pred_proba": round(float(row["pred_proba"]), 4),
                    "pred_top3": int(row["pred_top3"]),
                    "actual_position": int(row["finish_position"]),
                    "actual_top3": int(row["target"]),
                    "odds_rank": int(row["odds_rank"])
                    if not pd.isna(row["odds_rank"])
                    else None,
                    "odds": round(float(row["odds"]), 1)
                    if not pd.isna(row["odds"])
                    else None,
                }
            )
        horses.sort(key=lambda h: h["pred_proba"], reverse=True)
        race_predictions.append(
            {
                "race_id": race_id,
                "date": group.iloc[0]["date"],
                "venue": group.iloc[0]["venue"],
                "grade": group.iloc[0]["grade"],
                "entry_count": int(group.iloc[0]["entry_count"]),
                "horses": horses,
            }
        )

    race_predictions.sort(key=lambda r: r["date"], reverse=True)

    # 的中率分析
    hit_analysis = []
    for n in [1, 2, 3]:
        hits = 0
        total = 0
        for rp in race_predictions:
            top_n = rp["horses"][:n]
            if any(h["actual_top3"] == 1 for h in top_n):
                hits += 1
            total += 1
        hit_analysis.append(
            {
                "top_n": n,
                "hit_rate": round(hits / total, 4) if total > 0 else 0,
                "hits": hits,
                "total": total,
            }
        )

    output = {
        "version": "1.1",
        "model": "LightGBM",
        "experiment": "ml_experiment_v1",
        "created_at": datetime.now().isoformat(),
        "description": "3着以内予測 (binary classification) + 回収率分析",
        "split": {"train": "2023-2024", "test": "2025"},
        "features": FEATURE_COLS,
        "metrics": metrics,
        "feature_importance": feature_importance,
        "hit_analysis": hit_analysis,
        "roi_analysis": roi_analysis,
        "race_predictions": race_predictions[:200],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return metrics, roi_analysis


# =============================================================================
# メイン
# =============================================================================


def main():
    print("=" * 60)
    print("ML Experiment v1.1: 3着以内予測 + 回収率分析")
    print("=" * 60)

    data_root = get_keiba_data_root()
    races_dir = get_races_dir()
    target_dir = get_target_data_dir()
    output_path = data_root / "target" / "ml" / "ml_experiment_v1_result.json"

    # --- 1. データ読み込み ---
    print("\n[1/6] データ読み込み中...")
    files = find_integrated_jsons(races_dir, [2023, 2024, 2025])
    print(f"  JSONファイル数: {len(files)}")

    all_rows = []
    error_count = 0
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            rows = extract_entries_from_race(data)
            all_rows.extend(rows)
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  ERROR: {f.name}: {e}")

    df = pd.DataFrame(all_rows)
    print(f"  レコード数: {len(df):,}")
    print(f"  レース数:   {df['race_id'].nunique():,}")
    if error_count > 0:
        print(f"  読み込みエラー: {error_count}件")

    # --- 2. RPCI結合 ---
    print("\n[2/6] RPCI結合中...")
    rpci_map = load_rpci_index(target_dir)
    df["rpci"] = df["race_id"].map(rpci_map)
    rpci_rate = df["rpci"].notna().sum() / len(df) * 100
    print(f"  RPCI結合率: {rpci_rate:.1f}%")

    # --- 3. レーティング派生特徴量 ---
    print("\n[3/6] レーティング派生特徴量を追加中...")
    df = add_rating_features(df)
    rating_valid = df["rating"].notna().sum() / len(df) * 100
    print(f"  レーティング有効率: {rating_valid:.1f}%")
    print(f"  rating_deviation: mean={df['rating_deviation'].mean():.2f}, std={df['rating_deviation'].std():.2f}")
    print(f"  rating_vs_odds:   mean={df['rating_vs_odds'].mean():.2f}, std={df['rating_vs_odds'].std():.2f}")

    # --- 4. 特徴量確認 ---
    print("\n[4/6] 特徴量サマリー...")
    target_counts = df["target"].value_counts()
    print(f"  Target分布:")
    print(f"    圏内(1): {target_counts.get(1, 0):,} ({target_counts.get(1, 0)/len(df)*100:.1f}%)")
    print(f"    圏外(0): {target_counts.get(0, 0):,} ({target_counts.get(0, 0)/len(df)*100:.1f}%)")
    odds_valid = df["odds"].notna().sum() / len(df) * 100
    print(f"  オッズ有効率: {odds_valid:.1f}%")

    # --- 5. 時系列分割 + 学習 ---
    print("\n[5/6] 時系列分割 + LightGBM学習...")
    train_df, test_df = time_split(df, split_year=2025)
    print(f"  Train: {len(train_df):,} records ({train_df['race_id'].nunique():,} races)")
    print(f"  Test:  {len(test_df):,} records ({test_df['race_id'].nunique():,} races)")

    X_train = train_df[FEATURE_COLS].fillna(-1)
    y_train = train_df["target"]
    X_test = test_df[FEATURE_COLS].fillna(-1)
    y_test = test_df["target"]

    model = train_model(X_train, y_train, X_test, y_test)

    # --- 6. 評価 + 回収率分析 + JSON出力 ---
    print("\n[6/6] 評価 + 回収率分析 + JSON出力...")
    metrics, roi = evaluate_and_export(
        model, X_test, y_test, test_df, len(train_df), output_path
    )

    print("\n" + "=" * 60)
    print("結果サマリー")
    print("=" * 60)
    print(f"  Accuracy:  {metrics['accuracy']}")
    print(f"  AUC:       {metrics['auc']}")
    print(f"  Precision: {metrics['precision']}")
    print(f"  Recall:    {metrics['recall']}")
    print(f"  F1:        {metrics['f1']}")
    print(f"  Log Loss:  {metrics['log_loss']}")
    print()
    print("  --- 回収率 (Top1予測を毎レース購入) ---")
    w = roi["top1_win"]
    p = roi["top1_place"]
    print(f"  単勝: {w['bet_count']}R × 100円 = {w['total_bet']:,}円 → 払戻 {w['total_return']:,}円 (ROI {w['roi']}%)")
    print(f"  複勝: {p['bet_count']}R × 100円 = {p['total_bet']:,}円 → 払戻 {p['total_return']:,}円 (ROI {p['roi']}%) 的中率 {p['hit_rate']}%")
    print()
    print("  --- しきい値別回収率 ---")
    print(f"  {'閾値':>6} {'件数':>6} {'単勝ROI':>8} {'複勝ROI':>8} {'複勝的中':>8}")
    for t in roi["by_threshold"]:
        print(
            f"  {t['threshold']:>6.2f} {t['bet_count']:>6} {t['win_roi']:>7.1f}% {t['place_roi']:>7.1f}% {t['place_hit_rate']:>7.1f}%"
        )
    print(f"\n  Output: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

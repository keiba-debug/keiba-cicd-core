# -*- coding: utf-8 -*-
"""
ML Experiment v2: Value Betting Model (LightGBM dual model)

前走成績 + コース適性 + クラス変動 + 調教師パターンを追加。
Model A (精度) と Model B (Value: 市場系特徴量除外) のデュアルモデルで
「市場が見落としている馬」を検出する。

Usage:
    cd KeibaCICD.TARGET
    python ml/scripts/ml_experiment_v2.py
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
    accuracy_score, roc_auc_score, precision_score,
    recall_score, f1_score, log_loss,
)

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from common.config import get_keiba_data_root, get_races_dir, get_target_data_dir


# =============================================================================
# 定数
# =============================================================================

# 全特徴量（Model A用）
FEATURE_COLS_ALL = [
    # --- v1特徴量 ---
    "rating", "rating_deviation", "rating_vs_odds",
    "odds_rank", "age", "weight", "waku",
    "mark_point", "aggregate_mark_point", "ai_index",
    "distance", "track_type", "track_condition",
    "entry_count", "rpci", "training_arrow", "sex",
    # --- v2: 前走成績 ---
    "avg_finish_last3", "best_finish_last5",
    "last3f_avg_last3", "days_since_last_race",
    "win_rate_all", "top3_rate_all",
    "total_career_races", "recent_form_trend",
    # --- v2: コース適性 ---
    "venue_top3_rate", "track_type_top3_rate", "distance_fitness",
    # --- v2: クラス/ローテ ---
    "prev_race_entry_count", "entry_count_change", "rating_trend_last3",
    # --- v2: 調教師 ---
    "trainer_top3_rate",
]

# Value Model用（市場系を除外）
MARKET_FEATURES = {"odds_rank", "mark_point", "aggregate_mark_point", "ai_index", "rating_vs_odds"}
FEATURE_COLS_VALUE = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]

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
    "avg_finish_last3": "直近3走平均着順",
    "best_finish_last5": "直近5走ベスト着順",
    "last3f_avg_last3": "直近3走上がり3F平均",
    "days_since_last_race": "休養日数",
    "win_rate_all": "通算勝率",
    "top3_rate_all": "通算3着内率",
    "total_career_races": "通算出走数",
    "recent_form_trend": "近走トレンド",
    "venue_top3_rate": "競馬場別3着内率",
    "track_type_top3_rate": "芝ダ別3着内率",
    "distance_fitness": "距離適性3着内率",
    "prev_race_entry_count": "前走出走頭数",
    "entry_count_change": "出走頭数変化",
    "rating_trend_last3": "Rating推移",
    "trainer_top3_rate": "調教師3着内率",
}


# =============================================================================
# ユーティリティ
# =============================================================================

def safe_float(val, default=np.nan):
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_age(age_str: str) -> tuple:
    if not age_str:
        return "", 0
    m = re.match(r"(牡|牝|セン)(\d+)", age_str)
    if m:
        return m.group(1), int(m.group(2))
    return "", 0


# =============================================================================
# Step 1: データ読み込み（v1と同じ）
# =============================================================================

def find_integrated_jsons(races_dir: Path, years: list) -> list:
    files = []
    for year in years:
        year_dir = races_dir / str(year)
        if year_dir.exists():
            files.extend(year_dir.rglob("integrated_*.json"))
    return sorted(files)


def extract_entries_from_race(data: dict) -> list:
    race_info = data.get("race_info", {})
    meta = data.get("meta", {})
    race_id = meta.get("race_id", "")
    date_str = race_info.get("date", "")
    entries = data.get("entries", [])
    if not entries:
        return []

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

    track_type_val = 1 if track == "芝" else 0
    cond_map = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
    track_cond_val = cond_map.get(track_condition, -1)
    arrow_map = {"↑": 2, "↗": 1, "→": 0, "↘": -1, "↓": -2}

    rows = []
    for e in entries:
        ed = e.get("entry_data", {})
        result = e.get("result", {})
        td = e.get("training_data", {})

        fp_str = result.get("finish_position", "")
        try:
            finish_pos = int(fp_str)
        except (ValueError, TypeError):
            continue

        sex, age_num = parse_age(ed.get("age", ""))
        sex_val = {"牡": 0, "牝": 1, "セン": 2}.get(sex, 0)
        training_arrow_val = arrow_map.get(td.get("training_arrow", ""), 0)

        rows.append({
            "race_id": race_id,
            "date": date_str,
            "venue": venue,
            "grade": grade,
            "horse_id": e.get("horse_id", ""),
            "horse_number": e.get("horse_number", 0),
            "horse_name": e.get("horse_name", ""),
            "trainer_id": ed.get("trainer_id", ""),
            "finish_position": finish_pos,
            "target": 1 if finish_pos <= 3 else 0,
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
            "odds": safe_float(ed.get("odds")),
        })

    return rows


# =============================================================================
# Step 2: 過去走特徴量
# =============================================================================

def load_horse_history_cache(target_dir: Path) -> dict:
    path = target_dir / "ml" / "horse_history_cache.json"
    print(f"  Loading {path.name}...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Horses: {data['meta']['total_horses']:,}, Entries: {data['meta']['total_entries']:,}")
    return data["horses"]


def compute_past_features(horse_id: str, race_date: str, venue: str,
                          track_type: int, distance: int,
                          history_cache: dict) -> dict:
    """過去走から特徴量を計算（時系列リーク防止）"""
    result = {
        "avg_finish_last3": np.nan,
        "best_finish_last5": np.nan,
        "last3f_avg_last3": np.nan,
        "days_since_last_race": np.nan,
        "win_rate_all": np.nan,
        "top3_rate_all": np.nan,
        "total_career_races": 0,
        "recent_form_trend": np.nan,
        "venue_top3_rate": np.nan,
        "track_type_top3_rate": np.nan,
        "distance_fitness": np.nan,
        "prev_race_entry_count": np.nan,
        "entry_count_change": np.nan,
        "rating_trend_last3": np.nan,
    }

    history = history_cache.get(horse_id, [])
    if not history:
        return result

    # 当該レース日より前のレースのみ
    past = [h for h in history if h["race_date"] < race_date]
    if not past:
        return result

    n = len(past)
    result["total_career_races"] = n

    # --- 直近N走 ---
    last3 = past[-3:] if n >= 3 else past
    last5 = past[-5:] if n >= 5 else past

    positions_last3 = [h["finish_position"] for h in last3]
    result["avg_finish_last3"] = np.mean(positions_last3)
    result["best_finish_last5"] = min(h["finish_position"] for h in last5)

    # 上がり3F
    l3f_vals = [h["last_3f"] for h in last3 if h.get("last_3f") is not None]
    if l3f_vals:
        result["last3f_avg_last3"] = round(np.mean(l3f_vals), 1)

    # 休養日数
    try:
        last_date = datetime.strptime(past[-1]["race_date"], "%Y%m%d")
        current_date = datetime.strptime(race_date, "%Y%m%d")
        result["days_since_last_race"] = (current_date - last_date).days
    except (ValueError, TypeError):
        pass

    # 通算成績
    wins = sum(1 for h in past if h["finish_position"] == 1)
    top3s = sum(1 for h in past if h["finish_position"] <= 3)
    result["win_rate_all"] = round(wins / n, 4)
    result["top3_rate_all"] = round(top3s / n, 4)

    # 近走トレンド（直近3走の着順の傾きの符号反転。正=改善中）
    if len(positions_last3) >= 2:
        # 単純に (最初 - 最後)。正 = 着順が改善（数字が小さくなった）
        result["recent_form_trend"] = positions_last3[0] - positions_last3[-1]

    # --- コース適性 ---
    track_str = "芝" if track_type == 1 else "ダ"
    venue_races = [h for h in past if h.get("venue") == venue]
    if venue_races:
        result["venue_top3_rate"] = round(
            sum(1 for h in venue_races if h["finish_position"] <= 3) / len(venue_races), 4
        )
    track_races = [h for h in past if h.get("track") == track_str]
    if track_races:
        result["track_type_top3_rate"] = round(
            sum(1 for h in track_races if h["finish_position"] <= 3) / len(track_races), 4
        )
    dist_races = [h for h in past
                  if h.get("distance") and abs(h["distance"] - distance) <= 200]
    if dist_races:
        result["distance_fitness"] = round(
            sum(1 for h in dist_races if h["finish_position"] <= 3) / len(dist_races), 4
        )

    # --- クラス/ローテ ---
    result["prev_race_entry_count"] = past[-1].get("entry_count", np.nan)
    if past[-1].get("entry_count"):
        # entry_count_change は current - prev（正 = 前走より多頭数 = クラスアップ傾向）
        # ただし current entry_count は呼び出し側で後から設定する
        pass

    # Rating推移（直近3走のレーティングの傾き）
    last3_ratings = [h["rating"] for h in last3 if h.get("rating") is not None]
    if len(last3_ratings) >= 2:
        # 最新 - 最古。正 = レーティング上昇中
        result["rating_trend_last3"] = round(last3_ratings[-1] - last3_ratings[0], 1)

    return result


# =============================================================================
# Step 3: 調教師特徴量
# =============================================================================

def load_trainer_patterns(target_dir: Path) -> dict:
    path = target_dir / "trainer_patterns.json"
    if not path.exists():
        return {}, {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    trainers = data.get("trainers", {})

    # keibabook_id → jvn_code のマッピング構築
    kb_to_jvn = {}
    for jvn_code, t in trainers.items():
        for kb_id in t.get("keibabook_ids", []):
            kb_to_jvn[kb_id] = jvn_code

    return trainers, kb_to_jvn


def get_trainer_top3_rate(trainer_id: str, trainers: dict, kb_to_jvn: dict) -> float:
    jvn = kb_to_jvn.get(trainer_id, "")
    if not jvn or jvn not in trainers:
        return np.nan
    return trainers[jvn].get("overall_stats", {}).get("top3_rate", np.nan)


# =============================================================================
# Step 4: RPCI結合 + レーティング派生
# =============================================================================

def load_rpci_index(target_dir: Path) -> dict:
    path = target_dir / "race_trend_index.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v.get("rpci") for k, v in data.get("races", {}).items()}


def add_rating_features(df: pd.DataFrame) -> pd.DataFrame:
    race_mean_rating = df.groupby("race_id")["rating"].transform("mean")
    df["rating_deviation"] = df["rating"] - race_mean_rating
    df["rating_rank"] = df.groupby("race_id")["rating"].rank(ascending=False, method="min")
    df["rating_vs_odds"] = df["odds_rank"] - df["rating_rank"]
    df.drop(columns=["rating_rank"], inplace=True)
    return df


# =============================================================================
# Step 5: モデル学習
# =============================================================================

def time_split(df: pd.DataFrame, split_year: int = 2025):
    df["year"] = df["date"].str[:4].astype(int)
    train = df[df["year"] < split_year].copy()
    test = df[df["year"] >= split_year].copy()
    return train, test


def train_model(X_train, y_train, X_test, y_test, label=""):
    params = {
        "objective": "binary",
        "metric": "auc",
        "boosting": "gbdt",
        "num_leaves": 63,
        "learning_rate": 0.03,
        "feature_fraction": 0.7,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 30,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "max_depth": 7,
        "verbose": -1,
    }

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    model = lgb.train(
        params, train_data, num_boost_round=1500,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=200),
        ],
    )
    if label:
        print(f"  [{label}] Best iteration: {model.best_iteration}")
    return model


# =============================================================================
# Step 6: 回収率分析（拡張版）
# =============================================================================

def calc_roi_analysis(result_df: pd.DataFrame, proba_col: str = "pred_proba") -> dict:
    """標準のROI分析"""
    analysis = {}
    races = result_df.groupby("race_id")

    win_bets = 0; win_return = 0
    place_bets = 0; place_hits = 0; place_return_sum = 0

    for _, group in races:
        top1 = group.sort_values(proba_col, ascending=False).iloc[0]
        odds = top1["odds"]
        if pd.isna(odds) or odds <= 0:
            continue
        win_bets += 100
        if top1["finish_position"] == 1:
            win_return += odds * 100
        place_bets += 100
        if top1["target"] == 1:
            place_hits += 1
            place_return_sum += max(odds / 3.5, 1.1) * 100

    analysis["top1_win"] = {
        "total_bet": win_bets,
        "total_return": round(win_return),
        "roi": round(win_return / win_bets * 100, 1) if win_bets > 0 else 0,
        "bet_count": win_bets // 100,
    }
    analysis["top1_place"] = {
        "total_bet": place_bets,
        "total_return": round(place_return_sum),
        "roi": round(place_return_sum / place_bets * 100, 1) if place_bets > 0 else 0,
        "hit_rate": round(place_hits / (place_bets // 100), 4) if place_bets > 0 else 0,
        "bet_count": place_bets // 100,
    }

    threshold_analysis = []
    for threshold in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        bets = 0; win_ret = 0; place_ret = 0
        hits_win = 0; hits_place = 0; total_selected = 0
        for _, group in races:
            selected = group[group[proba_col] >= threshold]
            for _, row in selected.iterrows():
                odds = row["odds"]
                if pd.isna(odds) or odds <= 0:
                    continue
                total_selected += 1; bets += 100
                if row["finish_position"] == 1:
                    hits_win += 1; win_ret += odds * 100
                if row["target"] == 1:
                    hits_place += 1
                    place_ret += max(odds / 3.5, 1.1) * 100
        threshold_analysis.append({
            "threshold": threshold,
            "bet_count": total_selected,
            "win_hits": hits_win,
            "win_roi": round(win_ret / bets * 100, 1) if bets > 0 else 0,
            "place_hits": hits_place,
            "place_roi": round(place_ret / bets * 100, 1) if bets > 0 else 0,
            "place_hit_rate": round(hits_place / total_selected, 4) if total_selected > 0 else 0,
        })
    analysis["by_threshold"] = threshold_analysis
    return analysis


def calc_value_bet_analysis(result_df: pd.DataFrame) -> dict:
    """Value Bet分析: Model Bランク vs 人気順のギャップでROI計算"""
    # Model Bのレース内ランクを計算
    df = result_df.copy()
    df["value_rank"] = df.groupby("race_id")["pred_proba_value"].rank(
        ascending=False, method="min"
    )
    races = df.groupby("race_id")

    by_gap = []
    for min_gap in [2, 3, 4, 5]:
        bets = 0; win_ret = 0; place_ret = 0
        hits_win = 0; hits_place = 0; total = 0

        for _, group in races:
            # value_rank <= 3 かつ odds_rank >= value_rank + min_gap
            candidates = group[
                (group["value_rank"] <= 3) &
                (group["odds_rank"] >= group["value_rank"] + min_gap)
            ]
            for _, row in candidates.iterrows():
                odds = row["odds"]
                if pd.isna(odds) or odds <= 0:
                    continue
                total += 1; bets += 100
                if row["finish_position"] == 1:
                    hits_win += 1; win_ret += odds * 100
                if row["target"] == 1:
                    hits_place += 1
                    place_ret += max(odds / 3.5, 1.1) * 100

        by_gap.append({
            "min_gap": min_gap,
            "bet_count": total,
            "win_hits": hits_win,
            "win_roi": round(win_ret / bets * 100, 1) if bets > 0 else 0,
            "place_hits": hits_place,
            "place_roi": round(place_ret / bets * 100, 1) if bets > 0 else 0,
            "place_hit_rate": round(hits_place / total, 4) if total > 0 else 0,
        })

    return {"by_rank_gap": by_gap}


# =============================================================================
# Step 7: 評価 + JSON出力
# =============================================================================

def evaluate_model(model, X_test, y_test, feature_cols):
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
        "train_size": 0,  # set later
        "test_size": len(y_test),
    }

    importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False)

    feature_importance = [
        {
            "feature": row["feature"],
            "label": FEATURE_LABELS.get(row["feature"], row["feature"]),
            "importance": round(float(row["importance"]), 2),
        }
        for _, row in importance.iterrows()
    ]

    return y_proba, y_pred, metrics, feature_importance


def export_results(test_df, train_size, y_proba_a, y_proba_v,
                   metrics_a, metrics_v, fi_a, fi_v,
                   roi_a, roi_v, value_bets, output_path):
    """結果JSONを出力"""
    metrics_a["train_size"] = train_size
    metrics_v["train_size"] = train_size

    result_df = test_df.copy()
    result_df["pred_proba_accuracy"] = y_proba_a
    result_df["pred_proba_value"] = y_proba_v
    result_df["pred_top3_accuracy"] = (y_proba_a > 0.5).astype(int)

    # レースごとの予測結果
    race_predictions = []
    for race_id, group in result_df.groupby("race_id"):
        horses = []
        for _, row in group.iterrows():
            horses.append({
                "horse_number": int(row["horse_number"]),
                "horse_name": row["horse_name"],
                "pred_proba_accuracy": round(float(row["pred_proba_accuracy"]), 4),
                "pred_proba_value": round(float(row["pred_proba_value"]), 4),
                "pred_top3": int(row["pred_top3_accuracy"]),
                "actual_position": int(row["finish_position"]),
                "actual_top3": int(row["target"]),
                "odds_rank": int(row["odds_rank"]) if not pd.isna(row["odds_rank"]) else None,
                "odds": round(float(row["odds"]), 1) if not pd.isna(row["odds"]) else None,
            })
        horses.sort(key=lambda h: h["pred_proba_accuracy"], reverse=True)

        # Value rank
        value_sorted = sorted(horses, key=lambda h: h["pred_proba_value"], reverse=True)
        for rank, h in enumerate(value_sorted, 1):
            h["value_rank"] = rank

        race_predictions.append({
            "race_id": race_id,
            "date": group.iloc[0]["date"],
            "venue": group.iloc[0]["venue"],
            "grade": group.iloc[0]["grade"],
            "entry_count": int(group.iloc[0]["entry_count"]),
            "horses": horses,
        })

    race_predictions.sort(key=lambda r: r["date"], reverse=True)

    # Value Bet該当馬の全リスト（全テストデータから抽出）
    value_bet_picks = []
    for rp in race_predictions:
        for h in rp["horses"]:
            vr = h.get("value_rank")
            odds_rank = h.get("odds_rank")
            if vr is None or odds_rank is None:
                continue
            gap = odds_rank - vr
            if vr <= 3 and gap >= 2:
                value_bet_picks.append({
                    "race_id": rp["race_id"],
                    "date": rp["date"],
                    "venue": rp["venue"],
                    "grade": rp["grade"],
                    "horse_number": h["horse_number"],
                    "horse_name": h["horse_name"],
                    "value_rank": vr,
                    "odds_rank": odds_rank,
                    "gap": gap,
                    "odds": h.get("odds"),
                    "pred_proba_accuracy": h["pred_proba_accuracy"],
                    "pred_proba_value": h["pred_proba_value"],
                    "actual_position": h["actual_position"],
                    "is_top3": 1 if h["actual_position"] <= 3 else 0,
                })
    value_bet_picks.sort(key=lambda x: (-x["gap"], x["date"]))

    # 的中率分析
    hit_analysis = []
    for n in [1, 2, 3]:
        hits = 0; total = 0
        for rp in race_predictions:
            top_n = rp["horses"][:n]
            if any(h["actual_top3"] == 1 for h in top_n):
                hits += 1
            total += 1
        hit_analysis.append({
            "top_n": n,
            "hit_rate": round(hits / total, 4) if total > 0 else 0,
            "hits": hits, "total": total,
        })

    output = {
        "version": "2.0",
        "model": "LightGBM",
        "experiment": "ml_experiment_v2",
        "created_at": datetime.now().isoformat(),
        "description": "Value Betting Model (dual: 精度+Value)",
        "split": {"train": "2023-2024", "test": "2025"},
        "models": {
            "accuracy": {
                "features": FEATURE_COLS_ALL,
                "metrics": metrics_a,
                "feature_importance": fi_a,
            },
            "value": {
                "features": FEATURE_COLS_VALUE,
                "metrics": metrics_v,
                "feature_importance": fi_v,
            },
        },
        "hit_analysis": hit_analysis,
        "roi_analysis": {
            "accuracy_model": roi_a,
            "value_model": roi_v,
            "value_bets": value_bets,
        },
        "race_predictions": race_predictions[:200],
        "value_bet_picks": value_bet_picks,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output


# =============================================================================
# メイン
# =============================================================================

def main():
    print("=" * 60)
    print("ML Experiment v2: Value Betting Model")
    print("=" * 60)

    data_root = get_keiba_data_root()
    races_dir = get_races_dir()
    target_dir = get_target_data_dir()
    output_path = data_root / "target" / "ml" / "ml_experiment_v2_result.json"

    # --- 1. データ読み込み ---
    print("\n[1/8] データ読み込み中...")
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
    print(f"  レコード数: {len(df):,}, レース数: {df['race_id'].nunique():,}")

    # --- 2. RPCI結合 ---
    print("\n[2/8] RPCI結合中...")
    rpci_map = load_rpci_index(target_dir)
    df["rpci"] = df["race_id"].map(rpci_map)
    rpci_rate = df["rpci"].notna().sum() / len(df) * 100
    print(f"  RPCI結合率: {rpci_rate:.1f}%")

    # --- 3. レーティング派生 ---
    print("\n[3/8] レーティング派生特徴量...")
    df = add_rating_features(df)

    # --- 4. 過去走特徴量 ---
    print("\n[4/8] 過去走特徴量を計算中...")
    history_cache = load_horse_history_cache(target_dir)

    past_features_list = []
    for _, row in df.iterrows():
        race_date = row["date"].replace("/", "")
        pf = compute_past_features(
            row["horse_id"], race_date, row["venue"],
            row["track_type"], row["distance"], history_cache
        )
        # entry_count_change
        if not pd.isna(pf.get("prev_race_entry_count", np.nan)):
            pf["entry_count_change"] = row["entry_count"] - pf["prev_race_entry_count"]
        else:
            pf["entry_count_change"] = np.nan
        past_features_list.append(pf)

    past_df = pd.DataFrame(past_features_list)
    print(f"  past_features shape: {past_df.shape}")

    # 過去走がある馬の割合
    has_history = (past_df["total_career_races"] > 0).sum() / len(past_df) * 100
    print(f"  過去走データあり: {has_history:.1f}%")

    # dfと結合
    for col in past_df.columns:
        df[col] = past_df[col].values

    # --- 5. 調教師特徴量 ---
    print("\n[5/8] 調教師特徴量...")
    trainers, kb_to_jvn = load_trainer_patterns(target_dir)
    df["trainer_top3_rate"] = df["trainer_id"].apply(
        lambda tid: get_trainer_top3_rate(tid, trainers, kb_to_jvn)
    )
    trainer_hit = df["trainer_top3_rate"].notna().sum() / len(df) * 100
    print(f"  調教師マッチ率: {trainer_hit:.1f}%")

    # --- 6. 時系列分割 + 学習 ---
    print("\n[6/8] 時系列分割 + LightGBM学習...")
    train_df, test_df = time_split(df, split_year=2025)
    print(f"  Train: {len(train_df):,} records ({train_df['race_id'].nunique():,} races)")
    print(f"  Test:  {len(test_df):,} records ({test_df['race_id'].nunique():,} races)")

    X_train_all = train_df[FEATURE_COLS_ALL].fillna(-1)
    y_train = train_df["target"]
    X_test_all = test_df[FEATURE_COLS_ALL].fillna(-1)
    y_test = test_df["target"]

    X_train_val = train_df[FEATURE_COLS_VALUE].fillna(-1)
    X_test_val = test_df[FEATURE_COLS_VALUE].fillna(-1)

    print("\n  --- Model A (精度モデル: 全特徴量) ---")
    model_a = train_model(X_train_all, y_train, X_test_all, y_test, "Accuracy")

    print("\n  --- Model B (Valueモデル: 市場系除外) ---")
    model_b = train_model(X_train_val, y_train, X_test_val, y_test, "Value")

    # モデル保存（リアルタイム予測用）
    model_dir = data_root / "target" / "ml"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_a.save_model(str(model_dir / "model_a.txt"))
    model_b.save_model(str(model_dir / "model_b.txt"))
    # 特徴量リストも保存（予測時に同じ順序で読むため）
    model_meta = {
        "features_all": FEATURE_COLS_ALL,
        "features_value": FEATURE_COLS_VALUE,
        "market_features": list(MARKET_FEATURES),
        "created_at": datetime.now().isoformat(),
    }
    with open(model_dir / "model_meta.json", "w", encoding="utf-8") as f:
        json.dump(model_meta, f, ensure_ascii=False, indent=2)
    print(f"  Models saved: {model_dir / 'model_a.txt'}, {model_dir / 'model_b.txt'}")

    # --- 7. 評価 ---
    print("\n[7/8] 評価中...")
    y_proba_a, _, metrics_a, fi_a = evaluate_model(model_a, X_test_all, y_test, FEATURE_COLS_ALL)
    y_proba_v, _, metrics_v, fi_v = evaluate_model(model_b, X_test_val, y_test, FEATURE_COLS_VALUE)

    # ROI分析
    test_df_eval = test_df.copy()
    test_df_eval["pred_proba"] = y_proba_a
    test_df_eval["pred_proba_value"] = y_proba_v
    roi_a = calc_roi_analysis(test_df_eval, "pred_proba")
    roi_v = calc_roi_analysis(test_df_eval, "pred_proba_value")
    value_bets = calc_value_bet_analysis(test_df_eval)

    # --- 8. JSON出力 ---
    print("\n[8/8] JSON出力...")
    export_results(
        test_df, len(train_df), y_proba_a, y_proba_v,
        metrics_a, metrics_v, fi_a, fi_v,
        roi_a, roi_v, value_bets, output_path,
    )

    # サマリー表示
    print("\n" + "=" * 60)
    print("結果サマリー")
    print("=" * 60)
    print(f"\n  --- Model A (精度) ---")
    print(f"  AUC: {metrics_a['auc']}")
    print(f"  Accuracy: {metrics_a['accuracy']}")
    wa = roi_a["top1_win"]
    print(f"  Top1単勝ROI: {wa['roi']}% ({wa['bet_count']}R)")

    print(f"\n  --- Model B (Value) ---")
    print(f"  AUC: {metrics_v['auc']}")
    print(f"  Accuracy: {metrics_v['accuracy']}")
    wv = roi_v["top1_win"]
    print(f"  Top1単勝ROI: {wv['roi']}% ({wv['bet_count']}R)")

    print(f"\n  --- Value Bet (Model Bランク上位 × 人気薄) ---")
    print(f"  {'Gap':>5} {'件数':>6} {'単勝ROI':>8} {'複勝ROI':>8} {'複勝的中':>8}")
    for vb in value_bets["by_rank_gap"]:
        print(f"  {vb['min_gap']:>5} {vb['bet_count']:>6} {vb['win_roi']:>7.1f}% {vb['place_roi']:>7.1f}% {vb['place_hit_rate']*100:>7.1f}%")

    print(f"\n  Output: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
ML リアルタイム予測: 保存済みモデルで当日レースを予測

保存済みの Model A (精度) と Model B (Value) を読み込み、
指定日の integrated JSON から特徴量を構築して予測を出力する。

Usage:
    cd KeibaCICD.TARGET
    python ml/scripts/predict_race.py                  # 今日の日付
    python ml/scripts/predict_race.py --date 2026-02-08 # 指定日
    python ml/scripts/predict_race.py --date 2026-02-08 --race-id 202601060901  # 特定レース
"""

import sys
import argparse
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd
from datetime import datetime, date

import lightgbm as lgb

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from common.config import get_keiba_data_root, get_races_dir, get_target_data_dir


# =============================================================================
# ユーティリティ（ml_experiment_v2.py と共通）
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
# データ読み込み（結果なしでもOK版）
# =============================================================================

def find_race_files(races_dir: Path, target_date: str, race_id: str | None = None) -> list:
    """指定日のintegrated JSONを検索"""
    year, month, day = target_date.split("-")
    day_dir = races_dir / year / month / day / "temp"
    if not day_dir.exists():
        return []

    if race_id:
        specific = day_dir / f"integrated_{race_id}.json"
        return [specific] if specific.exists() else []

    return sorted(day_dir.glob("integrated_*.json"))


def extract_entries_for_prediction(data: dict) -> list:
    """レースデータから予測用エントリを抽出（結果不要）"""
    race_info = data.get("race_info", {})
    meta = data.get("meta", {})
    race_id = meta.get("race_id", "")
    date_str = race_info.get("date", "")
    entries = data.get("entries", [])
    if not entries:
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
        td = e.get("training_data", {})

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
            "race_name": race_info.get("race_name", ""),
            "race_number": race_info.get("race_number", 0),
        })

    return rows


# =============================================================================
# 過去走特徴量（ml_experiment_v2.py と同一ロジック）
# =============================================================================

def load_horse_history_cache(target_dir: Path) -> dict:
    path = target_dir / "ml" / "horse_history_cache.json"
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["horses"]


def compute_past_features(horse_id: str, race_date: str, venue: str,
                          track_type: int, distance: int,
                          history_cache: dict) -> dict:
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

    past = [h for h in history if h["race_date"] < race_date]
    if not past:
        return result

    n = len(past)
    result["total_career_races"] = n

    last3 = past[-3:] if n >= 3 else past
    last5 = past[-5:] if n >= 5 else past

    positions_last3 = [h["finish_position"] for h in last3]
    result["avg_finish_last3"] = np.mean(positions_last3)
    result["best_finish_last5"] = min(h["finish_position"] for h in last5)

    l3f_vals = [h["last_3f"] for h in last3 if h.get("last_3f") is not None]
    if l3f_vals:
        result["last3f_avg_last3"] = round(np.mean(l3f_vals), 1)

    try:
        last_date = datetime.strptime(past[-1]["race_date"], "%Y%m%d")
        current_date = datetime.strptime(race_date, "%Y%m%d")
        result["days_since_last_race"] = (current_date - last_date).days
    except (ValueError, TypeError):
        pass

    wins = sum(1 for h in past if h["finish_position"] == 1)
    top3s = sum(1 for h in past if h["finish_position"] <= 3)
    result["win_rate_all"] = round(wins / n, 4)
    result["top3_rate_all"] = round(top3s / n, 4)

    if len(positions_last3) >= 2:
        result["recent_form_trend"] = positions_last3[0] - positions_last3[-1]

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

    result["prev_race_entry_count"] = past[-1].get("entry_count", np.nan)

    last3_ratings = [h["rating"] for h in last3 if h.get("rating") is not None]
    if len(last3_ratings) >= 2:
        result["rating_trend_last3"] = round(last3_ratings[-1] - last3_ratings[0], 1)

    return result


# =============================================================================
# 調教師・RPCI・レーティング派生
# =============================================================================

def load_trainer_patterns(target_dir: Path) -> tuple:
    path = target_dir / "trainer_patterns.json"
    if not path.exists():
        return {}, {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    trainers = data.get("trainers", {})
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
# メイン予測
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ML Race Prediction")
    parser.add_argument("--date", type=str, default=None,
                        help="Date to predict (YYYY-MM-DD). Default: today")
    parser.add_argument("--race-id", type=str, default=None,
                        help="Specific race ID to predict")
    args = parser.parse_args()

    target_date = args.date or date.today().strftime("%Y-%m-%d")
    print("=" * 60)
    print(f"ML Race Prediction: {target_date}")
    print("=" * 60)

    data_root = get_keiba_data_root()
    races_dir = get_races_dir()
    target_dir = get_target_data_dir()
    model_dir = data_root / "target" / "ml"

    # --- 1. モデル読み込み ---
    print("\n[1/6] モデル読み込み...")
    model_a_path = model_dir / "model_a.txt"
    model_b_path = model_dir / "model_b.txt"
    meta_path = model_dir / "model_meta.json"

    if not model_a_path.exists() or not model_b_path.exists() or not meta_path.exists():
        print("  ERROR: 保存済みモデルが見つかりません。先に ml_experiment_v2.py を実行してください。")
        sys.exit(1)

    model_a = lgb.Booster(model_file=str(model_a_path))
    model_b = lgb.Booster(model_file=str(model_b_path))
    with open(meta_path, "r", encoding="utf-8") as f:
        model_meta = json.load(f)

    features_all = model_meta["features_all"]
    features_value = model_meta["features_value"]
    print(f"  Model A: {len(features_all)} features, Model B: {len(features_value)} features")

    # --- 2. レースデータ読み込み ---
    print("\n[2/6] レースデータ読み込み...")
    files = find_race_files(races_dir, target_date, args.race_id)
    if not files:
        print(f"  WARNING: {target_date} のレースデータが見つかりません")
        # 空の結果を出力
        output = {
            "date": target_date,
            "created_at": datetime.now().isoformat(),
            "races": [],
        }
        output_path = model_dir / "predictions_live.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  Output (empty): {output_path}")
        return

    all_rows = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            rows = extract_entries_for_prediction(data)
            all_rows.extend(rows)
        except Exception as e:
            print(f"  ERROR: {fp.name}: {e}")

    if not all_rows:
        print("  WARNING: 有効なエントリがありません")
        return

    df = pd.DataFrame(all_rows)
    print(f"  レコード数: {len(df):,}, レース数: {df['race_id'].nunique():,}")

    # --- 3. RPCI結合 ---
    print("\n[3/6] RPCI結合...")
    rpci_map = load_rpci_index(target_dir)
    df["rpci"] = df["race_id"].map(rpci_map)

    # --- 4. レーティング派生 ---
    print("\n[4/6] レーティング派生特徴量...")
    df = add_rating_features(df)

    # --- 5. 過去走特徴量 ---
    print("\n[5/6] 過去走特徴量...")
    history_cache = load_horse_history_cache(target_dir)

    past_features_list = []
    for _, row in df.iterrows():
        race_date = row["date"].replace("/", "")
        pf = compute_past_features(
            row["horse_id"], race_date, row["venue"],
            row["track_type"], row["distance"], history_cache
        )
        if not pd.isna(pf.get("prev_race_entry_count", np.nan)):
            pf["entry_count_change"] = row["entry_count"] - pf["prev_race_entry_count"]
        else:
            pf["entry_count_change"] = np.nan
        past_features_list.append(pf)

    past_df = pd.DataFrame(past_features_list)
    for col in past_df.columns:
        df[col] = past_df[col].values

    # 調教師特徴量
    trainers, kb_to_jvn = load_trainer_patterns(target_dir)
    df["trainer_top3_rate"] = df["trainer_id"].apply(
        lambda tid: get_trainer_top3_rate(tid, trainers, kb_to_jvn)
    )

    # --- 6. 予測 ---
    print("\n[6/6] 予測実行...")
    X_all = df[features_all].fillna(-1)
    X_val = df[features_value].fillna(-1)

    df["pred_proba_accuracy"] = model_a.predict(X_all)
    df["pred_proba_value"] = model_b.predict(X_val)

    # レース単位で結果をまとめる
    race_predictions = []
    for race_id, group in df.groupby("race_id"):
        horses = []
        for _, row in group.iterrows():
            horses.append({
                "horse_number": int(row["horse_number"]),
                "horse_name": row["horse_name"],
                "pred_proba_accuracy": round(float(row["pred_proba_accuracy"]), 4),
                "pred_proba_value": round(float(row["pred_proba_value"]), 4),
                "odds_rank": int(row["odds_rank"]) if not pd.isna(row["odds_rank"]) else None,
                "odds": round(float(row["odds"]), 1) if not pd.isna(row["odds"]) else None,
            })

        # Accuracy model でソート
        horses.sort(key=lambda h: h["pred_proba_accuracy"], reverse=True)

        # Value rank
        value_sorted = sorted(horses, key=lambda h: h["pred_proba_value"], reverse=True)
        for rank, h in enumerate(value_sorted, 1):
            h["value_rank"] = rank

        # Value Bet判定
        for h in horses:
            vr = h.get("value_rank")
            odr = h.get("odds_rank")
            if vr is not None and odr is not None:
                h["gap"] = odr - vr
                h["is_value_bet"] = vr <= 3 and (odr - vr) >= 3
            else:
                h["gap"] = None
                h["is_value_bet"] = False

        first_row = group.iloc[0]
        race_predictions.append({
            "race_id": race_id,
            "date": first_row["date"],
            "venue": first_row["venue"],
            "grade": first_row["grade"],
            "race_name": first_row.get("race_name", ""),
            "race_number": int(first_row.get("race_number", 0)),
            "entry_count": int(first_row["entry_count"]),
            "horses": horses,
        })

    race_predictions.sort(key=lambda r: r.get("race_number", 0))

    # JSON出力
    output = {
        "date": target_date,
        "created_at": datetime.now().isoformat(),
        "model_meta": {
            "model_a_features": len(features_all),
            "model_b_features": len(features_value),
        },
        "races": race_predictions,
    }

    output_path = model_dir / "predictions_live.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # サマリー表示
    print("\n" + "=" * 60)
    print(f"予測結果: {len(race_predictions)} レース")
    print("=" * 60)
    for rp in race_predictions:
        vb_horses = [h for h in rp["horses"] if h.get("is_value_bet")]
        vb_str = ""
        if vb_horses:
            vb_names = [f"{h['horse_name']}(VR{h['value_rank']} Gap{h['gap']})" for h in vb_horses]
            vb_str = f"  VB: {', '.join(vb_names)}"
        print(f"  {rp['venue']}{rp['race_number']}R {rp.get('race_name', '')[:12]:12s} ({rp['entry_count']}頭){vb_str}")

    print(f"\n  Output: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

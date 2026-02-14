"""
Value Bet バックテスト分析
===========================
experiment_v3_result.json のテストセット予測データを使い、
フィルタ条件の全組み合わせで単勝/複勝ROIを算出する。

芝/ダート別分析によりモデル分離の必要性も検証する。

Usage:
  python -m ml.backtest_vb
  python -m ml.backtest_vb --version v4.0
  python -m ml.backtest_vb --db-place-odds   # mykeibadbから実複勝オッズ取得
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from itertools import product
from typing import Dict, List, Optional, Tuple

# ── Config ──────────────────────────────────────────────
DATA3_ROOT = "C:/KEIBA-CICD/data3"
ML_VERSIONS_DIR = os.path.join(DATA3_ROOT, "ml/versions")

# フィルタ条件の軸
GAP_THRESHOLDS = [2, 3, 4, 5, 6]
EV_THRESHOLDS = [0.0, 0.8, 1.0, 1.2, 1.5]  # 0.0 = フィルタなし
PROBA_A_THRESHOLDS = [0.0, 0.05, 0.08, 0.10, 0.15]  # Model A確率
PROBA_V_THRESHOLDS = [0.0, 0.05, 0.08, 0.10, 0.15]  # Model B確率
ODDS_RANGES = [
    ("all", 0, 9999),
    ("1-5", 1, 5),
    ("5-10", 5, 10),
    ("10-30", 10, 30),
    ("30-100", 30, 100),
    ("100+", 100, 9999),
]
VALUE_RANK_FILTERS = [0, 1, 2, 3]  # 0 = フィルタなし, 1 = top1のみ, etc.
TRACK_TYPES = ["all", "turf", "dirt"]


def load_experiment_data(version: str) -> dict:
    """実験結果JSONを読み込み"""
    path = os.path.join(ML_VERSIONS_DIR, version, "ml_experiment_v3_result.json")
    if not os.path.exists(path):
        print(f"Error: {path} not found")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_race_metadata(race_ids: List[str]) -> Dict[str, dict]:
    """race JSONからtrack_type, distanceを取得"""
    metadata = {}
    for rid in race_ids:
        rid_str = str(rid)
        y, m, d = rid_str[:4], rid_str[4:6], rid_str[6:8]
        race_path = os.path.join(DATA3_ROOT, f"races/{y}/{m}/{d}/race_{rid_str}.json")
        if os.path.exists(race_path):
            try:
                with open(race_path, "r", encoding="utf-8") as f:
                    race = json.load(f)
                metadata[rid_str] = {
                    "track_type": race.get("track_type", ""),
                    "distance": race.get("distance", 0),
                    "race_name": race.get("race_name", ""),
                    "entry_count": len(race.get("entries", [])),
                }
            except Exception:
                pass
    return metadata


def load_db_place_odds() -> Dict[str, Dict[int, float]]:
    """mykeibadbから確定複勝オッズを取得（2025年以降）"""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="test123!",
            database="mykeibadb",
            charset="utf8mb4",
        )
        cursor = conn.cursor()
        cursor.execute("""
            SELECT RACE_CODE, UMABAN, ODDS_SAITEI
            FROM odds1_fukusho
            WHERE RACE_CODE >= '2025010100000000'
        """)
        place_odds = defaultdict(dict)
        for race_code, umaban, odds_saitei in cursor:
            try:
                odds_val = float(odds_saitei) / 10.0 if odds_saitei and odds_saitei.strip() not in ('----', '****', '0000', '') else 0
                if odds_val > 0:
                    place_odds[str(race_code).strip()][int(umaban)] = odds_val
            except (ValueError, TypeError):
                pass
        cursor.close()
        conn.close()
        print(f"  DB複勝オッズ: {len(place_odds)} races loaded")
        return dict(place_odds)
    except Exception as e:
        print(f"  DB複勝オッズ取得失敗: {e}")
        return {}


def build_horse_records(
    exp_data: dict,
    race_meta: Dict[str, dict],
    db_place_odds: Dict[str, Dict[int, float]],
) -> List[dict]:
    """全馬のフラットレコードを構築"""
    records = []
    for race in exp_data["race_predictions"]:
        rid = str(race["race_id"])
        meta = race_meta.get(rid, {})
        track_type = meta.get("track_type", "")
        distance = meta.get("distance", 0)
        entry_count = race.get("entry_count", meta.get("entry_count", 0))

        if not track_type:  # 未確定レース除外
            continue

        race_place_odds = db_place_odds.get(rid, {})

        for h in race["horses"]:
            odds = h.get("odds", 0) or 0
            pred_a = h.get("pred_proba_accuracy", 0) or 0
            pred_v = h.get("pred_proba_value", 0) or 0
            odds_rank = h.get("odds_rank", 0) or 0
            value_rank = h.get("value_rank", 0) or 0
            actual_pos = h.get("actual_position", 0) or 0
            is_top3 = h.get("actual_top3", 0) or 0
            is_win = 1 if actual_pos == 1 else 0

            # VB gap
            gap = odds_rank - value_rank if odds_rank > 0 and value_rank > 0 else 0

            # EV = pred_v × odds (レース内正規化済み確率)
            ev = pred_v * odds if odds > 0 else 0

            # 複勝オッズ: DB実値 or 簡易推定
            umaban = h.get("horse_number", 0)
            db_po = race_place_odds.get(umaban, 0)
            est_po = max(odds / 3.5, 1.1) if odds > 0 else 0

            # 複勝的中判定（頭数ルール）
            if entry_count >= 8:
                place_hit = 1 if actual_pos in (1, 2, 3) else 0
            elif entry_count >= 5:
                place_hit = 1 if actual_pos in (1, 2) else 0
            else:
                place_hit = 0  # 4頭以下は複勝なし

            records.append({
                "race_id": rid,
                "date": race.get("date", ""),
                "track_type": track_type,
                "distance": distance,
                "entry_count": entry_count,
                "umaban": umaban,
                "horse_name": h.get("horse_name", ""),
                "odds": odds,
                "odds_rank": odds_rank,
                "pred_a": pred_a,
                "pred_v": pred_v,
                "value_rank": value_rank,
                "gap": gap,
                "ev": ev,
                "actual_pos": actual_pos,
                "is_win": is_win,
                "is_top3": is_top3,
                "place_hit": place_hit,
                "place_odds_db": db_po,
                "place_odds_est": est_po,
            })
    return records


def calc_roi(
    records: List[dict],
    track_filter: str = "all",
    min_gap: int = 3,
    min_ev: float = 0.0,
    min_proba_a: float = 0.0,
    min_proba_v: float = 0.0,
    odds_range: Tuple[str, float, float] = ("all", 0, 9999),
    max_value_rank: int = 0,  # 0=no filter
    use_db_odds: bool = False,
) -> Optional[dict]:
    """条件でフィルタ後のROIを計算"""
    _, odds_lo, odds_hi = odds_range

    filtered = []
    for r in records:
        # Track filter
        if track_filter != "all" and r["track_type"] != track_filter:
            continue
        # VB candidates: value_rank <= 3 and gap >= threshold
        if r["value_rank"] > 3 or r["value_rank"] <= 0:
            continue
        if r["gap"] < min_gap:
            continue
        if r["odds_rank"] <= 0:
            continue
        # Additional filters
        if min_ev > 0 and r["ev"] < min_ev:
            continue
        if min_proba_a > 0 and r["pred_a"] < min_proba_a:
            continue
        if min_proba_v > 0 and r["pred_v"] < min_proba_v:
            continue
        if not (odds_lo <= r["odds"] < odds_hi):
            continue
        if max_value_rank > 0 and r["value_rank"] > max_value_rank:
            continue
        filtered.append(r)

    n = len(filtered)
    if n < 5:  # サンプル少なすぎは除外
        return None

    total_bet = n * 100
    win_return = sum(r["odds"] * 100 for r in filtered if r["is_win"] == 1)
    win_hits = sum(1 for r in filtered if r["is_win"] == 1)

    place_hits = sum(1 for r in filtered if r["place_hit"] == 1)

    if use_db_odds:
        place_return = sum(
            r["place_odds_db"] * 100
            for r in filtered
            if r["place_hit"] == 1 and r["place_odds_db"] > 0
        )
        # DB未対応の的中分は推定で補完
        place_return += sum(
            r["place_odds_est"] * 100
            for r in filtered
            if r["place_hit"] == 1 and r["place_odds_db"] == 0
        )
    else:
        place_return = sum(
            r["place_odds_est"] * 100
            for r in filtered
            if r["place_hit"] == 1
        )

    win_roi = win_return / total_bet * 100 if total_bet > 0 else 0
    place_roi = place_return / total_bet * 100 if total_bet > 0 else 0
    win_profit = win_return - total_bet
    place_profit = place_return - total_bet

    # 的中レース数（ユニーク）
    win_races = len(set(r["race_id"] for r in filtered if r["is_win"] == 1))
    place_races = len(set(r["race_id"] for r in filtered if r["place_hit"] == 1))

    return {
        "n_bets": n,
        "win_hits": win_hits,
        "win_roi": round(win_roi, 1),
        "win_profit": round(win_profit),
        "place_hits": place_hits,
        "place_hit_rate": round(place_hits / n * 100, 1) if n > 0 else 0,
        "place_roi": round(place_roi, 1),
        "place_profit": round(place_profit),
    }


def run_grid_search(records: List[dict], use_db_odds: bool = False) -> List[dict]:
    """全条件組み合わせのグリッドサーチ"""
    results = []
    total_combos = (
        len(TRACK_TYPES) * len(GAP_THRESHOLDS) * len(EV_THRESHOLDS)
        * len(PROBA_A_THRESHOLDS) * len(PROBA_V_THRESHOLDS)
        * len(ODDS_RANGES) * len(VALUE_RANK_FILTERS)
    )
    print(f"\nGrid search: {total_combos} combinations...")

    count = 0
    for track, gap, ev, pa, pv, odds_range, vrank in product(
        TRACK_TYPES, GAP_THRESHOLDS, EV_THRESHOLDS,
        PROBA_A_THRESHOLDS, PROBA_V_THRESHOLDS,
        ODDS_RANGES, VALUE_RANK_FILTERS,
    ):
        count += 1
        if count % 5000 == 0:
            print(f"  {count}/{total_combos}...")

        roi = calc_roi(
            records,
            track_filter=track,
            min_gap=gap,
            min_ev=ev,
            min_proba_a=pa,
            min_proba_v=pv,
            odds_range=odds_range,
            max_value_rank=vrank,
            use_db_odds=use_db_odds,
        )
        if roi is None:
            continue

        results.append({
            "track": track,
            "gap": f">={gap}",
            "ev": f">={ev}" if ev > 0 else "-",
            "proba_a": f">={pa:.0%}" if pa > 0 else "-",
            "proba_v": f">={pv:.0%}" if pv > 0 else "-",
            "odds": odds_range[0],
            "vrank": f"top{vrank}" if vrank > 0 else "-",
            **roi,
        })

    return results


def print_section(title: str, results: List[dict], sort_key: str, top_n: int = 20):
    """結果セクション表示"""
    print(f"\n{'='*100}")
    print(f" {title}")
    print(f"{'='*100}")

    sorted_results = sorted(results, key=lambda x: x[sort_key], reverse=True)[:top_n]

    header = (
        f"{'Track':<6} {'Gap':<5} {'EV':<6} {'A%':<7} {'V%':<7} {'Odds':<8} {'VRank':<6} "
        f"{'N':>5} {'W-Hit':>6} {'W-ROI':>7} {'W-Profit':>10} "
        f"{'P-Hit':>6} {'P-Rate':>7} {'P-ROI':>7} {'P-Profit':>10}"
    )
    print(header)
    print("-" * len(header))

    for r in sorted_results:
        print(
            f"{r['track']:<6} {r['gap']:<5} {r['ev']:<6} {r['proba_a']:<7} {r['proba_v']:<7} "
            f"{r['odds']:<8} {r['vrank']:<6} "
            f"{r['n_bets']:>5} {r['win_hits']:>6} {r['win_roi']:>6.1f}% {r['win_profit']:>+10,} "
            f"{r['place_hits']:>6} {r['place_hit_rate']:>6.1f}% {r['place_roi']:>6.1f}% {r['place_profit']:>+10,}"
        )


def print_track_comparison(records: List[dict], use_db_odds: bool = False):
    """芝/ダート比較（モデル分離判断用）"""
    print(f"\n{'='*100}")
    print(" 芝/ダート比較分析（モデル分離判断）")
    print(f"{'='*100}")

    for gap in [2, 3, 4, 5]:
        print(f"\n--- Gap >= {gap} ---")
        header = f"{'Track':<8} {'N':>6} {'W-Hit':>6} {'W-ROI':>8} {'P-Hit':>6} {'P-Rate':>8} {'P-ROI':>8}"
        print(header)
        print("-" * len(header))
        for track in ["all", "turf", "dirt"]:
            roi = calc_roi(records, track_filter=track, min_gap=gap, use_db_odds=use_db_odds)
            if roi:
                print(
                    f"{track:<8} {roi['n_bets']:>6} {roi['win_hits']:>6} "
                    f"{roi['win_roi']:>7.1f}% {roi['place_hits']:>6} "
                    f"{roi['place_hit_rate']:>7.1f}% {roi['place_roi']:>7.1f}%"
                )

    # 距離帯別
    print(f"\n--- Gap >= 3, 距離帯別 ---")
    dist_ranges = [
        ("sprint", 1000, 1400),
        ("mile", 1400, 1800),
        ("mid", 1800, 2200),
        ("long", 2200, 4000),
    ]
    header = f"{'Track':<8} {'Dist':<8} {'N':>6} {'W-Hit':>6} {'W-ROI':>8} {'P-Hit':>6} {'P-Rate':>8} {'P-ROI':>8}"
    print(header)
    print("-" * len(header))
    for track in ["turf", "dirt"]:
        for dist_name, dist_lo, dist_hi in dist_ranges:
            filtered = [
                r for r in records
                if r["track_type"] == track
                and r["value_rank"] <= 3
                and r["gap"] >= 3
                and r["odds_rank"] > 0
                and dist_lo <= r["distance"] < dist_hi
            ]
            n = len(filtered)
            if n < 5:
                continue
            total_bet = n * 100
            win_return = sum(r["odds"] * 100 for r in filtered if r["is_win"] == 1)
            win_hits = sum(1 for r in filtered if r["is_win"] == 1)
            place_hits = sum(1 for r in filtered if r["place_hit"] == 1)
            place_return = sum(r["place_odds_est"] * 100 for r in filtered if r["place_hit"] == 1)
            print(
                f"{track:<8} {dist_name:<8} {n:>6} {win_hits:>6} "
                f"{win_return/total_bet*100:>7.1f}% {place_hits:>6} "
                f"{place_hits/n*100:>7.1f}% {place_return/total_bet*100:>7.1f}%"
            )


def print_model_b_top1_analysis(records: List[dict], use_db_odds: bool = False):
    """Model B Top1 単勝ROI分析（ユーザーの重点関心事項）"""
    print(f"\n{'='*100}")
    print(" Model B Top1 単勝ROI分析")
    print(f"{'='*100}")

    for track in ["all", "turf", "dirt"]:
        print(f"\n--- {track.upper()} ---")
        header = f"{'Filter':<30} {'N':>6} {'W-Hit':>6} {'W-ROI':>8} {'W-Profit':>10} {'P-Hit':>6} {'P-ROI':>8}"
        print(header)
        print("-" * len(header))

        # Model B Top1 (= value_rank == 1), さまざまなサブフィルタ
        filters = [
            ("Top1 全体", lambda r: r["value_rank"] == 1),
            ("Top1 + odds>=3", lambda r: r["value_rank"] == 1 and r["odds"] >= 3),
            ("Top1 + odds>=5", lambda r: r["value_rank"] == 1 and r["odds"] >= 5),
            ("Top1 + odds>=10", lambda r: r["value_rank"] == 1 and r["odds"] >= 10),
            ("Top1 + gap>=2", lambda r: r["value_rank"] == 1 and r["gap"] >= 2),
            ("Top1 + gap>=3", lambda r: r["value_rank"] == 1 and r["gap"] >= 3),
            ("Top1 + gap>=5", lambda r: r["value_rank"] == 1 and r["gap"] >= 5),
            ("Top1 + A%>=10%", lambda r: r["value_rank"] == 1 and r["pred_a"] >= 0.10),
            ("Top1 + A%>=15%", lambda r: r["value_rank"] == 1 and r["pred_a"] >= 0.15),
            ("Top1 + EV>=1.0", lambda r: r["value_rank"] == 1 and r["ev"] >= 1.0),
            ("Top1 + EV>=1.5", lambda r: r["value_rank"] == 1 and r["ev"] >= 1.5),
            ("Top1 + gap>=3 + A%>=10%", lambda r: r["value_rank"] == 1 and r["gap"] >= 3 and r["pred_a"] >= 0.10),
            ("Top1 + gap>=3 + EV>=1.0", lambda r: r["value_rank"] == 1 and r["gap"] >= 3 and r["ev"] >= 1.0),
            ("Top1 + gap>=5 + odds>=10", lambda r: r["value_rank"] == 1 and r["gap"] >= 5 and r["odds"] >= 10),
        ]

        for name, cond in filters:
            filtered = [
                r for r in records
                if cond(r)
                and r["odds_rank"] > 0
                and (track == "all" or r["track_type"] == track)
            ]
            n = len(filtered)
            if n < 3:
                print(f"{name:<30} {'(n<3)':>6}")
                continue
            total_bet = n * 100
            win_return = sum(r["odds"] * 100 for r in filtered if r["is_win"] == 1)
            win_hits = sum(1 for r in filtered if r["is_win"] == 1)
            place_hits = sum(1 for r in filtered if r["place_hit"] == 1)
            place_return = sum(r["place_odds_est"] * 100 for r in filtered if r["place_hit"] == 1)
            win_profit = win_return - total_bet
            print(
                f"{name:<30} {n:>6} {win_hits:>6} "
                f"{win_return/total_bet*100:>7.1f}% {win_profit:>+10,.0f} "
                f"{place_hits:>6} {place_return/total_bet*100:>7.1f}%"
            )


def main():
    parser = argparse.ArgumentParser(description="Value Bet Backtest")
    parser.add_argument("--version", default="v4.0", help="Model version (default: v4.0)")
    parser.add_argument("--db-place-odds", action="store_true", help="Use mykeibadb place odds")
    args = parser.parse_args()

    print("=" * 100)
    print(f" Value Bet バックテスト分析 (model {args.version})")
    print("=" * 100)

    # 1. データ読み込み
    print("\n[1] 実験結果JSON読み込み...")
    exp = load_experiment_data(args.version)
    print(f"  レース数: {len(exp['race_predictions'])}")
    print(f"  VB picks (gap>=3): {len(exp['value_bet_picks'])}")

    # 2. race JSONからメタデータ取得
    print("\n[2] レースメタデータ読み込み...")
    race_ids = [str(r["race_id"]) for r in exp["race_predictions"]]
    race_meta = load_race_metadata(race_ids)
    print(f"  メタデータ取得: {len(race_meta)} races")

    # Track type distribution
    from collections import Counter
    tt_dist = Counter(m["track_type"] for m in race_meta.values() if m["track_type"])
    print(f"  芝: {tt_dist.get('turf', 0)}, ダート: {tt_dist.get('dirt', 0)}")

    # 3. DB複勝オッズ（オプション）
    db_place_odds = {}
    if args.db_place_odds:
        print("\n[3] DB複勝オッズ読み込み...")
        db_place_odds = load_db_place_odds()

    # 4. レコード構築
    print("\n[4] 分析レコード構築...")
    records = build_horse_records(exp, race_meta, db_place_odds)
    print(f"  総レコード数: {len(records)}")

    vb_records = [r for r in records if r["value_rank"] <= 3 and r["gap"] >= 2 and r["odds_rank"] > 0]
    print(f"  VB候補 (gap>=2): {len(vb_records)}")

    # ━━━ 分析出力 ━━━

    # A. 芝/ダート比較
    print_track_comparison(records, use_db_odds=bool(db_place_odds))

    # B. Model B Top1分析
    print_model_b_top1_analysis(records, use_db_odds=bool(db_place_odds))

    # C. グリッドサーチ
    grid_results = run_grid_search(records, use_db_odds=bool(db_place_odds))
    print(f"\n有効な条件組み合わせ: {len(grid_results)}")

    # D. 結果表示
    # サンプル数20以上に絞る
    robust = [r for r in grid_results if r["n_bets"] >= 20]
    print(f"  N>=20の条件: {len(robust)}")

    print_section("単勝ROI Top20 (N>=20)", robust, "win_roi")
    print_section("複勝ROI Top20 (N>=20)", robust, "place_roi")
    print_section("単勝利益 Top20 (N>=20)", robust, "win_profit")
    print_section("複勝利益 Top20 (N>=20)", robust, "place_profit")

    # E. 安定条件（N>=50 かつ ROI>=100%）
    stable_win = [r for r in grid_results if r["n_bets"] >= 50 and r["win_roi"] >= 100]
    stable_place = [r for r in grid_results if r["n_bets"] >= 50 and r["place_roi"] >= 100]
    print_section(f"安定: 単勝ROI>=100% & N>=50 ({len(stable_win)}件)", stable_win, "win_roi")
    print_section(f"安定: 複勝ROI>=100% & N>=50 ({len(stable_place)}件)", stable_place, "place_roi")

    # F. 結果をJSONファイルに保存
    output_path = os.path.join(DATA3_ROOT, "ml", "backtest_vb_results.json")
    output = {
        "version": args.version,
        "total_races": len(exp["race_predictions"]),
        "total_records": len(records),
        "grid_results_count": len(grid_results),
        "robust_count": len(robust),
        "top_win_roi": sorted(robust, key=lambda x: x["win_roi"], reverse=True)[:50],
        "top_place_roi": sorted(robust, key=lambda x: x["place_roi"], reverse=True)[:50],
        "top_win_profit": sorted(robust, key=lambda x: x["win_profit"], reverse=True)[:50],
        "top_place_profit": sorted(robust, key=lambda x: x["place_profit"], reverse=True)[:50],
        "stable_win": sorted(stable_win, key=lambda x: x["win_roi"], reverse=True),
        "stable_place": sorted(stable_place, key=lambda x: x["place_roi"], reverse=True),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n結果保存: {output_path}")

    print("\n完了!")


if __name__ == "__main__":
    main()

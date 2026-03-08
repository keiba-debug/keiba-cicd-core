"""
基準オッズ クロス分析 v2

目的: 「来る馬をより正確に推奨する」ための基準オッズ活用法を探る
- ARd × オッズ変動 → 複勝率向上の可能性
- モデルランク × smart money → 見逃し馬の発掘
- race_confidence × オッズ変動 → 自信度補正
- 3着内的中率の最大化（馬連・三連複を見据えて）
"""

import json
import glob
import numpy as np
from collections import defaultdict

DATA_DIR = "C:/KEIBA-CICD/data3"


def load_all_data():
    """Load KYI, races, predictions"""
    print("Loading data...")

    with open(f"{DATA_DIR}/indexes/jrdb_kyi_index.json", encoding="utf-8") as f:
        kyi = json.load(f)
    print(f"  KYI: {len(kyi)} entries")

    races = []
    for year in range(2024, 2026):
        for fpath in glob.glob(f"{DATA_DIR}/races/{year}/**/race_[0-9]*.json", recursive=True):
            with open(fpath, encoding="utf-8") as f:
                race = json.load(f)
            has_results = any(
                e.get("finish_position") and e["finish_position"] > 0
                for e in race.get("entries", [])
            )
            if has_results and race.get("num_runners", 0) >= 5:
                races.append(race)
    print(f"  Races: {len(races)}")

    pred_index = {}
    for year in range(2024, 2026):
        for fpath in glob.glob(f"{DATA_DIR}/races/{year}/**/predictions.json", recursive=True):
            try:
                with open(fpath, encoding="utf-8") as f:
                    pdata = json.load(f)
                for r in pdata.get("races", []):
                    rid = r.get("race_id")
                    if rid:
                        entry_map = {}
                        for e in r.get("entries", []):
                            entry_map[e.get("umaban")] = e
                        pred_index[rid] = {
                            "entries": entry_map,
                            "race_confidence": r.get("race_confidence"),
                        }
            except Exception:
                continue
    print(f"  Predictions: {len(pred_index)} races")

    return kyi, races, pred_index


def build_records(kyi, races, pred_index):
    """Build analysis records"""
    records = []
    race_records = defaultdict(list)  # race_id -> [records]

    for race in races:
        race_id = race.get("race_id", "")
        date = race.get("date", "")
        track_type = race.get("track_type", "")
        if "障" in race.get("race_name", "") or track_type == "障害":
            continue

        pred_race = pred_index.get(race_id, {})
        pred_entries = pred_race.get("entries", {})
        race_confidence = pred_race.get("race_confidence")

        for entry in race.get("entries", []):
            ketto_num = entry.get("ketto_num", "")
            umaban = entry.get("umaban")
            finish_pos = entry.get("finish_position")
            actual_odds = entry.get("odds")

            if not ketto_num or not finish_pos or not actual_odds:
                continue
            if finish_pos <= 0 or actual_odds <= 0:
                continue

            kyi_data = kyi.get(f"{ketto_num}_{date}")
            if not kyi_data:
                continue
            base_odds = kyi_data.get("base_odds")
            if not base_odds or base_odds <= 0:
                continue

            pred = pred_entries.get(umaban, {})
            ar_deviation = pred.get("ar_deviation")
            rank_p = pred.get("rank_p")
            rank_w = pred.get("rank_w")
            pred_proba_w = pred.get("pred_proba_w_cal")
            pred_proba_p = pred.get("pred_proba_p")
            win_ev = pred.get("win_ev")
            is_vb = pred.get("is_value_bet", False)
            dev_gap = pred.get("dev_gap")

            odds_move = actual_odds / base_odds
            base_pop = kyi_data.get("base_popularity")

            rec = {
                "race_id": race_id,
                "date": date,
                "umaban": umaban,
                "finish_pos": finish_pos,
                "is_win": finish_pos == 1,
                "is_top3": finish_pos <= 3,
                "actual_odds": actual_odds,
                "base_odds": base_odds,
                "base_pop": base_pop,
                "odds_move": odds_move,
                "ar_deviation": ar_deviation,
                "rank_p": rank_p,
                "rank_w": rank_w,
                "pred_proba_w": pred_proba_w,
                "pred_proba_p": pred_proba_p,
                "win_ev": win_ev,
                "is_vb": is_vb,
                "dev_gap": dev_gap,
                "race_confidence": race_confidence,
                "num_runners": race.get("num_runners", 0),
                "track_type": track_type,
                "kyakushitsu": kyi_data.get("kyakushitsu"),
                "pre_idm": kyi_data.get("pre_idm"),
            }
            records.append(rec)
            race_records[race_id].append(rec)

    print(f"\nTotal records: {len(records)}")
    print(f"Total races: {len(race_records)}")
    return records, race_records


def print_table(label, n, wins, top3, win_ret, avg_odds=None):
    """Helper to print a stats row"""
    if n < 20:
        print(f"  {label:<30} n={n:>5} (sample too small)")
        return
    wr = wins / n * 100
    tr = top3 / n * 100
    roi = win_ret / n * 100
    extra = f" avgOdds={avg_odds:.1f}" if avg_odds else ""
    print(f"  {label:<30} n={n:>5} Win{wr:>5.1f}% Top3{tr:>5.1f}% ROI{roi:>6.1f}%{extra}")


def calc_stats(subset):
    """Calculate stats for a subset"""
    n = len(subset)
    wins = sum(1 for r in subset if r["is_win"])
    top3 = sum(1 for r in subset if r["is_top3"])
    win_ret = sum(r["actual_odds"] for r in subset if r["is_win"])
    return n, wins, top3, win_ret


def analyze_cross(records, race_records):
    """Main cross analysis"""

    # =============================================
    # 分析A: ARd段階 x オッズ変動 → 複勝率
    # =============================================
    print(f"\n{'='*70}")
    print("分析A: ARdレベル x オッズ変動 -> 複勝率 (3着内的中)")
    print("目的: モデル評価が高い馬で、smart moneyが入った馬はさらに信頼できるか")
    print(f"{'='*70}")

    ard_bins = [
        ("ARd 65+", lambda r: r["ar_deviation"] and r["ar_deviation"] >= 65),
        ("ARd 55-64", lambda r: r["ar_deviation"] and 55 <= r["ar_deviation"] < 65),
        ("ARd 45-54", lambda r: r["ar_deviation"] and 45 <= r["ar_deviation"] < 55),
        ("ARd 35-44", lambda r: r["ar_deviation"] and 35 <= r["ar_deviation"] < 45),
        ("ARd <35", lambda r: r["ar_deviation"] and r["ar_deviation"] < 35),
    ]

    move_bins = [
        ("smart money(<=0.7x)", lambda r: r["odds_move"] <= 0.7),
        ("やや人気(0.7-0.9x)", lambda r: 0.7 < r["odds_move"] <= 0.9),
        ("変化なし(0.9-1.1x)", lambda r: 0.9 < r["odds_move"] <= 1.1),
        ("やや不人気(1.1-1.5x)", lambda r: 1.1 < r["odds_move"] <= 1.5),
        ("過小評価(>1.5x)", lambda r: r["odds_move"] > 1.5),
    ]

    for ard_label, ard_cond in ard_bins:
        ard_subset = [r for r in records if ard_cond(r)]
        print(f"\n  [{ard_label}] (全{len(ard_subset)}件)")
        for m_label, m_cond in move_bins:
            subset = [r for r in ard_subset if m_cond(r)]
            print_table(m_label, *calc_stats(subset))

    # =============================================
    # 分析B: rank_p x オッズ変動 → 見逃し馬の発掘
    # =============================================
    print(f"\n{'='*70}")
    print("分析B: モデルrank_p x オッズ変動 -> 見逃し馬の発掘")
    print("目的: モデルが低評価だがsmart moneyが入った馬の実力は?")
    print(f"{'='*70}")

    rank_bins = [
        ("rank_p 1-2", lambda r: r["rank_p"] and r["rank_p"] <= 2),
        ("rank_p 3-5", lambda r: r["rank_p"] and 3 <= r["rank_p"] <= 5),
        ("rank_p 6-8", lambda r: r["rank_p"] and 6 <= r["rank_p"] <= 8),
        ("rank_p 9+", lambda r: r["rank_p"] and r["rank_p"] >= 9),
    ]

    for rank_label, rank_cond in rank_bins:
        rank_subset = [r for r in records if rank_cond(r)]
        print(f"\n  [{rank_label}] (全{len(rank_subset)}件)")
        for m_label, m_cond in move_bins:
            subset = [r for r in rank_subset if m_cond(r)]
            print_table(m_label, *calc_stats(subset))

    # =============================================
    # 分析C: レース内Top3的中率の改善シミュレーション
    # =============================================
    print(f"\n{'='*70}")
    print("分析C: Top3選出精度の比較")
    print("現行(rank_p) vs rank_p+smart money補正 vs 基準オッズ順")
    print(f"{'='*70}")

    # レースごとに各方法でTop3を選出し、実際の3着内率を比較
    methods = {
        "rank_p Top3": lambda entries: sorted(
            [e for e in entries if e["rank_p"]], key=lambda e: e["rank_p"]
        )[:3],
        "rank_p Top5": lambda entries: sorted(
            [e for e in entries if e["rank_p"]], key=lambda e: e["rank_p"]
        )[:5],
        "base_odds Top3": lambda entries: sorted(
            [e for e in entries if e["base_odds"]], key=lambda e: e["base_odds"]
        )[:3],
        "actual_odds Top3": lambda entries: sorted(
            [e for e in entries if e["actual_odds"]], key=lambda e: e["actual_odds"]
        )[:3],
        "rank_p+smart補正 Top3": None,  # custom logic below
        "rank_p+smart補正 Top5": None,
    }

    results = defaultdict(lambda: {"n_races": 0, "hits": 0, "perfect": 0, "total_selected": 0, "total_hit": 0})

    for race_id, entries in race_records.items():
        if not entries or not any(e["rank_p"] for e in entries):
            continue

        valid = [e for e in entries if e["rank_p"] and e["base_odds"] and e["actual_odds"]]
        if len(valid) < 5:
            continue

        # Smart money adjusted score:
        # Lower = better. rank_p - bonus for smart money
        for e in valid:
            smart_bonus = 0
            if e["odds_move"] <= 0.7:
                smart_bonus = 2.0  # strong smart money
            elif e["odds_move"] <= 0.85:
                smart_bonus = 1.0  # moderate smart money
            elif e["odds_move"] >= 1.5:
                smart_bonus = -0.5  # market losing interest
            e["_smart_rank"] = e["rank_p"] - smart_bonus

        methods_eval = {
            "rank_p Top3": sorted(valid, key=lambda e: e["rank_p"])[:3],
            "rank_p Top5": sorted(valid, key=lambda e: e["rank_p"])[:5],
            "base_odds Top3": sorted(valid, key=lambda e: e["base_odds"])[:3],
            "actual_odds Top3": sorted(valid, key=lambda e: e["actual_odds"])[:3],
            "rank_p+smart補正 Top3": sorted(valid, key=lambda e: e["_smart_rank"])[:3],
            "rank_p+smart補正 Top5": sorted(valid, key=lambda e: e["_smart_rank"])[:5],
        }

        for method_name, selected in methods_eval.items():
            hit_count = sum(1 for e in selected if e["is_top3"])
            results[method_name]["n_races"] += 1
            results[method_name]["total_selected"] += len(selected)
            results[method_name]["total_hit"] += hit_count
            if hit_count >= 1:
                results[method_name]["hits"] += 1
            if hit_count >= len(selected):
                results[method_name]["perfect"] += 1

    print(f"\n  {'方法':<26} {'レース数':>7} {'1頭以上的中':>10} {'選出的中率':>10} {'全的中':>8}")
    print(f"  {'-'*65}")
    for method_name in ["rank_p Top3", "rank_p+smart補正 Top3", "base_odds Top3", "actual_odds Top3",
                         "rank_p Top5", "rank_p+smart補正 Top5"]:
        r = results[method_name]
        n = r["n_races"]
        if n == 0:
            continue
        hit_rate = r["hits"] / n * 100
        precision = r["total_hit"] / r["total_selected"] * 100 if r["total_selected"] else 0
        perfect = r["perfect"] / n * 100
        print(f"  {method_name:<26} {n:>7} {hit_rate:>9.1f}% {precision:>9.1f}% {perfect:>7.1f}%")

    # =============================================
    # 分析D: 「モデルが見逃した好走馬」の特徴
    # =============================================
    print(f"\n{'='*70}")
    print("分析D: モデルが見逃した好走馬 (rank_p>=6 & 3着内) の特徴")
    print("目的: smart moneyシグナルで見逃しを減らせるか?")
    print(f"{'='*70}")

    missed = [r for r in records
              if r["rank_p"] and r["rank_p"] >= 6
              and r["is_top3"]
              and r["ar_deviation"] is not None]

    not_missed = [r for r in records
                  if r["rank_p"] and r["rank_p"] <= 3
                  and r["is_top3"]
                  and r["ar_deviation"] is not None]

    print(f"\n  見逃し好走馬: {len(missed)}件")
    print(f"  的中推奨馬: {len(not_missed)}件")

    if missed and not_missed:
        # オッズ変動分布の比較
        missed_moves = [r["odds_move"] for r in missed]
        hit_moves = [r["odds_move"] for r in not_missed]

        print(f"\n  オッズ変動(実/基準)の分布:")
        print(f"    見逃し好走馬: mean={np.mean(missed_moves):.2f}, median={np.median(missed_moves):.2f}")
        print(f"    的中推奨馬:   mean={np.mean(hit_moves):.2f}, median={np.median(hit_moves):.2f}")

        # 見逃し馬のうちsmart moneyが入っていた割合
        missed_smart = [r for r in missed if r["odds_move"] <= 0.7]
        missed_moderate = [r for r in missed if 0.7 < r["odds_move"] <= 0.9]
        print(f"\n  見逃し好走馬のsmart money割合:")
        print(f"    強シグナル(<=0.7x): {len(missed_smart)}/{len(missed)} = {len(missed_smart)/len(missed)*100:.1f}%")
        print(f"    中シグナル(0.7-0.9x): {len(missed_moderate)}/{len(missed)} = {len(missed_moderate)/len(missed)*100:.1f}%")
        print(f"    合計: {(len(missed_smart)+len(missed_moderate))/len(missed)*100:.1f}%")

        # 参考: 全馬のsmart money割合
        all_smart = [r for r in records if r["odds_move"] <= 0.7]
        all_moderate = [r for r in records if 0.7 < r["odds_move"] <= 0.9]
        print(f"\n  (参考) 全馬のsmart money割合:")
        print(f"    強シグナル(<=0.7x): {len(all_smart)}/{len(records)} = {len(all_smart)/len(records)*100:.1f}%")
        print(f"    中シグナル(0.7-0.9x): {len(all_moderate)}/{len(records)} = {len(all_moderate)/len(records)*100:.1f}%")

    # =============================================
    # 分析E: race_confidence x オッズ変動
    # =============================================
    print(f"\n{'='*70}")
    print("分析E: race_confidence x smart moneyの効果")
    print("目的: 自信度が低いレースでsmart moneyが参考になるか")
    print(f"{'='*70}")

    conf_records = [r for r in records if r["race_confidence"] is not None and r["rank_p"]]

    if conf_records:
        conf_bins = [
            ("高自信(>=70)", lambda r: r["race_confidence"] >= 70),
            ("中自信(45-69)", lambda r: 45 <= r["race_confidence"] < 70),
            ("低自信(<45)", lambda r: r["race_confidence"] < 45),
        ]

        for conf_label, conf_cond in conf_bins:
            conf_subset = [r for r in conf_records if conf_cond(r)]
            print(f"\n  [{conf_label}] (全{len(conf_subset)}件)")

            # rank_p Top3の的中率 (smart money有無で比較)
            top3_picks = [r for r in conf_subset if r["rank_p"] <= 3]
            top3_smart = [r for r in top3_picks if r["odds_move"] <= 0.85]
            top3_normal = [r for r in top3_picks if 0.85 < r["odds_move"] <= 1.15]
            top3_drift = [r for r in top3_picks if r["odds_move"] > 1.15]

            for cat_label, cat_data in [("+ smart money", top3_smart),
                                         ("  変化なし", top3_normal),
                                         ("  人気落ち", top3_drift)]:
                print_table(f"rank_p<=3 {cat_label}", *calc_stats(cat_data))
    else:
        print("  race_confidence data not available in predictions")

    # =============================================
    # 分析F: 複合スコア設計のための相関分析
    # =============================================
    print(f"\n{'='*70}")
    print("分析F: 推奨馬スコア設計 - 複合条件の複勝率")
    print("目的: ARd + rank_p + smart money の最適な組み合わせ")
    print(f"{'='*70}")

    combos = [
        # (label, condition)
        ("A: ARd>=55 & rank_p<=3",
         lambda r: r["ar_deviation"] and r["ar_deviation"] >= 55 and r["rank_p"] and r["rank_p"] <= 3),
        ("B: A + smart(<=0.85x)",
         lambda r: r["ar_deviation"] and r["ar_deviation"] >= 55 and r["rank_p"] and r["rank_p"] <= 3 and r["odds_move"] <= 0.85),
        ("C: A + 変化なし(0.85-1.15x)",
         lambda r: r["ar_deviation"] and r["ar_deviation"] >= 55 and r["rank_p"] and r["rank_p"] <= 3 and 0.85 < r["odds_move"] <= 1.15),
        ("D: A + 不人気(>1.15x)",
         lambda r: r["ar_deviation"] and r["ar_deviation"] >= 55 and r["rank_p"] and r["rank_p"] <= 3 and r["odds_move"] > 1.15),
        ("E: ARd>=45 & rank_p<=5 & smart(<=0.85x)",
         lambda r: r["ar_deviation"] and r["ar_deviation"] >= 45 and r["rank_p"] and r["rank_p"] <= 5 and r["odds_move"] <= 0.85),
        ("F: rank_p 4-6 & smart(<=0.7x)",
         lambda r: r["rank_p"] and 4 <= r["rank_p"] <= 6 and r["odds_move"] <= 0.7),
        ("G: rank_p 7+ & smart(<=0.7x)",
         lambda r: r["rank_p"] and r["rank_p"] >= 7 and r["odds_move"] <= 0.7),
        ("H: ARd>=55 & rank_p<=3 & conf>=70",
         lambda r: r["ar_deviation"] and r["ar_deviation"] >= 55 and r["rank_p"] and r["rank_p"] <= 3
                   and r["race_confidence"] is not None and r["race_confidence"] >= 70),
        ("I: H + smart(<=0.85x)",
         lambda r: r["ar_deviation"] and r["ar_deviation"] >= 55 and r["rank_p"] and r["rank_p"] <= 3
                   and r["race_confidence"] is not None and r["race_confidence"] >= 70 and r["odds_move"] <= 0.85),
    ]

    print(f"\n  {'条件':<42} {'件数':>6} {'勝率':>7} {'複勝率':>7} {'単回収':>7}")
    print(f"  {'-'*72}")

    for label, cond in combos:
        subset = [r for r in records if cond(r)]
        n, wins, top3, win_ret = calc_stats(subset)
        if n < 10:
            print(f"  {label:<42} n={n:>5} (sample too small)")
            continue
        wr = wins / n * 100
        tr = top3 / n * 100
        roi = win_ret / n * 100
        print(f"  {label:<42} {n:>6} {wr:>6.1f}% {tr:>6.1f}% {roi:>6.1f}%")

    # =============================================
    # 分析G: レース内の相対オッズ変動
    # =============================================
    print(f"\n{'='*70}")
    print("分析G: レース内での相対オッズ変動")
    print("目的: レース内で最もオッズが下がった馬 = smart money集中馬の信頼性")
    print(f"{'='*70}")

    race_smart_stats = {"n_races": 0, "smart_in_top3": 0, "smart_is_winner": 0}

    for race_id, entries in race_records.items():
        valid = [e for e in entries if e["odds_move"] and e["rank_p"]]
        if len(valid) < 5:
            continue

        # レース内で最もオッズが下がった馬
        most_backed = min(valid, key=lambda e: e["odds_move"])
        if most_backed["odds_move"] >= 0.9:
            continue  # 大きな変動がないレースはスキップ

        race_smart_stats["n_races"] += 1
        if most_backed["is_top3"]:
            race_smart_stats["smart_in_top3"] += 1
        if most_backed["is_win"]:
            race_smart_stats["smart_is_winner"] += 1

    n = race_smart_stats["n_races"]
    if n > 0:
        print(f"\n  レース内最大smart money馬(odds_move<0.9のみ):")
        print(f"  対象レース: {n}")
        print(f"  3着内率: {race_smart_stats['smart_in_top3']/n*100:.1f}%")
        print(f"  勝率: {race_smart_stats['smart_is_winner']/n*100:.1f}%")

    # レース内smart money馬 × モデルrank_pの関係
    print(f"\n  レース内最大smart money馬のモデルランク分布:")
    rank_dist = defaultdict(int)
    rank_top3 = defaultdict(int)

    for race_id, entries in race_records.items():
        valid = [e for e in entries if e["odds_move"] and e["rank_p"]]
        if len(valid) < 5:
            continue
        most_backed = min(valid, key=lambda e: e["odds_move"])
        if most_backed["odds_move"] >= 0.9:
            continue

        rp = most_backed["rank_p"]
        bucket = "1-3" if rp <= 3 else "4-6" if rp <= 6 else "7+"
        rank_dist[bucket] += 1
        if most_backed["is_top3"]:
            rank_top3[bucket] += 1

    for bucket in ["1-3", "4-6", "7+"]:
        total = rank_dist.get(bucket, 0)
        hit = rank_top3.get(bucket, 0)
        if total > 0:
            print(f"    rank_p {bucket}: {total}件, 3着内率 {hit/total*100:.1f}%")

    # =============================================
    # 分析H: JRDB脚質 x オッズ変動
    # =============================================
    print(f"\n{'='*70}")
    print("分析H: JRDB脚質 x オッズ変動")
    print("目的: 脚質によってsmart moneyの信頼度は変わるか")
    print(f"{'='*70}")

    kyakushitsu_map = {1: "逃げ", 2: "先行", 3: "差し", 4: "追込"}
    kyaku_records = [r for r in records if r["kyakushitsu"] in kyakushitsu_map]

    for k_code, k_name in kyakushitsu_map.items():
        k_subset = [r for r in kyaku_records if r["kyakushitsu"] == k_code]
        print(f"\n  [{k_name}] (全{len(k_subset)}件)")
        for m_label, m_cond in [
            ("smart money(<=0.7x)", lambda r: r["odds_move"] <= 0.7),
            ("変化なし(0.85-1.15x)", lambda r: 0.85 < r["odds_move"] <= 1.15),
            ("不人気(>1.3x)", lambda r: r["odds_move"] > 1.3),
        ]:
            subset = [r for r in k_subset if m_cond(r)]
            print_table(m_label, *calc_stats(subset))


if __name__ == "__main__":
    kyi, races, pred_index = load_all_data()
    records, race_records = build_records(kyi, races, pred_index)
    analyze_cross(records, race_records)

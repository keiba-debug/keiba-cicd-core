"""全日程一括 買い目結果分析（FF CSV + predictions.json クロスリファレンス）"""
import json, re, glob, os

TEMP_DIR = "C:/KEIBA-CICD/data3/temp"
DATA_ROOT = "C:/KEIBA-CICD/data3"

# venue regex: 全10場対応
VENUE_RE = r"(東京|阪神|小倉|中山|京都|中京|福島|新潟|札幌|函館)"


def parse_csv(fp):
    """結果CSVをパース"""
    with open(fp, "r", encoding="utf-8") as f:
        lines = f.readlines()
    bets = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("場所") or line.startswith("---"):
            continue
        m = re.match(VENUE_RE + r"\s*(\d+)R\s+(単勝|複勝)\s+(\d+)\s+(\d+)円\s+(.*)", line)
        if not m:
            continue
        venue, rnum, bet_type, umaban, amount, rest = (
            m.group(1), int(m.group(2)), m.group(3),
            int(m.group(4)), int(m.group(5)), m.group(6).strip(),
        )
        if "取消" in rest:
            continue  # 返還は除外
        odds_m = re.search(r"\(\s*([\d.]+)\)", rest)
        odds = float(odds_m.group(1)) if odds_m else 0
        pay_m = re.search(r"(\d+)円$", rest)
        payout = int(pay_m.group(1)) if pay_m else 0
        bets.append({
            "venue": venue, "race_number": rnum, "bet_type": bet_type,
            "umaban": umaban, "amount": amount, "odds": odds, "payout": payout,
        })
    return bets


def load_predictions(date_str):
    """predictions.jsonを読み込み"""
    parts = date_str.split("-")
    pred_path = os.path.join(DATA_ROOT, "races", parts[0], parts[1], parts[2], "predictions.json")
    if not os.path.exists(pred_path):
        return {}
    with open(pred_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lookup = {}
    for race in data.get("races", []):
        vn = race.get("venue_name", "")
        rn = race.get("race_number", 0)
        tt = race.get("track_type", "")
        for e in race.get("entries", []):
            e["track_type"] = tt  # レースレベルのtrack_typeを各エントリに付与
            key = (vn, rn, e.get("umaban", 0))
            lookup[key] = e
    return lookup


def enrich_bets(bets, predictions):
    """betにprediction情報を付与"""
    for b in bets:
        key = (b["venue"], b["race_number"], b["umaban"])
        e = predictions.get(key, {})
        b["gap"] = e.get("vb_gap", 0) or 0
        b["rank_p"] = e.get("rank_p", 0) or e.get("rank_v", 0) or 0
        b["popularity"] = e.get("popularity", 0) or 0
        b["finish"] = e.get("finish_position", 99) or 99
        b["horse_name"] = e.get("horse_name") or "?"
        b["place_ev"] = e.get("place_ev", 0) or 0
        b["win_ev"] = e.get("win_ev", 0) or 0
        b["track_type"] = e.get("track_type", "") or ""
    return bets


def analyze_day(date_str, bets):
    """1日分の集計"""
    invest = sum(b["amount"] for b in bets)
    ret = sum(b["payout"] for b in bets)
    hits = sum(1 for b in bets if b["payout"] > 0)

    win_bets = [b for b in bets if b["bet_type"] == "単勝"]
    place_bets = [b for b in bets if b["bet_type"] == "複勝"]
    w_inv = sum(b["amount"] for b in win_bets)
    w_ret = sum(b["payout"] for b in win_bets)
    w_hits = sum(1 for b in win_bets if b["payout"] > 0)
    p_inv = sum(b["amount"] for b in place_bets)
    p_ret = sum(b["payout"] for b in place_bets)
    p_hits = sum(1 for b in place_bets if b["payout"] > 0)

    return {
        "date": date_str, "total_bets": len(bets),
        "invest": invest, "return": ret, "profit": ret - invest,
        "roi": ret / invest * 100 if invest > 0 else 0,
        "hits": hits, "hit_rate": hits / len(bets) * 100 if bets else 0,
        "win_bets": len(win_bets), "win_invest": w_inv, "win_return": w_ret, "win_hits": w_hits,
        "place_bets": len(place_bets), "place_invest": p_inv, "place_return": p_ret, "place_hits": p_hits,
    }


def gap_aggregate(all_bets):
    """Gap別集計"""
    stats = {}
    for b in all_bets:
        g = b["gap"]
        if g <= 1:
            continue  # gap 0-1 は VB対象外
        gk = str(g) if g <= 6 else "7+"
        if gk not in stats:
            stats[gk] = {"count": 0, "invest": 0, "return": 0, "hits": 0,
                          "win_c": 0, "win_h": 0, "place_c": 0, "place_h": 0}
        s = stats[gk]
        s["count"] += 1
        s["invest"] += b["amount"]
        s["return"] += b["payout"]
        if b["payout"] > 0:
            s["hits"] += 1
        if b["bet_type"] == "単勝":
            s["win_c"] += 1
            if b["payout"] > 0:
                s["win_h"] += 1
        else:
            s["place_c"] += 1
            if b["payout"] > 0:
                s["place_h"] += 1
    return stats


def pop_aggregate(all_bets):
    """人気帯別集計"""
    bands = {"1-3": [], "4-6": [], "7-10": [], "11+": []}
    for b in all_bets:
        p = b["popularity"]
        if p <= 3:
            bands["1-3"].append(b)
        elif p <= 6:
            bands["4-6"].append(b)
        elif p <= 10:
            bands["7-10"].append(b)
        else:
            bands["11+"].append(b)
    result = {}
    for k, bs in bands.items():
        inv = sum(x["amount"] for x in bs)
        ret = sum(x["payout"] for x in bs)
        h = sum(1 for x in bs if x["payout"] > 0)
        result[k] = {"count": len(bs), "invest": inv, "return": ret, "hits": h,
                      "roi": ret / inv * 100 if inv > 0 else 0}
    return result


def track_aggregate(all_bets):
    """芝/ダート別"""
    stats = {"turf": {"c": 0, "inv": 0, "ret": 0, "h": 0},
             "dirt": {"c": 0, "inv": 0, "ret": 0, "h": 0},
             "other": {"c": 0, "inv": 0, "ret": 0, "h": 0}}
    for b in all_bets:
        tt = b.get("track_type", "").lower()
        if tt in ("turf",):
            k = "turf"
        elif tt in ("dirt",):
            k = "dirt"
        else:
            k = "other"
        stats[k]["c"] += 1
        stats[k]["inv"] += b["amount"]
        stats[k]["ret"] += b["payout"]
        if b["payout"] > 0:
            stats[k]["h"] += 1
    return stats


def main():
    # CSVファイルを日付順に取得
    files = sorted(glob.glob(os.path.join(TEMP_DIR, "FF*_result_utf8.txt")))
    if not files:
        files = sorted(glob.glob(os.path.join(TEMP_DIR, "FF*_result.CSV")))

    print("=" * 80)
    print("  2026年2月 全日程 買い目結果分析（標準プリセット）")
    print("=" * 80)

    all_bets = []
    day_results = []

    for fp in files:
        # 日付抽出: FF20260201 -> 2026-02-01
        base = os.path.basename(fp)
        m = re.search(r"FF(\d{4})(\d{2})(\d{2})", base)
        if not m:
            continue
        date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        bets = parse_csv(fp)
        predictions = load_predictions(date_str)
        bets = enrich_bets(bets, predictions)

        day = analyze_day(date_str, bets)
        day_results.append(day)
        all_bets.extend(bets)

    # ── 日別成績 ──
    print(f"\n  【日別成績】")
    print(f"    {'日付':<12} {'件数':>4} {'投資':>8} {'回収':>8} {'収支':>8} {'ROI':>7} "
          f"| {'単勝':>8} {'複勝':>8}")
    print(f"    {'-'*12} {'----':>4} {'--------':>8} {'--------':>8} {'--------':>8} {'-------':>7} "
          f"| {'--------':>8} {'--------':>8}")
    for d in day_results:
        w_str = f"{d['win_hits']}/{d['win_bets']}"
        p_str = f"{d['place_hits']}/{d['place_bets']}"
        print(f"    {d['date']:<12} {d['total_bets']:>4} "
              f"Y{d['invest']:>7,} Y{d['return']:>7,} Y{d['profit']:>+7,} {d['roi']:>6.1f}% "
              f"| {w_str:>8} {p_str:>8}")

    # 合計
    tot_inv = sum(d["invest"] for d in day_results)
    tot_ret = sum(d["return"] for d in day_results)
    tot_profit = tot_ret - tot_inv
    tot_roi = tot_ret / tot_inv * 100 if tot_inv > 0 else 0
    tot_bets = sum(d["total_bets"] for d in day_results)
    tot_w_h = sum(d["win_hits"] for d in day_results)
    tot_w_c = sum(d["win_bets"] for d in day_results)
    tot_p_h = sum(d["place_hits"] for d in day_results)
    tot_p_c = sum(d["place_bets"] for d in day_results)
    print(f"    {'='*12} {'====':>4} {'========':>8} {'========':>8} {'========':>8} {'=======':>7} "
          f"| {'========':>8} {'========':>8}")
    print(f"    {'合計':<12} {tot_bets:>4} "
          f"Y{tot_inv:>7,} Y{tot_ret:>7,} Y{tot_profit:>+7,} {tot_roi:>6.1f}% "
          f"| {tot_w_h}/{tot_w_c}:>8 {tot_p_h}/{tot_p_c}:>8")

    # ── Gap別成績 ──
    gap_stats = gap_aggregate(all_bets)
    print(f"\n  【Gap別成績（全日程合算）】")
    print(f"    {'Gap':>4} {'件数':>4} {'投資':>8} {'回収':>8} {'ROI':>7} {'的中率':>7} | {'単勝':>6} {'複勝':>6}")
    cumulative_inv = 0
    cumulative_ret = 0
    for gk in sorted(gap_stats.keys(), key=lambda x: int(x.replace("+", "99"))):
        gs = gap_stats[gk]
        roi = gs["return"] / gs["invest"] * 100 if gs["invest"] > 0 else 0
        hr = gs["hits"] / gs["count"] * 100 if gs["count"] > 0 else 0
        cumulative_inv += gs["invest"]
        cumulative_ret += gs["return"]
        w_s = f"{gs['win_h']}/{gs['win_c']}"
        p_s = f"{gs['place_h']}/{gs['place_c']}"
        print(f"    {gk:>4} {gs['count']:>4} Y{gs['invest']:>7,} Y{gs['return']:>7,} "
              f"{roi:>6.1f}% {hr:>6.1f}% | {w_s:>6} {p_s:>6}")

    # 累積（gap>=3, >=4, >=5）
    print(f"\n    累積:")
    for min_g in [3, 4, 5]:
        subset = [b for b in all_bets if b["gap"] >= min_g]
        if not subset:
            continue
        inv = sum(b["amount"] for b in subset)
        ret = sum(b["payout"] for b in subset)
        h = sum(1 for b in subset if b["payout"] > 0)
        roi = ret / inv * 100 if inv > 0 else 0
        hr = h / len(subset) * 100
        print(f"    gap>={min_g}: {len(subset)}件 Y{inv:,} -> Y{ret:,} ROI {roi:.1f}% ({h}的中 {hr:.1f}%)")

    # ── 人気帯別 ──
    pop_stats = pop_aggregate(all_bets)
    print(f"\n  【人気帯別成績】")
    for band in ["1-3", "4-6", "7-10", "11+"]:
        ps = pop_stats.get(band, {})
        if not ps or ps["count"] == 0:
            continue
        roi = ps["roi"]
        hr = ps["hits"] / ps["count"] * 100 if ps["count"] > 0 else 0
        print(f"    {band+'人気':<8} {ps['count']:>4}件 Y{ps['invest']:>7,} -> Y{ps['return']:>7,} "
              f"ROI {roi:>6.1f}% ({ps['hits']}的中 {hr:.1f}%)")

    # ── 芝/ダート別 ──
    track_stats = track_aggregate(all_bets)
    print(f"\n  【芝/ダート別成績】")
    for tk, label in [("turf", "芝"), ("dirt", "ダート"), ("other", "不明")]:
        ts = track_stats[tk]
        if ts["c"] == 0:
            continue
        roi = ts["ret"] / ts["inv"] * 100 if ts["inv"] > 0 else 0
        hr = ts["h"] / ts["c"] * 100
        print(f"    {label:<6} {ts['c']:>4}件 Y{ts['inv']:>7,} -> Y{ts['ret']:>7,} "
              f"ROI {roi:>6.1f}% ({ts['h']}的中 {hr:.1f}%)")

    # ── 的中一覧（全日程） ──
    hits = [b for b in all_bets if b["payout"] > 0]
    print(f"\n  【的中一覧（全{len(hits)}件）】")
    print(f"    {'日付':<12} {'場所':>4} {'R':>2} {'種別':>3} {'馬番':>3} {'馬名':<12} "
          f"{'gap':>3} {'人気':>3} {'金額':>5} {'配当':>6} {'利益':>6}")
    for b in sorted(hits, key=lambda x: (x.get("_date", ""), x["venue"], x["race_number"])):
        pr = b["payout"] - b["amount"]
        hn = str(b.get("horse_name") or "?")[:12]
        dt = b.get("_date", "")
        print(f"    {dt:<12} {b['venue']:>4} {b['race_number']:>2} {b['bet_type']:>3} {b['umaban']:>3} "
              f"{hn:<12} {b['gap']:>3} {b['popularity']:>3} Y{b['amount']:>4} Y{b['payout']:>5} Y{pr:>+5}")

    # ── バックテスト期待値との比較 ──
    print(f"\n  【バックテスト期待値 vs 実績】")
    bt_place = {3: (0.2667, 1.183), 4: (0.2293, 1.274), 5: (0.2220, 1.482)}
    bt_win = {3: (0.0687, 0.946), 4: (0.0583, 1.004), 5: (0.0568, 1.160)}
    for min_g in [3, 4, 5]:
        p_sub = [b for b in all_bets if b["gap"] >= min_g and b["bet_type"] == "複勝"]
        w_sub = [b for b in all_bets if b["gap"] >= min_g and b["bet_type"] == "単勝"]
        if p_sub:
            p_hr = sum(1 for b in p_sub if b["payout"] > 0) / len(p_sub)
            p_inv = sum(b["amount"] for b in p_sub)
            p_ret = sum(b["payout"] for b in p_sub)
            p_roi = p_ret / p_inv if p_inv > 0 else 0
            exp_hr, exp_roi = bt_place.get(min_g, (0, 0))
            print(f"    複勝gap>={min_g}: 実績 {p_hr:.1%} / ROI {p_roi:.1%}  "
                  f"(BT期待: {exp_hr:.1%} / {exp_roi:.1%})  n={len(p_sub)}")
        if w_sub:
            w_hr = sum(1 for b in w_sub if b["payout"] > 0) / len(w_sub)
            w_inv = sum(b["amount"] for b in w_sub)
            w_ret = sum(b["payout"] for b in w_sub)
            w_roi = w_ret / w_inv if w_inv > 0 else 0
            exp_hr, exp_roi = bt_win.get(min_g, (0, 0))
            print(f"    単勝gap>={min_g}: 実績 {w_hr:.1%} / ROI {w_roi:.1%}  "
                  f"(BT期待: {exp_hr:.1%} / {exp_roi:.1%})  n={len(w_sub)}")


if __name__ == "__main__":
    # 日付タグを各betに付与
    import sys
    files = sorted(glob.glob(os.path.join(TEMP_DIR, "FF*_result_utf8.txt")))
    if not files:
        files = sorted(glob.glob(os.path.join(TEMP_DIR, "FF*_result.CSV")))

    # main内で_dateを付与するためリファクタ
    all_bets_global = []
    day_results_global = []

    print("=" * 80)
    print("  2026年2月 全日程 買い目結果分析（標準プリセット）")
    print("=" * 80)

    for fp in files:
        base = os.path.basename(fp)
        m = re.search(r"FF(\d{4})(\d{2})(\d{2})", base)
        if not m:
            continue
        date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        bets = parse_csv(fp)
        predictions = load_predictions(date_str)
        bets = enrich_bets(bets, predictions)
        for b in bets:
            b["_date"] = date_str
        day = analyze_day(date_str, bets)
        day_results_global.append(day)
        all_bets_global.extend(bets)

    # 日別成績
    print(f"\n  【日別成績】")
    print(f"    {'日付':<12} {'件数':>4} {'投資':>8} {'回収':>8} {'収支':>8} {'ROI':>7} "
          f"| {'単勝':>8} {'複勝':>8}")
    print(f"    {'-'*12} {'----':>4} {'--------':>8} {'--------':>8} {'--------':>8} {'-------':>7} "
          f"| {'--------':>8} {'--------':>8}")
    for d in day_results_global:
        w_str = f"{d['win_hits']}/{d['win_bets']}"
        p_str = f"{d['place_hits']}/{d['place_bets']}"
        mark = " ++" if d["profit"] > 0 else ""
        print(f"    {d['date']:<12} {d['total_bets']:>4} "
              f"Y{d['invest']:>7,} Y{d['return']:>7,} Y{d['profit']:>+7,} {d['roi']:>6.1f}%"
              f" | {w_str:>8} {p_str:>8}{mark}")

    tot_inv = sum(d["invest"] for d in day_results_global)
    tot_ret = sum(d["return"] for d in day_results_global)
    tot_profit = tot_ret - tot_inv
    tot_roi = tot_ret / tot_inv * 100 if tot_inv > 0 else 0
    tot_bets = sum(d["total_bets"] for d in day_results_global)
    tot_w_h = sum(d["win_hits"] for d in day_results_global)
    tot_w_c = sum(d["win_bets"] for d in day_results_global)
    tot_p_h = sum(d["place_hits"] for d in day_results_global)
    tot_p_c = sum(d["place_bets"] for d in day_results_global)
    print(f"    {'='*78}")
    w_tot = f"{tot_w_h}/{tot_w_c}"
    p_tot = f"{tot_p_h}/{tot_p_c}"
    print(f"    {'合計':<12} {tot_bets:>4} "
          f"Y{tot_inv:>7,} Y{tot_ret:>7,} Y{tot_profit:>+7,} {tot_roi:>6.1f}%"
          f" | {w_tot:>8} {p_tot:>8}")

    # Gap別
    gap_stats = gap_aggregate(all_bets_global)
    print(f"\n  【Gap別成績（全日程合算）】")
    print(f"    {'Gap':>4} {'件数':>4} {'投資':>8} {'回収':>8} {'ROI':>7} {'的中率':>7} | {'単勝':>6} {'複勝':>6}")
    for gk in sorted(gap_stats.keys(), key=lambda x: int(x.replace("+", "99"))):
        gs = gap_stats[gk]
        roi = gs["return"] / gs["invest"] * 100 if gs["invest"] > 0 else 0
        hr = gs["hits"] / gs["count"] * 100 if gs["count"] > 0 else 0
        w_s = f"{gs['win_h']}/{gs['win_c']}"
        p_s = f"{gs['place_h']}/{gs['place_c']}"
        print(f"    {gk:>4} {gs['count']:>4} Y{gs['invest']:>7,} Y{gs['return']:>7,} "
              f"{roi:>6.1f}% {hr:>6.1f}% | {w_s:>6} {p_s:>6}")

    print(f"\n    累積:")
    for min_g in [3, 4, 5]:
        subset = [b for b in all_bets_global if b["gap"] >= min_g]
        if not subset:
            continue
        inv = sum(b["amount"] for b in subset)
        ret = sum(b["payout"] for b in subset)
        h = sum(1 for b in subset if b["payout"] > 0)
        roi = ret / inv * 100 if inv > 0 else 0
        hr = h / len(subset) * 100
        print(f"    gap>={min_g}: {len(subset)}件 Y{inv:,} -> Y{ret:,} ROI {roi:.1f}% ({h}的中 {hr:.1f}%)")

    # 人気帯
    pop_stats = pop_aggregate(all_bets_global)
    print(f"\n  【人気帯別成績】")
    for band in ["1-3", "4-6", "7-10", "11+"]:
        ps = pop_stats.get(band, {})
        if not ps or ps["count"] == 0:
            continue
        hr = ps["hits"] / ps["count"] * 100
        print(f"    {band+'人気':<8} {ps['count']:>4}件 Y{ps['invest']:>7,} -> Y{ps['return']:>7,} "
              f"ROI {ps['roi']:>6.1f}% ({ps['hits']}的中 {hr:.1f}%)")

    # 芝ダート
    track_stats = track_aggregate(all_bets_global)
    print(f"\n  【芝/ダート別成績】")
    for tk, label in [("turf", "芝"), ("dirt", "ダート"), ("other", "不明")]:
        ts = track_stats[tk]
        if ts["c"] == 0:
            continue
        roi = ts["ret"] / ts["inv"] * 100 if ts["inv"] > 0 else 0
        hr = ts["h"] / ts["c"] * 100
        print(f"    {label:<6} {ts['c']:>4}件 Y{ts['inv']:>7,} -> Y{ts['ret']:>7,} "
              f"ROI {roi:>6.1f}% ({ts['h']}的中 {hr:.1f}%)")

    # 的中一覧
    hits = [b for b in all_bets_global if b["payout"] > 0]
    print(f"\n  【的中一覧（全{len(hits)}件）】")
    print(f"    {'日付':<12} {'場所':>4} {'R':>2} {'種別':>3} {'馬番':>3} {'馬名':<12} "
          f"{'gap':>3} {'人気':>3} {'金額':>5} {'配当':>6} {'利益':>6}")
    for b in sorted(hits, key=lambda x: (x.get("_date", ""), x["venue"], x["race_number"])):
        pr = b["payout"] - b["amount"]
        hn = str(b.get("horse_name") or "?")[:12]
        print(f"    {b['_date']:<12} {b['venue']:>4} {b['race_number']:>2} {b['bet_type']:>3} {b['umaban']:>3} "
              f"{hn:<12} {b['gap']:>3} {b['popularity']:>3} Y{b['amount']:>4} Y{b['payout']:>5} Y{pr:>+5}")

    # BT比較
    print(f"\n  【バックテスト期待値 vs 実績】")
    bt_place = {3: (0.2667, 1.183), 4: (0.2293, 1.274), 5: (0.2220, 1.482)}
    bt_win = {3: (0.0687, 0.946), 4: (0.0583, 1.004), 5: (0.0568, 1.160)}
    for min_g in [3, 4, 5]:
        p_sub = [b for b in all_bets_global if b["gap"] >= min_g and b["bet_type"] == "複勝"]
        w_sub = [b for b in all_bets_global if b["gap"] >= min_g and b["bet_type"] == "単勝"]
        if p_sub:
            p_hr = sum(1 for b in p_sub if b["payout"] > 0) / len(p_sub)
            p_inv = sum(b["amount"] for b in p_sub)
            p_ret = sum(b["payout"] for b in p_sub)
            p_roi = p_ret / p_inv if p_inv > 0 else 0
            exp_hr, exp_roi = bt_place[min_g]
            print(f"    複勝gap>={min_g}: 実績 {p_hr:.1%} / ROI {p_roi:.1%}  "
                  f"(BT期待: {exp_hr:.1%} / {exp_roi:.1%})  n={len(p_sub)}")
        if w_sub:
            w_hr = sum(1 for b in w_sub if b["payout"] > 0) / len(w_sub)
            w_inv = sum(b["amount"] for b in w_sub)
            w_ret = sum(b["payout"] for b in w_sub)
            w_roi = w_ret / w_inv if w_inv > 0 else 0
            exp_hr, exp_roi = bt_win[min_g]
            print(f"    単勝gap>={min_g}: 実績 {w_hr:.1%} / ROI {w_roi:.1%}  "
                  f"(BT期待: {exp_hr:.1%} / {exp_roi:.1%})  n={len(w_sub)}")

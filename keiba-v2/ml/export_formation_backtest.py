#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三連単フォーメーション バックテスト結果をJSON出力

★ predictions.json ベース（リークなし）
  - レース前の予測データのみ使用
  - backtest_cache（レース後データ）は使わない

Web UIの /analysis/formation ページ用データを生成する。
Output: data3/ml/formation_backtest.json

Usage:
    python -m ml.export_formation_backtest
"""

import glob
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.simulate_sanrentan_ev import load_sanrentan_payouts

# ===========================================================================
# Extended strategies (base + combined filters)
# ===========================================================================

EXTENDED_STRATEGIES = {
    # --- ベースライン ---
    "VB_45F3": {
        "label": "VB_45F3 (Base)",
        "tier": "base",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
        "min_vb": 3,
    },
    # --- FavOdds < 4.0 ---
    "VB_45F3_FO4": {
        "label": "FavOdds < 4.0",
        "tier": "recommended",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
        "ext_filter": {"max_fav_odds": 4.0},
        "min_vb": 3,
    },
    # --- ConfGap < 0.10 ---
    "VB_45F3_CG10": {
        "label": "ConfGap < 0.10",
        "tier": "recommended",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
        "ext_filter": {"max_conf_gap": 0.10},
        "min_vb": 3,
    },
    # --- FO<4 + CG<0.10 (推奨A) ---
    "VB_45F3_FO4_CG10": {
        "label": "FO<4 + CG<0.10",
        "tier": "top",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
        "ext_filter": {"max_fav_odds": 4.0, "max_conf_gap": 0.10},
        "min_vb": 3,
    },
    # --- FO<4 + CG<0.05 (最強) ---
    "VB_45F3_FO4_CG05": {
        "label": "FO<4 + CG<0.05",
        "tier": "top",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
        "ext_filter": {"max_fav_odds": 4.0, "max_conf_gap": 0.05},
        "min_vb": 3,
    },
    # --- FO<4 + CG<0.10 + 14-16h ---
    "VB_45F3_FO4_CG10_14h": {
        "label": "FO<4 + CG<0.10 + 14-16h",
        "tier": "aggressive",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
        "ext_filter": {"max_fav_odds": 4.0, "max_conf_gap": 0.10,
                        "min_runners": 14, "max_runners": 16},
        "min_vb": 3,
    },
}


# ===========================================================================
# predictions.json ベースの解析
# ===========================================================================

def analyze_pred_entries(entries: list) -> Optional[dict]:
    """predictions.json の entries からフィルタ用解析値を計算

    backtest_cache の analyze_entries と同等だが、
    pred_proba_p_raw / win_ev / odds を直接使う（リークなし）。
    """
    valid = [e for e in entries if (e.get("odds") or 0) > 0]
    if len(valid) < 5:
        return None

    # P% raw でソート
    horses = []
    for e in valid:
        p_raw = e.get("pred_proba_p_raw") or 0
        win_ev = e.get("win_ev") or 0
        odds = e.get("odds") or 0
        horses.append({
            "umaban": e["umaban"],
            "horse_name": e.get("horse_name", "?"),
            "odds": odds,
            "win_ev": win_ev,
            "p_raw": p_raw,
        })
    horses.sort(key=lambda h: -h["p_raw"])

    p_sum = sum(h["p_raw"] for h in horses)
    if p_sum <= 0:
        return None

    conf_gap = horses[0]["p_raw"] - horses[1]["p_raw"] if len(horses) >= 2 else 0
    p_top3_share = sum(h["p_raw"] for h in horses[:3]) / p_sum
    fav_odds = min(h["odds"] for h in horses)

    return {
        "horses": horses,
        "n_runners": len(valid),
        "conf_gap": conf_gap,
        "p_top3_share": p_top3_share,
        "fav_odds": fav_odds,
        "valid": True,
    }


def check_race_filter(analysis: dict, rf: dict) -> bool:
    """レースフィルター"""
    if "max_p_top3_share" in rf:
        if analysis["p_top3_share"] > rf["max_p_top3_share"]:
            return False
    if "min_fav_odds" in rf:
        if analysis["fav_odds"] < rf["min_fav_odds"]:
            return False
    return True


def check_ext_filter(analysis: dict, race_id: str, ext: dict) -> bool:
    """拡張フィルター"""
    if not ext:
        return True
    if "max_fav_odds" in ext and analysis["fav_odds"] >= ext["max_fav_odds"]:
        return False
    if "max_conf_gap" in ext and analysis["conf_gap"] > ext["max_conf_gap"]:
        return False
    if "min_runners" in ext and analysis["n_runners"] < ext["min_runners"]:
        return False
    if "max_runners" in ext and analysis["n_runners"] > ext["max_runners"]:
        return False
    if "min_race_num" in ext:
        if int(race_id[14:16]) < ext["min_race_num"]:
            return False
    if "max_race_num" in ext:
        if int(race_id[14:16]) > ext["max_race_num"]:
            return False
    return True


def build_vb_head_tickets(
    analysis: dict, cfg: dict
) -> Set[Tuple[int, ...]]:
    """VB頭フォーメーションのチケット生成（generate_sanrentan_formationと同一ロジック）"""
    horses = analysis["horses"]
    min_ev = cfg.get("min_win_ev", 1.5)
    min_odds = cfg.get("min_odds", 10.0)
    n_tri = cfg.get("n_tri", 4)
    n_wide = cfg.get("n_wide", 3)
    max_tickets = cfg.get("max_tickets", 28)

    vb_candidates = [h for h in horses if h["win_ev"] >= min_ev and h["odds"] >= min_odds]
    if not vb_candidates:
        return set()

    tickets: Set[Tuple[int, ...]] = set()
    for vb in vb_candidates:
        vb_num = vb["umaban"]
        others = [h for h in horses if h["umaban"] != vb_num]
        tri_horses = others[:n_tri]
        wide_horses = others[n_tri:n_tri + n_wide]

        second_nums = [h["umaban"] for h in tri_horses]
        third_nums = [h["umaban"] for h in tri_horses + wide_horses]

        vb_tickets = []
        for s in second_nums:
            for t in third_nums:
                if s != t:
                    vb_tickets.append((vb_num, s, t))
        tickets.update(vb_tickets[:max_tickets])

    return tickets


# ===========================================================================
# predictions.json 読み込み
# ===========================================================================

def load_predictions_races(
    start_date: str = "2025-03",
    end_date: str = "2026-03",
) -> List[dict]:
    """predictions.json からレースデータを読み込み（リークなし）"""
    pattern = str(config.races_dir() / "*" / "*" / "*" / "predictions.json")
    files = sorted(glob.glob(pattern))
    races = []
    for f in files:
        try:
            p = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        date = p.get("date", "")
        if date < start_date or date > end_date:
            continue
        for r in p.get("races", []):
            r["_date"] = date  # 参照用
            races.append(r)
    return races


# ===========================================================================
# バックテスト実行
# ===========================================================================

def run_backtest(races: List[dict], payouts: dict) -> dict:
    """全戦略のバックテスト実行 → JSON出力用辞書を返す"""
    strategies_out = []

    for strat_key, strat in EXTENDED_STRATEGIES.items():
        fired = 0
        inv = 0
        ret = 0
        hits = 0
        hit_details = []
        monthly = defaultdict(lambda: {"races": 0, "inv": 0, "ret": 0, "hits": 0})

        cfg = strat["cfg"]
        rf = strat.get("race_filter", {})
        ext = strat.get("ext_filter", {})
        min_vb = strat.get("min_vb", 0)

        for race in races:
            race_id = race["race_id"]
            if race.get("track_type") in ("obstacle", "steeplechase"):
                continue

            rp = payouts.get(race_id)
            if not rp:
                continue

            analysis = analyze_pred_entries(race.get("entries", []))
            if not analysis or not analysis.get("valid"):
                continue
            if analysis["n_runners"] < 8:
                continue
            if not check_race_filter(analysis, rf):
                continue
            if not check_ext_filter(analysis, race_id, ext):
                continue

            # VB候補数チェック
            min_ev = cfg.get("min_win_ev", 1.5)
            min_odds = cfg.get("min_odds", 10.0)
            vb_count = sum(
                1 for h in analysis["horses"]
                if h["win_ev"] >= min_ev and h["odds"] >= min_odds
            )
            if vb_count < min_vb:
                continue

            tickets = build_vb_head_tickets(analysis, cfg)
            if not tickets:
                continue

            fired += 1
            race_inv = len(tickets) * 100
            inv += race_inv
            month = f"{race_id[:4]}-{race_id[4:6]}"
            monthly[month]["races"] += 1
            monthly[month]["inv"] += race_inv

            pm = {t: p for t, p in rp}
            for t in tickets:
                if t in pm:
                    ret += pm[t]
                    hits += 1
                    monthly[month]["ret"] += pm[t]
                    monthly[month]["hits"] += 1
                    hit_details.append({
                        "race_id": race_id,
                        "ticket": list(t),
                        "payout": pm[t],
                    })

        roi = ret / inv * 100 if inv > 0 else 0
        hit_pays = sorted([h["payout"] for h in hit_details], reverse=True)
        top1 = hit_pays[0] if hit_pays else 0
        roi_ex_top1 = (ret - top1) / inv * 100 if inv > 0 else 0

        # 前後半分割
        months_sorted = sorted(monthly.keys())
        mid = len(months_sorted) // 2
        first_inv = sum(monthly[m]["inv"] for m in months_sorted[:mid])
        first_ret = sum(monthly[m]["ret"] for m in months_sorted[:mid])
        second_inv = sum(monthly[m]["inv"] for m in months_sorted[mid:])
        second_ret = sum(monthly[m]["ret"] for m in months_sorted[mid:])
        roi_first = first_ret / first_inv * 100 if first_inv > 0 else 0
        roi_second = second_ret / second_inv * 100 if second_inv > 0 else 0

        n_months = max(len(monthly), 1)

        strategies_out.append({
            "key": strat_key,
            "label": strat["label"],
            "tier": strat["tier"],
            "fired_races": fired,
            "total_hits": hits,
            "total_invested": inv,
            "total_return": ret,
            "roi": round(roi, 1),
            "avg_payout": ret // hits if hits > 0 else 0,
            "monthly_inv": round(inv / n_months),
            "hit_rate": round(hits / fired * 100, 1) if fired > 0 else 0,
            "avg_tickets": round(inv / 100 / max(fired, 1), 1),
            # robustness
            "roi_ex_top1": round(roi_ex_top1, 1),
            "roi_first_half": round(roi_first, 1),
            "roi_second_half": round(roi_second, 1),
            "top1_payout": top1,
            "top1_dependency": round(top1 / ret * 100, 1) if ret > 0 else 0,
            # monthly
            "monthly": [
                {
                    "month": m,
                    "races": monthly[m]["races"],
                    "inv": monthly[m]["inv"],
                    "ret": monthly[m]["ret"],
                    "hits": monthly[m]["hits"],
                    "roi": round(monthly[m]["ret"] / monthly[m]["inv"] * 100, 1)
                    if monthly[m]["inv"] > 0 else 0,
                    "pnl": monthly[m]["ret"] - monthly[m]["inv"],
                }
                for m in months_sorted
            ],
            # hit details (top 30)
            "hit_details": sorted(hit_details, key=lambda x: -x["payout"])[:30],
        })

    # 期間
    race_ids = sorted(r["race_id"] for r in races)

    return {
        "created_at": datetime.now().isoformat(),
        "data_source": "predictions.json (leak-free)",
        "period_start": f"{race_ids[0][:4]}-{race_ids[0][4:6]}-{race_ids[0][6:8]}",
        "period_end": f"{race_ids[-1][:4]}-{race_ids[-1][4:6]}-{race_ids[-1][6:8]}",
        "total_races": len(races),
        "races_with_payouts": len(payouts),
        "strategies": strategies_out,
    }


def main():
    print("=" * 80)
    print("  Formation Backtest → JSON Export (predictions.json based)")
    print("=" * 80)

    races = load_predictions_races(start_date="2025-03", end_date="2026-03")
    race_ids = [r["race_id"] for r in races]
    payouts = load_sanrentan_payouts(race_ids)
    print(f"  Predictions: {len(races)} races, Payouts: {len(payouts)}")

    result = run_backtest(races, payouts)

    out_path = config.ml_dir() / "formation_backtest.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  Saved: {out_path}")

    # Summary
    for s in result["strategies"]:
        marker = "**" if s["roi"] >= 100 else ""
        print(f"  {s['key']:<28} {s['fired_races']:>4}R {s['total_hits']:>3}hit "
              f"ROI={s['roi']:>6.1f}%{marker}  "
              f"Top1x={s['roi_ex_top1']:>6.1f}% "
              f"F/B={s['roi_first_half']:.0f}/{s['roi_second_half']:.0f}%")


if __name__ == "__main__":
    main()

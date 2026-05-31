#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""「危」(過剰人気アラート) ロジックの妥当性 backtest。

発端: Session 141。京都11R① で「危」(odds<=8 & ARd<53 & P%<15) と
「穴注目」(market_signal: rank_p4-6 & オッズ下落) が同じ馬に同時点灯し矛盾
(同じ「人気化=オッズ下落」を、危=過剰人気/消し、穴注目=スマートマネー/買い と逆解釈)。
しかも① は実際に勝った。

この backtest は:
  1. 現行「危」判定馬の実成績 (複勝率・単複ROI)。「危=本当に飛ぶ/おいしくない」か検証。
  2. 「危 ∩ 穴注目」重複馬の成績。矛盾ケースが実データでどちらが正しかったか。
  3. odds_move を入れた改善案 (危 かつ スマートマネー無し=オッズ下落してない) の成績比較。

結果データは ml.utils.race_io.load_race (finish_position) を analyze_market_signal と同じ方法で取得。
障害レースは除外。

使用例:
  python -m ml.analyze.backtest_danger_alert
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import config
from ml.utils.race_io import load_race, date_dir_for
from ml.utils.filters import is_obstacle

# 現行「危」判定の閾値 (HorseEntryTable.tsx と一致させる)
DANGER_ODDS_MAX = 8.0
DANGER_ARD_MAX = 53.0
DANGER_P_MAX = 0.15


def _is_danger(odds, ard, p_proba):
    """現行の危判定 (odds<=8 & ARd<53 & P%<15)。"""
    if odds is None or odds <= 0:
        return False
    if ard is None or p_proba is None:
        return False
    return odds <= DANGER_ODDS_MAX and ard < DANGER_ARD_MAX and p_proba < DANGER_P_MAX


def collect():
    races_dir = config.races_dir()
    rows = []
    for pred_path in sorted(races_dir.glob("**/predictions.json")):
        try:
            with open(pred_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        races_list = data.get("races", []) if isinstance(data, dict) else data
        if isinstance(races_list, str):
            continue
        for race in races_list:
            if not isinstance(race, dict) or is_obstacle(race):
                continue
            rid = race.get("race_id", "")
            date = race.get("date", "")
            if not date:
                continue
            try:
                day_dir = date_dir_for(date, root=races_dir)
            except ValueError:
                continue
            rd = load_race(day_dir, rid)
            if rd is None:
                continue
            actual = {}
            for e in rd.get("entries", []):
                u = e.get("umaban", 0)
                fp = e.get("finish_position", 0)
                if u > 0 and fp > 0:
                    actual[u] = fp
            if not actual:
                continue
            for e in race.get("entries", []):
                uma = e.get("umaban", 0)
                fp = actual.get(uma, 99)
                odds = float(e.get("odds", 0) or 0)
                place_odds = float(e.get("place_odds_min", 0) or 0)
                ard = e.get("ar_deviation")
                ard = float(ard) if isinstance(ard, (int, float)) else None
                p_proba = e.get("pred_proba_p")
                p_proba = float(p_proba) if isinstance(p_proba, (int, float)) else None
                odds_move = e.get("odds_move")
                rows.append({
                    "rid": rid, "date": date, "uma": uma, "fp": fp,
                    "odds": odds, "place_odds": place_odds,
                    "ard": ard, "p_proba": p_proba,
                    "odds_move": odds_move,
                    "ms": e.get("market_signal"),
                    "danger": _is_danger(odds, ard, p_proba),
                })
    return rows


def stats(subset):
    n = len(subset)
    if n == 0:
        return None
    wins = sum(1 for d in subset if d["fp"] == 1)
    top3 = sum(1 for d in subset if d["fp"] <= 3)
    w_bet = sum(100 for d in subset if d["odds"] > 0)
    w_ret = sum(int(d["odds"] * 100) for d in subset if d["fp"] == 1 and d["odds"] > 0)
    p_bet = sum(100 for d in subset if d["place_odds"] > 0)
    p_ret = sum(int(d["place_odds"] * 100) for d in subset if d["fp"] <= 3 and d["place_odds"] > 0)
    return {
        "n": n, "wr": wins / n * 100, "pr": top3 / n * 100,
        "w_roi": (w_ret / w_bet * 100) if w_bet else 0,
        "p_roi": (p_ret / p_bet * 100) if p_bet else 0,
    }


def _line(label, s):
    if s is None:
        print(f"  {label:<28} n=0")
        return
    print(f"  {label:<28} n={s['n']:>4}  勝率{s['wr']:5.1f}%  複勝率{s['pr']:5.1f}%  "
          f"単ROI{s['w_roi']:6.1f}%  複ROI{s['p_roi']:6.1f}%")


def main():
    rows = collect()
    print("=" * 78)
    print("  「危」(過剰人気アラート) ロジック backtest")
    print(f"  対象: 全 {len(rows)} 頭 (結果確定・障害除外)")
    print("=" * 78)

    danger = [d for d in rows if d["danger"]]
    non_danger = [d for d in rows if not d["danger"]]

    print("\n[1] 現行「危」判定の実成績 (危=飛ぶ/おいしくないか?)")
    _line("危 (現行ロジック)", stats(danger))
    _line("非危 (全体)", stats(non_danger))
    # 同じ人気帯(odds<=8)の中で危 vs 非危を比べる (人気帯を揃えた対照)
    pop = [d for d in rows if 0 < d["odds"] <= DANGER_ODDS_MAX]
    pop_danger = [d for d in pop if d["danger"]]
    pop_safe = [d for d in pop if not d["danger"]]
    print("\n  -- odds<=8 の人気帯に絞った対照 --")
    _line("人気帯 ∩ 危", stats(pop_danger))
    _line("人気帯 ∩ 非危", stats(pop_safe))

    print("\n[2] 「危 ∩ 穴注目」矛盾ケース (同時点灯はどちらが正しかったか)")
    both = [d for d in danger if d["ms"] == "穴注目"]
    danger_only = [d for d in danger if d["ms"] != "穴注目"]
    ana = [d for d in rows if d["ms"] == "穴注目"]
    _line("危 ∩ 穴注目 (矛盾)", stats(both))
    _line("危 (穴注目でない)", stats(danger_only))
    _line("穴注目 (全体)", stats(ana))
    # market_signal が何かしら付いてる危 (買いシグナルと衝突)
    print("\n  -- 危に重なった market_signal の内訳 --")
    by_ms = defaultdict(list)
    for d in danger:
        by_ms[d["ms"] or "(なし)"].append(d)
    for ms, sub in sorted(by_ms.items(), key=lambda kv: -len(kv[1])):
        _line(f"危 ∩ {ms}", stats(sub))

    print("\n[3] odds_move 改善案 (危 かつ スマートマネー無し)")
    # odds_move <= 1.0 はオッズ下落=買われた=スマートマネー流入の解釈
    # 改善案: 危 かつ odds_move が下落していない (>1.0 or None) = 本当の過剰人気
    danger_with_move = [d for d in danger if isinstance(d["odds_move"], (int, float))]
    smart = [d for d in danger_with_move if d["odds_move"] <= 1.0]  # オッズ下落=賢い金
    no_smart = [d for d in danger_with_move if d["odds_move"] > 1.0]  # オッズ上昇=見限られ
    print(f"  (危で odds_move あり: {len(danger_with_move)}/{len(danger)} 頭)")
    _line("危 ∩ オッズ下落(賢い金)", stats(smart))
    _line("危 ∩ オッズ上昇(見限り)", stats(no_smart))
    print("\n  → 「危 ∩ オッズ下落」の複勝率/ROI が「危 ∩ オッズ上昇」より高ければ、")
    print("     odds_move を見ずに一律「危」とするのは誤判定を含む = 改善余地あり。")


if __name__ == "__main__":
    main()

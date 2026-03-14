#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三連単フォーメーション・バックテスト

条件特化型フォーメーション群のバックテスト:
  - Pattern A: 人気馬2着固定  ▲▲▲▲ → 〇 → ▲▲▲▲△△△
  - Pattern B: 人気馬3着固定  ▲▲▲▲△△△ → ▲▲▲▲△△△ → 〇
  - (将来追加) 内枠狙い撃ち / 差し決着狙い / 同質馬集中 etc.

Usage:
    python -m ml.simulate_formation
    python -m ml.simulate_formation --pattern all
    python -m ml.simulate_formation --pattern fav2nd
    python -m ml.simulate_formation --verbose
"""

import json
import sys
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.simulate_sanrentan_ev import (
    load_backtest_cache, load_sanrentan_payouts,
    extract_win_probs, extract_market_probs, harville_prob,
)


# ===========================================================================
# Data types
# ===========================================================================

@dataclass
class FormationTickets:
    """フォーメーションから生成された買い目"""
    pattern_name: str
    tickets: List[Tuple[int, int, int]]
    o_horse: Optional[int] = None  # 固定馬の馬番
    meta: dict = field(default_factory=dict)


@dataclass
class PatternResult:
    name: str
    total_races: int = 0
    fired_races: int = 0  # パターン発動レース数
    total_tickets: int = 0
    total_invested: int = 0
    total_return: int = 0
    total_hits: int = 0
    monthly: dict = field(default_factory=dict)
    hit_details: list = field(default_factory=list)

    @property
    def roi(self) -> float:
        return self.total_return / self.total_invested * 100 if self.total_invested else 0

    @property
    def hit_rate(self) -> float:
        return self.total_hits / self.fired_races * 100 if self.fired_races else 0

    @property
    def avg_tickets(self) -> float:
        return self.total_tickets / self.fired_races if self.fired_races else 0

    @property
    def avg_payout(self) -> int:
        return self.total_return // self.total_hits if self.total_hits else 0


# ===========================================================================
# Entry analysis helpers
# ===========================================================================

def analyze_entries(entries: list) -> dict:
    """エントリーから各種指標を計算"""
    valid = [e for e in entries if (e.get("odds") or 0) > 0]
    if len(valid) < 3:
        return {}

    # 各馬のP%, W%(estimated), Gap
    horses = []
    for e in valid:
        odds = e["odds"]
        win_ev = e.get("win_ev") or 0
        p_raw = e.get("pred_proba_p_raw") or 0
        w_est = win_ev / odds if odds > 0 and win_ev > 0 else 0
        # P%がない場合はフォールバック
        if p_raw <= 0:
            p_raw = 1.0 / odds  # rough estimate
        gap = p_raw - w_est
        horses.append({
            "umaban": e["umaban"],
            "horse_name": e.get("horse_name", "?"),
            "odds": odds,
            "win_ev": win_ev,
            "p_raw": p_raw,
            "w_est": w_est,
            "gap": gap,
            "ar_deviation": e.get("ar_deviation") or 0,
            "is_value_bet": e.get("is_value_bet", False),
            "finish_position": e.get("finish_position"),
            "running_style": e.get("running_style", ""),
            "waku": e.get("waku", 0),
        })

    # P%で降順ソート
    horses.sort(key=lambda h: -h["p_raw"])

    # Confidence gap
    conf_gap = horses[0]["p_raw"] - horses[1]["p_raw"] if len(horses) >= 2 else 0

    # P% top3 share (荒れ予測の最強指標)
    p_sum = sum(h["p_raw"] for h in horses)
    p_top3_share = (sum(h["p_raw"] for h in horses[:3]) / p_sum
                    if p_sum > 0 else 0)

    # 1番人気オッズ
    fav_odds = min(h["odds"] for h in horses) if horses else 999

    # WinEV > 1.0 の馬数
    n_high_ev = sum(1 for h in horses if h["win_ev"] > 1.0)

    return {
        "horses": horses,
        "n_runners": len(valid),
        "conf_gap": conf_gap,
        "p_top3_share": p_top3_share,
        "fav_odds": fav_odds,
        "n_high_ev": n_high_ev,
        "valid": True,
    }


# ===========================================================================
# Pattern A: 人気馬2着固定
# ===========================================================================

def pattern_fav_2nd(analysis: dict, cfg: dict) -> List[FormationTickets]:
    """人気馬が2着に固定されるフォーメーション

    〇: odds <= max_odds & P%-W% Gap >= min_gap の馬 (2着固定)
    ▲: P%上位n_tri頭 (〇除く) → 1着候補
    △: 次のn_wide頭 → 3着追加候補
    Formation: ▲▲▲▲ → 〇 → ▲▲▲▲△△△
    """
    horses = analysis["horses"]
    max_odds = cfg.get("max_odds", 5.0)
    min_gap = cfg.get("min_gap", 0.15)
    n_tri = cfg.get("n_tri", 4)   # ▲の数
    n_wide = cfg.get("n_wide", 3)  # △の数
    max_tickets = cfg.get("max_tickets", 30)
    require_vb_in_1st = cfg.get("require_vb_in_1st", False)

    results = []

    # 〇候補: 人気馬(低オッズ) & Gap大
    o_candidates = [h for h in horses
                    if h["odds"] <= max_odds and h["gap"] >= min_gap]

    for o_horse in o_candidates:
        o_num = o_horse["umaban"]

        # ▲: P%上位(〇除く)
        others = [h for h in horses if h["umaban"] != o_num]
        tri_horses = others[:n_tri]

        # VBフィルター
        if require_vb_in_1st:
            has_vb = any(h["is_value_bet"] for h in tri_horses)
            if not has_vb:
                continue

        # △: 次のn_wide頭
        wide_horses = others[n_tri:n_tri + n_wide]

        # 1着候補 = ▲のみ
        first_nums = [h["umaban"] for h in tri_horses]
        # 3着候補 = ▲ + △
        third_nums = [h["umaban"] for h in tri_horses + wide_horses]

        # フォーメーション生成
        tickets = []
        for f in first_nums:
            for t in third_nums:
                if f != o_num and t != o_num and f != t:
                    tickets.append((f, o_num, t))

        # 点数制限
        tickets = tickets[:max_tickets]

        if tickets:
            results.append(FormationTickets(
                pattern_name="fav_2nd",
                tickets=tickets,
                o_horse=o_num,
                meta={
                    "o_name": o_horse["horse_name"],
                    "o_odds": o_horse["odds"],
                    "o_gap": o_horse["gap"],
                },
            ))

    return results


# ===========================================================================
# Pattern B: 人気馬3着固定
# ===========================================================================

def pattern_fav_3rd(analysis: dict, cfg: dict) -> List[FormationTickets]:
    """人気馬が3着に沈むフォーメーション

    〇: odds <= max_odds & P%-W% Gap >= min_gap の馬 (3着固定)
    ▲: P%上位n_tri頭 (〇除く) → 1着・2着候補
    △: 次のn_wide頭 → 1着・2着追加候補
    Formation: ▲▲▲▲△△△ → ▲▲▲▲△△△ → 〇
    """
    horses = analysis["horses"]
    max_odds = cfg.get("max_odds", 5.0)
    min_gap = cfg.get("min_gap", 0.15)
    n_tri = cfg.get("n_tri", 4)
    n_wide = cfg.get("n_wide", 3)
    max_tickets = cfg.get("max_tickets", 49)

    results = []

    o_candidates = [h for h in horses
                    if h["odds"] <= max_odds and h["gap"] >= min_gap]

    for o_horse in o_candidates:
        o_num = o_horse["umaban"]

        others = [h for h in horses if h["umaban"] != o_num]
        tri_horses = others[:n_tri]
        wide_horses = others[n_tri:n_tri + n_wide]

        # 1着・2着候補 = ▲ + △
        top_nums = [h["umaban"] for h in tri_horses + wide_horses]

        tickets = []
        for f in top_nums:
            for s in top_nums:
                if f != s and f != o_num and s != o_num:
                    tickets.append((f, s, o_num))

        tickets = tickets[:max_tickets]

        if tickets:
            results.append(FormationTickets(
                pattern_name="fav_3rd",
                tickets=tickets,
                o_horse=o_num,
                meta={
                    "o_name": o_horse["horse_name"],
                    "o_odds": o_horse["odds"],
                    "o_gap": o_horse["gap"],
                },
            ))

    return results


# ===========================================================================
# Pattern C: VB頭フォーメーション (VB馬が1着に来る)
# ===========================================================================

def pattern_vb_head(analysis: dict, cfg: dict) -> List[FormationTickets]:
    """VB馬が1着に来るフォーメーション

    ★: VB馬 (win_ev >= min_win_ev) → 1着固定
    ▲: P%上位n_tri頭 (★除く) → 2着候補
    △: 次のn_wide頭 → 3着追加候補
    Formation: ★ → ▲▲▲▲ → ▲▲▲▲△△△
    """
    horses = analysis["horses"]
    min_win_ev = cfg.get("min_win_ev", 1.5)
    min_odds = cfg.get("min_odds", 10.0)  # 低オッズVBは除外(旨みが薄い)
    n_tri = cfg.get("n_tri", 4)
    n_wide = cfg.get("n_wide", 3)
    max_tickets = cfg.get("max_tickets", 28)

    results = []

    # ★候補: VB or 高win_ev + 中穴以上
    vb_candidates = [h for h in horses
                     if h["win_ev"] >= min_win_ev
                     and h["odds"] >= min_odds]

    for vb in vb_candidates:
        vb_num = vb["umaban"]

        others = [h for h in horses if h["umaban"] != vb_num]
        tri_horses = others[:n_tri]
        wide_horses = others[n_tri:n_tri + n_wide]

        second_nums = [h["umaban"] for h in tri_horses]
        third_nums = [h["umaban"] for h in tri_horses + wide_horses]

        tickets = []
        for s in second_nums:
            for t in third_nums:
                if s != t and s != vb_num and t != vb_num:
                    tickets.append((vb_num, s, t))

        tickets = tickets[:max_tickets]

        if tickets:
            results.append(FormationTickets(
                pattern_name="vb_head",
                tickets=tickets,
                o_horse=vb_num,
                meta={
                    "vb_name": vb["horse_name"],
                    "vb_odds": vb["odds"],
                    "vb_win_ev": vb["win_ev"],
                },
            ))

    return results


# ===========================================================================
# Strategy configurations
# ===========================================================================

# ===========================================================================
# EV pruning: フォーメーション → Distortionスコアで刈り込み
# ===========================================================================

def prune_by_distortion(
    tickets: List[Tuple[int, int, int]],
    model_probs: Dict[int, float],
    market_probs: Dict[int, float],
    min_dist: float = 1.0,
    max_tickets: int = 15,
) -> List[Tuple[Tuple[int, int, int], float]]:
    """チケットをDistortionスコアでランク付けし、低スコアを除外

    Returns: [(ticket, distortion_ratio), ...] distortion降順
    """
    scored = []
    for t in tickets:
        a, b, c = t
        p_model = harville_prob(model_probs, a, b, c)
        p_market = harville_prob(market_probs, a, b, c)
        if p_model > 0 and p_market > 0:
            ratio = p_model / p_market
            scored.append((t, ratio))

    # Distortion降順でソート
    scored.sort(key=lambda x: -x[1])

    # min_dist以上のみ残す
    scored = [(t, r) for t, r in scored if r >= min_dist]

    # 点数制限
    return scored[:max_tickets]


# ===========================================================================
# Strategy configurations
# ===========================================================================

def check_race_filter(analysis: dict, race_filter: dict) -> bool:
    """レースレベルフィルターのチェック"""
    if not race_filter:
        return True
    if "max_p_top3_share" in race_filter:
        if analysis["p_top3_share"] > race_filter["max_p_top3_share"]:
            return False
    if "min_fav_odds" in race_filter:
        if analysis["fav_odds"] < race_filter["min_fav_odds"]:
            return False
    if "min_runners" in race_filter:
        if analysis["n_runners"] < race_filter["min_runners"]:
            return False
    if "max_conf_gap" in race_filter:
        if analysis["conf_gap"] > race_filter["max_conf_gap"]:
            return False
    if "min_n_high_ev" in race_filter:
        if analysis["n_high_ev"] < race_filter["min_n_high_ev"]:
            return False
    return True


STRATEGIES = {
    # ============================================================
    # Baseline (フィルターなし)
    # ============================================================
    "Fav2nd_Base": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
    },
    "Fav3rd_Base": {
        "pattern": "fav_3rd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 42},
    },

    # ============================================================
    # P%Share < 0.40 (荒れ予測フィルター)
    # ============================================================
    "F2_Sh40": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.40},
    },
    "F2_Sh40_G25": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.25, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.40},
    },
    "F3_Sh40": {
        "pattern": "fav_3rd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 42},
        "race_filter": {"max_p_top3_share": 0.40},
    },
    "F3_Sh40_Nar": {
        "pattern": "fav_3rd",
        "cfg": {"max_odds": 3.0, "min_gap": 0.15, "n_tri": 3, "n_wide": 3,
                "max_tickets": 30},
        "race_filter": {"max_p_top3_share": 0.40},
    },

    # ============================================================
    # P%Share < 0.45 (やや緩め)
    # ============================================================
    "F2_Sh45": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45},
    },
    "F2_Sh45_G25": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.25, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45},
    },
    "F3_Sh45": {
        "pattern": "fav_3rd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 42},
        "race_filter": {"max_p_top3_share": 0.45},
    },

    # ============================================================
    # Fav >= 3.0 (人気薄1番人気)
    # ============================================================
    "F2_Fav3": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
        "race_filter": {"min_fav_odds": 3.0},
    },
    "F3_Fav3": {
        "pattern": "fav_3rd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 42},
        "race_filter": {"min_fav_odds": 3.0},
    },
    "F2_Fav3_Sh45": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
        "race_filter": {"min_fav_odds": 3.0, "max_p_top3_share": 0.45},
    },
    "F3_Fav3_Sh45": {
        "pattern": "fav_3rd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 42},
        "race_filter": {"min_fav_odds": 3.0, "max_p_top3_share": 0.45},
    },

    # ============================================================
    # 多頭数 (16+) + 荒れフィルター
    # ============================================================
    "F2_16h_Sh45": {
        "pattern": "fav_2nd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 28},
        "race_filter": {"min_runners": 16, "max_p_top3_share": 0.45},
    },
    "F3_16h_Sh45": {
        "pattern": "fav_3rd",
        "cfg": {"max_odds": 5.0, "min_gap": 0.15, "n_tri": 4, "n_wide": 3,
                "max_tickets": 42},
        "race_filter": {"min_runners": 16, "max_p_top3_share": 0.45},
    },

    # ============================================================
    # VB頭 + 荒れフィルター
    # ============================================================
    "VB_Sh45": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45},
    },
    "VB_Fav3": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"min_fav_odds": 3.0},
    },
    "VB_Sh40_Fav3": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.40, "min_fav_odds": 3.0},
    },

    # ============================================================
    # VB頭 深堀り (VB_Sh40_Fav3ベース)
    # ============================================================
    # 点数削減: n_tri/n_wide を絞る
    "VB_40F3_Nar": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 3, "n_wide": 2, "max_tickets": 15},
        "race_filter": {"max_p_top3_share": 0.40, "min_fav_odds": 3.0},
    },
    # WinEV閾値を上げる
    "VB_40F3_HiEV": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 2.0, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.40, "min_fav_odds": 3.0},
    },
    # Fav >= 3.5 (さらに絞る)
    "VB_40F35": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.40, "min_fav_odds": 3.5},
    },
    # P%Share < 0.45 (少し緩める)
    "VB_45F3": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
    },
    "VB_45F3_Nar": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 3, "n_wide": 2, "max_tickets": 15},
        "race_filter": {"max_p_top3_share": 0.45, "min_fav_odds": 3.0},
    },
    # 多頭数追加
    "VB_40F3_16h": {
        "pattern": "vb_head",
        "cfg": {"min_win_ev": 1.5, "min_odds": 10.0,
                "n_tri": 4, "n_wide": 3, "max_tickets": 28},
        "race_filter": {"max_p_top3_share": 0.40, "min_fav_odds": 3.0,
                        "min_runners": 16},
    },
    # Combo + 荒れフィルター深堀り
    "Cmb_40F3": {
        "pattern": "combo_fav2_vb1",
        "cfg": {"max_odds_o": 5.0, "min_gap_o": 0.15,
                "min_win_ev_vb": 1.2, "min_odds_vb": 8.0,
                "n_wide": 5, "max_tickets": 20},
        "race_filter": {"max_p_top3_share": 0.40, "min_fav_odds": 3.0},
    },
    "Cmb_45F3_Nar": {
        "pattern": "combo_fav2_vb1",
        "cfg": {"max_odds_o": 5.0, "min_gap_o": 0.15,
                "min_win_ev_vb": 1.2, "min_odds_vb": 8.0,
                "n_wide": 3, "max_tickets": 12},
        "race_filter": {"min_fav_odds": 3.0, "max_p_top3_share": 0.45},
    },

    # ============================================================
    # Combo + 荒れフィルター
    # ============================================================
    "Cmb_Sh45": {
        "pattern": "combo_fav2_vb1",
        "cfg": {"max_odds_o": 5.0, "min_gap_o": 0.15,
                "min_win_ev_vb": 1.2, "min_odds_vb": 8.0,
                "n_wide": 5, "max_tickets": 20},
        "race_filter": {"max_p_top3_share": 0.45},
    },
    "Cmb_Fav3": {
        "pattern": "combo_fav2_vb1",
        "cfg": {"max_odds_o": 5.0, "min_gap_o": 0.15,
                "min_win_ev_vb": 1.2, "min_odds_vb": 8.0,
                "n_wide": 5, "max_tickets": 20},
        "race_filter": {"min_fav_odds": 3.0},
    },
    "Cmb_Fav3_Sh45": {
        "pattern": "combo_fav2_vb1",
        "cfg": {"max_odds_o": 5.0, "min_gap_o": 0.15,
                "min_win_ev_vb": 1.2, "min_odds_vb": 8.0,
                "n_wide": 5, "max_tickets": 20},
        "race_filter": {"min_fav_odds": 3.0, "max_p_top3_share": 0.45},
    },
}

PATTERN_FUNCS = {
    "fav_2nd": pattern_fav_2nd,
    "fav_3rd": pattern_fav_3rd,
    "vb_head": pattern_vb_head,
}


def pattern_combo_fav2_vb1(analysis: dict, cfg: dict) -> List[FormationTickets]:
    """VB馬1着 × 人気馬2着固定 × 広め3着

    ★(1着): VB馬 (win_ev高 + 中穴)
    〇(2着): 人気馬 (低odds + Gap大)
    △(3着): P%上位n_wide頭 (★〇除く)
    = ★ → 〇 → △△△△△
    """
    horses = analysis["horses"]
    max_odds_o = cfg.get("max_odds_o", 5.0)
    min_gap_o = cfg.get("min_gap_o", 0.20)
    min_win_ev = cfg.get("min_win_ev_vb", 1.3)
    min_odds_vb = cfg.get("min_odds_vb", 8.0)
    n_wide = cfg.get("n_wide", 5)
    max_tickets = cfg.get("max_tickets", 20)

    results = []

    o_candidates = [h for h in horses
                    if h["odds"] <= max_odds_o and h["gap"] >= min_gap_o]
    vb_candidates = [h for h in horses
                     if h["win_ev"] >= min_win_ev and h["odds"] >= min_odds_vb]

    for o_horse in o_candidates:
        for vb in vb_candidates:
            if vb["umaban"] == o_horse["umaban"]:
                continue

            others = [h for h in horses
                      if h["umaban"] not in (o_horse["umaban"], vb["umaban"])]
            third_horses = others[:n_wide]

            tickets = []
            for t in third_horses:
                tickets.append((vb["umaban"], o_horse["umaban"], t["umaban"]))

            tickets = tickets[:max_tickets]

            if tickets:
                results.append(FormationTickets(
                    pattern_name="combo_fav2_vb1",
                    tickets=tickets,
                    o_horse=o_horse["umaban"],
                    meta={
                        "vb_name": vb["horse_name"],
                        "vb_odds": vb["odds"],
                        "o_name": o_horse["horse_name"],
                        "o_odds": o_horse["odds"],
                    },
                ))

    return results


PATTERN_FUNCS["combo_fav2_vb1"] = pattern_combo_fav2_vb1


# ===========================================================================
# Backtest engine
# ===========================================================================

def run_formation_backtest(
    cache: list,
    payouts: Dict[str, list],
    strategies: dict = STRATEGIES,
    verbose: bool = False,
) -> Dict[str, PatternResult]:
    """フォーメーション戦略のバックテスト"""

    results = {name: PatternResult(name=name) for name in strategies}

    for race in cache:
        race_id = race["race_id"]
        entries = race.get("entries", [])

        if race.get("track_type") in ("obstacle", "steeplechase"):
            continue

        race_payouts = payouts.get(race_id)
        if not race_payouts:
            continue

        analysis = analyze_entries(entries)
        if not analysis.get("valid"):
            continue
        if analysis["n_runners"] < 5:
            continue

        month = f"{race_id[:4]}-{race_id[4:6]}"
        payout_map = {t: p for t, p in race_payouts}

        # EV刈り込み用に確率を事前計算
        model_probs = extract_win_probs(entries)
        market_probs = extract_market_probs(entries)

        for strat_name, strat_cfg in strategies.items():
            # レースフィルター
            race_filter = strat_cfg.get("race_filter")
            if not check_race_filter(analysis, race_filter):
                continue

            pattern_name = strat_cfg["pattern"]
            cfg = strat_cfg["cfg"]

            func = PATTERN_FUNCS.get(pattern_name)
            if not func:
                continue

            formations = func(analysis, cfg)
            if not formations:
                continue

            # 全formationの買い目をマージ（重複除去）
            all_tickets: Set[Tuple[int, int, int]] = set()
            for fm in formations:
                all_tickets.update(fm.tickets)

            # EV刈り込み
            prune_cfg = strat_cfg.get("prune")
            if prune_cfg and model_probs and market_probs:
                pruned = prune_by_distortion(
                    list(all_tickets), model_probs, market_probs,
                    min_dist=prune_cfg.get("min_dist", 1.0),
                    max_tickets=prune_cfg.get("max_tickets", 15),
                )
                tickets = [t for t, _ in pruned]
            else:
                tickets = list(all_tickets)

            sr = results[strat_name]
            sr.total_races += 1
            sr.fired_races += 1
            sr.total_tickets += len(tickets)
            sr.total_invested += len(tickets) * 100

            if month not in sr.monthly:
                sr.monthly[month] = {"races": 0, "tickets": 0,
                                     "inv": 0, "ret": 0, "hits": 0}
            m = sr.monthly[month]
            m["races"] += 1
            m["tickets"] += len(tickets)
            m["inv"] += len(tickets) * 100

            for ticket in tickets:
                if ticket in payout_map:
                    pay = payout_map[ticket]
                    sr.total_hits += 1
                    sr.total_return += pay
                    m["hits"] += 1
                    m["ret"] += pay

                    meta_str = ""
                    for fm in formations:
                        if ticket in fm.tickets:
                            meta_str = json.dumps(fm.meta, ensure_ascii=False)
                            break
                    sr.hit_details.append((race_id, ticket, pay, meta_str))

                    if verbose:
                        t = ticket
                        print(f"  HIT [{strat_name}] {race_id} "
                              f"{t[0]:>2}-{t[1]:>2}-{t[2]:>2} "
                              f"Pay={pay:>10,} {meta_str}")

    return results


# ===========================================================================
# Verify specific races
# ===========================================================================

def verify_example_races(cache: list, payouts: Dict[str, list]):
    """ユーザーが見つけた例題レースを検証"""
    examples = [
        ("2026030110011205", "小倉5R 2026-03-01", 113530),
        ("2026022209010203", "阪神3R 2026-02-22", 232990),
    ]

    print(f"\n{'='*100}")
    print(f"  例題レース検証")
    print(f"{'='*100}")

    for race_id, label, expected_pay in examples:
        race = next((r for r in cache if r["race_id"] == race_id), None)
        if not race:
            print(f"\n  {label}: not found in cache")
            continue

        entries = race.get("entries", [])
        analysis = analyze_entries(entries)
        if not analysis.get("valid"):
            print(f"\n  {label}: invalid entries")
            continue

        race_payouts = payouts.get(race_id)
        if not race_payouts:
            print(f"\n  {label}: no payout data")
            continue

        payout_map = {t: p for t, p in race_payouts}
        actual_ticket = None
        actual_pay = 0
        for t, p in race_payouts:
            if p == expected_pay or abs(p - expected_pay) < 100:
                actual_ticket = t
                actual_pay = p
                break

        if not actual_ticket:
            # 最高配当を取得
            actual_ticket, actual_pay = max(race_payouts, key=lambda x: x[1])

        print(f"\n--- {label} ---")
        print(f"  的中: {actual_ticket[0]}-{actual_ticket[1]}-{actual_ticket[2]}"
              f" = {actual_pay:,}円")

        # 確率計算
        model_probs = extract_win_probs(entries)
        market_probs = extract_market_probs(entries)

        print(f"  Race: n={analysis['n_runners']}, "
              f"P%Share={analysis['p_top3_share']:.3f}, "
              f"FavOdds={analysis['fav_odds']:.1f}, "
              f"ConfGap={analysis['conf_gap']:.3f}")

        # 各パターンで検証
        for strat_name, strat_cfg in STRATEGIES.items():
            race_filter = strat_cfg.get("race_filter")
            if not check_race_filter(analysis, race_filter):
                continue

            pattern_name = strat_cfg["pattern"]
            cfg = strat_cfg["cfg"]
            func = PATTERN_FUNCS.get(pattern_name)
            if not func:
                continue

            formations = func(analysis, cfg)
            all_tickets = set()
            for fm in formations:
                all_tickets.update(fm.tickets)

            raw_count = len(all_tickets)

            # EV刈り込み適用
            prune_cfg = strat_cfg.get("prune")
            if prune_cfg and model_probs and market_probs:
                pruned = prune_by_distortion(
                    list(all_tickets), model_probs, market_probs,
                    min_dist=prune_cfg.get("min_dist", 1.0),
                    max_tickets=prune_cfg.get("max_tickets", 15),
                )
                final_tickets = set(t for t, _ in pruned)
                prune_label = f"({raw_count}->{len(final_tickets)})"
            else:
                final_tickets = all_tickets
                prune_label = ""

            caught = actual_ticket in final_tickets
            if caught:
                for fm in formations:
                    if actual_ticket in fm.tickets:
                        meta = fm.meta
                        break
                # Distortionスコアも表示
                p_m = harville_prob(model_probs, *actual_ticket)
                p_mk = harville_prob(market_probs, *actual_ticket)
                dist = p_m / p_mk if p_mk > 0 else 0
                print(f"  {strat_name:<22} {len(final_tickets):>3}点 "
                      f"{prune_label:<10} -> HIT! Dist={dist:.2f} "
                      f"{json.dumps(meta, ensure_ascii=False)}")
            else:
                print(f"  {strat_name:<22} {len(final_tickets):>3}点 "
                      f"{prune_label:<10} -> miss")


# ===========================================================================
# Output
# ===========================================================================

def print_summary(results: Dict[str, PatternResult]):
    print(f"\n{'='*110}")
    print(f"  三連単フォーメーション バックテスト結果")
    print(f"{'='*110}")
    print(f"{'Strategy':<22} {'Fire':>5} {'Tkts':>7} {'Avg':>5} {'Hits':>4} "
          f"{'HitR%':>6} {'Invested':>11} {'Return':>11} {'ROI%':>7} "
          f"{'AvgPay':>9} {'月投資':>8}")
    print(f"{'-'*110}")

    for name in STRATEGIES:
        sr = results[name]
        if sr.fired_races == 0:
            continue
        n_months = max(len(sr.monthly), 1)
        monthly_inv = sr.total_invested / n_months
        marker = " **" if sr.roi >= 100 else ""
        print(f"{name:<22} {sr.fired_races:>5} {sr.total_tickets:>7} "
              f"{sr.avg_tickets:>5.1f} {sr.total_hits:>4} {sr.hit_rate:>5.1f}% "
              f"{sr.total_invested:>10,} {sr.total_return:>10,} "
              f"{sr.roi:>6.1f}%{marker} {sr.avg_payout:>8,} "
              f"{monthly_inv:>8,.0f}")

    print(f"{'-'*110}")


def print_monthly(results: Dict[str, PatternResult]):
    # ROI上位の戦略を月次表示
    promising = sorted(results.values(), key=lambda r: -r.roi)
    shown = 0
    for sr in promising:
        if sr.fired_races < 50 or sr.total_hits < 2:
            continue
        if shown >= 5:
            break
        shown += 1

        print(f"\n--- {sr.name} (ROI {sr.roi:.1f}%, "
              f"{sr.fired_races}R, {sr.total_hits}hits) ---")
        cum = 0
        for month in sorted(sr.monthly):
            m = sr.monthly[month]
            m_roi = m["ret"] / m["inv"] * 100 if m["inv"] else 0
            pnl = m["ret"] - m["inv"]
            cum += pnl
            print(f"  {month} {m['races']:>4}R {m['tickets']:>5}点 "
                  f"{m['hits']}的中 Inv={m['inv']:>8,} Ret={m['ret']:>8,} "
                  f"ROI={m_roi:>6.1f}% PnL={pnl:>+9,} Cum={cum:>+10,}")


def print_hits(results: Dict[str, PatternResult]):
    all_hits = []
    for sr in results.values():
        for race_id, ticket, pay, meta in sr.hit_details:
            all_hits.append((sr.name, race_id, ticket, pay, meta))

    if not all_hits:
        print("\n  的中なし")
        return

    # 重複除去・高配当順
    unique = {}
    for name, race_id, ticket, pay, meta in all_hits:
        key = (race_id, ticket)
        if key not in unique:
            unique[key] = {"pay": pay, "meta": meta, "strats": []}
        unique[key]["strats"].append(name)

    print(f"\n{'='*100}")
    print(f"  的中詳細（配当降順 Top 30）")
    print(f"{'='*100}")

    for (race_id, ticket), info in sorted(
            unique.items(), key=lambda x: -x[1]["pay"])[:30]:
        t = ticket
        strats = ", ".join(info["strats"][:3])
        print(f"  {race_id} {t[0]:>2}-{t[1]:>2}-{t[2]:>2} "
              f"Pay={info['pay']:>10,} [{strats}]")


# ===========================================================================
# Main
# ===========================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", default="all",
                        help="Pattern to run: all, fav2nd, fav3rd, vb, combo")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--verify", action="store_true",
                        help="Verify example races")
    args = parser.parse_args()

    print("=" * 100)
    print("  KeibaCICD 三連単フォーメーション バックテスト")
    print("=" * 100)

    cache = load_backtest_cache()
    race_codes = [r["race_id"] for r in cache]
    payouts = load_sanrentan_payouts(race_codes)
    print(f"  配当データ: {len(payouts):,}/{len(race_codes):,} races")

    # パターン選択
    if args.pattern != "all":
        pattern_map = {
            "fav2nd": "fav_2nd",
            "fav3rd": "fav_3rd",
            "vb": "vb_head",
            "combo": "combo_fav2_vb1",
        }
        target = pattern_map.get(args.pattern, args.pattern)
        strats = {k: v for k, v in STRATEGIES.items()
                  if v["pattern"] == target}
    else:
        strats = STRATEGIES

    if args.verify:
        verify_example_races(cache, payouts)

    results = run_formation_backtest(cache, payouts, strats, args.verbose)

    print_summary(results)
    print_monthly(results)
    print_hits(results)


if __name__ == "__main__":
    main()

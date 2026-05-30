#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bettype_efficiency.py 性質テスト (Session 138 / Phase 2 券種効率ビュー)

合成オッズ・期待リターンの数学、 強さ総合判定 (W/P/ADR + specialist)、
プラン構築、 エッジケースを手計算ケースでロックする。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_bettype_efficiency.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.strategies import bettype_efficiency as be
from ml.strategies import harville as hv


def _approx(a, b, tol=1e-6):
    return abs(a - b) < tol


# =====================================================================
# 合成オッズ・期待リターン (③) — 数学の核
# =====================================================================

def test_synthetic_odds_inverse_definition():
    """合成オッズ G = 1/Σ(1/oₖ)。 3点とも 6倍 → G=2.0"""
    g, ev, sum_p, cov = be.synthetic_and_ev([0.1, 0.1, 0.1], [6.0, 6.0, 6.0])
    assert _approx(g, 2.0)
    assert _approx(cov, 1.0)


def test_synthetic_single_leg_equals_odds():
    """1点だけなら 合成オッズ = その点のオッズ"""
    g, ev, sum_p, cov = be.synthetic_and_ev([0.3], [4.5])
    assert _approx(g, 4.5)
    # EV = p*odds
    assert _approx(ev, 0.3 * 4.5)


def test_expected_return_identity_G_times_sumP():
    """EV = Σpₖ/Σ(1/oₖ) = G·Σpₖ (期待値の線形性)"""
    probs = [0.05, 0.08, 0.02]
    odds = [10.0, 5.0, 20.0]
    g, ev, sum_p, cov = be.synthetic_and_ev(probs, odds)
    inv = sum(1 / o for o in odds)
    assert _approx(g, 1 / inv)
    assert _approx(sum_p, sum(probs))
    assert _approx(ev, sum(probs) / inv)
    assert _approx(ev, g * sum(probs))


def test_expected_return_wide_multihit_via_linearity():
    """ワイド多重的中: 個別 pₖ の和でも EV は線形性で正しい。
    例: 2点とも当たりうる (重なる) でも EV = Σpₖ·(stakeₖ·oₖ)/S は線形和で表せる。"""
    # pₖ は「その点が当たる確率」(重複してよい)。 EV は Σpₖ/Σ(1/oₖ)。
    g, ev, sum_p, cov = be.synthetic_and_ev([0.4, 0.35], [3.0, 4.0])
    inv = 1 / 3.0 + 1 / 4.0
    assert _approx(ev, (0.4 + 0.35) / inv)


def test_missing_odds_coverage_and_exclusion():
    """オッズ未取得 (None) の点は G/EV から除外し coverage に反映"""
    g, ev, sum_p, cov = be.synthetic_and_ev([0.1, 0.1], [5.0, None])
    assert _approx(cov, 0.5)
    assert _approx(g, 5.0)          # None 点を除いた 1点のみ
    assert _approx(ev, 0.1 * 5.0)   # funded 点の p のみ
    assert _approx(sum_p, 0.2)      # sum_p は全点 (表示用)


def test_all_odds_missing_returns_none():
    g, ev, sum_p, cov = be.synthetic_and_ev([0.1, 0.1], [None, None])
    assert g is None and ev is None
    assert _approx(cov, 0.0)


# =====================================================================
# top3 集合分布 (ワイド/複勝の ≥1的中)
# =====================================================================

def test_top3_set_distribution_sums_to_one():
    probs = hv.normalize({1: 0.4, 2: 0.3, 3: 0.2, 4: 0.1})
    dist = be.top3_set_distribution(probs)
    assert _approx(sum(dist.values()), 1.0, tol=1e-9)
    # 全 C(4,3)=4 集合
    assert len(dist) == 4


def test_fukusho_matches_harville_place():
    probs = hv.normalize({1: 0.4, 2: 0.3, 3: 0.2, 4: 0.1})
    dist = be.top3_set_distribution(probs)
    # 馬1が top3 (集合分布での和) == harville place_prob(k=3)
    via_dist = sum(p for s, p in dist.items() if 1 in s)
    via_hv = hv.place_prob(probs, [1], 3)
    assert _approx(via_dist, via_hv, tol=1e-9)


# =====================================================================
# 強さ総合判定 (①)
# =====================================================================

def _race(entries, **race_kw):
    r = {"race_id": "2026010105010101", "num_runners": len(entries),
         "entries": entries}
    r.update(race_kw)
    return r


def _e(umaban, w, p, adr, odds=5.0, name=None, **kw):
    d = {"umaban": umaban, "horse_name": name or f"H{umaban}",
         "pred_proba_w_cal": w, "pred_proba_p": p, "ar_deviation": adr,
         "odds": odds, "place_odds_min": 1.5}
    d.update(kw)
    return d


def test_composite_axis_is_strongest_all_signals():
    """W/P/ADR 全部トップの馬が composite 1位 = 軸◎"""
    entries = [
        _e(1, 0.30, 0.60, 65.0),   # 全部最強
        _e(2, 0.20, 0.40, 55.0),
        _e(3, 0.10, 0.20, 45.0),
    ]
    strengths, spec = be.compute_strengths(_race(entries))
    assert spec is None
    assert strengths[0].umaban == 1
    assert strengths[0].rank_composite == 1
    assert strengths[0].rank_w == 1 and strengths[0].rank_p == 1 and strengths[0].rank_adr == 1


def test_composite_weight_shifts_axis():
    """重みで軸が変わる: P を強く重みづけすると P 最強馬が軸に"""
    entries = [
        _e(1, 0.40, 0.20, 50.0),   # W 強, P 弱
        _e(2, 0.20, 0.70, 50.0),   # W 弱, P 強
    ]
    s_w, _ = be.compute_strengths(_race(entries), weights=(5.0, 1.0, 1.0))
    s_p, _ = be.compute_strengths(_race(entries), weights=(1.0, 5.0, 1.0))
    assert s_w[0].umaban == 1
    assert s_p[0].umaban == 2


def test_missing_adr_uses_available_signals():
    """ADR が None (障害等) でも W/P で composite が出る"""
    entries = [
        _e(1, 0.30, 0.60, None),
        _e(2, 0.20, 0.40, None),
    ]
    strengths, _ = be.compute_strengths(_race(entries))
    assert strengths[0].umaban == 1
    assert strengths[0].z_adr is None
    assert strengths[0].composite is not None


def test_specialist_overlay_replaces_p_signal():
    """niigata1000 適用時、 P シグナルは overlay display_score に差し替わる"""
    entries = [
        _e(1, 0.20, 0.30, 50.0, niigata1000={"display_score": 0.05}),  # overlay で P 低
        _e(2, 0.20, 0.30, 50.0, niigata1000={"display_score": 0.55}),  # overlay で P 高
    ]
    race = _race(entries, niigata1000_applied=True)
    strengths, spec = be.compute_strengths(race)
    assert spec == "niigata1000"
    # display_score が高い 2番が P で勝り composite 上位 (W/ADR 同点)
    assert strengths[0].umaban == 2
    assert strengths[0].p_source == "specialist"
    assert _approx(strengths[0].pred_p, 0.55)


def test_specialist_ignored_when_disabled():
    entries = [
        _e(1, 0.20, 0.30, 50.0, niigata1000={"display_score": 0.05}),
        _e(2, 0.20, 0.30, 50.0, niigata1000={"display_score": 0.55}),
    ]
    race = _race(entries, niigata1000_applied=True)
    strengths, spec = be.compute_strengths(race, prefer_specialist=False)
    assert spec is None
    assert strengths[0].p_source == "model"


# =====================================================================
# プラン構築 (②③) + vs_tansho フラグ
# =====================================================================

def _combo_odds_full():
    """4頭 (1,2,3,4) の単純なオッズ表 (馬連/ワイド/馬単/三連系)"""
    def kb(*u, ordered):
        seq = list(u) if ordered else sorted(u)
        return "".join(f"{x:02d}" for x in seq)
    umaren = {kb(a, b, ordered=False): {"odds": 8.0}
              for a in range(1, 5) for b in range(a + 1, 5)}
    wide = {kb(a, b, ordered=False): {"odds": 3.0}
            for a in range(1, 5) for b in range(a + 1, 5)}
    umatan = {kb(a, b, ordered=True): {"odds": 16.0}
              for a in range(1, 5) for b in range(1, 5) if a != b}
    import itertools
    srp = {kb(*c, ordered=False): {"odds": 30.0}
           for c in itertools.combinations(range(1, 5), 3)}
    srt = {kb(*c, ordered=True): {"odds": 120.0}
           for c in itertools.permutations(range(1, 5), 3)}
    return {"tansho": {}, "fukusho": {}, "umaren": umaren, "wide": wide,
            "umatan": umatan, "sanrenpuku": srp, "sanrentan": srt}


def test_build_plans_structure_and_points():
    entries = [
        _e(1, 0.40, 0.60, 60.0, odds=2.0),
        _e(2, 0.25, 0.45, 55.0, odds=4.0),
        _e(3, 0.20, 0.40, 52.0, odds=6.0),
        _e(4, 0.15, 0.35, 50.0, odds=8.0),
    ]
    re_ = be.evaluate_race(_race(entries), _combo_odds_full())
    assert re_.axis_umaban == 1
    assert re_.partners == [2, 3, 4]
    bytype = {}
    for p in re_.plans:
        bytype.setdefault(p.bet_type, []).append(p)
    # 馬連は相手2,3 (相手4は partners が3頭しかないので無し)
    umaren_pts = sorted(p.n_points for p in bytype["umaren"])
    assert umaren_pts == [2, 3]
    # 三連複 ◎-相手3 = C(3,2)=3点
    assert bytype["sanrenpuku"][0].n_points == 3
    # 三連単 ◎→相手3 = P(3,2)=6点
    assert bytype["sanrentan"][0].n_points == 6


def test_hit_prob_umaren_is_sum_of_disjoint():
    """馬連流しの hit_prob = 各点 (排反) の harville 和"""
    entries = [
        _e(1, 0.40, 0.60, 60.0, odds=2.0),
        _e(2, 0.25, 0.45, 55.0, odds=4.0),
        _e(3, 0.20, 0.40, 52.0, odds=6.0),
        _e(4, 0.15, 0.35, 50.0, odds=8.0),
    ]
    re_ = be.evaluate_race(_race(entries), _combo_odds_full())
    win_probs = {s.umaban: s.win_prob for s in re_.strengths}
    umaren3 = next(p for p in re_.plans if p.bet_type == "umaren" and p.n_points == 3)
    expect = sum(hv.umaren_prob(win_probs, 1, b) for b in [2, 3, 4])
    assert _approx(umaren3.hit_prob, round(expect, 5), tol=1e-4)


def test_vs_tansho_flag_lt_when_synthetic_below_win_odds():
    """合成オッズ < 単オッズ → vs_tansho='lt' (広げる意味薄い)"""
    # 軸の単勝を高めに (10倍)、 馬連合成は 8/n と低い → lt
    entries = [
        _e(1, 0.40, 0.60, 60.0, odds=10.0),
        _e(2, 0.25, 0.45, 55.0, odds=4.0),
        _e(3, 0.20, 0.40, 52.0, odds=6.0),
        _e(4, 0.15, 0.35, 50.0, odds=8.0),
    ]
    re_ = be.evaluate_race(_race(entries), _combo_odds_full())
    umaren2 = next(p for p in re_.plans if p.bet_type == "umaren" and p.n_points == 2)
    # 馬連2点とも8倍 → 合成4.0 < 単10.0
    assert _approx(umaren2.synthetic_odds, 4.0)
    assert umaren2.vs_tansho == "lt"


def test_vs_tansho_flag_gt_when_synthetic_above_win_odds():
    entries = [
        _e(1, 0.40, 0.60, 60.0, odds=2.0),  # 単2.0倍 (低い)
        _e(2, 0.25, 0.45, 55.0, odds=4.0),
        _e(3, 0.20, 0.40, 52.0, odds=6.0),
        _e(4, 0.15, 0.35, 50.0, odds=8.0),
    ]
    re_ = be.evaluate_race(_race(entries), _combo_odds_full())
    umaren2 = next(p for p in re_.plans if p.bet_type == "umaren" and p.n_points == 2)
    # 合成4.0 > 単2.0
    assert umaren2.vs_tansho == "gt"


def test_tansho_plan_ev_matches_winprob_times_odds():
    entries = [
        _e(1, 0.40, 0.60, 60.0, odds=3.0),
        _e(2, 0.25, 0.45, 55.0, odds=4.0),
        _e(3, 0.20, 0.40, 52.0, odds=6.0),
    ]
    re_ = be.evaluate_race(_race(entries), _combo_odds_full())
    tansho = next(p for p in re_.plans if p.bet_type == "tansho")
    win_probs = {s.umaban: s.win_prob for s in re_.strengths}
    assert _approx(tansho.expected_return, round(win_probs[1] * 3.0, 3), tol=1e-3)
    assert tansho.vs_tansho is None  # 基準なのでフラグ無し


def test_axis_override():
    entries = [
        _e(1, 0.40, 0.60, 60.0, odds=2.0),
        _e(2, 0.25, 0.45, 55.0, odds=4.0),
        _e(3, 0.20, 0.40, 52.0, odds=6.0),
    ]
    re_ = be.evaluate_race(_race(entries), _combo_odds_full(), axis=2)
    assert re_.axis_umaban == 2
    assert 2 not in re_.partners


def test_missing_combo_odds_marks_coverage():
    """組み合わせオッズが空 → synthetic None, warning"""
    entries = [
        _e(1, 0.40, 0.60, 60.0, odds=2.0),
        _e(2, 0.25, 0.45, 55.0, odds=4.0),
        _e(3, 0.20, 0.40, 52.0, odds=6.0),
    ]
    empty_odds = {k: {} for k in ("tansho", "fukusho", "umaren", "wide",
                                   "umatan", "sanrenpuku", "sanrentan")}
    re_ = be.evaluate_race(_race(entries), empty_odds)
    umaren = [p for p in re_.plans if p.bet_type == "umaren"]
    assert all(p.synthetic_odds is None for p in umaren)
    assert any("市場オッズ" in w for w in re_.warnings)


def test_empty_entries_returns_none():
    re_ = be.evaluate_race(_race([]), _combo_odds_full())
    assert re_ is None


def test_small_field_places_k_2():
    """7頭以下は複勝/ワイド着内を 2着内で計算 (set_dist=None 経路)"""
    entries = [_e(i, 0.30 - 0.03 * i, 0.5 - 0.05 * i, 55 - i, odds=2.0 + i)
               for i in range(1, 7)]   # 6頭
    re_ = be.evaluate_race(_race(entries, num_runners=6), _combo_odds_full())
    fukusho = next(p for p in re_.plans if p.bet_type == "fukusho")
    assert 0.0 < fukusho.hit_prob <= 1.0


# =====================================================================
# レビュー (Session 138 adversarial) で指摘されたエッジ追加テスト
# =====================================================================

def test_expected_return_ev_one_boundary():
    """EV=1.0 の意味を明示: p=0.2, odds=5.0 → EV=1.0 (期待払戻=支出, 損益0)"""
    g, ev, sum_p, cov = be.synthetic_and_ev([0.2], [5.0])
    assert _approx(g, 5.0)
    assert _approx(ev, 1.0)   # EV=1.0 は損益分岐 (控除率下では稀)


def test_wide_nagashi_hit_is_union_not_naive_sum():
    """ワイド流しの hit_prob は top3 集合分布での ≥1的中 (排反集合の和) であり、
    個別 pair 確率の単純和ではない (多重的中分を二重計上しない)。 8頭=places_k 3。"""
    entries = [_e(u, 0.40 - 0.04 * u, 0.60 - 0.05 * u, 62.0 - u, odds=2.0 + u)
               for u in range(1, 9)]   # 8頭 → places_k=3
    re_ = be.evaluate_race(_race(entries, num_runners=8), _combo_odds_full())
    assert re_.axis_umaban == 1 and re_.partners[:3] == [2, 3, 4]
    win_probs = {s.umaban: s.win_prob for s in re_.strengths}
    wide3 = next(p for p in re_.plans if p.bet_type == "wide" and p.n_points == 3)
    dist = be.topk_set_distribution(win_probs, 3)
    pset = {2, 3, 4}
    union = sum(p for s, p in dist.items() if 1 in s and (s & pset))   # ≥1的中 (厳密)
    naive = sum(hv.wide_prob(win_probs, 1, b) for b in [2, 3, 4])       # 単純和 (過大)
    assert _approx(wide3.hit_prob, round(union, 5), tol=1e-4)
    # 複数相手で重なりがあるので union < naive のはず (二重計上しない証拠)
    assert union < naive - 1e-6
    # sum_p (期待的中点数) は naive 和 (線形性で EV 用) と一致
    assert _approx(wide3.sum_p, round(naive, 5), tol=1e-4)


def test_all_pred_w_none_emits_warning_no_crash():
    """全馬 pred_proba_w_cal=None → win_prob 全0、 クラッシュせず warning"""
    entries = [
        {"umaban": 1, "horse_name": "A", "pred_proba_w_cal": None,
         "pred_proba_p": 0.3, "ar_deviation": 50.0, "odds": 5.0, "place_odds_min": 1.5},
        {"umaban": 2, "horse_name": "B", "pred_proba_w_cal": None,
         "pred_proba_p": 0.2, "ar_deviation": 48.0, "odds": 6.0, "place_odds_min": 1.6},
    ]
    re_ = be.evaluate_race(_race(entries), _combo_odds_full())
    assert re_ is not None
    assert any("勝率情報が不足" in w for w in re_.warnings)
    # 強さ判定は P/ADR だけで成立 (composite は出る)
    assert re_.strengths[0].composite is not None


def test_composite_all_equal_signals_is_deterministic():
    """全馬の W/P/ADR が同値 (std=0) でも axis は決定的 (win_prob→馬番 tie-break)"""
    entries = [_e(u, 0.20, 0.40, 55.0, odds=5.0) for u in (3, 1, 2)]
    s1, _ = be.compute_strengths(_race(entries))
    s2, _ = be.compute_strengths(_race([entries[2], entries[0], entries[1]]))
    # 入力順を変えても同じ軸 (composite 同点 → win_prob 同点 → 馬番昇順)
    assert s1[0].umaban == s2[0].umaban == 1


def test_partners_lt_3_warns_no_sanren():
    """相手が3頭未満 → 三連系プラン無し + warning"""
    entries = [
        _e(1, 0.50, 0.70, 60.0, odds=2.0),
        _e(2, 0.30, 0.50, 55.0, odds=4.0),
    ]  # 2頭立て → 相手1頭
    re_ = be.evaluate_race(_race(entries, num_runners=2), _combo_odds_full())
    assert not any(p.bet_type in ("sanrenpuku", "sanrentan") for p in re_.plans)
    assert any("三連" in w for w in re_.warnings)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

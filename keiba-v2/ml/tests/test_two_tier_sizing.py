# -*- coding: utf-8 -*-
"""two_tier_sizing の単体テスト (Session 165 / 2層分類サイザー = three_tier 再走)

検証:
  - classify_tier: shobu / miokuri (low_ceiling / +inf / 非勝負R / empty selection)
      * ceiling_floor_R=400% に変わったことの確認 (旧 1000% との差分)
      * 様子見廃止: recommend_flag=False は常に miokuri (ceiling 通過でも買わない)
  - size_race_two_tier:
      * 勝負R = bankroll×15% で fixed_grade_v2 wrap (山型・複0 継承)
      * 見送りR = 空 RaceSizing (非勝負 / 低 ceiling)
      * +inf ceiling は買う側 (情報不足は見送らない)
      * per_race_cap=99999 渡しても tier 配分が優先される
      * bankroll=0 安全
      * registry 登録 + DEFAULT_SIZER 不変

three_tier_sizing から compute_ceiling_R / _is_shobu_from_pred を再利用しているので
それらの単体テストは test_three_tier_sizing.py に委ねる (重複を避ける)。
"""
import pytest

from ml.strategies import bettype_efficiency as be
from ml.strategies import bettype_selection as bs
from ml.strategies import bettype_sizing as sz
from ml.strategies import two_tier_sizing as tt


# --- フィクスチャ (test_three_tier_sizing と同型) ---

def _strength(umaban, pred_w, odds, *, composite=0.0, pred_p=None, place_odds_min=None):
    return be.HorseStrength(
        umaban=umaban, horse_name=f"H{umaban}", win_prob=pred_w, odds=odds,
        place_odds_min=place_odds_min, pred_w=pred_w, pred_p=pred_p,
        ar_deviation=None, z_w=None, z_p=None, z_adr=None, composite=composite)


def _plan(bet_type, legs, *, hit_prob, ev, g, odds_legs, label="P"):
    return be.Plan(
        bet_type=bet_type, label=label, legs=legs, n_points=len(legs),
        hit_prob=hit_prob, sum_p=hit_prob, synthetic_odds=g,
        expected_return=ev, odds_legs=odds_legs, coverage=1.0, vs_tansho=None)


def _race_eff(axis, axis_odds, strengths, plans, *, num_runners=12):
    return be.RaceEfficiency(
        race_id="2026053108031109", date="2026-05-31", venue_name="東京",
        race_number=11, grade="", track_type="芝", distance=1600, num_runners=num_runners,
        axis_umaban=axis, axis_name=f"H{axis}", axis_odds=axis_odds,
        partners=[], weights=(1, 1, 1), specialist=None,
        strengths=strengths, plans=plans, warnings=[])


def _sel_plan(bet_type, legs, *, ev=None, g=None):
    return bs.SelectedPlan(bet_type=bet_type, label="P", legs=legs, hit_prob=0.1,
                           expected_return=ev, synthetic_odds=g, vs_tansho=None,
                           select_reason="x")


def _selection(axis, axis_odds, selected_plans):
    return bs.BetSelection(
        race_id="2026053108031109", date="2026-05-31", venue_name="東京",
        race_number=11, grade="", axis_umaban=axis, axis_name=f"H{axis}",
        axis_odds=axis_odds, strategy="concentrate", requested_strategy="concentrate",
        ev_floor=1.0, taste=None, specialist=None, selected_plans=selected_plans,
        skipped_plans=[], decision_reason="x", warnings=[])


def _make_pred_race(*, umaban, win_ev=1.5, is_value_bet=True,
                    rank_w=1, win_vb_gap=5, predicted_margin=30):
    """勝負判定 (C 定義 = is_value_bet ∧ win_ev>=1.3) 用の pred_race。"""
    return {
        "race_id": "2026053108031109",
        "entries": [{
            "umaban": umaban, "win_ev": win_ev, "is_value_bet": is_value_bet,
            "rank_w": rank_w, "win_vb_gap": win_vb_gap,
            "predicted_margin": predicted_margin,
        }],
    }


# ---------------------------------------------------------------------------
# _is_shobu_relaxed (C 定義)
# ---------------------------------------------------------------------------

def test_is_shobu_relaxed_pass():
    """is_value_bet=True ∧ win_ev=1.5>=1.3 → True (win_vb_gap=0 でも通る = 緩和の核心)。"""
    pred = _make_pred_race(umaban=3, win_ev=1.5, is_value_bet=True, win_vb_gap=0)
    assert tt._is_shobu_relaxed(pred, 3) is True


def test_is_shobu_relaxed_ev_fail():
    """win_ev=1.2 < 1.3 → False。"""
    pred = _make_pred_race(umaban=3, win_ev=1.2, is_value_bet=True)
    assert tt._is_shobu_relaxed(pred, 3) is False


def test_is_shobu_relaxed_vb_fail():
    """is_value_bet=False → False (他が良くても VB Floor 未通過は弾く)。"""
    pred = _make_pred_race(umaban=3, win_ev=2.0, is_value_bet=False)
    assert tt._is_shobu_relaxed(pred, 3) is False


def test_is_shobu_relaxed_none_safe():
    """フィールド None / pred None / 軸不在 で例外なく False。"""
    assert tt._is_shobu_relaxed(None, 3) is False
    assert tt._is_shobu_relaxed(_make_pred_race(umaban=99), 3) is False
    pred = {"entries": [{"umaban": 3, "win_ev": None, "is_value_bet": True}]}
    assert tt._is_shobu_relaxed(pred, 3) is False


def test_classify_tier_auto_shobu_via_c():
    """recommend_flag 省略 → pred_race から C 判定 (is_value_bet ∧ win_ev>=1.3) で shobu。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=15.0, odds_legs=[15.0])]
    eff = _race_eff(3, 15.0, [_strength(3, 0.3, 15.0)], plans)
    sel = _selection(3, 15.0, [_sel_plan("tansho", [[3]])])
    pred = _make_pred_race(umaban=3, win_ev=1.5, is_value_bet=True, win_vb_gap=0)
    tier, info = tt.classify_tier(eff, sel, pred_race=pred)
    assert tier == "shobu"
    assert info["recommend_flag"] is True


def test_classify_tier_auto_miokuri_low_ev():
    """recommend_flag 省略 / win_ev=1.0<1.3 → C 不成立 → miokuri (様子見廃止)。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=15.0, odds_legs=[15.0])]
    eff = _race_eff(3, 15.0, [_strength(3, 0.3, 15.0)], plans)
    sel = _selection(3, 15.0, [_sel_plan("tansho", [[3]])])
    pred = _make_pred_race(umaban=3, win_ev=1.0, is_value_bet=True)
    tier, _ = tt.classify_tier(eff, sel, pred_race=pred)
    assert tier == "miokuri"


def test_classify_tier_strict_predicate_override():
    """shobu_predicate=tansho_ippon 4条件に差し替え可能 (win_vb_gap=0 → 厳格版は False)。"""
    from ml.strategies.three_tier_sizing import _is_shobu_from_pred
    plans = [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=15.0, odds_legs=[15.0])]
    eff = _race_eff(3, 15.0, [_strength(3, 0.3, 15.0)], plans)
    sel = _selection(3, 15.0, [_sel_plan("tansho", [[3]])])
    pred = _make_pred_race(umaban=3, win_ev=1.5, is_value_bet=True, win_vb_gap=0)
    # C 既定なら shobu
    tier_c, _ = tt.classify_tier(eff, sel, pred_race=pred)
    assert tier_c == "shobu"
    # 厳格版 (win_vb_gap>=3 必要) なら win_vb_gap=0 で miokuri
    tier_strict, _ = tt.classify_tier(eff, sel, pred_race=pred,
                                      shobu_predicate=_is_shobu_from_pred)
    assert tier_strict == "miokuri"


# ---------------------------------------------------------------------------
# classify_tier: 二層 + 400% 閾値
# ---------------------------------------------------------------------------

def test_classify_tier_shobu():
    """ceiling_R=1500% / recommend_flag=True / selected_plans 存在 → 'shobu'。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0])]
    eff = _race_eff(3, 15.0, [_strength(3, 0.4, 15.0)], plans)
    sel = _selection(3, 15.0, [_sel_plan("tansho", [[3]])])
    tier, info = tt.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "shobu"
    assert info["ceiling_R"] == 1500.0


def test_classify_tier_non_shobu_is_miokuri():
    """★様子見廃止★: ceiling 通過でも recommend_flag=False は 'miokuri' (旧 kanshi が消えた)。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=15.0, odds_legs=[15.0])]
    eff = _race_eff(3, 15.0, [_strength(3, 0.3, 15.0)], plans)
    sel = _selection(3, 15.0, [_sel_plan("tansho", [[3]])])
    tier, info = tt.classify_tier(eff, sel, recommend_flag=False)
    assert tier == "miokuri"
    assert "様子見廃止" in info["reason"]


def test_classify_tier_ceiling_400_floor_pass():
    """ceiling_R=450% (>=400%) ∧ 勝負 → 'shobu' (旧 1000% floor なら見送りだった)。"""
    plans = [_plan("umaren", [[3, 7]], hit_prob=0.2, ev=1.2, g=4.5, odds_legs=[4.5])]
    eff = _race_eff(3, 5.0, [_strength(3, 0.4, 5.0)], plans)
    sel = _selection(3, 5.0, [_sel_plan("umaren", [[3, 7]], ev=1.2, g=4.5)])
    tier, info = tt.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "shobu"
    assert info["ceiling_R"] == 450.0


def test_classify_tier_ceiling_below_400_miokuri():
    """ceiling_R=350% (<400%) → 'miokuri' (★recommend_flag=True でも見送り優先★)。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.4, ev=None, g=3.5, odds_legs=[3.5])]
    eff = _race_eff(3, 3.5, [_strength(3, 0.4, 3.5)], plans)
    sel = _selection(3, 3.5, [_sel_plan("tansho", [[3]])])
    tier, info = tt.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "miokuri"
    assert info["ceiling_R"] == 350.0


def test_classify_tier_inf_ceiling_buys_if_shobu():
    """ceiling_R=+inf (情報不足) ∧ 勝負 → 'shobu' (★情報不足は買う側★)。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.4, ev=None, g=None, odds_legs=[None])]
    eff = _race_eff(3, 5.0, [_strength(3, 0.4, 5.0)], plans)
    sel = _selection(3, 5.0, [_sel_plan("tansho", [[3]])])
    tier, info = tt.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "shobu"
    assert info["ceiling_R"] == float("inf")


def test_classify_tier_inf_ceiling_non_shobu_miokuri():
    """ceiling_R=+inf ∧ 非勝負 → 'miokuri' (情報不足でも様子見廃止で買わない)。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[None])]
    eff = _race_eff(3, 5.0, [_strength(3, 0.3, 5.0)], plans)
    sel = _selection(3, 5.0, [_sel_plan("tansho", [[3]])])
    tier, _ = tt.classify_tier(eff, sel, recommend_flag=False)
    assert tier == "miokuri"


def test_classify_tier_shobu_but_empty_selection():
    """recommend_flag=True / selected_plans=[] → 'miokuri' (買えないので fallback)。"""
    plans = [_plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0])]
    eff = _race_eff(3, 15.0, [_strength(3, 0.4, 15.0)], plans)
    sel = _selection(3, 15.0, [])
    tier, _ = tt.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "miokuri"


# ---------------------------------------------------------------------------
# size_race_two_tier: 勝負R (fixed_grade_v2 wrap)
# ---------------------------------------------------------------------------

def test_size_race_two_tier_shobu_uses_v2_with_15pct_cap():
    """勝負R = bankroll×15%=1500 で fixed_grade_v2 が呼ばれる (複0 継承)。"""
    axis = 3
    strengths = [_strength(3, 0.4, 5.0, composite=1.5, place_odds_min=2.0)]  # strong tier
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0]),
        _plan("fukusho", [[3]], hit_prob=0.6, ev=None, g=2.0, odds_legs=[2.0]),
        _plan("sanrenpuku", [[3, 7, 11]], hit_prob=0.1, ev=1.5, g=20.0, odds_legs=[20.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]]),
        _sel_plan("sanrenpuku", [[3, 7, 11]], ev=1.5, g=20.0)])
    rs = tt.size_race_two_tier(eff, sel, bankroll=10000, recommend_flag=True)
    assert rs.total_yen <= 1500
    # ★v2 = 複勝 share=0 (FIXED_SHARES_V2)★ → 複なしを継承
    assert not any(l.bet_type == "fukusho" for l in rs.legs)
    # warnings 先頭が two_tier=shobu で始まる + cap 表示
    assert rs.warnings[0].startswith("two_tier=shobu")
    assert "cap=1500" in rs.warnings[0]


def test_size_race_two_tier_shobu_total_le_cap():
    """勝負R の total_yen <= bankroll×0.15 (cap が効く)。"""
    axis = 3
    strengths = [_strength(3, 0.4, 5.0, composite=1.5, place_odds_min=2.0)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0]),
        _plan("sanrenpuku", [[3, 7, 11]], hit_prob=0.1, ev=1.5, g=20.0, odds_legs=[20.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("sanrenpuku", [[3, 7, 11]], ev=1.5, g=20.0)])
    rs = tt.size_race_two_tier(eff, sel, bankroll=1000000, recommend_flag=True)
    # 1,000,000 × 15% = 150,000
    assert rs.total_yen <= 150000
    assert rs.total_yen > 0   # 勝負R なので買い目は出る


# ---------------------------------------------------------------------------
# size_race_two_tier: 見送りR
# ---------------------------------------------------------------------------

def test_size_race_two_tier_non_shobu_returns_empty():
    """★様子見廃止★: 非勝負R (recommend_flag=False) は ceiling 通過でも空。"""
    axis = 3
    strengths = [_strength(3, 0.30, 3.3, composite=0.5, pred_p=0.65)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.30, ev=None, g=3.3, odds_legs=[3.3]),
        _plan("umaren", [[3, 7]], hit_prob=0.30, ev=1.2, g=12.0, odds_legs=[12.0]),
    ]
    eff = _race_eff(axis, 3.3, strengths, plans, num_runners=10)
    sel = _selection(axis, 3.3, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("umaren", [[3, 7]], ev=1.2, g=12.0)])
    rs = tt.size_race_two_tier(eff, sel, bankroll=1000000, recommend_flag=False)
    assert rs.legs == []
    assert rs.total_yen == 0
    assert any("様子見廃止" in w for w in rs.warnings)


def test_size_race_two_tier_low_ceiling_returns_empty():
    """ceiling_R<400% → 空 RaceSizing (勝負でも見送り優先)。"""
    axis = 3
    strengths = [_strength(3, 0.4, 3.5, composite=1.5)]
    plans = [_plan("tansho", [[3]], hit_prob=0.4, ev=None, g=3.5, odds_legs=[3.5])]  # ceiling 350%
    eff = _race_eff(axis, 3.5, strengths, plans)
    sel = _selection(axis, 3.5, [_sel_plan("tansho", [[3]])])
    rs = tt.size_race_two_tier(eff, sel, bankroll=1000000, recommend_flag=True)
    assert rs.legs == []
    assert rs.total_yen == 0
    assert rs.per_race_cap == 0
    assert any("miokuri" in w for w in rs.warnings)


# ---------------------------------------------------------------------------
# per_race_cap 無視 / bankroll ゼロ / registry
# ---------------------------------------------------------------------------

def test_size_race_two_tier_per_race_cap_ignored():
    """per_race_cap=99999 渡しても無視され、 cap=bankroll×15% が使われる。"""
    axis = 3
    strengths = [_strength(3, 0.4, 5.0, composite=1.5, place_odds_min=2.0)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0]),
        _plan("sanrenpuku", [[3, 7, 11]], hit_prob=0.1, ev=1.5, g=20.0, odds_legs=[20.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("sanrenpuku", [[3, 7, 11]], ev=1.5, g=20.0)])
    rs = tt.size_race_two_tier(eff, sel, bankroll=10000, per_race_cap=99999,
                               recommend_flag=True)
    # bankroll×0.15 = 1500 が cap → total <= 1500
    assert rs.total_yen <= 1500


def test_size_race_two_tier_zero_bankroll_safe():
    """bankroll=0 → 空 sizing で例外なし。"""
    axis = 3
    strengths = [_strength(3, 0.4, 15.0, composite=1.5)]
    plans = [_plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0])]
    eff = _race_eff(axis, 15.0, strengths, plans)
    sel = _selection(axis, 15.0, [_sel_plan("tansho", [[3]])])
    rs = tt.size_race_two_tier(eff, sel, bankroll=0, recommend_flag=True)
    assert rs.legs == []
    assert rs.total_yen == 0


def test_size_race_two_tier_registry():
    """SIZERS['two_tier_v0'] == size_race_two_tier (registry 登録テスト)。"""
    assert sz.SIZERS[tt.TWO_TIER_SIZER] is tt.size_race_two_tier
    assert sz.get_sizer(tt.TWO_TIER_SIZER) is tt.size_race_two_tier


def test_default_sizer_unchanged():
    """DEFAULT_SIZER == FIXED_GRADE_SIZER (本番昇格していない = opt-in 運用)。"""
    assert sz.DEFAULT_SIZER == sz.FIXED_GRADE_SIZER

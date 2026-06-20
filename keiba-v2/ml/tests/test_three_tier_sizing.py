# -*- coding: utf-8 -*-
"""three_tier_sizing の単体テスト (Session 164 / 3層分類サイザー)

検証:
  - compute_ceiling_R: 通常 / 全欠損 (+inf) / plans 空 (+inf)
  - _is_shobu_from_pred: 4 条件 AND + None 安全 + margin_max 60/76 切替
  - _passes_kanshi_gates: W only / P only (小頭数/大頭数) / 全通 / 全不通過
  - _kanshi_effective_bet_types: ゲート ∧ selection の AND
  - classify_tier: shobu / kanshi / miokuri (low_ceiling / +inf / empty selection)
  - size_race_three_tier:
      * 勝負R = bankroll×15% で fixed_grade_v2 wrap (山型・複0)
      * 様子見R = KANSHI_SHARES 自前配分 (gate 不通過は捨てる)
      * 見送りR = 空 RaceSizing
      * axis_odds None → tansho leg なし
      * per_race_cap=99999 渡しても tier 配分が優先される
      * registry 登録 + DEFAULT_SIZER 不変
"""
import pytest

from ml.strategies import bettype_efficiency as be
from ml.strategies import bettype_selection as bs
from ml.strategies import bettype_sizing as sz
from ml.strategies import three_tier_sizing as tts


# --- フィクスチャ (bettype_sizing と同型) ---

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


def _make_pred_race(*, umaban, rank_w=1, win_vb_gap=5, win_ev=1.5,
                    predicted_margin=30, is_value_bet=True):
    """tansho_ippon 4条件AND の判定に使う pred_race を作る。"""
    return {
        "race_id": "2026053108031109",
        "entries": [{
            "umaban": umaban,
            "rank_w": rank_w,
            "win_vb_gap": win_vb_gap,
            "win_ev": win_ev,
            "predicted_margin": predicted_margin,
            "is_value_bet": is_value_bet,
        }],
    }


# ---------------------------------------------------------------------------
# compute_ceiling_R
# ---------------------------------------------------------------------------

def test_compute_ceiling_R_normal():
    """plans の synthetic_odds 最大 × 100 = ceiling_R を返す。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=5.0, odds_legs=[5.0]),
        _plan("sanrentan", [[3, 7, 11]], hit_prob=0.05, ev=1.8, g=40.0, odds_legs=[40.0]),
        _plan("umaren", [[3, 7]], hit_prob=0.2, ev=1.2, g=12.0, odds_legs=[12.0]),
    ]
    eff = _race_eff(3, 5.0, [_strength(3, 0.3, 5.0)], plans)
    # 最大 synthetic_odds = 40.0 → ceiling_R = 4000%
    assert tts.compute_ceiling_R(eff) == 4000.0


def test_compute_ceiling_R_all_missing():
    """全 plan の synthetic_odds=None → +inf (情報不足は安全側=買う)。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[None]),
        _plan("umaren", [[3, 7]], hit_prob=0.2, ev=None, g=None, odds_legs=[None]),
    ]
    eff = _race_eff(3, None, [_strength(3, 0.3, None)], plans)
    assert tts.compute_ceiling_R(eff) == float("inf")


def test_compute_ceiling_R_empty_plans():
    """race_eff.plans=[] → +inf (情報不足)。"""
    eff = _race_eff(3, 5.0, [_strength(3, 0.3, 5.0)], [])
    assert tts.compute_ceiling_R(eff) == float("inf")


def test_compute_ceiling_R_race_eff_none():
    """race_eff=None でも例外でなく +inf を返す (None fallback)。"""
    assert tts.compute_ceiling_R(None) == float("inf")


# ---------------------------------------------------------------------------
# _is_shobu_from_pred
# ---------------------------------------------------------------------------

def test_is_shobu_from_pred_all_pass():
    pred = _make_pred_race(umaban=3, rank_w=1, win_vb_gap=5,
                            win_ev=1.5, predicted_margin=30, is_value_bet=True)
    assert tts._is_shobu_from_pred(pred, 3) is True


def test_is_shobu_from_pred_margin_fail_60():
    """predicted_margin=65 / margin_max=60 → False (BT整合)。"""
    pred = _make_pred_race(umaban=3, predicted_margin=65)
    assert tts._is_shobu_from_pred(pred, 3, margin_max=60) is False


def test_is_shobu_from_pred_margin_pass_76():
    """predicted_margin=70 / margin_max=76 → True (ライブ再現 LIVE_MARGIN_OFFSET=16)。"""
    pred = _make_pred_race(umaban=3, predicted_margin=70)
    assert tts._is_shobu_from_pred(pred, 3, margin_max=76) is True


def test_is_shobu_from_pred_value_bet_false():
    """is_value_bet=False → False (他条件満たしても VB Floor 未通過は弾く)。"""
    pred = _make_pred_race(umaban=3, is_value_bet=False)
    assert tts._is_shobu_from_pred(pred, 3) is False


def test_is_shobu_from_pred_none_safe():
    """フィールドが None でも例外でなく False を返す (null 安全)。"""
    pred = {
        "race_id": "X",
        "entries": [{"umaban": 3, "rank_w": None, "win_vb_gap": None,
                     "win_ev": None, "predicted_margin": None, "is_value_bet": True}],
    }
    assert tts._is_shobu_from_pred(pred, 3) is False


def test_is_shobu_from_pred_pred_race_none():
    assert tts._is_shobu_from_pred(None, 3) is False


def test_is_shobu_from_pred_axis_absent():
    """軸が entries に無い → False (誤判定しない)。"""
    pred = _make_pred_race(umaban=99)
    assert tts._is_shobu_from_pred(pred, 3) is False


# ---------------------------------------------------------------------------
# _passes_kanshi_gates
# ---------------------------------------------------------------------------

def test_passes_kanshi_gates_w_only():
    """軸 W=0.35 (W>=25% 通過) / P=0.40 (P<50% 不通過) → {tansho, umatan, sanrentan} のみ。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.35, ev=None, g=2.8, odds_legs=[2.8]),
        _plan("fukusho", [[3]], hit_prob=0.40, ev=None, g=1.5, odds_legs=[1.5]),
    ]
    eff = _race_eff(3, 2.8, [_strength(3, 0.35, 2.8)], plans, num_runners=10)
    passed, info = tts._passes_kanshi_gates(eff)
    assert passed == {"tansho", "umatan", "sanrentan"}
    assert info["w_axis"] == pytest.approx(0.35)
    assert info["p_axis"] == pytest.approx(0.40)


def test_passes_kanshi_gates_p_only_small():
    """頭数7 (小頭数) / W=0.15 (不通過) / P=0.55 (>=50% 通過・三連複は60%不通過)
       → {umaren, wide} のみ。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.15, ev=None, g=6.0, odds_legs=[6.0]),
        _plan("fukusho", [[3]], hit_prob=0.55, ev=None, g=1.4, odds_legs=[1.4]),
    ]
    eff = _race_eff(3, 6.0, [_strength(3, 0.15, 6.0)], plans, num_runners=7)
    passed, _ = tts._passes_kanshi_gates(eff)
    assert passed == {"umaren", "wide"}   # 三連複は 0.60 floor 未満で弾かれる


def test_passes_kanshi_gates_p_large_pass():
    """頭数10 / P=0.65 → 連系全て (馬連/ワイド/三連複) 通過。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.15, ev=None, g=6.0, odds_legs=[6.0]),
        _plan("fukusho", [[3]], hit_prob=0.65, ev=None, g=1.3, odds_legs=[1.3]),
    ]
    eff = _race_eff(3, 6.0, [_strength(3, 0.15, 6.0)], plans, num_runners=10)
    passed, _ = tts._passes_kanshi_gates(eff)
    assert passed == {"umaren", "wide", "sanrenpuku"}


def test_passes_kanshi_gates_all_pass():
    """頭数10 / W=0.30 / P=0.65 → 6券種全通過。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.30, ev=None, g=3.3, odds_legs=[3.3]),
        _plan("fukusho", [[3]], hit_prob=0.65, ev=None, g=1.3, odds_legs=[1.3]),
    ]
    eff = _race_eff(3, 3.3, [_strength(3, 0.30, 3.3)], plans, num_runners=10)
    passed, _ = tts._passes_kanshi_gates(eff)
    assert passed == {"tansho", "umatan", "sanrentan", "umaren", "wide", "sanrenpuku"}


def test_passes_kanshi_gates_all_fail():
    """全閾値未満 → set() = 空。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.10, ev=None, g=10.0, odds_legs=[10.0]),
        _plan("fukusho", [[3]], hit_prob=0.30, ev=None, g=2.5, odds_legs=[2.5]),
    ]
    eff = _race_eff(3, 10.0, [_strength(3, 0.10, 10.0)], plans, num_runners=10)
    passed, _ = tts._passes_kanshi_gates(eff)
    assert passed == set()


def test_passes_kanshi_gates_fukusho_fallback():
    """fukusho plan 無し → HorseStrength.pred_p を P フォールバック使用。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.20, ev=None, g=5.0, odds_legs=[5.0]),
        # fukusho 無し
    ]
    eff = _race_eff(3, 5.0,
                    [_strength(3, 0.20, 5.0, pred_p=0.65)],
                    plans, num_runners=10)
    passed, info = tts._passes_kanshi_gates(eff)
    # fukusho フォールバック: pred_p=0.65 → 連系全通過
    assert "umaren" in passed and "wide" in passed and "sanrenpuku" in passed
    assert info["p_axis"] == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# classify_tier
# ---------------------------------------------------------------------------

def test_classify_tier_shobu():
    """ceiling_R=1500% / recommend_flag=True / selected_plans 存在 → 'shobu'。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0]),
    ]
    eff = _race_eff(3, 15.0, [_strength(3, 0.4, 15.0)], plans)
    sel = _selection(3, 15.0, [_sel_plan("tansho", [[3]])])
    tier, info = tts.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "shobu"
    assert info["ceiling_R"] == 1500.0


def test_classify_tier_kanshi():
    """ceiling_R=1500% / recommend_flag=False / selected_plans 存在 → 'kanshi'。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=15.0, odds_legs=[15.0]),
    ]
    eff = _race_eff(3, 15.0, [_strength(3, 0.3, 15.0)], plans)
    sel = _selection(3, 15.0, [_sel_plan("tansho", [[3]])])
    tier, _ = tts.classify_tier(eff, sel, recommend_flag=False)
    assert tier == "kanshi"


def test_classify_tier_miokuri_low_ceiling():
    """ceiling_R=500% < 1000% → 'miokuri' (★recommend_flag=True でも見送り優先★)。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=5.0, odds_legs=[5.0]),
    ]
    eff = _race_eff(3, 5.0, [_strength(3, 0.4, 5.0)], plans)
    sel = _selection(3, 5.0, [_sel_plan("tansho", [[3]])])
    tier, info = tts.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "miokuri"
    assert info["ceiling_R"] == 500.0


def test_classify_tier_inf_ceiling_not_miokuri():
    """ceiling_R=+inf (情報不足) → 'kanshi' (★情報不足は買う側★)。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[None]),
    ]
    eff = _race_eff(3, 5.0, [_strength(3, 0.3, 5.0)], plans)
    sel = _selection(3, 5.0, [_sel_plan("tansho", [[3]])])
    tier, info = tts.classify_tier(eff, sel, recommend_flag=False)
    assert tier == "kanshi"
    assert info["ceiling_R"] == float("inf")


def test_classify_tier_shobu_but_empty_selection():
    """recommend_flag=True / selected_plans=[] → 'miokuri' (買えないので強制 fallback)。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=15.0, odds_legs=[15.0]),
    ]
    eff = _race_eff(3, 15.0, [_strength(3, 0.4, 15.0)], plans)
    sel = _selection(3, 15.0, [])   # 空
    tier, _ = tts.classify_tier(eff, sel, recommend_flag=True)
    assert tier == "miokuri"


def test_classify_tier_miokuri_empty_selection_no_flag():
    """selected_plans=[] / recommend_flag=False → 'miokuri' (kanshi fallback)。"""
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=15.0, odds_legs=[15.0]),
    ]
    eff = _race_eff(3, 15.0, [_strength(3, 0.3, 15.0)], plans)
    sel = _selection(3, 15.0, [])
    tier, _ = tts.classify_tier(eff, sel, recommend_flag=False)
    assert tier == "miokuri"


# ---------------------------------------------------------------------------
# size_race_three_tier: 勝負R (fixed_grade_v2 wrap)
# ---------------------------------------------------------------------------

def test_size_race_three_tier_shobu_uses_v2_with_15pct_cap():
    """勝負R = bankroll×15%=1500 で fixed_grade_v2 が呼ばれる。"""
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
    rs = tts.size_race_three_tier(eff, sel, bankroll=10000,
                                  recommend_flag=True)   # 勝負R 強制
    # cap = 10000 × 15% = 1500 で総額が抑えられる
    assert rs.total_yen <= 1500
    # ★v2 = 複勝 share=0 (FIXED_SHARES_V2)★ → 複なしを継承
    assert not any(l.bet_type == "fukusho" for l in rs.legs)
    # warnings 先頭が three_tier=shobu で始まる + cap 表示
    assert rs.warnings[0].startswith("three_tier=shobu")
    assert "cap=1500" in rs.warnings[0]


def test_size_race_three_tier_shobu_total_le_cap():
    """勝負R の total_yen <= bankroll×0.15。"""
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
    rs = tts.size_race_three_tier(eff, sel, bankroll=20000,
                                  recommend_flag=True)
    # 20000 × 15% = 3000
    assert rs.total_yen <= 3000


# ---------------------------------------------------------------------------
# size_race_three_tier: 様子見R
# ---------------------------------------------------------------------------

def test_size_race_three_tier_kanshi_no_fukusho_leg():
    """KANSHI_SHARES に fukusho を含まないので legs に fukusho 一切なし。"""
    axis = 3
    strengths = [_strength(3, 0.30, 3.3, composite=0.5, pred_p=0.65)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.30, ev=None, g=3.3, odds_legs=[3.3]),
        _plan("fukusho", [[3]], hit_prob=0.65, ev=None, g=1.3, odds_legs=[1.3]),
        _plan("umaren", [[3, 7]], hit_prob=0.30, ev=1.2, g=12.0, odds_legs=[12.0]),
        _plan("wide", [[3, 7]], hit_prob=0.40, ev=1.3, g=15.0, odds_legs=[15.0]),
        _plan("sanrenpuku", [[3, 7, 11]], hit_prob=0.10, ev=1.5, g=20.0, odds_legs=[20.0]),
    ]
    eff = _race_eff(axis, 3.3, strengths, plans, num_runners=10)
    sel = _selection(axis, 3.3, [
        _sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]]),
        _sel_plan("umaren", [[3, 7]], ev=1.2, g=12.0),
        _sel_plan("wide", [[3, 7]], ev=1.3, g=15.0),
        _sel_plan("sanrenpuku", [[3, 7, 11]], ev=1.5, g=20.0)])
    rs = tts.size_race_three_tier(eff, sel, bankroll=100000,
                                   recommend_flag=False)   # 様子見R
    assert all(l.bet_type != "fukusho" for l in rs.legs)


def test_size_race_three_tier_kanshi_gate_filter():
    """W=0.30 (頭固定通過) / P=0.40 (連系不通過) → {tansho/umatan/sanrentan} のみ。"""
    axis = 3
    strengths = [_strength(3, 0.30, 3.3, composite=0.5, pred_p=0.40)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.30, ev=None, g=3.3, odds_legs=[3.3]),
        _plan("fukusho", [[3]], hit_prob=0.40, ev=None, g=1.6, odds_legs=[1.6]),
        _plan("umaren", [[3, 7]], hit_prob=0.20, ev=1.2, g=12.0, odds_legs=[12.0]),
        _plan("wide", [[3, 7]], hit_prob=0.30, ev=1.3, g=15.0, odds_legs=[15.0]),
        _plan("umatan", [[3, 7]], hit_prob=0.15, ev=1.0, g=20.0, odds_legs=[20.0]),
        _plan("sanrentan", [[3, 7, 11]], hit_prob=0.05, ev=1.8, g=40.0, odds_legs=[40.0]),
    ]
    eff = _race_eff(axis, 3.3, strengths, plans, num_runners=10)
    sel = _selection(axis, 3.3, [
        _sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]]),
        _sel_plan("umaren", [[3, 7]], ev=1.2, g=12.0),
        _sel_plan("wide", [[3, 7]], ev=1.3, g=15.0),
        _sel_plan("umatan", [[3, 7]], ev=1.0, g=20.0),
        _sel_plan("sanrentan", [[3, 7, 11]], ev=1.8, g=40.0)])
    rs = tts.size_race_three_tier(eff, sel, bankroll=200000,
                                   recommend_flag=False)
    # cap = 200000 × 3% = 6000 で各 bucket が十分でる
    types_seen = {l.bet_type for l in rs.legs}
    # 頭固定3券種は出る (W=0.30>=0.25 通過)
    assert "tansho" in types_seen
    assert "umatan" in types_seen
    assert "sanrentan" in types_seen
    # 連系3券種は出ない (P=0.40<0.60 不通過)
    assert "umaren" not in types_seen
    assert "wide" not in types_seen
    assert "sanrenpuku" not in types_seen


def test_size_race_three_tier_kanshi_gate_all_fail_returns_empty():
    """ゲート全不通過 → 空 RaceSizing (legs=[], total=0) + warnings に '全券種ゲート不通過'。"""
    axis = 3
    # W=0.10 / P=0.30 で全閾値未満
    strengths = [_strength(3, 0.10, 10.0, composite=0.1, pred_p=0.30)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.10, ev=None, g=10.0, odds_legs=[10.0]),
        _plan("fukusho", [[3]], hit_prob=0.30, ev=None, g=2.5, odds_legs=[2.5]),
    ]
    eff = _race_eff(axis, 10.0, strengths, plans, num_runners=10)
    sel = _selection(axis, 10.0, [
        _sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]])])
    rs = tts.size_race_three_tier(eff, sel, bankroll=100000,
                                   recommend_flag=False)
    assert rs.legs == []
    assert rs.total_yen == 0
    assert any("全券種ゲート不通過" in w for w in rs.warnings)


def test_size_race_three_tier_kanshi_per_race_cap_ignored():
    """per_race_cap=99999 渡しても無視され、 cap=bankroll×3% が使われる (tier 配分が優先)。"""
    axis = 3
    strengths = [_strength(3, 0.30, 3.3, composite=0.5, pred_p=0.65)]
    # ceiling_R >= 1000% にするため synthetic_odds 12 倍の馬連を含める
    plans = [
        _plan("tansho", [[3]], hit_prob=0.30, ev=None, g=3.3, odds_legs=[3.3]),
        _plan("fukusho", [[3]], hit_prob=0.65, ev=None, g=1.3, odds_legs=[1.3]),
        _plan("umaren", [[3, 7]], hit_prob=0.30, ev=1.2, g=12.0, odds_legs=[12.0]),
    ]
    eff = _race_eff(axis, 3.3, strengths, plans, num_runners=10)
    sel = _selection(axis, 3.3, [_sel_plan("tansho", [[3]]),
                                 _sel_plan("umaren", [[3, 7]], ev=1.2, g=12.0)])
    rs = tts.size_race_three_tier(eff, sel, bankroll=100000,
                                   per_race_cap=99999,   # 無視される
                                   recommend_flag=False)
    # bankroll×0.03 = 3000 がベース → tansho bucket = 3000×0.10 = 300
    assert rs.per_race_cap == 3000
    assert rs.total_yen <= 3000


def test_size_race_three_tier_kanshi_axis_odds_invalid():
    """axis_odds=None → tansho leg なし、 他券種は通常通り。"""
    axis = 3
    strengths = [_strength(3, 0.30, None, composite=0.5, pred_p=0.65)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.30, ev=None, g=None, odds_legs=[None]),
        _plan("fukusho", [[3]], hit_prob=0.65, ev=None, g=1.3, odds_legs=[1.3]),
        _plan("umaren", [[3, 7]], hit_prob=0.30, ev=1.2, g=12.0, odds_legs=[12.0]),
    ]
    eff = _race_eff(axis, None, strengths, plans, num_runners=10)
    sel = _selection(axis, None, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("umaren", [[3, 7]], ev=1.2, g=12.0)])
    rs = tts.size_race_three_tier(eff, sel, bankroll=200000,
                                   recommend_flag=False)
    # 単勝 leg なし (axis_odds 無効)
    assert not any(l.bet_type == "tansho" for l in rs.legs)
    # 馬連は出る (連系=P>=0.60 通過)
    assert any(l.bet_type == "umaren" for l in rs.legs)


# ---------------------------------------------------------------------------
# size_race_three_tier: 見送りR
# ---------------------------------------------------------------------------

def test_size_race_three_tier_miokuri_returns_empty():
    """ceiling_R<1000% → 空 RaceSizing。"""
    axis = 3
    strengths = [_strength(3, 0.4, 5.0, composite=0.5)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=5.0, odds_legs=[5.0]),  # ceiling 500%
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [_sel_plan("tansho", [[3]])])
    rs = tts.size_race_three_tier(eff, sel, bankroll=10000,
                                   recommend_flag=False)
    assert rs.legs == []
    assert rs.total_yen == 0
    assert rs.per_race_cap == 0
    assert any("miokuri" in w for w in rs.warnings)


# ---------------------------------------------------------------------------
# bankroll ゼロ・安全性
# ---------------------------------------------------------------------------

def test_size_race_three_tier_zero_bankroll_safe():
    """bankroll=0 → 空 sizing で例外なし (安全フォールバック)。"""
    axis = 3
    strengths = [_strength(3, 0.30, 3.3, composite=0.5, pred_p=0.65)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.30, ev=None, g=15.0, odds_legs=[15.0]),
    ]
    eff = _race_eff(axis, 3.3, strengths, plans, num_runners=10)
    sel = _selection(axis, 3.3, [_sel_plan("tansho", [[3]])])
    rs = tts.size_race_three_tier(eff, sel, bankroll=0,
                                   recommend_flag=False)
    # cap=0 → 空 sizing
    assert rs.legs == []
    assert rs.total_yen == 0


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

def test_size_race_three_tier_registry():
    """SIZERS['three_tier_v0'] == size_race_three_tier (registry 登録テスト)。"""
    assert sz.SIZERS[tts.THREE_TIER_SIZER] is tts.size_race_three_tier
    assert sz.get_sizer(tts.THREE_TIER_SIZER) is tts.size_race_three_tier


def test_default_sizer_unchanged():
    """DEFAULT_SIZER == FIXED_GRADE_SIZER (本番昇格していない = 既存のまま)。"""
    # three_tier_v0 は opt-in 運用。 既定は fixed_grade_v1 のまま (Session 161 確定)。
    assert sz.DEFAULT_SIZER == sz.FIXED_GRADE_SIZER

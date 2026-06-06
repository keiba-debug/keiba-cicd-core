# -*- coding: utf-8 -*-
"""bettype_sizing の単体テスト (Session 140 / multi-bettype サイジング)

検証:
  - アンカー◎単が freebudget Kelly と同額 (kelly_amount 式)
  - 複合は per_race 残予算を EV 比例配分 (plan 内逆オッズ)
  - 排反保守: 複合合計 <= 残予算 (naive per-leg Kelly より小)
  - per_race truncate (アンカー保護で複合を先に drop)
  - 全 amount は 100円単位・最低100 (or 除外)
  - 市場オッズ未取得 (EV None) の複合は買わない
  - get_sizer 未知名 ValueError
"""
import pytest

from ml.strategies import bettype_efficiency as be
from ml.strategies import bettype_selection as bs
from ml.strategies import bettype_sizing as sz


# --- fake ビルダー (実 dataclass を使う) ---

def _strength(umaban, pred_w, odds):
    return be.HorseStrength(
        umaban=umaban, horse_name=f"H{umaban}", win_prob=pred_w, odds=odds,
        place_odds_min=None, pred_w=pred_w, pred_p=None, ar_deviation=None,
        z_w=None, z_p=None, z_adr=None, composite=0.0)


def _plan(bet_type, legs, *, hit_prob, ev, g, odds_legs, label="P"):
    return be.Plan(
        bet_type=bet_type, label=label, legs=legs, n_points=len(legs),
        hit_prob=hit_prob, sum_p=hit_prob, synthetic_odds=g,
        expected_return=ev, odds_legs=odds_legs, coverage=1.0, vs_tansho=None)


def _race_eff(axis, axis_odds, strengths, plans):
    return be.RaceEfficiency(
        race_id="2026053108031109", date="2026-05-31", venue_name="東京",
        race_number=11, grade="", track_type="芝", distance=1600, num_runners=12,
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


# --- kelly_amount (freebudget 同式) ---

def test_kelly_amount_matches_freebudget_formula():
    # p=0.3, odds=5.0: b=4, kelly_raw=(4*0.3-0.7)/4=0.125, sized=min(0.03125,0.10)=0.03125
    # amount=int(10000*0.03125)//100*100 = 312//100*100 = 300
    amt = sz.kelly_amount(0.3, 5.0, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
    assert amt == 300


def test_kelly_amount_zero_when_negative_ev():
    # p=0.1, odds=5.0: EV=0.5<1 → kelly_raw<=0 → 0
    assert sz.kelly_amount(0.1, 5.0, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10) == 0


def test_kelly_amount_caps_at_per_bet():
    # 高 p で per_bet_cap (1000) に張り付く
    amt = sz.kelly_amount(0.6, 3.0, bankroll=10000, kelly_fraction=1.0, per_bet_cap_pct=0.10)
    assert amt == 1000


# --- size_race: アンカー◎単 ---

def test_anchor_tansho_matches_freebudget():
    axis = 3
    eff = _race_eff(axis, 5.0,
                    [_strength(3, 0.3, 5.0)],
                    [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0])])
    sel = _selection(axis, 5.0, [_sel_plan("tansho", [[3]])])
    rs = sz.size_race(eff, sel, bankroll=10000, per_race_cap=3000)
    tansho = [l for l in rs.legs if l.bet_type == "tansho"]
    assert len(tansho) == 1
    assert tansho[0].amount == sz.kelly_amount(0.3, 5.0, bankroll=10000,
                                               kelly_fraction=0.25, per_bet_cap_pct=0.10)
    assert tansho[0].amount == 300
    assert tansho[0].horses == [3]


# --- size_race: 複合 EV 比例 + 逆オッズ + 排反保守 ---

def test_combo_ev_proportional_and_residual_bound():
    axis = 3
    strengths = [_strength(3, 0.3, 5.0)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("umaren", [[3, 7], [3, 11]], hit_prob=0.3, ev=1.2, g=6.0, odds_legs=[6.0, 12.0]),
        _plan("sanrentan", [[3, 7, 11]], hit_prob=0.05, ev=1.8, g=40.0, odds_legs=[40.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("umaren", [[3, 7], [3, 11]], ev=1.2, g=6.0),
        _sel_plan("sanrentan", [[3, 7, 11]], ev=1.8, g=40.0),
    ])
    rs = sz.size_race(eff, sel, bankroll=10000, per_race_cap=3000)
    anchor = sum(l.amount for l in rs.legs if l.bet_type == "tansho")  # 300
    residual = 3000 - anchor
    # 排反保守: 複合合計は残予算を超えない
    assert rs.combo_yen <= residual
    # 三連単(EV1.8) は馬連(EV1.2) より多く配分される
    umaren_yen = sum(l.amount for l in rs.legs if l.bet_type == "umaren")
    sanren_yen = sum(l.amount for l in rs.legs if l.bet_type == "sanrentan")
    assert sanren_yen >= umaren_yen
    # 逆オッズ: 馬連 2点 (odds 6 vs 12) は odds 低い方が多い
    umaren_legs = [l for l in rs.legs if l.bet_type == "umaren"]
    if len(umaren_legs) == 2:
        lo = next(l for l in umaren_legs if l.leg_odds == 6.0)
        hi = next(l for l in umaren_legs if l.leg_odds == 12.0)
        assert lo.amount >= hi.amount


def test_all_amounts_unit_and_min():
    axis = 3
    eff = _race_eff(axis, 5.0, [_strength(3, 0.3, 5.0)], [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("umaren", [[3, 7], [3, 11], [3, 12]], hit_prob=0.3, ev=1.2, g=6.0,
              odds_legs=[6.0, 12.0, 20.0]),
    ])
    sel = _selection(axis, 5.0, [_sel_plan("tansho", [[3]]),
                                 _sel_plan("umaren", [[3, 7], [3, 11], [3, 12]], ev=1.2)])
    rs = sz.size_race(eff, sel, bankroll=10000, per_race_cap=3000)
    for l in rs.legs:
        assert l.amount % 100 == 0 and l.amount >= 100


def test_combo_dedup_nested_widths_same_bettype():
    # 回帰: bettype_efficiency は同一券種で入れ子の幅 (馬単◎-相手2 と ◎-相手3) を別 plan で出す。
    # selection が両方含んでも、 サイジングは券種ごとに 1 つ (最良EV) に dedup し重複買いしない。
    axis = 5
    strengths = [_strength(5, 0.3, 4.0)]
    plans = [
        _plan("tansho", [[5]], hit_prob=0.3, ev=None, g=None, odds_legs=[4.0]),
        _plan("umatan", [[5, 12], [5, 7]], hit_prob=0.2, ev=1.0, g=10.0,
              odds_legs=[9.3, 12.4], label="馬単 ◎→相手2"),
        _plan("umatan", [[5, 12], [5, 7], [5, 14]], hit_prob=0.25, ev=1.1, g=12.0,
              odds_legs=[9.3, 12.4, 37.4], label="馬単 ◎→相手3"),
    ]
    eff = _race_eff(axis, 4.0, strengths, plans)
    sel = _selection(axis, 4.0, [
        _sel_plan("tansho", [[5]]),
        _sel_plan("umatan", [[5, 12], [5, 7]], ev=1.0),
        _sel_plan("umatan", [[5, 12], [5, 7], [5, 14]], ev=1.1),
    ])
    rs = sz.size_race(eff, sel, bankroll=10000, per_race_cap=3000)
    umatan_legs = [tuple(l.horses) for l in rs.legs if l.bet_type == "umatan"]
    # 重複なし & 最良EV(=相手3, 3点)が採用される
    assert len(umatan_legs) == len(set(umatan_legs))   # 重複買いしない
    assert set(umatan_legs) == {(5, 12), (5, 7), (5, 14)}


def test_combo_missing_odds_not_bought():
    # 複合の EV が None (市場オッズ未取得) → 買わない (アンカーのみ)
    axis = 3
    eff = _race_eff(axis, 5.0, [_strength(3, 0.3, 5.0)], [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("umaren", [[3, 7]], hit_prob=0.2, ev=None, g=None, odds_legs=[None]),
    ])
    sel = _selection(axis, 5.0, [_sel_plan("tansho", [[3]]),
                                 _sel_plan("umaren", [[3, 7]], ev=None)])
    rs = sz.size_race(eff, sel, bankroll=10000, per_race_cap=3000)
    assert all(l.bet_type == "tansho" for l in rs.legs)


# --- per_race truncate + アンカー保護 ---

def test_per_race_truncate_protects_anchor():
    # per_race=500 と小さく、 アンカー300 + 複合多数 → 複合を先に drop、 アンカー残す
    axis = 3
    eff = _race_eff(axis, 5.0, [_strength(3, 0.3, 5.0)], [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("umaren", [[3, 7], [3, 11]], hit_prob=0.3, ev=1.2, g=6.0, odds_legs=[6.0, 12.0]),
        _plan("sanrentan", [[3, 7, 11]], hit_prob=0.05, ev=1.8, g=40.0, odds_legs=[40.0]),
    ])
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("umaren", [[3, 7], [3, 11]], ev=1.2),
        _sel_plan("sanrentan", [[3, 7, 11]], ev=1.8),
    ])
    rs = sz.size_race(eff, sel, bankroll=10000, per_race_cap=500)
    assert rs.total_yen <= 500
    # アンカー単は必ず残る
    assert any(l.bet_type == "tansho" for l in rs.legs)


def test_fit_legs_to_cap_scales_and_protects_anchor():
    rid = "2026053108031109"
    legs = [
        sz.SizedLeg(rid, "tansho", [3], 300, "単", 5.0, None, 0.3, ""),
        sz.SizedLeg(rid, "umaren", [3, 7], 2000, "馬連", 6.0, 1.2, 0.3, ""),
        sz.SizedLeg(rid, "sanrentan", [3, 7, 11], 2000, "三連単", 40.0, 0.5, 0.05, ""),
    ]  # total 4300 > cap 1000
    fitted, dropped = sz.fit_legs_to_cap(legs, 1000)
    assert sum(l.amount for l in fitted) <= 1000
    assert any(l.bet_type == "tansho" for l in fitted)   # アンカー保護


# --- get_sizer ---

def test_get_sizer_known():
    assert sz.get_sizer("anchor_kelly_combo_ev") is sz.size_race
    assert sz.get_sizer("adaptive_fund") is sz.size_race_adaptive


def test_adaptive_sizer_skip_all_empty():
    axis = 3
    eff = _race_eff(axis, 1.5, [_strength(3, 0.05, 1.5)],
                    [_plan("tansho", [[3]], hit_prob=0.05, ev=None, g=None, odds_legs=[1.5])])
    sel = bs.BetSelection(
        race_id=eff.race_id, date=eff.date, venue_name=eff.venue_name,
        race_number=eff.race_number, grade=eff.grade,
        axis_umaban=axis, axis_name=f"H{axis}", axis_odds=1.5,
        strategy="skip_all", requested_strategy="adaptive",
        ev_floor=1.0, taste=None, specialist=None,
        selected_plans=[], skipped_plans=[], decision_reason="x",
        fund_mode="skip_all", fund_reason="降りる", kelly_boost=1.0,
    )
    rs = sz.size_race_adaptive(eff, sel, bankroll=10000, per_race_cap=3000)
    assert rs.legs == []
    assert rs.total_yen == 0


def test_adaptive_sizer_boost_increases_anchor():
    axis = 3
    eff = _race_eff(axis, 4.0, [_strength(3, 0.35, 4.0)],
                    [_plan("tansho", [[3]], hit_prob=0.35, ev=None, g=None, odds_legs=[4.0])])
    sel = _selection(axis, 4.0, [_sel_plan("tansho", [[3]])])
    sel.requested_strategy = "adaptive"
    sel.fund_mode = "boost"
    sel.kelly_boost = 1.5
    base = sz.size_race(eff, sel, bankroll=10000, per_race_cap=3000)
    boosted = sz.size_race_adaptive(eff, sel, bankroll=10000, per_race_cap=3000)
    assert boosted.anchor_yen >= base.anchor_yen


def test_get_sizer_unknown_raises():
    with pytest.raises(ValueError):
        sz.get_sizer("nonexistent")

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


def test_alloc_mode_inverse_flat_odds():
    # Session 168: plan 内配分の天井変種。 legs odds 5 vs 20、 budget 1000。
    legs = [[3, 7], [3, 11]]
    odds = [5.0, 20.0]
    inv = dict((o, a) for (_l, o, a) in sz._alloc_inverse_odds(legs, odds, 1000, mode="inverse"))
    flat = dict((o, a) for (_l, o, a) in sz._alloc_inverse_odds(legs, odds, 1000, mode="flat"))
    od = dict((o, a) for (_l, o, a) in sz._alloc_inverse_odds(legs, odds, 1000, mode="odds"))
    # inverse: 低オッズに厚く (天井低い)
    assert inv[5.0] > inv[20.0]
    # flat: 均等
    assert flat[5.0] == flat[20.0]
    # odds: 高オッズ=高配当点に厚く (天井高い)
    assert od[20.0] > od[5.0]
    # 全モードとも budget を超えない
    for d in (inv, flat, od):
        assert sum(d.values()) <= 1000


def test_alloc_mode_default_is_inverse():
    # 既定 (mode 省略) = inverse (本番不変)。
    legs = [[3, 7], [3, 11]]
    odds = [5.0, 20.0]
    default = sz._alloc_inverse_odds(legs, odds, 1000)
    explicit = sz._alloc_inverse_odds(legs, odds, 1000, mode="inverse")
    assert [a for (_l, _o, a) in default] == [a for (_l, _o, a) in explicit]


def test_combo_allowed_types_restricts():
    # Session 168: allowed_types で券種を絞る (三連系のみ等)。
    axis = 3
    strengths = [_strength(3, 0.3, 5.0)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("umaren", [[3, 7], [3, 11]], hit_prob=0.3, ev=1.2, g=6.0, odds_legs=[6.0, 12.0]),
        _plan("sanrentan", [[3, 7, 11]], hit_prob=0.05, ev=1.8, g=40.0, odds_legs=[40.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("umaren", [[3, 7], [3, 11]], ev=1.2, g=6.0),
        _sel_plan("sanrentan", [[3, 7, 11]], ev=1.8, g=40.0),
    ])
    eff_by_key = {(p.bet_type, sz._legs_key(p.legs)): p for p in plans}
    legs = sz._size_combo_legs(eff.race_id, eff, sel, eff_by_key, 3000,
                               allowed_types=frozenset({"sanrentan"}))
    bts = {l.bet_type for l in legs}
    assert bts == {"sanrentan"}   # 馬連は除外される


def test_shobu_rate_combo_alloc_mode_threads_through():
    # Session 168: size_race_shobu_rate に combo_alloc_mode を渡すと plan 内配分が変わる。
    axis = 3
    strengths = [_strength(3, 0.3, 5.0)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("umaren", [[3, 7], [3, 11]], hit_prob=0.3, ev=1.2, g=6.0, odds_legs=[6.0, 30.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [_sel_plan("umaren", [[3, 7], [3, 11]], ev=1.2, g=6.0)])
    # 非勝負R (tansho_H 不成立) → combo のみ。 odds 配分なら高オッズ(30)点が厚い。
    rs_inv = sz.size_race_shobu_rate(eff, sel, bankroll=100000, per_race_cap=5200,
                                     combo_alloc_mode="inverse")
    rs_odds = sz.size_race_shobu_rate(eff, sel, bankroll=100000, per_race_cap=5200,
                                      combo_alloc_mode="odds")
    hi_inv = sum(l.amount for l in rs_inv.legs if l.leg_odds == 30.0)
    hi_odds = sum(l.amount for l in rs_odds.legs if l.leg_odds == 30.0)
    assert hi_odds > hi_inv   # odds モードは高配当点に厚い


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


# --- fixed_grade_v1: 評価ベース固定配分 (Session 161) ---

def _strength_g(umaban, pred_w, odds, composite, place_odds_min=None):
    """composite / place_odds_min を指定できる強さ (fixed_grade テスト用)。"""
    return be.HorseStrength(
        umaban=umaban, horse_name=f"H{umaban}", win_prob=pred_w, odds=odds,
        place_odds_min=place_odds_min, pred_w=pred_w, pred_p=None, ar_deviation=None,
        z_w=None, z_p=None, z_adr=None, composite=composite)


def test_get_sizer_fixed_grade_known():
    assert sz.get_sizer("fixed_grade_v1") is sz.size_race_fixed_grade


def _absorbing_combo_plan():
    """残予算を吸収する fundable な combo plan (使い切り上乗せを抑止し tier share を観測するため)。

    Session 163 で「combo が出ないと残予算を単に上乗せ」(使い切り保証) を入れたため、 単独軸
    (tansho のみ) だと単が常に cap=3000 に膨らみ tier share が観測できない。 EV>=floor かつ
    vs='gt' の広い combo を置いて residual を combo に吸わせ、 単を tier share のまま残す。
    """
    return _plan("sanrenpuku", [[3, 7, 11], [3, 7, 12], [3, 11, 12]],
                 hit_prob=0.1, ev=1.5, g=20.0, odds_legs=[20.0, 22.0, 24.0])


def test_fixed_grade_tansho_is_fixed_not_kelly():
    """単勝額がオッズに依らず一定 = Kelly でなく固定割合であることを証明。"""
    axis = 3
    sel = _selection(axis, None, [_sel_plan("tansho", [[3]]),
                                  _sel_plan("sanrenpuku", [[3, 7, 11], [3, 7, 12],
                                                           [3, 11, 12]], ev=1.5, g=20.0)])
    amounts = []
    for odds in (1.3, 8.0):
        eff = _race_eff(axis, odds,
                        [_strength_g(3, 0.3, odds, composite=1.0)],
                        [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None,
                               odds_legs=[odds]),
                         _absorbing_combo_plan()])
        sel.axis_odds = odds
        rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
        tansho = [l for l in rs.legs if l.bet_type == "tansho"]
        assert len(tansho) == 1
        amounts.append(tansho[0].amount)
    # 単独軸 → gap = composite 1.0 >= 1.0 → strong tier → v1 FIXED_SHARES 30% × 3000 = 900。
    #   combo が residual を吸うので使い切り上乗せは発火しない。
    assert amounts[0] == amounts[1] == 900
    # Kelly なら 1.3倍と8.0倍で額が変わるはず。 固定なので同一。
    assert sz.kelly_amount(0.3, 1.3, bankroll=10000, kelly_fraction=0.25,
                           per_bet_cap_pct=0.10) != amounts[0]


def test_fixed_grade_tier_modulation():
    """composite tier (strong/mid/weak) で単勝割合が変わる (v1 FIXED_SHARES)。"""
    axis = 3
    sel = _selection(axis, 5.0, [_sel_plan("tansho", [[3]]),
                                 _sel_plan("sanrenpuku", [[3, 7, 11], [3, 7, 12],
                                                          [3, 11, 12]], ev=1.5, g=20.0)])
    got = {}
    for tier, comp in (("strong", 1.0), ("mid", 0.5), ("weak", 0.1)):
        eff = _race_eff(axis, 5.0, [_strength_g(3, 0.3, 5.0, composite=comp)],
                        [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None,
                               odds_legs=[5.0]),
                         _absorbing_combo_plan()])
        # 既定 FIXED_SHARES (v1) で tier modulation を見る (combo が residual を吸う)。
        rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
        got[tier] = next(l.amount for l in rs.legs if l.bet_type == "tansho")
    # 単独軸 → gap=composite。 v1 FIXED_SHARES: strong 30%×3000=900 / mid 25%=750→700 /
    # weak 15%=450→400 (float 449.99→100円切捨)。 strong>mid>weak が要件。
    assert got["strong"] == 900 and got["mid"] == 700 and got["weak"] == 400
    assert got["strong"] > got["mid"] > got["weak"]


@pytest.fixture
def swap_enabled(monkeypatch):
    """swap は本番では無効 (floor=0.0・Session161 実払戻検証で一律マイナス)。
    機構そのものの単体テストは floor を明示的に立てて検証する。"""
    monkeypatch.setattr(sz, "WIDE_SWAP_PLACE_ODDS_FLOOR", 1.9)


def test_swap_disabled_by_default():
    """★本番既定 floor=0.0 = 置換は発火しない (複勝固定額で維持)★。"""
    assert sz.WIDE_SWAP_PLACE_ODDS_FLOOR == 0.0
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=1.0, place_odds_min=1.4)]  # 低 place
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.6, ev=None, g=None, odds_legs=[1.4]),
        _plan("wide", [[3, 7], [3, 11]], hit_prob=0.4, ev=1.3, g=8.0, odds_legs=[8.0, 9.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("fukusho", [[3]]),
        _sel_plan("wide", [[3, 7], [3, 11]], ev=1.3, g=8.0),
    ])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
    # 既定では置換せず複勝アンカーを維持する
    assert [l for l in rs.legs if l.bet_type == "fukusho"]


def test_fukusho_to_wide_swap_on_low_place_odds(swap_enabled):
    """[機構] floor を立てれば複勝 place<floor → ワイドに置換・複勝 leg なし・二重買いなし。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=1.0, place_odds_min=1.4)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.6, ev=None, g=None, odds_legs=[1.4]),
        _plan("wide", [[3, 7], [3, 11]], hit_prob=0.4, ev=1.3, g=8.0, odds_legs=[8.0, 9.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("fukusho", [[3]]),
        _sel_plan("wide", [[3, 7], [3, 11]], ev=1.3, g=8.0),
    ])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
    assert not [l for l in rs.legs if l.bet_type == "fukusho"]   # 複勝は消えた
    wide_legs = [l for l in rs.legs if l.bet_type == "wide"]
    assert wide_legs                                              # ワイドが入った
    # 二重買いなし: 同じワイド組が anchor 置換 1 回ぶん (combo に再登場しない)
    wide_horse_sets = [tuple(l.horses) for l in wide_legs]
    assert len(wide_horse_sets) == len(set(wide_horse_sets))


def test_no_swap_when_place_odds_above_floor():
    """複勝 place_odds_min が floor 以上 → 複勝アンカー維持・置換しない。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=1.0, place_odds_min=2.5)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.5, ev=None, g=None, odds_legs=[2.5]),
        _plan("wide", [[3, 7], [3, 11]], hit_prob=0.4, ev=1.3, g=8.0, odds_legs=[8.0, 9.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("fukusho", [[3]]),
        _sel_plan("wide", [[3, 7], [3, 11]], ev=1.3, g=8.0),
    ])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
    fuku = [l for l in rs.legs if l.bet_type == "fukusho"]
    assert len(fuku) == 1
    assert fuku[0].horses == [3]
    # 単独軸 strong tier 20% × 3000 = 600
    assert fuku[0].amount == 600


def test_swap_falls_back_when_wide_missing_odds(swap_enabled):
    """[機構] floor を立て低 place_odds でもワイドのオッズ欠損 (EV None) → 置換中止・複勝へ。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=1.0, place_odds_min=1.4)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.6, ev=None, g=None, odds_legs=[1.4]),
        # ワイドはオッズ欠損 (EV None) → swap できない
        _plan("wide", [[3, 7]], hit_prob=0.4, ev=None, g=None, odds_legs=[None]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("fukusho", [[3]]),
        _sel_plan("wide", [[3, 7]]),
    ])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
    assert [l for l in rs.legs if l.bet_type == "fukusho"]   # 複勝が残る
    assert not [l for l in rs.legs if l.bet_type == "wide"]  # ワイドは買われない


def test_fixed_grade_per_race_cap_and_anchor_protection():
    """極小 cap でも total <= cap・単勝 (アンカー) は残る。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=1.0, place_odds_min=2.5)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.5, ev=None, g=None, odds_legs=[2.5]),
        _plan("umaren", [[3, 7], [3, 11]], hit_prob=0.3, ev=1.2, g=6.0, odds_legs=[6.0, 12.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("fukusho", [[3]]),
        _sel_plan("umaren", [[3, 7], [3, 11]], ev=1.2, g=6.0),
    ])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=500)
    assert rs.total_yen <= 500
    assert [l for l in rs.legs if l.bet_type == "tansho"]   # アンカー保護で残る


def test_fixed_grade_rounds_below_min_drops_leg():
    """cap × frac < 100円 → その leg は省略 (sub-100 円なし)。"""
    axis = 3
    # cap=200, weak tier place 15% × 200 = 30 < 100 → 第2アンカーは出ない
    strengths = [_strength_g(3, 0.3, 5.0, composite=0.1, place_odds_min=2.5)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.5, ev=None, g=None, odds_legs=[2.5]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [_sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]])])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=200)
    assert all(l.amount >= sz.MIN_BET_YEN for l in rs.legs)
    # weak 20% × 200 = 40 < 100 → 単勝も出ない
    assert not [l for l in rs.legs if l.bet_type == "fukusho"]


def test_fixed_grade_skips_tansho_when_axis_odds_missing():
    """axis_odds None → 単勝 leg を出さない (複/combo は継続)。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, None, composite=1.0, place_odds_min=2.5)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[None]),
        _plan("fukusho", [[3]], hit_prob=0.5, ev=None, g=None, odds_legs=[2.5]),
    ]
    eff = _race_eff(axis, None, strengths, plans)
    sel = _selection(axis, None, [_sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]])])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
    assert not [l for l in rs.legs if l.bet_type == "tansho"]
    assert [l for l in rs.legs if l.bet_type == "fukusho"]


# --- fixed_grade_v2: 見送り + 堅いRでcombo厚く (Session 162) ---

def test_get_sizer_fixed_grade_v2_known():
    assert sz.get_sizer("fixed_grade_v2") is sz.size_race_fixed_grade_v2


def test_v2_does_not_skip_low_ceiling_race():
    """★Session 163: 見送りゲートは実払戻で害と確定 → 無効化★。 天井が低くても降りない。

    SKIP_MAX_ODDS_FLOOR=0.0 なので、 合成オッズが低い (堅い高的中) レースでも v2 は買う。
    validate_v2_skip_gate.py が「降りた群の方が ROI 高い」= ゲートは害と実証したため。
    """
    assert sz.SKIP_MAX_ODDS_FLOOR == 0.0   # ★無効化が本番の意図 (回帰ガード)
    axis = 3
    strengths = [_strength_g(3, 0.3, 1.2, composite=1.5, place_odds_min=1.1)]
    # 全 plan の合成オッズが低い (天井 < 5.0) = 旧ゲートなら見送ったレース
    plans = [
        _plan("tansho", [[3]], hit_prob=0.6, ev=None, g=1.2, odds_legs=[1.2]),
        _plan("fukusho", [[3]], hit_prob=0.9, ev=None, g=1.1, odds_legs=[1.1]),
        _plan("umaren", [[3, 7]], hit_prob=0.4, ev=0.9, g=2.5, odds_legs=[2.5]),
    ]
    eff = _race_eff(axis, 1.2, strengths, plans)
    sel = _selection(axis, 1.2, [_sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]])])
    rs = sz.size_race_fixed_grade_v2(eff, sel, bankroll=10000, per_race_cap=3000)
    assert rs.legs                                       # ★降りない (買う)
    assert not any("見送り" in w for w in rs.warnings)


def test_skip_gate_machinery_still_works_when_floor_explicit():
    """★ゲート機構自体は残置 (将来 別軸で再設計する足場)★。 本体に floor>0 を明示すれば降りる。

    本番 v2 は floor=0 で無効化したが、 size_race_fixed_grade に _skip_max_odds_floor>0 を
    渡すと従来通り空 RaceSizing を返す (機構が壊れていないことを担保)。
    """
    axis = 3
    strengths = [_strength_g(3, 0.3, 1.2, composite=1.5, place_odds_min=1.1)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.6, ev=None, g=1.2, odds_legs=[1.2]),
        _plan("fukusho", [[3]], hit_prob=0.9, ev=None, g=1.1, odds_legs=[1.1]),
        _plan("umaren", [[3, 7]], hit_prob=0.4, ev=0.9, g=2.5, odds_legs=[2.5]),
    ]
    eff = _race_eff(axis, 1.2, strengths, plans)
    sel = _selection(axis, 1.2, [_sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]])])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000,
                                  _shares_table=sz.FIXED_SHARES_V2, _skip_max_odds_floor=5.0)
    assert rs.legs == [] and rs.total_yen == 0
    assert any("見送り" in w for w in rs.warnings)


def test_v2_buys_when_ceiling_high_enough():
    """天井 >= floor (combo で配当が作れる) → 買う (降りない)。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, 1.2, composite=1.5, place_odds_min=1.4)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.5, ev=None, g=1.2, odds_legs=[1.2]),
        _plan("fukusho", [[3]], hit_prob=0.8, ev=None, g=1.4, odds_legs=[1.4]),
        # 三連単で天井が高い (合成40倍) = 単安くても三連単で旨味あり → 買う
        _plan("sanrentan", [[3, 7, 11]], hit_prob=0.05, ev=1.8, g=40.0, odds_legs=[40.0]),
    ]
    eff = _race_eff(axis, 1.2, strengths, plans)
    sel = _selection(axis, 1.2, [_sel_plan("tansho", [[3]]),
                                 _sel_plan("sanrentan", [[3, 7, 11]], ev=1.8, g=40.0)])
    rs = sz.size_race_fixed_grade_v2(eff, sel, bankroll=10000, per_race_cap=3000)
    assert rs.legs                                          # 降りない
    assert not any("見送り" in w for w in rs.warnings)


def test_v2_strong_tier_thins_tansho_vs_v1():
    """★同じ strong レースで v2 は v1 より単勝を薄くする (combo厚く)★。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=1.5, place_odds_min=2.0)]  # gap1.5=strong
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=5.0, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.5, ev=None, g=2.0, odds_legs=[2.0]),
        _plan("sanrenpuku", [[3, 7, 11]], hit_prob=0.1, ev=1.5, g=20.0, odds_legs=[20.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]]),
        _sel_plan("sanrenpuku", [[3, 7, 11]], ev=1.5, g=20.0)])
    v1 = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
    v2 = sz.size_race_fixed_grade_v2(eff, sel, bankroll=10000, per_race_cap=3000)
    t1 = sum(l.amount for l in v1.legs if l.bet_type == "tansho")
    t2 = sum(l.amount for l in v2.legs if l.bet_type == "tansho")
    c1 = sum(l.amount for l in v1.legs if l.bet_type == "sanrenpuku")
    c2 = sum(l.amount for l in v2.legs if l.bet_type == "sanrenpuku")
    # v1 strong=単30%=900, v2 strong=単15%=450 → v2 の方が単薄い
    assert t2 < t1
    # combo は v2 の方が厚い (単/複が薄い分 residual が増える)
    assert c2 > c1


def test_fixed_grade_useitup_topup_tansho_when_no_combo():
    """★Session 163: 使い切り保証★。 combo が出ないレースで残予算を単勝◎に上乗せし cap を使い切る。

    ふくだ「3000円を使い切る・残余は単に上乗せ」。 combo plan が selection に無い (= weak で
    全 combo が floor 未満等) と、 単 tier share だけでは cap が大量に余る → 残余を単に topup。
    """
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=0.1)]  # weak tier (gap=0.1)
    # combo plan 無し (単のみ)。 使い切り保証で単が cap=3000 まで膨らむはず。
    plans = [_plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0])]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [_sel_plan("tansho", [[3]])])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000,
                                  _shares_table=sz.FIXED_SHARES_V2)
    tansho = [l for l in rs.legs if l.bet_type == "tansho"]
    assert len(tansho) == 1
    assert tansho[0].amount == 3000            # ★残余を全部単に上乗せ → cap 使い切り
    assert sum(l.amount for l in rs.legs) == 3000
    assert any("使い切り" in w for w in rs.warnings)


def test_v2_emits_no_fukusho_budget_to_combo():
    """★Session 163: 複勝はメインから外した (FIXED_SHARES_V2 の複 share=0)★。

    ふくだ「数十円取りにいくゴミ複に意味なし」+ 複勝は専門キャラに移譲。 v2 は複を出さず、
    その予算が combo に回る (v1=複あり より v2=複なし の方が combo が厚い)。
    """
    assert all(a == 0.0 for _, a in sz.FIXED_SHARES_V2.values())  # 複 share 全 tier 0 (回帰ガード)
    axis = 3
    strengths = [_strength_g(3, 0.3, 5.0, composite=1.5, place_odds_min=1.4)]  # mid 寄り
    plans = [
        _plan("tansho", [[3]], hit_prob=0.4, ev=None, g=5.0, odds_legs=[5.0]),
        _plan("fukusho", [[3]], hit_prob=0.6, ev=None, g=1.4, odds_legs=[1.4]),
        _plan("sanrenpuku", [[3, 7, 11]], hit_prob=0.1, ev=1.5, g=20.0, odds_legs=[20.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]), _sel_plan("fukusho", [[3]]),
        _sel_plan("sanrenpuku", [[3, 7, 11]], ev=1.5, g=20.0)])
    v1 = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)  # 複あり
    v2 = sz.size_race_fixed_grade_v2(eff, sel, bankroll=10000, per_race_cap=3000)  # 複なし
    assert not any(l.bet_type == "fukusho" for l in v2.legs)          # ★v2 は複を出さない
    assert any(l.bet_type == "fukusho" for l in v1.legs)              # v1 は複を出す (対比)
    c1 = sum(l.amount for l in v1.legs if l.bet_type == "sanrenpuku")
    c2 = sum(l.amount for l in v2.legs if l.bet_type == "sanrenpuku")
    assert c2 > c1                                                    # 複の予算が combo に回る


def test_v1_unchanged_no_skip_no_v2_shares():
    """v1 は見送りせず FIXED_SHARES のまま (回帰・v2 追加で壊れてない)。"""
    axis = 3
    strengths = [_strength_g(3, 0.3, 1.2, composite=1.5, place_odds_min=1.1)]
    # 残予算を吸う combo を置き、 使い切り上乗せを抑止して tier share (30%=900) を観測。
    plans = [_plan("tansho", [[3]], hit_prob=0.6, ev=None, g=1.2, odds_legs=[1.2]),
             _absorbing_combo_plan()]
    eff = _race_eff(axis, 1.2, strengths, plans)
    sel = _selection(axis, 1.2, [_sel_plan("tansho", [[3]]),
                                 _sel_plan("sanrenpuku", [[3, 7, 11], [3, 7, 12],
                                                          [3, 11, 12]], ev=1.5, g=20.0)])
    rs = sz.size_race_fixed_grade(eff, sel, bankroll=10000, per_race_cap=3000)
    # v1 は天井が低くても見送らない & strong 単30%×3000=900
    assert any(l.bet_type == "tansho" and l.amount == 900 for l in rs.legs)


# --- template_flat: ラボのテンプレを全点 flat で実戦化 (Session 162) ---

def _strength_rank(umaban, composite, rank, odds=5.0):
    """composite + rank_composite を指定できる強さ (template_flat の序列テスト用)。"""
    s = be.HorseStrength(
        umaban=umaban, horse_name=f"H{umaban}", win_prob=0.2, odds=odds,
        place_odds_min=None, pred_w=0.2, pred_p=None, ar_deviation=None,
        z_w=None, z_p=None, z_adr=None, composite=composite)
    s.rank_composite = rank
    return s


def _eff_5horses(axis=7):
    """composite 降順 7>3>9>4>1 の 5頭立て race_eff (◎=7,○=3,▲=9,△=4,Ⅲ=1)。"""
    strengths = [
        _strength_rank(7, 5.0, 1), _strength_rank(3, 4.0, 2), _strength_rank(9, 3.0, 3),
        _strength_rank(4, 2.0, 4), _strength_rank(1, 1.0, 5),
    ]
    return _race_eff(axis, 3.0, strengths, [])  # plans 空 = odds 補完なし (額に無影響)


def test_get_sizer_template_flat_known():
    assert sz.get_sizer("template_flat") is sz.size_race_template_flat


def test_template_flat_fukusho_korogashi_points_and_marks():
    """複勝堅実党 = 複◎ + ワイド◎-○ の 2点。 ◎=composite1位, ○=2位。"""
    eff = _eff_5horses()
    sizer = sz.make_template_sizer("fukusho_korogashi", 100)
    rs = sizer(eff, None, bankroll=10000, per_race_cap=3000)
    assert len(rs.legs) == 2
    fuku = [l for l in rs.legs if l.bet_type == "fukusho"]
    wide = [l for l in rs.legs if l.bet_type == "wide"]
    assert len(fuku) == 1 and fuku[0].horses == [7]          # 複◎
    assert len(wide) == 1 and sorted(wide[0].horses) == [3, 7]  # ワイド◎-○


def test_template_flat_all_legs_flat_stake():
    """全 leg が flat_stake で一律 (傾斜なし)。"""
    eff = _eff_5horses()
    sizer = sz.make_template_sizer("sanrenpuku_1jiku", 100)
    rs = sizer(eff, None, bankroll=10000, per_race_cap=3000)
    assert len(rs.legs) == 6                                  # ◎軸 ○▲△Ⅲ から3頭組 = C(4,2)=6
    assert all(l.amount == 100 for l in rs.legs)
    assert all(l.bet_type == "sanrenpuku" for l in rs.legs)
    assert rs.total_yen == 600


def test_template_flat_stake_scales_roi_invariant():
    """flat_stake を上げると総額が比例スケール (ROI 不変・点数不変)。"""
    eff = _eff_5horses()
    rs1 = sz.make_template_sizer("sanrenpuku_1jiku", 100)(eff, None, bankroll=10000,
                                                          per_race_cap=3000)
    rs3 = sz.make_template_sizer("sanrenpuku_1jiku", 300)(eff, None, bankroll=10000,
                                                          per_race_cap=3000)
    assert len(rs1.legs) == len(rs3.legs)
    assert rs3.total_yen == rs1.total_yen * 3
    assert all(l.amount == 300 for l in rs3.legs)


def test_template_flat_ignores_selection():
    """selection を完全に無視する (None でも buy 目が出る = テンプレが買い目を全決定)。"""
    eff = _eff_5horses()
    sizer = sz.make_template_sizer("fukusho_korogashi", 100)
    rs_none = sizer(eff, None, bankroll=10000, per_race_cap=3000)
    # selection に全く別の軸/plan を入れても結果は変わらない (テンプレは race_eff の序列のみ参照)
    bogus_sel = _selection(99, 1.5, [_sel_plan("umaren", [[99, 1]])])
    rs_bogus = sizer(eff, bogus_sel, bankroll=10000, per_race_cap=3000)
    assert [(l.bet_type, l.horses) for l in rs_none.legs] == \
           [(l.bet_type, l.horses) for l in rs_bogus.legs]


def test_template_flat_odds_backfill_from_plans():
    """plans にオッズがあれば leg_odds を補完する (表示用・額には無影響)。"""
    strengths = [
        _strength_rank(7, 5.0, 1), _strength_rank(3, 4.0, 2), _strength_rank(9, 3.0, 3),
        _strength_rank(4, 2.0, 4), _strength_rank(1, 1.0, 5),
    ]
    plans = [
        _plan("fukusho", [[7]], hit_prob=0.6, ev=None, g=None, odds_legs=[1.8]),
        _plan("wide", [[3, 7]], hit_prob=0.4, ev=1.2, g=8.0, odds_legs=[8.0]),
    ]
    eff = _race_eff(7, 3.0, strengths, plans)
    rs = sz.make_template_sizer("fukusho_korogashi", 100)(eff, None, bankroll=10000,
                                                          per_race_cap=3000)
    fuku = next(l for l in rs.legs if l.bet_type == "fukusho")
    wide = next(l for l in rs.legs if l.bet_type == "wide")
    assert fuku.leg_odds == 1.8
    assert wide.leg_odds == 8.0


def test_template_flat_under_cap_not_truncated():
    """最大点数テンプレ (honmei_formation 12点) × flat100 = 1200 < cap3000 → 按分しない。"""
    eff = _eff_5horses()
    rs = sz.make_template_sizer("honmei_formation", 100)(eff, None, bankroll=10000,
                                                         per_race_cap=3000)
    assert len(rs.legs) == 12
    assert rs.total_yen == 1200
    assert rs.n_dropped == 0
    assert not rs.warnings                                    # 按分警告なし


def test_template_flat_truncates_when_over_cap():
    """flat_stake を上げて cap 超 → fit_legs_to_cap 発火 (total<=cap・警告)。"""
    eff = _eff_5horses()
    # 6点 × 600 = 3600 > cap 3000
    rs = sz.make_template_sizer("sanrenpuku_1jiku", 600)(eff, None, bankroll=10000,
                                                         per_race_cap=3000)
    assert rs.total_yen <= 3000
    assert rs.warnings                                        # 乖離警告が出る


def test_template_flat_empty_strengths():
    """strengths 不在 → 空 RaceSizing (落ちない)。"""
    eff = _race_eff(7, 3.0, [], [])
    rs = sz.make_template_sizer("fukusho_korogashi", 100)(eff, None, bankroll=10000,
                                                          per_race_cap=3000)
    assert rs.legs == [] and rs.total_yen == 0


def test_template_flat_uses_composite_order_not_input_order():
    """strengths の並びが composite 降順でなくても rank_composite で序列化する。"""
    # わざと composite 昇順に並べる (1位が最後)
    strengths = [
        _strength_rank(1, 1.0, 5), _strength_rank(4, 2.0, 4), _strength_rank(9, 3.0, 3),
        _strength_rank(3, 4.0, 2), _strength_rank(7, 5.0, 1),
    ]
    eff = _race_eff(7, 3.0, strengths, [])
    rs = sz.make_template_sizer("fukusho_korogashi", 100)(eff, None, bankroll=10000,
                                                          per_race_cap=3000)
    fuku = next(l for l in rs.legs if l.bet_type == "fukusho")
    assert fuku.horses == [7]                                 # composite1位が◎ (入力順でなく)


# --- template_select: レース特性でテンプレ出し分け (Session 162 / Step2) ---

def _eff_top2(top2_each, axis=7):
    """上位2頭の win_prob を top2_each に設定した 5頭立て (堅い2強の判定テスト用)。"""
    strengths = [
        _strength_rank(7, 5.0, 1), _strength_rank(3, 4.0, 2), _strength_rank(9, 3.0, 3),
        _strength_rank(4, 2.0, 4), _strength_rank(1, 1.0, 5),
    ]
    strengths[0].win_prob = top2_each
    strengths[1].win_prob = top2_each
    return _race_eff(axis, 3.0, strengths, [])


def test_get_sizer_template_select_known():
    assert sz.get_sizer("template_select") is sz.size_race_template_select


def test_select_template_strong_top2_picks_sanrenpuku():
    # top2 = 0.3+0.3 = 0.6 >= 0.5 → 堅い2強 → 三連複1頭軸
    eff = _eff_top2(0.30)
    assert sz.select_template(eff) == "sanrenpuku_1jiku"


def test_select_template_weak_top2_picks_fukusho():
    # top2 = 0.15+0.15 = 0.3 < 0.5 → 複勝堅実党
    eff = _eff_top2(0.15)
    assert sz.select_template(eff) == "fukusho_korogashi"


def test_template_select_routes_to_correct_template():
    # 堅い2強 → 三連複6点、 団子 → 複勝2点 を sizer 出力で確認
    rs_strong = sz.size_race_template_select(_eff_top2(0.30), None,
                                             bankroll=10000, per_race_cap=3000)
    assert all(l.bet_type == "sanrenpuku" for l in rs_strong.legs)
    assert len(rs_strong.legs) == 6

    rs_weak = sz.size_race_template_select(_eff_top2(0.15), None,
                                           bankroll=10000, per_race_cap=3000)
    bts = {l.bet_type for l in rs_weak.legs}
    assert bts == {"fukusho", "wide"}                         # 複勝堅実党


def test_template_select_flat_and_matches_flat_path():
    # 出し分け先のテンプレを template_flat で直接出したものと一致 (委譲が正しい)
    eff = _eff_top2(0.30)
    direct = sz.make_template_sizer("sanrenpuku_1jiku", 100)(eff, None, bankroll=10000,
                                                            per_race_cap=3000)
    via = sz.size_race_template_select(eff, None, bankroll=10000, per_race_cap=3000)
    assert [(l.bet_type, l.horses, l.amount) for l in direct.legs] == \
           [(l.bet_type, l.horses, l.amount) for l in via.legs]


def test_size_race_combo_block_unchanged_after_refactor():
    """combo ブロックを _size_combo_legs に抽出した後も size_race の挙動が不変 (パリティ)。"""
    axis = 3
    strengths = [_strength(3, 0.3, 5.0)]
    plans = [
        _plan("tansho", [[3]], hit_prob=0.3, ev=None, g=None, odds_legs=[5.0]),
        _plan("umaren", [[3, 7], [3, 11]], hit_prob=0.3, ev=1.2, g=6.0, odds_legs=[6.0, 12.0]),
        _plan("sanrenpuku", [[3, 7, 11]], hit_prob=0.05, ev=1.8, g=40.0, odds_legs=[40.0]),
    ]
    eff = _race_eff(axis, 5.0, strengths, plans)
    sel = _selection(axis, 5.0, [
        _sel_plan("tansho", [[3]]),
        _sel_plan("umaren", [[3, 7], [3, 11]], ev=1.2, g=6.0),
        _sel_plan("sanrenpuku", [[3, 7, 11]], ev=1.8, g=40.0),
    ])
    rs = sz.size_race(eff, sel, bankroll=10000, per_race_cap=3000)
    combo = [l for l in rs.legs if l.bet_type in ("umaren", "sanrenpuku")]
    assert combo                          # combo が出ている
    assert rs.combo_yen <= 3000 - rs.anchor_yen + 100   # 残予算内 (丸め余地)


# ===========================================================================
# shobu_rate: 勝負条件 (tansho_H 4条件・rank_w◎) で単勝を厚く (Session 166)
# ===========================================================================

def _shobu_strength(umaban, pred_w, odds, *, rank_w, gap, ev, margin):
    """勝負条件フィールド付き HorseStrength。 rank_w/gap/ev/margin を明示。"""
    s = be.HorseStrength(
        umaban=umaban, horse_name=f"H{umaban}", win_prob=pred_w, odds=odds,
        place_odds_min=None, pred_w=pred_w, pred_p=None, ar_deviation=None,
        z_w=None, z_p=None, z_adr=None, composite=0.0)
    s.rank_w = rank_w
    s.win_vb_gap = gap
    s.win_ev = ev
    s.predicted_margin = margin
    return s


def _shobu_eff(axis, axis_odds, strengths, plans):
    """rank_composite を強さ順に振った race_eff (shobu は rank_w◎ を見るので axis は別でよい)。"""
    return _race_eff(axis, axis_odds, strengths, plans)


# --- is_shobu_race の境界 ---

def test_is_shobu_race_all_conditions_met():
    # rank_w=1, gap=3, ev=1.3, margin=60 (全境界ちょうど) → True
    s = _shobu_strength(5, 0.2, 8.0, rank_w=1, gap=3, ev=1.3, margin=60)
    eff = _shobu_eff(5, 8.0, [s], [])
    assert sz.is_shobu_race(eff) is True


def test_is_shobu_race_fails_each_condition():
    # 各条件を 1 つだけ外すと False
    base = dict(rank_w=1, gap=3, ev=1.3, margin=60)
    for key, bad in [("rank_w", 2), ("gap", 2), ("ev", 1.29), ("margin", 61)]:
        kw = dict(base); kw[key] = bad
        s = _shobu_strength(5, 0.2, 8.0, **kw)
        eff = _shobu_eff(5, 8.0, [s], [])
        assert sz.is_shobu_race(eff) is False, f"{key}={bad} は勝負条件を外すべき"


def test_is_shobu_race_missing_feature_is_false():
    # 素性欠損 (win_ev=None) は判定不能 → False
    s = _shobu_strength(5, 0.2, 8.0, rank_w=1, gap=3, ev=1.3, margin=60)
    s.win_ev = None
    eff = _shobu_eff(5, 8.0, [s], [])
    assert sz.is_shobu_race(eff) is False


def test_is_shobu_race_no_rank_w_axis_is_false():
    # rank_w=1 の馬が居ない → False
    s = _shobu_strength(5, 0.2, 8.0, rank_w=2, gap=3, ev=1.3, margin=60)
    eff = _shobu_eff(5, 8.0, [s], [])
    assert sz.is_shobu_race(eff) is False


# --- 勝負R: rank_w◎ の単勝が厚い・複勝なし ---

def test_shobu_race_thick_tansho_on_rank_w_axis():
    # composite◎=3 だが rank_w◎=5。 勝負R では rank_w◎=5 の単勝を厚く買う。
    rankw = _shobu_strength(5, 0.2, 8.0, rank_w=1, gap=3, ev=1.5, margin=40)
    other = _shobu_strength(3, 0.25, 4.0, rank_w=2, gap=0, ev=1.0, margin=30)
    eff = _shobu_eff(3, 4.0, [other, rankw],  # axis(composite)=3
                     [_plan("tansho", [[5]], hit_prob=0.2, ev=None, g=None, odds_legs=[8.0])])
    sel = _selection(3, 4.0, [_sel_plan("tansho", [[5]])])
    rs = sz.size_race_shobu_rate(eff, sel, bankroll=10000, per_race_cap=4500)
    tansho = [l for l in rs.legs if l.bet_type == "tansho"]
    assert len(tansho) == 1
    assert tansho[0].horses == [5]                    # ★rank_w◎=5 (composite◎=3 ではない)
    assert tansho[0].amount >= int(4500 * sz.SHOBU_TANSHO_SHARE)  # 厚い (70%以上)
    assert not [l for l in rs.legs if l.bet_type == "fukusho"]    # ★複勝なし


def test_shobu_race_no_combo_all_to_tansho():
    # combo plan が無いレース → 使い切りで単勝に全額。 単勝シェア=100%。
    rankw = _shobu_strength(5, 0.2, 8.0, rank_w=1, gap=4, ev=2.0, margin=35)
    eff = _shobu_eff(5, 8.0, [rankw],
                     [_plan("tansho", [[5]], hit_prob=0.2, ev=None, g=None, odds_legs=[8.0])])
    sel = _selection(5, 8.0, [_sel_plan("tansho", [[5]])])
    rs = sz.size_race_shobu_rate(eff, sel, bankroll=10000, per_race_cap=4500)
    assert rs.total_yen == 4500
    tansho = [l for l in rs.legs if l.bet_type == "tansho"]
    assert tansho[0].amount == 4500                   # cap を使い切り単勝へ


# --- 通常R (非勝負): 単勝は買わない・combo は v2 のまま (設計書§3.3) ---

def _normal_race_eff_sel():
    """非勝負R (gap=0) + 残予算を吸う combo plan を持つ race_eff / selection。"""
    s = _shobu_strength(5, 0.2, 8.0, rank_w=1, gap=0, ev=1.0, margin=30)  # gap=0 で非勝負
    plans = [_plan("tansho", [[5]], hit_prob=0.2, ev=None, g=None, odds_legs=[8.0]),
             _absorbing_combo_plan()]
    eff = _shobu_eff(5, 8.0, [s], plans)
    sel = _selection(5, 8.0, [_sel_plan("tansho", [[5]]),
                              _sel_plan("sanrenpuku", [[3, 7, 11], [3, 7, 12], [3, 11, 12]],
                                        ev=1.5, g=20.0)])
    return eff, sel


def test_normal_race_shrinks_cap_to_normal_rate():
    # 勝負条件を満たさない → v2 委譲・cap は 4500×(5/15)=1500 に縮む。
    eff, sel = _normal_race_eff_sel()
    rs = sz.size_race_shobu_rate(eff, sel, bankroll=10000, per_race_cap=4500,
                                 normal_rate_pct=5.0, shobu_rate_pct=15.0)
    # 通常R は cap1500 内に収まる (4500ではなく縮んだ上限)
    assert rs.total_yen <= 1500


def test_normal_race_no_tansho_combo_uses_full_cap():
    # ★設計書§3.3 (Session 167): 通常レートは単勝を買わず combo に cap をフルに回す★。
    #   抜いた単勝(-EV)分を浮かせず +EV の combo へ。
    eff, sel = _normal_race_eff_sel()
    rs = sz.size_race_shobu_rate(eff, sel, bankroll=10000, per_race_cap=4500,
                                 normal_rate_pct=5.0, shobu_rate_pct=15.0)
    normal_cap = 1500  # 4500 × 5/15
    # 単勝・複勝は無い (combo のみ)。
    assert [l for l in rs.legs if l.bet_type in ("tansho", "fukusho")] == []
    assert rs.legs, "combo plan があるので買い目は空でない"
    # cap 内に収まる。
    assert 0 < rs.total_yen <= normal_cap
    # 番人: 素の v2 は (縮小cap でも) 単勝を出す = 通常レートが単勝を抜いていることの対照。
    rs_v2 = sz.size_race_fixed_grade_v2(eff, sel, bankroll=10000, per_race_cap=normal_cap)
    assert [l for l in rs_v2.legs if l.bet_type == "tansho"] != []
    # combo は cap をフルに使う = 素の v2 の combo (単勝に予算を取られた後) より厚い (同等以上)。
    v2_combo = sum(l.amount for l in rs_v2.legs if l.bet_type not in ("tansho", "fukusho"))
    assert rs.total_yen >= v2_combo


def test_shobu_rate_in_registry():
    assert sz.SHOBU_RATE_SIZER in sz.SIZERS
    assert sz.get_sizer(sz.SHOBU_RATE_SIZER) is sz.size_race_shobu_rate


def test_shobu_rate_default_combo_alloc_policy():
    # Session 168 (ふくだ判断A): 本番既定 = 通常R combo フラット / 勝負R combo オッズ比例。
    assert sz.SHOBU_NORMAL_COMBO_ALLOC == "flat"
    assert sz.SHOBU_SHOBU_COMBO_ALLOC == "odds"

    # オッズ差の大きい 2 点 combo (6 vs 60) で配分方式を判別できる fixture。
    def _plans():
        combo = _plan("sanrenpuku", [[3, 7, 11], [3, 7, 12]], hit_prob=0.1, ev=1.5,
                      g=20.0, odds_legs=[6.0, 60.0])
        return [_plan("tansho", [[5]], hit_prob=0.2, ev=None, g=None, odds_legs=[8.0]), combo]

    def _sel():
        return _selection(5, 8.0, [
            _sel_plan("tansho", [[5]]),
            _sel_plan("sanrenpuku", [[3, 7, 11], [3, 7, 12]], ev=1.5, g=20.0)])

    def amt(rs, odds):
        return sum(l.amount for l in rs.legs if l.leg_odds == odds)

    # --- 通常R (gap=0 → 非勝負): 既定 combo = フラット ---
    eff_n = _shobu_eff(5, 8.0, [_shobu_strength(5, 0.2, 8.0, rank_w=1, gap=0, ev=1.0,
                                                margin=30)], _plans())
    rs_def = sz.size_race_shobu_rate(eff_n, _sel(), bankroll=10000, per_race_cap=4500)
    rs_flat = sz.size_race_shobu_rate(eff_n, _sel(), bankroll=10000, per_race_cap=4500,
                                      combo_alloc_mode="flat")
    rs_inv = sz.size_race_shobu_rate(eff_n, _sel(), bankroll=10000, per_race_cap=4500,
                                     combo_alloc_mode="inverse")
    assert amt(rs_def, 6.0) == amt(rs_flat, 6.0)       # 既定 == flat
    assert amt(rs_def, 60.0) == amt(rs_flat, 60.0)
    assert abs(amt(rs_flat, 6.0) - amt(rs_flat, 60.0)) <= 100   # flat ≒ 均等
    assert amt(rs_inv, 6.0) > amt(rs_inv, 60.0)        # inverse は低オッズ点に厚い (天井低)

    # --- 勝負R (4条件成立): 既定 combo = オッズ比例 (高オッズ点に厚い = 天井高) ---
    eff_sh = _shobu_eff(5, 8.0, [_shobu_strength(5, 0.2, 8.0, rank_w=1, gap=4, ev=1.5,
                                                 margin=40)], _plans())
    assert sz.is_shobu_race(eff_sh)
    rs_sh = sz.size_race_shobu_rate(eff_sh, _sel(), bankroll=10000, per_race_cap=4500)
    assert amt(rs_sh, 60.0) >= amt(rs_sh, 6.0)         # 勝負R 既定は高配当点に厚い

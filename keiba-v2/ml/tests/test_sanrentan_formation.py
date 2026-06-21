# -*- coding: utf-8 -*-
"""三連単フォーメーション (ml.strategies.sanrentan_formation) + サイザーの単体テスト (S171)。"""
from __future__ import annotations

import pytest

from ml.strategies import bettype_efficiency as be
from ml.strategies import sanrentan_formation as sf
from ml.strategies import bettype_sizing as sz


def _strength(umaban, composite, pred_w, win_ev, win_prob, *, rank_w=None):
    """テスト用 HorseStrength。 win_prob は正規化前提だが個別テストは比率のみ使う。"""
    return be.HorseStrength(
        umaban=umaban, horse_name=f"h{umaban}", win_prob=win_prob, odds=None,
        place_odds_min=None, pred_w=pred_w, pred_p=None, ar_deviation=None,
        z_w=None, z_p=None, z_adr=None, composite=composite, rank_w=rank_w,
        win_ev=win_ev, predicted_margin=30.0)


def _race_eff(strengths, *, axis=None, rid="2026010101010101"):
    """最小 RaceEfficiency (plans は formation では未使用)。 rank_composite を composite 降順で付与。"""
    ss = sorted(strengths, key=lambda s: s.composite, reverse=True)
    for i, s in enumerate(ss, 1):
        s.rank_composite = i
    if axis is None:
        axis = ss[0].umaban
    return be.RaceEfficiency(
        race_id=rid, date=None, venue_name=None, race_number=None, grade="",
        track_type=None, distance=None, num_runners=len(ss), axis_umaban=axis,
        axis_name="", axis_odds=None, partners=[], weights=(1, 1, 1),
        specialist=None, strengths=ss, plans=[])


def _base_strengths():
    # ◎=1 (composite最強・低勝率設定で頭から外れる) / 妙味頭=2,3 (pred_w≥0.12 & win_ev≥1) / ヒモ=4,5,6
    return [
        _strength(1, composite=2.0, pred_w=0.35, win_ev=0.7, win_prob=0.35, rank_w=1),   # ◎ EV低=頭外
        _strength(2, composite=1.0, pred_w=0.18, win_ev=1.6, win_prob=0.18, rank_w=2),   # 頭候補
        _strength(3, composite=0.5, pred_w=0.13, win_ev=1.3, win_prob=0.13, rank_w=3),   # 頭候補
        _strength(4, composite=0.2, pred_w=0.10, win_ev=0.9, win_prob=0.10, rank_w=4),   # ヒモ (頭外)
        _strength(5, composite=0.0, pred_w=0.08, win_ev=0.8, win_prob=0.08, rank_w=5),
        _strength(6, composite=-0.3, pred_w=0.06, win_ev=0.7, win_prob=0.06, rank_w=6),
    ]


# ---- 候補抽出 ----

def test_axis_is_composite_top():
    re_ = _race_eff(_base_strengths())
    assert re_.axis_umaban == 1


def test_head_excludes_axis_and_applies_floors():
    re_ = _race_eff(_base_strengths())
    head = sf.select_head(re_, axis=1, win_prob_floor=0.12, ev_floor=1.0, n_max=3)
    # 2 (ev1.6), 3 (ev1.3) のみ。 4 は pred_w0.10<0.12 かつ ev0.9<1.0 で除外。 ◎=1 は除外。
    assert head == [2, 3]


def test_head_sorted_by_ev_desc():
    re_ = _race_eff(_base_strengths())
    head = sf.select_head(re_, axis=1, win_prob_floor=0.12, ev_floor=1.0, n_max=3)
    assert head[0] == 2  # ev1.6 が先頭


def test_head_empty_when_no_value_horse():
    # 全馬 win_ev<1.0 → 頭候補なし
    ss = [_strength(u, composite=1.0 - u * 0.1, pred_w=0.2, win_ev=0.5, win_prob=0.2)
          for u in range(1, 6)]
    re_ = _race_eff(ss)
    assert sf.select_head(re_, axis=re_.axis_umaban, ev_floor=1.0) == []


def test_renjiku_is_composite_top_excl_axis():
    re_ = _race_eff(_base_strengths())
    assert sf.select_renjiku(re_, axis=1, n=2) == [2, 3]


def test_third_multi_source_union_dedup():
    re_ = _race_eff(_base_strengths())
    third = sf.select_third(re_, axis=1, anaba_umabans=[7, 3], paddock_marks={8: "S", 9: "C"},
                            n_composite=4)
    # composite上位(◎除く)=2,3,4,5 → 印4=7,3(3は重複) → パドックS=8 (9はCで除外)
    assert third[:4] == [2, 3, 4, 5]
    assert 7 in third and 8 in third
    assert 9 not in third          # mark C は拾わない
    assert 1 not in third          # ◎は除外
    assert len(third) == len(set(third))  # 重複なし


# ---- build_formation ----

def test_build_formation_axis_position():
    re_ = _race_eff(_base_strengths())
    res = sf.build_formation(re_, sanrentan_odds=None, n_third_composite=4, max_points=99)
    assert res.axis == 1
    # ◎2着流し → 2着が必ず ◎(1) / ◎3着流し → 3着が必ず ◎(1)
    for leg in res.legs:
        if leg.role == sf.ROLE_MARU_2ND:
            assert leg.horses[1] == 1
        else:
            assert leg.horses[2] == 1
        assert len(set(leg.horses)) == 3   # 3頭異なる


def test_build_formation_trim_keeps_high_ev():
    re_ = _race_eff(_base_strengths())
    # ダミーオッズ: 全点同オッズだと hv_prob 順。 1点だけ高オッズにして残るか確認
    odds = {}
    # 頭=2,3 / ◎=1 / 3着=2,3,4,5 → 代表的な組番に適当なオッズ
    odds_all = sf.build_formation(re_, sanrentan_odds=None, max_points=99)
    target = odds_all.legs[0].horses
    kb = sf._kumiban_ordered(*target)
    sanrentan_odds = {sf._kumiban_ordered(*l.horses): {"odds": 10.0} for l in odds_all.legs}
    sanrentan_odds[kb] = {"odds": 5000.0}  # この点だけ極端に高オッズ=高hvEV
    res = sf.build_formation(re_, sanrentan_odds=sanrentan_odds, max_points=1)
    assert res.n_points == 1
    assert res.legs[0].horses == target   # 高hvEV点が残る


def test_build_formation_no_head_returns_empty():
    ss = [_strength(u, composite=1.0 - u * 0.1, pred_w=0.2, win_ev=0.5, win_prob=0.2)
          for u in range(1, 6)]
    re_ = _race_eff(ss)
    # gap/win_ev ゲートを切って「頭候補なし (win_ev<floor)」の経路を単離して検証
    res = sf.build_formation(re_, sanrentan_odds=None, min_axis_gap=0.0, min_axis_win_ev=0.0)
    assert res.legs == []
    assert any("頭候補なし" in w for w in res.warnings)


def test_build_formation_axis_gap_gate():
    # ◎の格 (composite gap) が薄いレースは見送り (S171 シビア化ゲート)
    ss = [_strength(u, composite=1.0 - u * 0.1, pred_w=0.2, win_ev=2.0, win_prob=0.2)
          for u in range(1, 6)]
    re_ = _race_eff(ss)  # gap = 0.9-0.8 = 0.1
    res = sf.build_formation(re_, sanrentan_odds=None, min_axis_gap=0.4)
    assert res.legs == []
    assert any("見送り" in w and "格" in w for w in res.warnings)
    # ゲートを下げれば買える (頭は win_ev2.0 で十分)
    res2 = sf.build_formation(re_, sanrentan_odds=None, min_axis_gap=0.0)
    assert res2.legs


def test_build_formation_axis_winev_gate():
    # ◎が過剰人気 (◎win_ev < 0.6) のレースは見送り (S172 本番ゲート・デフォルト0.6)
    ss = _base_strengths()
    ss[0] = _strength(1, composite=2.0, pred_w=0.35, win_ev=0.5, win_prob=0.35, rank_w=1)  # ◎=過剰人気
    re_ = _race_eff(ss)
    res = sf.build_formation(re_, sanrentan_odds=None)  # デフォルト min_axis_win_ev=0.6
    assert res.legs == []
    assert any("過剰人気" in w for w in res.warnings)
    # ゲートを切れば買える (頭は 2 が pred_w0.18≥0.15 ∧ win_ev1.6≥1.5)
    res2 = sf.build_formation(re_, sanrentan_odds=None, min_axis_win_ev=0.0)
    assert res2.legs


def test_default_axis_winev_gate_is_production_value():
    # 本番化 (S172): モジュール既定 = 0.6 (過剰人気◎の見送り)。 bat 非依存で効く。
    assert sf.DEFAULT_MIN_AXIS_WIN_EV == 0.6


# ---- サイザー (配分) ----

def _odds_for_all_legs(re_):
    base = sf.build_formation(re_, sanrentan_odds=None, max_points=999)
    return {sf._kumiban_ordered(*l.horses): {"odds": 50.0} for l in base.legs}


def test_sizer_investment_linked_within_cap():
    re_ = _race_eff(_base_strengths())
    odds = _odds_for_all_legs(re_)
    rs = sz.size_race_sanrentan_formation(
        re_, selection=None, bankroll=10000, per_race_cap=3000,
        sanrentan_odds=odds, anaba_umabans=[], paddock_marks={})
    assert rs.legs
    assert all(l.bet_type == "sanrentan" for l in rs.legs)
    # base race は通常R (◎ win_ev<1.3) → cap=3000×5/15=1000 に縮小される。 effective cap 基準で検証。
    assert rs.per_race_cap == 1000
    assert rs.total_yen <= rs.per_race_cap          # cap 内
    assert rs.total_yen >= rs.per_race_cap - 100     # 投資額連動 = cap をほぼ使い切る
    assert all(l.amount >= 100 for l in rs.legs)
    assert rs.anchor_yen == 0


def test_sizer_normal_rate_scaledown():
    # 通常R は cap を normal/shobu に縮める (5/15)。 勝負条件を満たさない base は通常R。
    re_ = _race_eff(_base_strengths())
    odds = _odds_for_all_legs(re_)
    rs = sz.size_race_sanrentan_formation(
        re_, selection=None, bankroll=10000, per_race_cap=5200,
        sanrentan_odds=odds, anaba_umabans=[], paddock_marks={},
        normal_rate_pct=5, shobu_rate_pct=15)
    # is_shobu_race=False 想定 → cap = 5200*5/15 = 1733 → 1700
    assert rs.per_race_cap == 1700
    assert rs.total_yen <= 1700


def test_sizer_empty_when_no_formation():
    ss = [_strength(u, composite=1.0 - u * 0.1, pred_w=0.2, win_ev=0.5, win_prob=0.2)
          for u in range(1, 6)]
    re_ = _race_eff(ss)
    rs = sz.size_race_sanrentan_formation(
        re_, selection=None, bankroll=10000, per_race_cap=3000,
        sanrentan_odds={}, anaba_umabans=[], paddock_marks={})
    assert rs.legs == []


def test_sizer_flat_stake_mode():
    re_ = _race_eff(_base_strengths())
    odds = _odds_for_all_legs(re_)
    rs = sz.size_race_sanrentan_formation(
        re_, selection=None, bankroll=10000, per_race_cap=99999,
        sanrentan_odds=odds, anaba_umabans=[], paddock_marks={}, flat_stake=300)
    assert all(l.amount == 300 for l in rs.legs)


def test_sizer_registered():
    assert sz.SANRENTAN_FORMATION_SIZER in sz.SIZERS
    assert sz.get_sizer(sz.SANRENTAN_FORMATION_SIZER) is sz.size_race_sanrentan_formation

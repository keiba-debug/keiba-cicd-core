#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""券種選択ロジック (bettype_selection) のテスト — Session 139 / Phase3

検証範囲:
  - should_fund: EV 絶対水準のみで判定 (vs_tansho は無視) — シズネ制約の本体
  - select_plans: concentrate / ev_floor / spread_if_worth / hole_seeker
  - skip_all 自動フォールバック
  - find_taste_axis: popularity_gap_max の z 乖離、 ev_min は軸不変
  - evaluate_and_select: Phase2 統合 + specialist overlay 整合 + 妙味軸差し替え
  - ★シズネ制約の回帰★: vs_tansho=='gt' でも EV<floor なら concentrate/ev_floor で
    fund されないこと (合成>単=広げ得 が -EV を後押しする誤誘導を構造的に遮断)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402


# ---------------------------------------------------------------------------
# ヘルパ: Plan / RaceEfficiency を直接組む
# ---------------------------------------------------------------------------

def _plan(bet_type, label, *, ev, g=None, vs=None, hit=0.1, legs=None):
    return be.Plan(
        bet_type=bet_type, label=label, legs=legs or [[1, 2]], n_points=1,
        hit_prob=hit, sum_p=hit, synthetic_odds=g, expected_return=ev,
        odds_legs=[g], coverage=1.0, vs_tansho=vs,
    )


def _tansho_plan():
    return be.Plan(
        bet_type="tansho", label="単勝 ◎", legs=[[1]], n_points=1,
        hit_prob=0.35, sum_p=0.35, synthetic_odds=None, expected_return=None,
        odds_legs=[2.8], coverage=1.0, vs_tansho=None,
    )


def _race_eff(plans, *, axis=1, strengths=None):
    return be.RaceEfficiency(
        race_id="2026053005021101", date="2026-05-30", venue_name="東京",
        race_number=11, grade="G1", track_type="芝", distance=2400,
        num_runners=12, axis_umaban=axis, axis_name="軸馬", axis_odds=2.8,
        partners=[2, 3, 4], weights=(1.0, 1.0, 1.0), specialist=None,
        strengths=strengths or [], plans=plans, warnings=[],
    )


# ---------------------------------------------------------------------------
# should_fund — EV 絶対水準のみ (シズネ制約の本体)
# ---------------------------------------------------------------------------

class TestShouldFund:
    def test_tansho_always_funded(self):
        assert bs.should_fund(_tansho_plan()) is True

    def test_ev_above_floor_funded(self):
        assert bs.should_fund(_plan("umaren", "馬連", ev=1.20)) is True

    def test_ev_below_floor_not_funded(self):
        assert bs.should_fund(_plan("umaren", "馬連", ev=0.85)) is False

    def test_ev_exactly_floor_funded(self):
        assert bs.should_fund(_plan("umaren", "馬連", ev=1.0)) is True

    def test_ev_none_not_funded(self):
        # 市場オッズ未取得 (EV=None) は買わない (判定不能)
        assert bs.should_fund(_plan("umaren", "馬連", ev=None)) is False

    def test_vs_tansho_gt_does_not_override_low_ev(self):
        # ★シズネ制約★: vs_tansho=='gt' (合成>単) でも EV<floor なら fund しない
        p = _plan("umaren", "馬連", ev=0.80, vs="gt")
        assert bs.should_fund(p) is False

    def test_custom_floor(self):
        p = _plan("umaren", "馬連", ev=1.10)
        assert bs.should_fund(p, ev_floor=1.20) is False
        assert bs.should_fund(p, ev_floor=1.05) is True


# ---------------------------------------------------------------------------
# select_plans — 各プリセット
# ---------------------------------------------------------------------------

class TestConcentrate:
    def test_all_ev_low_keeps_only_tansho(self):
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連 ◎-相手2", ev=0.90, g=2.0, vs="lt"),
            _plan("wide", "ワイド ◎-相手2", ev=0.85, g=1.8, vs="lt"),
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="concentrate")
        funded = [s.bet_type for s in sel.selected_plans]
        assert funded == ["tansho"]
        # 複合券種なし → 「単に集中」+ 広げ得≠儲かる
        assert "単勝◎に集中" in sel.decision_reason
        assert "広げ得≠儲かる" in sel.decision_reason

    def test_high_ev_and_gt_funded(self):
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連 ◎-相手2", ev=1.30, g=4.0, vs="gt"),
            _plan("wide", "ワイド ◎-相手2", ev=0.95, g=1.5, vs="lt"),
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="concentrate")
        funded = {s.bet_type for s in sel.selected_plans}
        assert funded == {"tansho", "umaren"}
        skipped = {s.bet_type for s in sel.skipped_plans}
        assert "wide" in skipped

    def test_high_ev_but_lt_not_funded(self):
        # EV>=floor だが vs_tansho=='lt' (合成<=単) → concentrate は単に集中
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連 ◎-相手2", ev=1.10, g=2.0, vs="lt"),
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="concentrate")
        funded = {s.bet_type for s in sel.selected_plans}
        assert funded == {"tansho"}
        reason = sel.skipped_plans[0].skip_reason
        assert "相対妙味薄" in reason


class TestEvFloor:
    def test_funds_all_above_floor_regardless_of_vs_tansho(self):
        # ev_floor は vs_tansho を見ない (EV>=floor なら lt でも fund)
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連", ev=1.10, g=2.0, vs="lt"),
            _plan("wide", "ワイド", ev=0.90, g=1.8, vs="gt"),
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="ev_floor")
        funded = {s.bet_type for s in sel.selected_plans}
        assert funded == {"tansho", "umaren"}

    def test_vs_tansho_gt_low_ev_still_skipped(self):
        # ★シズネ制約回帰★: ev_floor でも合成>単(gt)だけでは fund しない
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連", ev=0.70, g=5.0, vs="gt"),  # 合成>単だが EV<1
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="ev_floor")
        funded = {s.bet_type for s in sel.selected_plans}
        assert funded == {"tansho"}
        assert sel.skipped_plans[0].bet_type == "umaren"


class TestSpreadIfWorth:
    def test_keeps_low_ev_gt_with_warning(self):
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連", ev=0.80, g=5.0, vs="gt"),
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="spread_if_worth")
        funded = {s.bet_type for s in sel.selected_plans}
        assert funded == {"tansho", "umaren"}
        # 残置するが「広げ得≠儲かる / 期待値マイナス寄り」を select_reason に明示
        umaren = next(s for s in sel.selected_plans if s.bet_type == "umaren")
        assert "広げ得≠儲かる" in umaren.select_reason

    def test_drops_low_ev_lt(self):
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連", ev=0.80, g=1.5, vs="lt"),
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="spread_if_worth")
        funded = {s.bet_type for s in sel.selected_plans}
        assert funded == {"tansho"}


class TestSkipAll:
    def test_empty_plans_falls_back_to_skip_all(self):
        sel = bs.select_plans(_race_eff([]), strategy="concentrate")
        assert sel.strategy == "skip_all"
        assert sel.selected_plans == []
        assert "全見送り" in sel.decision_reason


# ---------------------------------------------------------------------------
# find_taste_axis — 妙味軸オプション
# ---------------------------------------------------------------------------

def _strength(umaban, win_prob, odds, composite=0.0):
    return be.HorseStrength(
        umaban=umaban, horse_name=f"H{umaban}", win_prob=win_prob,
        odds=odds, place_odds_min=None, pred_w=win_prob, pred_p=None,
        ar_deviation=None, z_w=None, z_p=None, z_adr=None, composite=composite,
    )


class TestFindTasteAxis:
    def test_popularity_gap_max_picks_underrated(self):
        # 馬2: 予想は中位だがオッズ高 (人気薄) = 過小評価 → gap 最大になりやすい
        strengths = [
            _strength(1, 0.40, 2.0),    # 強くて人気 (gap 小)
            _strength(2, 0.30, 30.0),   # 予想2位だが大穴オッズ → 過小評価
            _strength(3, 0.20, 6.0),
            _strength(4, 0.10, 12.0),
        ]
        re_ = _race_eff([_tansho_plan()], strengths=strengths)
        axis = bs.find_taste_axis(re_, "popularity_gap_max")
        assert axis == 2

    def test_ev_min_keeps_axis(self):
        strengths = [_strength(1, 0.4, 2.0), _strength(2, 0.3, 4.0)]
        re_ = _race_eff([_tansho_plan()], axis=1, strengths=strengths)
        assert bs.find_taste_axis(re_, "ev_min") == 1

    def test_no_strengths_returns_none(self):
        re_ = _race_eff([_tansho_plan()], strengths=[])
        assert bs.find_taste_axis(re_, "popularity_gap_max") is None

    def test_popularity_gap_max_ignores_extreme_longshot(self):
        # 旧バグ回帰 (Session 140): z(odds) 爆発で win_prob≈0 の極端人気薄 (438倍, model
        # 最下位) を軸に選んでいた。 軸の win_prob≈0 はハーヴィルを壊すので絶対に選ばせない。
        # → model 支持 + 1/n フロアで弾き、 過小評価された contender (#2) を選ぶ。
        strengths = [
            _strength(1, 0.40, 2.0),     # 本命 (model1位・最人気)
            _strength(2, 0.30, 30.0),    # model2位だが人気薄 = 過小評価 (狙い)
            _strength(3, 0.20, 6.0),
            _strength(4, 0.001, 438.0),  # winp≈0 の大穴 (旧実装の誤選択先)
        ]
        re_ = _race_eff([_tansho_plan()], strengths=strengths)
        assert bs.find_taste_axis(re_, "popularity_gap_max") == 2

    def test_popularity_gap_max_none_when_favorite_is_most_popular(self):
        # model 最評価馬が最人気でもある (= 過小評価された contender なし) → 軸据え置き (None)。
        strengths = [
            _strength(1, 0.50, 1.5),     # model1位 かつ 最人気
            _strength(2, 0.20, 4.0),     # model2位 かつ 2番人気 (gap=0)
            _strength(3, 0.15, 6.0),
        ]
        re_ = _race_eff([_tansho_plan()], strengths=strengths)
        assert bs.find_taste_axis(re_, "popularity_gap_max") is None

    def test_popularity_gap_max_tie_cluster_uses_composite(self):
        # 同点団子バグ回帰 (Session 141 / 5/31 京都12R ⑯=77倍・京都8R ⑥=60倍 をライブ投票):
        # win_prob は団子で同値が多発し、 同値を馬番で割った win_rank の上位に composite 中位の
        # longshot が紛れ込み軸に選ばれていた。 → model 順位は composite (AI印◎の基準) で測る。
        # 下記 #5 は win_prob 2位 (旧 win_rank では top-third) だが composite 最下位の longshot。
        # 旧実装は gap 最大の #5 (50倍) を軸にした。 新実装は composite で #5 を弾き、
        # 過小評価の #2 (composite2位・人気薄) を選ぶ。
        strengths = [
            _strength(1, 0.30, 2.0, composite=3.0),     # 本命 (composite1位・最人気)
            _strength(2, 0.20, 12.0, composite=2.0),    # composite2位だが人気薄 = 過小評価 (狙い)
            _strength(3, 0.15, 5.0, composite=1.0),
            _strength(4, 0.07, 8.0, composite=0.0),
            _strength(5, 0.25, 50.0, composite=-1.0),   # win_prob2位だが composite 最下位の longshot
            _strength(6, 0.03, 20.0, composite=-0.5),
        ]
        re_ = _race_eff([_tansho_plan()], strengths=strengths)
        axis = bs.find_taste_axis(re_, "popularity_gap_max")
        assert axis == 2          # composite で #5(longshot) を弾き、 過小評価 #2 を選ぶ
        assert axis != 5          # 旧実装の誤選択先 (composite 最下位の 50倍) は選ばない

    def test_popularity_gap_max_excludes_boundary_longshot(self):
        # top-3 締めの回帰 (6/6 venue2 R6 ⑦=120倍/composite rank5 をライブ前に GATE1 で発見):
        # composite top-third(ceil(n/3)) は大頭数で境界が緩く、 境界の平均馬が極端オッズで
        # gap 最大になり軸に拾われた。 → composite top-3 に締める。
        # n=12 (旧 support_cut=4, 新=3)。 #9 は composite rank4・90倍の境界 longshot で、
        # 勝率 floor(1/12) は通る (0.10>=0.083) が top-3 で弾く。 → top-3 の過小評価 #2 を選ぶ。
        strengths = [
            _strength(1, 0.30, 2.0, composite=2.5),    # 本命 (comp1・最人気)
            _strength(2, 0.15, 15.0, composite=1.8),   # comp2 だが人気薄 = 過小評価 (狙い)
            _strength(3, 0.13, 6.0, composite=1.2),    # comp3
            _strength(9, 0.10, 90.0, composite=0.4),   # comp4・90倍の境界 longshot (旧誤選択先)
            _strength(4, 0.08, 10.0, composite=0.2),
            _strength(5, 0.06, 12.0, composite=0.0),
            _strength(6, 0.05, 18.0, composite=-0.1),
            _strength(7, 0.04, 25.0, composite=-0.2),
            _strength(8, 0.03, 30.0, composite=-0.3),
            _strength(10, 0.02, 40.0, composite=-0.5),
            _strength(11, 0.02, 50.0, composite=-0.7),
            _strength(12, 0.02, 60.0, composite=-0.9),
        ]
        re_ = _race_eff([_tansho_plan()], strengths=strengths)
        axis = bs.find_taste_axis(re_, "popularity_gap_max")
        assert axis == 2          # top-3 の過小評価馬を選ぶ
        assert axis != 9          # composite rank4 の境界 longshot (90倍) は弾く


class TestHoleSeeker:
    def test_ev_min_sorts_by_synthetic_odds(self):
        plans = [
            _tansho_plan(),
            _plan("umaren", "馬連", ev=1.10, g=3.0, vs="gt"),
            _plan("sanrenpuku", "三連複", ev=1.05, g=20.0, vs="gt"),
        ]
        sel = bs.select_plans(_race_eff(plans), strategy="hole_seeker",
                              taste="ev_min")
        # 単勝以外で合成オッズ降順 → 三連複 (20) が馬連 (3) より前
        combo = [s for s in sel.selected_plans if s.bet_type != "tansho"]
        assert combo[0].bet_type == "sanrenpuku"
        assert sel.taste == "ev_min"

    def test_invalid_taste_raises(self):
        with pytest.raises(ValueError):
            bs.select_plans(_race_eff([_tansho_plan()]), strategy="hole_seeker",
                            taste="nonexistent")


# ---------------------------------------------------------------------------
# evaluate_and_select — Phase2 統合
# ---------------------------------------------------------------------------

def _pred_race(**over):
    race = {
        "race_id": "2026053005021101",
        "date": "2026-05-30",
        "venue_name": "東京",
        "race_number": 11,
        "grade": "G1",
        "num_runners": 8,
        "entries": [
            {"umaban": 1, "horse_name": "A", "pred_proba_w_cal": 0.40,
             "pred_proba_p": 0.70, "ar_deviation": 2.0, "odds": 2.5},
            {"umaban": 2, "horse_name": "B", "pred_proba_w_cal": 0.20,
             "pred_proba_p": 0.55, "ar_deviation": 1.0, "odds": 5.0},
            {"umaban": 3, "horse_name": "C", "pred_proba_w_cal": 0.15,
             "pred_proba_p": 0.45, "ar_deviation": 0.5, "odds": 8.0},
            {"umaban": 4, "horse_name": "D", "pred_proba_w_cal": 0.12,
             "pred_proba_p": 0.30, "ar_deviation": -0.5, "odds": 12.0},
            {"umaban": 5, "horse_name": "E", "pred_proba_w_cal": 0.08,
             "pred_proba_p": 0.25, "ar_deviation": -1.0, "odds": 20.0},
            {"umaban": 6, "horse_name": "F", "pred_proba_w_cal": 0.03,
             "pred_proba_p": 0.15, "ar_deviation": -1.5, "odds": 40.0},
            {"umaban": 7, "horse_name": "G", "pred_proba_w_cal": 0.01,
             "pred_proba_p": 0.10, "ar_deviation": -2.0, "odds": 80.0},
            {"umaban": 8, "horse_name": "H", "pred_proba_w_cal": 0.01,
             "pred_proba_p": 0.05, "ar_deviation": -2.5, "odds": 100.0},
        ],
    }
    race.update(over)
    return race

class TestEvaluateAndSelect:
    @pytest.fixture(autouse=True)
    def _hermetic_odds(self, monkeypatch):
        # ★DB分離★ evaluate_and_select は be.process_race 経由で mykeibadb の複合券種
        # オッズを引く。 テスト用 race_id が実在レース (5/30 OOS 等) と衝突すると実オッズで
        # 非決定的になるため、 空オッズ (市場オッズ未取得相当) に固定する。 複合券種オッズを
        # 使う検証は test_bettype_efficiency 側 (evaluate_race 直叩き) が担う。
        monkeypatch.setattr(be, "_load_combo_odds", lambda race_id: {})

    def test_axis_is_strongest_by_default(self):
        sel = bs.evaluate_and_select(_pred_race(), strategy="concentrate")
        assert sel is not None
        assert sel.axis_umaban == 1     # composite 最強
        # 単勝は必ず fund される
        assert any(s.bet_type == "tansho" for s in sel.selected_plans)

    def test_no_market_odds_yields_only_base_types(self):
        # DB 未接続 (combo_odds 空) → 複合券種 EV=None → concentrate は基準券種 (単/複) のみ
        sel = bs.evaluate_and_select(_pred_race(), strategy="concentrate")
        funded = {s.bet_type for s in sel.selected_plans}
        assert funded <= {"tansho", "fukusho"}      # 複合券種は出ない
        assert "tansho" in funded
        # 複合券種は全て skip
        assert all(s.bet_type in ("tansho", "fukusho") for s in sel.selected_plans)

    def test_hole_seeker_swaps_axis(self):
        # 大穴 (馬5: 予想中位・オッズ高) を仕込み、 popularity_gap_max で軸が動くか
        race = _pred_race()
        # 馬3 を「予想は2-3番手だがオッズ高」に強調
        race["entries"][2]["pred_proba_w_cal"] = 0.22
        race["entries"][2]["odds"] = 25.0
        sel = bs.evaluate_and_select(race, strategy="hole_seeker",
                                     taste="popularity_gap_max")
        assert sel is not None
        assert sel.taste == "popularity_gap_max"
        # 軸が composite 最強 (1) 以外に動く可能性 (過小評価馬)
        # 少なくとも単勝は fund され、 taste が記録される
        assert any(s.bet_type == "tansho" for s in sel.selected_plans)

    def test_specialist_overlay_recorded(self):
        race = _pred_race()
        race["niigata1000_applied"] = True
        for e in race["entries"]:
            e["niigata1000"] = {"display_score": 100 - e["umaban"] * 5}
        sel = bs.evaluate_and_select(race, strategy="concentrate")
        assert sel is not None
        assert sel.specialist == "niigata1000"


# ---------------------------------------------------------------------------
# artifact 出力 — selective_loader 互換
# ---------------------------------------------------------------------------

class TestArtifactCompat:
    def test_bets_have_required_loader_fields(self):
        plans = [_tansho_plan(),
                 _plan("umaren", "馬連 ◎-相手2", ev=1.30, g=4.0, vs="gt",
                       legs=[[1, 2]])]
        sel = bs.select_plans(_race_eff(plans), strategy="concentrate")
        bets = bs._selection_to_bets(sel)
        assert len(bets) >= 1
        for b in bets:
            assert b["source"] == bs.SOURCE
            assert len(str(b["race_id"])) == 16
            assert 1 <= b["umaban"] <= 18
            # ★selective_loader 必須フィールド (これが欠けると load で SchemaError)★
            assert isinstance(b["horse_name"], str) and b["horse_name"].strip()
            assert isinstance(b["odds"], float) and b["odds"] > 0
            # amount は付けない (候補段階)
            assert "amount" not in b

    def test_no_bets_when_axis_odds_missing(self):
        # 軸の単勝オッズ未確定 → bets[] には出さない (odds>0 検証に通らないため)
        plans = [_tansho_plan()]
        re_ = _race_eff(plans)
        re_.axis_odds = None
        sel = bs.select_plans(re_, strategy="concentrate")
        assert bs._selection_to_bets(sel) == []

    def test_artifact_round_trips_through_selective_loader(self, tmp_path):
        # ★実 artifact が selective_loader で実際に読めること★ (必須フィールド漏れの回帰)
        from ml.target_clicker import selective_loader as sl
        plans = [_tansho_plan(),
                 _plan("umaren", "馬連 ◎-相手2", ev=1.30, g=4.0, vs="gt",
                       legs=[[1, 2]])]
        sel = bs.select_plans(_race_eff(plans), strategy="concentrate")
        out = bs.write_selection(tmp_path, [sel], strategy="concentrate",
                                 ev_floor=1.0, taste=None)
        res = sl.load_selective_bets(out, require_funded=False)
        assert len(res.bets) >= 1
        for b in res.bets:
            assert b.source == bs.SOURCE and b.horse_name and b.odds > 0
        # 候補段階 (amount 無し) は vote-mode で弾かれる = -EV 誤投票を構造的に防ぐ
        with pytest.raises(sl.SchemaError):
            sl.load_selective_bets(out, require_funded=True)

    def test_source_in_allowed_sources(self):
        # selective_loader が bettype_selection を許可しているか
        from ml.target_clicker import selective_loader as sl
        assert bs.SOURCE in sl.ALLOWED_SOURCES


# ---------------------------------------------------------------------------
# ★シズネ制約の総合回帰★ — -EV を vs_tansho 経由で fund する抜け道が無いこと
# ---------------------------------------------------------------------------

class TestShizuneConstraintRegression:
    def test_no_negative_ev_funded_in_concentrate(self):
        # 全複合券種が「合成>単 (gt)」だが EV<1.0。 concentrate は単のみのはず。
        plans = [_tansho_plan()]
        for bt in ("umaren", "wide", "umatan", "sanrenpuku", "sanrentan"):
            plans.append(_plan(bt, bt, ev=0.75, g=10.0, vs="gt"))
        sel = bs.select_plans(_race_eff(plans), strategy="concentrate")
        for s in sel.selected_plans:
            if s.bet_type != "tansho":
                assert s.expected_return is not None and s.expected_return >= 1.0, \
                    f"{s.bet_type} は EV<1.0 なのに fund された (誤誘導)"

    def test_no_negative_ev_funded_in_ev_floor(self):
        plans = [_tansho_plan()]
        for bt in ("umaren", "wide", "sanrenpuku"):
            plans.append(_plan(bt, bt, ev=0.60, g=15.0, vs="gt"))
        sel = bs.select_plans(_race_eff(plans), strategy="ev_floor")
        for s in sel.selected_plans:
            if s.bet_type != "tansho":
                assert s.expected_return >= 1.0

    def test_decision_reason_always_carries_caveat(self):
        # どのプリセット・どの結果でも decision_reason に「広げ得≠儲かる」が必ず入る
        for strat in ("concentrate", "ev_floor", "spread_if_worth"):
            plans = [_tansho_plan(), _plan("umaren", "馬連", ev=1.30, g=4.0, vs="gt")]
            sel = bs.select_plans(_race_eff(plans), strategy=strat)
            assert "広げ得≠儲かる" in sel.decision_reason


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

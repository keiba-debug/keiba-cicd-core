#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bet_engine.py ユニットテスト

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_bet_engine.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from ml.bet_engine import (
    BetStrategyParams,
    BetRecommendation,
    PRESETS,
    evaluate_win,
    evaluate_place,
    calc_kelly_fraction,
    detect_danger,
    generate_recommendations,
    apply_single_win_constraint,
    apply_budget,
    round_to_unit,
    recommendations_to_dict,
    recommendations_summary,
    rescale_budget,
)


# =====================================================================
# evaluate_win
# =====================================================================

class TestEvaluateWin:
    """単勝評価テスト"""

    def test_pass_standard(self):
        """gap=7, margin=0.8 → standard (gap>=6) で通過"""
        params = PRESETS['standard']
        ok, units = evaluate_win(7, 0.8, params)
        assert ok is True
        assert units >= 1

    def test_pass_wide(self):
        """gap=5, margin=0.8 → wide (gap>=5) で通過"""
        params = PRESETS['wide']
        ok, units = evaluate_win(5, 0.8, params)
        assert ok is True
        assert units >= 1

    def test_fail_gap_too_small_standard(self):
        """gap=5 < win_min_gap=6 → standard で不通過"""
        params = PRESETS['standard']
        ok, units = evaluate_win(5, 0.5, params)
        assert ok is False
        assert units == 0

    def test_fail_gap_too_small_wide(self):
        """gap=4 < win_min_gap=5 → wide で不通過"""
        params = PRESETS['wide']
        ok, units = evaluate_win(4, 0.5, params)
        assert ok is False
        assert units == 0

    def test_fail_margin_too_large(self):
        """gap=6 but margin=2.0 > 1.2 → 不通過"""
        params = PRESETS['standard']
        ok, units = evaluate_win(6, 2.0, params)
        assert ok is False
        assert units == 0

    def test_margin_none_passes(self):
        """margin=None → margin フィルタ skip"""
        params = PRESETS['wide']
        ok, units = evaluate_win(5, None, params)
        assert ok is True

    def test_danger_raises_threshold(self):
        """danger → min_gap +2 → standard (gap=6) requires gap>=8"""
        params = PRESETS['standard']  # win_min_gap=6
        ok, _ = evaluate_win(7, 0.5, params, is_danger=True)
        assert ok is False  # 6+2=8 > 7

        ok, _ = evaluate_win(8, 0.5, params, is_danger=True)
        assert ok is True

    def test_units_proportional_to_gap(self):
        """gap が大きいほど units が増える"""
        params = PRESETS['wide']  # win_min_gap=5
        _, u1 = evaluate_win(5, 0.5, params)
        _, u2 = evaluate_win(6, 0.5, params)
        _, u3 = evaluate_win(8, 0.5, params)
        assert u1 == 1
        assert u2 == 2
        assert u3 == 3

    def test_standard_stricter_than_wide(self):
        """standard (gap>=6) は wide (gap>=5) より厳しい"""
        params_std = PRESETS['standard']
        params_wide = PRESETS['wide']
        # gap=5 → wide OK, standard NG
        ok_wide, _ = evaluate_win(5, 0.8, params_wide)
        ok_std, _ = evaluate_win(5, 0.8, params_std)
        assert ok_wide is True
        assert ok_std is False


# =====================================================================
# evaluate_place (カスタムパラメータでロジックテスト)
# =====================================================================

class TestEvaluatePlace:
    """複勝評価テスト（全プリセットでPlace無効化のためカスタムparamsでテスト）"""

    PLACE_PARAMS = BetStrategyParams(
        win_min_gap=5,
        place_min_gap=3,
        place_max_margin=1.0,
        place_min_ev=1.0,
    )

    def test_pass_with_ev(self):
        """gap=4, margin=0.5, EV=1.2 → 通過"""
        ok, kelly = evaluate_place(4, 0.5, 0.4, 3.0, self.PLACE_PARAMS)
        assert ok is True
        assert kelly > 0

    def test_fail_gap_too_small(self):
        """gap=2 < place_min_gap=3 → 不通過"""
        ok, kelly = evaluate_place(2, 0.5, 0.4, 3.0, self.PLACE_PARAMS)
        assert ok is False

    def test_fail_margin_too_large(self):
        """margin=2.0 > 1.0 → 不通過"""
        ok, _ = evaluate_place(4, 2.0, 0.4, 3.0, self.PLACE_PARAMS)
        assert ok is False

    def test_fail_ev_too_low(self):
        """EV=0.8 < 1.0 → 不通過"""
        # p_top3=0.2, odds=4.0 → EV=0.8
        ok, _ = evaluate_place(4, 0.5, 0.2, 4.0, self.PLACE_PARAMS)
        assert ok is False

    def test_margin_none_passes(self):
        """margin=None → margin フィルタ skip"""
        ok, kelly = evaluate_place(4, None, 0.5, 3.0, self.PLACE_PARAMS)
        assert ok is True

    def test_no_odds_fallback(self):
        """オッズ不明 → gap のみで判定、固定サイズ"""
        ok, kelly = evaluate_place(4, 0.5, None, None, self.PLACE_PARAMS)
        assert ok is True
        assert kelly == pytest.approx(0.02)

    def test_danger_raises_threshold(self):
        """danger → min_gap +2"""
        ok, _ = evaluate_place(4, 0.5, 0.5, 3.0, self.PLACE_PARAMS, is_danger=True)
        assert ok is False  # 3+2=5 > 4

    def test_kelly_capped(self):
        """Kelly が kelly_cap を超えない"""
        ok, kelly = evaluate_place(5, 0.3, 0.8, 5.0, self.PLACE_PARAMS)
        assert ok is True
        assert kelly <= self.PLACE_PARAMS.kelly_cap

    def test_presets_disable_place(self):
        """全プリセットでPlace無効化されていることを確認"""
        for name, params in PRESETS.items():
            ok, _ = evaluate_place(10, 0.1, 0.9, 5.0, params)
            assert ok is False, f"preset {name} should disable place"


# =====================================================================
# calc_kelly_fraction
# =====================================================================

class TestCalcKellyFraction:
    """Kelly Criterion テスト"""

    def test_positive_edge(self):
        """p=0.5, odds=3.0 → positive"""
        f = calc_kelly_fraction(0.5, 3.0)
        # f = (2*0.5 - 0.5) / 2 = 0.25
        assert f == pytest.approx(0.25)

    def test_negative_edge(self):
        """p=0.1, odds=2.0 → negative → 0"""
        f = calc_kelly_fraction(0.1, 2.0)
        assert f == 0.0

    def test_fair_bet(self):
        """p=0.5, odds=2.0 → f=0"""
        f = calc_kelly_fraction(0.5, 2.0)
        assert f == pytest.approx(0.0)

    def test_zero_odds(self):
        """odds=0 → 0"""
        f = calc_kelly_fraction(0.5, 0.0)
        assert f == 0.0

    def test_zero_prob(self):
        """prob=0 → 0"""
        f = calc_kelly_fraction(0.0, 5.0)
        assert f == 0.0


# =====================================================================
# detect_danger
# =====================================================================

class TestDetectDanger:
    """危険馬検出テスト"""

    def test_no_danger(self):
        entries = [
            {'umaban': 1, 'comment_memo_trouble_score': 0},
            {'umaban': 2, 'comment_memo_trouble_score': 3},
        ]
        d = detect_danger(entries, threshold=5.0)
        assert d == {}

    def test_danger_detected(self):
        entries = [
            {'umaban': 1, 'comment_memo_trouble_score': 6},
            {'umaban': 2, 'comment_memo_trouble_score': 3},
            {'umaban': 3, 'comment_memo_trouble_score': 8},
        ]
        d = detect_danger(entries, threshold=5.0)
        assert d == {1: 6, 3: 8}

    def test_missing_field(self):
        entries = [{'umaban': 1}]
        d = detect_danger(entries, threshold=5.0)
        assert d == {}


# =====================================================================
# apply_single_win_constraint
# =====================================================================

class TestSingleWinConstraint:
    """1レース1単勝制約テスト"""

    def _make_rec(self, umaban, bet_type, win_gap, odds=10.0, kelly=0.03):
        return BetRecommendation(
            race_id='test', umaban=umaban, horse_name=f'Horse{umaban}',
            bet_type=bet_type, strength='normal',
            win_amount=100 if bet_type in ('単勝', '単複') else 0,
            place_amount=100 if bet_type in ('複勝', '単複') else 0,
            win_gap=win_gap, gap=win_gap, odds=odds,
            kelly_capped=kelly,
        )

    def test_single_win_no_change(self):
        """単勝1件のみ → 変更なし"""
        recs = [self._make_rec(1, '単勝', 5), self._make_rec(2, '複勝', 3)]
        result = apply_single_win_constraint(recs)
        assert len(result) == 2
        assert result[0].bet_type == '単勝'
        assert result[1].bet_type == '複勝'

    def test_two_wins_downgrade_second(self):
        """単勝2件 → 2番手を複勝に降格"""
        recs = [self._make_rec(1, '単勝', 5), self._make_rec(2, '単勝', 3)]
        result = apply_single_win_constraint(recs)
        # umaban=1 (gap=5) keeps 単勝, umaban=2 (gap=3) downgraded to 複勝
        wins = [r for r in result if r.bet_type == '単勝']
        assert len(wins) == 1
        assert wins[0].umaban == 1

    def test_tanpuku_downgrade(self):
        """単複2件 → 2番手を複勝に降格"""
        recs = [self._make_rec(1, '単複', 6), self._make_rec(2, '単複', 4)]
        result = apply_single_win_constraint(recs)
        # umaban=2 should be downgraded from 単複 to 複勝
        r2 = [r for r in result if r.umaban == 2][0]
        assert r2.bet_type == '複勝'
        assert r2.win_amount == 0


# =====================================================================
# apply_budget
# =====================================================================

class TestApplyBudget:
    """予算スケーリングテスト"""

    def test_under_budget(self):
        """予算内 → そのまま"""
        params = PRESETS['standard']
        recs = [
            BetRecommendation(
                race_id='r1', umaban=1, horse_name='A',
                bet_type='複勝', strength='normal',
                win_amount=0, place_amount=0,
                kelly_capped=0.03,
            ),
        ]
        result = apply_budget(recs, 30000, params)
        assert result[0].place_amount > 0
        assert result[0].place_amount <= 30000

    def test_over_budget_scales_down(self):
        """予算超過 → 按分"""
        params = PRESETS['standard']
        recs = []
        for i in range(20):
            recs.append(BetRecommendation(
                race_id=f'r{i}', umaban=1, horse_name=f'H{i}',
                bet_type='単複', strength='normal',
                win_amount=300, place_amount=0,
                kelly_capped=0.05,
            ))
        result = apply_budget(recs, 5000, params)
        total = sum(r.win_amount + r.place_amount for r in result)
        assert total <= 5000 + 100 * len(recs)  # rounding tolerance

    def test_empty_recs(self):
        """空リスト → 空"""
        params = PRESETS['standard']
        result = apply_budget([], 30000, params)
        assert result == []


# =====================================================================
# round_to_unit
# =====================================================================

class TestRoundToUnit:
    def test_exact(self):
        assert round_to_unit(500, 100) == 500

    def test_round_down(self):
        assert round_to_unit(550, 100) == 500

    def test_small(self):
        assert round_to_unit(50, 100) == 0


# =====================================================================
# generate_recommendations (統合テスト)
# =====================================================================

class TestGenerateRecommendations:
    """パイプライン統合テスト"""

    @pytest.fixture
    def sample_race(self):
        """テスト用レースデータ"""
        return {
            'race_id': '2026022206010101',
            'track_type': '芝',
            'entries': [
                {
                    'umaban': 1, 'horse_name': 'Horse1',
                    'odds': 15.0, 'vb_gap': 6, 'win_vb_gap': 7,
                    'rank_v': 1, 'odds_rank': 7,
                    'place_odds_min': 3.5,
                    'pred_proba_v_raw': 0.45,
                    'predicted_margin': 0.3,
                    'win_ev': 1.5, 'place_ev': 1.6,
                    'comment_memo_trouble_score': 0,
                },
                {
                    'umaban': 3, 'horse_name': 'Horse3',
                    'odds': 8.0, 'vb_gap': 4, 'win_vb_gap': 6,
                    'rank_v': 2, 'odds_rank': 6,
                    'place_odds_min': 2.5,
                    'pred_proba_v_raw': 0.40,
                    'predicted_margin': 0.7,
                    'win_ev': 1.1, 'place_ev': 1.0,
                    'comment_memo_trouble_score': 0,
                },
                {
                    'umaban': 5, 'horse_name': 'Horse5',
                    'odds': 3.0, 'vb_gap': 0, 'win_vb_gap': 0,
                    'rank_v': 3, 'odds_rank': 3,
                    'place_odds_min': 1.5,
                    'pred_proba_v_raw': 0.35,
                    'predicted_margin': 1.5,
                    'win_ev': 0.5, 'place_ev': 0.5,
                    'comment_memo_trouble_score': 0,
                },
                {
                    'umaban': 7, 'horse_name': 'Horse7',
                    'odds': 50.0, 'vb_gap': 1, 'win_vb_gap': 1,
                    'rank_v': 5, 'odds_rank': 6,
                    'place_odds_min': 8.0,
                    'pred_proba_v_raw': 0.10,
                    'predicted_margin': 3.0,
                    'win_ev': 0.2, 'place_ev': 0.8,
                    'comment_memo_trouble_score': 0,
                },
            ],
        }

    def test_standard_preset(self, sample_race):
        """standard プリセット (gap>=6) での推奨生成"""
        params = PRESETS['standard']
        recs = generate_recommendations([sample_race], params, budget=30000)

        assert len(recs) > 0

        # Horse1 (win_gap=7 >= 6, margin=0.3) → 単勝候補
        h1 = [r for r in recs if r.umaban == 1]
        assert len(h1) == 1
        assert h1[0].bet_type == '単勝'

        # Horse5 (gap=0) → VB対象外
        h5 = [r for r in recs if r.umaban == 5]
        assert len(h5) == 0

        # Horse7 (rank_v=5 > 3) → 対象外
        h7 = [r for r in recs if r.umaban == 7]
        assert len(h7) == 0

    def test_wide_more_bets_than_standard(self, sample_race):
        """wide (gap>=5) → standard (gap>=6) より多い推奨"""
        params_std = PRESETS['standard']
        params_wide = PRESETS['wide']
        recs_std = generate_recommendations([sample_race], params_std, budget=30000)
        recs_wide = generate_recommendations([sample_race], params_wide, budget=30000)
        assert len(recs_wide) >= len(recs_std)

    def test_single_win_constraint_applied(self):
        """2馬が単勝候補 → 1馬だけ残る"""
        race = {
            'race_id': 'test_race',
            'track_type': '芝',
            'entries': [
                {
                    'umaban': 1, 'horse_name': 'A',
                    'odds': 20.0, 'vb_gap': 6, 'win_vb_gap': 8,
                    'rank_v': 1, 'odds_rank': 7,
                    'place_odds_min': 4.0,
                    'pred_proba_v_raw': 0.5,
                    'predicted_margin': 0.3,
                    'win_ev': 2.0, 'place_ev': 2.0,
                    'comment_memo_trouble_score': 0,
                },
                {
                    'umaban': 2, 'horse_name': 'B',
                    'odds': 15.0, 'vb_gap': 5, 'win_vb_gap': 7,
                    'rank_v': 2, 'odds_rank': 7,
                    'place_odds_min': 3.5,
                    'pred_proba_v_raw': 0.45,
                    'predicted_margin': 0.5,
                    'win_ev': 1.5, 'place_ev': 1.6,
                    'comment_memo_trouble_score': 0,
                },
            ],
        }
        params = PRESETS['standard']
        recs = generate_recommendations([race], params, budget=30000)

        win_bets = [r for r in recs if r.bet_type in ('単勝', '単複')]
        assert len(win_bets) <= 1

    def test_empty_race(self):
        """空レース → 空推奨"""
        race = {'race_id': 'empty', 'track_type': '芝', 'entries': []}
        recs = generate_recommendations([race], PRESETS['standard'])
        assert recs == []

    def test_danger_suppresses_bet(self):
        """danger 馬は gap 閾値が上がる"""
        race = {
            'race_id': 'danger_test',
            'track_type': '芝',
            'entries': [
                {
                    'umaban': 1, 'horse_name': 'DangerHorse',
                    'odds': 10.0, 'vb_gap': 4, 'win_vb_gap': 6,
                    'rank_v': 1, 'odds_rank': 5,
                    'place_odds_min': 2.5,
                    'pred_proba_v_raw': 0.4,
                    'predicted_margin': 0.5,
                    'win_ev': 1.0, 'place_ev': 1.0,
                    'comment_memo_trouble_score': 7,  # danger
                },
            ],
        }
        params = PRESETS['standard']  # win_min_gap=6
        recs = generate_recommendations([race], params, budget=30000)

        # win_gap=6 < win_min_gap(6)+danger_boost(2)=8 → 単勝不可
        # place_min_gap=99 → 複勝も不可
        assert len(recs) == 0

    def test_win_only_no_place_bets(self, sample_race):
        """全プリセットがWin-only: 複勝推奨が出ないことを確認"""
        for name, params in PRESETS.items():
            recs = generate_recommendations([sample_race], params, budget=30000)
            for r in recs:
                assert r.bet_type == '単勝', \
                    f"preset {name}: unexpected bet_type {r.bet_type} for umaban {r.umaban}"


# =====================================================================
# recommendations_summary
# =====================================================================

class TestRecommendationsSummary:

    def test_empty(self):
        s = recommendations_summary([])
        assert s['total_bets'] == 0
        assert s['total_amount'] == 0

    def test_basic(self):
        recs = [
            BetRecommendation(
                race_id='r1', umaban=1, horse_name='A',
                bet_type='単複', strength='strong',
                win_amount=200, place_amount=500,
            ),
            BetRecommendation(
                race_id='r2', umaban=3, horse_name='B',
                bet_type='複勝', strength='normal',
                win_amount=0, place_amount=300,
                is_danger=True,
            ),
        ]
        s = recommendations_summary(recs)
        assert s['total_bets'] == 2
        assert s['total_amount'] == 1000
        assert s['win_bets'] == 1
        assert s['place_bets'] == 2  # 単複 + 複勝
        assert s['strong_count'] == 1
        assert s['danger_count'] == 1


# =====================================================================
# rescale_budget
# =====================================================================

class TestRescaleBudget:

    def test_double_budget(self):
        recs = [
            {'win_amount': 200, 'place_amount': 300},
            {'win_amount': 100, 'place_amount': 400},
        ]
        # total = 1000, new_budget = 2000 → scale 2x
        result = rescale_budget(recs, 2000)
        total = sum(r['win_amount'] + r['place_amount'] for r in result)
        # Due to rounding, might not be exactly 2000
        assert total <= 2200  # allow some rounding
        assert total >= 1800

    def test_empty(self):
        result = rescale_budget([], 5000)
        assert result == []


# =====================================================================
# recommendations_to_dict
# =====================================================================

class TestRecommendationsToDict:

    def test_serializable(self):
        import json
        recs = [
            BetRecommendation(
                race_id='r1', umaban=1, horse_name='A',
                bet_type='単勝', strength='strong',
                win_amount=200,
            ),
        ]
        dicts = recommendations_to_dict(recs)
        # Should be JSON serializable
        json_str = json.dumps(dicts, ensure_ascii=False)
        assert 'race_id' in json_str
        assert '単勝' in json_str


# =====================================================================
# PRESETS 整合性
# =====================================================================

class TestPresets:

    def test_all_presets_exist(self):
        assert 'standard' in PRESETS
        assert 'wide' in PRESETS

    def test_standard_stricter_than_wide(self):
        s = PRESETS['standard']
        w = PRESETS['wide']
        assert s.win_min_gap > w.win_min_gap

    def test_both_win_only(self):
        """両プリセットともPlace無効化"""
        for name, params in PRESETS.items():
            assert params.place_min_gap >= 90, \
                f"preset {name} should disable place (place_min_gap={params.place_min_gap})"

    def test_margin_same(self):
        """両プリセットともmargin<=1.2"""
        for name, params in PRESETS.items():
            assert params.win_max_margin == 1.2, \
                f"preset {name} has unexpected max_margin={params.win_max_margin}"

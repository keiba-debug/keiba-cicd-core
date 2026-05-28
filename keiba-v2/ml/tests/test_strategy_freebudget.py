#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""freebudget.py ユニットテスト (Session 134)

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_strategy_freebudget.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.strategies.freebudget import (
    BET_UNIT_YEN,
    DEFAULT_BANKROLL,
    DEFAULT_KELLY_FRACTION,
    DEFAULT_PER_BET_CAP_PCT,
    extract_freebudget_bets,
)


# =====================================================================
# テスト用の最小 predictions dict ビルダ
# =====================================================================

def _race(
    race_id: str,
    *,
    grade: str = "G1",
    track_type: str = "turf",
    distance: int = 2000,
    venue_name: str = "東京",
    race_number: int = 11,
    num_runners: int = 16,
    race_confidence: float = 0.5,
    entries: list[dict] | None = None,
) -> dict:
    return {
        "race_id": race_id,
        "grade": grade,
        "track_type": track_type,
        "distance": distance,
        "venue_name": venue_name,
        "race_number": race_number,
        "num_runners": num_runners,
        "race_confidence": race_confidence,
        "entries": entries or [],
    }


def _entry(
    umaban: int,
    *,
    horse_name: str = "TestHorse",
    odds: float = 10.0,
    win_ev: float = 1.5,
    ar_deviation: float = 60.0,
    rank_p: int = 1,
    rank_w: int = 1,
    odds_rank: int = 3,
    vb_gap: int = 4,
    dev_gap: float = 1.2,
    pred_proba_p_raw: float = 0.30,
    place_odds_min: float = 2.5,
    place_ev: float = 1.0,
    predicted_margin: float = 30.0,
    novelty_score: int = 0,
    novelty_first_distance: int = 0,
    novelty_first_surface: int = 0,
    market_signal: str | None = None,
) -> dict:
    return {
        "umaban": umaban,
        "horse_name": horse_name,
        "odds": odds,
        "win_ev": win_ev,
        "ar_deviation": ar_deviation,
        "rank_p": rank_p,
        "rank_w": rank_w,
        "odds_rank": odds_rank,
        "vb_gap": vb_gap,
        "dev_gap": dev_gap,
        "pred_proba_p_raw": pred_proba_p_raw,
        "place_odds_min": place_odds_min,
        "place_ev": place_ev,
        "predicted_margin": predicted_margin,
        "novelty_score": novelty_score,
        "novelty_first_distance": novelty_first_distance,
        "novelty_first_surface": novelty_first_surface,
        "market_signal": market_signal,
    }


# =====================================================================
# 基本ハッピーパス
# =====================================================================

class TestExtractFreebudgetBets:

    def test_no_races_returns_empty(self):
        result = extract_freebudget_bets({"races": []})
        assert result.bets == []
        assert result.n_eligible == 0
        assert "predictions has no races" in result.warnings[0]

    def test_single_vb_horse_funded(self):
        """VB Floor 通過 1 馬 → Kelly 案分で amount > 0"""
        races = [
            _race("2026053108010101", entries=[
                _entry(6, win_ev=1.8, odds=12.0, ar_deviation=66.0,
                       rank_p=1, dev_gap=1.5, vb_gap=5),
            ])
        ]
        result = extract_freebudget_bets(
            {"races": races}, bankroll=10000,
        )
        assert result.n_eligible >= 1
        assert result.n_funded >= 1
        assert result.total_yen > 0
        bet = result.bets[0]
        assert bet.race_id == "2026053108010101"
        assert bet.umaban == 6
        assert bet.amount >= 100
        assert bet.amount % 100 == 0
        assert bet.source == "freebudget_kelly_1q"

    def test_low_ev_horse_filtered_out(self):
        """EV < 1.0 = VB Floor 不通過 → 採用されない"""
        races = [
            _race("2026053108010101", entries=[
                _entry(6, win_ev=0.8, odds=5.0),  # EV<1.0
            ])
        ]
        result = extract_freebudget_bets({"races": races})
        assert result.bets == []
        assert result.n_funded == 0

    def test_per_bet_cap_applied(self):
        """1馬で全予算超えるケース → cap 適用 (1馬 bankroll × per_bet_cap_pct 以下)"""
        races = [
            _race("2026053108010101", entries=[
                _entry(6, win_ev=5.0, odds=2.0, ar_deviation=70.0,
                       rank_p=1, dev_gap=2.0, vb_gap=7,
                       pred_proba_p_raw=0.6),  # 高EV高P% → Kelly 大
            ])
        ]
        result = extract_freebudget_bets(
            {"races": races}, bankroll=10000, per_bet_cap_pct=0.10,
        )
        if result.bets:
            assert result.bets[0].amount <= 1000  # 10% cap

    def test_amount_is_100_yen_unit(self):
        """amount は必ず 100 円単位"""
        races = [
            _race("2026053108010101", entries=[
                _entry(6, win_ev=1.5, odds=8.0, ar_deviation=65.0),
            ])
        ]
        result = extract_freebudget_bets({"races": races})
        for bet in result.bets:
            assert bet.amount % BET_UNIT_YEN == 0
            assert bet.amount >= 100

    def test_total_not_exceeds_bankroll(self):
        """合計 amount は bankroll を超えない (truncate)"""
        # 10馬 × 各 ~1000円 候補 = 全採用なら 10000円ぎりぎり、 11馬以上で truncate 発生
        races = [
            _race(f"20260531{i:02d}010101", entries=[
                _entry(1, win_ev=2.0, odds=5.0, ar_deviation=66.0,
                       rank_p=1, dev_gap=1.6, vb_gap=5,
                       pred_proba_p_raw=0.4),
            ])
            for i in range(1, 13)  # 12 race
        ]
        result = extract_freebudget_bets({"races": races}, bankroll=10000)
        assert result.total_yen <= 10000

    def test_truncation_keeps_high_ev_first(self):
        """truncate 時に EV 降順で残る (低EV から落とす)"""
        races = [
            _race("20260531" + f"{i:02d}" + "010101", entries=[
                _entry(1, win_ev=ev, odds=5.0, ar_deviation=66.0,
                       rank_p=1, dev_gap=1.5, vb_gap=5,
                       pred_proba_p_raw=0.4),
            ])
            for i, ev in enumerate([3.0, 2.0, 1.5, 1.3, 1.1, 1.05], start=1)
        ]
        result = extract_freebudget_bets(
            {"races": races}, bankroll=3000, per_bet_cap_pct=0.5,
        )
        if result.bets and result.n_truncated > 0:
            kept_evs = sorted([b.win_ev for b in result.bets], reverse=True)
            assert kept_evs[0] >= 1.5  # 高 EV が残る

    def test_zero_odds_filtered(self):
        """odds <= 1.0 は除外 (Kelly 計算不能)"""
        races = [
            _race("2026053108010101", entries=[
                _entry(6, win_ev=2.0, odds=1.0, ar_deviation=66.0),
            ])
        ]
        result = extract_freebudget_bets({"races": races})
        assert result.bets == []

    def test_invalid_preset_raises(self):
        with pytest.raises(ValueError, match="unknown preset"):
            extract_freebudget_bets({"races": []}, preset="nonexistent")


# =====================================================================
# JSON 出力スキーマ
# =====================================================================

class TestWriteFreebudgetBetsSchema:

    def test_schema_compatible_with_selective_loader(self, tmp_path):
        """出力 JSON が selective_loader.load_selective_bets を通る"""
        from ml.strategies.freebudget import write_freebudget_bets, FreebudgetResult
        from ml.target_clicker.selective_loader import load_selective_bets

        # 1 馬の最小ケース
        from ml.strategies.freebudget import FreebudgetBet
        result = FreebudgetResult(
            bets=[
                FreebudgetBet(
                    race_id="2026053108010101",
                    race_number=8,
                    venue_name="新潟",
                    grade="G1",
                    track_type="turf",
                    distance=2000,
                    num_runners=16,
                    umaban=6,
                    horse_name="テスト馬",
                    odds=12.0,
                    rank_p=1,
                    rank_w=1,
                    odds_rank=3,
                    vb_gap=4,
                    win_ev=1.5,
                    confidence=0.5,
                    amount=300,
                    kelly_p=0.125,
                    kelly_raw=0.05,
                    kelly_sized=0.03,
                    vb_score=6.0,
                )
            ],
            bankroll=10000,
            kelly_fraction=0.25,
            per_bet_cap_pct=0.10,
            preset="standard",
            total_yen=300,
            n_eligible=1,
            n_funded=1,
        )
        out_path = write_freebudget_bets(tmp_path, result)
        assert out_path.exists()

        # selective_loader で読めること
        loaded = load_selective_bets(out_path)
        assert len(loaded.bets) == 1
        assert loaded.bets[0].source == "freebudget_kelly_1q"
        assert loaded.bets[0].amount == 300
        assert loaded.n_freebudget_kelly_1q == 1

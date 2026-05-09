"""integrator (polaris統合) テスト

設計書 §4.1 の integrate() に準拠:
  display_score = sigmoid(logit(polaris_p) + rule_logit)
  selection_score = None if is_rejected else display_score
"""
from __future__ import annotations

import math

import pytest

from analysis.niigata1000.integrator import (
    apply_rule_engine,
    integrate,
)
from analysis.niigata1000.rule_engine import RuleEngine
from analysis.niigata1000.rule_loader import parse_rule_set


# ----------------------------------------------------------------------------
# integrate: 純粋関数ロジック
# ----------------------------------------------------------------------------

def test_integrate_identity_when_rule_zero():
    """rule_logit=0 のときは polaris_p がそのまま display_score"""
    out = integrate(polaris_p=0.30, rule_logit=0.0, is_rejected=False)
    assert out["display_score"] == pytest.approx(0.30, abs=1e-9)
    assert out["selection_score"] == pytest.approx(0.30)
    assert out["polaris_p"] == 0.30
    assert out["rule_logit"] == 0.0
    assert out["delta_p"] == pytest.approx(0.0, abs=1e-9)
    assert out["is_rejected"] is False


def test_integrate_positive_rule_increases_score():
    out = integrate(polaris_p=0.20, rule_logit=1.0, is_rejected=False)
    assert out["display_score"] > 0.20
    # logit(0.20) ≈ -1.386, +1.0 → -0.386 → sigmoid ≈ 0.405
    assert out["display_score"] == pytest.approx(0.4045, abs=1e-3)
    assert out["delta_p"] == pytest.approx(out["display_score"] - 0.20)


def test_integrate_negative_rule_decreases_score():
    out = integrate(polaris_p=0.40, rule_logit=-0.5, is_rejected=False)
    # logit(0.40) ≈ -0.405, -0.5 → -0.905 → sigmoid ≈ 0.288
    assert out["display_score"] < 0.40
    assert out["display_score"] == pytest.approx(0.288, abs=1e-3)


def test_integrate_rejected_makes_selection_score_none():
    out = integrate(polaris_p=0.50, rule_logit=0.5, is_rejected=True)
    # display_score は計算される
    assert out["display_score"] is not None
    assert out["display_score"] > 0.50
    # selection_score は None
    assert out["selection_score"] is None
    assert out["is_rejected"] is True


def test_integrate_clips_polaris_p_at_zero():
    """polaris_p=0 で log(0) を避ける"""
    out = integrate(polaris_p=0.0, rule_logit=0.0, is_rejected=False)
    assert out["display_score"] < 0.01  # ほぼ 0


def test_integrate_clips_polaris_p_at_one():
    out = integrate(polaris_p=1.0, rule_logit=0.0, is_rejected=False)
    assert out["display_score"] > 0.99


def test_integrate_returns_required_keys():
    out = integrate(polaris_p=0.3, rule_logit=0.0, is_rejected=False)
    assert set(out.keys()) >= {
        "display_score", "selection_score", "polaris_p",
        "rule_logit", "final_logit", "delta_p", "is_rejected",
    }


def test_integrate_final_logit_consistency():
    """final_logit = logit(p_clipped) + rule_logit"""
    out = integrate(polaris_p=0.3, rule_logit=0.5, is_rejected=False)
    expected_polaris_logit = math.log(0.3 / 0.7)
    assert out["final_logit"] == pytest.approx(expected_polaris_logit + 0.5)


# ----------------------------------------------------------------------------
# apply_rule_engine: 高レベル API
# ----------------------------------------------------------------------------

def _engine_with_rules(rules: list[dict]) -> RuleEngine:
    rs = parse_rule_set({
        "clip_groups": {"C-1": 0.5, "D": 0.6, "E": 0.3},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": rules,
    })
    return RuleEngine(rs)


def test_apply_rule_engine_combines_polaris_and_rules():
    """RuleEngine の結果と polaris を統合する"""
    engine = _engine_with_rules([
        {"id": "frame_8", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "外枠最強", "source": ""},
    ])
    ctx = {"wakuban": 8}
    out = apply_rule_engine(polaris_p=0.20, ctx=ctx, engine=engine)
    # rule 発火で +0.5 logit、display_score は polaris(0.20) より上
    assert out["display_score"] > 0.20
    assert out["rule_logit"] == pytest.approx(0.5)
    assert out["is_rejected"] is False
    # 説明文が含まれる
    assert "explanation" in out
    assert "外枠最強" in out["explanation"]


def test_apply_rule_engine_rejected_propagates():
    """STEP F が立つと selection_score=None で is_rejected=True"""
    engine = _engine_with_rules([
        {"id": "f1", "step": "F",
         "condition": "niigata_1000m_count >= 3 and niigata_1000m_top3_count == 0",
         "logit_score": None, "explanation": "千直全敗", "source": ""},
    ])
    ctx = {"niigata_1000m_count": 4, "niigata_1000m_top3_count": 0}
    out = apply_rule_engine(polaris_p=0.30, ctx=ctx, engine=engine)
    assert out["is_rejected"] is True
    assert out["selection_score"] is None
    assert out["display_score"] is not None


def test_apply_rule_engine_no_rules_fires_returns_polaris_p():
    """ルール発火ゼロなら display_score == polaris_p"""
    engine = _engine_with_rules([
        {"id": "x", "step": "B", "condition": "wakuban == 99",
         "logit_score": 0.5, "explanation": "", "source": ""},
    ])
    ctx = {"wakuban": 1}
    out = apply_rule_engine(polaris_p=0.25, ctx=ctx, engine=engine)
    assert out["display_score"] == pytest.approx(0.25, abs=1e-9)
    assert out["rule_logit"] == 0.0
    assert out["selection_score"] == pytest.approx(0.25)


def test_apply_rule_engine_returns_explanation_text():
    """explanation キーには format_explanation の出力が入る"""
    engine = _engine_with_rules([
        {"id": "frame_8", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "外枠最強", "source": ""},
    ])
    ctx = {"wakuban": 8, "umaban": 5, "horse_name": "テスト馬"}
    out = apply_rule_engine(polaris_p=0.20, ctx=ctx, engine=engine)
    assert "polaris" in out["explanation"].lower() or "20.0%" in out["explanation"]
    assert "外枠最強" in out["explanation"]
    assert "信頼度" in out["explanation"]

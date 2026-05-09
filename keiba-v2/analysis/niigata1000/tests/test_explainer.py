"""explainer (信頼度 + 説明文) テスト

設計書 §6 (説明文) + §7 (信頼度) を準拠検証する。
"""
from __future__ import annotations

import pytest

from analysis.niigata1000.explainer import (
    STEP_LABELS,
    compute_confidence,
    format_explanation,
)
from analysis.niigata1000.rule_engine import RuleEngine
from analysis.niigata1000.rule_loader import parse_rule_set


# ----------------------------------------------------------------------------
# compute_confidence (§7 サンプル数ベース)
# ----------------------------------------------------------------------------

def test_confidence_low_when_any_sample_below_10():
    """一つでも 10 未満なら 低"""
    ctx = {
        "total_career_races_at_cutoff": 50,
        "niigata_1000m_count": 5,  # +5 base = 10 → 中レベル
        "jockey_choku_n": 50,
        "trainer_choku_n": 3,  # ← これが min=3 → 低
    }
    assert compute_confidence(ctx) == "低"


def test_confidence_medium_when_min_between_10_and_29():
    ctx = {
        "total_career_races_at_cutoff": 15,
        "niigata_1000m_count": 10,  # +5 = 15
        "jockey_choku_n": 15,
        "trainer_choku_n": 15,
    }
    assert compute_confidence(ctx) == "中"


def test_confidence_high_when_all_sample_30plus():
    ctx = {
        "total_career_races_at_cutoff": 30,
        "niigata_1000m_count": 25,  # +5 = 30
        "jockey_choku_n": 30,
        "trainer_choku_n": 30,
    }
    assert compute_confidence(ctx) == "高"


def test_confidence_uses_niigata_base_5():
    """niigata_1000m_count=0 でも +5 ベースで足切り"""
    ctx = {
        "total_career_races_at_cutoff": 30,
        "niigata_1000m_count": 0,
        "jockey_choku_n": 30,
        "trainer_choku_n": 30,
    }
    # niigata=0+5=5 → 低 (min=5)
    assert compute_confidence(ctx) == "低"


def test_confidence_handles_none_as_zero():
    """ctx のサンプル数が None の場合 0 として扱う"""
    ctx = {
        "total_career_races_at_cutoff": None,
        "niigata_1000m_count": 0,
        "jockey_choku_n": None,
        "trainer_choku_n": None,
    }
    assert compute_confidence(ctx) == "低"


# ----------------------------------------------------------------------------
# STEP_LABELS
# ----------------------------------------------------------------------------

def test_step_labels_cover_all_steps():
    expected = {"A", "B", "B'", "C-1", "C-2", "C-3", "D-1", "D-2", "D-3", "E", "F"}
    assert set(STEP_LABELS.keys()) >= expected


# ----------------------------------------------------------------------------
# format_explanation: 各 STEP の発火ルールを step ごとに表示
# ----------------------------------------------------------------------------

def _engine_with_rules(rules: list[dict]) -> RuleEngine:
    rs = parse_rule_set({
        "clip_groups": {"C-1": 0.5, "C-2": 0.3, "C-3": 0.15, "D": 0.6, "E": 0.3},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": rules,
    })
    return RuleEngine(rs)


def test_format_explanation_includes_fired_rule_explanations():
    engine = _engine_with_rules([
        {"id": "frame_8", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "枠8（外枠最強）", "source": ""},
        {"id": "sire_a", "step": "C-1", "condition": "sire_name == 'A'",
         "logit_score": 0.30, "explanation": "父A（千直適性高）", "source": ""},
    ])
    result = engine.apply({"wakuban": 8, "sire_name": "A"})
    text = format_explanation(result, ctx={"wakuban": 8, "sire_name": "A"})

    assert "STEP B" in text or "枠順" in text
    assert "枠8（外枠最強）" in text
    assert "STEP C-1" in text or "血統" in text
    assert "父A（千直適性高）" in text
    # logit 値が表示される
    assert "+0.50" in text
    assert "+0.30" in text


def test_format_explanation_total_line():
    engine = _engine_with_rules([
        {"id": "x", "step": "B", "condition": "True",
         "logit_score": 0.5, "explanation": "テスト", "source": ""},
    ])
    result = engine.apply({})
    text = format_explanation(result, ctx={})
    assert "合計" in text
    assert "+0.50" in text


def test_format_explanation_includes_rejected_warning():
    engine = _engine_with_rules([
        {"id": "f1", "step": "F",
         "condition": "niigata_1000m_count >= 3 and niigata_1000m_top3_count == 0",
         "logit_score": None, "explanation": "千直全敗", "source": ""},
    ])
    result = engine.apply({"niigata_1000m_count": 4, "niigata_1000m_top3_count": 0})
    text = format_explanation(result, ctx={})
    assert "除外" in text
    assert "千直全敗" in text


def test_format_explanation_no_fired_rules():
    """発火ルールゼロでも例外なく合計0で表示"""
    engine = _engine_with_rules([
        {"id": "x", "step": "B", "condition": "wakuban == 99",
         "logit_score": 0.5, "explanation": "", "source": ""},
    ])
    result = engine.apply({"wakuban": 1})
    text = format_explanation(result, ctx={})
    assert "0.00" in text or "+0.00" in text


# ----------------------------------------------------------------------------
# format_explanation with polaris merging (3b-4 で intergrate される入力)
# ----------------------------------------------------------------------------

def test_format_explanation_with_polaris_optional():
    """polaris_p, display_score, delta_p を渡すと該当行が出力される"""
    engine = _engine_with_rules([
        {"id": "b", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "外枠", "source": ""},
    ])
    result = engine.apply({"wakuban": 8})
    text = format_explanation(
        result,
        ctx={"wakuban": 8, "umaban": 5, "horse_name": "テスト馬", "age": 4, "sex": "牝"},
        polaris_p=0.20,
        display_score=0.28,
    )
    # polaris 行が含まれる
    assert "polaris" in text.lower() or "20.0%" in text
    assert "28.0%" in text


def test_format_explanation_without_polaris_skips_top_section():
    """polaris_p が None なら polaris 関連行を出さない"""
    engine = _engine_with_rules([
        {"id": "b", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "", "source": ""},
    ])
    result = engine.apply({"wakuban": 8})
    text = format_explanation(result, ctx={}, polaris_p=None, display_score=None)
    assert "polaris" not in text.lower()

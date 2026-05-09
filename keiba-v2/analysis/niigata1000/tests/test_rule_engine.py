"""RuleEngine v0.2 テスト

設計書 §3 のセマンティクス:
  - branch 内のルールは priority 昇順で評価し最初の一致のみ適用
  - 同一 step 内 (branch=None) は全一致を加算合算
  - clip_groups の制約に従い step 内合計をクリップ
    - C-1/C-2/C-3/E は単独 step
    - D は D-1+D-2+D-3 をマージしてクリップ
  - global_clip [-1.5, +2.0] で全体を最終クリップ
  - STEP F は logit 加減点なし、is_rejected=True を立てる
"""
from __future__ import annotations

from pathlib import Path

import pytest

from analysis.niigata1000.rule_engine import RuleEngine, RuleResult
from analysis.niigata1000.rule_loader import load_rules, parse_rule_set


V02_PATH = Path(__file__).resolve().parents[1] / "rules" / "v0_2.yaml"


# ----------------------------------------------------------------------------
# 単純ケース: 単一ルール発火
# ----------------------------------------------------------------------------

def _minimal_rules(rules_list: list[dict]) -> dict:
    return {
        "clip_groups": {"C-1": 0.50, "C-2": 0.30, "C-3": 0.15, "D": 0.60, "E": 0.30},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": rules_list,
    }


def test_single_rule_fires_when_condition_true():
    rs = parse_rule_set(_minimal_rules([
        {"id": "x", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "外枠", "source": ""}
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"wakuban": 8})
    assert result.total_logit == pytest.approx(0.5)
    assert "x" in [r.id for r in result.fired_rules]
    assert result.is_rejected is False


def test_single_rule_does_not_fire_when_condition_false():
    rs = parse_rule_set(_minimal_rules([
        {"id": "x", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "", "source": ""}
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"wakuban": 4})
    assert result.total_logit == 0.0
    assert result.fired_rules == []


def test_missing_feature_treated_as_none():
    """ctx に存在しない変数は None として扱われる (NameError にならない)"""
    rs = parse_rule_set(_minimal_rules([
        {"id": "x", "step": "C-2",
         "condition": "past_corner_first_avg_5 is not None and past_corner_first_avg_5 <= 4.0",
         "logit_score": 0.15, "explanation": "", "source": ""}
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({})  # past_corner_first_avg_5 不在
    assert result.total_logit == 0.0


# ----------------------------------------------------------------------------
# branch + priority: mutex（最初の一致のみ）
# ----------------------------------------------------------------------------

def test_branch_first_match_only():
    """branch=bp の3ルール、priority昇順で最初の1つだけ適用"""
    rs = parse_rule_set(_minimal_rules([
        {"id": "p1", "step": "B'", "branch": "bp", "priority": 1,
         "condition": "wakuban in (1, 2) and past_choku_top3_rate is not None and past_choku_top3_rate >= 0.5",
         "logit_score": 0.25, "explanation": "千直巧者", "source": ""},
        {"id": "p2", "step": "B'", "branch": "bp", "priority": 2,
         "condition": "wakuban in (1, 2) and past_corner_first_avg_5 is not None and past_corner_first_avg_5 < 4.0",
         "logit_score": 0.10, "explanation": "先行型", "source": ""},
        {"id": "p3", "step": "B'", "branch": "bp", "priority": 3,
         "condition": "wakuban in (1, 2)",
         "logit_score": -0.40, "explanation": "実力不明", "source": ""},
    ]))
    engine = RuleEngine(rs)

    # case1: 千直巧者 (p1)
    r1 = engine.apply({"wakuban": 1, "past_choku_top3_rate": 0.6, "niigata_1000m_count": 3,
                       "past_corner_first_avg_5": 3.5})
    assert r1.total_logit == pytest.approx(0.25)
    fired_ids = [r.id for r in r1.fired_rules]
    assert fired_ids == ["p1"]

    # case2: 千直未経験だが先行型 (p2)
    r2 = engine.apply({"wakuban": 2, "past_choku_top3_rate": None,
                       "past_corner_first_avg_5": 3.5})
    assert r2.total_logit == pytest.approx(0.10)
    assert [r.id for r in r2.fired_rules] == ["p2"]

    # case3: いずれにも該当せず実力不明 (p3)
    r3 = engine.apply({"wakuban": 1, "past_choku_top3_rate": None,
                       "past_corner_first_avg_5": 7.0})
    assert r3.total_logit == pytest.approx(-0.40)
    assert [r.id for r in r3.fired_rules] == ["p3"]


# ----------------------------------------------------------------------------
# 加算合算 (branch=None)
# ----------------------------------------------------------------------------

def test_additive_when_no_branch():
    rs = parse_rule_set(_minimal_rules([
        {"id": "a", "step": "C-2", "condition": "past_corner_first_avg_5 <= 4.0",
         "logit_score": 0.15, "explanation": "先行", "source": ""},
        {"id": "b", "step": "C-2", "condition": "past_last_3f_min_5 <= 33.5",
         "logit_score": 0.15, "explanation": "末脚速い", "source": ""},
        {"id": "c", "step": "C-2",
         "condition": "past_corner_first_avg_5 <= 4.0 and past_last_3f_min_5 <= 33.5",
         "logit_score": 0.10, "explanation": "強馬候補", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"past_corner_first_avg_5": 3.5, "past_last_3f_min_5": 33.0})
    # 3つすべて発火: 0.15 + 0.15 + 0.10 = 0.40
    # ただし C-2 クリップ ±0.30 で 0.30 に制限される
    assert result.total_logit == pytest.approx(0.30)
    assert {r.id for r in result.fired_rules} == {"a", "b", "c"}


# ----------------------------------------------------------------------------
# clip_groups: step 内合計クリップ
# ----------------------------------------------------------------------------

def test_step_internal_clip_C1():
    """C-1 合計 +0.55 でも 0.50 にクリップされる"""
    rs = parse_rule_set(_minimal_rules([
        {"id": "s1", "step": "C-1", "condition": "sire_name == 'A'",
         "logit_score": 0.30, "explanation": "", "source": ""},
        {"id": "s2", "step": "C-1", "condition": "sire_name == 'A'",
         "logit_score": 0.25, "explanation": "", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"sire_name": "A"})
    assert result.total_logit == pytest.approx(0.50)


def test_step_d_merged_clip():
    """D-1 + D-2 + D-3 合計 +0.95 でも D クリップ ±0.60 で 0.60 に制限"""
    rs = parse_rule_set(_minimal_rules([
        {"id": "d1", "step": "D-1", "condition": "True",
         "logit_score": 0.40, "explanation": "", "source": ""},
        {"id": "d2", "step": "D-2", "condition": "True",
         "logit_score": 0.30, "explanation": "", "source": ""},
        {"id": "d3", "step": "D-3", "condition": "True",
         "logit_score": 0.25, "explanation": "", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({})
    assert result.total_logit == pytest.approx(0.60)


def test_step_d_merged_clip_negative_bound():
    """D 合計 -0.85 でも -0.60 にクリップ"""
    rs = parse_rule_set(_minimal_rules([
        {"id": "d2a", "step": "D-2", "condition": "True",
         "logit_score": -0.50, "explanation": "", "source": ""},
        {"id": "d2b", "step": "D-2", "condition": "True",
         "logit_score": -0.35, "explanation": "", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({})
    assert result.total_logit == pytest.approx(-0.60)


# ----------------------------------------------------------------------------
# global_clip: 全体 [-1.5, +2.0]
# ----------------------------------------------------------------------------

def test_global_clip_upper():
    """各 step max まで積み上げ → 合計を 2.0 にクリップ
    B(+1.0) + C-1(+0.5) + C-2(+0.3) + C-3(+0.15) + D(+0.6) + E(+0.3) = +2.85
    → global_clip で 2.0 にクリップ
    """
    rs = parse_rule_set(_minimal_rules([
        {"id": "b", "step": "B", "condition": "True",
         "logit_score": 1.0, "explanation": "", "source": ""},
        {"id": "c1", "step": "C-1", "condition": "True",
         "logit_score": 0.50, "explanation": "", "source": ""},
        {"id": "c2", "step": "C-2", "condition": "True",
         "logit_score": 0.30, "explanation": "", "source": ""},
        {"id": "c3", "step": "C-3", "condition": "True",
         "logit_score": 0.15, "explanation": "", "source": ""},
        {"id": "d", "step": "D-1", "condition": "True",
         "logit_score": 0.60, "explanation": "", "source": ""},
        {"id": "e", "step": "E", "condition": "True",
         "logit_score": 0.30, "explanation": "", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({})
    # step合計 = 1.0+0.5+0.3+0.15+0.6+0.3 = 2.85 → global 2.0 にクリップ
    assert result.total_logit == pytest.approx(2.0)


def test_global_clip_lower():
    rs = parse_rule_set(_minimal_rules([
        {"id": "b", "step": "B", "condition": "True",
         "logit_score": -1.0, "explanation": "", "source": ""},
        {"id": "c1", "step": "C-1", "condition": "True",
         "logit_score": -0.50, "explanation": "", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({})
    # 合計 -1.5、global lower -1.5 → -1.5
    assert result.total_logit == pytest.approx(-1.5)


# ----------------------------------------------------------------------------
# STEP F: REJECT
# ----------------------------------------------------------------------------

def test_step_f_sets_rejected_flag():
    rs = parse_rule_set(_minimal_rules([
        {"id": "f1", "step": "F",
         "condition": "niigata_1000m_count >= 3 and niigata_1000m_top3_count == 0",
         "logit_score": None, "explanation": "千直全敗", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"niigata_1000m_count": 4, "niigata_1000m_top3_count": 0})
    assert result.is_rejected is True
    assert "f1" in [r.id for r in result.fired_rules]
    # F ルールは logit 加減点なし
    assert result.total_logit == 0.0


def test_step_f_does_not_set_rejected_when_no_match():
    rs = parse_rule_set(_minimal_rules([
        {"id": "f1", "step": "F",
         "condition": "niigata_1000m_count >= 3 and niigata_1000m_top3_count == 0",
         "logit_score": None, "explanation": "", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"niigata_1000m_count": 1, "niigata_1000m_top3_count": 0})
    assert result.is_rejected is False


def test_step_f_combined_with_logit_rules():
    """F が立っても通常の logit 加減点は別途計算される (display_score 用)"""
    rs = parse_rule_set(_minimal_rules([
        {"id": "b", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "", "source": ""},
        {"id": "f1", "step": "F",
         "condition": "niigata_1000m_count >= 3 and niigata_1000m_top3_count == 0",
         "logit_score": None, "explanation": "", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"wakuban": 8, "niigata_1000m_count": 3, "niigata_1000m_top3_count": 0})
    assert result.total_logit == pytest.approx(0.5)
    assert result.is_rejected is True


# ----------------------------------------------------------------------------
# step_breakdown: 説明文生成用の内訳
# ----------------------------------------------------------------------------

def test_step_breakdown_has_per_step_contributions():
    rs = parse_rule_set(_minimal_rules([
        {"id": "b", "step": "B", "condition": "wakuban == 8",
         "logit_score": 0.5, "explanation": "枠8", "source": ""},
        {"id": "c1a", "step": "C-1", "condition": "sire_name == 'A'",
         "logit_score": 0.30, "explanation": "父A", "source": ""},
    ]))
    engine = RuleEngine(rs)
    result = engine.apply({"wakuban": 8, "sire_name": "A"})
    # B contribution = 0.5, C-1 contribution = 0.30
    assert result.step_breakdown["B"] == pytest.approx(0.5)
    assert result.step_breakdown["C-1"] == pytest.approx(0.30)
    # D は発火なし → 0
    assert result.step_breakdown.get("D-1", 0) == 0


# ----------------------------------------------------------------------------
# 実 v0_2.yaml ロード + 統合
# ----------------------------------------------------------------------------

def test_v0_2_apply_smoke():
    """v0_2.yaml を実際にロードして apply が例外なく回る"""
    rs = load_rules(V02_PATH)
    engine = RuleEngine(rs)
    ctx = {
        "wakuban": 8,
        "age": 4,
        "sex": "牝",
        "era": "2023-2026",
        "track_condition_grp": "良",
        "sire_name": "ロードカナロア",
        "sire_line": "キングカメハメハ系",
        "bms_line": "サンデー系",
        "past_corner_first_avg_5": 3.5,
        "past_last_3f_min_5": 33.0,
        "past_choku_top3_rate": None,
        "niigata_1000m_count": 0,
        "niigata_1000m_top3_count": 0,
        "past_short_count": 5,
        "prev_distance": 1200,
        "prev_finish": 4,
        "days_since_prev": 42,
        "jockey_name": "鮫島克駿",
        "trainer_name": "斎藤誠",
        "jockey_choku_strong_rate": 0.30,
        "jockey_choku_top3_rate": 0.25,
        "jockey_choku_n": 30,
        "trainer_choku_strong_rate": 0.30,
        "trainer_choku_top3_rate": 0.25,
        "trainer_choku_n": 20,
    }
    result = engine.apply(ctx)
    # 強い加点が乗り、reject されない
    assert result.total_logit > 0
    assert result.is_rejected is False
    assert isinstance(result, RuleResult)


def test_v0_2_apply_reject_case():
    """千直3戦以上で全敗 → is_rejected=True"""
    rs = load_rules(V02_PATH)
    engine = RuleEngine(rs)
    ctx = {
        "wakuban": 4,
        "age": 5,
        "sex": "牡",
        "era": "2023-2026",
        "track_condition_grp": "良",
        "sire_name": "?",
        "sire_line": "その他",
        "bms_line": "その他",
        "past_corner_first_avg_5": 6.0,
        "past_last_3f_min_5": 35.0,
        "past_choku_top3_rate": 0.0,
        "niigata_1000m_count": 4,        # F ルール条件
        "niigata_1000m_top3_count": 0,   # F ルール条件
        "past_short_count": 5,
        "prev_distance": 1400,
        "prev_finish": 8,
        "days_since_prev": 30,
        "jockey_name": "X",
        "trainer_name": "Y",
        "jockey_choku_strong_rate": None,
        "jockey_choku_top3_rate": None,
        "jockey_choku_n": 0,
        "trainer_choku_strong_rate": None,
        "trainer_choku_top3_rate": None,
        "trainer_choku_n": 0,
    }
    result = engine.apply(ctx)
    assert result.is_rejected is True

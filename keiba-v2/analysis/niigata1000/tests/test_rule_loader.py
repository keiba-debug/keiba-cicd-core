"""rule_loader テスト

YAML スキーマ検証 + ロードロジックを TDD で検証。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from analysis.niigata1000.rule_loader import (
    Rule,
    RuleSet,
    VALID_STEPS,
    load_rules,
    parse_rule_set,
)


# ----------------------------------------------------------------------------
# 実 YAML (rules/v0_2.yaml) のロード
# ----------------------------------------------------------------------------

V02_PATH = (
    Path(__file__).resolve().parents[1] / "rules" / "v0_2.yaml"
)


def test_load_v0_2_yaml_succeeds():
    """実プロダクション用 YAML が問題なくロードできる"""
    rs = load_rules(V02_PATH)
    assert isinstance(rs, RuleSet)
    assert len(rs.rules) > 0


def test_v0_2_has_all_expected_steps():
    """STEP A〜F すべてが少なくとも1つ以上のルールを持つ (A は条件変数のみのため除外可)"""
    rs = load_rules(V02_PATH)
    steps_present = {r.step for r in rs.rules}
    # A は加減点なし（条件変数のみ）なので YAML には不要
    expected = {"B", "B'", "C-1", "C-2", "C-3", "D-1", "D-2", "D-3", "E", "F"}
    assert expected.issubset(steps_present)


def test_v0_2_clip_groups_match_design():
    """clip_groups が §3 設計書と一致"""
    rs = load_rules(V02_PATH)
    assert rs.clip_groups["C-1"] == 0.50
    assert rs.clip_groups["C-2"] == 0.30
    assert rs.clip_groups["C-3"] == 0.15
    assert rs.clip_groups["D"] == 0.60
    assert rs.clip_groups["E"] == 0.30


def test_v0_2_global_clip_matches_design():
    rs = load_rules(V02_PATH)
    assert rs.global_clip == {"min": -1.5, "max": 2.0}


def test_v0_2_step_f_rules_have_null_score():
    """STEP F (REJECT) のルールは logit_score=None"""
    rs = load_rules(V02_PATH)
    for r in rs.rules:
        if r.step == "F":
            assert r.logit_score is None


def test_v0_2_branch_priority_unique_per_branch():
    """同一 branch 内の priority は一意"""
    rs = load_rules(V02_PATH)
    by_branch: dict = {}
    for r in rs.rules:
        if r.branch is None:
            continue
        by_branch.setdefault(r.branch, []).append(r.priority)
    for branch, prios in by_branch.items():
        assert len(prios) == len(set(prios)), f"branch={branch} has duplicate priorities"


# ----------------------------------------------------------------------------
# parse_rule_set: 直接 dict から構築 (合成テスト用)
# ----------------------------------------------------------------------------

MINIMAL_DICT = {
    "clip_groups": {"C-1": 0.5, "D": 0.6},
    "global_clip": {"min": -1.5, "max": 2.0},
    "rules": [
        {
            "id": "frame_8",
            "step": "B",
            "condition": "wakuban == 8",
            "logit_score": 0.50,
            "explanation": "枠8",
            "source": "test",
        }
    ],
}


def test_parse_rule_set_minimal():
    rs = parse_rule_set(MINIMAL_DICT)
    assert len(rs.rules) == 1
    r = rs.rules[0]
    assert r.id == "frame_8"
    assert r.step == "B"
    assert r.logit_score == 0.50
    assert r.branch is None  # 省略時 None
    assert r.priority == 0   # 省略時 0


def test_parse_rule_set_with_branch_and_priority():
    d = {
        "clip_groups": {},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": [
            {
                "id": "r1",
                "step": "B'",
                "branch": "bp",
                "priority": 1,
                "condition": "wakuban in (1, 2)",
                "logit_score": 0.25,
                "explanation": "test",
                "source": "test",
            },
            {
                "id": "r2",
                "step": "B'",
                "branch": "bp",
                "priority": 2,
                "condition": "wakuban in (1, 2)",
                "logit_score": -0.4,
                "explanation": "test",
                "source": "test",
            },
        ],
    }
    rs = parse_rule_set(d)
    assert len(rs.rules) == 2
    assert rs.rules[0].branch == "bp"
    assert rs.rules[1].priority == 2


# ----------------------------------------------------------------------------
# 検証エラー: id 重複 / 無効 step / score 範囲外 / 構文エラー
# ----------------------------------------------------------------------------

def test_duplicate_id_raises():
    d = {
        "clip_groups": {},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": [
            {"id": "X", "step": "B", "condition": "True", "logit_score": 0.1,
             "explanation": "", "source": ""},
            {"id": "X", "step": "C-1", "condition": "True", "logit_score": 0.1,
             "explanation": "", "source": ""},
        ],
    }
    with pytest.raises(ValueError, match="duplicate"):
        parse_rule_set(d)


def test_invalid_step_raises():
    d = {
        "clip_groups": {},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": [
            {"id": "X", "step": "Z", "condition": "True", "logit_score": 0.1,
             "explanation": "", "source": ""},
        ],
    }
    with pytest.raises(ValueError, match="invalid step"):
        parse_rule_set(d)


def test_score_out_of_range_raises():
    """logit_score は |x| <= 2.0 程度に制限 (典型 ±0.1〜±1.0)"""
    d = {
        "clip_groups": {},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": [
            {"id": "X", "step": "B", "condition": "True", "logit_score": 5.0,
             "explanation": "", "source": ""},
        ],
    }
    with pytest.raises(ValueError, match="logit_score out of range"):
        parse_rule_set(d)


def test_invalid_condition_syntax_raises():
    d = {
        "clip_groups": {},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": [
            {"id": "X", "step": "B", "condition": "wakuban === 8",
             "logit_score": 0.1, "explanation": "", "source": ""},
        ],
    }
    with pytest.raises(ValueError, match="condition syntax error"):
        parse_rule_set(d)


def test_step_f_with_logit_score_raises():
    """STEP F は logit_score が None でなければエラー"""
    d = {
        "clip_groups": {},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": [
            {"id": "X", "step": "F", "condition": "True", "logit_score": 0.1,
             "explanation": "", "source": ""},
        ],
    }
    with pytest.raises(ValueError, match="STEP F.*logit_score"):
        parse_rule_set(d)


def test_step_non_f_with_null_score_raises():
    """STEP F 以外は logit_score 必須"""
    d = {
        "clip_groups": {},
        "global_clip": {"min": -1.5, "max": 2.0},
        "rules": [
            {"id": "X", "step": "B", "condition": "True", "logit_score": None,
             "explanation": "", "source": ""},
        ],
    }
    with pytest.raises(ValueError, match="logit_score required"):
        parse_rule_set(d)


# ----------------------------------------------------------------------------
# RuleSet ヘルパー
# ----------------------------------------------------------------------------

def test_rules_grouped_by_step():
    rs = load_rules(V02_PATH)
    grouped = rs.rules_by_step()
    assert "B" in grouped
    assert "F" in grouped
    # B は frame_8 〜 frame_outer_heavy_track 含む
    assert any(r.id == "frame_8" for r in grouped["B"])


def test_branched_rules_sorted_by_priority():
    """同一 branch 内のルールは priority 昇順でグループ化される"""
    rs = load_rules(V02_PATH)
    bp = rs.branched_rules()
    # bp_internal branch が存在
    assert "bp_internal" in bp
    prios = [r.priority for r in bp["bp_internal"]]
    assert prios == sorted(prios)


# ----------------------------------------------------------------------------
# VALID_STEPS 定数
# ----------------------------------------------------------------------------

def test_valid_steps_contents():
    assert VALID_STEPS == {"A", "B", "B'", "C-1", "C-2", "C-3",
                           "D-1", "D-2", "D-3", "E", "F"}

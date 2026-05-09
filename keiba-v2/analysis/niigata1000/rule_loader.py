"""vega-niigata1000 RuleEngine v0.2 ルールローダー

YAML (rules/v0_2.yaml) を読んで構造化された RuleSet を返す。
スキーマ検証 + condition 構文チェックも行う。
"""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


VALID_STEPS = {
    "A", "B", "B'", "C-1", "C-2", "C-3",
    "D-1", "D-2", "D-3", "E", "F",
}

# logit_score の上下限（典型 ±0.1〜±1.0、ハード上限 ±2.0）
SCORE_HARD_LIMIT = 2.0


@dataclass
class Rule:
    id: str
    step: str
    condition: str
    logit_score: float | None  # STEP F は None
    explanation: str
    source: str
    branch: str | None = None
    priority: int = 0


@dataclass
class RuleSet:
    rules: list[Rule]
    clip_groups: dict[str, float]
    global_clip: dict[str, float]

    def rules_by_step(self) -> dict[str, list[Rule]]:
        """step ごとに分類"""
        out: dict[str, list[Rule]] = defaultdict(list)
        for r in self.rules:
            out[r.step].append(r)
        return dict(out)

    def branched_rules(self) -> dict[str, list[Rule]]:
        """branch 別にグループ化（priority 昇順、branch=None は除外）"""
        out: dict[str, list[Rule]] = defaultdict(list)
        for r in self.rules:
            if r.branch is None:
                continue
            out[r.branch].append(r)
        for k in out:
            out[k].sort(key=lambda r: r.priority)
        return dict(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_rules(path: str | Path) -> RuleSet:
    """YAML ファイルから RuleSet をロード"""
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return parse_rule_set(data)


def parse_rule_set(data: dict[str, Any]) -> RuleSet:
    """dict から RuleSet を構築（検証付き）"""
    clip_groups = dict(data.get("clip_groups") or {})
    global_clip = dict(data.get("global_clip") or {})

    raw_rules = data.get("rules") or []
    rules: list[Rule] = []
    seen_ids: set[str] = set()

    for raw in raw_rules:
        rule = _parse_rule(raw)
        if rule.id in seen_ids:
            raise ValueError(f"duplicate rule id: {rule.id!r}")
        seen_ids.add(rule.id)
        rules.append(rule)

    # branch 内の priority 重複チェック
    branch_prios: dict[str, set[int]] = defaultdict(set)
    for r in rules:
        if r.branch is None:
            continue
        if r.priority in branch_prios[r.branch]:
            raise ValueError(
                f"duplicate priority {r.priority} in branch {r.branch!r} (rule={r.id!r})"
            )
        branch_prios[r.branch].add(r.priority)

    return RuleSet(rules=rules, clip_groups=clip_groups, global_clip=global_clip)


# ---------------------------------------------------------------------------
# 内部: 1 rule の検証 + Rule 構築
# ---------------------------------------------------------------------------

def _parse_rule(raw: dict[str, Any]) -> Rule:
    rid = raw.get("id")
    if not isinstance(rid, str) or not rid:
        raise ValueError(f"rule id must be non-empty string: {raw!r}")

    step = raw.get("step")
    if step not in VALID_STEPS:
        raise ValueError(f"invalid step {step!r} for rule {rid!r}")

    condition = raw.get("condition")
    if not isinstance(condition, str) or not condition.strip():
        raise ValueError(f"condition required for rule {rid!r}")
    try:
        ast.parse(condition, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"condition syntax error in rule {rid!r}: {e}") from e

    logit_score = raw.get("logit_score", None)
    # STEP F は score なし、それ以外は必須
    if step == "F":
        if logit_score is not None:
            raise ValueError(f"STEP F rule {rid!r} must have logit_score=None (REJECT only)")
    else:
        if logit_score is None:
            raise ValueError(f"logit_score required for non-F rule {rid!r}")
        if not isinstance(logit_score, (int, float)):
            raise ValueError(f"logit_score must be number for rule {rid!r}")
        if abs(logit_score) > SCORE_HARD_LIMIT:
            raise ValueError(
                f"logit_score out of range (|x|<= {SCORE_HARD_LIMIT}) "
                f"for rule {rid!r}: {logit_score}"
            )
        logit_score = float(logit_score)

    explanation = raw.get("explanation", "") or ""
    source = raw.get("source", "") or ""
    branch = raw.get("branch")
    if branch is not None and not isinstance(branch, str):
        raise ValueError(f"branch must be string or null for rule {rid!r}")
    priority = raw.get("priority", 0)
    if not isinstance(priority, int):
        raise ValueError(f"priority must be int for rule {rid!r}")

    return Rule(
        id=rid,
        step=step,
        condition=condition,
        logit_score=logit_score,
        explanation=explanation,
        source=source,
        branch=branch,
        priority=priority,
    )

"""vega-niigata1000 RuleEngine v0.2

設計書 §3〜§4 に従いルールを適用し、合計 logit + 除外フラグを返す。

セマンティクス:
  - branch 内の rule は priority 昇順で評価し、最初の一致のみ適用
  - 同一 step 内 (branch=None) は全一致を加算合算
  - clip_groups の制約に従い step 内合計をクリップ
  - global_clip [-1.5, +2.0] で全体を最終クリップ
  - STEP F は logit 加算なし、is_rejected=True を立てる

ctx 不在キーは None として扱う (NameError にしない)。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from analysis.niigata1000.rule_loader import Rule, RuleSet


# step → clip_group キー (D-1/D-2/D-3 はマージグループ "D")
STEP_TO_CLIP_GROUP: dict[str, str] = {
    "C-1": "C-1",
    "C-2": "C-2",
    "C-3": "C-3",
    "D-1": "D",
    "D-2": "D",
    "D-3": "D",
    "E": "E",
}
# B / B' は YAML 設計上クリップなし (個別ルール側で値域コントロール)


@dataclass
class RuleResult:
    total_logit: float
    is_rejected: bool
    fired_rules: list[Rule] = field(default_factory=list)
    step_breakdown: dict[str, float] = field(default_factory=dict)


class _DefaultingDict(dict):
    """eval の locals に渡し、未定義キーで NameError を出さず None を返す"""

    def __missing__(self, key: str) -> Any:
        return None


class RuleEngine:
    def __init__(self, rule_set: RuleSet):
        self.rule_set = rule_set
        # 事前 group: branch ごとに priority 昇順、branch=None は加算用
        by_branch: dict[str | None, list[Rule]] = defaultdict(list)
        for r in rule_set.rules:
            by_branch[r.branch].append(r)
        for k in by_branch:
            by_branch[k].sort(key=lambda r: r.priority)
        self._branched: dict[str, list[Rule]] = {
            k: v for k, v in by_branch.items() if k is not None
        }
        self._unbranched: list[Rule] = by_branch.get(None, [])

    # -----------------------------------------------------------------------
    # apply
    # -----------------------------------------------------------------------

    def apply(self, ctx: dict[str, Any]) -> RuleResult:
        eval_ctx = _DefaultingDict(ctx)
        eval_globals = {"__builtins__": {}}

        fired: list[Rule] = []

        # 1. branch ごとに priority 昇順で評価し、最初の一致のみ追加
        for branch, rules in self._branched.items():
            for r in rules:
                if self._eval(r, eval_globals, eval_ctx):
                    fired.append(r)
                    break  # mutex: first match only

        # 2. branch=None のルールは全一致を追加
        for r in self._unbranched:
            if self._eval(r, eval_globals, eval_ctx):
                fired.append(r)

        # 3. step ごとの logit 合計
        step_sum: dict[str, float] = defaultdict(float)
        is_rejected = False
        for r in fired:
            if r.step == "F":
                is_rejected = True
                continue
            if r.logit_score is None:
                continue  # safety; should not happen for non-F
            step_sum[r.step] += r.logit_score

        # 4. clip_group 単位でマージしてクリップ
        clip_groups = self.rule_set.clip_groups
        group_sum: dict[str, float] = defaultdict(float)
        # マッピング step→group, group外の step (B/B') はそのまま step キーで通す
        for step, val in step_sum.items():
            group_key = STEP_TO_CLIP_GROUP.get(step, step)
            group_sum[group_key] += val

        clipped: dict[str, float] = {}
        for group_key, val in group_sum.items():
            limit = clip_groups.get(group_key)
            if limit is None:
                clipped[group_key] = val
            else:
                clipped[group_key] = max(-limit, min(limit, val))

        total = sum(clipped.values())

        # 5. global clip
        gmin = self.rule_set.global_clip.get("min", float("-inf"))
        gmax = self.rule_set.global_clip.get("max", float("inf"))
        total = max(gmin, min(gmax, total))

        # step_breakdown は元の step 単位 (D-1/D-2/D-3 を分けて保持)
        return RuleResult(
            total_logit=total,
            is_rejected=is_rejected,
            fired_rules=fired,
            step_breakdown=dict(step_sum),
        )

    # -----------------------------------------------------------------------
    # 内部
    # -----------------------------------------------------------------------

    @staticmethod
    def _eval(rule: Rule, eval_globals: dict, eval_ctx: _DefaultingDict) -> bool:
        try:
            return bool(eval(rule.condition, eval_globals, eval_ctx))
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                f"failed to evaluate rule {rule.id!r}: condition={rule.condition!r}"
            ) from e

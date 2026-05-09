"""vega-niigata1000 polaris統合 (logit空間加算)

設計書 §4.1: integrate(polaris_p, rule_logit, is_rejected) → dict
  display_score = sigmoid(logit(polaris_p) + rule_logit)
  selection_score = None if is_rejected else display_score

apply_rule_engine() は RuleEngine + integrate + format_explanation を一括で呼ぶ高レベルAPI。
"""
from __future__ import annotations

import math
from typing import Any

from analysis.niigata1000.explainer import format_explanation
from analysis.niigata1000.rule_engine import RuleEngine

# polaris_p のクリップ範囲 (log(0)/log(1) を避ける)
P_CLIP_MIN = 1e-3
P_CLIP_MAX = 1.0 - 1e-3


def integrate(
    polaris_p: float,
    rule_logit: float,
    is_rejected: bool,
) -> dict[str, Any]:
    """polaris確率 × ルール logit を logit空間で加算する。

    Returns:
        {display_score, selection_score, polaris_p, rule_logit, final_logit,
         delta_p, is_rejected}
    """
    p_clipped = max(P_CLIP_MIN, min(P_CLIP_MAX, polaris_p))
    polaris_logit = math.log(p_clipped / (1.0 - p_clipped))
    final_logit = polaris_logit + rule_logit
    display_score = 1.0 / (1.0 + math.exp(-final_logit))
    selection_score = None if is_rejected else display_score
    return {
        "display_score": display_score,
        "selection_score": selection_score,
        "polaris_p": polaris_p,
        "rule_logit": rule_logit,
        "final_logit": final_logit,
        "delta_p": display_score - polaris_p,
        "is_rejected": is_rejected,
    }


def apply_rule_engine(
    polaris_p: float,
    ctx: dict[str, Any],
    engine: RuleEngine,
) -> dict[str, Any]:
    """polaris予測 × RuleEngine 結果 × 説明文を一括で生成する高レベルAPI。

    Returns:
        integrate() の dict + "explanation" (str) + "fired_rule_ids" (list[str])
    """
    result = engine.apply(ctx)
    out = integrate(
        polaris_p=polaris_p,
        rule_logit=result.total_logit,
        is_rejected=result.is_rejected,
    )
    out["explanation"] = format_explanation(
        result,
        ctx=ctx,
        polaris_p=polaris_p,
        display_score=out["display_score"],
    )
    out["fired_rule_ids"] = [r.id for r in result.fired_rules]
    out["step_breakdown"] = dict(result.step_breakdown)
    return out

"""vega-niigata1000 説明文ジェネレータ + 信頼度計算

設計書 §6 (説明文フォーマット) + §7 (信頼度計算) を実装する。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from analysis.niigata1000.rule_engine import RuleResult


# ---------------------------------------------------------------------------
# §7 信頼度
# ---------------------------------------------------------------------------

NIIGATA_BASE = 5  # 千直未経験馬の最低サンプル数 (設計書 §7)


def _coerce_int(v: Any) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def compute_confidence(ctx: dict) -> str:
    """サンプル数ベースで信頼度ラベルを返す (高/中/低)

    使うサンプル:
      - 馬の通算経験 (total_career_races_at_cutoff)
      - 千直経験 + ベース5 (niigata_1000m_count + 5)
      - 騎手の千直2年 (jockey_choku_n)
      - 厩舎の千直2年 (trainer_choku_n)

    閾値:
      min >= 30 → 高
      min >= 10 → 中
      else      → 低
    """
    samples = [
        _coerce_int(ctx.get("total_career_races_at_cutoff")),
        _coerce_int(ctx.get("niigata_1000m_count")) + NIIGATA_BASE,
        _coerce_int(ctx.get("jockey_choku_n")),
        _coerce_int(ctx.get("trainer_choku_n")),
    ]
    m = min(samples)
    if m >= 30:
        return "高"
    if m >= 10:
        return "中"
    return "低"


# ---------------------------------------------------------------------------
# §6 説明文
# ---------------------------------------------------------------------------

STEP_LABELS: dict[str, str] = {
    "A": "環境",
    "B": "枠順",
    "B'": "内枠救済",
    "C-1": "血統",
    "C-2": "過去走脚質",
    "C-3": "属性",
    "D-1": "コンビ",
    "D-2": "騎手",
    "D-3": "厩舎",
    "E": "ローテ",
    "F": "警戒/除外",
}

# 表示順
STEP_ORDER = ["B", "B'", "C-1", "C-2", "C-3", "D-1", "D-2", "D-3", "E"]


def _fmt_logit(v: float) -> str:
    return f"{v:+.2f}"


def _fmt_pct(v: float) -> str:
    return f"{v * 100:+.1f}%"


def format_explanation(
    result: RuleResult,
    ctx: dict[str, Any],
    polaris_p: float | None = None,
    display_score: float | None = None,
) -> str:
    """RuleResult を人間可読な説明文に整形する。

    polaris_p / display_score を渡せばヘッダー行に polaris→補正→最終 を表示。
    None なら polaris 関連行は省略する (Phase 3b-4 で integrator が呼び出す形)。
    """
    lines: list[str] = []

    # ヘッダー (馬の概要)
    umaban = ctx.get("umaban")
    horse_name = ctx.get("horse_name", "")
    sex = ctx.get("sex", "")
    age = ctx.get("age")
    if umaban or horse_name:
        header = f"🐎 {umaban}番 {horse_name}".strip()
        if sex or age:
            header += f"({sex}{age}歳)" if age else f"({sex})"
        lines.append(header)

    # polaris → 補正 → 最終
    if polaris_p is not None and display_score is not None:
        delta_p = display_score - polaris_p
        lines.append(
            f"   polaris: {polaris_p * 100:.1f}% "
            f"→ 千直補正 {_fmt_pct(delta_p)} "
            f"→ 最終: {display_score * 100:.1f}%"
        )

    # 信頼度 + 除外マーカー
    confidence = compute_confidence(ctx)
    rejected_marker = " ⚠️除外推奨" if result.is_rejected else ""
    lines.append(f"   信頼度: {confidence}{rejected_marker}")
    lines.append("")

    # STEP ごとの発火ルール
    fired_by_step: dict[str, list] = defaultdict(list)
    for r in result.fired_rules:
        fired_by_step[r.step].append(r)

    for step in STEP_ORDER:
        rules = fired_by_step.get(step, [])
        if not rules:
            continue
        label = STEP_LABELS.get(step, step)
        lines.append(f"   STEP {step} ({label}):")
        for r in rules:
            score = r.logit_score if r.logit_score is not None else 0.0
            lines.append(
                f"     ✅ {r.explanation}  logit {_fmt_logit(score)}"
            )

    # 警戒/除外 (STEP F) は別表示
    f_rules = fired_by_step.get("F", [])
    if f_rules:
        lines.append("")
        lines.append("   ⚠️ 除外推奨:")
        for r in f_rules:
            lines.append(f"     - {r.explanation}")

    # 合計
    lines.append("   ─────────────")
    lines.append(f"   合計: logit {_fmt_logit(result.total_logit)}")

    return "\n".join(lines)

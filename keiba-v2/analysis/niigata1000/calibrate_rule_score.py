"""vega-niigata1000 Phase 3b-5 自動キャリブレーション

設計書 §5.1 命中率差駆動:
  condition_p = 条件成立時の 3着内率
  overall_p   = 全体の 3着内率
  rule_logit  = logit(condition_p) - logit(overall_p)
  clip rule_logit to [-1.0, +1.0]

各ルールについて、過去 135R で何頭に発火したか / それらの top3率 を集計し、
推奨 logit_score を算出。matched_n が閾値未満は手動値を維持 (§5.2)。

CLI:
  python -m analysis.niigata1000.calibrate_rule_score \
    [--input rules/v0_2.yaml] [--output rules/v0_3.yaml] \
    [--report docs/.../calibration_report.md] [--min-n 30]
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from analysis.niigata1000 import backtest_runner, features
from analysis.niigata1000.rule_engine import RuleEngine
from analysis.niigata1000.rule_loader import Rule, RuleSet, load_rules

DEFAULT_INPUT = (
    Path(__file__).resolve().parent / "rules" / "v0_2.yaml"
)
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent / "rules" / "v0_3.yaml"
)

# §5.1: 出走 50回以上 or ROI 100%超 → 自動キャリブ。それ未満は手動値維持
DEFAULT_MIN_SAMPLES = 30  # ROI 情報がないため出走数のみで判定 (50は厳しすぎるため緩める)
LOGIT_CLIP = 1.0
DEFAULT_PRIOR_STRENGTH = 30  # Bayesian 事前分布の擬似サンプル数 (k)


def _logit(p: float, eps: float = 1e-3) -> float:
    p = max(eps, min(1 - eps, p))
    return math.log(p / (1 - p))


def _posterior_mean(top3: int, n: int, overall_p: float, k: float) -> float:
    """Beta(α=k*overall_p, β=k*(1-overall_p)) prior + Binomial likelihood の posterior mean

    n=0 → overall_p (=prior mean)
    n→∞ → top3/n (=point estimate)
    """
    a0 = k * overall_p
    b0 = k * (1.0 - overall_p)
    return (a0 + top3) / (a0 + b0 + n)


# ---------------------------------------------------------------------------
# 全 千直 馬 × 発火ルール の収集
# ---------------------------------------------------------------------------

def collect_outcomes(
    rules_yaml_path: Path,
    years: set[int] | None = None,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """全 千直 horses を走査し、(全馬リスト, rule_id → 発火馬リスト) を返す"""
    rs = load_rules(rules_yaml_path)
    engine = RuleEngine(rs)

    history_cache = features.load_history_cache()
    pedigree_index = features.load_pedigree_index()
    sire_stats = features.load_sire_stats()

    race_files = backtest_runner.find_choku_race_files(years=years)

    all_horses: list[dict] = []
    rule_matches: dict[str, list[dict]] = defaultdict(list)

    for path in race_files:
        with path.open("r", encoding="utf-8") as f:
            race = json.load(f)
        polaris_map = backtest_runner.load_polaris_predictions(
            race["date"], race["race_id"]
        )
        for entry in race.get("entries", []):
            umaban = entry.get("umaban")
            if umaban not in polaris_map:
                continue
            try:
                ctx = backtest_runner.build_horse_ctx(
                    entry, race, history_cache, pedigree_index, sire_stats
                )
            except FileNotFoundError:
                continue
            result = engine.apply(ctx)
            finish = entry.get("finish_position") or 99
            horse_record = {
                "race_id": race["race_id"],
                "race_date": race["date"],
                "umaban": umaban,
                "finish_position": entry.get("finish_position"),
                "is_top3": 1 <= finish <= 3,
                "is_win": finish == 1,
                "odds": entry.get("odds"),
            }
            all_horses.append(horse_record)
            for r in result.fired_rules:
                rule_matches[r.id].append(horse_record)

    return all_horses, dict(rule_matches)


# ---------------------------------------------------------------------------
# キャリブ計算
# ---------------------------------------------------------------------------

def calibrate(
    rule_set: RuleSet,
    all_horses: list[dict],
    rule_matches: dict[str, list[dict]],
    min_samples: int = DEFAULT_MIN_SAMPLES,
    method: str = "point",
    prior_strength: float = DEFAULT_PRIOR_STRENGTH,
) -> list[dict[str, Any]]:
    """各ルールごとに matched_n / top3_rate / 推奨 logit を計算

    method:
      - 'point':    raw 命中率 → logit差 (in-sample 過学習リスクあり、設計書 §5.1)
      - 'bayesian': Beta posterior shrinkage で点推定の不確実性を吸収 (推奨)
    """
    overall_n = len(all_horses)
    overall_top3 = sum(1 for h in all_horses if h["is_top3"])
    overall_p = overall_top3 / overall_n if overall_n else 0.0
    overall_logit = _logit(overall_p)

    results: list[dict[str, Any]] = []
    for rule in rule_set.rules:
        matches = rule_matches.get(rule.id, [])
        n = len(matches)
        top3 = sum(1 for h in matches if h["is_top3"])
        wins = sum(1 for h in matches if h["is_win"])
        win_payoff = sum((h["odds"] or 0) * 100 for h in matches if h["is_win"])
        cond_p = top3 / n if n else None

        # 推奨 logit の計算 (method ごと)
        if method == "bayesian":
            # n=0 でも posterior_mean = overall_p で 0 が出る
            posterior_p = _posterior_mean(top3, n, overall_p, prior_strength)
            shrunk_logit = _logit(posterior_p) - overall_logit
            recommended = max(-LOGIT_CLIP, min(LOGIT_CLIP, shrunk_logit))
            logit_diff = shrunk_logit
        else:  # point
            cond_logit = _logit(cond_p) if cond_p is not None else None
            logit_diff = (cond_logit - overall_logit) if cond_logit is not None else None
            recommended = (
                max(-LOGIT_CLIP, min(LOGIT_CLIP, logit_diff))
                if logit_diff is not None else None
            )

        # サンプル不足時は手動値維持 (Bayesian は shrinkage が効くので緩和できる)
        if method == "bayesian":
            # Bayesian は shrinkage 効くが、n=0 等は明らかに無情報なので手動値維持
            use_recommended = (
                recommended is not None and n >= 1 and rule.step != "F"
            )
        else:
            use_recommended = (
                recommended is not None and n >= min_samples and rule.step != "F"
            )
        new_score = (
            round(recommended, 2) if use_recommended else rule.logit_score
        )

        results.append({
            "id": rule.id,
            "step": rule.step,
            "current_score": rule.logit_score,
            "matched_n": n,
            "top3_count": top3,
            "top3_rate": cond_p,
            "win_count": wins,
            "win_roi": (win_payoff / (n * 100)) if n else 0.0,
            "logit_diff": logit_diff,
            "recommended_score": recommended,
            "auto_calibrated": use_recommended,
            "new_score": new_score,
            "explanation": rule.explanation,
            "method": method,
        })

    return results


# ---------------------------------------------------------------------------
# レポート/YAML 出力
# ---------------------------------------------------------------------------

def format_report(
    rule_set: RuleSet,
    all_horses: list[dict],
    results: list[dict[str, Any]],
    min_samples: int,
) -> str:
    n_total = len(all_horses)
    top3_total = sum(1 for h in all_horses if h["is_top3"])
    overall_p = top3_total / n_total if n_total else 0.0

    lines: list[str] = []
    lines.append("# Phase 3b-5 自動キャリブレーション結果")
    lines.append("")
    lines.append(f"- 母集団: {n_total} 走 (千直 全135R)")
    lines.append(f"- 全体3着内率: {overall_p*100:.2f}% ({top3_total}/{n_total})")
    lines.append(f"- 自動キャリブ閾値: matched_n >= {min_samples}")
    lines.append("")
    lines.append("## ルール別キャリブ結果")
    lines.append("")
    lines.append(
        "| id | step | matched_n | top3 | top3率 | 単勝ROI | 現在 logit | 推奨 logit | 新 logit | 自動 |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|:--:|")
    for r in results:
        cur = f"{r['current_score']:+.2f}" if r['current_score'] is not None else "—"
        rec = f"{r['recommended_score']:+.2f}" if r['recommended_score'] is not None else "—"
        new = f"{r['new_score']:+.2f}" if r['new_score'] is not None else "—"
        top3rate = f"{r['top3_rate']*100:.1f}%" if r['top3_rate'] is not None else "—"
        roi = f"{r['win_roi']*100:.0f}%"
        auto = "✓" if r['auto_calibrated'] else ""
        lines.append(
            f"| {r['id']} | {r['step']} | {r['matched_n']} | {r['top3_count']} "
            f"| {top3rate} | {roi} | {cur} | {rec} | {new} | {auto} |"
        )

    # サンプル不足ルール一覧
    sparse = [r for r in results if r["matched_n"] < min_samples and r["step"] != "F"]
    if sparse:
        lines.append("")
        lines.append(f"## サンプル不足 (matched_n < {min_samples}) — 手動値維持")
        for r in sparse:
            lines.append(f"- `{r['id']}`: n={r['matched_n']}, "
                         f"top3率={r['top3_rate']*100:.1f}%" if r['top3_rate'] is not None
                         else f"- `{r['id']}`: n={r['matched_n']}, top3率=—")

    # STEP F は別表
    f_rules = [r for r in results if r["step"] == "F"]
    if f_rules:
        lines.append("")
        lines.append("## STEP F (除外推奨) — 該当馬の top3率")
        lines.append("")
        lines.append("| id | matched_n | top3率 |")
        lines.append("|---|---:|---:|")
        for r in f_rules:
            top3rate = f"{r['top3_rate']*100:.1f}%" if r['top3_rate'] is not None else "—"
            lines.append(f"| {r['id']} | {r['matched_n']} | {top3rate} |")

    return "\n".join(lines)


def write_calibrated_yaml(
    input_path: Path,
    results: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """v0_2.yaml をベースに new_score を反映した v0_3.yaml を生成"""
    with input_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    by_id = {r["id"]: r for r in results}
    for raw in data.get("rules", []):
        rid = raw.get("id")
        if rid in by_id:
            res = by_id[rid]
            if res["auto_calibrated"]:
                raw["logit_score"] = float(res["new_score"])
                # 注釈
                raw.setdefault("source", "")
                if "auto-cal" not in raw["source"]:
                    raw["source"] = (raw["source"] + " | auto-cal v0.3").strip(" |")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="vega-niigata1000 rule auto-calibrator")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=None,
                        help="markdown レポート出力先")
    parser.add_argument("--min-n", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument("--no-write", action="store_true",
                        help="YAML 出力をスキップ (レポートのみ)")
    parser.add_argument("--train-years", type=str, default=None,
                        help="キャリブ対象年フィルタ (例: 2020-2023)")
    parser.add_argument("--method", choices=["point", "bayesian"], default="bayesian",
                        help="キャリブ方式 (default: bayesian)")
    parser.add_argument("--prior-strength", type=float, default=DEFAULT_PRIOR_STRENGTH,
                        help=f"Bayesian 事前分布の擬似サンプル数 k (default: {DEFAULT_PRIOR_STRENGTH})")
    args = parser.parse_args()

    train_years = backtest_runner._parse_years(args.train_years)
    rs = load_rules(args.input)
    all_horses, rule_matches = collect_outcomes(args.input, years=train_years)
    results = calibrate(
        rs, all_horses, rule_matches,
        min_samples=args.min_n,
        method=args.method,
        prior_strength=args.prior_strength,
    )
    report = format_report(rs, all_horses, results, args.min_n)
    print(report)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(f"\nwrote report: {args.report}")

    if not args.no_write:
        write_calibrated_yaml(args.input, results, args.output)
        print(f"wrote YAML: {args.output}")


if __name__ == "__main__":
    main()

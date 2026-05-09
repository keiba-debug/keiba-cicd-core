"""vega-niigata1000 Phase 3c バックテスト runner

過去 135R (2020-2025) の千直で polaris単独 vs polaris+rule (v0_2) を比較する。

注意点:
  - polaris予測値 (pred_proba_p) は predictions.json から取得 (lookahead bias あり)
  - lookahead は両方の比較対象に同じ影響を与えるので、相対改善の評価は妥当
  - cutoff_date は race の開催日に固定 (当日除外)

CLI:
  python -m analysis.niigata1000.backtest_runner [--limit N] [--out report.md]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from analysis.niigata1000 import features
from analysis.niigata1000.integrator import apply_rule_engine
from analysis.niigata1000.rule_engine import RuleEngine
from analysis.niigata1000.rule_loader import load_rules

RACES_ROOT = Path("C:/KEIBA-CICD/data3/races")
DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parent / "rules" / "v0_2.yaml"
)

# sex_cd → 表示記号
SEX_CD_MAP = {"1": "牡", "2": "牝", "3": "セン"}


# ---------------------------------------------------------------------------
# レース検索
# ---------------------------------------------------------------------------

def find_choku_race_files(years: set[int] | None = None) -> list[Path]:
    """新潟芝1000m直線の全 race_*.json (years でフィルタ)"""
    out: list[Path] = []
    for path in RACES_ROOT.glob("*/*/*/race_*.json"):
        if "_info" in path.name:
            continue
        rid = path.stem[5:]  # "race_<rid>"
        if len(rid) != 16 or rid[8:10] != "04":
            continue
        if years is not None:
            try:
                rid_year = int(rid[:4])
            except ValueError:
                continue
            if rid_year not in years:
                continue
        try:
            with path.open("r", encoding="utf-8") as f:
                race = json.load(f)
        except Exception:
            continue
        if race.get("distance") == 1000 and race.get("track_type") == "turf":
            out.append(path)
    return sorted(out)


def _parse_years(arg: str | None) -> set[int] | None:
    if not arg:
        return None
    out: set[int] = set()
    for tok in arg.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok:
            a, b = tok.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(tok))
    return out


def load_polaris_predictions(race_date: str, race_id: str) -> dict[int, float]:
    """指定 race の predictions.json から umaban→pred_proba_p の dict を返す

    Returns:
        {umaban: pred_proba_p}。見つからない場合は空 dict
    """
    y, m, d = race_date.split("-")
    pred_path = RACES_ROOT / y / m / d / "predictions.json"
    if not pred_path.exists():
        return {}
    with pred_path.open("r", encoding="utf-8") as f:
        preds = json.load(f)
    for race in preds.get("races", []):
        if race.get("race_id") == race_id:
            return {
                e["umaban"]: e.get("pred_proba_p", 0.0)
                for e in race.get("entries", [])
                if e.get("pred_proba_p") is not None
            }
    return {}


# ---------------------------------------------------------------------------
# ctx 構築
# ---------------------------------------------------------------------------

def build_horse_ctx(
    entry: dict,
    race: dict,
    history_cache: dict,
    pedigree_index: dict,
    sire_stats: dict,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    """1馬分の RuleEngine 入力 ctx を組む"""
    cutoff_date = race["date"]
    ketto = entry.get("ketto_num") or ""

    hf = features.compute_horse_features(ketto, cutoff_date, history_cache)
    ped = features.compute_horse_pedigree(ketto, pedigree_index, sire_stats)
    rel = features.compute_relation_features(
        jockey_code=entry.get("jockey_code"),
        trainer_code=entry.get("trainer_code"),
        cutoff_date=cutoff_date,
        history_cache=history_cache,
        snapshot_root=snapshot_root,
    )
    env = features.compute_race_env({
        "race_date": race["date"],
        "track_condition": race.get("track_condition"),
        "num_runners": race.get("num_runners"),
        "grade": race.get("grade"),
        "race_name": race.get("race_name"),
    })

    sex_cd = entry.get("sex_cd") or ""
    sex_label = SEX_CD_MAP.get(str(sex_cd), "")

    ctx = {
        **hf, **ped, **rel, **env,
        "wakuban": entry.get("wakuban"),
        "umaban": entry.get("umaban"),
        "horse_name": entry.get("horse_name", ""),
        "ketto_num": ketto,
        "age": entry.get("age"),
        "sex": sex_label,
        "jockey_name": entry.get("jockey_name", ""),
        "trainer_name": entry.get("trainer_name", ""),
        "jockey_code": entry.get("jockey_code"),
        "trainer_code": entry.get("trainer_code"),
    }
    return ctx


# ---------------------------------------------------------------------------
# レース実行 (1R)
# ---------------------------------------------------------------------------

def run_race(
    race: dict,
    history_cache: dict,
    pedigree_index: dict,
    sire_stats: dict,
    engine: RuleEngine,
    snapshot_root: Path | None = None,
) -> list[dict[str, Any]]:
    race_id = race["race_id"]
    race_date = race["date"]
    polaris_map = load_polaris_predictions(race_date, race_id)

    out: list[dict[str, Any]] = []
    for entry in race.get("entries", []):
        umaban = entry.get("umaban")
        polaris_p = polaris_map.get(umaban)
        if polaris_p is None:
            continue
        ctx = build_horse_ctx(entry, race, history_cache, pedigree_index, sire_stats, snapshot_root)
        result = apply_rule_engine(polaris_p=polaris_p, ctx=ctx, engine=engine)
        out.append({
            "race_id": race_id,
            "race_date": race_date,
            "umaban": umaban,
            "ketto_num": ctx["ketto_num"],
            "horse_name": ctx["horse_name"],
            "wakuban": ctx["wakuban"],
            "polaris_p": polaris_p,
            "rule_logit": result["rule_logit"],
            "display_score": result["display_score"],
            "selection_score": result["selection_score"],
            "is_rejected": result["is_rejected"],
            "fired_rule_ids": result["fired_rule_ids"],
            "finish_position": entry.get("finish_position"),
            "odds": entry.get("odds"),
            "popularity": entry.get("popularity"),
        })
    return out


# ---------------------------------------------------------------------------
# 全レース実行
# ---------------------------------------------------------------------------

def run_backtest(
    rules_yaml_path: Path | None = None,
    limit: int | None = None,
    snapshot_root: Path | None = None,
    years: set[int] | None = None,
) -> tuple[list[Path], list[list[dict]]]:
    if rules_yaml_path is None:
        rules_yaml_path = DEFAULT_RULES_PATH

    rs = load_rules(rules_yaml_path)
    engine = RuleEngine(rs)

    history_cache = features.load_history_cache()
    pedigree_index = features.load_pedigree_index()
    sire_stats = features.load_sire_stats()

    race_files = find_choku_race_files(years=years)
    if limit:
        race_files = race_files[:limit]

    all_results: list[list[dict]] = []
    for path in race_files:
        with path.open("r", encoding="utf-8") as f:
            race = json.load(f)
        try:
            race_results = run_race(
                race, history_cache, pedigree_index, sire_stats, engine, snapshot_root
            )
        except FileNotFoundError as e:
            # snapshot 未生成等 → スキップ
            print(f"WARN skip {race['race_id']}: {e}")
            continue
        all_results.append(race_results)

    return race_files, all_results


# ---------------------------------------------------------------------------
# メトリクス集計
# ---------------------------------------------------------------------------

def _race_topn(race_results: list[dict], score_key: str, n: int) -> list[dict]:
    """selection_score is None の馬は最後尾。score_key で降順ソート上位N"""
    def _key(r):
        s = r.get(score_key)
        if s is None:
            return (-1, 0)
        return (1, s)
    return sorted(race_results, key=_key, reverse=True)[:n]


def aggregate_metrics(all_results: list[list[dict]]) -> dict[str, Any]:
    """polaris単独 vs polaris+rule の比較メトリクス"""
    metrics: dict[str, Any] = {}

    for label, score_key in [("polaris_only", "polaris_p"),
                             ("polaris_rule", "selection_score")]:
        n_races = 0
        # Top-3 推奨の3着内率 (race-level: 推奨3頭で1頭でも3着内に入れば的中)
        top3_hits = 0
        # Top-1 推奨の単勝的中
        top1_wins = 0
        top1_payoffs = 0.0  # 払戻 (odds × 100)
        top1_count = 0
        top3_payoffs = 0.0  # 単勝ROI: 3頭買い total
        top3_count = 0

        for race_results in all_results:
            if not race_results:
                continue
            # 全頭が rejected なら scoreが -∞ になり top1=None。skipping.
            top3 = _race_topn(race_results, score_key, 3)
            if not top3:
                continue
            n_races += 1
            top3_hit = any(
                (r.get("finish_position") or 99) <= 3 for r in top3
                if r.get("selection_score") is not None or score_key == "polaris_p"
            )
            if top3_hit:
                top3_hits += 1

            # Top-1
            top1 = top3[0]
            if top1.get("selection_score") is None and score_key == "selection_score":
                # 全頭 rejected → 買えない
                pass
            else:
                top1_count += 1
                if top1.get("finish_position") == 1:
                    top1_wins += 1
                    top1_payoffs += (top1.get("odds") or 0.0) * 100

            # Top-3 単勝
            for r in top3:
                if r.get("selection_score") is None and score_key == "selection_score":
                    continue
                top3_count += 1
                if r.get("finish_position") == 1:
                    top3_payoffs += (r.get("odds") or 0.0) * 100

        metrics[label] = {
            "n_races": n_races,
            "top3_hit_rate": top3_hits / n_races if n_races else 0.0,
            "top1_wins": top1_wins,
            "top1_count": top1_count,
            "top1_win_rate": top1_wins / top1_count if top1_count else 0.0,
            "top1_roi": top1_payoffs / (top1_count * 100) if top1_count else 0.0,
            "top3_count": top3_count,
            "top3_roi": top3_payoffs / (top3_count * 100) if top3_count else 0.0,
        }

    # 除外推奨馬の精度
    rejected_horses: list[dict] = []
    non_rejected_horses: list[dict] = []
    for race_results in all_results:
        for r in race_results:
            if r.get("is_rejected"):
                rejected_horses.append(r)
            else:
                non_rejected_horses.append(r)

    def _top3_rate(horses: list[dict]) -> float:
        if not horses:
            return 0.0
        top3 = sum(1 for r in horses if (r.get("finish_position") or 99) <= 3)
        return top3 / len(horses)

    metrics["rejected_analysis"] = {
        "n_rejected": len(rejected_horses),
        "rejected_top3_rate": _top3_rate(rejected_horses),
        "n_non_rejected": len(non_rejected_horses),
        "non_rejected_top3_rate": _top3_rate(non_rejected_horses),
    }

    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="vega-niigata1000 Phase 3c backtest")
    parser.add_argument("--limit", type=int, default=None,
                        help="評価レース数の上限 (debug用)")
    parser.add_argument("--rules", type=Path, default=None,
                        help=f"ルール YAML (default: {DEFAULT_RULES_PATH})")
    parser.add_argument("--out", type=Path, default=None,
                        help="結果 JSON 出力先")
    parser.add_argument("--years", type=str, default=None,
                        help="評価年フィルタ (例: 2024,2025 / 2024-2025)")
    args = parser.parse_args()

    years = _parse_years(args.years)
    race_files, all_results = run_backtest(
        rules_yaml_path=args.rules, limit=args.limit, years=years,
    )
    metrics = aggregate_metrics(all_results)

    print(f"backtest: {len(race_files)} races, {sum(len(r) for r in all_results)} horses")
    print()
    for label in ("polaris_only", "polaris_rule"):
        m = metrics[label]
        print(f"=== {label} ===")
        print(f"  n_races: {m['n_races']}")
        print(f"  top3_hit_rate: {m['top3_hit_rate']*100:.1f}%")
        print(f"  top1_win_rate: {m['top1_win_rate']*100:.1f}% ({m['top1_wins']}/{m['top1_count']})")
        print(f"  top1_ROI: {m['top1_roi']*100:.1f}%")
        print(f"  top3_ROI: {m['top3_roi']*100:.1f}%")
    ra = metrics["rejected_analysis"]
    print(f"=== rejected analysis ===")
    print(f"  rejected: {ra['n_rejected']} 頭, top3率 {ra['rejected_top3_rate']*100:.1f}%")
    print(f"  non-rejected: {ra['n_non_rejected']} 頭, top3率 {ra['non_rejected_top3_rate']*100:.1f}%")

    if args.out:
        args.out.write_text(
            json.dumps({"metrics": metrics, "n_races": len(race_files)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\nwrote: {args.out}")


if __name__ == "__main__":
    main()

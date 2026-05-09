"""vega-niigata1000 predict overlay (Phase 3d-0)

予測パイプラインの後段で、新潟芝1000m直線（千直）レースだけ rule_engine v0_2 を
適用し、各 entry に "niigata1000" キーを埋める軽量フック。

batch_predict.py / predict.py から呼ばれる。

Usage (programmatic):
    from analysis.niigata1000.predict_overlay import overlay_niigata_rules
    n = overlay_niigata_rules(
        predicted_races=all_predictions,   # predict_race 出力 list
        original_races=races,              # get_races_for_date 出力 list
        history_cache=history_cache,
        pedigree_index=pedigree_index,
        sire_stats=sire_stats_index,
    )

Usage (CLI、既存 predictions.json への後付け適用):
    python -m analysis.niigata1000.predict_overlay --date 2026-05-03

predictions.json に追加されるフィールド:
    niigata1000_overlay : {applied_races: N} (トップレベル、千直開催日のみ)
    races[].niigata1000_applied : bool (千直レースのみ true)
    races[].entries[].niigata1000 : dict (千直 entry のみ、polaris_p ありの場合)
        display_score, selection_score, rule_logit, delta_p, is_rejected,
        fired_rule_ids, step_breakdown, explanation, confidence
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from analysis.niigata1000 import features
from analysis.niigata1000.explainer import compute_confidence
from analysis.niigata1000.integrator import apply_rule_engine
from analysis.niigata1000.rule_engine import RuleEngine
from analysis.niigata1000.rule_loader import load_rules

DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "rules" / "v0_2.yaml"
SEX_CD_MAP = {"1": "牡", "2": "牝", "3": "セン"}


def is_niigata_1000m_race(race: dict) -> bool:
    """新潟芝1000m直線レースか判定。

    race_id 9-10桁目=04 + distance=1000 + (track_type=turf OR 芝)。
    元 race JSON は track_type='turf' だが、predict_race 出力後は '芝' になる。
    """
    rid = race.get("race_id", "")
    if not isinstance(rid, str) or len(rid) != 16 or rid[8:10] != "04":
        return False
    if race.get("distance") != 1000:
        return False
    track = race.get("track_type") or ""
    return track == "turf" or track == "芝"


def build_horse_ctx(
    entry: dict,
    race: dict,
    history_cache: dict,
    pedigree_index: dict,
    sire_stats: dict,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    """1馬分の RuleEngine 入力 ctx を組む。

    backtest_runner.build_horse_ctx と同じロジック。
    cutoff_date は race['date']（当日除外、設計書 §8.1）。
    """
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

    return {
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


def overlay_niigata_rules(
    predicted_races: list[dict],
    original_races: list[dict],
    history_cache: dict,
    pedigree_index: dict,
    sire_stats: dict,
    snapshot_root: Path | None = None,
    rules_yaml_path: Path | None = None,
    engine: RuleEngine | None = None,
) -> int:
    """予測結果 (predicted_races) に対して千直レースだけ rule_engine を適用する。

    predicted_races は in-place で書き換えられる。

    Args:
        predicted_races: predict_race 出力の list (race_id, distance, track_type, entries 等)
        original_races: 元 race JSON list (entries に jockey_code/trainer_code/sex_cd 等を含む)
        history_cache: horse_history_cache.json
        pedigree_index: 血統インデックス
        sire_stats: 種牡馬統計
        snapshot_root: niigata1000 月次スナップショット格納先 (None → DEFAULT)
        rules_yaml_path: ルール YAML (None → v0_2.yaml)
        engine: 既存 RuleEngine (None → 新規ロード、レース 0 件なら作らない)

    Returns:
        オーバーレイを適用した千直レース数
    """
    choku_pred_races = [r for r in predicted_races if is_niigata_1000m_race(r)]
    if not choku_pred_races:
        return 0

    orig_by_id = {r.get("race_id"): r for r in original_races if r.get("race_id")}

    if engine is None:
        rs = load_rules(rules_yaml_path or DEFAULT_RULES_PATH)
        engine = RuleEngine(rs)

    applied = 0
    for pred_race in choku_pred_races:
        rid = pred_race.get("race_id")
        orig = orig_by_id.get(rid)
        if orig is None:
            continue
        orig_entries_by_umaban = {
            e.get("umaban"): e for e in orig.get("entries", []) if e.get("umaban") is not None
        }

        pred_race["niigata1000_applied"] = True
        for pred_entry in pred_race.get("entries", []):
            umaban = pred_entry.get("umaban")
            polaris_p = pred_entry.get("pred_proba_p")
            orig_entry = orig_entries_by_umaban.get(umaban)
            if polaris_p is None or orig_entry is None:
                continue
            try:
                ctx = build_horse_ctx(
                    orig_entry, orig, history_cache, pedigree_index, sire_stats, snapshot_root,
                )
                result = apply_rule_engine(
                    polaris_p=float(polaris_p), ctx=ctx, engine=engine,
                )
                pred_entry["niigata1000"] = {
                    "display_score": round(float(result["display_score"]), 4),
                    "selection_score": (
                        round(float(result["selection_score"]), 4)
                        if result["selection_score"] is not None else None
                    ),
                    "rule_logit": round(float(result["rule_logit"]), 4),
                    "delta_p": round(float(result["delta_p"]), 4),
                    "is_rejected": bool(result["is_rejected"]),
                    "fired_rule_ids": list(result["fired_rule_ids"]),
                    "step_breakdown": {
                        k: round(float(v), 4) for k, v in result["step_breakdown"].items()
                    },
                    "explanation": result["explanation"],
                    "confidence": compute_confidence(ctx),
                    # UI 参照用 (predict.py の戻り値 entries には wakuban / jockey_name が無いため)
                    "wakuban": orig_entry.get("wakuban"),
                    "jockey_name": orig_entry.get("jockey_name", ""),
                    "trainer_name": orig_entry.get("trainer_name", ""),
                    "sex": ctx.get("sex", ""),
                    "age": orig_entry.get("age"),
                }
            except Exception as e:
                pred_entry["niigata1000"] = {"error": f"{type(e).__name__}: {e}"}
        applied += 1
    return applied


# ---------------------------------------------------------------------------
# CLI: 既存 predictions.json への後付け適用
# ---------------------------------------------------------------------------

DEFAULT_DATA3 = Path("C:/KEIBA-CICD/data3")


def _apply_to_existing_predictions(
    date: str,
    pred_path: Path | None = None,
    rules_yaml_path: Path | None = None,
) -> int:
    """既存 predictions.json を読んで千直 race だけ overlay 適用、in-place 書き戻し。"""
    if pred_path is None:
        y, m, d = date.split("-")
        pred_path = DEFAULT_DATA3 / "races" / y / m / d / "predictions.json"

    if not pred_path.exists():
        print(f"ERR: {pred_path} not found")
        return -1

    with pred_path.open("r", encoding="utf-8") as f:
        preds = json.load(f)

    races = preds.get("races", [])
    if not races:
        print(f"WARN: no races in {pred_path}")
        return 0

    # 元 race JSON をロード (entry の jockey_code/sex_cd 等が必要)
    races_dir = pred_path.parent
    original_races: list[dict] = []
    for r in races:
        rid = r.get("race_id")
        if not rid:
            continue
        rpath = races_dir / f"race_{rid}.json"
        if rpath.exists():
            with rpath.open("r", encoding="utf-8") as f:
                original_races.append(json.load(f))

    print(f"loaded: {len(races)} predicted races, {len(original_races)} original races")

    # マスタロード
    print("loading masters...")
    history_cache = features.load_history_cache()
    pedigree_index = features.load_pedigree_index()
    sire_stats = features.load_sire_stats()

    # overlay 適用
    n = overlay_niigata_rules(
        predicted_races=races,
        original_races=original_races,
        history_cache=history_cache,
        pedigree_index=pedigree_index,
        sire_stats=sire_stats,
        rules_yaml_path=rules_yaml_path,
    )

    if n > 0:
        preds["niigata1000_overlay"] = {"applied_races": n}
        with pred_path.open("w", encoding="utf-8") as f:
            json.dump(preds, f, ensure_ascii=False, indent=2)
        print(f"OK: overlaid {n} niigata 1000m race(s), saved to {pred_path}")
    else:
        print(f"no niigata 1000m races on {date}")
    return n


def main() -> int:
    parser = argparse.ArgumentParser(
        description="既存 predictions.json に千直 rule_engine v0_2 overlay を後付け適用"
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="predictions.json パス (default: data3/races/Y/M/D/predictions.json)",
    )
    parser.add_argument(
        "--rules", type=Path, default=None,
        help=f"ルールYAML (default: {DEFAULT_RULES_PATH})",
    )
    args = parser.parse_args()
    n = _apply_to_existing_predictions(
        date=args.date, pred_path=args.predictions, rules_yaml_path=args.rules,
    )
    return 0 if n >= 0 else 1


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.exit(main())

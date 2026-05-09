"""vega-niigata1000 Phase 3a データ準備層

設計書 §14 (v0.2.1) を単一の真実とする。
データ辞書: analysis/niigata1000/data_dictionary.md

リーク防止規約 (§8.1):
  全特徴量は cutoff_date 必須引数で「cutoff_date 当日は含めない」(strict less than)。
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# §14.3 系統判定は _helpers から再利用 (Phase 1 verify との一貫性を保つ)
from analysis.niigata1000._helpers import classify_sire_line  # noqa: F401  re-exported

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

NIIGATA_VENUE_CODE = "04"
CHOKU_DISTANCE = 1000  # 新潟芝1000m直線
CHOKU_TRACK_TYPE = "turf"
SHORT_DISTANCES = (1000, 1100, 1200)
ERA_BOUNDARY = "2023-01-01"  # 前期/後期の境界 (cutoff: < 2023-01-01 が前期)
FULL_FIELD_THRESHOLD = 16
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEFAULT_HISTORY_CACHE_PATH = Path("C:/KEIBA-CICD/data3/ml/horse_history_cache.json")
DEFAULT_PEDIGREE_INDEX_PATH = Path("C:/KEIBA-CICD/data3/indexes/pedigree_index.json")
DEFAULT_SIRE_STATS_PATH = Path("C:/KEIBA-CICD/data3/indexes/sire_stats_index.json")

_HISTORY_CACHE: dict | None = None
_PEDIGREE_INDEX: dict | None = None
_SIRE_STATS: dict | None = None


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _validate_cutoff(cutoff_date: str) -> date:
    """ISO YYYY-MM-DD 形式を強制し date オブジェクトを返す"""
    if not isinstance(cutoff_date, str) or not ISO_DATE_RE.match(cutoff_date):
        raise ValueError(
            f"cutoff_date must be ISO 'YYYY-MM-DD' string, got: {cutoff_date!r}"
        )
    try:
        return date.fromisoformat(cutoff_date)
    except ValueError as e:
        raise ValueError(f"invalid cutoff_date: {cutoff_date!r}") from e


def load_history_cache() -> dict:
    """horse_history_cache.json をロード (プロセス内キャッシュ)"""
    global _HISTORY_CACHE
    if _HISTORY_CACHE is None:
        with DEFAULT_HISTORY_CACHE_PATH.open("r", encoding="utf-8") as f:
            _HISTORY_CACHE = json.load(f)
    return _HISTORY_CACHE


def load_pedigree_index() -> dict:
    global _PEDIGREE_INDEX
    if _PEDIGREE_INDEX is None:
        with DEFAULT_PEDIGREE_INDEX_PATH.open("r", encoding="utf-8") as f:
            _PEDIGREE_INDEX = json.load(f)
    return _PEDIGREE_INDEX


def load_sire_stats() -> dict:
    global _SIRE_STATS
    if _SIRE_STATS is None:
        with DEFAULT_SIRE_STATS_PATH.open("r", encoding="utf-8") as f:
            _SIRE_STATS = json.load(f)
    return _SIRE_STATS


def _is_choku_run(run: dict) -> bool:
    """新潟芝1000m直線レースの判定"""
    return (
        run.get("venue_code") == NIIGATA_VENUE_CODE
        and run.get("distance") == CHOKU_DISTANCE
        and run.get("track_type") == CHOKU_TRACK_TYPE
    )


def _is_short_turf(run: dict) -> bool:
    """短距離 (1000-1200m) 芝レースの判定"""
    return (
        run.get("distance") in SHORT_DISTANCES
        and run.get("track_type") == CHOKU_TRACK_TYPE
    )


def _valid_last_3f(run: dict) -> float | None:
    v = run.get("last_3f")
    if v is None or v <= 0:
        return None
    return float(v)


def _valid_finish(run: dict) -> int | None:
    v = run.get("finish_position")
    if v is None or v <= 0:
        return None
    return int(v)


def _valid_corner_first(run: dict) -> int | None:
    corners = run.get("corners")
    if not corners:
        return None
    v = corners[0]
    if v in (None, 0):
        return None
    return int(v)


# ---------------------------------------------------------------------------
# §14.1 馬個別特徴量
# ---------------------------------------------------------------------------

_DEFAULT_FEATURES: dict[str, Any] = {
    "total_career_races_at_cutoff": 0,
    "niigata_1000m_count": 0,
    "niigata_1000m_top3_count": 0,
    "past_choku_top3_rate": None,
    "past_choku_finish_avg": None,
    "past_choku_last_3f_avg": None,
    "past_corner_first_avg_5": None,
    "past_corner_first_min_5": None,
    "past_last_3f_avg_5": None,
    "past_last_3f_min_5": None,
    "past_short_count": 0,
    "past_short_avg_l3f": None,
    "prev_distance": None,
    "prev_finish": None,
    "days_since_prev": None,
    "is_first_choku": True,
}


def compute_horse_features(
    ketto_num: str,
    cutoff_date: str,
    history_cache: dict | None = None,
) -> dict[str, Any]:
    """§14.1 馬個別特徴量を一括算出する。

    Args:
        ketto_num: 馬の血統登録番号 (10桁)
        cutoff_date: ISO 'YYYY-MM-DD'。当日は **含めない** (strict less than)
        history_cache: horse_history_cache.json のロード済み dict。
                       None の場合はデフォルトパスからロード

    Returns:
        §14.1 全フィールドを含む dict。馬が見つからない場合は欠損値の dict
    """
    cutoff_d = _validate_cutoff(cutoff_date)

    if history_cache is None:
        history_cache = load_history_cache()

    runs = history_cache.get(ketto_num, [])
    past = [r for r in runs if r.get("race_date", "") < cutoff_date]
    past.sort(key=lambda r: r.get("race_date", ""))

    feat = dict(_DEFAULT_FEATURES)

    if not past:
        return feat

    feat["total_career_races_at_cutoff"] = len(past)

    # --- 過去千直 (全期間) -----------------------------------------------
    choku = [r for r in past if _is_choku_run(r)]
    n_choku = len(choku)
    feat["niigata_1000m_count"] = n_choku
    feat["is_first_choku"] = n_choku == 0

    if n_choku > 0:
        top3 = sum(1 for r in choku if (_valid_finish(r) or 99) <= 3)
        feat["niigata_1000m_top3_count"] = top3
        feat["past_choku_top3_rate"] = top3 / n_choku

        finishes = [_valid_finish(r) for r in choku if _valid_finish(r) is not None]
        if finishes:
            feat["past_choku_finish_avg"] = sum(finishes) / len(finishes)

        l3f_choku = [_valid_last_3f(r) for r in choku if _valid_last_3f(r) is not None]
        if l3f_choku:
            feat["past_choku_last_3f_avg"] = sum(l3f_choku) / len(l3f_choku)

    # --- 直近5走 ----------------------------------------------------------
    last5 = past[-5:]

    cf5 = [_valid_corner_first(r) for r in last5 if _valid_corner_first(r) is not None]
    if cf5:
        feat["past_corner_first_avg_5"] = sum(cf5) / len(cf5)
        feat["past_corner_first_min_5"] = min(cf5)

    l3f5 = [_valid_last_3f(r) for r in last5 if _valid_last_3f(r) is not None]
    if l3f5:
        feat["past_last_3f_avg_5"] = sum(l3f5) / len(l3f5)
        feat["past_last_3f_min_5"] = min(l3f5)

    # --- 短距離 (1000-1200m turf) -----------------------------------------
    short = [r for r in past if _is_short_turf(r)]
    feat["past_short_count"] = len(short)
    l3f_short = [_valid_last_3f(r) for r in short if _valid_last_3f(r) is not None]
    if l3f_short:
        feat["past_short_avg_l3f"] = sum(l3f_short) / len(l3f_short)

    # --- 前走 -------------------------------------------------------------
    prev = past[-1]
    feat["prev_distance"] = prev.get("distance")
    feat["prev_finish"] = _valid_finish(prev)

    prev_date_str = prev.get("race_date", "")
    if prev_date_str and ISO_DATE_RE.match(prev_date_str):
        prev_d = date.fromisoformat(prev_date_str)
        feat["days_since_prev"] = (cutoff_d - prev_d).days

    return feat


# ---------------------------------------------------------------------------
# §14.4 環境変数 (race-level)
# ---------------------------------------------------------------------------

def classify_track_condition_grp(track_condition: str | None) -> str:
    """良/稍重以上 の2分類。不明値は安全側 (稍重以上) に倒す。"""
    if track_condition == "良":
        return "良"
    return "稍重以上"


def classify_era(race_date: str) -> str:
    """前期 (2020-2022) / 後期 (2023-2026) の判定。

    境界: race_date < '2023-01-01' なら前期。
    """
    if not isinstance(race_date, str) or not ISO_DATE_RE.match(race_date):
        raise ValueError(f"race_date must be ISO 'YYYY-MM-DD', got: {race_date!r}")
    if race_date < ERA_BOUNDARY:
        return "2020-2022"
    return "2023-2026"


def is_full_field(num_runners: int | None) -> bool:
    """フルゲート判定 (16頭以上)"""
    if num_runners is None:
        return False
    return num_runners >= FULL_FIELD_THRESHOLD


def classify_race_type(grade: str | None, race_name: str | None) -> str:
    """G3アイビスSD / OP / 条件戦 の3分類。

    優先順位:
      1. race_name に "アイビスサマーダッシュ" → "G3アイビスSD"
      2. grade in {"OP", "L"} → "OP"
      3. その他 → "条件戦"
    """
    if race_name and "アイビスサマーダッシュ" in race_name:
        return "G3アイビスSD"
    if grade in ("OP", "L"):
        return "OP"
    return "条件戦"


# ---------------------------------------------------------------------------
# §14.3 血統特徴量
# ---------------------------------------------------------------------------

_DEFAULT_PEDIGREE: dict[str, Any] = {
    "sire_id": "",
    "sire_name": "?",
    "sire_line": "不明",
    "bms_id": "",
    "bms_name": "?",
    "bms_line": "不明",
}


def compute_horse_pedigree(
    ketto_num: str,
    pedigree_index: dict | None = None,
    sire_stats: dict | None = None,
) -> dict[str, Any]:
    """§14.3 血統特徴量を一括算出する。

    Args:
        ketto_num: 馬の血統登録番号
        pedigree_index: pedigree_index.json のロード済み dict (None で自動ロード)
        sire_stats: sire_stats_index.json のロード済み dict (None で自動ロード)

    Returns:
        sire_id / sire_name / sire_line / bms_id / bms_name / bms_line を含む dict。
        馬不在/sire 不在のときは欠損値 ("" / "?" / "不明") にフォールバック
    """
    if pedigree_index is None:
        pedigree_index = load_pedigree_index()
    if sire_stats is None:
        sire_stats = load_sire_stats()

    feat = dict(_DEFAULT_PEDIGREE)

    ped = pedigree_index.get(ketto_num)
    if not ped:
        return feat

    sire_id = ped.get("sire") or ""
    bms_id = ped.get("bms") or ""

    sire_db = sire_stats.get("sire", {})
    bms_db = sire_stats.get("bms", {})

    sire_name = sire_db.get(sire_id, {}).get("name", "?") if sire_id else "?"
    bms_name = bms_db.get(bms_id, {}).get("name", "?") if bms_id else "?"

    feat["sire_id"] = sire_id
    feat["sire_name"] = sire_name
    feat["sire_line"] = classify_sire_line(sire_name)
    feat["bms_id"] = bms_id
    feat["bms_name"] = bms_name
    feat["bms_line"] = classify_sire_line(bms_name)

    return feat


def compute_race_env(race: dict) -> dict[str, Any]:
    """§14.4 race-level 環境変数を一括算出する。

    Args:
        race: race-level dict。期待キー: race_date / track_condition / num_runners /
              grade / race_name (いずれも欠損可)

    Returns:
        §14.4 全フィールドを含む dict
    """
    race_date = race.get("race_date") or "2026-01-01"  # 不明時は後期扱い
    return {
        "track_condition_grp": classify_track_condition_grp(race.get("track_condition")),
        "era": classify_era(race_date),
        "is_full_field": is_full_field(race.get("num_runners")),
        "race_type": classify_race_type(race.get("grade"), race.get("race_name")),
    }


# ---------------------------------------------------------------------------
# §14.2 関係者特徴量 (base + delta - expired, §8.2 リーク防止)
# ---------------------------------------------------------------------------

RELATION_SAMPLE_THRESHOLD = 5  # §14.5: 直近2年で出走 < 5回なら rate は None

_DEFAULT_RELATION: dict[str, Any] = {
    "jockey_choku_n": 0,
    "jockey_choku_top3_rate": None,
    "jockey_choku_strong_rate": None,
    "trainer_choku_n": 0,
    "trainer_choku_top3_rate": None,
    "trainer_choku_strong_rate": None,
}


def _previous_month_ym(cutoff_d: date) -> str:
    """cutoff_date の前月 YYYY-MM を返す"""
    first_of_month = cutoff_d.replace(day=1)
    last_of_prev = first_of_month - timedelta(days=1)
    return f"{last_of_prev.year:04d}-{last_of_prev.month:02d}"


def _aggregate_actor_in_range(
    choku_runs: list[dict],
    actor_kind: str,
    actor_code: str,
    start_inclusive: str,
    end_exclusive: str,
) -> dict[str, int]:
    """[start_inclusive, end_exclusive) の千直走を actor_code で抽出して n/top3/strong 集計"""
    n = top3 = strong = 0
    code_key = "jockey_code" if actor_kind == "jockey" else "trainer_code"
    for r in choku_runs:
        d = r.get("race_date", "")
        if not (start_inclusive <= d < end_exclusive):
            continue
        if r.get(code_key) != actor_code:
            continue
        n += 1
        if r.get("is_top3"):
            top3 += 1
        if r.get("is_strong"):
            strong += 1
    return {"n": n, "top3": top3, "strong": strong}


def compute_relation_features(
    jockey_code: str | None,
    trainer_code: str | None,
    cutoff_date: str,
    history_cache: dict | None = None,
    snapshot_root: "Path | None" = None,
) -> dict[str, Any]:
    """§14.2 関係者特徴量を base + delta - expired で算出する (§8.2)。

    アルゴリズム:
      1. base = 前月末スナップショット (cutoff_date - 1月の月末時点で直近2年集計済み)
      2. cutoff_2y = cutoff_date - 730 days
      3. delta_start = max(月初 of cutoff, cutoff_2y)
      4. delta = aggregate in [delta_start, cutoff_date)
      5. expired = aggregate in [base.window_start, cutoff_2y) — base にあるが新窓外
      6. total = base + delta - expired
      7. n < 5 なら rate は None (§14.5)

    Args:
        jockey_code: 騎手コード (None で全 0/None)
        trainer_code: 厩舎コード (None で全 0/None)
        cutoff_date: ISO 'YYYY-MM-DD'
        history_cache: 千直走の集計対象。None で自動ロード
        snapshot_root: スナップショット格納ルート。None で DEFAULT_SNAPSHOT_ROOT
    """
    # 遅延 import: 循環参照を避ける
    from analysis.niigata1000 import snapshot_builder as _sb

    cutoff_d = _validate_cutoff(cutoff_date)
    cutoff_2y = (cutoff_d - timedelta(days=_sb.ROLLING_WINDOW_DAYS)).isoformat()
    month_start = cutoff_d.replace(day=1).isoformat()
    delta_start = max(month_start, cutoff_2y)
    expired_end = cutoff_2y  # exclusive end

    # base snapshot (前月)
    base_ym = _previous_month_ym(cutoff_d)
    base = _sb.load_snapshot(base_ym, root=snapshot_root)
    if base is None:
        from pathlib import Path as _Path
        root_path = snapshot_root or _sb.DEFAULT_SNAPSHOT_ROOT
        raise FileNotFoundError(
            f"base snapshot {base_ym}.json not found under {root_path}. "
            f"Run snapshot_builder first."
        )

    # 千直走 (delta + expired 集計用)
    if history_cache is None:
        history_cache = load_history_cache()
    choku_runs = _sb._extract_choku_runs_with_strong(history_cache)

    feat = dict(_DEFAULT_RELATION)

    for actor_kind, actor_code, prefix in (
        ("jockey", jockey_code, "jockey_choku"),
        ("trainer", trainer_code, "trainer_choku"),
    ):
        if not actor_code:
            continue

        actor_table_key = "jockeys" if actor_kind == "jockey" else "trainers"
        base_stats = base.get(actor_table_key, {}).get(actor_code, {"n": 0, "top3": 0, "strong": 0})
        delta = _aggregate_actor_in_range(choku_runs, actor_kind, actor_code, delta_start, cutoff_date)
        expired = _aggregate_actor_in_range(
            choku_runs, actor_kind, actor_code, base["window_start"], expired_end
        )

        total_n = base_stats["n"] + delta["n"] - expired["n"]
        total_top3 = base_stats["top3"] + delta["top3"] - expired["top3"]
        total_strong = base_stats["strong"] + delta["strong"] - expired["strong"]

        feat[f"{prefix}_n"] = total_n
        if total_n >= RELATION_SAMPLE_THRESHOLD:
            feat[f"{prefix}_top3_rate"] = total_top3 / total_n
            feat[f"{prefix}_strong_rate"] = total_strong / total_n

    return feat

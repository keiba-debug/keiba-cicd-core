"""vega-niigata1000 §14.2 関係者snapshot builder

設計書 §8.2: 月次スナップショット (snapshot_date 時点で直近2年集計済み) を事前計算する。
出力: data3/indexes/niigata1000_relations/{YYYY-MM}.json

スナップショット形式:
{
  "snapshot_ym": "2024-07",
  "snapshot_date": "2024-07-31",
  "window_start": "2022-08-01",
  "window_end": "2024-07-31",
  "jockeys": {
    "<jockey_code>": {"n": int, "top3": int, "strong": int}, ...
  },
  "trainers": {
    "<trainer_code>": {"n": int, "top3": int, "strong": int}, ...
  }
}

CLI:
  python -m analysis.niigata1000.snapshot_builder --start 2020-01 --end 2026-04
"""
from __future__ import annotations

import argparse
import calendar
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from analysis.niigata1000 import features

DEFAULT_SNAPSHOT_ROOT = Path("C:/KEIBA-CICD/data3/indexes/niigata1000_relations")
ROLLING_WINDOW_DAYS = 730  # 直近2年


# ---------------------------------------------------------------------------
# 月末/window 計算
# ---------------------------------------------------------------------------

def _last_day_of_month(ym: str) -> str:
    """YYYY-MM → 月末日 YYYY-MM-DD"""
    y, m = ym.split("-")
    last = calendar.monthrange(int(y), int(m))[1]
    return f"{y}-{m}-{last:02d}"


def _window_start(snapshot_date: str) -> str:
    """snapshot_date から ROLLING_WINDOW_DAYS 日前 (inclusive 開始日)"""
    d = date.fromisoformat(snapshot_date)
    return (d - timedelta(days=ROLLING_WINDOW_DAYS)).isoformat()


def _iterate_yyyymm(start_ym: str, end_ym: str) -> Iterable[str]:
    """[start_ym, end_ym] の YYYY-MM を昇順で yield"""
    sy, sm = (int(x) for x in start_ym.split("-"))
    ey, em = (int(x) for x in end_ym.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1


# ---------------------------------------------------------------------------
# 千直レース抽出 + race-level 強馬判定
# ---------------------------------------------------------------------------

def _parse_time_seconds(time_str: str | None) -> float | None:
    """'1:12.0' → 72.0, '55.4' → 55.4, None/不正 → None"""
    if not time_str or not isinstance(time_str, str):
        return None
    try:
        if ":" in time_str:
            mm, rest = time_str.split(":", 1)
            return int(mm) * 60 + float(rest)
        return float(time_str)
    except (ValueError, AttributeError):
        return None


def _is_choku_run(run: dict) -> bool:
    return (
        run.get("venue_code") == "04"
        and run.get("distance") == 1000
        and run.get("track_type") == "turf"
    )


def _extract_choku_runs_with_strong(history_cache: dict) -> list[dict]:
    """history_cache から千直レース全走を抽出し、race内 mean ベースで is_strong を付与する。

    is_strong 判定 (Phase 2 と同じ):
      pre_2f = time_sec - last_3f
      pre_2f_dev = pre_2f - mean(pre_2f in race)
      last_3f_dev = last_3f - mean(last_3f in race)
      strong = (pre_2f_dev < 0 AND last_3f_dev < 0 AND finish_position <= 3)

    Returns:
      list[dict] 各 run に以下のキーを追加:
        - time_sec, is_strong (bool), is_top3 (bool)
    """
    # race_id → [run, ...]
    by_race: dict[str, list[dict]] = defaultdict(list)
    for ketto, runs in history_cache.items():
        for run in runs:
            if not _is_choku_run(run):
                continue
            time_sec = _parse_time_seconds(run.get("time"))
            l3f = run.get("last_3f")
            if time_sec is None or l3f is None or l3f <= 0:
                continue
            entry = dict(run)
            entry["ketto_num"] = ketto
            entry["time_sec"] = time_sec
            by_race[run["race_id"]].append(entry)

    out: list[dict] = []
    for race_id, race_runs in by_race.items():
        # race-level mean
        pre_2f_list = [r["time_sec"] - r["last_3f"] for r in race_runs]
        l3f_list = [r["last_3f"] for r in race_runs]
        if not pre_2f_list:
            continue
        pre_mean = sum(pre_2f_list) / len(pre_2f_list)
        l3f_mean = sum(l3f_list) / len(l3f_list)

        for r in race_runs:
            pre_dev = (r["time_sec"] - r["last_3f"]) - pre_mean
            l3f_dev = r["last_3f"] - l3f_mean
            finish = r.get("finish_position") or 99
            is_top3 = 1 <= finish <= 3
            is_strong = (pre_dev < 0) and (l3f_dev < 0) and is_top3
            r["is_top3"] = bool(is_top3)
            r["is_strong"] = bool(is_strong)
            out.append(r)

    out.sort(key=lambda r: r.get("race_date", ""))
    return out


# ---------------------------------------------------------------------------
# build_relation_snapshot
# ---------------------------------------------------------------------------

def _aggregate_window(
    choku_runs: list[dict],
    window_start: str,
    window_end: str,
) -> tuple[dict, dict]:
    """window_start <= race_date <= window_end の千直走を jockey/trainer ごとに集計"""
    jockeys: dict = defaultdict(lambda: {"n": 0, "top3": 0, "strong": 0})
    trainers: dict = defaultdict(lambda: {"n": 0, "top3": 0, "strong": 0})
    for r in choku_runs:
        d = r.get("race_date", "")
        if not (window_start <= d <= window_end):
            continue
        j = r.get("jockey_code")
        t = r.get("trainer_code")
        top3_inc = 1 if r.get("is_top3") else 0
        strong_inc = 1 if r.get("is_strong") else 0
        if j:
            jockeys[j]["n"] += 1
            jockeys[j]["top3"] += top3_inc
            jockeys[j]["strong"] += strong_inc
        if t:
            trainers[t]["n"] += 1
            trainers[t]["top3"] += top3_inc
            trainers[t]["strong"] += strong_inc
    return dict(jockeys), dict(trainers)


def build_relation_snapshot(
    snapshot_ym: str,
    history_cache: dict | None = None,
) -> dict:
    """指定月末時点のスナップショット (直近2年集計) を生成する"""
    if history_cache is None:
        history_cache = features.load_history_cache()

    snapshot_date = _last_day_of_month(snapshot_ym)
    window_start = _window_start(snapshot_date)

    choku_runs = _extract_choku_runs_with_strong(history_cache)
    jockeys, trainers = _aggregate_window(choku_runs, window_start, snapshot_date)

    return {
        "snapshot_ym": snapshot_ym,
        "snapshot_date": snapshot_date,
        "window_start": window_start,
        "window_end": snapshot_date,
        "jockeys": jockeys,
        "trainers": trainers,
    }


# ---------------------------------------------------------------------------
# 永続化
# ---------------------------------------------------------------------------

def write_snapshot(snapshot: dict, root: Path | None = None) -> Path:
    if root is None:
        root = DEFAULT_SNAPSHOT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{snapshot['snapshot_ym']}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    return path


def load_snapshot(snapshot_ym: str, root: Path | None = None) -> dict | None:
    if root is None:
        root = DEFAULT_SNAPSHOT_ROOT
    path = root / f"{snapshot_ym}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_all_snapshots(
    start_ym: str,
    end_ym: str,
    history_cache: dict | None = None,
    root: Path | None = None,
) -> list[Path]:
    """[start_ym, end_ym] 範囲で全月のスナップショットを生成・書き込む"""
    if history_cache is None:
        history_cache = features.load_history_cache()
    paths: list[Path] = []
    # choku_runs を 1 度だけ計算 (高速化)
    choku_runs = _extract_choku_runs_with_strong(history_cache)
    for ym in _iterate_yyyymm(start_ym, end_ym):
        snapshot_date = _last_day_of_month(ym)
        window_start = _window_start(snapshot_date)
        jockeys, trainers = _aggregate_window(choku_runs, window_start, snapshot_date)
        snap = {
            "snapshot_ym": ym,
            "snapshot_date": snapshot_date,
            "window_start": window_start,
            "window_end": snapshot_date,
            "jockeys": jockeys,
            "trainers": trainers,
        }
        paths.append(write_snapshot(snap, root=root))
    return paths


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="vega-niigata1000 関係者snapshotビルダー")
    parser.add_argument("--start", required=True, help="開始 YYYY-MM (例: 2020-01)")
    parser.add_argument("--end", required=True, help="終了 YYYY-MM (例: 2026-04)")
    parser.add_argument("--root", type=Path, default=None,
                        help=f"出力先ルート (default: {DEFAULT_SNAPSHOT_ROOT})")
    args = parser.parse_args()
    paths = build_all_snapshots(args.start, args.end, root=args.root)
    print(f"Generated {len(paths)} snapshots")
    for p in paths:
        print(f"  {p}")


if __name__ == "__main__":
    main()

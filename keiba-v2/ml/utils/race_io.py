#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""race_*.json + predictions.json 走査の共通ユーティリティ

ml/ 配下で重複していた以下を集約:
    - analyze_predictions.load_race_results
    - analyze_betting_strategy.load_race_results
    - analyze_market_signal.collect_data
    - enrich_novelty.build_race_meta
    - analyze_novelty.build_results / iter_date_dirs
    - extend_backtest_cache.load_results_from_race_json

races/YYYY/MM/DD/race_*.json と races/YYYY/MM/DD/predictions.json
を走査する standard な API を提供する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# core.config への参照を遅延 import
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "keiba-v2") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "keiba-v2"))


# ===========================================================================
# Date directory walking
# ===========================================================================

def races_root() -> Path:
    """races ディレクトリ (config.races_dir() のキャッシュ無し版)"""
    from core import config
    return Path(config.races_dir())


def iter_date_dirs(
    start: Optional[str] = None,
    end: Optional[str] = None,
    *,
    root: Optional[Path] = None,
) -> Iterator[Path]:
    """races/YYYY/MM/DD ディレクトリを逐次 yield

    Args:
        start: 'YYYY-MM' or 'YYYY-MM-DD' 形式 (この月以降)
        end:   'YYYY-MM' or 'YYYY-MM-DD' 形式 (この月以前)
        root:  デフォルトは config.races_dir()

    enrich_novelty/analyze_novelty の iter_date_dirs と互換 (月単位フィルタ)。
    """
    base = Path(root) if root else races_root()
    if not base.exists():
        return
    start_m = (start or "")[:7]
    end_m = (end or "")[:7]
    for year_dir in sorted(base.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            ym = f"{year_dir.name}-{month_dir.name}"
            if start_m and ym < start_m:
                continue
            if end_m and ym > end_m:
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if day_dir.is_dir():
                    yield day_dir


def date_dir_for(date_str: str, *, root: Optional[Path] = None) -> Path:
    """'YYYY-MM-DD' / 'YYYYMMDD' / 'YYYY/MM/DD' → races/YYYY/MM/DD"""
    base = Path(root) if root else races_root()
    s = str(date_str).replace("-", "").replace("/", "")
    if len(s) != 8:
        raise ValueError(f"invalid date_str: {date_str}")
    return base / s[:4] / s[4:6] / s[6:8]


# ===========================================================================
# race_*.json loaders
# ===========================================================================

def iter_race_files(date_dir: Path) -> Iterator[Path]:
    """date_dir 内の race_*.json をソート順に yield"""
    yield from sorted(Path(date_dir).glob("race_[0-9]*.json"))


def load_race(date_dir: Path, race_id: str) -> Optional[dict]:
    """単一 race_{race_id}.json を読み込み"""
    p = Path(date_dir) / f"race_{race_id}.json"
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_race_results(date_dir: Path, *, include_finish: bool = True) -> dict:
    """date_dir 内の全 race_*.json からエントリ結果を集める

    Returns: {race_id: {umaban: {finish_position, odds, ...}}}

    analyze_predictions / analyze_betting_strategy / analyze_novelty の
    各 load_race_results / build_results と互換。
    """
    out: dict = {}
    for rf in iter_race_files(date_dir):
        try:
            with open(rf, encoding="utf-8") as f:
                rd = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        rid = rd.get("race_id")
        if not rid:
            continue
        entry_map: dict = {}
        for e in rd.get("entries", []):
            um = e.get("umaban")
            if um is None:
                continue
            info = {"odds": e.get("odds") or 0}
            if include_finish:
                info["finish_position"] = e.get("finish_position")
                # 後方互換キー
                info["finish"] = e.get("finish_position")
            entry_map[um] = info
        out[rid] = entry_map
    return out


def iter_race_results(
    start: Optional[str] = None,
    end: Optional[str] = None,
    *,
    root: Optional[Path] = None,
) -> Iterator[Tuple[Path, dict]]:
    """期間内の全 date_dir について (date_dir, results) を yield"""
    for d in iter_date_dirs(start, end, root=root):
        results = load_race_results(d)
        if results:
            yield d, results


# ===========================================================================
# predictions.json loaders
# ===========================================================================

def load_predictions(date_dir: Path) -> Optional[dict]:
    """date_dir/predictions.json を読み込み"""
    p = Path(date_dir) / "predictions.json"
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def iter_predictions(
    start: Optional[str] = None,
    end: Optional[str] = None,
    *,
    root: Optional[Path] = None,
    with_results: bool = False,
) -> Iterator[Tuple[Path, dict]] | Iterator[Tuple[Path, dict, dict]]:
    """期間内の全 predictions.json を yield

    with_results=False: (date_dir, predictions_data)
    with_results=True : (date_dir, predictions_data, results_dict)

    predictions.json が無い日はスキップ。
    """
    for d in iter_date_dirs(start, end, root=root):
        data = load_predictions(d)
        if not data:
            continue
        if with_results:
            results = load_race_results(d)
            yield d, data, results
        else:
            yield d, data

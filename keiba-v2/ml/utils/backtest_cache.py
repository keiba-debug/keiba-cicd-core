#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""backtest_cache.json 共通ローダー

ml/ 配下 21 ファイルで重複していたパス hardcode と読み込みを集約。
config.ml_dir() / "backtest_cache.json" を唯一の真実とする。

提供:
    load_backtest_cache(path=None, suffix=None) -> list[dict]
        — JSON をそのまま読み込み
    flatten_to_df(races) -> pd.DataFrame
        — analyze_polaris_weakness.load_backtest_flat 互換の馬単位フラット DF
    cache_to_predictions(races) -> list[dict]
        — analyze_allocation.cache_to_predictions 互換
        — generate_recommendations / bet_engine に渡せる形式
    build_lookup(races) -> dict[(race_id, umaban), dict]
        — 高速検索辞書
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

# core.config への参照を遅延 import (循環回避)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "keiba-v2") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "keiba-v2"))


def _default_cache_path(suffix: Optional[str] = None) -> Path:
    """デフォルトの backtest_cache パスを返す

    suffix を指定すると backtest_cache_{suffix}.json を返す
    (backtest_bet_engine.py の --cache-suffix 機能と整合)。
    """
    from core import config
    name = f"backtest_cache_{suffix}.json" if suffix else "backtest_cache.json"
    return config.ml_dir() / name


def load_backtest_cache(
    path: Optional[Path] = None,
    suffix: Optional[str] = None,
    *,
    quiet: bool = False,
) -> List[dict]:
    """backtest_cache.json を読み込む

    Args:
        path:   明示パス (これが優先)
        suffix: backtest_cache_{suffix}.json
        quiet:  True なら print 抑止

    Returns: races のリスト (各 race は {race_id, entries, ...})
    """
    cache_path = Path(path) if path else _default_cache_path(suffix)
    if not cache_path.exists():
        raise FileNotFoundError(f"backtest_cache not found: {cache_path}")
    with open(cache_path, encoding="utf-8") as f:
        races = json.load(f)
    if not quiet:
        print(f"[Load] backtest_cache: {len(races):,} races from {cache_path.name}")
    return races


def build_lookup(races: List[dict]) -> dict:
    """{(race_id, umaban): entry_dict} 検索辞書

    結果のキー race_id は str, umaban は int (cache 内の型まま)。
    """
    out: dict = {}
    for race in races:
        rid = race.get("race_id")
        if not rid:
            continue
        for e in race.get("entries", []):
            um = e.get("umaban")
            if um is None:
                continue
            out[(rid, um)] = e
    return out


def flatten_to_df(races: List[dict], *, with_odds_band: bool = True):
    """馬単位のフラット DataFrame に変換 (analyze_polaris_weakness 互換)

    Columns:
        race_id, date (YYYY-MM-DD), track_type, grade, age_class, num_runners,
        umaban, horse_name, finish, odds, odds_rank, pred_p, rank_p, rank_w,
        vb_gap, win_vb_gap, win_ev, place_ev, ar_deviation, dev_gap,
        closing_strength, is_top3, is_win, is_upset, is_big_upset, odds_band
    """
    if pd is None:
        raise ImportError("pandas is required for flatten_to_df")

    rows: List[dict] = []
    for race in races:
        rid = race.get("race_id", "")
        date_str = str(rid)[:8]
        date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else ""
        race_info = {
            "race_id": rid,
            "date": date,
            "track_type": race.get("track_type", ""),
            "grade": race.get("grade", ""),
            "age_class": race.get("age_class", ""),
            "num_runners": len(race.get("entries", [])),
        }
        for e in race.get("entries", []):
            row = {**race_info}
            row["umaban"] = e.get("umaban", 0)
            row["horse_name"] = e.get("horse_name", "")
            row["finish"] = e.get("finish_position", 99)
            row["odds"] = e.get("odds", 0) or 0
            row["odds_rank"] = e.get("odds_rank", 0) or 0
            row["pred_p"] = e.get("pred_proba_p_raw", 0) or 0
            row["rank_p"] = e.get("rank_p", 0) or 0
            row["rank_w"] = e.get("rank_w", 0) or 0
            row["vb_gap"] = e.get("vb_gap", 0) or 0
            row["win_vb_gap"] = e.get("win_vb_gap", 0) or 0
            row["win_ev"] = e.get("win_ev", 0) or 0
            row["place_ev"] = e.get("place_ev", 0) or 0
            row["ar_deviation"] = e.get("ar_deviation", 0) or 0
            row["dev_gap"] = e.get("dev_gap", 0) or 0
            row["closing_strength"] = e.get("closing_strength", 0) or 0
            row["is_top3"] = e.get("is_top3", 0)
            row["is_win"] = e.get("is_win", 0)
            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["is_top3"] = df["is_top3"].astype(bool)
    df["is_win"] = df["is_win"].astype(bool)
    df["is_upset"] = df["is_top3"] & (df["odds"] >= 10.0)
    df["is_big_upset"] = df["is_top3"] & (df["odds"] >= 20.0)

    if with_odds_band:
        from ml.utils.segments import bin_odds
        df["odds_band"] = bin_odds(df["odds"])

    return df


def cache_to_predictions(races: List[dict]) -> List[dict]:
    """backtest_cache → generate_recommendations 入力形式

    bet_engine.generate_recommendations が期待する race dict 形式に整形する。
    analyze_allocation.cache_to_predictions と互換。
    """
    preds: List[dict] = []
    for race in races:
        entries = []
        for e in race.get("entries", []):
            entries.append({
                "umaban": e.get("umaban"),
                "horse_name": e.get("horse_name", ""),
                "odds": e.get("odds", 0),
                "odds_rank": e.get("odds_rank", 99),
                "vb_gap": e.get("vb_gap", 0),
                "win_vb_gap": e.get("win_vb_gap", e.get("vb_gap", 0)),
                "rank_p": e.get("rank_p", 99),
                "rank_w": e.get("rank_w", 99),
                "place_odds_min": e.get("place_odds_min"),
                "pred_proba_p_raw": e.get("pred_proba_p_raw"),
                "predicted_margin": e.get("predicted_margin"),
                "win_ev": e.get("win_ev"),
                "place_ev": e.get("place_ev"),
                "comment_memo_trouble_score": e.get("comment_memo_trouble_score", 0),
                "ar_deviation": e.get("ar_deviation"),
            })
        preds.append({
            "race_id": race.get("race_id"),
            "track_type": race.get("track_type", ""),
            "grade": race.get("grade", ""),
            "grade_offset": race.get("grade_offset", 0),
            "entries": entries,
        })
    return preds

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特徴量スナップショット保存・読み込み

レース単位で計算された特徴量をJSONファイルとして保存する。
保存先: data3/features/YYYY/MM/DD/features_{race_id}.json

目的:
  - 特徴量の可視化・検証
  - リーク検出の基盤
  - 実験間の特徴量差分比較
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def _race_id_to_date_parts(race_id: str) -> tuple:
    """race_id (16桁 YYYYMMDDJJKKNNRR) から (YYYY, MM, DD) を抽出"""
    return race_id[:4], race_id[4:6], race_id[6:8]


def _features_dir(race_id: str) -> Path:
    """スナップショット保存ディレクトリを返す"""
    yyyy, mm, dd = _race_id_to_date_parts(race_id)
    return config.data_root() / "features" / yyyy / mm / dd


def save_feature_snapshot(
    rows: List[dict],
    race: dict,
    source: str = "experiment",
) -> Optional[Path]:
    """レース単位の特徴量スナップショットを保存

    Args:
        rows: compute_features_for_race() の戻り値（List[dict]、各馬の特徴量dict）
        race: レースJSON（メタ情報取得用）
        source: "experiment" or "predict"

    Returns:
        保存先パス（成功時）、None（失敗時）
    """
    if not rows:
        return None

    race_id = rows[0].get('race_id', '')
    date_str = rows[0].get('date', '')

    # メタ情報以外の特徴量キーを特定
    meta_keys = {
        'race_id', 'date', 'ketto_num', 'horse_name', 'umaban',
        'venue_name', 'grade', 'age_class',
        'finish_position', 'is_top3', 'is_win', 'place_odds_low',
    }

    entries = []
    feature_keys = None
    for row in rows:
        features = {k: _serialize(v) for k, v in row.items() if k not in meta_keys}
        if feature_keys is None:
            feature_keys = sorted(features.keys())

        entries.append({
            'umaban': row.get('umaban'),
            'ketto_num': row.get('ketto_num', ''),
            'horse_name': row.get('horse_name', ''),
            'finish_position': row.get('finish_position'),
            'features': features,
        })

    snapshot = {
        'race_id': race_id,
        'date': date_str,
        'venue_name': race.get('venue_name', ''),
        'race_name': race.get('race_name', ''),
        'grade': race.get('grade', ''),
        'source': source,
        'saved_at': datetime.now().isoformat(timespec='seconds'),
        'feature_count': len(feature_keys) if feature_keys else 0,
        'entries': entries,
    }

    out_dir = _features_dir(race_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"features_{race_id}.json"

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)

    return out_path


def load_feature_snapshot(race_id: str) -> Optional[dict]:
    """保存済みスナップショットを読み込む

    Returns:
        スナップショットdict（存在しない場合はNone）
    """
    out_dir = _features_dir(race_id)
    path = out_dir / f"features_{race_id}.json"
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _serialize(val):
    """JSON互換の値に変換"""
    if val is None:
        return None
    if isinstance(val, float):
        import math
        if math.isnan(val) or math.isinf(val):
            return None
        return round(val, 6)
    if isinstance(val, (int, str, bool)):
        return val
    try:
        return float(val)
    except (TypeError, ValueError):
        return str(val)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
スピード指数特徴量 (v3.5)

keibabook拡張データ(kb_ext)のspeed_indexes（過去5走スピード指数）から
ML用特徴量を抽出。

データソース: data3/keibabook/YYYY/MM/DD/kb_ext_{race_id}.json
  → entries[umaban].speed_indexes  (list of float|None, 5走前→前走)
"""

from typing import Optional


def compute_speed_features(
    umaban: str,
    kb_ext: dict | None,
) -> dict:
    """1頭のスピード指数特徴量を計算

    Args:
        umaban: 馬番（文字列）
        kb_ext: kb_ext JSONの内容（Noneならデータなし）

    Returns:
        dict: 特徴量辞書
    """
    default = {
        'speed_idx_latest': -1.0,
        'speed_idx_best5': -1.0,
        'speed_idx_avg3': -1.0,
        'speed_idx_trend': 0.0,
        'speed_idx_std': -1.0,
    }

    if not kb_ext:
        return default

    entries = kb_ext.get('entries', {})
    entry = entries.get(str(umaban))
    if not entry:
        return default

    raw = entry.get('speed_indexes')
    if not raw:
        return default

    # None以外の有効値を抽出
    valid = [v for v in raw if v is not None]
    if not valid:
        return default

    result = dict(default)

    # 最新（前走）のスピード指数
    # rawは[5走前, 4走前, 3走前, 2走前, 前走] の順
    for v in reversed(raw):
        if v is not None:
            result['speed_idx_latest'] = v
            break

    # 5走中の最高値
    result['speed_idx_best5'] = max(valid)

    # 直近3走の平均（rawの後ろ3つから有効値）
    recent3 = [v for v in raw[-3:] if v is not None]
    if recent3:
        result['speed_idx_avg3'] = sum(recent3) / len(recent3)

    # トレンド（直近2走の差: 前走 - 2走前）
    # 正=上昇傾向、負=下降傾向
    if len(valid) >= 2:
        # 有効値の中で最新2つを使う
        recent_valid = []
        for v in reversed(raw):
            if v is not None:
                recent_valid.append(v)
                if len(recent_valid) == 2:
                    break
        if len(recent_valid) == 2:
            result['speed_idx_trend'] = recent_valid[0] - recent_valid[1]

    # 標準偏差（安定性）
    if len(valid) >= 2:
        mean = sum(valid) / len(valid)
        variance = sum((v - mean) ** 2 for v in valid) / len(valid)
        result['speed_idx_std'] = variance ** 0.5

    return result

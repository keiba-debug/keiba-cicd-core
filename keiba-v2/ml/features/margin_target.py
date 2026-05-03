#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
着差回帰ターゲット計算ユーティリティ

race JSONのtimeフィールド(M:SS.T形式)から着差(time_behind_winner)を計算する。
experiment_regression.py と predict.py の両方から共有利用。

Phase 1: 走破タイムベース (0.1s精度)
  - 同タイムは着順×0.02sオフセットで区別
  - 5.0s上限キャップ (外れ値抑制)
  - 取消・除外(finish_position=0)はNaN

Phase 2 (将来): CHAKUSA_CODEベースでsub-0.1s区別
"""

import math
from typing import Dict, Optional

import numpy as np


def parse_time_str(time_str: str) -> float:
    """走破タイム文字列 "M:SS.T" を秒に変換

    Args:
        time_str: "1:34.5" や "0:58.2" 形式

    Returns:
        秒数 (float)。パース失敗時は NaN
    """
    if not time_str or not isinstance(time_str, str):
        return float('nan')
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        else:
            return float(time_str)
    except (ValueError, IndexError):
        return float('nan')


def compute_race_margins(
    entries: list,
    cap: float = 5.0,
    same_time_offset: float = 0.02,
) -> Dict[int, float]:
    """1レースの全出走馬のtime_behind_winnerを計算

    Args:
        entries: race JSON の entries リスト
        cap: 着差上限秒数 (これを超える着差はcapで丸める)
        same_time_offset: 同タイム馬の着順差×offset で区別

    Returns:
        dict: {umaban: target_margin}
              1着 = 0.0, 取消/除外/タイムなし = NaN
    """
    # 着順・タイムを収集
    valid_entries = []
    for e in entries:
        fp = e.get('finish_position', 0)
        if fp <= 0:
            continue
        time_sec = parse_time_str(e.get('time', ''))
        valid_entries.append({
            'umaban': e.get('umaban', 0),
            'finish_position': fp,
            'time_sec': time_sec,
        })

    if not valid_entries:
        return {}

    # 1着馬のタイムを特定
    valid_entries.sort(key=lambda x: x['finish_position'])
    winner_time = float('nan')
    for ve in valid_entries:
        if ve['finish_position'] == 1 and not math.isnan(ve['time_sec']):
            winner_time = ve['time_sec']
            break

    if math.isnan(winner_time):
        return {}

    # 着差を計算
    result = {}
    for ve in valid_entries:
        umaban = ve['umaban']
        fp = ve['finish_position']
        time_sec = ve['time_sec']

        if math.isnan(time_sec):
            result[umaban] = float('nan')
            continue

        if fp == 1:
            result[umaban] = 0.0
            continue

        raw_margin = time_sec - winner_time

        # 同タイムの馬を着順で微細に区別
        # (0.1s精度 → 着順差 × 0.02s で sub-0.1s 差をつける)
        if raw_margin >= 0:
            # 同タイムグループ内の着順オフセット
            # 同じ raw_margin を持つ馬の中で、着順が後ろの馬ほどわずかに大きい値にする
            margin = raw_margin + (fp - 2) * same_time_offset * 0.1
            # ただし、raw_margin自体を超える量のオフセットはつけない
            # (次のタイム帯に食い込まないようにする)
            margin = max(margin, raw_margin)
        else:
            # タイム差がマイナス（まれ: 1着のタイムが遅い異常データ）
            margin = 0.0

        # キャップ適用
        margin = min(margin, cap)
        result[umaban] = round(margin, 3)

    return result


def compute_race_margins_v2(
    entries: list,
    race_date: str,
    sed_index: dict = None,
    cap: float = 5.0,
    same_time_offset: float = 0.02,
    furi_scale: float = 0.1,
    mode: str = 'raw',
) -> Dict[int, float]:
    """1レースの target_margin を計算 (B案: 不利補正 + レース内標準化対応)

    Args:
        entries: race JSON の entries リスト
        race_date: 'YYYY-MM-DD' 形式 (SED index lookup 用)
        sed_index: JRDB SED index (dict). mode in ('adjusted','adj_zscore') の時に必要
        cap: 着差上限秒数 (raw/adjusted モードのみ)
        same_time_offset: 同タイム馬の着順差×offset で区別
        furi_scale: 不利1単位あたりの秒換算 (デフォルト0.1秒/単位)
        mode:
            'raw'        — 従来 (走破時間 - 1着時間)
            'adjusted'   — 不利補正済み (time - furi_scale * furi_adj)
            'zscore'     — レース内z-score (生時間ベース)
            'adj_zscore' — 不利補正 + z-score (推奨)

    Returns:
        dict: {umaban: target_value}
              1着 = 0.0 (raw/adjusted) または 最小値 (zscore系)
              取消・除外・補正データ無し = NaN
    """
    valid_entries = []
    for e in entries:
        fp = e.get('finish_position', 0)
        if fp <= 0:
            continue
        time_sec = parse_time_str(e.get('time', ''))
        if math.isnan(time_sec):
            continue
        # 不利補正 lookup
        furi = 0
        if mode in ('adjusted', 'adj_zscore'):
            ketto = e.get('ketto_num')
            if ketto and sed_index:
                key = f"{ketto}_{race_date}"
                sed_e = sed_index.get(key)
                if sed_e:
                    furi = sed_e.get('furi_adj', 0) or 0
        adj_time = time_sec - furi_scale * furi if mode in ('adjusted', 'adj_zscore') else time_sec
        valid_entries.append({
            'umaban': e.get('umaban', 0),
            'finish_position': fp,
            'time_sec': time_sec,
            'adj_time': adj_time,
        })

    if not valid_entries:
        return {}

    # ========= z-score 系: レース内標準化 =========
    if mode in ('zscore', 'adj_zscore'):
        times = np.array([ve['adj_time'] for ve in valid_entries])
        race_mean = float(times.mean())
        race_std = float(times.std())
        if race_std < 1e-6:
            race_std = 1.0  # 全馬同タイム (実質ゼロ)
        result = {}
        for ve in valid_entries:
            z = (ve['adj_time'] - race_mean) / race_std
            # z-score は 1着が負方向 (時間小) — そのまま「low=better」を保つ
            result[ve['umaban']] = round(z, 4)
        return result

    # ========= raw / adjusted モード: 1着差ベース =========
    # 1着馬の補正済みタイム
    valid_entries.sort(key=lambda x: x['finish_position'])
    winner_time = float('nan')
    for ve in valid_entries:
        if ve['finish_position'] == 1:
            winner_time = ve['adj_time']
            break
    if math.isnan(winner_time):
        return {}

    result = {}
    for ve in valid_entries:
        umaban = ve['umaban']
        fp = ve['finish_position']
        adj_t = ve['adj_time']

        if fp == 1:
            result[umaban] = 0.0
            continue

        raw_margin = adj_t - winner_time
        if raw_margin >= 0:
            margin = raw_margin + (fp - 2) * same_time_offset * 0.1
            margin = max(margin, raw_margin)
        else:
            # 不利補正で1着馬より速い "補正後タイム" になるケース → 0扱い
            margin = 0.0
        margin = min(margin, cap)
        result[umaban] = round(margin, 3)

    return result


def add_margin_target_to_df(
    df,
    date_index: dict,
    load_race_fn,
    cap: float = 5.0,
    mode: str = 'raw',
    sed_index: dict = None,
    furi_scale: float = 0.1,
) -> None:
    """DataFrameにtarget_marginカラムを追加 (in-place)

    Args:
        df: build_dataset()の出力DataFrame (race_id, umaban カラムが必要)
        date_index: race_date_index
        load_race_fn: load_race_json関数
        cap: 着差上限 (mode='raw'/'adjusted' のみ有効)
        mode: 'raw' / 'adjusted' / 'zscore' / 'adj_zscore'
        sed_index: JRDB SED index (mode='adjusted'/'adj_zscore' で必須)
        furi_scale: 不利1単位あたりの秒換算 (デフォルト0.1秒)
    """
    from ml.experiment import _iter_date_index

    if mode in ('adjusted', 'adj_zscore') and sed_index is None:
        raise ValueError(f"mode={mode} requires sed_index")

    # race_id → date_str のマッピングを構築
    race_date_map = {}
    for date_str, race_id in _iter_date_index(date_index):
        race_date_map[race_id] = date_str

    # レースごとにmarginを計算
    margin_index = {}  # (race_id, umaban) -> margin
    processed = 0
    errors = 0
    n_furi_corrected = 0

    unique_race_ids = df['race_id'].unique()
    for race_id in unique_race_ids:
        date_str = race_date_map.get(race_id)
        if not date_str:
            errors += 1
            continue
        try:
            race = load_race_fn(race_id, date_str)
            if mode == 'raw':
                margins = compute_race_margins(race.get('entries', []), cap=cap)
            else:
                margins = compute_race_margins_v2(
                    race.get('entries', []),
                    race_date=date_str,
                    sed_index=sed_index,
                    cap=cap,
                    furi_scale=furi_scale,
                    mode=mode,
                )
                # 不利補正が効いた馬数をカウント (adjusted系のみ)
                if mode in ('adjusted', 'adj_zscore') and sed_index:
                    for e in race.get('entries', []):
                        ketto = e.get('ketto_num')
                        if ketto:
                            sed_e = sed_index.get(f"{ketto}_{date_str}")
                            if sed_e and sed_e.get('furi_adj', 0) > 0:
                                n_furi_corrected += 1
            for umaban, margin in margins.items():
                margin_index[(race_id, umaban)] = margin
            processed += 1
        except Exception:
            errors += 1

    # DataFrameにマッピング
    df['target_margin'] = df.apply(
        lambda row: margin_index.get((row['race_id'], row['umaban']), float('nan')),
        axis=1,
    )

    valid = df['target_margin'].notna().sum()
    total = len(df)
    print(f"[Margin] mode={mode}, {processed:,} races processed, {errors} errors")
    print(f"[Margin] target_margin: {valid:,}/{total:,} valid ({valid/total*100:.1f}%)")
    if mode in ('adjusted', 'adj_zscore'):
        print(f"[Margin] furi corrected: {n_furi_corrected:,} horse-races (scale={furi_scale}s/unit)")

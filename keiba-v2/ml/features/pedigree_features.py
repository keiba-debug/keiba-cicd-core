#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
血統特徴量 (v5.12)

sire_stats_index.jsonから種牡馬(sire)・母馬(dam)・母父(bms)の
集計統計を特徴量として取得。

v5.8: H0(ベースライン) + H3(休み明け) + H4(間隔詰め) → 全モデルAUC改善
v5.9: + H5(瞬発/持続) + H6(成長曲線)
v5.11: + dam(母馬)統計量追加 — 母馬効果(遺伝+子宮環境+育成)を直接捕捉
v5.12: point-in-time対応（pit_*_tl使用時）
"""

import bisect
from typing import Dict, Tuple


# Bayesian smoothing constants (same as build_sire_stats.py)
_PRIOR_TOP3_ALPHA = 2.5
_PRIOR_TOP3_BETA = 7.5
_MIN_RUNS_CONDITIONAL = 10


def _bayesian_rate(successes: int, total: int) -> float:
    return round((successes + _PRIOR_TOP3_ALPHA) / (total + _PRIOR_TOP3_ALPHA + _PRIOR_TOP3_BETA), 4)


def build_sire_index(sire_stats: dict) -> Tuple[dict, dict, dict]:
    """sire_stats_index.jsonのsire/dam/bmsを辞書として返す

    Returns:
        (sire_index, dam_index, bms_index)
    """
    return (
        sire_stats.get('sire', {}),
        sire_stats.get('dam', {}),
        sire_stats.get('bms', {}),
    )


# 取得対象フィールド: (index内キー, 特徴量名prefix)
_SIRE_FIELDS = [
    ('top3_rate', 'top3_rate'),
    ('fresh_advantage', 'fresh_advantage'),
    ('tight_penalty', 'tight_penalty'),
    ('sprint_top3_rate', 'sprint_top3_rate'),
    ('sustained_top3_rate', 'sustained_top3_rate'),
    ('finish_type_pref', 'finish_type_pref'),
    ('young_top3_rate', 'young_top3_rate'),
    ('mature_top3_rate', 'mature_top3_rate'),
    ('maturity_index', 'maturity_index'),
]


def _pit_sire_lookup(timeline: dict, race_date: str) -> dict:
    """累積タイムラインからrace_date直前のスナップショットを取得し、レート計算

    timeline stores cumulative counts AFTER each date's races.
    bisect_left(dates, race_date) - 1 gives the latest date strictly before race_date.
    """
    if timeline is None:
        return None
    dates = timeline['dates']
    idx = bisect.bisect_left(dates, race_date) - 1
    if idx < 0:
        return None

    total = timeline['total'][idx]
    if total == 0:
        return None

    result = {
        'top3_rate': _bayesian_rate(timeline['top3'][idx], total),
    }

    # Normal rate (needed for fresh_advantage and tight_penalty)
    normal_runs = timeline['normal_runs'][idx]
    normal_rate = None
    if normal_runs >= _MIN_RUNS_CONDITIONAL:
        normal_rate = _bayesian_rate(timeline['normal_top3'][idx], normal_runs)

    # Fresh advantage
    fresh_runs = timeline['fresh_runs'][idx]
    if fresh_runs >= _MIN_RUNS_CONDITIONAL and normal_rate is not None:
        fresh_rate = _bayesian_rate(timeline['fresh_top3'][idx], fresh_runs)
        result['fresh_advantage'] = round(fresh_rate - normal_rate, 4)

    # Tight penalty
    tight_runs = timeline['tight_runs'][idx]
    if tight_runs >= _MIN_RUNS_CONDITIONAL and normal_rate is not None:
        tight_rate = _bayesian_rate(timeline['tight_top3'][idx], tight_runs)
        result['tight_penalty'] = round(tight_rate - normal_rate, 4)

    # Sprint / sustained
    sprint_rate = None
    sprint_runs = timeline['sprint_runs'][idx]
    if sprint_runs >= _MIN_RUNS_CONDITIONAL:
        sprint_rate = _bayesian_rate(timeline['sprint_top3'][idx], sprint_runs)
        result['sprint_top3_rate'] = sprint_rate

    sustained_rate = None
    sustained_runs = timeline['sustained_runs'][idx]
    if sustained_runs >= _MIN_RUNS_CONDITIONAL:
        sustained_rate = _bayesian_rate(timeline['sustained_top3'][idx], sustained_runs)
        result['sustained_top3_rate'] = sustained_rate

    if sprint_rate is not None and sustained_rate is not None:
        result['finish_type_pref'] = round(sprint_rate - sustained_rate, 4)

    # Young / mature
    young_rate = None
    young_runs = timeline['young_runs'][idx]
    if young_runs >= _MIN_RUNS_CONDITIONAL:
        young_rate = _bayesian_rate(timeline['young_top3'][idx], young_runs)
        result['young_top3_rate'] = young_rate

    mature_rate = None
    mature_runs = timeline['mature_runs'][idx]
    if mature_runs >= _MIN_RUNS_CONDITIONAL:
        mature_rate = _bayesian_rate(timeline['mature_top3'][idx], mature_runs)
        result['mature_top3_rate'] = mature_rate

    if young_rate is not None and mature_rate is not None:
        result['maturity_index'] = round(mature_rate - young_rate, 4)

    return result


def get_pedigree_features(
    ketto_num: str,
    pedigree_index: Dict[str, dict],
    sire_index: Dict[str, dict],
    dam_index: Dict[str, dict],
    bms_index: Dict[str, dict],
    race_date: str = None,
    pit_sire_tl: dict = None,
    pit_dam_tl: dict = None,
    pit_bms_tl: dict = None,
) -> dict:
    """馬のketto_numから血統特徴量を取得

    pit_*_tl + race_date が渡された場合はpoint-in-time safe。
    渡されない場合は従来の静的index（predict.py互換）。

    Args:
        ketto_num: 10桁馬ID
        pedigree_index: {ketto_num: {sire: hansyoku_num, dam: hansyoku_num, bms: hansyoku_num}}
        sire_index: {hansyoku_num: {top3_rate, fresh_advantage, ...}}
        dam_index: 同上
        bms_index: 同上
    """
    result = {}
    for _, feat_name in _SIRE_FIELDS:
        result[f'sire_{feat_name}'] = None
        result[f'dam_{feat_name}'] = None
        result[f'bms_{feat_name}'] = None

    ped = pedigree_index.get(ketto_num)
    if not ped:
        return result

    use_pit = pit_sire_tl is not None and race_date

    # Sire stats
    sire_id = ped.get('sire')
    if sire_id:
        if use_pit:
            s = _pit_sire_lookup(pit_sire_tl.get(sire_id), race_date)
            if s:
                for key, feat_name in _SIRE_FIELDS:
                    result[f'sire_{feat_name}'] = s.get(key)
        else:
            s = sire_index.get(sire_id)
            if s:
                for key, feat_name in _SIRE_FIELDS:
                    result[f'sire_{feat_name}'] = s.get(key)

    # Dam stats
    dam_id = ped.get('dam')
    if dam_id:
        if use_pit:
            d = _pit_sire_lookup((pit_dam_tl or {}).get(dam_id), race_date)
            if d:
                for key, feat_name in _SIRE_FIELDS:
                    result[f'dam_{feat_name}'] = d.get(key)
        else:
            d = dam_index.get(dam_id)
            if d:
                for key, feat_name in _SIRE_FIELDS:
                    result[f'dam_{feat_name}'] = d.get(key)

    # BMS stats
    bms_id = ped.get('bms')
    if bms_id:
        if use_pit:
            b = _pit_sire_lookup((pit_bms_tl or {}).get(bms_id), race_date)
            if b:
                for key, feat_name in _SIRE_FIELDS:
                    result[f'bms_{feat_name}'] = b.get(key)
        else:
            b = bms_index.get(bms_id)
            if b:
                for key, feat_name in _SIRE_FIELDS:
                    result[f'bms_{feat_name}'] = b.get(key)

    return result

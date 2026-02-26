#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
血統特徴量 (v5.11)

sire_stats_index.jsonから種牡馬(sire)・母馬(dam)・母父(bms)の
集計統計を特徴量として取得。

v5.8: H0(ベースライン) + H3(休み明け) + H4(間隔詰め) → 全モデルAUC改善
v5.9: + H5(瞬発/持続) + H6(成長曲線)
v5.11: + dam(母馬)統計量追加 — 母馬効果(遺伝+子宮環境+育成)を直接捕捉
"""

from typing import Dict, Tuple


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


def get_pedigree_features(
    ketto_num: str,
    pedigree_index: Dict[str, dict],
    sire_index: Dict[str, dict],
    dam_index: Dict[str, dict],
    bms_index: Dict[str, dict],
) -> dict:
    """馬のketto_numから血統特徴量を取得

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

    # Sire stats
    sire_id = ped.get('sire')
    if sire_id:
        s = sire_index.get(sire_id)
        if s:
            for key, feat_name in _SIRE_FIELDS:
                result[f'sire_{feat_name}'] = s.get(key)

    # Dam stats
    dam_id = ped.get('dam')
    if dam_id:
        d = dam_index.get(dam_id)
        if d:
            for key, feat_name in _SIRE_FIELDS:
                result[f'dam_{feat_name}'] = d.get(key)

    # BMS stats
    bms_id = ped.get('bms')
    if bms_id:
        b = bms_index.get(bms_id)
        if b:
            for key, feat_name in _SIRE_FIELDS:
                result[f'bms_{feat_name}'] = b.get(key)

    return result

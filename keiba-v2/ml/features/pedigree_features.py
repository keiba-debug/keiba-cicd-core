#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
血統特徴量 (v5.8)

sire_stats_index.jsonから種牡馬(sire)・母父(bms)の
集計統計を特徴量として取得。

v5.7のLabelEncoding直接投入は過学習で失敗。
v5.8では事前計算の統計量（ベイズ平滑化済み）を使用。
"""

from typing import Dict, Optional


def build_sire_index(sire_stats: dict) -> tuple:
    """sire_stats_index.jsonのsire/bmsを辞書として返す

    Returns:
        (sire_index, bms_index)
    """
    return sire_stats.get('sire', {}), sire_stats.get('bms', {})


def get_pedigree_features(
    ketto_num: str,
    pedigree_index: Dict[str, dict],
    sire_index: Dict[str, dict],
    bms_index: Dict[str, dict],
) -> dict:
    """馬のketto_numから血統特徴量を取得

    Args:
        ketto_num: 10桁馬ID
        pedigree_index: {ketto_num: {sire: hansyoku_num, bms: hansyoku_num}}
        sire_index: {hansyoku_num: {top3_rate, fresh_advantage, tight_penalty, ...}}
        bms_index: 同上
    """
    result = {
        'sire_top3_rate': None,
        'bms_top3_rate': None,
        'sire_fresh_advantage': None,
        'sire_tight_penalty': None,
        'bms_fresh_advantage': None,
        'bms_tight_penalty': None,
    }

    ped = pedigree_index.get(ketto_num)
    if not ped:
        return result

    # Sire stats
    sire_id = ped.get('sire')
    if sire_id:
        s = sire_index.get(sire_id)
        if s:
            result['sire_top3_rate'] = s.get('top3_rate')
            result['sire_fresh_advantage'] = s.get('fresh_advantage')
            result['sire_tight_penalty'] = s.get('tight_penalty')

    # BMS stats
    bms_id = ped.get('bms')
    if bms_id:
        b = bms_index.get(bms_id)
        if b:
            result['bms_top3_rate'] = b.get('top3_rate')
            result['bms_fresh_advantage'] = b.get('fresh_advantage')
            result['bms_tight_penalty'] = b.get('tight_penalty')

    return result

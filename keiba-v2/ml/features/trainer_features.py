#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教師特徴量

trainers.jsonから調教師統計を取得。
JRA-VAN 5桁コードで100%マッチ（v2の0.5%問題を解消）。
"""

from typing import Dict, Optional


def build_trainer_index(trainers_data: list) -> Dict[str, dict]:
    """trainers.jsonをcodeベースの辞書に変換"""
    return {t['code']: t for t in trainers_data}


def get_trainer_features(
    trainer_code: str,
    venue_code: str,
    trainer_index: Dict[str, dict],
) -> dict:
    """調教師コードから特徴量を取得"""
    result = {
        'trainer_win_rate': -1,
        'trainer_top3_rate': -1,
        'trainer_venue_top3_rate': -1,
        'trainer_total_runs': 0,
    }

    t = trainer_index.get(trainer_code)
    if t is None:
        return result

    result['trainer_win_rate'] = t.get('win_rate', 0)
    result['trainer_top3_rate'] = t.get('top3_rate', 0)
    result['trainer_total_runs'] = t.get('total_runs', 0)

    # 場所別成績
    venue_stats = t.get('venue_stats', {}).get(venue_code, {})
    if venue_stats.get('runs', 0) >= 10:
        result['trainer_venue_top3_rate'] = venue_stats.get('top3_rate', 0)

    return result

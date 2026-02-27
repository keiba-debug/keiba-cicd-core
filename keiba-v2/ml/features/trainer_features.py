#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教師特徴量

trainers.jsonから調教師統計を取得。
JRA-VAN 5桁コードで100%マッチ（v2の0.5%問題を解消）。

v5.12: point-in-time対応（pit_timeline使用時）
"""

import bisect
from typing import Dict, Optional


def build_trainer_index(trainers_data: list) -> Dict[str, dict]:
    """trainers.jsonをcodeベースの辞書に変換"""
    return {t['code']: t for t in trainers_data}


def _pit_lookup(timeline: dict, race_date: str, venue_code: str = None):
    """累積タイムラインからrace_date直前のスナップショットを取得

    timeline = {
        'dates': ['2020-01-05', ...],  # sorted
        'total': [5, ...],
        'wins':  [1, ...],
        'top3':  [2, ...],
        'venue': {vc: {'dates': [...], 'total': [...], 'wins': [...], 'top3': [...]}}
    }
    """
    dates = timeline['dates']
    idx = bisect.bisect_left(dates, race_date) - 1
    if idx < 0:
        return None

    result = {
        'total': timeline['total'][idx],
        'wins': timeline['wins'][idx],
        'top3': timeline['top3'][idx],
    }

    # 場所別
    if venue_code:
        vs = timeline.get('venue', {}).get(venue_code)
        if vs:
            v_idx = bisect.bisect_left(vs['dates'], race_date) - 1
            if v_idx >= 0:
                result['venue_total'] = vs['total'][v_idx]
                result['venue_wins'] = vs['wins'][v_idx]
                result['venue_top3'] = vs['top3'][v_idx]

    return result


def get_trainer_features(
    trainer_code: str,
    venue_code: str,
    trainer_index: Dict[str, dict],
    race_date: str = None,
    pit_timeline: Dict[str, dict] = None,
) -> dict:
    """調教師コードから特徴量を取得

    pit_timeline + race_date が渡された場合はpoint-in-time safe。
    渡されない場合は従来の静的index（predict.py互換）。
    """
    result = {
        'trainer_win_rate': -1,
        'trainer_top3_rate': -1,
        'trainer_venue_top3_rate': -1,
        'trainer_total_runs': 0,
    }

    # PIT mode
    if pit_timeline is not None and race_date:
        tl = pit_timeline.get(trainer_code)
        if tl is None:
            return result
        snap = _pit_lookup(tl, race_date, venue_code)
        if snap is None:
            return result

        total = snap['total']
        if total > 0:
            result['trainer_win_rate'] = round(snap['wins'] / total, 4)
            result['trainer_top3_rate'] = round(snap['top3'] / total, 4)
            result['trainer_total_runs'] = total

        v_total = snap.get('venue_total', 0)
        if v_total >= 10:
            result['trainer_venue_top3_rate'] = round(snap.get('venue_top3', 0) / v_total, 4)

        return result

    # Static mode (predict.py)
    t = trainer_index.get(trainer_code)
    if t is None:
        return result

    result['trainer_win_rate'] = t.get('win_rate', 0)
    result['trainer_top3_rate'] = t.get('top3_rate', 0)
    result['trainer_total_runs'] = t.get('total_runs', 0)

    venue_stats = t.get('venue_stats', {}).get(venue_code, {})
    if venue_stats.get('runs', 0) >= 10:
        result['trainer_venue_top3_rate'] = venue_stats.get('top3_rate', 0)

    return result

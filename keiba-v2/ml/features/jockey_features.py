#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
騎手特徴量（新規）

jockeys.jsonから騎手統計を取得。
JRA-VAN 5桁コードで100%マッチ。

v5.6: jockey_close_win_rate (接戦勝率)
v5.12: point-in-time対応（pit_timeline使用時）
"""

import bisect
from typing import Dict, Optional


def build_jockey_index(jockeys_data: list) -> Dict[str, dict]:
    """jockeys.jsonをcodeベースの辞書に変換"""
    return {j['code']: j for j in jockeys_data}


def _pit_lookup(timeline: dict, race_date: str, venue_code: str = None):
    """累積タイムラインからrace_date直前のスナップショットを取得"""
    dates = timeline['dates']
    idx = bisect.bisect_left(dates, race_date) - 1
    if idx < 0:
        return None

    result = {
        'total': timeline['total'][idx],
        'wins': timeline['wins'][idx],
        'top3': timeline['top3'][idx],
    }

    if venue_code:
        vs = timeline.get('venue', {}).get(venue_code)
        if vs:
            v_idx = bisect.bisect_left(vs['dates'], race_date) - 1
            if v_idx >= 0:
                result['venue_total'] = vs['total'][v_idx]
                result['venue_wins'] = vs['wins'][v_idx]
                result['venue_top3'] = vs['top3'][v_idx]

    # close finish stats
    close = timeline.get('close')
    if close:
        c_idx = bisect.bisect_left(close['dates'], race_date) - 1
        if c_idx >= 0:
            result['close_wins'] = close['wins'][c_idx]
            result['close_seconds'] = close['seconds'][c_idx]

    return result


def get_jockey_features(
    jockey_code: str,
    venue_code: str,
    jockey_index: Dict[str, dict],
    race_date: str = None,
    pit_timeline: Dict[str, dict] = None,
) -> dict:
    """騎手コードから特徴量を取得

    pit_timeline + race_date が渡された場合はpoint-in-time safe。
    渡されない場合は従来の静的index（predict.py互換）。
    """
    result = {
        'jockey_win_rate': -1,
        'jockey_top3_rate': -1,
        'jockey_venue_top3_rate': -1,
        'jockey_total_runs': 0,
        'jockey_close_win_rate': None,
    }

    # PIT mode
    if pit_timeline is not None and race_date:
        tl = pit_timeline.get(jockey_code)
        if tl is None:
            return result
        snap = _pit_lookup(tl, race_date, venue_code)
        if snap is None:
            return result

        total = snap['total']
        if total > 0:
            result['jockey_win_rate'] = round(snap['wins'] / total, 4)
            result['jockey_top3_rate'] = round(snap['top3'] / total, 4)
            result['jockey_total_runs'] = total

        v_total = snap.get('venue_total', 0)
        if v_total >= 10:
            result['jockey_venue_top3_rate'] = round(snap.get('venue_top3', 0) / v_total, 4)

        close_wins = snap.get('close_wins', 0)
        close_seconds = snap.get('close_seconds', 0)
        close_total = close_wins + close_seconds
        if close_total >= 10:
            result['jockey_close_win_rate'] = round(close_wins / close_total, 4)

        return result

    # Static mode (predict.py)
    j = jockey_index.get(jockey_code)
    if j is None:
        return result

    result['jockey_win_rate'] = j.get('win_rate', 0)
    result['jockey_top3_rate'] = j.get('top3_rate', 0)
    result['jockey_total_runs'] = j.get('total_runs', 0)

    venue_stats = j.get('venue_stats', {}).get(venue_code, {})
    if venue_stats.get('runs', 0) >= 10:
        result['jockey_venue_top3_rate'] = venue_stats.get('top3_rate', 0)

    close_total = j.get('close_total', 0)
    if close_total >= 10:
        result['jockey_close_win_rate'] = j.get('close_win_rate', 0)

    return result

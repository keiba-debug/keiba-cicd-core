#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
騎手特徴量（新規）

jockeys.jsonから騎手統計を取得。
JRA-VAN 5桁コードで100%マッチ。
"""

from typing import Dict, Optional


def build_jockey_index(jockeys_data: list) -> Dict[str, dict]:
    """jockeys.jsonをcodeベースの辞書に変換"""
    return {j['code']: j for j in jockeys_data}


def get_jockey_features(
    jockey_code: str,
    venue_code: str,
    jockey_index: Dict[str, dict],
) -> dict:
    """騎手コードから特徴量を取得"""
    result = {
        'jockey_win_rate': -1,
        'jockey_top3_rate': -1,
        'jockey_venue_top3_rate': -1,
        'jockey_total_runs': 0,
    }

    j = jockey_index.get(jockey_code)
    if j is None:
        return result

    result['jockey_win_rate'] = j.get('win_rate', 0)
    result['jockey_top3_rate'] = j.get('top3_rate', 0)
    result['jockey_total_runs'] = j.get('total_runs', 0)

    # 場所別成績
    venue_stats = j.get('venue_stats', {}).get(venue_code, {})
    if venue_stats.get('runs', 0) >= 10:
        result['jockey_venue_top3_rate'] = venue_stats.get('top3_rate', 0)

    return result

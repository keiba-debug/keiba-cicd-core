#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
出遅れ（スロースタート）特徴量 (v5.4)

keibabookの成績ページ「発走状況」から抽出した出遅れデータを使い、
馬ごとの出遅れ傾向をML特徴量として出力する。

データソース:
  kb_ext[entries][umaban]['is_slow_start'] = True
  （batch_scraper.py の scrape_seiseki() で設定）

特徴量:
  - horse_slow_start_rate: 過去レースでの出遅れ率
  - horse_slow_start_last5: 直近5走での出遅れ回数
  - horse_slow_start_resilience: 出遅れしても複勝圏に入った割合

注意: horse_history_cacheにumaban追加が必要（v5.4で追加）
"""


def compute_slow_start_features(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
    kb_ext_index: dict,
) -> dict:
    """馬の過去走から出遅れ傾向特徴量を計算。

    時系列リーク防止: race_date より前のレースのみ使用。
    """
    result = {
        'horse_slow_start_rate': -1.0,
        'horse_slow_start_last5': -1,
        'horse_slow_start_resilience': -1.0,
    }

    if not ketto_num or not kb_ext_index:
        return result

    runs = history_cache.get(ketto_num, [])
    past = [r for r in runs if r['race_date'] < race_date]

    if not past:
        return result

    # 出遅れ判定のあるレース（kb_extが存在するもの）のみカウント
    total_with_data = 0
    slow_count = 0
    slow_top3 = 0  # 出遅れしても複勝圏

    for r in past:
        race_id = r['race_id']
        umaban = r.get('umaban', 0)
        if not umaban:
            continue

        kb_ext = kb_ext_index.get(race_id)
        if not kb_ext:
            continue

        entry_data = kb_ext.get('entries', {}).get(str(umaban))
        if entry_data is None:
            continue

        # race_extras.hassou が存在するレース = 発走状況データあり
        has_hassou = bool(kb_ext.get('race_extras', {}).get('hassou'))
        if not has_hassou:
            continue

        total_with_data += 1
        if entry_data.get('is_slow_start'):
            slow_count += 1
            fp = r.get('finish_position', 99)
            num_runners = r.get('num_runners', 0)
            place_limit = 3 if num_runners >= 8 else (2 if num_runners >= 5 else 0)
            if fp <= place_limit:
                slow_top3 += 1

    # 全体出遅れ率
    if total_with_data >= 3:
        result['horse_slow_start_rate'] = round(slow_count / total_with_data, 4)
    elif total_with_data > 0:
        result['horse_slow_start_rate'] = round(slow_count / total_with_data, 4)

    # 直近5走の出遅れ回数
    last5_slow = 0
    last5_count = 0
    for r in reversed(past):
        if last5_count >= 5:
            break
        race_id = r['race_id']
        umaban = r.get('umaban', 0)
        if not umaban:
            continue
        kb_ext = kb_ext_index.get(race_id)
        if not kb_ext:
            continue
        entry_data = kb_ext.get('entries', {}).get(str(umaban))
        if entry_data is None:
            continue
        has_hassou = bool(kb_ext.get('race_extras', {}).get('hassou'))
        if not has_hassou:
            continue
        last5_count += 1
        if entry_data.get('is_slow_start'):
            last5_slow += 1

    if last5_count > 0:
        result['horse_slow_start_last5'] = last5_slow

    # 出遅れ時の複勝圏率（レジリエンス）
    if slow_count >= 2:
        result['horse_slow_start_resilience'] = round(slow_top3 / slow_count, 4)
    elif slow_count == 1:
        result['horse_slow_start_resilience'] = float(slow_top3)

    return result

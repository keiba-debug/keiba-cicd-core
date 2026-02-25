#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
出遅れ分析データ構築

kb_ext JSONの is_slow_start + race_extras.hassou から
騎手・馬の出遅れ傾向を集計し、Web分析ページ用のJSONを生成。

Usage:
    python -m builders.build_slow_start_analysis
"""

import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def _extract_hassou_excerpt(hassou_text: str, umaban: int) -> str:
    """hassouテキストから指定馬番の部分を抽出

    例: "(2)出遅れ１馬身不利　(7)ダッシュ付かず" → umaban=2 → "出遅れ１馬身不利"
    例: "(2)(16)出遅れ１馬身不利" → umaban=2 → "出遅れ１馬身不利"
    複数馬番がグループ化されている場合にも対応。
    """
    # (umaban) の後に続く (N) グループをスキップして説明テキストを取得
    pattern = rf'\({umaban}\)(?:\(\d+\))*([^(]*)'
    m = re.search(pattern, hassou_text)
    if m:
        return m.group(1).strip().rstrip('　 ')
    return ''


def _load_race_json(race_id: str) -> Optional[dict]:
    """race_idからレースJSONを読み込む"""
    # race_id: 16桁 YYYYMMDD...
    date_str = race_id[:8]
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:8]

    race_path = config.races_dir() / year / month / day / f"race_{race_id}.json"
    if race_path.exists():
        try:
            return json.loads(race_path.read_text(encoding='utf-8'))
        except Exception:
            pass
    return None


def _build_race_entry_index(race_data: dict) -> Dict[int, dict]:
    """レースJSONのentriesを馬番→エントリ辞書に変換"""
    index = {}
    for e in race_data.get('entries', []):
        umaban = e.get('umaban', 0)
        if umaban > 0:
            index[umaban] = e
    return index


def _extract_race_num(race_id: str) -> int:
    """race_idからレース番号を取得 (末尾2桁)"""
    try:
        return int(race_id[-2:])
    except (ValueError, IndexError):
        return 0


def build_slow_start_analysis() -> dict:
    """kb_ext + race JSONから出遅れ分析データを構築"""
    kb_dir = config.keibabook_dir()
    print(f"[SlowStart] Scanning {kb_dir}...")

    # 集計用
    def _new_year_bucket():
        return {'total': 0, 'slow': 0, 'fps_slow': [], 'fps_normal': []}

    jockey_stats = defaultdict(lambda: {
        'jockey_name': '',
        'total_rides': 0,
        'slow_starts': 0,
        'finish_positions_when_slow': [],
        'finish_positions_normal': [],
        'year_buckets': defaultdict(_new_year_bucket),
    })

    horse_stats = defaultdict(lambda: {
        'horse_name': '',
        'total_with_hassou': 0,
        'slow_count': 0,
        'finish_positions_when_slow': [],
        'year_buckets': defaultdict(lambda: {'total': 0, 'slow': 0}),
    })

    all_incidents = []

    race_count = 0
    entry_count = 0
    slow_count = 0
    race_cache = {}

    # kb_ext ファイルをスキャン
    for kb_file in sorted(kb_dir.rglob("kb_ext_*.json")):
        try:
            kb_data = json.loads(kb_file.read_text(encoding='utf-8'))
        except Exception:
            continue

        # hassouデータがなければスキップ（データ品質ルール）
        hassou = kb_data.get('race_extras', {}).get('hassou', '')
        if not hassou:
            continue

        race_id = kb_data.get('race_id', '')
        date = kb_data.get('date', '')
        if not race_id or not date:
            continue

        race_count += 1

        # レースJSON読み込み（キャッシュ）
        if race_id not in race_cache:
            race_cache[race_id] = _load_race_json(race_id)
        race_data = race_cache[race_id]

        race_entry_index = {}
        venue_name = ''
        race_name = ''
        num_runners = 0
        if race_data:
            race_entry_index = _build_race_entry_index(race_data)
            venue_name = race_data.get('venue_name', '')
            race_name = race_data.get('race_name', '')
            num_runners = race_data.get('num_runners', 0)

        race_num = _extract_race_num(race_id)
        entries = kb_data.get('entries', {})

        for umaban_str, entry_data in entries.items():
            try:
                umaban = int(umaban_str)
            except ValueError:
                continue

            # レースJSONからマッチするエントリを取得
            race_entry = race_entry_index.get(umaban, {})
            horse_name = race_entry.get('horse_name', '')
            ketto_num = race_entry.get('ketto_num', '')
            jockey_name = race_entry.get('jockey_name', '')
            jockey_code = race_entry.get('jockey_code', '')
            finish_position = race_entry.get('finish_position', 0)

            if not ketto_num:
                continue

            entry_count += 1
            is_slow = bool(entry_data.get('is_slow_start'))
            year = date[:4]

            # 騎手集計
            if jockey_code:
                js = jockey_stats[jockey_code]
                js['jockey_name'] = jockey_name or js['jockey_name']
                js['total_rides'] += 1
                yb = js['year_buckets'][year]
                yb['total'] += 1
                if is_slow:
                    js['slow_starts'] += 1
                    yb['slow'] += 1
                    if finish_position > 0:
                        js['finish_positions_when_slow'].append(finish_position)
                        yb['fps_slow'].append(finish_position)
                else:
                    if finish_position > 0:
                        js['finish_positions_normal'].append(finish_position)
                        yb['fps_normal'].append(finish_position)

            # 馬集計
            hs = horse_stats[ketto_num]
            hs['horse_name'] = horse_name or hs['horse_name']
            hs['total_with_hassou'] += 1
            hyb = hs['year_buckets'][year]
            hyb['total'] += 1

            if is_slow:
                slow_count += 1
                hs['slow_count'] += 1
                hyb['slow'] += 1
                if finish_position > 0:
                    hs['finish_positions_when_slow'].append(finish_position)

                hassou_excerpt = _extract_hassou_excerpt(hassou, umaban)

                incident = {
                    'date': date,
                    'venue_name': venue_name,
                    'race_num': race_num,
                    'umaban': umaban,
                    'horse_name': horse_name,
                    'ketto_num': ketto_num,
                    'jockey_name': jockey_name,
                    'jockey_code': jockey_code,
                    'finish_position': finish_position,
                    'num_runners': num_runners,
                    'hassou_excerpt': hassou_excerpt,
                }
                all_incidents.append(incident)

        if race_count % 2000 == 0:
            print(f"  ... {race_count:,} races processed")

    print(f"[SlowStart] {race_count:,} races with hassou, "
          f"{entry_count:,} entries, {slow_count:,} slow starts")

    # --- 集計結果を最終形式に変換 ---

    # 騎手ランキング（30騎乗以上）
    jockey_ranking = []
    for jc, js in jockey_stats.items():
        if js['total_rides'] < 30:
            continue
        fps_slow = js['finish_positions_when_slow']
        fps_normal = js['finish_positions_normal']
        top3_slow = sum(1 for fp in fps_slow if fp <= 3)
        top3_normal = sum(1 for fp in fps_normal if fp <= 3)

        # 年別統計
        year_stats = {}
        for y, yb in sorted(js['year_buckets'].items()):
            if yb['total'] == 0:
                continue
            yt3_slow = sum(1 for fp in yb['fps_slow'] if fp <= 3)
            yt3_normal = sum(1 for fp in yb['fps_normal'] if fp <= 3)
            year_stats[y] = {
                'total': yb['total'],
                'slow': yb['slow'],
                'rate': round(yb['slow'] / yb['total'], 4),
                'avg_fp_slow': round(sum(yb['fps_slow']) / len(yb['fps_slow']), 1)
                    if yb['fps_slow'] else None,
                'top3_slow': round(yt3_slow / len(yb['fps_slow']), 4)
                    if yb['fps_slow'] else None,
                'top3_normal': round(yt3_normal / len(yb['fps_normal']), 4)
                    if yb['fps_normal'] else None,
            }

        jockey_ranking.append({
            'jockey_code': jc,
            'jockey_name': js['jockey_name'],
            'total_rides': js['total_rides'],
            'slow_starts': js['slow_starts'],
            'slow_start_rate': round(js['slow_starts'] / js['total_rides'], 4)
                if js['total_rides'] > 0 else 0,
            'avg_finish_when_slow': round(sum(fps_slow) / len(fps_slow), 1)
                if fps_slow else None,
            'top3_rate_when_slow': round(top3_slow / len(fps_slow), 4)
                if fps_slow else None,
            'top3_rate_normal': round(top3_normal / len(fps_normal), 4)
                if fps_normal else None,
            'year_stats': year_stats,
        })
    jockey_ranking.sort(key=lambda x: x['slow_start_rate'], reverse=True)

    # 直近のインシデント（日付降順）
    all_incidents.sort(key=lambda x: (x['date'], x['venue_name'], x['race_num']),
                       reverse=True)

    # 馬の出遅れ統計（slow_count >= 1 のみ）
    horse_list = []
    for kn, hs in horse_stats.items():
        if hs['slow_count'] == 0:
            continue
        fps = hs['finish_positions_when_slow']
        top3 = sum(1 for fp in fps if fp <= 3)

        # 年別統計
        year_stats = {}
        for y, hyb in sorted(hs['year_buckets'].items()):
            if hyb['total'] == 0:
                continue
            year_stats[y] = {
                'total': hyb['total'],
                'slow': hyb['slow'],
            }

        horse_list.append({
            'ketto_num': kn,
            'horse_name': hs['horse_name'],
            'total_with_hassou': hs['total_with_hassou'],
            'slow_count': hs['slow_count'],
            'slow_start_rate': round(hs['slow_count'] / hs['total_with_hassou'], 4)
                if hs['total_with_hassou'] > 0 else 0,
            'avg_finish_when_slow': round(sum(fps) / len(fps), 1) if fps else None,
            'top3_when_slow': top3,
            'year_stats': year_stats,
        })
    horse_list.sort(key=lambda x: x['slow_start_rate'], reverse=True)

    # カバレッジ情報
    dates = [inc['date'] for inc in all_incidents if inc['date']]
    from_date = min(dates) if dates else ''
    to_date = max(dates) if dates else ''

    result = {
        'generated_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'coverage': {
            'from_date': from_date,
            'to_date': to_date,
            'races_with_hassou': race_count,
            'total_entries': entry_count,
            'total_slow_starts': slow_count,
        },
        'jockey_ranking': jockey_ranking,
        'recent_incidents': all_incidents,
        'horse_stats': horse_list,
    }

    return result


def main():
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Slow Start Analysis Builder")
    print(f"{'='*60}\n")

    t0 = time.time()

    result = build_slow_start_analysis()

    # 保存
    out_path = config.analysis_dir() / "slow_start_analysis.json"
    config.ensure_dir(config.analysis_dir())
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )

    elapsed = time.time() - t0

    cov = result['coverage']
    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Races with hassou: {cov['races_with_hassou']:,}")
    print(f"  Total entries:     {cov['total_entries']:,}")
    print(f"  Slow starts:       {cov['total_slow_starts']:,}")
    print(f"  Date range:        {cov['from_date']} ~ {cov['to_date']}")
    print(f"  Jockeys (30+ rides): {len(result['jockey_ranking']):,}")
    print(f"  Horses (1+ slow):  {len(result['horse_stats']):,}")
    print(f"  Output:            {out_path}")
    print(f"  Elapsed:           {elapsed:.1f}s")

    # Top 5 出遅れ率騎手
    print(f"\n  Top 5 jockey slow start rate:")
    for j in result['jockey_ranking'][:5]:
        print(f"    {j['jockey_name']:>8}: {j['slow_start_rate']:.1%} "
              f"({j['slow_starts']}/{j['total_rides']})")

    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

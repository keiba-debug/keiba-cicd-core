#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
race_*.json レース結果補完ツール

JRA-VAN SE_DATA バイナリ (C:/TFJV/SE_DATA) が TARGET 側で取得失敗していると、
build_race_master 経由では race_*.json の finish_position 等が 0 のまま残る。

このスクリプトは mykeibadb の umagoto_race_joho を二次ソースとして読み、
race_*.json の対象エントリを上書き更新する。

使い方:
    python -m builders.patch_race_results --date 2026-04-26
    python -m builders.patch_race_results --start 2026-04-26 --end 2026-05-02
    python -m builders.patch_race_results --date 2026-04-26 --dry-run

出力:
    各レースについて 補完件数 / スキップ件数 を標準出力。
    --dry-run の場合はファイル書き換えは行わない。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from core.config import data_root
from core.db import query


def _expand_dates(start: str, end: str) -> Iterable[str]:
    s = datetime.strptime(start, '%Y-%m-%d').date()
    e = datetime.strptime(end, '%Y-%m-%d').date()
    cur = s
    while cur <= e:
        yield cur.strftime('%Y-%m-%d')
        cur += timedelta(days=1)


def _race_dir(d: str) -> Path:
    y, m, dd = d.split('-')
    return data_root() / 'races' / y / m / dd


def _list_race_files(d: str) -> list[Path]:
    """日付配下の race_*.json (race_info.json は除外)"""
    rd = _race_dir(d)
    if not rd.exists():
        return []
    return sorted(rd.glob('race_[0-9]*.json'))


def _parse_int(raw: str | None) -> int:
    if raw is None:
        return 0
    s = str(raw).strip()
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _format_time(soha: str | None) -> str:
    """SOHA_TIME 4桁 'mssd' (m分ss.d秒) → '1:25.8'"""
    if not soha:
        return ''
    s = str(soha).strip()
    if len(s) != 4 or not s.isdigit():
        return ''
    minutes = int(s[0])
    seconds = int(s[1:3])
    tenths = int(s[3])
    return f'{minutes}:{seconds:02d}.{tenths}'


def _odds_value(raw: str | None) -> float:
    """TANSHO_ODDS char(4) → float (÷10)"""
    v = _parse_int(raw)
    return v / 10.0 if v > 0 else 0.0


def _decisec_to_sec(raw: str | None) -> float:
    """KOHAN_3F/4F: 100倍値（'331' → 33.1）"""
    v = _parse_int(raw)
    return v / 10.0 if v > 0 else 0.0


def _corner_list(row: dict) -> list[int]:
    """CORNER1..4_JUNI を 0埋め含む list[int] で返す。全0なら []"""
    arr = [
        _parse_int(row.get('CORNER1_JUNI')),
        _parse_int(row.get('CORNER2_JUNI')),
        _parse_int(row.get('CORNER3_JUNI')),
        _parse_int(row.get('CORNER4_JUNI')),
    ]
    if all(x == 0 for x in arr):
        return []
    return arr


# JRA-VAN 着差コード → 表示文字列
_CHAKUSA_MAP = {
    'AT ': 'アタマ', 'AT': 'アタマ',
    'HN ': 'ハナ', 'HN': 'ハナ',
    'KU ': 'クビ', 'KU': 'クビ',
    'DH ': '同着', 'DH': '同着',
    'OO ': '大差', 'OO': '大差',
}


def _format_chakusa(raw: str | None) -> str:
    if not raw:
        return ''
    s = str(raw).rstrip()
    if not s:
        return ''
    if s in _CHAKUSA_MAP:
        return _CHAKUSA_MAP[s]
    # 数値コード: '011' = 1, '015' = 1 1/2 等の処理は省略 (未補完で残す)
    return ''


def _fetch_results(race_code: str) -> dict[int, dict]:
    """指定race_code の馬ごと結果を {umaban: row} で返す"""
    rows = query(
        """
        SELECT UMABAN, KAKUTEI_CHAKUJUN, NYUSEN_JUNI, IJO_KUBUN_CODE,
               SOHA_TIME, KOHAN_3F, KOHAN_4F,
               TANSHO_ODDS, TANSHO_NINKIJUN,
               CORNER1_JUNI, CORNER2_JUNI, CORNER3_JUNI, CORNER4_JUNI,
               CHAKUSA_CODE1
        FROM umagoto_race_joho
        WHERE RACE_CODE = %s
        """,
        (race_code,),
    )
    out: dict[int, dict] = {}
    for r in rows:
        u = _parse_int(r.get('UMABAN'))
        if u > 0:
            out[u] = r
    return out


def _patch_entry(entry: dict, row: dict) -> bool:
    """1エントリを更新。何か変更したら True"""
    changed = False
    finish = _parse_int(row.get('KAKUTEI_CHAKUJUN'))
    if finish > 0 and entry.get('finish_position', 0) != finish:
        entry['finish_position'] = finish
        changed = True

    time_str = _format_time(row.get('SOHA_TIME'))
    if time_str and entry.get('time', '') != time_str:
        entry['time'] = time_str
        changed = True

    last3f = _decisec_to_sec(row.get('KOHAN_3F'))
    if last3f > 0 and entry.get('last_3f', 0.0) != last3f:
        entry['last_3f'] = last3f
        changed = True

    last4f = _decisec_to_sec(row.get('KOHAN_4F'))
    if last4f > 0 and entry.get('last_4f', 0.0) != last4f:
        entry['last_4f'] = last4f
        changed = True

    odds = _odds_value(row.get('TANSHO_ODDS'))
    if odds > 0 and entry.get('odds', 0.0) != odds:
        entry['odds'] = odds
        changed = True

    pop = _parse_int(row.get('TANSHO_NINKIJUN'))
    if pop > 0 and entry.get('popularity', 0) != pop:
        entry['popularity'] = pop
        changed = True

    corners = _corner_list(row)
    if corners and entry.get('corners') != corners:
        entry['corners'] = corners
        changed = True

    chakusa = _format_chakusa(row.get('CHAKUSA_CODE1'))
    if chakusa and entry.get('margin', '') != chakusa:
        entry['margin'] = chakusa
        changed = True

    return changed


def _patch_race_file(path: Path, dry_run: bool = False) -> tuple[int, int, int]:
    """1レース分を補完。戻り値: (更新エントリ数, スキップエントリ数, 結果なし=0)"""
    try:
        race = json.loads(path.read_text(encoding='utf-8'))
    except Exception as ex:  # noqa: BLE001
        print(f'  [SKIP] {path.name}: read error {ex}')
        return (0, 0, 0)

    race_id = race.get('race_id')
    if not race_id:
        # race_id 未設定 → ファイル名から復元
        race_id = path.stem.replace('race_', '')

    results = _fetch_results(race_id)
    if not results:
        return (0, 0, 0)

    updated = 0
    skipped = 0
    for entry in race.get('entries', []):
        u = entry.get('umaban', 0)
        row = results.get(u)
        if not row:
            skipped += 1
            continue
        if _patch_entry(entry, row):
            updated += 1
        else:
            skipped += 1

    if updated > 0 and not dry_run:
        path.write_text(
            json.dumps(race, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    return (updated, skipped, len(results))


def _process_date(d: str, dry_run: bool = False) -> dict:
    files = _list_race_files(d)
    if not files:
        print(f'[{d}] race_*.json なし')
        return {'races': 0, 'updated_entries': 0, 'updated_races': 0}

    total_updated_entries = 0
    updated_races = 0
    print(f'[{d}] {len(files)} レース処理開始 (dry_run={dry_run})')
    for f in files:
        u, s, total = _patch_race_file(f, dry_run=dry_run)
        if total == 0:
            print(f'  - {f.name}: mykeibadb未取込')
            continue
        if u > 0:
            updated_races += 1
            total_updated_entries += u
            print(f'  + {f.name}: 更新 {u}件 / スキップ {s}件')
    print(f'[{d}] 完了: {updated_races}/{len(files)}レース更新, {total_updated_entries}エントリ反映')
    return {
        'races': len(files),
        'updated_races': updated_races,
        'updated_entries': total_updated_entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='race_*.json をmykeibadbから補完')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--date', help='対象日 YYYY-MM-DD')
    g.add_argument('--start', help='範囲開始 YYYY-MM-DD (--end と併用)')
    ap.add_argument('--end', help='範囲終了 YYYY-MM-DD')
    ap.add_argument('--dry-run', action='store_true', help='変更内容を表示のみ')
    args = ap.parse_args()

    if args.start:
        if not args.end:
            print('--start には --end が必要', file=sys.stderr)
            return 2
        dates = list(_expand_dates(args.start, args.end))
    else:
        dates = [args.date]

    grand_updated_entries = 0
    grand_updated_races = 0
    for d in dates:
        r = _process_date(d, dry_run=args.dry_run)
        grand_updated_entries += r['updated_entries']
        grand_updated_races += r['updated_races']

    print(f'\n=== 全体集計: {grand_updated_races}レース更新, '
          f'{grand_updated_entries}エントリ反映 (dry_run={args.dry_run}) ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())

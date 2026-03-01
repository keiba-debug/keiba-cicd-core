#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
predictions.json フィールド名マイグレーション

旧名 → 新名 (Session 70 P/W/AR体系)
- pred_proba_v → pred_proba_p
- pred_proba_v_raw → pred_proba_p_raw
- rank_v → rank_p
- pred_proba_wv → pred_proba_w
- pred_proba_wv_cal → pred_proba_w_cal
- rank_wv → rank_w
- pred_proba_a, rank_a, pred_proba_w(旧) → 削除

Usage:
    python scripts/migrate_prediction_fields.py [--dry-run]
"""

import argparse
import json
import sys
from pathlib import Path

# フィールド名マッピング（旧 → 新）
RENAME_MAP = {
    'pred_proba_v': 'pred_proba_p',
    'pred_proba_v_raw': 'pred_proba_p_raw',
    'rank_v': 'rank_p',
    'pred_proba_wv': 'pred_proba_w',
    'pred_proba_wv_cal': 'pred_proba_w_cal',
    'rank_wv': 'rank_w',
}

# 削除するフィールド
DELETE_FIELDS = {'pred_proba_a', 'rank_a'}

# 旧名の pred_proba_w / rank_w は新名の pred_proba_wv / rank_wv に由来するので
# リネーム後に重複しないよう順序に注意
# 旧 pred_proba_w (市場モデル) は削除対象だが、
# 旧 pred_proba_wv が新 pred_proba_w になる。
# 旧JSONに pred_proba_w が存在する場合、これは旧市場モデルの値なので削除する。


def migrate_entry(entry: dict) -> dict:
    """1エントリのフィールド名をマイグレーション"""
    new_entry = {}
    for key, value in entry.items():
        if key in DELETE_FIELDS:
            continue  # 削除

        if key in RENAME_MAP:
            new_key = RENAME_MAP[key]
            new_entry[new_key] = value
        elif key == 'pred_proba_w' and 'pred_proba_wv' in entry:
            # 旧 pred_proba_w (市場モデル) → 削除
            # 旧 pred_proba_wv が新 pred_proba_w になる
            continue
        elif key == 'rank_w' and 'rank_wv' in entry:
            # 旧 rank_w (市場モデル) → 削除
            # 旧 rank_wv が新 rank_w になる
            continue
        else:
            new_entry[key] = value

    return new_entry


def needs_migration(entry: dict) -> bool:
    """旧フィールド名が存在するか"""
    return any(key in entry for key in RENAME_MAP) or any(key in entry for key in DELETE_FIELDS)


def migrate_file(filepath: Path, dry_run: bool = False) -> tuple[bool, int]:
    """1ファイルをマイグレーション

    Returns:
        (changed, entry_count)
    """
    with open(filepath, encoding='utf-8') as f:
        data = json.load(f)

    races = data.get('races', [])
    if not races:
        return False, 0

    # 既にマイグレーション済みかチェック
    first_entry = races[0].get('entries', [{}])[0] if races[0].get('entries') else {}
    if not needs_migration(first_entry):
        return False, 0

    total_entries = 0
    for race in races:
        entries = race.get('entries', [])
        race['entries'] = [migrate_entry(e) for e in entries]
        total_entries += len(entries)

    # recommendations内のentryも更新
    recs = data.get('recommendations', {})
    if isinstance(recs, dict):
        for preset_name, preset_recs in recs.items():
            if isinstance(preset_recs, list):
                for rec in preset_recs:
                    if 'entry' in rec and isinstance(rec['entry'], dict):
                        if needs_migration(rec['entry']):
                            rec['entry'] = migrate_entry(rec['entry'])

    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=None, separators=(',', ':'))

    return True, total_entries


def main():
    parser = argparse.ArgumentParser(description='Migrate prediction JSON field names')
    parser.add_argument('--dry-run', action='store_true', help='Check without modifying files')
    parser.add_argument('--path', default='C:/KEIBA-CICD/data3/races',
                        help='Root path to search for predictions.json')
    args = parser.parse_args()

    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    root = Path(args.path)
    files = sorted(root.glob('**/predictions.json'))

    print(f'Found {len(files)} predictions.json files')
    if args.dry_run:
        print('(DRY RUN - no files will be modified)')

    migrated = 0
    skipped = 0
    total_entries = 0

    for filepath in files:
        changed, entry_count = migrate_file(filepath, dry_run=args.dry_run)
        if changed:
            migrated += 1
            total_entries += entry_count
            rel = filepath.relative_to(root)
            print(f'  {"[DRY] " if args.dry_run else ""}Migrated: {rel} ({entry_count} entries)')
        else:
            skipped += 1

    print(f'\nDone: {migrated} migrated, {skipped} skipped (already up-to-date), {total_entries} entries total')

    # Also migrate predictions_live.json
    live_path = Path('C:/KEIBA-CICD/data3/ml/predictions_live.json')
    if live_path.exists():
        changed, entry_count = migrate_file(live_path, dry_run=args.dry_run)
        if changed:
            print(f'  {"[DRY] " if args.dry_run else ""}Migrated: predictions_live.json ({entry_count} entries)')
        else:
            print(f'  predictions_live.json: already up-to-date')


if __name__ == '__main__':
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRDBインデックス構築

SED（事後IDM）とKYI（事前IDM）をパースし、
KeibaCICDのketto_num(10桁)+race_dateで引けるインデックスを構築する。

出力:
  data3/indexes/jrdb_sed_index.json  — 事後IDM・指数（過去成績用）
  data3/indexes/jrdb_kyi_index.json  — 事前IDM・予測値（出走表用）

Usage:
    python -m builders.build_jrdb_index
    python -m builders.build_jrdb_index --years 2024-2025
    python -m builders.build_jrdb_index --type sed
    python -m builders.build_jrdb_index --type kyi
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jrdb.parser import parse_sed_line, parse_kyi_line

RAW_DIR = Path('C:/KEIBA-CICD/data3/jrdb/raw')
INDEX_DIR = Path('C:/KEIBA-CICD/data3/indexes')


def build_sed_index(year_range: range) -> dict:
    """SED全ファイル → {ketto_num_10}_{race_date} → 事後IDMデータ"""
    sed_dir = RAW_DIR / 'SED'
    if not sed_dir.exists():
        print(f"ERROR: {sed_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(sed_dir.glob('SED*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 370:
                continue
            try:
                r = parse_sed_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            kn10 = '20' + r['ketto_num_jrdb']
            race_date = r['race_date']
            if not race_date:
                continue

            key = f"{kn10}_{race_date}"

            # 事後IDMデータ + レース分析用フィールド
            # race_key info for race-level grouping
            rk = r['jrdb_race_key']
            venue_code = rk[0:2]
            race_num = int(rk[6:8]) if len(rk) >= 8 else 0

            index[key] = {
                'idm': r['idm'],
                'soten': r['soten'],
                'baba_sa': r['baba_sa'],
                'pace_adj': r['pace_adj'],
                'deokure_adj': r['deokure_adj'],
                'ichi_tori_adj': r['ichi_tori_adj'],
                'furi_adj': r['furi_adj'],
                'race_adj': r['race_adj'],
                'ten_idx': r['ten_idx'],
                'agari_idx': r['agari_idx'],
                'pace_idx': r['pace_idx'],
                'race_pace_idx': r['race_pace_idx'],
                'course_tori': r['course_tori'],
                'joushou_code': r['joushou_code'],
                'race_pace': r['race_pace'],
                'horse_pace': r['horse_pace'],
                'front_3f': r['front_3f'],
                'rear_3f': r['rear_3f'],
                # 前崩れ / レース質分析用
                'corner1': r['corner1'],
                'corner2': r['corner2'],
                'corner3': r['corner3'],
                'corner4': r['corner4'],
                'finish_position': r['finish_position'],
                'num_runners': r['num_runners'],
                'distance': r['distance'],
                'track_code': r['track_code'],
                'venue_code': venue_code,
                'race_num': race_num,
                'race_date': race_date,
            }

        file_count += 1

    print(f"[SED Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_kyi_index(year_range: range) -> dict:
    """KYI全ファイル → {ketto_num_10}_{race_date} → 事前IDMデータ"""
    kyi_dir = RAW_DIR / 'KYI'
    if not kyi_dir.exists():
        print(f"ERROR: {kyi_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    # KYIはレースキーから日付を推定する必要がある
    # KYIファイル名: KYI250301.txt → 2025-03-01
    for f in sorted(kyi_dir.glob('KYI*.txt')):
        fname = f.stem  # KYI250301
        yy = fname[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year not in year_range:
            continue

        # ファイル名から日付推定
        mmdd = fname[5:9]
        if len(mmdd) == 4:
            race_date = f"{year}-{mmdd[:2]}-{mmdd[2:]}"
        else:
            race_date = ''

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 620:
                continue
            try:
                r = parse_kyi_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            kn10 = '20' + r['ketto_num_jrdb']

            # KYIには日付フィールドがないのでファイル名から
            key = f"{kn10}_{race_date}"

            index[key] = {
                'pre_idm': r['pre_idm'],
                'jockey_idx': r['jockey_idx'],
                'info_idx': r['info_idx'],
                'sogo_idx': r['sogo_idx'],
                'training_idx': r['training_idx'],
                'stable_idx': r['stable_idx'],
                'gekisou_idx': r['gekisou_idx'],
                'pred_ten_idx': r['pred_ten_idx'],
                'pred_pace_idx': r['pred_pace_idx'],
                'pred_agari_idx': r['pred_agari_idx'],
                'pred_position_idx': r['pred_position_idx'],
                'pred_pace': r['pred_pace'],
                'kyakushitsu': r['kyakushitsu'],
                'distance_aptitude': r['distance_aptitude'],
                'base_odds': r['base_odds'],
                'base_popularity': r['base_popularity'],
                'start_idx': r['start_idx'],
                'deokure_rate': r['deokure_rate'],
            }

        file_count += 1

    print(f"[KYI Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def main():
    parser = argparse.ArgumentParser(description='Build JRDB Index')
    parser.add_argument('--years', default='2020-2025',
                        help='年度範囲 (例: 2020-2025)')
    parser.add_argument('--type', choices=['sed', 'kyi', 'all'], default='all',
                        help='構築対象 (sed/kyi/all)')
    args = parser.parse_args()

    # 年度範囲パース
    if '-' in args.years:
        start, end = args.years.split('-')
        year_range = range(int(start), int(end) + 1)
    else:
        year_range = range(int(args.years), int(args.years) + 1)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    if args.type in ('sed', 'all'):
        t0 = time.time()
        sed_index = build_sed_index(year_range)
        if sed_index:
            out = INDEX_DIR / 'jrdb_sed_index.json'
            out.write_text(json.dumps(sed_index, ensure_ascii=False), encoding='utf-8')
            size_mb = out.stat().st_size / 1024 / 1024
            print(f"  Saved: {out} ({size_mb:.1f} MB, {time.time()-t0:.1f}s)")

    if args.type in ('kyi', 'all'):
        t0 = time.time()
        kyi_index = build_kyi_index(year_range)
        if kyi_index:
            out = INDEX_DIR / 'jrdb_kyi_index.json'
            out.write_text(json.dumps(kyi_index, ensure_ascii=False), encoding='utf-8')
            size_mb = out.stat().st_size / 1024 / 1024
            print(f"  Saved: {out} ({size_mb:.1f} MB, {time.time()-t0:.1f}s)")


if __name__ == '__main__':
    main()

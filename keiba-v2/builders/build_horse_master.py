#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
馬マスターJSON構築

UM_DATA（馬マスタ）をスキャンして
data3/masters/horses/{ketto_num}.json を生成。

同時に data3/masters/horse_name_index.json（馬名→ketto_num逆引き）も構築。

Usage:
    python -m builders.build_horse_master [--dry-run]
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.jravan import um_parser
from core.jravan.um_parser import UM_RECORD_LEN
from core.models.horse import HorseMaster


def build_horse_masters(dry_run: bool = False):
    """全UM_DATAをスキャンして馬マスタJSONを生成"""
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Horse Master Builder")
    print(f"  Output: {config.horses_dir()}")
    print(f"  Dry run: {dry_run}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # 全UM_DATAファイルをスキャン（recent_n=0 で全件）
    print("[UM] Scanning all UM_DATA files...")
    um_files = um_parser.get_um_files(recent_n=0)
    print(f"[UM] Found {len(um_files)} UM files")

    horses: Dict[str, HorseMaster] = {}
    name_index: Dict[str, str] = {}
    file_count = 0

    for um_file in um_files:
        try:
            data = um_file.read_bytes()
        except Exception as e:
            print(f"  ERROR reading {um_file}: {e}")
            continue

        file_count += 1
        num = len(data) // UM_RECORD_LEN

        for i in range(num):
            offset = i * UM_RECORD_LEN
            rec = um_parser.parse_record(data, offset)
            if rec is None:
                continue

            # 最新レコードを優先（新しいファイルが先にスキャンされる）
            if rec.ketto_num in horses:
                continue

            horse = HorseMaster(
                ketto_num=rec.ketto_num,
                name=rec.name,
                name_kana=rec.name_kana,
                name_eng=rec.name_eng,
                birth_date=rec.birth_date,
                sex_cd=rec.sex_cd,
                sex_name=rec.sex_name,
                tozai_cd=rec.tozai_cd,
                tozai_name=rec.tozai_name,
                trainer_code=rec.trainer_code,
                trainer_name=rec.trainer_name,
                owner_name=rec.owner_name,
                breeder_name=rec.breeder_name,
                is_active=rec.is_active,
            )
            horses[rec.ketto_num] = horse

            if rec.name and rec.name not in name_index:
                name_index[rec.name] = rec.ketto_num

        if file_count % 10 == 0:
            print(f"  ... {file_count}/{len(um_files)} files, {len(horses):,} horses")

    print(f"[UM] Total: {len(horses):,} unique horses from {file_count} files")

    # 書き込み
    written = 0
    if not dry_run:
        horses_dir = config.ensure_dir(config.horses_dir())
        for ketto_num, horse in horses.items():
            filepath = horses_dir / f"{ketto_num}.json"
            filepath.write_text(
                json.dumps(horse.to_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            written += 1
            if written % 10_000 == 0:
                print(f"  ... {written:,} horse JSONs written")

        # 馬名インデックス
        index_path = config.masters_dir() / "horse_name_index.json"
        index_path.write_text(
            json.dumps(name_index, ensure_ascii=False, indent=0),
            encoding='utf-8',
        )
        print(f"[Index] horse_name_index.json: {len(name_index):,} entries")

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Horses:     {len(horses):,}")
    print(f"  Written:    {written:,} JSON files")
    print(f"  Name index: {len(name_index):,} entries")
    print(f"  Elapsed:    {elapsed:.1f}s")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Build horse master JSONs from UM_DATA')
    parser.add_argument('--dry-run', action='store_true', help='Count only, do not write files')
    args = parser.parse_args()

    build_horse_masters(dry_run=args.dry_run)


if __name__ == '__main__':
    main()

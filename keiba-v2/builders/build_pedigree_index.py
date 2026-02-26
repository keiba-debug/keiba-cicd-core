#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
血統インデックス構築 (v5.7)

UM_DATAから馬ごとの父(sire)・母父(broodmare sire)の
繁殖登録番号(HansyokuNum)を抽出して pedigree_index.json を生成。

ML特徴量としてLabelEncoding→LightGBM categorical_featureで使用。

Usage:
    python -m builders.build_pedigree_index
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.jravan import um_parser


def build_pedigree_index() -> Dict[str, Dict[str, str]]:
    """UM_DATAから血統インデックスを構築

    Returns:
        {ketto_num: {"sire": hansyoku_num, "bms": hansyoku_num}}
    """
    print("[UM] Scanning all UM_DATA files...")
    index = {}

    files = um_parser.get_um_files(0)  # 全ファイル
    print(f"  Found {len(files)} UM files")

    for um_file in files:
        try:
            data = um_file.read_bytes()
        except Exception:
            continue

        num = len(data) // 1609
        for i in range(num):
            offset = i * 1609
            rec = um_parser.parse_record(data, offset)
            if rec is None:
                continue

            ketto = rec.ketto_num
            if not ketto or ketto in index:
                continue

            entry = {}
            if rec.sire_num:
                entry['sire'] = rec.sire_num
            if rec.bms_num:
                entry['bms'] = rec.bms_num

            if entry:
                index[ketto] = entry

    print(f"[UM] {len(index):,} horses with pedigree data")

    # 統計
    sire_count = sum(1 for v in index.values() if 'sire' in v)
    bms_count = sum(1 for v in index.values() if 'bms' in v)
    unique_sires = len(set(v['sire'] for v in index.values() if 'sire' in v))
    unique_bms = len(set(v['bms'] for v in index.values() if 'bms' in v))

    print(f"  Sire coverage: {sire_count:,} ({unique_sires:,} unique sires)")
    print(f"  BMS coverage:  {bms_count:,} ({unique_bms:,} unique BMS)")

    return index


def main():
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Pedigree Index Builder")
    print(f"{'='*60}\n")

    t0 = time.time()

    index = build_pedigree_index()

    # 保存
    out_path = config.indexes_dir() / "pedigree_index.json"
    config.ensure_dir(config.indexes_dir())

    print(f"\n[Save] Writing {out_path}...")
    out_path.write_text(
        json.dumps(index, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )

    file_size = out_path.stat().st_size / 1024 / 1024
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Horses:    {len(index):,}")
    print(f"  File size: {file_size:.1f} MB")
    print(f"  Output:    {out_path}")
    print(f"  Elapsed:   {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

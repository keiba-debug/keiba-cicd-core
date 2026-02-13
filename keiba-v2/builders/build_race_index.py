#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レースインデックス構築

data3/races/ 配下のレースJSONをスキャンして
data3/indexes/race_date_index.json を生成。

構造: { "2024-01-06": ["race_id_1", "race_id_2", ...], ... }

Usage:
    python -m builders.build_race_index
"""

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def build_date_index() -> dict:
    """data3/races/ からレース日付インデックスを構築"""
    races_root = config.races_dir()
    print(f"[Index] Scanning {races_root}...")

    date_index = defaultdict(list)
    count = 0

    for json_file in races_root.rglob("race_[0-9]*.json"):
        try:
            data = json.loads(json_file.read_text(encoding='utf-8'))
            race_id = data['race_id']
            date = data['date']
            date_index[date].append(race_id)
            count += 1
        except Exception as e:
            print(f"  ERROR: {json_file}: {e}")

    # 各日付内のrace_idをソート
    for date in date_index:
        date_index[date].sort()

    # 日付順にソート
    sorted_index = dict(sorted(date_index.items()))

    print(f"[Index] {count:,} races across {len(sorted_index):,} dates")
    return sorted_index


def main():
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Race Date Index Builder")
    print(f"{'='*60}\n")

    t0 = time.time()

    date_index = build_date_index()

    # 保存
    out_path = config.indexes_dir() / "race_date_index.json"
    config.ensure_dir(config.indexes_dir())
    out_path.write_text(
        json.dumps(date_index, ensure_ascii=False, indent=0),
        encoding='utf-8',
    )

    elapsed = time.time() - t0

    # サマリ
    dates = sorted(date_index.keys())
    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Total dates:   {len(dates):,}")
    print(f"  Total races:   {sum(len(v) for v in date_index.values()):,}")
    print(f"  Date range:    {dates[0]} ~ {dates[-1]}")
    print(f"  Output:        {out_path}")
    print(f"  Elapsed:       {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

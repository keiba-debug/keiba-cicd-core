#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
馬名→ketto_num逆引きインデックス構築 (v2)

data3/masters/horses/ の全馬JSONを走査し、
馬名→ketto_numの辞書を構築します。

Usage:
    python -m builders.build_horse_name_index
    python -m builders.build_horse_name_index --info
    python -m builders.build_horse_name_index --name "ディープインパクト"
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def build_index() -> dict:
    """data3/masters/horsesから馬名インデックスを構築"""
    horses_dir = config.horses_dir()
    if not horses_dir.exists():
        print(f"[ERROR] horses dir not found: {horses_dir}")
        return {}

    print(f"  Scanning: {horses_dir}")

    name_to_id = {}
    duplicates = 0
    errors = 0

    json_files = sorted(horses_dir.glob("*.json"))
    total = len(json_files)
    print(f"  Found {total:,} horse files")

    # 高速化: regexで必要フィールドのみ抽出（完全JSONパースを回避）
    name_pat = re.compile(rb'"name"\s*:\s*"([^"]*)"')
    ketto_pat = re.compile(rb'"ketto_num"\s*:\s*"(\d+)"')

    for i, json_file in enumerate(json_files):
        try:
            raw = json_file.read_bytes()
            nm = name_pat.search(raw)
            km = ketto_pat.search(raw)
            if not nm or not km:
                continue

            name = nm.group(1).decode('utf-8').strip()
            ketto_num = km.group(1).decode('utf-8')
            if not name:
                continue

            if name in name_to_id:
                if ketto_num > name_to_id[name]:
                    name_to_id[name] = ketto_num
                duplicates += 1
            else:
                name_to_id[name] = ketto_num

        except Exception:
            errors += 1

        if (i + 1) % 50000 == 0:
            print(f"  ... {i+1:,}/{total:,}")

    print(f"  Unique names: {len(name_to_id):,}")
    print(f"  Duplicates (same name): {duplicates:,}")
    if errors:
        print(f"  Errors: {errors}")

    return name_to_id


def main():
    parser = argparse.ArgumentParser(description="Horse Name Index Builder (v2)")
    parser.add_argument("--info", action="store_true", help="Show index info")
    parser.add_argument("--name", type=str, help="Look up horse name")
    parser.add_argument("--build-index", action="store_true", help="Build index (default action)")
    args = parser.parse_args()

    output_path = config.indexes_dir() / "horse_name_index.json"

    if args.name:
        if not output_path.exists():
            print(f"[ERROR] Index not found: {output_path}")
            print("  Run: python -m builders.build_horse_name_index")
            return 1
        with open(output_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        name_map = index.get('name_to_id', {})
        ketto = name_map.get(args.name)
        if ketto:
            print(f"  {args.name} -> {ketto}")
        else:
            print(f"  {args.name}: not found")
        return 0

    if args.info:
        if not output_path.exists():
            print(f"[ERROR] Index not found: {output_path}")
            return 1
        with open(output_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        meta = index.get('metadata', {})
        print(f"  Created: {meta.get('created_at', '?')}")
        print(f"  Entries: {meta.get('total_names', '?')}")
        return 0

    # Build
    print("=" * 60)
    print("Horse Name Index Builder (v2)")
    print("=" * 60)

    name_to_id = build_index()
    if not name_to_id:
        return 1

    from datetime import datetime
    index_data = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/masters/horses",
            "total_names": len(name_to_id),
        },
        "name_to_id": name_to_id,
    }

    config.ensure_dir(output_path.parent)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Index saved: {output_path}")
    print(f"  Total names: {len(name_to_id):,}")
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"  Size: {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    exit(main())

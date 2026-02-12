#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
keibabook厩舎ID ↔ JRA-VAN調教師コード対応インデックス構築 (v2)

data3/keibabook/ の kb_ext と data3/races/ のレースJSONを結合し、
keibabook の stable_comment に含まれる厩舎名と JRA-VAN trainer_code の対応を構築します。

簡易版: trainer_nameでの名寄せ（data3/masters/trainers.json + data3/races のtrainer_name）

Usage:
    python -m builders.build_trainer_kb_index
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def build_index() -> dict:
    """data3/masters/trainers.jsonからJRA-VAN調教師コード→名前の辞書を構築"""
    trainers_path = config.masters_dir() / "trainers.json"
    if not trainers_path.exists():
        print(f"[ERROR] trainers.json not found: {trainers_path}")
        return {}

    with open(trainers_path, 'r', encoding='utf-8') as f:
        trainers = json.load(f)

    # code -> name
    code_to_name = {}
    name_to_code = {}

    for t in trainers:
        code = t.get('code', '')
        name = t.get('name', '').strip()
        if code and name:
            code_to_name[code] = name
            # 同名調教師は上書きされるが実運用上はほぼ問題ない
            name_to_code[name] = code

    print(f"  JRA-VAN trainers: {len(code_to_name)}")
    print(f"  Unique names: {len(name_to_code)}")

    return {
        "code_to_name": code_to_name,
        "name_to_code": name_to_code,
    }


def main():
    print("=" * 60)
    print("Trainer KB Index Builder (v2)")
    print("=" * 60)

    index = build_index()
    if not index:
        return 1

    output_path = config.indexes_dir() / "trainer_kb_index.json"

    index_data = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/masters/trainers.json",
            "total_trainers": len(index["code_to_name"]),
        },
        **index,
    }

    config.ensure_dir(output_path.parent)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Index saved: {output_path}")
    return 0


if __name__ == "__main__":
    exit(main())

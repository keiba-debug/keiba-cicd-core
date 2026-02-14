#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初期マイグレーション: 現在のファイルを versions/ に初期アーカイブ作成。

一度だけ実行。既にアーカイブ済みならスキップ（冪等）。

Usage:
    python -m scripts.migrate_versions
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.versioning import archive_before_save, archive_flat


def migrate_ml():
    """data3/ml/ の現在のモデルをアーカイブ"""
    ml_dir = config.ml_dir()
    meta_path = ml_dir / "model_meta.json"

    if not meta_path.exists():
        print("[ML] model_meta.json not found — skipping")
        return

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    version = meta.get("version", "unknown")

    print(f"[ML] Current version: {version}")
    archived = archive_before_save(
        base_dir=ml_dir,
        version=version,
        files=[
            "model_a.txt",
            "model_b.txt",
            "model_meta.json",
            "ml_experiment_v3_result.json",
        ],
        metadata={"created_at": meta.get("created_at", "")},
    )
    if archived:
        print(f"[ML] Archived v{version}")
    else:
        print(f"[ML] v{version} already archived — skipped")


def migrate_analysis():
    """data3/analysis/ の分析ファイルをアーカイブ"""
    analysis_dir = config.data_root() / "analysis"

    targets = [
        ("trainer_patterns.json", "metadata"),
        ("rating_standards.json", "metadata"),
        ("race_type_standards.json", "metadata"),
    ]

    for filename, meta_key in targets:
        fpath = analysis_dir / filename
        if not fpath.exists():
            print(f"[Analysis] {filename} not found — skipping")
            continue

        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            meta = data.get(meta_key, {})
            version = meta.get("version", "unknown")
        except Exception as e:
            print(f"[Analysis] {filename} read error: {e} — skipping")
            continue

        print(f"[Analysis] {filename} current version: {version}")
        archived = archive_flat(
            base_dir=analysis_dir,
            version=version,
            source_file=filename,
            metadata={"created_at": meta.get("created_at", "")},
        )
        if archived:
            print(f"[Analysis] Archived {filename} v{version}")
        else:
            print(f"[Analysis] {filename} v{version} already archived — skipped")


def main():
    print("=" * 60)
    print("Version Migration: Initial Archive")
    print("=" * 60)
    print()

    migrate_ml()
    print()
    migrate_analysis()

    print()
    print("=" * 60)
    print("[OK] Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    main()

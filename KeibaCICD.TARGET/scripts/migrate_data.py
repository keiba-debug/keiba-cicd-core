#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
データ移行スクリプト

KeibaCICD.TARGET/data -> KEIBA_DATA_ROOT_DIR/target へデータを移行します。
また、LOG_DIR -> KEIBA_DATA_ROOT_DIR/logs へログを移行します。

Usage:
    python migrate_data.py --dry-run        # ドライラン（実際には移行しない）
    python migrate_data.py                   # 実際に移行
    python migrate_data.py --force           # 既存ファイルを上書き
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

# 共通設定モジュールをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.config import (
    get_keiba_data_root,
    get_target_data_dir,
    get_log_dir,
    ensure_target_dirs
)


def get_old_target_data_dir() -> Path:
    """旧TARGETデータディレクトリを取得"""
    return Path(__file__).resolve().parents[1] / "data"


def get_old_log_dir() -> Path:
    """旧ログディレクトリを取得（環境変数LOG_DIRが指している場所）"""
    import os
    old_log = os.getenv("LOG_DIR")
    if old_log:
        return Path(old_log)
    return get_keiba_data_root() / "logs"


def scan_files(source_dir: Path) -> List[Path]:
    """ディレクトリ内のすべてのファイルをスキャン"""
    if not source_dir.exists():
        return []

    files = []
    for item in source_dir.rglob("*"):
        if item.is_file():
            files.append(item)
    return files


def migrate_files(
    source_dir: Path,
    target_dir: Path,
    dry_run: bool = True,
    force: bool = False
) -> Tuple[int, int, int]:
    """
    ファイルを移行する

    Returns:
        (copied_count, skipped_count, error_count)
    """
    if not source_dir.exists():
        print(f"Source directory does not exist: {source_dir}")
        return 0, 0, 0

    files = scan_files(source_dir)
    copied_count = 0
    skipped_count = 0
    error_count = 0

    print(f"\nFound {len(files)} files in {source_dir}")

    for file_path in files:
        # 相対パスを計算
        rel_path = file_path.relative_to(source_dir)
        dest_path = target_dir / rel_path

        # 既に存在する場合
        if dest_path.exists() and not force:
            print(f"  [SKIP] {rel_path} (already exists)")
            skipped_count += 1
            continue

        # ドライランの場合
        if dry_run:
            print(f"  [DRY] {rel_path} -> {dest_path}")
            copied_count += 1
            continue

        # 実際にコピー
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest_path)
            print(f"  [OK] {rel_path}")
            copied_count += 1
        except Exception as e:
            print(f"  [ERROR] {rel_path}: {e}")
            error_count += 1

    return copied_count, skipped_count, error_count


def main():
    parser = argparse.ArgumentParser(
        description="Migrate TARGET data to unified data directory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run (do not actually copy files)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing files"
    )
    parser.add_argument(
        "--skip-target",
        action="store_true",
        help="Skip TARGET data migration"
    )
    parser.add_argument(
        "--skip-logs",
        action="store_true",
        help="Skip log files migration"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("KeibaCICD Data Migration Tool")
    print("=" * 70)

    if args.dry_run:
        print("MODE: DRY RUN (no files will be copied)")
    else:
        print("MODE: PRODUCTION (files will be copied)")

    if args.force:
        print("FORCE: Enabled (existing files will be overwritten)")

    print()

    # 新しいディレクトリ構造を作成
    ensure_target_dirs()

    total_copied = 0
    total_skipped = 0
    total_errors = 0

    # 1. TARGETデータの移行
    if not args.skip_target:
        old_target_dir = get_old_target_data_dir()
        new_target_dir = get_target_data_dir()

        print("[1] TARGET Data Migration")
        print(f"    Source: {old_target_dir}")
        print(f"    Target: {new_target_dir}")

        copied, skipped, errors = migrate_files(
            old_target_dir,
            new_target_dir,
            args.dry_run,
            args.force
        )

        total_copied += copied
        total_skipped += skipped
        total_errors += errors

        print(f"\n    Copied: {copied}, Skipped: {skipped}, Errors: {errors}")

    # 2. ログファイルの移行
    if not args.skip_logs:
        old_log_dir = get_old_log_dir()
        new_log_dir = get_log_dir()

        # 移行先と移行元が同じ場合はスキップ
        if old_log_dir.resolve() == new_log_dir.resolve():
            print("\n[2] Log Files Migration")
            print(f"    Source and target are the same: {old_log_dir}")
            print("    Skipping log migration")
        else:
            print("\n[2] Log Files Migration")
            print(f"    Source: {old_log_dir}")
            print(f"    Target: {new_log_dir}")

            copied, skipped, errors = migrate_files(
                old_log_dir,
                new_log_dir,
                args.dry_run,
                args.force
            )

            total_copied += copied
            total_skipped += skipped
            total_errors += errors

            print(f"\n    Copied: {copied}, Skipped: {skipped}, Errors: {errors}")

    # 最終結果
    print("\n" + "=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"Total copied:  {total_copied}")
    print(f"Total skipped: {total_skipped}")
    print(f"Total errors:  {total_errors}")

    if args.dry_run:
        print("\nThis was a DRY RUN. Run without --dry-run to actually migrate files.")
    elif total_errors == 0:
        print("\nMigration completed successfully!")
    else:
        print(f"\nMigration completed with {total_errors} errors.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

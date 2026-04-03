#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""モデルバージョン切替スクリプト

アーカイブされたモデルファイルをアクティブディレクトリにコピーして切り替える。
現在のモデルは自動的にアーカイブされる。

Usage:
    python -m ml.switch_model polaris-2.0          # polaris-2.0に切替
    python -m ml.switch_model --list                # 利用可能バージョン一覧
    python -m ml.switch_model --current             # 現在のバージョン表示
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ML_DIR = Path("C:/KEIBA-CICD/data3/ml")
VERSIONS_DIR = ML_DIR / "versions"

# アーカイブ対象のモデルファイル
MODEL_FILES = [
    "model_p.txt",
    "model_w.txt",
    "model_ar.txt",
    "model_meta.json",
    "model_closing.txt",
    "model_closing_meta.json",
    "model_perf.txt",
    "model_perf_meta.json",
    "model_obstacle.txt",
    "model_obstacle_p.txt",
    "model_obstacle_w.txt",
    "model_obstacle_meta.json",
]


def get_current_version() -> str:
    meta_path = ML_DIR / "model_meta.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f).get("version", "unknown")
    return "unknown"


def list_versions() -> list[str]:
    if not VERSIONS_DIR.exists():
        return []
    versions = []
    for d in sorted(VERSIONS_DIR.iterdir()):
        if d.is_dir() and d.name.startswith("v"):
            meta = d / "model_meta.json"
            if meta.exists():
                versions.append(d.name[1:])  # strip 'v' prefix
    return versions


def archive_current():
    """現在のモデルをアーカイブ"""
    ver = get_current_version()
    if ver == "unknown":
        print("[WARN] 現在のバージョンが不明。アーカイブをスキップ")
        return

    dest = VERSIONS_DIR / f"v{ver}"
    dest.mkdir(parents=True, exist_ok=True)

    copied = 0
    for fname in MODEL_FILES:
        src = ML_DIR / fname
        if src.exists():
            shutil.copy2(str(src), str(dest / fname))
            copied += 1

    print(f"[Archive] v{ver} → {dest} ({copied} files)")


def switch_to(target_version: str):
    """指定バージョンに切替"""
    src_dir = VERSIONS_DIR / f"v{target_version}"
    if not src_dir.exists():
        print(f"[ERROR] バージョンディレクトリが見つかりません: {src_dir}")
        sys.exit(1)

    meta = src_dir / "model_meta.json"
    if not meta.exists():
        print(f"[ERROR] model_meta.json が見つかりません: {meta}")
        sys.exit(1)

    # 現在のモデルをアーカイブ
    current = get_current_version()
    if current != "unknown":
        archive_current()

    # ターゲットバージョンのファイルをコピー
    copied = 0
    missing = []
    for fname in MODEL_FILES:
        src = src_dir / fname
        if src.exists():
            shutil.copy2(str(src), str(ML_DIR / fname))
            copied += 1
        else:
            missing.append(fname)

    print(f"[Switch] v{current} → v{target_version} ({copied} files copied)")
    if missing:
        print(f"  [WARN] Missing in archive: {', '.join(missing)}")

    # 確認
    new_ver = get_current_version()
    print(f"  Active model: v{new_ver}")


def main():
    parser = argparse.ArgumentParser(description="モデルバージョン切替")
    parser.add_argument("version", nargs="?", help="切替先バージョン名 (例: polaris-2.0)")
    parser.add_argument("--list", action="store_true", help="利用可能バージョン一覧")
    parser.add_argument("--current", action="store_true", help="現在のバージョン表示")
    args = parser.parse_args()

    if args.current:
        ver = get_current_version()
        print(f"Current: v{ver}")
        return

    if args.list:
        current = get_current_version()
        versions = list_versions()
        print(f"Current: v{current}")
        print(f"Available ({len(versions)}):")
        for v in versions:
            marker = " ← active" if v == current else ""
            print(f"  v{v}{marker}")
        return

    if not args.version:
        parser.print_help()
        return

    target = args.version
    current = get_current_version()

    if target == current:
        print(f"Already on v{target}")
        return

    available = list_versions()
    if target not in available:
        print(f"[ERROR] v{target} は利用できません")
        print(f"Available: {', '.join(available)}")
        sys.exit(1)

    switch_to(target)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
archive から polaris live を復元する（set_active を使わないファイルコピー）。

レース中の registry 切替を避けつつ、live/ のモデルファイルだけ戻す。

Usage:
    python -m ml.restore_live polaris 2.3
    python -m ml.restore_live polaris 2.3 --dry-run
"""

import argparse
import io
import json
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config

LIVE_FILES = ["model_p.txt", "model_w.txt", "model_ar.txt", "calibrators.pkl", "meta.json"]


def restore_live(model_name: str, version: str, dry_run: bool = False) -> int:
    ml_dir = config.ml_dir()
    archive_dir = ml_dir / "models" / model_name / "archive" / f"v{version}"
    live_dir = ml_dir / "models" / model_name / "live"

    if not archive_dir.exists():
        print(f"[ERROR] archive not found: {archive_dir}")
        return 1

    print(f"[Restore] {archive_dir} → {live_dir}")
    for fname in LIVE_FILES:
        src = archive_dir / fname
        if not src.exists():
            print(f"  skip (missing): {fname}")
            continue
        dst = live_dir / fname
        if dry_run:
            print(f"  would copy: {fname}")
        else:
            live_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            print(f"  copied: {fname}")

    # 旧構造 ml_dir 直下も同期（predict 互換）
    if not dry_run:
        for fname in ["model_p.txt", "model_w.txt", "model_ar.txt", "calibrators.pkl"]:
            src = archive_dir / fname
            if src.exists():
                shutil.copy2(str(src), str(ml_dir / fname))
        meta_src = archive_dir / "meta.json"
        if meta_src.exists():
            shutil.copy2(str(meta_src), str(ml_dir / "model_meta.json"))

    print(f"  done (registry active_version は変更していません)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", help="モデル名 (polaris)")
    ap.add_argument("version", help="復元元バージョン (例: 2.3)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return restore_live(args.model, args.version, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
モデルバージョン切替スクリプト (Session 119)

archive/v{version}/ → live/ にコピーして active を切り替える。
学習失敗時のロールバックや、複数バージョンを比較する時に使う。

Usage:
    python -m ml.set_active polaris 2.1b           # アーカイブからactive切替
    python -m ml.set_active polaris --list         # archive一覧
    python -m ml.set_active polaris 2.2-pace-fix --dry-run  # 何が起きるか確認のみ
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


def list_archive(model_name: str):
    base = config.ml_dir() / "models" / model_name
    archive = base / "archive"
    live = base / "live"
    print(f"\n=== {model_name} ===")
    if live.exists() and (live / "meta.json").exists():
        m = json.loads((live / "meta.json").read_text(encoding="utf-8"))
        print(f"  [LIVE]    v{m.get('version', '?')}  ({m.get('created_at', '?')})")
    else:
        print(f"  [LIVE]    (none)")
    if not archive.exists():
        print(f"  [ARCHIVE] (空)")
        return
    versions = sorted(archive.iterdir())
    if not versions:
        print(f"  [ARCHIVE] (空)")
        return
    for v in versions:
        if not v.is_dir():
            continue
        meta_path = v / "meta.json"
        if meta_path.exists():
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            ver = m.get("version", v.name)
            created = m.get("created_at", "?")
            print(f"  [archive] v{ver}  ({created})  → {v.name}/")
        else:
            print(f"  [archive] (no meta) → {v.name}/")


def set_active(model_name: str, version: str, dry_run: bool = False) -> int:
    base = config.ml_dir() / "models" / model_name
    archive = base / "archive"
    live = base / "live"

    src = archive / f"v{version}"
    if not src.exists():
        # 数字だけ指定された場合 (例: 2.1b → v2.1b)
        for cand in archive.iterdir():
            if cand.name == version or cand.name == f"v{version}":
                src = cand
                break
        if not src.exists():
            print(f"[ERROR] archive に v{version} が見つかりません")
            print(f"  search: {archive}")
            list_archive(model_name)
            return 1

    # 切替前に現在の live を archive に退避（同名なら skip）
    if live.exists() and (live / "meta.json").exists():
        cur_meta = json.loads((live / "meta.json").read_text(encoding="utf-8"))
        cur_ver = cur_meta.get("version", "unknown")
        backup = archive / f"v{cur_ver}"
        if not backup.exists() and cur_ver != version:
            if dry_run:
                print(f"  [DRY] live(v{cur_ver}) → archive にバックアップ予定: {backup}")
            else:
                backup.mkdir(parents=True, exist_ok=True)
                for fname in ["model_p.txt", "model_w.txt", "model_ar.txt",
                              "calibrators.pkl", "meta.json"]:
                    s = live / fname
                    if s.exists():
                        shutil.copy2(str(s), str(backup / fname))
                print(f"  [Backup] live(v{cur_ver}) → {backup}")

    # archive から live にコピー
    print(f"  {'[DRY]' if dry_run else '[Activate]'} {src} → {live}")
    if dry_run:
        return 0

    live.mkdir(parents=True, exist_ok=True)
    for fname in ["model_p.txt", "model_w.txt", "model_ar.txt",
                  "calibrators.pkl", "meta.json"]:
        s = src / fname
        if s.exists():
            shutil.copy2(str(s), str(live / fname))
        else:
            print(f"  [WARN] {fname} not found in archive")

    new_meta = json.loads((live / "meta.json").read_text(encoding="utf-8"))
    print(f"\n  ✅ Active model: polaris v{new_meta.get('version', '?')}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", choices=["polaris", "enif", "eclipse"], nargs="?", default="polaris")
    ap.add_argument("version", nargs="?", help="切替先バージョン (例: 2.1b)")
    ap.add_argument("--list", action="store_true", help="archive一覧のみ")
    ap.add_argument("--dry-run", action="store_true", help="実行せず差分のみ表示")
    args = ap.parse_args()

    if args.list or not args.version:
        list_archive(args.model)
        return 0

    return set_active(args.model, args.version, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

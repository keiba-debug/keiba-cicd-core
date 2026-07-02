#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Polaris モデル昇格スクリプト (S184 世代検証フロー)

`experiment.py --save-archive-only` で archive/v{version}/ に隔離保存したモデルを、
shadow 世代検証 OK 後に live へ昇格する。逆方向 (ロールバック) も同じコマンドで可能
(旧 live は必ず archive に退避されるので、旧バージョンを指定し直せば戻る)。

やること (フル保存時の experiment.py と同じ配置):
  1. 現 live を models/polaris/archive/v{現version}/ に退避 (既存なら skip)
  2. archive/v{version}/ → models/polaris/live/ にコピー
  3. legacy root (data3/ml/model_*.txt, calibrators.pkl, model_meta.json) も更新
  4. registry の active_version を更新

Usage:
    python -m ml.promote_polaris --version 2.5          # dry-run (確認のみ)
    python -m ml.promote_polaris --version 2.5 --yes    # 実行
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config  # noqa: E402

FILES = ["model_p.txt", "model_w.txt", "model_ar.txt", "calibrators.pkl", "meta.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', required=True, help='昇格するバージョン (例: 2.5)')
    ap.add_argument('--yes', action='store_true', help='実行 (無指定は dry-run)')
    args = ap.parse_args()

    ml_dir = config.ml_dir()
    live_dir = ml_dir / "models" / "polaris" / "live"
    archive_root = ml_dir / "models" / "polaris" / "archive"
    src_dir = archive_root / f"v{args.version}"

    if not src_dir.exists():
        sys.exit(f"ERROR: {src_dir} がありません")
    missing = [f for f in FILES if not (src_dir / f).exists()]
    if missing:
        sys.exit(f"ERROR: {src_dir} に不足ファイル: {missing}")

    cur_meta = json.loads((live_dir / "meta.json").read_text(encoding='utf-8'))
    cur_ver = cur_meta.get('version', 'unknown')
    new_meta = json.loads((src_dir / "meta.json").read_text(encoding='utf-8'))
    print(f"現 live : v{cur_ver} (created {cur_meta.get('created_at')})")
    print(f"昇格対象: v{new_meta.get('version')} (created {new_meta.get('created_at')}, "
          f"split={new_meta.get('split')})")

    if not args.yes:
        print("\n[dry-run] --yes を付けると実行します")
        return

    # 1. 現 live を退避
    backup_dir = archive_root / f"v{cur_ver}"
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True)
        for f in FILES:
            src = live_dir / f
            if src.exists():
                shutil.copy2(str(src), str(backup_dir / f))
        print(f"[1/4] live(v{cur_ver}) を退避: {backup_dir}")
    else:
        print(f"[1/4] 退避先 {backup_dir} は既存 → skip (重み保全済み)")

    # 2. archive → live
    for f in FILES:
        shutil.copy2(str(src_dir / f), str(live_dir / f))
    print(f"[2/4] {src_dir} → {live_dir}")

    # 3. legacy root 更新 (旧構造フォールバック整合)
    for f in ["model_p.txt", "model_w.txt", "model_ar.txt", "calibrators.pkl"]:
        shutil.copy2(str(src_dir / f), str(ml_dir / f))
    shutil.copy2(str(src_dir / "meta.json"), str(ml_dir / "model_meta.json"))
    print(f"[3/4] legacy root ({ml_dir}) 更新")

    # 4. registry active 切替
    from ml.model_loader import set_active_version
    set_active_version("polaris", args.version)
    print(f"[4/4] registry active_version = {args.version}")
    print(f"\n完了: live は v{args.version}。ロールバックは "
          f"`python -m ml.promote_polaris --version {cur_ver} --yes`")


if __name__ == '__main__':
    main()

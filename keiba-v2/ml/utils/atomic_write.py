#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JSON ファイル全書き換え用 アトミック write (Session 129)

設計: docs/auto-purchase/shizune_review_session129.md 観点 K の延長

責務:
  - 任意の content (str / bytes) を tmp ファイル経由で書き込み、 fsync 後 rename
  - mkdir-based 排他ロックで同一 path への並行書込み防止
  - Windows でも動作 (os.replace で rename 競合回避)

なぜ jsonl_append.py と別か:
  - jsonl_append は「1 行 append (O_APPEND)」 専用
  - atomic_write は「ファイル全体を新内容で置き換え」 用 (ledger v2 の {date}.json 全書換に必須)
  - 用途が違うので分離

公開 API:
  write_text_atomic(path, content, *, encoding="utf-8", timeout_sec=5.0) -> bool
  write_json_atomic(path, data, *, indent=2, timeout_sec=5.0) -> bool
"""

from __future__ import annotations

import errno
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


_LOCK_POLL_SEC = 0.05


def _acquire_lock(lock_dir: Path, timeout_sec: float) -> bool:
    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            lock_dir.mkdir(parents=False, exist_ok=False)
            return True
        except FileExistsError:
            pass
        except OSError as e:
            if e.errno == errno.ENOENT:
                return False
            return False
        if time.monotonic() >= deadline:
            return False
        time.sleep(_LOCK_POLL_SEC)


def _release_lock(lock_dir: Path) -> None:
    try:
        lock_dir.rmdir()
    except Exception:
        pass


def write_text_atomic(
    path: Path | str,
    content: str,
    *,
    encoding: str = "utf-8",
    timeout_sec: float = 5.0,
    verbose: bool = False,
) -> bool:
    """テキストを atomic に書き込み: tmp 作成 → write+fsync → os.replace。

    Returns True=成功 / False=失敗。 例外は投げない (best-effort)。
    """
    path = Path(path)
    lock_dir = path.parent / f"{path.name}.lock"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        if verbose:
            print(f"[atomic_write] mkdir failed: {e}", file=sys.stderr)
        return False

    if not _acquire_lock(lock_dir, timeout_sec):
        print(f"[atomic_write] lock acquire timeout ({timeout_sec}s): {lock_dir}",
              file=sys.stderr)
        return False

    tmp_path: Path | None = None
    try:
        # 同一 dir に tmp 作って rename → cross-device move 回避
        fd, tmp_str = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
        )
        tmp_path = Path(tmp_str)
        try:
            data = content.encode(encoding)
            n = os.write(fd, data)
            if n != len(data):
                print(f"[atomic_write] partial write ({n}/{len(data)}): {path}",
                      file=sys.stderr)
                return False
            try:
                os.fsync(fd)
            except OSError as e:
                if verbose:
                    print(f"[atomic_write] fsync warning: {e}", file=sys.stderr)
        finally:
            os.close(fd)

        # os.replace は Windows でも既存ファイル上書き可能 (atomic)
        os.replace(str(tmp_path), str(path))
        tmp_path = None  # rename 成功 → cleanup 不要
        return True
    except Exception as e:
        print(f"[atomic_write] write failed: {type(e).__name__}: {e}: {path}",
              file=sys.stderr)
        return False
    finally:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        _release_lock(lock_dir)


def write_json_atomic(
    path: Path | str,
    data: Any,
    *,
    indent: int | None = 2,
    timeout_sec: float = 5.0,
    verbose: bool = False,
) -> bool:
    """JSON を atomic に書き込み。 ensure_ascii=False で日本語そのまま保存。"""
    try:
        content = json.dumps(data, ensure_ascii=False, indent=indent) + "\n"
    except (TypeError, ValueError) as e:
        print(f"[atomic_write] json.dumps failed: {e}", file=sys.stderr)
        return False
    return write_text_atomic(path, content, timeout_sec=timeout_sec, verbose=verbose)

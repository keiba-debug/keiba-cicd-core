#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JSONL アトミック追記 (Session 129 / シズネ指摘 K)

設計: docs/auto-purchase/shizune_review_session129.md 観点 K

背景:
  target_clicker `auto_vote.py:_audit()` (Session 128) は単純 append で
    - fsync なし (OS クラッシュで未フラッシュ行が消える)
    - ファイルロックなし (並行書込みでロストアップデート)
  だった。 TS 側は Session 126 で `lib/io/atomic-write.ts` を共通化済だが、
  Python 側 (target_clicker JSONL) は同じ穴のまま = 「同じ穴 3 つ目」 (シズネ命名)。

  税務 7 年保存要件 (14_LEDGER_SCHEMA.md) を満たすには、 監査ログの行欠損は
  「お金の経路の透明性」 を破る = 防衛ライン陥落。

  ledger v2 配線でも同じ穴を再発させないため、 ここで共通土台を作る。

責務:
  - JSONL 1 行を「行末改行付き UTF-8 + fsync + mkdir-based 排他ロック」 で追記
  - Windows / Linux 両対応 (msvcrt / fcntl 依存しない)
  - 失敗時は例外を投げず False を返す (本体停止防止)
  - lock 競合は最大 timeout_sec 秒リトライ

公開 API:
  append_jsonl(path, entry, *, timeout_sec=5.0) -> bool
"""

from __future__ import annotations

import errno
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


_LOCK_POLL_SEC = 0.05    # 50ms ごとにロック取得試行


def _acquire_lock(lock_dir: Path, timeout_sec: float) -> bool:
    """mkdir-based 排他ロック取得 (atomic な mkdir を利用)"""
    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            lock_dir.mkdir(parents=False, exist_ok=False)
            return True
        except FileExistsError:
            pass
        except OSError as e:
            # ENOENT (親 dir 不在) はリトライ不能
            if e.errno == errno.ENOENT:
                return False
            # その他 OSError もリトライ不能
            return False
        if time.monotonic() >= deadline:
            return False
        time.sleep(_LOCK_POLL_SEC)


def _release_lock(lock_dir: Path) -> None:
    try:
        lock_dir.rmdir()
    except Exception:
        pass


def append_jsonl(
    path: Path | str,
    entry: dict[str, Any],
    *,
    timeout_sec: float = 5.0,
    verbose: bool = False,
) -> bool:
    """JSONL ファイルに 1 エントリを安全に追記する。

    1. 親 dir を mkdir -p
    2. mkdir-based ロック取得 (timeout_sec までリトライ)
    3. os.open(O_APPEND | O_WRONLY | O_CREAT) で開く
    4. json.dumps(entry) + "\\n" を書き込み
    5. os.fsync で fdatasync (Windows は flushFileBuffers 相当)
    6. close + ロック解放

    Args:
        path: JSONL ファイルパス
        entry: 書き込む dict (json.dumps 可能であること)
        timeout_sec: ロック取得タイムアウト (デフォルト 5 秒)
        verbose: True で stderr にデバッグログ

    Returns:
        True = 成功 / False = 失敗 (例外は投げない)
    """
    path = Path(path)
    lock_dir = path.parent / f"{path.name}.lock"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        if verbose:
            print(f"[jsonl_append] mkdir failed: {e}", file=sys.stderr)
        return False

    if not _acquire_lock(lock_dir, timeout_sec):
        print(f"[jsonl_append] lock acquire timeout ({timeout_sec}s): {lock_dir}",
              file=sys.stderr)
        return False

    fd: int | None = None
    try:
        line = json.dumps(entry, ensure_ascii=False)
        data = (line + "\n").encode("utf-8")

        flags = os.O_APPEND | os.O_WRONLY | os.O_CREAT
        # Windows では O_BINARY が必要 (CRLF 変換抑制)
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY

        fd = os.open(str(path), flags, 0o644)
        n = os.write(fd, data)
        if n != len(data):
            # 部分書込み = ディスクフルなどの致命傷
            print(f"[jsonl_append] partial write ({n}/{len(data)}): {path}",
                  file=sys.stderr)
            return False

        try:
            os.fsync(fd)
        except OSError as e:
            # fsync 失敗 (Windows の一部 fs では非サポート) は warn のみ
            if verbose:
                print(f"[jsonl_append] fsync warning: {e}", file=sys.stderr)

        return True
    except Exception as e:
        print(f"[jsonl_append] write failed: {type(e).__name__}: {e}: {path}",
              file=sys.stderr)
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        _release_lock(lock_dir)

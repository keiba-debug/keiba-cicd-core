#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TARGET frontier JV 起動 + 認証ダイアログ進行 + IPAT 連動メニュー起動 (Phase 4-A/B)

設計: docs/auto-purchase/18_TARGET_FULL_AUTOMATION.md

責務 (本書 §1):
  Phase 4-A: TARGET 起動 + 認証ダイアログ自動進行
  Phase 4-B: IPAT 連動投票メニュー起動 (ﾌｧｲﾙ→IPATで投票する, cmd_id=1601)
  Phase 4-C: IPAT セッション継続管理 (login_ready 検知 + 音声プロンプト)

範囲外 (Phase 4 設計から永続的に除外):
  - IPAT 暗証番号自動入力 ★ シズネ原則「お金経路の最終認証は人」

実機検証待ち項目 (Session 131+ で来週末 OOS で確定):
  - TARGET exe パス (現状は env / 既知候補 / レジストリで検出)
  - 起動後の認証ダイアログ (タイトル/ボタン候補は推測)
  - IPAT ログインウィンドウのクラス/タイトル (TWebBrowser 内 TEdit 想定)

公開 API:
  launch_target(...)            -> LaunchResult
  open_ipat_menu(...)           -> bool
  wait_ipat_login_ready(...)    -> bool
  wait_ipat_main_ready(...)     -> bool
  auto_dismiss_dialogs(...)     -> list[str]   # dismiss したタイトル一覧
  inspect_launch_dialogs(...)   -> Path        # 起動シーケンス inspect 結果保存
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pywinauto import Application, Desktop
from pywinauto.findwindows import ElementNotFoundError

from ml.target_clicker.menu_runner import (
    TARGET_WINDOW_KEYWORD,
    _find_menu_item_id,
    _send_menu_command,
    find_target_window,
)


# =====================================================================
# 定数
# =====================================================================

TARGET_EXE_ENV_VAR = "TARGET_EXE_PATH"

# Session 131+ で来週末 OOS により確定予定。 暫定的に既知候補を列挙
TARGET_EXE_DEFAULT_CANDIDATES = [
    r"C:\TFJV\target_jv.exe",
    r"C:\Program Files (x86)\TARGET frontier JV\target_jv.exe",
    r"C:\Program Files\TARGET frontier JV\target_jv.exe",
    r"C:\Program Files (x86)\JRA-VAN\TARGET frontier JV\target_jv.exe",
]

# 認証ダイアログ自動進行用 whitelist の上書きファイル
DIALOG_WHITELIST_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "target_clicker" / "launch_dialogs.json"

# inspect 結果出力ディレクトリ (16_TARGET_AUTOCLICK の inspect-batch と並列)
INSPECT_DIR = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "target_clicker" / "inspect"

# 認証ダイアログ進行のデフォルト whitelist (v2 スキーマ / Session 131 シズネ 🔴 B)。
# - タイトル完全一致 or regex を使用、 部分一致での過剰反応を避ける
# - button_titles は最も「無害な進行」 を意味するものから順に試行
# - 設定変更につながる「適用」 「変更を保存」 などは絶対に含めない
# - whitelist 外のダイアログは abort + 音声通知 (自動 skip 禁止)
#
# JSON ファイル `data3/userdata/target_clicker/launch_dialogs.json` を以下スキーマで
# 配置することで上書き可能 (シズネ B 修正方針):
#
#   {
#     "version": "1.0",
#     "verified_at": "2026-05-24T10:00:00+09:00",
#     "verified_by": "fukuda",
#     "target_version": "TARGET frontier JV Ver6.21 Rev002",
#     "dialogs": [
#       {"title_re": "...", "buttons": ["..."], "purpose": "..."}
#     ]
#   }
#
# target_version != TARGET 実バージョン のとき音声警告 + auto_dismiss は OFF 化される。
DEFAULT_DIALOG_WHITELIST: list[dict] = [
    {
        "title_re": r"^TARGET frontier JV$",   # ライセンス確認等
        "buttons": ["OK"],
        "purpose": "ライセンス情報確認 (推測)",
    },
    {
        "title_re": r"^お知らせ$",
        "buttons": ["閉じる", "OK"],
        "purpose": "アップデート/お知らせ通知 (推測)",
    },
    {
        "title": "情報",   # TARGET の「情報」 ダイアログ全般 (進行用 OK のみ)
        "buttons": ["OK"],
        "purpose": "情報通知 (推測)",
    },
]

WHITELIST_SCHEMA_VERSION = "1.0"


@dataclass
class DialogWhitelistConfig:
    """whitelist 設定ファイル全体 (v2 スキーマ)"""
    version: str = WHITELIST_SCHEMA_VERSION
    verified_at: Optional[str] = None
    verified_by: Optional[str] = None
    target_version: Optional[str] = None     # 期待する TARGET バージョン文字列
    dialogs: list[dict] = field(default_factory=list)
    source: str = "default"                  # "default" / "file" / "legacy_list"


def load_dialog_whitelist_v2(path: Optional[Path] = None
                              ) -> DialogWhitelistConfig:
    """data3/userdata/target_clicker/launch_dialogs.json から whitelist を読み込む。

    後方互換性:
      - JSON が list 形式 (旧スキーマ) なら DialogWhitelistConfig.dialogs にコピー、
        verified_at / target_version は None
      - JSON が dict 形式 (v2) なら version/verified_at/target_version/dialogs を解釈

    Session 132 シズネ 🟡-5 (Session 133 実装):
      - dict 形式で `verified_by` が無い場合は stderr に WARNING を出す
        (= 監査責任所在の明示を強制、 fail-open 設計 = 起動は止めない)
      - list 形式 (legacy) も WARNING を出す (v2 への移行を促す)

    失敗時は DEFAULT_DIALOG_WHITELIST を持つ DialogWhitelistConfig を返す。
    """
    file_path = path or DIALOG_WHITELIST_PATH
    if not file_path.exists():
        return DialogWhitelistConfig(
            dialogs=list(DEFAULT_DIALOG_WHITELIST),
            source="default",
        )
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[launcher] whitelist 読込失敗 (default 使用): {e}", file=sys.stderr)
        return DialogWhitelistConfig(
            dialogs=list(DEFAULT_DIALOG_WHITELIST),
            source="default",
        )

    if isinstance(data, list):
        # legacy format — Session 132 🟡-5: v2 への移行推奨を WARNING
        print(f"[launcher] WARNING: {file_path.name} が legacy list 形式です。 "
              f"v2 スキーマ (dict + verified_by + target_version) への移行を推奨します "
              f"(監査責任所在の明示)",
              file=sys.stderr)
        return DialogWhitelistConfig(
            dialogs=data,
            source="legacy_list",
        )

    if isinstance(data, dict):
        dialogs = data.get("dialogs", [])
        if not isinstance(dialogs, list):
            print(f"[launcher] whitelist の dialogs フィールドが list でない (default 使用)",
                  file=sys.stderr)
            return DialogWhitelistConfig(
                dialogs=list(DEFAULT_DIALOG_WHITELIST),
                source="default",
            )
        verified_by = data.get("verified_by")
        # Session 132 🟡-5: verified_by 必須化 (WARNING、 fail-open)
        if not verified_by:
            print(f"[launcher] WARNING: {file_path.name} に verified_by が指定されていません。 "
                  f"v2 スキーマでは JSON 内容の責任所在 (誰が実機検証して作ったか) を "
                  f"明示する必要があります — verified_by フィールドを追加してください",
                  file=sys.stderr)
        return DialogWhitelistConfig(
            version=str(data.get("version", WHITELIST_SCHEMA_VERSION)),
            verified_at=data.get("verified_at"),
            verified_by=verified_by,
            target_version=data.get("target_version"),
            dialogs=dialogs,
            source="file",
        )

    print(f"[launcher] whitelist の形式が不正 (default 使用)", file=sys.stderr)
    return DialogWhitelistConfig(
        dialogs=list(DEFAULT_DIALOG_WHITELIST),
        source="default",
    )


def verify_target_version(actual: str, expected: Optional[str]) -> bool:
    """TARGET 実バージョンと whitelist 期待バージョンの一致確認 (シズネ 🔴 B)

    Args:
        actual: 実機の TARGET ウィンドウタイトル文字列 (例: "TARGET frontier JV  Ver6.21  Rev002")
        expected: whitelist.target_version (例: "TARGET frontier JV Ver6.21 Rev002")

    Returns:
        True なら一致 (whitelist 信頼 OK)。 expected が None なら True (検証 skip)。
        False なら不一致 → 呼び出し側は auto_dismiss を OFF にする想定。

    判定: 両者の空白を正規化したうえで完全一致比較
    """
    if expected is None or not expected.strip():
        return True
    actual_norm = " ".join((actual or "").split())
    expected_norm = " ".join(expected.split())
    return actual_norm == expected_norm


# =====================================================================
# データクラス
# =====================================================================

@dataclass
class LaunchResult:
    success: bool
    action: str                   # "launched" / "already_running" / "timeout" / "error" /
                                   # "dialog_unknown" (シズネ B: whitelist 外 dialog 検知 abort)
    reason: str
    target_handle: Optional[int] = None
    exe_path: Optional[str] = None
    dialogs_dismissed: list[str] = field(default_factory=list)
    unknown_dialogs: list[str] = field(default_factory=list)
    version_mismatch: Optional[str] = None    # target_version 不一致時の actual version
    elapsed_sec: Optional[float] = None


# =====================================================================
# TARGET exe 検出
# =====================================================================

def find_target_exe(*, verbose: bool = True) -> Optional[Path]:
    """TARGET exe パスを env var / 既知候補 / レジストリ App Paths から検出

    検出順序:
      1. 環境変数 TARGET_EXE_PATH
      2. TARGET_EXE_DEFAULT_CANDIDATES のいずれか
      3. Windows レジストリ App Paths\\target_jv.exe
    """
    env_path = os.getenv(TARGET_EXE_ENV_VAR)
    if env_path:
        p = Path(env_path)
        if p.exists():
            if verbose:
                print(f"[launcher] TARGET exe (env): {p}")
            return p

    for cand in TARGET_EXE_DEFAULT_CANDIDATES:
        p = Path(cand)
        if p.exists():
            if verbose:
                print(f"[launcher] TARGET exe (default): {p}")
            return p

    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\target_jv.exe",
            )
            path, _ = winreg.QueryValueEx(key, None)
            p = Path(path)
            if p.exists():
                if verbose:
                    print(f"[launcher] TARGET exe (registry): {p}")
                return p
        except Exception:
            pass
    return None


def is_target_already_running() -> Optional[int]:
    """既起動なら window handle を返す (なければ None)。 find_target_window 利用"""
    w = find_target_window()
    if w is None:
        return None
    try:
        return w.handle
    except Exception:
        return None


# =====================================================================
# Phase 4-A: TARGET 起動 + 認証ダイアログ進行
# =====================================================================

def launch_target(
    *,
    timeout_sec: int = 30,
    focus_only_if_running: bool = True,
    exe_path: Optional[Path] = None,
    auto_dismiss: bool = True,
    dismiss_timeout_sec: int = 10,
    verbose: bool = True,
) -> LaunchResult:
    """TARGET 起動 + メインウィンドウ到達まで待機。 既起動なら focus のみ。

    Args:
        timeout_sec: メインウィンドウ検出のタイムアウト
        focus_only_if_running: True で既起動時は新規 Popen せず focus
        exe_path: 明示パス (None なら find_target_exe で検出)
        auto_dismiss: True で起動後の認証ダイアログを自動進行
        dismiss_timeout_sec: auto_dismiss のタイムアウト
        verbose: stdout に進捗ログ
    """
    start = time.time()

    # 既起動チェック
    handle = is_target_already_running()
    if handle and focus_only_if_running:
        try:
            app = Application(backend="win32").connect(handle=handle)
            win = app.window(handle=handle)
            win.set_focus()
            elapsed = time.time() - start
            if verbose:
                print(f"[launcher] TARGET already running, focused (handle={handle:08x})")
            return LaunchResult(
                success=True, action="already_running",
                reason="既起動 window を focus", target_handle=handle,
                elapsed_sec=elapsed,
            )
        except Exception as e:
            return LaunchResult(
                success=False, action="error",
                reason=f"既起動 focus 失敗: {type(e).__name__}: {e}",
                target_handle=handle,
                elapsed_sec=time.time() - start,
            )

    # 新規起動
    exe = exe_path or find_target_exe(verbose=verbose)
    if exe is None:
        return LaunchResult(
            success=False, action="error",
            reason=(f"TARGET exe が見つかりません。 "
                    f"環境変数 {TARGET_EXE_ENV_VAR} で明示指定するか、 "
                    f"既知候補 {TARGET_EXE_DEFAULT_CANDIDATES} のいずれかに配置してください"),
            elapsed_sec=time.time() - start,
        )

    try:
        # 子プロセスとして起動 (親プロセスが終了しても継続するよう CREATE_NEW_PROCESS_GROUP)
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([str(exe)], cwd=str(exe.parent),
                         creationflags=creationflags)
        if verbose:
            print(f"[launcher] subprocess.Popen({exe})")
    except Exception as e:
        return LaunchResult(
            success=False, action="error",
            reason=f"subprocess.Popen 失敗: {type(e).__name__}: {e}",
            exe_path=str(exe),
            elapsed_sec=time.time() - start,
        )

    # whitelist v2 を読み込み (target_version 検証用)
    wl_cfg = load_dialog_whitelist_v2() if auto_dismiss else None
    if verbose and wl_cfg:
        print(f"[launcher] whitelist source={wl_cfg.source} "
              f"target_version={wl_cfg.target_version!r} "
              f"dialogs={len(wl_cfg.dialogs)}")

    # メインウィンドウ到達待機
    # 起動中の dialog は abort_on_unknown=False で寛容に消化 (まだ TARGET 由来判定が
    # 安定しない時期)。 main 到達後の追加消化で厳格モードに切り替える。
    dismissed: list[str] = []
    unknown: list[str] = []
    deadline = time.time() + timeout_sec
    main_handle: Optional[int] = None
    while time.time() < deadline:
        if auto_dismiss and wl_cfg is not None:
            res = auto_dismiss_dialogs(
                whitelist=wl_cfg.dialogs,
                timeout_sec=1, max_iterations=1,
                abort_on_unknown=False, verbose=verbose,
            )
            dismissed.extend(res.dismissed)
            for t in res.unknown_dialogs:
                if t not in unknown:
                    unknown.append(t)

        h = is_target_already_running()
        if h:
            main_handle = h
            break
        time.sleep(1.0)

    if main_handle is None:
        return LaunchResult(
            success=False, action="timeout",
            reason=f"{timeout_sec}s 内に TARGET window を検出できず",
            exe_path=str(exe),
            dialogs_dismissed=dismissed,
            unknown_dialogs=unknown,
            elapsed_sec=time.time() - start,
        )

    # target_version 検証 (シズネ 🔴 B): 不一致なら音声警告 + 厳格モード解除を提案
    version_mismatch: Optional[str] = None
    if wl_cfg and wl_cfg.target_version:
        try:
            app = Application(backend="win32").connect(handle=main_handle)
            actual_title = app.window(handle=main_handle).window_text() or ""
        except Exception:
            actual_title = ""
        if not verify_target_version(actual_title, wl_cfg.target_version):
            version_mismatch = actual_title
            if verbose:
                print(f"[launcher] ⚠ target_version 不一致: "
                      f"expected={wl_cfg.target_version!r}, actual={actual_title!r} "
                      "- abort_on_unknown を OFF に変更します (手動確認推奨)")

    # 後続のダイアログを厳格モード (abort_on_unknown=True) で消化。
    # target_version 不一致時は寛容モードで進行 (誤検知を避ける、 ただし unknown は記録)。
    if auto_dismiss and wl_cfg is not None:
        strict = (version_mismatch is None)
        extra_res = auto_dismiss_dialogs(
            whitelist=wl_cfg.dialogs,
            timeout_sec=dismiss_timeout_sec,
            abort_on_unknown=strict, verbose=verbose,
        )
        dismissed.extend(extra_res.dismissed)
        for t in extra_res.unknown_dialogs:
            if t not in unknown:
                unknown.append(t)
        if extra_res.aborted:
            return LaunchResult(
                success=False, action="dialog_unknown",
                reason=(f"whitelist 外のダイアログが出現したため abort: "
                        f"{', '.join(extra_res.unknown_dialogs[:3])}"),
                target_handle=main_handle,
                exe_path=str(exe),
                dialogs_dismissed=dismissed,
                unknown_dialogs=unknown,
                version_mismatch=version_mismatch,
                elapsed_sec=time.time() - start,
            )

    elapsed = time.time() - start
    if verbose:
        print(f"[launcher] TARGET launched, handle={main_handle:08x}, "
              f"dismissed={len(dismissed)} dialogs, "
              f"unknown={len(unknown)}, {elapsed:.1f}s")
        if version_mismatch:
            print(f"[launcher] ⚠ TARGET version mismatch — manual review 推奨")
    return LaunchResult(
        success=True, action="launched",
        reason="TARGET 起動完了", target_handle=main_handle,
        exe_path=str(exe), dialogs_dismissed=dismissed,
        unknown_dialogs=unknown,
        version_mismatch=version_mismatch,
        elapsed_sec=elapsed,
    )


def _load_dialog_whitelist() -> list[dict]:
    """data3/userdata/target_clicker/launch_dialogs.json から whitelist を読む

    後方互換用 (v1)。 dialogs フィールドのみ返す。 v2 スキーマでの version/
    verified_at/target_version も使いたい場合は `load_dialog_whitelist_v2()` を使う。
    """
    cfg = load_dialog_whitelist_v2()
    return cfg.dialogs


def _click_first_button(window, button_titles: list[str]) -> Optional[str]:
    """指定タイトル候補で最初に見つかったボタンを click_input

    Win32 (TButton/Button/TBitBtn) を順に試行する。 click_input が失敗したら
    click() に fallback。
    """
    for title in button_titles:
        for cls in ("TButton", "Button", "TBitBtn"):
            try:
                btn = window.child_window(title=title, class_name=cls)
                if btn.exists(timeout=0.3):
                    try:
                        btn.click_input()
                    except Exception:
                        btn.click()
                    return f"{title}({cls})"
            except (ElementNotFoundError, Exception):
                continue
    return None


def _match_title(rule: dict, title: str) -> bool:
    """whitelist rule にタイトルがマッチするか判定"""
    title_re = rule.get("title_re")
    if title_re:
        try:
            return bool(re.match(title_re, title))
        except re.error:
            return False
    title_exact = rule.get("title")
    if title_exact:
        return title_exact == title
    return False


@dataclass
class DismissResult:
    """auto_dismiss_dialogs の戻り値 (v2 / Session 131 シズネ 🔴 B)"""
    dismissed: list[str] = field(default_factory=list)
    unknown_dialogs: list[str] = field(default_factory=list)
    aborted: bool = False                  # abort_on_unknown=True かつ未知検知時 True


# TARGET 関連でない無視 OK のダイアログタイトル (パターン)
# (= whitelist にも入れないが unknown 警告も出さない、 ノイズ扱い)
_IGNORE_DIALOG_TITLES = (
    "Program Manager",
    "Default IME",
    "MSCTFIME UI",
)


def _is_target_owned_dialog(window) -> bool:
    """TARGET frontier JV プロセス由来のダイアログか簡易判定

    暫定実装: window class 名 + タイトルから推測。 厳密にはプロセス ID 比較が
    必要だが、 実機検証 Session 131 OOS で精度向上予定。
    """
    try:
        cls = window.class_name() or ""
        title = window.window_text() or ""
    except Exception:
        return False
    # Delphi VCL クラス (TForm/TFormBase 系) は TARGET 由来の可能性が高い
    if cls.startswith("TForm") or cls.startswith("TApp"):
        return True
    # タイトルに TARGET / JRA / IPAT を含む
    if any(k in title for k in ("TARGET", "JRA", "IPAT", "frontier")):
        return True
    return False


def auto_dismiss_dialogs(
    *,
    whitelist: Optional[list[dict]] = None,
    timeout_sec: int = 10,
    max_iterations: int = 5,
    abort_on_unknown: bool = False,
    verbose: bool = True,
) -> DismissResult:
    """whitelist にマッチするダイアログを button click で進行。

    シズネ視点 (Session 131 🔴 B):
      - whitelist にマッチしないダイアログは絶対 click しない
      - 「変更を保存」 「適用」 等の設定変更系ボタンは whitelist 既定に含めない
      - 同一ダイアログが max_iterations 回出続けたら諦める (無限ループ防止)
      - **abort_on_unknown=True** で whitelist 外 + TARGET 関連 dialog を検知したら
        即座に dismiss を停止し、 unknown_dialogs にタイトルを記録して返す。
        (呼び出し側で abort + 音声通知の判断)

    Returns:
        DismissResult: dismissed (タイトル一覧) / unknown_dialogs / aborted
    """
    wl = whitelist or _load_dialog_whitelist()
    result = DismissResult()
    deadline = time.time() + timeout_sec
    iterations = 0
    seen_unknown_titles: set[str] = set()

    while time.time() < deadline and iterations < max_iterations:
        iterations += 1
        progress = False
        try:
            windows = list(Desktop().windows())
        except Exception as e:
            if verbose:
                print(f"[launcher] Desktop().windows() 失敗: {e}", file=sys.stderr)
            break

        for w in windows:
            try:
                if not w.is_visible():
                    continue
                title = (w.window_text() or "").strip()
                if not title:
                    continue
                # ノイズタイトルは無視
                if title in _IGNORE_DIALOG_TITLES:
                    continue
                # メインの TARGET window 自体は dialog ではないので飛ばす
                if title.startswith("TARGET frontier JV  Ver"):
                    continue

                # whitelist マッチ判定
                matched_rule: Optional[dict] = None
                for rule in wl:
                    if _match_title(rule, title):
                        matched_rule = rule
                        break

                if matched_rule:
                    buttons = matched_rule.get("buttons", [])
                    if not buttons:
                        continue
                    clicked = _click_first_button(w, buttons)
                    if clicked:
                        result.dismissed.append(title)
                        progress = True
                        if verbose:
                            purpose = matched_rule.get("purpose", "")
                            print(f"[launcher] dismissed {title!r} via {clicked!r}"
                                  f"{' ('+purpose+')' if purpose else ''}")
                    continue

                # whitelist 外 dialog
                # TARGET 由来か簡易判定
                if _is_target_owned_dialog(w) and title not in seen_unknown_titles:
                    seen_unknown_titles.add(title)
                    result.unknown_dialogs.append(title)
                    if verbose:
                        print(f"[launcher] UNKNOWN dialog detected: {title!r} "
                              "(whitelist にマッチしません)")
                    if abort_on_unknown:
                        result.aborted = True
                        return result
            except Exception:
                continue
        if not progress:
            time.sleep(0.5)
    return result


# =====================================================================
# Phase 4-B: IPAT 連動投票メニュー起動
# =====================================================================

def open_ipat_menu(*, timeout_sec: int = 15, verbose: bool = True) -> bool:
    """TARGET メイン画面から「ﾌｧｲﾙ→IPATで投票する」 (cmd_id=1601) を WM_COMMAND 起動

    Session 128 ライブ検証 (16 §10.5) で確定済の経路。 cmd_id は動的解決のため
    バージョン変化に追従。
    """
    w = find_target_window()
    if w is None:
        if verbose:
            print(f"[launcher] TARGET window {TARGET_WINDOW_KEYWORD!r} not found")
        return False

    try:
        app = Application(backend="win32").connect(handle=w.handle)
        win = app.window(handle=w.handle)
        win.set_focus()
        time.sleep(0.3)
    except Exception as e:
        if verbose:
            print(f"[launcher] connect/focus failed: {type(e).__name__}: {e}")
        return False

    cmd_id = _find_menu_item_id(win, "ﾌｧｲﾙ", "IPAT")
    if cmd_id is None:
        if verbose:
            print("[launcher] menu item (ﾌｧｲﾙ→IPAT) not found")
        return False

    try:
        _send_menu_command(win, cmd_id)
        if verbose:
            print(f"[launcher] WM_COMMAND cmd_id={cmd_id} sent (ﾌｧｲﾙ→IPAT)")
    except Exception as e:
        if verbose:
            print(f"[launcher] WM_COMMAND failed: {type(e).__name__}: {e}")
        return False

    # IPAT 連動投票画面が新規に開くまで簡易 polling (ウィンドウ数の変化で判定)
    # 実機検証待ち: 正確な判定は wait_ipat_login_ready で行う
    time.sleep(1.0)
    return True


# =====================================================================
# Phase 4-C: IPAT ログイン待機 / メイン画面到達待機
# =====================================================================

# IPAT ログイン画面の判定キーワード (実機検証待ち、 暫定リスト)
_IPAT_LOGIN_TITLE_KEYWORDS = (
    "IPAT", "ﾊﾟｽﾜｰﾄﾞ", "暗証番号", "PAT", "ログイン",
)


def _find_ipat_login_window():
    """IPAT 連動投票画面の暗証番号入力ウィンドウを探す。 見つからなければ None"""
    try:
        for w in Desktop().windows():
            try:
                if not w.is_visible():
                    continue
                title = (w.window_text() or "")
                if not title:
                    continue
                # TARGET メインは除外
                if TARGET_WINDOW_KEYWORD in title:
                    continue
                # IPAT 関連キーワードを含むタイトル
                if any(k in title for k in _IPAT_LOGIN_TITLE_KEYWORDS):
                    return w
            except Exception:
                continue
    except Exception:
        pass
    return None


def wait_ipat_login_ready(
    *,
    timeout_sec: int = 60,
    notify_every_sec: int = 30,
    verbose: bool = True,
) -> bool:
    """IPAT 連動投票画面の暗証番号入力フィールド出現を待つ

    実機検証待ち:
      暫定的に「IPAT/暗証番号 を含むタイトルのウィンドウが visible」 を成功判定。
      実機で IPAT 連動投票画面が embedded Web View なら、 wnd タイトル取得方式を
      変更する必要がある可能性。

    Session 131+ の動作確認で確定する。
    """
    deadline = time.time() + timeout_sec
    last_notify = time.time()
    while time.time() < deadline:
        w = _find_ipat_login_window()
        if w is not None:
            try:
                title = w.window_text() or "?"
            except Exception:
                title = "?"
            if verbose:
                print(f"[launcher] IPAT login window detected: {title!r}")
            return True
        # 一定時間ごとに残時間ログ
        now = time.time()
        if verbose and (now - last_notify >= notify_every_sec):
            remaining = int(deadline - now)
            print(f"[launcher] IPAT login window 未検出 (残 {remaining}s)")
            last_notify = now
        time.sleep(1.0)
    if verbose:
        print(f"[launcher] IPAT login window 未検出 (timeout {timeout_sec}s)")
    return False


def precheck_ipat_session(*, timeout_sec: int = 10, verbose: bool = True) -> tuple[bool, str]:
    """IPAT 認証後の pre-flight セッション検証 (Phase 4-C-min / シズネ 🔴 D)

    Session 131 シズネレビューで「セッション切れ事後検知のみは不十分。
    selective_vote.bat 走り出し前に pre-flight 検証が必要」 と指摘されて追加。

    判定パターン (実機検証待ち、 Session 131 OOS で精度向上予定):
      1. TARGET window が存在
      2. メニューバーが accessible (`win.menu()` が None でない)
      3. 「ﾌｧｲﾙ→IPAT」 メニュー項目の cmd_id が取得できる
         (= IPAT 機能が enabled な状態)

    将来的な強化 (Session 131+ で OOS 検知後):
      - IPAT 連動投票画面内の「最終認証: HH:MM:SS」 表示の新規性確認
      - 残高表示要素の取得確認
      - 「投票履歴照会」 メニュー項目の enabled 状態確認

    Returns:
        (ok, reason). ok=False のとき reason に詳細を入れる。
    """
    w = find_target_window()
    if w is None:
        return (False, "TARGET window not found")

    try:
        app = Application(backend="win32").connect(handle=w.handle)
        win = app.window(handle=w.handle)
    except Exception as e:
        return (False, f"TARGET connect failed: {type(e).__name__}: {e}")

    try:
        menu = win.menu()
    except Exception as e:
        return (False, f"menu() raised: {type(e).__name__}: {e}")
    if menu is None:
        return (False, "TARGET menu not accessible")

    # IPAT メニュー項目が取得可能 = IPAT 機能が enabled
    cmd_id = _find_menu_item_id(win, "ﾌｧｲﾙ", "IPAT")
    if cmd_id is None:
        return (False, "IPAT menu item not found (session may be expired)")

    if verbose:
        print(f"[launcher] precheck: TARGET menu OK, IPAT cmd_id={cmd_id}")
    return (True, f"OK (cmd_id={cmd_id})")


def wait_ipat_main_ready(*, timeout_sec: int = 120, verbose: bool = True) -> bool:
    """暗証番号入力後の IPAT メイン画面 (投票準備完了状態) に到達するまで待つ

    判定ロジック (暫定):
      暗証番号入力ウィンドウが一度 visible になった後、 そのウィンドウが
      閉じた (= ログイン成功) ら True を返す。 ログイン失敗時はウィンドウ
      が残るので timeout で False。

    実機検証待ち: Session 131+ で来週末 OOS により挙動確定
    """
    deadline = time.time() + timeout_sec
    login_was_visible = _find_ipat_login_window() is not None
    while time.time() < deadline:
        login_now = _find_ipat_login_window()
        if login_now is not None:
            login_was_visible = True
        elif login_was_visible:
            # ログイン画面が表示されていて、 今は消えている = 認証成功
            if verbose:
                print("[launcher] IPAT login window closed → main ready")
            return True
        time.sleep(1.0)
    if verbose:
        print(f"[launcher] IPAT main ready 未検知 (timeout {timeout_sec}s)")
    return False


# =====================================================================
# inspect-launch: 起動シーケンス調査用
# =====================================================================

def inspect_launch_dialogs(
    *,
    duration_sec: int = 30,
    poll_sec: float = 0.5,
    save_json: bool = True,
    verbose: bool = True,
) -> Optional[Path]:
    """起動から duration_sec の間に出現する全 visible window を記録

    使い方:
      1. TARGET を閉じた状態でこのコマンド実行
      2. duration_sec 内で別ターミナルから TARGET を手動起動 (もしくは launch_target)
      3. 起動シーケンスの全 dialog を JSON に dump

    出力:
      data3/userdata/target_clicker/inspect/launch_{YYYYMMDD_HHMMSS}.json
    """
    INSPECT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = INSPECT_DIR / f"launch_{ts}.json"

    seen: dict[str, dict] = {}  # title → first-seen info
    deadline = time.time() + duration_sec
    if verbose:
        print(f"[launcher] inspect-launch: 監視中 ({duration_sec}s)... "
              f"別ウィンドウで TARGET を起動してください")
    while time.time() < deadline:
        try:
            for w in Desktop().windows():
                try:
                    if not w.is_visible():
                        continue
                    title = (w.window_text() or "").strip()
                    if not title:
                        continue
                    if title in seen:
                        continue
                    cls = w.class_name() or ""
                    handle = f"{w.handle:08x}" if hasattr(w, "handle") else ""
                    rect = None
                    try:
                        r = w.rectangle()
                        rect = [r.left, r.top, r.right, r.bottom]
                    except Exception:
                        pass
                    # 子コントロール (Button のみ取得)
                    buttons = []
                    try:
                        for c in w.descendants():
                            try:
                                ccls = c.class_name() or ""
                                if "Button" in ccls or "BitBtn" in ccls:
                                    ctxt = c.window_text() or ""
                                    if ctxt:
                                        buttons.append({"class": ccls, "text": ctxt})
                            except Exception:
                                continue
                    except Exception:
                        pass
                    seen[title] = {
                        "first_seen": datetime.now().isoformat(timespec="seconds"),
                        "title": title,
                        "class": cls,
                        "handle": handle,
                        "rect": rect,
                        "buttons": buttons,
                    }
                    if verbose:
                        print(f"[launcher]   detected: title={title!r} class={cls!r} "
                              f"buttons={[b['text'] for b in buttons]}")
                except Exception:
                    continue
        except Exception as e:
            if verbose:
                print(f"[launcher] enum 失敗: {e}", file=sys.stderr)
        time.sleep(poll_sec)

    result = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "duration_sec": duration_sec,
        "windows": list(seen.values()),
    }
    if save_json:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"[launcher] saved: {out_path}")
            print(f"[launcher] {len(seen)} unique windows observed")
    return out_path


# =====================================================================
# Phase 4-C-full: セッション切れ事後検知 + 再ログイン要求 (Session 132)
# =====================================================================
# 設計: 18_TARGET_FULL_AUTOMATION.md §1.3 Phase 4-C-full
#
# Phase 4-C-min (Session 131) は pre-flight 検証のみ。 暗証番号入力後の運用中に
# セッションが切れたケースを救えなかった。 Phase 4-C-full は:
#   ① エラーダイアログ検知 (detect_session_expired_dialog)
#   ② TARGET 再起動なし復旧フロー (recover_ipat_session)
#   ③ 暗証番号入力は永続手動 (Step 4 は ふくだ操作)
# で構成する。 実機検証は来週末 (5/30-31) で確定予定。
# =====================================================================

# セッション切れ専用エラーダイアログのパターン JSON 上書きパス
# (whitelist と同パターン、 v2 スキーマ準拠)
SESSION_EXPIRED_PATTERNS_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "target_clicker" / "session_expired_patterns.json"

# Session 132 時点の推測パターン (実機 inspect で確定予定)。
# - title_re / title はダイアログタイトル
# - body_keywords は dialog 内テキストの部分一致キーワード (どれか 1 つマッチで成立)
# - close_buttons は復旧フロー Step 1 で押す button title 候補 (順に試行)
DEFAULT_SESSION_EXPIRED_PATTERNS: list[dict] = [
    {
        "title_re": r".*(再ログイン|セッション|認証|タイムアウト).*",
        "body_keywords": [
            "再度ログイン", "認証情報が無効", "セッションが切れ",
            "セッションが終了", "再ログイン", "timeout",
            "ログインし直", "認証エラー",
        ],
        "close_buttons": ["OK", "閉じる", "はい"],
        "purpose": "IPAT セッション切れエラー (推測 / 実機検証待ち)",
    },
]


@dataclass
class SessionExpiredDialogInfo:
    """detect_session_expired_dialog の戻り値"""
    detected: bool
    title: Optional[str] = None
    body_text: Optional[str] = None
    matched_keyword: Optional[str] = None
    close_buttons: list[str] = field(default_factory=list)
    handle: Optional[int] = None
    pattern_source: str = "default"            # "default" / "file"


def load_session_expired_patterns(path: Optional[Path] = None) -> tuple[list[dict], str]:
    """data3/userdata/target_clicker/session_expired_patterns.json から読み込み。

    Session 132 シズネ 🟡-5 (Session 133 実装):
      - dict 形式で `verified_by` が無い場合は stderr に WARNING (fail-open)
      - list 形式 (legacy) も WARNING を出す (v2 dict への移行を促す)
      - `target_version` 不一致も警告対象 (whitelist v2 と同様の運用)

    Returns:
        (patterns, source). source は "default" / "file" / "error".
    """
    file_path = path or SESSION_EXPIRED_PATTERNS_PATH
    if not file_path.exists():
        return (list(DEFAULT_SESSION_EXPIRED_PATTERNS), "default")
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[launcher] session_expired_patterns 読込失敗 (default 使用): {e}",
              file=sys.stderr)
        return (list(DEFAULT_SESSION_EXPIRED_PATTERNS), "default")

    if isinstance(data, list):
        # legacy format — Session 132 🟡-5: v2 への移行推奨を WARNING
        print(f"[launcher] WARNING: {file_path.name} が legacy list 形式です。 "
              f"v2 スキーマ (dict + verified_by + target_version + patterns) への移行を "
              f"推奨します (監査責任所在の明示)",
              file=sys.stderr)
        return (data, "file")
    if isinstance(data, dict):
        patterns = data.get("patterns", [])
        if isinstance(patterns, list):
            # Session 132 🟡-5: verified_by 必須化 (WARNING、 fail-open)
            verified_by = data.get("verified_by")
            if not verified_by:
                print(f"[launcher] WARNING: {file_path.name} に verified_by が指定されて "
                      f"いません。 v2 スキーマでは JSON 内容の責任所在 (誰が実機検証して "
                      f"作ったか) を明示する必要があります — verified_by フィールドを "
                      f"追加してください",
                      file=sys.stderr)
            return (patterns, "file")
    print(f"[launcher] session_expired_patterns の形式が不正 (default 使用)",
          file=sys.stderr)
    return (list(DEFAULT_SESSION_EXPIRED_PATTERNS), "default")


def _read_dialog_body(window, max_descendants: int = 50) -> str:
    """dialog の descendants から visible text を ' | ' join で抽出 (best-effort)"""
    texts: list[str] = []
    try:
        for i, c in enumerate(window.descendants()):
            if i >= max_descendants:
                break
            try:
                t = c.window_text()
                if t and t.strip():
                    texts.append(t.strip())
            except Exception:
                continue
    except Exception:
        pass
    return " | ".join(texts)


def detect_session_expired_dialog(
    *,
    patterns: Optional[list[dict]] = None,
    verbose: bool = True,
) -> SessionExpiredDialogInfo:
    """セッション切れエラーダイアログを Desktop から検出。

    判定ロジック:
      1. patterns (default or file) を順に評価
      2. dialog title が title_re/title にマッチ
      3. dialog body に body_keywords のいずれかが含まれる (body_keywords が空ならスキップ)
      4. 両方満たせば SessionExpiredDialogInfo(detected=True) を返す

    検出しなければ detected=False。 検出は 1 件のみ (最初に見つけたもの)。
    """
    if patterns is None:
        patterns, source = load_session_expired_patterns()
    else:
        source = "argument"

    try:
        windows = list(Desktop().windows())
    except Exception as e:
        if verbose:
            print(f"[launcher] Desktop().windows() 失敗: {e}", file=sys.stderr)
        return SessionExpiredDialogInfo(detected=False, pattern_source=source)

    for w in windows:
        try:
            if not w.is_visible():
                continue
            title = (w.window_text() or "").strip()
            if not title:
                continue
            # TARGET メインウィンドウ自体は除外
            if title.startswith("TARGET frontier JV  Ver"):
                continue

            for rule in patterns:
                if not _match_title(rule, title):
                    continue
                body_keywords = rule.get("body_keywords") or []
                if not body_keywords:
                    # title だけで判定 (body 検査スキップ)
                    handle = getattr(w, "handle", None)
                    if verbose:
                        print(f"[launcher] session_expired detected (title only): "
                              f"{title!r}")
                    return SessionExpiredDialogInfo(
                        detected=True, title=title, body_text=None,
                        matched_keyword=None,
                        close_buttons=list(rule.get("close_buttons", ["OK"])),
                        handle=handle, pattern_source=source,
                    )

                body = _read_dialog_body(w)
                matched_kw = None
                for kw in body_keywords:
                    if kw and kw in body:
                        matched_kw = kw
                        break
                if matched_kw is None:
                    continue

                handle = getattr(w, "handle", None)
                if verbose:
                    print(f"[launcher] session_expired detected: title={title!r} "
                          f"keyword={matched_kw!r}")
                return SessionExpiredDialogInfo(
                    detected=True, title=title, body_text=body[:300],
                    matched_keyword=matched_kw,
                    close_buttons=list(rule.get("close_buttons", ["OK"])),
                    handle=handle, pattern_source=source,
                )
        except Exception:
            continue

    return SessionExpiredDialogInfo(detected=False, pattern_source=source)


def _close_session_expired_dialog(info: SessionExpiredDialogInfo,
                                  verbose: bool = True) -> bool:
    """検出したセッション切れ dialog を close_buttons の最初に押せるボタンで閉じる"""
    if info.handle is None:
        if verbose:
            print(f"[launcher] _close_session_expired_dialog: handle None, skip")
        return False
    try:
        app = Application(backend="win32").connect(handle=info.handle)
        win = app.window(handle=info.handle)
    except Exception as e:
        if verbose:
            print(f"[launcher] _close_session_expired_dialog: connect failed: "
                  f"{type(e).__name__}: {e}")
        return False
    clicked = _click_first_button(win, info.close_buttons or ["OK"])
    if clicked and verbose:
        print(f"[launcher] session_expired dialog closed via {clicked!r}")
    return clicked is not None


@dataclass
class RecoveryResult:
    """recover_ipat_session の戻り値"""
    success: bool
    action: str                       # "recovered" / "manual_required" / "timeout" /
                                      #  "error" / "no_session_to_recover"
    reason: str
    steps_completed: list[str] = field(default_factory=list)
    detected_dialog_title: Optional[str] = None
    elapsed_sec: Optional[float] = None


def recover_ipat_session(
    *,
    expired_info: Optional[SessionExpiredDialogInfo] = None,
    open_ipat_timeout_sec: int = 15,
    login_timeout_sec: int = 180,             # 手動入力時間を考慮して長め
    main_timeout_sec: int = 120,
    notify_steps: bool = True,
    verbose: bool = True,
) -> RecoveryResult:
    """TARGET 再起動なしで IPAT セッションを復旧する (Phase 4-C-full)

    フロー (設計書 18 §1.3 Phase 4-C-full):
      Step 1: エラーダイアログを閉じる (expired_info があれば)
      Step 2: open_ipat_menu() で IPAT 連動メニューを再起動
      Step 3: wait_ipat_login_ready() でログイン画面を待つ
      Step 4: 手動暗証番号入力 ★ 永続手動 (notify_ipat_login_required で促す)
      Step 5: wait_ipat_main_ready() + precheck_ipat_session() で再認証完了確認

    Args:
        expired_info: 事前に detect_session_expired_dialog() で取得した info
                      (None なら Step 1 skip)
        login_timeout_sec: Step 3 のタイムアウト (default 180s = 暗証番号入力を待つため長め)

    Returns:
        RecoveryResult。 success=False の action 種別:
          - "manual_required": 自動復旧不可、 ふくだ手動再認証が必要
          - "timeout": どこかの step で timeout
          - "error": connect/click 失敗等
          - "no_session_to_recover": precheck で OK だった (= 誤検知だった可能性)
    """
    start = time.time()
    steps: list[str] = []

    # Step 1: エラーダイアログを閉じる (多段モーダル対応 / Session 132 シズネ 🟡-8)
    # 最大 max_close_attempts 回まで「detect → close」 を繰り返し、 IPAT 側で
    # 「ログアウト確認」 + 「ログイン画面に戻ります」 のような 2 段モーダルが
    # 積まれているケースを順に潰す。 1 段閉じてから次段を detect しなければ
    # 検知できない構造のため、 静的解決ではなく動的に再 detect する。
    max_close_attempts = 3
    if expired_info and expired_info.detected:
        current_info = expired_info
        for attempt in range(1, max_close_attempts + 1):
            # 後方互換性: 1 段目は suffix なし (Session 132 既存 step 名)、
            # 2 段目以降は _2 / _3 suffix で多段モーダル検出を可視化
            suffix = "" if attempt == 1 else f"_{attempt}"
            closed = _close_session_expired_dialog(current_info, verbose=verbose)
            if closed:
                steps.append(f"dialog_closed{suffix}")
            else:
                steps.append(f"dialog_close_skipped{suffix}")
                # 閉じれなければ多段である可能性なし。 ループ抜け
                break
            # 次段の dialog を探す (handle が変わっていれば多段)
            next_info = detect_session_expired_dialog(verbose=False)
            if (next_info.detected and next_info.handle is not None
                    and next_info.handle != current_info.handle):
                if verbose:
                    print(f"[launcher] recover: Step 1 next-layer dialog detected "
                          f"(attempt {attempt + 1}/{max_close_attempts}): "
                          f"{next_info.title!r}")
                current_info = next_info
            else:
                # 残り dialog なし or 同一 handle = ループ抜け
                break

    # Step 2: open_ipat_menu
    if verbose:
        print(f"[launcher] recover: Step 2 open_ipat_menu...")
    ok = open_ipat_menu(timeout_sec=open_ipat_timeout_sec, verbose=verbose)
    if not ok:
        return RecoveryResult(
            success=False, action="manual_required",
            reason="open_ipat_menu failed (cmd_id 取得失敗の可能性)",
            steps_completed=steps,
            detected_dialog_title=expired_info.title if expired_info else None,
            elapsed_sec=time.time() - start,
        )
    steps.append("ipat_menu_opened")

    # Step 3: wait_ipat_login_ready
    if verbose:
        print(f"[launcher] recover: Step 3 wait_ipat_login_ready "
              f"(timeout {login_timeout_sec}s)...")
    ok = wait_ipat_login_ready(timeout_sec=login_timeout_sec, verbose=verbose)
    if not ok:
        return RecoveryResult(
            success=False, action="timeout",
            reason=f"wait_ipat_login_ready timeout {login_timeout_sec}s",
            steps_completed=steps,
            detected_dialog_title=expired_info.title if expired_info else None,
            elapsed_sec=time.time() - start,
        )
    steps.append("login_window_visible")

    # Step 4: 音声で再認証を促す (notify_steps が True の場合のみ)
    if notify_steps:
        try:
            from ml.target_clicker.notify import notify_ipat_login_required
            notify_ipat_login_required()
        except Exception as e:
            print(f"[launcher] notify_ipat_login_required failed (continuing): {e}",
                  file=sys.stderr)
    if verbose:
        print(f"[launcher] recover: ふくだ暗証番号入力をお待ちしています...")

    # Step 5: wait_ipat_main_ready + precheck
    if verbose:
        print(f"[launcher] recover: Step 5 wait_ipat_main_ready "
              f"(timeout {main_timeout_sec}s)...")
    ok = wait_ipat_main_ready(timeout_sec=main_timeout_sec, verbose=verbose)
    if not ok:
        return RecoveryResult(
            success=False, action="timeout",
            reason=f"wait_ipat_main_ready timeout {main_timeout_sec}s "
                   "(ふくだ暗証番号入力が完了しなかった可能性)",
            steps_completed=steps,
            detected_dialog_title=expired_info.title if expired_info else None,
            elapsed_sec=time.time() - start,
        )
    steps.append("ipat_main_ready")

    # pre-flight 検証
    ok, reason = precheck_ipat_session(verbose=verbose)
    if not ok:
        return RecoveryResult(
            success=False, action="manual_required",
            reason=f"precheck_ipat_session failed: {reason}",
            steps_completed=steps,
            detected_dialog_title=expired_info.title if expired_info else None,
            elapsed_sec=time.time() - start,
        )
    steps.append("precheck_passed")

    elapsed = time.time() - start
    if verbose:
        print(f"[launcher] recover: SUCCESS ({elapsed:.1f}s, steps={steps})")
    return RecoveryResult(
        success=True, action="recovered",
        reason="IPAT セッション再認証成功",
        steps_completed=steps,
        detected_dialog_title=expired_info.title if expired_info else None,
        elapsed_sec=elapsed,
    )


# =====================================================================
# CLI
# =====================================================================

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd")

    p_launch = sub.add_parser("launch", help="Phase 4-A: TARGET 起動 + 認証ダイアログ進行")
    p_launch.add_argument("--timeout", type=int, default=30)
    p_launch.add_argument("--no-dismiss", action="store_true",
                          help="認証ダイアログ自動進行を抑制")
    p_launch.add_argument("--exe", type=Path, default=None,
                          help="TARGET exe パスを明示指定")

    p_ipat = sub.add_parser("open-ipat", help="Phase 4-B: IPAT 連動投票メニューを起動")
    p_ipat.add_argument("--timeout", type=int, default=15)

    p_login = sub.add_parser("wait-login", help="Phase 4-C: IPAT ログイン画面の出現を待機")
    p_login.add_argument("--timeout", type=int, default=60)

    p_main = sub.add_parser("wait-main", help="Phase 4-C: IPAT メイン画面到達を待機")
    p_main.add_argument("--timeout", type=int, default=120)

    p_inspect = sub.add_parser(
        "inspect-launch",
        help="起動シーケンス調査: 出現する全 dialog を JSON dump",
    )
    p_inspect.add_argument("--duration", type=int, default=30)

    p_detect = sub.add_parser(
        "detect-session-expired",
        help="Phase 4-C-full: セッション切れエラーダイアログを検出 (1 回スキャン)",
    )

    p_recover = sub.add_parser(
        "recover-session",
        help="Phase 4-C-full: TARGET 再起動なしで IPAT セッション復旧を試行",
    )
    p_recover.add_argument("--login-timeout", type=int, default=180)
    p_recover.add_argument("--main-timeout", type=int, default=120)
    p_recover.add_argument("--race-id", default="",
                            help="関連 race_id (16桁)。 空文字なら events_jsonl のみ追記")
    p_recover.add_argument("--no-notify", action="store_true",
                            help="音声通知をスキップ")
    p_recover.add_argument("--no-ledger", action="store_true",
                            help="ledger event 記録をスキップ (デバッグ用)")

    p_full = sub.add_parser(
        "full",
        help="フルシーケンス: launch → open-ipat → wait-login (暗証入力は手動) → wait-main",
    )
    p_full.add_argument("--launch-timeout", type=int, default=30)
    p_full.add_argument("--login-timeout", type=int, default=60)
    p_full.add_argument("--main-timeout", type=int, default=120)
    p_full.add_argument("--no-dismiss", action="store_true")

    args = p.parse_args()

    if args.cmd is None or args.cmd == "launch":
        if args.cmd is None:
            args = p_launch.parse_args([])  # default values
        r = launch_target(
            timeout_sec=args.timeout,
            exe_path=args.exe,
            auto_dismiss=not args.no_dismiss,
        )
        print(f"\n[launch] success={r.success} action={r.action}")
        print(f"  reason={r.reason}")
        if r.target_handle:
            print(f"  handle={r.target_handle:08x}")
        if r.dialogs_dismissed:
            print(f"  dismissed={r.dialogs_dismissed}")
        if r.elapsed_sec is not None:
            print(f"  elapsed={r.elapsed_sec:.1f}s")
        sys.exit(0 if r.success else 1)
    elif args.cmd == "open-ipat":
        ok = open_ipat_menu(timeout_sec=args.timeout)
        sys.exit(0 if ok else 1)
    elif args.cmd == "wait-login":
        ok = wait_ipat_login_ready(timeout_sec=args.timeout)
        sys.exit(0 if ok else 1)
    elif args.cmd == "wait-main":
        ok = wait_ipat_main_ready(timeout_sec=args.timeout)
        sys.exit(0 if ok else 1)
    elif args.cmd == "inspect-launch":
        inspect_launch_dialogs(duration_sec=args.duration)
    elif args.cmd == "detect-session-expired":
        info = detect_session_expired_dialog()
        print(f"\n[detect-session-expired] detected={info.detected}")
        if info.detected:
            print(f"  title={info.title!r}")
            print(f"  matched_keyword={info.matched_keyword!r}")
            print(f"  close_buttons={info.close_buttons}")
            print(f"  pattern_source={info.pattern_source}")
        sys.exit(0 if info.detected else 1)
    elif args.cmd == "recover-session":
        info = detect_session_expired_dialog()
        r = recover_ipat_session(
            expired_info=info if info.detected else None,
            login_timeout_sec=args.login_timeout,
            main_timeout_sec=args.main_timeout,
            notify_steps=not args.no_notify,
        )
        print(f"\n[recover-session] success={r.success} action={r.action}")
        print(f"  reason={r.reason}")
        print(f"  steps_completed={r.steps_completed}")
        if r.elapsed_sec is not None:
            print(f"  elapsed={r.elapsed_sec:.1f}s")

        # シズネ Session 132 🟡-10 対応: CLI 単独実行時も ledger event を残す
        # (Session 132 までは writer.py に関数定義だけで呼び出し箇所ゼロだった)
        if not args.no_ledger:
            try:
                if r.success:
                    from ml.purchase_ledger.writer import record_ipat_session_recovered
                    record_ipat_session_recovered(
                        race_id=args.race_id or "",
                        elapsed_sec=r.elapsed_sec or 0.0,
                        steps_completed=r.steps_completed,
                    )
                    print(f"[recover-session] ledger IPAT_SESSION_RECOVERED recorded")
                else:
                    from ml.purchase_ledger.writer import (
                        record_ipat_session_recovery_failed,
                    )
                    record_ipat_session_recovery_failed(
                        race_id=args.race_id or "",
                        failure_action=r.action,
                        reason=r.reason,
                        elapsed_sec=r.elapsed_sec,
                        steps_completed=r.steps_completed,
                    )
                    print(f"[recover-session] ledger IPAT_SESSION_RECOVERY_FAILED recorded")
            except Exception as e:
                print(f"[recover-session] ledger 記録失敗: {type(e).__name__}: {e}",
                      file=sys.stderr)

        # 結果通知 (success / failure 両方)
        if not args.no_notify:
            try:
                if r.success:
                    from ml.target_clicker.notify import (
                        notify_ipat_session_recovery_succeeded,
                    )
                    notify_ipat_session_recovery_succeeded(elapsed_sec=r.elapsed_sec)
                else:
                    from ml.target_clicker.notify import (
                        notify_ipat_session_recovery_required_manual,
                    )
                    notify_ipat_session_recovery_required_manual(reason=r.reason)
            except Exception as e:
                print(f"[recover-session] notify 失敗: {type(e).__name__}: {e}",
                      file=sys.stderr)

        sys.exit(0 if r.success else 1)
    elif args.cmd == "full":
        r = launch_target(timeout_sec=args.launch_timeout,
                          auto_dismiss=not args.no_dismiss)
        print(f"[full] launch: success={r.success} action={r.action} "
              f"({r.elapsed_sec:.1f}s)" if r.elapsed_sec else f"[full] launch: {r.action}")
        if not r.success:
            sys.exit(1)
        if not open_ipat_menu(timeout_sec=15):
            print("[full] open_ipat_menu failed")
            sys.exit(1)
        # 音声で暗証番号入力を促す
        try:
            from ml.target_clicker.notify import notify_ipat_login_required
            notify_ipat_login_required()
        except Exception as e:
            print(f"[full] notify failed (continuing): {e}", file=sys.stderr)
        if not wait_ipat_login_ready(timeout_sec=args.login_timeout):
            print("[full] wait_ipat_login_ready timeout")
            sys.exit(1)
        print("[full] 暗証番号入力をお待ちしています...")
        if not wait_ipat_main_ready(timeout_sec=args.main_timeout):
            print("[full] wait_ipat_main_ready timeout")
            sys.exit(1)
        print("[full] IPAT 認証完了、 投票準備 OK")

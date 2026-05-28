#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase 4-C-full (Session 132) のロジックテスト

設計: docs/auto-purchase/18_TARGET_FULL_AUTOMATION.md §1.3 Phase 4-C-full

対象:
  - launcher.load_session_expired_patterns()  ← JSON 読込 + default フォールバック
  - launcher.detect_session_expired_dialog()  ← title/body keyword 判定
  - launcher.recover_ipat_session()           ← 各 step 失敗 / 全成功
  - launcher.RecoveryResult / SessionExpiredDialogInfo dataclass

方針:
  - 実機 (TARGET / pywinauto) に依存しないテスト。 Desktop().windows() は
    monkeypatch で偽装、 open_ipat_menu / wait_ipat_login_ready / wait_ipat_main_ready /
    precheck_ipat_session は monkeypatch で結果固定。
  - 暗証番号自動入力禁止テストは別ファイル (test_launcher_no_password.py)。
    本ファイルは「復旧フローの logic」 のみ検証する。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_launcher_recovery.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.target_clicker import launcher as launcher_mod
from ml.target_clicker.launcher import (
    DEFAULT_SESSION_EXPIRED_PATTERNS,
    RecoveryResult,
    SessionExpiredDialogInfo,
    detect_session_expired_dialog,
    load_session_expired_patterns,
    recover_ipat_session,
)


# =====================================================================
# ヘルパ: pywinauto Desktop / window を mock 化するファクトリ
# =====================================================================

class _FakeWindow:
    """pywinauto window/dialog の最小 mock"""
    def __init__(self, title: str, visible: bool = True,
                 descendants_text: list[str] | None = None,
                 handle: int = 0x1234):
        self._title = title
        self._visible = visible
        self._descendants_text = descendants_text or []
        self.handle = handle

    def is_visible(self) -> bool:
        return self._visible

    def window_text(self) -> str:
        return self._title

    def descendants(self):
        for txt in self._descendants_text:
            yield _FakeChild(txt)


class _FakeChild:
    def __init__(self, text: str):
        self._text = text

    def window_text(self) -> str:
        return self._text


def _patch_desktop_windows(monkeypatch, fake_windows: list[_FakeWindow]):
    """Desktop().windows() が fake_windows を返すよう patch"""
    class _FakeDesktop:
        def windows(self):
            return list(fake_windows)
    monkeypatch.setattr(launcher_mod, "Desktop", lambda *a, **kw: _FakeDesktop())


# =====================================================================
# load_session_expired_patterns
# =====================================================================

class TestLoadSessionExpiredPatterns:

    def test_file_absent_returns_default(self, tmp_path):
        patterns, source = load_session_expired_patterns(tmp_path / "missing.json")
        assert source == "default"
        assert patterns == DEFAULT_SESSION_EXPIRED_PATTERNS

    def test_list_format_is_loaded(self, tmp_path):
        f = tmp_path / "patterns.json"
        custom = [{"title_re": r"^カスタム$", "body_keywords": ["x"],
                   "close_buttons": ["OK"]}]
        f.write_text(json.dumps(custom), encoding="utf-8")
        patterns, source = load_session_expired_patterns(f)
        assert source == "file"
        assert patterns == custom

    def test_dict_format_v2_is_loaded(self, tmp_path):
        f = tmp_path / "patterns.json"
        custom = {
            "version": "1.0",
            "verified_by": "fukuda",
            "patterns": [{"title": "再ログイン", "body_keywords": [],
                           "close_buttons": ["OK"]}],
        }
        f.write_text(json.dumps(custom), encoding="utf-8")
        patterns, source = load_session_expired_patterns(f)
        assert source == "file"
        assert patterns == custom["patterns"]

    def test_broken_json_falls_back_to_default(self, tmp_path):
        f = tmp_path / "patterns.json"
        f.write_text("{ not valid json", encoding="utf-8")
        patterns, source = load_session_expired_patterns(f)
        assert source == "default"
        assert patterns == DEFAULT_SESSION_EXPIRED_PATTERNS

    def test_default_patterns_have_required_keys(self):
        for p in DEFAULT_SESSION_EXPIRED_PATTERNS:
            # title_re or title が必須
            assert "title_re" in p or "title" in p
            # close_buttons は存在 (空でも OK)
            assert "close_buttons" in p


# =====================================================================
# detect_session_expired_dialog
# =====================================================================

class TestDetectSessionExpiredDialog:

    def test_no_windows_returns_undetected(self, monkeypatch):
        _patch_desktop_windows(monkeypatch, [])
        info = detect_session_expired_dialog(verbose=False)
        assert info.detected is False

    def test_target_main_window_is_ignored(self, monkeypatch):
        # TARGET メインウィンドウは検知対象外
        win = _FakeWindow("TARGET frontier JV  Ver6.21  Rev002")
        _patch_desktop_windows(monkeypatch, [win])
        info = detect_session_expired_dialog(verbose=False)
        assert info.detected is False

    def test_title_match_with_body_keyword_detected(self, monkeypatch):
        # title が「再ログイン」 を含み body に「再度ログイン」 が含まれる
        win = _FakeWindow(
            "再ログインしてください",
            descendants_text=["セッションが切れました", "再度ログインしてください"],
        )
        _patch_desktop_windows(monkeypatch, [win])
        info = detect_session_expired_dialog(verbose=False)
        assert info.detected is True
        assert info.title == "再ログインしてください"
        assert info.matched_keyword == "再度ログイン"
        assert info.close_buttons  # default パターンの close_buttons がある

    def test_title_match_no_body_keyword_not_detected(self, monkeypatch):
        # title はマッチ、 body に keyword なし → default patterns は body 必須
        win = _FakeWindow(
            "再ログイン",
            descendants_text=["全然関係ないメッセージ"],
        )
        _patch_desktop_windows(monkeypatch, [win])
        info = detect_session_expired_dialog(verbose=False)
        assert info.detected is False

    def test_title_mismatch_not_detected(self, monkeypatch):
        win = _FakeWindow(
            "情報",
            descendants_text=["再度ログインしてください"],
        )
        _patch_desktop_windows(monkeypatch, [win])
        info = detect_session_expired_dialog(verbose=False)
        assert info.detected is False

    def test_custom_pattern_title_only(self, monkeypatch):
        # body_keywords が空なら title だけで判定
        win = _FakeWindow("CustomExpired", descendants_text=[])
        _patch_desktop_windows(monkeypatch, [win])
        patterns = [{"title": "CustomExpired", "body_keywords": [],
                     "close_buttons": ["はい"]}]
        info = detect_session_expired_dialog(patterns=patterns, verbose=False)
        assert info.detected is True
        assert info.title == "CustomExpired"
        assert info.close_buttons == ["はい"]
        assert info.matched_keyword is None

    def test_pattern_source_reflects_argument(self, monkeypatch):
        _patch_desktop_windows(monkeypatch, [])
        info = detect_session_expired_dialog(
            patterns=[{"title": "x", "close_buttons": ["OK"]}],
            verbose=False,
        )
        assert info.pattern_source == "argument"

    def test_invisible_window_is_skipped(self, monkeypatch):
        win = _FakeWindow(
            "再ログイン", visible=False,
            descendants_text=["再度ログイン"],
        )
        _patch_desktop_windows(monkeypatch, [win])
        info = detect_session_expired_dialog(verbose=False)
        assert info.detected is False


# =====================================================================
# recover_ipat_session
# =====================================================================

class TestRecoverIpatSession:

    def _patch_steps(self, monkeypatch, *,
                     open_ipat: bool = True,
                     wait_login: bool = True,
                     wait_main: bool = True,
                     precheck: tuple[bool, str] = (True, "OK"),
                     close_dialog: bool = True):
        """各 step を mock 化"""
        monkeypatch.setattr(launcher_mod, "open_ipat_menu",
                            lambda **kw: open_ipat)
        monkeypatch.setattr(launcher_mod, "wait_ipat_login_ready",
                            lambda **kw: wait_login)
        monkeypatch.setattr(launcher_mod, "wait_ipat_main_ready",
                            lambda **kw: wait_main)
        monkeypatch.setattr(launcher_mod, "precheck_ipat_session",
                            lambda **kw: precheck)
        monkeypatch.setattr(launcher_mod, "_close_session_expired_dialog",
                            lambda info, verbose=True: close_dialog)
        # notify は import 失敗で best-effort 経路を通る (テスト本体は素通り)
        # ここでは何もしない (notify 失敗は print stderr で済まされる)

    def test_all_steps_succeed_returns_recovered(self, monkeypatch):
        self._patch_steps(monkeypatch)
        info = SessionExpiredDialogInfo(detected=True, title="x", handle=1,
                                         close_buttons=["OK"])
        r = recover_ipat_session(expired_info=info, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.success is True
        assert r.action == "recovered"
        assert "dialog_closed" in r.steps_completed
        assert "ipat_menu_opened" in r.steps_completed
        assert "login_window_visible" in r.steps_completed
        assert "ipat_main_ready" in r.steps_completed
        assert "precheck_passed" in r.steps_completed

    def test_no_expired_info_skips_dialog_close(self, monkeypatch):
        self._patch_steps(monkeypatch)
        r = recover_ipat_session(expired_info=None, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.success is True
        assert "dialog_closed" not in r.steps_completed
        assert "dialog_close_skipped" not in r.steps_completed

    def test_open_ipat_menu_fail_returns_manual_required(self, monkeypatch):
        self._patch_steps(monkeypatch, open_ipat=False)
        r = recover_ipat_session(expired_info=None, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.success is False
        assert r.action == "manual_required"
        assert "open_ipat_menu failed" in r.reason

    def test_wait_login_timeout_returns_timeout(self, monkeypatch):
        self._patch_steps(monkeypatch, wait_login=False)
        r = recover_ipat_session(expired_info=None, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.success is False
        assert r.action == "timeout"
        assert "wait_ipat_login_ready timeout" in r.reason
        assert "ipat_menu_opened" in r.steps_completed
        assert "login_window_visible" not in r.steps_completed

    def test_wait_main_timeout_returns_timeout(self, monkeypatch):
        self._patch_steps(monkeypatch, wait_main=False)
        r = recover_ipat_session(expired_info=None, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.success is False
        assert r.action == "timeout"
        assert "wait_ipat_main_ready timeout" in r.reason
        assert "login_window_visible" in r.steps_completed

    def test_precheck_fail_returns_manual_required(self, monkeypatch):
        self._patch_steps(monkeypatch, precheck=(False, "menu lost"))
        r = recover_ipat_session(expired_info=None, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.success is False
        assert r.action == "manual_required"
        assert "precheck_ipat_session failed" in r.reason
        assert "menu lost" in r.reason

    def test_close_dialog_failure_still_proceeds(self, monkeypatch):
        # close_dialog が False でも次の step に進む
        self._patch_steps(monkeypatch, close_dialog=False)
        info = SessionExpiredDialogInfo(detected=True, title="x", handle=1,
                                         close_buttons=["OK"])
        r = recover_ipat_session(expired_info=info, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.success is True
        assert "dialog_close_skipped" in r.steps_completed

    def test_elapsed_sec_is_set(self, monkeypatch):
        self._patch_steps(monkeypatch)
        r = recover_ipat_session(expired_info=None, login_timeout_sec=1,
                                 main_timeout_sec=1, notify_steps=False, verbose=False)
        assert r.elapsed_sec is not None
        assert r.elapsed_sec >= 0


# =====================================================================
# dataclass defaults
# =====================================================================

class TestDataclassDefaults:

    def test_session_expired_dialog_info_defaults(self):
        info = SessionExpiredDialogInfo(detected=False)
        assert info.detected is False
        assert info.title is None
        assert info.body_text is None
        assert info.matched_keyword is None
        assert info.close_buttons == []
        assert info.handle is None
        assert info.pattern_source == "default"

    def test_recovery_result_defaults(self):
        r = RecoveryResult(success=False, action="error", reason="x")
        assert r.success is False
        assert r.steps_completed == []
        assert r.detected_dialog_title is None
        assert r.elapsed_sec is None

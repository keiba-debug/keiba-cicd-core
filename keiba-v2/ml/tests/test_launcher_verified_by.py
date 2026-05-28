#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""シズネ Session 132 レビュー 🟡-5 (Session 133 実装):
`session_expired_patterns.json` v2 + whitelist v2 で verified_by 必須化 + 起動時 WARNING

対象:
  - launcher.load_dialog_whitelist_v2()
  - launcher.load_session_expired_patterns()

方針: 起動時 stderr の WARNING を capsys で検出。 fail-open 設計 (= 起動は止めず警告のみ)。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_launcher_verified_by.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.target_clicker.launcher import (
    DEFAULT_DIALOG_WHITELIST,
    DEFAULT_SESSION_EXPIRED_PATTERNS,
    load_dialog_whitelist_v2,
    load_session_expired_patterns,
)


# =====================================================================
# load_dialog_whitelist_v2: verified_by 必須化
# =====================================================================

class TestWhitelistV2VerifiedBy:

    def test_v2_with_verified_by_no_warning(self, tmp_path, capsys):
        """v2 + verified_by 指定 → WARNING 出ない"""
        f = tmp_path / "launch_dialogs.json"
        data = {
            "version": "1.0",
            "verified_at": "2026-05-31T08:00:00+09:00",
            "verified_by": "fukuda",
            "target_version": "TARGET frontier JV Ver6.21 Rev002",
            "dialogs": [{"title": "情報", "buttons": ["OK"]}],
        }
        f.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_dialog_whitelist_v2(f)
        captured = capsys.readouterr()
        assert "WARNING" not in captured.err
        assert cfg.verified_by == "fukuda"
        assert cfg.source == "file"

    def test_v2_without_verified_by_emits_warning(self, tmp_path, capsys):
        """v2 + verified_by 未指定 → stderr に WARNING (fail-open で起動継続)"""
        f = tmp_path / "launch_dialogs.json"
        data = {
            "version": "1.0",
            "dialogs": [{"title": "情報", "buttons": ["OK"]}],
        }
        f.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_dialog_whitelist_v2(f)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "verified_by" in captured.err
        # fail-open: cfg は正常に読まれる (起動止めない)
        assert cfg.source == "file"
        assert cfg.verified_by is None

    def test_legacy_list_emits_warning(self, tmp_path, capsys):
        """legacy list 形式 → v2 移行推奨 WARNING (fail-open)"""
        f = tmp_path / "launch_dialogs.json"
        data = [{"title": "情報", "buttons": ["OK"]}]
        f.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_dialog_whitelist_v2(f)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "legacy" in captured.err
        assert cfg.source == "legacy_list"

    def test_v2_with_empty_verified_by_emits_warning(self, tmp_path, capsys):
        """verified_by が空文字列 → WARNING (None 判定と同じ)"""
        f = tmp_path / "launch_dialogs.json"
        data = {
            "version": "1.0",
            "verified_by": "",
            "dialogs": [{"title": "情報", "buttons": ["OK"]}],
        }
        f.write_text(json.dumps(data), encoding="utf-8")

        cfg = load_dialog_whitelist_v2(f)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_file_absent_no_warning(self, tmp_path, capsys):
        """ファイル不在 → default 使用、 WARNING 出ない (default は責任所在で議論しない)"""
        cfg = load_dialog_whitelist_v2(tmp_path / "missing.json")
        captured = capsys.readouterr()
        assert "WARNING" not in captured.err
        assert cfg.source == "default"


# =====================================================================
# load_session_expired_patterns: verified_by 必須化
# =====================================================================

class TestSessionExpiredPatternsV2VerifiedBy:

    def test_v2_with_verified_by_no_warning(self, tmp_path, capsys):
        """v2 + verified_by 指定 → WARNING 出ない"""
        f = tmp_path / "session_expired_patterns.json"
        data = {
            "version": "1.0",
            "verified_by": "fukuda",
            "target_version": "TARGET frontier JV Ver6.21 Rev002",
            "patterns": [{"title_re": r"^再ログイン$", "body_keywords": [],
                           "close_buttons": ["OK"]}],
        }
        f.write_text(json.dumps(data), encoding="utf-8")

        patterns, source = load_session_expired_patterns(f)
        captured = capsys.readouterr()
        assert "WARNING" not in captured.err
        assert source == "file"

    def test_v2_without_verified_by_emits_warning(self, tmp_path, capsys):
        """v2 + verified_by 未指定 → stderr に WARNING (fail-open で起動継続)"""
        f = tmp_path / "session_expired_patterns.json"
        data = {
            "version": "1.0",
            "patterns": [{"title_re": r"^再ログイン$", "body_keywords": [],
                           "close_buttons": ["OK"]}],
        }
        f.write_text(json.dumps(data), encoding="utf-8")

        patterns, source = load_session_expired_patterns(f)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "verified_by" in captured.err
        # fail-open: patterns は読まれる
        assert source == "file"
        assert len(patterns) == 1

    def test_legacy_list_emits_warning(self, tmp_path, capsys):
        """legacy list 形式 → v2 移行推奨 WARNING (fail-open)"""
        f = tmp_path / "session_expired_patterns.json"
        data = [{"title_re": r"^再ログイン$", "body_keywords": [],
                  "close_buttons": ["OK"]}]
        f.write_text(json.dumps(data), encoding="utf-8")

        patterns, source = load_session_expired_patterns(f)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "legacy" in captured.err
        assert source == "file"

    def test_v2_with_empty_verified_by_emits_warning(self, tmp_path, capsys):
        """verified_by が空文字列 → WARNING (None 判定と同じ)"""
        f = tmp_path / "session_expired_patterns.json"
        data = {
            "version": "1.0",
            "verified_by": "",
            "patterns": [{"title_re": r"^再ログイン$", "body_keywords": [],
                           "close_buttons": ["OK"]}],
        }
        f.write_text(json.dumps(data), encoding="utf-8")

        patterns, source = load_session_expired_patterns(f)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_file_absent_no_warning(self, tmp_path, capsys):
        """ファイル不在 → default 使用、 WARNING 出ない"""
        patterns, source = load_session_expired_patterns(tmp_path / "missing.json")
        captured = capsys.readouterr()
        assert "WARNING" not in captured.err
        assert source == "default"

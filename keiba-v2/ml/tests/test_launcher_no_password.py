#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""launcher.py が IPAT 暗証番号を自動入力する経路を持っていないことを CI で検証する。

シズネレビュー (Session 131 / 🔴 C) の必須テスト:
  「暗証番号入力 = 永続手動」 の境界線を文書宣言だけで守るのは弱い。
  ソースコードレベルで以下を構造的に禁止する。

  1. credential 取得モジュール (keyring / getpass / pyperclip 等) の import 禁止
  2. 暗証番号らしき値を type/send するコードパターン禁止
     (例: send_keys(暗証番号), set_edit_text(ﾊﾟｽﾜｰﾄﾞ))
  3. 環境変数や config から暗証番号を読み出すパターン禁止
     (例: os.getenv("IPAT_PASSWORD"))

このテストは launcher.py 改修時に「便利だから自動入力しよう」 と緩む将来の自分への
防御線として機能する。 失敗時は「設計原則に違反するコードを足した」 と認識すること。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_launcher_no_password.py -v
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest


LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "target_clicker" / "launcher.py"


# 暗証番号を扱いそうな module の import を全面禁止
FORBIDDEN_IMPORTS = (
    "keyring",
    "getpass",
    "pyperclip",       # クリップボード経由の貼り付けも禁止
)


# launcher.py 内で暗証番号を意味する識別子。 ローカル変数として作るのも禁止
FORBIDDEN_IDENTIFIERS_RE = re.compile(
    r"(?:^|[^a-zA-Z0-9_])"  # 前境界
    r"(?:ipat_password|ipat_pwd|ipat_passwd|pin_code|"
    r"暗証番号_value|暗証番号_input|password_value)"
    r"(?:$|[^a-zA-Z0-9_])",  # 後境界
    re.IGNORECASE,
)


def _read_launcher_source() -> str:
    if not LAUNCHER_PATH.exists():
        pytest.skip(f"launcher.py not found at {LAUNCHER_PATH}")
    return LAUNCHER_PATH.read_text(encoding="utf-8")


def _parse_launcher_ast() -> ast.Module:
    src = _read_launcher_source()
    return ast.parse(src, filename=str(LAUNCHER_PATH))


class TestNoCredentialImports:
    """credential 取得モジュールの import を AST レベルで全面禁止"""

    def test_no_forbidden_module_imports(self):
        tree = _parse_launcher_ast()
        offenders: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS:
                        offenders.append((node.lineno, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                if node.module in FORBIDDEN_IMPORTS:
                    offenders.append((node.lineno,
                                       f"from {node.module} import ..."))
        assert not offenders, (
            "launcher.py must NOT import credential modules. "
            f"Found: {offenders}. "
            "Reason: 暗証番号自動入力は永続手動の設計原則違反 (シズネ 🔴 C)"
        )


class TestNoPasswordTyping:
    """暗証番号らしき値を type/send するコードパターン禁止"""

    @pytest.mark.parametrize("forbidden_pattern", [
        # send_keys / type_keys / set_edit_text に password 系を渡す
        r"send_keys\s*\([^)]*(?:暗証|ﾊﾟｽﾜｰﾄﾞ|パスワード|password|pwd|passwd|pin)",
        r"type_keys\s*\([^)]*(?:暗証|ﾊﾟｽﾜｰﾄﾞ|パスワード|password|pwd|passwd|pin)",
        r"set_edit_text\s*\([^)]*(?:暗証|ﾊﾟｽﾜｰﾄﾞ|パスワード|password|pwd|passwd|pin)",
        # pyautogui.typewrite 系
        r"typewrite\s*\([^)]*(?:暗証|ﾊﾟｽﾜｰﾄﾞ|パスワード|password|pwd|passwd|pin)",
    ])
    def test_no_password_typing(self, forbidden_pattern):
        src = _read_launcher_source()
        m = re.search(forbidden_pattern, src, re.IGNORECASE)
        assert m is None, (
            f"launcher.py must NOT type passwords. "
            f"Pattern {forbidden_pattern!r} matched: {m.group() if m else 'N/A'}. "
            "Reason: 暗証番号自動入力は永続手動の設計原則違反 (シズネ 🔴 C)"
        )


class TestNoCredentialEnvOrConfig:
    """環境変数や config から暗証番号を読むパターン禁止"""

    @pytest.mark.parametrize("forbidden_pattern", [
        # 環境変数名に PASSWORD/PWD/PASSWD/PIN を含む
        r"os\.getenv\s*\([^)]*(?:PASSWORD|PWD|PASSWD|\bPIN\b)",
        r"os\.environ\[[^]]*(?:PASSWORD|PWD|PASSWD|\bPIN\b)",
        r"os\.environ\.get\s*\([^)]*(?:PASSWORD|PWD|PASSWD|\bPIN\b)",
        # 既知の credential 環境変数名
        r"\bIPAT_PASSWORD\b",
        r"\bIPAT_PWD\b",
        r"\bIPAT_PASSWD\b",
        r"\bIPAT_PIN\b",
    ])
    def test_no_credential_env(self, forbidden_pattern):
        src = _read_launcher_source()
        m = re.search(forbidden_pattern, src)
        assert m is None, (
            f"launcher.py must NOT capture credentials from env. "
            f"Pattern {forbidden_pattern!r} matched: {m.group() if m else 'N/A'}. "
            "Reason: 暗証番号自動入力は永続手動の設計原則違反 (シズネ 🔴 C)"
        )


class TestNoForbiddenIdentifiers:
    """暗証番号らしき変数名 (例: ipat_password / pin_code) を作らない"""

    def test_no_forbidden_identifiers(self):
        src = _read_launcher_source()
        offenders = []
        for match in FORBIDDEN_IDENTIFIERS_RE.finditer(src):
            line_no = src[:match.start()].count("\n") + 1
            offenders.append((line_no, match.group().strip()))
        assert not offenders, (
            f"launcher.py contains forbidden credential identifiers: {offenders}. "
            "Reason: 暗証番号自動入力は永続手動の設計原則違反 (シズネ 🔴 C)"
        )


class TestModuleDocstringAcknowledgesPolicy:
    """launcher.py の docstring に「暗証番号は永続手動」 ポリシーが明記されていること

    将来「ポリシーを忘れて自動入力実装」 を防ぐ、 文書レベルの防御線。
    """

    def test_docstring_states_password_is_manual(self):
        src = _read_launcher_source()
        # module docstring を取得
        tree = ast.parse(src)
        docstring = ast.get_docstring(tree)
        assert docstring is not None, "launcher.py must have a module docstring"
        # 「暗証番号」 「手動」 が同じ docstring に登場すること
        assert "暗証番号" in docstring, (
            "launcher.py docstring must explicitly mention 暗証番号 policy"
        )
        assert ("手動" in docstring or "永続" in docstring), (
            "launcher.py docstring must state IPAT 暗証番号 is intentionally manual "
            "(シズネ 🔴 C)"
        )

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mykeibadb MySQL接続ユーティリティ

mykeibadb (JRA-VAN → MySQL) からデータを取得するための接続モジュール。

環境変数:
    MYKEIBADB_HOST: MySQLホスト（デフォルト: localhost）
    MYKEIBADB_PORT: MySQLポート（デフォルト: 3306）
    MYKEIBADB_USER: MySQLユーザー（デフォルト: root）
    MYKEIBADB_PASS: MySQLパスワード（デフォルト: test123!）
    MYKEIBADB_DB:   データベース名（デフォルト: mykeibadb）
"""

import os
from contextlib import contextmanager
from typing import Optional

import mysql.connector


def _get_config() -> dict:
    return {
        'host': os.getenv('MYKEIBADB_HOST', 'localhost'),
        'port': int(os.getenv('MYKEIBADB_PORT', '3306')),
        'user': os.getenv('MYKEIBADB_USER', 'root'),
        'password': os.getenv('MYKEIBADB_PASS', 'test123!'),
        'database': os.getenv('MYKEIBADB_DB', 'mykeibadb'),
        'charset': 'utf8mb4',
    }


@contextmanager
def get_connection():
    """MySQL接続のコンテキストマネージャ"""
    conn = mysql.connector.connect(**_get_config())
    try:
        yield conn
    finally:
        conn.close()


def query(sql: str, params: Optional[tuple] = None) -> list:
    """SQLクエリを実行して結果をdict形式で返す"""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        cursor.close()
        return rows


def query_one(sql: str, params: Optional[tuple] = None) -> Optional[dict]:
    """1行だけ取得"""
    rows = query(sql, params)
    return rows[0] if rows else None

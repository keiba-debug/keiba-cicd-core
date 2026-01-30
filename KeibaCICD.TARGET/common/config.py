#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KeibaCICD.TARGET 共通設定モジュール

環境変数ベースのパス管理を提供し、全スクリプトで統一的に使用できます。

環境変数:
    KEIBA_DATA_ROOT_DIR: 競馬データルートディレクトリ（デフォルト: E:/share/KEIBA-CICD/data2）
    JV_DATA_ROOT_DIR: JRA-VAN生データディレクトリ（デフォルト: Y:/）

Usage:
    from common.config import get_keiba_data_root, get_target_data_dir

    data_root = get_keiba_data_root()
    output_path = get_target_data_dir() / "race_type_standards.json"
"""

import os
from pathlib import Path
from typing import Optional


# =============================================================================
# 環境変数取得ヘルパー
# =============================================================================

def _get_env_path(key: str, default: str) -> Path:
    """
    環境変数からパスを取得

    Args:
        key: 環境変数名
        default: デフォルト値

    Returns:
        Pathオブジェクト
    """
    value = os.getenv(key)
    if value:
        return Path(value)
    return Path(default)


# =============================================================================
# .env ファイル読み込み（オプション）
# =============================================================================

def load_dotenv_if_available() -> None:
    """
    .envファイルが存在する場合は読み込む

    探索順序:
        1. ../../KeibaCICD.keibabook/.env
        2. ../.env
    """
    try:
        from dotenv import load_dotenv
        env_candidates = [
            Path(__file__).resolve().parents[2] / "KeibaCICD.keibabook" / ".env",
            Path(__file__).resolve().parents[1] / ".env",
        ]
        for env_path in env_candidates:
            if env_path.exists():
                load_dotenv(env_path)
                break
    except ImportError:
        pass


# 初期化時に.env読み込み
load_dotenv_if_available()


# =============================================================================
# データディレクトリパス取得
# =============================================================================

def get_keiba_data_root() -> Path:
    """
    競馬データルートディレクトリを取得

    Returns:
        KEIBA_DATA_ROOT_DIR の値（デフォルト: E:/share/KEIBA-CICD/data2）
    """
    return _get_env_path("KEIBA_DATA_ROOT_DIR", "E:/share/KEIBA-CICD/data2")


def get_jv_data_root() -> Path:
    """
    JRA-VAN生データルートディレクトリを取得

    Returns:
        JV_DATA_ROOT_DIR の値（デフォルト: Y:/）
    """
    return _get_env_path("JV_DATA_ROOT_DIR", "Y:/")


def get_target_data_dir() -> Path:
    """
    TARGET専用データディレクトリを取得

    Returns:
        {KEIBA_DATA_ROOT_DIR}/target
    """
    return get_keiba_data_root() / "target"


def get_log_dir() -> Path:
    """
    ログディレクトリを取得

    Returns:
        {KEIBA_DATA_ROOT_DIR}/logs
    """
    return get_keiba_data_root() / "logs"


def get_races_dir() -> Path:
    """
    レースデータディレクトリを取得

    Returns:
        {KEIBA_DATA_ROOT_DIR}/races
    """
    return get_keiba_data_root() / "races"


def get_horses_dir() -> Path:
    """
    馬データディレクトリを取得

    Returns:
        {KEIBA_DATA_ROOT_DIR}/horses
    """
    return get_keiba_data_root() / "horses"


# =============================================================================
# JRA-VAN データパス
# =============================================================================

def get_jv_de_data_path() -> Path:
    """
    JRA-VAN DE_DATA（出馬表）パスを取得

    Returns:
        {JV_DATA_ROOT_DIR}/DE_DATA
    """
    return get_jv_data_root() / "DE_DATA"


def get_jv_se_data_path() -> Path:
    """
    JRA-VAN SE_DATA（成績）パスを取得

    Returns:
        {JV_DATA_ROOT_DIR}/SE_DATA
    """
    return get_jv_data_root() / "SE_DATA"


def get_jv_ck_data_path() -> Path:
    """
    JRA-VAN CK_DATA（調教）パスを取得

    Returns:
        {JV_DATA_ROOT_DIR}/CK_DATA
    """
    return get_jv_data_root() / "CK_DATA"


# =============================================================================
# ディレクトリ作成ヘルパー
# =============================================================================

def ensure_dir(path: Path) -> Path:
    """
    ディレクトリが存在しない場合は作成

    Args:
        path: ディレクトリパス

    Returns:
        作成したディレクトリパス
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_target_dirs() -> None:
    """
    TARGET関連の必要なディレクトリを作成
    """
    ensure_dir(get_target_data_dir())
    ensure_dir(get_target_data_dir() / "analysis")
    ensure_dir(get_target_data_dir() / "training_summary")
    ensure_dir(get_log_dir())


# =============================================================================
# 設定情報の表示
# =============================================================================

def print_config() -> None:
    """
    現在の設定を表示（デバッグ用）
    """
    print("=" * 60)
    print("KeibaCICD.TARGET Configuration")
    print("=" * 60)
    print(f"KEIBA_DATA_ROOT_DIR: {get_keiba_data_root()}")
    print(f"JV_DATA_ROOT_DIR:    {get_jv_data_root()}")
    print()
    print("Directories:")
    print(f"  - Target:  {get_target_data_dir()}")
    print(f"  - Logs:    {get_log_dir()}")
    print(f"  - Races:   {get_races_dir()}")
    print(f"  - Horses:  {get_horses_dir()}")
    print()
    print("JRA-VAN Data:")
    print(f"  - DE_DATA: {get_jv_de_data_path()}")
    print(f"  - SE_DATA: {get_jv_se_data_path()}")
    print(f"  - CK_DATA: {get_jv_ck_data_path()}")
    print("=" * 60)


# =============================================================================
# CLI用（このファイルを直接実行した場合）
# =============================================================================

if __name__ == "__main__":
    print_config()
    print("\nEnsuring directories...")
    ensure_target_dirs()
    print("Done!")

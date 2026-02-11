#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KeibaCICD v4 設定モジュール

環境変数:
    KEIBA_DATA_ROOT: データルート（デフォルト: C:/KEIBA-CICD/data3）
    JV_DATA_ROOT:    JRA-VAN生データ（デフォルト: C:/TFJV）
"""

import os
from pathlib import Path
from typing import Optional


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass


_load_dotenv()


def _env_path(key: str, default: str) -> Path:
    return Path(os.getenv(key, default))


# === データルート ===

def data_root() -> Path:
    return _env_path("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")

def jv_root() -> Path:
    return _env_path("JV_DATA_ROOT", "C:/TFJV")


# === data3 内のパス ===

def races_dir() -> Path:
    return data_root() / "races"

def keibabook_dir() -> Path:
    return data_root() / "keibabook"

def masters_dir() -> Path:
    return data_root() / "masters"

def horses_dir() -> Path:
    return masters_dir() / "horses"

def indexes_dir() -> Path:
    return data_root() / "indexes"

def ml_dir() -> Path:
    return data_root() / "ml"

def userdata_dir() -> Path:
    return data_root() / "userdata"


# === JRA-VAN 生データパス ===

def jv_se_data_path() -> Path:
    return jv_root() / "SE_DATA"

def jv_sr_data_path() -> Path:
    return jv_root() / "SE_DATA"  # SR*.DATもSE_DATA内にある

def jv_um_data_path() -> Path:
    return jv_root() / "UM_DATA"

def jv_ck_data_path() -> Path:
    return jv_root() / "CK_DATA"

def jv_de_data_path() -> Path:
    return jv_root() / "DE_DATA"


# === ユーティリティ ===

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def print_config() -> None:
    print("=" * 50)
    print("KeibaCICD v4 Configuration")
    print("=" * 50)
    print(f"DATA_ROOT:    {data_root()}")
    print(f"JV_DATA_ROOT: {jv_root()}")
    print()
    print("Data directories:")
    print(f"  races:      {races_dir()}")
    print(f"  keibabook:  {keibabook_dir()}")
    print(f"  masters:    {masters_dir()}")
    print(f"  indexes:    {indexes_dir()}")
    print(f"  ml:         {ml_dir()}")
    print()
    print("JRA-VAN raw data:")
    print(f"  SE_DATA:    {jv_se_data_path()}")
    print(f"  UM_DATA:    {jv_um_data_path()}")
    print(f"  CK_DATA:    {jv_ck_data_path()}")
    print(f"  DE_DATA:    {jv_de_data_path()}")
    print("=" * 50)


if __name__ == "__main__":
    print_config()

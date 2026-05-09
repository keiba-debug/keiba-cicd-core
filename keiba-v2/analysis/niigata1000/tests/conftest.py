"""Phase 3a テスト共通fixture (vega-niigata1000)

Pin:
  - 2018106612: 千直経験豊富 (cutoff_date 変動の挙動検証)
  - 2023104705: 2025-06-29 デビュー馬 (欠損時挙動検証)

実データ (horse_history_cache.json, 248MB) を session-scoped で1回だけロード。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# keiba-v2 ルートを sys.path へ
KEIBA_V2_ROOT = Path(__file__).resolve().parents[3]
if str(KEIBA_V2_ROOT) not in sys.path:
    sys.path.insert(0, str(KEIBA_V2_ROOT))

HISTORY_CACHE_PATH = Path("C:/KEIBA-CICD/data3/ml/horse_history_cache.json")
PEDIGREE_INDEX_PATH = Path("C:/KEIBA-CICD/data3/indexes/pedigree_index.json")
SIRE_STATS_PATH = Path("C:/KEIBA-CICD/data3/indexes/sire_stats_index.json")


@pytest.fixture(scope="session")
def history_cache() -> dict:
    """horse_history_cache.json を session 単位で1回ロード"""
    if not HISTORY_CACHE_PATH.exists():
        pytest.skip(f"history cache not found: {HISTORY_CACHE_PATH}")
    with HISTORY_CACHE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def pedigree_index() -> dict:
    if not PEDIGREE_INDEX_PATH.exists():
        pytest.skip(f"pedigree index not found: {PEDIGREE_INDEX_PATH}")
    with PEDIGREE_INDEX_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sire_stats() -> dict:
    if not SIRE_STATS_PATH.exists():
        pytest.skip(f"sire stats not found: {SIRE_STATS_PATH}")
    with SIRE_STATS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def pin_veteran() -> str:
    """千直経験豊富な Pin 馬"""
    return "2018106612"


@pytest.fixture(scope="session")
def pin_debut() -> str:
    """2025-06-29 デビュー馬"""
    return "2023104705"

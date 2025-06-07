"""
競馬ブック バッチ処理システム

統合されたバッチ処理機能を提供します。
"""

__version__ = "1.0.0"
__author__ = "Keiba CICD Core Team"

# 主要なクラスとモジュールをエクスポート
from .core.common import (
    parse_date,
    setup_batch_logger,
    ensure_batch_directories,
    create_authenticated_session,
    BatchStats
)

from .data_fetcher import DataFetcher

__all__ = [
    "parse_date",
    "setup_batch_logger", 
    "ensure_batch_directories",
    "create_authenticated_session",
    "BatchStats",
    "DataFetcher"
] 
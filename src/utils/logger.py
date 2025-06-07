"""
ログ管理ユーティリティ

アプリケーション全体のログ設定を管理します。
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import Config


def setup_logger(
    name: str = "keiba_scraper",
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True
) -> logging.Logger:
    """
    ロガーをセットアップする
    
    Args:
        name: ロガー名
        level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: ログファイルのパス（Noneの場合は自動生成）
        console_output: コンソール出力の有効化
        
    Returns:
        logging.Logger: 設定されたロガー
    """
    # ディレクトリが存在することを確認
    Config.ensure_directories()
    
    # ロガーの作成
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 既存のハンドラーをクリア
    logger.handlers.clear()
    
    # フォーマッターの作成
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラーの追加
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # ファイルハンドラーの追加
    if log_file is None:
        # デフォルトのログファイル名を生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = Config.LOG_DIR / f"{name}_{timestamp}.log"
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    logger.info(f"ロガーを初期化しました: {name}")
    logger.info(f"ログファイル: {log_file}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    既存のロガーを取得する
    
    Args:
        name: ロガー名
        
    Returns:
        logging.Logger: ロガー
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    ロガー機能を提供するMixinクラス
    """
    
    @property
    def logger(self) -> logging.Logger:
        """
        ロガーを取得する
        
        Returns:
            logging.Logger: クラス名に基づいたロガー
        """
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger
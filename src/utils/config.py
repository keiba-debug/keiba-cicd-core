"""
設定管理クラス

アプリケーションの設定を管理します。
"""

import os
from pathlib import Path
from typing import Dict, List


class Config:
    """
    設定管理クラス
    
    環境変数やデフォルト値を管理します。
    """
    
    # プロジェクトルートディレクトリ
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    # データディレクトリ
    DATA_DIR = PROJECT_ROOT / "data"
    KEIBABOOK_DIR = DATA_DIR / "keibabook"
    SEISEKI_DIR = KEIBABOOK_DIR / "seiseki"
    SHUTSUBA_DIR = KEIBABOOK_DIR / "shutsuba"
    DEBUG_DIR = DATA_DIR / "debug"
    
    # ログディレクトリ
    LOG_DIR = PROJECT_ROOT / "logs"
    
    # 競馬ブック関連設定
    KEIBABOOK_BASE_URL = "https://www.keibabook.co.jp"
    KEIBABOOK_SEISEKI_URL = "https://www.keibabook.co.jp/race/result/"
    
    # スクレイピング設定
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    DEFAULT_TIMEOUT = 10
    DEFAULT_SLEEP_TIME = 2.0
    
    # リトライ設定
    MAX_RETRY_COUNT = 3
    RETRY_DELAY = 5.0
    
    @classmethod
    def get_env(cls, key: str, default: str = "") -> str:
        """
        環境変数を取得する
        
        Args:
            key: 環境変数のキー
            default: デフォルト値
            
        Returns:
            str: 環境変数の値
        """
        return os.getenv(key, default)
    
    @classmethod
    def get_required_cookies(cls) -> List[Dict[str, str]]:
        """
        競馬ブックで必要なCookieを取得する
        
        Returns:
            List[Dict[str, str]]: 必要なCookieのリスト
        """
        return [
            {
                "name": "keibabook_session",
                "value": cls.get_env("KEIBABOOK_SESSION", "sample_session_value"),
                "domain": ".keibabook.co.jp",
                "path": "/",
                "secure": True,
                "httpOnly": True
            },
            {
                "name": "tk",
                "value": cls.get_env("KEIBABOOK_TK", "sample_tk_value"),
                "domain": ".keibabook.co.jp",
                "path": "/",
                "secure": True,
                "httpOnly": False
            },
            {
                "name": "XSRF-TOKEN",
                "value": cls.get_env("KEIBABOOK_XSRF_TOKEN", "sample_xsrf_value"),
                "domain": ".keibabook.co.jp",
                "path": "/",
                "secure": True,
                "httpOnly": False
            }
        ]
    
    @classmethod
    def ensure_directories(cls) -> None:
        """
        必要なディレクトリが存在することを確認し、存在しない場合は作成する
        """
        directories = [
            cls.DATA_DIR,
            cls.KEIBABOOK_DIR,
            cls.SEISEKI_DIR,
            cls.SHUTSUBA_DIR,
            cls.DEBUG_DIR,
            cls.LOG_DIR
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_debug_mode(cls) -> bool:
        """
        デバッグモードが有効かどうかを取得する
        
        Returns:
            bool: デバッグモードが有効な場合True
        """
        return cls.get_env("DEBUG", "false").lower() in ("true", "1", "yes", "on")
    
    @classmethod
    def get_headless_mode(cls) -> bool:
        """
        ヘッドレスモードが有効かどうかを取得する
        
        Returns:
            bool: ヘッドレスモードが有効な場合True
        """
        return cls.get_env("HEADLESS", "true").lower() in ("true", "1", "yes", "on")
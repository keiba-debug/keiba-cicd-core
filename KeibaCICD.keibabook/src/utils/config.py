"""
設定管理クラス

アプリケーションの設定を管理します。
"""

import os
from pathlib import Path
from typing import Dict, List

# .envファイルの読み込み
try:
    from dotenv import load_dotenv
    # プロジェクトルートの.envファイルを読み込み
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenvがインストールされていない場合は警告
    print("警告: python-dotenvがインストールされていません。環境変数を手動で設定してください。")


class Config:
    """
    設定管理クラス
    
    環境変数やデフォルト値を管理します。
    """
    
    # プロジェクトルートディレクトリ
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    
    # 競馬ブック関連設定
    KEIBABOOK_BASE_URL = "https://p.keibabook.co.jp"
    KEIBABOOK_SEISEKI_URL = "https://p.keibabook.co.jp/cyuou/seiseki/"
    KEIBABOOK_SHUTSUBA_URL = "https://p.keibabook.co.jp/cyuou/shutsuba/"
    KEIBABOOK_CYOKYO_URL = "https://p.keibabook.co.jp/cyuou/cyokyo/0/0/"
    KEIBABOOK_DANWA_URL = "https://p.keibabook.co.jp/cyuou/danwa/0/"
    KEIBABOOK_SYOIN_URL = "https://p.keibabook.co.jp/cyuou/syoin/0/"
    KEIBABOOK_NITTEI_URL = "https://p.keibabook.co.jp/cyuou/nittei/"
    
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
    def get_data_root_dir(cls) -> Path:
        """
        データルートディレクトリを取得する
        
        環境変数 KEIBA_DATA_ROOT_DIR で変更可能
        
        Returns:
            Path: データルートディレクトリのパス
        """
        custom_path = cls.get_env("KEIBA_DATA_ROOT_DIR")
        if custom_path:
            return Path(custom_path)
        return cls.PROJECT_ROOT / "data"
    
    @classmethod
    def get_data_dir(cls) -> Path:
        """
        メインデータディレクトリを取得する
        
        環境変数 KEIBA_DATA_DIR で変更可能
        
        Returns:
            Path: メインデータディレクトリのパス
        """
        custom_path = cls.get_env("KEIBA_DATA_DIR")
        if custom_path:
            return Path(custom_path)
        return cls.get_data_root_dir()
    
    @classmethod
    def get_keibabook_dir(cls) -> Path:
        """
        競馬ブックデータディレクトリを取得する
        
        環境変数 KEIBA_KEIBABOOK_DIR で変更可能
        
        Returns:
            Path: 競馬ブックデータディレクトリのパス
        """
        custom_path = cls.get_env("KEIBA_KEIBABOOK_DIR")
        if custom_path:
            return Path(custom_path)
        return cls.get_data_dir() / "keibabook"
    
    @classmethod
    def get_seiseki_dir(cls) -> Path:
        """
        成績データディレクトリを取得する
        
        環境変数 KEIBA_SEISEKI_DIR で変更可能
        
        Returns:
            Path: 成績データディレクトリのパス
        """
        custom_path = cls.get_env("KEIBA_SEISEKI_DIR")
        if custom_path:
            return Path(custom_path)
        return cls.get_keibabook_dir() / "seiseki"
    
    @classmethod
    def get_shutsuba_dir(cls) -> Path:
        """
        出馬表データディレクトリを取得する
        
        環境変数 KEIBA_SHUTSUBA_DIR で変更可能
        
        Returns:
            Path: 出馬表データディレクトリのパス
        """
        custom_path = cls.get_env("KEIBA_SHUTSUBA_DIR")
        if custom_path:
            return Path(custom_path)
        return cls.get_keibabook_dir() / "shutsuba"
    
    @classmethod
    def get_debug_dir(cls) -> Path:
        """
        デバッグデータディレクトリを取得する
        
        環境変数 KEIBA_DEBUG_DIR で変更可能
        
        Returns:
            Path: デバッグデータディレクトリのパス
        """
        custom_path = cls.get_env("KEIBA_DEBUG_DIR")
        if custom_path:
            return Path(custom_path)
        return cls.get_data_dir() / "debug"
    
    @classmethod
    def get_log_dir(cls) -> Path:
        """
        ログディレクトリを取得する

        環境変数 LOG_DIR または KEIBA_LOG_DIR で変更可能
        デフォルトは KEIBA_DATA_ROOT_DIR/logs

        Returns:
            Path: ログディレクトリのパス
        """
        # LOG_DIRを優先的にチェック
        custom_path = cls.get_env("LOG_DIR")
        if not custom_path:
            # 後方互換性のためKEIBA_LOG_DIRもチェック
            custom_path = cls.get_env("KEIBA_LOG_DIR")
        if custom_path:
            return Path(custom_path)
        # デフォルトはデータルート配下のlogsフォルダ
        return cls.get_data_root_dir() / "logs"
    
    # 後方互換性のためのプロパティ
    @property
    def DATA_DIR(self) -> Path:
        """データディレクトリ（後方互換性）"""
        return self.get_data_dir()
    
    @property
    def KEIBABOOK_DIR(self) -> Path:
        """競馬ブックディレクトリ（後方互換性）"""
        return self.get_keibabook_dir()
    
    @property
    def SEISEKI_DIR(self) -> Path:
        """成績ディレクトリ（後方互換性）"""
        return self.get_seiseki_dir()
    
    @property
    def SHUTSUBA_DIR(self) -> Path:
        """出馬表ディレクトリ（後方互換性）"""
        return self.get_shutsuba_dir()
    
    @property
    def DEBUG_DIR(self) -> Path:
        """デバッグディレクトリ（後方互換性）"""
        return self.get_debug_dir()
    
    @property
    def LOG_DIR(self) -> Path:
        """ログディレクトリ（後方互換性）"""
        return self.get_log_dir()
    
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
                "domain": "p.keibabook.co.jp",
                "path": "/",
                "secure": True,
                "httpOnly": True
            },
            {
                "name": "tk",
                "value": cls.get_env("KEIBABOOK_TK", "sample_tk_value"),
                "domain": "p.keibabook.co.jp",
                "path": "/",
                "secure": True,
                "httpOnly": False
            },
            {
                "name": "XSRF-TOKEN",
                "value": cls.get_env("KEIBABOOK_XSRF_TOKEN", "sample_xsrf_value"),
                "domain": "p.keibabook.co.jp",
                "path": "/",
                "secure": True,
                "httpOnly": False
            }
        ]
    
    @classmethod
    def ensure_directories(cls) -> None:
        """
        必要なディレクトリが存在することを確認し、存在しない場合は作成する
        v2.3対応: 同一フォルダ保存。未使用の keibabook サブフォルダは作成しない
        """
        directories = [
            cls.get_data_dir(),
            # cls.get_keibabook_dir(),  # 未使用のため作成しない
            cls.get_debug_dir(),
            cls.get_log_dir()
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
    
    @classmethod
    def get_log_level(cls) -> str:
        """
        ログレベルを取得する
        
        環境変数 LOG_LEVEL で変更可能
        
        Returns:
            str: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        """
        return cls.get_env("LOG_LEVEL", "INFO").upper()
    
    @classmethod
    def get_current_config_summary(cls) -> Dict[str, str]:
        """
        現在の設定を要約として取得する
        
        Returns:
            Dict[str, str]: 設定の要約
        """
        return {
            "data_root_dir": str(cls.get_data_root_dir()),
            "data_dir": str(cls.get_data_dir()),
            "keibabook_dir": str(cls.get_keibabook_dir()),
            "seiseki_dir": str(cls.get_seiseki_dir()),
            "shutsuba_dir": str(cls.get_shutsuba_dir()),
            "debug_dir": str(cls.get_debug_dir()),
            "log_dir": str(cls.get_log_dir()),
            "log_level": cls.get_log_level(),
            "debug_mode": str(cls.get_debug_mode()),
            "headless_mode": str(cls.get_headless_mode())
        }
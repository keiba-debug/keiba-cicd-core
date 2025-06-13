#!/usr/bin/env python3
"""
バッチ処理共通ユーティリティ

全てのバッチ処理で使用される共通機能を提供します。
"""

import os
import sys
import logging
import datetime
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# プロジェクト内のConfigクラスをインポート
try:
    from ...utils.config import Config
except ImportError:
    # 相対インポートを試す
    try:
        from utils.config import Config
    except ImportError:
        # Configクラスが利用できない場合のダミー実装
        class Config:
            @classmethod
            def get_required_cookies(cls):
                return [
                    {
                        "name": "keibabook_session",
                        "value": os.getenv("KEIBABOOK_SESSION", ""),
                        "domain": "p.keibabook.co.jp"
                    },
                    {
                        "name": "tk",
                        "value": os.getenv("KEIBABOOK_TK", ""),
                        "domain": "p.keibabook.co.jp"
                    },
                    {
                        "name": "XSRF-TOKEN",
                        "value": os.getenv("KEIBABOOK_XSRF_TOKEN", ""),
                        "domain": "p.keibabook.co.jp"
                    }
                ]


def parse_date(date_str: str) -> datetime.date:
    """
    日付文字列をパースしてdatetime.dateオブジェクトを返す
    
    Args:
        date_str: 日付文字列 (YYYY/MM/DD, YY/MM/DD, YYYYMMDD形式)
        
    Returns:
        datetime.date: パースされた日付
        
    Raises:
        ValueError: サポートされていない日付形式の場合
    """
    try:
        # 2025/5/31 または 25/5/31 の形式をサポート
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts[0]) == 2:
                parts[0] = '20' + parts[0]
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        # 20250531 の形式をサポート
        elif len(date_str) == 8:
            return datetime.date(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]))
        else:
            raise ValueError(f"サポートされていない日付形式です: {date_str}")
    except Exception as e:
        raise ValueError(f"日付の解析に失敗しました: {date_str}, エラー: {e}")


def setup_batch_logger(name: str, log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    バッチ処理用のロガーを設定
    
    Args:
        name: ロガー名
        log_level: ログレベル (DEBUG, INFO, WARNING, ERROR)
        log_file: ログファイルパス（省略時は自動生成）
        
    Returns:
        logging.Logger: 設定されたロガー
    """
    # 環境変数からログディレクトリを取得
    log_dir = os.environ.get('KEIBA_LOG_DIR')
    if log_dir:
        logs_dir = Path(log_dir)
    else:
        # 環境変数が設定されていない場合はデフォルト
        base_dir = Path(os.environ.get('KEIBA_DATA_DIR', '.'))
        logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # ログファイル名を自動生成
    if log_file is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f'{name}_{timestamp}.log'
    
    # ロガーを作成
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 既存のハンドラーをクリア
    logger.handlers.clear()
    
    # フォーマッターを設定
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ファイルハンドラー
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 初期ログ出力
    logger.info(f"ロガー '{name}' を初期化しました")
    logger.info(f"ログファイル: {log_file}")
    logger.info(f"ログレベル: {log_level}")
    
    return logger


def get_base_directories() -> Dict[str, str]:
    """
    データ保存用のベースディレクトリパスを取得
    
    Returns:
        Dict[str, str]: ディレクトリパスの辞書
    """
    # 環境変数からkeibabook用ディレクトリを取得
    keibabook_dir = os.environ.get('KEIBA_KEIBABOOK_DIR')
    if keibabook_dir:
        base_dir = Path(keibabook_dir)
    else:
        # 環境変数が設定されていない場合はデフォルト
        base_dir = Path("data/keibabook")
    
    return {
        # レースID保存用
        'race_ids': str(base_dir / "race_ids"),
        
        # JSON保存用（すべて同一フォルダ）
        'json_base': str(base_dir),  # 環境変数で指定されたディレクトリ直下
    }


def ensure_batch_directories():
    """
    バッチ処理に必要なディレクトリを作成
    """
    dirs = get_base_directories()
    
    # 必要なディレクトリを作成
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
        print(f"✅ ディレクトリ確認/作成: {dir_path}")


def get_race_ids_file_path(date_str: str) -> str:
    """
    レースIDファイルのパスを取得
    
    Args:
        date_str: 日付文字列 (YYYYMMDD)
        
    Returns:
        str: レースIDファイルのフルパス
    """
    dirs = get_base_directories()
    return os.path.join(dirs['race_ids'], f"{date_str}_info.json")


def get_json_file_path(data_type: str, identifier: str) -> str:
    """
    JSONファイルの保存パスを取得
    
    Args:
        data_type: データタイプ (seiseki, shutsuba, cyokyo, danwa, nittei)
        identifier: ファイル識別子 (race_idまたは日付)
        
    Returns:
        str: JSONファイルのフルパス
    """
    dirs = get_base_directories()
    filename = f"{data_type}_{identifier}.json"
    return os.path.join(dirs['json_base'], filename)


def create_authenticated_session() -> requests.Session:
    """
    Cookie認証付きのHTTPセッションを作成
    
    Returns:
        requests.Session: 認証設定済みのセッション
    """
    session = requests.Session()
    
    # ヘッダーを設定
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    
    # 必要なCookieを設定
    cookies_data = Config.get_required_cookies()
    for cookie in cookies_data:
        if cookie['value']:  # 値が設定されている場合のみ
            session.cookies.set(
                name=cookie['name'],
                value=cookie['value'],
                domain=cookie.get('domain', 'p.keibabook.co.jp'),
                path=cookie.get('path', '/')
            )
    
    return session


@dataclass
class BatchStats:
    """バッチ処理の統計情報を管理するクラス"""
    
    total_races: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    processed_races: List[str] = field(default_factory=list)
    failed_races: List[str] = field(default_factory=list)
    
    def start(self):
        """処理開始時刻を記録"""
        self.start_time = datetime.datetime.now()
    
    def finish(self):
        """処理終了時刻を記録"""
        self.end_time = datetime.datetime.now()
    
    def add_success(self, race_id: str):
        """成功したレースを記録"""
        self.success_count += 1
        self.processed_races.append(race_id)
    
    def add_error(self, race_id: str):
        """失敗したレースを記録"""
        self.error_count += 1
        self.failed_races.append(race_id)
    
    def add_skip(self):
        """スキップしたレースを記録"""
        self.skipped_count += 1
    
    @property
    def success_rate(self) -> float:
        """成功率を計算"""
        if self.total_races == 0:
            return 0.0
        return (self.success_count / self.total_races) * 100
    
    @property
    def elapsed_time(self) -> Optional[datetime.timedelta]:
        """経過時間を計算"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """統計情報を辞書形式で返す"""
        return {
            'total_races': self.total_races,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'skipped_count': self.skipped_count,
            'success_rate': f"{self.success_rate:.1f}%",
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'elapsed_time': str(self.elapsed_time) if self.elapsed_time else None,
            'processed_races': self.processed_races,
            'failed_races': self.failed_races
        }
    
    def print_summary(self, logger: Optional[logging.Logger] = None):
        """統計情報のサマリーを表示"""
        output_func = logger.info if logger else print
        
        output_func("=" * 50)
        output_func("📊 バッチ処理統計サマリー")
        output_func("=" * 50)
        output_func(f"📈 処理結果:")
        output_func(f"  - 総レース数: {self.total_races}")
        output_func(f"  - 成功: {self.success_count}")
        output_func(f"  - 失敗: {self.error_count}")
        output_func(f"  - スキップ: {self.skipped_count}")
        output_func(f"  - 成功率: {self.success_rate:.1f}%")
        
        if self.elapsed_time:
            output_func(f"  - 処理時間: {self.elapsed_time}")
        
        if self.failed_races:
            output_func(f"❌ 失敗したレース:")
            for race_id in self.failed_races:
                output_func(f"  - {race_id}")
        
        output_func("=" * 50)


# 開催場所のマッピング（共通定数）
VENUE_MAPPING = {
    "東京": "04",
    "中山": "06", 
    "阪神": "01",
    "京都": "02",
    "新潟": "03",
    "福島": "05",
    "小倉": "07",
    "札幌": "08",
}

# 逆引き用のマッピング
VENUE_CODE_TO_NAME = {v: k for k, v in VENUE_MAPPING.items()}

# データタイプの定義
DATA_TYPES = ["seiseki", "shutsuba", "cyokyo", "danwa"] 
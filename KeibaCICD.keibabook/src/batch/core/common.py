#!/usr/bin/env python3
"""



"""

import os
import sys
import logging
import datetime
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env 未使用時は環境変数のみで動作

# Config
try:
    from ...utils.config import Config
except ImportError:
    # 
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
    datetime.date
    
    Args:
        date_str:  (YYYY/MM/DD, YY/MM/DD, YYYYMMDD)
        
    Returns:
        datetime.date: 
        
    Raises:
        ValueError: 
    """
    try:
        # 2025-08-09 形式 (ハイフン区切り)
        if '-' in date_str:
            parts = date_str.split('-')
            if len(parts) == 3:
                if len(parts[0]) == 2:
                    parts[0] = '20' + parts[0]
                return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        # 2025/5/31  25/5/31 
        elif '/' in date_str:
            parts = date_str.split('/')
            if len(parts[0]) == 2:
                parts[0] = '20' + parts[0]
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        # 20250531 
        elif len(date_str) == 8:
            return datetime.date(int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8]))
        else:
            raise ValueError(f": {date_str}")
    except Exception as e:
        raise ValueError(f": {date_str}, : {e}")


def setup_batch_logger(name: str, log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    
    
    Args:
        name: 
        log_level:  (DEBUG, INFO, WARNING, ERROR)
        log_file: 
        
    Returns:
        logging.Logger: 
    """
    # Config / 環境変数。ドライブルートのみ（例: Z:\）の場合は作成できないためローカルにフォールバック
    try:
        logs_dir = Path(Config.get_log_dir())
    except Exception:
        base_dir = Path(os.environ.get('KEIBA_DATA_ROOT_DIR') or
                        os.environ.get('KEIBA_DATA_DIR') or '.')
        # Windows でドライブルートのみ（Z:\ 等）のときは mkdir で FileNotFoundError になるためローカルへ
        if sys.platform == 'win32' and base_dir.drive and len(base_dir.parts) <= 1:
            base_dir = Path(__file__).resolve().parents[2]  # batch/core -> keibabook/src
        logs_dir = base_dir / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Z: がマウントされていない等で失敗した場合は keibabook 直下の logs を使用
        fallback = Path(__file__).resolve().parents[2] / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        logs_dir = fallback
    
    # 
    if log_file is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f'{name}_{timestamp}.log'
    
    # 
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 
    logger.handlers.clear()
    
    # 
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 
    logger.info(f" '{name}' ")
    logger.info(f": {log_file}")
    logger.info(f": {log_level}")
    
    return logger


def get_base_directories() -> Dict[str, str]:
    """


    Returns:
        Dict[str, str]:
    """
    #  KEIBA_DATA_ROOT_DIR Config
    try:
        base_dir = Path(Config.get_data_root_dir())
    except Exception:
        #
        base_dir = Path(os.environ.get('KEIBA_DATA_ROOT_DIR') or 'data')

    # 新構造フラグを環境変数から取得（デフォルトは旧構造）
    use_new_structure = os.environ.get('USE_NEW_DATA_STRUCTURE', 'false').lower() == 'true'

    if use_new_structure:
        # 新しいフォルダ構造
        return {
            # ID (新構造では日付別に保存)
            'race_ids': str(base_dir / "races"),

            # JSON (tempは日付別)
            'json_base': str(base_dir / "races"),

            # ルートディレクトリ
            'root': str(base_dir),
        }
    else:
        # 旧フォルダ構造（互換性のため）
        return {
            # ID
            'race_ids': str(base_dir / "race_ids"),

            # JSON (tempフォルダに保存)
            'json_base': str(base_dir / "temp"),

            # ルートディレクトリ
            'root': str(base_dir),
        }


def ensure_batch_directories():
    """
    
    """
    dirs = get_base_directories()
    
    # 
    for key, dir_path in dirs.items():
        if key != 'root':  # ルートは作成しない
            os.makedirs(dir_path, exist_ok=True)
            print(f"[OK] /: {dir_path}")


def get_race_ids_file_path(date_str: str, create_dir: bool = False) -> str:
    """
    ID

    Args:
        date_str:  (YYYYMMDD)
        create_dir: Trueの場合、ディレクトリを作成する（デフォルト: False）

    Returns:
        str: ID
    """
    dirs = get_base_directories()
    use_new_structure = os.environ.get('USE_NEW_DATA_STRUCTURE', 'false').lower() == 'true'

    if use_new_structure:
        # 新構造: races/YYYY/MM/DD/race_info.json
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        race_dir = os.path.join(dirs['race_ids'], year, month, day)
        if create_dir:
            os.makedirs(race_dir, exist_ok=True)
        return os.path.join(race_dir, "race_info.json")
    else:
        # 旧構造: race_ids/YYYYMMDD_info.json
        return os.path.join(dirs['race_ids'], f"{date_str}_info.json")


def get_json_file_path(data_type: str, identifier: str, actual_date: str = None, create_dir: bool = True) -> str:
    """
    JSON

    Args:
        data_type:  (seiseki, shutsuba, cyokyo, danwa, nittei)
        identifier:  (race_id)
        actual_date: 実際の開催日 (YYYYMMDD形式、省略時はidentifierから抽出)
        create_dir: Trueの場合、ディレクトリを作成する（デフォルト: True）

    Returns:
        str: JSON
    """
    dirs = get_base_directories()
    use_new_structure = os.environ.get('USE_NEW_DATA_STRUCTURE', 'false').lower() == 'true'
    filename = f"{data_type}_{identifier}.json"

    if use_new_structure:
        # 新構造: races/YYYY/MM/DD/temp/
        # actual_dateが指定されていればそれを使用、なければidentifierから抽出
        if actual_date and len(actual_date) == 8:
            date_str = actual_date
        elif len(identifier) >= 8:
            date_str = identifier[:8]
        else:
            # フォールバック: tempフォルダ直下
            return os.path.join(dirs['json_base'], filename)

        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        temp_dir = os.path.join(dirs['json_base'], year, month, day, "temp")
        if create_dir:
            os.makedirs(temp_dir, exist_ok=True)
        return os.path.join(temp_dir, filename)
    else:
        # 旧構造: temp/
        return os.path.join(dirs['json_base'], filename)


def create_authenticated_session() -> requests.Session:
    """
    CookieHTTP
    
    Returns:
        requests.Session: 
    """
    session = requests.Session()
    
    # 
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    })
    
    # Cookie
    cookies_data = Config.get_required_cookies()
    for cookie in cookies_data:
        if cookie['value']:  # 
            session.cookies.set(
                name=cookie['name'],
                value=cookie['value'],
                domain=cookie.get('domain', 'p.keibabook.co.jp'),
                path=cookie.get('path', '/')
            )
    
    return session


@dataclass
class BatchStats:
    """"""
    
    total_races: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    processed_races: List[str] = field(default_factory=list)
    failed_races: List[str] = field(default_factory=list)
    
    def start(self):
        """"""
        self.start_time = datetime.datetime.now()
    
    def finish(self):
        """"""
        self.end_time = datetime.datetime.now()
    
    def add_success(self, race_id: str):
        """"""
        self.success_count += 1
        self.processed_races.append(race_id)
    
    def add_error(self, race_id: str):
        """"""
        self.error_count += 1
        self.failed_races.append(race_id)
    
    def add_skip(self):
        """"""
        self.skipped_count += 1
    
    @property
    def success_rate(self) -> float:
        """"""
        if self.total_races == 0:
            return 0.0
        return (self.success_count / self.total_races) * 100
    
    @property
    def elapsed_time(self) -> Optional[datetime.timedelta]:
        """"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """"""
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
        """"""
        output_func = logger.info if logger else print
        
        output_func("=" * 50)
        output_func("[DATA] ")
        output_func("=" * 50)
        output_func(f"[UP] :")
        output_func(f"  - : {self.total_races}")
        output_func(f"  - : {self.success_count}")
        output_func(f"  - : {self.error_count}")
        output_func(f"  - : {self.skipped_count}")
        output_func(f"  - : {self.success_rate:.1f}%")
        
        if self.elapsed_time:
            output_func(f"  - : {self.elapsed_time}")
        
        if self.failed_races:
            output_func(f"[ERROR] :")
            for race_id in self.failed_races:
                output_func(f"  - {race_id}")
        
        output_func("=" * 50)


# 
VENUE_MAPPING = {
    "": "04",
    "": "06", 
    "": "01",
    "": "02",
    "": "03",
    "": "05",
    "": "07",
    "": "08",
}

# 
VENUE_CODE_TO_NAME = {v: k for k, v in VENUE_MAPPING.items()}

# 
DATA_TYPES = ["seiseki", "shutsuba", "cyokyo", "danwa"] 
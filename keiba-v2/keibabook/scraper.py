#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
keibabook.co.jp HTTPスクレイパー (v2)

v1の RequestsScraper + OptimizedDataFetcher を統合。
requests.Session + cookie認証でスクレイピング。

環境変数:
    KEIBABOOK_SESSION   keibabook_session cookie
    KEIBABOOK_TK        tk cookie
    KEIBABOOK_XSRF_TOKEN  XSRF-TOKEN cookie
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# URLs
BASE_URL = "https://p.keibabook.co.jp"
NITTEI_URL = f"{BASE_URL}/cyuou/nittei/"
SYUTUBA_URL = f"{BASE_URL}/cyuou/syutuba/"
CYOKYO_URL = f"{BASE_URL}/cyuou/cyokyo/0/0/"
DANWA_URL = f"{BASE_URL}/cyuou/danwa/0/"
SYOIN_URL = f"{BASE_URL}/cyuou/syoin/"
PADDOK_URL = f"{BASE_URL}/cyuou/paddok/"
SEISEKI_URL = f"{BASE_URL}/cyuou/seiseki/"
BABAKEIKOU_URL = f"{BASE_URL}/cyuou/babakeikou/"

# デフォルト設定
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = (5, 30)  # (接続, 読み取り)
DEFAULT_DELAY = 1.0


class KeibabookScraper:
    """keibabook.co.jp HTTPスクレイパー"""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        max_retries: int = 3,
        debug_html_dir: Optional[Path] = None,
    ):
        self.delay = delay
        self.max_retries = max_retries
        self.debug_html_dir = debug_html_dir

        # Session + retry
        self.session = requests.Session()
        retry = Retry(
            total=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=10,
            pool_maxsize=20,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Headers
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        # Cookies
        self._setup_cookies()

    def _setup_cookies(self) -> None:
        """環境変数からcookieを設定"""
        cookies = [
            ("keibabook_session", os.getenv("KEIBABOOK_SESSION", "")),
            ("tk", os.getenv("KEIBABOOK_TK", "")),
            ("XSRF-TOKEN", os.getenv("KEIBABOOK_XSRF_TOKEN", "")),
        ]
        loaded = 0
        for name, value in cookies:
            if value:
                self.session.cookies.set(
                    name=name,
                    value=value,
                    domain="p.keibabook.co.jp",
                    path="/",
                )
                loaded += 1
        if loaded == 0:
            logger.warning("keibabook cookieが未設定です。KEIBABOOK_SESSION等の環境変数を確認してください。")
        else:
            logger.info(f"keibabook cookie {loaded}個を設定")

    def scrape(self, url: str, timeout=DEFAULT_TIMEOUT) -> str:
        """URLからHTMLを取得

        Returns:
            HTML文字列

        Raises:
            requests.RequestException: HTTP/接続エラー
        """
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()

        # エンコーディング
        if response.encoding is None or response.encoding == "ISO-8859-1":
            response.encoding = "utf-8"

        html = response.text

        # 基本バリデーション
        if len(html) < 500:
            raise ValueError(f"レスポンスが短すぎます ({len(html)} chars): {url}")
        if "ログインが必要です" in html or "404 Not Found" in html:
            raise ValueError(f"アクセス拒否またはページ未発見: {url}")

        return html

    def _wait(self) -> None:
        """リクエスト間隔を待つ"""
        if self.delay > 0:
            time.sleep(self.delay)

    # === ページ別スクレイパー ===

    def scrape_nittei(self, date_str: str) -> str:
        """日程ページ取得。date_str: YYYYMMDD"""
        return self.scrape(f"{NITTEI_URL}{date_str}")

    def scrape_syutuba(self, race_id_12: str) -> str:
        """出馬表ページ取得"""
        html = self.scrape(f"{SYUTUBA_URL}{race_id_12}")
        self._wait()
        return html

    def scrape_cyokyo(self, race_id_12: str, save_debug: bool = True) -> str:
        """調教ページ取得。debug HTML保存オプション付き。"""
        html = self.scrape(f"{CYOKYO_URL}{race_id_12}")

        # debug HTML保存（cyokyo_enricher用）
        if save_debug and self.debug_html_dir:
            self._save_debug_html(html, race_id_12)

        self._wait()
        return html

    def scrape_danwa(self, race_id_12: str) -> str:
        """談話ページ取得"""
        html = self.scrape(f"{DANWA_URL}{race_id_12}")
        self._wait()
        return html

    def scrape_syoin(self, race_id_12: str) -> str:
        """前走インタビューページ取得"""
        html = self.scrape(f"{SYOIN_URL}{race_id_12}")
        self._wait()
        return html

    def scrape_paddok(self, race_id_12: str) -> str:
        """パドックページ取得"""
        html = self.scrape(f"{PADDOK_URL}{race_id_12}")
        self._wait()
        return html

    def scrape_seiseki(self, race_id_12: str) -> str:
        """成績ページ取得"""
        html = self.scrape(f"{SEISEKI_URL}{race_id_12}")
        self._wait()
        return html

    def scrape_babakeikou(self, date_str: str, place_code: str) -> str:
        """馬場傾向ページ取得。date_str: YYYYMMDD, place_code: 2桁"""
        html = self.scrape(f"{BABAKEIKOU_URL}{date_str}{place_code}")
        self._wait()
        return html

    def _save_debug_html(self, html: str, race_id_12: str) -> None:
        """調教HTMLをdebugディレクトリに保存"""
        if not self.debug_html_dir:
            return
        self.debug_html_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cyokyo_{race_id_12}_{ts}_requests.html"
        path = self.debug_html_dir / filename
        path.write_text(html, encoding="utf-8")
        logger.debug(f"debug HTML saved: {path}")

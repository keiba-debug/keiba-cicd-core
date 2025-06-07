"""
基本スクレイパークラス

全てのスクレイパーの基底クラスを定義します。
"""

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BaseScraper(ABC):
    """
    全てのスクレイパーの基底クラス
    
    共通的な処理と抽象メソッドを定義します。
    """
    
    def __init__(self, headless: bool = True, debug: bool = False):
        """
        初期化
        
        Args:
            headless: ヘッドレスモードの有効化
            debug: デバッグモードの有効化
        """
        self.headless = headless
        self.debug = debug
        self.driver: Optional[webdriver.Chrome] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def setup_driver(self) -> webdriver.Chrome:
        """
        Chromeドライバーをセットアップする
        
        Returns:
            webdriver.Chrome: セットアップされたドライバー
        """
        options = Options()
        
        if self.headless:
            options.add_argument("--headless")
        
        # 基本的なオプション
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # User-Agentの設定
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f"--user-agent={user_agent}")
        
        # その他のオプション
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=options)
        
        # WebDriverの検出を回避
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.logger.info("Chromeドライバーをセットアップしました")
        return self.driver
    
    def close_driver(self) -> None:
        """
        ドライバーを閉じる
        """
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logger.info("Chromeドライバーを閉じました")
    
    def set_cookies(self, cookies: List[Dict[str, str]]) -> None:
        """
        Cookieを設定する
        
        Args:
            cookies: 設定するCookieのリスト
        """
        if not self.driver:
            raise RuntimeError("ドライバーが初期化されていません")
        
        for cookie in cookies:
            self.driver.add_cookie(cookie)
        
        self.logger.info(f"{len(cookies)}個のCookieを設定しました")
    
    def wait_for_element(self, by: By, value: str, timeout: int = 10) -> bool:
        """
        要素の出現を待つ
        
        Args:
            by: 検索方法（By.ID, By.CLASS_NAME等）
            value: 検索値
            timeout: タイムアウト時間（秒）
            
        Returns:
            bool: 要素が見つかった場合True
        """
        if not self.driver:
            raise RuntimeError("ドライバーが初期化されていません")
        
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except Exception as e:
            self.logger.warning(f"要素の待機がタイムアウトしました: {by}='{value}', エラー: {e}")
            return False
    
    def safe_sleep(self, seconds: float) -> None:
        """
        安全な待機処理
        
        Args:
            seconds: 待機時間（秒）
        """
        self.logger.debug(f"{seconds}秒待機します")
        time.sleep(seconds)
    
    def save_html(self, html_content: str, file_path: str) -> None:
        """
        HTMLコンテンツをファイルに保存する
        
        Args:
            html_content: 保存するHTMLコンテンツ
            file_path: 保存先ファイルパス
        """
        try:
            # ディレクトリが存在しない場合は作成
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"HTMLファイルを保存しました: {file_path}")
            
        except Exception as e:
            self.logger.error(f"HTMLファイルの保存に失敗しました: {e}")
            raise
    
    def get_page_source(self) -> str:
        """
        現在のページのHTMLソースを取得する
        
        Returns:
            str: HTMLソース
            
        Raises:
            RuntimeError: ドライバーが初期化されていない場合
        """
        if not self.driver:
            raise RuntimeError("ドライバーが初期化されていません")
        
        return self.driver.page_source
    
    def navigate_to(self, url: str) -> None:
        """
        指定されたURLに移動する
        
        Args:
            url: 移動先のURL
            
        Raises:
            RuntimeError: ドライバーが初期化されていない場合
        """
        if not self.driver:
            raise RuntimeError("ドライバーが初期化されていません")
        
        self.driver.get(url)
        self.logger.info(f"URLに移動しました: {url}")
    
    def debug_log(self, message: str, data: any = None) -> None:
        """
        デバッグログを出力する
        
        Args:
            message: ログメッセージ
            data: 追加のデータ（オプション）
        """
        if self.debug:
            if data is not None:
                self.logger.debug(f"{message}: {data}")
            else:
                self.logger.debug(message)
    
    @abstractmethod
    def scrape(self, url: str, **kwargs) -> str:
        """
        指定されたURLからデータをスクレイピングする
        
        Args:
            url: スクレイピング対象のURL
            **kwargs: 追加のパラメータ
            
        Returns:
            str: 取得されたHTMLコンテンツ
            
        Raises:
            NotImplementedError: サブクラスで実装されていない場合
        """
        raise NotImplementedError("サブクラスでscrapeメソッドを実装してください")
    
    @abstractmethod
    def get_required_cookies(self) -> List[Dict[str, str]]:
        """
        必要なCookieを取得する
        
        Returns:
            List[Dict[str, str]]: 必要なCookieのリスト
            
        Raises:
            NotImplementedError: サブクラスで実装されていない場合
        """
        raise NotImplementedError("サブクラスでget_required_cookiesメソッドを実装してください")
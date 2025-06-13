"""
競馬ブックスクレイパー

競馬ブックのデータを取得するスクレイパーです。
"""

import time
from typing import Dict, List

from selenium.webdriver.common.by import By

from scrapers.base_scraper import BaseScraper
from utils.config import Config


class KeibabookScraper(BaseScraper):
    """
    競馬ブック専用のスクレイパー
    
    競馬ブックのWebサイトから以下のデータを取得します：
    - 成績ページ
    - 出馬表ページ
    - その他の競馬関連データ
    """
    
    def __init__(self, headless: bool = True, debug: bool = False):
        """
        初期化
        
        Args:
            headless: ヘッドレスモードの有効化
            debug: デバッグモードの有効化
        """
        super().__init__(headless, debug)
        self.base_url = Config.KEIBABOOK_BASE_URL
    
    def scrape(self, url: str, **kwargs) -> str:
        """
        指定されたURLからデータをスクレイピングする
        
        Args:
            url: スクレイピング対象のURL
            **kwargs: 追加のパラメータ
                - save_html_path: HTMLを保存するパス（オプション）
                - wait_time: 待機時間（オプション）
                
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        save_html_path = kwargs.get('save_html_path')
        wait_time = kwargs.get('wait_time', Config.DEFAULT_SLEEP_TIME)
        
        try:
            # ドライバーをセットアップ
            self.setup_driver()
            
            # まず競馬ブックのトップページに移動
            self.logger.info("競馬ブックのトップページに移動します")
            self.navigate_to(self.base_url)
            self.safe_sleep(1)
            
            # 必要なCookieを設定
            self.logger.info("Cookieを設定します")
            cookies = self.get_required_cookies()
            self.set_cookies(cookies)
            
            # 目的のページに移動
            self.logger.info(f"目的のページに移動します: {url}")
            self.navigate_to(url)
            
            # ページの読み込みを待機
            self.safe_sleep(wait_time)
            
            # 特定の要素が読み込まれるまで待機
            self._wait_for_page_load()
            
            # HTMLソースを取得
            html_content = self.get_page_source()
            
            # HTMLを保存（オプション）
            if save_html_path:
                self.save_html(html_content, save_html_path)
            
            self.logger.info("スクレイピングが完了しました")
            return html_content
            
        except Exception as e:
            self.logger.error(f"スクレイピング中にエラーが発生しました: {e}")
            raise
        finally:
            self.close_driver()
    

    
    def get_nittei_page(self, date_str: str, save_html_path: str = None) -> str:
        """
        レース日程ページをスクレイピングする
        
        Args:
            date_str: 日付文字列 (YYYYMMDD)
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        url = f"{Config.KEIBABOOK_NITTEI_URL}{date_str}"
        
        if save_html_path is None:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            save_html_path = Config.get_debug_dir() / f"nittei_{date_str}_{timestamp}.html"
        
        return self.scrape(url, save_html_path=save_html_path, wait_time=3)
    
    def get_seiseki_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        成績ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        url = f"{Config.KEIBABOOK_SEISEKI_URL}{race_id}"
        
        if save_html_path is None:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            save_html_path = Config.get_debug_dir() / f"seiseki_{race_id}_{timestamp}.html"
        
        return self.scrape(url, save_html_path=save_html_path, wait_time=3)
    
    def get_shutsuba_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        出馬表ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        url = f"{Config.KEIBABOOK_SHUTSUBA_URL}{race_id}"
        
        if save_html_path is None:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            save_html_path = Config.get_debug_dir() / f"shutsuba_{race_id}_{timestamp}.html"
        
        return self.scrape(url, save_html_path=save_html_path, wait_time=3)
    
    def get_cyokyo_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        調教ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        url = f"{Config.KEIBABOOK_CYOKYO_URL}{race_id}"
        
        if save_html_path is None:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            save_html_path = Config.get_debug_dir() / f"cyokyo_{race_id}_{timestamp}.html"
        
        return self.scrape(url, save_html_path=save_html_path, wait_time=3)
    
    def get_danwa_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        厩舎の話ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        url = f"{Config.KEIBABOOK_DANWA_URL}{race_id}"
        
        if save_html_path is None:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            save_html_path = Config.get_debug_dir() / f"danwa_{race_id}_{timestamp}.html"
        
        return self.scrape(url, save_html_path=save_html_path, wait_time=3)
    
    def get_required_cookies(self) -> List[Dict[str, str]]:
        """
        必要なCookieを取得する
        
        Returns:
            List[Dict[str, str]]: 必要なCookieのリスト
        """
        return Config.get_required_cookies()
    
    def _wait_for_page_load(self) -> None:
        """
        ページの読み込み完了を待機する
        """
        # 成績テーブルまたは出馬表テーブルが読み込まれるまで待機
        table_found = (
            self.wait_for_element(By.CLASS_NAME, "raceTable", timeout=5) or
            self.wait_for_element(By.CLASS_NAME, "shutsubaTable", timeout=5) or
            self.wait_for_element(By.TAG_NAME, "table", timeout=5)
        )
        
        if table_found:
            self.debug_log("テーブルの読み込みを確認しました")
        else:
            self.logger.warning("テーブルの読み込みを確認できませんでした")
        
        # bameiboxクラスの要素の読み込みを待機
        bameibox_found = self.wait_for_element(By.CLASS_NAME, "bameibox", timeout=3)
        if bameibox_found:
            self.debug_log("bameiboxの読み込みを確認しました")
        
        # 追加の待機時間
        self.safe_sleep(1)
    
    def validate_page_content(self, html_content: str) -> bool:
        """
        取得したページの内容を検証する
        
        Args:
            html_content: 検証対象のHTMLコンテンツ
            
        Returns:
            bool: 内容が有効な場合True
        """
        # 基本的なHTMLタグの存在確認
        if not html_content or len(html_content) < 1000:
            self.logger.error("HTMLコンテンツが短すぎます")
            return False
        
        # エラーページの検出
        error_indicators = [
            "404 Not Found",
            "Error",
            "エラーが発生しました",
            "ページが見つかりません"
        ]
        
        for indicator in error_indicators:
            if indicator in html_content:
                self.logger.error(f"エラーページを検出しました: {indicator}")
                return False
        
        # 競馬ブック特有のコンテンツの確認
        required_content = [
            "keibabook",
            "競馬ブック"
        ]
        
        content_found = any(content in html_content for content in required_content)
        if not content_found:
            self.logger.warning("競馬ブック特有のコンテンツが見つかりません")
        
        return True
"""
Requests ベーススクレイパー

ChromeDriverを使わずにrequestsライブラリでデータを取得するスクレイパーです。
"""

import time
import requests
from typing import Dict, List, Optional
from pathlib import Path

from ..utils.config import Config
from ..utils.logger import setup_logger


class RequestsScraper:
    """
    requests ベースの軽量スクレイパー
    
    ChromeDriverを使わずにHTTPリクエストでデータを取得します。
    高速でリソース使用量が少ないのが特徴です。
    """
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモードの有効化
        """
        self.debug = debug
        self.logger = setup_logger(__name__)
        self.session = requests.Session()
        self.base_url = Config.KEIBABOOK_BASE_URL
        
        # デフォルトヘッダーを設定
        self.session.headers.update({
            'User-Agent': Config.DEFAULT_USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Cookieを設定
        self._setup_cookies()
    
    def _setup_cookies(self) -> None:
        """
        必要なCookieをセッションに設定する
        """
        try:
            cookies_data = Config.get_required_cookies()
            for cookie in cookies_data:
                self.session.cookies.set(
                    name=cookie['name'],
                    value=cookie['value'],
                    domain=cookie.get('domain', 'p.keibabook.co.jp'),
                    path=cookie.get('path', '/')
                )
            self.logger.info(f"Cookieを設定しました: {len(cookies_data)}個")
        except Exception as e:
            self.logger.warning(f"Cookie設定中にエラーが発生しました: {e}")
    
    def scrape(self, url: str, **kwargs) -> str:
        """
        指定されたURLからデータをスクレイピングする
        
        Args:
            url: スクレイピング対象のURL
            **kwargs: 追加のパラメータ
                - save_html_path: HTMLを保存するパス（オプション）
                - timeout: タイムアウト時間（オプション）
                
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        save_html_path = kwargs.get('save_html_path')
        timeout = kwargs.get('timeout', Config.DEFAULT_TIMEOUT)
        
        try:
            self.logger.info(f"データを取得します: {url}")
            
            # HTTPリクエストを送信
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            # エンコーディングを設定
            if response.encoding is None or response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'
            
            html_content = response.text
            
            # HTMLを保存（オプション）
            if save_html_path:
                self.save_html(html_content, save_html_path)
            
            self.logger.info(f"データ取得完了: {len(html_content)}文字")
            return html_content
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTPリクエスト中にエラーが発生しました: {e}")
            raise
        except Exception as e:
            self.logger.error(f"スクレイピング中にエラーが発生しました: {e}")
            raise
    
    def scrape_page(self, page_type: str, race_id: str, save_html_path: str = None) -> str:
        """
        指定されたページタイプのデータを取得
        
        Args:
            page_type: ページタイプ ('seiseki', 'syutuba', 'cyokyo', 'danwa')
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        # URLを構築
        if page_type == 'seiseki':
            url = f"{Config.KEIBABOOK_SEISEKI_URL}{race_id}"
        elif page_type == 'syutuba':
            url = f"https://p.keibabook.co.jp/cyuou/syutuba/{race_id}"
        elif page_type == 'cyokyo':
            url = f"https://p.keibabook.co.jp/cyuou/cyokyo/0/0/{race_id}"
        elif page_type == 'danwa':
            url = f"https://p.keibabook.co.jp/cyuou/danwa/0/{race_id}"
        else:
            raise ValueError(f"未対応のページタイプ: {page_type}")
        
        if save_html_path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_html_path = Config.get_debug_dir() / f"{page_type}_{race_id}_{timestamp}_requests.html"
        
        return self.scrape(url, save_html_path=save_html_path)

    def scrape_seiseki_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        成績ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        return self.scrape_page('seiseki', race_id, save_html_path)
    
    def scrape_syutuba_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        出馬表ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        return self.scrape_page('syutuba', race_id, save_html_path)
    
    def scrape_cyokyo_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        調教ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        return self.scrape_page('cyokyo', race_id, save_html_path)
    
    def scrape_danwa_page(self, race_id: str, save_html_path: str = None) -> str:
        """
        厩舎の話ページをスクレイピングする
        
        Args:
            race_id: レースID
            save_html_path: HTMLを保存するパス（オプション）
            
        Returns:
            str: 取得されたHTMLコンテンツ
        """
        return self.scrape_page('danwa', race_id, save_html_path)
    
    def scrape_syoin_page(self, race_id: str) -> str:
        """
        前走インタビューページを取得する
        
        Args:
            race_id: レースID
            
        Returns:
            str: HTMLコンテンツ
        """
        url = f'https://p.keibabook.co.jp/cyuou/syoin/{race_id}'
        html = self.scrape(url)
        
        if self.validate_page_content(html):
            self.logger.info(f"前走インタビューページを取得しました: {race_id}")
            return html
        else:
            self.logger.error(f"前走インタビューページの内容が無効です: {race_id}")
            return ""
    
    def scrape_paddok_page(self, race_id: str) -> str:
        """
        パドック情報ページを取得する
        
        Args:
            race_id: レースID
            
        Returns:
            str: HTMLコンテンツ
        """
        url = f'https://p.keibabook.co.jp/cyuou/paddok/{race_id}'
        html = self.scrape(url)
        
        if self.validate_page_content(html):
            self.logger.info(f"パドック情報ページを取得しました: {race_id}")
            return html
        else:
            self.logger.error(f"パドック情報ページの内容が無効です: {race_id}")
            return ""
    
    def save_html(self, html_content: str, file_path: str) -> None:
        """
        HTMLコンテンツをファイルに保存する
        
        Args:
            html_content: 保存するHTMLコンテンツ
            file_path: 保存先のファイルパス
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"HTMLを保存しました: {path}")
        except Exception as e:
            self.logger.error(f"HTML保存中にエラーが発生しました: {e}")
    
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
            "ページが見つかりません",
            "アクセスが拒否されました",
            "ログインが必要です"
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
    
    def close(self) -> None:
        """
        セッションを閉じる
        """
        self.session.close()
        self.logger.info("セッションを終了しました")
    
    def __enter__(self):
        """コンテキストマネージャのエントリ"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャの終了"""
        self.close() 
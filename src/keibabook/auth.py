import os
from typing import Optional
import requests
from bs4 import BeautifulSoup
from loguru import logger
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

class KeibaBookAuth:
    def __init__(self):
        load_dotenv()
        self.session = requests.Session()
        self.base_url = "https://p.keibabook.co.jp"
        self.login_url = f"{self.base_url}/login/login"
        self.username = os.getenv("KEIBABOOK_USERNAME")
        self.password = os.getenv("KEIBABOOK_PASSWORD")
        # Cookie認証用
        self.cookie_keibabook_session = os.getenv("KEIBABOOK_SESSION")
        self.cookie_tk = os.getenv("KEIBABOOK_TK")
        self.cookie_xsrf_token = os.getenv("KEIBABOOK_XSRF_TOKEN")
        
        # セッションのデフォルトヘッダーを設定
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        
        logger.debug(f"ログインURL: {self.login_url}")
        logger.debug(f"ユーザー名: {self.username}")

    def _set_cookies_from_env(self):
        """環境変数からCookieをセット"""
        if self.cookie_keibabook_session:
            self.session.cookies.set('keibabook_session', self.cookie_keibabook_session, domain='p.keibabook.co.jp')
        if self.cookie_tk:
            self.session.cookies.set('tk', self.cookie_tk, domain='p.keibabook.co.jp')
        if self.cookie_xsrf_token:
            self.session.cookies.set('XSRF-TOKEN', self.cookie_xsrf_token, domain='p.keibabook.co.jp')

    def _get_csrf_token(self, response_text: str) -> str:
        """HTMLからCSRFトークンを取得"""
        soup = BeautifulSoup(response_text, 'html.parser')
        token_input = soup.find('input', {'name': '_token'})
        if token_input:
            return token_input.get('value', '')
        return ''

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def login(self) -> bool:
        """ログインを実行し、成功したかどうかを返す。Cookie認証が優先される。"""
        # まずCookie認証を試みる
        if self.cookie_keibabook_session and self.cookie_tk and self.cookie_xsrf_token:
            logger.info("Cookie認証モードでログインを試みます")
            self._set_cookies_from_env()
            if self.is_logged_in():
                logger.info("Cookie認証でログイン済みと判定")
                return True
            else:
                logger.warning("Cookie認証でログイン判定できませんでした。フォーム認証にフォールバックします。")
        # フォーム認証
        if not self.username or not self.password:
            logger.error("ユーザー名・パスワードまたはCookie情報がありません")
            return False
        try:
            logger.debug("ログインページにアクセス中...")
            response = self.session.get(self.login_url)
            response.raise_for_status()
            csrf_token = self._get_csrf_token(response.text)
            logger.debug(f"CSRFトークン: {csrf_token}")
            login_data = {
                "_token": csrf_token,
                "referer": "",
                "service": "keibabook",
                "login_id": self.username,
                "pswd": self.password,
                "autologin": "1"
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self.login_url,
                "Origin": self.base_url
            }
            logger.debug(f"ログインデータ: {login_data}")
            logger.debug(f"リクエストヘッダー: {headers}")
            response = self.session.post(
                self.login_url,
                data=login_data,
                headers=headers,
                allow_redirects=True
            )
            response.raise_for_status()
            logger.debug(f"ログイン後ステータスコード: {response.status_code}")
            logger.debug(f"ログイン後ヘッダー: {dict(response.headers)}")
            logger.debug(f"リダイレクト履歴: {[r.url for r in response.history]}")
            logger.debug(f"最終URL: {response.url}")
            logger.debug(f"セッションクッキー: {dict(self.session.cookies)}")
            if "ログアウト" in response.text:
                logger.info("フォーム認証でログインに成功しました")
                return True
            else:
                logger.error("フォーム認証でログインに失敗しました")
                logger.debug(f"レスポンス本文: {response.text[:500]}...")
                return False
        except requests.RequestException as e:
            logger.error(f"ログイン中にエラーが発生しました: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.debug(f"エラーレスポンス本文: {e.response.text[:500]}...")
            raise

    def is_logged_in(self) -> bool:
        """現在のセッションがログイン状態かどうかを確認"""
        try:
            response = self.session.get(f"{self.base_url}/mypage/top")
            # マイページにアクセスできて"ログアウト"があればログイン状態
            return "ログアウト" in response.text
        except requests.RequestException:
            return False

    def get_session(self) -> requests.Session:
        """現在のセッションを取得"""
        return self.session 
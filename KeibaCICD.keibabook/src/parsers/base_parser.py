"""
基本パーサークラス

全てのパーサーの基底クラスを定義します。
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup


class BaseParser(ABC):
    """
    全てのパーサーの基底クラス
    
    共通的な処理と抽象メソッドを定義します。
    """
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモードの有効化
        """
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    def load_html(self, file_path: str) -> BeautifulSoup:
        """
        HTMLファイルを読み込んでBeautifulSoupオブジェクトを返す
        
        Args:
            file_path: HTMLファイルのパス
            
        Returns:
            BeautifulSoup: パースされたHTMLオブジェクト
            
        Raises:
            FileNotFoundError: ファイルが見つからない場合
            Exception: HTMLの読み込みに失敗した場合
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            self.logger.info(f"HTMLファイルを正常に読み込みました: {file_path}")
            return soup
            
        except FileNotFoundError:
            self.logger.error(f"HTMLファイルが見つかりません: {file_path}")
            raise
        except Exception as e:
            self.logger.error(f"HTMLファイルの読み込みに失敗しました: {e}")
            raise
    
    def save_json(self, data: Dict[str, Any], file_path: str) -> None:
        """
        データをJSONファイルとして保存する
        
        Args:
            data: 保存するデータ
            file_path: 保存先ファイルパス
            
        Raises:
            Exception: ファイルの保存に失敗した場合
        """
        try:
            # ディレクトリが存在しない場合は作成
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"JSONファイルを正常に保存しました: {file_path}")
            
        except Exception as e:
            self.logger.error(f"JSONファイルの保存に失敗しました: {e}")
            raise
    
    def clean_text(self, text: str) -> str:
        """
        テキストをクリーニングする
        
        Args:
            text: クリーニング対象のテキスト
            
        Returns:
            str: クリーニング後のテキスト
        """
        if not text:
            return ""
        
        # 前後の空白を削除
        text = text.strip()
        
        # 連続する空白を単一の空白に変換
        import re
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def extract_text_safely(self, element: Optional[Any], default: str = "") -> str:
        """
        要素からテキストを安全に抽出する
        
        Args:
            element: BeautifulSoupの要素
            default: 要素がNoneの場合のデフォルト値
            
        Returns:
            str: 抽出されたテキスト
        """
        if element is None:
            return default
        
        text = element.get_text() if hasattr(element, 'get_text') else str(element)
        return self.clean_text(text)
    
    def debug_log(self, message: str, data: Any = None) -> None:
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
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルをパースしてデータを抽出する
        
        Args:
            html_file_path: HTMLファイルのパス
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
            
        Raises:
            NotImplementedError: サブクラスで実装されていない場合
        """
        raise NotImplementedError("サブクラスでparseメソッドを実装してください")
    
    @abstractmethod
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        抽出されたデータを検証する
        
        Args:
            data: 検証対象のデータ
            
        Returns:
            bool: データが有効な場合True
            
        Raises:
            NotImplementedError: サブクラスで実装されていない場合
        """
        raise NotImplementedError("サブクラスでvalidate_dataメソッドを実装してください")
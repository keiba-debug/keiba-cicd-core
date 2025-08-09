"""
パーサーモジュール

競馬ブックの各種ページから情報を抽出するパーサークラスを提供します。
"""

from .base_parser import BaseParser
from .seiseki_parser import SeisekiParser

__all__ = ["BaseParser", "SeisekiParser"]
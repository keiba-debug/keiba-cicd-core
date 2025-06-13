"""
パーサーモジュール

競馬ブックの各種ページから情報を抽出するパーサークラスを提供します。
"""

from parsers.base_parser import BaseParser
from parsers.seiseki_parser import SeisekiParser

__all__ = ["BaseParser", "SeisekiParser"]
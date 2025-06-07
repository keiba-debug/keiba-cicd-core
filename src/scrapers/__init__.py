"""
スクレイパーモジュール

競馬ブックのデータを取得するスクレイパークラスを提供します。
"""

from .base_scraper import BaseScraper
from .keibabook_scraper import KeibabookScraper

__all__ = ["BaseScraper", "KeibabookScraper"]
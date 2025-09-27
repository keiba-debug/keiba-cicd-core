"""
騎手情報取得テストスクリプト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scrapers.jockey_scraper import JockeyScraper

def main():
    print("騎手情報取得テスト開始")

    scraper = JockeyScraper()

    # リーディング情報取得
    print("リーディング情報取得中...")
    result = scraper.scrape_leading_jockeys(2025, 9)

    if result:
        print(f"取得成功: {len(result.get('rankings', []))}名のランキング")
        for ranking in result.get('rankings', [])[:5]:
            print(f"  {ranking}")
    else:
        print("取得失敗")

if __name__ == "__main__":
    main()
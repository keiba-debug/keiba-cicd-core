#!/usr/bin/env python3
"""
馬場情報スクレイピングテストスクリプト

使用方法:
    python test_babakeikou.py <日付YYYYMMDD> <場コード>
    
例:
    python test_babakeikou.py 20250927 01  # 2025/09/27 阪神
    python test_babakeikou.py 20260118 05  # 2026/01/18 中山
"""

import sys
import json
from pathlib import Path

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.scrapers.requests_scraper import RequestsScraper
from src.parsers.babakeikou_parser import BabaKeikouParser


def test_babakeikou(date: str, place_code: str):
    """馬場情報の取得とパースをテスト"""
    
    print(f"=" * 60)
    print(f"馬場情報テスト: 日付={date}, 場コード={place_code}")
    print(f"=" * 60)
    
    # スクレイパーで取得
    scraper = RequestsScraper(debug=True)
    
    try:
        html_content = scraper.scrape_babakeikou_page(date, place_code)
        
        if not html_content:
            print("[ERROR] Failed to retrieve HTML content")
            return
        
        print(f"[OK] HTML contents retrieved: {len(html_content)} chars")
        
        # パーサーでパース
        parser = BabaKeikouParser(debug=True)
        result = parser.parse_html_content(html_content)
        
        print(f"\n[RESULT] Parse Result:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 検証
        if parser.validate_data(result):
            print("\n[OK] Data Validation Passed")
        else:
            print("\n[WARN] Data Validation Failed (Required data may be missing)")
        
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\n場コード一覧:")
        print("  01: 阪神")
        print("  02: 函館")
        print("  03: 福島")
        print("  04: 新潟")
        print("  05: 中山")
        print("  06: 中京")
        print("  07: 小倉")
        print("  08: 京都")
        print("  09: 東京")
        print("  10: 札幌")
        sys.exit(1)
    
    date = sys.argv[1]
    place_code = sys.argv[2]
    
    test_babakeikou(date, place_code)


if __name__ == "__main__":
    main()

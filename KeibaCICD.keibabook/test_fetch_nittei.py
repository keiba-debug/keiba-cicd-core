#!/usr/bin/env python3
"""
日程ページのHTMLを取得してテスト
"""

from src.scrapers.requests_scraper import RequestsScraper
from src.parsers.nittei_parser import NitteiParser

# HTML取得
scraper = RequestsScraper()
html = scraper.scrape('https://p.keibabook.co.jp/cyuou/nittei/20250824')
success = html is not None and len(html) > 0

if success:
    print("HTML取得成功")
    with open('test_nittei.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    # パース
    parser = NitteiParser()
    result = parser.parse_with_date(html, '20250824')
    if result:
        import json
        print("パース成功")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("パース失敗")
else:
    print("HTML取得失敗")
#!/usr/bin/env python3
"""
日程ページのHTMLを取得して分析するデバッグスクリプト
"""

from ..scrapers.requests_scraper import RequestsScraper
from ..parsers.nittei_parser import NitteiParser
from bs4 import BeautifulSoup
import os

def main():
    # RequestsScraperでHTMLを取得
    scraper = RequestsScraper()
    url = 'https://p.keibabook.co.jp/cyuou/nittei/20250607'
    
    print(f"🔍 日程ページを取得中: {url}")
    html_content = scraper.scrape(url)
    
    # HTMLファイルを保存
    os.makedirs('debug_html', exist_ok=True)
    html_file = 'debug_html/nittei_20250607.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTMLファイルを保存: {html_file}")
    print(f"📊 ファイルサイズ: {len(html_content):,}文字")
    
    # BeautifulSoupで解析
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 開催場所を探す
    print("\n🔍 HTML構造を分析中...")
    
    # 様々なパターンで開催場所を探す
    patterns = [
        ('div.kaisai', 'div class="kaisai"'),
        ('table.kaisai', 'table class="kaisai"'),
        ('div[class*="kaisai"]', 'div with kaisai in class'),
        ('table[class*="kaisai"]', 'table with kaisai in class'),
        ('th.midasi', 'th class="midasi"'),
        ('th[class*="midasi"]', 'th with midasi in class'),
    ]
    
    for selector, description in patterns:
        elements = soup.select(selector)
        print(f"📋 {description}: {len(elements)}個")
        if elements:
            for i, elem in enumerate(elements[:3]):  # 最初の3個だけ表示
                text = elem.get_text(strip=True)[:100]  # 最初の100文字
                print(f"   [{i+1}] {text}")
    
    # 全てのテーブルを確認
    tables = soup.find_all('table')
    print(f"\n📊 全テーブル数: {len(tables)}")
    
    for i, table in enumerate(tables[:5]):  # 最初の5個のテーブル
        print(f"\n🏁 テーブル {i+1}:")
        rows = table.find_all('tr')
        print(f"   行数: {len(rows)}")
        
        # 最初の数行を表示
        for j, row in enumerate(rows[:3]):
            cells = row.find_all(['th', 'td'])
            cell_texts = [cell.get_text(strip=True)[:50] for cell in cells]
            print(f"   行{j+1}: {cell_texts}")
    
    # NitteiParserでパース
    print("\n🔧 NitteiParserでパース中...")
    parser = NitteiParser()
    result = parser.parse_with_date(html_content, '20250607')
    
    if result:
        print(f"✅ パース成功:")
        print(f"   開催数: {result.get('kaisai_count', 0)}")
        print(f"   総レース数: {result.get('total_races', 0)}")
        
        kaisai_data = result.get('kaisai_data', {})
        for venue, races in kaisai_data.items():
            print(f"   📍 {venue}: {len(races)}レース")
            for race in races[:3]:  # 最初の3レースを表示
                print(f"      - {race.get('race_no')}R: {race.get('race_name')} (ID: {race.get('race_id')})")
    else:
        print("❌ パース失敗")
    
    scraper.close()

if __name__ == '__main__':
    main() 
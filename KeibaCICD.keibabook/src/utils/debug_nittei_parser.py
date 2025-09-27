#!/usr/bin/env python3
"""
NitteiParserのデバッグ - 発走時刻が取得されない問題の調査
"""

from src.scrapers.requests_scraper import RequestsScraper
from src.parsers.nittei_parser import NitteiParser
import json

# HTML取得
scraper = RequestsScraper()
html = scraper.scrape('https://p.keibabook.co.jp/cyuou/nittei/20250824')

if html:
    print("HTML取得成功")
    
    # パーサのデバッグ
    parser = NitteiParser()
    
    # _extract_kaisai_dataを直接呼び出して調査
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    # kaisaiテーブル内のtrを詳しく調査
    kaisai_div = soup.find('div', class_='kaisai')
    if kaisai_div:
        tables = kaisai_div.find_all('table', class_='kaisai')
        print(f"テーブル数: {len(tables)}")
        
        # 最初のテーブルの最初のレース（1R）のみ詳細に調査
        if tables:
            table = tables[0]
            rows = table.find_all('tr')
            
            # レース情報が入っている行を探す
            for i, row in enumerate(rows):
                tds = row.find_all('td')
                if len(tds) >= 2:
                    race_no = tds[0].get_text(strip=True)
                    if race_no == '1R':
                        print(f"\n=== 1Rの行を発見（行番号: {i}） ===")
                        print(f"td数: {len(tds)}")
                        
                        for j, td in enumerate(tds):
                            text = td.get_text(strip=True)
                            print(f"td[{j}]: {text}")
                            
                            # HTMLも確認
                            if j == 2:  # 3番目のtd
                                print(f"  HTML: {td}")
                        
                        # 時刻抽出テスト
                        if len(tds) >= 3:
                            time_text = tds[2].get_text(strip=True)
                            print(f"\n時刻抽出対象テキスト: '{time_text}'")
                            
                            import re
                            time_pattern = r'\b([01]?\d|2[0-3]):([0-5]\d)\b'
                            match = re.search(time_pattern, time_text)
                            if match:
                                print(f"正規表現マッチ成功: {match.group(0)}")
                            else:
                                print("正規表現マッチ失敗")
                        break
    
    # 実際のパース結果も確認
    print("\n=== NitteiParserの実行結果 ===")
    result = parser.parse_with_date(html, '20250824')
    if result:
        # 最初のレースだけ表示
        for venue, races in result.get('kaisai_data', {}).items():
            if races and len(races) > 0:
                print(f"\n{venue}の最初のレース:")
                print(json.dumps(races[0], ensure_ascii=False, indent=2))
                break
else:
    print("HTML取得失敗")
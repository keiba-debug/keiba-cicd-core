#!/usr/bin/env python3
"""
HTMLから発走時刻を抽出するテスト
"""

from bs4 import BeautifulSoup

# HTMLファイルを読み込み
with open('test_nittei.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# kaisaiテーブルを探す
kaisai_div = soup.find('div', class_='kaisai')
if kaisai_div:
    tables = kaisai_div.find_all('table', class_='kaisai')
    print(f"kaisaiテーブル数: {len(tables)}")
    
    for table_idx, table in enumerate(tables):
        print(f"\nテーブル {table_idx + 1}:")
        rows = table.find_all('tr')
        
        for row_idx, row in enumerate(rows[:10]):  # 最初の10行
            print(f"  行 {row_idx + 1}:")
            
            # th要素
            th = row.find('th')
            if th:
                print(f"    th: {th.get_text(strip=True)}")
            
            # td要素
            tds = row.find_all('td')
            for td_idx, td in enumerate(tds):
                text = td.get_text(strip=True)
                print(f"    td[{td_idx}]: {text[:50]}...")  # 最初の50文字
                
                # 時刻パターンを探す
                import re
                time_match = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', text)
                if time_match:
                    print(f"      → 時刻発見: {time_match.group(0)}")
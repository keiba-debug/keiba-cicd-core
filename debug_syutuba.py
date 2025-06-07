#!/usr/bin/env python3
"""
出馬表ページのHTMLを取得してumacdの構造を分析するデバッグスクリプト
"""

from src.keibabook.scrapers.requests_scraper import RequestsScraper
from bs4 import BeautifulSoup
import os
import re

def main():
    # RequestsScraperでHTMLを取得
    scraper = RequestsScraper()
    
    # 先ほど取得したレースIDを使用（東京1R）
    race_id = '202503040101'
    url = f'https://p.keibabook.co.jp/cyuou/syutuba/{race_id}'
    
    print(f"🔍 出馬表ページを取得中: {url}")
    html_content = scraper.scrape(url)
    
    # HTMLファイルを保存
    os.makedirs('debug_html', exist_ok=True)
    html_file = f'debug_html/syutuba_{race_id}.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTMLファイルを保存: {html_file}")
    print(f"📊 ファイルサイズ: {len(html_content):,}文字")
    
    # BeautifulSoupで解析
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # umacdを含むリンクを探す
    print("\n🔍 umacd属性を持つ要素を分析中...")
    
    umacd_links = soup.find_all('a', attrs={'umacd': True})
    print(f"📋 umacd属性を持つリンク数: {len(umacd_links)}")
    
    for i, link in enumerate(umacd_links[:10]):  # 最初の10個を表示
        umacd = link.get('umacd')
        href = link.get('href', '')
        text = link.get_text(strip=True)
        class_attr = link.get('class', [])
        
        print(f"   [{i+1}] umacd='{umacd}' | text='{text}' | href='{href}' | class={class_attr}")
    
    # 馬名を含むリンクを探す
    print("\n🐎 馬名リンクの構造を分析中...")
    
    # 馬名らしいリンクを探す（umalinkクラスやdb/umaを含むhref）
    horse_links = soup.find_all('a', href=re.compile(r'/db/uma/'))
    print(f"📋 /db/uma/を含むリンク数: {len(horse_links)}")
    
    for i, link in enumerate(horse_links[:5]):  # 最初の5個を表示
        umacd = link.get('umacd')
        href = link.get('href', '')
        text = link.get_text(strip=True)
        class_attr = link.get('class', [])
        
        print(f"   [{i+1}] umacd='{umacd}' | text='{text}' | href='{href}' | class={class_attr}")
    
    # 出馬表テーブルを探す
    print("\n📊 出馬表テーブルの構造を分析中...")
    
    tables = soup.find_all('table')
    print(f"📋 全テーブル数: {len(tables)}")
    
    for i, table in enumerate(tables):
        # テーブル内のumacdリンクを確認
        table_umacd_links = table.find_all('a', attrs={'umacd': True})
        if table_umacd_links:
            print(f"\n🏁 テーブル {i+1} (umacdリンク: {len(table_umacd_links)}個):")
            
            # テーブルの最初の数行を表示
            rows = table.find_all('tr')[:5]
            for j, row in enumerate(rows):
                cells = row.find_all(['th', 'td'])
                cell_info = []
                
                for cell in cells:
                    cell_text = cell.get_text(strip=True)[:30]  # 最初の30文字
                    umacd_link = cell.find('a', attrs={'umacd': True})
                    if umacd_link:
                        umacd = umacd_link.get('umacd')
                        cell_info.append(f"{cell_text} [umacd:{umacd}]")
                    else:
                        cell_info.append(cell_text)
                
                print(f"   行{j+1}: {cell_info}")
    
    scraper.close()

if __name__ == '__main__':
    main() 
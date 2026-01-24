#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
寸評取得テストスクリプト
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.scrapers.requests_scraper import RequestsScraper
from src.parsers.seiseki_parser import SeisekiParser
from bs4 import BeautifulSoup


def test_sunpyo(race_id: str):
    """寸評が取得できるかテスト"""
    
    print("=" * 60)
    print(f"Sunpyo Test: race_id={race_id}")
    print("=" * 60)
    
    scraper = RequestsScraper()
    
    try:
        html = scraper.scrape_seiseki_page(race_id)
        print(f"[OK] HTML retrieved: {len(html)} chars")
        
        # 寸評がHTMLに含まれているか確認
        if "\u5bf8\u8a55" in html:  # 寸評
            print("[OK] 'sunpyo' column FOUND in HTML!")
        else:
            print("[WARN] 'sunpyo' column NOT found in HTML")
        
        # テーブルヘッダーを確認
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', class_='seiseki')
        
        if table:
            headers = []
            for th in table.find('tr').find_all('th'):
                text = th.get_text().strip().replace('\n', '')
                headers.append(text)
            print(f"[INFO] Table headers: {headers}")
            
            # 寸評の位置を確認
            sunpyo_index = -1
            for i, h in enumerate(headers):
                if "\u5bf8\u8a55" in h:  # 寸評
                    sunpyo_index = i
                    break
            
            if sunpyo_index >= 0:
                print(f"[OK] 'sunpyo' column at index {sunpyo_index}")
                
                # 最初のデータ行から寸評を取得
                rows = table.find_all('tr')[1:4]  # 最初の3行
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) > sunpyo_index:
                        horse_name = ""
                        sunpyo_value = ""
                        
                        # 馬名を探す
                        for cell in cells:
                            link = cell.find('a', class_='umalink_click')
                            if link:
                                horse_name = link.get_text().strip()
                                break
                        
                        sunpyo_value = cells[sunpyo_index].get_text().strip()
                        print(f"  - {horse_name}: sunpyo='{sunpyo_value}'")
            else:
                print("[WARN] 'sunpyo' column NOT in headers")
        else:
            print("[ERROR] Table not found")
        
        # パーサーでパースしてみる
        print("\n[INFO] Testing with SeisekiParser...")
        parser = SeisekiParser(debug=False)
        
        # 一時ファイルに保存してパース
        temp_path = Path("temp_seiseki.html")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        try:
            result = parser.parse(str(temp_path))
            
            # 結果の最初の3馬を表示
            if result.get('results'):
                print(f"[OK] Parsed {len(result['results'])} horses")
                for i, horse in enumerate(result['results'][:3]):
                    # 寸評キーがあるか確認
                    keys = list(horse.keys())
                    sunpyo_key = None
                    for k in keys:
                        if "\u5bf8\u8a55" in k:
                            sunpyo_key = k
                            break
                    
                    if sunpyo_key:
                        horse_name_val = horse.get('馬名', 'Unknown')
                        sunpyo_val = horse.get(sunpyo_key, '')
                        print(f"  - {horse_name_val}: {sunpyo_key}='{sunpyo_val}'")
                    else:
                        keys_str = str(keys[:10])
                        print(f"  - Keys: {keys_str}...")
        finally:
            temp_path.unlink(missing_ok=True)
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    race_id = sys.argv[1] if len(sys.argv) > 1 else "202601050312"
    test_sunpyo(race_id)

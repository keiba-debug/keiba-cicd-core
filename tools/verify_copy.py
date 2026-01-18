# -*- coding: utf-8 -*-
import os

path = 'Z:/KEIBA-CICD/調教データ/output_251228.txt'
if os.path.exists(path):
    size = os.path.getsize(path)
    print(f'ファイルサイズ: {size} bytes')
    
    # 行数確認
    with open(path, 'r', encoding='cp932') as f:
        lines = f.readlines()
        print(f'行数: {len(lines)}')
        
    # ゴキゲンサン確認
    with open(path, 'r', encoding='cp932') as f:
        for line in f:
            if 'ゴキゲンサン' in line:
                print(f'ゴキゲンサン: {line.strip()}')
                break
else:
    print(f'ファイルが見つかりません: {path}')

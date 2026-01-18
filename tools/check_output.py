# -*- coding: utf-8 -*-
with open('keiba-cicd-core/tools/output_test.txt', 'r', encoding='cp932') as f:
    lines = f.readlines()
    print(f'総行数: {len(lines)}')
    
    # ゴから始まる馬を探す
    print('\nゴ から始まる馬:')
    for i, line in enumerate(lines):
        parts = line.strip().split('\t')
        if len(parts) >= 1 and parts[0].startswith('ゴ'):
            print(f'  Line {i+1}: {line.strip()}')
    
    # ゴキゲンサンを探す
    print('\nゴキゲンサン検索:')
    for i, line in enumerate(lines):
        if 'ゴキゲンサン' in line:
            print(f'  Found at line {i+1}: {line.strip()}')
            break
    else:
        print('  見つかりません')

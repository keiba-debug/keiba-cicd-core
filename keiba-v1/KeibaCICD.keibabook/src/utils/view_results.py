#!/usr/bin/env python3
"""
生成されたMDの結果セクションを確認
"""

import glob

# MDファイルを取得
files = glob.glob('Z:/KEIBA-CICD/data/organized/2025/08/23/*/202504020111.md')

if files:
    with open(files[0], 'r', encoding='utf-8') as f:
        content = f.read()
    
    # レース結果セクションを探す
    start = content.find('## 🏁 レース結果')
    if start > 0:
        end = content.find('\n## ', start + 1)
        if end < 0:
            end = len(content)
        
        section = content[start:end]
        
        # 新機能の確認
        print("=== RACE RESULTS SECTION ===\n")
        # エンコーディングエラーを避けるため、絵文字を除去
        clean_section = section.replace('🏁', '[FLAG]').replace('💬', '[COMMENT]')
        print(clean_section[:2000] if len(clean_section) > 2000 else clean_section)
        print("\n=== VALIDATION ===")
        print(f"[OK] Has lap summary: {'レースラップ要約' in section}")
        print(f"[OK] Has extended columns: {'上り3F' in section and '通過' in section and '4角' in section}")
        print(f"[OK] Has payouts table: {'### 払戻' in section}")
    else:
        print("No results section found")
else:
    print("No MD file found")
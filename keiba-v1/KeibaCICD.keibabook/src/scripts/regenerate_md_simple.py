#!/usr/bin/env python3
"""
MDファイルを再生成（札幌のみ）
"""

import json
import os
from src.integrator.markdown_generator import MarkdownGenerator

# 札幌の統合JSONファイルを処理
integrated_dir = "Z:/KEIBA-CICD/data/organized/2025/08/24/札幌"
generator = MarkdownGenerator()

json_files = [f for f in os.listdir(integrated_dir) if f.startswith('integrated_') and f.endswith('.json')]
print(f"札幌の統合JSONファイル数: {len(json_files)}")

for json_file in json_files:
    json_path = os.path.join(integrated_dir, json_file)
    print(f"処理中: {json_file}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        race_data = json.load(f)
    
    # MDファイルを生成
    generator.generate_race_markdown(race_data, save=True)

# 札幌11RのMDファイルを確認
md_file = "Z:/KEIBA-CICD/data/organized/2025/08/24/札幌/202502080211.md"
if os.path.exists(md_file):
    print(f"\n札幌11R (キーンランドC) のMDファイルを確認中...")
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # 発走予定時刻の行を探す
        found_time = False
        for line in content.split('\n'):
            if "発走予定時刻" in line:
                print(f"[OK] 発走予定時刻が見つかりました: {line.strip()}")
                found_time = True
                break
        if not found_time:
            # レース情報セクションの最初の10行を表示
            print("レース情報セクションの内容:")
            in_race_info = False
            line_count = 0
            for line in content.split('\n'):
                if "## レース情報" in line:
                    in_race_info = True
                elif in_race_info and line_count < 10:
                    print(f"  {line}")
                    line_count += 1
                elif line_count >= 10:
                    break
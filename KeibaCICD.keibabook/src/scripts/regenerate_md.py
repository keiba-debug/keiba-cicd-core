#!/usr/bin/env python3
"""
MDファイルを再生成（start_time含む）
"""

import os
import sys
from src.integrator.markdown_generator import MarkdownGenerator

# 対象日付
date_str = "20250824"

# MarkdownGeneratorを初期化
generator = MarkdownGenerator()

print(f"日付 {date_str} のMDファイルを再生成します...")

# batch_generateを実行（特定日付のディレクトリを指定）
integrated_dir = f"Z:/KEIBA-CICD/data/organized/2025/08/24"
result = generator.batch_generate(integrated_dir)

if result['success']:
    print(f"\n=== 再生成完了 ===")
    print(f"成功: {result['success_count']}レース")
    print(f"失敗: {result['failed_count']}レース")
    print(f"成功率: {result['success_rate']:.1f}%")
    
    # 札幌11RのMDファイルを確認
    md_file = "Z:/KEIBA-CICD/data/organized/2025/08/24/札幌/202502080211.md"
    if os.path.exists(md_file):
        print(f"\n札幌11RのMDファイルを確認中...")
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # 発走時刻が含まれているか確認
            if "発走予定時刻" in content:
                print("✓ MDファイルに「発走予定時刻」が含まれています")
                # 該当行を表示
                for line in content.split('\n'):
                    if "発走予定時刻" in line:
                        print(f"  {line.strip()}")
                        break
            else:
                print("✗ MDファイルに「発走予定時刻」が見つかりません")
else:
    print(f"エラー: {result.get('error', '不明なエラー')}")
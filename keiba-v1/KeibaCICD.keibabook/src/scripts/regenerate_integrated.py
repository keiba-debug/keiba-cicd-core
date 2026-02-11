#!/usr/bin/env python3
"""
統合JSONファイルを再生成（start_time含む）
"""

import os
import sys
from src.integrator.race_data_integrator import RaceDataIntegrator

# 対象日付
date_str = "20250824"

# RaceDataIntegratorを初期化
integrator = RaceDataIntegrator(use_organized_dir=True)

# 実際の日付マッピングを読み込み（既存のメソッドを使用）
integrator.load_actual_dates()

print(f"日付 {date_str} の統合ファイルを再生成します...")

# batch_create_integrated_filesを実行
result = integrator.batch_create_integrated_files(date_str)

if result['success']:
    print(f"\n=== 再生成完了 ===")
    print(f"成功: {result['success_count']}レース")
    print(f"失敗: {result['failed_count']}レース")
    print(f"成功率: {result['success_rate']:.1f}%")
else:
    print(f"エラー: {result.get('error', '不明なエラー')}")
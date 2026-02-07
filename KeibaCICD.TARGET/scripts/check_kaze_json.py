#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
カゼノハゴロモの調教サマリデータを確認
"""

import json

json_file = r"C:\KEIBA-CICD\data2\races\2026\02\07\temp\training_summary.json"

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

summaries = data['summaries']

# カゼノハゴロモを検索
kaze = summaries.get('カゼノハゴロモ')

if kaze:
    print("=== カゼノハゴロモ ===")
    print(f"最終追切: {kaze.get('finalDate')} {kaze.get('finalCenter')} {kaze.get('finalLocation')}")
    print(f"4Fタイム: {kaze.get('finalTime4F')}秒")
    print(f"Lap1: {kaze.get('finalLap1')}秒")
    print(f"Lap評価: {kaze.get('finalLap')}")
    print(f"スピード: {kaze.get('finalSpeed')}")
    print(f"Detail: {kaze.get('detail')}")
else:
    print("カゼノハゴロモが見つかりません")
    print("馬名例:", list(summaries.keys())[:10])

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ワイドアルバの調教サマリデータを確認
"""

import json

json_file = r"C:\KEIBA-CICD\data2\races\2026\02\07\temp\training_summary.json"

with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

summaries = data['summaries']

# ワイドアルバを検索
wide_aruba = summaries.get('ワイドアルバ')

if wide_aruba:
    print("=== ワイドアルバ ===")
    print(f"最終追切: {wide_aruba.get('finalDate')} {wide_aruba.get('finalCenter')} {wide_aruba.get('finalLocation')}")
    print(f"4Fタイム: {wide_aruba.get('finalTime4F')}秒")
    print(f"3Fタイム: {wide_aruba.get('finalTime3F')}秒")
    print(f"2Fタイム: {wide_aruba.get('finalTime2F')}秒")
    print(f"Lap1: {wide_aruba.get('finalLap1')}秒")
    print(f"Lap評価: {wide_aruba.get('finalLap')}")
    print(f"スピード: {wide_aruba.get('finalSpeed')}")
    print(f"Detail: {wide_aruba.get('detail')}")
else:
    print("ワイドアルバが見つかりません")
    print("馬名例:", list(summaries.keys())[:10])

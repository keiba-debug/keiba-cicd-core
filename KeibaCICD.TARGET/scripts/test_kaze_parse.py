#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
カゼノハゴロモのWC_DATAパースをテスト
"""

import os
import sys
from pathlib import Path

# 環境変数設定
os.environ.setdefault("KEIBA_DATA_ROOT_DIR", r"C:\KEIBA-CICD\data2")
os.environ.setdefault("JV_DATA_ROOT_DIR", r"C:\TFJV")

# PYTHONPATHにTARGETディレクトリを追加
target_dir = Path(__file__).parent.parent
if str(target_dir) not in sys.path:
    sys.path.insert(0, str(target_dir))

from parse_ck_data import parse_ck_file

def test_kaze():
    """カゼノハゴロモ（2023103073）のWC_DATAを確認"""

    # WC020260205.DAT（美浦コース、2026年2月5日）
    wc_file = Path(r"C:\TFJV\CK_DATA\2026\202602\WC020260205.DAT")

    if not wc_file.exists():
        print(f"❌ ファイルが見つかりません: {wc_file}")
        return False

    print(f"📁 ファイル: {wc_file}")
    print(f"📊 パース開始...\n")

    # パース実行
    records = parse_ck_file(wc_file)

    # カゼノハゴロモ（2023103073）のデータを検索
    target_horse_id = "2023103073"
    target_records = [r for r in records if r.horse_id == target_horse_id]

    if not target_records:
        print(f"❌ 馬ID {target_horse_id} のデータがパースされていません")
        print(f"   全{len(records)}件のレコードを確認しました")

        # デバッグ: 最初の数件を表示
        print("\n最初の5件のレコード:")
        for i, r in enumerate(records[:5], 1):
            print(f"  {i}. {r.horse_id} - {r.date} {r.time} {r.center}{r.location}")

        return False

    print(f"✅ {len(target_records)}件のレコードが見つかりました\n")

    # 各レコードを表示
    for i, record in enumerate(target_records, 1):
        print(f"=== レコード {i} ===")
        print(f"  日時: {record.date} {record.time}")
        print(f"  場所: {record.center}{record.location}")
        print(f"  4Fタイム: {record.time_4f:.1f}秒")
        print(f"  3Fタイム: {record.time_3f:.1f}秒")
        print(f"  2Fタイム: {record.time_2f:.1f}秒")
        print(f"  Lap4: {record.lap_4:.1f}秒")
        print(f"  Lap3: {record.lap_3:.1f}秒")
        print(f"  Lap2: {record.lap_2:.1f}秒")
        print(f"  Lap1: {record.lap_1:.1f}秒")
        print(f"  スピード: {record.speed_class}")
        print(f"  ラップ: {record.lap_class}")
        print(f"  upgraded_lap_class: {record.upgraded_lap_class}")
        print()

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("カゼノハゴロモ WC_DATAパース確認")
    print("=" * 60)
    print()

    try:
        result = test_kaze()

        print("=" * 60)
        if result:
            print("✅ パース成功")
        else:
            print("❌ パース失敗")
        print("=" * 60)

        sys.exit(0 if result else 1)

    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

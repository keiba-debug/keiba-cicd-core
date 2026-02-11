#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HC_DATAパース修正の動作確認スクリプト

ワイドアルバ（2023106359）の2/4(水)7:52栗東坂路の調教データを確認
期待値: 4F=54.9秒, 3F=40.4秒, 2F=26.6秒, Lap1=13.0秒
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

def test_wide_aruba():
    """ワイドアルバ（2023106359）の調教データを確認"""

    # HC120260204.DAT（栗東坂路、2026年2月4日）
    ck_file = Path(r"C:\TFJV\CK_DATA\2026\202602\HC120260204.DAT")

    if not ck_file.exists():
        print(f"❌ ファイルが見つかりません: {ck_file}")
        return False

    print(f"📁 ファイル: {ck_file}")
    print(f"📊 パース開始...\n")

    # パース実行
    records = parse_ck_file(ck_file)

    # ワイドアルバ（2023106359）のデータを検索
    target_horse_id = "2023106359"
    target_records = [r for r in records if r.horse_id == target_horse_id]

    if not target_records:
        print(f"❌ 馬ID {target_horse_id} のデータが見つかりません")
        print(f"   全{len(records)}件のレコードを確認しました")
        return False

    print(f"✅ {len(target_records)}件のレコードが見つかりました\n")

    # 期待値
    expected = {
        "time_4f": 54.9,
        "time_3f": 40.4,
        "time_2f": 26.6,
        "lap_1": 13.0,
        "lap_2": 13.6,
        "lap_3": 13.8,
        "lap_4": 14.5,
    }

    # 各レコードを検証
    all_passed = True
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

        # 検証（小数点1桁まで比較）
        errors = []
        for key, exp_value in expected.items():
            actual_value = getattr(record, key)
            if abs(actual_value - exp_value) > 0.01:
                errors.append(f"  ❌ {key}: 期待値 {exp_value:.1f}, 実際 {actual_value:.1f}")

        if errors:
            print("  結果: ❌ FAILED")
            for err in errors:
                print(err)
            all_passed = False
        else:
            print("  結果: ✅ PASSED")
        print()

    return all_passed

if __name__ == "__main__":
    print("=" * 60)
    print("HC_DATAパース修正の動作確認")
    print("=" * 60)
    print()

    try:
        result = test_wide_aruba()

        print("=" * 60)
        if result:
            print("✅ 全テストPASS - 修正成功！")
        else:
            print("❌ テストFAILED - 期待値と一致しません")
        print("=" * 60)

        sys.exit(0 if result else 1)

    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

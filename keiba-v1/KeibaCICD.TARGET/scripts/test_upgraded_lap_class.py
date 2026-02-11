#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
upgraded_lap_class プロパティのテストスクリプト

5つのテストケース:
1. SS昇格（好タイム + S+）
2. SS昇格（好タイム + S=）
3. SS非昇格（好タイム + S-）
4. SS非昇格（非好タイム + S+）
5. 通常A評価（非好タイム + A+）
"""

from parse_ck_data import TrainingRecord, TrainingConfig

# テスト用の設定（美浦坂路の基準: 52.9秒、13.4秒）
config = TrainingConfig()

def create_test_record(time_4f: float, lap_1: float, lap_2: float) -> TrainingRecord:
    """テスト用のTrainingRecordを作成"""
    return TrainingRecord(
        date="20260207",
        time="0800",
        center="美浦",
        location="坂路",
        horse_id="2019103487",
        time_4f=time_4f,
        time_3f=time_4f * 0.75,  # 仮の値
        time_2f=time_4f * 0.5,   # 仮の値
        lap_4=13.5,
        lap_3=13.3,
        lap_2=lap_2,
        lap_1=lap_1,
    )

def test_case_1():
    """テストケース1: SS昇格（好タイム + S+）"""
    print("\n=== テストケース1: SS昇格（好タイム + S+）===")
    # 好タイム: 52.0秒（基準52.9秒より速い）
    # ラップ: lap_2=12.2, lap_1=11.8 → 加速（+）
    # lap_1=11.8 → 基準13.4 - 1.5 = 11.9以下なのでS
    record = create_test_record(time_4f=52.0, lap_1=11.8, lap_2=12.2)

    print(f"  4Fタイム: {record.time_4f:.1f}秒")
    print(f"  好タイム: {record.is_good_time}")
    print(f"  Lap1: {record.lap_1:.1f}秒, Lap2: {record.lap_2:.1f}秒")
    print(f"  加速: {record.acceleration}")
    print(f"  lap_class: {record.lap_class}")
    print(f"  upgraded_lap_class: {record.upgraded_lap_class}")

    expected = "SS"
    actual = record.upgraded_lap_class
    assert actual == expected, f"Expected {expected}, but got {actual}"
    print(f"  ✅ PASS: {expected}")

def test_case_2():
    """テストケース2: SS昇格（好タイム + S=）"""
    print("\n=== テストケース2: SS昇格（好タイム + S=）===")
    # 好タイム: 51.5秒
    # ラップ: lap_2=11.8, lap_1=11.8 → 同タイム（=）
    record = create_test_record(time_4f=51.5, lap_1=11.8, lap_2=11.8)

    print(f"  4Fタイム: {record.time_4f:.1f}秒")
    print(f"  好タイム: {record.is_good_time}")
    print(f"  Lap1: {record.lap_1:.1f}秒, Lap2: {record.lap_2:.1f}秒")
    print(f"  加速: {record.acceleration}")
    print(f"  lap_class: {record.lap_class}")
    print(f"  upgraded_lap_class: {record.upgraded_lap_class}")

    expected = "SS"
    actual = record.upgraded_lap_class
    assert actual == expected, f"Expected {expected}, but got {actual}"
    print(f"  ✅ PASS: {expected}")

def test_case_3():
    """テストケース3: SS非昇格（好タイム + S-）"""
    print("\n=== テストケース3: SS非昇格（好タイム + S-）===")
    # 好タイム: 52.5秒
    # ラップ: lap_2=11.5, lap_1=11.9 → 減速（-）
    record = create_test_record(time_4f=52.5, lap_1=11.9, lap_2=11.5)

    print(f"  4Fタイム: {record.time_4f:.1f}秒")
    print(f"  好タイム: {record.is_good_time}")
    print(f"  Lap1: {record.lap_1:.1f}秒, Lap2: {record.lap_2:.1f}秒")
    print(f"  加速: {record.acceleration}")
    print(f"  lap_class: {record.lap_class}")
    print(f"  upgraded_lap_class: {record.upgraded_lap_class}")

    expected = "S-"
    actual = record.upgraded_lap_class
    assert actual == expected, f"Expected {expected}, but got {actual}"
    print(f"  ✅ PASS: {expected}")

def test_case_4():
    """テストケース4: SS非昇格（非好タイム + S+）"""
    print("\n=== テストケース4: SS非昇格（非好タイム + S+）===")
    # 非好タイム: 53.5秒（基準52.9秒より遅い）
    # ラップ: lap_2=12.2, lap_1=11.8 → 加速（+）
    record = create_test_record(time_4f=53.5, lap_1=11.8, lap_2=12.2)

    print(f"  4Fタイム: {record.time_4f:.1f}秒")
    print(f"  好タイム: {record.is_good_time}")
    print(f"  Lap1: {record.lap_1:.1f}秒, Lap2: {record.lap_2:.1f}秒")
    print(f"  加速: {record.acceleration}")
    print(f"  lap_class: {record.lap_class}")
    print(f"  upgraded_lap_class: {record.upgraded_lap_class}")

    expected = "S+"
    actual = record.upgraded_lap_class
    assert actual == expected, f"Expected {expected}, but got {actual}"
    print(f"  ✅ PASS: {expected}")

def test_case_5():
    """テストケース5: 通常A評価（非好タイム + A+）"""
    print("\n=== テストケース5: 通常A評価（非好タイム + A+）===")
    # 非好タイム: 54.0秒
    # ラップ: lap_2=13.2, lap_1=12.8 → 加速（+）
    # lap_1=12.8 → 基準13.4 - 0.5 = 12.9以下なのでA
    record = create_test_record(time_4f=54.0, lap_1=12.8, lap_2=13.2)

    print(f"  4Fタイム: {record.time_4f:.1f}秒")
    print(f"  好タイム: {record.is_good_time}")
    print(f"  Lap1: {record.lap_1:.1f}秒, Lap2: {record.lap_2:.1f}秒")
    print(f"  加速: {record.acceleration}")
    print(f"  lap_class: {record.lap_class}")
    print(f"  upgraded_lap_class: {record.upgraded_lap_class}")

    expected = "A+"
    actual = record.upgraded_lap_class
    assert actual == expected, f"Expected {expected}, but got {actual}"
    print(f"  ✅ PASS: {expected}")

if __name__ == "__main__":
    print("=" * 60)
    print("upgraded_lap_class プロパティのテスト")
    print("=" * 60)

    try:
        test_case_1()
        test_case_2()
        test_case_3()
        test_case_4()
        test_case_5()

        print("\n" + "=" * 60)
        print("✅ 全テストケースPASS")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)

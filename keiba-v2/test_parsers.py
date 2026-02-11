#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
パーサー動作検証スクリプト

実データを使って各パーサーの出力を確認する。
"""
import sys
import json
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.config import print_config
from core.jravan import race_id as rid


def test_config():
    print("\n" + "=" * 60)
    print("1. Config テスト")
    print("=" * 60)
    print_config()


def test_race_id():
    print("\n" + "=" * 60)
    print("2. RaceID テスト")
    print("=" * 60)

    # 構築テスト
    r = rid.build(2026, 1, 24, "06", 1, 2, 8)
    print(f"  build(2026,1,24,'06',1,2,8) = {r}")
    assert r == "2026012406010208", f"Expected 2026012406010208, got {r}"

    # パーステスト
    info = rid.parse(r)
    print(f"  parse({r}) = {info}")
    assert info['venue_name'] == '中山'
    assert info['race_num'] == '08'

    # 人間可読テスト
    human = rid.to_human(r)
    print(f"  to_human({r}) = {human}")

    # SE_DATAからの構築テスト
    r2 = rid.build_from_se("2026", "0124", "06", 1, 2, 8)
    print(f"  build_from_se = {r2}")
    assert r2 == r

    # 日付パステスト
    p = rid.to_date_path(r)
    print(f"  to_date_path = {p}")
    assert p == "2026/01/24"

    print("  -> RaceID: ALL PASSED")


def test_se_parser():
    print("\n" + "=" * 60)
    print("3. SE_DATA パーサーテスト")
    print("=" * 60)

    from core.jravan import se_parser

    # レコード数概算
    count = se_parser.count_records([2025])
    print(f"  2025年 レコード概算: {count:,}")

    # 最初の5レコード
    print("\n  最初の5レコード:")
    for i, rec in enumerate(se_parser.scan([2025])):
        if i >= 5:
            break
        print(f"    [{i+1}] race_id={rec['race_id']} "
              f"umaban={rec['umaban']} {rec['horse_name']} "
              f"着順={rec['finish_position']} "
              f"タイム={rec['time']} "
              f"上3F={rec['last_3f']} "
              f"オッズ={rec['odds']} "
              f"人気={rec['popularity']} "
              f"斤量={rec['futan']} "
              f"馬体重={rec['horse_weight']}({rec['horse_weight_diff']:+d}) "
              f"通過={rec['corners']} "
              f"騎手={rec['jockey_name']} "
              f"調教師={rec['trainer_name']}")

    print("  -> SE_DATA: OK")


def test_sr_parser():
    print("\n" + "=" * 60)
    print("4. SR_DATA パーサーテスト")
    print("=" * 60)

    from core.jravan import sr_parser

    records = sr_parser.scan([2025])
    print(f"  2025年 有効レコード数: {len(records):,}")

    # 最初の5レコード
    print("\n  最初の5レコード:")
    for rec in records[:5]:
        pace = rec.to_pace_dict()
        print(f"    race_id={rec.race_id} {rec.venue_name} {rec.race_number}R "
              f"{rec.track_type} {rec.distance}m {rec.baba_name} "
              f"{rec.num_runners}頭 "
              f"S3={pace['s3']} L3={pace['l3']} RPCI={pace['rpci']} "
              f"傾向={pace['race_trend']}")

    print("  -> SR_DATA: OK")


def test_um_parser():
    print("\n" + "=" * 60)
    print("5. UM_DATA パーサーテスト")
    print("=" * 60)

    from core.jravan import um_parser

    # 最新ファイル一覧
    files = um_parser.get_um_files(5)
    print(f"  最新UMファイル数: {len(files)}")
    for f in files[:3]:
        print(f"    {f.name}")

    # 名前インデックス構築（少数テスト）
    horses = um_parser.scan(recent_n=2)
    print(f"\n  スキャン結果（最新2ファイル）: {len(horses):,} 頭")

    # 最初の5頭
    for h in horses[:5]:
        print(f"    {h.ketto_num}: {h.name} ({h.sex_name}) "
              f"調教師={h.trainer_name}({h.trainer_code}) "
              f"{h.tozai_name} "
              f"{'現役' if h.is_active else '抹消'}")

    print("  -> UM_DATA: OK")


def test_cross_validation():
    """SE_DATAとSR_DATAの同一race_idで突き合わせ"""
    print("\n" + "=" * 60)
    print("6. SE × SR クロス検証")
    print("=" * 60)

    from core.jravan import se_parser, sr_parser

    # 2025年の最初のSR_DATAレコードを取得
    sr_records = sr_parser.scan([2025])
    if not sr_records:
        print("  SR_DATAが見つかりません")
        return

    target = sr_records[0]
    print(f"  対象レース: {rid.to_human(target.race_id)}")
    print(f"  距離={target.distance}m {target.track_type} {target.baba_name} "
          f"{target.num_runners}頭")
    print(f"  ペース: S3={target.first_3f} L3={target.last_3f} RPCI={target.rpci}")

    # 同じrace_idのSE_DATAを検索
    print(f"\n  出走馬:")
    count = 0
    for rec in se_parser.scan([2025]):
        if rec['race_id'] == target.race_id:
            count += 1
            print(f"    {rec['umaban']:2d}番 {rec['horse_name']:<10s} "
                  f"着順={rec['finish_position']:2d} タイム={rec['time']} "
                  f"上3F={rec['last_3f']:.1f} オッズ={rec['odds']:.1f} "
                  f"騎手={rec['jockey_name']}")

    print(f"\n  SE_DATA出走頭数: {count} / SR_DATA出走頭数: {target.num_runners}")
    if count == target.num_runners:
        print("  -> 頭数一致: PASSED")
    else:
        print(f"  -> 頭数不一致（{count} vs {target.num_runners}）: INVESTIGATE")


if __name__ == '__main__':
    test_config()
    test_race_id()
    test_se_parser()
    test_sr_parser()
    test_um_parser()
    test_cross_validation()

    print("\n" + "=" * 60)
    print("全テスト完了!")
    print("=" * 60)

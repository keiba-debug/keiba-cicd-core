#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教師×調教×着順 履歴データ収集スクリプト（v2: 高速版）

既存の training_summary.json（バッチ生成済み）と SE_DATA（レース成績）を
kettoNum+raceDate でマージし、調教師ごとの履歴を収集する。

v1はCK_DATAを1件ずつ再解析していたため19万件×ファイルI/Oで数時間かかったが、
v2は事前生成済みJSONを使うため数分で完了する。

出力: trainer_training_history.json（中間ファイル）
→ analyze_trainer_patterns.py で統計分析に使用

Usage:
    python collect_trainer_training_history.py --since 2023
    python collect_trainer_training_history.py --since 2024 --output C:/KEIBA-CICD/data2/target/trainer_training_history.json
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# UTF-8出力
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# パス設定
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))

from common.config import get_keiba_data_root

# SE_DATAリーダー（__init__.py回避のため直接ロード）
import importlib.util
_se_spec = importlib.util.spec_from_file_location(
    'se_reader',
    str(SCRIPT_DIR.parent / 'common' / 'jravan' / 'se_reader.py')
)
se_reader = importlib.util.module_from_spec(_se_spec)
_se_spec.loader.exec_module(se_reader)


def load_trainer_index() -> Dict:
    """
    trainer_id_index.json を読み込み、名前→jvn_code の逆引き辞書を構築
    """
    data_root = get_keiba_data_root()
    index_path = Path(data_root) / "target" / "trainer_id_index.json"
    if not index_path.exists():
        print(f"警告: trainer_id_index.json が見つかりません: {index_path}")
        return {'name_to_jvn': {}, 'jvn_to_info': {}}

    with open(index_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    name_to_jvn: Dict[str, str] = {}
    jvn_to_info: Dict[str, Dict] = {}

    for kb_id, info in raw.items():
        jvn_code = info.get('jvn_code', '')
        name = info.get('name', '')
        if jvn_code and name:
            name_to_jvn[name] = jvn_code
            if jvn_code not in jvn_to_info:
                jvn_to_info[jvn_code] = {
                    'name': name,
                    'tozai': info.get('tozai', ''),
                    'keibabook_ids': [],
                }
            jvn_to_info[jvn_code]['keibabook_ids'].append(kb_id)

    return {'name_to_jvn': name_to_jvn, 'jvn_to_info': jvn_to_info}


def load_all_training_summaries(since_year: int) -> Tuple[Dict[str, Dict], int, int]:
    """
    既存の training_summary.json を全読みし、
    kettoNum+raceDate → training features のマップを構築

    Returns:
        (training_map, files_loaded, horses_loaded)
    """
    data_root = Path(get_keiba_data_root())
    races_dir = data_root / "races"

    training_map: Dict[str, Dict] = {}
    files_loaded = 0
    horses_loaded = 0

    for year_dir in sorted(races_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
        except ValueError:
            continue
        if year < since_year:
            continue

        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue

                summary_path = day_dir / "temp" / "training_summary.json"
                if not summary_path.exists():
                    continue

                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue

                # 日付を YYYYMMDD 形式に
                meta = data.get('meta', {})
                date_str = meta.get('date', '')  # "2023-01-05"
                if date_str:
                    race_date = date_str.replace('-', '')
                else:
                    race_date = f"{year_dir.name}{month_dir.name}{day_dir.name}"

                summaries = data.get('summaries', {})
                for horse_name, summary in summaries.items():
                    ketto_num = summary.get('kettoNum', '')
                    if not ketto_num:
                        continue

                    key = f"{ketto_num}_{race_date}"

                    # 加速パターンを finalLap 末尾から推測
                    fl = summary.get('finalLap', '')
                    accel = ''
                    if fl and fl[-1] in ('+', '-', '='):
                        accel = fl[-1]

                    training_map[key] = {
                        'finalLap': fl,
                        'finalLocation': summary.get('finalLocation', ''),
                        'finalSpeed': summary.get('finalSpeed', ''),
                        'finalTime4F': summary.get('finalTime4F', 0),
                        'finalLap1': summary.get('finalLap1', 0),
                        'finalAcceleration': accel,
                        'weekendLap': summary.get('weekendLap', ''),
                        'weekendLocation': summary.get('weekendLocation', ''),
                        'weekendSpeed': summary.get('weekendSpeed', ''),
                        'weekAgoLap': summary.get('weekAgoLap', ''),
                        'timeClass': summary.get('timeRank', ''),
                        'hasGoodTime': summary.get('finalSpeed') == '◎',
                        'countLabel': '',
                        'totalCount': 0,
                    }
                    horses_loaded += 1

                files_loaded += 1

    return training_map, files_loaded, horses_loaded


def collect_history(years: List[int]) -> Dict:
    """
    training_summary.json × SE_DATA を kettoNum+raceDate でマージし、
    調教師別の履歴を収集
    """
    print(f"\n{'='*60}")
    print(f"=== 調教師×調教×着順 履歴データ収集 (v2: 高速版) ===")
    print(f"{'='*60}")
    print(f"対象年: {years}")

    start_time = time.time()

    # 1. 調教師インデックスの読み込み
    print("\n[Step 1] 調教師インデックス読み込み...")
    trainer_index = load_trainer_index()
    name_to_jvn = trainer_index['name_to_jvn']
    jvn_to_info = trainer_index['jvn_to_info']
    print(f"  調教師数: {len(name_to_jvn)}")

    # 2. 調教サマリ全読み込み
    since_year = min(years)
    print(f"\n[Step 2] 調教サマリJSON読み込み ({since_year}年〜)...")
    training_map, files_loaded, horses_loaded = load_all_training_summaries(since_year)
    elapsed = time.time() - start_time
    print(f"  ファイル数: {files_loaded}")
    print(f"  馬×日エントリ: {horses_loaded:,}")
    print(f"  ({elapsed:.1f}秒)")

    # 3. SE_DATAスキャン → 調教データとマージ
    print(f"\n[Step 3] SE_DATAスキャン & 調教マージ...")
    total_estimate = se_reader.count_se_records(years)
    print(f"  概算レコード数: {total_estimate:,}")

    trainer_records: Dict[str, List[Dict]] = defaultdict(list)
    matched_count = 0
    unmatched_trainer = 0
    no_training = 0
    skipped = 0

    for i, rec in enumerate(se_reader.scan_se_data(years)):
        if rec['finishPosition'] <= 0:
            skipped += 1
            continue

        # 調教師マッチ
        trainer_name = rec['trainerName']
        jvn_code = name_to_jvn.get(trainer_name)
        if not jvn_code:
            unmatched_trainer += 1
            continue

        # 調教データマッチ（dictルックアップのみ、ファイルI/Oなし）
        key = f"{rec['kettoNum']}_{rec['raceDate']}"
        training = training_map.get(key)
        if not training or not training.get('finalLap'):
            no_training += 1
            continue

        matched_count += 1
        record = {
            'raceDate': rec['raceDate'],
            'kettoNum': rec['kettoNum'],
            'horseName': rec['horseName'],
            'finishPosition': rec['finishPosition'],
            'odds': rec['odds'],
            'popularity': rec['popularity'],
            'training': training,
        }
        trainer_records[jvn_code].append(record)

        if (i + 1) % 20000 == 0:
            elapsed = time.time() - start_time
            pct = (i + 1) / max(total_estimate, 1) * 100
            print(f"  ... {i+1:,} ({pct:.0f}%) マッチ:{matched_count:,} 調教なし:{no_training:,} ({elapsed:.1f}秒)")

    elapsed = time.time() - start_time
    print(f"  スキャン完了: マッチ {matched_count:,} / 調教なし {no_training:,} / 調教師不明 {unmatched_trainer:,} ({elapsed:.1f}秒)")

    # 4. 結果構築
    print(f"\n[Step 4] 結果構築...")
    trainers_output = {}
    for jvn_code, records in trainer_records.items():
        info = jvn_to_info.get(jvn_code, {})
        trainers_output[jvn_code] = {
            'name': info.get('name', ''),
            'tozai': info.get('tozai', ''),
            'keibabook_ids': info.get('keibabook_ids', []),
            'records': records,
        }

    total_records = sum(len(t['records']) for t in trainers_output.values())
    trainers_with_20plus = sum(1 for t in trainers_output.values() if len(t['records']) >= 20)

    result = {
        'meta': {
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'years': years,
            'total_se_records_matched': matched_count,
            'total_training_records': total_records,
            'total_trainers': len(trainers_output),
            'trainers_with_20plus_records': trainers_with_20plus,
            'training_summary_files': files_loaded,
            'collection_time_sec': round(elapsed, 1),
        },
        'trainers': trainers_output,
    }

    print(f"\n{'='*50}")
    print(f"=== 収集結果 ===")
    print(f"  調教師数: {len(trainers_output)}")
    print(f"  20走以上: {trainers_with_20plus}")
    print(f"  総レコード: {total_records:,}")
    print(f"  処理時間: {elapsed:.1f}秒")
    print(f"{'='*50}")

    return result


def main():
    parser = argparse.ArgumentParser(description='調教師×調教×着順 履歴データ収集（v2高速版）')
    parser.add_argument('--since', type=int, default=2023,
                        help='開始年（デフォルト: 2023）')
    parser.add_argument('--until', type=int, default=2026,
                        help='終了年（デフォルト: 2026）')
    parser.add_argument('--output', type=str, default=None,
                        help='出力ファイルパス')
    args = parser.parse_args()

    years = list(range(args.since, args.until + 1))
    data_root = Path(get_keiba_data_root())
    output_path = Path(args.output) if args.output else (data_root / 'target' / 'trainer_training_history.json')

    # 収集実行
    result = collect_history(years)

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n保存完了: {output_path} ({file_size_mb:.1f} MB)")

    return 0


if __name__ == '__main__':
    sys.exit(main())

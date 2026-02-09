#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教師パターン分析スクリプト

collect_trainer_training_history.py の出力を分析し、
調教師ごとの勝負パターン（好走率の高い調教パターン）を特定する。

出力: trainer_patterns.json
→ WebViewerのフロントエンドで使用

Usage:
    python analyze_trainer_patterns.py
    python analyze_trainer_patterns.py --input history.json --output patterns.json
    python analyze_trainer_patterns.py --min-records 10
"""

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# UTF-8出力
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# パス設定
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))
from common.config import get_target_data_dir, get_jv_data_root

# FALLBACK_QUICK_REFERENCE: 手動で定義された24名の勝負パターン
QUICK_REFERENCE: Dict[str, str] = {
    "矢作芳人": "A2ラップ（2F各12秒台加速）",
    "友道康夫": "A1ラップ（終い1Fのみ12秒台）",
    "木村哲也": "前週坂路55秒以下+当週ウッド+ルメール",
    "堀宣行": "ウッド4F 53秒切り",
    "上村洋行": "前週土日坂路+当週ウッド終い11秒台",
    "高野友和": "坂路55秒以上+A1（地味な加速）",
    "鹿戸雄一": "前週土日坂路55秒以下+当週追い切り",
    "藤原英昭": "坂路11秒台ラップ（A3/B3）+前日追いなし",
    "寺島良": "前週土日坂路A1→当週ウッド+ダート戦",
    "吉村圭司": "栗東坂路A2ラップ（2F各12秒台加速）",
    "久保田貴士": "前日美浦坂路追いあり+田辺騎手",
    "森秀行": "A3ラップ（2F各11秒台加速）",
    "大竹正博": "前週土日坂路57秒以下+当週ウッド+芝戦",
    "辻野泰之": "加速ラップ+芝レース",
    "松下武士": "A2/A3ラップ（矢作パターン）+全体54秒以上",
    "牧浦充徳": "A2ラップ+B2ラップ（高回収率）",
    "菊沢隆徳": "美浦坂路加速ラップ（改修後）",
    "石橋守": "栗東坂路A2/A3ラップ（11秒台加速）",
    "竹内正洋": "美浦ウッド5F67秒以下+終い11秒台",
    "加藤士津八": "美浦坂路追い切り（改修後）",
    "野中賢二": "ダート戦+坂路加速ラップ",
    "嘉藤貴行": "前週土日坂路60秒以上→当週ウッド",
    "新谷功一": "坂路51秒以下+減速ラップ（B2/B3）",
    "福永祐一": "栗東坂路加速ラップ（A1/A2中心）",
}


def parse_chok_com_files() -> Dict[str, str]:
    """
    CHOK_COM（CKCM*.DAT）からコメントを読み込み

    Returns:
        {trainer_name: comment, ...} （名前ベース、後でjvn_codeにマッピング）
    """
    chok_com_dir = get_jv_data_root() / "MY_DATA" / "CHOK_COM"
    if not chok_com_dir.exists():
        return {}

    # trainer_id_indexからjvn_code→name マッピングを構築
    index_path = get_target_data_dir() / "trainer_id_index.json"
    jvn_to_name = {}
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        for info in raw.values():
            jvn_code = info.get('jvn_code', '')
            name = info.get('name', '')
            if jvn_code and name:
                jvn_to_name[jvn_code] = name

    comments = {}
    for dat_file in sorted(chok_com_dir.glob("CKCM*.DAT")):
        try:
            with open(dat_file, 'r', encoding='shift_jis', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if len(line) < 6:
                        continue
                    # 先頭5桁がjvn_codeに類似したコード
                    code_part = line[:6].strip()
                    comment_part = line[6:].strip()
                    if comment_part:
                        # 5桁のjvn_codeを試行
                        for jvn_code in [code_part[:5], code_part]:
                            name = jvn_to_name.get(jvn_code)
                            if name:
                                comments[name] = comment_part
                                break
        except Exception:
            pass

    return comments


def compute_stats(records: List[Dict]) -> Dict:
    """レコードリストから統計を計算"""
    n = len(records)
    if n == 0:
        return {'win_rate': 0, 'top3_rate': 0, 'top5_rate': 0, 'avg_finish': 0, 'sample_size': 0}

    wins = sum(1 for r in records if r['finishPosition'] == 1)
    top3 = sum(1 for r in records if r['finishPosition'] <= 3)
    top5 = sum(1 for r in records if r['finishPosition'] <= 5)
    avg_finish = sum(r['finishPosition'] for r in records) / n

    return {
        'win_rate': round(wins / n, 4),
        'top3_rate': round(top3 / n, 4),
        'top5_rate': round(top5 / n, 4),
        'avg_finish': round(avg_finish, 2),
        'sample_size': n,
    }


def get_confidence(sample_size: int) -> str:
    """サンプルサイズから信頼度を判定"""
    if sample_size >= 30:
        return 'high'
    elif sample_size >= 10:
        return 'medium'
    else:
        return 'low'


def get_lap_group(lap_class: str) -> str:
    """ラップ分類をグループ化（SS, S+, S=, A+, A-, B+, ...）→ 先頭文字"""
    if not lap_class:
        return ''
    if lap_class == 'SS':
        return 'SS'
    return lap_class[0] if lap_class else ''


def analyze_trainer(name: str, records: List[Dict]) -> Dict:
    """
    単一調教師のパターン分析

    Returns:
        {
            'overall_stats': {...},
            'best_patterns': [...],
            'all_patterns': {...},
        }
    """
    overall = compute_stats(records)

    # 各次元でグループ化して統計計算
    all_patterns: Dict[str, Dict[str, Any]] = {}

    # 1. finalLap別
    by_final_lap: Dict[str, List[Dict]] = defaultdict(list)
    for r in records:
        lap = r.get('training', {}).get('finalLap', '')
        if lap:
            by_final_lap[lap].append(r)
    all_patterns['by_final_lap'] = {
        k: {**compute_stats(v), 'confidence': get_confidence(len(v))}
        for k, v in sorted(by_final_lap.items())
        if len(v) >= 3
    }

    # 2. finalLocation別
    by_location: Dict[str, List[Dict]] = defaultdict(list)
    for r in records:
        loc = r.get('training', {}).get('finalLocation', '')
        if loc:
            by_location[loc].append(r)
    all_patterns['by_location'] = {
        k: {**compute_stats(v), 'confidence': get_confidence(len(v))}
        for k, v in sorted(by_location.items())
        if len(v) >= 3
    }

    # 3. countLabel別（調教本数）
    by_volume: Dict[str, List[Dict]] = defaultdict(list)
    for r in records:
        vol = r.get('training', {}).get('countLabel', '')
        if vol:
            by_volume[vol].append(r)
    all_patterns['by_volume'] = {
        k: {**compute_stats(v), 'confidence': get_confidence(len(v))}
        for k, v in sorted(by_volume.items())
        if len(v) >= 3
    }

    # 4. timeClass別（好タイム種別）
    by_time_class: Dict[str, List[Dict]] = defaultdict(list)
    for r in records:
        tc = r.get('training', {}).get('timeClass', '')
        if tc:
            by_time_class[tc].append(r)
    all_patterns['by_time_class'] = {
        k: {**compute_stats(v), 'confidence': get_confidence(len(v))}
        for k, v in sorted(by_time_class.items())
        if len(v) >= 3
    }

    # 5. acceleration別
    by_accel: Dict[str, List[Dict]] = defaultdict(list)
    for r in records:
        accel = r.get('training', {}).get('finalAcceleration', '')
        if accel:
            by_accel[accel].append(r)
    all_patterns['by_acceleration'] = {
        k: {**compute_stats(v), 'confidence': get_confidence(len(v))}
        for k, v in sorted(by_accel.items())
        if len(v) >= 3
    }

    # 勝負パターン特定（複合条件）
    best_patterns = identify_best_patterns(records, overall, name)

    return {
        'overall_stats': overall,
        'best_patterns': best_patterns,
        'all_patterns': all_patterns,
    }


def identify_best_patterns(records: List[Dict], overall: Dict, trainer_name: str) -> List[Dict]:
    """
    複合条件での勝負パターンを特定

    top3_rate >= 0.25 AND sample_size >= 8 のパターンを探索し、
    overall_top3_rate との差が大きいものを優先
    """
    patterns = []
    overall_top3 = overall.get('top3_rate', 0)

    # パターン候補を生成
    pattern_defs = [
        # (description, filter_func, conditions_dict)
        ("好タイム+加速ラップ",
         lambda r: r.get('training', {}).get('hasGoodTime') and r.get('training', {}).get('finalAcceleration') == '+',
         {"hasGoodTime": True, "acceleration": "+"}),
        ("SS/S評価",
         lambda r: get_lap_group(r.get('training', {}).get('finalLap', '')) in ('SS', 'S'),
         {"finalLapClassGroup": ["SS", "S+", "S=", "S-"]}),
        ("坂路+加速",
         lambda r: r.get('training', {}).get('finalLocation') == '坂' and r.get('training', {}).get('finalAcceleration') == '+',
         {"finalLocation": "坂", "acceleration": "+"}),
        ("コース+好タイム",
         lambda r: r.get('training', {}).get('finalLocation') == 'コ' and r.get('training', {}).get('finalSpeed'),
         {"finalLocation": "コ", "hasGoodTime": True}),
        ("調教本数多+好タイム",
         lambda r: r.get('training', {}).get('countLabel') == '多' and r.get('training', {}).get('hasGoodTime'),
         {"countLabel": "多", "hasGoodTime": True}),
        ("坂路+好タイム",
         lambda r: r.get('training', {}).get('finalLocation') == '坂' and r.get('training', {}).get('finalSpeed'),
         {"finalLocation": "坂", "hasGoodTime": True}),
        ("坂路+SS/S評価",
         lambda r: r.get('training', {}).get('finalLocation') == '坂' and get_lap_group(r.get('training', {}).get('finalLap', '')) in ('SS', 'S'),
         {"finalLocation": "坂", "finalLapClassGroup": ["SS", "S+", "S="]}),
        ("コース+加速ラップ",
         lambda r: r.get('training', {}).get('finalLocation') == 'コ' and r.get('training', {}).get('finalAcceleration') == '+',
         {"finalLocation": "コ", "acceleration": "+"}),
        ("両方好タイム",
         lambda r: r.get('training', {}).get('timeClass') == '両',
         {"timeClass": "両"}),
        # --- 1週前調教関連 ---
        ("一週前好タイム→最終追切",
         lambda r: r.get('training', {}).get('weekAgoSpeed') == '◎' and r.get('training', {}).get('finalSpeed') != '◎',
         {"weekAgoHasGoodTime": True, "hasGoodTime": False}),
        ("一週前SS/S評価",
         lambda r: get_lap_group(r.get('training', {}).get('weekAgoLap', '')) in ('SS', 'S'),
         {"weekAgoLapClassGroup": ["SS", "S"]}),
        ("一週前坂路+加速",
         lambda r: r.get('training', {}).get('weekAgoLocation') == '坂' and r.get('training', {}).get('weekAgoLap', '').endswith('+'),
         {"weekAgoLocation": "坂", "weekAgoAcceleration": "+"}),
        # --- 土日調教関連 ---
        ("土日好タイム→最終追切",
         lambda r: r.get('training', {}).get('weekendSpeed') == '◎',
         {"weekendHasGoodTime": True}),
        ("土日坂路+加速",
         lambda r: r.get('training', {}).get('weekendLocation') == '坂' and r.get('training', {}).get('weekendLap', '').endswith('+'),
         {"weekendLocation": "坂", "weekendAcceleration": "+"}),
        ("土日SS/S→最終追切",
         lambda r: get_lap_group(r.get('training', {}).get('weekendLap', '')) in ('SS', 'S'),
         {"weekendLapClassGroup": ["SS", "S"]}),
    ]

    for desc, filter_func, conditions in pattern_defs:
        matched = [r for r in records if filter_func(r)]
        if len(matched) < 8:
            continue

        stats = compute_stats(matched)
        if stats['top3_rate'] < 0.25:
            continue

        # overall との差分で重み付け
        lift = stats['top3_rate'] - overall_top3
        if lift < 0.05:
            continue

        # QUICK_REFERENCE のラベルがあればhuman_labelとして付与
        human_label = QUICK_REFERENCE.get(trainer_name, '')

        patterns.append({
            'description': desc,
            'human_label': human_label if human_label else None,
            'conditions': conditions,
            'stats': {
                **stats,
                'confidence': get_confidence(stats['sample_size']),
                'lift': round(lift, 4),
            },
            # ソート用スコア: top3_rate * sqrt(sample_size) * lift
            '_score': stats['top3_rate'] * math.sqrt(stats['sample_size']) * max(lift, 0.01),
        })

    # スコア順でソート、上位3パターン
    patterns.sort(key=lambda p: p['_score'], reverse=True)
    for p in patterns:
        del p['_score']

    return patterns[:3]


def main():
    parser = argparse.ArgumentParser(description='調教師パターン分析')
    parser.add_argument('--input', type=str, default=None,
                        help='入力ファイル（trainer_training_history.json）')
    parser.add_argument('--output', type=str, default=None,
                        help='出力ファイル（trainer_patterns.json）')
    parser.add_argument('--min-records', type=int, default=20,
                        help='最低レコード数（デフォルト: 20）')
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else (get_target_data_dir() / 'trainer_training_history.json')
    output_path = Path(args.output) if args.output else (get_target_data_dir() / 'trainer_patterns.json')

    if not input_path.exists():
        print(f"エラー: 入力ファイルが見つかりません: {input_path}")
        print(f"先に collect_trainer_training_history.py を実行してください。")
        return 1

    print(f"\n{'='*60}")
    print(f"=== 調教師パターン分析 ===")
    print(f"{'='*60}")
    print(f"入力: {input_path}")
    print(f"最低レコード数: {args.min_records}")

    start_time = time.time()

    # 1. 履歴データ読み込み
    print(f"\n[Step 1] 履歴データ読み込み...")
    with open(input_path, 'r', encoding='utf-8') as f:
        history = json.load(f)

    meta = history.get('meta', {})
    trainers_data = history.get('trainers', {})
    print(f"  対象年: {meta.get('years', [])}")
    print(f"  調教師数: {len(trainers_data)}")
    print(f"  総レコード: {meta.get('total_training_records', 0):,}")

    # 2. CHOK_COMコメント読み込み
    print(f"\n[Step 2] CHOK_COMコメント読み込み...")
    chok_comments = parse_chok_com_files()
    print(f"  コメント数: {len(chok_comments)}")

    # 3. パターン分析
    print(f"\n[Step 3] パターン分析...")
    trainers_output = {}
    analyzed = 0
    skipped = 0
    total_patterns_found = 0

    for jvn_code, trainer_data in trainers_data.items():
        records = trainer_data.get('records', [])
        if len(records) < args.min_records:
            skipped += 1
            continue

        name = trainer_data.get('name', '')
        analysis = analyze_trainer(name, records)
        analyzed += 1

        # CHOK_COMコメントをマージ
        comment = chok_comments.get(name, '')
        # trainer_id_indexのcommentも確認
        if not comment:
            comment = ''  # フォールバック

        n_patterns = len(analysis['best_patterns'])
        total_patterns_found += n_patterns

        trainers_output[jvn_code] = {
            'jvn_code': jvn_code,
            'keibabook_ids': trainer_data.get('keibabook_ids', []),
            'name': name,
            'tozai': trainer_data.get('tozai', ''),
            'comment': comment,
            'total_runners': len(records),
            'overall_stats': analysis['overall_stats'],
            'best_patterns': analysis['best_patterns'],
            'all_patterns': analysis['all_patterns'],
        }

    print(f"  分析完了: {analyzed}名 / スキップ: {skipped}名")
    print(f"  勝負パターン検出: {total_patterns_found}件")

    # 4. 出力
    print(f"\n[Step 4] 結果保存...")
    result = {
        'meta': {
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'data_period': f"{meta.get('years', [None])[0]}-01-01 ~ {meta.get('years', [None])[-1]}-12-31",
            'total_trainers': len(trainers_output),
            'total_patterns': total_patterns_found,
            'min_records': args.min_records,
            'source_history': str(input_path.name),
            'version': '1.0',
        },
        'trainers': trainers_output,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    file_size_mb = output_path.stat().st_size / (1024 * 1024)

    print(f"\n{'='*50}")
    print(f"=== 分析結果 ===")
    print(f"  調教師数: {len(trainers_output)}")
    print(f"  勝負パターン: {total_patterns_found}件")
    print(f"  出力: {output_path} ({file_size_mb:.1f} MB)")
    print(f"  処理時間: {elapsed:.1f}秒")

    # QUICK_REFERENCE名のパターン検出状況
    qr_matched = 0
    for jvn_code, t in trainers_output.items():
        if t['name'] in QUICK_REFERENCE and t.get('best_patterns'):
            qr_matched += 1
    print(f"  QUICK_REFERENCE ({len(QUICK_REFERENCE)}名) のうちパターン検出: {qr_matched}名")
    print(f"{'='*50}")

    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教サマリ生成スクリプト

JRA-VAN CK_DATAから調教データを解析し、WebViewer用のtraining_summary.jsonを生成する。

Usage:
    # 単一日付
    python generate_training_summary.py --date 2026-01-25
    
    # 日付範囲
    python generate_training_summary.py --start 2026-01-25 --end 2026-01-26
    
    # 解析対象期間を指定（デフォルト14日）
    python generate_training_summary.py --date 2026-01-25 --days 21
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# 親ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from parse_ck_data import analyze_horse_training, TrainingConfig, CK_DATA_ROOT, get_recent_training_files
from horse_id_mapper import get_horse_name_index

# common.config から SE_DATA パス・KEIBA_DATA_ROOT を取得
sys.path.insert(0, str(Path(__file__).parent.parent))
from common.config import get_jv_se_data_path, get_keiba_data_root


# =============================================================================
# 定数
# =============================================================================

# データルート（KEIBA_DATA_ROOT_DIR に従う）
DATA_ROOT = str(get_keiba_data_root())

# SE_DATA パス
SE_DATA_PATH = get_jv_se_data_path()

# SU_DATA レコード長（555バイト）
SU_RECORD_LEN = 555

# 調教データ解析対象期間（日数）
DEFAULT_DAYS_BACK = 14


# =============================================================================
# ユーティリティ関数
# =============================================================================

def get_date_range(start_date: str, end_date: str) -> List[str]:
    """日付範囲のリストを生成"""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return dates


# =============================================================================
# 前走日付取得（SE_DATA から）
# =============================================================================

def get_previous_race_date(ketto_num: str, current_race_date: str) -> Optional[str]:
    """
    SE_DATA から馬の前走日付を取得
    
    Args:
        ketto_num: 血統登録番号（10桁）
        current_race_date: 今走日付（YYYYMMDD形式）
        
    Returns:
        前走日付（YYYY-MM-DD形式）、なければNone
    """
    if not ketto_num or not SE_DATA_PATH.exists():
        return None
    
    try:
        # 過去3年分のSU_DATAファイルを検索
        current_year = int(current_race_date[:4])
        race_dates = []
        
        for year in range(current_year, current_year - 3, -1):
            year_dir = SE_DATA_PATH / str(year)
            if not year_dir.exists():
                continue
            
            # SU*.DAT ファイルを検索（馬毎成績）
            su_files = sorted(year_dir.glob("SU*.DAT"), reverse=True)
            
            for su_file in su_files:
                try:
                    with open(su_file, 'rb') as f:
                        data = f.read()
                    
                    # レコードを走査
                    offset = 0
                    while offset + SU_RECORD_LEN <= len(data):
                        # 血統登録番号を抽出（オフセット30から10バイト）
                        record_ketto = data[offset+30:offset+40].decode('shift_jis', errors='ignore').strip()
                        
                        if record_ketto == ketto_num:
                            # 開催日を抽出（オフセット2から8バイト）
                            race_date_raw = data[offset+2:offset+10].decode('shift_jis', errors='ignore').strip()
                            if len(race_date_raw) == 8 and race_date_raw.isdigit():
                                # 今走より前の日付のみ収集
                                if race_date_raw < current_race_date:
                                    race_dates.append(race_date_raw)
                        
                        offset += SU_RECORD_LEN
                        
                except Exception:
                    continue
        
        if not race_dates:
            return None
        
        # 最も新しい前走日付を取得
        race_dates.sort(reverse=True)
        prev_date = race_dates[0]
        
        # YYYY-MM-DD形式に変換
        return f"{prev_date[:4]}-{prev_date[4:6]}-{prev_date[6:8]}"
        
    except Exception as e:
        print(f"  [WARN] Failed to get previous race date for {ketto_num}: {e}")
        return None


def load_previous_training_summary(date: str) -> Dict[str, Dict[str, Any]]:
    """
    指定日の training_summary.json を読み込む
    
    Args:
        date: 日付（YYYY-MM-DD形式）
        
    Returns:
        馬名をキーにした調教サマリ辞書
    """
    try:
        year, month, day = date.split('-')
        file_path = Path(DATA_ROOT) / 'races' / year / month / day / 'temp' / 'training_summary.json'
        
        if not file_path.exists():
            return {}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('summaries', {})
        
    except Exception:
        return {}


# 前走調教キャッシュ（日付 -> summaries）
_previous_training_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}


def find_integrated_files(date: str) -> List[Path]:
    """指定日のintegrated_*.jsonファイルを検索
    
    検索対象:
    - {date_dir}/integrated_*.json (直下)
    - {date_dir}/temp/integrated_*.json (tempフォルダ)
    - {date_dir}/{track}/integrated_*.json (競馬場フォルダ)
    """
    year, month, day = date.split('-')
    date_dir = Path(DATA_ROOT) / 'races' / year / month / day
    
    if not date_dir.exists():
        return []
    
    files = []
    
    # 直下を検索
    files.extend(date_dir.glob('integrated_*.json'))
    
    # tempフォルダを検索
    temp_dir = date_dir / 'temp'
    if temp_dir.exists():
        files.extend(temp_dir.glob('integrated_*.json'))
    
    # 競馬場フォルダを検索（サブディレクトリ内）
    for subdir in date_dir.iterdir():
        if subdir.is_dir() and subdir.name != 'temp':
            files.extend(subdir.glob('integrated_*.json'))
    
    return files


def normalize_horse_name(name: str) -> str:
    """
    馬名を正規化（接頭辞を除去）
    
    例:
    - "(外)ロッシニアーナ" → "ロッシニアーナ"
    - "（地）ホクショウマサル" → "ホクショウマサル"
    """
    import re
    if not name:
        return name
    
    # (外), (地), (父), (市), (抽) などを除去（半角・全角両方）
    return re.sub(r'^[\(（\[]外[\)）\]]|^[\(（\[]地[\)）\]]|^[\(（\[]父[\)）\]]|^[\(（\[]市[\)）\]]|^[\(（\[]抽[\)）\]]', '', name).strip()


def extract_horse_ids_from_integrated(file_path: Path) -> List[Dict[str, str]]:
    """integrated_*.jsonから馬IDと馬名を抽出"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        horses = []
        for entry in data.get('entries', []):
            horse_id = entry.get('horse_id', '')
            horse_name = entry.get('horse_name', '')
            
            if horse_id and horse_name:
                horses.append({
                    'horse_id': horse_id,
                    'horse_name': horse_name,
                    'horse_name_normalized': normalize_horse_name(horse_name)
                })
        
        return horses
    except Exception as e:
        print(f"  [ERROR] Failed to read {file_path}: {e}")
        return []


def format_training_detail(record: Optional[Dict]) -> str:
    """調教レコードを詳細文字列に変換"""
    if not record:
        return ""
    
    location = record.get('location', '')
    time_4f = record.get('time_4f', 0)
    lap_1 = record.get('lap_1', 0)
    
    if time_4f and lap_1:
        return f"{location} 4F{time_4f:.1f}-{lap_1:.1f}"
    elif time_4f:
        return f"{location} 4F{time_4f:.1f}"
    return ""


def get_location_short(location: str) -> str:
    """場所を短縮形に変換"""
    if location == '坂路':
        return '坂'
    elif location == 'コース':
        return 'コ'
    return location


def get_speed_label(has_good_time: bool) -> str:
    """好タイムかどうかでラベルを返す"""
    return '◎' if has_good_time else ''


def generate_summary_for_date(date: str, days_back: int = DEFAULT_DAYS_BACK, 
                              horse_name_index: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """指定日の調教サマリを生成
    
    Args:
        date: 日付 (YYYY-MM-DD形式)
        days_back: 調教データ解析対象期間（日数）
        horse_name_index: 馬名→10桁ID のインデックス（外部から渡す場合）
    """
    print(f"\n[{date}] 調教サマリ生成開始...")
    
    # 解析対象期間を計算
    race_date = datetime.strptime(date, '%Y-%m-%d')
    final_start = (race_date - timedelta(days=2)).strftime('%Y%m%d')
    final_end = race_date.strftime('%Y%m%d')
    week_ago_start = (race_date - timedelta(days=9)).strftime('%Y%m%d')
    week_ago_end = (race_date - timedelta(days=5)).strftime('%Y%m%d')
    
    # integrated_*.jsonファイルを検索
    integrated_files = find_integrated_files(date)
    if not integrated_files:
        print(f"  [WARN] No integrated files found for {date}")
        return {}
    
    print(f"  Found {len(integrated_files)} race files")
    
    # 馬名インデックスが渡されていない場合は取得
    if horse_name_index is None:
        print("  Getting horse name index...")
        horse_name_index = get_horse_name_index()
        print(f"  Horse name index: {len(horse_name_index)} entries")
    
    # 全出走馬のIDを収集（馬名ベース）
    all_horses: Dict[str, str] = {}  # horse_name -> jvn_10digit_id
    horses_without_id = []
    
    for file_path in integrated_files:
        horses = extract_horse_ids_from_integrated(file_path)
        for horse in horses:
            horse_name = horse['horse_name']
            horse_name_normalized = horse.get('horse_name_normalized', horse_name)
            
            if horse_name_normalized not in all_horses:
                # 馬名から10桁IDを取得（正規化した馬名で検索）
                jvn_id = horse_name_index.get(horse_name_normalized)
                
                # 正規化名で見つからない場合、元の馬名でも試行
                if not jvn_id:
                    jvn_id = horse_name_index.get(horse_name)
                
                if jvn_id:
                    # 正規化した馬名をキーにして保存（training_summaryのキーと一致させる）
                    all_horses[horse_name_normalized] = jvn_id
                else:
                    horses_without_id.append(horse_name)
    
    print(f"  Total horses: {len(all_horses)} (matched), {len(horses_without_id)} (not found in UM_DATA)")
    
    # 各馬の調教データを解析
    summaries: Dict[str, Dict[str, Any]] = {}
    config = TrainingConfig()
    horses_with_sakamichi = 0  # 坂路レコードが1件以上ある馬の数
    
    for horse_name, jvn_horse_id in all_horses.items():
        try:
            # 調教データを解析（10桁IDを使用）
            training_data = analyze_horse_training(
                horse_id=jvn_horse_id,
                race_date=date.replace('-', ''),
                days_back=days_back
            )
            
            if not training_data:
                continue
            
            # サマリデータを構築
            summary = {
                'horseName': horse_name,
                'kettoNum': jvn_horse_id,
            }
            
            # タイム分類（全体）
            time_rank = ""
            has_good_sakamichi = False
            has_good_course = False
            
            for record in training_data.get('all_records', []):
                if record.get('is_good_time'):
                    if record.get('location') == '坂路':
                        has_good_sakamichi = True
                    elif record.get('location') == 'コース':
                        has_good_course = True
            
            if has_good_sakamichi and has_good_course:
                time_rank = "両"
            elif has_good_sakamichi:
                time_rank = "坂"
            elif has_good_course:
                time_rank = "コ"
            
            summary['timeRank'] = time_rank
            
            # 最終追切: 当週の水曜か木曜
            final = training_data.get('final')
            if final:
                summary['finalLocation'] = get_location_short(final.get('location', ''))
                summary['finalSpeed'] = get_speed_label(final.get('is_good_time', False))
                summary['finalLap'] = final.get('upgraded_lap_class', final.get('lap_class', ''))
                summary['finalTime4F'] = final.get('time_4f', 0)
                summary['finalLap1'] = final.get('lap_1', 0)
            else:
                summary['finalLocation'] = ''
                summary['finalSpeed'] = ''
                summary['finalLap'] = ''
                summary['finalTime4F'] = 0
                summary['finalLap1'] = 0
            
            # 土日追切: 前週の土曜か日曜（両方あればタイムが早いほう）
            weekend = training_data.get('weekend')
            if weekend:
                summary['weekendLocation'] = get_location_short(weekend.get('location', ''))
                summary['weekendSpeed'] = get_speed_label(weekend.get('is_good_time', False))
                summary['weekendLap'] = weekend.get('upgraded_lap_class', weekend.get('lap_class', ''))
                summary['weekendTime4F'] = weekend.get('time_4f', 0)
                summary['weekendLap1'] = weekend.get('lap_1', 0)
            else:
                summary['weekendLocation'] = ''
                summary['weekendSpeed'] = ''
                summary['weekendLap'] = ''
                summary['weekendTime4F'] = 0
                summary['weekendLap1'] = 0
            
            # 一週前追切: 前週の水曜か木曜
            week_ago = training_data.get('week_ago')
            if week_ago:
                summary['weekAgoLocation'] = get_location_short(week_ago.get('location', ''))
                summary['weekAgoSpeed'] = get_speed_label(week_ago.get('is_good_time', False))
                summary['weekAgoLap'] = week_ago.get('upgraded_lap_class', week_ago.get('lap_class', ''))
                summary['weekAgoTime4F'] = week_ago.get('time_4f', 0)
                summary['weekAgoLap1'] = week_ago.get('lap_1', 0)
            else:
                summary['weekAgoLocation'] = ''
                summary['weekAgoSpeed'] = ''
                summary['weekAgoLap'] = ''
                summary['weekAgoTime4F'] = 0
                summary['weekAgoLap1'] = 0
            
            # ラップ分類（互換性のため残す）
            summary['lapRank'] = summary.get('finalLap', '')
            
            # 調教詳細: 最終 / 土日 / 1週前
            details = []
            if final:
                detail = format_training_detail(final)
                if detail:
                    details.append(f"最終:{detail}")
            if weekend:
                detail = format_training_detail(weekend)
                if detail:
                    details.append(f"土日:{detail}")
            if week_ago:
                detail = format_training_detail(week_ago)
                if detail:
                    details.append(f"1週前:{detail}")
            
            summary['detail'] = " / ".join(details) if details else ""
            
            # 前走調教情報を追加
            summary['previousRaceDate'] = ''
            summary['previousDetail'] = ''
            summary['previousLapRank'] = ''
            summary['previousFinalSpeed'] = ''
            
            # 坂路レコードの有無を集計（坂路/コース判定の診断用）
            if training_data.get('n_sakamichi', 0) > 0:
                horses_with_sakamichi += 1
            
            # 馬名をキーにして保存
            summaries[horse_name] = summary
            
        except Exception as e:
            print(f"  [ERROR] Failed to analyze {horse_name} ({jvn_horse_id}): {e}")
    
    print(f"  Generated {len(summaries)} summaries")
    print(f"  坂路レコードあり: {horses_with_sakamichi} 頭 / コースのみ: {len(summaries) - horses_with_sakamichi} 頭")
    
    # 前走調教情報を追加
    # NOTE: SE_DATAスキャンは非常に遅いため一時的に無効化
    # 馬ページ（horses-v2）で調教履歴が確認可能
    # 将来的にはSU*.IDXインデックスを使用した高速検索を実装予定
    print("  前走調教情報: スキップ（SE_DATAスキャン無効化中）")
    
    return summaries


def save_training_summary(date: str, summaries: Dict[str, Dict[str, Any]]) -> bool:
    """調教サマリをJSONファイルに保存"""
    year, month, day = date.split('-')
    output_dir = Path(DATA_ROOT) / 'races' / year / month / day / 'temp'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'training_summary.json'
    
    # メタデータを追加
    race_date = datetime.strptime(date, '%Y-%m-%d')
    data = {
        'meta': {
            'date': date,
            'created_at': datetime.now().isoformat(),
            'ranges': {
                'final': '当週の水曜か木曜',
                'weekend': '前週の土曜か日曜（両方あればタイムが早いほう）',
                'weekAgo': '前週の水曜か木曜',
            },
            'count': len(summaries)
        },
        'summaries': summaries
    }
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"  Saved: {output_file}")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to save {output_file}: {e}")
        return False


# =============================================================================
# メイン処理
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='調教サマリ生成')
    parser.add_argument('--date', type=str, help='対象日（YYYY-MM-DD形式）')
    parser.add_argument('--start', type=str, help='開始日（YYYY-MM-DD形式）')
    parser.add_argument('--end', type=str, help='終了日（YYYY-MM-DD形式）')
    parser.add_argument('--days', type=int, default=DEFAULT_DAYS_BACK,
                        help=f'調教データ解析対象期間（デフォルト: {DEFAULT_DAYS_BACK}日）')
    
    args = parser.parse_args()
    
    # 日付リストを構築
    if args.start and args.end:
        dates = get_date_range(args.start, args.end)
        print(f"=== 調教サマリ生成 ({args.start} ~ {args.end}) ===")
    elif args.date:
        dates = [args.date]
        print(f"=== 調教サマリ生成 ({args.date}) ===")
    else:
        print("Error: --date または --start/--end を指定してください")
        sys.exit(1)
    
    print(f"DATA_ROOT: {DATA_ROOT}")
    jv_root = os.environ.get('JV_DATA_ROOT_DIR', '(未設定→C:/TFJV)')
    print(f"JV_DATA_ROOT_DIR: {jv_root}")
    print(f"CK_DATA参照先: {CK_DATA_ROOT}")
    # 1日分のCK_DATAファイル数（HC/WC）を表示
    if dates:
        race_date_ymd = dates[0].replace('-', '')
        ck_files = get_recent_training_files(race_date_ymd, args.days)
        hc_n = sum(1 for p in ck_files if p.name.upper().startswith('HC'))
        wc_n = sum(1 for p in ck_files if p.name.upper().startswith('WC') or p.name.upper().startswith('WD'))
        print(f"CK_DATAファイル: {len(ck_files)} 件 (HC={hc_n}, WC/WD={wc_n})")
    print(f"対象日数: {len(dates)}")
    print(f"解析対象期間: {args.days}日")
    
    # 馬名インデックスを取得（キャッシュがあれば使用）
    print("\n馬名インデックスを取得中...")
    horse_name_index = get_horse_name_index()
    print(f"馬名インデックス: {len(horse_name_index)} 頭")
    
    # 各日付を処理
    success_count = 0
    for date in dates:
        summaries = generate_summary_for_date(date, args.days, horse_name_index)
        if summaries:
            if save_training_summary(date, summaries):
                success_count += 1
        else:
            print(f"  [SKIP] No data for {date}")
    
    print(f"\n=== 完了: {success_count}/{len(dates)} 日 ===")


if __name__ == '__main__':
    main()

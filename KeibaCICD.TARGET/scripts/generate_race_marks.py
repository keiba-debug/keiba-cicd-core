# -*- coding: utf-8 -*-
"""
レース展開評価印作成スクリプト
PCI分析に基づき、展開と結果から注目馬を抽出

印の定義:
  H+ : ハイペースで先行して好走（実力証明）
  S+ : スローペースで差して好走（実力証明）
  NC : 展開不利でノーカウント
"""

import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# pci_standards.json のパス
PCI_STANDARDS_PATH = Path(__file__).parent.parent / "data" / "pci_standards.json"

# デフォルト設定（距離別の好走マージンなど）
DEFAULT_GOOD_RUN_MARGIN = {
    # 距離 -> 好走判定の着差（秒）
    "1000": 0.3,
    "1150": 0.3,
    "1200": 0.4,
    "1400": 0.4,
    "1600": 0.5,
    "1700": 0.5,
    "1800": 0.5,
    "1900": 0.5,
    "2000": 0.6,
    "2100": 0.6,
    "2200": 0.6,
    "2400": 0.7,
    "2500": 0.7,
    "2600": 0.8,
    "3000": 0.8,
    "3200": 0.8,
    "3400": 0.9,
    "3600": 1.0,
}
DEFAULT_PCI_DIFF_THRESHOLD = 3.0  # 先行/差し判定のPCI差


def load_pci_standards() -> dict:
    """pci_standards.jsonを読み込む"""
    if not PCI_STANDARDS_PATH.exists():
        print(f"警告: 基準値ファイルが見つかりません: {PCI_STANDARDS_PATH}")
        return {}
    
    with open(PCI_STANDARDS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def classify_class_group(class_name: str) -> str:
    """クラス名からクラスグループを判定"""
    if not class_name:
        return "中級"  # デフォルト
    
    if '新馬' in class_name or '未勝利' in class_name:
        return "下級"
    elif '1勝' in class_name or '2勝' in class_name or '3勝' in class_name:
        return "中級"
    elif 'OP' in class_name or 'オープン' in class_name or 'L' in class_name or 'G' in class_name:
        return "上級"
    else:
        return "中級"  # その他は中級扱い


def get_course_standards(track: str, surface: str, distance: str, class_group: str = "全体") -> dict:
    """コース・クラス別の基準値を取得"""
    pci_data = load_pci_standards()
    
    # JSONから取得
    tracks = pci_data.get("tracks", {})
    track_data = tracks.get(track, {})
    surface_data = track_data.get(surface, {})
    distance_data = surface_data.get(distance, {})
    
    if not distance_data:
        return None
    
    # クラス別の基準値を取得（なければ全体にフォールバック）
    class_data = distance_data.get(class_group)
    if not class_data or class_data is None:
        class_data = distance_data.get("全体")
    
    # 値がnullまたは未設定の場合
    if not class_data or class_data.get("h_threshold") is None:
        return None
    
    # 好走マージンはデフォルト値から取得
    good_run_margin = DEFAULT_GOOD_RUN_MARGIN.get(distance, 0.5)
    
    return {
        "pci_standard": class_data.get("standard"),
        "h_threshold": class_data.get("h_threshold"),
        "s_threshold": class_data.get("s_threshold"),
        "good_run_margin": good_run_margin,
        "pci_diff_threshold": DEFAULT_PCI_DIFF_THRESHOLD,
        "sample_count": class_data.get("sample_count", 0),
        "class_group": class_group
    }


def parse_time_to_seconds(time_str: str) -> float:
    """走破タイムを秒に変換 (例: 1.10.3 -> 70.3)"""
    if not time_str:
        return None
    try:
        parts = time_str.replace(' ', '').split('.')
        if len(parts) == 3:
            minutes = int(parts[0])
            seconds = int(parts[1])
            tenths = int(parts[2])
            return minutes * 60 + seconds + tenths / 10
        elif len(parts) == 2:
            seconds = int(parts[0])
            tenths = int(parts[1])
            return seconds + tenths / 10
    except:
        pass
    return None


def get_race_id(full_id: str) -> str:
    """馬番を除いたレースIDを取得（末尾2桁を除去）"""
    if len(full_id) >= 2:
        return full_id[:-2]
    return full_id


def detect_course_from_filename(csv_path: str) -> tuple:
    """ファイル名からコース情報を検出"""
    filename = Path(csv_path).stem.lower()
    
    # 競馬場検出
    track = "中山"  # デフォルト
    for t in ["東京", "中山", "阪神", "京都", "中京", "新潟", "小倉", "福島", "札幌", "函館"]:
        if t in filename:
            track = t
            break
    
    # コース（芝/ダート）検出
    if "芝" in filename or "turf" in filename:
        surface = "芝"
    else:
        surface = "ダート"  # デフォルト
    
    # 距離検出
    import re
    distance_match = re.search(r'(\d{3,4})', filename)
    distance = distance_match.group(1) if distance_match else "1200"
    
    return track, surface, distance


def analyze_races(csv_path: str, track: str = None, surface: str = None, distance: str = None):
    """レースデータを分析して印を付与"""
    
    # ファイル名から自動検出（引数未指定時）
    if track is None or surface is None or distance is None:
        detected_track, detected_surface, detected_distance = detect_course_from_filename(csv_path)
        track = track or detected_track
        surface = surface or detected_surface
        distance = distance or detected_distance
        print(f"コース検出: {track} {surface} {distance}m")
    
    # 基準値の存在確認（全体で少なくとも1つあるか）
    test_standards = get_course_standards(track, surface, distance, "全体")
    if not test_standards:
        print(f"基準値が見つかりません: {track} {surface} {distance}m")
        print(f"pci_standards.jsonに設定を追加してください")
        return []
    
    print(f"クラス別基準値を使用: {track} {surface} {distance}m")
    
    # エンコーディング検出
    for enc in ['utf-8-sig', 'utf-8', 'cp932']:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                if headers and any('レース' in h or 'PCI' in h for h in headers):
                    encoding = enc
                    break
        except UnicodeDecodeError:
            continue
    else:
        encoding = 'cp932'
    
    # データ読み込み（レース単位でグループ化）
    races = defaultdict(list)
    
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            race_id_col = 'レースID(新)' if 'レースID(新)' in row else list(row.keys())[0]
            race_id_full = row.get(race_id_col, '')
            race_id = get_race_id(race_id_full)
            
            # 必要データ抽出
            try:
                pci = float(row.get('PCI', ''))
            except:
                continue
            
            try:
                pci3 = float(row.get('PCI3', ''))
            except:
                continue
            
            try:
                rpci = float(row.get('RPCI', ''))
            except:
                rpci = pci3  # RPCIがなければPCI3を使用
            
            # 着順
            finish_str = row.get('着順', '').strip()
            try:
                # 全角数字を半角に変換
                finish_str = finish_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                finish = int(finish_str)
            except:
                continue
            
            # 走破タイム
            time_str = row.get('走破タイム', '')
            time_seconds = parse_time_to_seconds(time_str)
            
            races[race_id].append({
                'race_id_full': race_id_full,
                'race_id': race_id,
                'date': row.get('日付', ''),
                'race_name': row.get('レース名', ''),
                'class_name': row.get('クラス名', ''),
                'horse_name': row.get('馬名S', ''),
                'finish': finish,
                'time_seconds': time_seconds,
                'pci': pci,
                'pci3': pci3,
                'rpci': rpci,
                'tactic': row.get('決め手', ''),
                'jockey': row.get('騎手', ''),
                'popularity': row.get('人気', ''),
                'row': row  # 元データ保持
            })
    
    # 各レースを処理して印を付与
    results = []
    
    for race_id, horses in races.items():
        if len(horses) < 3:
            continue
        
        # 勝ち馬のタイムを取得
        sorted_horses = sorted(horses, key=lambda x: x['finish'])
        winner = sorted_horses[0]
        winner_time = winner['time_seconds']
        
        # クラスグループを判定（レースの最初の馬から取得）
        class_name = horses[0].get('class_name', '')
        class_group = classify_class_group(class_name)
        
        # クラス別の基準値を取得
        standards = get_course_standards(track, surface, distance, class_group)
        if not standards:
            # クラス別がなければ全体を使用
            standards = get_course_standards(track, surface, distance, "全体")
        if not standards:
            continue
        
        h_threshold = standards["h_threshold"]
        s_threshold = standards["s_threshold"]
        good_run_margin = standards["good_run_margin"]
        pci_diff_threshold = standards["pci_diff_threshold"]
        
        # レースのペース判定
        pci3 = horses[0]['pci3']
        rpci = horses[0]['rpci']
        
        if pci3 < h_threshold:
            pace = 'H'  # ハイペース
        elif pci3 > s_threshold:
            pace = 'S'  # スローペース
        else:
            pace = 'M'  # 平均ペース
        
        for horse in horses:
            # 着差計算
            if winner_time and horse['time_seconds']:
                margin = horse['time_seconds'] - winner_time
            else:
                margin = None
            
            # PCI差（参考値）
            pci_diff = horse['pci'] - rpci
            
            # 位置取り判定（決め手を優先、なければPCI差）
            tactic = horse['tactic'].strip() if horse['tactic'] else ''
            
            if tactic in ['逃げ', '先行']:
                style = 'F'  # 先行（Front）
            elif tactic in ['差し', '追込', '後方']:
                style = 'C'  # 差し（Closer）
            elif tactic:
                style = 'M'  # その他（中団など）
            else:
                # 決め手がない場合はPCI差で判定
                if pci_diff >= pci_diff_threshold:
                    style = 'F'
                elif pci_diff <= -pci_diff_threshold:
                    style = 'C'
                else:
                    style = 'M'
            
            # 好走判定
            is_good_run = margin is not None and margin <= good_run_margin
            is_bad_run = margin is not None and margin > good_run_margin
            
            # 印の付与
            mark = ''
            
            if pace == 'H' and style == 'F' and is_good_run:
                # ハイペースで先行して好走 → 実力証明
                mark = 'H+'
            elif pace == 'S' and style == 'C' and is_good_run:
                # スローペースで差して好走 → 実力証明
                mark = 'S+'
            elif pace == 'H' and style == 'F' and is_bad_run:
                # ハイペースで先行して凡走 → ノーカウント
                mark = 'NC'
            elif pace == 'S' and style == 'C' and is_bad_run:
                # スローペースで差して凡走 → ノーカウント
                mark = 'NC'
            
            results.append({
                'race_id_full': horse['race_id_full'],
                'race_id': horse['race_id'],
                'date': horse['date'],
                'race_name': horse['race_name'],
                'class_group': class_group,
                'horse_name': horse['horse_name'],
                'finish': horse['finish'],
                'margin': margin,
                'pci': horse['pci'],
                'pci3': pci3,
                'rpci': rpci,
                'pci_diff': pci_diff,
                'h_threshold': h_threshold,
                's_threshold': s_threshold,
                'pace': pace,
                'style': style,
                'tactic': horse['tactic'],
                'mark': mark,
                'jockey': horse['jockey'],
                'popularity': horse['popularity']
            })
    
    return results


def output_csv(results: list, output_path: str, marks_only: bool = True):
    """結果をCSVに出力（レースID,印 形式）"""
    
    # 印がある馬のみフィルタ
    if marks_only:
        filtered = [r for r in results if r['mark']]
    else:
        filtered = results
    
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        for r in filtered:
            # レースID,印 形式（ヘッダーなし）
            f.write(f"{r['race_id_full']},{r['mark']}\n")
    
    print(f"CSV出力完了: {output_path}")
    print(f"  出力件数: {len(filtered)}")
    print(f"  H+ (ハイペース実力証明): {sum(1 for r in filtered if r['mark'] == 'H+')}")
    print(f"  S+ (スロー実力証明): {sum(1 for r in filtered if r['mark'] == 'S+')}")
    print(f"  NC (ノーカウント): {sum(1 for r in filtered if r['mark'] == 'NC')}")


def output_clipboard(results: list, marks_only: bool = True):
    """結果をクリップボードに出力"""
    
    if marks_only:
        # 印がある馬のみ
        filtered = [r for r in results if r['mark']]
    else:
        filtered = results
    
    lines = []
    for r in filtered:
        # レースID(新),印 形式
        lines.append(f"{r['race_id_full']},{r['mark']}")
    
    text = '\n'.join(lines)
    
    # クリップボードにコピー
    try:
        process = subprocess.Popen(
            ['clip'],
            stdin=subprocess.PIPE,
            shell=True
        )
        process.communicate(text.encode('cp932'))
        print(f"クリップボードにコピーしました（{len(filtered)}件）")
    except Exception as e:
        print(f"クリップボードへのコピーに失敗: {e}")
        print("以下のデータをコピーしてください:")
        print(text)


def output_summary(results: list):
    """サマリーを出力"""
    
    print("\n" + "=" * 60)
    print("レース展開評価 サマリー")
    print("=" * 60)
    
    # 印別集計
    marks = defaultdict(list)
    for r in results:
        if r['mark']:
            marks[r['mark']].append(r)
    
    for mark, horses in sorted(marks.items()):
        print(f"\n■ {mark} ({len(horses)}頭)")
        print("-" * 40)
        for h in horses[:10]:  # 最大10頭表示
            print(f"  {h['horse_name']:<12} {h['date']} {h['race_name']}")
        if len(horses) > 10:
            print(f"  ... 他 {len(horses) - 10}頭")


def list_csv_files(directory: str = "Y:/TXT") -> list:
    """ディレクトリ内のCSVファイル一覧を取得"""
    dir_path = Path(directory)
    if dir_path.exists():
        return sorted(dir_path.glob("*.csv"))
    return []


def find_input_file(args_input: str = None, args_list: bool = False, args_index: int = None) -> str:
    """入力ファイルを検索・選択"""
    
    default_dir = "Y:/TXT"
    
    # --list オプション: ファイル一覧表示
    if args_list:
        files = list_csv_files(default_dir)
        print(f"\n{default_dir} 内のCSVファイル:")
        print("-" * 50)
        for i, f in enumerate(files):
            print(f"  [{i}] {f.name}")
        print("-" * 50)
        print("使用例: python generate_race_marks.py --index 0 --clip")
        return None
    
    # --index オプション: インデックスで指定
    if args_index is not None:
        files = list_csv_files(default_dir)
        if 0 <= args_index < len(files):
            return str(files[args_index])
        else:
            print(f"エラー: インデックス {args_index} は範囲外です（0-{len(files)-1}）")
            return None
    
    # -i オプション: パスまたはパターンで指定
    if args_input:
        input_path = Path(args_input)
        
        # 直接パスが存在する場合
        if input_path.exists():
            return str(input_path)
        
        # ワイルドカードパターン
        if '*' in args_input:
            matches = glob.glob(args_input)
            if matches:
                return matches[0]
        
        # ディレクトリ内でキーワード検索
        base_dir = input_path.parent if input_path.parent.exists() else Path(default_dir)
        keyword = input_path.stem.lower()
        
        files = list_csv_files(str(base_dir))
        matches = [f for f in files if keyword in f.stem.lower()]
        
        if matches:
            return str(matches[0])
        
        print(f"ファイルが見つかりません: {args_input}")
        return None
    
    # デフォルト: 中山ダート1200（PCIなしを優先）
    files = list_csv_files(default_dir)
    matches_1200 = [f for f in files if '1200' in f.stem]
    non_pci = [f for f in matches_1200 if 'PCI' not in f.stem]
    
    if non_pci:
        return str(non_pci[0])
    elif matches_1200:
        return str(matches_1200[0])
    elif files:
        return str(files[0])
    
    print("ファイルが見つかりません")
    return None


if __name__ == '__main__':
    import argparse
    import glob
    
    parser = argparse.ArgumentParser(
        description='レース展開評価印作成スクリプト',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # ファイル一覧を表示
  python generate_race_marks.py --list
  
  # インデックスで指定して実行
  python generate_race_marks.py --index 0 -o result.csv --clip
  
  # ファイルパスを直接指定
  python generate_race_marks.py -i "Y:/TXT/data.csv" -o "Y:/_temp/result.csv" --clip
  
  # キーワードで検索
  python generate_race_marks.py -i "1200" --clip --summary
'''
    )
    
    # 入力ファイル指定
    input_group = parser.add_argument_group('入力ファイル指定')
    input_group.add_argument('-i', '--input', help='入力CSVファイル（パス、パターン、キーワード）')
    input_group.add_argument('--list', action='store_true', help='利用可能なCSVファイル一覧を表示')
    input_group.add_argument('--index', type=int, help='ファイル一覧のインデックス番号で指定')
    
    # 出力オプション
    output_group = parser.add_argument_group('出力オプション')
    output_group.add_argument('-o', '--output', help='出力CSVファイルパス')
    output_group.add_argument('--clip', action='store_true', help='印付き馬をクリップボードに出力')
    output_group.add_argument('--clip-all', action='store_true', help='全馬をクリップボードに出力')
    output_group.add_argument('--summary', action='store_true', help='サマリーを表示')
    output_group.add_argument('--no-csv', action='store_true', help='CSV出力をスキップ')
    
    args = parser.parse_args()
    
    # 入力ファイル検索
    input_path = find_input_file(args.input, args.list, args.index)
    
    if input_path is None:
        sys.exit(0 if args.list else 1)
    
    print(f"入力ファイル: {input_path}")
    
    # 分析実行
    results = analyze_races(input_path)
    
    if not results:
        print("分析結果がありません")
        sys.exit(1)
    
    # CSV出力
    if not args.no_csv:
        if args.output:
            output_csv(results, args.output)
        else:
            # デフォルト出力先
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"Y:/_temp/race_marks_{timestamp}.csv"
            output_csv(results, output_path)
    
    # クリップボード出力
    if args.clip:
        output_clipboard(results, marks_only=True)
    elif args.clip_all:
        output_clipboard(results, marks_only=False)
    
    # サマリー表示
    if args.summary:
        output_summary(results)

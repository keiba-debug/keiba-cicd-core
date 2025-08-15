"""週末レース確認スクリプト（改良版）
直近土日の9R〜12Rを表示
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

def find_weekend_dates() -> List[str]:
    """直近の土日の日付を取得（YYYYMMDD形式）"""
    today = datetime.now()
    
    # 今日の曜日を取得（0=月曜、6=日曜）
    weekday = today.weekday()
    
    # 直近の土曜日を計算
    if weekday == 5:  # 土曜日
        saturday = today
    elif weekday == 6:  # 日曜日
        saturday = today - timedelta(days=1)
    else:  # 平日
        days_until_saturday = (5 - weekday) % 7
        if days_until_saturday == 0:  # 今日が土曜を過ぎている場合
            days_until_saturday = 7
        saturday = today + timedelta(days=days_until_saturday)
    
    sunday = saturday + timedelta(days=1)
    
    # 過去の土日も候補に含める（データがない場合に備えて）
    last_saturday = saturday - timedelta(days=7)
    last_sunday = sunday - timedelta(days=7)
    
    dates = [
        saturday.strftime('%Y%m%d'),
        sunday.strftime('%Y%m%d'),
        last_saturday.strftime('%Y%m%d'),
        last_sunday.strftime('%Y%m%d')
    ]
    
    return dates

def check_data_exists(date_str: str) -> bool:
    """指定日のデータが存在するか確認"""
    nittei_file = Path(f"Z:/KEIBA-CICD/data/temp/nittei_{date_str}.json")
    race_ids_file = Path(f"Z:/KEIBA-CICD/data/race_ids/{date_str}_info.json")
    return nittei_file.exists() or race_ids_file.exists()

def load_race_data(date_str: str) -> Optional[Dict]:
    """レースデータを読み込み"""
    # まずtempフォルダから探す
    nittei_file = Path(f"Z:/KEIBA-CICD/data/temp/nittei_{date_str}.json")
    if nittei_file.exists():
        with open(nittei_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # race_idsフォルダから探す
    race_ids_file = Path(f"Z:/KEIBA-CICD/data/race_ids/{date_str}_info.json")
    if race_ids_file.exists():
        with open(race_ids_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # race_ids形式の場合、データ構造を変換
            if 'races' in data:
                return {
                    'date': date_str,
                    'kaisai_data': data.get('races', {}),
                    'total_races': data.get('total_races', 0),
                    'kaisai_count': data.get('kaisai_count', 0)
                }
    
    return None

def format_date(date_str: str) -> str:
    """日付を読みやすい形式に変換"""
    year = date_str[:4]
    month = date_str[4:6]
    day = date_str[6:8]
    
    date_obj = datetime.strptime(date_str, '%Y%m%d')
    weekday = ['月', '火', '水', '木', '金', '土', '日'][date_obj.weekday()]
    
    return f"{year}/{month}/{day}({weekday})"

def display_main_races(date_str: str, data: Dict):
    """9R〜12Rのレース情報を表示"""
    formatted_date = format_date(date_str)
    
    print("=" * 70)
    print(f"[DATE] {formatted_date} のメインレース（9R〜12R）")
    print("=" * 70)
    
    all_races = []
    graded_races = []
    
    for kaisai_name, races in data.get('kaisai_data', {}).items():
        # 開催場所から競馬場名を抽出
        if '札幌' in kaisai_name:
            venue = '札幌'
        elif '新潟' in kaisai_name:
            venue = '新潟'
        elif '中京' in kaisai_name:
            venue = '中京'
        elif '東京' in kaisai_name:
            venue = '東京'
        elif '中山' in kaisai_name:
            venue = '中山'
        elif '阪神' in kaisai_name:
            venue = '阪神'
        elif '京都' in kaisai_name:
            venue = '京都'
        elif '福島' in kaisai_name:
            venue = '福島'
        elif '小倉' in kaisai_name:
            venue = '小倉'
        else:
            venue = kaisai_name
        
        print(f"\n【{kaisai_name}】")
        
        for race in races:
            race_no = race.get('race_no', '')
            # 9R〜12Rのみ表示
            if race_no in ['9R', '10R', '11R', '12R']:
                race_name = race.get('race_name', '')
                course = race.get('course', '')
                race_id = race.get('race_id', '')
                
                # 重賞判定
                is_graded = False
                grade = ""
                if 'Ｇ１' in race_name or 'G1' in race_name:
                    grade = "G1"
                    is_graded = True
                elif 'Ｇ２' in race_name or 'G2' in race_name:
                    grade = "G2"
                    is_graded = True
                elif 'Ｇ３' in race_name or 'G3' in race_name:
                    grade = "G3"
                    is_graded = True
                
                # 表示
                marker = "  [*]" if is_graded else "     "
                grade_str = f"({grade})" if grade else ""
                print(f"{marker} {race_no}: {race_name} {grade_str}")
                print(f"       コース: {course}")
                print(f"       レースID: {race_id}")
                
                # リストに追加
                race_info = {
                    'date': date_str,
                    'venue': venue,
                    'kaisai': kaisai_name,
                    'race_no': race_no,
                    'race_name': race_name,
                    'race_id': race_id,
                    'course': course,
                    'is_graded': is_graded,
                    'grade': grade
                }
                all_races.append(race_info)
                if is_graded:
                    graded_races.append(race_info)
    
    return all_races, graded_races

def main():
    """メイン処理"""
    print("\n" + "=" * 70)
    print("週末レース確認ツール - 9R〜12R表示")
    print("=" * 70)
    
    # 直近の土日を探す
    weekend_dates = find_weekend_dates()
    
    available_dates = []
    for date_str in weekend_dates:
        if check_data_exists(date_str):
            available_dates.append(date_str)
    
    if not available_dates:
        print("\n[ERROR] レースデータが見つかりません")
        print("データ取得を実行してください:")
        print(f"python -m src.fast_batch_cli schedule --start-date {weekend_dates[0][:4]}/{weekend_dates[0][4:6]}/{weekend_dates[0][6:8]}")
        return
    
    # 直近2日分を表示（土日）
    display_count = min(2, len(available_dates))
    all_graded_races = []
    
    for date_str in available_dates[:display_count]:
        data = load_race_data(date_str)
        if data:
            all_races, graded_races = display_main_races(date_str, data)
            all_graded_races.extend(graded_races)
    
    # 重賞レースのサマリー
    if all_graded_races:
        print("\n" + "=" * 70)
        print("[GRADED] 重賞レース一覧")
        print("=" * 70)
        
        for race in all_graded_races:
            formatted_date = format_date(race['date'])
            print(f"\n[{race['grade']}] {race['venue']} {race['race_no']}: {race['race_name']}")
            print(f"  日付: {formatted_date}")
            print(f"  コース: {race['course']}")
            print(f"  レースID: {race['race_id']}")
            print(f"  コマンド: python src/markdown_cli_enhanced.py --race-id {race['race_id']} --organized")
    
    # 統計情報
    print("\n" + "=" * 70)
    print("[SUMMARY] 統計情報")
    print("=" * 70)
    print(f"対象日: {', '.join([format_date(d) for d in available_dates[:display_count]])}")
    print(f"重賞レース数: {len(all_graded_races)}")
    
    # データ取得コマンドの提案
    if available_dates[:display_count]:
        print("\n" + "=" * 70)
        print("[COMMAND] データ取得・MD生成コマンド")
        print("=" * 70)
        
        for date_str in available_dates[:display_count]:
            date_formatted = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
            print(f"\n# {format_date(date_str)}のデータ処理")
            print(f"python -m src.fast_batch_cli full --start {date_formatted} --delay 0.5")
            print(f"python -m src.integrator_cli batch --date {date_formatted}")
            print(f"python -m src.markdown_cli batch --date {date_formatted} --organized")


if __name__ == "__main__":
    main()
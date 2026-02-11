#!/usr/bin/env python3
"""
競馬データ分析ツール

収集された競馬データの分析とレポート生成を行います。
"""

import json
import pandas as pd
from pathlib import Path
import argparse
from datetime import datetime, timedelta
import sys

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Keibabookパッケージのパスを追加
keibabook_src = project_root / "KeibaCICD.keibabook" / "src"
sys.path.insert(0, str(keibabook_src))

from utils.logger import setup_logger


class DataAnalyzer:
    """競馬データ分析クラス"""
    
    def __init__(self, data_dir: str = "data/keibabook/seiseki"):
        """
        初期化
        
        Args:
            data_dir: データディレクトリのパス
        """
        self.data_dir = Path(data_dir)
        self.logger = setup_logger("data_analyzer", level="INFO")
        
    def load_race_data(self, race_id: str = None, date_range: tuple = None) -> pd.DataFrame:
        """
        レースデータを読み込む
        
        Args:
            race_id: 特定のレースID
            date_range: 日付範囲 (start_date, end_date)
            
        Returns:
            pd.DataFrame: 統合されたレースデータ
        """
        all_data = []
        
        if race_id:
            # 特定のレースのみ
            file_path = self.data_dir / f"seiseki_{race_id}.json"
            if file_path.exists():
                data = self._load_json_file(file_path)
                if data:
                    all_data.append(data)
        else:
            # 全てまたは日付範囲のファイルを読み込み
            json_files = list(self.data_dir.glob("seiseki_*.json"))
            self.logger.info(f"Found {len(json_files)} data files")
            
            for file_path in json_files:
                if date_range:
                    # ファイル名から日付を抽出して範囲チェック
                    date_str = file_path.stem.split('_')[1][:8]  # seiseki_202502041211.json -> 20250204
                    try:
                        file_date = datetime.strptime(date_str, '%Y%m%d').date()
                        start_date, end_date = date_range
                        if not (start_date <= file_date <= end_date):
                            continue
                    except ValueError:
                        continue
                
                data = self._load_json_file(file_path)
                if data:
                    all_data.append(data)
        
        if not all_data:
            self.logger.warning("No data found")
            return pd.DataFrame()
        
        # DataFrameに変換
        df = self._convert_to_dataframe(all_data)
        self.logger.info(f"Loaded {len(df)} race records")
        return df
    
    def _load_json_file(self, file_path: Path) -> dict:
        """JSONファイルを読み込む"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def _convert_to_dataframe(self, race_data_list: list) -> pd.DataFrame:
        """レースデータリストをDataFrameに変換"""
        records = []
        
        for race_data in race_data_list:
            race_info = race_data.get('race_info', {})
            results = race_data.get('results', [])
            
            for result in results:
                record = {
                    'race_name': race_info.get('race_name', ''),
                    'race_date': race_info.get('race_date', ''),
                    'venue': race_info.get('venue', ''),
                    **result
                }
                records.append(record)
        
        df = pd.DataFrame(records)
        
        # データ型変換
        if not df.empty:
            # 数値カラムの変換
            numeric_columns = ['着順', '枠番', '馬番', '単勝人気', '単勝オッズ', '馬体重', '増減']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def generate_summary_report(self, df: pd.DataFrame) -> dict:
        """サマリーレポートを生成"""
        if df.empty:
            return {}
        
        report = {
            'basic_stats': {
                'total_races': df['race_name'].nunique() if 'race_name' in df.columns else 0,
                'total_horses': len(df),
                'interview_coverage': (df['interview'].notna() & (df['interview'] != '')).sum() if 'interview' in df.columns else 0,
                'memo_coverage': (df['memo'].notna() & (df['memo'] != '')).sum() if 'memo' in df.columns else 0,
            }
        }
        
        # インタビュー統計
        if 'interview' in df.columns:
            interview_data = df[df['interview'].notna() & (df['interview'] != '')]
            report['interview_stats'] = {
                'coverage_rate': round((df['interview'].notna() & (df['interview'] != '')).mean() * 100, 1),
                'avg_length': interview_data['interview'].str.len().mean() if len(interview_data) > 0 else 0,
            }
        
        # メモ統計
        if 'memo' in df.columns:
            memo_data = df[df['memo'].notna() & (df['memo'] != '')]
            report['memo_stats'] = {
                'coverage_rate': round((df['memo'].notna() & (df['memo'] != '')).mean() * 100, 1),
                'avg_length': memo_data['memo'].str.len().mean() if len(memo_data) > 0 else 0,
            }
        
        # 人気と着順の分析
        if '着順' in df.columns and '単勝人気' in df.columns:
            popular_horses = df[df['単勝人気'] <= 3]
            if len(popular_horses) > 0:
                first_favorites = popular_horses[popular_horses['単勝人気'] == 1]
                report['popular_horse_stats'] = {
                    'total_popular_horses': len(popular_horses),
                    'win_rate_1st_favorite': round((first_favorites['着順'] == 1).mean() * 100, 1) if len(first_favorites) > 0 else 0,
                    'top3_rate_popular': round((popular_horses['着順'] <= 3).mean() * 100, 1),
                }
        
        return report
    
    def export_report(self, df: pd.DataFrame, report: dict, output_file: str = "data/analysis/report.txt"):
        """レポートをテキストファイルに出力"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== Horse Racing Data Analysis Report ===\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("=== Basic Statistics ===\n")
            basic = report.get('basic_stats', {})
            f.write(f"Total Races: {basic.get('total_races', 0)}\n")
            f.write(f"Total Horses: {basic.get('total_horses', 0)}\n")
            f.write(f"Interview Data: {basic.get('interview_coverage', 0)} horses\n")
            f.write(f"Memo Data: {basic.get('memo_coverage', 0)} horses\n\n")
            
            if 'interview_stats' in report:
                f.write("=== Interview Statistics ===\n")
                interview = report['interview_stats']
                f.write(f"Coverage Rate: {interview.get('coverage_rate', 0):.1f}%\n")
                f.write(f"Average Length: {interview.get('avg_length', 0):.1f} characters\n\n")
            
            if 'memo_stats' in report:
                f.write("=== Memo Statistics ===\n")
                memo = report['memo_stats']
                f.write(f"Coverage Rate: {memo.get('coverage_rate', 0):.1f}%\n")
                f.write(f"Average Length: {memo.get('avg_length', 0):.1f} characters\n\n")
            
            if 'popular_horse_stats' in report:
                f.write("=== Popular Horse Analysis ===\n")
                popular = report['popular_horse_stats']
                f.write(f"1st Favorite Win Rate: {popular.get('win_rate_1st_favorite', 0):.1f}%\n")
                f.write(f"Top 3 Popular Top 3 Rate: {popular.get('top3_rate_popular', 0):.1f}%\n\n")
        
        self.logger.info(f"Report exported to {output_path}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Horse Racing Data Analyzer")
    parser.add_argument("--race-id", help="Specific race ID to analyze")
    parser.add_argument("--date-start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default="data/analysis", help="Output directory")
    
    args = parser.parse_args()
    
    # 日付範囲の処理
    date_range = None
    if args.date_start or args.date_end:
        start_date = datetime.strptime(args.date_start, '%Y-%m-%d').date() if args.date_start else datetime.now().date() - timedelta(days=30)
        end_date = datetime.strptime(args.date_end, '%Y-%m-%d').date() if args.date_end else datetime.now().date()
        date_range = (start_date, end_date)
    
    # 分析実行
    analyzer = DataAnalyzer()
    
    print("Loading data...")
    df = analyzer.load_race_data(race_id=args.race_id, date_range=date_range)
    
    if df.empty:
        print("No data found for analysis")
        return
    
    print("Generating report...")
    report = analyzer.generate_summary_report(df)
    
    print("Exporting report...")
    analyzer.export_report(df, report, f"{args.output_dir}/report.txt")
    
    # コンソール出力
    print("\n=== Analysis Complete ===")
    basic = report.get('basic_stats', {})
    print(f"Analyzed {basic.get('total_races', 0)} races with {basic.get('total_horses', 0)} horses")
    
    if 'interview_stats' in report:
        print(f"Interview coverage: {report['interview_stats'].get('coverage_rate', 0):.1f}%")
    if 'memo_stats' in report:
        print(f"Memo coverage: {report['memo_stats'].get('coverage_rate', 0):.1f}%")
    
    print(f"Results saved to: {args.output_dir}")


if __name__ == "__main__":
    main() 
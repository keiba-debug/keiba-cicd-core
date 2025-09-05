#!/usr/bin/env python3
"""
データ完全性可視化ツール
organized配下のデータ取得状況をHTMLレポートとして出力
"""

import json
import glob
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import argparse

def analyze_race_data(race_dir: Path) -> Dict[str, Any]:
    """レースディレクトリのデータ完全性を分析"""
    
    data_types = {
        'shutsuba': 'shutsuba_*.json',
        'seiseki': 'seiseki_*.json',
        'cyokyo': 'cyokyo_*.json',
        'danwa': 'danwa_*.json',
        'syoin': 'syoin_*.json',
        'paddok': 'paddok_*.json',
        'integrated': 'integrated_*.json',
        'markdown': '*.md'
    }
    
    coverage = {}
    for data_type, pattern in data_types.items():
        files = list(race_dir.glob(pattern))
        if data_type == 'markdown':
            # integrated_*.mdを除外
            files = [f for f in files if not f.name.startswith('integrated')]
        coverage[data_type] = len(files)
    
    return coverage

def generate_html_report(analysis_results: Dict[str, Any], output_path: str):
    """HTML形式のレポートを生成"""
    
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>KeibaCICD データ完全性レポート</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }
        h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .summary { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .venue-section { background: white; padding: 15px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th { background: #4CAF50; color: white; padding: 10px; text-align: left; }
        td { padding: 8px; border-bottom: 1px solid #ddd; }
        tr:hover { background: #f5f5f5; }
        .complete { background: #d4edda; color: #155724; }
        .partial { background: #fff3cd; color: #856404; }
        .missing { background: #f8d7da; color: #721c24; }
        .stats { display: flex; justify-content: space-around; margin: 20px 0; }
        .stat-box { background: white; padding: 15px; border-radius: 8px; text-align: center; flex: 1; margin: 0 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-value { font-size: 2em; font-weight: bold; color: #4CAF50; }
        .stat-label { color: #666; margin-top: 5px; }
        .legend { display: flex; gap: 20px; margin: 20px 0; }
        .legend-item { display: flex; align-items: center; gap: 5px; }
        .legend-color { width: 20px; height: 20px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>🏇 KeibaCICD データ完全性レポート</h1>
    <p>生成日時: {timestamp}</p>
    <p>対象日: {target_date}</p>
    
    <div class="summary">
        <h2>📊 サマリー</h2>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">{total_venues}</div>
                <div class="stat-label">開催場数</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{total_races}</div>
                <div class="stat-label">総レース数</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{coverage_rate}%</div>
                <div class="stat-label">データカバー率</div>
            </div>
        </div>
        
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color complete"></div>
                <span>完全（全データ取得済み）</span>
            </div>
            <div class="legend-item">
                <div class="legend-color partial"></div>
                <span>部分的（一部データ欠損）</span>
            </div>
            <div class="legend-item">
                <div class="legend-color missing"></div>
                <span>欠損（主要データなし）</span>
            </div>
        </div>
    </div>
"""
    
    # 会場ごとの詳細
    for venue_name, venue_data in analysis_results['venues'].items():
        status_class = "complete"
        total_coverage = sum(1 for r in venue_data['races'].values() 
                            if r.get('shutsuba', 0) > 0 and r.get('integrated', 0) > 0)
        
        if total_coverage == 0:
            status_class = "missing"
        elif total_coverage < len(venue_data['races']):
            status_class = "partial"
        
        html += f"""
    <div class="venue-section {status_class}">
        <h2>{venue_name} （{len(venue_data['races'])}R）</h2>
        <table>
            <tr>
                <th>レース</th>
                <th>出走表</th>
                <th>成績</th>
                <th>調教</th>
                <th>談話</th>
                <th>勝因敗因</th>
                <th>パドック</th>
                <th>統合</th>
                <th>MD</th>
            </tr>
"""
        
        for race_id, race_data in sorted(venue_data['races'].items()):
            race_num = race_id[-2:] if len(race_id) >= 2 else race_id
            
            def status_icon(count):
                if count > 0:
                    return "✅"
                else:
                    return "❌"
            
            html += f"""
            <tr>
                <td>{race_num}R</td>
                <td>{status_icon(race_data.get('shutsuba', 0))}</td>
                <td>{status_icon(race_data.get('seiseki', 0))}</td>
                <td>{status_icon(race_data.get('cyokyo', 0))}</td>
                <td>{status_icon(race_data.get('danwa', 0))}</td>
                <td>{status_icon(race_data.get('syoin', 0))}</td>
                <td>{status_icon(race_data.get('paddok', 0))}</td>
                <td>{status_icon(race_data.get('integrated', 0))}</td>
                <td>{status_icon(race_data.get('markdown', 0))}</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
"""
    
    # 推奨アクション
    html += """
    <div class="summary">
        <h2>🎯 推奨アクション</h2>
        <ul>
"""
    
    missing_types = analysis_results.get('missing_summary', {})
    if missing_types:
        for data_type, count in missing_types.items():
            if count > 0:
                html += f"            <li>{data_type}データが{count}レース分欠損しています。再取得を推奨。</li>\n"
    else:
        html += "            <li>全データ取得完了！</li>\n"
    
    html += """
        </ul>
    </div>
</body>
</html>
"""
    
    # テンプレート変数を置換
    html = html.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target_date=analysis_results.get('date', 'N/A'),
        total_venues=len(analysis_results.get('venues', {})),
        total_races=sum(len(v['races']) for v in analysis_results.get('venues', {}).values()),
        coverage_rate=analysis_results.get('coverage_rate', 0)
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

def main():
    parser = argparse.ArgumentParser(description='データ完全性可視化ツール')
    parser.add_argument('--date', required=True, help='対象日 (YYYY/MM/DD)')
    parser.add_argument('--output', default='coverage_report.html', help='出力ファイル名')
    
    args = parser.parse_args()
    
    # 分析実行
    date_parts = args.date.split('/')
    base_path = Path(f"Z:/KEIBA-CICD/data/organized/{date_parts[0]}/{date_parts[1]}/{date_parts[2]}")
    
    if not base_path.exists():
        print(f"Error: {base_path} does not exist")
        return
    
    analysis_results = {
        'date': args.date,
        'venues': {},
        'missing_summary': {}
    }
    
    # 各会場のデータを分析
    for venue_dir in base_path.iterdir():
        if venue_dir.is_dir():
            venue_name = venue_dir.name
            races = {}
            
            # 各レースIDのデータを収集
            for json_file in venue_dir.glob("integrated_*.json"):
                race_id = json_file.stem.replace('integrated_', '')
                race_dir = venue_dir  # 同じディレクトリ内
                races[race_id] = analyze_race_data(race_dir)
            
            # レースIDがない場合は出走表から推測
            if not races:
                for json_file in venue_dir.glob("shutsuba_*.json"):
                    race_id = json_file.stem.replace('shutsuba_', '')
                    races[race_id] = analyze_race_data(venue_dir)
            
            if races:
                analysis_results['venues'][venue_name] = {'races': races}
    
    # カバー率計算
    total_expected = sum(len(v['races']) * 8 for v in analysis_results['venues'].values())  # 8種類のデータ
    total_actual = sum(
        sum(race_data.get(dt, 0) for dt in ['shutsuba', 'seiseki', 'cyokyo', 'danwa', 'syoin', 'paddok', 'integrated', 'markdown'])
        for v in analysis_results['venues'].values()
        for race_data in v['races'].values()
    )
    
    analysis_results['coverage_rate'] = round((total_actual / total_expected * 100) if total_expected > 0 else 0, 1)
    
    # 欠損サマリー
    missing_summary = {}
    for data_type in ['shutsuba', 'seiseki', 'cyokyo', 'danwa', 'syoin', 'paddok', 'integrated', 'markdown']:
        missing_count = sum(
            1 for v in analysis_results['venues'].values()
            for race_data in v['races'].values()
            if race_data.get(data_type, 0) == 0
        )
        if missing_count > 0:
            missing_summary[data_type] = missing_count
    
    analysis_results['missing_summary'] = missing_summary
    
    # HTMLレポート生成
    generate_html_report(analysis_results, args.output)
    print(f"レポート生成完了: {args.output}")
    
    # 簡易サマリーを標準出力
    print(f"\n=== データ完全性サマリー ({args.date}) ===")
    print(f"開催場数: {len(analysis_results['venues'])}")
    print(f"総レース数: {sum(len(v['races']) for v in analysis_results['venues'].values())}")
    print(f"カバー率: {analysis_results['coverage_rate']}%")
    
    if missing_summary:
        print("\n欠損データ:")
        for dt, count in missing_summary.items():
            print(f"  - {dt}: {count}レース")

if __name__ == "__main__":
    main()
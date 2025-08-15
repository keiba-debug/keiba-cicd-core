"""
レース別MDファイル生成機能
Phase 1: 基本機能の実装
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class RaceMarkdownGenerator:
    """レース情報をMarkdown形式で生成するクラス"""
    
    def __init__(self, data_root: str = "Z:/KEIBA-CICD/data"):
        self.data_root = Path(data_root)
        self.organized_dir = self.data_root / "organized"
        
    def load_race_data(self, race_id: str) -> Dict[str, Any]:
        """レースデータを読み込み"""
        data = {}
        
        # 出馬表データ
        shutsuba_file = self.data_root / f"shutsuba_{race_id}.json"
        if shutsuba_file.exists():
            with open(shutsuba_file, 'r', encoding='utf-8') as f:
                data['shutsuba'] = json.load(f)
        
        # 調教データ
        cyokyo_file = self.data_root / f"cyokyo_{race_id}.json"
        if cyokyo_file.exists():
            with open(cyokyo_file, 'r', encoding='utf-8') as f:
                data['cyokyo'] = json.load(f)
        
        # 厩舎コメント
        danwa_file = self.data_root / f"danwa_{race_id}.json"
        if danwa_file.exists():
            with open(danwa_file, 'r', encoding='utf-8') as f:
                data['danwa'] = json.load(f)
                
        return data
    
    def load_race_info(self, date: str, race_id: str) -> Optional[Dict]:
        """日程データから特定レースの情報を取得"""
        nittei_file = self.data_root / "temp" / f"nittei_{date}.json"
        
        if not nittei_file.exists():
            return None
            
        with open(nittei_file, 'r', encoding='utf-8') as f:
            nittei_data = json.load(f)
            
        # レースIDから該当レースを検索
        for kaisai_name, races in nittei_data.get('kaisai_data', {}).items():
            for race in races:
                if race['race_id'] == race_id:
                    race['kaisai_name'] = kaisai_name
                    return race
        return None
    
    def generate_markdown(self, date: str, race_id: str) -> str:
        """Markdownコンテンツを生成"""
        # レース情報取得
        race_info = self.load_race_info(date, race_id)
        if not race_info:
            return f"# レース情報が見つかりません: {race_id}"
        
        # レースデータ取得
        race_data = self.load_race_data(race_id)
        
        # Markdown生成
        md_lines = []
        
        # ヘッダー
        kaisai = race_info.get('kaisai_name', '')
        race_no = race_info.get('race_no', '')
        race_name = race_info.get('race_name', '')
        
        # グレードレース判定
        grade = ""
        if 'Ｇ１' in race_name or 'G1' in race_name:
            grade = "(G1)"
        elif 'Ｇ２' in race_name or 'G2' in race_name:
            grade = "(G2)"
        elif 'Ｇ３' in race_name or 'G3' in race_name:
            grade = "(G3)"
        
        md_lines.append(f"# {kaisai} {race_no} {race_name} {grade}")
        md_lines.append(f"*生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        md_lines.append("")
        
        # レース情報セクション
        md_lines.append("## レース情報")
        md_lines.append(f"- **日付**: {date[:4]}-{date[4:6]}-{date[6:8]}")
        md_lines.append(f"- **開催**: {kaisai}")
        md_lines.append(f"- **レース番号**: {race_no}")
        md_lines.append(f"- **レース名**: {race_name}")
        if grade:
            md_lines.append(f"- **グレード**: {grade.strip('()')}")
        md_lines.append(f"- **コース**: {race_info.get('course', 'N/A')}")
        md_lines.append("")
        
        # 出馬表セクション
        if 'shutsuba' in race_data:
            md_lines.append("## 出馬表")
            md_lines.append("")
            md_lines.append("| 枠 | 馬番 | 馬名 | 性齢 | 斤量 | 騎手 | 調教師 | オッズ | 人気 |")
            md_lines.append("|----|------|------|------|------|------|--------|--------|------|")
            
            horses = race_data['shutsuba'].get('horses', [])
            for horse in horses:
                waku = horse.get('waku', '-')
                umaban = horse.get('umaban', '-')
                name = horse.get('name', '-')
                sei_rei = horse.get('sei_rei', '-')
                kinryo = horse.get('kinryo', '-')
                jockey = horse.get('jockey', '-')
                trainer = horse.get('trainer', '-')
                odds = horse.get('odds', '-')
                ninki = horse.get('ninki', '-')
                
                md_lines.append(f"| {waku} | {umaban} | {name} | {sei_rei} | {kinryo} | {jockey} | {trainer} | {odds} | {ninki} |")
            md_lines.append("")
        
        # 調教情報セクション
        if 'cyokyo' in race_data:
            md_lines.append("## 調教情報")
            cyokyo_data = race_data['cyokyo'].get('data', [])
            for item in cyokyo_data[:5]:  # 上位5頭のみ
                md_lines.append(f"### {item.get('umaban', '')}番 {item.get('name', '')}")
                md_lines.append(f"- **調教日**: {item.get('date', 'N/A')}")
                md_lines.append(f"- **場所**: {item.get('place', 'N/A')}")
                md_lines.append(f"- **タイム**: {item.get('time', 'N/A')}")
                md_lines.append(f"- **評価**: {item.get('hyoka', 'N/A')}")
                md_lines.append("")
        
        # 厩舎コメントセクション
        if 'danwa' in race_data:
            md_lines.append("## 厩舎コメント")
            danwa_data = race_data['danwa'].get('data', [])
            for item in danwa_data[:5]:  # 上位5頭のみ
                md_lines.append(f"### {item.get('umaban', '')}番 {item.get('name', '')}")
                md_lines.append(f"{item.get('comment', 'コメントなし')}")
                md_lines.append("")
        
        # 期待値分析セクション（プレースホルダー）
        md_lines.append("## 期待値分析")
        md_lines.append("*（期待値計算機能は実装予定）*")
        md_lines.append("")
        
        # 外部コメントセクション（プレースホルダー）
        md_lines.append("## 外部コメント")
        md_lines.append("*（外部コメント統合機能は実装予定）*")
        md_lines.append("")
        
        return "\n".join(md_lines)
    
    def save_markdown(self, date: str, race_id: str, content: str, race_info: Dict):
        """Markdownファイルを保存"""
        # 保存先ディレクトリ作成
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        
        # 開催場所から競馬場名を抽出
        kaisai = race_info.get('kaisai_name', '')
        if '札幌' in kaisai:
            track = '札幌'
        elif '新潟' in kaisai:
            track = '新潟'
        elif '中京' in kaisai:
            track = '中京'
        elif '東京' in kaisai:
            track = '東京'
        elif '中山' in kaisai:
            track = '中山'
        elif '阪神' in kaisai:
            track = '阪神'
        elif '京都' in kaisai:
            track = '京都'
        elif '福島' in kaisai:
            track = '福島'
        elif '小倉' in kaisai:
            track = '小倉'
        else:
            track = 'その他'
        
        output_dir = self.organized_dir / year / month / day / track
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # ファイル名生成
        race_no = race_info.get('race_no', '')
        race_name = race_info.get('race_name', '').replace('/', '_')
        filename = f"{race_no}_{race_name}.md"
        
        # 保存
        output_file = output_dir / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return output_file


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='レース別MDファイル生成')
    parser.add_argument('--date', required=True, help='日付 (YYYYMMDD)')
    parser.add_argument('--race-id', help='レースID')
    parser.add_argument('--all', action='store_true', help='全レースを生成')
    
    args = parser.parse_args()
    
    generator = RaceMarkdownGenerator()
    
    if args.race_id:
        # 特定レース生成
        race_info = generator.load_race_info(args.date, args.race_id)
        if race_info:
            content = generator.generate_markdown(args.date, args.race_id)
            output_file = generator.save_markdown(args.date, args.race_id, content, race_info)
            print(f"[OK] MDファイル生成: {output_file}")
        else:
            print(f"[ERROR] レース情報が見つかりません: {args.race_id}")
    
    elif args.all:
        # 全レース生成
        nittei_file = Path(f"Z:/KEIBA-CICD/data/temp/nittei_{args.date}.json")
        if nittei_file.exists():
            with open(nittei_file, 'r', encoding='utf-8') as f:
                nittei_data = json.load(f)
            
            count = 0
            for kaisai_name, races in nittei_data.get('kaisai_data', {}).items():
                for race in races:
                    race_id = race['race_id']
                    race['kaisai_name'] = kaisai_name
                    
                    content = generator.generate_markdown(args.date, race_id)
                    output_file = generator.save_markdown(args.date, race_id, content, race)
                    print(f"[OK] {kaisai_name} {race['race_no']}: {output_file}")
                    count += 1
            
            print(f"\n[完了] {count}レースのMDファイルを生成しました")
        else:
            print(f"[ERROR] 日程ファイルが見つかりません: {nittei_file}")


if __name__ == "__main__":
    main()
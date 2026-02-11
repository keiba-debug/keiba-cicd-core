"""
拡張版Markdown生成モジュール
外部コメント・馬場情報・レース傾向を統合
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# 既存のMarkdownGeneratorを継承
from src.integrator.markdown_generator import MarkdownGenerator


class EnhancedMarkdownGenerator(MarkdownGenerator):
    """
    外部コメント・馬場情報・レース傾向に対応した拡張版ジェネレータ
    """
    
    def __init__(self, output_dir: str = None, use_organized_dir: bool = True):
        """
        初期化
        
        Args:
            output_dir: 出力ディレクトリ
            use_organized_dir: organizedディレクトリ以下に出力するか
        """
        super().__init__(output_dir, use_organized_dir)
        
        # 追加データのパス設定
        self.external_comments_dir = Path(self.data_root) / 'external_comments'
        self.track_conditions_dir = Path(self.data_root) / 'track_conditions'
        self.race_trends_dir = Path(self.data_root) / 'race_trends'
    
    def generate_race_markdown(self, race_data: Dict[str, Any], save: bool = True) -> str:
        """
        拡張版: レースデータからMarkdownを生成（外部データ統合付き）
        
        Args:
            race_data: 統合レースデータ
            save: ファイルとして保存するか
            
        Returns:
            Markdown形式の文字列
        """
        md_content = []
        
        # race_id取得
        race_id = race_data.get('meta', {}).get('race_id', '')
        
        # 実際の日付を取得（race_infoから）
        actual_date = race_data.get('race_info', {}).get('date', '')
        if actual_date:
            # YYYY/MM/DD または YYYY-MM-DD 形式から YYYYMMDD に変換
            date_str = actual_date.replace('/', '').replace('-', '')
        else:
            # フォールバック: race_idから推測（これは正確ではない）
            date_str = race_id[:8] if len(race_id) >= 8 else ''
            
        venue = self._get_venue_name(race_id)
        print(f"[DEBUG] 日付: {date_str}, 競馬場: {venue}, race_id: {race_id}")
        
        # ヘッダー情報
        md_content.append(self._generate_header(race_data))
        
        # レース情報セクション
        md_content.append(self._generate_race_info(race_data))
        
        # 馬場情報セクション（新規追加）
        track_condition = self._load_track_condition(date_str, venue)
        if track_condition:
            md_content.append(self._generate_track_condition_section(track_condition, venue))
        
        # レース傾向セクション（新規追加）
        race_trend = self._load_race_trend(date_str, venue, race_id)
        if race_trend:
            md_content.append(self._generate_race_trend_section(race_trend))
        
        # 出走表テーブル
        md_content.append(self._generate_entry_table(race_data))
        
        # レース結果（成績データがある場合）
        if self._has_results(race_data):
            md_content.append(self._generate_results_table(race_data))
            md_content.append(self._generate_race_flow_mermaid(race_data))
            md_content.append(self._generate_results_summary(race_data))
            md_content.append(self._generate_payouts_section(race_data))
            md_content.append(self._generate_laps_section(race_data))
        
        # 調教・厩舎談話情報
        md_content.append(self._generate_training_comments(race_data))
        
        # パドック情報
        paddock_section = self._generate_paddock_section(race_data)
        if paddock_section:
            md_content.append(paddock_section)
        
        # 前走インタビュー
        interview_section = self._generate_previous_interview_section(race_data)
        if interview_section:
            md_content.append(interview_section)
        
        # 外部コメントセクション（新規追加）
        external_comments = self._load_external_comments(date_str, venue, race_id)
        print(f"[DEBUG] 外部コメント読み込み結果: {bool(external_comments)}")
        if external_comments:
            section = self._generate_external_comments_section(external_comments)
            print(f"[DEBUG] 外部コメントセクション生成: {len(section)} 文字")
            md_content.append(section)
        else:
            print(f"[DEBUG] 外部コメントがありません")
        
        # 分析情報
        md_content.append(self._generate_analysis(race_data))
        
        # 期待値分析（新規追加）
        md_content.append(self._generate_expected_value_analysis(race_data))
        
        # 外部リンク
        md_content.append(self._generate_links(race_data))
        
        # メタ情報
        md_content.append(self._generate_footer(race_data))
        
        markdown_text = '\n\n'.join(filter(None, md_content))
        
        if save:
            output_path = self._get_output_path(race_data)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_text)
        
        return markdown_text
    
    def _load_track_condition(self, date_str: str, venue: str) -> Optional[Dict]:
        """馬場情報を読み込み"""
        if not date_str or not venue:
            return None
            
        # ファイルパスを構成
        year = date_str[:4]
        month = date_str[4:6]
        filename = f'track_condition_{date_str}.json'
        file_path = self.track_conditions_dir / year / month / filename
        
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('tracks', {}).get(venue, {})
            except Exception as e:
                print(f"馬場情報読み込みエラー: {e}")
        
        return None
    
    def _load_race_trend(self, date_str: str, venue: str, race_id: str) -> Optional[Dict]:
        """レース傾向を読み込み"""
        if not date_str or not venue:
            return None
        
        # レース番号を取得
        race_no = f"{int(race_id[10:12])}R" if len(race_id) >= 12 else None
        if not race_no:
            return None
        
        # ファイルパスを構成
        year = date_str[:4]
        month = date_str[4:6]
        filename = f'race_trend_{date_str}.json'
        file_path = self.race_trends_dir / year / month / filename
        
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    venue_data = data.get('tracks', {}).get(venue, {})
                    return venue_data.get('races', {}).get(race_no, {})
            except Exception as e:
                print(f"レース傾向読み込みエラー: {e}")
        
        return None
    
    def _load_external_comments(self, date_str: str, venue: str, race_id: str) -> Dict:
        """外部コメントを読み込み"""
        comments = {}
        
        if not date_str or not venue:
            return comments
        
        # レース番号を取得
        race_no = f"{int(race_id[10:12])}R" if len(race_id) >= 12 else None
        if not race_no:
            return comments
        
        # 福田コメント（JSON）
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        
        # JSONファイル
        fukuda_json = self.external_comments_dir / 'fukuda' / year / month / day / f'{venue}{race_no}.json'
        print(f"[DEBUG] 外部コメントファイルを探索: {fukuda_json}")
        print(f"[DEBUG] ファイル存在: {fukuda_json.exists()}")
        
        if fukuda_json.exists():
            try:
                with open(fukuda_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    comments['fukuda'] = data.get('comments', {}).get('fukuda', {})
                    print(f"[DEBUG] 福田コメント読み込み成功: {comments['fukuda']}")
            except Exception as e:
                print(f"福田コメント（JSON）読み込みエラー: {e}")
        
        # テキストファイル
        fukuda_txt = self.external_comments_dir / 'fukuda' / year / month / day / f'{venue}{race_no}.txt'
        if fukuda_txt.exists():
            try:
                with open(fukuda_txt, 'r', encoding='utf-8') as f:
                    comments['fukuda_text'] = f.read()
            except Exception as e:
                print(f"福田コメント（テキスト）読み込みエラー: {e}")
        
        # AIコメント
        ai_json = self.external_comments_dir / 'ai_analysis' / year / month / day / f'{venue}{race_no}.json'
        if ai_json.exists():
            try:
                with open(ai_json, 'r', encoding='utf-8') as f:
                    comments['ai'] = json.load(f)
            except Exception as e:
                print(f"AIコメント読み込みエラー: {e}")
        
        return comments
    
    def _generate_track_condition_section(self, track_data: Dict, venue: str) -> str:
        """馬場情報セクション生成"""
        lines = ["## 馬場情報"]
        
        # 天候情報
        weather = track_data.get('weather', '')
        temp = track_data.get('temperature', '')
        humidity = track_data.get('humidity', '')
        
        if weather:
            weather_info = f"- **天候**: {weather}"
            if temp:
                weather_info += f" (気温: {temp}℃"
                if humidity:
                    weather_info += f", 湿度: {humidity}%"
                weather_info += ")"
            lines.append(weather_info)
        
        # 風情報
        wind = track_data.get('wind', {})
        if wind:
            lines.append(f"- **風**: {wind.get('direction', '')} {wind.get('speed', '')}m/s")
        
        # 芝状態
        turf = track_data.get('turf', {})
        if turf:
            lines.append("\n### 芝コース")
            lines.append(f"- **状態**: {turf.get('condition', '')}")
            lines.append(f"- **含水率**: {turf.get('moisture', '')}%")
            if turf.get('notes'):
                lines.append(f"- **特記事項**: {turf.get('notes', '')}")
            if turf.get('time_index'):
                lines.append(f"- **タイム指数**: {turf.get('time_index', '')}")
        
        # ダート状態
        dirt = track_data.get('dirt', {})
        if dirt:
            lines.append("\n### ダートコース")
            lines.append(f"- **状態**: {dirt.get('condition', '')}")
            lines.append(f"- **含水率**: {dirt.get('moisture', '')}%")
            if dirt.get('notes'):
                lines.append(f"- **特記事項**: {dirt.get('notes', '')}")
        
        # バイアス
        bias = track_data.get('bias', {})
        if bias:
            lines.append("\n### コースバイアス")
            if bias.get('turf_inside'):
                lines.append(f"- **芝内側**: {bias.get('turf_inside', '')} (1.0が標準)")
            if bias.get('turf_outside'):
                lines.append(f"- **芝外側**: {bias.get('turf_outside', '')}")
        
        return '\n'.join(lines)
    
    def _generate_race_trend_section(self, trend_data: Dict) -> str:
        """レース傾向セクション生成"""
        lines = ["## レース傾向"]
        
        # 過去の傾向
        historical = trend_data.get('historical_trends', {})
        if historical:
            lines.append("\n### 過去の傾向")
            
            pace = historical.get('pace_tendency', '')
            if pace:
                lines.append(f"- **ペース傾向**: {pace}")
            
            position = historical.get('favorable_position', '')
            if position:
                lines.append(f"- **有利な脚質**: {position}")
            
            winning_rate = historical.get('winning_rate_by_position', {})
            if winning_rate:
                lines.append("\n**脚質別勝率**:")
                for pos, rate in winning_rate.items():
                    lines.append(f"- {pos}: {rate}%")
        
        # 血統傾向
        bloodline = trend_data.get('bloodline_trends', {})
        if bloodline:
            lines.append("\n### 血統傾向")
            
            top_sires = bloodline.get('top_sires', [])
            if top_sires:
                lines.append(f"- **好走血統**: {', '.join(top_sires)}")
            
            success_rate = bloodline.get('success_rate', {})
            if success_rate:
                lines.append("\n**種牡馬別成功率**:")
                for sire, rate in success_rate.items():
                    lines.append(f"- {sire}: {rate}%")
        
        # 騎手傾向
        jockey = trend_data.get('jockey_trends', {})
        if jockey:
            lines.append("\n### 騎手傾向")
            
            top_jockeys = jockey.get('top_jockeys', [])
            if top_jockeys:
                lines.append(f"- **好成績騎手**: {', '.join(top_jockeys)}")
            
            recent = jockey.get('recent_winners', [])
            if recent:
                lines.append("\n**近年の勝利騎手**:")
                for winner in recent:
                    lines.append(f"- {winner.get('year', '')}年: {winner.get('jockey', '')}")
        
        return '\n'.join(lines)
    
    def _generate_external_comments_section(self, comments: Dict) -> str:
        """外部コメントセクション生成"""
        lines = ["## 外部コメント・分析メモ"]
        
        # 福田コメント（構造化）
        if 'fukuda' in comments:
            fukuda = comments['fukuda']
            lines.append("\n### 福田メモ")
            
            # 総評
            if fukuda.get('general'):
                lines.append(f"\n**総評**: {fukuda['general']}")
            
            # 馬別コメント
            horses = fukuda.get('horses', {})
            if horses:
                lines.append("\n**馬別評価**:")
                for num, horse_info in horses.items():
                    line = f"- **{num}番 {horse_info.get('name', '')}**: "
                    line += horse_info.get('comment', '')
                    
                    rating = horse_info.get('rating', '')
                    if rating:
                        line += f" (評価: {rating}"
                        confidence = horse_info.get('confidence', '')
                        if confidence:
                            line += f", 自信度: {confidence}/5"
                        line += ")"
                    lines.append(line)
            
            # 戦略
            strategy = fukuda.get('strategy', {})
            if strategy:
                lines.append("\n**買い目戦略**:")
                if strategy.get('main'):
                    lines.append(f"- メイン: {strategy['main']}")
                if strategy.get('hedge'):
                    lines.append(f"- ヘッジ: {strategy['hedge']}")
                if strategy.get('budget'):
                    lines.append(f"- 予算: {strategy['budget']:,}円")
        
        # 福田コメント（テキスト）
        if 'fukuda_text' in comments:
            lines.append("\n### メモ（テキスト）")
            lines.append("```")
            lines.append(comments['fukuda_text'])
            lines.append("```")
        
        # AI分析コメント
        if 'ai' in comments:
            ai = comments['ai']
            lines.append("\n### AI分析")
            
            if ai.get('pace_prediction'):
                lines.append(f"- **ペース予想**: {ai['pace_prediction']}")
            
            key_factors = ai.get('key_factors', [])
            if key_factors:
                lines.append("\n**注目ポイント**:")
                for factor in key_factors:
                    lines.append(f"- {factor}")
        
        return '\n'.join(lines)
    
    def _generate_expected_value_analysis(self, race_data: Dict) -> str:
        """期待値分析セクション生成"""
        lines = ["## 期待値分析"]
        
        # TODO: 実際の期待値計算ロジックを実装
        lines.append("\n*（期待値計算機能は実装予定）*")
        lines.append("")
        lines.append("| 馬番 | 馬名 | 推定勝率 | オッズ | 期待値 | 推奨度 |")
        lines.append("|------|------|----------|--------|--------|--------|")
        lines.append("| - | - | - | - | - | - |")
        
        return '\n'.join(lines)
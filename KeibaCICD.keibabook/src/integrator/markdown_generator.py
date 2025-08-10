"""
Markdown形式の統合レースデータ生成モジュール
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class MarkdownGenerator:
    """
    レースデータをMarkdown形式で出力するジェネレータ
    """
    
    def __init__(self, output_dir: str = None, use_organized_dir: bool = True):
        """
        初期化
        
        Args:
            output_dir: 出力ディレクトリ（デフォルト: data/markdown）
            use_organized_dir: organizedディレクトリ以下に出力するか（デフォルト: True）
        """
        self.data_root = os.getenv('KEIBA_DATA_ROOT_DIR', './data')  # keibabookフォルダを使わない
        self.use_organized_dir = use_organized_dir
        if use_organized_dir:
            self.output_dir = None  # 動的に決定
        else:
            self.output_dir = output_dir or self.data_root + '/markdown'
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # race_idと実際の開催日のマッピング
        self.actual_date_map = {}
        self.venue_name_map = {}  # 実際の競馬場名のマッピング
        self.load_actual_dates()
    
    def generate_race_markdown(self, race_data: Dict[str, Any], save: bool = True) -> str:
        """
        レースデータからMarkdownを生成
        
        Args:
            race_data: 統合レースデータ
            save: ファイルとして保存するか
            
        Returns:
            Markdown形式の文字列
        """
        md_content = []
        
        # ヘッダー情報
        md_content.append(self._generate_header(race_data))
        
        # レース情報セクション
        md_content.append(self._generate_race_info(race_data))
        
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
        
        # パドック情報（あれば）
        paddock_section = self._generate_paddock_section(race_data)
        if paddock_section:
            md_content.append(paddock_section)
        
        # 前走インタビュー（あれば）
        interview_section = self._generate_previous_interview_section(race_data)
        if interview_section:
            md_content.append(interview_section)
        
        # 分析情報
        md_content.append(self._generate_analysis(race_data))
        
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
    
    def _generate_header(self, race_data: Dict[str, Any]) -> str:
        """レースヘッダー生成"""
        race_info = race_data.get('race_info', {})
        race_id = race_data.get('meta', {}).get('race_id', '')
        
        # レース名を取得（デフォルト値を設定）
        race_name = race_info.get('race_name', '')
        if not race_name and race_id:
            # race_idから情報を推測
            race_num = int(race_id[10:12]) if len(race_id) >= 12 else 0
            race_name = f"{race_num}R"
        
        grade = race_info.get('grade', '')
        if grade and grade != 'OP':
            race_name = f"{race_name} ({grade})"
        
        return f"# {race_name}"
    
    def _generate_race_info(self, race_data: Dict[str, Any]) -> str:
        """レース基本情報生成"""
        race_info = race_data.get('race_info', {})
        race_id = race_data.get('meta', {}).get('race_id', '')
        
        lines = ["## 📋 レース情報"]
        
        # 日付を整形
        date_str = self._format_date(race_id)
        venue = self._get_venue_name(race_id)
        
        info_items = []
        if date_str:
            info_items.append(f"- **日付**: {date_str}")
        if venue:
            info_items.append(f"- **競馬場**: {venue}")
        
        distance = race_info.get('distance', 0)
        track = race_info.get('track', '')
        if distance:
            info_items.append(f"- **距離**: {track}{distance}m")
        
        weather = race_info.get('weather', '')
        if weather:
            info_items.append(f"- **天候**: {weather}")
        
        track_condition = race_info.get('track_condition', '')
        if track_condition:
            info_items.append(f"- **馬場状態**: {track_condition}")
        
        lines.extend(info_items)
        return '\n'.join(lines)
    
    def _generate_entry_table(self, race_data: Dict[str, Any]) -> str:
        """出走表テーブル生成（詳細版）"""
        entries = race_data.get('entries', [])
        if not entries:
            return ""
        
        lines = ["## 🐎 出走表"]
        lines.append("")
        
        # テーブルヘッダー
        lines.append("| 枠 | 馬番 | 馬名 | 性齢 | 騎手 | 斤量 | オッズ | 人気 | 本誌 | 総合P | 調教 |")
        lines.append("|:---:|:---:|------|:---:|------|:---:|------:|:---:|:---:|:---:|:----:|")
        
        for entry in entries:
            entry_data = entry.get('entry_data', {})
            training_data = entry.get('training_data', {})
            
            waku = entry_data.get('waku', '')
            horse_num = entry['horse_number']
            horse_name = entry['horse_name']
            age = entry_data.get('age', '')
            jockey = entry_data.get('jockey', '-')
            weight = entry_data.get('weight', '')
            odds = entry_data.get('odds', '-')
            rank = entry_data.get('odds_rank', '-')
            honshi_mark = entry_data.get('honshi_mark', '-')
            mark_point = entry_data.get('aggregate_mark_point', entry_data.get('mark_point', 0))
            training_eval = training_data.get('evaluation', '-') if training_data else '-'
            
            # 馬名にリンクを追加
            horse_id = entry.get('horse_id', '')
            if horse_id:
                horse_name = f"[{horse_name}](https://p.keibabook.co.jp/db/uma/{horse_id})"
            
            lines.append(f"| {waku} | {horse_num} | {horse_name} | {age} | {jockey} | {weight} | {odds} | {rank} | {honshi_mark} | {mark_point} | {training_eval} |")
        
        # 参考: 人別印一覧（折りたたみイメージ、シンプル出力）
        lines.append("")
        lines.append("<details><summary>人別印（参考）</summary>")
        for entry in entries[:10]:
            mbp = entry.get('entry_data', {}).get('marks_by_person') or {}
            if not mbp:
                continue
            lines.append("")
            lines.append(f"- {entry['horse_number']}番 {entry['horse_name']}")
            for k, v in list(mbp.items())[:5]:
                lines.append(f"  - {k}: {v}")
        lines.append("</details>")
        
        # 短評セクションを追加
        short_comments = []
        for entry in entries:
            short_comment = entry.get('entry_data', {}).get('short_comment', '')
            if short_comment and short_comment != '-' and short_comment != '':
                short_comments.append({
                    'num': entry['horse_number'],
                    'name': entry['horse_name'],
                    'comment': short_comment
                })
        
        if short_comments:
            lines.append("")
            lines.append("### 📝 短評")
            lines.append("")
            for item in short_comments[:10]:  # 最大10頭分
                lines.append(f"**{item['num']}番 {item['name']}**: {item['comment']}")
        
        return '\n'.join(lines)
    
    def _generate_results_table(self, race_data: Dict[str, Any]) -> str:
        """レース結果テーブル生成"""
        entries = race_data.get('entries', [])
        
        # 結果データがある馬のみ抽出してソート
        results = []
        for entry in entries:
            result = entry.get('result', {})
            if result and result.get('finish_position'):
                results.append({
                    'position': result.get('finish_position', ''),
                    'horse_num': entry['horse_number'],
                    'horse_name': entry['horse_name'],
                    'time': result.get('time', ''),
                    'margin': result.get('margin', ''),
                    'last_3f': result.get('last_3f', ''),
                    'jockey': entry.get('entry_data', {}).get('jockey', ''),
                    'odds': entry.get('entry_data', {}).get('odds', ''),
                    'comment': result.get('raw_data', {}).get('interview', '')
                })
        
        if not results:
            return ""
        
        # 着順でソート
        try:
            results.sort(key=lambda x: int(x['position']) if x['position'].isdigit() else 999)
        except:
            pass
        
        lines = ["## 🏁 レース結果"]
        lines.append("")
        lines.append("| 着順 | 馬番 | 馬名 | タイム | 着差 | 上り | 騎手 | オッズ |")
        lines.append("|:---:|:---:|------|--------|------|------|------|-------:|")
        
        for result in results[:10]:  # 上位10頭のみ表示
            lines.append(f"| {result['position']} | {result['horse_num']} | {result['horse_name']} | "
                        f"{result['time']} | {result['margin']} | {result['last_3f']} | "
                        f"{result['jockey']} | {result['odds']} |")
        
        # 騎手コメントがあれば追加
        comments_with_text = [r for r in results if r.get('comment')]
        if comments_with_text:
            lines.append("")
            lines.append("### 💬 騎手コメント")
            lines.append("")
            for result in comments_with_text[:3]:  # 上位3頭のコメント
                lines.append(f"**{result['position']}着 {result['horse_name']}**")
                lines.append(f"> {result['comment']}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_race_flow_mermaid(self, race_data: Dict[str, Any]) -> str:
        """レース展開のMermaidグラフ生成"""
        entries = race_data.get('entries', [])
        
        # 上位5頭の結果を取得
        top_horses = []
        for entry in entries:
            result = entry.get('result', {})
            if result and result.get('finish_position'):
                try:
                    position = int(result['finish_position'])
                    if position <= 5:
                        top_horses.append({
                            'position': position,
                            'name': entry['horse_name'],
                            'passing': result.get('raw_data', {}).get('通過順位', '')
                        })
                except:
                    pass
        
        if not top_horses:
            return ""
        
        top_horses.sort(key=lambda x: x['position'])
        
        lines = ["## 📊 レース展開"]
        lines.append("")
        lines.append("```mermaid")
        lines.append("graph LR")
        lines.append("    subgraph ゴール")
        
        for i, horse in enumerate(top_horses):
            if i == 0:
                lines.append(f"        A[1着: {horse['name']}]")
            else:
                prev_label = chr(ord('A') + i - 1)
                curr_label = chr(ord('A') + i)
                lines.append(f"        {prev_label} --> {curr_label}[{horse['position']}着: {horse['name']}]")
        
        lines.append("    end")
        lines.append("```")
        
        return '\n'.join(lines)

    def _generate_results_summary(self, race_data: Dict[str, Any]) -> str:
        """成績サマリー（上位・上がり最速など）"""
        entries = race_data.get('entries', [])
        results = []
        for entry in entries:
            res = entry.get('result') or {}
            if res and res.get('finish_position'):
                try:
                    pos = int(res.get('finish_position'))
                except Exception:
                    continue
                results.append({
                    'position': pos,
                    'num': entry['horse_number'],
                    'name': entry['horse_name'],
                    'time': res.get('time', ''),
                    'margin': res.get('margin', ''),
                    'last_3f': res.get('last_3f', ''),
                    'jockey': entry.get('entry_data', {}).get('jockey', ''),
                    'odds': entry.get('entry_data', {}).get('odds', ''),
                    'odds_rank': entry.get('entry_data', {}).get('odds_rank', '')
                })
        if not results:
            return ""
        results.sort(key=lambda x: x['position'])
        lines = ["## 🧾 成績サマリー", ""]
        # 上位3頭
        lines.append("### 上位3頭")
        for r in results[:3]:
            lines.append(f"- {r['position']}着 {r['num']}番 {r['name']}（{r['jockey']}） オッズ:{r['odds']} 人気:{r['odds_rank']} タイム:{r['time']} 着差:{r['margin']}")
        # 上がり最速
        try:
            with_last = [r for r in results if r.get('last_3f')]
            def last_to_float(s: str) -> float:
                # 例: 34.5 → 34.5 / '34.5' / '34秒5' などに簡易対応
                import re
                m = re.findall(r"\d+\.?\d*", s)
                return float(m[0]) if m else 999.9
            if with_last:
                fastest = sorted(with_last, key=lambda x: last_to_float(x['last_3f']))[0]
                lines.append("")
                lines.append(f"- 上がり最速: {fastest['num']}番 {fastest['name']} {fastest['last_3f']}")
        except Exception:
            pass
        return '\n'.join(lines)
    
    def _generate_training_comments(self, race_data: Dict[str, Any]) -> str:
        """調教・厩舎談話情報生成"""
        entries = race_data.get('entries', [])
        
        training_info = []
        stable_comments = []
        
        for entry in entries:
            horse_name = entry['horse_name']
            horse_num = entry['horse_number']
            
            # 調教情報（詳細版）
            training = entry.get('training_data')
            if training:
                info = {
                    'horse': f"{horse_num}番 {horse_name}",
                    'eval': training.get('evaluation', ''),
                    'last_training': training.get('last_training', ''),
                    'course': training.get('training_course', ''),
                    'load': training.get('training_load', ''),
                    'rank': training.get('training_rank', ''),
                    'comment': training.get('trainer_comment', ''),
                    'times': training.get('training_times', []),
                    'short_review': training.get('short_review', '')
                }
                if info['eval'] or info['comment'] or info['times'] or info['short_review']:
                    training_info.append(info)
            
            # 厩舎談話（詳細版）
            stable = entry.get('stable_comment')
            if stable:
                comment_text = stable.get('comment', '')
                if comment_text:
                    stable_comments.append({
                        'horse': f"{horse_num}番 {horse_name}",
                        'comment': comment_text,
                        'trainer': stable.get('trainer', ''),
                        'date': stable.get('date', '')
                    })
        
        if not training_info and not stable_comments:
            return ""
        
        lines = ["## 📝 調教・厩舎情報"]
        lines.append("")
        
        if training_info:
            lines.append("### 🏃 調教情報（評価・短評）")
            lines.append("")
            lines.append("| 馬番・馬名 | 評価 | 最終追切 | コース | 負荷 | 順位 | 短評 |")
            lines.append("|-----------|:---:|---------|--------|:---:|:---:|------|")
            
            # 評価の高い順にソート
            eval_order = {'S': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, '': 99}
            training_info.sort(key=lambda x: eval_order.get(x.get('eval', ''), 99))
            
            for info in training_info[:10]:  # 最大10頭
                eval = info['eval'] or '-'
                last = info['last_training'] or '-'
                course = info['course'] or '-'
                load = info['load'] or '-'
                rank = info['rank'] or '-'
                short_review = info.get('short_review', '')
                if short_review and len(short_review) > 30:
                    short_review = short_review[:30] + '...'
                short_review = short_review or '-'
                lines.append(f"| {info['horse']} | {eval} | {last} | {course} | {load} | {rank} | {short_review} |")
            
            # 調教タイムがある場合は追加
            for info in training_info:
                if info['times'] and len(info['times']) > 0:
                    lines.append("")
                    lines.append(f"**{info['horse']}の調教タイム**")
                    for time_data in info['times'][:3]:  # 最新3本
                        lines.append(f"- {time_data}")
                    break  # 1頭分のみ表示
            
            # トレーナーコメントがある場合
            comments_with_text = [i for i in training_info if i.get('comment')]
            if comments_with_text:
                lines.append("")
                lines.append("**調教師コメント（抜粋）**")
                for info in comments_with_text[:3]:
                    lines.append(f"> {info['horse']}: {info['comment']}" )
            
            lines.append("")
        
        if stable_comments:
            lines.append("### 💬 厩舎談話（厩舎コメント）")
            lines.append("")
            
            for comment in stable_comments[:10]:  # 最大10件に増やす
                lines.append(f"**{comment['horse']}**")
                if comment.get('trainer'):
                    lines.append(f"*{comment['trainer']}調教師*")
                if comment.get('date'):
                    lines.append(f"*({comment['date']})*")
                lines.append(f"> {comment['comment']}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_analysis(self, race_data: Dict[str, Any]) -> str:
        """分析情報生成"""
        analysis = race_data.get('analysis', {})
        if not analysis:
            return ""
        
        lines = ["## 📈 レース分析"]
        lines.append("")
        
        # ペース予想
        pace = analysis.get('expected_pace', '')
        if pace:
            lines.append(f"- **予想ペース**: {pace}")
        
        # 人気馬
        favorites = analysis.get('favorites', [])
        if favorites:
            lines.append("- **上位人気馬**:")
            for fav in favorites[:3]:
                lines.append(f"  - {fav['odds_rank']}番人気: {fav['horse_name']}")
        
        # 注目の調教馬
        highlights = analysis.get('training_highlights', [])
        if highlights:
            lines.append("- **調教好調馬**:")
            for highlight in highlights[:3]:
                lines.append(f"  - {highlight}")
        
        return '\n'.join(lines)

    def _generate_payouts_section(self, race_data: Dict[str, Any]) -> str:
        payouts = race_data.get('payouts') or {}
        if not payouts or all(v in (None, [], {}) for v in payouts.values()):
            return ""
        lines = ["## 💴 配当情報", ""]
        def fmt(v):
            if v is None:
                return '-'
            if isinstance(v, list):
                return ', '.join(str(x) for x in v) if v else '-'
            return str(v)
        lines.append(f"- 単勝: {fmt(payouts.get('win'))}")
        lines.append(f"- 複勝: {fmt(payouts.get('place'))}")
        lines.append(f"- 馬連: {fmt(payouts.get('quinella'))}")
        lines.append(f"- 馬単: {fmt(payouts.get('exacta'))}")
        lines.append(f"- ワイド: {fmt(payouts.get('wide'))}")
        lines.append(f"- 3連複: {fmt(payouts.get('trio'))}")
        lines.append(f"- 3連単: {fmt(payouts.get('trifecta'))}")
        return '\n'.join(lines)

    def _generate_laps_section(self, race_data: Dict[str, Any]) -> str:
        laps = race_data.get('laps') or {}
        if not laps:
            return ""
        lines = ["## ⏱ ラップ/ペース", ""]
        if laps.get('lap_times'):
            lap_text = ' - '.join(laps['lap_times'][:12])  # 長すぎ回避
            lines.append(f"- ラップ: {lap_text}")
        if laps.get('first_1000m'):
            lines.append(f"- 1000m通過: {laps['first_1000m']}")
        if laps.get('pace'):
            pace_map = {'H': 'ハイ', 'M': 'ミドル', 'S': 'スロー'}
            lines.append(f"- ぺース: {pace_map.get(laps['pace'], laps['pace'])}")
        return '\n'.join(lines)
    
    def _generate_links(self, race_data: Dict[str, Any]) -> str:
        """外部リンク生成"""
        race_id = race_data.get('meta', {}).get('race_id', '')
        if not race_id:
            return ""
        
        lines = ["## 🔗 関連リンク"]
        lines.append("")
        
        # 競馬ブックのレースページ（推定URL）
        date_part = race_id[:8]
        lines.append(f"- [競馬ブック レースページ](https://p.keibabook.co.jp/cyuou/race/{date_part}/{race_id})")
        
        # 各馬の詳細ページ
        entries = race_data.get('entries', [])
        if entries:
            lines.append("")
            lines.append("### 出走馬詳細")
            for entry in entries[:5]:  # 上位5頭
                horse_id = entry.get('horse_id', '')
                if horse_id:
                    horse_name = entry['horse_name']
                    lines.append(f"- [{horse_name}](https://p.keibabook.co.jp/db/uma/{horse_id})")
        
        return '\n'.join(lines)
    
    def _generate_footer(self, race_data: Dict[str, Any]) -> str:
        """フッター情報生成"""
        meta = race_data.get('meta', {})
        
        lines = ["---"]
        lines.append("")
        lines.append("### データ情報")
        lines.append(f"- **生成日時**: {meta.get('created_at', '')}")
        lines.append(f"- **更新日時**: {meta.get('updated_at', '')}")
        lines.append(f"- **データソース**: 競馬ブック")
        
        # データ取得状況
        sources = meta.get('data_sources', {})
        if sources:
            lines.append("- **取得データ**:")
            for key, status in sources.items():
                emoji = "✅" if status == "" else "❌"
                lines.append(f"  - {emoji} {key}")
        
        return '\n'.join(lines)
    
    def _has_results(self, race_data: Dict[str, Any]) -> bool:
        """結果データがあるか確認"""
        entries = race_data.get('entries', [])
        for entry in entries:
            if entry.get('result', {}).get('finish_position'):
                return True
        return False
    
    def _generate_paddock_section(self, race_data: Dict[str, Any]) -> str:
        """パドック情報セクション生成（詳細版）"""
        entries = race_data.get('entries', [])
        paddock_entries = []
        
        for entry in entries:
            paddock_info = entry.get('paddock_info')
            if paddock_info and (paddock_info.get('mark') or paddock_info.get('comment') or paddock_info.get('evaluation')):
                paddock_entries.append({
                    'horse_number': entry['horse_number'],
                    'horse_name': entry['horse_name'],
                    'paddock': paddock_info
                })
        
        if not paddock_entries:
            # パドックデータが取得できていない場合の説明
            return "## 🐴 パドック情報\n\n*パドック情報は現在利用できません（レース直前に公開されます）*"
        
        lines = ["## 🐴 パドック情報"]
        lines.append("")
        
        # 評価の高い馬を優先表示
        eval_order = {'◎': 1, '○': 2, '▲': 3, '△': 4, '☆': 5, '★': 6, '×': 99, '-': 100}
        paddock_entries.sort(key=lambda x: eval_order.get(x['paddock'].get('mark', '-'), 100))
        
        # テーブル形式で表示
        lines.append("| 馬番 | 馬名 | 評価 | 点数 | 状態 | 気配 | コメント |")
        lines.append("|:---:|------|:---:|:---:|------|------|----------|")
        
        for entry in paddock_entries[:12]:  # 最大12頭
            paddock = entry['paddock']
            horse_num = entry['horse_number']
            horse_name = entry['horse_name']
            mark = paddock.get('mark', paddock.get('evaluation', '-'))
            score = paddock.get('mark_score', '-')
            condition = paddock.get('condition', '-')
            temperament = paddock.get('temperament', '-')
            comment = paddock.get('comment', '-')
            
            # コメントが長い場合は短縮
            if comment and comment != '-' and len(comment) > 40:
                comment = comment[:40] + "..."
            
            lines.append(f"| {horse_num} | {horse_name} | {mark} | {score} | {condition} | {temperament} | {comment} |")
        
        # 詳細コメントがある場合は追加
        detailed_comments = [e for e in paddock_entries if e['paddock'].get('comment') and len(e['paddock'].get('comment', '')) > 40]
        if detailed_comments:
            lines.append("")
            lines.append("### パドック詳細コメント")
            lines.append("")
            for entry in detailed_comments[:5]:
                lines.append(f"**{entry['horse_number']}番 {entry['horse_name']}**")
                lines.append(f"> {entry['paddock']['comment']}")
                lines.append("")
        
        return '\n'.join(lines)
    
    def _generate_previous_interview_section(self, race_data: Dict[str, Any]) -> str:
        """前走インタビューセクション生成（詳細版）"""
        entries = race_data.get('entries', [])
        interview_entries = []
        
        for entry in entries:
            interview = entry.get('previous_race_interview')
            if interview and (interview.get('comment') or interview.get('race_name')):
                interview_entries.append({
                    'horse_number': entry['horse_number'],
                    'horse_name': entry['horse_name'],
                    'jockey': interview.get('jockey', ''),
                    'comment': interview.get('comment', ''),
                    'race_name': interview.get('race_name', ''),
                    'finish_position': interview.get('finish_position', ''),
                    'date': interview.get('date', '')
                })
        
        if not interview_entries:
            return ""
        
        lines = ["## 💬 前走インタビュー"]
        lines.append("")
        
        # インタビューがある馬を表示
        for entry in interview_entries[:8]:  # 最大8頭まで表示に増やす
            lines.append(f"### {entry['horse_number']}番 {entry['horse_name']}")
            
            # レース情報があれば表示
            if entry.get('race_name'):
                race_info = []
                if entry.get('date'):
                    race_info.append(entry['date'])
                if entry.get('race_name'):
                    race_info.append(entry['race_name'])
                if entry.get('finish_position'):
                    race_info.append(f"{entry['finish_position']}着")
                if race_info:
                    lines.append(f"*前走: {' / '.join(race_info)}*")
            
            if entry['jockey']:
                lines.append(f"**{entry['jockey']}騎手**")
            
            if entry['comment']:
                # コメントを見やすく整形
                comment_lines = entry['comment'].split('。')
                formatted_comment = '。\n> '.join(line.strip() for line in comment_lines if line.strip())
                if not formatted_comment.endswith('。'):
                    formatted_comment += '。'
                lines.append(f"> {formatted_comment}")
            else:
                lines.append("> *コメントなし*")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def load_actual_dates(self):
        """
        race_ids フォルダから実際の開催日マッピングを読み込む
        """
        race_ids_dir = os.path.join(self.data_root, 'race_ids')
        if not os.path.exists(race_ids_dir):
            return
        
        for file_name in os.listdir(race_ids_dir):
            if file_name.endswith('_info.json'):
                date_str = file_name.replace('_info.json', '')
                file_path = os.path.join(race_ids_dir, file_name)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 各開催のrace_idを実際の日付にマッピング
                    for kaisai_name, races in data.get('kaisai_data', {}).items():
                        # 開催名から競馬場名を取得（例：「2回新潟5日目」→「新潟」）
                        import re
                        # 長い名前を先にマッチさせる（中京を中より優先）
                        venue_match = re.search(r'(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)', kaisai_name)
                        venue_name = venue_match.group(1) if venue_match else ''
                        
                        for race in races:
                            race_id = race.get('race_id', '')
                            if race_id:
                                self.actual_date_map[race_id] = date_str
                                if venue_name:
                                    self.venue_name_map[race_id] = venue_name
                except Exception as e:
                    pass
    
    def _format_date(self, race_id: str) -> str:
        """race_idから日付を整形"""
        # 実際の開催日付を使用
        if race_id in self.actual_date_map:
            date_str = self.actual_date_map[race_id]
        elif len(race_id) >= 8:
            date_str = race_id[:8]
        else:
            return ""
        
        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}年{int(month)}月{int(day)}日"
        except:
            return ""
    
    def _get_venue_name(self, race_id: str) -> str:
        """race_idから競馬場名を取得"""
        # 実際の競馬場名を優先的に使用
        if race_id in self.venue_name_map:
            return self.venue_name_map[race_id]
        
        # フォールバック：コードから推測
        if len(race_id) >= 10:
            venue_code = race_id[8:10]
            venue_map = {
                '01': '札幌',
                '02': '函館',
                '03': '福島',
                '04': '新潟',
                '05': '東京',
                '06': '中山',
                '07': '中京',
                '08': '京都',
                '09': '阪神',
                '10': '小倉'
            }
            return venue_map.get(venue_code, '')
        return ""
    
    def _get_output_path(self, race_data: Dict[str, Any]) -> str:
        """出力パスを生成"""
        race_id = race_data.get('meta', {}).get('race_id', 'unknown')
        
        # 常にorganizedディレクトリに出力
        if race_id in self.actual_date_map:
            date_str = self.actual_date_map[race_id]
        else:
            date_str = race_id[:8] if len(race_id) >= 8 else '00000000'
        
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        
        # 競馬場名を取得
        venue_name = self.venue_name_map.get(race_id, '')
        if not venue_name and len(race_id) >= 10:
            # race_idから競馬場コードを取得してマッピング
            venue_code = race_id[8:10]
            venue_map = {
                '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
                '05': '東京', '06': '中山', '07': '中京', '08': '京都',
                '09': '阪神', '10': '小倉'
            }
            venue_name = venue_map.get(venue_code, '')
        
        if venue_name:
            # 競馬場別フォルダ構造: organized/YYYY/MM/DD/競馬場名/
            output_dir = os.path.join(self.data_root, 'organized', year, month, day, venue_name)
        else:
            # 競馬場名が取得できない場合は日付フォルダ直下
            output_dir = os.path.join(self.data_root, 'organized', year, month, day)
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(output_dir, f"{race_id}.md")
    
    def batch_generate(self, integrated_dir: str = None) -> Dict[str, Any]:
        """
        統合JSONファイルから一括でMarkdownを生成
        
        Args:
            integrated_dir: 統合ファイルのディレクトリ
            
        Returns:
            処理結果のサマリー
        """
        if not integrated_dir:
            integrated_dir = os.getenv('KEIBA_DATA_ROOT_DIR', './data') + '/integrated'
        
        json_files = list(Path(integrated_dir).glob('integrated_*.json'))
        
        success = 0
        failed = 0
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    race_data = json.load(f)
                
                self.generate_race_markdown(race_data, save=True)
                success += 1
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
                failed += 1
        
        return {
            'total': len(json_files),
            'success': success,
            'failed': failed
        }
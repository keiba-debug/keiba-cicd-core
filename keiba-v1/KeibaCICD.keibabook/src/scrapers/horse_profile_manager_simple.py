#!/usr/bin/env python3
"""
馬プロファイル管理システム（シンプル版）
馬ごとの情報を体系的に管理し、プロファイルファイルを生成・更新する
"""

import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class HorseProfileManager:
    """馬プロファイル管理クラス（シンプル版）"""

    def __init__(self, base_path: str = "Z:/KEIBA-CICD"):
        """
        初期化

        Args:
            base_path: KEIBA-CICDのベースパス
        """
        import os
        self.base_path = Path(base_path)

        # 環境変数からデータルートを取得（data2構造対応）
        data_root = os.getenv('KEIBA_DATA_ROOT_DIR', str(self.base_path / "data2"))
        self.data_root = Path(data_root)

        # 新構造対応
        self.profiles_dir = self.data_root / "horses" / "profiles"
        self.organized_dir = self.data_root / "organized"  # 旧構造との互換性
        self.races_dir = self.data_root / "races"  # 新構造
        self.temp_dir = self.data_root / "temp"  # JSONデータ保存先

        # プロファイルディレクトリを作成
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # ロギング設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        # 追加: 環境変数 HPM_DEBUG が有効なら DEBUG に引き上げ
        try:
            import os as _os
            if str(_os.getenv('HPM_DEBUG', '')).lower() in ('1', 'true', 'yes', 'on'):
                logging.getLogger().setLevel(logging.DEBUG)
                logger.setLevel(logging.DEBUG)
                logger.debug("HPM_DEBUG=on -> log level DEBUG")
        except Exception:
            pass

    def create_simple_seiseki_table(self, seiseki_table_md: str, past_races: List[Dict], horse_id: str = "") -> str:
        """
        シンプルな完全成績テーブルを生成
        
        Args:
            seiseki_table_md: 元のテーブル（Markdown）
            past_races: 過去成績データ
            horse_id: 馬ID
            
        Returns:
            新しいテーブル（Markdown）
        """
        logger.debug(f"create_simple_seiseki_table開始")
        
        # 表示する列の順序
        DISPLAY_COLUMNS = [
            'コメント', '本誌', '日付', '競馬場', 'レース', 'クラス', '距離', '馬場', '重量', '騎手', 
            '頭数', '馬番', '馬体重', '着順/人気', '枠', '頭数(区分)', 
            'タイム', 'タイム差', 'ペース後3F', '寸評'
        ]
        
        try:
            lines = seiseki_table_md.splitlines()
            if not lines:
                return seiseki_table_md

            # ヘッダー行を探す
            header_line = None
            data_start_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('|') and '年月日' in line:
                    header_line = line
                    data_start_idx = i + 2  # セパレータ行をスキップ
                    break
            
            if not header_line:
                return seiseki_table_md

            # 元のヘッダーを解析
            original_headers = [cell.strip() for cell in header_line.strip('|').split('|')]
            logger.debug(f"元のヘッダー: {original_headers}")
            
            # 列マッピングを作成
            column_mapping = {}
            for i, header in enumerate(original_headers):
                header_clean = header.strip()
                if '年月日' in header_clean:
                    column_mapping['日付'] = i
                elif '競馬場' in header_clean:
                    column_mapping['競馬場'] = i
                elif 'レース' in header_clean and 'クラス' not in header_clean:
                    column_mapping['レース'] = i
                elif 'クラス' in header_clean:
                    column_mapping['クラス'] = i
                elif '距離' in header_clean:
                    column_mapping['距離'] = i
                elif '馬場' in header_clean and '競馬場' not in header_clean:
                    column_mapping['馬場'] = i
                elif '重量' in header_clean:
                    column_mapping['重量'] = i
                elif '騎手' in header_clean:
                    column_mapping['騎手'] = i
                elif '頭数' in header_clean and '区分' not in header_clean:
                    column_mapping['頭数'] = i
                elif '馬番' in header_clean or 'ゲート' in header_clean or 'ゲ｜ト' in header_clean:
                    column_mapping['馬番'] = i
                elif '馬体重' in header_clean:
                    column_mapping['馬体重'] = i
                elif '着順' in header_clean and '人気' in header_clean:
                    column_mapping['着順/人気'] = i
                elif 'タイム' in header_clean and '差' not in header_clean:
                    column_mapping['タイム'] = i
                elif 'タイム差' in header_clean:
                    column_mapping['タイム差'] = i
                elif 'ペース' in header_clean:
                    column_mapping['ペース後3F'] = i

            logger.debug(f"列マッピング: {column_mapping}")

            # integrated_XXXXX.jsonからデータを取得する関数
            def get_integrated_data(race_id: str, horse_id: str) -> Dict:
                """integrated_XXXXX.jsonから対象馬のデータを取得"""
                try:
                    if len(race_id) == 12:
                        year = race_id[:4]
                        month = race_id[6:8]
                        day = race_id[8:10]
                        
                        json_path = self.data_root / "races" / year / month / day / f"integrated_{race_id}.json"
                        if json_path.exists():
                            with open(json_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                
                            for entry in data.get('entries', []):
                                if str(entry.get('horse_id', '')) == str(horse_id):
                                    entry_data = entry.get('entry_data', {})
                                    raw_data = entry.get('raw_data', {})
                                    
                                    return {
                                        'short_comment': entry_data.get('short_comment', ''),
                                        'honshi_mark': entry_data.get('honshi_mark', ''),
                                        '通過順位': raw_data.get('通過順位', ''),
                                        '寸評': raw_data.get('寸評', ''),
                                        '4角位置': raw_data.get('4角位置', '')
                                    }
                except Exception as e:
                    logger.debug(f"integrated_データ取得エラー {race_id}: {e}")
                return {}

            # 過去成績のマップを作成
            match_map = {}
            for r in past_races or []:
                key = (str(r.get('日付', '')), str(r.get('レース名', ''))[:10])
                
                race_id = r.get('レースID', '')
                integrated_data = get_integrated_data(race_id, horse_id) if race_id else {}
                
                # 枠分類の計算
                waku_raw = str(r.get('枠番', '') or '')
                if waku_raw.isdigit():
                    wn = int(waku_raw)
                    if wn <= 3:
                        waku_class = f"{wn}(内)"
                    elif wn <= 6:
                        waku_class = f"{wn}(中)"
                    else:
                        waku_class = f"{wn}(外)"
                else:
                    waku_class = '-'

                # 頭数分類の計算
                tousuu_raw = str(r.get('頭数', '') or '')
                if tousuu_raw.isdigit():
                    tn = int(tousuu_raw)
                    if tn <= 12:
                        tousuu_class = f"{tn}(少)"
                    elif tn <= 15:
                        tousuu_class = f"{tn}(中)"
                    else:
                        tousuu_class = f"{tn}(多)"
                else:
                    tousuu_class = '-'

                match_map[key] = {
                    'honshi': integrated_data.get('honshi_mark', '') or r.get('本誌', '-') or '-',
                    'waku': waku_class,
                    'tousuu': tousuu_class,
                    'short_comment': integrated_data.get('short_comment', ''),
                    '寸評': integrated_data.get('寸評', ''),
                }

            # 新しいテーブルを構築
            new_lines = []
            
            # ヘッダー行
            new_headers = []
            for col in DISPLAY_COLUMNS:
                if col in column_mapping:
                    new_headers.append(original_headers[column_mapping[col]])
                else:
                    new_headers.append(col)
            new_lines.append('| ' + ' | '.join(new_headers) + ' |')
            
            # セパレータ行
            new_lines.append('| ' + ' | '.join([':---:' for _ in new_headers]) + ' |')
            
            # データ行
            for i in range(data_start_idx, len(lines)):
                line = lines[i]
                if not line.startswith('|') or line.count('|') < 3:
                    continue
                    
                original_cells = [cell.strip() for cell in line.strip('|').split('|')]
                if len(original_cells) < 5:
                    continue
                
                # 日付とレース名でマッチング
                date_str = original_cells[column_mapping.get('日付', 0)] if '日付' in column_mapping else ''
                race_name = original_cells[column_mapping.get('レース', 4)] if 'レース' in column_mapping else ''
                key = (date_str, race_name[:10])
                info = match_map.get(key, {'honshi': '-', 'waku': '-', 'tousuu': '-', 'short_comment': '', '寸評': ''})
                
                # 新しい行を構築
                new_cells = []
                for col in DISPLAY_COLUMNS:
                    if col in column_mapping:
                        idx = column_mapping[col]
                        if idx < len(original_cells):
                            value = original_cells[idx]
                            # 日付の変換
                            if col == '日付' and value:
                                import re
                                date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', value)
                                if date_match:
                                    year = date_match.group(1)
                                    month = date_match.group(2).zfill(2)
                                    day = date_match.group(3).zfill(2)
                                    value = f"{year}/{month}/{day}"
                            new_cells.append(value)
                        else:
                            new_cells.append('-')
                    else:
                        # 追加列
                        if col == 'コメント':
                            new_cells.append(info.get('short_comment', ''))
                        elif col == '本誌':
                            new_cells.append(info.get('honshi', ''))
                        elif col == '枠':
                            new_cells.append(info.get('waku', ''))
                        elif col == '頭数(区分)':
                            new_cells.append(info.get('tousuu', ''))
                        elif col == '寸評':
                            new_cells.append(info.get('寸評', ''))
                        else:
                            new_cells.append('-')
                
                new_lines.append('| ' + ' | '.join(new_cells) + ' |')

            result = '\n'.join(new_lines)
            logger.debug(f"create_simple_seiseki_table完了: 出力テーブル行数={len(result.splitlines())}")
            return result
            
        except Exception as e:
            logger.error(f"create_simple_seiseki_tableエラー: {e}")
            logger.debug(f"エラー詳細: {type(e).__name__}: {str(e)}")
            return seiseki_table_md

    def create_horse_profile(self, horse_id: str, horse_name: str, horse_data: Dict = None,
                           include_history: bool = False, use_web_fetch: bool = False,
                           include_seiseki_table: bool = False) -> Path:
        """
        馬のプロファイルファイルを作成または更新（シンプル版）

        Args:
            horse_id: 馬のID
            horse_name: 馬名
            horse_data: 馬の追加情報
            include_history: 過去成績を含めるか
            use_web_fetch: Webから取得するか
            include_seiseki_table: 完全成績テーブルを含むか

        Returns:
            作成されたプロファイルファイルのパス
        """
        # ファイル名を生成
        import re
        def _sanitize(name: str) -> str:
            cleaned = re.sub(r'^[\(（]\s*[地外]\s*[\)）]\s*', '', name or '')
            cleaned = re.sub(r'[\\/:*?"<>|]', '_', cleaned)
            return cleaned
        safe_name = _sanitize(horse_name)
        profile_file = self.profiles_dir / f"{horse_id}_{safe_name}.md"

        # 既存ファイルがある場合は読み込み
        existing_content = ""
        user_memo = ""

        if profile_file.exists():
            with open(profile_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()

                # ユーザーメモセクションを保持
                memo_pattern = r'---\n## ユーザーメモ\n(.*?)(?:\n---|\Z)'
                memo_match = re.search(memo_pattern, existing_content, re.DOTALL)
                if memo_match:
                    user_memo = memo_match.group(1).strip()

        # プロファイル内容を生成
        content_parts = [
            f"# 馬プロファイル: {horse_name}",
            "",
            "## 基本情報",
            f"- **馬ID**: {horse_id}",
            f"- **馬名**: {horse_name}",
        ]

        if horse_data:
            if '性齢' in horse_data:
                content_parts.append(f"- **性齢**: {horse_data['性齢']}")
            if '騎手' in horse_data:
                content_parts.append(f"- **騎手**: {horse_data['騎手']}")
            if '斤量' in horse_data:
                content_parts.append(f"- **斤量**: {horse_data['斤量']}")

            content_parts.extend([
                f"- **更新日時**: {datetime.now().isoformat()}",
                "",
                "## 最近の出走情報",
            ])

            # レースファイル情報
            if 'レースファイル' in horse_data:
                content_parts.append(f"- **最終確認レース**: {horse_data['レースファイル']}")

            # その他の情報を整理して表示
            if 'オッズ' in horse_data and horse_data['オッズ']:
                content_parts.append(f"- **オッズ**: {horse_data['オッズ']}")
            if 'AI指数' in horse_data and horse_data['AI指数']:
                content_parts.append(f"- **AI指数**: {horse_data['AI指数']}")
            if '本誌' in horse_data and horse_data['本誌']:
                content_parts.append(f"- **本誌印**: {horse_data['本誌']}")
            if '短評' in horse_data and horse_data['短評']:
                content_parts.append(f"- **短評**: {horse_data['短評']}")

        # 完全成績テーブル（要求順序: 基本情報/最近の出走情報の直後）
        seiseki_header_idx = None
        seiseki_table_raw = None
        if include_seiseki_table:
            content_parts.extend([
                "",
                "## 完全成績",
                ""
            ])

            # 成績テーブルを取得
            from .horse_seiseki_fetcher import HorseSeisekiFetcher
            seiseki_fetcher = HorseSeisekiFetcher()
            logger.info(f"完全成績テーブル取得中: {horse_id}")

            seiseki_table_raw = seiseki_fetcher.fetch_seiseki_table(horse_id)
            seiseki_header_idx = len(content_parts) - 1  # 直前に空行を追加しているため、見出し直後の空行位置
            if not seiseki_table_raw:
                content_parts.append("*完全成績テーブルを取得できませんでした*")
                logger.warning(f"完全成績テーブル取得失敗: {horse_id}")

        if include_history:
            # Web取得オプション
            if use_web_fetch and horse_id:
                from .horse_past_races_fetcher import HorsePastRacesFetcher
                fetcher = HorsePastRacesFetcher()
                logger.info(f"Webから過去成績取得中: {horse_id}")

                # 競馬ブックから直接取得
                race_list = fetcher.fetch_horse_race_list(horse_id)
                past_races = []
                logger.info(f"取得したレース数: {len(race_list)}")

                # レースIDから詳細データを取得
                for race in race_list[:10]:
                    race_id = race.get('race_id', '')
                    if race_id:
                        # 既存JSONから詳細を取得
                        detail = self.get_race_detail_from_json(race_id, horse_name)
                        if detail:
                            logger.debug(f"JSONから詳細取得: {race_id}")
                            past_races.append(detail)
                        else:
                            # 基本情報のみでも追加
                            logger.debug(f"Webからの基本情報を使用: {race_id}")
                            past_races.append({
                                '日付': race.get('date', ''),
                                '競馬場': race.get('競馬場', ''),
                                'レース名': race.get('race_name', ''),
                                'race_class': race.get('race_class', ''),
                                '着順': race.get('着順', ''),
                                '騎手': race.get('騎手', ''),
                                '距離': race.get('距離', ''),
                                '馬場': race.get('馬場', ''),
                                'タイム': race.get('タイム', ''),
                                '上がり': race.get('上がり', ''),
                                '人気': race.get('人気', ''),
                                '馬体重': race.get('馬体重', ''),
                                '増減': race.get('増減', ''),
                                '通過': race.get('通過', ''),
                                '厩舎コメント': race.get('厩舎コメント', ''),
                                '枠番': race.get('枠番', ''),
                                '馬番': race.get('馬番', ''),
                                '頭数': race.get('頭数', ''),
                                'レースID': race_id
                            })
                logger.info(f"成績データ数: {len(past_races)}")
            else:
                # 既存JSONから過去成績を取得
                past_races = self.get_horse_past_races(horse_name, horse_id)

            # 完全成績テーブル（拡張版）を先に挿入
            if include_seiseki_table and seiseki_table_raw:
                try:
                    logger.debug(f"拡張前テーブル（先頭2行）: {seiseki_table_raw.splitlines()[:2]}")
                    augmented = self.create_simple_seiseki_table(seiseki_table_raw, past_races, horse_id)
                    logger.debug(f"拡張後テーブル（先頭2行）: {augmented.splitlines()[:2]}")
                    insert_at = seiseki_header_idx + 1
                    content_parts.insert(insert_at, augmented)
                    logger.debug("完全成績テーブルを拡張して挿入しました")
                except Exception as e:
                    # フォールバックとして生テーブルを挿入
                    logger.error(f"拡張エラー: {e}")
                    content_parts.insert(seiseki_header_idx + 1, seiseki_table_raw)
                    logger.debug("拡張失敗のため生テーブルを挿入しました")

            # 過去レースからの特徴分析
            features = self.analyze_horse_features(past_races)

            # 成績統計を計算
            stats = self.calculate_race_statistics(past_races)

            content_parts.extend([
                "",
                "## 過去成績分析",
                "",
                "### 成績サマリー",
                "| 項目 | 1着 | 2着 | 3着 | 着外 | 勝率 | 連対率 | 複勝率 |",
                "|:----:|:---:|:---:|:---:|:----:|:----:|:------:|:------:|",
                f"| 通算 | {stats['total']['1着']} | {stats['total']['2着']} | {stats['total']['3着']} | {stats['total']['着外']} | {stats['total']['勝率']}% | {stats['total']['連対率']}% | {stats['total']['複勝率']}% |",
                f"| 芝 | {stats['turf']['1着']} | {stats['turf']['2着']} | {stats['turf']['3着']} | {stats['turf']['着外']} | {stats['turf']['勝率']}% | {stats['turf']['連対率']}% | {stats['turf']['複勝率']}% |",
                f"| ダート | {stats['dirt']['1着']} | {stats['dirt']['2着']} | {stats['dirt']['3着']} | {stats['dirt']['着外']} | {stats['dirt']['勝率']}% | {stats['dirt']['連対率']}% | {stats['dirt']['複勝率']}% |",
                "",
                "### 最近10走（統合）",
                "| 日付 | 競馬場 | レース | 着順/人気 | 騎手 | 距離 | 馬場 | タイム | 上がり | 上がり順 | 枠 | 頭数 | 本誌 | 通過 | 短評 |",
                "|:----:|:------:|:------|:--------:|:----:|:----:|:----:|:------:|:------:|:------:|:--:|:----:|:----:|:----:|:-----|",
                self.format_combined_last10_table(past_races),
                "",
                "### 距離別成績",
                self.format_distance_stats_table(past_races),
                "",
                "### 馬場状態別成績",
                self.format_surface_stats_table(past_races),
                "",
                "### 条件別成績",
                self.format_condition_stats_table(past_races),
            ])

            # 分析メモセクション
            content_parts.extend([
                "",
                "## 分析メモ",
                "",
                "### 強み",
            ])

            # 特徴分析がある場合は表示
            if 'features' in locals() and features.get('strengths'):
                for strength in features['strengths']:
                    content_parts.append(f"- {strength}")
            else:
                content_parts.append("- （データから見える強みを記入）")

            content_parts.extend([
                "",
                "### 弱み",
            ])

            if 'features' in locals() and features.get('weaknesses'):
                for weakness in features['weaknesses']:
                    content_parts.append(f"- {weakness}")
            else:
                content_parts.append("- （データから見える弱みを記入）")

            content_parts.extend([
                "",
                "### 狙い目条件",
            ])

            if 'features' in locals() and features.get('favorable_conditions'):
                for condition in features['favorable_conditions']:
                    content_parts.append(f"- {condition}")
            else:
                content_parts.append("- （この馬が狙い目となる条件を記入）")

        content_parts.extend([
            "",
            "## 競馬ブックリンク",
            f"- [馬情報詳細](https://p.keibabook.co.jp/db/uma/{horse_id})",
            f"- [完全成績](https://p.keibabook.co.jp/db/uma/{horse_id}/kanzen)",
            "",
            "---",
            "## ユーザーメモ",
            user_memo if user_memo else "（ここに予想メモや注目ポイントを記入）",
            "",
            "---",
            f"*最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        # ファイルに書き込み
        content = '\n'.join(content_parts)
        
        with open(profile_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"プロファイル作成/更新: {profile_file.name}")

        return profile_file

    # 既存のメソッドを簡略化してコピー
    def get_race_detail_from_json(self, race_id: str, horse_name: str) -> Optional[Dict]:
        """レースIDから既存JSONを検索して詳細データを取得"""
        # 簡略化実装
        return None

    def get_horse_past_races(self, horse_name: str, horse_id: str = None) -> List[Dict]:
        """既存のJSONデータから馬の過去レース成績を取得"""
        # 簡略化実装
        return []

    def analyze_horse_features(self, past_races: List[Dict]) -> Dict:
        """過去レースから馬の特徴を分析"""
        return {'strengths': [], 'weaknesses': [], 'favorable_conditions': []}

    def calculate_race_statistics(self, past_races: List[Dict]) -> Dict:
        """過去レース成績から統計を計算"""
        return {
            'total': {'1着': 0, '2着': 0, '3着': 0, '着外': 0, '勝率': 0, '連対率': 0, '複勝率': 0},
            'turf': {'1着': 0, '2着': 0, '3着': 0, '着外': 0, '勝率': 0, '連対率': 0, '複勝率': 0},
            'dirt': {'1着': 0, '2着': 0, '3着': 0, '着外': 0, '勝率': 0, '連対率': 0, '複勝率': 0}
        }

    def format_combined_last10_table(self, past_races: List[Dict]) -> str:
        """基本成績と詳細成績を統合した最近10走テーブルを返す"""
        return "| データ取得中... | - | - | - | - | - | - | - | - | - | - | - | - | - | - |"

    def format_distance_stats_table(self, past_races: List[Dict]) -> str:
        """距離別の出走数/勝利/連対/複勝/勝率を集計してMarkdownテーブルを返す"""
        return "| 距離 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 特記事項 |\n|:----:|:------:|:----:|:----:|:----:|:----:|:---------|"

    def format_surface_stats_table(self, past_races: List[Dict]) -> str:
        """馬場状態別の出走数/勝利/連対/複勝/勝率を集計してMarkdownテーブルを返す"""
        return "| 馬場 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 特記事項 |\n|:----:|:------:|:----:|:----:|:----:|:----:|:---------|"

    def format_condition_stats_table(self, past_races: List[Dict]) -> str:
        """条件別成績を集計してテーブル形式にフォーマット"""
        return "| 条件 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 連対率 | 複勝率 |\n|:----:|:------:|:----:|:----:|:----:|:----:|:------:|:------:|"

#!/usr/bin/env python3
"""
馬プロファイル管理システム
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
    """馬プロファイル管理クラス"""

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

    def extract_horses_from_race(self, race_file: Path) -> List[Tuple[str, str, Dict]]:
        """
        レースMDファイルから出走馬情報を抽出

        Args:
            race_file: レースMDファイルのパス

        Returns:
            (horse_id, horse_name, horse_data)のタプルのリスト
        """
        horses = []

        try:
            with open(race_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 出走表セクションを探す
            table_pattern = r'\| 枠 \| 馬番 \| 馬名.*?\n((?:\|.*?\n)+)'
            table_match = re.search(table_pattern, content)

            if table_match:
                table_rows = table_match.group(1).strip().split('\n')

                for row in table_rows:
                    if row.startswith('|') and '|' in row:
                        cells = [cell.strip() for cell in row.split('|')[1:-1]]

                        if len(cells) >= 3:
                            # 馬名セルからhorse_idとhorse_nameを抽出
                            horse_name_cell = cells[2]

                            # リンク付きの場合（4パターンに対応）
                            # パターン1: keibabook URL
                            link_pattern1 = r'\[([^\]]+)\]\(https://p\.keibabook\.co\.jp/db/uma/(\d+)\)'
                            # パターン2: 相対パスプロファイル
                            link_pattern2 = r'\[([^\]]+)\]\([./]*horses/profiles/(\d+)_[^)]+\.md\)'
                            # パターン3: file:///形式の絶対パス
                            link_pattern3 = r'\[([^\]]+)\]\(file:///.*?/(\d+)_[^)]+\.md\)'
                            # パターン4: Z:/形式の絶対パス（現在の形式）
                            link_pattern4 = r'\[([^\]]+)\]\(Z:/.*?/(\d+)_[^)]+\.md\)'

                            link_match = (re.search(link_pattern1, horse_name_cell) or
                                        re.search(link_pattern2, horse_name_cell) or
                                        re.search(link_pattern3, horse_name_cell) or
                                        re.search(link_pattern4, horse_name_cell))

                            if link_match:
                                horse_name = link_match.group(1).strip()
                                horse_id = link_match.group(2)

                                # 地方馬マーカーを除去
                                horse_name = re.sub(r'^\[地\]', '', horse_name).strip()
                                horse_name = re.sub(r'^\(地\)', '', horse_name).strip()

                                # 馬データを収集
                                horse_data = {
                                    '性齢': cells[3] if len(cells) > 3 else '',
                                    '騎手': cells[4] if len(cells) > 4 else '',
                                    '斤量': cells[5] if len(cells) > 5 else '',
                                    'オッズ': cells[6] if len(cells) > 6 else '',
                                    'AI指数': cells[7] if len(cells) > 7 else '',
                                    'レート': cells[8] if len(cells) > 8 else '',
                                    '本誌': cells[9] if len(cells) > 9 else '',
                                    '総合P': cells[10] if len(cells) > 10 else '',
                                    '調教': cells[11] if len(cells) > 11 else '',
                                    '短評': cells[12] if len(cells) > 12 else '',
                                    'レースファイル': str(race_file),
                                    '抽出日時': datetime.now().isoformat()
                                }

                                horses.append((horse_id, horse_name, horse_data))
                                logger.debug(f"馬情報抽出: {horse_id} - {horse_name}")

        except Exception as e:
            logger.error(f"レースファイル解析エラー {race_file}: {e}")

        return horses

    def create_horse_profile(self, horse_id: str, horse_name: str, horse_data: Dict = None,
                           include_history: bool = False, use_web_fetch: bool = False,
                           include_seiseki_table: bool = False) -> Path:
        """
        馬のプロファイルファイルを作成または更新

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
        # 先頭マーカー(地)/(外)（半角・全角）を除去し、禁止文字はアンダースコアへ
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

        # 過去成績セクション（オプション）
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

            # 1. seisekiから基本テーブルを取得
            seiseki_table_raw = seiseki_fetcher.fetch_seiseki_table(horse_id)
            
            # 2. kanzenから本誌データを取得（フォールバック用）
            kanzen_data = None
            if seiseki_table_raw and horse_id:
                try:
                    import requests
                    from bs4 import BeautifulSoup
                    kanzen_url = f"https://p.keibabook.co.jp/db/uma/{horse_id}/kanzen"
                    logger.debug(f"kanzenページ取得開始: {kanzen_url}")
                    resp = requests.get(kanzen_url, timeout=8)
                    if resp.ok and len(resp.text) > 1000:
                        kanzen_data = resp.text
                        logger.debug(f"kanzenページ取得成功: {len(kanzen_data)}文字")
                    else:
                        logger.debug(f"kanzenページ取得失敗: status={resp.status_code}")
                except Exception as e:
                    logger.debug(f"kanzenページ取得エラー: {e}")
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

            # 過去レースからの特徴分析
            features = self.analyze_horse_features(past_races)

            # 成績統計を計算
            stats = self.calculate_race_statistics(past_races)

            # 完全成績テーブル（拡張版）を先に挿入
            if include_seiseki_table and seiseki_table_raw:
                try:
                    logger.debug(f"拡張前テーブル（先頭2行）: {seiseki_table_raw.splitlines()[:2]}")
                    augmented = self.augment_seiseki_table(seiseki_table_raw, past_races, horse_id, kanzen_data)
                    logger.debug(f"拡張後テーブル（先頭2行）: {augmented.splitlines()[:2]}")
                    insert_at = seiseki_header_idx + 1
                    content_parts.insert(insert_at, augmented)
                    logger.debug("完全成績テーブルを拡張して挿入しました")
                except Exception as e:
                    # フォールバックとして生テーブルを挿入
                    logger.error(f"拡張エラー: {e}")
                    content_parts.insert(seiseki_header_idx + 1, seiseki_table_raw)
                    logger.debug("拡張失敗のため生テーブルを挿入しました")

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

            # すでに挿入済みの完全成績テーブルが未拡張の場合は、保存直前に最終チェックで差し替え

            # 騎手コメントセクション（最新3走）
            if past_races:
                jockey_comments = self.format_jockey_comments_table(past_races[:3])
                if jockey_comments:
                    content_parts.extend([
                        "",
                        "### 騎手コメント（最新3走）",
                        "| 日付 | レース | 着順 | 騎手 | コメント |",
                        "|:----:|:------|:----:|:----:|:---------|",
                        jockey_comments
                    ])

        # 分析メモセクション
        content_parts.extend([
            "",
            "## 分析メモ",
            "",
            "### 強み",
        ])

        # 特徴分析がある場合は表示
        if include_history and 'features' in locals() and features.get('strengths'):
            for strength in features['strengths']:
                content_parts.append(f"- {strength}")
        else:
            content_parts.append("- （データから見える強みを記入）")

        content_parts.extend([
            "",
            "### 弱み",
        ])

        if include_history and 'features' in locals() and features.get('weaknesses'):
            for weakness in features['weaknesses']:
                content_parts.append(f"- {weakness}")
        else:
            content_parts.append("- （データから見える弱みを記入）")

        content_parts.extend([
            "",
            "### 狙い目条件",
        ])

        if include_history and 'features' in locals() and features.get('favorable_conditions'):
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
        
        # デバッグ: 完全成績セクションの内容を確認
        if include_seiseki_table:
            lines = content.splitlines()
            seiseki_start = -1
            for i, line in enumerate(lines):
                if line.strip() == "## 完全成績":
                    seiseki_start = i
                    break
            if seiseki_start != -1:
                seiseki_lines = lines[seiseki_start:seiseki_start+10]  # 最初の10行
                logger.debug(f"最終出力の完全成績セクション（先頭10行）: {seiseki_lines}")

        with open(profile_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"プロファイル作成/更新: {profile_file.name}")

        return profile_file

    def get_tanpyo_from_md(self, race_id: str, horse_name: str) -> Optional[str]:
        """
        MD新聞またはJSONから短評を取得

        Args:
            race_id: レースID
            horse_name: 馬名

        Returns:
            短評文字列
        """
        try:
            # レースIDから日付と競馬場を抽出 (202504050911 形式)
            # 2025(year)04(track)05(month)09(day)11(race)
            if len(race_id) == 12:
                year = race_id[:4]
                track_code = race_id[4:6]
                month = race_id[6:8]
                day = race_id[8:10]

                # 競馬場コードから競馬場名をマッピング
                track_map = {
                    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
                    '05': '中山', '06': '東京', '07': '中京', '08': '京都',
                    '09': '阪神', '10': '小倉'
                }
                track_name = track_map.get(track_code, '')

                if track_name:
                    # 新構造でJSONを探す
                    json_path = self.data_root / "races" / year / month / day / "temp" / f"{race_id}.json"

                    # 旧構造でJSONを探す
                    if not json_path.exists():
                        json_path = self.data_root / "organized" / year / month / day / track_name / "temp" / f"{race_id}.json"

                    # さらに旧構造
                    if not json_path.exists():
                        json_path = Path("Z:/KEIBA-CICD/data/organized") / year / month / day / track_name / "temp" / f"{race_id}.json"

                    if json_path.exists():
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                            # syutubaデータから短評を取得
                            if 'syutuba' in data:
                                for entry in data['syutuba']:
                                    if entry.get('horse_name') == horse_name:
                                        return entry.get('tanpyo', '')

                            # entriesデータから短評を取得（統合JSONの場合）
                            if 'entries' in data:
                                for entry in data['entries']:
                                    if entry.get('horse_name') == horse_name:
                                        return entry.get('entry_data', {}).get('tanpyo', '')
        except Exception as e:
            logger.debug(f"短評取得エラー {race_id}: {e}")

        return None

    def get_honshi_from_md(self, race_id: str, horse_name: str) -> Optional[str]:
        """
        MD新聞/統合JSONから本誌印を取得

        Args:
            race_id: レースID
            horse_name: 馬名

        Returns:
            本誌印（例: "◎", "○", "▲", "△" など）
        """
        try:
            if len(race_id) == 12:
                year = race_id[:4]
                track_code = race_id[4:6]
                month = race_id[6:8]
                day = race_id[8:10]

                track_map = {
                    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
                    '05': '中山', '06': '東京', '07': '中京', '08': '京都',
                    '09': '阪神', '10': '小倉'
                }
                track_name = track_map.get(track_code, '')
                if track_name:
                    json_path = self.data_root / "races" / year / month / day / "temp" / f"{race_id}.json"
                    if not json_path.exists():
                        json_path = self.data_root / "organized" / year / month / day / track_name / "temp" / f"{race_id}.json"
                    if not json_path.exists():
                        json_path = Path("Z:/KEIBA-CICD/data/organized") / year / month / day / track_name / "temp" / f"{race_id}.json"

                    if json_path.exists():
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        def pick_honshi(obj: Dict) -> Optional[str]:
                            for k in ['本誌', '本紙', '本誌印', '本紙印', 'honshi', 'honshi_mark']:
                                v = obj.get(k)
                                if v not in (None, ''):
                                    return v
                            return None

                        if 'syutuba' in data:
                            for entry in data['syutuba']:
                                if entry.get('horse_name') == horse_name:
                                    v = pick_honshi(entry)
                                    if v:
                                        return v

                        if 'entries' in data:
                            for entry in data['entries']:
                                if entry.get('horse_name') == horse_name:
                                    v = pick_honshi(entry) or pick_honshi(entry.get('entry_data', {}))
                                    if v:
                                        return v
        except Exception as e:
            logger.debug(f"本誌取得エラー {race_id}: {e}")
        return None

    def _find_honshi_in_races_dir(self, date_str: str, race_name_prefix: str, horse_name: str) -> Optional[str]:
        """
        races ディレクトリ配下（data2/races/YYYY/MM/DD）から本誌印を探索して返す。

        Args:
            date_str: YYYY/MM/DD 形式
            race_name_prefix: レース名の先頭10文字
            horse_name: 馬名
        """
        try:
            if not date_str or len(date_str.split('/')) != 3:
                return None
            year, month, day = date_str.split('/')
            day_dir = self.data_root / 'races' / year / month / day
            if not day_dir.exists():
                # 旧 organized 構造には integrated_*.json が無いことが多いのでスキップ
                return None

            import json as _json
            # integrated_*.json を優先
            for jf in day_dir.glob('integrated_*.json'):
                try:
                    with open(jf, 'r', encoding='utf-8') as f:
                        data = _json.load(f)
                    # entries 形式
                    for entry in data.get('entries', []):
                        if entry.get('horse_name') == horse_name:
                            ed = entry.get('entry_data', {})
                            for k in ['本誌', '本紙', 'honshi', 'honshi_mark', '本誌印', '本紙印']:
                                v = entry.get(k) or ed.get(k)
                                if v not in (None, ''):
                                    return v
                except Exception:
                    continue
            # syutuba JSON
            for jf in (day_dir / 'temp').glob('*.json') if (day_dir / 'temp').exists() else []:
                try:
                    with open(jf, 'r', encoding='utf-8') as f:
                        data = _json.load(f)
                    for entry in data.get('syutuba', []):
                        if entry.get('horse_name') == horse_name:
                            for k in ['本誌', '本紙', 'honshi', 'honshi_mark', '本誌印', '本紙印']:
                                v = entry.get(k)
                                if v not in (None, ''):
                                    return v
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def get_race_detail_from_json(self, race_id: str, horse_name: str) -> Optional[Dict]:
        """
        レースIDから既存JSONを検索して詳細データを取得

        Args:
            race_id: レースID
            horse_name: 馬名

        Returns:
            レース詳細情報
        """
        # seisekiファイルを探す
        seiseki_file = self.temp_dir / f"seiseki_{race_id}.json"
        keibabook_file = Path(f"Z:/KEIBA-CICD/data/keibabook/seiseki_{race_id}.json")

        target_file = None
        if seiseki_file.exists():
            target_file = seiseki_file
        elif keibabook_file.exists():
            target_file = keibabook_file

        if target_file:
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    race_info_base = data.get('race_info', {})
                    race_name = race_info_base.get('race_name', '')

                    # race_nameから日付を抽出
                    import re
                    date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', race_name)
                    race_date = ''
                    if date_match:
                        race_date = f"{date_match.group(1)}/{date_match.group(2).zfill(2)}/{date_match.group(3).zfill(2)}"

                    # 結果から該当馬を探す
                    if 'results' in data:
                        for result in data['results']:
                            if result.get('馬名') == horse_name:
                                # 同義語補完
                                def pick_first(d, keys, default=''):
                                    for k in keys:
                                        v = d.get(k)
                                        if v not in (None, ''):
                                            return v
                                    return default

                                honshi = pick_first(result, ['本誌', '本紙', '本誌印', '本紙印', 'honshi', 'honshi_mark'], '')
                                agari = pick_first(result, ['上がり', '上り3F', '上り', 'last_3f', '後3F'], '')
                                agari_rank = pick_first(result, ['上がり順位', '上り順位', '上り3F順位', 'agari_rank'], '')
                                sunpyou = pick_first(result, ['寸評', '寸評_短評', 'comment'], '')
                                baba = race_info_base.get('turf_condition', '') or race_info_base.get('track_condition', '')

                                return {
                                    '日付': race_date,
                                    '競馬場': race_info_base.get('venue', ''),
                                    'レース名': race_name,
                                    '着順': result.get('着順', ''),
                                    '騎手': result.get('騎手_2', '') or result.get('騎手', ''),
                                    '距離': race_info_base.get('distance', ''),
                                    '馬場': baba,
                                    'タイム': result.get('タイム', ''),
                                    '上がり': agari,
                                    '上がり順位': agari_rank,
                                    '人気': result.get('単人気', ''),
                                    '馬体重': result.get('馬体重', ''),
                                    '増減': result.get('増減', ''),
                                    '通過': result.get('通過順位', ''),
                                    '寸評': sunpyou,
                                    'memo': result.get('memo', ''),
                                    'interview': result.get('interview', ''),
                                    '本誌': honshi,
                                    '短評': self.get_tanpyo_from_md(race_id, horse_name) or '',  # MD新聞から短評を取得
                                    '厩舎コメント': '',  # JSONには含まれていない
                                    'レースID': race_id
                                }
            except Exception as e:
                logger.debug(f"レース詳細取得エラー {race_id}: {e}")

        return None

    def get_horse_past_races(self, horse_name: str, horse_id: str = None) -> List[Dict]:
        """
        既存のJSONデータから馬の過去レース成績を取得

        Args:
            horse_name: 馬名
            horse_id: 馬ID（オプション）

        Returns:
            過去レース成績のリスト
        """
        past_races = []

        # インデックスファイルが存在する場合は使用
        index_file = Path("Z:/KEIBA-CICD/data/horses/horse_race_index.json")
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    horse_index = json.load(f)

                if horse_name in horse_index:
                    past_races = horse_index[horse_name][:10]  # 最新10レース
                    logger.debug(f"インデックスから{len(past_races)}レース取得: {horse_name}")
                    return past_races
            except Exception as e:
                logger.debug(f"インデックス読み込みエラー: {e}")

        # インデックスがない場合は従来の方法（制限付き）
        # tempディレクトリのseiseki_*.jsonファイルを検索
        seiseki_files = list(self.temp_dir.glob("seiseki_*.json"))[:20]  # 最新20ファイルのみ
        logger.debug(f"過去成績検索開始: {horse_name}, ファイル数: {len(seiseki_files)}")

        # keibabookディレクトリも検索
        keibabook_dir = Path("Z:/KEIBA-CICD/data/keibabook")
        if keibabook_dir.exists():
            keibabook_files = list(keibabook_dir.glob("seiseki_*.json"))
            seiseki_files.extend(keibabook_files)
            logger.debug(f"keibabookファイル追加: {len(keibabook_files)}")

        # ファイル名から日付を抽出してソート（新しい順）
        seiseki_files = sorted(seiseki_files, key=lambda x: x.stem, reverse=True)

        # 検索を高速化するため、最大ファイル数を制限
        max_files = 50  # 最新50ファイルまで
        for json_file in seiseki_files[:max_files]:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # 馬名で検索
                    if 'results' in data:
                        race_info_base = data.get('race_info', {})
                        race_name = race_info_base.get('race_name', '')

                        # race_nameから日付を抽出
                        import re
                        date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', race_name)
                        race_date = ''
                        if date_match:
                            race_date = f"{date_match.group(1)}/{date_match.group(2).zfill(2)}/{date_match.group(3).zfill(2)}"

                        for result in data['results']:
                            if result.get('馬名') == horse_name:
                                # レース情報を抽出
                                race_info = {
                                    '日付': race_date,
                                    '競馬場': race_info_base.get('venue', ''),
                                    'レース名': race_name,
                                    '着順': result.get('着順', ''),
                                    '騎手': result.get('騎手_2', '') or result.get('騎手', ''),
                                    '距離': race_info_base.get('distance', ''),
                                    '馬場': race_info_base.get('track_condition', '') or race_info_base.get('turf_condition', ''),
                                    'タイム': result.get('タイム', ''),
                                    '上がり': result.get('上り3F', '') or result.get('上がり', '') or result.get('last_3f', ''),
                                    '上がり順位': result.get('上がり順位', '') or result.get('上り順位', '') or result.get('上り3F順位', '') or result.get('agari_rank', ''),
                                    '寸評': result.get('寸評', '') or result.get('comment', ''),
                                    'メモ': result.get('memo', ''),
                                    'インタビュー': result.get('interview', ''),
                                    '通過順位': result.get('通過順位', ''),
                                    '着差': result.get('着差', ''),
                                    '単勝オッズ': result.get('単勝オッズ', ''),
                                    '人気': result.get('単人気', ''),
                                    '馬体重': result.get('馬体重', ''),
                                    '増減': result.get('増減', ''),
                                    '短評': '',  # 後でMD新聞から取得
                                    'レースID': json_file.stem.replace('seiseki_', '')
                                }
                                # MD新聞から短評を取得
                                tanpyo = self.get_tanpyo_from_md(
                                    json_file.stem.replace('seiseki_', ''),
                                    horse_name
                                )
                                if tanpyo:
                                    race_info['短評'] = tanpyo
                                past_races.append(race_info)
                                # テーブル処理完了

            except Exception as e:
                logger.debug(f"JSONファイル読み込みスキップ {json_file}: {e}")

        # 日付でソート（新しい順）
        past_races.sort(key=lambda x: x.get('レースID', ''), reverse=True)

        return past_races

    def format_basic_races_table(self, past_races: List[Dict]) -> str:
        """
        基本成績をMarkdownテーブル形式にフォーマット

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            Markdownテーブル文字列
        """
        if not past_races:
            logger.warning("過去レースデータが空です")
            return "| データ取得中... | - | - | - | - | - | - | - | - | - | - | - |"

        # 日付降順にソート（YYYY/MM/DD想定のため文字列比較でOK）
        sorted_races = sorted(past_races, key=lambda r: r.get('日付', ''), reverse=True)

        lines = []
        for race in sorted_races[:10]:
            # 馬体重と増減を組み合わせ
            weight_info = race.get('馬体重', '-')
            if weight_info != '-' and race.get('増減'):
                weight_info += f"({race.get('増減')})"

            # 短評を取得（最大20文字）
            tanpyo = race.get('短評', '')
            if tanpyo and len(tanpyo) > 20:
                tanpyo = tanpyo[:20] + '...'

            # レース名とレースクラスを組み合わせ
            race_name = race.get('レース名', '-')[:10]
            race_class = race.get('race_class', '')
            if not race_class or race_class == '-':
                # race_classがない場合、レース名からクラスを抽出
                if '未勝利' in race_name:
                    race_class = '未勝利'
                elif '1勝' in race_name or '１勝' in race_name:
                    race_class = '1勝クラス'
                elif '2勝' in race_name or '２勝' in race_name:
                    race_class = '2勝クラス'
                elif '3勝' in race_name or '３勝' in race_name:
                    race_class = '3勝クラス'
                elif 'G1' in race_name or 'G１' in race_name:
                    race_class = 'G1'
                elif 'G2' in race_name or 'G２' in race_name:
                    race_class = 'G2'
                elif 'G3' in race_name or 'G３' in race_name:
                    race_class = 'G3'
                elif 'オープン' in race_name:
                    race_class = 'OP'
                elif '障害' in race_name:
                    race_class = '障害'
                else:
                    race_class = race_name

            line = f"| {race.get('日付', '-')} | {race.get('競馬場', '-')} | " \
                   f"{race_class} | **{race.get('着順', '-')}** | " \
                   f"{race.get('人気', '-')}人 | {race.get('騎手', '-')} | " \
                   f"{race.get('距離', '-')} | {race.get('馬場', '-')} | " \
                   f"{race.get('タイム', '-')} | {race.get('上がり', '-')} | " \
                   f"{weight_info} | {tanpyo if tanpyo else '-'} |"
            lines.append(line)

        return '\n'.join(lines)

    def format_detail_races_table(self, past_races: List[Dict]) -> str:
        """
        詳細情報をMarkdownテーブル形式にフォーマット

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            Markdownテーブル文字列
        """
        if not past_races:
            return "| データ取得中... | - | - | - | - | - | - |"

        # 日付降順に並べ替え
        sorted_races = sorted(past_races, key=lambda r: r.get('日付', ''), reverse=True)
        lines = []
        for race in sorted_races[:10]:
            # 枠分類を判定（枠番が無ければ 馬番×頭数 で三分割）
            waku = race.get('枠番', '')
            waku_class = '-'
            if waku and str(waku).isdigit():
                waku_num = int(waku)
                if waku_num <= 3:
                    waku_class = f"{waku}(内)"
                elif waku_num <= 6:
                    waku_class = f"{waku}(中)"
                else:
                    waku_class = f"{waku}(外)"
            else:
                # フォールバック: 馬番×頭数
                bano = race.get('馬番', '')
                tousuu_fb = race.get('頭数', '')
                if str(bano).isdigit() and str(tousuu_fb).isdigit():
                    bn = int(bano)
                    tn = int(tousuu_fb)
                    if tn > 0:
                        import math as _math
                        seg = _math.ceil(tn / 3)
                        if bn <= seg:
                            waku_class = f"{bano}(内)"
                        elif bn <= seg * 2:
                            waku_class = f"{bano}(中)"
                        else:
                            waku_class = f"{bano}(外)"
                else:
                    waku_class = waku if waku else '-'

            # 頭数から頭数分類を判定
            tousuu = race.get('頭数', '')
            if tousuu and tousuu != '-' and tousuu.isdigit():
                tousuu_num = int(tousuu)
                if tousuu_num <= 12:
                    tousuu_class = f"{tousuu}(少)"
                elif tousuu_num <= 15:
                    tousuu_class = f"{tousuu}(中)"
                else:
                    tousuu_class = f"{tousuu}(多)"
            else:
                tousuu_class = tousuu if tousuu else '-'

            # 寸評とmemoを結合（短縮）
            review = race.get('寸評', '')
            memo = race.get('memo', '')
            if review and memo:
                comment = f"{review[:20]}..."
            elif review:
                comment = review[:30] if len(review) > 30 else review
            elif memo:
                comment = memo[:30] if len(memo) > 30 else memo
            else:
                comment = '-'

            # 着順の表記を正規化（数字以外を含む場合は数字部分を優先）
            import re as _re
            pos_raw = str(race.get('着順', '-'))
            pos_norm = pos_raw
            if pos_raw and pos_raw != '-':
                m = _re.search(r"\d+", pos_raw)
                pos_norm = m.group(0) if m else pos_raw

            line = f"| {race.get('日付', '-')} | **{pos_norm}** | " \
                   f"{waku_class} | {tousuu_class} | " \
                   f"{race.get('本誌', '-') or '-'} | {race.get('通過', '-') or '-'} | " \
                   f"{comment} |"
            lines.append(line)

        return '\n'.join(lines)

    def format_past_races_table(self, past_races: List[Dict]) -> str:
        """
        過去レース成績をMarkdownテーブル形式にフォーマット

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            Markdownテーブル文字列
        """
        if not past_races:
            logger.warning("過去レースデータが空です")
            return "| データ取得中... | - | - | - | - | - | - | - | - | - |"

        # 日付降順にソート
        sorted_races = sorted(past_races, key=lambda r: r.get('日付', ''), reverse=True)
        lines = []
        # 最新10走（ソート済み）
        for race in sorted_races[:10]:
            # 着順と人気を組み合わせ（着順の表記を正規化）
            import re as _re2
            pos_raw = str(race.get('着順', '-'))
            pos_norm = pos_raw
            if pos_raw and pos_raw != '-':
                m = _re2.search(r"\d+", pos_raw)
                pos_norm = m.group(0) if m else pos_raw
            position_pop = f"**{pos_norm}**"
            if race.get('人気'):
                position_pop += f"/{race.get('人気')}人"

            # 馬体重と増減を組み合わせ
            weight_info = race.get('馬体重', '-')
            if weight_info != '-' and race.get('増減'):
                weight_info += f"({race.get('増減')})"

            line = f"| {race.get('日付', '-')} | {race.get('競馬場', '-')} | " \
                   f"{race.get('レース名', '-')[:10]} | {position_pop} | " \
                   f"{race.get('騎手', '-')} | {race.get('距離', '-')} | " \
                   f"{race.get('馬場', '-')} | {race.get('タイム', '-')} | " \
                   f"{race.get('上がり', '-')} | {weight_info} |"
            lines.append(line)

        return '\n'.join(lines)

    def _extract_agari_rank(self, agari: str, tousuu: str, provided_rank: str = "") -> str:
        """
        上がり表記から上がり順位を推定して返す。
        入力例: "S 33.5", "M 35.7", "H 36.1" など。順位情報がJSONにないため、
        現状は "-" を返し、将来JSONに rank が入ればここで解釈する。
        """
        # 1) JSON側に順位があればそれを優先
        if provided_rank:
            return str(provided_rank)
        # 2) まだ無い場合は推定不可のため"-"
        return "-"

    def format_combined_last10_table(self, past_races: List[Dict]) -> str:
        """
        基本成績と詳細成績を統合した最近10走テーブルを返す（降順）。
        """
        if not past_races:
            return "| データ取得中... | - | - | - | - | - | - | - | - | - | - | - | - | - | - |"

        sorted_races = sorted(past_races, key=lambda r: r.get('日付', ''), reverse=True)
        lines = []
        import re as _re5
        for race in sorted_races[:10]:
            # 着順正規化と人気の結合
            pos_raw = str(race.get('着順', '-'))
            pos_norm = pos_raw
            if pos_raw and pos_raw != '-':
                m = _re5.search(r"\d+", pos_raw)
                pos_norm = m.group(0) if m else pos_raw
            position_pop = f"**{pos_norm}**"
            if race.get('人気'):
                position_pop += f"/{race.get('人気')}人"

            # 馬体重と増減
            weight_info = race.get('馬体重', '-')
            if weight_info != '-' and race.get('増減'):
                weight_info += f"({race.get('増減')})"

            # 枠分類（枠番→無ければ 馬番×頭数 の三分割）
            waku = race.get('枠番', '')
            if waku and str(waku).isdigit():
                w = int(waku)
                if w <= 3:
                    waku_class = f"{waku}(内)"
                elif w <= 6:
                    waku_class = f"{waku}(中)"
                else:
                    waku_class = f"{waku}(外)"
            else:
                bano_fb = race.get('馬番', '')
                tousuu_fb = race.get('頭数', '')
                if str(bano_fb).isdigit() and str(tousuu_fb).isdigit():
                    bn = int(bano_fb)
                    tn = int(tousuu_fb)
                    if tn > 0:
                        import math as _math
                        seg = _math.ceil(tn / 3)
                        if bn <= seg:
                            waku_class = f"{bano_fb}(内)"
                        elif bn <= seg * 2:
                            waku_class = f"{bano_fb}(中)"
                        else:
                            waku_class = f"{bano_fb}(外)"
                else:
                    waku_class = waku if waku else '-'

            # 頭数分類
            tousuu = race.get('頭数', '')
            if tousuu and str(tousuu).isdigit():
                t = int(tousuu)
                if t <= 12:
                    tousuu_class = f"{tousuu}(少)"
                elif t <= 15:
                    tousuu_class = f"{tousuu}(中)"
                else:
                    tousuu_class = f"{tousuu}(多)"
            else:
                tousuu_class = tousuu if tousuu else '-'

            agari = race.get('上がり', '-')
            agari_rank = self._extract_agari_rank(agari, str(tousuu), str(race.get('上がり順位', '')))

            line = f"| {race.get('日付', '-')} | {race.get('競馬場', '-')} | " \
                   f"{race.get('レース名', '-')[:10]} | {position_pop} | " \
                   f"{race.get('騎手', '-')} | {race.get('距離', '-')} | " \
                   f"{race.get('馬場', '-')} | {race.get('タイム', '-')} | {agari} | {agari_rank} | " \
                   f"{waku_class} | {tousuu_class} | {race.get('本誌', '-') or '-'} | " \
                   f"{race.get('通過', '-') or '-'} | {race.get('短評', '-') or '-'} |"
            lines.append(line)

        return "\n".join(lines)

    def _extract_distance_meter(self, distance_field: str) -> Optional[int]:
        """
        距離表記からメートル数を抽出（例: "芝1600", "1800m", "ダ1200m" → 1600/1800/1200）

        Args:
            distance_field: 距離の文字列表現

        Returns:
            整数のメートル数（抽出できなければNone）
        """
        if not distance_field:
            return None
        try:
            import re
            m = re.search(r"(\d{3,4})", str(distance_field))
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return None

    def format_distance_stats_table(self, past_races: List[Dict]) -> str:
        """
        距離別の出走数/勝利/連対/複勝/勝率を集計してMarkdownテーブルを返す
        """
        headers = "| 距離 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 特記事項 |\n|:----:|:------:|:----:|:----:|:----:|:----:|:---------|"
        if not past_races:
            return headers + "\n| 1200m | - | - | - | - | -% | - |\n| 1400m | - | - | - | - | -% | - |\n| 1600m | - | - | - | - | -% | - |\n| 1800m | - | - | - | - | -% | - |\n| 2000m+ | - | - | - | - | -% | - |"

        # バケット: 1200, 1400, 1600, 1800, 2000+
        buckets = [1200, 1400, 1600, 1800]
        stats = {1200: {'t': 0, 'w': 0, 'p': 0, 's': 0},
                 1400: {'t': 0, 'w': 0, 'p': 0, 's': 0},
                 1600: {'t': 0, 'w': 0, 'p': 0, 's': 0},
                 1800: {'t': 0, 'w': 0, 'p': 0, 's': 0},
                 2000: {'t': 0, 'w': 0, 'p': 0, 's': 0}}  # 2000+ は2000キーに集約

        import re as _re3
        for race in past_races:
            dist_val = self._extract_distance_meter(race.get('距離', ''))
            pos = str(race.get('着順', ''))
            # 着順数値化
            pos_num = None
            if pos:
                m = _re3.search(r"\d+", pos)
                if m:
                    try:
                        pos_num = int(m.group(0))
                    except Exception:
                        pos_num = None
            if dist_val is None:
                continue
            bucket_key = 2000 if dist_val >= 2000 else max([b for b in buckets if dist_val >= b], default=1200)
            s = stats[bucket_key]
            s['t'] += 1
            if pos_num == 1:
                s['w'] += 1
            if pos_num is not None and pos_num <= 2:
                s['p'] += 1
            if pos_num is not None and pos_num <= 3:
                s['s'] += 1

        def line_for(label: str, key: int) -> str:
            d = stats[key]
            if d['t'] == 0:
                return f"| {label} | - | - | - | - | -% | - |"
            win_rate = f"{d['w']*100/d['t']:.1f}%"
            return f"| {label} | {d['t']} | {d['w']} | {d['p']} | {d['s']} | {win_rate} | - |"

        lines = [headers,
                 line_for('1200m', 1200),
                 line_for('1400m', 1400),
                 line_for('1600m', 1600),
                 line_for('1800m', 1800),
                 line_for('2000m+', 2000)]
        return "\n".join(lines)

    def format_surface_stats_table(self, past_races: List[Dict]) -> str:
        """
        馬場状態別の出走数/勝利/連対/複勝/勝率を集計してMarkdownテーブルを返す
        """
        headers = "| 馬場 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 特記事項 |\n|:----:|:------:|:----:|:----:|:----:|:----:|:---------|"
        if not past_races:
            return headers + "\n| 良 | - | - | - | - | -% | - |\n| 稍重 | - | - | - | - | -% | - |\n| 重 | - | - | - | - | -% | - |\n| 不良 | - | - | - | - | -% | - |"

        def normalize_baba(value: str) -> str:
            if not value:
                return ''
            v = str(value)
            if '良' in v:
                return '良'
            if '稍' in v or '稍重' in v:
                return '稍重'
            if '不良' in v:
                return '不良'
            if '重' in v:
                return '重'
            return ''

        cats = ['良', '稍重', '重', '不良']
        stats = {c: {'t': 0, 'w': 0, 'p': 0, 's': 0} for c in cats}

        import re as _re4
        for race in past_races:
            baba = normalize_baba(race.get('馬場', ''))
            if not baba:
                continue
            pos = str(race.get('着順', ''))
            pos_num = None
            if pos:
                m = _re4.search(r"\d+", pos)
                if m:
                    try:
                        pos_num = int(m.group(0))
                    except Exception:
                        pos_num = None
            s = stats[baba]
            s['t'] += 1
            if pos_num == 1:
                s['w'] += 1
            if pos_num is not None and pos_num <= 2:
                s['p'] += 1
            if pos_num is not None and pos_num <= 3:
                s['s'] += 1

        def line_for(b: str) -> str:
            d = stats[b]
            if d['t'] == 0:
                return f"| {b} | - | - | - | - | -% | - |"
            win_rate = f"{d['w']*100/d['t']:.1f}%"
            return f"| {b} | {d['t']} | {d['w']} | {d['p']} | {d['s']} | {win_rate} | - |"

        lines = [headers] + [line_for(c) for c in cats]
        return "\n".join(lines)

    def augment_seiseki_table(self, seiseki_table_md: str, past_races: List[Dict], horse_id: str = "", kanzen_data: str = None) -> str:
        """
        シンプルな完全成績テーブルを生成
        
        Args:
            seiseki_table_md: 元のテーブル（Markdown）
            past_races: 過去成績データ
            horse_id: 馬ID
            
        Returns:
            新しいテーブル（Markdown）
        """
        logger.debug(f"augment_seiseki_table開始")
        logger.debug(f"horse_id: {horse_id}")
        logger.debug(f"data_root: {self.data_root}")
        logger.debug(f"data_root存在確認: {self.data_root.exists()}")
        
        # 表示する列の順序
        DISPLAY_COLUMNS = [
            'コメント', '本誌', '日付', '競馬場', 'レース', 'クラス', '距離', '馬場', '重量', '騎手', 
            '頭数', '馬番', '馬体重', '着順/人気', '枠', '頭数(区分)', 
            'タイム', 'タイム差', 'ペース後3F', '通過順位', '4角位置', '寸評'
        ]
        
        try:
            lines = seiseki_table_md.splitlines()
            if not lines:
                return seiseki_table_md

            # ヘッダー行を探す
            header_line = None
            data_start_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('|') and ('年月日' in line or '日付' in line):
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
                if '年月日' in header_clean or '日付' in header_clean:
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
            def get_integrated_data(race_id: str, horse_id: str, race_date: str = None) -> Dict:
                """integrated_XXXXX.jsonから対象馬のデータを取得"""
                try:
                    if not race_id or not horse_id:
                        logger.debug(f"race_idまたはhorse_idが空: race_id={race_id}, horse_id={horse_id}")
                        return {}
                    
                    # レース開催日からパスを構築
                    if race_date:
                        # YYYY/MM/DD形式からパスを構築
                        date_parts = race_date.split('/')
                        if len(date_parts) == 3:
                            year, month, day = date_parts[0], date_parts[1].zfill(2), date_parts[2].zfill(2)
                        else:
                            logger.debug(f"日付形式が不正: {race_date}")
                            return {}
                    else:
                        # レースIDから日付を抽出（フォールバック）
                        if len(race_id) == 12:
                            year = race_id[:4]
                            month = race_id[4:6]
                            day = race_id[6:8]
                        else:
                            logger.debug(f"race_idの長さが不正: {race_id} (長さ: {len(race_id)})")
                            return {}
                    
                    # パス構築
                    json_path = self.data_root / "races" / year / month / day / "temp" / f"integrated_{race_id}.json"
                    logger.debug(f"JSONパス構築: {json_path}")
                    logger.debug(f"race_id: {race_id}, race_date: {race_date}, year: {year}, month: {month}, day: {day}")
                    
                    # ディレクトリの存在確認
                    day_dir = self.data_root / "races" / year / month / day
                    temp_dir = day_dir / "temp"
                    logger.debug(f"日付ディレクトリ存在確認: {day_dir} -> {day_dir.exists()}")
                    logger.debug(f"tempディレクトリ存在確認: {temp_dir} -> {temp_dir.exists()}")
                    
                    if temp_dir.exists():
                        # tempディレクトリ内のファイル一覧を確認
                        files_in_dir = list(temp_dir.glob("integrated_*.json"))
                        logger.debug(f"temp内integrated_*.jsonファイル一覧: {[f.name for f in files_in_dir]}")
                    
                    if json_path.exists():
                        logger.debug(f"JSONファイル発見: {json_path}")
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                        entries = data.get('entries', [])
                        logger.debug(f"entries数: {len(entries)}")
                        
                        for i, entry in enumerate(entries):
                            entry_horse_id = str(entry.get('horse_id', ''))
                            logger.debug(f"entry[{i}] horse_id: {entry_horse_id}, target: {horse_id}")
                            if entry_horse_id == str(horse_id):
                                entry_data = entry.get('entry_data', {})
                                result_data = entry.get('result', {})
                                raw_data = result_data.get('raw_data', {}) if result_data else {}
                                
                                result = {
                                    'short_comment': entry_data.get('short_comment', ''),
                                    'honshi_mark': entry_data.get('honshi_mark', ''),
                                    '通過順位': raw_data.get('通過順位', ''),
                                    '寸評': raw_data.get('寸評', ''),
                                    '4角位置': raw_data.get('4角位置', '')
                                }
                                logger.debug(f"integrated_データ取得成功: {result}")
                                return result
                        
                        logger.debug(f"対象馬ID {horse_id} が見つかりませんでした")
                    else:
                        logger.debug(f"JSONファイルが存在しません: {json_path}")
                        
                except Exception as e:
                    logger.debug(f"integrated_データ取得エラー {race_id}: {e}")
                    import traceback
                    logger.debug(f"エラー詳細: {traceback.format_exc()}")
                return {}

            # 過去成績のマップを作成
            match_map = {}
            logger.debug(f"past_races数: {len(past_races or [])}")
            for i, r in enumerate(past_races or []):
                logger.debug(f"past_races[{i}]: {r}")
                key = (str(r.get('日付', '')), str(r.get('レース名', ''))[:10])
                logger.debug(f"マッチキー: {key}")
                
                race_id = r.get('レースID', '')
                race_date = r.get('日付', '')
                logger.debug(f"レースID: {race_id}, 日付: {race_date}")
                integrated_data = get_integrated_data(race_id, horse_id, race_date) if race_id else {}
                
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
                    '通過順位': integrated_data.get('通過順位', ''),
                    '4角位置': integrated_data.get('4角位置', ''),
                }

            # 新しいテーブルを構築
            new_lines = []
            
            # ヘッダー行
            new_headers = []
            for col in DISPLAY_COLUMNS:
                if col in column_mapping:
                    # 年月日を日付に変更、ゲ｜トを馬番に変更
                    header_text = original_headers[column_mapping[col]]
                    if '年月日' in header_text:
                        header_text = header_text.replace('年月日', '日付')
                    if 'ゲ｜ト' in header_text:
                        header_text = header_text.replace('ゲ｜ト', '馬番')
                    new_headers.append(header_text)
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
                info = match_map.get(key, {'honshi': '-', 'waku': '-', 'tousuu': '-', 'short_comment': '', '寸評': '', '通過順位': '', '4角位置': ''})
                
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
                    elif col == '着順/人気':
                        # 着順と人気を結合
                        chaku_idx = None
                        ninki_idx = None
                        for i, header in enumerate(original_headers):
                            if '着順' in header and '人気' not in header:
                                chaku_idx = i
                            elif '人気' in header and '着順' not in header:
                                ninki_idx = i
                        
                        chaku_val = original_cells[chaku_idx] if chaku_idx is not None and chaku_idx < len(original_cells) else ''
                        ninki_val = original_cells[ninki_idx] if ninki_idx is not None and ninki_idx < len(original_cells) else ''
                        
                        # 着順の正規化（数字部分を抽出）
                        import re
                        chaku_match = re.search(r'\d+', chaku_val) if chaku_val else None
                        chaku_num = chaku_match.group(0) if chaku_match else chaku_val
                        
                        # 人気の正規化（数字部分を抽出）
                        ninki_match = re.search(r'\d+', ninki_val) if ninki_val else None
                        ninki_num = ninki_match.group(0) if ninki_match else ninki_val
                        
                        # 結合
                        if chaku_num and ninki_num:
                            combined = f"**{chaku_num}**/{ninki_num}人"
                        elif chaku_num:
                            combined = f"**{chaku_num}**"
                        else:
                            combined = '-'
                        
                        new_cells.append(combined)
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
                        elif col == '通過順位':
                            new_cells.append(info.get('通過順位', ''))
                        elif col == '4角位置':
                            new_cells.append(info.get('4角位置', ''))
                        else:
                            new_cells.append('-')
                
                new_lines.append('| ' + ' | '.join(new_cells) + ' |')

            result = '\n'.join(new_lines)
            logger.debug(f"augment_seiseki_table完了: 出力テーブル行数={len(result.splitlines())}")
            return result
            
        except Exception as e:
            logger.error(f"augment_seiseki_tableエラー: {e}")
            logger.debug(f"エラー詳細: {type(e).__name__}: {str(e)}")
            import traceback
            logger.debug(f"トレースバック: {traceback.format_exc()}")
            return seiseki_table_md

    def format_condition_stats_table(self, past_races: List[Dict]) -> str:
        """
        条件別成績を集計してテーブル形式にフォーマット

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            Markdownテーブル文字列
        """
        # 集計用辞書
        stats = {
            '内枠': {'total': 0, 'win': 0, 'place': 0, 'show': 0},
            '中枠': {'total': 0, 'win': 0, 'place': 0, 'show': 0},
            '外枠': {'total': 0, 'win': 0, 'place': 0, 'show': 0},
            '少頭数': {'total': 0, 'win': 0, 'place': 0, 'show': 0},
            '中頭数': {'total': 0, 'win': 0, 'place': 0, 'show': 0},
            '多頭数': {'total': 0, 'win': 0, 'place': 0, 'show': 0},
        }

        for race in past_races:
            position = race.get('着順', '')
            if not position or not position.isdigit():
                continue
            pos = int(position)

            # 枠番による集計
            waku = race.get('枠番', '')
            if waku and waku.isdigit():
                waku_num = int(waku)
                if waku_num <= 3:
                    key = '内枠'
                elif waku_num <= 6:
                    key = '中枠'
                else:
                    key = '外枠'

                stats[key]['total'] += 1
                if pos == 1:
                    stats[key]['win'] += 1
                if pos <= 2:
                    stats[key]['place'] += 1
                if pos <= 3:
                    stats[key]['show'] += 1

            # 頭数による集計
            tousuu = race.get('頭数', '')
            if tousuu and tousuu.isdigit():
                tousuu_num = int(tousuu)
                if tousuu_num <= 12:
                    key = '少頭数'
                elif tousuu_num <= 15:
                    key = '中頭数'
                else:
                    key = '多頭数'

                stats[key]['total'] += 1
                if pos == 1:
                    stats[key]['win'] += 1
                if pos <= 2:
                    stats[key]['place'] += 1
                if pos <= 3:
                    stats[key]['show'] += 1

        # テーブル作成
        lines = [
            "| 条件 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 連対率 | 複勝率 |",
            "|:----:|:------:|:----:|:----:|:----:|:----:|:------:|:------:|"
        ]

        for condition, data in stats.items():
            if data['total'] > 0:
                win_rate = f"{data['win']*100/data['total']:.1f}"
                place_rate = f"{data['place']*100/data['total']:.1f}"
                show_rate = f"{data['show']*100/data['total']:.1f}"
                line = f"| {condition} | {data['total']} | {data['win']} | " \
                       f"{data['place']} | {data['show']} | " \
                       f"{win_rate}% | {place_rate}% | {show_rate}% |"
                lines.append(line)

        return '\n'.join(lines)

    def format_jockey_comments_table(self, past_races: List[Dict]) -> str:
        """
        騎手コメントをテーブル形式にフォーマット

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            Markdownテーブル文字列
        """
        lines = []
        for race in past_races:
            if race.get('interview'):
                interview = race.get('interview', '')
                # 長いコメントは短縮
                if len(interview) > 80:
                    interview = interview[:80] + '...'

                line = f"| {race.get('日付', '-')} | {race.get('レース名', '-')[:10]} | " \
                       f"**{race.get('着順', '-')}** | {race.get('騎手', '-')} | " \
                       f"{interview} |"
                lines.append(line)

        return '\n'.join(lines) if lines else ""

    def format_comments_section(self, past_races: List[Dict]) -> str:
        """
        厩舎コメントやレース後コメントをフォーマット

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            コメントセクションのMarkdown文字列
        """
        sections = []

        # 厩舎コメント
        stable_comments = []
        for race in past_races[:5]:
            if race.get('厩舎コメント'):
                date = race.get('日付', '')
                race_name = race.get('レース名', '')
                comment = race.get('厩舎コメント', '')
                stable_comments.append(f"- **{date} {race_name}**: {comment}")

        if stable_comments:
            sections.append("### 🏠 厩舎コメント")
            sections.extend(stable_comments)
            sections.append("")

        # 騎手インタビュー
        interviews = []
        for race in past_races[:3]:
            if race.get('interview'):
                date = race.get('日付', '')
                race_name = race.get('レース名', '')
                jockey = race.get('騎手', '')
                interview = race.get('interview', '')
                interviews.append(f"- **{date} {race_name}** ({jockey}): {interview}")

        if interviews:
            sections.append("### 🏇 騎手コメント")
            sections.extend(interviews)
            sections.append("")

        # レース寸評
        reviews = []
        for race in past_races[:5]:
            if race.get('寸評') or race.get('memo'):
                date = race.get('日付', '')
                race_name = race.get('レース名', '')
                position = race.get('着順', '')
                review = race.get('寸評', '')
                memo = race.get('memo', '')
                text = f"- **{date} {race_name}** ({position}着)"
                if review:
                    text += f": {review}"
                if memo:
                    text += f" / {memo}"
                reviews.append(text)

        if reviews:
            sections.append("### 📋 レース寸評")
            sections.extend(reviews)

        if sections:
            return '\n'.join(sections)
        return ""

    def analyze_horse_features(self, past_races: List[Dict]) -> Dict:
        """
        過去レースから馬の特徴を分析

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            特徴分析結果の辞書
        """
        features = {
            'strengths': [],
            'weaknesses': [],
            'favorable_conditions': []
        }

        if not past_races:
            return features

        # 勝利パターンの分析
        wins = [r for r in past_races if r.get('着順') == '1']
        if wins:
            # 勝利時の特徴
            for win in wins[:3]:  # 最近の勝利3つ
                if win.get('寸評'):
                    features['strengths'].append(f"勝利時の特徴: {win['寸評']}")
                if win.get('通過順位'):
                    features['favorable_conditions'].append(f"通過{win['通過順位']}での勝利実績")

        # 着順パターンの分析
        recent_5 = past_races[:5]
        good_results = [r for r in recent_5 if r.get('着順', '99') in ['1', '2', '3']]
        if len(good_results) >= 3:
            features['strengths'].append("安定した上位入線（最近5走で3回以上入着）")

        # 人気と着順の関係
        for race in past_races[:10]:
            if race.get('人気') and race.get('着順'):
                try:
                    pop = int(race['人気'])
                    result = int(race['着順'])
                    if pop >= 5 and result <= 3:
                        features['strengths'].append(f"人気薄での好走実績（{pop}番人気→{result}着）")
                        break
                except:
                    pass

        return features

    def format_comments_section(self, past_races: List[Dict]) -> str:
        """
        過去レースのコメント・寸評をフォーマット

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            フォーマット済みコメントセクション
        """
        comments = []

        for race in past_races[:5]:  # 最近5走
            if not race.get('日付'):
                continue

            race_comments = []

            # 基本情報
            header = f"### {race.get('日付', '')} {race.get('競馬場', '')} {race.get('着順', '')}着"
            race_comments.append(header)

            # 各種コメント
            if race.get('寸評'):
                race_comments.append(f"- **寸評**: {race['寸評']}")
            if race.get('メモ'):
                race_comments.append(f"- **メモ**: {race['メモ']}")
            if race.get('インタビュー'):
                race_comments.append(f"- **騎手コメント**: {race['インタビュー']}")

            # 通過順位と上がりタイム
            details = []
            if race.get('通過順位'):
                details.append(f"通過{race['通過順位']}")
            if race.get('上がり'):
                details.append(f"上がり{race['上がり']}")
            if details:
                race_comments.append(f"- **レース内容**: {' / '.join(details)}")

            if len(race_comments) > 1:  # ヘッダー以外にコメントがある場合
                comments.extend(race_comments)
                comments.append("")

        return '\n'.join(comments)

    def calculate_race_statistics(self, past_races: List[Dict]) -> Dict:
        """
        過去レース成績から統計を計算

        Args:
            past_races: 過去レース成績のリスト

        Returns:
            統計情報の辞書
        """
        stats = {
            'total': {'1着': 0, '2着': 0, '3着': 0, '着外': 0, '勝率': 0, '連対率': 0, '複勝率': 0},
            'turf': {'1着': 0, '2着': 0, '3着': 0, '着外': 0, '勝率': 0, '連対率': 0, '複勝率': 0},
            'dirt': {'1着': 0, '2着': 0, '3着': 0, '着外': 0, '勝率': 0, '連対率': 0, '複勝率': 0}
        }

        turf_count = 0
        dirt_count = 0

        for race in past_races:
            position = race.get('着順', '')
            distance = race.get('距離', '')

            # 着順をカウント
            if position == '1':
                stats['total']['1着'] += 1
                if '芝' in distance:
                    stats['turf']['1着'] += 1
                    turf_count += 1
                elif 'ダ' in distance:
                    stats['dirt']['1着'] += 1
                    dirt_count += 1
            elif position == '2':
                stats['total']['2着'] += 1
                if '芝' in distance:
                    stats['turf']['2着'] += 1
                    turf_count += 1
                elif 'ダ' in distance:
                    stats['dirt']['2着'] += 1
                    dirt_count += 1
            elif position == '3':
                stats['total']['3着'] += 1
                if '芝' in distance:
                    stats['turf']['3着'] += 1
                    turf_count += 1
                elif 'ダ' in distance:
                    stats['dirt']['3着'] += 1
                    dirt_count += 1
            elif position:
                stats['total']['着外'] += 1
                if '芝' in distance:
                    stats['turf']['着外'] += 1
                    turf_count += 1
                elif 'ダ' in distance:
                    stats['dirt']['着外'] += 1
                    dirt_count += 1

        # 率を計算
        total_count = len(past_races)
        if total_count > 0:
            stats['total']['勝率'] = round(stats['total']['1着'] / total_count * 100, 1)
            stats['total']['連対率'] = round((stats['total']['1着'] + stats['total']['2着']) / total_count * 100, 1)
            stats['total']['複勝率'] = round((stats['total']['1着'] + stats['total']['2着'] + stats['total']['3着']) / total_count * 100, 1)

        if turf_count > 0:
            stats['turf']['勝率'] = round(stats['turf']['1着'] / turf_count * 100, 1)
            stats['turf']['連対率'] = round((stats['turf']['1着'] + stats['turf']['2着']) / turf_count * 100, 1)
            stats['turf']['複勝率'] = round((stats['turf']['1着'] + stats['turf']['2着'] + stats['turf']['3着']) / turf_count * 100, 1)

        if dirt_count > 0:
            stats['dirt']['勝率'] = round(stats['dirt']['1着'] / dirt_count * 100, 1)
            stats['dirt']['連対率'] = round((stats['dirt']['1着'] + stats['dirt']['2着']) / dirt_count * 100, 1)
            stats['dirt']['複勝率'] = round((stats['dirt']['1着'] + stats['dirt']['2着'] + stats['dirt']['3着']) / dirt_count * 100, 1)

        return stats

    def update_win5_horses(self, date: str) -> Dict[str, List]:
        """
        指定日のWIN5対象馬のプロファイルを更新

        Args:
            date: 日付（YYYY/MM/DD形式）

        Returns:
            レースごとの処理結果
        """
        # 日付をパス形式に変換
        date_parts = date.replace('/', '/').split('/')
        year, month, day = date_parts[0], date_parts[1].zfill(2), date_parts[2].zfill(2)

        # WIN5対象レース（固定）
        win5_races = [
            ('阪神', '202504010409'),  # 阪神9R
            ('中山', '202504050410'),  # 中山10R
            ('阪神', '202504010410'),  # 阪神10R
            ('中山', '202504050411'),  # 中山11R
            ('阪神', '202504010411'),  # 阪神11R
        ]

        results = {}

        for track, race_id in win5_races:
            race_file = self.organized_dir / year / month / day / track / f"{race_id}.md"

            if race_file.exists():
                horses = self.extract_horses_from_race(race_file)
                race_results = []

                for horse_id, horse_name, horse_data in horses:
                    try:
                        profile_path = self.create_horse_profile(horse_id, horse_name, horse_data)
                        race_results.append({
                            'horse_id': horse_id,
                            'horse_name': horse_name,
                            'profile': str(profile_path)
                        })
                    except Exception as e:
                        logger.error(f"プロファイル作成エラー {horse_id} {horse_name}: {e}")

                results[f"{track}_{race_id}"] = race_results
                logger.info(f"{track} {race_id}: {len(race_results)}頭のプロファイル作成")
            else:
                logger.warning(f"レースファイルが見つかりません: {race_file}")
                results[f"{track}_{race_id}"] = []

        return results


# コマンドライン実行用
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="馬プロファイル管理")
    parser.add_argument("--date", help="対象日付 (YYYY/MM/DD)", default="2025/09/14")
    parser.add_argument("--horse-id", help="特定の馬ID")
    parser.add_argument("--with-history", action="store_true", help="過去成績を含む")
    parser.add_argument("--use-web-fetch", action="store_true", help="WebからレースIDを取得")
    parser.add_argument("--all", action="store_true", help="全馬を対象")

    args = parser.parse_args()
    manager = HorseProfileManager()

    if args.horse_id:
        # 特定の馬のプロファイルを生成
        print(f"馬ID {args.horse_id} のプロファイルを生成")

        # 馬名を取得（既存ファイルから）
        profile_dir = Path("Z:/KEIBA-CICD/data/horses/profiles")
        horse_name = None
        for f in profile_dir.glob(f"{args.horse_id}_*.md"):
            horse_name = f.stem.split('_', 1)[1]
            break

        if not horse_name:
            horse_name = "馬名不明"

        profile_path = manager.create_horse_profile(
            args.horse_id,
            horse_name,
            include_history=args.with_history,
            use_web_fetch=args.use_web_fetch
        )
        print(f"完了: {profile_path}")
    elif args.all:
        # 全馬を対象
        print(f"{args.date} の全馬プロファイルを生成")
        results = manager.update_all_horses(
            args.date,
            include_history=args.with_history,
            use_web_fetch=args.use_web_fetch
        )
        total_horses = sum(len(v) for v in results.values())
        print(f"完了: {total_horses}頭のプロファイルを生成しました")
    else:
        # WIN5対象馬のみ
        print(f"WIN5対象馬のプロファイルを生成: {args.date}")
        results = manager.update_win5_horses(args.date)
        total_horses = sum(len(v) for v in results.values())
        print(f"完了: {total_horses}頭のプロファイルを生成しました")

    print(f"保存先: Z:/KEIBA-CICD/data/horses/profiles/")
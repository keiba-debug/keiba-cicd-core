#!/usr/bin/env python3
"""



1
"""

import os
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from ..utils.config import Config
from ..batch.core.common import get_json_file_path, get_race_ids_file_path

# JRA-VANライブラリのパスを追加（調教師ID変換用）
TARGET_DIR = Path(__file__).resolve().parents[3] / "KeibaCICD.TARGET"
if TARGET_DIR.exists():
    sys.path.insert(0, str(TARGET_DIR))
    try:
        from common.jravan import get_trainer_info
    except ImportError:
        get_trainer_info = None
else:
    get_trainer_info = None


@dataclass
class DataSourceStatus:
    """"""
    seiseki: str = ""
    syutuba: str = ""
    cyokyo: str = ""
    danwa: str = ""
    nittei: str = ""
    syoin: str = ""
    paddok: str = ""


@dataclass
class RaceMetadata:
    """"""
    race_id: str
    data_version: str = "2.0"
    created_at: str = ""
    updated_at: str = ""
    data_sources: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


class RaceDataIntegrator:
    """
    
    
    
    1JSON
    """
    
    def __init__(self, use_organized_dir: bool = True):
        """"""
        self.logger = logging.getLogger(__name__)
        self.data_root = os.getenv('KEIBA_DATA_ROOT_DIR', './data')  # keibabookフォルダを使わない
        self.use_organized_dir = use_organized_dir

        # race_idと実際の開催日のマッピング
        self.actual_date_map = {}
        self.venue_name_map = {}
        self.race_id_to_date_map = {}  # 処理中の日付マッピング
        self.load_actual_dates()

    # 内部ユーティリティ: 全角数字などを安全に数値化
    @staticmethod
    def _to_int_safe(value) -> Optional[int]:
        if value is None:
            return None
        try:
            s = str(value)
            # 全角→半角
            z2h = str.maketrans('０１２３４５６７８９', '0123456789')
            s = s.translate(z2h)
            # 数字以外を除去
            import re
            digits = ''.join(re.findall(r'\d+', s))
            return int(digits) if digits else None
        except Exception:
            return None
    
    def load_actual_dates(self):
        """
        race_idsフォルダから実際の開催日マッピングを読み込む
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
                        # 開催名から競馬場名を取得（フルネームで）
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
                    self.logger.warning(f"Failed to load {file_path}: {e}")
        
    def _load_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        JSON
        
        Args:
            file_path: 
            
        Returns:
            Optional[Dict[str, Any]]: JSONNone
        """
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"JSON: {file_path}, {e}")
            return None
    
    def _load_race_data(self, race_id: str, data_type: str) -> Optional[Dict[str, Any]]:
        """


        Args:
            race_id: ID
            data_type: seiseki, syutuba, cyokyo, danwa, syoin, paddok

        Returns:
            Optional[Dict[str, Any]]: None
        """
        # 実際の開催日を取得（処理中のマッピングまたは保存済みマッピング）
        actual_date = self.race_id_to_date_map.get(race_id) or self.actual_date_map.get(race_id)
        file_path = get_json_file_path(data_type, race_id, actual_date)
        return self._load_json_file(file_path)
    
    def _extract_race_info(self, race_id: str, syutuba_data: Dict, race_ids_data: Dict = None) -> Dict[str, Any]:
        """
        
        
        Args:
            race_id: ID
            syutuba_data: 
            race_ids_data: race_ids JSONデータ（発走時刻含む）
            
        Returns:
            Dict[str, Any]: 
        """
        # 実際の開催日を使用
        if race_id in self.actual_date_map:
            date_str = self.actual_date_map[race_id]
        else:
            date_str = race_id[:8]
        
        # 競馬場情報
        venue_code = race_id[8:10]
        race_number = int(race_id[10:12])
        
        # 実際の競馬場名を使用
        if race_id in self.venue_name_map:
            venue = self.venue_name_map[race_id]
        else:
            venue_map = {
                '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
                '05': '東京', '06': '中山', '07': '中京', '08': '京都',
                '09': '阪神', '10': '小倉'
            }
            venue = venue_map.get(venue_code, f'{venue_code}')
        
        # 発走時刻を取得（簡易実装）
        from ..utils.post_time_mapping import get_estimated_post_time
        post_time = get_estimated_post_time(race_number)
        
        # 
        race_info = {
            'date': f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}",
            'venue': venue,
            'race_number': race_number,
            'race_name': '',
            'grade': '',
            'distance': 0,
            'track': '',
            'direction': '',
            'weather': '',
            'track_condition': '',
            'post_time': post_time  # 発走時刻を追加
        }
        
        # 
        if syutuba_data and 'race_info' in syutuba_data:
            info = syutuba_data['race_info']
            race_info.update({
                'race_name': info.get('race_name', ''),
                'grade': self._extract_grade(info.get('race_name', '')),
                'distance': info.get('distance', 0),
                'track': info.get('track', info.get('track_type', '')),
                'direction': info.get('direction', ''),
                'weather': info.get('weather', ''),
                'track_condition': info.get('track_condition', ''),
                'race_condition': info.get('race_condition', '')  # レース条件も追加
            })
        
        # race_ids JSONから発走時刻を取得
        if race_ids_data:
            for venue, races in race_ids_data.get('kaisai_data', {}).items():
                for race in races:
                    if isinstance(race, dict) and race.get('race_id') == race_id:
                        # 発走時刻を追加（存在する場合のみ）
                        if race.get('start_time'):
                            race_info['start_time'] = race['start_time']
                        if race.get('start_at'):
                            race_info['start_at'] = race['start_at']
                        break
        
        return race_info
    
    def _extract_grade(self, race_name: str) -> str:
        """
        
        
        Args:
            race_name: 
            
        Returns:
            str: G1, G2, G3, OP, 
        """
        if 'GI' in race_name or 'G1' in race_name:
            return 'G1'
        elif 'GII' in race_name or 'G2' in race_name:
            return 'G2'
        elif 'GIII' in race_name or 'G3' in race_name:
            return 'G3'
        elif '' in race_name or 'OP' in race_name:
            return 'OP'
        elif '' in race_name:
            return ''
        elif '' in race_name:
            return ''
        elif '1' in race_name:
            return '1'
        elif '2' in race_name:
            return '2'
        elif '3' in race_name:
            return '3'
        else:
            return ''
    
    def _merge_horse_data(
        self,
        horse_number: int,
        syutuba_entry: Dict,
        cyokyo_data: Optional[Dict],
        danwa_data: Optional[Dict],
        seiseki_data: Optional[Dict],
        syoin_data: Optional[Dict] = None,
        paddok_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        
        
        Args:
            horse_number: 
            syutuba_entry: 
            cyokyo_data: 
            danwa_data: 
            seiseki_data: 
            
        Returns:
            Dict[str, Any]: 
        """
        # shutsubaデータのキー名マッピング（日本語キー対応）
        horse_data = {
            'horse_number': horse_number,
            'horse_name': syutuba_entry.get('馬 名') or syutuba_entry.get('馬名_clean') or syutuba_entry.get('horse_name', ''),
            'horse_id': syutuba_entry.get('umacd') or syutuba_entry.get('horse_id', ''),
            
            # 
            'entry_data': {
                'weight': syutuba_entry.get('重量') or syutuba_entry.get('weight', 0),
                'weight_diff': syutuba_entry.get('増減') or syutuba_entry.get('weight_diff', ''),
                'jockey': syutuba_entry.get('騎手') or syutuba_entry.get('騎\u2003手') or syutuba_entry.get('騎 手') or syutuba_entry.get('jockey', ''),
                'trainer': syutuba_entry.get('厩舎') or syutuba_entry.get('厩\u2003舎') or syutuba_entry.get('厩 舎') or syutuba_entry.get('trainer', ''),
                # 調教師ID関連（追加）
                'trainer_id': syutuba_entry.get('trainer_id') or None,
                'trainer_link': syutuba_entry.get('trainer_link') or None,
                'trainer_tozai': None,  # 後でJRA-VANから取得
                'owner': syutuba_entry.get('owner', ''),
                'short_comment': syutuba_entry.get('短評') or syutuba_entry.get('短\u2003評') or syutuba_entry.get('短 評') or syutuba_entry.get('short_comment', ''),
                'odds': syutuba_entry.get('単勝') or syutuba_entry.get('odds', ''),
                'odds_rank': syutuba_entry.get('人気') or syutuba_entry.get('odds_rank', 0),
                'ai_index': syutuba_entry.get('AI指数', '-'),
                'ai_rank': syutuba_entry.get('AI指数ランク', ''),
                'popularity_index': syutuba_entry.get('人気指数', ''),
                'age': syutuba_entry.get('性齢') or syutuba_entry.get('age', ''),
                'sex': syutuba_entry.get('sex', ''),
                'waku': syutuba_entry.get('枠番') or syutuba_entry.get('waku', ''),
                'rating': syutuba_entry.get('レイティング') or syutuba_entry.get('rating', ''),
                'horse_weight': syutuba_entry.get('馬体重(kg)') or syutuba_entry.get('horse_weight', ''),
                'father': syutuba_entry.get('father', ''),
                'mother': syutuba_entry.get('mother', ''),
                'mother_father': syutuba_entry.get('mother_father', ''),
                # 本誌見解と印ポイント
                'honshi_mark': syutuba_entry.get('本誌印') or syutuba_entry.get('本誌') or syutuba_entry.get('本紙', ''),
                'mark_point': syutuba_entry.get('本誌印ポイント', 0),
                # 追加: 複数者の印と総合ポイント
                'marks_by_person': syutuba_entry.get('marks_by_person', {}),
                'aggregate_mark_point': syutuba_entry.get('総合印ポイント', syutuba_entry.get('本誌印ポイント', 0))
            }
        }
        
        # 調教師IDから所属情報を取得（JRA-VANライブラリが利用可能な場合）
        trainer_id = horse_data['entry_data'].get('trainer_id')
        if trainer_id and get_trainer_info:
            try:
                trainer_info = get_trainer_info(trainer_id)
                if trainer_info:
                    if trainer_info.get('tozai'):
                        horse_data['entry_data']['trainer_tozai'] = trainer_info['tozai']
                    # コメントデータも追加（あれば）
                    comment = trainer_info.get('comment')
                    if comment:
                        # 文字化け文字を除去
                        comment = comment.replace('\ufffd', '').replace('�', '')
                        import re
                        comment = re.sub(r'�[A-Za-z0-9@]', '', comment)
                        horse_data['entry_data']['trainer_comment'] = comment
                        self.logger.debug(f"調教師コメント設定: {trainer_id} -> {comment[:50]}...")
                    else:
                        self.logger.debug(f"調教師コメントなし: trainer_id={trainer_id}")
                else:
                    self.logger.debug(f"調教師情報が見つかりません: trainer_id={trainer_id}")
            except Exception as e:
                # エラーが発生しても処理を続行
                self.logger.warning(f"調教師情報取得エラー (trainer_id={trainer_id}): {e}")
                import traceback
                self.logger.debug(traceback.format_exc())
        elif trainer_id and not get_trainer_info:
            self.logger.debug(f"get_trainer_infoが利用できません: trainer_id={trainer_id}")
        elif not trainer_id:
            self.logger.debug(f"trainer_idが設定されていません: 馬名={horse_data.get('horse_name', '')}")
        
        # 
        if cyokyo_data:
            if 'horses' in cyokyo_data:
                # 旧来の構造 {'horses': [...]} に対応
                for horse in cyokyo_data['horses']:
                    num = RaceDataIntegrator._to_int_safe(horse.get('horse_number') or horse.get('馬番'))
                    if num == horse_number:
                        horse_data['training_data'] = {
                            'last_training': horse.get('last_training', ''),
                            'training_times': horse.get('training_times', []),
                            'training_course': horse.get('training_course', ''),
                            'evaluation': horse.get('evaluation', ''),
                            'trainer_comment': horse.get('comment', ''),
                            'attack_explanation': horse.get('attack_explanation', ''),
                            'short_review': horse.get('short_review', ''),
                            'training_load': horse.get('training_load', ''),
                            'training_rank': horse.get('rank', ''),
                            'training_arrow': horse.get('training_arrow', '')  # 調教矢印を追加
                        }
                        break
                else:
                    horse_data['training_data'] = None
            elif 'training_data' in cyokyo_data and isinstance(cyokyo_data['training_data'], list):
                # 新構造 {'training_data': [...]}（CyokyoParserのフォーマット）に対応
                for item in cyokyo_data['training_data']:
                    # 馬番キーのバリエーションに対応
                    item_horse_no = RaceDataIntegrator._to_int_safe(item.get('horse_number') or item.get('馬番'))
                    if item_horse_no == horse_number:
                        horse_data['training_data'] = {
                            'last_training': item.get('last_training') or item.get('調教日', ''),
                            'training_times': item.get('training_times', []),
                            'training_course': item.get('training_course') or item.get('コース', ''),
                            'evaluation': item.get('evaluation') or item.get('評価', ''),
                            # 攻め解説と短評を別々に保持
                            'trainer_comment': item.get('trainer_comment') or item.get('comment', ''),
                            'attack_explanation': item.get('attack_explanation', ''),
                            'short_review': item.get('short_review', ''),
                            'training_load': item.get('training_load') or item.get('負荷', ''),
                            'training_rank': item.get('training_rank') or item.get('順位', ''),
                            'training_arrow': item.get('training_arrow', '')  # 調教矢印を追加
                        }
                        break
                else:
                    horse_data['training_data'] = None
            else:
                horse_data['training_data'] = None
        else:
            horse_data['training_data'] = None
        
        # 
        if danwa_data:
            # 1) 旧来の構造 {'comments': [...]} をサポート
            if 'comments' in danwa_data and isinstance(danwa_data['comments'], list):
                for comment in danwa_data['comments']:
                    num = RaceDataIntegrator._to_int_safe(comment.get('horse_number') or comment.get('馬番'))
                    if num == horse_number:
                        horse_data['stable_comment'] = {
                            'date': comment.get('date', ''),
                            'comment': comment.get('comment', '') or comment.get('談話', '') or comment.get('展望', ''),
                            'condition': comment.get('condition', ''),
                            'target_race': comment.get('target_race', ''),
                            'trainer': comment.get('trainer', '') or comment.get('調教師', '')
                        }
                        break
                else:
                    horse_data['stable_comment'] = None
            # 2) DanwaParser 構造 {'danwa_data': [...]} をサポート
            elif 'danwa_data' in danwa_data and isinstance(danwa_data['danwa_data'], list):
                for row in danwa_data['danwa_data']:
                    num = RaceDataIntegrator._to_int_safe(row.get('horse_number') or row.get('馬番'))
                    if num == horse_number:
                        horse_data['stable_comment'] = {
                            'date': row.get('date', ''),
                            'comment': row.get('厩舎の話', '') or row.get('コメント', '') or row.get('談話', '') or row.get('展望', ''),
                            'condition': row.get('状態', ''),
                            'target_race': row.get('target_race', ''),
                            'trainer': row.get('調教師', '')
                        }
                        break
                else:
                    horse_data['stable_comment'] = None
            else:
                horse_data['stable_comment'] = None
        else:
            horse_data['stable_comment'] = None
        
        # 成績データ
        if seiseki_data:
            results = seiseki_data.get('results', seiseki_data.get('horses', []))
            for result in results:
                # 馬番の比較（文字列と数値の両方に対応）
                horse_num = result.get('馬番') or result.get('horse_number')
                if horse_num and str(horse_num) == str(horse_number):
                    horse_data['result'] = {
                        'finish_position': result.get('着順') or result.get('finish_position', 0),
                        'time': result.get('タイム') or result.get('time', ''),
                        'margin': result.get('着差') or result.get('margin', ''),
                        'last_3f': result.get('上り3F') or result.get('上り') or result.get('last_3f', ''),
                        'passing_orders': result.get('通過順位') or result.get('コーナー通過順') or result.get('corner_positions', ''),
                        'last_corner_position': result.get('4角位置') or result.get('last_corner_position', ''),
                        'first_3f': result.get('前半3F') or result.get('first_3f', ''),
                        'sunpyo': result.get('寸評') or result.get('sunpyo', ''),  # 寸評を追加
                        'prize_money': result.get('prize_money', 0),
                        'horse_weight': result.get('馬体重') or result.get('horse_weight', ''),
                        'horse_weight_diff': result.get('増減') or result.get('horse_weight_diff', ''),
                        # 元データも保持
                        'raw_data': result
                    }
                    break
        else:
            horse_data['result'] = None
        
        # 前走インタビューデータ
        if syoin_data and 'interviews' in syoin_data:
            for interview in syoin_data['interviews']:
                if interview.get('horse_number') == horse_number:
                    horse_data['previous_race_interview'] = {
                        'jockey': interview.get('jockey', ''),
                        'comment': interview.get('comment', ''),  # 後方互換性
                        'interview': interview.get('interview', ''),  # 前走インタビュー
                        'next_race_memo': interview.get('next_race_memo', ''),  # 次走へのメモ
                        'finish_position': interview.get('finish_position', ''),  # 着順
                        'previous_race_mention': interview.get('previous_race_mention', '')
                    }
                    break
        else:
            horse_data['previous_race_interview'] = None
        
        # パドック情報データ
        if paddok_data and 'paddock_evaluations' in paddok_data:
            for evaluation in paddok_data['paddock_evaluations']:
                if evaluation.get('horse_number') == horse_number:
                    horse_data['paddock_info'] = {
                        'mark': evaluation.get('mark', ''),
                        'mark_score': evaluation.get('mark_score', 0),
                        'comment': evaluation.get('comment', ''),
                        'condition': evaluation.get('condition', ''),
                        'temperament': evaluation.get('temperament', ''),
                        'gait': evaluation.get('gait', ''),
                        'horse_weight': evaluation.get('horse_weight', ''),
                        'weight_change': evaluation.get('weight_change', ''),
                        'evaluator': evaluation.get('evaluator', '')
                    }
                    break
        else:
            horse_data['paddock_info'] = None
        
        # 
        horse_data['past_performances'] = {
            'total_races': 0,
            'wins': 0,
            'places': 0,
            'shows': 0,
            'earnings': 0,
            'recent_form': []
        }
        
        # 履歴特徴量を追加（Phase1）
        horse_data['history_features'] = self._load_history_features(horse_data.get('horse_id'))
        
        return horse_data
    
    def _load_history_features(self, horse_id: str) -> Optional[Dict]:
        """馬の履歴特徴量を読み込む"""
        if not horse_id:
            return None
        
        # accumulated/horses/{horse_id}.json から読み込み
        accumulated_path = Path(self.data_root).parent / "accumulated" / "horses" / f"{horse_id}.json"
        
        if accumulated_path.exists():
            try:
                with open(accumulated_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('history_features', {})
            except Exception as e:
                self.logger.debug(f"Failed to load history features for horse {horse_id}: {e}")
        
        return None
    
    def _analyze_race(self, entries: List[Dict]) -> Dict[str, Any]:
        """
        
        
        Args:
            entries: 
            
        Returns:
            Dict[str, Any]: 
        """
        analysis = {
            'expected_pace': 'M-M',  # 
            'favorites': [],
            'training_highlights': [],
            'entry_count': len(entries)
        }
        
        # 
        favorites = []
        for entry in entries:
            odds_rank = entry.get('entry_data', {}).get('odds_rank', 999)
            # 文字列を整数に変換
            try:
                odds_rank = int(odds_rank) if odds_rank else 999
            except (ValueError, TypeError):
                odds_rank = 999
            
            if odds_rank <= 3:
                favorites.append({
                    'horse_number': entry['horse_number'],
                    'horse_name': entry['horse_name'],
                    'odds_rank': odds_rank
                })
        
        analysis['favorites'] = sorted(favorites, key=lambda x: x['odds_rank'])
        
        # 
        training_highlights = []
        for entry in entries:
            training = entry.get('training_data', {})
            if training and training.get('evaluation') in ['A', 'B']:
                training_highlights.append(
                    f"{entry['horse_number']} {entry['horse_name']} - {training['evaluation']}"
                )
        
        analysis['training_highlights'] = training_highlights
        
        return analysis
    
    def create_integrated_file(self, race_id: str, save: bool = True, race_ids_data: Dict = None) -> Dict[str, Any]:
        """
        
        
        Args:
            race_id: ID
            save: 
            race_ids_data: race_ids JSONデータ（発走時刻含む）
            
        Returns:
            Dict[str, Any]: 
        """
        self.logger.info(f": {race_id}")
        
        # 
        syutuba_data = self._load_race_data(race_id, 'shutsuba')
        cyokyo_data = self._load_race_data(race_id, 'cyokyo')
        danwa_data = self._load_race_data(race_id, 'danwa')
        seiseki_data = self._load_race_data(race_id, 'seiseki')
        syoin_data = self._load_race_data(race_id, 'syoin')
        paddok_data = self._load_race_data(race_id, 'paddok')
        
        # 
        data_sources = DataSourceStatus()
        if syutuba_data:
            data_sources.syutuba = ""
        if cyokyo_data:
            data_sources.cyokyo = ""
        if danwa_data:
            data_sources.danwa = ""
        if seiseki_data:
            data_sources.seiseki = ""
        if syoin_data:
            data_sources.syoin = ""
        if paddok_data:
            data_sources.paddok = ""
        
        # 
        if not syutuba_data:
            self.logger.error(f": {race_id}")
            return {}
        
        # 
        metadata = RaceMetadata(
            race_id=race_id,
            data_sources=asdict(data_sources)
        )
        
        # 
        race_info = self._extract_race_info(race_id, syutuba_data, race_ids_data)
        # seiseki由来の詳細でrace_infoを補完
        if seiseki_data:
            # race_details
            details = seiseki_data.get('race_details') or {}
            for k in ['distance', 'track_condition', 'weather', 'start_time', 'grade']:
                if details.get(k) and not race_info.get(k):
                    race_info[k] = details.get(k)
            # track_type -> track のマッピング
            if details.get('track_type') and not race_info.get('track'):
                track_type = details.get('track_type')
                race_info['track'] = '芝' if track_type == '芝' else 'ダ'
        
        # 
        integrated_data = {
            'meta': asdict(metadata),
            'race_info': race_info,
            'entries': [],
            # 追加: 配当とラップ（存在すれば）
            'payouts': seiseki_data.get('payouts') if seiseki_data else None,
            'laps': seiseki_data.get('laps') if seiseki_data else None
        }
        
        # 
        horses_data = syutuba_data.get('horses', syutuba_data.get('entries', []))
        if horses_data:
            for entry in horses_data:
                # 馬番を取得（複数のキー名に対応）
                horse_number = entry.get('馬番') or entry.get('horse_number') or 0
                if horse_number:
                    # 馬番を整数に変換
                    try:
                        horse_number = int(horse_number)
                    except (ValueError, TypeError):
                        continue
                    
                    horse_data = self._merge_horse_data(
                        horse_number,
                        entry,
                        cyokyo_data,
                        danwa_data,
                        seiseki_data,
                        syoin_data,
                        paddok_data
                    )
                    integrated_data['entries'].append(horse_data)
        
        # 
        integrated_data['analysis'] = self._analyze_race(integrated_data['entries'])
        
        # 展開データを追加
        if syutuba_data and 'tenkai_data' in syutuba_data:
            integrated_data['tenkai_data'] = syutuba_data['tenkai_data']
        
        # 本紙の見解を追加
        if syutuba_data and 'race_comment' in syutuba_data:
            integrated_data['race_comment'] = syutuba_data['race_comment']
        
        # 
        if save:
            output_path = self._get_integrated_file_path(race_id)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(integrated_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f": {output_path}")
        
        return integrated_data
    
    def _get_integrated_file_path(self, race_id: str) -> str:
        """


        Args:
            race_id: ID

        Returns:
            str:
        """
        filename = f"integrated_{race_id}.json"

        # 実際の開催日を取得（処理中のマッピングまたは保存済みマッピング）
        actual_date = self.race_id_to_date_map.get(race_id) or self.actual_date_map.get(race_id)

        if actual_date:
            date_str = actual_date
        elif race_id in self.actual_date_map:
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

        # 出力先を races/YYYY/MM/DD/temp に固定（競馬場名や構造フラグを使用しない）
        output_dir = os.path.join(self.data_root, 'races', year, month, day, 'temp')
        
        return os.path.join(output_dir, filename)
    
    def update_with_results(self, race_id: str) -> bool:
        """
        
        
        Args:
            race_id: ID
            
        Returns:
            bool: True
        """
        try:
            # 
            integrated_path = self._get_integrated_file_path(race_id)
            if not os.path.exists(integrated_path):
                self.logger.warning(f": {race_id}")
                # 
                self.create_integrated_file(race_id)
                return True
            
            with open(integrated_path, 'r', encoding='utf-8') as f:
                integrated_data = json.load(f)
            
            # 
            seiseki_data = self._load_race_data(race_id, 'seiseki')
            if not seiseki_data:
                self.logger.warning(f": {race_id}")
                return False
            
            # 
            if 'results' in seiseki_data:
                for result in seiseki_data['results']:
                    horse_number = result.get('horse_number')
                    for entry in integrated_data['entries']:
                        if entry['horse_number'] == horse_number:
                            entry['result'] = {
                                'finish_position': result.get('finish_position', 0),
                                'time': result.get('time', ''),
                                'margin': result.get('margin', ''),
                                'last_3f': result.get('last_3f', ''),
                                'corner_positions': result.get('corner_positions', ''),
                                'prize_money': result.get('prize_money', 0),
                                'horse_weight': result.get('horse_weight', ''),
                                'horse_weight_diff': result.get('horse_weight_diff', '')
                            }
                            break
            
            # 
            integrated_data['meta']['updated_at'] = datetime.now().isoformat()
            integrated_data['meta']['data_sources']['seiseki'] = ""
            
            # 
            with open(integrated_path, 'w', encoding='utf-8') as f:
                json.dump(integrated_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f": {race_id}")
            return True
            
        except Exception as e:
            self.logger.error(f": {race_id}, {e}")
            return False
    
    def batch_create_integrated_files(self, date_str: str) -> Dict[str, Any]:
        """
        
        
        Args:
            date_str:  (YYYYMMDD)
            
        Returns:
            Dict[str, Any]: 
        """
        self.logger.info(f": {date_str}")
        
        # ID
        race_ids_file = get_race_ids_file_path(date_str)
        if not os.path.exists(race_ids_file):
            self.logger.error(f"ID: {date_str}")
            return {'success': False, 'error': 'No race IDs file'}
        
        with open(race_ids_file, 'r', encoding='utf-8') as f:
            race_ids_data = json.load(f)
        
        # IDと日付マッピングをクリアして再作成
        race_ids = []
        self.race_id_to_date_map.clear()

        for venue, races in race_ids_data.get('kaisai_data', {}).items():
            for race in races:
                if isinstance(race, dict) and 'race_id' in race:
                    race_id = race['race_id']
                    race_ids.append(race_id)
                    # マッピングに追加（実際の開催日を保存）
                    self.race_id_to_date_map[race_id] = date_str
                elif isinstance(race, str):
                    race_ids.append(race)
                    self.race_id_to_date_map[race] = date_str
        
        # 
        success_count = 0
        failed_count = 0
        
        for race_id in race_ids:
            try:
                result = self.create_integrated_file(race_id, race_ids_data=race_ids_data)
                if result:
                    success_count += 1
                    self.logger.info(f"[OK] : {race_id}")
                else:
                    failed_count += 1
                    self.logger.error(f"[ERROR] : {race_id}")
            except Exception as e:
                failed_count += 1
                self.logger.error(f"[ERROR] : {race_id}, {e}")
        
        summary = {
            'success': True,
            'date': date_str,
            'total_races': len(race_ids),
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': (success_count / len(race_ids) * 100) if race_ids else 0
        }
        
        self.logger.info(f":  {success_count},  {failed_count}")
        return summary
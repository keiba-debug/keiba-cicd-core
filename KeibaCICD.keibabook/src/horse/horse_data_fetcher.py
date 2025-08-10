#!/usr/bin/env python3
"""
馬データ取得クラス

競走馬の詳細データ（プロフィール、血統、戦績）を取得します。
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from ..scrapers.requests_scraper import RequestsScraper
from ..parsers.base_parser import BaseParser
from ..utils.config import Config


@dataclass
class HorseProfile:
    """馬プロフィール"""
    horse_id: str
    horse_name: str
    sex: str = ""
    birth_date: str = ""
    father: str = ""
    mother: str = ""
    mother_father: str = ""
    owner: str = ""
    trainer: str = ""
    producer: str = ""
    birth_place: str = ""
    status: str = ""  # 現役/引退
    
    
@dataclass
class RaceRecord:
    """レース戦績"""
    date: str
    venue: str
    race_name: str
    race_grade: str
    distance: str
    track: str
    track_condition: str
    finish_position: int
    horse_count: int
    jockey: str
    weight: str
    time: str
    margin: str
    corner_positions: str
    last_3f: str
    odds: float
    popularity: int
    horse_weight: str
    prize_money: int
    

@dataclass
class HorseStatistics:
    """馬の成績統計"""
    total_races: int = 0
    wins: int = 0
    places: int = 0
    shows: int = 0
    out_of_money: int = 0
    total_earnings: int = 0
    win_rate: float = 0.0
    place_rate: float = 0.0
    
    # 条件別成績
    by_track: Dict[str, Dict] = None  # 芝/ダート別
    by_distance: Dict[str, Dict] = None  # 距離別
    by_venue: Dict[str, Dict] = None  # 競馬場別
    by_condition: Dict[str, Dict] = None  # 馬場状態別
    
    def __post_init__(self):
        if self.by_track is None:
            self.by_track = {}
        if self.by_distance is None:
            self.by_distance = {}
        if self.by_venue is None:
            self.by_venue = {}
        if self.by_condition is None:
            self.by_condition = {}


class HorseDataParser(BaseParser):
    """馬データパーサー"""
    
    def parse_profile(self, html_content: str) -> Optional[HorseProfile]:
        """
        馬プロフィールをパース
        
        Args:
            html_content: HTMLコンテンツ
            
        Returns:
            Optional[HorseProfile]: プロフィール情報
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # プロフィールテーブルを探す
            profile = HorseProfile(horse_id="", horse_name="")
            
            # 馬名を取得
            horse_name_elem = soup.find('h1', class_='horse_name')
            if not horse_name_elem:
                horse_name_elem = soup.find('div', class_='name')
            if horse_name_elem:
                profile.horse_name = horse_name_elem.get_text(strip=True)
            
            # プロフィールテーブルから情報抽出
            profile_table = soup.find('table', class_='profile')
            if profile_table:
                rows = profile_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        label = th.get_text(strip=True)
                        value = td.get_text(strip=True)
                        
                        if '性別' in label or '性' in label:
                            profile.sex = value
                        elif '生年月日' in label or '誕生日' in label:
                            profile.birth_date = value
                        elif '父' in label and '母父' not in label:
                            profile.father = value
                        elif '母' in label and '母父' not in label:
                            profile.mother = value
                        elif '母父' in label:
                            profile.mother_father = value
                        elif '馬主' in label:
                            profile.owner = value
                        elif '調教師' in label:
                            profile.trainer = value
                        elif '生産者' in label or '生産' in label:
                            profile.producer = value
                        elif '産地' in label:
                            profile.birth_place = value
            
            return profile
            
        except Exception as e:
            self.logger.error(f"プロフィールパースエラー: {e}")
            return None
    
    def parse_race_history(self, html_content: str) -> List[RaceRecord]:
        """
        レース戦績をパース
        
        Args:
            html_content: HTMLコンテンツ
            
        Returns:
            List[RaceRecord]: レース戦績リスト
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            records = []
            
            # 戦績テーブルを探す
            history_table = soup.find('table', class_='race_history')
            if not history_table:
                history_table = soup.find('table', {'id': 'race_results'})
            
            if history_table:
                rows = history_table.find_all('tr')[1:]  # ヘッダーを除く
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 10:
                        record = RaceRecord(
                            date=cells[0].get_text(strip=True),
                            venue=cells[1].get_text(strip=True),
                            race_name=cells[2].get_text(strip=True),
                            race_grade="",
                            distance=cells[3].get_text(strip=True),
                            track=cells[4].get_text(strip=True),
                            track_condition=cells[5].get_text(strip=True),
                            finish_position=self._parse_int(cells[6].get_text(strip=True)),
                            horse_count=self._parse_int(cells[7].get_text(strip=True)),
                            jockey=cells[8].get_text(strip=True),
                            weight=cells[9].get_text(strip=True),
                            time=cells[10].get_text(strip=True) if len(cells) > 10 else "",
                            margin=cells[11].get_text(strip=True) if len(cells) > 11 else "",
                            corner_positions=cells[12].get_text(strip=True) if len(cells) > 12 else "",
                            last_3f=cells[13].get_text(strip=True) if len(cells) > 13 else "",
                            odds=self._parse_float(cells[14].get_text(strip=True)) if len(cells) > 14 else 0.0,
                            popularity=self._parse_int(cells[15].get_text(strip=True)) if len(cells) > 15 else 0,
                            horse_weight=cells[16].get_text(strip=True) if len(cells) > 16 else "",
                            prize_money=self._parse_int(cells[17].get_text(strip=True)) if len(cells) > 17 else 0
                        )
                        
                        # グレードを判定
                        race_name = record.race_name
                        if 'GI' in race_name or 'G1' in race_name:
                            record.race_grade = 'G1'
                        elif 'GII' in race_name or 'G2' in race_name:
                            record.race_grade = 'G2'
                        elif 'GIII' in race_name or 'G3' in race_name:
                            record.race_grade = 'G3'
                        
                        records.append(record)
            
            return records
            
        except Exception as e:
            self.logger.error(f"戦績パースエラー: {e}")
            return []
    
    def _parse_int(self, text: str) -> int:
        """整数パース"""
        try:
            # 数字以外の文字を除去
            import re
            cleaned = re.sub(r'[^0-9]', '', text)
            return int(cleaned) if cleaned else 0
        except:
            return 0
    
    def _parse_float(self, text: str) -> float:
        """浮動小数点数パース"""
        try:
            # 数字とピリオド以外を除去
            import re
            cleaned = re.sub(r'[^0-9.]', '', text)
            return float(cleaned) if cleaned else 0.0
        except:
            return 0.0


class HorseDataFetcher:
    """
    馬データ取得クラス
    
    競走馬の詳細データを取得・管理します。
    """
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        self.scraper = RequestsScraper()
        self.parser = HorseDataParser()
        
        # 保存先ディレクトリ
        self.data_root = os.getenv('KEIBA_DATA_ROOT_DIR', './data/keibabook')
        self.horse_data_dir = os.path.join(self.data_root, '馬データ')
        os.makedirs(self.horse_data_dir, exist_ok=True)
        
        self.logger.info("馬データ取得クラスを初期化しました")
    
    def fetch_horse_data(self, horse_id: str, horse_name: str = "") -> Optional[Dict[str, Any]]:
        """
        馬の全データを取得
        
        Args:
            horse_id: 馬ID（umacd）
            horse_name: 馬名（オプション）
            
        Returns:
            Optional[Dict[str, Any]]: 馬データ
        """
        try:
            self.logger.info(f"馬データ取得開始: {horse_id} {horse_name}")
            
            # 既存データをチェック
            existing_data = self._load_existing_data(horse_id)
            if existing_data:
                self.logger.info(f"既存データを使用: {horse_id}")
                return existing_data
            
            # プロフィールを取得
            profile_url = f"https://p.keibabook.co.jp/horse/profile/{horse_id}"
            profile_html = self.scraper.scrape(profile_url)
            
            if not profile_html:
                self.logger.error(f"プロフィール取得失敗: {horse_id}")
                return None
            
            profile = self.parser.parse_profile(profile_html)
            if profile:
                profile.horse_id = horse_id
                if horse_name:
                    profile.horse_name = horse_name
            
            # 戦績を取得
            history_url = f"https://p.keibabook.co.jp/horse/history/{horse_id}"
            history_html = self.scraper.scrape(history_url)
            
            race_records = []
            if history_html:
                race_records = self.parser.parse_race_history(history_html)
            
            # 統計を計算
            statistics = self._calculate_statistics(race_records)
            
            # 馬データを構築
            horse_data = {
                'meta': {
                    'horse_id': horse_id,
                    'horse_name': profile.horse_name if profile else horse_name,
                    'fetched_at': datetime.now().isoformat(),
                    'data_version': '1.0'
                },
                'profile': asdict(profile) if profile else None,
                'race_records': [asdict(r) for r in race_records],
                'statistics': asdict(statistics),
                'pedigree': self._extract_pedigree(profile) if profile else None
            }
            
            # データを保存
            self._save_horse_data(horse_id, horse_data)
            
            self.logger.info(f"✅ 馬データ取得完了: {horse_id} - {len(race_records)}戦")
            return horse_data
            
        except Exception as e:
            self.logger.error(f"馬データ取得エラー: {horse_id}, {e}")
            return None
    
    def fetch_horses_for_race(self, race_id: str) -> Dict[str, Any]:
        """
        レースの全出走馬のデータを取得
        
        Args:
            race_id: レースID
            
        Returns:
            Dict[str, Any]: 処理結果サマリー
        """
        try:
            self.logger.info(f"レース出走馬データ取得開始: {race_id}")
            
            # 出走表データを読み込み
            shutsuba_file = os.path.join(self.data_root, f"shutsuba_{race_id}.json")
            if not os.path.exists(shutsuba_file):
                shutsuba_file = os.path.join(self.data_root, f"syutuba_{race_id}.json")
            
            if not os.path.exists(shutsuba_file):
                self.logger.error(f"出走表データが見つかりません: {race_id}")
                return {'success': False, 'error': 'No shutsuba data'}
            
            with open(shutsuba_file, 'r', encoding='utf-8') as f:
                shutsuba_data = json.load(f)
            
            # 各馬のデータを取得
            horses = []
            success_count = 0
            failed_count = 0
            
            for entry in shutsuba_data.get('entries', []):
                horse_id = entry.get('umacd', '')
                horse_name = entry.get('horse_name', '')
                
                if not horse_id:
                    self.logger.warning(f"馬IDが見つかりません: {horse_name}")
                    failed_count += 1
                    continue
                
                horse_data = self.fetch_horse_data(horse_id, horse_name)
                if horse_data:
                    horses.append(horse_data)
                    success_count += 1
                else:
                    failed_count += 1
                
                # リクエスト間隔
                time.sleep(1)
            
            # サマリー
            summary = {
                'success': True,
                'race_id': race_id,
                'total_horses': len(shutsuba_data.get('entries', [])),
                'success_count': success_count,
                'failed_count': failed_count,
                'horses': horses
            }
            
            self.logger.info(f"✅ レース出走馬データ取得完了: 成功 {success_count}頭, 失敗 {failed_count}頭")
            return summary
            
        except Exception as e:
            self.logger.error(f"レース出走馬データ取得エラー: {race_id}, {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_statistics(self, race_records: List[RaceRecord]) -> HorseStatistics:
        """
        成績統計を計算
        
        Args:
            race_records: レース戦績リスト
            
        Returns:
            HorseStatistics: 統計情報
        """
        stats = HorseStatistics()
        
        if not race_records:
            return stats
        
        stats.total_races = len(race_records)
        
        for record in race_records:
            # 着順カウント
            if record.finish_position == 1:
                stats.wins += 1
            elif record.finish_position == 2:
                stats.places += 1
            elif record.finish_position == 3:
                stats.shows += 1
            else:
                stats.out_of_money += 1
            
            # 賞金加算
            stats.total_earnings += record.prize_money
            
            # 条件別集計
            # トラック別
            track = record.track
            if track not in stats.by_track:
                stats.by_track[track] = {'races': 0, 'wins': 0}
            stats.by_track[track]['races'] += 1
            if record.finish_position == 1:
                stats.by_track[track]['wins'] += 1
            
            # 競馬場別
            venue = record.venue
            if venue not in stats.by_venue:
                stats.by_venue[venue] = {'races': 0, 'wins': 0}
            stats.by_venue[venue]['races'] += 1
            if record.finish_position == 1:
                stats.by_venue[venue]['wins'] += 1
            
            # 馬場状態別
            condition = record.track_condition
            if condition not in stats.by_condition:
                stats.by_condition[condition] = {'races': 0, 'wins': 0}
            stats.by_condition[condition]['races'] += 1
            if record.finish_position == 1:
                stats.by_condition[condition]['wins'] += 1
        
        # 率を計算
        if stats.total_races > 0:
            stats.win_rate = (stats.wins / stats.total_races) * 100
            stats.place_rate = ((stats.wins + stats.places) / stats.total_races) * 100
        
        return stats
    
    def _extract_pedigree(self, profile: HorseProfile) -> Dict[str, Any]:
        """
        血統情報を抽出
        
        Args:
            profile: プロフィール
            
        Returns:
            Dict[str, Any]: 血統情報
        """
        return {
            'father': profile.father,
            'mother': profile.mother,
            'mother_father': profile.mother_father,
            'pedigree_tree': {
                '1代': {
                    '父': profile.father,
                    '母': profile.mother
                },
                '2代': {
                    '母父': profile.mother_father
                }
            }
        }
    
    def _load_existing_data(self, horse_id: str) -> Optional[Dict[str, Any]]:
        """
        既存データを読み込み
        
        Args:
            horse_id: 馬ID
            
        Returns:
            Optional[Dict[str, Any]]: 既存データ
        """
        file_path = os.path.join(self.horse_data_dir, f"{horse_id}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"既存データ読み込みエラー: {horse_id}, {e}")
        return None
    
    def _save_horse_data(self, horse_id: str, horse_data: Dict[str, Any]):
        """
        馬データを保存
        
        Args:
            horse_id: 馬ID
            horse_data: 馬データ
        """
        try:
            # 現役/引退で分類
            status_dir = '現役馬'
            if horse_data.get('profile', {}).get('status') == '引退':
                status_dir = '引退馬'
            
            save_dir = os.path.join(self.horse_data_dir, status_dir)
            os.makedirs(save_dir, exist_ok=True)
            
            file_path = os.path.join(save_dir, f"{horse_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(horse_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"馬データ保存完了: {file_path}")
            
        except Exception as e:
            self.logger.error(f"馬データ保存エラー: {horse_id}, {e}")
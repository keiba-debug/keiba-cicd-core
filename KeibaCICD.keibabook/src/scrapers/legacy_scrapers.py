#!/usr/bin/env python3
"""
レガシースクレイパー

旧scraper.pyから移行された特殊用途のスクレイパークラス群
"""

from typing import Dict, List, Optional, Tuple
import json
import time
import re
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel

from utils.logger import setup_logger

logger = setup_logger("legacy_scrapers")


class DanwaData(BaseModel):
    """談話データのモデル"""
    race_id: str
    horse_number: int
    horse_name: str
    stable_comment: str
    article_id: str
    scraped_at: str


class SyutubaHorseData(BaseModel):
    """出馬表データのモデル"""
    race_id: str
    horse_number: int
    horse_name: str
    sex_age: str
    jockey: str
    trainer: str
    short_comment: str


class DanwaTableHorseData(BaseModel):
    """厩舎の話データのモデル"""
    race_id: str
    horse_number: int
    horse_name: str
    stable_comment: str


class CyokyoSemekaisetuData(BaseModel):
    """調教攻め解説データのモデル"""
    race_id: str
    horse_number: int
    horse_name: str
    attack_explanation: str


class RaceIdExtractor:
    """レースID抽出ユーティリティ"""
    
    @staticmethod
    def extract_from_url(url: str) -> Optional[str]:
        """URLからレースIDを抽出"""
        patterns = [
            r'/seiseki/(\d{12})',
            r'/syutuba/(\d{12})',
            r'/cyokyo/(\d{12})',
            r'/danwa/(\d{12})',
            r'race_id=(\d{12})',
            r'/(\d{12})/?$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def parse_race_id(race_id: str) -> Tuple[str, str, str]:
        """レースIDを日付、場所、レース番号に分解"""
        if len(race_id) != 12:
            raise ValueError(f"Invalid race_id format: {race_id}")
        
        date_part = race_id[:8]  # YYYYMMDD
        venue_part = race_id[8:10]  # 場所コード
        race_part = race_id[10:12]  # レース番号
        
        return date_part, venue_part, race_part


class DanwaScraper:
    """談話記事スクレイパー"""
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.base_url = "https://p.keibabook.co.jp"
        self.output_dir = Path("data/keibabook/danwa")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def scrape_danwa(self, url: str) -> Optional[DanwaData]:
        """談話記事をスクレイピング"""
        try:
            # レースIDを抽出
            race_id = RaceIdExtractor.extract_from_url(url)
            if not race_id:
                logger.error(f"レースIDを抽出できません: {url}")
                return None

            # リクエスト間隔を設定
            time.sleep(1)
            
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 記事IDを取得
            article_id = url.split('/')[-1]
            
            # 馬情報を抽出
            horse_info = soup.select_one('.horse-info')
            if not horse_info:
                logger.error(f"馬情報が見つかりません: {url}")
                return None
                
            horse_number = int(horse_info.select_one('.number').text.strip())
            horse_name = horse_info.select_one('.name').text.strip()
            stable_comment = horse_info.select_one('.comment').text.strip()
            
            return DanwaData(
                race_id=race_id,
                horse_number=horse_number,
                horse_name=horse_name,
                stable_comment=stable_comment,
                article_id=article_id,
                scraped_at=datetime.now().isoformat()
            )
            
        except requests.RequestException as e:
            logger.error(f"スクレイピング中にエラーが発生しました: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"予期せぬエラーが発生しました: {str(e)}")
            return None

    def save_danwa(self, data: DanwaData) -> None:
        """談話データをJSONファイルとして保存"""
        try:
            output_file = self.output_dir / f"{data.race_id}_{data.article_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data.dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"データを保存しました: {output_file}")
        except Exception as e:
            logger.error(f"データの保存中にエラーが発生しました: {str(e)}")
            raise


class SyutubaScraper:
    """出馬表スクレイパー"""
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.base_url = "https://p.keibabook.co.jp"
        self.output_dir = Path("data/keibabook/syutuba")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def scrape_syutuba(self, url: str) -> List[SyutubaHorseData]:
        """出馬表ページから馬ごとの短評を取得"""
        try:
            # レースIDを抽出
            race_id = RaceIdExtractor.extract_from_url(url)
            if not race_id:
                logger.error(f"レースIDを抽出できません: {url}")
                return []

            time.sleep(1)
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 4番目のテーブル（index=4）が出馬表本体
            tables = soup.find_all('table')
            if len(tables) < 5:
                logger.error(f"出馬表テーブルが見つかりません: {url}")
                return []
            table = tables[4]

            horses = []
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 16:
                    continue  # データ行でなければスキップ
                try:
                    horse_number = int(tds[1].get_text(strip=True))
                    horse_name = tds[9].get_text(strip=True)
                    sex_age = tds[10].get_text(strip=True)
                    jockey = tds[12].get_text(strip=True)
                    trainer = tds[14].get_text(strip=True)
                    short_comment = tds[15].get_text(strip=True)
                    horses.append(SyutubaHorseData(
                        race_id=race_id,
                        horse_number=horse_number,
                        horse_name=horse_name,
                        sex_age=sex_age,
                        jockey=jockey,
                        trainer=trainer,
                        short_comment=short_comment
                    ))
                except Exception as e:
                    logger.error(f"馬データのパースに失敗: {str(e)}")
                    continue  # パース失敗行はスキップ
            return horses
        except requests.RequestException as e:
            logger.error(f"出馬表スクレイピング中にエラー: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"予期せぬエラー: {str(e)}")
            return []

    def save_syutuba(self, data: List[SyutubaHorseData]) -> None:
        """出馬表データを保存"""
        try:
            if not data:
                logger.warning("保存するデータがありません")
                return
                
            race_id = data[0].race_id
            output_file = self.output_dir / f"{race_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([d.dict() for d in data], f, ensure_ascii=False, indent=2)
            logger.info(f"出馬表データを保存しました: {output_file}")
        except Exception as e:
            logger.error(f"データ保存中にエラー: {str(e)}")
            raise


class DanwaTableScraper:
    """厩舎の話テーブルスクレイパー"""
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.base_url = "https://p.keibabook.co.jp"
        self.output_dir = Path("data/keibabook/danwa_table")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def scrape_danwa_table(self, url: str) -> List[DanwaTableHorseData]:
        """厩舎の話テーブルから馬ごとの談話を取得"""
        try:
            # レースIDを抽出
            race_id = RaceIdExtractor.extract_from_url(url)
            if not race_id:
                logger.error(f"レースIDを抽出できません: {url}")
                return []

            time.sleep(1)
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 2番目のテーブル（index=2）が厩舎の話本体
            tables = soup.find_all('table')
            if len(tables) < 3:
                logger.error(f"厩舎の話テーブルが見つかりません: {url}")
                return []
            table = tables[2]

            horses = []
            for tr in table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 3:
                    continue  # データ行でなければスキップ
                try:
                    horse_number = int(tds[0].get_text(strip=True))
                    horse_name = tds[1].get_text(strip=True)
                    stable_comment = tds[2].get_text(strip=True)
                    horses.append(DanwaTableHorseData(
                        race_id=race_id,
                        horse_number=horse_number,
                        horse_name=horse_name,
                        stable_comment=stable_comment
                    ))
                except Exception as e:
                    logger.error(f"厩舎の話データのパースに失敗: {str(e)}")
                    continue
            return horses
        except requests.RequestException as e:
            logger.error(f"厩舎の話スクレイピング中にエラー: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"予期せぬエラー: {str(e)}")
            return []

    def save_danwa_table(self, data: List[DanwaTableHorseData]) -> None:
        """厩舎の話データを保存"""
        try:
            if not data:
                logger.warning("保存するデータがありません")
                return
                
            race_id = data[0].race_id
            output_file = self.output_dir / f"{race_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([d.dict() for d in data], f, ensure_ascii=False, indent=2)
            logger.info(f"厩舎の話データを保存しました: {output_file}")
        except Exception as e:
            logger.error(f"データ保存中にエラー: {str(e)}")
            raise


class CyokyoSemekaisetuScraper:
    """調教攻め解説スクレイパー"""
    
    def __init__(self, session: requests.Session):
        self.session = session
        self.base_url = "https://p.keibabook.co.jp"
        self.output_dir = Path("data/keibabook/cyokyo_semekaisetsu")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def scrape_cyokyo(self, url: str) -> List[CyokyoSemekaisetuData]:
        """調教攻め解説を取得"""
        try:
            # レースIDを抽出
            race_id = RaceIdExtractor.extract_from_url(url)
            if not race_id:
                logger.error(f"レースIDを抽出できません: {url}")
                return []

            time.sleep(1)
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 調教攻め解説テーブルを探す
            tables = soup.find_all('table')
            target_table = None
            
            for table in tables:
                # テーブルのヘッダーを確認
                headers = [th.get_text(strip=True) for th in table.find_all('th')]
                if any('攻め' in header for header in headers):
                    target_table = table
                    break
            
            if not target_table:
                logger.error(f"調教攻め解説テーブルが見つかりません: {url}")
                return []

            horses = []
            for tr in target_table.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) < 4:
                    continue  # データ行でなければスキップ
                try:
                    horse_number = int(tds[0].get_text(strip=True))
                    horse_name = tds[1].get_text(strip=True)
                    attack_explanation = tds[3].get_text(strip=True)  # 攻め解説列
                    horses.append(CyokyoSemekaisetuData(
                        race_id=race_id,
                        horse_number=horse_number,
                        horse_name=horse_name,
                        attack_explanation=attack_explanation
                    ))
                except Exception as e:
                    logger.error(f"調教攻め解説データのパースに失敗: {str(e)}")
                    continue
            return horses
        except requests.RequestException as e:
            logger.error(f"調教攻め解説スクレイピング中にエラー: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"予期せぬエラー: {str(e)}")
            return []

    def save_cyokyo(self, data: List[CyokyoSemekaisetuData]) -> None:
        """調教攻め解説データを保存"""
        try:
            if not data:
                logger.warning("保存するデータがありません")
                return
                
            race_id = data[0].race_id
            output_file = self.output_dir / f"{race_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([d.dict() for d in data], f, ensure_ascii=False, indent=2)
            logger.info(f"調教攻め解説データを保存しました: {output_file}")
        except Exception as e:
            logger.error(f"データ保存中にエラー: {str(e)}")
            raise 
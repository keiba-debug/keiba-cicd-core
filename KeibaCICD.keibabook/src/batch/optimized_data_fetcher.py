#!/usr/bin/env python3
"""
requests

DataFetcher
- RequestsScraperSelenium
- 
- 
- 
- 
- 
- 
- 
"""

import os
import json
import time
import logging
import psutil
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass, field
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..scrapers.requests_scraper import RequestsScraper
from ..parsers.seiseki_parser import SeisekiParser
from ..parsers.syutuba_parser import SyutubaParser
from ..parsers.cyokyo_parser import CyokyoParser
from ..parsers.danwa_parser import DanwaParser
from ..parsers.nittei_parser import NitteiParser
from .core.common import ensure_batch_directories, get_race_ids_file_path, get_json_file_path


@dataclass
class ErrorStats:
    """"""
    http_errors: int = 0
    timeout_errors: int = 0
    parse_errors: int = 0
    other_errors: int = 0
    total_retries: int = 0
    error_details: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_error(self, error_type: str, details: Dict[str, Any]):
        """"""
        if error_type == 'http':
            self.http_errors += 1
        elif error_type == 'timeout':
            self.timeout_errors += 1
        elif error_type == 'parse':
            self.parse_errors += 1
        else:
            self.other_errors += 1
        
        self.error_details.append({
            'type': error_type,
            'timestamp': datetime.now().isoformat(),
            **details
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """"""
        return {
            'http_errors': self.http_errors,
            'timeout_errors': self.timeout_errors,
            'parse_errors': self.parse_errors,
            'other_errors': self.other_errors,
            'total_retries': self.total_retries,
            'total_errors': self.http_errors + self.timeout_errors + self.parse_errors + self.other_errors
        }


@dataclass
class PerformanceStats:
    """"""
    execution_times: List[float] = field(default_factory=list)
    memory_usage: List[float] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def add_execution_time(self, duration: float):
        """"""
        self.execution_times.append(duration)
    
    def add_memory_usage(self, usage_mb: float):
        """"""
        self.memory_usage.append(usage_mb)
    
    def get_current_memory_usage(self) -> float:
        """MB"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def get_summary(self) -> Dict[str, Any]:
        """"""
        if not self.execution_times:
            return {
                'avg_time': 0,
                'max_time': 0,
                'min_time': 0,
                'total_time': 0,
                'avg_memory': 0,
                'max_memory': 0,
                'current_memory': self.get_current_memory_usage()
            }
        
        return {
            'avg_time': sum(self.execution_times) / len(self.execution_times),
            'max_time': max(self.execution_times),
            'min_time': min(self.execution_times),
            'total_time': sum(self.execution_times),
            'avg_memory': sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
            'max_memory': max(self.memory_usage) if self.memory_usage else 0,
            'current_memory': self.get_current_memory_usage()
        }


class OptimizedDataFetcher:
    """
    requests
    
    :
    1. RequestsScraperSelenium
    2. 
    3. 
    4. 
    5. 10-20
    6. 3
    7. 
    8. 
    9. 
    """
    
    def __init__(self, delay: int = 1, max_workers: int = 5, max_retries: int = 3):
        """


        Args:
            delay: - requests
            max_workers:
            max_retries:
        """
        self.delay = delay
        self.max_workers = max_workers
        self.max_retries = max_retries

        # RequestsScraper
        self.scraper = RequestsScraper()

        #
        self._setup_optimized_session()

        #
        self.seiseki_parser = SeisekiParser()
        self.shutsuba_parser = SyutubaParser()
        self.cyokyo_parser = CyokyoParser()
        self.danwa_parser = DanwaParser()
        self.nittei_parser = NitteiParser()

        #
        self.error_stats = ErrorStats()
        self.performance_stats = PerformanceStats()

        #
        self._connection_lock = threading.Lock()
        self._active_connections = 0
        self._max_connections = max_workers * 2  #

        # race_idと実際の開催日のマッピング
        self.race_id_to_date_map = {} 
        
        # 
        ensure_batch_directories()
        
        # 
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("[START] DataFetcherrequests")
        self.logger.info(f"[SETTING] : delay={delay}, max_workers={max_workers}, max_retries={max_retries}")
    
    def _setup_optimized_session(self):
        """HTTP"""
        self.session = requests.Session()
        
        # 
        # urllib3
        try:
            #  (urllib3 >= 1.26)
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
                backoff_factor=1  # 
            )
        except TypeError:
            #  (urllib3 < 1.26)
            retry_strategy = Retry(
                total=self.max_retries,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
                backoff_factor=1  # 
            )
        
        # HTTP
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.max_workers * 2,
            pool_maxsize=self.max_workers * 4,
            pool_block=False
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 
        self.session.timeout = (5, 30)  # (, )
    
    def _adjust_connection_pool(self):
        """"""
        with self._connection_lock:
            # 
            if self._active_connections > self._max_connections * 0.8:
                # 80%
                new_max = min(self._max_connections * 1.5, 100)  # 100
                self._max_connections = int(new_max)
                self.logger.info(f"[UP] : {self._max_connections}")
            elif self._active_connections < self._max_connections * 0.3:
                # 30%
                new_max = max(self._max_connections * 0.7, self.max_workers * 2)
                self._max_connections = int(new_max)
                self.logger.info(f"[CHART] : {self._max_connections}")
    
    def parse_html_content_direct(self, html_content: str, data_type: str, race_id: str) -> Optional[Dict[str, Any]]:
        """
        HTML
        
        Args:
            html_content: HTML
            data_type: 
            race_id: ID
            
        Returns:
            Optional[Dict[str, Any]]: 
        """
        try:
            # BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            if data_type == 'seiseki':
                # SeisekiParser
                race_info = self.seiseki_parser._extract_race_info(soup)
                results = self.seiseki_parser._extract_results(soup)
                interviews_and_memos = self.seiseki_parser._extract_interviews_and_memos(soup)
                results = self.seiseki_parser._merge_interview_memo_data(results, interviews_and_memos)
                race_info['race_id'] = race_id  # race_idを追加
                return {"race_info": race_info, "results": results}
                
            elif data_type == 'shutsuba':
                # 
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                    tmp_file.write(html_content)
                    tmp_file_path = tmp_file.name
                try:
                    data = self.shutsuba_parser.parse(tmp_file_path)
                    if data and 'race_info' in data:
                        data['race_info']['race_id'] = race_id  # race_idを追加
                    return data
                finally:
                    os.unlink(tmp_file_path)
                    
            elif data_type == 'cyokyo':
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                    tmp_file.write(html_content)
                    tmp_file_path = tmp_file.name
                try:
                    data = self.cyokyo_parser.parse(tmp_file_path)
                    if data and 'race_info' in data:
                        data['race_info']['race_id'] = race_id  # race_idを追加
                    return data
                finally:
                    os.unlink(tmp_file_path)
                    
            elif data_type == 'danwa':
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                    tmp_file.write(html_content)
                    tmp_file_path = tmp_file.name
                try:
                    data = self.danwa_parser.parse(tmp_file_path)
                    if data and 'race_info' in data:
                        data['race_info']['race_id'] = race_id  # race_idを追加
                    return data
                finally:
                    os.unlink(tmp_file_path)
                    
            elif data_type == 'syoin':
                # 前走インタビューパーサー
                from ..parsers.syoin_parser import SyoinParser
                syoin_parser = SyoinParser()
                data = syoin_parser.parse_html_content(html_content)
                if data and 'race_info' in data:
                    data['race_info']['race_id'] = race_id  # race_idを追加
                return data
                    
            elif data_type == 'paddok':
                # パドック情報パーサー
                from ..parsers.paddok_parser import PaddokParser
                paddok_parser = PaddokParser()
                data = paddok_parser.parse_html_content(html_content)
                if data and 'race_info' in data:
                    data['race_info']['race_id'] = race_id  # race_idを追加
                return data
                    
        except Exception as e:
            self.logger.error(f"[ERROR] {data_type}: {e}")
            return None
    
    def _fetch_with_retry(self, fetch_func, *args, **kwargs) -> Tuple[bool, Any]:
        """
        
        
        Args:
            fetch_func: 
            *args: 
            **kwargs: 
            
        Returns:
            Tuple[bool, Any]: (, )
        """
        last_error = None
        backoff_times = [1, 2, 4]  # 
        
        for attempt in range(self.max_retries):
            try:
                result = fetch_func(*args, **kwargs)
                if result:
                    return True, result
                else:
                    # 
                    last_error = "Empty result"
                    
            except requests.exceptions.Timeout as e:
                last_error = e
                self.error_stats.add_error('timeout', {
                    'attempt': attempt + 1,
                    'function': fetch_func.__name__,
                    'error': str(e)
                })
                self.logger.warning(f"[TIME]  ( {attempt + 1}/{self.max_retries}): {e}")
                
            except requests.exceptions.HTTPError as e:
                last_error = e
                self.error_stats.add_error('http', {
                    'attempt': attempt + 1,
                    'function': fetch_func.__name__,
                    'status_code': e.response.status_code if e.response else None,
                    'error': str(e)
                })
                self.logger.warning(f" HTTP ( {attempt + 1}/{self.max_retries}): {e}")
                
            except Exception as e:
                last_error = e
                self.error_stats.add_error('other', {
                    'attempt': attempt + 1,
                    'function': fetch_func.__name__,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
                self.logger.warning(f"[WARN]  ( {attempt + 1}/{self.max_retries}): {e}")
            
            # 
            if attempt < self.max_retries - 1:
                wait_time = backoff_times[attempt] if attempt < len(backoff_times) else backoff_times[-1]
                self.logger.info(f"⏳ {wait_time}...")
                time.sleep(wait_time)
                self.error_stats.total_retries += 1
        
        return False, last_error
    
    def fetch_single_race_data_fast(self, race_id: str, data_type: str) -> bool:
        """
        
        
        Args:
            race_id: ID
            data_type: 
            
        Returns:
            bool: True
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"[FAST] {data_type}: {race_id}")
            
            # 
            self.performance_stats.add_memory_usage(
                self.performance_stats.get_current_memory_usage()
            )
            
            # 
            with self._connection_lock:
                self._active_connections += 1
            
            try:
                # 
                fetch_func = None
                if data_type == 'seiseki':
                    fetch_func = self.scraper.scrape_seiseki_page
                elif data_type == 'shutsuba':
                    fetch_func = self.scraper.scrape_syutuba_page
                elif data_type == 'cyokyo':
                    fetch_func = self.scraper.scrape_cyokyo_page
                elif data_type == 'danwa':
                    fetch_func = self.scraper.scrape_danwa_page
                elif data_type == 'syoin':
                    fetch_func = self.scraper.scrape_syoin_page
                elif data_type == 'paddok':
                    fetch_func = self.scraper.scrape_paddok_page
                
                if not fetch_func:
                    self.logger.error(f"[ERROR] : {data_type}")
                    return False
                
                success, html_content = self._fetch_with_retry(fetch_func, race_id)
                
                if not success:
                    self.logger.error(f"[ERROR] {data_type}: {race_id} - {html_content}")
                    return False
                
                # 
                parsed_data = self.parse_html_content_direct(html_content, data_type, race_id)
                
                if not parsed_data:
                    self.error_stats.add_error('parse', {
                        'race_id': race_id,
                        'data_type': data_type
                    })
                    self.logger.error(f"[ERROR] {data_type}: {race_id}")
                    return False
                
                # JSON（実際の開催日を使用）
                actual_date = self.race_id_to_date_map.get(race_id)
                json_file_path = get_json_file_path(data_type, race_id, actual_date)
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"[OK] {data_type} JSON: {json_file_path}")
                
                # requests
                if self.delay > 0:
                    time.sleep(self.delay)
                
                return True
                
            finally:
                # 
                with self._connection_lock:
                    self._active_connections -= 1
                
                # 
                self._adjust_connection_pool()
                
        except Exception as e:
            self.error_stats.add_error('other', {
                'race_id': race_id,
                'data_type': data_type,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            self.logger.error(f"[ERROR] {data_type}: {e}")
            return False
            
        finally:
            # 
            execution_time = time.time() - start_time
            self.performance_stats.add_execution_time(execution_time)
            self.logger.debug(f"[TIME] : {execution_time:.2f}")
    
    def fetch_race_schedule_fast(self, date_str: str) -> bool:
        """
        
        JSON
        
        Args:
            date_str:  (YYYYMMDD)
            
        Returns:
            bool: TrueTrue
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"[FAST] : {date_str}")
            
            # 
            self.performance_stats.add_memory_usage(
                self.performance_stats.get_current_memory_usage()
            )
            
            # 
            url = f"https://p.keibabook.co.jp/cyuou/nittei/{date_str}"
            success, html_content = self._fetch_with_retry(self.scraper.scrape, url)
            
            if not success:
                self.logger.error(f"[ERROR] : {date_str} - {html_content}")
                return False
            
            # NitteiParser
            parsed_data = self.nittei_parser.parse_with_date(html_content, date_str)
            
            if not parsed_data:
                self.logger.error(f"[ERROR] : {date_str}")
                return False
            
            # 
            total_races = parsed_data.get('total_races', 0)
            kaisai_count = parsed_data.get('kaisai_count', 0)
            
            if total_races == 0 or kaisai_count == 0:
                self.logger.info(f"📅 開催なし: {date_str} - レース数: {total_races}, 開催場数: {kaisai_count}")
                self.logger.info(f"⏭ フォルダ・JSONファイルの作成をスキップ")
                return True  # 開催なしでも成功として扱う
            
            # JSON保存（開催がある場合のみ）
            json_file_path = get_json_file_path('nittei', date_str, create_dir=True)
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            
            # レースID保存（開催がある場合のみ - フォルダ作成を有効化）
            race_ids_file = get_race_ids_file_path(date_str, create_dir=True)
            race_ids_data = {
                'date': date_str,
                'kaisai_data': {}
            }
            
            # ID
            kaisai_data = parsed_data.get('kaisai_data', {})
            for venue, races in kaisai_data.items():
                race_ids_data['kaisai_data'][venue] = races
            
            with open(race_ids_file, 'w', encoding='utf-8') as f:
                json.dump(race_ids_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"[OK] : {json_file_path}")
            self.logger.info(f"[RACE] : {kaisai_count}, {total_races}")
            self.logger.info(f"[OK] ID: {race_ids_file}")
            
            return True
            
        except Exception as e:
            self.error_stats.add_error('other', {
                'date_str': date_str,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            self.logger.error(f"[ERROR] : {e}")
            return False
            
        finally:
            # 
            execution_time = time.time() - start_time
            self.performance_stats.add_execution_time(execution_time)
            self.logger.debug(f"[TIME] : {execution_time:.2f}")
    
    def fetch_all_race_data_parallel_fast(self, date_str: str, data_types: List[str]) -> Dict[str, Any]:
        """
        
        
        Args:
            date_str:  (YYYYMMDD)
            data_types: 
            
        Returns:
            Dict[str, Any]: 
        """
        start_time = time.time()
        
        self.logger.info(f"[START] : {date_str}")
        self.logger.info(f"[DATA] : {', '.join(data_types)}")
        self.logger.info(f"[FAST] : {self.max_workers}")
        self.logger.info(f"[HOT] RequestsScraperSelenium")
        
        # ID
        race_ids = self.get_race_ids_from_file(date_str)
        if not race_ids:
            self.logger.error(f"[ERROR] ID: {date_str}")
            return {'success': False, 'error': 'No race IDs found'}
        
        # 
        tasks = []
        for race_id in race_ids:
            for data_type in data_types:
                tasks.append((race_id, data_type))
        
        self.logger.info(f"[LIST] : {len(tasks)}{len(race_ids)} × {len(data_types)}")
        
        # 
        total_success = 0
        total_failed = 0
        results_by_type = {data_type: {'success': 0, 'failed': 0} for data_type in data_types}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 
            future_to_task = {
                executor.submit(self.fetch_single_race_data_fast, race_id, data_type): (race_id, data_type)
                for race_id, data_type in tasks
            }
            
            # 
            completed_tasks = 0
            for future in as_completed(future_to_task):
                race_id, data_type = future_to_task[future]
                completed_tasks += 1
                
                try:
                    success = future.result()
                    if success:
                        results_by_type[data_type]['success'] += 1
                        total_success += 1
                    else:
                        results_by_type[data_type]['failed'] += 1
                        total_failed += 1
                        
                    # 
                    if completed_tasks % 10 == 0 or completed_tasks == len(tasks):
                        progress = (completed_tasks / len(tasks)) * 100
                        elapsed = time.time() - start_time
                        self.logger.info(f"[UP] : {completed_tasks}/{len(tasks)} ({progress:.1f}%) - : {elapsed:.1f}")
                        
                except Exception as e:
                    self.logger.error(f"[ERROR]  ({race_id}, {data_type}): {e}")
                    results_by_type[data_type]['failed'] += 1
                    total_failed += 1
        
        # 
        total_time = time.time() - start_time
        
        # 
        perf_summary = self.performance_stats.get_summary()
        error_summary = self.error_stats.get_summary()
        
        # 
        summary = {
            'success': True,
            'date': date_str,
            'total_races': len(race_ids),
            'total_tasks': len(tasks),
            'total_success': total_success,
            'total_failed': total_failed,
            'results_by_type': results_by_type,
            'processing_time_seconds': round(total_time, 2),
            'tasks_per_second': round(len(tasks) / total_time, 2) if total_time > 0 else 0,
            'performance_stats': perf_summary,
            'error_stats': error_summary,
            'quality_score': round((total_success / len(tasks)) * 100, 2) if len(tasks) > 0 else 0
        }
        
        self.logger.info(f"[OK] ")
        self.logger.info(f"[DATA] : {total_success}, : {total_failed}")
        self.logger.info(f"[TIME] : {total_time:.2f}")
        self.logger.info(f"[START] : {summary['tasks_per_second']:.2f}/")
        self.logger.info(f"[UP] : {summary['quality_score']:.1f}%")
        
        # 
        self.logger.info(f"[SAVE] : ={perf_summary['current_memory']:.1f}MB, ={perf_summary['max_memory']:.1f}MB")
        self.logger.info(f"[FAST] : ={perf_summary['avg_time']:.2f}, ={perf_summary['max_time']:.2f}, ={perf_summary['min_time']:.2f}")
        
        # 
        if error_summary['total_errors'] > 0:
            self.logger.warning(f"[WARN] : HTTP={error_summary['http_errors']}, ={error_summary['timeout_errors']}, ={error_summary['parse_errors']}, ={error_summary['other_errors']}")
            self.logger.warning(f"[REFRESH] : {error_summary['total_retries']}")
        
        # 95%
        if summary['quality_score'] < 95:
            self.logger.warning(f"[WARN] : {summary['quality_score']:.1f}% < 95%")
            self._generate_quality_alert(summary)
        
        return summary
    
    def _generate_quality_alert(self, summary: Dict[str, Any]):
        """"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': 'quality_alert',
            'quality_score': summary['quality_score'],
            'total_failed': summary['total_failed'],
            'error_details': self.error_stats.error_details[-10:]  # 10
        }
        
        # 
        self.logger.critical(f" : {json.dumps(alert, ensure_ascii=False, indent=2)}")
        
        # 
        alert_dir = os.path.join('batch_data', 'alerts')
        os.makedirs(alert_dir, exist_ok=True)
        alert_file = os.path.join(alert_dir, f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(alert_file, 'w', encoding='utf-8') as f:
            json.dump(alert, f, ensure_ascii=False, indent=2)
    
    def get_race_ids_from_file(self, date_str: str) -> List[str]:
        """
        IDID

        Args:
            date_str:  (YYYYMMDD)

        Returns:
            List[str]: ID
        """
        try:
            race_ids_file = get_race_ids_file_path(date_str)

            if not os.path.exists(race_ids_file):
                self.logger.warning(f"[WARN] ID: {race_ids_file}")
                return []

            with open(race_ids_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            race_ids = []
            kaisai_data = data.get('kaisai_data', {})

            # race_idと実際の日付のマッピングをクリアして再作成
            self.race_id_to_date_map.clear()

            for venue, races in kaisai_data.items():
                for race in races:
                    race_id = race.get('race_id')
                    if race_id:
                        race_ids.append(race_id)
                        # マッピングに追加（実際の開催日を保存）
                        self.race_id_to_date_map[race_id] = date_str

            self.logger.info(f"[LIST] ID: {len(race_ids)}")
            return race_ids
            
        except Exception as e:
            self.logger.error(f"[ERROR] ID: {e}")
            return []
    
    def get_statistics_report(self) -> Dict[str, Any]:
        """
        
        
        Returns:
            Dict[str, Any]: 
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'performance': self.performance_stats.get_summary(),
            'errors': self.error_stats.get_summary(),
            'error_details': self.error_stats.error_details,
            'connection_pool': {
                'active': self._active_connections,
                'max': self._max_connections
            }
        }
    
    def reset_statistics(self):
        """
        
        """
        self.error_stats = ErrorStats()
        self.performance_stats = PerformanceStats()
        self.logger.info("[DATA] ")
    
    def close(self):
        """
        
        """
        # 
        final_report = self.get_statistics_report()
        self.logger.info(f"[DATA] : {json.dumps(final_report, ensure_ascii=False, indent=2)}")
        
        # 
        if hasattr(self, 'session'):
            self.session.close()
        
        if hasattr(self.scraper, 'close'):
            self.scraper.close()
            
        self.logger.info(" OptimizedDataFetcher") 
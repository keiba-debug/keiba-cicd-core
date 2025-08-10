#!/usr/bin/env python3
"""



"""

import os
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class FileOrganizer:
    """
    
    
    //
    """
    
    def __init__(self, root_dir: str = None):
        """
        
        
        Args:
            root_dir: 
        """
        self.logger = logging.getLogger(__name__)
        self.root_dir = root_dir or os.getenv('KEIBA_DATA_ROOT_DIR', './data/keibabook')
        
        # 
        self.organized_root = os.path.join(self.root_dir, 'organized')
        
        # race_idと実際の開催日のマッピング
        self.actual_date_map = {}
        
        # 
        self.venue_map = {
            '01': '', '02': '', '03': '', '04': '',
            '05': '', '06': '', '07': '', '08': '',
            '09': '', '10': ''
        }
        
        # 
        self.data_type_map = {
            'nittei': '',
            'seiseki': '',
            'shutsuba': '',
            'syutuba': '',  # 
            'cyokyo': '',
            'danwa': '',
            'syoin': '',
            'paddok': '',
            'integrated': ''
        }
    
    def load_actual_dates(self):
        """
        race_idsフォルダから実際の開催日マッピングを読み込む
        """
        race_ids_dir = os.path.join(self.root_dir, 'race_ids')
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
                        for race in races:
                            race_id = race.get('race_id', '')
                            if race_id:
                                # race_idから実際の開催日付を設定
                                self.actual_date_map[race_id] = date_str
                except Exception as e:
                    self.logger.warning(f"Failed to load {file_path}: {e}")
    
    def _extract_info_from_filename(self, filename: str) -> Optional[Dict]:
        """
        
        
        Args:
            filename: 
            
        Returns:
            Optional[Dict]: 
        """
        try:
            # 
            name = os.path.splitext(filename)[0]
            
            # 1: datatype_YYYYMMDDVVRR.json (: seiseki_202501010511.json)
            if '_' in name:
                parts = name.split('_')
                if len(parts) == 2:
                    data_type = parts[0]
                    identifier = parts[1]
                    
                    # ID (12)
                    if len(identifier) == 12:
                        return {
                            'type': 'race',
                            'data_type': data_type,
                            'date': identifier[:8],
                            'venue_code': identifier[8:10],
                            'race_number': identifier[10:12],
                            'race_id': identifier
                        }
                    #  (8)
                    elif len(identifier) == 8:
                        return {
                            'type': 'date',
                            'data_type': data_type,
                            'date': identifier
                        }
            
            # 2: integrated_YYYYMMDDVVRR.json
            if name.startswith('integrated_'):
                race_id = name.replace('integrated_', '')
                if len(race_id) == 12:
                    return {
                        'type': 'integrated',
                        'data_type': 'integrated',
                        'date': race_id[:8],
                        'venue_code': race_id[8:10],
                        'race_number': race_id[10:12],
                        'race_id': race_id
                    }
            
            # 3: YYYYMMDD_info.json (race_ids)
            if name.endswith('_info'):
                date = name.replace('_info', '')
                if len(date) == 8:
                    return {
                        'type': 'race_ids',
                        'data_type': 'race_ids',
                        'date': date
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f": {filename}, {e}")
            return None
    
    def _get_organized_path(self, file_info: Dict) -> str:
        """
        
        
        Args:
            file_info: 
            
        Returns:
            str: 
        """
        # race_idがある場合は実際の開催日付を使用
        if 'race_id' in file_info and file_info['race_id'] in self.actual_date_map:
            date_str = self.actual_date_map[file_info['race_id']]
        else:
            date_str = file_info['date']
        
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        
        # : organized///
        base_path = os.path.join(self.organized_root, year, month, day)
        
        # 
        if file_info['type'] == 'race':
            # : /////
            venue_code = file_info['venue_code']
            venue_name = self.venue_map.get(venue_code, f'{venue_code}')
            data_type_name = self.data_type_map.get(file_info['data_type'], file_info['data_type'])
            
            return os.path.join(base_path, venue_name, data_type_name)
            
        elif file_info['type'] == 'integrated':
            # : ////
            return os.path.join(base_path, '')
            
        elif file_info['type'] == 'race_ids':
            # ID: ////
            return os.path.join(base_path, '')
            
        else:
            # : ////
            data_type_name = self.data_type_map.get(file_info['data_type'], file_info['data_type'])
            return os.path.join(base_path, data_type_name)
    
    def organize_file(self, source_file: str, copy: bool = False) -> Optional[str]:
        """
        
        
        Args:
            source_file: 
            copy: False
            
        Returns:
            Optional[str]: 
        """
        try:
            if not os.path.exists(source_file):
                self.logger.error(f": {source_file}")
                return None
            
            filename = os.path.basename(source_file)
            file_info = self._extract_info_from_filename(filename)
            
            if not file_info:
                self.logger.warning(f": {filename}")
                return None
            
            # 
            target_dir = self._get_organized_path(file_info)
            os.makedirs(target_dir, exist_ok=True)
            
            target_file = os.path.join(target_dir, filename)
            
            # 
            if copy:
                shutil.copy2(source_file, target_file)
                self.logger.info(f"[FILE] : {filename} -> {target_dir}")
            else:
                shutil.move(source_file, target_file)
                self.logger.info(f"[FILE] : {filename} -> {target_dir}")
            
            return target_file
            
        except Exception as e:
            self.logger.error(f": {source_file}, {e}")
            return None
    
    def organize_directory(self, source_dir: str = None, copy: bool = False) -> Dict:
        """
        
        
        Args:
            source_dir: root_dir
            copy: False
            
        Returns:
            Dict: 
        """
        source_dir = source_dir or self.root_dir
        
        self.logger.info(f"[FOLDER] : {source_dir}")
        
        # JSON
        json_files = []
        for file in os.listdir(source_dir):
            if file.endswith('.json'):
                json_files.append(os.path.join(source_dir, file))
        
        # integrated
        integrated_dir = os.path.join(source_dir, 'integrated')
        if os.path.exists(integrated_dir):
            for file in os.listdir(integrated_dir):
                if file.endswith('.json'):
                    json_files.append(os.path.join(integrated_dir, file))
        
        # race_ids
        race_ids_dir = os.path.join(source_dir, 'race_ids')
        if os.path.exists(race_ids_dir):
            for file in os.listdir(race_ids_dir):
                if file.endswith('.json'):
                    json_files.append(os.path.join(race_ids_dir, file))
        
        self.logger.info(f"[DATA] : {len(json_files)}")
        
        # 
        success_count = 0
        failed_count = 0
        organized_paths = []
        
        for json_file in json_files:
            result = self.organize_file(json_file, copy=copy)
            if result:
                success_count += 1
                organized_paths.append(result)
            else:
                failed_count += 1
        
        # 
        summary = {
            'success': True,
            'total_files': len(json_files),
            'success_count': success_count,
            'failed_count': failed_count,
            'organized_root': self.organized_root,
            'organized_paths': organized_paths
        }
        
        self.logger.info(f"[OK] :  {success_count},  {failed_count}")
        
        return summary
    
    def create_index(self) -> Dict:
        """
        
        
        Returns:
            Dict: 
        """
        self.logger.info("[INDEX] ")
        
        index = {
            'created_at': datetime.now().isoformat(),
            'root_dir': self.organized_root,
            'structure': {},
            'statistics': {
                'total_files': 0,
                'by_year': {},
                'by_venue': {},
                'by_data_type': {}
            }
        }
        
        # 
        for root, dirs, files in os.walk(self.organized_root):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.organized_root)
                    
                    # 
                    parts = rel_path.split(os.sep)
                    if len(parts) >= 3:
                        year = parts[0]
                        month = parts[1]
                        day = parts[2]
                        
                        # 
                        index['statistics']['total_files'] += 1
                        
                        # 
                        if year not in index['statistics']['by_year']:
                            index['statistics']['by_year'][year] = 0
                        index['statistics']['by_year'][year] += 1
                        
                        # 
                        if year not in index['structure']:
                            index['structure'][year] = {}
                        if month not in index['structure'][year]:
                            index['structure'][year][month] = {}
                        if day not in index['structure'][year][month]:
                            index['structure'][year][month][day] = []
                        
                        index['structure'][year][month][day].append(rel_path)
                        
                        # 
                        if len(parts) >= 4:
                            # 
                            if len(parts) >= 5:
                                venue = parts[3]
                                if venue not in index['statistics']['by_venue']:
                                    index['statistics']['by_venue'][venue] = 0
                                index['statistics']['by_venue'][venue] += 1
                                
                                # 
                                data_type = parts[4] if len(parts) > 4 else parts[3]
                                if data_type not in index['statistics']['by_data_type']:
                                    index['statistics']['by_data_type'][data_type] = 0
                                index['statistics']['by_data_type'][data_type] += 1
        
        # 
        index_file = os.path.join(self.organized_root, 'index.json')
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"[OK] : {index_file}")
        self.logger.info(f"[DATA] : {index['statistics']['total_files']}")
        
        return index
    
    def find_files(self, date: str = None, venue: str = None, 
                   data_type: str = None) -> List[str]:
        """
        
        
        Args:
            date:  (YYYYMMDD)
            venue: 
            data_type: 
            
        Returns:
            List[str]: 
        """
        matches = []
        
        # 
        search_path = self.organized_root
        
        if date:
            year = date[:4]
            month = date[4:6]
            day = date[6:8]
            search_path = os.path.join(search_path, year, month, day)
        
        if not os.path.exists(search_path):
            return matches
        
        #  データタイプのサブフォルダ名（空の場合はファイル名で判定）
        target_subdir = None
        filename_prefix = None
        if data_type:
            mapped = self.data_type_map.get(data_type, data_type)
            if mapped:
                target_subdir = mapped
            else:
                # サブフォルダを使わないデータタイプ（例: syoin/paddok/integrated）はファイル名プレフィクスで判定
                filename_prefix = f"{data_type}_"
        
        # 
        for root, dirs, files in os.walk(search_path):
            #  競馬場
            if venue and venue not in root:
                continue
            
            # サブフォルダ名でのフィルタ（該当する場合のみ）
            if target_subdir and target_subdir not in root:
                continue
            
            for file in files:
                if not file.endswith('.json'):
                    continue
                
                # ファイル名プレフィクスでのフィルタ（サブフォルダを使わないタイプのみ）
                if filename_prefix and not file.startswith(filename_prefix) and not file.startswith('integrated_'):
                    # integrated は filename_prefix ではなく integrated_ 固定
                    continue
                
                matches.append(os.path.join(root, file))
        
        return matches
    
    def get_storage_stats(self) -> Dict:
        """
        
        
        Returns:
            Dict: 
        """
        stats = {
            'total_size_bytes': 0,
            'total_size_mb': 0,
            'file_count': 0,
            'by_data_type': {}
        }
        
        for root, dirs, files in os.walk(self.organized_root):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    
                    stats['total_size_bytes'] += file_size
                    stats['file_count'] += 1
                    
                    # 
                    for dtype, dtype_name in self.data_type_map.items():
                        if dtype in file or dtype_name in root:
                            if dtype not in stats['by_data_type']:
                                stats['by_data_type'][dtype] = {
                                    'count': 0,
                                    'size_bytes': 0
                                }
                            stats['by_data_type'][dtype]['count'] += 1
                            stats['by_data_type'][dtype]['size_bytes'] += file_size
                            break
        
        stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
        
        # MB
        for dtype in stats['by_data_type']:
            size_bytes = stats['by_data_type'][dtype]['size_bytes']
            stats['by_data_type'][dtype]['size_mb'] = round(size_bytes / (1024 * 1024), 2)
        
        return stats
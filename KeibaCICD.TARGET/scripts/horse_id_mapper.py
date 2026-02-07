#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
馬ID変換ユーティリティ（KeibaCICD用 馬名辞書）

競馬ブックの馬名とJRA-VAN血統登録番号（10桁）の対応を、馬名辞書インデックスで行う。
TARGETのUM_DATA（UM{年}{半期}.DAT）を読み、10歳まで対応するため直近約20ファイルで
馬名→血統番号の辞書を構築する。初期セットアップで1回 --build-index を実行すればよい。
競馬ブック馬ID（umacd）とのマッチング結果を将来インデックスに含めることも可能。

Usage:
    # 初期セットアップ: 辞書を構築（KeibaCICD用に1回実行）
    python horse_id_mapper.py --build-index
    
    # 馬名から10桁IDを取得
    python horse_id_mapper.py --name "ディープインパクト"
    
    # インデックス情報表示
    python horse_id_mapper.py --info
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# 環境変数読み込み
try:
    from dotenv import load_dotenv
    env_candidates = [
        Path(__file__).resolve().parents[2] / "KeibaCICD.keibabook" / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass


# =============================================================================
# 定数
# =============================================================================

# JRA-VAN データルート
JV_DATA_ROOT = Path(os.getenv("JV_DATA_ROOT_DIR", "C:/TFJV"))
UM_DATA_ROOT = JV_DATA_ROOT / "UM_DATA"

# インデックスファイルパス
try:
    # 新しいデータディレクトリ構造を使用（推奨）
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from common.config import get_target_data_dir
    HORSE_NAME_INDEX_FILE = get_target_data_dir() / "horse_name_index.json"
except ImportError:
    # フォールバック: 旧データディレクトリ（後方互換性）
    INDEX_DIR = Path(__file__).parent.parent / "data"
    HORSE_NAME_INDEX_FILE = INDEX_DIR / "horse_name_index.json"

# UM_DATA レコード長（JV_UM_UMA 仕様: 1609バイト）
UM_RECORD_LEN = 1609

# 馬名・血統番号のオフセット（0-based）
# KettoNum: 12-21 (10バイト), Bamei: 47-82 (36バイト)
OFFSET_KETTO = 11
OFFSET_BAMEI = 46
LEN_BAMEI = 36

# インデックス構築対象: 直近この年数分（10歳まで対応 ≒ 約20ファイル）
YEARS_BACK = 11


# =============================================================================
# Shift-JIS デコード
# =============================================================================

def decode_sjis(data: bytes) -> str:
    """Shift-JISバイト列を文字列にデコード"""
    try:
        return data.decode('shift_jis', errors='replace').strip()
    except Exception:
        return ""


# =============================================================================
# UM_DATA ファイル操作
# =============================================================================

def get_um_files(max_years_back: int = YEARS_BACK) -> list:
    """
    UM_DATAファイルリストを取得。
    ファイル名: UM{年}{半期}.DAT（例: UM20211.DAT, UM20212.DAT）
    直近 max_years_back 年分のみ取得（10歳まで対応で約20ファイル）。
    """
    files = []
    if not UM_DATA_ROOT.exists():
        print(f"Warning: UM_DATA directory not found: {UM_DATA_ROOT}")
        return files

    from datetime import date
    current_year = date.today().year
    start_year = current_year - max_years_back

    for year in range(start_year, current_year + 2):
        year_dir = UM_DATA_ROOT / str(year)
        if not year_dir.is_dir():
            continue
        for half in (1, 2):
            um_file = year_dir / f"UM{year}{half}.DAT"
            if um_file.exists():
                files.append(um_file)

    return sorted(files)


# =============================================================================
# インデックス管理
# =============================================================================

class HorseIdMapper:
    """馬IDマッパー（シングルトン的に使用）"""
    
    _instance = None
    _index: Dict[str, str] = {}
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._loaded:
            self._load_index()
    
    def _load_index(self) -> None:
        """インデックスをファイルから読み込み"""
        if HORSE_NAME_INDEX_FILE.exists():
            try:
                with open(HORSE_NAME_INDEX_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._index = data.get('index', {})
                self._loaded = True
                print(f"[HorseIdMapper] Loaded {len(self._index)} entries from cache")
            except Exception as e:
                print(f"[HorseIdMapper] Failed to load index: {e}")
                self._index = {}
        else:
            print(f"[HorseIdMapper] Index file not found, building from UM_DATA...")
            self.rebuild_index()
    
    def rebuild_index(self) -> int:
        """UM_DATAからインデックスを再構築"""
        print("[HorseIdMapper] Building horse name index from UM_DATA...")
        self._index = {}
        
        um_files = get_um_files()
        if not um_files:
            print("[HorseIdMapper] No UM_DATA files found")
            return 0
        
        for um_file in um_files:
            try:
                with open(um_file, 'rb') as f:
                    data = f.read()
                
                num_records = len(data) // UM_RECORD_LEN
                added = 0
                for i in range(num_records):
                    offset = i * UM_RECORD_LEN
                    ketto = decode_sjis(data[offset + OFFSET_KETTO:offset + OFFSET_KETTO + 10]).strip()
                    name = decode_sjis(data[offset + OFFSET_BAMEI:offset + OFFSET_BAMEI + LEN_BAMEI]).strip()
                    
                    # 血統番号10桁・馬名が有効な場合のみ登録
                    if ketto and len(ketto) == 10 and name and name not in self._index:
                        self._index[name] = ketto
                        added += 1
                if added or num_records:
                    print(f"  {um_file.name}: {num_records} records, +{added} new")
            except Exception as e:
                print(f"[HorseIdMapper] Error reading {um_file}: {e}")
        
        # インデックスをファイルに保存
        self._save_index()
        self._loaded = True
        
        print(f"[HorseIdMapper] Built index with {len(self._index)} entries")
        return len(self._index)
    
    def _save_index(self) -> None:
        """インデックスをファイルに保存"""
        HORSE_NAME_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'meta': {
                'created_at': datetime.now().isoformat(),
                'count': len(self._index),
                'source': str(UM_DATA_ROOT),
            },
            'index': self._index
        }
        
        try:
            with open(HORSE_NAME_INDEX_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[HorseIdMapper] Saved index to {HORSE_NAME_INDEX_FILE}")
        except Exception as e:
            print(f"[HorseIdMapper] Failed to save index: {e}")
    
    def get_jvn_id(self, horse_name: str) -> Optional[str]:
        """馬名からJRA-VAN 10桁IDを取得"""
        return self._index.get(horse_name.strip())
    
    def get_index(self) -> Dict[str, str]:
        """インデックス全体を取得"""
        return self._index.copy()
    
    def get_count(self) -> int:
        """登録馬数を取得"""
        return len(self._index)
    
    def is_loaded(self) -> bool:
        """インデックスが読み込まれているか"""
        return self._loaded


# =============================================================================
# 便利関数（外部からの簡易アクセス用）
# =============================================================================

def get_jvn_horse_id(horse_name: str) -> Optional[str]:
    """
    馬名からJRA-VAN 10桁IDを取得
    
    Args:
        horse_name: 馬名
    
    Returns:
        10桁の血統登録番号（見つからない場合はNone）
    """
    mapper = HorseIdMapper()
    return mapper.get_jvn_id(horse_name)


def get_horse_name_index() -> Dict[str, str]:
    """
    馬名→10桁ID のインデックスを取得
    
    Returns:
        {馬名: 10桁ID} の辞書
    """
    mapper = HorseIdMapper()
    return mapper.get_index()


def rebuild_horse_index() -> int:
    """
    インデックスを再構築
    
    Returns:
        登録馬数
    """
    mapper = HorseIdMapper()
    return mapper.rebuild_index()


# =============================================================================
# メイン
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='馬ID変換ユーティリティ')
    parser.add_argument('--build-index', action='store_true', help='インデックスを再構築')
    parser.add_argument('--name', type=str, help='馬名から10桁IDを検索')
    parser.add_argument('--info', action='store_true', help='インデックス情報を表示')
    
    args = parser.parse_args()
    
    if args.build_index:
        count = rebuild_horse_index()
        print(f"\n完了: {count} 頭のインデックスを構築しました")
        return
    
    if args.name:
        jvn_id = get_jvn_horse_id(args.name)
        if jvn_id:
            print(f"馬名: {args.name}")
            print(f"JRA-VAN ID: {jvn_id}")
        else:
            print(f"馬名 '{args.name}' は見つかりませんでした")
        return
    
    if args.info:
        mapper = HorseIdMapper()
        print(f"インデックスファイル: {HORSE_NAME_INDEX_FILE}")
        print(f"登録馬数: {mapper.get_count()}")
        print(f"UM_DATAパス: {UM_DATA_ROOT}")
        
        if HORSE_NAME_INDEX_FILE.exists():
            with open(HORSE_NAME_INDEX_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            meta = data.get('meta', {})
            print(f"作成日時: {meta.get('created_at', '不明')}")
        return
    
    # 引数なしの場合はヘルプを表示
    parser.print_help()


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
調教師ID変換ユーティリティ

競馬ブックの厩舎IDとJRA-VAN調教師コードの変換を提供

使用例:
    from common.jravan import get_trainer_jvn_code

    # 競馬ブック厩舎ID → JRA-VAN調教師コード
    jvn_code = get_trainer_jvn_code("ｳ011")
    # => "01234"
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict

# 環境変数読み込み（オプション）
try:
    from dotenv import load_dotenv
    env_candidates = [
        Path(__file__).resolve().parents[3] / "KeibaCICD.keibabook" / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

# インデックスファイルのパス（環境変数を考慮）
try:
    from common.config import get_target_data_dir
    TRAINER_INDEX_FILE = get_target_data_dir() / "trainer_id_index.json"
except ImportError:
    # フォールバック: 相対パス（後方互換性）
    TRAINER_INDEX_FILE = Path(__file__).parent.parent.parent / "data" / "trainer_id_index.json"


class TrainerIdMapper:
    """調教師IDマッパー（シングルトン）"""
    
    _instance = None
    _index: Dict[str, Dict] = {}
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._loaded:
            self._load_index()
    
    def _load_index(self):
        """インデックス読み込み"""
        if TRAINER_INDEX_FILE.exists():
            try:
                with open(TRAINER_INDEX_FILE, 'r', encoding='utf-8') as f:
                    self._index = json.load(f)
                self._loaded = True
            except Exception as e:
                print(f"警告: 調教師インデックスの読み込みに失敗しました: {e}")
                self._index = {}
                self._loaded = True
        else:
            self._index = {}
            self._loaded = True
    
    def get_jvn_code_by_keibabook_id(self, keibabook_id: str) -> Optional[str]:
        """
        競馬ブック厩舎ID → JRA-VAN調教師コード
        
        Args:
            keibabook_id: 競馬ブック厩舎ID（例: "ｳ011"）
        
        Returns:
            JRA-VAN調教師コード（5桁）または None
        """
        trainer = self._index.get(keibabook_id)
        if trainer:
            return trainer.get("jvn_code")
        return None
    
    def get_trainer_info(self, keibabook_id: str) -> Optional[Dict]:
        """
        厩舎IDから調教師情報を取得
        
        Args:
            keibabook_id: 競馬ブック厩舎ID（例: "ｳ011"）
        
        Returns:
            {
                "keibabook_id": "ｳ011",
                "jvn_code": "01234",
                "name": "友道康夫",
                "tozai": "栗東",
                "comment": "コメントデータ..."  # あれば
            } または None
        """
        return self._index.get(keibabook_id)
    
    def reload_index(self):
        """インデックスを再読み込み"""
        self._loaded = False
        self._load_index()


def get_trainer_jvn_code(keibabook_id: str) -> Optional[str]:
    """
    競馬ブック厩舎ID → JRA-VAN調教師コード
    
    Args:
        keibabook_id: 競馬ブック厩舎ID（例: "ｳ011"）
    
    Returns:
        JRA-VAN調教師コード（5桁）または None
    
    使用例:
        >>> get_trainer_jvn_code("ｳ011")
        '01234'
    """
    mapper = TrainerIdMapper()
    return mapper.get_jvn_code_by_keibabook_id(keibabook_id)


def get_trainer_info(keibabook_id: str) -> Optional[Dict]:
    """
    厩舎IDから調教師情報を取得
    
    Args:
        keibabook_id: 競馬ブック厩舎ID（例: "ｳ011"）
    
    Returns:
        調教師情報辞書または None
    """
    mapper = TrainerIdMapper()
    return mapper.get_trainer_info(keibabook_id)

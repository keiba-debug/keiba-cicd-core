#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
keibabook拡張データモデル

JRA-VANベースのレースデータに対するkeibabook固有の拡張情報。
馬番（umaban）をキーとして結合する。
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
import json


@dataclass
class KeibabookTrainingData:
    """調教データ"""
    short_review: str = ''
    attack_explanation: str = ''
    evaluation: str = ''        # A/B/C/D
    training_load: str = ''
    training_rank: str = ''


@dataclass
class KeibabookStableComment:
    """厩舎談話"""
    date: str = ''
    comment: str = ''
    trainer: str = ''


@dataclass
class KeibabookPaddockInfo:
    """パドック情報"""
    mark: str = ''
    mark_score: int = 0
    comment: str = ''
    condition: str = ''


@dataclass
class KeibabookEntryExt:
    """馬番ごとのkeibabook拡張"""
    honshi_mark: str = ''
    mark_point: int = 0
    marks_by_person: Dict[str, str] = field(default_factory=dict)
    aggregate_mark_point: int = 0
    ai_index: Optional[float] = None
    ai_rank: str = ''
    odds_rank: int = 0
    short_comment: str = ''
    training_arrow: str = ''    # ↑/↗/→/↘/↓
    training_data: Optional[KeibabookTrainingData] = None
    stable_comment: Optional[KeibabookStableComment] = None
    paddock_info: Optional[KeibabookPaddockInfo] = None
    previous_race_interview: str = ''
    result_interview: str = ''
    sunpyo: str = ''


@dataclass
class KeibabookExtension:
    """レース単位のkeibabook拡張データ"""
    race_id: str                # 16桁（JRA-VAN形式）
    date: str = ''
    scraped_at: str = ''
    entries: Dict[str, KeibabookEntryExt] = field(default_factory=dict)
    # entriesのキーはumaban（馬番）の文字列

    def to_dict(self) -> Dict:
        d = {
            'race_id': self.race_id,
            'date': self.date,
            'scraped_at': self.scraped_at,
            'entries': {},
        }
        for umaban, ext in self.entries.items():
            d['entries'][umaban] = asdict(ext)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

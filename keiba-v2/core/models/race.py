#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レースデータモデル

JRA-VANベースのレースマスターJSON用データクラス。
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import json
from datetime import datetime


@dataclass
class RaceEntry:
    """レース出走馬エントリ"""
    umaban: int
    wakuban: int
    ketto_num: str
    horse_name: str
    sex_cd: str
    age: int
    jockey_name: str
    trainer_name: str
    futan: float
    horse_weight: int
    horse_weight_diff: int
    finish_position: int
    time: str
    last_3f: float
    last_4f: float
    odds: float
    popularity: int
    corners: List[int] = field(default_factory=list)
    # 将来拡張用（jockey_code, trainer_code）
    jockey_code: str = ''
    trainer_code: str = ''


@dataclass
class RacePace:
    """レースペース情報"""
    s3: Optional[float] = None
    s4: Optional[float] = None
    l3: Optional[float] = None
    l4: Optional[float] = None
    rpci: Optional[float] = None
    race_trend: Optional[str] = None


@dataclass
class RaceMaster:
    """レースマスター（1レース = 1JSON）"""
    race_id: str                # 16桁
    date: str                   # YYYY-MM-DD
    venue_code: str
    venue_name: str
    kai: int
    nichi: int
    race_number: int
    distance: int = 0
    track_type: str = ''        # "turf" or "dirt"
    track_condition: str = ''   # 良/稍重/重/不良
    num_runners: int = 0
    race_name: str = ''
    grade: str = ''
    weather: str = ''
    pace: Optional[RacePace] = None
    entries: List[RaceEntry] = field(default_factory=list)
    meta: Dict = field(default_factory=lambda: {
        'data_version': '4.0',
        'source': 'jravan',
        'created_at': '',
        'has_keibabook_ext': False,
    })

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict) -> 'RaceMaster':
        entries = [RaceEntry(**e) for e in data.get('entries', [])]
        pace_data = data.get('pace')
        pace = RacePace(**pace_data) if pace_data else None
        return cls(
            race_id=data['race_id'],
            date=data['date'],
            venue_code=data['venue_code'],
            venue_name=data['venue_name'],
            kai=data['kai'],
            nichi=data['nichi'],
            race_number=data['race_number'],
            distance=data.get('distance', 0),
            track_type=data.get('track_type', ''),
            track_condition=data.get('track_condition', ''),
            num_runners=data.get('num_runners', 0),
            race_name=data.get('race_name', ''),
            grade=data.get('grade', ''),
            weather=data.get('weather', ''),
            pace=pace,
            entries=entries,
            meta=data.get('meta', {}),
        )

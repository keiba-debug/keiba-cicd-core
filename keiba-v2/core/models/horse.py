#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
馬マスタデータモデル
"""

from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class HorseMaster:
    """馬マスタ（1馬 = 1JSON）"""
    ketto_num: str
    name: str
    name_kana: str = ''
    name_eng: str = ''
    birth_date: str = ''
    sex_cd: str = ''
    sex_name: str = ''
    tozai_cd: str = ''
    tozai_name: str = ''
    trainer_code: str = ''
    trainer_name: str = ''
    owner_name: str = ''
    breeder_name: str = ''
    is_active: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)

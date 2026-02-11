#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN UM_DATA（馬マスタ）パーサー

UM*.DAT: 1609バイト固定長レコード（Shift-JIS）

既存 parse_jv_horse_data.py からの移植版。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..config import jv_um_data_path
from ..constants import UM_RECORD_LEN, SEX_CODES, TOZAI_CODES


def _decode(data: bytes, start: int, length: int) -> str:
    """Shift-JISデコード"""
    try:
        decoded = data[start:start + length].decode('shift_jis', errors='replace').strip()
        if decoded.count('\ufffd') > len(decoded) * 0.5:
            decoded = data[start:start + length].decode('shift_jis', errors='ignore').strip()
        decoded = decoded.replace('\ufffd', '')
    except UnicodeDecodeError:
        decoded = data[start:start + length].decode('shift_jis', errors='ignore').strip()
    return decoded.replace('\u3000', '').replace('@', '')


def _parse_trainer_code(record: bytes) -> str:
    """調教師コード（5桁数値）を抽出"""
    chars = []
    for b in record[850:855]:
        if 0x30 <= b <= 0x39:
            chars.append(chr(b))
    code = ''.join(chars).strip()
    return code.zfill(5) if len(code) < 5 else code[:5]


@dataclass
class HorseRecord:
    """馬マスタレコード"""
    ketto_num: str
    name: str
    name_kana: str
    name_eng: str
    birth_date: str
    sex_cd: str
    sex_name: str
    tozai_cd: str
    tozai_name: str
    trainer_code: str
    trainer_name: str
    del_kubun: str
    reg_date: str
    del_date: str
    owner_name: str
    breeder_name: str

    @property
    def is_active(self) -> bool:
        return self.del_kubun == '0'

    def to_dict(self) -> Dict:
        return {
            'ketto_num': self.ketto_num,
            'name': self.name,
            'name_kana': self.name_kana,
            'name_eng': self.name_eng,
            'birth_date': self.birth_date,
            'sex_cd': self.sex_cd,
            'sex_name': self.sex_name,
            'tozai_cd': self.tozai_cd,
            'tozai_name': self.tozai_name,
            'trainer_code': self.trainer_code,
            'trainer_name': self.trainer_name,
            'is_active': self.is_active,
            'owner_name': self.owner_name,
            'breeder_name': self.breeder_name,
        }


def parse_record(data: bytes, offset: int = 0) -> Optional[HorseRecord]:
    """
    UM_DATA 1609バイトレコードをパース

    バイトオフセット:
      0-1:     RecordType ("UM")
      11-20:   KettoNum (10)
      21:      DelKubun (1)
      22-29:   RegDate (8)
      30-37:   DelDate (8)
      38-45:   BirthDate (8)
      46-81:   BameiName (36, Shift-JIS)
      82-117:  BameiKana (36, Shift-JIS)
      118-177: BameiEng (60, Shift-JIS)
      200:     SexCD (1)
      849:     TozaiCD (1)
      850-854: TrainerCode (5)
      855-862: TrainerName (8, Shift-JIS)
    """
    record = data[offset:offset + UM_RECORD_LEN]
    if len(record) < UM_RECORD_LEN:
        return None

    if _decode(record, 0, 2) != 'UM':
        return None

    ketto_num = _decode(record, 11, 10)
    if not ketto_num:
        return None

    sex_cd = _decode(record, 200, 1)
    trainer_code = _parse_trainer_code(record)

    # tozai_cd: offset 849が"0"の場合、trainer_codeから推定
    tozai_cd = _decode(record, 849, 1)
    if tozai_cd not in ('1', '2'):
        # trainer_code先頭が00-09=美浦系、10-19=栗東系（JRA-VAN仕様推定）
        if trainer_code and len(trainer_code) >= 2:
            prefix = int(trainer_code[:2]) if trainer_code[:2].isdigit() else -1
            if prefix >= 10:
                tozai_cd = '2'  # 栗東
            elif prefix >= 0:
                tozai_cd = '1'  # 美浦

    owner_name = ''
    breeder_name = ''
    try:
        owner_name = _decode(record, 970, 44)
        breeder_name = _decode(record, 920, 40)
    except Exception:
        pass

    return HorseRecord(
        ketto_num=ketto_num,
        name=_decode(record, 46, 36),
        name_kana=_decode(record, 82, 36),
        name_eng=_decode(record, 118, 60),
        birth_date=_decode(record, 38, 8),
        sex_cd=sex_cd,
        sex_name=SEX_CODES.get(sex_cd, f'?({sex_cd})'),
        tozai_cd=tozai_cd,
        tozai_name=TOZAI_CODES.get(tozai_cd, f'?({tozai_cd})'),
        trainer_code=trainer_code,
        trainer_name=_decode(record, 855, 8),
        del_kubun=_decode(record, 21, 1),
        reg_date=_decode(record, 22, 8),
        del_date=_decode(record, 30, 8),
        owner_name=owner_name,
        breeder_name=breeder_name,
    )


# === スキャン関数 ===

def get_um_files(recent_n: int = 20) -> List[Path]:
    """UM_DATAファイル一覧（新しい順）"""
    root = jv_um_data_path()
    if not root.exists():
        return []
    files = []
    for year_dir in sorted(root.iterdir(), reverse=True):
        if year_dir.is_dir() and year_dir.name.isdigit():
            for um_file in sorted(year_dir.glob('UM*.DAT'), reverse=True):
                files.append(um_file)
    return files[:recent_n] if recent_n > 0 else files


def scan(recent_n: int = 20) -> List[HorseRecord]:
    """UM_DATAをスキャンして馬レコードを返す"""
    records = []
    seen = set()
    for um_file in get_um_files(recent_n):
        try:
            data = um_file.read_bytes()
        except Exception:
            continue

        num = len(data) // UM_RECORD_LEN
        for i in range(num):
            offset = i * UM_RECORD_LEN
            rec = parse_record(data, offset)
            if rec and rec.ketto_num not in seen:
                records.append(rec)
                seen.add(rec.ketto_num)

    return records


def build_name_index(recent_n: int = 20) -> Dict[str, str]:
    """馬名→ketto_numインデックスを構築"""
    index = {}
    for um_file in get_um_files(recent_n):
        try:
            data = um_file.read_bytes()
        except Exception:
            continue

        num = len(data) // UM_RECORD_LEN
        for i in range(num):
            offset = i * UM_RECORD_LEN
            ketto = _decode(data, offset + 11, 10)
            name = _decode(data, offset + 46, 36).strip()
            if name and name not in index:
                index[name] = ketto

    return index


def find_by_id(horse_id: str) -> Optional[HorseRecord]:
    """馬IDで検索"""
    horse_id = horse_id.zfill(10)
    for um_file in get_um_files(0):  # 全ファイル検索
        try:
            data = um_file.read_bytes()
        except Exception:
            continue

        num = len(data) // UM_RECORD_LEN
        for i in range(num):
            offset = i * UM_RECORD_LEN
            ketto = _decode(data, offset + 11, 10)
            if ketto == horse_id:
                return parse_record(data, offset)

    return None

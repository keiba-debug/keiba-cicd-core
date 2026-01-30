#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN JV-Data UM（馬データ）解析スクリプト

UM_DATAから馬情報を読み取り、高速検索を可能にします。

Usage:
    python parse_jv_horse_data.py --horse-id 2024100018
    python parse_jv_horse_data.py --search "サトノダイヤモンド"
    python parse_jv_horse_data.py --build-index
"""

import argparse
import json
import os
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def _load_dotenv_if_available() -> None:
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


def _get_env_path(key: str, default: str) -> Path:
    value = os.getenv(key)
    if value:
        return Path(value)
    return Path(default)


_load_dotenv_if_available()

# JRA-VAN データパス
JV_DATA_ROOT = _get_env_path("JV_DATA_ROOT_DIR", "Y:/")
UM_DATA_PATH = JV_DATA_ROOT / "UM_DATA"

# レコード長
UM_RECORD_LEN = 1609

# 性別コード
SEX_CODES = {
    "1": "牡",
    "2": "牝",
    "3": "セン",
}

# 東西所属
TOZAI_CODES = {
    "1": "美浦",
    "2": "栗東",
}


@dataclass
class HorseRecord:
    """馬レコード"""
    ketto_num: str          # 血統登録番号（馬ID）
    del_kubun: str          # 抹消区分
    reg_date: str           # 登録年月日
    del_date: str           # 抹消年月日
    birth_date: str         # 生年月日
    name: str               # 馬名
    name_kana: str          # 馬名カナ
    name_eng: str           # 馬名英字
    sex_cd: str             # 性別コード
    sex_name: str           # 性別名
    tozai_cd: str           # 東西所属コード
    tozai_name: str         # 東西所属名
    trainer_code: str       # 調教師コード
    trainer_name: str       # 調教師名略称
    owner_code: str         # 馬主コード
    owner_name: str         # 馬主名
    breeder_code: str       # 生産者コード
    breeder_name: str       # 生産者名
    
    def to_dict(self) -> dict:
        return {
            "horse_id": self.ketto_num,
            "name": self.name,
            "name_kana": self.name_kana,
            "name_eng": self.name_eng,
            "birth_date": self.birth_date,
            "sex": self.sex_name,
            "tozai": self.tozai_name,
            "trainer_code": self.trainer_code,
            "trainer_name": self.trainer_name,
            "owner_name": self.owner_name,
            "breeder_name": self.breeder_name,
            "is_active": self.del_kubun == "0",
        }
    
    def get_age(self, ref_date: datetime = None) -> int:
        """年齢を計算"""
        if not self.birth_date or len(self.birth_date) != 8:
            return 0
        ref = ref_date or datetime.now()
        try:
            birth = datetime.strptime(self.birth_date, "%Y%m%d")
            age = ref.year - birth.year
            # 競馬では1月1日で加齢
            return age
        except ValueError:
            return 0


def decode_sjis(data: bytes) -> str:
    """Shift-JISでデコードしてトリム"""
    # errors='replace'だと文字化けが発生するため、'ignore'を使用
    # ただし、完全に無効なバイト列の場合は空文字になる可能性があるため、
    # まず'replace'で試し、置換文字が多すぎる場合は'ignore'を試す
    try:
        decoded = data.decode('shift_jis', errors='replace').strip()
        # 置換文字（\ufffd）が全体の50%以上を占める場合は、'ignore'で再試行
        if decoded.count('\ufffd') > len(decoded) * 0.5:
            decoded = data.decode('shift_jis', errors='ignore').strip()
        # 置換文字を除去
        decoded = decoded.replace('\ufffd', '')
    except UnicodeDecodeError:
        # デコードに失敗した場合は'ignore'で再試行
        decoded = data.decode('shift_jis', errors='ignore').strip()
    
    # 全角空白と@を除去
    return decoded.replace('\u3000', '').replace('@', '')


def parse_um_record(data: bytes, offset: int = 0) -> Optional[HorseRecord]:
    """
    UMレコードをパース
    
    Args:
        data: ファイル全体のバイトデータ
        offset: レコードの開始位置
    
    Returns:
        HorseRecord or None
    """
    try:
        record = data[offset:offset + UM_RECORD_LEN]
        
        if len(record) < UM_RECORD_LEN:
            return None
        
        # レコードタイプチェック（先頭2バイトが"UM"であること）
        record_type = decode_sjis(record[0:2])
        if record_type != "UM":
            return None
        
        # フィールド抽出（1-basedオフセットを0-basedに変換）
        ketto_num = decode_sjis(record[11:21])
        del_kubun = decode_sjis(record[21:22])
        reg_date = decode_sjis(record[22:30])
        del_date = decode_sjis(record[30:38])
        birth_date = decode_sjis(record[38:46])
        name = decode_sjis(record[46:82])
        name_kana = decode_sjis(record[82:118])
        name_eng = decode_sjis(record[118:178])
        sex_cd = decode_sjis(record[200:201])
        tozai_cd = decode_sjis(record[849:850])
        # 調教師コードは5桁数値（ゼロ埋め）なので、バイト列から直接数値文字列に変換
        # 例: b'01234' → "01234"
        trainer_code_bytes = record[850:855]
        # 数値文字列として扱う（ASCII範囲の文字のみ、空白やNULLは無視）
        trainer_code_chars = []
        for b in trainer_code_bytes:
            if 0x30 <= b <= 0x39:  # '0'-'9'
                trainer_code_chars.append(chr(b))
            elif b == 0x20 or b == 0x00:  # 空白やNULLは無視
                continue
            # その他の文字は無視（数値以外は含めない）
        trainer_code = ''.join(trainer_code_chars).strip()
        # 5桁未満の場合はゼロ埋め
        if len(trainer_code) < 5:
            trainer_code = trainer_code.zfill(5)
        # 5桁を超える場合は最初の5桁のみ
        if len(trainer_code) > 5:
            trainer_code = trainer_code[:5]
        # 調教師名はShift-JISでデコード（855-862、8バイト）
        # 注意: 8バイトは全角4文字分。実際の名前が短い場合は空白で埋められている
        trainer_name_bytes = record[855:863]
        
        # デバッグ: 最初の数件でバイト列を確認
        # 調教師コードが01155の場合（最初の1件）のみデバッグ出力
        if trainer_code == "01155" and len(trainer_code) == 5:
            print(f"  [デバッグ] 調教師名バイト列: {trainer_name_bytes.hex()} (len={len(trainer_name_bytes)})")
            print(f"  [デバッグ] 各バイト: {[hex(b) for b in trainer_name_bytes]}")
            # 異なるオフセットで試す
            for offset in [854, 855, 856]:
                test_bytes = record[offset:offset+8]
                test_name = decode_sjis(test_bytes)
                if test_name and len(test_name) >= 2:
                    print(f"  [デバッグ] offset {offset}: {test_name}")
        
        trainer_name = decode_sjis(trainer_name_bytes)
        
        # より後方のフィールド（オフセット調整が必要な場合あり）
        # 馬主・生産者情報は血統情報の後にあるため、正確なオフセットは仕様書確認が必要
        owner_code = ""
        owner_name = ""
        breeder_code = ""
        breeder_name = ""
        
        try:
            # 推定オフセット（要調整）
            owner_name = decode_sjis(record[970:1014])
            breeder_name = decode_sjis(record[920:960])
        except Exception:
            pass
        
        return HorseRecord(
            ketto_num=ketto_num,
            del_kubun=del_kubun,
            reg_date=reg_date,
            del_date=del_date,
            birth_date=birth_date,
            name=name,
            name_kana=name_kana,
            name_eng=name_eng,
            sex_cd=sex_cd,
            sex_name=SEX_CODES.get(sex_cd, f"不明({sex_cd})"),
            tozai_cd=tozai_cd,
            tozai_name=TOZAI_CODES.get(tozai_cd, f"不明({tozai_cd})"),
            trainer_code=trainer_code,
            trainer_name=trainer_name,
            owner_code=owner_code,
            owner_name=owner_name,
            breeder_code=breeder_code,
            breeder_name=breeder_name,
        )
    except Exception as e:
        print(f"パースエラー at offset {offset}: {e}")
        return None


def get_um_files() -> List[Path]:
    """利用可能なUMファイル一覧を取得（新しい順）"""
    files = []
    
    if not UM_DATA_PATH.exists():
        return files
    
    for year_dir in sorted(UM_DATA_PATH.iterdir(), reverse=True):
        if year_dir.is_dir() and year_dir.name.isdigit():
            for um_file in sorted(year_dir.glob("UM*.DAT"), reverse=True):
                files.append(um_file)
    
    return files


def find_horse_by_id(horse_id: str) -> Optional[HorseRecord]:
    """
    馬IDで検索
    
    Args:
        horse_id: 血統登録番号（10桁）
    
    Returns:
        HorseRecord or None
    """
    # 10桁に正規化
    horse_id = horse_id.zfill(10)
    
    for um_file in get_um_files():
        try:
            with open(um_file, 'rb') as f:
                data = f.read()
            
            num_records = len(data) // UM_RECORD_LEN
            
            for i in range(num_records):
                offset = i * UM_RECORD_LEN
                # クイックチェック: 馬IDの位置を直接確認
                ketto = decode_sjis(data[offset + 11:offset + 21])
                if ketto == horse_id:
                    return parse_um_record(data, offset)
        except Exception as e:
            print(f"ファイル読み込みエラー {um_file}: {e}")
    
    return None


def search_horses_by_name(query: str, limit: int = 20) -> List[HorseRecord]:
    """
    馬名で検索
    
    Args:
        query: 検索文字列
        limit: 最大件数
    
    Returns:
        マッチしたHorseRecordのリスト
    """
    results = []
    query_lower = query.lower()
    
    for um_file in get_um_files():
        try:
            with open(um_file, 'rb') as f:
                data = f.read()
            
            num_records = len(data) // UM_RECORD_LEN
            
            for i in range(num_records):
                offset = i * UM_RECORD_LEN
                # 馬名部分を直接確認
                name = decode_sjis(data[offset + 46:offset + 82])
                
                if query_lower in name.lower():
                    record = parse_um_record(data, offset)
                    if record:
                        results.append(record)
                        if len(results) >= limit:
                            return results
        except Exception as e:
            print(f"ファイル読み込みエラー {um_file}: {e}")
    
    return results


def find_horse_by_name(name: str) -> Optional[str]:
    """
    馬名で完全一致検索し、10桁馬IDを返す
    
    Args:
        name: 馬名（完全一致）
    
    Returns:
        10桁の血統登録番号（見つからない場合はNone）
    """
    name_stripped = name.strip()
    
    for um_file in get_um_files():
        try:
            with open(um_file, 'rb') as f:
                data = f.read()
            
            num_records = len(data) // UM_RECORD_LEN
            
            for i in range(num_records):
                offset = i * UM_RECORD_LEN
                # 馬名部分を直接確認
                horse_name = decode_sjis(data[offset + 46:offset + 82]).strip()
                
                if horse_name == name_stripped:
                    ketto = decode_sjis(data[offset + 11:offset + 21])
                    return ketto
        except Exception:
            pass
    
    return None


def build_horse_name_index() -> Dict[str, str]:
    """
    馬名→10桁IDのインデックスを構築
    
    Returns:
        {馬名: 10桁ID} の辞書
    """
    index = {}
    
    for um_file in get_um_files():
        try:
            with open(um_file, 'rb') as f:
                data = f.read()
            
            num_records = len(data) // UM_RECORD_LEN
            
            for i in range(num_records):
                offset = i * UM_RECORD_LEN
                ketto = decode_sjis(data[offset + 11:offset + 21])
                name = decode_sjis(data[offset + 46:offset + 82]).strip()
                
                if name and name not in index:
                    index[name] = ketto
        except Exception:
            pass
    
    return index


def build_horse_index(output_path: Path = None) -> dict:
    """
    馬インデックスを構築
    
    Returns:
        {horse_id: {name, file_path, offset}} の辞書
    """
    index = {}
    
    for um_file in get_um_files():
        print(f"インデックス構築中: {um_file.name}")
        try:
            with open(um_file, 'rb') as f:
                data = f.read()
            
            num_records = len(data) // UM_RECORD_LEN
            
            for i in range(num_records):
                offset = i * UM_RECORD_LEN
                ketto = decode_sjis(data[offset + 11:offset + 21])
                name = decode_sjis(data[offset + 46:offset + 82])
                
                if ketto and ketto not in index:
                    index[ketto] = {
                        "name": name,
                        "file": str(um_file),
                        "offset": offset,
                    }
        except Exception as e:
            print(f"ファイル読み込みエラー {um_file}: {e}")
    
    print(f"インデックス完了: {len(index)} 頭")
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"出力: {output_path}")
    
    return index


def main():
    parser = argparse.ArgumentParser(
        description="JRA-VAN JV-Data UM（馬データ）解析ツール"
    )
    parser.add_argument(
        "--horse-id",
        type=str,
        help="馬ID（血統登録番号）で検索"
    )
    parser.add_argument(
        "--search",
        type=str,
        help="馬名で検索"
    )
    parser.add_argument(
        "--build-index",
        action="store_true",
        help="馬インデックスを構築"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="出力ファイルパス (JSON形式)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="検索結果の最大件数"
    )
    
    args = parser.parse_args()
    
    if args.build_index:
        output_path = Path(args.output) if args.output else None
        build_horse_index(output_path)
        return
    
    if args.horse_id:
        result = find_horse_by_id(args.horse_id)
        if result:
            result_json = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(result_json)
                print(f"Output: {args.output}")
            else:
                # コンソール出力はASCIIエスケープ
                print(json.dumps(result.to_dict(), indent=2))
        else:
            print("Not found")
        return
    
    if args.search:
        print(f"馬名検索: {args.search}")
        results = search_horses_by_name(args.search, args.limit)
        print(f"結果: {len(results)} 件")
        for r in results:
            age = r.get_age()
            print(f"  {r.ketto_num}: {r.name} ({r.sex_name}{age}歳) - {r.trainer_name}")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)
            print(f"出力: {args.output}")
        return
    
    # デフォルト: ファイル一覧表示
    print("利用可能なUMファイル:")
    for um_file in get_um_files()[:10]:
        file_size = um_file.stat().st_size
        num_records = file_size // UM_RECORD_LEN
        print(f"  {um_file.name}: {num_records} レコード")


if __name__ == "__main__":
    main()

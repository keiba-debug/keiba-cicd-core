# -*- coding: utf-8 -*-
"""
TARGET馬印ファイル解析スクリプト

ファイル形式:
- ファイル名: UMyykpp.DAT (yy=西暦下2桁, k=回次, pp=場所名漢字)
- 1レコード = 44バイト（レース印6バイト + 馬印36バイト + 改行2バイト）
- 全体 = 96レコード（8日 × 12レース）
"""

import os
import sys
from pathlib import Path

# 印の定義（Shift-JIS バイト列 → 印記号）
MARK_BYTES_TO_SYMBOL = {
    b'\x81\x9d': '◎',  # 本命
    b'\x81\x9b': '○',  # 対抗
    b'\x81\xa3': '▲',  # 単穴
    b'\x81\xa2': '△',  # 連下
    b'\x87\x56': '★',  # 注意
    b'\x8c\x8a': '穴',  # 穴馬
    b'\x20\x20': '',    # 無印
}

# 逆引き（印記号 → Shift-JIS バイト列）
SYMBOL_TO_MARK_BYTES = {v: k for k, v in MARK_BYTES_TO_SYMBOL.items() if v}
SYMBOL_TO_MARK_BYTES[''] = b'\x20\x20'

# 場所名マッピング（JRA-VAN場所コード → 漢字）
VENUE_CODE_TO_KANJI = {
    '01': '札',
    '02': '函',
    '03': '福',
    '04': '新',
    '05': '東',
    '06': '中',
    '07': '名',
    '08': '京',
    '09': '阪',
    '10': '小',
}

KANJI_TO_VENUE_CODE = {v: k for k, v in VENUE_CODE_TO_KANJI.items()}


def get_mark_file_path(year: int, kai: int, venue_kanji: str, my_data_dir: str = None) -> Path:
    """
    馬印ファイルのパスを取得
    
    Args:
        year: 西暦年（例: 2026）
        kai: 回次（1-6程度）
        venue_kanji: 場所名漢字（東, 京, 阪 等）
        my_data_dir: MY_DATAディレクトリ（デフォルト: JV_DATA_ROOT_DIR/MY_DATA）
    
    Returns:
        ファイルパス
    """
    if my_data_dir is None:
        jv_root = os.environ.get('JV_DATA_ROOT_DIR', 'C:\\TFJV')
        my_data_dir = Path(jv_root) / 'MY_DATA'
    else:
        my_data_dir = Path(my_data_dir)
    
    yy = str(year)[-2:]  # 西暦下2桁
    filename = f'UM{yy}{kai}{venue_kanji}.DAT'
    return my_data_dir / filename


def get_record_index(day: int, race_number: int) -> int:
    """
    レコードインデックスを計算
    
    Args:
        day: 日次（1-8）
        race_number: レース番号（1-12）
    
    Returns:
        レコードインデックス（0-95）
    """
    return (day - 1) * 12 + (race_number - 1)


def parse_race_marks(file_path: Path, day: int, race_number: int) -> dict:
    """
    指定レースの馬印を取得
    
    Args:
        file_path: 馬印ファイルパス
        day: 日次（1-8）
        race_number: レース番号（1-12）
    
    Returns:
        {
            'race_mark': レース印文字列,
            'color_code': 色コード,
            'horse_marks': {馬番: 印記号, ...}
        }
    """
    if not file_path.exists():
        return None
    
    with open(file_path, 'rb') as f:
        content = f.read()
    
    record_index = get_record_index(day, race_number)
    record_start = record_index * 44
    
    if record_start + 44 > len(content):
        return None
    
    record = content[record_start:record_start + 44]
    
    # レース印（バイト0-5）
    # +0: '0'（未使用）
    # +1: 色コード（'0'-'9'）
    # +2-5: レース印
    color_code = chr(record[1]) if record[1] != 0x20 else ''
    race_mark_bytes = record[2:6]
    try:
        race_mark = race_mark_bytes.decode('shift-jis').strip()
    except:
        race_mark = ''
    
    # 馬印（バイト6-41、18頭分）
    horse_marks = {}
    for uma in range(1, 19):
        offset = 6 + (uma - 1) * 2
        mark_bytes = record[offset:offset + 2]
        mark = MARK_BYTES_TO_SYMBOL.get(bytes(mark_bytes), '')
        if mark:
            horse_marks[uma] = mark
    
    return {
        'race_mark': race_mark,
        'color_code': color_code,
        'horse_marks': horse_marks,
    }


def write_horse_mark(file_path: Path, day: int, race_number: int, 
                     horse_number: int, mark: str) -> bool:
    """
    馬印を書き込み
    
    Args:
        file_path: 馬印ファイルパス
        day: 日次（1-8）
        race_number: レース番号（1-12）
        horse_number: 馬番（1-18）
        mark: 印記号（◎, ○, ▲, △, ★, 穴, 空文字=無印）
    
    Returns:
        成功/失敗
    """
    if mark not in SYMBOL_TO_MARK_BYTES:
        print(f"Unknown mark: {mark}")
        return False
    
    mark_bytes = SYMBOL_TO_MARK_BYTES[mark]
    
    record_index = get_record_index(day, race_number)
    record_start = record_index * 44
    offset = record_start + 6 + (horse_number - 1) * 2
    
    # ファイルが存在しない場合は新規作成（96レコード × 44バイト）
    if not file_path.exists():
        # 全レコードをスペースで初期化
        content = bytearray(96 * 44)
        for i in range(96):
            base = i * 44
            content[base:base + 42] = b' ' * 42
            content[base + 42:base + 44] = b'\r\n'
        file_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        with open(file_path, 'rb') as f:
            content = bytearray(f.read())
    
    # 書き込み
    content[offset:offset + 2] = mark_bytes
    
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return True


def main():
    """テスト実行"""
    # 環境変数設定
    jv_root = os.environ.get('JV_DATA_ROOT_DIR', 'C:\\TFJV')
    my_data_dir = Path(jv_root) / 'MY_DATA'
    
    print("=== TARGET馬印ファイル解析 ===\n")
    
    # 2026年 1回東京（UM261東.DAT）11R を読み込み
    file_path = get_mark_file_path(2026, 1, '東', my_data_dir)
    print(f"ファイル: {file_path}")
    print(f"存在: {file_path.exists()}")
    
    if file_path.exists():
        # 1日目11R
        result = parse_race_marks(file_path, 1, 11)
        if result:
            print(f"\n東京1日目11R（根岸S）:")
            print(f"  レース印: {result['race_mark']}")
            print(f"  色コード: {result['color_code']}")
            print(f"  馬印:")
            for uma, mark in sorted(result['horse_marks'].items()):
                print(f"    {uma}番: {mark}")
    
    # 2026年 2回京都（UM262京.DAT）11R を読み込み
    file_path = get_mark_file_path(2026, 2, '京', my_data_dir)
    print(f"\nファイル: {file_path}")
    print(f"存在: {file_path.exists()}")
    
    if file_path.exists():
        # 1日目11R
        result = parse_race_marks(file_path, 1, 11)
        if result:
            print(f"\n京都1日目11R（シルクロードS）:")
            print(f"  レース印: {result['race_mark']}")
            print(f"  色コード: {result['color_code']}")
            print(f"  馬印:")
            for uma, mark in sorted(result['horse_marks'].items()):
                print(f"    {uma}番: {mark}")


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""東京・京都の印データを確認"""
import glob
import os

# 印のバイトパターン
MARKS = {
    (0x81, 0x9d): '◎',
    (0x81, 0x9b): '○',
    (0x81, 0xa3): '▲',
    (0x81, 0xa2): '△',
    (0x87, 0x56): '★',
    (0x8c, 0x8a): '穴',
}

def check_file(filepath):
    """ファイル内の全レコードをチェック"""
    print(f"\n=== {os.path.basename(filepath)} ===")
    
    with open(filepath, 'rb') as f:
        content = f.read()
    
    num_records = len(content) // 44
    print(f"Size: {len(content)} bytes, Records: {num_records}")
    
    for rec in range(num_records):
        record = content[rec * 44 : rec * 44 + 44]
        horse_marks = {}
        
        for uma in range(1, 19):
            offset = 6 + (uma - 1) * 2
            b1 = record[offset]
            b2 = record[offset + 1]
            key = (b1, b2)
            
            if key in MARKS:
                horse_marks[uma] = MARKS[key]
        
        if horse_marks:
            day = rec // 12 + 1
            race = rec % 12 + 1
            marks_str = ", ".join([f"{uma}番:{m}" for uma, m in sorted(horse_marks.items())])
            print(f"  {day}日目 {race}R: {marks_str}")


def main():
    jv_root = os.environ.get('JV_DATA_ROOT_DIR', 'C:/TFJV')
    my_data = os.path.join(jv_root, 'MY_DATA')
    
    # 2026年のファイルを確認
    patterns = [
        f"{my_data}/UM261*.DAT",
        f"{my_data}/UM262*.DAT",
    ]
    
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            check_file(filepath)


if __name__ == '__main__':
    main()

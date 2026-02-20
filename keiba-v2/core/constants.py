#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KeibaCICD v4 定数定義

JRA-VANの各種コード体系を定義。
"""

# 競馬場コード（JRA-VAN JyoCD）
VENUE_CODES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
VENUE_NAMES_TO_CODES = {v: k for k, v in VENUE_CODES.items()}

# 性別コード
SEX_CODES = {"1": "牡", "2": "牝", "3": "セン"}

# 東西所属コード
TOZAI_CODES = {"1": "美浦", "2": "栗東"}

# 馬場状態コード
BABA_CODES = {"1": "良", "2": "稍重", "3": "重", "4": "不良"}

# トラックコード（先頭1桁）
TRACK_TYPES = {"1": "turf", "2": "dirt"}

# グレードコード（SR_DATA GradeCD @614）
GRADE_CODES = {
    "A": "G1", "B": "G2", "C": "G3",
    "L": "Listed", "E": "OP",
}

# SE_DATA レコード長
SE_RECORD_LEN = 555

# SR_DATA (RA record) レコード長
SR_RECORD_LEN = 1272

# UM_DATA レコード長
UM_RECORD_LEN = 1609

# グレード序列（数値が小さいほど上位クラス）
GRADE_LEVEL = {
    "G1": 1, "G2": 2, "G3": 3, "Listed": 4,
    "OP": 5, "3勝クラス": 6, "2勝クラス": 7, "1勝クラス": 8,
    "未勝利": 9, "新馬": 10,
}

# 栗東馬割合による競馬場ランク（降格ローテ理論）
# A=最高レベル(栗東馬多い) → E=最低レベル(美浦がホーム)
VENUE_RANK = {
    "阪神": "A", "京都": "A",
    "小倉": "B", "中京": "B",
    "札幌": "C", "函館": "C",
    "新潟": "D", "福島": "D",
    "東京": "E", "中山": "E",
}
VENUE_RANK_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}

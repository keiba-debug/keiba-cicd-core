# -*- coding: utf-8 -*-
"""
JRA-VANデータパーサー

各データタイプのパーサーを提供します。
通常は data_access モジュールを使用することを推奨します。

使用例:
    from pathlib import Path
    from common.jravan.parsers import parse_ck_file, find_horse_by_id

    # CK_DATAファイルをパース（パスは JV_DATA_ROOT_DIR から構築）
    import os
    jv_root = os.environ.get("JV_DATA_ROOT_DIR", "")
    ck_path = Path(jv_root) / "CK_DATA" / "2026" / "202601" / "HC020260124.DAT"
    records = parse_ck_file(ck_path)

    # 馬情報取得
    horse = find_horse_by_id("2019103487")
"""

from .ck_parser import parse_ck_file
from .um_parser import find_horse_by_id, search_horses_by_name, find_horse_by_name
from .de_parser import parse_dr_file, get_race_times_for_date

__all__ = [
    # CK_DATA
    "parse_ck_file",
    # UM_DATA
    "find_horse_by_id",
    "search_horses_by_name",
    "find_horse_by_name",
    # DE_DATA
    "parse_dr_file",
    "get_race_times_for_date",
]

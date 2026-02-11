# -*- coding: utf-8 -*-
"""
JRA-VAN データ統合ライブラリ

競馬ブックとJRA-VANのID変換、データ取得を効率化する統一インターフェース

使用例:
    from common.jravan import get_horse_id_by_name, analyze_horse_training

    # 馬名からJRA-VAN IDに変換
    horse_id = get_horse_id_by_name("ドウデュース")

    # 調教データ取得
    training = analyze_horse_training(horse_id, "20260125", days_back=14)
"""

# ID変換
from .id_converter import (
    get_horse_id_by_name,
    get_horse_name_by_id,
    get_track_code,
    get_track_name,
)

# 調教師ID変換
from .trainer_mapper import (
    get_trainer_jvn_code,
    get_trainer_info,
    TrainerIdMapper,
)

# レースID操作
from .race_id import (
    build_race_id,
    parse_race_id,
)

# データ取得
from .data_access import (
    get_horse_info,
    get_training_data,
    analyze_horse_training,
)

# パーサー（直接使用は非推奨、data_accessを使うこと）
from .parsers import (
    parse_ck_file,
    parse_um_file,
    parse_de_file,
)


__all__ = [
    # ID変換
    "get_horse_id_by_name",
    "get_horse_name_by_id",
    "get_track_code",
    "get_track_name",
    # 調教師ID変換
    "get_trainer_jvn_code",
    "get_trainer_info",
    "TrainerIdMapper",
    # レースID
    "build_race_id",
    "parse_race_id",
    # データ取得
    "get_horse_info",
    "get_training_data",
    "analyze_horse_training",
    # パーサー
    "parse_ck_file",
    "parse_um_file",
    "parse_de_file",
]

# -*- coding: utf-8 -*-
"""
JRA-VANデータアクセスレイヤー

高レベルなデータ取得APIを提供します。

使用例:
    from common.jravan.data_access import get_horse_info, get_training_data

    # 馬情報取得
    info = get_horse_info("ドウデュース")

    # 調教データ取得
    training = get_training_data("2019103487", "20260125", days_back=14)
"""

import sys
from pathlib import Path
from typing import Dict, Optional

# parse_ck_data.pyの関数をインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from parse_ck_data import analyze_horse_training as _analyze_horse_training

from .id_converter import get_horse_id_by_name
from .parsers.um_parser import find_horse_by_id


def get_horse_info(identifier: str) -> Optional[Dict]:
    """
    馬の基本情報を取得

    Args:
        identifier: 馬名 または JRA-VAN 10桁ID

    Returns:
        馬情報の辞書（見つからない場合はNone）

    使用例:
        >>> info = get_horse_info("ドウデュース")
        >>> print(info["name"], info["sex"], info["age"])
        ドウデュース 牡 4歳

        >>> info = get_horse_info("2019103487")
        >>> print(info["trainer_name"])
        友道康夫
    """
    # 10桁の数値ならIDとみなす
    if len(identifier) == 10 and identifier.isdigit():
        horse_id = identifier
    else:
        # 馬名とみなす
        horse_id = get_horse_id_by_name(identifier)

    if not horse_id:
        return None

    horse = find_horse_by_id(horse_id)
    if not horse:
        return None

    return horse.to_dict()


def get_training_data(
    horse_id: str,
    race_date: str,
    days_back: int = 14
) -> Dict:
    """
    馬の調教データを取得

    Args:
        horse_id: JRA-VAN 10桁ID
        race_date: レース日（YYYYMMDD形式）
        days_back: 遡る日数（デフォルト14日）

    Returns:
        調教データの辞書

    使用例:
        >>> training = get_training_data("2019103487", "20260125")
        >>> if training["final"]:
        ...     print(f"最終追切: {training['final']['date']}")
    """
    return _analyze_horse_training(horse_id, race_date, days_back)


def analyze_horse_training(
    identifier: str,
    race_date: str,
    days_back: int = 14
) -> Dict:
    """
    馬の調教データを取得（馬名またはIDで指定可能）

    Args:
        identifier: 馬名 または JRA-VAN 10桁ID
        race_date: レース日（YYYYMMDD形式）
        days_back: 遡る日数（デフォルト14日）

    Returns:
        調教データの辞書

    使用例:
        >>> training = analyze_horse_training("ドウデュース", "20260125")
        >>> print(f"調教本数: {training['total_count']}")
    """
    # 10桁の数値ならIDとみなす
    if len(identifier) == 10 and identifier.isdigit():
        horse_id = identifier
    else:
        # 馬名とみなす
        horse_id = get_horse_id_by_name(identifier)

    if not horse_id:
        return {"error": f"Horse not found: {identifier}"}

    return _analyze_horse_training(horse_id, race_date, days_back)


def get_race_info(race_id: str) -> Optional[Dict]:
    """
    レース情報を取得（未実装）

    Args:
        race_id: JRA-VAN 16桁レースID

    Returns:
        レース情報の辞書（見つからない場合はNone）

    使用例:
        >>> info = get_race_info("2026012406010208")
        >>> print(info["race_name"], info["hasso_time"])
    """
    # TODO: DE_DATA/SE_DATAから取得
    raise NotImplementedError("get_race_info is not implemented yet")


def get_race_results(race_id: str) -> Optional[Dict]:
    """
    レース結果を取得（未実装）

    Args:
        race_id: JRA-VAN 16桁レースID

    Returns:
        レース結果の辞書（見つからない場合はNone）

    使用例:
        >>> results = get_race_results("2026012406010208")
        >>> for result in results["entries"]:
        ...     print(f"{result['chakujun']}着 {result['horse_name']}")
    """
    # TODO: SE_DATAから取得
    raise NotImplementedError("get_race_results is not implemented yet")

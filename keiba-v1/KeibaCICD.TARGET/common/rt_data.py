# -*- coding: utf-8 -*-
"""
RT_DATA（速報・オッズ）パーサー

JV_DATA_ROOT_DIR 配下の RT_DATA のオッズデータを解析します。
JV-Data O1レコード（単複枠オッズ）形式に準拠。

使用例:
    from common.rt_data import get_race_odds_from_rt

    odds = get_race_odds_from_rt("2026013105010101")
    # => {"01": {"win_odds": 5.2, "place_min": 2.1, "place_max": 2.8, "ninki": 1}, ...}
"""

from pathlib import Path
from typing import Dict, List, Optional, Any

from .config import get_jv_rt_data_path


def _parse_o1_record(content: str) -> Optional[Dict[str, Any]]:
    """
    O1レコード（単複枠オッズ）をパース
    JVData_Struct.cs JV_O1_ODDS_TANFUKUWAKU 準拠
    """
    # 改行除去して1行に
    raw = content.replace("\r", "").replace("\n", "").strip()
    if len(raw) < 270:
        return None
    if not raw.startswith("O1"):
        return None

    result: Dict[str, Any] = {
        "race_id": raw[11:27] if len(raw) >= 27 else "",
        "horses": {},
    }

    # 単勝オッズ: 44 + 8*i (i=0..27), 各8バイト: Umaban(2) Odds(4) Ninki(2)
    # オッズは10倍表示 (520 -> 52.0)
    for i in range(28):
        start = 43 + 8 * i  # 0-indexed
        end = start + 8
        if end > len(raw):
            break
        block = raw[start:end]
        umaban = block[0:2].strip()
        if not umaban or umaban == "00":
            continue
        try:
            odds_raw = int(block[2:6].strip() or 0)
            ninki_raw = block[6:8].strip()
            win_odds = odds_raw / 10.0 if odds_raw > 0 else None
            ninki = int(ninki_raw) if ninki_raw.isdigit() else None
            result["horses"][umaban] = {
                "win_odds": win_odds,
                "place_min": None,
                "place_max": None,
                "ninki": ninki,
            }
        except (ValueError, IndexError):
            continue

    # 複勝オッズ: 268 + 12*i (i=0..27), 各12バイト: Umaban(2) OddsLow(4) OddsHigh(4) Ninki(2)
    for i in range(28):
        start = 267 + 12 * i
        end = start + 12
        if end > len(raw):
            break
        block = raw[start:end]
        umaban = block[0:2].strip()
        if umaban not in result["horses"]:
            continue
        try:
            low_raw = int(block[2:6].strip() or 0)
            high_raw = int(block[6:10].strip() or 0)
            result["horses"][umaban]["place_min"] = low_raw / 10.0 if low_raw > 0 else None
            result["horses"][umaban]["place_max"] = high_raw / 10.0 if high_raw > 0 else None
        except (ValueError, IndexError):
            pass

    return result


def _find_rt_file_for_race(
    rt_root: Path,
    race_id: str,
) -> Optional[Path]:
    """
    レースIDに対応するRT_DATAファイルを検索
    ファイル名: RT{YYYYMMDD}{JJ}{KK}{NN}{RR}{馬番}.DAT
    """
    if len(race_id) != 16:
        return None
    yyyymmdd = race_id[0:8]
    jj = race_id[8:10]
    kk = race_id[10:12]
    nn = race_id[12:14]
    rr = race_id[14:16]
    year = race_id[0:4]
    mmdd = race_id[4:8]

    # 検索パス: RT_DATA/{年}/{MMDD}/ または RT_DATA/{年}/
    candidates = [
        rt_root / year / mmdd,
        rt_root / year,
    ]
    prefix = f"RT{yyyymmdd}{jj}{kk}{nn}{rr}"

    for base in candidates:
        if not base.exists():
            continue
        # 1番のファイルから読めば全頭のオッズが取れる（O1はレース単位）
        for suffix in ("1", "01"):
            fname = f"{prefix}{suffix}.DAT"
            p = base / fname
            if p.exists():
                return p
        # 該当する任意のファイル
        for p in sorted(base.glob(f"{prefix}*.DAT")):
            return p

    return None


def get_race_odds_from_rt(
    race_id: str,
    rt_root: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    レースIDからRT_DATAのオッズを取得

    Args:
        race_id: 16桁レースID（例: 2026013105010101）
        rt_root: RT_DATAルート（省略時はconfigから取得）

    Returns:
        {
            "race_id": str,
            "source": "RT_DATA",
            "horses": {
                "01": {"win_odds": 5.2, "place_min": 2.1, "place_max": 2.8, "ninki": 1},
                ...
            }
        }
        見つからない場合はNone
    """
    rt_root = rt_root or get_jv_rt_data_path()
    if not rt_root.exists():
        return None

    path = _find_rt_file_for_race(rt_root, race_id)
    if not path:
        return None

    try:
        with open(path, "r", encoding="shift_jis", errors="replace") as f:
            content = f.read()
    except OSError:
        return None

    parsed = _parse_o1_record(content)
    if not parsed or not parsed["horses"]:
        return None

    parsed["source"] = "RT_DATA"
    return parsed


def list_races_with_odds(
    date_yyyymmdd: str,
    rt_root: Optional[Path] = None,
) -> List[str]:
    """
    指定日にオッズがあるレースIDの一覧を取得

    Args:
        date_yyyymmdd: 日付（YYYYMMDD）
        rt_root: RT_DATAルート

    Returns:
        レースIDのリスト
    """
    rt_root = rt_root or get_jv_rt_data_path()
    if len(date_yyyymmdd) != 8:
        return []

    year = date_yyyymmdd[0:4]
    mmdd = date_yyyymmdd[4:8]

    base = rt_root / year / mmdd
    if not base.exists():
        base = rt_root / year
    if not base.exists():
        return []

    seen: set = set()
    for p in base.glob(f"RT{date_yyyymmdd}*.DAT"):
        name = p.stem
        if len(name) >= 24:
            race_id = name[2:18]
            seen.add(race_id)

    return sorted(seen)

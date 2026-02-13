#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mykeibadb オッズ取得モジュール

mykeibadb の各種オッズテーブルから、レース前オッズ・確定オッズ・
時系列オッズを取得する。

テーブル対応:
    odds1_tansho          - 確定単勝オッズ (N_ODDS_TANPUKU)
    odds1_fukusho         - 確定複勝オッズ
    odds1_tansho_jikeiretsu - 時系列単勝オッズ (HAPPYO_TSUKIHI_JIFUN付き)
    odds1_fukusho_jikeiretsu - 時系列複勝オッズ
    odds2_umaren          - 確定馬連オッズ
    odds3_wide            - 確定ワイドオッズ
    umagoto_race_joho     - 馬毎レース情報 (SE) 内の確定オッズ

ODDS値の仕様 (JRA-VAN):
    単勝: 4桁 (例: "0035" = 3.5倍, "9999" = 999.9倍以上)
    馬連: 6桁 (例: "000120" = 12.0倍)
    特殊値: "----" = 取消, "****" = エラー, "0000" = 未設定
"""

from typing import Dict, List, Optional
from core.db import query


def parse_odds_value(raw: str, digits: int = 1) -> Optional[float]:
    """JRA-VANオッズ文字列をfloatに変換

    Args:
        raw: "0035", "000120" 等
        digits: 小数桁数（単勝=1, 馬連=1）

    Returns:
        float or None (取消・エラー時)
    """
    if not raw or raw.strip() in ('', '----', '****', '0000'):
        return None
    try:
        return int(raw) / (10 ** digits)
    except (ValueError, TypeError):
        return None


# === 確定オッズ ===

def get_final_win_odds(race_code: str) -> Dict[int, dict]:
    """確定単勝オッズを取得

    Returns:
        {umaban: {'odds': float, 'ninki': int}}
    """
    rows = query(
        "SELECT UMABAN, ODDS, NINKI FROM odds1_tansho WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        umaban = int(r['UMABAN'])
        odds = parse_odds_value(r['ODDS'])
        ninki = int(r['NINKI']) if r['NINKI'] and r['NINKI'].strip() else None
        if odds is not None:
            result[umaban] = {'odds': odds, 'ninki': ninki}
    return result


def get_final_place_odds(race_code: str) -> Dict[int, dict]:
    """確定複勝オッズを取得

    Returns:
        {umaban: {'odds_low': float, 'odds_high': float, 'ninki': int}}
    """
    rows = query(
        "SELECT UMABAN, ODDS_SAITEI, ODDS_SAIKOU, NINKI FROM odds1_fukusho WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        umaban = int(r['UMABAN'])
        low = parse_odds_value(r.get('ODDS_SAITEI', ''))
        high = parse_odds_value(r.get('ODDS_SAIKOU', ''))
        ninki = int(r['NINKI']) if r['NINKI'] and r['NINKI'].strip() else None
        if low is not None:
            result[umaban] = {'odds_low': low, 'odds_high': high, 'ninki': ninki}
    return result


# === 時系列オッズ（レース前オッズ取得の核心） ===

def get_timeseries_win_odds(race_code: str) -> List[dict]:
    """時系列単勝オッズを全スナップショット取得

    Returns:
        [{'time': str, 'umaban': int, 'odds': float, 'ninki': int}, ...]
        time昇順でソート
    """
    rows = query(
        "SELECT HAPPYO_TSUKIHI_JIFUN, UMABAN, ODDS, NINKI "
        "FROM odds1_tansho_jikeiretsu "
        "WHERE RACE_CODE = %s ORDER BY HAPPYO_TSUKIHI_JIFUN, UMABAN",
        (race_code,)
    )
    result = []
    for r in rows:
        odds = parse_odds_value(r['ODDS'])
        if odds is not None:
            result.append({
                'time': r['HAPPYO_TSUKIHI_JIFUN'],
                'umaban': int(r['UMABAN']),
                'odds': odds,
                'ninki': int(r['NINKI']) if r['NINKI'] and r['NINKI'].strip() else None,
            })
    return result


def get_latest_pre_race_win_odds(race_code: str) -> Dict[int, dict]:
    """レース直前（最終スナップショット）の単勝オッズを取得

    時系列オッズのうち最も遅い時刻のスナップショットを返す。
    これがレース前の「最新オッズ」に該当する。

    Returns:
        {umaban: {'odds': float, 'ninki': int, 'snapshot_time': str}}
    """
    # 最新のスナップショット時刻を取得
    latest = query(
        "SELECT MAX(HAPPYO_TSUKIHI_JIFUN) as latest_time "
        "FROM odds1_tansho_jikeiretsu WHERE RACE_CODE = %s",
        (race_code,)
    )
    if not latest or not latest[0].get('latest_time'):
        return {}

    latest_time = latest[0]['latest_time']

    rows = query(
        "SELECT UMABAN, ODDS, NINKI "
        "FROM odds1_tansho_jikeiretsu "
        "WHERE RACE_CODE = %s AND HAPPYO_TSUKIHI_JIFUN = %s",
        (race_code, latest_time)
    )
    result = {}
    for r in rows:
        umaban = int(r['UMABAN'])
        odds = parse_odds_value(r['ODDS'])
        ninki = int(r['NINKI']) if r['NINKI'] and r['NINKI'].strip() else None
        if odds is not None:
            result[umaban] = {
                'odds': odds,
                'ninki': ninki,
                'snapshot_time': latest_time,
            }
    return result


def get_odds_snapshots_count(race_code: str) -> int:
    """あるレースの時系列オッズスナップショット数を返す"""
    result = query(
        "SELECT COUNT(DISTINCT HAPPYO_TSUKIHI_JIFUN) as cnt "
        "FROM odds1_tansho_jikeiretsu WHERE RACE_CODE = %s",
        (race_code,)
    )
    return result[0]['cnt'] if result else 0


# === 馬連オッズ ===

def get_final_quinella_odds(race_code: str) -> Dict[str, dict]:
    """確定馬連オッズを取得

    Returns:
        {'0102': {'odds': 12.0, 'ninki': 3}, ...}
    """
    rows = query(
        "SELECT KUMIBAN, ODDS, NINKI FROM odds2_umaren WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        odds = parse_odds_value(r['ODDS'])
        ninki = int(r['NINKI']) if r['NINKI'] and r['NINKI'].strip() else None
        if odds is not None:
            result[r['KUMIBAN']] = {'odds': odds, 'ninki': ninki}
    return result


# === バッチローダー（ML学習用） ===

def batch_get_pre_race_odds(race_codes: List[str]) -> Dict[str, Dict[int, dict]]:
    """複数レースの事前オッズを一括取得（ML学習用）

    各レースについて、時系列オッズの最終スナップショットを取得。
    時系列データがなければ確定オッズにフォールバック。

    Args:
        race_codes: race_codeのリスト

    Returns:
        {race_code: {umaban: {'odds': float, 'ninki': int, 'source': str}}}
        source: 'timeseries' | 'final'
    """
    from core.db import get_connection

    if not race_codes:
        return {}

    result = {}

    # バッチサイズで分割（MySQLのIN句上限対策）
    batch_size = 500
    for i in range(0, len(race_codes), batch_size):
        batch = race_codes[i:i + batch_size]
        placeholders = ','.join(['%s'] * len(batch))

        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 1) 時系列オッズ: 各レースの最終スナップショットを取得
            #    サブクエリで各レースのMAX(HAPPYO_TSUKIHI_JIFUN)を求める
            sql_ts = (
                "SELECT t.RACE_CODE, t.UMABAN, t.ODDS, t.NINKI "
                "FROM odds1_tansho_jikeiretsu t "
                "INNER JOIN ("
                "  SELECT RACE_CODE, MAX(HAPPYO_TSUKIHI_JIFUN) as max_time "
                "  FROM odds1_tansho_jikeiretsu "
                f"  WHERE RACE_CODE IN ({placeholders}) "
                "  GROUP BY RACE_CODE"
                ") m ON t.RACE_CODE = m.RACE_CODE "
                "  AND t.HAPPYO_TSUKIHI_JIFUN = m.max_time"
            )
            cursor.execute(sql_ts, tuple(batch))
            ts_rows = cursor.fetchall()

            ts_races = set()
            for r in ts_rows:
                rc = r['RACE_CODE']
                ts_races.add(rc)
                if rc not in result:
                    result[rc] = {}
                umaban = int(r['UMABAN'])
                odds = parse_odds_value(r['ODDS'])
                ninki = int(r['NINKI']) if r['NINKI'] and r['NINKI'].strip() else None
                if odds is not None:
                    result[rc][umaban] = {'odds': odds, 'ninki': ninki, 'source': 'timeseries'}

            # 2) 時系列がないレースは確定オッズでフォールバック
            missing = [rc for rc in batch if rc not in ts_races]
            if missing:
                placeholders_m = ','.join(['%s'] * len(missing))
                sql_final = (
                    "SELECT RACE_CODE, UMABAN, ODDS, NINKI FROM odds1_tansho "
                    f"WHERE RACE_CODE IN ({placeholders_m})"
                )
                cursor.execute(sql_final, tuple(missing))
                final_rows = cursor.fetchall()

                for r in final_rows:
                    rc = r['RACE_CODE']
                    if rc not in result:
                        result[rc] = {}
                    umaban = int(r['UMABAN'])
                    odds = parse_odds_value(r['ODDS'])
                    ninki = int(r['NINKI']) if r['NINKI'] and r['NINKI'].strip() else None
                    if odds is not None:
                        result[rc][umaban] = {'odds': odds, 'ninki': ninki, 'source': 'final'}

            cursor.close()

    return result


def is_db_available() -> bool:
    """mykeibadb DBが接続可能かチェック"""
    try:
        from core.db import get_connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
        return True
    except Exception:
        return False


# === ユーティリティ ===

def get_race_count() -> int:
    """DBに格納されたレース数"""
    result = query("SELECT COUNT(DISTINCT RACE_CODE) as cnt FROM race_shosai")
    return result[0]['cnt'] if result else 0


def check_data_availability(race_code: str) -> dict:
    """指定レースのデータ有無チェック"""
    checks = {
        'race_shosai': query(
            "SELECT COUNT(*) as cnt FROM race_shosai WHERE RACE_CODE = %s",
            (race_code,)
        )[0]['cnt'],
        'umagoto_race_joho': query(
            "SELECT COUNT(*) as cnt FROM umagoto_race_joho WHERE RACE_CODE = %s",
            (race_code,)
        )[0]['cnt'],
        'odds1_tansho': query(
            "SELECT COUNT(*) as cnt FROM odds1_tansho WHERE RACE_CODE = %s",
            (race_code,)
        )[0]['cnt'],
        'odds1_jikeiretsu': query(
            "SELECT COUNT(*) as cnt FROM odds1_tansho_jikeiretsu WHERE RACE_CODE = %s",
            (race_code,)
        )[0]['cnt'],
        'odds2_umaren': query(
            "SELECT COUNT(*) as cnt FROM odds2_umaren WHERE RACE_CODE = %s",
            (race_code,)
        )[0]['cnt'],
    }
    return checks


if __name__ == '__main__':
    # 簡易テスト
    import sys
    if len(sys.argv) > 1:
        rc = sys.argv[1]
    else:
        # デフォルトのテスト用race_code
        rc = '2026020806010208'

    print(f"Race: {rc}")
    print(f"\nData availability: {check_data_availability(rc)}")

    final = get_final_win_odds(rc)
    if final:
        print(f"\nFinal win odds ({len(final)} horses):")
        for umaban in sorted(final.keys()):
            d = final[umaban]
            print(f"  #{umaban}: {d['odds']}x (ninki={d['ninki']})")

    ts_count = get_odds_snapshots_count(rc)
    print(f"\nTimeseries snapshots: {ts_count}")

    if ts_count > 0:
        pre = get_latest_pre_race_win_odds(rc)
        print(f"\nLatest pre-race odds ({len(pre)} horses):")
        for umaban in sorted(pre.keys()):
            d = pre[umaban]
            print(f"  #{umaban}: {d['odds']}x (time={d['snapshot_time']})")

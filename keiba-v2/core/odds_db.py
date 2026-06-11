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


def _parse_ninki(raw) -> Optional[int]:
    """NINKI(人気)文字列を安全に int へ。 '**'(エラー)/'----'(取消)/空 は None。

    JRA-VAN は未確定/エラー時 NINKI に '**' を入れることがあり、 素朴な int() は落ちる。
    """
    if raw is None:
        return None
    s = str(raw).strip()
    return int(s) if s.isdigit() else None


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
        ninki = _parse_ninki(r['NINKI'])
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
        ninki = _parse_ninki(r['NINKI'])
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
                'ninki': _parse_ninki(r['NINKI']),
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
        ninki = _parse_ninki(r['NINKI'])
        if odds is not None:
            result[umaban] = {
                'odds': odds,
                'ninki': ninki,
                'snapshot_time': latest_time,
            }
    return result


def _hhmi_minus(hhmi: str, minutes: int) -> str:
    """'HHMI'(4桁) から minutes 分引いた 'HHMI'。 負側のみ24h戻し(日跨ぎはレア)。"""
    try:
        h, m = int(hhmi[:2]), int(hhmi[2:])
    except (ValueError, TypeError, IndexError):
        return hhmi
    total = (h * 60 + m - minutes) % (24 * 60)
    return f"{total // 60:02d}{total % 60:02d}"


def get_win_odds_at_cutoff(race_code: str, minutes_before: int = 5) -> Dict[int, dict]:
    """発走 minutes_before 分前(以前) の最後の時系列単勝オッズ。

    = 投票締切時点で実際に見えるオッズ = 後知恵でない直前オッズ。
    時系列の単純な最終スナップショットは「発走後に配信される確定オッズ」を含む
    (実測: 発走14:30 のレースに 14:43 のスナップショットがある) ため、 HASSO_JIKOKU を
    基準にカットオフして発走後データを除外する。 較正/EV検証/実運用で同一時点を使うのが肝。

    フォールバック: 発走時刻欠損 → 確定オッズ(source=final_fallback)。
                    カットオフ以前のtsが無い → 最終pre(source=latest_pre_fallback)。
    Returns: {umaban: {'odds', 'ninki', 'snapshot_time', 'source'}}
    """
    rs = query("SELECT HASSO_JIKOKU FROM race_shosai WHERE RACE_CODE = %s", (race_code,))
    hasso = str(rs[0]["HASSO_JIKOKU"]).strip() if rs and rs[0].get("HASSO_JIKOKU") else ""
    if not (hasso.isdigit() and len(hasso) == 4):
        return {u: {**v, 'source': 'final_fallback'}
                for u, v in get_final_win_odds(race_code).items()}
    cutoff = race_code[4:8] + _hhmi_minus(hasso, minutes_before)
    mt = query(
        "SELECT MAX(HAPPYO_TSUKIHI_JIFUN) m FROM odds1_tansho_jikeiretsu "
        "WHERE RACE_CODE = %s AND HAPPYO_TSUKIHI_JIFUN <= %s", (race_code, cutoff))
    if not mt or not mt[0].get("m"):
        return {u: {**v, 'source': 'latest_pre_fallback'}
                for u, v in get_latest_pre_race_win_odds(race_code).items()}
    snap = mt[0]["m"]
    result = {}
    rows = query(
        "SELECT UMABAN, ODDS, NINKI FROM odds1_tansho_jikeiretsu "
        "WHERE RACE_CODE = %s AND HAPPYO_TSUKIHI_JIFUN = %s", (race_code, snap))
    for r in rows:
        odds = parse_odds_value(r['ODDS'])
        if odds is not None:
            result[int(r['UMABAN'])] = {
                'odds': odds, 'ninki': _parse_ninki(r['NINKI']),
                'snapshot_time': snap, 'source': 'cutoff',
            }
    return result


def get_place_odds_at_cutoff(race_code: str, minutes_before: int = 5) -> Dict[int, dict]:
    """発走 minutes_before 分前(以前) の最後の時系列複勝オッズ (low/high)。

    get_win_odds_at_cutoff の複勝版。 複勝EV(=補正P×複勝最低オッズ) の検証で使う。
    Returns: {umaban: {'odds_low', 'odds_high', 'ninki', 'snapshot_time', 'source'}}
    """
    rs = query("SELECT HASSO_JIKOKU FROM race_shosai WHERE RACE_CODE = %s", (race_code,))
    hasso = str(rs[0]["HASSO_JIKOKU"]).strip() if rs and rs[0].get("HASSO_JIKOKU") else ""
    if not (hasso.isdigit() and len(hasso) == 4):
        return {u: {**v, 'source': 'final_fallback'}
                for u, v in get_final_place_odds(race_code).items()}
    cutoff = race_code[4:8] + _hhmi_minus(hasso, minutes_before)
    mt = query(
        "SELECT MAX(HAPPYO_TSUKIHI_JIFUN) m FROM odds1_fukusho_jikeiretsu "
        "WHERE RACE_CODE = %s AND HAPPYO_TSUKIHI_JIFUN <= %s", (race_code, cutoff))
    if not mt or not mt[0].get("m"):
        return {}
    snap = mt[0]["m"]
    result = {}
    rows = query(
        "SELECT UMABAN, ODDS_SAITEI, ODDS_SAIKOU, NINKI FROM odds1_fukusho_jikeiretsu "
        "WHERE RACE_CODE = %s AND HAPPYO_TSUKIHI_JIFUN = %s", (race_code, snap))
    for r in rows:
        low = parse_odds_value(r.get('ODDS_SAITEI', ''))
        high = parse_odds_value(r.get('ODDS_SAIKOU', ''))
        if low is not None:
            result[int(r['UMABAN'])] = {
                'odds_low': low, 'odds_high': high, 'ninki': _parse_ninki(r['NINKI']),
                'snapshot_time': snap, 'source': 'cutoff',
            }
    return result


def batch_get_win_odds_at_cutoff(
    race_codes: List[str],
    minutes_before: int = 5,
) -> Dict[str, Dict[int, dict]]:
    """複数レースの「発走 minutes_before 分前(以前)」単勝オッズを一括取得 (較正fit/診断用)。

    get_win_odds_at_cutoff のバッチ版。 HASSO を一括取得して race 別カットオフを決め、
    各レースで cutoff 以前の最終スナップショットを引く。 HASSO 欠損 race は確定オッズに
    フォールバック。 1 接続で race ごとにサブクエリ実行 (時系列全行 fetch は重いため回避)。

    Returns: {race_code: {umaban: {'odds', 'ninki', 'snapshot_time', 'source'}}}
    """
    from core.db import get_connection

    if not race_codes:
        return {}

    # 1) HASSO_JIKOKU を一括取得 → race 別カットオフ文字列(MMDDHHMI)
    cutoffs: Dict[str, str] = {}
    bs = 500
    for i in range(0, len(race_codes), bs):
        b = race_codes[i:i + bs]
        ph = ",".join(["%s"] * len(b))
        for r in query(f"SELECT RACE_CODE, HASSO_JIKOKU FROM race_shosai WHERE RACE_CODE IN ({ph})",
                       tuple(b)):
            h = str(r["HASSO_JIKOKU"] or "").strip()
            if h.isdigit() and len(h) == 4:
                rc = r["RACE_CODE"]
                cutoffs[rc] = rc[4:8] + _hhmi_minus(h, minutes_before)

    # 2) race ごとに cutoff 以前の最終スナップショットを引く
    result: Dict[str, Dict[int, dict]] = {}
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        for rc in race_codes:
            co = cutoffs.get(rc)
            if co is None:
                cur.execute(
                    "SELECT UMABAN, ODDS, NINKI, NULL AS HAPPYO_TSUKIHI_JIFUN "
                    "FROM odds1_tansho WHERE RACE_CODE = %s", (rc,))
                src = "final_fallback"
            else:
                cur.execute(
                    "SELECT UMABAN, ODDS, NINKI, HAPPYO_TSUKIHI_JIFUN FROM odds1_tansho_jikeiretsu "
                    "WHERE RACE_CODE = %s AND HAPPYO_TSUKIHI_JIFUN = ("
                    "  SELECT MAX(HAPPYO_TSUKIHI_JIFUN) FROM odds1_tansho_jikeiretsu "
                    "  WHERE RACE_CODE = %s AND HAPPYO_TSUKIHI_JIFUN <= %s)", (rc, rc, co))
                src = "cutoff"
            for r in cur.fetchall():
                odds = parse_odds_value(r["ODDS"])
                if odds is not None:
                    result.setdefault(rc, {})[int(r["UMABAN"])] = {
                        'odds': odds, 'ninki': _parse_ninki(r["NINKI"]),
                        'snapshot_time': r.get("HAPPYO_TSUKIHI_JIFUN"), 'source': src,
                    }
        cur.close()
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
        ninki = _parse_ninki(r['NINKI'])
        if odds is not None:
            result[r['KUMIBAN']] = {'odds': odds, 'ninki': ninki}
    return result


# === ワイドオッズ ===

def get_final_wide_odds(race_code: str) -> Dict[str, dict]:
    """確定ワイドオッズを取得

    Returns:
        {'0102': {'odds_low': 7.7, 'odds_high': 8.5, 'ninki': 10}, ...}
        KUMIBANは4桁 (例: '0102' = 馬番1-2)
    """
    rows = query(
        "SELECT KUMIBAN, ODDS_SAITEI, ODDS_SAIKOU, NINKI FROM odds3_wide WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        low = parse_odds_value(r.get('ODDS_SAITEI', ''))
        high = parse_odds_value(r.get('ODDS_SAIKOU', ''))
        ninki = _parse_ninki(r['NINKI'])
        if low is not None:
            result[r['KUMIBAN']] = {'odds_low': low, 'odds_high': high, 'ninki': ninki}
    return result


# === 馬単オッズ ===

def get_final_exacta_odds(race_code: str) -> Dict[str, dict]:
    """確定馬単オッズを取得 (odds4_umatan)

    Returns:
        {'1406': {'odds': 10.7, 'ninki': 1}, ...}
        KUMIBANは4桁・順序あり (例: '1406' = 1着14番→2着6番)
    """
    rows = query(
        "SELECT KUMIBAN, ODDS, NINKI FROM odds4_umatan WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        odds = parse_odds_value(r['ODDS'])
        ninki = _parse_ninki(r['NINKI'])
        if odds is not None:
            result[r['KUMIBAN']] = {'odds': odds, 'ninki': ninki}
    return result


# === 三連複オッズ ===

def get_final_trio_odds(race_code: str) -> Dict[str, dict]:
    """確定三連複オッズを取得 (odds5_sanrenpuku)

    Returns:
        {'040614': {'odds': 6.7, 'ninki': 1}, ...}
        KUMIBANは6桁・順不同 (馬番昇順, 例: '040614' = 4-6-14)
    """
    rows = query(
        "SELECT KUMIBAN, ODDS, NINKI FROM odds5_sanrenpuku WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        odds = parse_odds_value(r['ODDS'])
        ninki = _parse_ninki(r['NINKI'])
        if odds is not None:
            result[r['KUMIBAN']] = {'odds': odds, 'ninki': ninki}
    return result


# === 三連単オッズ ===

def get_final_trifecta_odds(race_code: str) -> Dict[str, dict]:
    """確定三連単オッズを取得 (odds6_sanrentan)

    Returns:
        {'061404': {'odds': 26.1, 'ninki': 1}, ...}
        KUMIBANは6桁・順序あり (例: '061404' = 1着6番→2着14番→3着4番)
    """
    rows = query(
        "SELECT KUMIBAN, ODDS, NINKI FROM odds6_sanrentan WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        odds = parse_odds_value(r['ODDS'])
        ninki = _parse_ninki(r['NINKI'])
        if odds is not None:
            result[r['KUMIBAN']] = {'odds': odds, 'ninki': ninki}
    return result


# === 全券種オッズ一括取得 (券種効率ビュー用) ===

def get_all_combo_odds(race_code: str) -> Dict[str, Dict[str, dict]]:
    """1レースの全券種オッズを一括取得 (券種効率ビュー / ハーヴィル合成オッズ判断用)

    各券種ごとに KUMIBAN → odds の dict を返す。 ワイドは odds_low/high を持つため
    キー 'odds' は odds_low を採用 (保守的、 bet_engine._lookup_wide_odds と整合)。

    Returns:
        {
          'tansho':   {umaban_int: {'odds': float, 'ninki': int}},        # 単勝 (単一馬)
          'fukusho':  {umaban_int: {'odds_low','odds_high','ninki'}},     # 複勝
          'umaren':   {'0102': {'odds','ninki'}},                         # 馬連 (4桁順不同)
          'wide':     {'0102': {'odds','odds_low','odds_high','ninki'}},  # ワイド (4桁順不同)
          'umatan':   {'0102': {'odds','ninki'}},                         # 馬単 (4桁順序あり)
          'sanrenpuku': {'010203': {'odds','ninki'}},                     # 三連複 (6桁順不同)
          'sanrentan':  {'010203': {'odds','ninki'}},                     # 三連単 (6桁順序あり)
        }

    注: odds2-6 は「確定 (発走時) オッズ」テーブルで 1 組番 (KUMIBAN) = 1 行 (時系列の
    重複スナップショット無し。 実データで rows == distinct_kumiban を確認済) のため、
    各 getter の dict 化で組番が衝突することはない。
    """
    wide_raw = get_final_wide_odds(race_code)
    wide = {
        k: {'odds': v.get('odds_low'), 'odds_low': v.get('odds_low'),
            'odds_high': v.get('odds_high'), 'ninki': v.get('ninki')}
        for k, v in wide_raw.items()
    }
    return {
        'tansho': get_final_win_odds(race_code),
        'fukusho': get_final_place_odds(race_code),
        'umaren': get_final_quinella_odds(race_code),
        'wide': wide,
        'umatan': get_final_exacta_odds(race_code),
        'sanrenpuku': get_final_trio_odds(race_code),
        'sanrentan': get_final_trifecta_odds(race_code),
    }


# === バッチローダー（ML学習用） ===

def batch_get_pre_race_odds(
    race_codes: List[str],
    strict: bool = False,
) -> Dict[str, Dict[int, dict]]:
    """複数レースの事前オッズを一括取得（ML学習用）

    各レースについて、時系列オッズの最終スナップショットを取得。
    時系列データがなければ確定オッズにフォールバック。

    注意: 確定オッズ(final)はJRA-VANの「発走直前の最終オッズ」であり、
    レース結果を含む事後情報ではない。ただしデータ送信タイミングは
    レース後のSEデータに含まれる。

    Args:
        race_codes: race_codeのリスト
        strict: Trueの場合、時系列オッズのみ使用（確定オッズへのフォールバック無し）

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
                ninki = _parse_ninki(r['NINKI'])
                if odds is not None:
                    result[rc][umaban] = {'odds': odds, 'ninki': ninki, 'source': 'timeseries'}

            # 2) 時系列がないレースは確定オッズでフォールバック（strict時はスキップ）
            missing = [rc for rc in batch if rc not in ts_races]
            if missing and not strict:
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
                    ninki = _parse_ninki(r['NINKI'])
                    if odds is not None:
                        result[rc][umaban] = {'odds': odds, 'ninki': ninki, 'source': 'final'}

            cursor.close()

    return result


def batch_get_place_odds(
    race_codes: List[str],
) -> Dict[str, Dict[int, dict]]:
    """複数レースの複勝オッズを一括取得

    時系列複勝オッズの最終スナップショットを取得。
    時系列データがなければ確定複勝オッズにフォールバック。

    Returns:
        {race_code: {umaban: {'odds_low': float, 'odds_high': float, 'source': str}}}
    """
    from core.db import get_connection

    if not race_codes:
        return {}

    result = {}

    batch_size = 500
    for i in range(0, len(race_codes), batch_size):
        batch = race_codes[i:i + batch_size]
        placeholders = ','.join(['%s'] * len(batch))

        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 1) 時系列複勝オッズ: 各レースの最終スナップショットを取得
            sql_ts = (
                "SELECT t.RACE_CODE, t.UMABAN, t.ODDS_SAITEI, t.ODDS_SAIKOU "
                "FROM odds1_fukusho_jikeiretsu t "
                "INNER JOIN ("
                "  SELECT RACE_CODE, MAX(HAPPYO_TSUKIHI_JIFUN) as max_time "
                "  FROM odds1_fukusho_jikeiretsu "
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
                low = parse_odds_value(r.get('ODDS_SAITEI', ''))
                high = parse_odds_value(r.get('ODDS_SAIKOU', ''))
                if low is not None:
                    result[rc][umaban] = {'odds_low': low, 'odds_high': high, 'source': 'timeseries'}

            # 2) 時系列がないレースは確定複勝オッズでフォールバック
            missing = [rc for rc in batch if rc not in ts_races]
            if missing:
                placeholders_m = ','.join(['%s'] * len(missing))
                sql_final = (
                    "SELECT RACE_CODE, UMABAN, ODDS_SAITEI, ODDS_SAIKOU FROM odds1_fukusho "
                    f"WHERE RACE_CODE IN ({placeholders_m})"
                )
                cursor.execute(sql_final, tuple(missing))
                final_rows = cursor.fetchall()

                for r in final_rows:
                    rc = r['RACE_CODE']
                    if rc not in result:
                        result[rc] = {}
                    umaban = int(r['UMABAN'])
                    low = parse_odds_value(r.get('ODDS_SAITEI', ''))
                    high = parse_odds_value(r.get('ODDS_SAIKOU', ''))
                    if low is not None:
                        result[rc][umaban] = {'odds_low': low, 'odds_high': high, 'source': 'final'}

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

# -*- coding: utf-8 -*-
"""kaiko_features の単体テスト (Session 169 / 回顧軸 = 前走不利・巻き返し特徴量)

検証:
  - _pace_slope: 前後半ラップ差・先頭区間ドロップ・有効区間<4でNone
  - compute_kaiko_features:
      * 過去走なし → 全デフォルト
      * surge = corner4 - finish（last / max3 / avg3）
      * blocked_last = surge>0 ∧ finish>=4 のみ正、それ以外0
      * trouble_badfinish3 = (不利 or 出遅れ) ∧ finish>=6 の直近3走カウント
      * SED欠損の過去走はスキップされ surge 系 None のまま
      * srb_index=None → Phase B 特徴量は全 None
      * front_collapse_victim = 前傾(slope>0) ∧ 失速(surge<0)
      * kire_make = 後傾(slope<0) ∧ 差し(surge>0) ∧ 着外(finish>=4)
      * 当該レース日より後の走は past に含めない（リーク防止）
"""
import pytest

from ml.features.kaiko_features import (
    _pace_slope,
    compute_kaiko_features,
    kaiko_feature_defaults,
    KAIKO_FEATURE_COLS,
    KAIKO_SRB_FEATURES,
)


# --- _pace_slope ---

def test_pace_slope_none_cases():
    assert _pace_slope(None) is None
    assert _pace_slope([]) is None
    assert _pace_slope([120, 110, 0, None]) is None  # 有効区間2 < 4


def test_pace_slope_drops_start_furlong():
    # 6区間: [start遅, ...] → 先頭ドロップ後 [110,110,120,120,130] half=2
    # first=mean(110,110)=110, second=mean(120,120,130)=123.3 → +13.3
    ft = [130, 110, 110, 120, 120, 130]
    s = _pace_slope(ft)
    assert s == pytest.approx(13.3, abs=0.1)


def test_pace_slope_sign_zenkei_vs_koukei():
    # 後半が遅い = 前傾（前崩れ）→ 正
    assert _pace_slope([120, 120, 130, 130]) > 0   # 4区間（ドロップなし）
    # 後半が速い = 後傾（瞬発戦）→ 負
    assert _pace_slope([130, 130, 120, 120]) < 0


# --- フィクスチャ ---

def _sed(corner4, finish, furi=0, deokure=0):
    return {'corner4': corner4, 'finish_position': finish,
            'furi_adj': furi, 'deokure_adj': deokure, 'num_runners': 16}


def _run(date, rid, corner4, finish, furi=0, deokure=0):
    """history_cache の1走 + 対応する SED エントリを返す。"""
    return ({'race_date': date, 'race_id': rid, 'umaban': 5,
             'finish_position': finish},
            _sed(corner4, finish, furi, deokure))


def _build(runs):
    """runs=[(date,rid,corner4,finish,furi,deokure), ...] → (history_cache, sed_index)"""
    ketto = '2020999999'
    hist, sed = [], {}
    for date, rid, c4, fin, *rest in runs:
        furi = rest[0] if len(rest) > 0 else 0
        deo = rest[1] if len(rest) > 1 else 0
        hist.append({'race_date': date, 'race_id': rid, 'umaban': 5,
                     'finish_position': fin})
        sed[f"{ketto}_{date}"] = _sed(c4, fin, furi, deo)
    return ketto, {ketto: hist}, sed


# --- compute_kaiko_features ---

def test_no_past_returns_defaults():
    ketto, hc, sed = _build([('2024-01-01', '2024010105010101', 5, 3)])
    # 当該レース日が過去走と同日 → past 空
    feat = compute_kaiko_features(ketto, '2024-01-01', hc, sed, None)
    assert feat == kaiko_feature_defaults()
    assert feat['kaiko_surge_last'] is None
    assert feat['kaiko_trouble_badfinish3'] == 0


def test_surge_basic():
    # 4角5番手 → 3着 = surge +2
    ketto, hc, sed = _build([('2024-05-01', '2024050105010101', 5, 3)])
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    assert feat['kaiko_surge_last'] == 2
    assert feat['kaiko_surge_max3'] == 2
    assert feat['kaiko_surge_avg3'] == 2.0


def test_surge_max3_avg3():
    # surges: +2, -3, +6（直近3走）
    ketto, hc, sed = _build([
        ('2024-03-01', '2024030105010101', 5, 3),    # +2
        ('2024-04-01', '2024040105010102', 4, 7),    # -3
        ('2024-05-01', '2024050105010103', 12, 6),   # +6
    ])
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    assert feat['kaiko_surge_last'] == 6
    assert feat['kaiko_surge_max3'] == 6
    assert feat['kaiko_surge_avg3'] == pytest.approx((2 - 3 + 6) / 3, abs=0.01)


def test_blocked_last_fires_on_surge_and_badfinish():
    # 12番手 → 5着 = surge +7, finish>=4 → blocked = 7
    ketto, hc, sed = _build([('2024-05-01', '2024050105010101', 12, 5)])
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    assert feat['kaiko_blocked_last'] == 7


def test_blocked_last_zero_when_placed():
    # 12番手 → 2着 = surge +10 だが finish<4 → blocked = 0（馬券圏に来たので妙味なし）
    ketto, hc, sed = _build([('2024-05-01', '2024050105010101', 12, 2)])
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    assert feat['kaiko_blocked_last'] == 0


def test_trouble_badfinish3_count():
    # 不利あり×10着 / 出遅れ×8着 / クリーン×3着 → 2件
    ketto, hc, sed = _build([
        ('2024-03-01', '2024030105010101', 8, 10, 5, 0),   # 不利 ∧ 凡走
        ('2024-04-01', '2024040105010102', 6, 8, 0, 3),    # 出遅れ ∧ 凡走
        ('2024-05-01', '2024050105010103', 5, 3, 0, 0),    # クリーン好走
    ])
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    assert feat['kaiko_trouble_badfinish3'] == 2


def test_missing_sed_skipped():
    # history に2走あるが SED は1走分しかない → surge は埋まるレコードのみ
    ketto = '2020999999'
    hc = {ketto: [
        {'race_date': '2024-04-01', 'race_id': '2024040105010101', 'umaban': 5, 'finish_position': 7},
        {'race_date': '2024-05-01', 'race_id': '2024050105010102', 'umaban': 5, 'finish_position': 3},
    ]}
    sed = {f"{ketto}_2024-05-01": _sed(5, 3)}  # 前々走の SED 欠
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    assert feat['kaiko_surge_last'] == 2  # 直近走のみ


def test_srb_none_phase_b_all_none():
    ketto, hc, sed = _build([('2024-05-01', '2024050105010101', 12, 5)])
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    for c in KAIKO_SRB_FEATURES:
        assert feat[c] is None


def test_front_collapse_victim():
    # 前傾(slope>0) ∧ 失速(surge<0): 4角3番手→8着 surge=-5, 前傾ラップ
    ketto, hc, sed = _build([('2024-05-01', '2024050105010101', 3, 8)])
    jk = '05241501'  # race_id_to_jrdb_key('2024050105010101') を後で検算
    from ml.features.jrdb_features import race_id_to_jrdb_key
    jk = race_id_to_jrdb_key('2024050105010101')
    srb = {jk: {'furlong_times': [120, 120, 130, 130]}}  # slope>0 前傾
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, srb)
    assert feat['kaiko_prev_pace_slope'] > 0
    assert feat['kaiko_front_collapse_victim_last'] == 5  # abs(-5)
    assert feat['kaiko_kire_make_last'] == 0


def test_kire_make():
    # 後傾(slope<0) ∧ 差し(surge>0) ∧ 着外(finish>=4): 12番手→5着 surge=+7
    ketto, hc, sed = _build([('2024-05-01', '2024050105010101', 12, 5)])
    from ml.features.jrdb_features import race_id_to_jrdb_key
    jk = race_id_to_jrdb_key('2024050105010101')
    srb = {jk: {'furlong_times': [130, 130, 120, 120]}}  # slope<0 後傾
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, srb)
    assert feat['kaiko_prev_pace_slope'] < 0
    assert feat['kaiko_kire_make_last'] == 7
    assert feat['kaiko_front_collapse_victim_last'] == 0


def test_no_future_leak():
    # 当該レース日より後の走は past に含めない
    ketto, hc, sed = _build([
        ('2024-05-01', '2024050105010101', 5, 3),    # past
        ('2024-07-01', '2024070105010102', 1, 1),    # 未来（除外されるべき）
    ])
    feat = compute_kaiko_features(ketto, '2024-06-01', hc, sed, None)
    assert feat['kaiko_surge_last'] == 2  # 5/1 の +2 のみ。7/1 は無視


def test_feature_cols_match_defaults():
    assert set(KAIKO_FEATURE_COLS) == set(kaiko_feature_defaults().keys())
    assert all(c in KAIKO_FEATURE_COLS for c in KAIKO_SRB_FEATURES)

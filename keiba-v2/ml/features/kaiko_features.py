#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回顧（kaiko）特徴量 — 「前走の不利で着順が能力を過小表現している馬」を捉える軸

背景（書籍横断考察 2026-06-20 / 『レース回顧の新常識』×『妙味度名鑑』）:
  現行 polaris の主力（IDM / CID）は「能力」と「状態」の軸。構造上、
  「強いのに前走で詰まって・脚を余して・前崩れに巻き込まれて負けた馬」
  ＝着順が実走内容を過小表現している馬を見抜けない（指数も着順も下がって入る）。
  これがモデルの死角＝「回顧軸」。市場が過小評価する馬の発生メカニズムそのもの。

死蔵 JRDB データから、過去走join でこの回顧シグナルを特徴量化する。
（JRDB 棚卸し v2 docs/jrdb_data_inventory.md §5 — SRB はアルファ残存の本命）

Phase A（SED・再インデックス不要）:
  - surge = corner4 - finish_position（直線でのポジションゲイン＝後方から押し上げ / 脚を余した）
  - blocked = 差したのに着外（不利 victim で上積み余地）
  - trouble_badfinish3 = JRDB 不利/出遅れ記録 × 着外 のrecency

Phase B（SRB furlong_times 配線・race単位 join）:
  - pace_slope = 前半 vs 後半ラップ差（前傾=前崩れ / 後傾=瞬発戦）
  - front_collapse_victim = 前に居て前傾ペースで潰れた（ペース正常化で巻き返し）

結合キー:
  SED:  {ketto_num_10}_{race_date}        （馬×過去走日）
  SRB:  race_id_to_jrdb_key(past race_id) （過去レース単位）

欠損は None（LightGBM が NaN として「データなし」を区別）。カウント系は 0。
"""

from typing import Dict, List, Optional
import statistics

from ml.features.jrdb_features import race_id_to_jrdb_key


# 着順「着外」の閾値（巻き返し判定用）。少頭数を考えると 4 着以降を「妙味の出る着外」とみなす
_BADFINISH_TH = 4
_CLEAR_OUT_TH = 6  # 明確な凡走（不利×凡走カウント用）


def _pace_slope(furlong_times: Optional[list]) -> Optional[float]:
    """レースの18区間ハロンタイムから前後半ラップ差を計算。

    Returns:
        後半平均 - 前半平均（0.1秒単位）。
        > 0 → 後半が遅い = 前傾ラップ（ハイペース消耗・前崩れ → 差し有利）
        < 0 → 後半が速い = 後傾ラップ（スロー瞬発戦 → 前残り/キレ勝負）
        データ不足（有効区間 < 4）は None。
    """
    if not furlong_times:
        return None
    t = [x for x in furlong_times if x]  # None / 0 を除去
    if len(t) < 4:
        return None
    # 先頭区間はスタンディングスタートで遅い → 5区間以上あるなら除外して歪み回避
    if len(t) >= 5:
        t = t[1:]
    half = len(t) // 2
    first = statistics.mean(t[:half])
    second = statistics.mean(t[half:])
    return round(second - first, 1)


def kaiko_feature_defaults() -> dict:
    """全 kaiko 特徴量の初期値（欠損 = None / カウント = 0）。"""
    return {
        # === Phase A: SED（着順 vs 通過順・不利） ===
        'kaiko_surge_last': None,        # 前走 corner4 - finish（>0 = 押し上げ）
        'kaiko_surge_max3': None,        # 直近3走の最大 surge（ベストの巻き返し脚）
        'kaiko_surge_avg3': None,        # 直近3走の平均 surge
        'kaiko_blocked_last': None,      # 前走で差したのに着外（surge>0 ∧ finish>=4 の大きさ）
        'kaiko_trouble_badfinish3': 0,   # 直近3走で「不利/出遅れ ∧ 明確凡走」の回数
        # === Phase B: SRB（レースのラップ形状） ===
        'kaiko_prev_pace_slope': None,       # 前走の前後半ラップ差（後傾+ / 前傾-）
        'kaiko_pace_slope_avg3': None,       # 直近3走の平均
        'kaiko_front_collapse_victim_last': None,  # 前で潰れた（前傾 ∧ 失速）の大きさ
        'kaiko_kire_make_last': None,        # 後傾戦で差し届かず（後傾 ∧ 差して着外）
    }


# experiment.py / optuna_tuner.py が参照する特徴量名リスト
KAIKO_FEATURE_COLS = list(kaiko_feature_defaults().keys())

# SRB 配線が必要な特徴量（Phase A だけ回すときの除外用）
KAIKO_SRB_FEATURES = [
    'kaiko_prev_pace_slope',
    'kaiko_pace_slope_avg3',
    'kaiko_front_collapse_victim_last',
    'kaiko_kire_make_last',
]


def compute_kaiko_features(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
    jrdb_sed_index: dict,
    jrdb_srb_index: dict = None,
) -> dict:
    """回顧（前走不利 / 巻き返し）特徴量を計算。

    Args:
        ketto_num: 10桁血統登録番号
        race_date: 当該レース日 (YYYY-MM-DD)
        history_cache: {ketto_num: [{race_date, race_id, umaban, ...}, ...]}
        jrdb_sed_index: SED事後インデックス {ketto_num_race_date: {...}}
        jrdb_srb_index: SRBインデックス {jrdb_race_key: {furlong_times, ...}}（None で Phase A のみ）

    Returns:
        dict: kaiko_ プレフィックス付き特徴量
    """
    result = kaiko_feature_defaults()

    past_runs = history_cache.get(ketto_num, [])
    past = [r for r in past_runs if r.get('race_date', '') < race_date]
    if not past:
        return result

    last5 = past[-5:]

    # 各過去走の SED レコード + 当該過去走の SRB（レース）レコードを集める
    # 時系列順（古→新）の per-run dict: surge / pace_slope / trouble flags
    runs = []
    for r in last5:
        rd = r.get('race_date', '')
        sed = jrdb_sed_index.get(f"{ketto_num}_{rd}")
        if not sed:
            continue
        corner4 = sed.get('corner4') or 0
        finish = sed.get('finish_position') or 0
        surge = None
        if corner4 > 0 and finish > 0:
            surge = corner4 - finish  # >0 = 直線で押し上げ
        furi = (sed.get('furi_adj') or 0) > 0
        deokure = (sed.get('deokure_adj') or 0) > 0

        slope = None
        if jrdb_srb_index:
            rid = r.get('race_id', '')
            if rid:
                jk = race_id_to_jrdb_key(rid)
                if jk:
                    srb = jrdb_srb_index.get(jk)
                    if srb:
                        slope = _pace_slope(srb.get('furlong_times'))

        runs.append({
            'surge': surge,
            'finish': finish,
            'furi': furi,
            'deokure': deokure,
            'slope': slope,
        })

    if not runs:
        return result

    # === Phase A: surge 系 ===
    surges = [x['surge'] for x in runs if x['surge'] is not None]
    if surges:
        result['kaiko_surge_last'] = surges[-1]
        last3_surges = [x['surge'] for x in runs[-3:] if x['surge'] is not None]
        if last3_surges:
            result['kaiko_surge_max3'] = max(last3_surges)
            result['kaiko_surge_avg3'] = round(statistics.mean(last3_surges), 2)

    # blocked: 前走で押し上げた（surge>0）のに着外（finish>=4）→ 不利 victim・上積み余地
    last_run = runs[-1]
    if last_run['surge'] is not None and last_run['finish'] > 0:
        if last_run['surge'] > 0 and last_run['finish'] >= _BADFINISH_TH:
            result['kaiko_blocked_last'] = last_run['surge']
        else:
            result['kaiko_blocked_last'] = 0

    # trouble_badfinish3: 直近3走で「不利 or 出遅れ ∧ 明確凡走」の回数
    cnt = 0
    for x in runs[-3:]:
        if (x['furi'] or x['deokure']) and x['finish'] >= _CLEAR_OUT_TH:
            cnt += 1
    result['kaiko_trouble_badfinish3'] = cnt

    # === Phase B: SRB ラップ形状 ===
    if jrdb_srb_index:
        slopes = [x['slope'] for x in runs if x['slope'] is not None]
        if slopes:
            result['kaiko_prev_pace_slope'] = slopes[-1]
            last3_slopes = [x['slope'] for x in runs[-3:] if x['slope'] is not None]
            if last3_slopes:
                result['kaiko_pace_slope_avg3'] = round(statistics.mean(last3_slopes), 1)

        # 前崩れ victim: 前走が前傾（slope<0…ではなく後半遅い=slope>0が前傾）で失速（surge<0）
        #   slope>0 = 前傾（前崩れ）。そこで surge<0（前で粘れず後退）= ペース被害 → 正常化で巻き返し
        ls = last_run['slope']
        lsg = last_run['surge']
        if ls is not None and lsg is not None:
            if ls > 0 and lsg < 0:
                result['kaiko_front_collapse_victim_last'] = abs(lsg)
            else:
                result['kaiko_front_collapse_victim_last'] = 0
            # キレ負け: 後傾（slope<0）で差して（surge>0）着外（finish>=4）= 瞬発戦敗・脚質ミスマッチ
            if ls < 0 and lsg > 0 and last_run['finish'] >= _BADFINISH_TH:
                result['kaiko_kire_make_last'] = lsg
            else:
                result['kaiko_kire_make_last'] = 0

    return result

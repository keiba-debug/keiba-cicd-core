#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRDB特徴量

SED（事後IDM）の過去走履歴 + KYI（事前IDM）の当該レース予測値から特徴量を計算。

特徴量カテゴリ:
  A. 過去走IDM統計（SED）: idm_last, idm_avg3, idm_max5, idm_trend, idm_std
  B. 過去走テン/上がり指数（SED）: ten_idx, agari_idx の統計
  C. 過去走補正項（SED）: 出遅・不利の頻度
  D. 事前IDM・総合指数（KYI）: pre_idm, sogo_idx, training_idx等
  E. 乖離指標: 過去IDM平均 vs 事前IDM（成長/衰退シグナル）

結合キー: {ketto_num_10}_{race_date} → JRDB index lookup
"""

from typing import Dict, List, Optional
import statistics


def compute_jrdb_features(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
    jrdb_sed_index: dict,
    jrdb_kyi_index: dict,
) -> dict:
    """
    JRDB特徴量を計算。

    Args:
        ketto_num: 10桁血統登録番号
        race_date: 当該レース日 (YYYY-MM-DD)
        history_cache: 馬の過去走リスト {ketto_num: [{race_date, ...}, ...]}
        jrdb_sed_index: SED事後IDMインデックス {ketto_num_race_date: {...}}
        jrdb_kyi_index: KYI事前IDMインデックス {ketto_num_race_date: {...}}

    Returns:
        dict: jrdb_ プレフィックス付き特徴量
    """
    result = {
        # A. 過去走IDM統計 (SED)
        'jrdb_idm_last': -1.0,
        'jrdb_idm_avg3': -1.0,
        'jrdb_idm_max5': -1.0,
        'jrdb_idm_trend': 0.0,      # 最新 - 平均 (正=上昇傾向)
        'jrdb_idm_std': -1.0,
        # B. テン・上がり指数 (SED)
        'jrdb_agari_idx_last': -1.0,
        'jrdb_agari_idx_avg3': -1.0,
        'jrdb_ten_idx_last': -1.0,
        'jrdb_ten_idx_avg3': -1.0,
        # C. 過去走補正項 (SED)
        'jrdb_deokure_count5': 0,    # 直近5走で出遅ありの回数
        'jrdb_furi_count5': 0,       # 直近5走で不利ありの回数
        'jrdb_joushou_mean': -1.0,   # 上昇度コード平均
        # D. 事前IDM・指数 (KYI)
        'jrdb_pre_idm': -1.0,
        'jrdb_sogo_idx': -1.0,
        'jrdb_training_idx': -1.0,
        'jrdb_stable_idx': -1.0,
        'jrdb_jockey_idx': -1.0,
        'jrdb_info_idx': -1.0,
        'jrdb_gekisou_idx': -1.0,
        'jrdb_start_idx': -1.0,
        'jrdb_deokure_rate': -1.0,
        # E. 乖離指標
        'jrdb_idm_vs_pre': 0.0,     # 過去IDM平均 - 事前IDM (正=過小評価)
        'jrdb_idm_growth': 0.0,     # 直近IDM - 過去全体平均 (正=成長)
        # F. 不利補正内訳 (SED) — 前走の不利は次走巻き返しの兆候
        'jrdb_mae_furi_last': 0.0,   # 前走・前半不利補正
        'jrdb_naka_furi_last': 0.0,  # 前走・中盤不利補正
        'jrdb_ato_furi_last': 0.0,   # 前走・後半不利補正
        'jrdb_furi_total_last': 0.0, # 前走・不利合計
        'jrdb_baba_sa_last': 0.0,    # 前走・馬場差補正
        'jrdb_baba_sa_avg3': 0.0,    # 直近3走・馬場差補正平均
        # G. ペース適性 (SED + KYI)
        'jrdb_pace_match': None,     # 馬のペース vs レースペース適合度
        'jrdb_kyakushitsu': None,    # 脚質コード (1=逃げ,2=先行,3=差し,4=追込)
        'jrdb_distance_apt': None,   # 距離適性
    }

    # === A-C: 過去走IDMデータ (SED) ===
    past_runs = history_cache.get(ketto_num, [])
    past = [r for r in past_runs if r.get('race_date', '') < race_date]

    if past:
        # 直近5走のSEDデータを取得
        last5 = past[-5:]
        sed_records = []
        for r in last5:
            rd = r.get('race_date', '')
            sed_key = f"{ketto_num}_{rd}"
            sed = jrdb_sed_index.get(sed_key)
            if sed:
                sed_records.append(sed)

        if sed_records:
            # IDM値を抽出
            idm_vals = [s['idm'] for s in sed_records if s.get('idm') is not None]

            if idm_vals:
                result['jrdb_idm_last'] = float(idm_vals[-1])
                if len(idm_vals) >= 2:
                    result['jrdb_idm_avg3'] = round(statistics.mean(idm_vals[-3:]), 1)
                    result['jrdb_idm_max5'] = float(max(idm_vals))
                    result['jrdb_idm_trend'] = round(idm_vals[-1] - statistics.mean(idm_vals), 1)
                if len(idm_vals) >= 3:
                    result['jrdb_idm_std'] = round(statistics.stdev(idm_vals), 1)

            # 上がり指数
            agari_vals = [s['agari_idx'] for s in sed_records
                          if s.get('agari_idx') is not None]
            if agari_vals:
                result['jrdb_agari_idx_last'] = float(agari_vals[-1])
                if len(agari_vals) >= 2:
                    result['jrdb_agari_idx_avg3'] = round(statistics.mean(agari_vals[-3:]), 1)

            # テン指数
            ten_vals = [s['ten_idx'] for s in sed_records
                        if s.get('ten_idx') is not None]
            if ten_vals:
                result['jrdb_ten_idx_last'] = float(ten_vals[-1])
                if len(ten_vals) >= 2:
                    result['jrdb_ten_idx_avg3'] = round(statistics.mean(ten_vals[-3:]), 1)

            # 出遅・不利カウント
            deokure_count = sum(1 for s in sed_records if s.get('deokure_adj', 0) > 0)
            furi_count = sum(1 for s in sed_records if s.get('furi_adj', 0) > 0)
            result['jrdb_deokure_count5'] = deokure_count
            result['jrdb_furi_count5'] = furi_count

            # 上昇度コード平均
            joushou_vals = [s['joushou_code'] for s in sed_records
                            if s.get('joushou_code', 0) > 0]
            if joushou_vals:
                result['jrdb_joushou_mean'] = round(statistics.mean(joushou_vals), 2)

    # === D: 事前IDM・指数 (KYI) ===
    kyi_key = f"{ketto_num}_{race_date}"
    kyi = jrdb_kyi_index.get(kyi_key)

    if kyi:
        for field, feat_name in [
            ('pre_idm', 'jrdb_pre_idm'),
            ('sogo_idx', 'jrdb_sogo_idx'),
            ('training_idx', 'jrdb_training_idx'),
            ('stable_idx', 'jrdb_stable_idx'),
            ('jockey_idx', 'jrdb_jockey_idx'),
            ('info_idx', 'jrdb_info_idx'),
            ('gekisou_idx', 'jrdb_gekisou_idx'),
            ('start_idx', 'jrdb_start_idx'),
            ('deokure_rate', 'jrdb_deokure_rate'),
        ]:
            val = kyi.get(field)
            if val is not None:
                result[feat_name] = float(val)

    # === E: 乖離指標 ===
    # 過去IDM平均 vs 今回事前IDM
    if result['jrdb_idm_avg3'] > -1 and result['jrdb_pre_idm'] > -1:
        result['jrdb_idm_vs_pre'] = round(
            result['jrdb_idm_avg3'] - result['jrdb_pre_idm'], 1)

    # 成長指標: 直近IDM vs 全過去IDM平均
    if past and result['jrdb_idm_last'] > -1:
        all_sed = []
        for r in past:
            rd = r.get('race_date', '')
            sed_key = f"{ketto_num}_{rd}"
            sed = jrdb_sed_index.get(sed_key)
            if sed and sed.get('idm') is not None:
                all_sed.append(sed['idm'])
        if len(all_sed) >= 3:
            result['jrdb_idm_growth'] = round(
                result['jrdb_idm_last'] - statistics.mean(all_sed), 1)

    # === F: 不利補正内訳 + 馬場差 (SED) ===
    if past:
        last5 = past[-5:]
        sed_recs = []
        for r in last5:
            rd = r.get('race_date', '')
            sed_key = f"{ketto_num}_{rd}"
            sed = jrdb_sed_index.get(sed_key)
            if sed:
                sed_recs.append(sed)

        if sed_recs:
            last_sed = sed_recs[-1]
            # 前走の不利補正内訳
            result['jrdb_mae_furi_last'] = float(last_sed.get('mae_furi_adj', 0) or 0)
            result['jrdb_naka_furi_last'] = float(last_sed.get('naka_furi_adj', 0) or 0)
            result['jrdb_ato_furi_last'] = float(last_sed.get('ato_furi_adj', 0) or 0)
            result['jrdb_furi_total_last'] = (
                result['jrdb_mae_furi_last']
                + result['jrdb_naka_furi_last']
                + result['jrdb_ato_furi_last']
            )
            # 前走の馬場差補正
            result['jrdb_baba_sa_last'] = float(last_sed.get('baba_sa', 0) or 0)
            # 直近3走の馬場差平均
            baba_vals = [float(s.get('baba_sa', 0) or 0) for s in sed_recs[-3:]]
            if baba_vals:
                result['jrdb_baba_sa_avg3'] = round(
                    sum(baba_vals) / len(baba_vals), 1)

            # ペース適合度: 直近3走で馬ペースとレースペースが合ってた割合
            _PACE_MAP = {'H': 0, 'M': 1, 'S': 2}
            pace_matches = 0
            pace_total = 0
            for s in sed_recs[-3:]:
                hp = _PACE_MAP.get(s.get('horse_pace'))
                rp = _PACE_MAP.get(s.get('race_pace'))
                if hp is not None and rp is not None:
                    pace_total += 1
                    if abs(hp - rp) <= 1:  # 1段階以内のズレはOK
                        pace_matches += 1
            if pace_total > 0:
                result['jrdb_pace_match'] = round(pace_matches / pace_total, 2)

    # === G: 脚質・距離適性 (KYI) ===
    if kyi:
        kyakushitsu = kyi.get('kyakushitsu')
        if kyakushitsu is not None and kyakushitsu > 0:
            result['jrdb_kyakushitsu'] = int(kyakushitsu)
        dist_apt = kyi.get('distance_aptitude')
        if dist_apt is not None:
            result['jrdb_distance_apt'] = int(dist_apt)

    return result


# 全JRDB特徴量名リスト（experiment.pyで使用）
JRDB_FEATURE_COLS = [
    # A. 過去走IDM統計
    'jrdb_idm_last', 'jrdb_idm_avg3', 'jrdb_idm_max5',
    'jrdb_idm_trend', 'jrdb_idm_std',
    # B. テン・上がり指数
    'jrdb_agari_idx_last', 'jrdb_agari_idx_avg3',
    'jrdb_ten_idx_last', 'jrdb_ten_idx_avg3',
    # C. 補正項
    'jrdb_deokure_count5', 'jrdb_furi_count5', 'jrdb_joushou_mean',
    # D. 事前IDM・指数
    'jrdb_pre_idm', 'jrdb_sogo_idx', 'jrdb_training_idx',
    'jrdb_stable_idx', 'jrdb_jockey_idx', 'jrdb_info_idx',
    'jrdb_gekisou_idx', 'jrdb_start_idx', 'jrdb_deokure_rate',
    # E. 乖離指標
    'jrdb_idm_vs_pre', 'jrdb_idm_growth',
    # F. 不利補正内訳 + 馬場差
    'jrdb_mae_furi_last', 'jrdb_naka_furi_last', 'jrdb_ato_furi_last',
    'jrdb_furi_total_last', 'jrdb_baba_sa_last', 'jrdb_baba_sa_avg3',
    # G. ペース適性 + 脚質 + 距離適性
    'jrdb_pace_match', 'jrdb_kyakushitsu', 'jrdb_distance_apt',
]

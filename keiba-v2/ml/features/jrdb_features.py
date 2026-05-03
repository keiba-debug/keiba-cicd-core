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


def race_id_to_jrdb_key(race_id: str) -> str:
    """KeibaCICD race_id (16桁 YYYYMMDDJJKKNNRR) → JRDBレースキー (8桁 VVYYKHHR)

    JJ→VV(場コード), YY(年2桁), KK→K(回1桁), NN→H(日hex1桁), RR(R番号)
    """
    if len(race_id) < 16:
        return ''
    venue = race_id[8:10]
    year = race_id[2:4]
    kai = str(int(race_id[10:12]))
    nichi = format(int(race_id[12:14]), 'x')  # hex
    race_num = race_id[14:16]
    return f"{venue}{year}{kai}{nichi}{race_num}"


def compute_jrdb_features(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
    jrdb_sed_index: dict,
    jrdb_kyi_index: dict,
    jrdb_cyb_index: dict = None,
    jrdb_cha_index: dict = None,
    jrdb_kka_index: dict = None,
    jrdb_joa_index: dict = None,
    race_id: str = '',
    umaban: int = 0,
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
        'jrdb_pace_match': None,     # 馬のペース vs レースペース完全一致率 (0-1)
        'jrdb_pace_mismatch_avg': None,  # 馬-レース ペース絶対差の平均 (0=一致, 2=真逆)
        'jrdb_kyakushitsu': None,    # 脚質コード (1=逃げ,2=先行,3=差し,4=追込)
        'jrdb_distance_apt': None,   # 距離適性
        # H. 調教分析 (CYB)
        'jrdb_cyb_oikiri_idx': -1.0,       # 追切指数 (基準60)
        'jrdb_cyb_shiage_idx': -1.0,       # 仕上指数 (基準60)
        'jrdb_cyb_shiage_change': -1,      # 仕上変化 (1:++,2:+,3:不変,4:-)
        'jrdb_cyb_training_eval': -1,      # 調教評価 (1:良,2:可,3:悪)
        'jrdb_cyb_oikiri_prev': -1.0,      # 一週前追切指数
        # I. 本追切 (CHA)
        'jrdb_cha_oikiri_idx': -1.0,       # 本追切・追切指数
        'jrdb_cha_shimai_idx': -1.0,       # 本追切・終い指数
        'jrdb_cha_oikiri_type': -1,        # 追切種類 (1:馬なり,2:普通,3:一杯)
        # J. CID/LS情報 (JOA)
        'jrdb_cid': None,                  # CID (コンディションインデックス)
        'jrdb_cid_score': None,            # CID素点
        'jrdb_ls_idx': None,               # LS指数 (ロングショット)
        # L. CID時系列 (JOA過去走)
        'jrdb_cid_score_last': None,       # 前走CID素点
        'jrdb_cid_score_avg3': None,       # 直近3走CID素点平均
        'jrdb_cid_score_trend': None,      # 今回CID素点 - 前走CID素点 (正=調子上向き)
        'jrdb_cid_score_vs_avg': None,     # 今回CID素点 - 直近3走平均 (正=好調)
        'jrdb_ls_idx_last': None,          # 前走LS指数
        'jrdb_ls_idx_trend': None,         # 今回LS - 前走LS (正=穴指数上昇)
        # K. 産駒成績 (KKA)
        'jrdb_kka_total_runs': -1,         # JRDB成績 合計レース数
        'jrdb_kka_win_rate': None,         # JRDB成績 勝率
        'jrdb_kka_dam_rentai': -1,         # 母産駒最連対率(%)
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

            # ペース適合度: 直近3走で馬ペースとレースペースの一致度 (Session 119 修正)
            # 旧ロジックは「abs(hp - rp) <= 1」で73%が1.0に張り付き分散ゼロ → 死特徴量化
            # A: jrdb_pace_match を完全一致のみに厳格化
            # B: jrdb_pace_mismatch_avg 新規 — 平均絶対差 (0=完全一致, 2=真逆)
            _PACE_MAP = {'H': 0, 'M': 1, 'S': 2}
            pace_matches = 0
            pace_total = 0
            mismatch_sum = 0.0
            for s in sed_recs[-3:]:
                hp = _PACE_MAP.get(s.get('horse_pace'))
                rp = _PACE_MAP.get(s.get('race_pace'))
                if hp is not None and rp is not None:
                    pace_total += 1
                    if hp == rp:  # 厳格: 完全一致のみ
                        pace_matches += 1
                    mismatch_sum += abs(hp - rp)
            if pace_total > 0:
                result['jrdb_pace_match'] = round(pace_matches / pace_total, 2)
                result['jrdb_pace_mismatch_avg'] = round(mismatch_sum / pace_total, 2)

    # === G: 脚質・距離適性 (KYI) ===
    if kyi:
        kyakushitsu = kyi.get('kyakushitsu')
        if kyakushitsu is not None and kyakushitsu > 0:
            result['jrdb_kyakushitsu'] = int(kyakushitsu)
        dist_apt = kyi.get('distance_aptitude')
        if dist_apt is not None:
            result['jrdb_distance_apt'] = int(dist_apt)

    # === H: 調教分析 (CYB) ===
    jrdb_key = race_id_to_jrdb_key(race_id) if race_id else ''
    if jrdb_key and umaban > 0 and jrdb_cyb_index:
        cyb_lookup = f"{jrdb_key}_{umaban:02d}"
        cyb = jrdb_cyb_index.get(cyb_lookup)
        if cyb:
            oi = cyb.get('oikiri_idx', 0)
            if oi and oi > 0:
                result['jrdb_cyb_oikiri_idx'] = float(oi)
            si = cyb.get('shiage_idx', 0)
            if si and si > 0:
                result['jrdb_cyb_shiage_idx'] = float(si)
            sc = cyb.get('shiage_change', 0)
            if sc and sc > 0:
                result['jrdb_cyb_shiage_change'] = int(sc)
            te = cyb.get('training_eval', 0)
            if te and te > 0:
                result['jrdb_cyb_training_eval'] = int(te)
            op = cyb.get('oikiri_idx_prev_week', 0)
            if op and op > 0:
                result['jrdb_cyb_oikiri_prev'] = float(op)

    # === I: 本追切 (CHA) ===
    if jrdb_key and umaban > 0 and jrdb_cha_index:
        cha_lookup = f"{jrdb_key}_{umaban:02d}"
        cha = jrdb_cha_index.get(cha_lookup)
        if cha:
            oi = cha.get('oikiri_idx', 0)
            if oi and oi > 0:
                result['jrdb_cha_oikiri_idx'] = float(oi)
            si = cha.get('shimai_e_idx', 0)
            if si and si > 0:
                result['jrdb_cha_shimai_idx'] = float(si)
            ot = cha.get('oikiri_type', 0)
            if ot and ot > 0:
                result['jrdb_cha_oikiri_type'] = int(ot)

    # === J: CID/LS (JOA) ===
    if jrdb_key and umaban > 0 and jrdb_joa_index:
        joa_lookup = f"{jrdb_key}_{umaban:02d}"
        joa = jrdb_joa_index.get(joa_lookup)
        if joa:
            cid = joa.get('cid')
            if cid is not None:
                result['jrdb_cid'] = float(cid)
            cs = joa.get('cid_score')
            if cs is not None:
                result['jrdb_cid_score'] = float(cs)
            ls = joa.get('ls_idx')
            if ls is not None:
                result['jrdb_ls_idx'] = float(ls)

    # === L: CID/LS 時系列 (JOA過去走) ===
    if jrdb_joa_index and past:
        past_cid_scores = []
        past_ls_idxs = []
        for r in past[-5:]:
            past_rid = r.get('race_id', '')
            past_uma = r.get('umaban', 0)
            if past_rid and past_uma:
                past_jk = race_id_to_jrdb_key(past_rid)
                if past_jk:
                    past_joa = jrdb_joa_index.get(f"{past_jk}_{past_uma:02d}")
                    if past_joa:
                        cs = past_joa.get('cid_score')
                        if cs is not None:
                            past_cid_scores.append(float(cs))
                        ls = past_joa.get('ls_idx')
                        if ls is not None:
                            past_ls_idxs.append(float(ls))

        if past_cid_scores:
            result['jrdb_cid_score_last'] = past_cid_scores[-1]
            if len(past_cid_scores) >= 2:
                result['jrdb_cid_score_avg3'] = round(
                    statistics.mean(past_cid_scores[-3:]), 2)
            # トレンド: 今回 vs 前走
            if result['jrdb_cid_score'] is not None:
                result['jrdb_cid_score_trend'] = round(
                    result['jrdb_cid_score'] - past_cid_scores[-1], 2)
                if len(past_cid_scores) >= 2:
                    result['jrdb_cid_score_vs_avg'] = round(
                        result['jrdb_cid_score'] - statistics.mean(past_cid_scores[-3:]), 2)

        if past_ls_idxs:
            result['jrdb_ls_idx_last'] = past_ls_idxs[-1]
            if result['jrdb_ls_idx'] is not None:
                result['jrdb_ls_idx_trend'] = round(
                    result['jrdb_ls_idx'] - past_ls_idxs[-1], 2)

    # === K: 産駒成績 (KKA) ===
    if jrdb_key and umaban > 0 and jrdb_kka_index:
        kka_lookup = f"{jrdb_key}_{umaban:02d}"
        kka = jrdb_kka_index.get(kka_lookup)
        if kka:
            jr = kka.get('jrdb_results', [0, 0, 0, 0])
            total = sum(jr)
            if total > 0:
                result['jrdb_kka_total_runs'] = total
                result['jrdb_kka_win_rate'] = round(jr[0] / total, 3)
            dr = kka.get('dam_best_rentai', 0)
            if dr and dr > 0:
                result['jrdb_kka_dam_rentai'] = int(dr)

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
    'jrdb_pace_match', 'jrdb_pace_mismatch_avg', 'jrdb_kyakushitsu', 'jrdb_distance_apt',
    # H. 調教分析 (CYB)
    'jrdb_cyb_oikiri_idx', 'jrdb_cyb_shiage_idx', 'jrdb_cyb_shiage_change',
    'jrdb_cyb_training_eval', 'jrdb_cyb_oikiri_prev',
    # I. 本追切 (CHA)
    'jrdb_cha_oikiri_idx', 'jrdb_cha_shimai_idx', 'jrdb_cha_oikiri_type',
    # J. CID/LS (JOA)
    'jrdb_cid', 'jrdb_cid_score', 'jrdb_ls_idx',
    # L. CID/LS 時系列 (JOA過去走)
    'jrdb_cid_score_last', 'jrdb_cid_score_avg3',
    'jrdb_cid_score_trend', 'jrdb_cid_score_vs_avg',
    'jrdb_ls_idx_last', 'jrdb_ls_idx_trend',
    # K. 産駒成績 (KKA)
    'jrdb_kka_total_runs', 'jrdb_kka_win_rate', 'jrdb_kka_dam_rentai',
]

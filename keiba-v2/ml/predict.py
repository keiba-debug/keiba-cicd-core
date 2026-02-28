#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
リアルタイム予測スクリプト (v3.4モデル)

JRA-VANレースJSON + keibabook拡張JSON + mykeibadb事前オッズ → predictions_live.json

v3.4: mykeibadb連携 - レース前最新オッズを自動取得
      DB接続不可時はJSONオッズにフォールバック

Usage:
    python -m ml.predict [--date 2026-02-08] [--race-id 2026020806010101]
    python -m ml.predict --latest   # 最新の開催日
    python -m ml.predict --no-db    # DBオッズ未使用
    python -m ml.predict --predict-only  # ML予測のみ（VB/買い目スキップ）
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.features.base_features import extract_base_features
from ml.features.baba_features import load_baba_index, get_baba_features
from ml.features.past_features import compute_past_features
from ml.features.trainer_features import get_trainer_features, build_trainer_index
from ml.features.jockey_features import get_jockey_features, build_jockey_index
from ml.features.running_style_features import compute_running_style_features
from ml.features.rotation_features import compute_rotation_features
from ml.features.pace_features import compute_pace_features
from ml.features.training_features import compute_training_features
from ml.features.speed_features import compute_speed_features
from ml.features.comment_features import compute_comment_features
from ml.features.slow_start_features import compute_slow_start_features
from ml.bet_engine import (
    PRESETS, generate_recommendations,
    recommendations_to_dict, recommendations_summary,
    load_grade_offsets, get_grade_key,
    VB_FLOOR_MIN_WIN_EV, VB_FLOOR_MIN_ARD,
    VB_FLOOR_ARD_VB_MIN_ARD, VB_FLOOR_ARD_VB_MIN_ODDS,
)

# === Value Bet閾値 ===
VALUE_BET_MIN_GAP = 3  # experiment_v3.pyと統一


def load_model_and_meta(model_version: Optional[str] = None):
    """学習済みモデルとメタ情報をロード

    Args:
        model_version: バージョン指定（例: "5.0", "3.5"）。
                       None=最新のliveモデル、"latest"=同上。
                       指定時は versions/v{version}/ からロード。
    """
    import lightgbm as lgb

    ml_dir = config.ml_dir()

    # バージョン指定時はアーカイブからロード
    if model_version and model_version != "latest":
        ver_dir = ml_dir / "versions" / f"v{model_version}"
        if not ver_dir.exists():
            available = list_model_versions()
            ver_list = ", ".join(v['version'] for v in available)
            raise FileNotFoundError(
                f"モデルバージョン v{model_version} が見つかりません。\n"
                f"利用可能: {ver_list}"
            )
        load_dir = ver_dir
        print(f"[Model] Loading archived model v{model_version}")
    else:
        load_dir = ml_dir
        print(f"[Model] Loading latest (live) model")

    model_a_path = load_dir / "model_a.txt"
    model_b_path = load_dir / "model_b.txt"
    model_w_path = load_dir / "model_w.txt"
    model_wv_path = load_dir / "model_wv.txt"
    meta_path = load_dir / "model_meta.json"

    # Place モデル (A/B) は必須
    missing = [p for p in [model_a_path, model_b_path, meta_path] if not p.exists()]
    if missing:
        names = ", ".join(p.name for p in missing)
        raise FileNotFoundError(
            f"モデルファイルが見つかりません: {names} (in {load_dir})\n"
            "先に python -m ml.experiment を実行してください"
        )

    model_a = lgb.Booster(model_file=str(model_a_path))
    model_b = lgb.Booster(model_file=str(model_b_path))

    # Win モデル (W/WV) はオプション（後方互換）
    model_w = None
    model_wv = None
    if model_w_path.exists() and model_wv_path.exists():
        model_w = lgb.Booster(model_file=str(model_w_path))
        model_wv = lgb.Booster(model_file=str(model_wv_path))
        print(f"[Model] Win models loaded: model_w.txt, model_wv.txt")
    else:
        print(f"[Model] Win models not found - running without win predictions")

    # IsotonicRegressionキャリブレーター（オプション）
    # EV計算にはcalibrated確率を使用、ランキングはraw正規化（順序不変のため）
    calibrators = None
    cal_path = load_dir / "calibrators.pkl"
    if cal_path.exists():
        import pickle
        with open(cal_path, 'rb') as f:
            calibrators = pickle.load(f)
        print(f"[Model] Calibrators loaded: {list(calibrators.keys())}")

    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)

    # calibrator整合性チェック
    if meta.get('has_calibrators') and calibrators is None:
        print("[WARN] model_meta says calibrators exist but calibrators.pkl not found — using raw probabilities for EV")

    # 回帰モデル (着差予測, オプション)
    model_reg_b = None
    reg_path = load_dir / "model_reg_b.txt"
    if reg_path.exists():
        model_reg_b = lgb.Booster(model_file=str(reg_path))
        print(f"[Model] Regression model loaded: model_reg_b.txt")
    else:
        print(f"[Model] Regression model not found - running without margin predictions")

    ver_label = meta.get('version', '?')
    feat_a = len(meta.get('features_all', []))
    feat_v = len(meta.get('features_value', []))
    print(f"[Model] Version: {ver_label}, Features: A={feat_a}, V={feat_v}")

    return model_a, model_b, model_w, model_wv, meta, calibrators, model_reg_b


def load_obstacle_model():
    """障害レース用モデルをロード（存在しない場合はNone）

    Returns:
        (model, meta, calibrator) or (None, None, None)
    """
    import lightgbm as lgb

    ml_dir = config.ml_dir()
    model_path = ml_dir / "model_obstacle.txt"
    meta_path = ml_dir / "model_obstacle_meta.json"

    if not model_path.exists() or not meta_path.exists():
        return None, None, None

    model = lgb.Booster(model_file=str(model_path))
    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)

    calibrator = None
    cal_path = ml_dir / "calibrator_obstacle.pkl"
    if cal_path.exists():
        import pickle
        with open(cal_path, 'rb') as f:
            calibrator = pickle.load(f)

    ver = meta.get('version', '?')
    feat_count = meta.get('feature_count', '?')
    print(f"[Model] Obstacle model loaded: v{ver}, {feat_count} features")
    return model, meta, calibrator


def predict_obstacle_race(
    race: dict,
    model_obstacle,
    obstacle_meta: dict,
    obstacle_calibrator,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    db_odds: Optional[Dict[int, dict]] = None,
    kb_ext_index: Optional[dict] = None,
    race_level_index: Optional[dict] = None,
    pedigree_index: Optional[dict] = None,
    sire_stats_index: Optional[dict] = None,
) -> dict:
    """障害レースの予測を実行（簡易版: モデル1本、VB/bet_engine不要）"""
    from ml.features.pedigree_features import get_pedigree_features, build_sire_index

    features = obstacle_meta.get('features', [])
    _sire_idx, _dam_idx, _bms_idx = build_sire_index(sire_stats_index or {})

    race_date = race['date']
    race_id = race['race_id']
    venue_code = race['venue_code']
    venue_name = race.get('venue_name', '')
    track_type = race.get('track_type', 'obstacle')
    distance = race.get('distance', 0)
    entry_count = race.get('num_runners', 0)
    current_grade = race.get('grade', '')
    current_is_handicap = race.get('is_handicap', False)
    current_is_female_only = race.get('is_female_only', False)
    current_month = int(race_date.split('-')[1]) if len(race_date.split('-')) >= 2 else 0

    kb_ext = (kb_ext_index or {}).get(race_id)
    kb_entries = kb_ext.get('entries', {}) if kb_ext else {}

    predictions = []
    feature_rows = []

    for entry in race.get('entries', []):
        umaban = entry.get('umaban', 0)
        ketto_num = entry.get('ketto_num', '')

        feat = extract_base_features(entry, race)

        if db_odds and umaban in db_odds:
            feat['odds'] = db_odds[umaban]['odds']
            ninki = db_odds[umaban].get('ninki')
            if ninki is not None:
                feat['popularity'] = ninki

        past = compute_past_features(
            ketto_num=ketto_num, race_date=race_date,
            venue_code=venue_code, track_type=track_type,
            distance=distance, entry_count=entry_count,
            history_cache=history_cache, race_level_index=race_level_index,
        )
        feat.update(past)

        tc = entry.get('trainer_code', '')
        feat.update(get_trainer_features(tc, venue_code, trainer_index))

        jc = entry.get('jockey_code', '')
        feat.update(get_jockey_features(jc, venue_code, jockey_index))

        rs_feat = compute_running_style_features(
            ketto_num=ketto_num, race_date=race_date,
            entry_count=entry_count, history_cache=history_cache,
        )
        feat.update(rs_feat)

        rot_feat = compute_rotation_features(
            ketto_num=ketto_num, race_date=race_date,
            futan=entry.get('futan', 0.0), horse_weight=entry.get('horse_weight', 0),
            popularity=entry.get('popularity', 0), jockey_code=entry.get('jockey_code', ''),
            history_cache=history_cache, current_grade=current_grade,
            current_venue=venue_name, current_distance=distance,
            current_track_type=track_type, current_month=current_month,
            current_is_handicap=current_is_handicap,
            current_is_female_only=current_is_female_only,
        )
        feat.update(rot_feat)

        speed_feat = compute_speed_features(umaban=str(umaban), kb_ext=kb_ext)
        feat.update(speed_feat)

        ped_feat = get_pedigree_features(
            ketto_num, pedigree_index or {}, _sire_idx, _dam_idx, _bms_idx,
        )
        feat.update(ped_feat)

        kb_e = kb_entries.get(str(umaban))

        predictions.append({
            'umaban': umaban,
            'ketto_num': ketto_num,
            'horse_name': entry.get('horse_name', ''),
            'odds': feat.get('odds', 0),
            'popularity': feat.get('popularity', 0),
            'features': feat,
            'kb_mark': kb_e.get('honshi_mark', '') if kb_e else '',
        })

    if not predictions:
        return {
            'race_id': race_id, 'date': race_date,
            'venue_name': venue_name, 'race_number': race.get('race_number', 0),
            'distance': distance, 'track_type': 'obstacle',
            'num_runners': 0, 'grade': current_grade,
            'age_class': '', 'is_handicap': current_is_handicap,
            'is_female_only': current_is_female_only, 'entries': [],
        }

    # 特徴量行列を構築
    def _to_float(val):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.nan
        try:
            return float(val)
        except (TypeError, ValueError):
            return np.nan

    for p in predictions:
        row = [_to_float(p['features'].get(f, np.nan)) for f in features]
        feature_rows.append(row)

    arr = np.array(feature_rows, dtype=np.float64)
    pred_raw = model_obstacle.predict(arr)

    # キャリブレーション
    pred_cal = pred_raw
    if obstacle_calibrator is not None:
        pred_cal = obstacle_calibrator.predict(pred_raw)

    # レース内正規化
    sum_pred = pred_raw.sum()
    pred_norm = pred_raw / sum_pred if sum_pred > 0 else pred_raw

    # ランク計算
    rank_dict = {i: r for r, i in enumerate(np.argsort(-pred_norm), 1)}

    result_entries = []
    for i, p in enumerate(predictions):
        rank = rank_dict[i]
        result_entries.append({
            'umaban': p['umaban'],
            'horse_name': p['horse_name'],
            'odds': p['odds'],
            'popularity': p['popularity'],
            'pred_proba_a': round(float(pred_norm[i]), 4),
            'pred_proba_v': round(float(pred_norm[i]), 4),
            'pred_proba_v_raw': round(float(pred_raw[i]), 6),
            'rank_a': int(rank),
            'rank_v': int(rank),
            'odds_rank': 0,
            'vb_gap': 0,
            'pred_proba_w': None, 'pred_proba_wv': None,
            'pred_proba_wv_cal': None,
            'rank_w': None, 'rank_wv': None,
            'win_vb_gap': 0,
            'place_odds_min': None, 'place_odds_max': None,
            'win_ev': None, 'place_ev': None,
            'predicted_margin': None, 'ar_deviation': None,
            'is_value_bet': False,
            'kb_mark': p['kb_mark'],
            'kb_mark_point': 0, 'kb_training_arrow': '',
            'kb_rating': None, 'kb_comment': '',
            'kb_ai_index': None,
            'koukaku_rote_count': 0,
            'is_koukaku_venue': 0, 'is_koukaku_female': 0,
            'is_koukaku_season': 0, 'is_koukaku_distance': 0,
            'is_koukaku_turf_to_dirt': 0, 'is_koukaku_handicap': 0,
            'comment_stable_condition': 0, 'comment_stable_confidence': 0,
            'comment_stable_mark': 0, 'comment_memo_condition': 0,
            'comment_memo_trouble_score': 0,
            'comment_has_stable': 0, 'comment_has_interview': 0,
        })

    result_entries.sort(key=lambda x: -x['pred_proba_v'])

    return {
        'race_id': race_id,
        'date': race_date,
        'venue_name': venue_name,
        'race_number': race.get('race_number', 0),
        'distance': distance,
        'track_type': 'obstacle',
        'num_runners': entry_count,
        'grade': current_grade,
        'age_class': '',
        'is_handicap': current_is_handicap,
        'is_female_only': current_is_female_only,
        'entries': result_entries,
    }


def list_model_versions() -> list:
    """利用可能なモデルバージョン一覧を返す（新しい順）

    Returns:
        list of dict: version, archived_at, has_win_model, feature_count_all, feature_count_value
    """
    from core.versioning import get_versions

    ml_dir = config.ml_dir()
    versions = []

    # アーカイブされたバージョン
    for entry in get_versions(ml_dir):
        ver = entry.get('version', '?')
        ver_dir = ml_dir / "versions" / f"v{ver}"
        meta_path = ver_dir / "model_meta.json"

        info = {
            'version': ver,
            'archived_at': entry.get('archived_at', ''),
            'has_win_model': (ver_dir / "model_w.txt").exists(),
            'is_live': False,
        }

        if meta_path.exists():
            with open(meta_path, encoding='utf-8') as f:
                meta = json.load(f)
            info['feature_count_all'] = len(meta.get('features_all', []))
            info['feature_count_value'] = len(meta.get('features_value', []))
            info['created_at'] = meta.get('created_at', '')

        versions.append(info)

    # 現在のliveモデル
    live_meta_path = ml_dir / "model_meta.json"
    if live_meta_path.exists():
        with open(live_meta_path, encoding='utf-8') as f:
            meta = json.load(f)
        versions.insert(0, {
            'version': meta.get('version', '?') + ' (live)',
            'created_at': meta.get('created_at', ''),
            'has_win_model': (ml_dir / "model_w.txt").exists(),
            'feature_count_all': len(meta.get('features_all', [])),
            'feature_count_value': len(meta.get('features_value', [])),
            'is_live': True,
        })

    return versions


def load_master_data():
    """マスタデータをロード"""
    # Horse history cache
    hh_path = config.ml_dir() / "horse_history_cache.json"
    with open(hh_path, encoding='utf-8') as f:
        history_cache = json.load(f)

    # Trainers
    tr_path = config.masters_dir() / "trainers.json"
    with open(tr_path, encoding='utf-8') as f:
        trainers_list = json.load(f)
    trainer_index = build_trainer_index(trainers_list)

    # Jockeys
    jk_path = config.masters_dir() / "jockeys.json"
    with open(jk_path, encoding='utf-8') as f:
        jockeys_list = json.load(f)
    jockey_index = build_jockey_index(jockeys_list)

    # Pace index + kb_ext index
    from ml.experiment import build_pace_index, build_kb_ext_index
    di_path = config.indexes_dir() / "race_date_index.json"
    with open(di_path, encoding='utf-8') as f:
        date_index = json.load(f)
    pace_index = build_pace_index(date_index)
    kb_ext_index = build_kb_ext_index(date_index)

    # Race level index (v5.6)
    rl_path = config.indexes_dir() / "race_level_index.json"
    race_level_index = {}
    if rl_path.exists():
        with open(rl_path, encoding='utf-8') as f:
            race_level_index = json.load(f)
        print(f"  Race level index: {len(race_level_index):,} races")

    # Pedigree index + sire stats (v5.8)
    ped_path = config.indexes_dir() / "pedigree_index.json"
    pedigree_index = {}
    if ped_path.exists():
        with open(ped_path, encoding='utf-8') as f:
            pedigree_index = json.load(f)
        print(f"  Pedigree index: {len(pedigree_index):,} horses")

    sire_stats_path = config.indexes_dir() / "sire_stats_index.json"
    sire_stats_index = {}
    if sire_stats_path.exists():
        with open(sire_stats_path, encoding='utf-8') as f:
            sire_stats_index = json.load(f)
        sire_count = len(sire_stats_index.get('sire', {}))
        dam_count = len(sire_stats_index.get('dam', {}))
        bms_count = len(sire_stats_index.get('bms', {}))
        print(f"  Sire stats: {sire_count:,} sires, {dam_count:,} dams, {bms_count:,} BMS")

    # Baba index (v5.41): cushion + moisture
    baba_index = load_baba_index()
    print(f"  Baba index: {len(baba_index):,} races")

    return (history_cache, trainer_index, jockey_index, pace_index,
            kb_ext_index, race_level_index, pedigree_index, sire_stats_index,
            baba_index)


def load_keibabook_ext(race_id: str, date: str) -> Optional[dict]:
    """keibabook拡張JSONをロード（存在しなければNone）"""
    date_parts = date.split('-')
    kb_path = (config.keibabook_dir() / date_parts[0] / date_parts[1] /
               date_parts[2] / f"kb_ext_{race_id}.json")
    if kb_path.exists():
        with open(kb_path, encoding='utf-8') as f:
            return json.load(f)
    return None


def get_keibabook_features(kb_entry: Optional[dict]) -> dict:
    """keibabook拡張データからML特徴量を抽出"""
    result = {
        'rating': -1,
        'rating_deviation': -1,
        'mark_point': 0,
        'aggregate_mark_point': 0,
        'ai_index': -1,
        'training_arrow': 0,
    }
    if kb_entry is None:
        return result

    rating = kb_entry.get('rating')
    if rating is not None:
        result['rating'] = rating

    result['mark_point'] = kb_entry.get('mark_point', 0)
    result['aggregate_mark_point'] = kb_entry.get('aggregate_mark_point', 0)

    ai = kb_entry.get('ai_index')
    if ai is not None:
        result['ai_index'] = ai

    result['training_arrow'] = kb_entry.get('training_arrow_value', 0)

    return result


# TRACK_CODE → track_type マッピング（JRA-VAN仕様）
_TRACK_CODE_MAP = {
    '10': 'turf', '11': 'turf', '12': 'turf', '13': 'turf', '14': 'turf',
    '15': 'turf', '16': 'turf', '17': 'dirt', '18': 'dirt', '19': 'dirt',
    '20': 'dirt', '21': 'dirt', '22': 'dirt', '23': 'dirt',
    '24': 'turf', '25': 'turf', '26': 'turf', '27': 'turf', '28': 'turf',
    '29': 'dirt',
    '51': 'obstacle', '52': 'obstacle', '53': 'obstacle', '54': 'obstacle',
    '55': 'obstacle', '56': 'obstacle', '57': 'obstacle', '58': 'obstacle',
    '59': 'obstacle',
}


def _fetch_race_shosai_from_db(race_id: str) -> Optional[dict]:
    """DBのRACE_SHOSAIからtrack_type/distance/gradeを取得

    GRADE_CODE + KYOSO_JOKEN_CODEから全クラスを正しく判定。
    年齢クラス（2歳/3歳/古馬）も返す。
    """
    try:
        from core.db import get_connection
        from core.constants import GRADE_CODES, JOKEN_CLASS_MAP
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT KYORI, TRACK_CODE, KYOSOMEI_HONDAI, GRADE_CODE, '
                'KYOSO_JOKEN_CODE_2SAI, KYOSO_JOKEN_CODE_3SAI, '
                'KYOSO_JOKEN_CODE_4SAI, KYOSO_JOKEN_CODE_5SAI_IJO, '
                'KYOSO_JOKEN_CODE_SAIJAKUNEN '
                'FROM RACE_SHOSAI WHERE RACE_CODE = %s',
                (race_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            kyori, track_code, race_name = row[0], row[1], row[2]
            grade_code = (row[3] or '').strip()
            j2sai = (row[4] or '').strip()
            j3sai = (row[5] or '').strip()
            j4sai = (row[6] or '').strip()
            j5sai = (row[7] or '').strip()
            j_min = (row[8] or '').strip()

            track_type = _TRACK_CODE_MAP.get(track_code.strip(), '')
            distance = int(kyori.strip()) if kyori and kyori.strip().isdigit() else 0

            # grade判定: GRADE_CODE優先、空ならJOKENで条件クラス判定
            grade = GRADE_CODES.get(grade_code, '')
            if not grade and j_min:
                grade = JOKEN_CLASS_MAP.get(j_min, '')

            # 年齢クラス判定
            age_class = ''
            if j2sai != '000' and j3sai == '000':
                age_class = '2歳'
            elif j3sai != '000' and j4sai == '000':
                age_class = '3歳'
            elif j4sai != '000' or j5sai != '000':
                age_class = '古馬'

            return {
                'track_type': track_type,
                'distance': distance,
                'race_name': race_name.strip() if race_name else '',
                'grade': grade,
                'age_class': age_class,
            }
    except Exception:
        return None


def predict_race(
    race: dict,
    kb_ext: Optional[dict],
    model_a, model_b,
    meta: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    db_odds: Optional[Dict[int, dict]] = None,
    training_summary_day: Optional[dict] = None,
    model_w=None,
    model_wv=None,
    db_place_odds: Optional[Dict[int, dict]] = None,
    kb_ext_index: Optional[dict] = None,
    calibrators: Optional[dict] = None,
    model_reg_b=None,
    grade_offsets: Optional[Dict[str, float]] = None,
    race_level_index: Optional[dict] = None,
    pedigree_index: Optional[dict] = None,
    sire_stats_index: Optional[dict] = None,
    baba_index: Optional[dict] = None,
) -> dict:
    """1レースの予測を実行

    Args:
        db_odds: mykeibadbから取得した事前単勝オッズ {umaban: {'odds': float, 'ninki': int}}
        training_summary_day: CK_DATA調教サマリ {ketto_num: summary} (当日分)
        model_w: Win精度モデル (Optional)
        model_wv: Winバリューモデル (Optional)
        db_place_odds: mykeibadb複勝オッズ {umaban: {'odds_low': float, 'odds_high': float}}
        calibrators: IsotonicRegressionキャリブレーター辞書 (Optional)
        model_reg_b: 着差回帰モデル (Optional)
        pedigree_index: 血統インデックス {ketto_num: {sire, dam, bms}} (Optional)
        sire_stats_index: 種牡馬/母馬/母父統計 {sire: {...}, dam: {...}, bms: {...}} (Optional)
    """
    from ml.features.pedigree_features import get_pedigree_features, build_sire_index

    features_all = meta['features_all']
    features_value = meta['features_value']

    # Sire/Dam/BMS index (build once per predict_race call)
    _sire_idx, _dam_idx, _bms_idx = build_sire_index(sire_stats_index or {})

    race_date = race['date']
    race_id = race['race_id']
    venue_code = race['venue_code']
    venue_name = race.get('venue_name', '')
    track_type = race.get('track_type', '')
    distance = race.get('distance', 0)
    entry_count = race.get('num_runners', 0)
    current_grade = race.get('grade', '')
    current_is_handicap = race.get('is_handicap', False)
    current_is_female_only = race.get('is_female_only', False)
    current_age_class = ''

    # DB補完: track_type/distance/gradeが不足している場合
    if not track_type or distance == 0 or not current_grade:
        _db_race = _fetch_race_shosai_from_db(race_id)
        if _db_race:
            # DB補完で障害レースと判明した場合はフラグ付きで返す（main()で障害モデルにリダイレクト）
            if _db_race.get('track_type') == 'obstacle':
                race['track_type'] = 'obstacle'
                race['distance'] = _db_race.get('distance', 0)
                race['race_name'] = _db_race.get('race_name', '')
                return {
                    'race_id': race['race_id'], 'date': race_date,
                    'venue_name': venue_name, 'race_number': race.get('race_number', 0),
                    'distance': _db_race.get('distance', 0), 'track_type': 'obstacle',
                    'num_runners': len(race.get('entries', [])),
                    'race_name': _db_race.get('race_name', ''),
                    'grade': '', 'age_class': '', 'is_handicap': False,
                    'is_female_only': False, 'entries': [],
                    '_needs_obstacle_model': True,
                }
            if not track_type:
                track_type = _db_race.get('track_type', '')
            if distance == 0:
                distance = _db_race.get('distance', 0)
            if not current_grade:
                current_grade = _db_race.get('grade', '')
            current_age_class = _db_race.get('age_class', '')
            if race.get('race_name', '') == '':
                race['race_name'] = _db_race.get('race_name', '')

    # age_class未取得の場合、entries[]のageから推定
    if not current_age_class:
        ages = [e.get('age', 0) for e in race.get('entries', []) if e.get('age', 0) > 0]
        if ages:
            min_age, max_age = min(ages), max(ages)
            if max_age == 2:
                current_age_class = '2歳'
            elif min_age <= 3 and max_age == 3:
                current_age_class = '3歳'
            else:
                current_age_class = '古馬'
    current_month = int(race_date.split('-')[1]) if len(race_date.split('-')) >= 2 else 0

    kb_entries = kb_ext.get('entries', {}) if kb_ext else {}

    predictions = []
    feature_rows_a = []
    feature_rows_v = []

    for entry in race.get('entries', []):
        umaban = entry.get('umaban', 0)
        ketto_num = entry.get('ketto_num', '')

        # 基本特徴量
        feat = extract_base_features(entry, race)

        # DB事前オッズで上書き
        if db_odds and umaban in db_odds:
            feat['odds'] = db_odds[umaban]['odds']
            ninki = db_odds[umaban].get('ninki')
            if ninki is not None:
                feat['popularity'] = ninki

        # 過去走特徴量
        past = compute_past_features(
            ketto_num=ketto_num,
            race_date=race_date,
            venue_code=venue_code,
            track_type=track_type,
            distance=distance,
            entry_count=entry_count,
            history_cache=history_cache,
            race_level_index=race_level_index,
        )
        feat.update(past)

        # 調教師特徴量
        tc = entry.get('trainer_code', '')
        trainer_feat = get_trainer_features(tc, venue_code, trainer_index)
        feat.update(trainer_feat)

        # 騎手特徴量
        jc = entry.get('jockey_code', '')
        jockey_feat = get_jockey_features(jc, venue_code, jockey_index)
        feat.update(jockey_feat)

        # 脚質特徴量 (v3.1)
        rs_feat = compute_running_style_features(
            ketto_num=ketto_num,
            race_date=race_date,
            entry_count=entry_count,
            history_cache=history_cache,
        )
        feat.update(rs_feat)

        # ローテ・コンディション特徴量 (v3.1 + v5.1 降格ローテ)
        rot_feat = compute_rotation_features(
            ketto_num=ketto_num,
            race_date=race_date,
            futan=entry.get('futan', 0.0),
            horse_weight=entry.get('horse_weight', 0),
            popularity=entry.get('popularity', 0),
            jockey_code=entry.get('jockey_code', ''),
            history_cache=history_cache,
            current_grade=current_grade,
            current_venue=venue_name,
            current_distance=distance,
            current_track_type=track_type,
            current_month=current_month,
            current_is_handicap=current_is_handicap,
            current_is_female_only=current_is_female_only,
        )
        feat.update(rot_feat)

        # ペース特徴量 (v3.1)
        pace_feat = compute_pace_features(
            ketto_num=ketto_num,
            race_date=race_date,
            days_since_last_race=past.get('days_since_last_race', -1),
            history_cache=history_cache,
            pace_index=pace_index,
        )
        feat.update(pace_feat)

        # 調教特徴量 (v3.3 + v4.1 CK_DATA)
        kb_e = kb_entries.get(str(umaban))
        ck_training = (training_summary_day or {}).get(ketto_num) if ketto_num else None
        train_feat = compute_training_features(
            umaban=str(umaban),
            kb_ext=kb_ext,
            ck_training=ck_training,
        )
        feat.update(train_feat)

        # スピード指数特徴量 (v3.5)
        speed_feat = compute_speed_features(
            umaban=str(umaban),
            kb_ext=kb_ext,
        )
        feat.update(speed_feat)

        # コメントNLP特徴量 (v5.3)
        comment_feat = compute_comment_features(
            umaban=str(umaban),
            kb_ext=kb_ext,
        )
        feat.update(comment_feat)

        # 出遅れ特徴量 (v5.4)
        slow_feat = compute_slow_start_features(
            ketto_num=ketto_num,
            race_date=race_date,
            history_cache=history_cache,
            kb_ext_index=kb_ext_index or {},
        )
        feat.update(slow_feat)

        # 血統特徴量 (v5.8): 事前計算の集計統計量
        ped_feat = get_pedigree_features(ketto_num, pedigree_index or {}, _sire_idx, _dam_idx, _bms_idx)
        feat.update(ped_feat)

        # 馬場特徴量 (v5.41)
        baba_feat = get_baba_features(race_id, track_type, baba_index or {})
        feat.update(baba_feat)

        # odds_rank（レース内順位）は全馬のoddsが揃ってから計算
        feat['odds_rank'] = np.nan  # placeholder — real oddsがあればランク化される

        # keibabook拡張（あれば）
        kb_feat = get_keibabook_features(kb_e)

        # keibabookのratingをフィーチャに (もし特徴量リストに含まれていれば)
        # ※v3のfeature_colsにはrating系は含まれていないが将来対応用
        feat.update({k: v for k, v in kb_feat.items() if k not in feat})

        predictions.append({
            'umaban': umaban,
            'ketto_num': ketto_num,
            'horse_name': entry.get('horse_name', ''),
            'odds': feat.get('odds', 0),           # DB更新後の値を使用
            'popularity': feat.get('popularity', 0), # DB更新後の値を使用
            'features': feat,
            # kb拡張情報（表示用）
            'kb_mark': kb_e.get('honshi_mark', '') if kb_e else '',
            'kb_mark_point': kb_e.get('mark_point', 0) if kb_e else 0,
            'kb_training_arrow': kb_e.get('training_arrow', '') if kb_e else '',
            'kb_rating': kb_e.get('rating') if kb_e else None,
            'kb_comment': kb_e.get('short_comment', '') if kb_e else '',
        })

    # odds_rank計算（有効なオッズがある場合のみ）
    has_real_odds = any(p['features'].get('odds', 0) > 0 for p in predictions)
    if has_real_odds:
        odds_list = [(i, p['features'].get('odds', 0)) for i, p in enumerate(predictions)]
        odds_list.sort(key=lambda x: (x[1] if x[1] > 0 else 9999))
        for rank, (idx, _) in enumerate(odds_list, 1):
            predictions[idx]['features']['odds_rank'] = rank
    # else: odds_rank = np.nan のまま → LightGBMのNaN処理に委ねる

    # 特徴量行列を構築（NaN処理はLightGBMネイティブに委ねる）
    # None/非数値はnp.nanに変換（comment_features等がNoneを返す場合のnp.isnan対応）
    def _to_float(val):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.nan
        try:
            return float(val)
        except (TypeError, ValueError):
            return np.nan

    for p in predictions:
        row_a = [_to_float(p['features'].get(f, np.nan)) for f in features_all]
        row_v = [_to_float(p['features'].get(f, np.nan)) for f in features_value]
        feature_rows_a.append(row_a)
        feature_rows_v.append(row_v)

    arr_a = np.array(feature_rows_a, dtype=np.float64)
    arr_v = np.array(feature_rows_v, dtype=np.float64)

    # === 特徴量NaN検証: 全値NaNの特徴量があれば警告 ===
    nan_cols_a = [f for j, f in enumerate(features_all)
                  if np.all(np.isnan(arr_a[:, j]))]
    nan_cols_v = [f for j, f in enumerate(features_value)
                  if np.all(np.isnan(arr_v[:, j]))]
    if nan_cols_a:
        print(f"[WARN] Model A: 全値NaNの特徴量 ({len(nan_cols_a)}件): {nan_cols_a}")
    if nan_cols_v:
        print(f"[WARN] Model B: 全値NaNの特徴量 ({len(nan_cols_v)}件): {nan_cols_v}")

    # === Place予測 (is_top3) ===
    pred_a_raw = model_a.predict(arr_a)
    pred_b_raw = model_b.predict(arr_v)

    # === EV用 vs ランキング用の確率使い分け ===
    # EV計算: IsotonicRegressionでキャリブレーション済みの絶対確率を使用
    #         （賭けの期待値計算には正確な確率が必要）
    # ランキング: raw予測値をレース内正規化（相対順序のみ必要、calibrationノイズを避ける）
    # 注意: IsotonicRegressionは単調変換なのでランキング順序は変わらないが、
    #       正規化基準が異なるため、EVとrankが乖離するケースがありうる
    pred_b_for_ev = pred_b_raw  # デフォルト: rawをそのまま使用
    if calibrators and 'cal_b' in calibrators:
        pred_b_for_ev = calibrators['cal_b'].predict(pred_b_raw)

    # レース内正規化: 各馬の確率合計を100%にする（ランキング用）
    sum_a = pred_a_raw.sum()
    sum_b = pred_b_raw.sum()
    pred_a = pred_a_raw / sum_a if sum_a > 0 else pred_a_raw
    pred_b = pred_b_raw / sum_b if sum_b > 0 else pred_b_raw

    # === Win予測 (is_win) ===
    has_win_model = model_w is not None and model_wv is not None
    pred_w = None
    pred_wv = None
    pred_wv_for_ev = None
    rank_w_dict = {}
    rank_wv_dict = {}

    if has_win_model:
        pred_w_raw = model_w.predict(arr_a)
        pred_wv_raw = model_wv.predict(arr_v)

        # IsotonicRegressionキャリブレーション（Win EV計算用）
        pred_wv_for_ev = pred_wv_raw  # デフォルト: rawをそのまま使用
        if calibrators and 'cal_wv' in calibrators:
            pred_wv_for_ev = calibrators['cal_wv'].predict(pred_wv_raw)

        sum_w = pred_w_raw.sum()
        sum_wv = pred_wv_raw.sum()
        pred_w = pred_w_raw / sum_w if sum_w > 0 else pred_w_raw
        pred_wv = pred_wv_raw / sum_wv if sum_wv > 0 else pred_wv_raw
        rank_w_dict = {i: r for r, i in enumerate(np.argsort(-pred_w), 1)}
        rank_wv_dict = {i: r for r, i in enumerate(np.argsort(-pred_wv), 1)}

    # === ability_score → rating_display (Method A: グレードオフセット付き) ===
    # 符号反転: 高い=強い。RATING_BASE + ability * RATING_SCALE + grade_offset
    RATING_SCALE = 14.7
    RATING_BASE = 74.2
    ability_score = None
    rating_display = None
    if model_reg_b is not None:
        ability_score = -model_reg_b.predict(arr_v)
        rating_display = RATING_BASE + ability_score * RATING_SCALE
        # Method A: グレードオフセット適用
        grade_key = get_grade_key(current_grade, current_age_class)
        grade_offset = (grade_offsets or {}).get(grade_key, 0.0)
        if grade_offset != 0.0:
            rating_display = rating_display + grade_offset

    # ランク計算
    rank_a_dict = {i: r for r, i in enumerate(np.argsort(-pred_a), 1)}
    rank_v_dict = {i: r for r, i in enumerate(np.argsort(-pred_b), 1)}

    # 結果を格納
    result_entries = []
    for i, p in enumerate(predictions):
        ra = rank_a_dict[i]
        rv = rank_v_dict[i]

        # odds_rank: NaN（オッズなし）→ 0 として出力
        odds_rank_raw = p['features'].get('odds_rank', np.nan)
        try:
            odds_rank = 0 if np.isnan(odds_rank_raw) else int(odds_rank_raw)
        except (TypeError, ValueError):
            odds_rank = 0

        # VB gap: odds_rankが有効な場合のみ計算
        gap = (odds_rank - rv) if odds_rank > 0 else 0

        # Win ranks & gap
        rw = rank_w_dict.get(i) if has_win_model else None
        rwv = rank_wv_dict.get(i) if has_win_model else None
        win_gap = int(odds_rank - rwv) if has_win_model and rwv and odds_rank > 0 else 0

        # 複勝オッズ
        umaban = p['umaban']
        place_low = None
        place_high = None
        if db_place_odds and umaban in db_place_odds:
            place_low = db_place_odds[umaban].get('odds_low')
            place_high = db_place_odds[umaban].get('odds_high')

        entry = {
            'umaban': umaban,
            'horse_name': p['horse_name'],
            'odds': p['odds'],
            'popularity': p['popularity'],
            # Place predictions (is_top3)
            'pred_proba_a': round(float(pred_a[i]), 4),
            'pred_proba_v': round(float(pred_b[i]), 4),
            'pred_proba_v_raw': round(float(pred_b_raw[i]), 6),
            'rank_a': int(ra),
            'rank_v': int(rv),
            'odds_rank': odds_rank,
            'vb_gap': int(gap),  # 参考情報（EVベース判定に移行済み）
            # Win predictions (is_win)
            'pred_proba_w': round(float(pred_w[i]), 4) if has_win_model else None,
            'pred_proba_wv': round(float(pred_wv[i]), 4) if has_win_model else None,
            'pred_proba_wv_cal': round(float(pred_wv_for_ev[i]), 6)
                if has_win_model and pred_wv_for_ev is not None else None,
            'rank_w': int(rw) if rw is not None else None,
            'rank_wv': int(rwv) if rwv is not None else None,
            'win_vb_gap': win_gap,
            # Place odds
            'place_odds_min': place_low,
            'place_odds_max': place_high,
            # EV (期待値) — キャリブレーション済み確率を使用
            # Win: calibrated P(win) × 単勝オッズ
            # Place: calibrated P(top3) × 複勝最低オッズ (raw sum≈3.0)
            'win_ev': round(float(pred_wv_for_ev[i]) * p['odds'], 4)
                if has_win_model and pred_wv_for_ev is not None and p['odds'] > 0 else None,
            'place_ev': round(float(pred_b_for_ev[i]) * place_low, 4)
                if place_low and place_low > 0 else None,
            # 能力R (rating_display: 高い=強い、74.3≈平均的勝ち馬)
            'predicted_margin': round(float(rating_display[i]), 1) if rating_display is not None else None,
            # keibabook情報
            'kb_mark': p['kb_mark'],
            'kb_mark_point': p['kb_mark_point'],
            'kb_training_arrow': p['kb_training_arrow'],
            'kb_rating': p['kb_rating'],
            'kb_comment': p['kb_comment'],
            'kb_ai_index': p['features'].get('kb_ai_index'),
            # 降格ローテ (v5.1)
            'koukaku_rote_count': p['features'].get('koukaku_rote_count', 0) or 0,
            'is_koukaku_venue': p['features'].get('is_koukaku_venue', 0) or 0,
            'is_koukaku_female': p['features'].get('is_koukaku_female', 0) or 0,
            'is_koukaku_season': p['features'].get('is_koukaku_season', 0) or 0,
            'is_koukaku_distance': p['features'].get('is_koukaku_distance', 0) or 0,
            'is_koukaku_turf_to_dirt': p['features'].get('is_koukaku_turf_to_dirt', 0) or 0,
            'is_koukaku_handicap': p['features'].get('is_koukaku_handicap', 0) or 0,
            # コメントNLPスコア (v5.3)
            'comment_stable_condition': p['features'].get('comment_stable_condition', 0) or 0,
            'comment_stable_confidence': p['features'].get('comment_stable_confidence', 0) or 0,
            'comment_stable_mark': p['features'].get('comment_stable_mark', 0) or 0,
            'comment_memo_condition': p['features'].get('comment_memo_condition', 0) or 0,
            'comment_memo_trouble_score': p['features'].get('comment_memo_trouble_score', 0) or 0,
            'comment_has_stable': p['features'].get('comment_has_stable', 0) or 0,
            'comment_has_interview': p['features'].get('comment_has_interview', 0) or 0,
        }
        entry['is_value_bet'] = False  # AR偏差値計算後に更新
        result_entries.append(entry)

    # ソート: Model B確率の高い順
    result_entries.sort(key=lambda x: -x['pred_proba_v'])

    # AR偏差値を計算（レース内相対評価、mean=50, std=10）
    ar_scores = [e['predicted_margin'] for e in result_entries
                 if e['predicted_margin'] is not None]
    if len(ar_scores) >= 2:
        ar_mean = np.mean(ar_scores)
        ar_std = max(np.std(ar_scores), 3.0)  # 少頭数のstd不安定対策: floor=3.0
        for e in result_entries:
            if e['predicted_margin'] is not None:
                e['ar_deviation'] = round(50 + 10 * (e['predicted_margin'] - ar_mean) / ar_std, 1)
            else:
                e['ar_deviation'] = None
    else:
        for e in result_entries:
            e['ar_deviation'] = 50.0  # AR情報不足時は全員50

    # VBフラグ更新: VB Floor条件（購入プラン⊆VB候補 を保証）
    # 条件A: EV >= 1.0 AND ARd >= 50（期待値＋能力）
    # 条件B: ARd >= 65 AND odds >= 10（ARd VBルート: 能力 vs 市場乖離）
    for e in result_entries:
        ev_ok = (e.get('win_ev') or 0) >= VB_FLOOR_MIN_WIN_EV
        ard_ok = (e.get('ar_deviation') or 0) >= VB_FLOOR_MIN_ARD
        ard_vb_ok = ((e.get('ar_deviation') or 0) >= VB_FLOOR_ARD_VB_MIN_ARD
                     and (e.get('odds') or 0) >= VB_FLOOR_ARD_VB_MIN_ODDS)
        e['is_value_bet'] = bool((ev_ok and ard_ok) or ard_vb_ok)

    return {
        'race_id': race['race_id'],
        'date': race_date,
        'venue_name': venue_name,
        'race_number': race.get('race_number', 0),
        'distance': distance,
        'track_type': track_type,
        'num_runners': entry_count,
        'grade': current_grade,
        'age_class': current_age_class,
        'is_handicap': current_is_handicap,
        'is_female_only': current_is_female_only,
        'entries': result_entries,
    }


def get_races_for_date(date: str) -> List[dict]:
    """指定日のレースJSONを全て読み込む"""
    date_parts = date.split('-')
    race_dir = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2]

    if not race_dir.exists():
        return []

    races = []
    for rp in sorted(race_dir.glob("race_[0-9]*.json")):
        with open(rp, encoding='utf-8') as f:
            races.append(json.load(f))

    return races


def get_latest_date() -> Optional[str]:
    """date_indexから最新の日付を取得"""
    di_path = config.indexes_dir() / "race_date_index.json"
    with open(di_path, encoding='utf-8') as f:
        date_index = json.load(f)

    if date_index:
        return sorted(date_index.keys())[-1]
    return None


def main():
    parser = argparse.ArgumentParser(description='v3 Race Prediction')
    parser.add_argument('--date', help='対象日 (YYYY-MM-DD)')
    parser.add_argument('--race-id', help='特定レースID (16桁)')
    parser.add_argument('--latest', action='store_true', help='最新開催日')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用')
    parser.add_argument('--model-version', help='モデルバージョン指定 (例: 5.0, 3.5)')
    parser.add_argument('--list-versions', action='store_true', help='利用可能なモデルバージョン一覧')
    parser.add_argument('--predict-only', action='store_true',
                        help='ML予測のみ（VB判定・買い目生成をスキップ）')
    args = parser.parse_args()

    # バージョン一覧表示
    if args.list_versions:
        versions = list_model_versions()
        print(f"\n{'='*60}")
        print(f"  利用可能なモデルバージョン")
        print(f"{'='*60}")
        for v in versions:
            live = " [LIVE]" if v.get('is_live') else ""
            win = " +Win" if v.get('has_win_model') else ""
            feat = f"A={v.get('feature_count_all', '?')}/V={v.get('feature_count_value', '?')}"
            created = v.get('created_at', v.get('archived_at', ''))
            print(f"  v{v['version']}{live}{win}  {feat}  ({created})")
        print(f"{'='*60}\n")
        return

    use_db_odds = not args.no_db
    model_version = args.model_version

    t0 = time.time()

    ver_label = f" (model v{model_version})" if model_version else ""
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Race Prediction{ver_label}")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF (JSON fallback)'}")
    print(f"{'='*60}\n")

    # モデルロード
    print("[Load] Loading models...")
    model_a, model_b, model_w, model_wv, meta, calibrators, model_reg_b = load_model_and_meta(model_version)

    # 障害モデルロード
    model_obstacle, obstacle_meta, obstacle_calibrator = load_obstacle_model()
    has_obstacle_model = model_obstacle is not None

    # マスタデータロード
    print("[Load] Loading master data...")
    (history_cache, trainer_index, jockey_index, pace_index,
     kb_ext_index, race_level_index, pedigree_index, sire_stats_index,
     baba_index) = load_master_data()
    print(f"  History: {len(history_cache):,} horses")
    print(f"  Trainers: {len(trainer_index):,}")
    print(f"  Jockeys: {len(jockey_index):,}")
    print(f"  KB Ext: {len(kb_ext_index):,} races")
    print(f"  Pace index: {len(pace_index):,} races")

    # 対象レース決定
    if args.race_id:
        # 特定レース
        from core.jravan.race_id import parse as parse_race_id
        info = parse_race_id(args.race_id)
        if not info:
            print(f"ERROR: Invalid race_id: {args.race_id}")
            return
        date = info['date']
        races = [r for r in get_races_for_date(date)
                 if r['race_id'] == args.race_id]
    elif args.date:
        date = args.date
        races = get_races_for_date(date)
    elif args.latest:
        date = get_latest_date()
        if not date:
            print("ERROR: No dates in index")
            return
        races = get_races_for_date(date)
    else:
        print("ERROR: Specify --date, --race-id, or --latest")
        return

    if not races:
        print(f"No races found for {date}")
        return

    print(f"\n[Predict] {len(races)} races for {date}")

    # DB事前オッズ取得
    db_odds_index = {}
    db_place_odds_index = {}
    if use_db_odds:
        try:
            from core.odds_db import batch_get_pre_race_odds, batch_get_place_odds, is_db_available
            if is_db_available():
                race_codes = [r['race_id'] for r in races]
                db_odds_index = batch_get_pre_race_odds(race_codes)
                db_place_odds_index = batch_get_place_odds(race_codes)
                print(f"[DB Odds] Win: {len(db_odds_index)}/{len(races)}, "
                      f"Place: {len(db_place_odds_index)}/{len(races)} races")
            else:
                print("[DB Odds] mykeibadb not available, using JSON odds")
        except Exception as e:
            print(f"[DB Odds] Error: {e}, using JSON odds")

    # CK_DATA調教サマリ読み込み
    training_summary_day = {}
    date_parts = date.split('-')
    ts_path = (config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2]
               / "temp" / "training_summary.json")
    if ts_path.exists():
        try:
            with open(ts_path, encoding='utf-8') as f:
                ts_data = json.load(f)
            for _name, entry in ts_data.get('summaries', {}).items():
                kn = entry.get('kettoNum', '')
                if kn:
                    training_summary_day[kn] = entry
            print(f"[CK_DATA] {len(training_summary_day):,} horses with training summary")
        except Exception as e:
            print(f"[CK_DATA] Error loading training_summary: {e}")

    # グレードオフセット読み込み（Method A）
    grade_offsets = load_grade_offsets()
    if grade_offsets:
        print(f"[Grade] Method A: {len(grade_offsets)} grade offsets loaded")

    # Pre-pass: track_type不明のレースをDB補完で障害判定
    # keibabook-sourcedの古いJSONはtrack_type/race_nameが空のことがある
    for race in races:
        if not race.get('track_type') and not race.get('race_name'):
            db_race = _fetch_race_shosai_from_db(race['race_id'])
            if db_race:
                if db_race.get('track_type') == 'obstacle':
                    race['track_type'] = 'obstacle'
                if not race.get('race_name') and db_race.get('race_name'):
                    race['race_name'] = db_race['race_name']
                if race.get('distance', 0) == 0 and db_race.get('distance', 0) > 0:
                    race['distance'] = db_race['distance']

    # 障害レースを分離（障害モデルがあれば予測、なければ除外）
    obstacle_races = []
    flat_races = []
    for race in races:
        race_name = race.get('race_name', '')
        track_type = race.get('track_type', '')
        if '障害' in race_name or track_type == 'obstacle':
            obstacle_races.append(race)
        else:
            flat_races.append(race)
    if obstacle_races:
        if has_obstacle_model:
            print(f"[Obstacle] {len(obstacle_races)} obstacle races → obstacle model")
        else:
            print(f"[Filter] {len(obstacle_races)} obstacle races excluded (no model)")
            obstacle_races = []

    # 予測実行（平地）
    all_predictions = []
    vb_count = 0

    for race in flat_races:
        kb_ext = load_keibabook_ext(race['race_id'], race['date'])
        pred = predict_race(
            race, kb_ext,
            model_a, model_b, meta,
            history_cache, trainer_index, jockey_index, pace_index,
            db_odds=db_odds_index.get(race['race_id']),
            training_summary_day=training_summary_day,
            model_w=model_w,
            model_wv=model_wv,
            db_place_odds=db_place_odds_index.get(race['race_id']),
            kb_ext_index=kb_ext_index,
            calibrators=calibrators,
            model_reg_b=model_reg_b,
            grade_offsets=grade_offsets,
            race_level_index=race_level_index,
            pedigree_index=pedigree_index,
            sire_stats_index=sire_stats_index,
            baba_index=baba_index,
        )
        all_predictions.append(pred)

        # Value Bet集計
        for e in pred['entries']:
            if e['is_value_bet']:
                vb_count += 1

        venue = pred.get('venue_name', '?')
        rn = pred.get('race_number', '?')
        top1 = pred['entries'][0] if pred['entries'] else None
        top1_name = top1['horse_name'] if top1 else '?'
        top1_gap = top1['vb_gap'] if top1 else 0
        vb_marker = ' [VB]' if top1 and top1['is_value_bet'] else ''
        print(f"  {venue}{rn}R: Top1={top1_name} (gap={top1_gap}){vb_marker}")

    # === DB補完で障害と判明したレースをリダイレクト ===
    if has_obstacle_model:
        redirected_races = []
        for pred in all_predictions:
            if pred.get('_needs_obstacle_model'):
                race_id = pred['race_id']
                original_race = next((r for r in flat_races if r['race_id'] == race_id), None)
                if original_race:
                    redirected_races.append(original_race)
        if redirected_races:
            all_predictions = [p for p in all_predictions if not p.get('_needs_obstacle_model')]
            obstacle_races.extend(redirected_races)
            print(f"[Obstacle] {len(redirected_races)} races redirected from flat → obstacle model")

    # === 障害レース予測 ===
    obstacle_predictions = []
    if obstacle_races and has_obstacle_model:
        for race in obstacle_races:
            pred = predict_obstacle_race(
                race, model_obstacle, obstacle_meta, obstacle_calibrator,
                history_cache, trainer_index, jockey_index, pace_index,
                db_odds=db_odds_index.get(race['race_id']),
                kb_ext_index=kb_ext_index,
                race_level_index=race_level_index,
                pedigree_index=pedigree_index,
                sire_stats_index=sire_stats_index,
            )
            obstacle_predictions.append(pred)
            all_predictions.append(pred)

            venue = pred.get('venue_name', '?')
            rn = pred.get('race_number', '?')
            top1 = pred['entries'][0] if pred['entries'] else None
            top1_name = top1['horse_name'] if top1 else '?'
            print(f"  {venue}{rn}R: Top1={top1_name} [障害]")

        print(f"[Obstacle] {len(obstacle_predictions)} obstacle races predicted")

    # === 買い目推奨生成 (bet_engine) ===
    all_recommendations = {}
    multi_leg_output = []

    if args.predict_only:
        print(f"\n[PredictOnly] Skipping bet_engine & multi-leg (--predict-only)")
    else:
        print(f"\n[BetEngine] Generating recommendations...")
        for preset_name, preset_params in PRESETS.items():
            recs = generate_recommendations(all_predictions, preset_params, budget=30000)
            all_recommendations[preset_name] = {
                'params': {
                    'win_min_ev': preset_params.win_min_ev,
                    'win_min_gap': preset_params.win_min_gap,
                    'win_min_rating': preset_params.win_min_rating,
                    'win_min_ar_deviation': preset_params.win_min_ar_deviation,
                    'win_max_rank': preset_params.win_max_rank,
                    'win_v_ratio_min': preset_params.win_v_ratio_min,
                    'win_v_bypass_gap': preset_params.win_v_bypass_gap,
                    'win_v_bypass_ev': preset_params.win_v_bypass_ev,
                    'place_min_gap': preset_params.place_min_gap,
                    'place_min_rating': preset_params.place_min_rating,
                    'place_min_ar_deviation': preset_params.place_min_ar_deviation,
                    'place_min_ev': preset_params.place_min_ev,
                    'kelly_fraction': preset_params.kelly_fraction,
                },
                'bets': recommendations_to_dict(recs),
                'summary': recommendations_summary(recs),
            }
            s = recommendations_summary(recs)
            print(f"  {preset_name}: {s['total_bets']} bets, "
                  f"Win={s['win_bets']}, Place={s['place_bets']}, "
                  f"Amount={s['total_amount']:,}")

        # === マルチレグ推奨生成 ===
        print(f"\n[MultiLeg] Generating multi-leg recommendations...")
        try:
            from ml.simulate_multi_leg import generate_recommendations as gen_multi_leg
            multi_leg_recs = gen_multi_leg(all_predictions)
            for r in multi_leg_recs:
                multi_leg_output.append({
                    'race_id': r.race_id,
                    'venue': r.venue,
                    'race_number': r.race_num,
                    'strategy': r.strategy,
                    'ticket_type': r.ticket_type,
                    'horses': list(r.horses),
                    'horse_names': list(r.horse_names),
                    'cost': r.cost,
                    'note': r.note,
                })
            print(f"  {len(multi_leg_output)} tickets across "
                  f"{len(set(r.race_id for r in multi_leg_recs))} races")
        except Exception as e:
            print(f"  [Warning] multi-leg generation failed: {e}")

    # 結果保存
    actual_model_version = model_version if model_version else meta.get('version', '?')
    output = {
        'version': '4.0',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'date': date,
        'model_version': actual_model_version,
        'model_source': 'archive' if model_version else 'live',
        'model_features_all': len(meta.get('features_all', [])),
        'model_features_value': len(meta.get('features_value', [])),
        'model_has_win': model_w is not None,
        'model_has_obstacle': has_obstacle_model,
        'odds_source': 'mykeibadb' if db_odds_index else 'json',
        'predict_only': bool(args.predict_only),
        'db_odds_coverage': f"{len(db_odds_index)}/{len(races)}",
        'races': all_predictions,
        'recommendations': all_recommendations,
        'multi_leg_recommendations': multi_leg_output,
        'summary': {
            'total_races': len(all_predictions),
            'obstacle_races': len(obstacle_predictions) if obstacle_races else 0,
            'total_entries': sum(len(p['entries']) for p in all_predictions),
            'value_bets': vb_count,
            'ev_positive_win': sum(
                1 for p in all_predictions for e in p['entries']
                if (e.get('win_ev') or 0) > 1.0
            ),
            'ev_positive_place': sum(
                1 for p in all_predictions for e in p['entries']
                if (e.get('place_ev') or 0) > 1.0
            ),
        },
    }

    out_json = json.dumps(output, ensure_ascii=False, indent=2)

    out_path = config.ml_dir() / "predictions_live.json"
    out_path.write_text(out_json, encoding='utf-8')

    # 日別アーカイブ: races/YYYY/MM/DD/predictions.json
    date_parts = date.split('-')
    archive_dir = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2]
    if archive_dir.exists():
        archive_path = archive_dir / "predictions.json"
        archive_path.write_text(out_json, encoding='utf-8')
        print(f"\n[Archive] {archive_path}")

    elapsed = time.time() - t0

    print(f"\n[Summary]")
    print(f"  Races:      {len(all_predictions)}")
    print(f"  Value Bets: {vb_count}")
    print(f"  Output:     {out_path}")
    print(f"  Elapsed:    {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

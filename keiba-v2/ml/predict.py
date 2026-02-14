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
from ml.features.past_features import compute_past_features
from ml.features.trainer_features import get_trainer_features, build_trainer_index
from ml.features.jockey_features import get_jockey_features, build_jockey_index
from ml.features.running_style_features import compute_running_style_features
from ml.features.rotation_features import compute_rotation_features
from ml.features.pace_features import compute_pace_features
from ml.features.training_features import compute_training_features
from ml.features.speed_features import compute_speed_features


def load_model_and_meta():
    """学習済みモデルとメタ情報をロード"""
    import lightgbm as lgb

    ml_dir = config.ml_dir()

    model_a = lgb.Booster(model_file=str(ml_dir / "model_a.txt"))
    model_b = lgb.Booster(model_file=str(ml_dir / "model_b.txt"))

    with open(ml_dir / "model_meta.json", encoding='utf-8') as f:
        meta = json.load(f)

    return model_a, model_b, meta


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

    # Pace index
    from ml.experiment_v3 import build_pace_index
    di_path = config.indexes_dir() / "race_date_index.json"
    with open(di_path, encoding='utf-8') as f:
        date_index = json.load(f)
    pace_index = build_pace_index(date_index)

    return history_cache, trainer_index, jockey_index, pace_index


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
) -> dict:
    """1レースの予測を実行

    Args:
        db_odds: mykeibadbから取得した事前オッズ {umaban: {'odds': float, 'ninki': int}}
    """
    features_all = meta['features_all']
    features_value = meta['features_value']

    race_date = race['date']
    venue_code = race['venue_code']
    track_type = race.get('track_type', '')
    distance = race.get('distance', 0)
    entry_count = race.get('num_runners', 0)

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

        # ローテ・コンディション特徴量 (v3.1)
        rot_feat = compute_rotation_features(
            ketto_num=ketto_num,
            race_date=race_date,
            futan=entry.get('futan', 0.0),
            horse_weight=entry.get('horse_weight', 0),
            popularity=entry.get('popularity', 0),
            history_cache=history_cache,
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

        # 調教特徴量 (v3.3)
        kb_e = kb_entries.get(str(umaban))
        train_feat = compute_training_features(
            umaban=str(umaban),
            kb_ext=kb_ext,
        )
        feat.update(train_feat)

        # スピード指数特徴量 (v3.5)
        speed_feat = compute_speed_features(
            umaban=str(umaban),
            kb_ext=kb_ext,
        )
        feat.update(speed_feat)

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
    for p in predictions:
        row_a = [p['features'].get(f, np.nan) for f in features_all]
        row_v = [p['features'].get(f, np.nan) for f in features_value]
        feature_rows_a.append(row_a)
        feature_rows_v.append(row_v)

    arr_a = np.array(feature_rows_a)
    arr_v = np.array(feature_rows_v)

    # 予測
    pred_a_raw = model_a.predict(arr_a)
    pred_b_raw = model_b.predict(arr_v)

    # レース内正規化: 各馬の確率合計を100%にする
    sum_a = pred_a_raw.sum()
    sum_b = pred_b_raw.sum()
    pred_a = pred_a_raw / sum_a if sum_a > 0 else pred_a_raw
    pred_b = pred_b_raw / sum_b if sum_b > 0 else pred_b_raw

    # ランク計算
    rank_a = np.argsort(-pred_a) + 1
    rank_v = np.argsort(-pred_b) + 1

    # 結果を格納
    rank_a_dict = {i: r for r, i in enumerate(np.argsort(-pred_a), 1)}
    rank_v_dict = {i: r for r, i in enumerate(np.argsort(-pred_b), 1)}

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

        result_entries.append({
            'umaban': p['umaban'],
            'horse_name': p['horse_name'],
            'odds': p['odds'],
            'popularity': p['popularity'],
            'pred_proba_a': round(float(pred_a[i]), 4),
            'pred_proba_v': round(float(pred_b[i]), 4),
            'rank_a': int(ra),
            'rank_v': int(rv),
            'odds_rank': odds_rank,
            'vb_gap': int(gap),
            'is_value_bet': gap >= 3 and odds_rank > 0,
            # keibabook情報
            'kb_mark': p['kb_mark'],
            'kb_mark_point': p['kb_mark_point'],
            'kb_training_arrow': p['kb_training_arrow'],
            'kb_rating': p['kb_rating'],
            'kb_comment': p['kb_comment'],
        })

    # ソート: Model B確率の高い順
    result_entries.sort(key=lambda x: -x['pred_proba_v'])

    return {
        'race_id': race['race_id'],
        'date': race_date,
        'venue_name': race.get('venue_name', ''),
        'race_number': race.get('race_number', 0),
        'distance': distance,
        'track_type': track_type,
        'num_runners': entry_count,
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
    args = parser.parse_args()
    use_db_odds = not args.no_db

    t0 = time.time()

    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Race Prediction (v3.4 model)")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF (JSON fallback)'}")
    print(f"{'='*60}\n")

    # モデルロード
    print("[Load] Loading models...")
    model_a, model_b, meta = load_model_and_meta()
    print(f"  Model A features: {len(meta['features_all'])}")
    print(f"  Model B features: {len(meta['features_value'])}")

    # マスタデータロード
    print("[Load] Loading master data...")
    history_cache, trainer_index, jockey_index, pace_index = load_master_data()
    print(f"  History: {len(history_cache):,} horses")
    print(f"  Trainers: {len(trainer_index):,}")
    print(f"  Jockeys: {len(jockey_index):,}")
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
    if use_db_odds:
        try:
            from core.odds_db import batch_get_pre_race_odds, is_db_available
            if is_db_available():
                race_codes = [r['race_id'] for r in races]
                db_odds_index = batch_get_pre_race_odds(race_codes)
                print(f"[DB Odds] {len(db_odds_index)}/{len(races)} races with DB odds")
            else:
                print("[DB Odds] mykeibadb not available, using JSON odds")
        except Exception as e:
            print(f"[DB Odds] Error: {e}, using JSON odds")

    # 予測実行
    all_predictions = []
    vb_count = 0

    for race in races:
        kb_ext = load_keibabook_ext(race['race_id'], race['date'])
        pred = predict_race(
            race, kb_ext,
            model_a, model_b, meta,
            history_cache, trainer_index, jockey_index, pace_index,
            db_odds=db_odds_index.get(race['race_id']),
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

    # 結果保存
    output = {
        'version': '3.4',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'date': date,
        'model_version': meta.get('version', '?'),
        'odds_source': 'mykeibadb' if db_odds_index else 'json',
        'db_odds_coverage': f"{len(db_odds_index)}/{len(races)}",
        'races': all_predictions,
        'summary': {
            'total_races': len(all_predictions),
            'total_entries': sum(len(p['entries']) for p in all_predictions),
            'value_bets': vb_count,
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

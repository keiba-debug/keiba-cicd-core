#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRDBインデックス構築

SED（事後IDM）とKYI（事前IDM）をパースし、
KeibaCICDのketto_num(10桁)+race_dateで引けるインデックスを構築する。

出力:
  data3/indexes/jrdb_sed_index.json  — 事後IDM・指数（過去成績用）
  data3/indexes/jrdb_kyi_index.json  — 事前IDM・予測値（出走表用）

Usage:
    python -m builders.build_jrdb_index
    python -m builders.build_jrdb_index --years 2024-2025
    python -m builders.build_jrdb_index --type sed
    python -m builders.build_jrdb_index --type kyi
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jrdb.parser import (
    parse_sed_line, parse_kyi_line, parse_srb_line,
    parse_cyb_line, parse_cha_line, parse_kka_line,
    parse_ukc_line, parse_joa_line, parse_kaa_line,
)

RAW_DIR = Path('C:/KEIBA-CICD/data3/jrdb/raw')
INDEX_DIR = Path('C:/KEIBA-CICD/data3/indexes')


def build_sed_index(year_range: range) -> dict:
    """SED全ファイル → {ketto_num_10}_{race_date} → 事後IDMデータ"""
    sed_dir = RAW_DIR / 'SED'
    if not sed_dir.exists():
        print(f"ERROR: {sed_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(sed_dir.glob('SED*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 370:
                continue
            try:
                r = parse_sed_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            kn10 = '20' + r['ketto_num_jrdb']
            race_date = r['race_date']
            if not race_date:
                continue

            key = f"{kn10}_{race_date}"

            # 事後IDMデータ + レース分析用フィールド
            # race_key info for race-level grouping
            rk = r['jrdb_race_key']
            venue_code = rk[0:2]
            race_num = int(rk[6:8]) if len(rk) >= 8 else 0

            index[key] = {
                'idm': r['idm'],
                'soten': r['soten'],
                'baba_sa': r['baba_sa'],
                'pace_adj': r['pace_adj'],
                'deokure_adj': r['deokure_adj'],
                'ichi_tori_adj': r['ichi_tori_adj'],
                'furi_adj': r['furi_adj'],
                'mae_furi_adj': r['mae_furi_adj'],
                'naka_furi_adj': r['naka_furi_adj'],
                'ato_furi_adj': r['ato_furi_adj'],
                'race_adj': r['race_adj'],
                'ten_idx': r['ten_idx'],
                'agari_idx': r['agari_idx'],
                'pace_idx': r['pace_idx'],
                'race_pace_idx': r['race_pace_idx'],
                'course_tori': r['course_tori'],
                'joushou_code': r['joushou_code'],
                'race_pace': r['race_pace'],
                'horse_pace': r['horse_pace'],
                'front_3f': r['front_3f'],
                'rear_3f': r['rear_3f'],
                # 前崩れ / レース質分析用
                'corner1': r['corner1'],
                'corner2': r['corner2'],
                'corner3': r['corner3'],
                'corner4': r['corner4'],
                'finish_position': r['finish_position'],
                'num_runners': r['num_runners'],
                'distance': r['distance'],
                'track_code': r['track_code'],
                'venue_code': venue_code,
                'race_num': race_num,
                'race_date': race_date,
            }

        file_count += 1

    print(f"[SED Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_kyi_index(year_range: range) -> dict:
    """KYI全ファイル → {ketto_num_10}_{race_date} → 事前IDMデータ"""
    kyi_dir = RAW_DIR / 'KYI'
    if not kyi_dir.exists():
        print(f"ERROR: {kyi_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    # KYIはレースキーから日付を推定する必要がある
    # KYIファイル名: KYI250301.txt → 2025-03-01
    for f in sorted(kyi_dir.glob('KYI*.txt')):
        fname = f.stem  # KYI250301
        yy = fname[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year not in year_range:
            continue

        # ファイル名から日付推定
        mmdd = fname[5:9]
        if len(mmdd) == 4:
            race_date = f"{year}-{mmdd[:2]}-{mmdd[2:]}"
        else:
            race_date = ''

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 620:
                continue
            try:
                r = parse_kyi_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            kn10 = '20' + r['ketto_num_jrdb']

            # KYIには日付フィールドがないのでファイル名から
            key = f"{kn10}_{race_date}"

            index[key] = {
                # === 既存フィールド ===
                'pre_idm': r['pre_idm'],
                'jockey_idx': r['jockey_idx'],
                'info_idx': r['info_idx'],
                'sogo_idx': r['sogo_idx'],
                'training_idx': r['training_idx'],
                'stable_idx': r['stable_idx'],
                'gekisou_idx': r['gekisou_idx'],
                'pred_ten_idx': r['pred_ten_idx'],
                'pred_pace_idx': r['pred_pace_idx'],
                'pred_agari_idx': r['pred_agari_idx'],
                'pred_position_idx': r['pred_position_idx'],
                'pred_pace': r['pred_pace'],
                'kyakushitsu': r['kyakushitsu'],
                'distance_aptitude': r['distance_aptitude'],
                'base_odds': r['base_odds'],
                'base_popularity': r['base_popularity'],
                'start_idx': r['start_idx'],
                'deokure_rate': r['deokure_rate'],
                # === 新規フィールド (Session 114) ===
                'ninki_idx': r['ninki_idx'],
                'rotation': r['rotation'],
                'base_place_odds': r['base_place_odds'],
                'base_place_popularity': r['base_place_popularity'],
                # 調教・厩舎詳細
                'training_arrow': r['training_arrow'],
                'stable_eval': r['stable_eval'],
                'jockey_rentairitsu': r['jockey_rentairitsu'],
                # 適性
                'distance_aptitude2': r['distance_aptitude2'],
                'turf_aptitude': r['turf_aptitude'],
                'dirt_aptitude': r['dirt_aptitude'],
                'omo_tekisei': r['omo_tekisei'],
                'hizume_code': r['hizume_code'],
                # 馬具
                'blinker': r['blinker'],
                # JRDB印コード
                'mark_sogo': r['mark_sogo'],
                'mark_idm': r['mark_idm'],
                'mark_info': r['mark_info'],
                'mark_jockey': r['mark_jockey'],
                'mark_stable': r['mark_stable'],
                'mark_training': r['mark_training'],
                'mark_gekisou': r['mark_gekisou'],
                # 専門紙印（特定情報）
                'tokutei_honmei': r['tokutei_honmei'],
                'tokutei_taikou': r['tokutei_taikou'],
                'tokutei_tanana': r['tokutei_tanana'],
                'tokutei_renka': r['tokutei_renka'],
                'tokutei_hoshi': r['tokutei_hoshi'],
                # 専門紙印（総合情報）
                'sogo_honmei': r['sogo_honmei'],
                'sogo_taikou': r['sogo_taikou'],
                'sogo_tanana': r['sogo_tanana'],
                'sogo_renka': r['sogo_renka'],
                'sogo_hoshi': r['sogo_hoshi'],
                # 展開予想詳細
                'pred_dochu_order': r['pred_dochu_order'],
                'pred_dochu_diff': r['pred_dochu_diff'],
                'pred_dochu_uchi_soto': r['pred_dochu_uchi_soto'],
                'pred_3f_order': r['pred_3f_order'],
                'pred_3f_diff': r['pred_3f_diff'],
                'pred_3f_uchi_soto': r['pred_3f_uchi_soto'],
                'pred_goal_order': r['pred_goal_order'],
                'pred_goal_diff': r['pred_goal_diff'],
                'pred_goal_uchi_soto': r['pred_goal_uchi_soto'],
                'tenkai_kigou': r['tenkai_kigou'],
                # 各指数順位
                'gekisou_rank': r['gekisou_rank'],
                'ls_idx_rank': r['ls_idx_rank'],
                'ten_idx_rank': r['ten_idx_rank'],
                'pace_idx_rank': r['pace_idx_rank'],
                'agari_idx_rank': r['agari_idx_rank'],
                'position_idx_rank': r['position_idx_rank'],
                # 騎手期待値
                'jockey_expected_win_rate': r['jockey_expected_win_rate'],
                'jockey_expected_place_rate': r['jockey_expected_place_rate'],
                'yusou_kubun': r['yusou_kubun'],
                # 万券指数
                'manken_idx': r['manken_idx'],
                'manken_mark': r['manken_mark'],
                # 降級・激走
                'koukyu_flag': r['koukyu_flag'],
                'gekisou_type': r['gekisou_type'],
                'kyuuyou_reason': r['kyuuyou_reason'],
                # 入厩情報
                'nyuukyuu_num_runs': r['nyuukyuu_num_runs'],
                'nyuukyuu_date': r['nyuukyuu_date'],
                'nyuukyuu_days_before': r['nyuukyuu_days_before'],
                # 放牧先・厩舎
                'houboku_rank': r['houboku_rank'],
                'kyuusha_rank': r['kyuusha_rank'],
                # 馬体重
                'wakutei_weight': r['wakutei_weight'],
                'wakutei_weight_diff': r['wakutei_weight_diff'],
                # フラグ
                'flags': r['flags'],
            }

        file_count += 1

    print(f"[KYI Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_cyb_index(year_range: range) -> dict:
    """CYB全ファイル → {jrdb_race_key}_{umaban:02d} → 調教分析データ"""
    cyb_dir = RAW_DIR / 'CYB'
    if not cyb_dir.exists():
        print(f"ERROR: {cyb_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(cyb_dir.glob('CYB*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 90:
                continue
            try:
                r = parse_cyb_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            key = f"{r['jrdb_race_key']}_{r['umaban']:02d}"
            index[key] = {
                'training_type': r['training_type'],
                'course_type': r['course_type'],
                'turf_count': r['turf_count'],
                'wood_count': r['wood_count'],
                'dirt_count': r['dirt_count'],
                'polytrack_count': r['polytrack_count'],
                'training_volume': r['training_volume'],
                'training_emphasis': r['training_emphasis'],
                'oikiri_idx': r['oikiri_idx'],
                'shiage_idx': r['shiage_idx'],
                'training_eval_class': r['training_eval_class'],
                'shiage_change': r['shiage_change'],
                'training_eval': r['training_eval'],
                'oikiri_idx_prev_week': r['oikiri_idx_prev_week'],
                'training_comment': r['training_comment'],
            }

        file_count += 1

    print(f"[CYB Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_cha_index(year_range: range) -> dict:
    """CHA全ファイル → {jrdb_race_key}_{umaban:02d} → 本追切データ"""
    cha_dir = RAW_DIR / 'CHA'
    if not cha_dir.exists():
        print(f"ERROR: {cha_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(cha_dir.glob('CHA*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 55:
                continue
            try:
                r = parse_cha_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            key = f"{r['jrdb_race_key']}_{r['umaban']:02d}"
            index[key] = {
                'training_date': r['training_date'],
                'oikiri_course': r['oikiri_course'],
                'oikiri_type': r['oikiri_type'],
                'nori': r['nori'],
                'ten_e': r['ten_e'],
                'chukan_e': r['chukan_e'],
                'shimai_e': r['shimai_e'],
                'ten_e_idx': r['ten_e_idx'],
                'chukan_e_idx': r['chukan_e_idx'],
                'shimai_e_idx': r['shimai_e_idx'],
                'oikiri_idx': r['oikiri_idx'],
            }

        file_count += 1

    print(f"[CHA Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_kka_index(year_range: range) -> dict:
    """KKA全ファイル → {jrdb_race_key}_{umaban:02d} → 競走馬拡張データ"""
    kka_dir = RAW_DIR / 'KKA'
    if not kka_dir.exists():
        print(f"ERROR: {kka_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(kka_dir.glob('KKA*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 300:
                continue
            try:
                r = parse_kka_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            key = f"{r['jrdb_race_key']}_{r['umaban']:02d}"
            index[key] = {
                'jrdb_results': r['jrdb_results'],
                'exchange_results': r['exchange_results'],
                'other_results': r['other_results'],
                'dam_best_rentai': r['dam_best_rentai'],
                'dam_place_rentai': r['dam_place_rentai'],
                'dam_avg_distance': r['dam_avg_distance'],
                'bms_best_rentai': r['bms_best_rentai'],
                'bms_place_rentai': r['bms_place_rentai'],
                'bms_avg_distance': r['bms_avg_distance'],
                # 産地成績レベル (配列)
                's_pace_level': r['s_pace_level'],
                'n_pace_level': r['n_pace_level'],
                'h_pace_level': r['h_pace_level'],
                'season_results': r['season_results'],
            }

        file_count += 1

    print(f"[KKA Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_ukc_index(year_range: range) -> dict:
    """UKC全ファイル → {ketto_num_jrdb} → 馬基本データ

    UKCはマスタデータ。同一馬が複数ファイルに出現するため、最新を採用。
    """
    ukc_dir = RAW_DIR / 'UKC'
    if not ukc_dir.exists():
        print(f"ERROR: {ukc_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(ukc_dir.glob('UKC*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 270:
                continue
            try:
                r = parse_ukc_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            key = r['ketto_num_jrdb']
            index[key] = {
                'horse_name': r['horse_name'],
                'sex_code': r['sex_code'],
                'coat_color': r['coat_color'],
                'sire_name': r['sire_name'],
                'dam_name': r['dam_name'],
                'broodmare_sire': r['broodmare_sire'],
                'birth_date': r['birth_date'],
                'owner_name': r['owner_name'],
                'breeder_name': r['breeder_name'],
                'origin': r['origin'],
                'retired_flag': r['retired_flag'],
            }

        file_count += 1

    print(f"[UKC Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_joa_index(year_range: range) -> dict:
    """JOA全ファイル → {jrdb_race_key}_{umaban:02d} → CID/LS/BB情報"""
    joa_dir = RAW_DIR / 'JOA'
    if not joa_dir.exists():
        print(f"ERROR: {joa_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(joa_dir.glob('JOA*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 100:
                continue
            try:
                r = parse_joa_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            key = f"{r['jrdb_race_key']}_{r['umaban']:02d}"
            index[key] = {
                'cid_choushi': r['cid_choushi'],
                'cid_sani': r['cid_sani'],
                'cid_score': r['cid_score'],
                'cid': r['cid'],
                'ls_idx': r['ls_idx'],
                'ls_eval': r['ls_eval'],
                'em': r['em'],
                'bb_turf_dirt': r['bb_turf_dirt'],
                'bb_turf_dirt_win': r['bb_turf_dirt_win'],
                'bb_turf_dirt_place': r['bb_turf_dirt_place'],
                'bb_turf': r['bb_turf'],
                'bb_turf_win': r['bb_turf_win'],
                'bb_turf_place': r['bb_turf_place'],
            }

        file_count += 1

    print(f"[JOA Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def build_srb_index(year_range: range) -> dict:
    """SRB全ファイル → {jrdb_race_key} → レースレベル分析データ

    SRBファイルはSED.lzhに同梱されてraw/SED/に展開される。
    キー: JRDBレースキー(8桁)
    """
    sed_dir = RAW_DIR / 'SED'
    if not sed_dir.exists():
        print(f"ERROR: {sed_dir} not found")
        return {}

    index = {}
    file_count = 0
    error_count = 0

    for f in sorted(sed_dir.glob('SRB*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue

        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 340:
                continue
            try:
                r = parse_srb_line(line)
                if not r:
                    continue
            except Exception:
                error_count += 1
                continue

            key = r['jrdb_race_key']
            index[key] = {
                'furlong_times': r['furlong_times'],
                'pace_up_position': r['pace_up_position'],
                'bias_1corner': r['bias_1corner'],
                'bias_2corner': r['bias_2corner'],
                'bias_mukousei': r['bias_mukousei'],
                'bias_3corner': r['bias_3corner'],
                'bias_4corner': r['bias_4corner'],
                'bias_straight': r['bias_straight'],
                'race_comment': r['race_comment'],
            }

        file_count += 1

    print(f"[SRB Index] {file_count} files, {len(index):,} entries, {error_count} errors")
    return index


def _save_index(index: dict, name: str, t0: float):
    """インデックスをJSONに保存"""
    if not index:
        return
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    out = INDEX_DIR / f'jrdb_{name}_index.json'
    out.write_text(json.dumps(index, ensure_ascii=False), encoding='utf-8')
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"  Saved: {out} ({size_mb:.1f} MB, {time.time()-t0:.1f}s)")


def build_kaa_index(year_range: range) -> dict:
    """KAA全ファイル → {venue_code}_{race_date} → 開催データ（馬場・天候）"""
    kaa_dir = RAW_DIR / 'KAA'
    if not kaa_dir.exists():
        print(f"ERROR: {kaa_dir} not found")
        return {}

    index = {}
    errors = 0
    file_count = 0

    for f in sorted(kaa_dir.glob('KAA*.txt')):
        yy = f.stem[3:5]
        try:
            year = 2000 + int(yy) if int(yy) < 80 else 1900 + int(yy)
        except ValueError:
            continue
        if year not in year_range:
            continue

        data = f.read_bytes()
        for line in data.split(b'\r\n'):
            if len(line) < 49:
                continue
            try:
                rec = parse_kaa_line(line)
                if rec:
                    key = f"{rec['venue_code']}_{rec['race_date']}"
                    index[key] = rec
            except Exception:
                errors += 1
        file_count += 1

    print(f"[KAA] {file_count} files → {len(index):,} entries, {errors} errors")
    return index


ALL_TYPES = ['sed', 'kyi', 'srb', 'cyb', 'cha', 'kka', 'ukc', 'joa', 'kaa']


def main():
    parser = argparse.ArgumentParser(description='Build JRDB Index')
    parser.add_argument('--years', default='2020-2026',
                        help='年度範囲 (例: 2020-2025)')
    parser.add_argument('--type', choices=ALL_TYPES + ['all'], default='all',
                        help='構築対象')
    args = parser.parse_args()

    # 年度範囲パース
    if '-' in args.years:
        start, end = args.years.split('-')
        year_range = range(int(start), int(end) + 1)
    else:
        year_range = range(int(args.years), int(args.years) + 1)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    targets = ALL_TYPES if args.type == 'all' else [args.type]

    if 'sed' in targets:
        t0 = time.time()
        _save_index(build_sed_index(year_range), 'sed', t0)

    if 'kyi' in targets:
        t0 = time.time()
        _save_index(build_kyi_index(year_range), 'kyi', t0)

    if 'srb' in targets:
        t0 = time.time()
        _save_index(build_srb_index(year_range), 'srb', t0)

    if 'cyb' in targets:
        t0 = time.time()
        _save_index(build_cyb_index(year_range), 'cyb', t0)

    if 'cha' in targets:
        t0 = time.time()
        _save_index(build_cha_index(year_range), 'cha', t0)

    if 'kka' in targets:
        t0 = time.time()
        _save_index(build_kka_index(year_range), 'kka', t0)

    if 'ukc' in targets:
        t0 = time.time()
        _save_index(build_ukc_index(year_range), 'ukc', t0)

    if 'joa' in targets:
        t0 = time.time()
        _save_index(build_joa_index(year_range), 'joa', t0)

    if 'kaa' in targets:
        t0 = time.time()
        _save_index(build_kaa_index(year_range), 'kaa', t0)


if __name__ == '__main__':
    main()

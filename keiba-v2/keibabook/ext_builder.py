#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
keibabook拡張データ変換スクリプト

2つのモード:
  1. v2ネイティブ: スクレイピング済みパースデータから直接kb_ext JSON構築
     → build_kb_ext_from_scraped() (batch_scraper.pyから呼ばれる)
  2. レガシー: data2/integrated JSONからkb_ext JSON変換（過去データ一括変換用）
     → build_keibabook_ext() (CLI --year/--date)

12桁race_id → 16桁race_idの変換はvenue_name（日本語）で行う。

Usage:
    python -m keibabook.ext_builder [--year 2025] [--dry-run]
    python -m keibabook.ext_builder --date 2026-02-08 [--dry-run]
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.constants import VENUE_NAMES_TO_CODES

# data2ルート
DATA2_ROOT = Path("C:/KEIBA-CICD/data2")


def convert_race_id_12_to_16(
    race_id_12: str, date_str: str, venue_name: str,
) -> Optional[str]:
    """
    12桁race_id → 16桁race_idに変換。

    12桁: YYYYKKJJNNRR  (年4+回2+場所(keibabook独自)2+日2+R2)
    16桁: YYYYMMDDJJKKNNRR (年4+月2+日2+場所(JRA-VAN)2+回2+日次2+R2)

    keibabookとJRA-VANの場所コードは異なるため、
    venue_name（日本語場所名）からJRA-VANコードに変換する。
    """
    if not race_id_12 or len(race_id_12) != 12:
        return None

    year = race_id_12[0:4]
    kai = race_id_12[4:6]
    # race_id_12[6:8] はkeibabook独自場所コード（JRA-VANとは異なる）
    nichi = race_id_12[8:10]
    race_num = race_id_12[10:12]

    # venue_name → JRA-VAN場所コード
    jv_venue = VENUE_NAMES_TO_CODES.get(venue_name, '')
    if not jv_venue:
        return None

    # 日付パース
    date_clean = date_str.replace('/', '-')
    parts = date_clean.split('-')
    if len(parts) != 3:
        return None

    mm = parts[1].zfill(2)
    dd = parts[2].zfill(2)

    return f"{year}{mm}{dd}{jv_venue}{kai}{nichi}{race_num}"


def extract_training_arrow_value(arrow: str) -> int:
    """training_arrowを数値に変換（MLで使用）"""
    mapping = {'↑': 2, '↗': 1, '→': 0, '↘': -1, '↓': -2}
    return mapping.get(arrow, 0)


def extract_keibabook_entry(entry: dict) -> dict:
    """integrated JSONの1エントリからkeibabook固有フィールドを抽出"""
    ed = entry.get('entry_data', {})
    td = entry.get('training_data', {})
    sc = entry.get('stable_comment', {})
    pri = entry.get('previous_race_interview', {})
    result = entry.get('result', {})

    # ratingをfloatに変換
    rating_str = ed.get('rating', '')
    rating = None
    if rating_str and rating_str != '-':
        try:
            rating = float(rating_str)
        except (ValueError, TypeError):
            pass

    # ai_indexをfloatに変換
    ai_str = ed.get('ai_index', '')
    ai_index = None
    if ai_str and ai_str != '-':
        try:
            ai_index = float(ai_str)
        except (ValueError, TypeError):
            pass

    # odds_rankをintに変換
    odds_rank_str = ed.get('odds_rank', '')
    odds_rank = 0
    if odds_rank_str:
        try:
            odds_rank = int(odds_rank_str)
        except (ValueError, TypeError):
            pass

    ext = {
        # マーク系
        'honshi_mark': ed.get('honshi_mark', ''),
        'mark_point': ed.get('mark_point', 0),
        'marks_by_person': ed.get('marks_by_person', {}),
        'aggregate_mark_point': ed.get('aggregate_mark_point', 0),
        # AI/オッズ
        'ai_index': ai_index,
        'ai_rank': ed.get('ai_rank', ''),
        'odds_rank': odds_rank,
        # レーティング
        'rating': rating,
        # コメント
        'short_comment': ed.get('short_comment', ''),
        # 調教
        'training_arrow': td.get('training_arrow', ''),
        'training_arrow_value': extract_training_arrow_value(td.get('training_arrow', '')),
        'training_data': {
            'short_review': td.get('short_review', ''),
            'attack_explanation': td.get('attack_explanation', ''),
            'evaluation': td.get('evaluation', ''),
            'training_load': td.get('training_load', ''),
            'training_rank': td.get('training_rank', ''),
        },
        # 厩舎コメント
        'stable_comment': {
            'comment': sc.get('comment', ''),
        },
        # 寸評（結果）
        'sunpyo': result.get('sunpyo', '') if result else '',
        # 前走インタビュー
        'previous_race_interview': {
            'interview': pri.get('interview', ''),
            'next_race_memo': pri.get('next_race_memo', ''),
        },
    }

    return ext


# ============================================================
# v2ネイティブ: パース済みデータから直接kb_ext構築
# ============================================================

def _safe_float(val, default=None):
    """文字列をfloatに安全変換"""
    if val is None or val == '' or val == '-':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    """文字列をintに安全変換"""
    if val is None or val == '' or val == '-':
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _build_entry_from_scraped(
    horse: dict,
    cyokyo_horse: Optional[dict] = None,
    danwa_entry: Optional[dict] = None,
    syoin_entry: Optional[dict] = None,
    paddok_entry: Optional[dict] = None,
    seiseki_entry: Optional[dict] = None,
) -> dict:
    """パース済みデータから1馬分のkb_extエントリを構築。

    出力フィールドはextract_keibabook_entry()と同一形式。
    """
    # 出馬表から
    rating = _safe_float(horse.get('レイティング'))
    ai_index = _safe_float(horse.get('AI指数'))
    odds_rank = _safe_int(horse.get('人気'))

    # 調教データ（v2 cyokyo_parser出力）
    training_arrow = ""
    short_review = ""
    attack_explanation = ""
    if cyokyo_horse:
        training_arrow = cyokyo_horse.get('training_arrow', '')
        short_review = cyokyo_horse.get('short_review', '')
        attack_explanation = cyokyo_horse.get('attack_explanation', '')

    # 談話
    stable_comment = ""
    if danwa_entry:
        stable_comment = danwa_entry.get('厩舎の話', '') or danwa_entry.get('談話', '') or danwa_entry.get('コメント', '')

    # 前走インタビュー
    interview = ""
    next_race_memo = ""
    if syoin_entry:
        interview = syoin_entry.get('interview', '')
        next_race_memo = syoin_entry.get('next_race_memo', '')

    # 成績（寸評）
    sunpyo = ""
    if seiseki_entry:
        sunpyo = seiseki_entry.get('sunpyo', '')

    ext = {
        # マーク系
        'honshi_mark': horse.get('本誌印', ''),
        'mark_point': horse.get('本誌印ポイント', 0),
        'marks_by_person': horse.get('marks_by_person', {}),
        'aggregate_mark_point': horse.get('総合印ポイント', 0),
        # AI/オッズ
        'ai_index': ai_index,
        'ai_rank': horse.get('AI指数ランク', ''),
        'odds_rank': odds_rank,
        # レーティング
        'rating': rating,
        # コメント
        'short_comment': horse.get('短評', ''),
        # 調教
        'training_arrow': training_arrow,
        'training_arrow_value': extract_training_arrow_value(training_arrow),
        'training_data': {
            'short_review': short_review,
            'attack_explanation': attack_explanation,
            'evaluation': '',
            'training_load': '',
            'training_rank': '',
        },
        # 厩舎コメント
        'stable_comment': {
            'comment': stable_comment,
        },
        # 寸評（結果）
        'sunpyo': sunpyo,
        # 前走インタビュー
        'previous_race_interview': {
            'interview': interview,
            'next_race_memo': next_race_memo,
        },
    }

    return ext


def build_kb_ext_from_scraped(
    race_id_12: str,
    venue_name: str,
    date_str: str,
    syutuba: dict,
    cyokyo_detail: Optional[dict] = None,
    danwa: Optional[dict] = None,
    syoin: Optional[dict] = None,
    paddok: Optional[dict] = None,
    seiseki: Optional[dict] = None,
) -> Optional[Tuple[str, dict]]:
    """パース済みデータからkb_ext JSONを構築。

    Args:
        race_id_12: 12桁race_id
        venue_name: 日本語場所名（nitteiのkaisaiキーから抽出）
        date_str: YYYY-MM-DD
        syutuba: parse_syutuba_html()の出力
        cyokyo_detail: parse_cyokyo_html()の出力（v2詳細版）
        danwa: parse_danwa_html()の出力
        syoin: parse_syoin_html()の出力
        paddok: parse_paddok_html()の出力
        seiseki: parse_seiseki_html()の出力

    Returns:
        (race_id_16, kb_ext_dict) or None
    """
    race_id_16 = convert_race_id_12_to_16(race_id_12, date_str, venue_name)
    if not race_id_16:
        return None

    horses = syutuba.get('horses', [])
    if not horses:
        return None

    # 調教データを馬番→dictのマップに
    cyokyo_map: Dict[int, dict] = {}
    if cyokyo_detail:
        for h in cyokyo_detail.get('horses', []):
            num = h.get('horse_number')
            if num:
                cyokyo_map[int(num)] = h

    # 談話を馬番マップに
    danwa_map: Dict[str, dict] = {}
    if danwa:
        for d in danwa.get('danwa_data', []):
            bano = d.get('馬番', '')
            if bano:
                danwa_map[str(bano)] = d

    # 前走インタビューを馬番マップに
    syoin_map: Dict[int, dict] = {}
    if syoin:
        for iv in syoin.get('interviews', []):
            num = iv.get('horse_number')
            if num:
                syoin_map[int(num)] = iv

    # パドックを馬番マップに
    paddok_map: Dict[int, dict] = {}
    if paddok:
        for pe in paddok.get('paddock_evaluations', []):
            num = pe.get('horse_number')
            if num:
                paddok_map[int(num)] = pe

    # 成績を馬番マップに（着順から馬番を推定）
    seiseki_map: Dict[str, dict] = {}
    if seiseki:
        for r in seiseki.get('results', []):
            bano = r.get('馬番', '')
            if bano:
                seiseki_map[str(bano)] = r

    # エントリ構築
    entries: Dict[str, dict] = {}
    for horse in horses:
        umaban = str(horse.get('馬番', ''))
        if not umaban or not umaban.isdigit():
            continue

        umaban_int = int(umaban)
        entries[umaban] = _build_entry_from_scraped(
            horse=horse,
            cyokyo_horse=cyokyo_map.get(umaban_int),
            danwa_entry=danwa_map.get(umaban),
            syoin_entry=syoin_map.get(umaban_int),
            paddok_entry=paddok_map.get(umaban_int),
            seiseki_entry=seiseki_map.get(umaban),
        )

    # 展開データ
    tenkai = syutuba.get('tenkai_data')
    pace = ""
    if tenkai and tenkai.get('pace'):
        pace = tenkai['pace']

    kb_ext = {
        'race_id': race_id_16,
        'race_id_12': race_id_12,
        'date': date_str,
        'entries': entries,
        'analysis': {
            'expected_pace': pace,
        },
        'tenkai_data': tenkai if tenkai else None,
        'race_comment': syutuba.get('race_comment', ''),
    }

    return race_id_16, kb_ext


def save_kb_ext(race_id_16: str, kb_ext: dict, date_str: str) -> Path:
    """kb_ext JSONをdata3/keibabook/に保存。

    Returns:
        保存先Path
    """
    parts = date_str.split('-')
    out_dir = config.keibabook_dir() / parts[0] / parts[1] / parts[2]
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"kb_ext_{race_id_16}.json"
    out_path.write_text(
        json.dumps(kb_ext, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return out_path


def update_kb_ext_field(race_id_16: str, date_str: str, updates: dict) -> bool:
    """既存kb_extの特定フィールドを更新（paddok/seiseki後の部分更新用）。

    Args:
        race_id_16: 16桁race_id
        date_str: YYYY-MM-DD
        updates: {umaban: {field: value, ...}, ...}

    Returns:
        更新成功かどうか
    """
    parts = date_str.split('-')
    kb_path = config.keibabook_dir() / parts[0] / parts[1] / parts[2] / f"kb_ext_{race_id_16}.json"

    if not kb_path.exists():
        return False

    with open(kb_path, encoding='utf-8') as f:
        kb_ext = json.load(f)

    entries = kb_ext.get('entries', {})
    updated = False

    for umaban, fields in updates.items():
        if umaban in entries:
            entries[umaban].update(fields)
            updated = True

    if updated:
        kb_path.write_text(
            json.dumps(kb_ext, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    return updated


# ============================================================
# レガシー: data2 integrated JSONからの変換（後方互換）
# ============================================================

def convert_integrated_json(integrated_path: Path) -> Optional[Tuple[str, dict]]:
    """1つのintegrated JSONをkb_ext JSONに変換"""
    with open(integrated_path, encoding='utf-8') as f:
        data = json.load(f)

    meta = data.get('meta', {})
    race_info = data.get('race_info', {})
    race_id_12 = meta.get('race_id', '')
    date_str = race_info.get('date', '')

    venue_name = race_info.get('venue', '')

    if not race_id_12 or not date_str:
        return None

    # 12桁→16桁変換（venue_nameでJRA-VAN場所コードに変換）
    race_id_16 = convert_race_id_12_to_16(race_id_12, date_str, venue_name)
    if not race_id_16:
        return None

    # エントリ抽出
    entries = {}
    for entry in data.get('entries', []):
        umaban = str(entry.get('horse_number', ''))
        if not umaban:
            continue
        entries[umaban] = extract_keibabook_entry(entry)

    # レースレベルの情報
    analysis = data.get('analysis', {})
    tenkai = data.get('tenkai_data', {})

    kb_ext = {
        'race_id': race_id_16,
        'race_id_12': race_id_12,
        'date': date_str.replace('/', '-'),
        'entries': entries,
        # レースレベルの拡張情報
        'analysis': {
            'expected_pace': analysis.get('expected_pace', ''),
        },
        'tenkai_data': tenkai if tenkai else None,
        'race_comment': data.get('race_comment', ''),
    }

    return race_id_16, kb_ext


def build_keibabook_ext(year: int = None, date: str = None, dry_run: bool = False):
    """data2のintegrated JSONをスキャンしてkb_ext JSONに変換

    Args:
        year: 変換対象年（省略で全年）
        date: 変換対象日 YYYY-MM-DD（yearと排他）
        dry_run: 書き込みせず件数のみ表示
    """
    print(f"\n{'='*60}")
    print(f"  keibabook拡張データ変換")
    print(f"  Source: {DATA2_ROOT / 'races'}")
    print(f"  Dest:   {config.keibabook_dir()}")
    if date:
        print(f"  Date:   {date}")
    elif year:
        print(f"  Year:   {year}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # integrated JSONを検索
    if date:
        parts = date.split('-')
        if len(parts) != 3:
            print(f"ERROR: Invalid date format: {date}")
            return 0, 0
        search_path = DATA2_ROOT / "races" / parts[0] / parts[1] / parts[2]
    elif year:
        search_path = DATA2_ROOT / "races" / str(year)
    else:
        search_path = DATA2_ROOT / "races"

    if not search_path.exists():
        print(f"[Scan] Directory not found: {search_path}")
        return 0, 0

    integrated_files = sorted(search_path.rglob("integrated_*.json"))
    print(f"[Scan] Found {len(integrated_files):,} integrated JSON files")

    converted = 0
    errors = 0
    skipped = 0

    for i, ipath in enumerate(integrated_files):
        try:
            result = convert_integrated_json(ipath)
            if result is None:
                skipped += 1
                continue

            race_id_16, kb_ext = result

            if not dry_run:
                # 出力先: data3/keibabook/YYYY/MM/DD/kb_ext_{race_id_16}.json
                date = kb_ext['date']
                date_parts = date.split('-')
                out_dir = config.keibabook_dir() / date_parts[0] / date_parts[1] / date_parts[2]
                out_dir.mkdir(parents=True, exist_ok=True)

                out_path = out_dir / f"kb_ext_{race_id_16}.json"
                out_path.write_text(
                    json.dumps(kb_ext, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )

            converted += 1

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {ipath.name}: {e}")

        if (i + 1) % 2000 == 0:
            print(f"  ... {i+1:,}/{len(integrated_files):,} "
                  f"(converted={converted:,}, errors={errors})")

    elapsed = time.time() - t0

    print(f"\n[Done] {converted:,} converted, {skipped} skipped, {errors} errors")
    print(f"  Elapsed: {elapsed:.1f}s")

    if not dry_run and converted > 0:
        # サイズ確認
        kb_dir = config.keibabook_dir()
        total_size = sum(f.stat().st_size for f in kb_dir.rglob("*.json"))
        print(f"  Output: {kb_dir}")
        print(f"  Size:   {total_size / 1024 / 1024:.1f} MB")

    return converted, errors


def verify_conversion():
    """変換結果を検証: data3のraceJSONとkb_extが馬番で対応するか確認"""
    print("\n[Verify] Checking kb_ext <-> race JSON alignment...")

    kb_dir = config.keibabook_dir()
    kb_files = sorted(kb_dir.rglob("kb_ext_*.json"))[:10]

    for kb_path in kb_files:
        with open(kb_path, encoding='utf-8') as f:
            kb = json.load(f)

        race_id = kb['race_id']
        date_parts = kb['date'].split('-')
        race_path = (config.races_dir() / date_parts[0] / date_parts[1] /
                     date_parts[2] / f"race_{race_id}.json")

        if not race_path.exists():
            print(f"  WARN: No race JSON for {race_id}")
            continue

        with open(race_path, encoding='utf-8') as f:
            race = json.load(f)

        # 馬番の照合
        race_umabans = {str(e['umaban']) for e in race.get('entries', [])}
        kb_umabans = set(kb.get('entries', {}).keys())

        if race_umabans == kb_umabans:
            # ratingの有無確認
            sample_umaban = list(kb_umabans)[0] if kb_umabans else None
            rating = kb['entries'][sample_umaban].get('rating') if sample_umaban else None
            print(f"  OK: {race_id} - {len(race_umabans)} entries match, "
                  f"rating={rating}")
        else:
            only_race = race_umabans - kb_umabans
            only_kb = kb_umabans - race_umabans
            print(f"  MISMATCH: {race_id} race_only={only_race} kb_only={only_kb}")


def main():
    parser = argparse.ArgumentParser(description='keibabook拡張データ変換')
    parser.add_argument('--year', type=int, help='変換対象年（省略で全年）')
    parser.add_argument('--date', default=None, help='変換対象日 (YYYY-MM-DD) インクリメンタルモード')
    parser.add_argument('--dry-run', action='store_true', help='書き込みせず件数のみ表示')
    parser.add_argument('--verify', action='store_true', help='変換結果の検証')
    args = parser.parse_args()

    if args.date and args.year:
        print("ERROR: --date and --year are mutually exclusive")
        sys.exit(1)

    if args.verify:
        verify_conversion()
        return

    converted, errors = build_keibabook_ext(
        year=args.year, date=args.date, dry_run=args.dry_run,
    )

    if not args.dry_run and converted > 0:
        verify_conversion()


if __name__ == '__main__':
    main()

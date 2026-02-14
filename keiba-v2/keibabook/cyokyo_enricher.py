#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教データ補強スクリプト

既存のkb_ext JSONに対して、debug HTMLから詳細調教セッションデータを追加する。
追い切りタイム、脚色、併せ馬、休養間隔などの情報をkb_extに組み込む。

データフロー:
  data2/debug/cyokyo_{race_id_12}_{timestamp}_requests.html
    → cyokyo_parser.py で詳細パース
    → kb_ext JSON の各エントリに cyokyo_detail フィールドを追加

Usage:
    python -m keibabook.cyokyo_enricher [--dry-run] [--year 2025]
    python -m keibabook.cyokyo_enricher --date 2026-02-08
    python -m keibabook.cyokyo_enricher --reparse-only  # HTMLパースのみ(kb_ext更新なし)
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from keibabook.cyokyo_parser import parse_cyokyo_html, extract_oikiri_summary

# debug HTMLの場所
DEBUG_DIR = config.debug_dir()


def build_debug_html_index(year: Optional[int] = None) -> dict:
    """
    debug HTMLファイルをインデクス化。

    同一race_idに複数HTMLがある場合、最新タイムスタンプのものを使用。

    Returns:
        dict: {race_id_12: Path} のマッピング
    """
    pattern = "cyokyo_*.html"
    html_files = sorted(DEBUG_DIR.glob(pattern))

    index = {}  # race_id_12 -> (timestamp, path)
    for path in html_files:
        # ファイル名: cyokyo_{race_id_12}_{YYYYMMDD}_{HHMMSS}_requests.html
        m = re.match(r"cyokyo_(\d{12})_(\d{8})_(\d{6})_requests\.html", path.name)
        if not m:
            continue
        race_id_12 = m.group(1)
        timestamp = m.group(2) + m.group(3)  # YYYYMMDDHHMMSS

        # 年フィルタ
        if year and not race_id_12.startswith(str(year)):
            continue

        # 最新タイムスタンプを保持
        if race_id_12 not in index or timestamp > index[race_id_12][0]:
            index[race_id_12] = (timestamp, path)

    # タプルからPathだけ取り出す
    return {rid: path for rid, (_, path) in index.items()}


def build_kb_ext_index() -> dict:
    """
    既存のkb_ext JSONをrace_id_12でインデクス化。

    高速化: ファイル先頭からrace_id_12を正規表現で抽出（json.load不要）。

    Returns:
        dict: {race_id_12: Path} のマッピング
    """
    kb_dir = config.keibabook_dir()
    if not kb_dir.exists():
        return {}

    # race_id_12はJSON先頭付近にある
    rid12_re = re.compile(r'"race_id_12"\s*:\s*"(\d{12})"')

    index = {}
    for kb_path in kb_dir.rglob("kb_ext_*.json"):
        try:
            with open(kb_path, encoding="utf-8") as f:
                head = f.read(300)  # 先頭300byteで十分
            m = rid12_re.search(head)
            if m:
                index[m.group(1)] = kb_path
        except Exception:
            continue
    return index


def enrich_kb_ext(
    kb_ext_path: Path,
    html_path: Path,
    dry_run: bool = False,
) -> bool:
    """
    1つのkb_ext JSONに詳細調教データを追加。

    kb_ext.entries[umaban] に以下を追加:
      - cyokyo_detail: {
          sessions: [...],
          oikiri_summary: {...},
          rest_period: str,
          horse_code: str,
        }
    """
    # kb_ext読み込み
    with open(kb_ext_path, encoding="utf-8") as f:
        kb_ext = json.load(f)

    race_id_12 = kb_ext.get("race_id_12", "")

    # HTML読み込み&パース
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    parsed = parse_cyokyo_html(html, race_id_12)
    horses = parsed.get("horses", [])

    if not horses:
        return False

    entries = kb_ext.get("entries", {})
    enriched_count = 0

    for horse in horses:
        umaban = str(horse.get("horse_number", ""))
        if not umaban or umaban not in entries:
            continue

        # 追い切りサマリーを計算
        summary = extract_oikiri_summary(horse)

        # cyokyo_detailを追加
        entries[umaban]["cyokyo_detail"] = {
            "horse_code": horse.get("horse_code", ""),
            "sessions": horse.get("sessions", []),
            "rest_period": horse.get("rest_period", ""),
            "oikiri_summary": summary,
        }

        # attack_explanation / short_review をtraining_dataにも反映
        attack_exp = horse.get("attack_explanation", "")
        if attack_exp and "training_data" in entries[umaban]:
            entries[umaban]["training_data"]["attack_explanation"] = attack_exp
        short_rev = horse.get("short_review", "")
        if short_rev and "training_data" in entries[umaban]:
            entries[umaban]["training_data"]["short_review"] = short_rev

        enriched_count += 1

    if enriched_count == 0:
        return False

    if not dry_run:
        with open(kb_ext_path, "w", encoding="utf-8") as f:
            json.dump(kb_ext, f, ensure_ascii=False, indent=2)

    return True


def run_enrichment(
    year: Optional[int] = None,
    date: Optional[str] = None,
    dry_run: bool = False,
    reparse_only: bool = False,
):
    """メインのバッチ処理。"""
    print(f"\n{'='*60}")
    print(f"  調教データ補強 (cyokyo_enricher)")
    print(f"  Debug HTML: {DEBUG_DIR}")
    print(f"  kb_ext dir: {config.keibabook_dir()}")
    if date:
        print(f"  Date filter: {date}")
    elif year:
        print(f"  Year filter: {year}")
    print(f"  Dry run: {dry_run}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # Step 1: debug HTMLインデックス構築
    print("[1/3] Building debug HTML index...")
    filter_year = year
    if date:
        filter_year = int(date.split("-")[0])
    html_index = build_debug_html_index(year=filter_year)
    print(f"  Found {len(html_index):,} unique cyokyo HTML files")

    if reparse_only:
        # パースのみモード: 統計情報を表示
        print("\n[reparse-only] Parsing all HTML files...")
        success = 0
        errors = 0
        total_sessions = 0
        total_oikiri = 0
        for i, (race_id_12, path) in enumerate(html_index.items()):
            try:
                with open(path, encoding="utf-8") as f:
                    html = f.read()
                data = parse_cyokyo_html(html, race_id_12)
                for h in data.get("horses", []):
                    total_sessions += len(h.get("sessions", []))
                    total_oikiri += sum(
                        1 for s in h.get("sessions", []) if s.get("is_oikiri")
                    )
                success += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  ERROR: {path.name}: {e}")
            if (i + 1) % 2000 == 0:
                print(f"  ... {i+1:,}/{len(html_index):,}")

        elapsed = time.time() - t0
        print(f"\n[Done] {success:,} parsed, {errors} errors")
        print(f"  Total sessions: {total_sessions:,}")
        print(f"  Total oikiri: {total_oikiri:,}")
        print(f"  Elapsed: {elapsed:.1f}s")
        return

    # Step 2: kb_extインデックス構築
    print("[2/3] Building kb_ext index...")
    kb_index = build_kb_ext_index()
    print(f"  Found {len(kb_index):,} kb_ext JSON files")

    # dateフィルタ（パスベースで高速）
    if date:
        parts = date.split("-")
        # kb_ext path: data3/keibabook/YYYY/MM/DD/kb_ext_*.json
        date_path_fragment = f"{parts[0]}/{parts[1]}/{parts[2]}"
        filtered_kb = {
            rid: p for rid, p in kb_index.items()
            if date_path_fragment in str(p).replace("\\", "/")
        }
        kb_index = filtered_kb
        print(f"  After date filter: {len(kb_index):,}")

    # Step 3: マッチング & 補強
    print("[3/3] Enriching kb_ext with cyokyo detail...")
    matched = 0
    enriched = 0
    no_html = 0
    errors = 0

    for i, (race_id_12, kb_path) in enumerate(kb_index.items()):
        if race_id_12 not in html_index:
            no_html += 1
            continue

        matched += 1
        html_path = html_index[race_id_12]

        try:
            if enrich_kb_ext(kb_path, html_path, dry_run=dry_run):
                enriched += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {kb_path.name}: {e}")

        if (i + 1) % 2000 == 0:
            print(f"  ... {i+1:,}/{len(kb_index):,} "
                  f"(matched={matched}, enriched={enriched}, errors={errors})")

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Results:")
    print(f"  kb_ext files:   {len(kb_index):,}")
    print(f"  HTML available: {matched:,} ({matched/max(len(kb_index),1)*100:.1f}%)")
    print(f"  No HTML found:  {no_html:,}")
    print(f"  Enriched:       {enriched:,}")
    print(f"  Errors:         {errors}")
    print(f"  Elapsed:        {elapsed:.1f}s")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="調教データ補強")
    parser.add_argument("--year", type=int, help="対象年")
    parser.add_argument("--date", help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="書き込みなし")
    parser.add_argument("--reparse-only", action="store_true",
                        help="HTMLパースのみ（統計表示、kb_ext更新なし）")
    args = parser.parse_args()

    run_enrichment(
        year=args.year,
        date=args.date,
        dry_run=args.dry_run,
        reparse_only=args.reparse_only,
    )


if __name__ == "__main__":
    main()

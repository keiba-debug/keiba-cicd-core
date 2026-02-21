#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
発走状況バックフィル

既存kb_extに発走状況データ（出遅れ等）を追加取得するスクリプト。
成績ページから発走状況のみを抽出し、既存kb_extを更新する。

Usage:
    python -m keibabook.backfill_hassou --date 2026-02-15
    python -m keibabook.backfill_hassou --start 2025-01-01 --end 2025-12-31
    python -m keibabook.backfill_hassou --start 2020-01-01 --end 2026-02-21 --dry-run
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from keibabook.scraper import KeibabookScraper
from keibabook.parsers.seiseki_parser import _extract_race_extras, parse_hassou_text
from keibabook.ext_builder import update_kb_ext_field, update_kb_ext_race_level

from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _find_kb_ext_files(start_date: str, end_date: str) -> list[dict]:
    """日付範囲内のkb_extファイルを検索"""
    kb_dir = config.keibabook_dir()
    files = []

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        y, m, d = current.strftime("%Y"), current.strftime("%m"), current.strftime("%d")
        day_dir = kb_dir / y / m / d

        if day_dir.exists():
            for kb_path in sorted(day_dir.glob("kb_ext_*.json")):
                race_id_16 = kb_path.stem.replace("kb_ext_", "")
                try:
                    with open(kb_path, encoding="utf-8") as f:
                        kb_data = json.load(f)
                    race_id_12 = kb_data.get("race_id_12", "")
                    if not race_id_12:
                        continue
                    # race_extrasが既にあるならスキップ
                    if kb_data.get("race_extras", {}).get("hassou"):
                        continue
                    files.append({
                        "path": kb_path,
                        "race_id_16": race_id_16,
                        "race_id_12": race_id_12,
                        "date": f"{y}-{m}-{d}",
                    })
                except Exception:
                    continue

        current += timedelta(days=1)

    return files


def backfill_hassou(
    start_date: str,
    end_date: str,
    delay: float = 1.5,
    dry_run: bool = False,
    limit: int = 0,
):
    """発走状況データをバックフィル"""
    t0 = time.time()

    # 対象ファイル検索
    logger.info(f"Scanning kb_ext files: {start_date} ~ {end_date}...")
    targets = _find_kb_ext_files(start_date, end_date)
    logger.info(f"  Found {len(targets)} races needing hassou data")

    if limit > 0:
        targets = targets[:limit]
        logger.info(f"  Limited to {limit} races")

    if dry_run:
        logger.info("[DRY RUN] Would fetch the following races:")
        for t in targets[:20]:
            logger.info(f"  {t['date']} {t['race_id_12']} ({t['race_id_16']})")
        if len(targets) > 20:
            logger.info(f"  ... and {len(targets) - 20} more")
        return

    scraper = KeibabookScraper(delay=delay)
    updated = 0
    errors = 0
    no_data = 0

    for i, target in enumerate(targets):
        rid_12 = target["race_id_12"]
        rid_16 = target["race_id_16"]
        date_str = target["date"]

        try:
            html = scraper.scrape_seiseki(rid_12)
            soup = BeautifulSoup(html, "html.parser")
            extras = _extract_race_extras(soup)

            hassou = extras.get("hassou", "")

            if extras:
                # race_extras をレースレベルに保存
                update_kb_ext_race_level(rid_16, date_str, {"race_extras": extras})

                # 出遅れ馬にフラグ設定
                if hassou:
                    slow_starts = parse_hassou_text(hassou)
                    if slow_starts:
                        field_updates = {}
                        for ss in slow_starts:
                            bano = str(ss["umaban"])
                            field_updates[bano] = {"is_slow_start": True}
                        update_kb_ext_field(rid_16, date_str, field_updates)
                        logger.info(f"  [{i+1}/{len(targets)}] {rid_12}: 発走={hassou[:30]} 出遅{len(slow_starts)}")
                    else:
                        logger.info(f"  [{i+1}/{len(targets)}] {rid_12}: 発走={hassou[:30]} (パース不能)")
                        no_data += 1
                else:
                    logger.info(f"  [{i+1}/{len(targets)}] {rid_12}: extras={list(extras.keys())} (発走なし)")
                    no_data += 1
                updated += 1
            else:
                no_data += 1
                if (i + 1) % 50 == 0:
                    logger.info(f"  [{i+1}/{len(targets)}] {rid_12}: データなし")

        except Exception as e:
            errors += 1
            logger.error(f"  [{i+1}/{len(targets)}] {rid_12}: {e}")

    elapsed = time.time() - t0
    logger.info(f"\n{'='*60}")
    logger.info(f"  Backfill完了")
    logger.info(f"  Updated: {updated}, NoData: {no_data}, Errors: {errors}")
    logger.info(f"  Elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    logger.info(f"{'='*60}")


def _date_range(start: str, end: str) -> tuple[str, str]:
    return start, end


def main():
    parser = argparse.ArgumentParser(description="発走状況バックフィル")
    parser.add_argument("--date", help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--start", help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", help="終了日 (YYYY-MM-DD)")
    parser.add_argument("--delay", type=float, default=1.5, help="リクエスト間隔秒")
    parser.add_argument("--dry-run", action="store_true", help="実際の取得はせず対象レースのみ表示")
    parser.add_argument("--limit", type=int, default=0, help="最大処理件数 (0=無制限)")
    args = parser.parse_args()

    if args.date:
        start_date = end_date = args.date.replace("/", "-")
    elif args.start and args.end:
        start_date = args.start.replace("/", "-")
        end_date = args.end.replace("/", "-")
    else:
        print("ERROR: --date または --start/--end を指定してください")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  発走状況バックフィル")
    print(f"  期間: {start_date} ~ {end_date}")
    print(f"  Delay: {args.delay}s")
    if args.dry_run:
        print(f"  [DRY RUN]")
    print(f"{'='*60}\n")

    backfill_hassou(
        start_date=start_date,
        end_date=end_date,
        delay=args.delay,
        dry_run=args.dry_run,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""スピード指数バッチ取得スクリプト

既存のkb_ext JSONに speed_indexes フィールドを追加する。
kb_ext内の race_id_12 を使ってkeibabookのスピード指数ページを取得し、
パースして各馬のスピード指数を kb_ext に書き込む。

Usage:
    python -m keibabook.batch_speed_scrape [--dry-run] [--limit N]
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# .env読み込み
env_path = Path(__file__).resolve().parents[1] / '.env'
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

from keibabook.scraper import KeibabookScraper
from keibabook.parsers.speed_parser import parse_speed_html

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

KB_EXT_ROOT = Path(r"C:\KEIBA-CICD\data3\keibabook")


def find_kb_ext_files() -> list:
    """speed_indexes未取得のkb_extファイルを検索"""
    files = []
    for json_path in sorted(KB_EXT_ROOT.rglob("kb_ext_*.json")):
        files.append(json_path)
    return files


def needs_speed_update(kb_ext: dict) -> bool:
    """speed_indexesの更新が必要かチェック"""
    entries = kb_ext.get('entries', {})
    if not entries:
        return False
    # 1つでもspeed_indexesキーがないか、全てNoneなら更新必要
    for entry in entries.values():
        if 'speed_indexes' in entry and entry['speed_indexes'] is not None:
            return False  # 既にデータあり
    return True


def update_kb_ext_with_speed(kb_ext: dict, speed_data: dict) -> bool:
    """kb_extにスピード指数を追加

    Returns:
        True if any update was made
    """
    if not speed_data or not speed_data.get('horses'):
        return False

    entries = kb_ext.get('entries', {})
    speed_map = {}
    for h in speed_data['horses']:
        bano = h.get('馬番', '')
        if bano:
            speed_map[str(bano)] = h

    updated = False
    for umaban, entry in entries.items():
        speed_entry = speed_map.get(str(umaban))
        if speed_entry:
            entry['speed_indexes'] = speed_entry.get('speed_indexes')
            updated = True
        elif 'speed_indexes' not in entry:
            entry['speed_indexes'] = None

    return updated


def main():
    parser = argparse.ArgumentParser(description='スピード指数バッチ取得')
    parser.add_argument('--dry-run', action='store_true', help='実際にスクレイプせず件数のみ表示')
    parser.add_argument('--limit', type=int, default=0, help='処理する最大ファイル数（0=全件）')
    parser.add_argument('--delay', type=float, default=1.5, help='リクエスト間隔（秒）')
    args = parser.parse_args()

    logger.info("スピード指数バッチ取得を開始")

    # kb_extファイル一覧
    all_files = find_kb_ext_files()
    logger.info(f"kb_extファイル数: {len(all_files)}")

    # 更新が必要なファイルを特定
    need_update = []
    already_done = 0
    no_race_id_12 = 0

    for fpath in all_files:
        try:
            with open(fpath, encoding='utf-8') as f:
                kb_ext = json.load(f)
            if not kb_ext.get('race_id_12'):
                no_race_id_12 += 1
                continue
            if needs_speed_update(kb_ext):
                need_update.append((fpath, kb_ext))
            else:
                already_done += 1
        except Exception:
            continue

    logger.info(f"更新必要: {len(need_update)}, 取得済み: {already_done}, race_id_12なし: {no_race_id_12}")

    if args.dry_run:
        logger.info("[dry-run] 終了")
        return

    if not need_update:
        logger.info("更新対象なし。終了。")
        return

    # 処理上限
    targets = need_update[:args.limit] if args.limit > 0 else need_update
    logger.info(f"処理対象: {len(targets)} ファイル")

    scraper = KeibabookScraper()
    success = 0
    fail = 0
    skip = 0

    for i, (fpath, kb_ext) in enumerate(targets):
        rid_12 = kb_ext['race_id_12']
        rid_16 = kb_ext.get('race_id', 'unknown')

        try:
            html = scraper.scrape_speed(rid_12)
            time.sleep(args.delay)

            if len(html) < 5000:
                # スケジュールページが返った場合はスキップ
                skip += 1
                if skip <= 3:
                    logger.warning(f"  [{i+1}/{len(targets)}] {rid_12}: HTML短すぎ({len(html)}), スキップ")
                continue

            speed_data = parse_speed_html(html, rid_12)

            if update_kb_ext_with_speed(kb_ext, speed_data):
                with open(fpath, 'w', encoding='utf-8') as f:
                    json.dump(kb_ext, f, ensure_ascii=False, indent=2)
                success += 1
            else:
                skip += 1

        except Exception as e:
            fail += 1
            if fail <= 5:
                logger.error(f"  [{i+1}/{len(targets)}] {rid_12}: {e}")

        if (i + 1) % 50 == 0:
            logger.info(f"  進捗: {i+1}/{len(targets)} (成功={success}, スキップ={skip}, 失敗={fail})")

    logger.info(f"\n完了: 成功={success}, スキップ={skip}, 失敗={fail}")


if __name__ == '__main__':
    main()

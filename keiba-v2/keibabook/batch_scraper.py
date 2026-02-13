#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
keibabookバッチスクレイパー (v2)

keibabook.co.jpからデータを取得し、kb_ext JSONをdata3/keibabookに直接構築する。
data2を経由しない一本道パイプライン。

Usage:
    python -m keibabook.batch_scraper --date 2026-02-15 --types basic
    python -m keibabook.batch_scraper --date 2026-02-15 --types paddok
    python -m keibabook.batch_scraper --date 2026-02-15 --types seiseki
    python -m keibabook.batch_scraper --start 2026-02-08 --end 2026-02-09 --types basic
"""

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from keibabook.scraper import KeibabookScraper
from keibabook.parsers.nittei_parser import parse_nittei_html
from keibabook.parsers.syutuba_parser import parse_syutuba_html
from keibabook.parsers.danwa_parser import parse_danwa_html
from keibabook.parsers.syoin_parser import parse_syoin_html
from keibabook.parsers.paddok_parser import parse_paddok_html
from keibabook.parsers.seiseki_parser import parse_seiseki_html
from keibabook.parsers.babakeikou_parser import parse_babakeikou_html
from keibabook.cyokyo_parser import parse_cyokyo_html
from keibabook.parsers.speed_parser import parse_speed_html
from keibabook.ext_builder import (
    build_kb_ext_from_scraped, save_kb_ext, update_kb_ext_field,
    convert_race_id_12_to_16,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Windows stdout UTF-8対策
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _extract_venue_name(kaisai_key: str) -> str:
    """kaisaiキー（例: '1回東京1日目'）から場所名を抽出"""
    m = re.search(r"\d+回(.+?)\d+日目", kaisai_key)
    return m.group(1) if m else ""


def _save_race_info(nittei: dict, date_str: str) -> None:
    """nitteiデータをrace_info.jsonとしてdata3/races/YYYY/MM/DD/に保存。

    各レースエントリに16桁race_idも付加する（WebViewer用）。
    """
    parts = date_str.split("-")
    if len(parts) != 3:
        return
    out_dir = config.data_root() / "races" / parts[0] / parts[1] / parts[2]
    out_dir.mkdir(parents=True, exist_ok=True)

    # 16桁race_idを付加
    enriched = {}
    for kaisai_key, races in nittei.get("kaisai_data", {}).items():
        venue = _extract_venue_name(kaisai_key)
        enriched_races = []
        for race in races:
            entry = dict(race)
            rid_12 = race.get("race_id", "")
            if rid_12 and venue:
                rid_16 = convert_race_id_12_to_16(rid_12, date_str, venue)
                if rid_16:
                    entry["race_id_16"] = rid_16
            enriched_races.append(entry)
        enriched[kaisai_key] = enriched_races

    race_info = {
        "date": date_str,
        "kaisai_data": enriched,
    }
    out_path = out_dir / "race_info.json"
    out_path.write_text(
        json.dumps(race_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"  race_info.json 保存: {out_path}")


def _date_yyyymmdd_to_iso(yyyymmdd: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _date_iso_to_yyyymmdd(iso: str) -> str:
    """YYYY-MM-DD → YYYYMMDD"""
    return iso.replace("-", "")


class KeibabookBatchScraper:
    """keibabookバッチスクレイピング → kb_ext直接構築"""

    def __init__(self, delay: float = 1.0, max_workers: int = 5):
        self.delay = delay
        self.max_workers = max_workers
        self.scraper = KeibabookScraper(
            delay=delay,
            debug_html_dir=config.debug_dir(),
        )

    # ─── 日程取得 ───

    def scrape_schedule(self, date_str: str, save_info: bool = True) -> dict:
        """日程取得。date_str: YYYY-MM-DD

        Args:
            date_str: YYYY-MM-DD
            save_info: race_info.jsonを保存するか

        Returns:
            parse_nittei_html()の出力（kaisai_data含む）
        """
        yyyymmdd = _date_iso_to_yyyymmdd(date_str)
        logger.info(f"日程取得: {date_str}")
        html = self.scraper.scrape_nittei(yyyymmdd)
        data = parse_nittei_html(html, yyyymmdd)
        logger.info(f"  開催数: {data['kaisai_count']}, レース数: {data['total_races']}")

        if save_info and data["total_races"] > 0:
            _save_race_info(data, date_str)

        return data

    # ─── 前日準備 (basic) ───

    def scrape_basic(
        self,
        date_str: str,
        from_race: Optional[int] = None,
        to_race: Optional[int] = None,
        track: Optional[str] = None,
    ) -> dict:
        """前日準備: 日程→出馬表+調教+談話+前走インタビュー→kb_ext構築

        Args:
            date_str: YYYY-MM-DD
            from_race: 開始レース番号フィルタ
            to_race: 終了レース番号フィルタ
            track: 競馬場フィルタ（例: "東京"）

        Returns:
            {"success": True, "total_races": N, "built": N, "errors": N}
        """
        t0 = time.time()
        nittei = self.scrape_schedule(date_str)

        if nittei["total_races"] == 0:
            logger.info("開催なし — スキップ")
            return {"success": True, "total_races": 0, "built": 0, "errors": 0}

        # レースリスト構築
        race_tasks = []
        for kaisai_key, races in nittei["kaisai_data"].items():
            venue = _extract_venue_name(kaisai_key)
            if track and track != venue:
                continue
            for race in races:
                race_no_m = re.match(r"(\d+)", race.get("race_no", ""))
                race_no = int(race_no_m.group(1)) if race_no_m else 0
                if from_race and race_no < from_race:
                    continue
                if to_race and race_no > to_race:
                    continue
                race_tasks.append({
                    "race_id_12": race["race_id"],
                    "venue_name": venue,
                    "date_str": date_str,
                })

        total = len(race_tasks)
        logger.info(f"対象レース: {total}件")

        built = 0
        errors = 0

        # 各レースを処理（スクレイピング部分は逐次、パース/構築は高速）
        for i, task in enumerate(race_tasks):
            rid = task["race_id_12"]
            venue = task["venue_name"]
            try:
                # スクレイピング
                syutuba_html = self.scraper.scrape_syutuba(rid)
                cyokyo_html = self.scraper.scrape_cyokyo(rid, save_debug=True)
                danwa_html = self.scraper.scrape_danwa(rid)
                syoin_html = self.scraper.scrape_syoin(rid)

                # スピード指数（エラーでも続行）
                speed = None
                try:
                    speed_html = self.scraper.scrape_speed(rid)
                    speed = parse_speed_html(speed_html, rid)
                except Exception as e:
                    logger.warning(f"  speed {rid}: スキップ ({e})")

                # パース
                syutuba = parse_syutuba_html(syutuba_html, rid)
                cyokyo = parse_cyokyo_html(cyokyo_html, rid)
                danwa = parse_danwa_html(danwa_html, rid)
                syoin = parse_syoin_html(syoin_html, rid)

                # kb_ext構築
                result = build_kb_ext_from_scraped(
                    race_id_12=rid,
                    venue_name=venue,
                    date_str=date_str,
                    syutuba=syutuba,
                    cyokyo_detail=cyokyo,
                    danwa=danwa,
                    syoin=syoin,
                    speed=speed,
                )

                if result:
                    race_id_16, kb_ext = result
                    save_kb_ext(race_id_16, kb_ext, date_str)
                    built += 1
                    logger.info(f"  [{i+1}/{total}] {rid} → {race_id_16} ({len(kb_ext.get('entries',{}))}頭)")
                else:
                    errors += 1
                    logger.warning(f"  [{i+1}/{total}] {rid} — kb_ext構築失敗")

            except Exception as e:
                errors += 1
                logger.error(f"  [{i+1}/{total}] {rid} — エラー: {e}")

        elapsed = time.time() - t0
        logger.info(f"\n[basic完了] {built}件構築, {errors}件エラー ({elapsed:.1f}秒)")

        return {"success": True, "total_races": total, "built": built, "errors": errors}

    # ─── パドック取得 ───

    def scrape_paddok(
        self,
        date_str: str,
        from_race: Optional[int] = None,
        to_race: Optional[int] = None,
        track: Optional[str] = None,
    ) -> dict:
        """パドック取得→既存kb_extにパドック情報を追加更新"""
        t0 = time.time()
        nittei = self.scrape_schedule(date_str)

        if nittei["total_races"] == 0:
            return {"success": True, "total_races": 0, "updated": 0, "errors": 0}

        updated = 0
        errors = 0
        total = 0

        for kaisai_key, races in nittei["kaisai_data"].items():
            venue = _extract_venue_name(kaisai_key)
            if track and track != venue:
                continue
            for race in races:
                race_no_m = re.match(r"(\d+)", race.get("race_no", ""))
                race_no = int(race_no_m.group(1)) if race_no_m else 0
                if from_race and race_no < from_race:
                    continue
                if to_race and race_no > to_race:
                    continue
                total += 1
                rid = race["race_id"]

                try:
                    html = self.scraper.scrape_paddok(rid)
                    paddok = parse_paddok_html(html, rid)

                    # paddock_infoをkb_extに反映
                    race_id_16 = convert_race_id_12_to_16(rid, date_str, venue)
                    if race_id_16:
                        field_updates = {}
                        for pe in paddok.get("paddock_evaluations", []):
                            num = pe.get("horse_number")
                            if num:
                                field_updates[str(num)] = {
                                    "paddock_info": {
                                        "mark": pe.get("mark", ""),
                                        "mark_score": pe.get("mark_score", 0),
                                        "comment": pe.get("comment", ""),
                                    }
                                }

                        if field_updates:
                            update_kb_ext_field(race_id_16, date_str, field_updates)
                            logger.info(f"  paddok {rid}: {len(field_updates)}頭更新")
                        else:
                            logger.info(f"  paddok {rid}: データなし")
                    else:
                        logger.info(f"  paddok {rid}: race_id_16変換失敗")
                    updated += 1

                except Exception as e:
                    errors += 1
                    logger.error(f"  paddok {rid}: エラー {e}")

        elapsed = time.time() - t0
        logger.info(f"\n[paddok完了] {updated}件, {errors}件エラー ({elapsed:.1f}秒)")
        return {"success": True, "total_races": total, "updated": updated, "errors": errors}

    # ─── 成績取得 ───

    def scrape_seiseki(
        self,
        date_str: str,
        from_race: Optional[int] = None,
        to_race: Optional[int] = None,
        track: Optional[str] = None,
    ) -> dict:
        """成績取得→既存kb_extにsunpyo（寸評）を追加"""
        t0 = time.time()
        nittei = self.scrape_schedule(date_str)

        if nittei["total_races"] == 0:
            return {"success": True, "total_races": 0, "updated": 0, "errors": 0}

        updated = 0
        errors = 0
        total = 0

        for kaisai_key, races in nittei["kaisai_data"].items():
            venue = _extract_venue_name(kaisai_key)
            if track and track != venue:
                continue
            for race in races:
                race_no_m = re.match(r"(\d+)", race.get("race_no", ""))
                race_no = int(race_no_m.group(1)) if race_no_m else 0
                if from_race and race_no < from_race:
                    continue
                if to_race and race_no > to_race:
                    continue
                total += 1
                rid = race["race_id"]

                try:
                    html = self.scraper.scrape_seiseki(rid)
                    seiseki = parse_seiseki_html(html, rid)

                    # sunpyoをkb_extに反映
                    race_id_16 = convert_race_id_12_to_16(rid, date_str, venue)
                    if race_id_16:
                        field_updates = {}
                        for r in seiseki.get("results", []):
                            bano = r.get("馬番", "")
                            sunpyo = r.get("sunpyo", "")
                            if bano and sunpyo:
                                field_updates[str(bano)] = {"sunpyo": sunpyo}

                        if field_updates:
                            update_kb_ext_field(race_id_16, date_str, field_updates)
                            logger.info(f"  seiseki {rid}: sunpyo {len(field_updates)}頭更新")
                        else:
                            logger.info(f"  seiseki {rid}: sunpyoなし")
                    updated += 1

                except Exception as e:
                    errors += 1
                    logger.error(f"  seiseki {rid}: エラー {e}")

        elapsed = time.time() - t0
        logger.info(f"\n[seiseki完了] {updated}件, {errors}件エラー ({elapsed:.1f}秒)")
        return {"success": True, "total_races": total, "updated": updated, "errors": errors}

    # ─── 馬場傾向取得 ───

    def scrape_babakeikou(self, date_str: str) -> dict:
        """馬場傾向取得（全開催場）"""
        t0 = time.time()
        nittei = self.scrape_schedule(date_str)

        if nittei["total_races"] == 0:
            return {"success": True, "venues": 0}

        yyyymmdd = _date_iso_to_yyyymmdd(date_str)
        # keibabookの場所コード（JRA-VANとは異なる）
        kb_place_codes = {
            "阪神": "01", "函館": "02", "福島": "03", "新潟": "04",
            "中山": "05", "中京": "06", "小倉": "07", "京都": "08",
            "東京": "09", "札幌": "10",
        }
        fetched = 0
        for kaisai_key in nittei["kaisai_data"]:
            venue = _extract_venue_name(kaisai_key)
            code = kb_place_codes.get(venue)
            if not code:
                continue
            try:
                html = self.scraper.scrape_babakeikou(yyyymmdd, code)
                data = parse_babakeikou_html(html)
                # 馬場傾向はdata3/analysis/babaに保存（既存のbaba分析と統合可能）
                out_dir = config.data_root() / "analysis" / "baba"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"baba_{date_str}_{venue}.json"
                out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                fetched += 1
                logger.info(f"  babakeikou {venue}: {data.get('turf', {}).get('condition', '?')}")
            except Exception as e:
                logger.error(f"  babakeikou {venue}: エラー {e}")

        elapsed = time.time() - t0
        logger.info(f"\n[babakeikou完了] {fetched}場 ({elapsed:.1f}秒)")
        return {"success": True, "venues": fetched}


# ─── 日付範囲ヘルパー ───

def _date_range(start: str, end: str) -> list[str]:
    """YYYY-MM-DD の範囲リストを生成"""
    from datetime import datetime, timedelta
    dates = []
    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    while current <= end_dt:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="keibabookバッチスクレイパー (v2)")
    parser.add_argument("--date", help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--start", help="開始日 (YYYY-MM-DD) — 範囲指定")
    parser.add_argument("--end", help="終了日 (YYYY-MM-DD) — 範囲指定")
    parser.add_argument("--types", default="basic",
                        help="取得タイプ: basic|paddok|seiseki|nittei|babakeikou (カンマ区切り可)")
    parser.add_argument("--delay", type=float, default=1.0, help="リクエスト間隔秒")
    parser.add_argument("--max-workers", type=int, default=5, help="並列数")
    parser.add_argument("--from-race", type=int, help="開始レース番号フィルタ")
    parser.add_argument("--to-race", type=int, help="終了レース番号フィルタ")
    parser.add_argument("--track", help="競馬場フィルタ（例: 東京）")
    args = parser.parse_args()

    # 日付決定
    if args.start and args.end:
        dates = _date_range(args.start, args.end)
    elif args.date:
        # YYYY/MM/DD形式もサポート
        dates = [args.date.replace("/", "-")]
    else:
        print("ERROR: --date または --start/--end を指定してください")
        sys.exit(1)

    types = [t.strip() for t in args.types.split(",")]

    batch = KeibabookBatchScraper(delay=args.delay, max_workers=args.max_workers)

    print(f"\n{'='*60}")
    print(f"  keibabook v2 バッチスクレイパー")
    print(f"  日付: {dates[0]}" + (f" 〜 {dates[-1]}" if len(dates) > 1 else ""))
    print(f"  タイプ: {', '.join(types)}")
    print(f"  出力: {config.keibabook_dir()}")
    print(f"{'='*60}\n")

    for date_str in dates:
        for t in types:
            if t == "nittei":
                batch.scrape_schedule(date_str)
            elif t == "basic":
                batch.scrape_basic(
                    date_str,
                    from_race=args.from_race,
                    to_race=args.to_race,
                    track=args.track,
                )
            elif t == "paddok":
                batch.scrape_paddok(
                    date_str,
                    from_race=args.from_race,
                    to_race=args.to_race,
                    track=args.track,
                )
            elif t == "seiseki":
                batch.scrape_seiseki(
                    date_str,
                    from_race=args.from_race,
                    to_race=args.to_race,
                    track=args.track,
                )
            elif t == "babakeikou":
                batch.scrape_babakeikou(date_str)
            else:
                logger.warning(f"不明なタイプ: {t}")

    print(f"\n{'='*60}")
    print(f"  完了")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

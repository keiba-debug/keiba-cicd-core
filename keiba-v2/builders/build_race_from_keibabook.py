#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
keibabook出馬表からrace JSONを生成（SE_DATA未配信のレース前用）

レース前はJRA-VAN SE_DATAがまだ届いていないため、keibabookの出馬表ページから
馬名・騎手・調教師等を取得し、最小限のrace JSONを生成する。

SE_DATAが届いた後は build_race_master.py で上書きされる（レース結果含む完全版）。

Usage:
    python -m builders.build_race_from_keibabook --date 2026-02-14
    python -m builders.build_race_from_keibabook --date 2026-02-14 --dry-run
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.constants import VENUE_NAMES_TO_CODES
from keibabook.scraper import KeibabookScraper
from keibabook.parsers.syutuba_parser import parse_syutuba_html


def load_race_info(date: str) -> dict:
    """race_info.jsonから対象日のレース一覧を読み込む"""
    parts = date.split("-")
    path = config.races_dir() / parts[0] / parts[1] / parts[2] / "race_info.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_venue_name(kaisai_key: str) -> str:
    """開催キーから場所名を抽出: '1回東京5日目' → '東京'"""
    m = re.search(r"\d+回(.+?)\d+日目", kaisai_key)
    return m.group(1) if m else ""


def extract_track_info(race_info: dict) -> tuple:
    """race_infoのcourseフィールドからトラック種別と距離を抽出"""
    course = race_info.get("course", "")
    m = re.match(r"(芝|ダ|ダート)\s*(\d+)", course)
    if m:
        track = "芝" if m.group(1) == "芝" else "ダ"
        return track, int(m.group(2))
    return "", 0


def build_race_json_from_syutuba(
    race_id_16: str,
    race_id_12: str,
    date: str,
    venue_name: str,
    race_number: int,
    race_name: str,
    syutuba_data: dict,
) -> dict:
    """syutubaパース結果からrace JSON構造を構築"""

    venue_code = VENUE_NAMES_TO_CODES.get(venue_name, "")
    # race_id_16からkai, nichiを抽出
    kai = int(race_id_16[10:12])
    nichi = int(race_id_16[12:14])

    # syutubaのrace_infoからトラック情報
    ri = syutuba_data.get("race_info", {})
    track_type = ri.get("track", "")
    distance = ri.get("distance", 0)

    # 出走馬エントリ構築
    entries = []
    horses = syutuba_data.get("horses", [])
    for horse in horses:
        umaban_str = horse.get("馬番", "")
        if not umaban_str.isdigit():
            continue
        umaban = int(umaban_str)

        # 枠番の推定（出馬表に枠番がある場合はそれを使用）
        wakuban = 0
        waku_str = horse.get("枠番", "") or horse.get("枠", "")
        if waku_str and waku_str.isdigit():
            wakuban = int(waku_str)

        # 騎手名
        jockey_name = horse.get("騎手", "")
        # 調教師名（syutubaにはtrainer_idはあるが名前は厩舎のリンクテキスト）
        trainer_name = ""
        # 出馬表テーブルの「厩舎」列を確認
        for k in ("厩舎", "調教師", "きゅう舎"):
            if k in horse and horse[k]:
                trainer_name = horse[k]
                break

        # 性齢パース（例: "牡3" → sex_cd="1", age=3 / "牝4" → "2",4 / "セ5" → "3",5）
        sex_cd = ""
        age = 0
        seiri_str = horse.get("性齢", "")
        if seiri_str:
            sex_char = seiri_str[0] if seiri_str else ""
            if sex_char == "牡":
                sex_cd = "1"
            elif sex_char == "牝":
                sex_cd = "2"
            elif sex_char in ("セ", "騸"):
                sex_cd = "3"
            age_part = re.sub(r"[^\d]", "", seiri_str)
            if age_part:
                age = int(age_part)

        # 斤量
        futan = 0.0
        futan_str = horse.get("重量", "") or horse.get("斤量", "")
        try:
            futan = float(futan_str) if futan_str else 0.0
        except ValueError:
            pass

        entry = {
            "umaban": umaban,
            "wakuban": wakuban,
            "ketto_num": horse.get("umacd", ""),  # keibabookのhorse_code（7桁）
            "horse_name": horse.get("馬名_clean", horse.get("馬名", "")),
            "sex_cd": sex_cd,
            "age": age,
            "jockey_name": jockey_name,
            "trainer_name": trainer_name,
            "futan": futan,
            "horse_weight": 0,
            "horse_weight_diff": 0,
            "finish_position": 0,
            "time": "",
            "last_3f": 0.0,
            "last_4f": 0.0,
            "odds": 0.0,
            "popularity": 0,
            "corners": [],
            "jockey_code": "",
            "trainer_code": "",
        }
        entries.append(entry)

    entries.sort(key=lambda e: e["umaban"])

    return {
        "race_id": race_id_16,
        "date": date,
        "venue_code": venue_code,
        "venue_name": venue_name,
        "kai": kai,
        "nichi": nichi,
        "race_number": race_number,
        "distance": distance,
        "track_type": track_type,
        "track_condition": "",
        "num_runners": len(entries),
        "race_name": race_name,
        "grade": "",
        "weather": "",
        "pace": None,
        "entries": entries,
        "meta": {
            "data_version": "4.0-keibabook",
            "source": "keibabook_syutuba",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "has_keibabook_ext": True,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="keibabook出馬表からrace JSONを生成（レース前用）"
    )
    parser.add_argument("--date", required=True, help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="書き込みなし")
    parser.add_argument("--force", action="store_true",
                        help="既存race JSONがあっても上書き")
    args = parser.parse_args()

    date = args.date
    t0 = time.time()

    print(f"\n{'='*60}")
    print(f"  Race JSON Builder (keibabook syutuba)")
    print(f"  Date: {date}")
    print(f"  Output: {config.races_dir()}")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Force: {args.force}")
    print(f"{'='*60}\n")

    # race_info.json読み込み
    race_info = load_race_info(date)
    if not race_info:
        print("ERROR: race_info.json が見つかりません。先に基本情報構築を実行してください。")
        sys.exit(1)

    kaisai_data = race_info.get("kaisai_data", {})
    total_races = sum(len(races) for races in kaisai_data.values())
    print(f"対象レース: {total_races}件")

    # 既存race JSONの確認（forceでない場合はスキップ）
    parts = date.split("-")
    race_dir = config.races_dir() / parts[0] / parts[1] / parts[2]

    # スクレイパー初期化
    scraper = KeibabookScraper()

    created = 0
    skipped = 0
    errors = 0

    for kaisai_key, races in kaisai_data.items():
        venue_name = extract_venue_name(kaisai_key)
        if not venue_name:
            print(f"  WARN: 場所名抽出失敗: {kaisai_key}")
            continue

        print(f"\n  {kaisai_key} ({venue_name})")

        for race in races:
            race_id_12 = race.get("race_id", "")
            race_id_16 = race.get("race_id_16", "")
            race_no_str = race.get("race_no", "").replace("R", "")
            race_name = race.get("race_name", "")

            if not race_id_12 or not race_id_16:
                errors += 1
                continue

            race_number = int(race_no_str) if race_no_str.isdigit() else 0

            # 既存チェック
            filepath = race_dir / f"race_{race_id_16}.json"
            if filepath.exists() and not args.force:
                skipped += 1
                continue

            # syutubaページ取得
            try:
                html = scraper.scrape_syutuba(race_id_12)
                syutuba_data = parse_syutuba_html(html, race_id_12)
            except Exception as e:
                print(f"    {race_no_str}R: ERROR - {e}")
                errors += 1
                continue

            horse_count = len(syutuba_data.get("horses", []))
            if horse_count == 0:
                print(f"    {race_no_str}R: WARN - 出走馬なし")
                errors += 1
                continue

            # race JSON構築
            race_json = build_race_json_from_syutuba(
                race_id_16=race_id_16,
                race_id_12=race_id_12,
                date=date,
                venue_name=venue_name,
                race_number=race_number,
                race_name=race_name,
                syutuba_data=syutuba_data,
            )

            if not args.dry_run:
                config.ensure_dir(race_dir)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(race_json, f, ensure_ascii=False, indent=2)

            print(f"    {race_no_str}R: {race_name} ({horse_count}頭) → {filepath.name}")
            created += 1

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Results:")
    print(f"  Created: {created}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""日程（nittei）パーサー — 開催日程ページから全レースIDを抽出"""

import re
from typing import Any

from bs4 import BeautifulSoup


def parse_nittei_html(html: str, date_str: str = "") -> dict[str, Any]:
    """日程HTMLをパース。

    Args:
        html: 日程ページのHTML
        date_str: YYYYMMDD

    Returns:
        {
          "date": "20260215",
          "kaisai_data": {
            "1回東京1日目": [
              {"race_no": "1R", "race_name": "...", "course": "芝・1800m",
               "race_id": "202602050101", "start_time": "10:05",
               "start_at": "2026-02-15T10:05:00+09:00"}
            ], ...
          },
          "total_races": 36,
          "kaisai_count": 3
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    kaisai_data: dict[str, list] = {}
    total_races = 0

    # 各開催テーブル: <table class="kaisai"> を直接探索
    kaisai_tables = soup.find_all("table", class_="kaisai")

    for table in kaisai_tables:

        # 開催名 (e.g. "1回東京1日目")
        midasi = table.find("th", class_="midasi")
        kaisai_name = midasi.get_text(strip=True) if midasi else "不明"

        races = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue

            # レース番号
            first_text = cells[0].get_text(strip=True)
            race_no_m = re.match(r"^(\d+R)", first_text)
            if not race_no_m:
                continue
            race_no = race_no_m.group(1)

            # レース名・コース（2番目のセルのa > p）
            race_name = ""
            course = ""
            race_id_12 = ""
            if len(cells) >= 2:
                link = cells[1].find("a")
                if link:
                    # race_id from href
                    href = link.get("href", "")
                    rid_m = re.search(r"/(?:shutsuba|syutuba)/(\d{12})", href)
                    if rid_m:
                        race_id_12 = rid_m.group(1)

                    ps = link.find_all("p")
                    if ps:
                        race_name = ps[0].get_text(strip=True) if len(ps) > 0 else ""
                        course = ps[1].get_text(strip=True) if len(ps) > 1 else ""

            # 発走時刻（3番目のセル）
            start_time = ""
            if len(cells) >= 3:
                time_text = cells[2].get_text(strip=True)
                time_m = re.search(r"(\d{1,2}:\d{2})", time_text)
                if time_m:
                    start_time = time_m.group(1)

            # ISO8601 start_at
            start_at = ""
            if date_str and start_time and len(date_str) == 8:
                y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
                start_at = f"{y}-{m}-{d}T{start_time}:00+09:00"

            if race_id_12:
                races.append({
                    "race_no": race_no,
                    "race_name": race_name,
                    "course": course,
                    "race_id": race_id_12,
                    "start_time": start_time,
                    "start_at": start_at,
                })

        if races:
            kaisai_data[kaisai_name] = races
            total_races += len(races)

    return {
        "date": date_str,
        "kaisai_data": kaisai_data,
        "total_races": total_races,
        "kaisai_count": len(kaisai_data),
    }

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前走インタビュー（syoin）パーサー — 前走の騎手インタビュー・次走メモを抽出"""

import re
from typing import Any, Optional

from bs4 import BeautifulSoup


# 次走メモ区切りキーワード
_NEXT_RACE_KEYWORDS = ["次走へのメモ", "次走メモ", "次走へ", "次走", "今後", "次回", "次戦", "メモ"]


def parse_syoin_html(html: str, race_id_12: str = "") -> dict[str, Any]:
    """前走インタビューHTMLをパース。

    Returns:
        {
          "race_info": {"race_id": "..."},
          "interviews": [
            {"horse_number": 1, "horse_name": "...", "jockey": "...",
             "interview": "...", "next_race_memo": "..."},
            ...
          ]
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    interviews: list[dict] = []

    # syoinテーブル
    table = soup.find("table", class_="syoin")
    if not table:
        # フォールバック: インタビュー/コメントを含むテーブル
        for t in soup.find_all("table"):
            text = t.get_text()
            if "インタビュー" in text or "前走" in text:
                table = t
                break

    if not table:
        return {"race_info": {"race_id": race_id_12}, "interviews": []}

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        entry = _parse_interview_row(cells)
        if entry and entry.get("horse_number"):
            interviews.append(entry)

    return {"race_info": {"race_id": race_id_12}, "interviews": interviews}


def _parse_interview_row(cells) -> Optional[dict]:
    """行からインタビューデータを抽出"""
    entry: dict[str, Any] = {}

    # 馬番（数値セル）
    for cell in cells:
        text = cell.get_text(strip=True)
        if text.isdigit() and int(text) <= 18:
            entry["horse_number"] = int(text)
            break

    if "horse_number" not in entry:
        return None

    # 馬名（umalink）
    for cell in cells:
        link = cell.find("a", class_=re.compile(r"umalink"))
        if link:
            entry["horse_name"] = link.get_text(strip=True)
            break
    if "horse_name" not in entry:
        for cell in cells:
            link = cell.find("a")
            if link and link.get_text(strip=True):
                text = link.get_text(strip=True)
                if not text.isdigit():
                    entry["horse_name"] = text
                    break

    # インタビュー本文 (最も長いテキストセル)
    longest = ""
    for cell in cells:
        text = cell.get_text(strip=True)
        if len(text) > len(longest) and not text.isdigit():
            longest = text

    # インタビューと次走メモを分割
    interview, memo = _split_interview_memo(longest)
    entry["interview"] = interview
    entry["next_race_memo"] = memo

    return entry


def _split_interview_memo(text: str) -> tuple[str, str]:
    """インタビューテキストを本文と次走メモに分割"""
    for keyword in _NEXT_RACE_KEYWORDS:
        idx = text.find(keyword)
        if idx >= 0:
            return text[:idx].strip(), text[idx + len(keyword):].strip().lstrip("：:・ ")
    return text, ""

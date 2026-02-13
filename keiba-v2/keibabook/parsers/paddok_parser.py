#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""パドック（paddok）パーサー — パドック評価・コメントを抽出"""

import re
from typing import Any

from bs4 import BeautifulSoup

# 評価→スコア変換
_MARK_SCORES = {"S": 5, "Ａ": 5, "A": 5, "Ｂ": 4, "B": 4, "Ｃ": 3, "C": 3,
                "◎": 5, "○": 4, "▲": 3, "△": 2}


def parse_paddok_html(html: str, race_id_12: str = "") -> dict[str, Any]:
    """パドックHTMLをパース。

    Returns:
        {
          "race_info": {"race_id": "..."},
          "paddock_evaluations": [
            {"horse_number": 1, "horse_name": "...", "comment": "...",
             "mark": "◎", "mark_score": 5},
            ...
          ]
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    evals: list[dict] = []

    # パドックテーブル: "コメント"と"評価"を含むテーブル
    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text()
        if "コメント" in text and ("評価" in text or "パドック" in text):
            target_table = table
            break

    if not target_table:
        return {
            "race_info": {"race_id": race_id_12},
            "paddock_evaluations": [],
            "data_status": "no_data_available",
        }

    # ヘッダー
    headers: list[str] = []
    rows = target_table.find_all("tr")
    if rows:
        for cell in rows[0].find_all(["th", "td"]):
            headers.append(cell.get_text(strip=True))

    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        entry: dict[str, Any] = {}

        # 馬番 — class="umaban"のセルを優先
        for cell in cells:
            if "umaban" in cell.get("class", []):
                text = cell.get_text(strip=True)
                if text.isdigit():
                    entry["horse_number"] = int(text)
                break

        # フォールバック: 枠番(class="waku")を除いた最初の数字セル
        if "horse_number" not in entry:
            for cell in cells:
                if "waku" in cell.get("class", []):
                    continue
                text = cell.get_text(strip=True)
                if text.isdigit() and int(text) <= 18:
                    entry["horse_number"] = int(text)
                    break

        if "horse_number" not in entry:
            continue

        # 馬名（リンクから）
        for cell in cells:
            link = cell.find("a")
            if link:
                name = link.get_text(strip=True)
                if name and not name.isdigit():
                    entry["horse_name"] = name
                    break

        # コメント・評価（ヘッダーベースまたはインデックスベース）
        comment_idx = None
        mark_idx = None
        for i, h in enumerate(headers):
            if "コメント" in h:
                comment_idx = i
            if "評価" in h:
                mark_idx = i

        if comment_idx is not None and comment_idx < len(cells):
            entry["comment"] = cells[comment_idx].get_text(strip=True)
        if mark_idx is not None and mark_idx < len(cells):
            entry["mark"] = cells[mark_idx].get_text(strip=True)
        else:
            # フォールバック: 最後のセルを評価とみなす
            last_text = cells[-1].get_text(strip=True) if cells else ""
            if len(last_text) <= 2:
                entry["mark"] = last_text

        # コメントのフォールバック（最も長いテキスト）
        if "comment" not in entry:
            longest = ""
            for cell in cells:
                text = cell.get_text(strip=True)
                if len(text) > len(longest) and not text.isdigit() and len(text) > 3:
                    longest = text
            entry["comment"] = longest

        # スコア
        mark = entry.get("mark", "")
        entry["mark_score"] = _MARK_SCORES.get(mark, 0)

        evals.append(entry)

    return {
        "race_info": {"race_id": race_id_12},
        "paddock_evaluations": evals,
        "evaluation_count": len(evals),
        "data_status": "complete" if evals else "no_data_available",
    }

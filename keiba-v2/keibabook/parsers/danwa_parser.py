#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""談話（danwa）パーサー — 厩舎の話を抽出"""

import re
from typing import Any

from bs4 import BeautifulSoup


# 談話テーブル検出キーワード
_DANWA_KEYWORDS = {"馬番", "馬名", "厩舎", "談話", "コメント", "調教師", "話"}


def parse_danwa_html(html: str, race_id_12: str = "") -> dict[str, Any]:
    """談話HTMLをパース。

    Returns:
        {
          "race_info": {"race_id": "..."},
          "danwa_data": [
            {"馬番": "1", "馬名": "...", "厩舎の話": "..."},
            ...
          ]
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    danwa_data: list[dict] = []

    # 談話テーブルを探す（キーワード3つ以上含むテーブル）
    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text()
        matches = sum(1 for kw in _DANWA_KEYWORDS if kw in text)
        if matches >= 3:
            target_table = table
            break

    if not target_table:
        return {"race_info": {"race_id": race_id_12}, "danwa_data": []}

    # ヘッダー抽出
    rows = target_table.find_all("tr")
    headers: list[str] = []
    if rows:
        for cell in rows[0].find_all(["th", "td"]):
            headers.append(re.sub(r"[\s\u2003\u3000]+", "", cell.get_text(strip=True)))

    # データ行
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        entry: dict[str, str] = {}
        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else f"field_{i}"
            entry[key] = cell.get_text(strip=True)

        # 馬番があるエントリのみ
        bano = entry.get("馬番", "")
        if bano and bano.isdigit():
            # 厩舎の話キー正規化
            comment = ""
            for k in ["厩舎の話", "談話", "コメント", "展望"]:
                if entry.get(k):
                    comment = entry[k]
                    break
            if not comment:
                # 最も長いテキストを談話として採用
                for k, v in entry.items():
                    if k not in ("馬番", "馬名", "厩舎", "調教師") and len(v) > len(comment):
                        comment = v
            entry["厩舎の話"] = comment
            danwa_data.append(entry)

    return {"race_info": {"race_id": race_id_12}, "danwa_data": danwa_data}

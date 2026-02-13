#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""スピード指数（speed）パーサー — 過去5走のスピード指数を抽出

URLパターン: /cyuou/speed/0/{race_id_12}

HTML構造:
    <table>
      <tr>
        <th class="waku">枠番</th>
        <th class="umaban">馬番</th>
        <th class="kbamei">馬名</th>
        <th class="speed">5走前</th>
        <th class="speed">4走前</th>
        <th class="speed">3走前</th>
        <th class="speed">2走前</th>
        <th class="speed">前走</th>
      </tr>
      <tr>
        <td class="waku"><p class="waku1">1</p></td>
        <td class="umaban">1</td>
        <td class="left"><a class="umalink_click">馬名</a></td>
        <td class="speed">
          <a href="/cyuou/seiseki/...">
            <p>2025.09.27 中山</p>
            <p>芝良1200m 14着</p>
            <p class="speed"><span class="speed">67.1</span></p>
          </a>
        </td>
        ...
      </tr>
    </table>

出力:
    {
      "horses": [
        {"馬番": "1", "馬名": "ロードトライン",
         "speed_indexes": [67.1, 79.7, 82.9, 77.4, 68.8],
         "speed_labels": ["5走前", "4走前", "3走前", "2走前", "前走"]},
        ...
      ],
      "horse_count": 18
    }

speed_indexesは古い順（5走前→前走）。値がない場合はNone。
"speedbest"クラスは5走中の最高値を示す。
"""

import re
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag


def parse_speed_html(html: str, race_id_12: str = "") -> dict[str, Any]:
    """スピード指数HTMLをパース。

    Returns:
        {
          "horses": [
            {"馬番": str, "馬名": str,
             "speed_indexes": [float|None, ...],  # 5走前→前走 (最大5要素)
             "speed_labels": [str, ...]},
          ],
          "horse_count": int
        }
    """
    soup = BeautifulSoup(html, "html.parser")

    horses = []
    header_labels = ["5走前", "4走前", "3走前", "2走前", "前走"]

    # class="speed" を持つ <th> があるテーブルを探す
    target_table = None
    for table in soup.find_all("table"):
        ths = table.find_all("th", class_="speed")
        if ths:
            target_table = table
            break

    if not target_table:
        return {"horses": [], "horse_count": 0}

    rows = target_table.find_all("tr")

    for row in rows:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        # ヘッダー行はスキップ
        if cells[0].name == "th":
            continue

        # 馬番セル（class="umaban"）
        umaban_cell = row.find("td", class_="umaban")
        if not umaban_cell:
            continue
        umaban = umaban_cell.get_text(strip=True)
        if not re.match(r"^\d{1,2}$", umaban):
            continue

        # 馬名セル（class="left" 内の <a>）
        name_cell = row.find("td", class_="left")
        horse_name = ""
        if name_cell:
            a_tag = name_cell.find("a")
            if a_tag:
                horse_name = a_tag.get_text(strip=True)

        # スピード指数セル（class="speed" の <td>）
        speed_cells = row.find_all("td", class_="speed")
        speed_values = []
        for td in speed_cells:
            val = _extract_speed_from_cell(td)
            speed_values.append(val)

        # 5要素にパディング（5走未満の場合は先頭をNoneで埋める）
        while len(speed_values) < 5:
            speed_values.insert(0, None)
        speed_values = speed_values[:5]

        # 全てNoneなら無視
        if all(v is None for v in speed_values):
            continue

        horses.append({
            "馬番": umaban,
            "馬名": horse_name,
            "speed_indexes": speed_values,
            "speed_labels": header_labels[:len(speed_values)],
        })

    return {
        "horses": horses,
        "horse_count": len(horses),
    }


def _extract_speed_from_cell(td: Tag) -> Optional[float]:
    """<td class="speed"> セルからスピード指数値を抽出。

    セル内構造:
        <a href="...">
          <p>2025.09.27 中山</p>
          <p>芝良1200m 14着</p>
          <p class="speed"><span class="speed">67.1</span></p>
        </a>

    span.speed または span.speedbest のテキストが数値。
    """
    # span.speed または span.speedbest を探す
    span = td.find("span", class_=re.compile(r"speed"))
    if span:
        return _parse_speed_value(span.get_text(strip=True))

    # フォールバック: <p class="speed"> 内のテキスト
    p_speed = td.find("p", class_="speed")
    if p_speed:
        return _parse_speed_value(p_speed.get_text(strip=True))

    return None


def _parse_speed_value(text: str) -> Optional[float]:
    """スピード指数テキストをfloatに変換。無効値はNone。"""
    if not text:
        return None
    # 全角→半角
    text = text.translate(str.maketrans("０１２３４５６７８９．", "0123456789."))
    text = text.strip()
    if text in ("", "-", "--", "---", "***", "＊＊＊"):
        return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None

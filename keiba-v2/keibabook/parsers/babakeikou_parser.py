#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""馬場傾向（babakeikou）パーサー — クッション値、含水率等を抽出"""

import re
from typing import Any

from bs4 import BeautifulSoup


def parse_babakeikou_html(html: str, race_id_12: str = "") -> dict[str, Any]:
    """馬場傾向HTMLをパース。

    Returns:
        {
          "basic_info": {"date": "...", "place": "...", "weather": "..."},
          "turf": {"condition": "良", "cushion_value": "7.5", "moisture_rate": "8.0"},
          "dirt": {"condition": "良", "moisture_rate": "12.5"},
          "moisture": {"turf_inner": "8.0", "turf_outer": "8.2", ...},
          "comments": [...],
          "parse_status": "success"
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    result: dict[str, Any] = {
        "basic_info": {},
        "turf": {},
        "dirt": {},
        "moisture": {},
        "comments": [],
        "parse_status": "success",
    }

    # 日付
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        result["basic_info"]["date"] = f"{m.group(1)}年{m.group(2)}月{m.group(3)}日"

    # 場所
    m = re.search(r"\d+回(.+?)\d+日目", text)
    if m:
        result["basic_info"]["place"] = m.group(1)

    # 天候
    for w in ["晴", "曇", "雨", "小雨", "雪"]:
        if w in text:
            result["basic_info"]["weather"] = w
            break

    # 芝馬場状態
    m = re.search(r"芝[：:・\s]*([良稍重不]+)", text)
    if m:
        raw = m.group(1)
        if "不" in raw:
            result["turf"]["condition"] = "不良"
        elif "重" in raw:
            result["turf"]["condition"] = "重"
        elif "稍" in raw:
            result["turf"]["condition"] = "稍重"
        else:
            result["turf"]["condition"] = "良"

    # ダート馬場状態
    m = re.search(r"ダ[ート]*[：:・\s]*([良稍重不]+)", text)
    if m:
        raw = m.group(1)
        if "不" in raw:
            result["dirt"]["condition"] = "不良"
        elif "重" in raw:
            result["dirt"]["condition"] = "重"
        elif "稍" in raw:
            result["dirt"]["condition"] = "稍重"
        else:
            result["dirt"]["condition"] = "良"

    # クッション値
    m = re.search(r"クッション[値]*[：:・\s]*(\d+\.?\d*)", text)
    if m:
        result["turf"]["cushion_value"] = m.group(1)

    # 含水率（芝）
    m = re.search(r"芝[^\d]*[（(]?内?\s*(\d+\.?\d*)[%％]", text)
    if m:
        result["moisture"]["turf_inner"] = m.group(1)
    m = re.search(r"芝[^\d]*外?\s*(\d+\.?\d*)[%％]", text)
    if m:
        result["moisture"]["turf_outer"] = m.group(1)

    # 含水率（ダート）
    m = re.search(r"ダ[ート]*[^\d]*(\d+\.?\d*)[%％]", text)
    if m:
        result["dirt"]["moisture_rate"] = m.group(1)
        result["moisture"]["dirt"] = m.group(1)

    # コメント
    for kw in ["傾向", "注意", "ポイント", "特記"]:
        for p in soup.find_all("p"):
            p_text = p.get_text(strip=True)
            if kw in p_text and len(p_text) > 10:
                result["comments"].append(p_text)

    return result

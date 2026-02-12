#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""成績（seiseki）パーサー — レース結果、配当、ラップ、寸評を抽出"""

import re
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag


def parse_seiseki_html(html: str, race_id_12: str = "") -> dict[str, Any]:
    """成績HTMLをパース。

    Returns:
        {
          "race_info": {"race_id": "...", "race_name": "..."},
          "results": [
            {"着順": "1", "馬名": "...", "騎手": "...", "タイム": "2:23.1",
             "上り3F": "35.8", "通過順位": "3-3-2-1", "馬体重": "502(+4)",
             "sunpyo": "...", "interview": "..."},
            ...
          ],
          "payouts": {"win": 520, ...},
          "laps": {"lap_times": [...], "pace": "M"},
          "race_details": {...}
        }
    """
    soup = BeautifulSoup(html, "html.parser")

    race_info = _extract_race_info(soup, race_id_12)
    results = _extract_results(soup)
    interviews = _extract_interviews(soup)
    results = _merge_interviews(results, interviews)
    payouts = _extract_payouts(soup)
    laps = _extract_laps(soup)
    details = _extract_race_details(soup)

    return {
        "race_info": race_info,
        "results": results,
        "payouts": payouts,
        "laps": laps,
        "race_details": details,
    }


def _extract_race_info(soup: BeautifulSoup, race_id_12: str) -> dict:
    info: dict[str, Any] = {"race_id": race_id_12}
    title = soup.find("title")
    if title:
        info["race_name"] = title.get_text(strip=True)
    return info


def _extract_results(soup: BeautifulSoup) -> list[dict]:
    """成績テーブルから各馬の結果を抽出"""
    results: list[dict] = []

    table = soup.find("table", class_=re.compile(r"seiseki"))
    if not table:
        for t in soup.find_all("table"):
            text = t.get_text()
            if "着順" in text and "タイム" in text:
                table = t
                break
    if not table:
        return results

    # ヘッダー
    headers: list[str] = []
    thead = table.find("thead")
    first_row = thead.find("tr") if thead else table.find("tr")
    if first_row:
        for cell in first_row.find_all(["th", "td"]):
            h = cell.get_text(strip=True)
            # colspan対応
            colspan = int(cell.get("colspan", 1))
            headers.append(h)
            for _ in range(colspan - 1):
                headers.append(f"{h}_dup")

    # データ行
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        entry: dict[str, str] = {}
        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else f"field_{i}"
            key = re.sub(r"[\s\u2003\u3000]+", "", key)
            entry[key] = cell.get_text(strip=True)

        # 着順が数字のエントリのみ
        rank = entry.get("着順", entry.get("着", ""))
        if rank and (rank.isdigit() or rank in ("取消", "除外", "中止")):
            results.append(entry)

    return results


def _extract_interviews(soup: BeautifulSoup) -> list[dict]:
    """bameibox divから騎手インタビュー・寸評を抽出"""
    interviews: list[dict] = []

    for div in soup.find_all("div", class_="bameibox"):
        text = div.get_text(strip=True)
        if not text:
            continue

        # 馬名（着順）パターン
        entry: dict[str, str] = {}
        m = re.match(r"(.+?)（(\d+)着）", text)
        if m:
            entry["horse_name"] = m.group(1)
            entry["finish_position"] = m.group(2)

        # インタビューとメモに分離
        p_tags = div.find_all("p")
        for p in p_tags:
            p_text = p.get_text(strip=True)
            if "騎手" in p_text:
                entry["interview"] = p_text
            elif p_text and "interview" not in entry:
                entry["sunpyo"] = p_text

        if entry:
            interviews.append(entry)

    return interviews


def _merge_interviews(results: list[dict], interviews: list[dict]) -> list[dict]:
    """インタビューデータを結果にマージ"""
    for iv in interviews:
        horse_name = iv.get("horse_name", "")
        for r in results:
            if horse_name and horse_name in r.get("馬名", ""):
                if iv.get("sunpyo"):
                    r["sunpyo"] = iv["sunpyo"]
                if iv.get("interview"):
                    r["interview"] = iv["interview"]
                break
    return results


def _extract_payouts(soup: BeautifulSoup) -> dict:
    """配当テーブルを抽出"""
    payouts: dict[str, Any] = {}
    text = soup.get_text()

    # 単勝
    m = re.search(r"単勝[^\d]*(\d[\d,]+)", text)
    if m:
        payouts["win"] = int(m.group(1).replace(",", ""))

    # 複勝
    m_all = re.findall(r"複勝[^\d]*(\d[\d,]+)", text)
    if m_all:
        payouts["place"] = [int(v.replace(",", "")) for v in m_all[:3]]

    # 馬連
    m = re.search(r"馬連[^\d]*(\d[\d,]+)", text)
    if m:
        payouts["quinella"] = int(m.group(1).replace(",", ""))

    # 馬単
    m = re.search(r"馬単[^\d]*(\d[\d,]+)", text)
    if m:
        payouts["exacta"] = int(m.group(1).replace(",", ""))

    # ワイド
    m_all = re.findall(r"ワイド[^\d]*(\d[\d,]+)", text)
    if m_all:
        payouts["wide"] = [int(v.replace(",", "")) for v in m_all[:3]]

    # 3連複
    m = re.search(r"3連複[^\d]*(\d[\d,]+)", text)
    if m:
        payouts["trio"] = int(m.group(1).replace(",", ""))

    # 3連単
    m = re.search(r"3連単[^\d]*(\d[\d,]+)", text)
    if m:
        payouts["trifecta"] = int(m.group(1).replace(",", ""))

    return payouts


def _extract_laps(soup: BeautifulSoup) -> dict:
    """ラップタイムを抽出"""
    laps: dict[str, Any] = {}
    text = soup.get_text()

    # ラップタイム (12.3-11.8-... パターン)
    m = re.search(r"(\d{2}\.\d[\s\-]*){3,}", text)
    if m:
        lap_str = m.group(0)
        times = re.findall(r"\d{2}\.\d", lap_str)
        if times:
            laps["lap_times"] = times

    # ペース判定
    if "Ｈ" in text or "ハイ" in text:
        laps["pace"] = "H"
    elif "Ｓ" in text or "スロー" in text:
        laps["pace"] = "S"
    else:
        laps["pace"] = "M"

    return laps


def _extract_race_details(soup: BeautifulSoup) -> dict:
    """レース詳細（距離、馬場、天候等）を抽出"""
    details: dict[str, Any] = {}
    text = soup.get_text()

    # 距離
    m = re.search(r"(芝|ダート?)\s*(\d{3,4})m", text)
    if m:
        details["track_type"] = "芝" if "芝" in m.group(1) else "ダート"
        details["distance"] = int(m.group(2))

    # 馬場状態
    m = re.search(r"馬場[：:・\s]*(良|稍重|重|不良)", text)
    if m:
        details["track_condition"] = m.group(1)

    # 天候
    for w in ["晴", "曇", "雨", "小雨", "雪"]:
        if w in text:
            details["weather"] = w
            break

    return details

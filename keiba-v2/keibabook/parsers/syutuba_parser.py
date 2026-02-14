#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""出馬表（syutuba）パーサー — 出走馬情報、印、AI指数、展開を抽出

出力はext_builderが必要とするフィールドに合わせた構造。
"""

import re
import urllib.parse
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

# 印→ポイント変換（ext_builder互換）
MARK_VALUES = {
    "◎": 8, "○": 5, "▲": 3, "△": 2, "穴": 1, "注": 1, "×": 0,
}

# 丸数字→半角数字
MARU_MAP = {chr(0x2460 + i): str(i + 1) for i in range(20)}  # ①〜⑳


def parse_syutuba_html(html: str, race_id_12: str = "") -> dict[str, Any]:
    """出馬表HTMLをパース。

    Returns:
        {
          "race_info": {"title": ..., "track": ..., "distance": ...},
          "horses": [
            {"馬番": "1", "馬名_clean": "...", "umacd": "2019105283",
             "騎手": "...", "trainer_id": "ｳ011", "重量": "56",
             "単勝": "2.1", "人気": "1",
             "AI指数": "82.5", "AI指数ランク": "1", "人気指数": "1.8",
             "レイティング": "105",
             "短評": "...",
             "本誌印": "◎", "本誌印ポイント": 8,
             "marks_by_person": {"CPU": "◎", ...},
             "総合印ポイント": 25,
             ...}
          ],
          "horse_count": 18,
          "ai_data": {...},
          "tenkai_data": {...},
          "race_comment": "..."
        }
    """
    soup = BeautifulSoup(html, "html.parser")

    race_info = _extract_race_info(soup)
    horses = _extract_horses(soup)
    ai_data = _extract_ai_data(soup)
    tenkai_data = _extract_tenkai_data(soup)
    race_comment = _extract_race_comment(soup)

    # AI指数を各馬にマージ
    if ai_data and "entries" in ai_data:
        _merge_ai_data(horses, ai_data["entries"])

    # 印ポイント計算
    _calculate_mark_points(horses)

    return {
        "race_info": race_info,
        "horses": horses,
        "horse_count": len(horses),
        "ai_data": ai_data,
        "tenkai_data": tenkai_data,
        "race_comment": race_comment,
    }


# ── レース情報 ──

def _extract_race_info(soup: BeautifulSoup) -> dict:
    info: dict[str, Any] = {}

    title = soup.find("title")
    if title:
        info["title"] = title.get_text(strip=True)

    # race listからコース情報（京都は「芝内・2000m」「芝外・1800m」表記）
    race_list = soup.find("ul", class_="race")
    if race_list:
        active = race_list.find("li", class_="active")
        if active:
            val = active.get("value", "")
            parts = val.split("<br>") if "<br>" in val else val.split("<br/>")
            if len(parts) >= 2:
                info["race_condition"] = parts[0].strip()
                # 芝内・2000m, 芝外・1800m, 芝・1800m, ダ・1200m 等
                m = re.match(r"(芝(?:内|外)?|ダ|ダート)・?(\d+)m", parts[1].strip())
                if m:
                    info["track"] = "芝" if "芝" in m.group(1) else "ダ"
                    info["distance"] = int(m.group(2))

    # フォールバック（ページ全文から距離を探す）
    if "distance" not in info:
        text = soup.get_text()
        m = re.search(r"(芝(?:内|外)?|ダート?)[・\s]*(\d{3,4})m", text)
        if m:
            info["track"] = "芝" if "芝" in m.group(1) else "ダ"
            info["distance"] = int(m.group(2))

    return info


# ── 出走馬 ──

def _extract_horses(soup: BeautifulSoup) -> list[dict]:
    horses: list[dict] = []

    # syutubaテーブル
    table = soup.find("table", class_=re.compile(r"syutuba"))
    if not table:
        for t in soup.find_all("table"):
            if len(t.find_all("a", attrs={"umacd": True})) > 3:
                table = t
                break
    if not table:
        return horses

    # ヘッダー
    headers: list[str] = []
    thead = table.find("thead")
    if thead:
        for cell in thead.find("tr").find_all(["th", "td"]):
            headers.append(cell.get_text(strip=True))

    # データ行
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        horse = _extract_horse_row(row, headers)
        if horse and horse.get("馬番", "").isdigit():
            horses.append(horse)

    return horses


def _extract_horse_row(row: Tag, headers: list[str]) -> Optional[dict]:
    cells = row.find_all(["td", "th"])
    if not cells:
        return None

    data: dict[str, Any] = {}

    for i, cell in enumerate(cells):
        text = cell.get_text(strip=True)
        header = headers[i] if i < len(headers) else f"field_{i}"
        # キー正規化: スペース除去 (「騎　手」→「騎手」)
        key = re.sub(r"[\s\u2003\u3000]+", "", header)
        data[key] = text

        # umacd (馬ID)
        umacd_link = cell.find("a", attrs={"umacd": True})
        if umacd_link:
            data["umacd"] = umacd_link.get("umacd", "")
            data["馬名_clean"] = umacd_link.get_text(strip=True)
            data["馬名_link"] = umacd_link.get("href", "")

        # trainer_id (厩舎リンク)
        trainer_link = cell.find("a", href=re.compile(r"/db/kyusya/"))
        if trainer_link:
            href = trainer_link.get("href", "")
            encoded_id = href.split("/kyusya/")[-1] if "/kyusya/" in href else ""
            data["trainer_id"] = urllib.parse.unquote(encoded_id)
            data["trainer_link"] = (
                href if href.startswith("http") else f"https://p.keibabook.co.jp{href}"
            )

    return data


# ── AI指数 ──

def _extract_ai_data(soup: BeautifulSoup) -> dict:
    ai_data: dict[str, Any] = {}
    section = soup.find("p", class_="title", string="AI指数")
    if not section:
        return ai_data

    table = section.find_next("table", class_="ai")
    if not table:
        return ai_data

    entries = []
    tbody = table.find("tbody")
    if tbody:
        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 5:
                waku = cells[1].find("p", class_=re.compile(r"waku\d+"))
                horse_num = waku.get_text(strip=True) if waku else ""
                # 全角→半角
                horse_num = horse_num.translate(
                    str.maketrans("０１２３４５６７８９", "0123456789")
                )
                uma = cells[2].find("a")
                entries.append({
                    "rank": cells[0].get_text(strip=True),
                    "horse_number": horse_num,
                    "horse_name": uma.get_text(strip=True) if uma else cells[2].get_text(strip=True),
                    "popularity_index": cells[3].get_text(strip=True),
                    "ai_index": cells[4].get_text(strip=True),
                })

    ai_data["entries"] = entries
    return ai_data


def _merge_ai_data(horses: list[dict], ai_entries: list[dict]) -> None:
    for ai in ai_entries:
        num = ai.get("horse_number", "")
        num_norm = num.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        for horse in horses:
            if str(horse.get("馬番")) == str(num_norm):
                horse["AI指数"] = ai.get("ai_index", "")
                horse["AI指数ランク"] = ai.get("rank", "")
                horse["人気指数"] = ai.get("popularity_index", "")
                break


# ── 展開 ──

def _extract_tenkai_data(soup: BeautifulSoup) -> dict:
    tenkai: dict[str, Any] = {}
    section = soup.find("p", class_="title", string="展開")
    if not section:
        return tenkai

    parent = section.parent
    if not parent:
        return tenkai

    # ペース
    pace_elem = parent.find("p", string=re.compile(r"ペース"))
    if pace_elem:
        m = re.search(r"ペース[　\s]*([A-Z\-]+)", pace_elem.get_text())
        if m:
            tenkai["pace"] = m.group(1)

    # ポジション
    table = parent.find("table")
    if table:
        positions: dict[str, list[str]] = {}
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            for i in range(0, len(cells), 2):
                if i + 1 < len(cells):
                    pos_name = cells[i].get_text(strip=True)
                    nums = []
                    for span in cells[i + 1].find_all("span", class_="marusuji"):
                        txt = span.get_text(strip=True)
                        for maru, digit in MARU_MAP.items():
                            txt = txt.replace(maru, digit)
                        nums.append(txt)
                    positions[pos_name] = nums
        tenkai["positions"] = positions

        # 解説
        desc_p = table.find_next_sibling("p")
        if desc_p:
            desc = desc_p.get_text(strip=True)
            if desc and not desc.startswith("title"):
                tenkai["description"] = desc

    return tenkai


# ── 本紙の見解 ──

def _extract_race_comment(soup: BeautifulSoup) -> str:
    title = soup.find("p", class_="title", string=re.compile(r"本[紙誌]の見解"))
    if title:
        p = title.find_next_sibling("p")
        if p:
            return p.get_text(strip=True)
    return ""


# ── 印ポイント計算 ──

def _calculate_mark_points(horses: list[dict]) -> None:
    """本誌印 + 複数者の総合印ポイントを計算"""

    # 印元候補 (label, キー候補)
    candidate_sources = [
        ("CPU", ["CPU", "ＣＰＵ"]),
        ("本誌", ["本誌", "本紙", "本誌見解", "本紙見解"]),
        ("牟田雅", ["牟田雅", "牟田"]),
        ("西村敬", ["西村敬", "西村"]),
        ("広瀬健", ["広瀬健", "広瀬"]),
    ]

    def _to_point(mark_text: str) -> int:
        if not mark_text or not mark_text.strip():
            return 0
        for m, p in MARK_VALUES.items():
            if m in mark_text:
                return p
        return 0

    for horse in horses:
        # 本誌印
        honshi = horse.get("本誌") or horse.get("本紙") or horse.get("本誌見解") or ""
        if honshi:
            horse["本誌印"] = honshi
            horse["本誌印ポイント"] = _to_point(honshi)

        # 複数者の総合
        marks_by_person: dict[str, str] = {}
        total = 0
        picked = 0

        for label, variants in candidate_sources:
            for key in variants:
                if key in horse:
                    val = horse.get(key, "")
                    marks_by_person[label] = val if val else "無印"
                    total += _to_point(str(val))
                    picked += 1
                    break
            if picked >= 7:
                break

        # 残りキーから印を拾う
        if picked < 7:
            skip_keys = {"馬番", "馬名", "馬名_clean", "単勝", "人気", "枠番",
                         "umacd", "馬名_link", "trainer_id", "trainer_link"}
            for k, v in horse.items():
                if k in skip_keys or k in marks_by_person:
                    continue
                if any(sym in str(v) for sym in MARK_VALUES if sym):
                    marks_by_person[k] = v
                    total += _to_point(str(v))
                    picked += 1
                    if picked >= 7:
                        break

        horse["marks_by_person"] = marks_by_person
        horse["総合印ポイント"] = max(0, int(round(total)))

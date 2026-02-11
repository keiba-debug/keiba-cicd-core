#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教データ拡張パーサー (v2)

競馬ブックWEBの調教ページ (/cyuou/cyokyo/0/0/{race_id}) の
HTMLから詳細な調教セッションデータを抽出する。

v1パーサーとの違い:
  - v1: 外側テーブルのヘッダ行のみ (short_review, attack_explanation, training_arrow)
  - v2: 内側テーブル (table.cyokyodata) の全セッション行を抽出
        追い切り(oikiri)、併せ馬(awase)、休養間隔(kankaku)を構造化

出力JSON構造:
  {
    "race_id": "202601040410",
    "horses": [
      {
        "horse_number": 1,
        "horse_name": "カニキュル",
        "horse_code": "0935827",
        "short_review": "好気配示す",
        "training_arrow": "↗",
        "attack_explanation": "手前を替えて重心が...",
        "sessions": [
          {
            "is_oikiri": false,
            "rider": "助手",
            "date": "9/24(水)",
            "harrow": "",
            "course": "美Ｗ",
            "condition": "良",
            "times": {"6f": 83.9, "5f": 67.0, "half_mile": 52.4, "3f": 37.6, "1f": 12.0},
            "position": "［８］",
            "intensity": "強めに追う",
            "comment": "一本調子の走り",
            "awase": null
          }
        ],
        "rest_period": "中3週"
      }
    ]
  }
"""

import re
import json
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag


def parse_cyokyo_html(html: str, race_id: str = "") -> dict:
    """
    調教ページHTMLから全馬の詳細調教データを抽出。

    Args:
        html: 調教ページのHTML文字列
        race_id: 12桁race_id (省略可、ファイル名から分かる場合)

    Returns:
        dict: {"race_id": str, "horses": list[dict]}
    """
    soup = BeautifulSoup(html, "html.parser")
    horses = []

    # 各馬: table.default.cyokyo
    cyokyo_tables = soup.find_all("table", class_="cyokyo")

    for table in cyokyo_tables:
        horse = _parse_horse_table(table)
        if horse and horse.get("horse_number"):
            horses.append(horse)

    return {"race_id": race_id, "horses": horses}


def parse_cyokyo_file(html_path: str | Path) -> dict:
    """HTMLファイルからパース。ファイル名からrace_idを推定。"""
    path = Path(html_path)
    race_id = ""
    m = re.search(r"(\d{12})", path.stem)
    if m:
        race_id = m.group(1)

    with open(path, encoding="utf-8") as f:
        html = f.read()

    return parse_cyokyo_html(html, race_id)


def _parse_horse_table(table: Tag) -> Optional[dict]:
    """
    1頭分のtable.default.cyokyoから全データを抽出。

    構造:
      <table class="default cyokyo" id="cyokyo{horse_code}">
        <thead>...</thead>
        <tbody>
          <tr>  ← ヘッダ行 (枠番, 馬番, 馬名, 短評, 矢印)
          <tr>  ← 内側テーブル (td colspan=5 > table.cyokyodata)
        </tbody>
      </table>
      <div class="semekaisetu">攻め解説</div>
    """
    result = {
        "horse_number": None,
        "horse_name": "",
        "horse_code": "",
        "short_review": "",
        "training_arrow": "",
        "attack_explanation": "",
        "sessions": [],
        "rest_period": "",
    }

    # horse_code from table id (e.g. id="cyokyo0946578")
    table_id = table.get("id", "")
    m = re.search(r"cyokyo(\d+)", table_id)
    if m:
        result["horse_code"] = m.group(1)

    # ヘッダ行 (外側テーブルの最初のtbody > tr)
    tbody = table.find("tbody")
    if not tbody:
        return None

    rows = tbody.find_all("tr", recursive=False)
    if not rows:
        return None

    header_row = rows[0]
    _parse_header_row(header_row, result)

    # 内側テーブル (table.cyokyodata)
    inner_table = table.find("table", class_="cyokyodata")
    if inner_table:
        _parse_session_table(inner_table, result)

    # 攻め解説 (table直後のdiv.semekaisetu)
    seme_div = table.find_next_sibling("div", class_="semekaisetu")
    if seme_div:
        p = seme_div.find("p")
        if p:
            result["attack_explanation"] = p.get_text(strip=True)

    return result


def _parse_header_row(row: Tag, result: dict) -> None:
    """外側テーブルのヘッダ行から基本情報を抽出。"""
    # 馬番
    umaban_cell = row.find("td", class_="umaban")
    if umaban_cell:
        text = umaban_cell.get_text(strip=True)
        m = re.search(r"(\d+)", text)
        if m:
            result["horse_number"] = int(m.group(1))

    # 馬名 + horse_code(リンクから)
    kbamei_cell = row.find("td", class_="kbamei")
    if kbamei_cell:
        link = kbamei_cell.find("a")
        if link:
            result["horse_name"] = link.get_text(strip=True)
            href = link.get("href", "")
            code_m = re.search(r"/db/uma/(\d+)", href)
            if code_m and not result["horse_code"]:
                result["horse_code"] = code_m.group(1)
        else:
            result["horse_name"] = kbamei_cell.get_text(strip=True)

    # 短評
    tanpyo_cell = row.find("td", class_="tanpyo")
    if tanpyo_cell:
        result["short_review"] = tanpyo_cell.get_text(strip=True)

    # 矢印
    yajirusi_cell = row.find("td", class_="yajirusi")
    if yajirusi_cell:
        span = yajirusi_cell.find("span")
        text = span.get_text(strip=True) if span else yajirusi_cell.get_text(strip=True)
        if text:
            result["training_arrow"] = text


def _parse_session_table(inner_table: Tag, result: dict) -> None:
    """
    table.cyokyodataの全行をパース。

    行タイプ:
      tr.time   — 通常の調教セッション
      tr.oikiri — 追い切り（☆マーク付き、最終追い切り）
      tr.awase  — 併せ馬情報（直前のセッションに紐付く）
      tr with td.kankaku — 休養間隔（中N週）
    """
    tbody = inner_table.find("tbody")
    if not tbody:
        return

    all_rows = tbody.find_all("tr", recursive=False)

    for row in all_rows:
        classes = row.get("class", [])

        # 休養間隔
        kankaku_td = row.find("td", class_="kankaku")
        if kankaku_td:
            kankaku_p = kankaku_td.find("p", class_="kankaku")
            if kankaku_p:
                result["rest_period"] = kankaku_p.get_text(strip=True)
            else:
                result["rest_period"] = kankaku_td.get_text(strip=True)
            continue

        # 併せ馬行
        if "awase" in classes:
            awase_text = row.get_text(strip=True)
            # 直前のセッションに紐付ける
            if result["sessions"] and awase_text:
                result["sessions"][-1]["awase"] = awase_text
            continue

        # 通常セッション / 追い切り
        if "time" in classes or "oikiri" in classes:
            session = _parse_session_row(row, is_oikiri="oikiri" in classes)
            if session:
                result["sessions"].append(session)
            continue

        # ベスト行（日付が「ベスト」の場合もtimeクラス）— 上のtime分岐で処理済み


def _parse_session_row(row: Tag, is_oikiri: bool = False) -> Optional[dict]:
    """
    1つの調教セッション行をパース。

    列順 (th参照):
      0: mark, 1: norite(騎乗者), 2: tukihi(日付), 3: harrow,
      4: corse(コース), 5: baba(馬場),
      6: 1哩, 7: 7F, 8: 6F(坂路), 9: 5F(4F), 10: 半哩(3F), 11: 3F(2F), 12: 1F(1F),
      13: mawariiti(回り位置), 14: asiiro(脚色), 15: tanpyo(短評), 16: movie
    """
    cells = row.find_all("td")
    if len(cells) < 13:
        return None

    def cell_text(idx: int) -> str:
        if idx < len(cells):
            return cells[idx].get_text(strip=True)
        return ""

    def parse_time(val: str) -> Optional[float]:
        """タイム文字列をfloatに変換。'1回'等の非数値はNone。"""
        if not val:
            return None
        # "1回" "2回" → 坂路回数（非タイム）
        if "回" in val:
            return None
        try:
            return float(val)
        except ValueError:
            return None

    session = {
        "is_oikiri": is_oikiri,
        "rider": cell_text(1),
        "date": cell_text(2),
        "harrow": cell_text(3),
        "course": cell_text(4),
        "condition": cell_text(5),
        "times": {
            "1mile": parse_time(cell_text(6)),
            "7f": parse_time(cell_text(7)),
            "6f": parse_time(cell_text(8)),
            "5f": parse_time(cell_text(9)),
            "half_mile": parse_time(cell_text(10)),
            "3f": parse_time(cell_text(11)),
            "1f": parse_time(cell_text(12)),
        },
        "position": cell_text(13) if len(cells) > 13 else "",
        "intensity": cell_text(14) if len(cells) > 14 else "",
        "comment": cell_text(15) if len(cells) > 15 else "",
        "awase": None,
    }

    return session


# ============================================================
# ユーティリティ: サマリー特徴量の抽出
# ============================================================

def extract_oikiri_summary(horse_data: dict) -> dict:
    """
    1頭のデータから追い切り(oikiri)のサマリー特徴量を抽出。
    ML特徴量やext_builder向け。

    Returns:
        dict with keys:
          - oikiri_course: str (追い切りコース, e.g. "美Ｗ")
          - oikiri_condition: str (馬場状態)
          - oikiri_5f: float|None
          - oikiri_3f: float|None
          - oikiri_1f: float|None
          - oikiri_intensity: str (脚色, e.g. "強めに追う")
          - oikiri_rider: str
          - oikiri_comment: str (追い切り短評)
          - oikiri_has_awase: bool
          - oikiri_awase_text: str
          - session_count: int (全セッション数)
          - rest_period: str
          - training_arrow: str
          - training_arrow_value: int
    """
    arrow_map = {"↑": 2, "↗": 1, "→": 0, "↘": -1, "↓": -2}

    summary = {
        "oikiri_course": "",
        "oikiri_condition": "",
        "oikiri_5f": None,
        "oikiri_3f": None,
        "oikiri_1f": None,
        "oikiri_intensity": "",
        "oikiri_rider": "",
        "oikiri_comment": "",
        "oikiri_has_awase": False,
        "oikiri_awase_text": "",
        "session_count": len(horse_data.get("sessions", [])),
        "rest_period": horse_data.get("rest_period", ""),
        "training_arrow": horse_data.get("training_arrow", ""),
        "training_arrow_value": arrow_map.get(horse_data.get("training_arrow", ""), 0),
    }

    # 追い切りセッションを探す
    for s in horse_data.get("sessions", []):
        if s.get("is_oikiri"):
            times = s.get("times", {})
            summary["oikiri_course"] = s.get("course", "")
            summary["oikiri_condition"] = s.get("condition", "")
            summary["oikiri_5f"] = times.get("5f")
            summary["oikiri_3f"] = times.get("3f")  # half_mileは3F
            summary["oikiri_1f"] = times.get("1f")
            summary["oikiri_intensity"] = s.get("intensity", "")
            summary["oikiri_rider"] = s.get("rider", "")
            summary["oikiri_comment"] = s.get("comment", "")
            summary["oikiri_has_awase"] = s.get("awase") is not None
            summary["oikiri_awase_text"] = s.get("awase", "") or ""
            break  # 最初の追い切り（通常1つ）

    return summary


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys
    import argparse

    # Windows cp932でUnicode矢印等が出力できない対策
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="調教データ拡張パーサー (v2)")
    parser.add_argument("html_path", help="調教HTMLファイルパス")
    parser.add_argument("--summary", action="store_true", help="追い切りサマリーも表示")
    args = parser.parse_args()

    data = parse_cyokyo_file(args.html_path)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if args.summary:
        print("\n--- Oikiri Summary ---")
        for h in data["horses"]:
            s = extract_oikiri_summary(h)
            print(f"  {h['horse_number']:>2} {h['horse_name']}: "
                  f"course={s['oikiri_course']} 5f={s['oikiri_5f']} "
                  f"3f={s['oikiri_3f']} 1f={s['oikiri_1f']} "
                  f"intensity={s['oikiri_intensity']} "
                  f"awase={s['oikiri_has_awase']}")

# -*- coding: utf-8 -*-
"""AIコメント印 (markSet=4) 書込み CLI。

comment_llm の「人気薄・複勝妙味ピックアップ」report (report_{date}.md) を読み、
確信度 高/中/低 を TARGET 馬印スロット4 に Ａ/Ｂ/Ｃ で転記する。
評価 (markSet=2) / 購入軸 (markSet=3) とは独立した別スロット。

  確信度 → 印:  高 → Ａ   中 → Ｂ   低 → Ｃ

  --dry-run (既定) : パース結果を表示。DAT は書かない。
  --apply          : DAT (markSet=4) に書込み。

race_id は同日の predictions.json (venue_name + race_number → race_id) で解決する。

設計: docs/auto-purchase/26_MARK_SLOT_MAP.md (4-8 空き枠)

使用例:
  python -m ml.ai_marks.write_comment_marks --date 2026-06-21            # dry-run
  python -m ml.ai_marks.write_comment_marks --date 2026-06-21 --apply    # markSet=4 へ実書込み
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Windows コンソール (cp932) で 函/Ａ 等を表示できるよう utf-8 に揃える。
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ml.ai_marks.dat_writer import _MARK_SLOT_COMMENT, write_comment_marks_to_dat

# 確信度 → AIコメント印 (全角)。
_CONF_TO_MARK: Dict[str, str] = {"高": "Ａ", "中": "Ｂ", "低": "Ｃ"}
# 印の強さ (重複時に強い方を残す)。
_MARK_PRIORITY: Dict[str, int] = {"Ａ": 3, "Ｂ": 2, "Ｃ": 1}

# JRA 競馬場名 (report の ## 見出し / 抜粋行の検出に使う)。
_VENUES = ("札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉")

# 「## 函館」など場見出し。
_RE_TRACK = re.compile(r"^##\s*(" + "|".join(_VENUES) + r")\s*$")
# 「**2R**」などレース見出し。
_RE_RACE = re.compile(r"^\*{0,2}\s*(\d{1,2})\s*R\s*\*{0,2}\s*$")
# 「  - ［低］馬番10 …」本体の馬行。
_RE_HORSE = re.compile(r"［(高|中|低)］\s*馬番\s*(\d{1,2})")
# 「- 東京6R 馬番12 …」抜粋セクションの馬行 (確信「高」だけ抜粋なので一律 高扱い)。
_RE_EXCERPT = re.compile(r"(" + "|".join(_VENUES) + r")\s*(\d{1,2})\s*R\s*馬番\s*(\d{1,2})")


def _data_root() -> Path:
    return Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))


def _report_path(date: str) -> Path:
    return _data_root() / "comment_llm" / "live" / f"report_{date}.md"


def _predictions_path(date: str) -> Path:
    y, m, d = date.split("-")
    return _data_root() / "races" / y / m / d / "predictions.json"


def _stronger(a: str, b: str) -> str:
    return a if _MARK_PRIORITY.get(a, 0) >= _MARK_PRIORITY.get(b, 0) else b


def parse_report(text: str) -> Dict[Tuple[str, int], Dict[int, str]]:
    """report テキストを {(venue_name, race_no): {umaban: 'Ａ'|'Ｂ'|'Ｃ'}} に。

    本体 (## 場 / **NR** / ［確信］馬番) と 抜粋セクション (- 場NR 馬番…=一律高) の
    両方を拾い、同一馬が重複したら強い印 (Ａ>Ｂ>Ｃ) を残す。
    """
    out: Dict[Tuple[str, int], Dict[int, str]] = {}

    def add(venue: str, race: int, uma: int, mark: str) -> None:
        key = (venue, race)
        cur = out.setdefault(key, {})
        cur[uma] = _stronger(cur[uma], mark) if uma in cur else mark

    track: str | None = None
    race: int | None = None
    in_excerpt = False
    for line in text.splitlines():
        s = line.strip()

        m_track = _RE_TRACK.match(s)
        if m_track:
            track, race, in_excerpt = m_track.group(1), None, False
            continue
        if s.startswith("##"):
            # 場名でない見出し (例: ## ★確信「高」だけ抜粋) → 本体パース解除・抜粋モード。
            track, race, in_excerpt = None, None, True
            continue

        m_race = _RE_RACE.match(s)
        if m_race and track is not None:
            race = int(m_race.group(1))
            continue

        # 抜粋行 (- 東京6R 馬番12 …): 場+R を行内に含む。本体外でも拾う。
        m_ex = _RE_EXCERPT.search(s)
        if m_ex and (in_excerpt or track is None):
            add(m_ex.group(1), int(m_ex.group(2)), int(m_ex.group(3)), "Ａ")
            continue

        m_horse = _RE_HORSE.search(s)
        if m_horse and track is not None and race is not None:
            add(track, race, int(m_horse.group(2)), _CONF_TO_MARK[m_horse.group(1)])
            continue

    return out


def _build_race_id_map(date: str) -> Dict[Tuple[str, int], str]:
    """predictions.json から {(venue_name, race_no): race_id}。"""
    pp = _predictions_path(date)
    if not pp.exists():
        raise FileNotFoundError(f"predictions.json なし: {pp}")
    with open(pp, encoding="utf-8") as f:
        pred = json.load(f)
    mp: Dict[Tuple[str, int], str] = {}
    for r in pred.get("races", []):
        venue = r.get("venue_name", "")
        try:
            rno = int(r.get("race_number"))
        except (TypeError, ValueError):
            continue
        rid = r.get("race_id", "")
        if venue and rid:
            mp[(venue, rno)] = rid
    return mp


def process_date(date: str, *, report: Path | None = None, apply: bool = False,
                 verbose: bool = True) -> dict:
    rp = report or _report_path(date)
    if not rp.exists():
        if verbose:
            print(f"[comment-marks] report なし: {rp}", file=sys.stderr)
        return {"ok": False, "date": date, "reason": "no_report",
                "races": 0, "marked": 0, "written": 0, "marks_total": 0}

    parsed = parse_report(rp.read_text(encoding="utf-8"))
    rid_map = _build_race_id_map(date)

    mode = "APPLY" if apply else "DRY-RUN"
    if verbose:
        total_marks = sum(len(v) for v in parsed.values())
        print(f"[comment-marks] {date} {mode} mark_set={_MARK_SLOT_COMMENT} "
              f"report={rp.name} 対象={len(parsed)}R 計{total_marks}頭")
        print()

    n_marked = 0
    n_written = 0
    n_total = 0
    n_unresolved = 0
    for (venue, rno) in sorted(parsed.keys()):
        marks = parsed[(venue, rno)]
        rid = rid_map.get((venue, rno))
        # 印を強い順 (Ａ→Ｂ→Ｃ) に並べて表示。
        ordered = sorted(marks.items(), key=lambda kv: (-_MARK_PRIORITY.get(kv[1], 0), kv[0]))
        cells = " ".join(f"{sym}{u}" for u, sym in ordered)
        if rid is None:
            n_unresolved += 1
            if verbose:
                print(f"  {venue}{rno:>2}R  [race_id 未解決] {cells}", file=sys.stderr)
            continue
        n_marked += 1
        n_total += len(marks)
        if verbose:
            print(f"  {venue}{rno:>2}R  {cells}")
        if apply:
            try:
                n_written += write_comment_marks_to_dat(rid, marks, mark_set=_MARK_SLOT_COMMENT)
            except Exception as e:  # noqa: BLE001
                print(f"    [WARN] DAT書込み失敗 {rid}: {e}", file=sys.stderr)

    if verbose:
        print()
        if apply:
            print(f"[comment-marks] {date} 印あり={n_marked}R (計{n_total}頭) "
                  f"→ markSet={_MARK_SLOT_COMMENT} に {n_written}頭 書込み")
        else:
            print(f"[comment-marks] {date} 印あり={n_marked}R (計{n_total}頭) "
                  "(dry-run: DAT 未書込み)")
        if n_unresolved:
            print(f"[comment-marks] race_id 未解決 {n_unresolved}R (predictions に該当なし)",
                  file=sys.stderr)

    return {"ok": True, "date": date, "races": len(parsed), "marked": n_marked,
            "written": n_written, "marks_total": n_total, "unresolved": n_unresolved}


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AIコメント印 (markSet=4) 書込み")
    ap.add_argument("--date", help="YYYY-MM-DD (省略時は今日)")
    ap.add_argument("--report", type=Path, default=None,
                    help="report .md パス (省略時は comment_llm/live/report_{date}.md)")
    ap.add_argument("--apply", action="store_true",
                    help="DAT (markSet=4) に実書込み (未指定は dry-run)")
    args = ap.parse_args(argv)

    date = args.date or datetime.now().strftime("%Y-%m-%d")
    res = process_date(date, report=args.report, apply=args.apply)
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

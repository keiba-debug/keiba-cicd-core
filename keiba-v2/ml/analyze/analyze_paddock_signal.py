#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E: パドック点数 (競馬ブック) × AI印 の条件分析 (Session 148)

kb_ext_*.json の entries[].paddock_info.mark (生値) を backtest_cache のレースと突合し、
  1) パドック mark 単独の力 (mark別 3着内率 / 単勝・複勝 実配当ROI)
  2) AI印 (composite top5) × パドック mark のクロス (◎がパドックS/A vs C で何が変わるか)
を出す。

★S と A は別物 (ふくだ Session 148: S は出現稀少で A より上)。
  paddok_parser の mark_score は S=A=5 に潰している → ここでは mark 生値で層別。
  全角/半角ゆれは NFKC 正規化で吸収。
パドック印は原則 7R/8R 以降のみ提供 → カバレッジはレース番号別に確認済みの前提で、
mark が存在するレースだけを分析対象にする (後半レース限定オーバーレイ)。

CLI:
    python -m ml.analyze.analyze_paddock_signal
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import statistics
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

KB_ROOT = Path("C:/KEIBA-CICD/data3/keibabook")


def norm_mark(raw: str) -> str:
    """全角→半角・大文字化。'Ｓ'→'S'。空/不明は ''。"""
    s = unicodedata.normalize("NFKC", str(raw or "")).strip().upper()
    return s


def load_paddock_marks(race_ids: List[str]) -> Dict[str, Dict[int, str]]:
    """rid(16桁) -> {umaban: mark}。kb_ext のパスは YYYY/MM/DD から構成。"""
    out: Dict[str, Dict[int, str]] = {}
    for rid in race_ids:
        y, m, d = rid[:4], rid[4:6], rid[6:8]
        f = KB_ROOT / y / m / d / f"kb_ext_{rid}.json"
        if not f.exists():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        ent = data.get("entries") or {}
        marks: Dict[int, str] = {}
        items = ent.items() if isinstance(ent, dict) else ((e.get("umaban"), e) for e in ent)
        for k, e in items:
            pi = (e or {}).get("paddock_info") or {}
            mk = norm_mark(pi.get("mark"))
            if mk:
                try:
                    marks[int(k)] = mk
                except (TypeError, ValueError):
                    continue
        if marks:
            out[rid] = marks
    return out


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser()
    p.add_argument("--cache-path", default=None)
    args = p.parse_args()

    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]
    print(f"backtest_cache: {len(races)} races")
    pad = load_paddock_marks(codes)
    print(f"  パドックmarkありレース: {len(pad)} / {len(codes)}")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(list(pad.keys()))

    # mark別 全馬 / AI印◎ クロス
    by_mark = defaultdict(lambda: {"n": 0, "top3": 0, "win": 0,
                                   "tan_c": 0.0, "tan_p": 0.0, "fuku_c": 0.0, "fuku_p": 0.0})
    axis_cross = defaultdict(lambda: {"n": 0, "top3": 0, "win": 0,
                                      "tan_c": 0.0, "tan_p": 0.0, "fuku_c": 0.0, "fuku_p": 0.0})
    n_used = 0
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        rid = str(pred["race_id"])
        marks = pad.get(rid)
        if not marks:
            continue
        entries = pred.get("entries", [])
        if not any(int(e.get("finish_position") or 99) == 1 for e in entries):
            continue
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        n_used += 1
        fin = {int(e.get("umaban") or 0): int(e.get("finish_position") or 99) for e in entries}
        rpay = haraimodoshi.get(rid, {})
        tan = rpay.get("tansho", {})
        fuku = rpay.get("fukusho", {})
        axis_uma = re_.strengths[0].umaban
        for s in re_.strengths:
            mk = marks.get(s.umaban)
            if not mk:
                continue
            tgt = [by_mark[mk]]
            if s.umaban == axis_uma:
                tgt.append(axis_cross[mk])
            f_ = fin.get(s.umaban, 99)
            for a in tgt:
                a["n"] += 1
                if f_ <= 3:
                    a["top3"] += 1
                if f_ == 1:
                    a["win"] += 1
                a["tan_c"] += 100.0
                a["tan_p"] += tan.get(s.umaban, 0)
                a["fuku_c"] += 100.0
                a["fuku_p"] += fuku.get(s.umaban, 0)

    def _table(title: str, agg: dict):
        print(f"\n  ◆ {title}")
        print(f"  {'mark':<6}{'n':>8}{'勝率':>8}{'3着内率':>9}{'単勝ROI':>9}{'複勝ROI':>9}")
        print("  " + "-" * 50)
        order = sorted(agg.keys(), key=lambda k: (-agg[k]["n"]))
        for mk in order:
            a = agg[mk]
            if a["n"] < 5:
                continue
            print(f"  {mk:<6}{a['n']:>8,}{a['win'] / a['n'] * 100:>7.1f}%"
                  f"{a['top3'] / a['n'] * 100:>8.1f}%"
                  f"{a['tan_p'] / a['tan_c'] * 100 if a['tan_c'] else 0:>8.1f}%"
                  f"{a['fuku_p'] / a['fuku_c'] * 100 if a['fuku_c'] else 0:>8.1f}%")

    print(f"  分析対象レース: {n_used}")
    _table("パドック mark 単独 (全馬)", by_mark)
    _table("AI ◎ (composite 1位) × パドック mark", axis_cross)
    print("\n  → ◎×パドック高評価とC評価で ROI 差が出るなら「後半レース限定オーバーレイ」"
          "(ゲート/印補正) に進む価値あり。S と A は別行で確認 (同格に潰さない)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

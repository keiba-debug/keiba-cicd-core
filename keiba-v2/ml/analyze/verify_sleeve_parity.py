#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""振舞い不変検証 (Session 176 / §8-1 ゲート): sleeve_orchestrator(gap単独) ≡ gap_tansho_scheduler。

同一 predictions/post_times/timing 上で、両スケジューラを当日の時刻グリッドで dry 実行し、
★投票レースの (total_yen, sorted bet_specs) が完全一致 (差分0)★ を assert する。
一致すれば「gap をスリーブ化しても買い目・金額は変わらない」=リグレッション無しの証明。

使い方:
  python -m ml.analyze.verify_sleeve_parity --date 2026-06-21
"""
from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from ml.strategies import gap_tansho_live as gl
from ml.strategies import gap_tansho_scheduler as GAP
from ml.strategies import sleeve_orchestrator as ORCH
from ml.strategies.bettype_scheduler import build_bet_specs
from ml.utils.race_io import date_dir_for


def _enable_gap(initial=300000, bet_pct=1.0, day_pct=5.0):
    """両モジュールが見る gl.read_gap_config を enabled に固定 (dry・金は動かない)。"""
    cfg = gl.GapConfig(True, initial, bet_pct, day_pct, source="PARITY enabled")
    gl.read_gap_config = lambda *a, **k: cfg


def _time_grid(date_str: str):
    y, m, d = (int(x) for x in date_str.split("-"))
    t = datetime(y, m, d, 9, 0)
    end = datetime(y, m, d, 16, 30)
    while t <= end:
        yield t
        t += timedelta(minutes=5)


def _votes_summary(state_path: Path) -> dict:
    """state の votes から {race_id: (total_yen, tuple(sorted bet_specs))} を作る (投票成立のみ)。"""
    import json
    if not state_path.exists():
        return {}
    doc = json.loads(state_path.read_text(encoding="utf-8"))
    out = {}
    for rid, v in (doc.get("votes") or {}).items():
        if v.get("exit_code") != 0:
            continue
        specs = tuple(sorted(v.get("bet_specs") or []))
        out[rid] = (int(v.get("amount", 0) or 0), specs)
    return out


def run(date_str: str) -> int:
    _enable_gap()
    day_dir = date_dir_for(date_str)
    gap_sp = GAP.state_path(day_dir, live=False)
    orch_sp = ORCH.state_path(day_dir, live=False)
    for p in (gap_sp, orch_sp, GAP.lock_path(day_dir), ORCH.lock_path(day_dir)):
        try:
            p.unlink()
        except OSError:
            pass

    for now in _time_grid(date_str):
        GAP.run_pass(date_str, now=now, live=False, verbose=False)
        ORCH.run_pass(date_str, now=now, live=False, verbose=False)

    gap_v = _votes_summary(gap_sp)
    orch_v = _votes_summary(orch_sp)

    all_rids = sorted(set(gap_v) | set(orch_v))
    diffs = []
    for rid in all_rids:
        if gap_v.get(rid) != orch_v.get(rid):
            diffs.append((rid, gap_v.get(rid), orch_v.get(rid)))

    print(f"=== sleeve parity {date_str} ===")
    print(f"  gap_tansho_scheduler 投票: {len(gap_v)}レース")
    print(f"  sleeve_orchestrator  投票: {len(orch_v)}レース")
    for rid, gv in sorted(gap_v.items()):
        tag = "✓" if orch_v.get(rid) == gv else "✗"
        print(f"   {tag} {rid}: {gv[0]}円 {list(gv[1])}")
    if diffs:
        print(f"  ✗✗ 差分 {len(diffs)}件:")
        for rid, g, o in diffs:
            print(f"     {rid}: gap={g} orch={o}")
        print("RESULT: FAIL (挙動不一致)")
        return 1
    print(f"RESULT: PASS (差分0・{len(gap_v)}レース完全一致)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-06-21")
    return run(ap.parse_args().date)


if __name__ == "__main__":
    sys.exit(main())

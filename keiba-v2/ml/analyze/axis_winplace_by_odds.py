#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""軸◎の 単勝/複勝 ROI を ★軸の単勝オッズ帯★ 別に出す (Session 163 / ふくだ中穴ガツン検証)

ふくだ仮説 [[payout-ceiling-strategy]] / [[feedback_betting_philosophy]]:
  「単7-10倍くらいの中穴でガツン勝負するときに 単5000複15000 みたいな買い方はある。
   低オッズ本命に複600固定は薄利で意味が薄い」。
→ これを実払戻で検証する。 軸◎の 単勝ROI / 複勝ROI を ★軸の単勝オッズ帯★ で割り、
  「複は中穴(7-10倍)帯で本当に美味しく、 低オッズ帯では薄利か」を直接見る。

軸 = bettype_selection.evaluate_and_select(concentrate) の axis_umaban (= AI印◎/composite最強)。
精算 = haraimodoshi 実払戻 (単=tansho払戻 / 複=fukusho払戻)。 flat 100円/点で帯別 ROI を算出。
オッズ = predictions 直前オッズ (リークなし・本番同条件)。

CLI:
    python -m ml.analyze.axis_winplace_by_odds --start 2026-01 --end 2026-03-16
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402

# 軸単勝オッズ帯 (下限, ラベル)。 ふくだの「中穴7-10倍」を独立帯にする。
ODDS_BANDS: List[Tuple[float, float, str]] = [
    (1.0, 2.0, "1.0-2.0 (断然)"),
    (2.0, 3.5, "2.0-3.5 (人気)"),
    (3.5, 5.0, "3.5-5.0 (中堅)"),
    (5.0, 7.0, "5.0-7.0 (やや穴)"),
    (7.0, 10.0, "7.0-10.0 (中穴★)"),
    (10.0, 15.0, "10.0-15.0 (穴)"),
    (15.0, 9999.0, "15.0+ (大穴)"),
]


def _band(odds: float) -> str:
    for lo, hi, label in ODDS_BANDS:
        if lo <= odds < hi:
            return label
    return "不明"


@dataclass
class BandAgg:
    n: int = 0
    win_hit: int = 0
    place_hit: int = 0
    win_cost: float = 0.0
    win_payout: float = 0.0
    place_cost: float = 0.0
    place_payout: float = 0.0

    @property
    def win_roi(self):
        return self.win_payout / self.win_cost * 100 if self.win_cost else 0.0

    @property
    def place_roi(self):
        return self.place_payout / self.place_cost * 100 if self.place_cost else 0.0

    @property
    def win_rate(self):
        return self.win_hit / self.n * 100 if self.n else 0.0

    @property
    def place_rate(self):
        return self.place_hit / self.n * 100 if self.n else 0.0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--start", default="2026-01")
    p.add_argument("--end", default="2026-03-16")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    from ml.export_formation_backtest import load_predictions_races
    races = load_predictions_races(start_date=args.start, end_date=args.end)
    print(f"predictions.json: {len(races)} races ({args.start}~{args.end}, leak-free 直前オッズ)")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    print("  loading haraimodoshi (実払戻)...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi loaded: {len(haraimodoshi)}\n")

    bands: Dict[str, BandAgg] = {lbl: BandAgg() for *_, lbl in ODDS_BANDS}
    n_eval = 0
    for r in races:
        rid = str(r.get("race_id") or "")
        rpay = haraimodoshi.get(rid)
        if not rpay or not rpay.get("tansho"):
            continue
        sel = bs.evaluate_and_select(r, strategy="concentrate", ev_floor=bs.DEFAULT_EV_FLOOR)
        if sel is None:
            continue
        re_ = be.process_race(r, axis=sel.axis_umaban)
        if re_ is None:
            continue
        axis = re_.axis_umaban
        axis_odds = re_.axis_odds
        if not axis_odds or axis_odds <= 1.0:
            continue
        lbl = _band(axis_odds)
        a = bands[lbl]
        a.n += 1
        n_eval += 1
        # 単勝: 軸が1着なら tansho払戻
        win_pay = (rpay.get("tansho") or {}).get(axis, 0)
        a.win_cost += 100
        a.win_payout += win_pay
        if win_pay:
            a.win_hit += 1
        # 複勝: 軸が3着内なら fukusho払戻
        place_pay = (rpay.get("fukusho") or {}).get(axis, 0)
        a.place_cost += 100
        a.place_payout += place_pay
        if place_pay:
            a.place_hit += 1

    print(f"  評価レース: {n_eval}\n")
    print(f"{'='*92}")
    print(f"  軸◎の 単勝/複勝 ROI × 軸単勝オッズ帯 (flat 100円・haraimodoshi 実払戻)")
    print(f"  {'オッズ帯':<18}{'R数':>5}{'単的中':>7}{'単ROI':>8}{'複的中':>7}{'複ROI':>8}{'複の旨味':>10}")
    print(f"  {'-'*88}")
    for *_, lbl in ODDS_BANDS:
        a = bands[lbl]
        if a.n == 0:
            continue
        # 複の旨味 = 複ROI が控除率(複80%)からどれだけ上振れているか
        edge = a.place_roi - 80.0
        flag = "◎厚く" if edge >= 10 else ("○" if edge >= 0 else "△薄く")
        print(f"  {lbl:<18}{a.n:>5}{a.win_rate:>6.0f}%{a.win_roi:>7.0f}%"
              f"{a.place_rate:>6.0f}%{a.place_roi:>7.0f}%{edge:>+7.0f}pt {flag}")
    print(f"  {'-'*88}")
    print(f"  複の旨味=複ROI−控除率80% (+ = 控除率を埋めて余りある旨味帯=厚く / − = 薄利帯=薄く)")
    print(f"\n  ★ふくだ仮説の検証:★ 中穴(7-10倍)帯で複ROIが高ければ「中穴で複厚く」は正しい。")
    print(f"     断然(1-2倍)帯で複ROIが低ければ「低オッズ本命に複600固定」は薄利で正しくない。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""shobu_rate サイザー end-to-end dry 検証 (本番経路・投票しない) (Session 166)

★目的★: 本番 config (read_per_race_cap) と本番経路 (size_one_race) で shobu_rate が
  設計どおり動くか確認する。 実戦投入前の最終チェック。

★確認★:
  - 勝負R: rank_w◎ の単勝が厚く (cap=勝負レート上限) ・複勝なし
  - 通常R: cap が通常レートに縮む (total <= 通常cap) ・v2配分
  - 全レースで total <= per_race_cap (runner番人 _check_per_race_limits を通る)

引数: --date YYYY-MM-DD (既定=直近のオッズ確定済 predictions を手動指定)。
実行例: python -m ml.analyze.verify_shobu_rate_e2e --pred C:/KEIBA-CICD/data3/races/2026/06/14/predictions.json
"""
import argparse
import json

from ml.strategies.bettype_scheduler import size_one_race
from ml.strategies.freebudget_scheduler import read_per_race_cap
from ml.strategies.bettype_sizing import is_shobu_race
from ml.strategies import bettype_efficiency as be
from ml.strategies.bettype_selection import evaluate_and_select


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True, help="predictions.json のパス (オッズ確定済)")
    ap.add_argument("--ev-floor", type=float, default=0.85)
    args = ap.parse_args()

    cap = read_per_race_cap()
    print(f"本番 read_per_race_cap = {cap} (勝負レート上限・runner番人と同値)\n")
    d = json.load(open(args.pred, encoding="utf-8"))
    races = d.get("races", [])

    n_shobu = n_normal = n_over = 0
    normal_max = 0
    for pr in races:
        sel = evaluate_and_select(pr, strategy="concentrate", ev_floor=args.ev_floor)
        if sel is None or not sel.selected_plans:
            continue
        race_eff = be.process_race(pr, axis=sel.axis_umaban)
        if race_eff is None:
            continue
        shobu = is_shobu_race(race_eff)
        rs = size_one_race(pr, strategy="concentrate", ev_floor=args.ev_floor,
                           sizing="shobu_rate", bankroll=10000, per_race_cap=cap)
        if rs is None:
            continue
        label = f"{pr.get('venue_name')} {pr.get('race_number')}R"
        if rs.total_yen > cap:
            n_over += 1
            print(f"  ⚠ OVER CAP: {label} total={rs.total_yen} > {cap}")
        if shobu:
            n_shobu += 1
            t = next((l for l in rs.legs if l.bet_type == "tansho"), None)
            ty = t.amount if t else 0
            fk = [l for l in rs.legs if l.bet_type == "fukusho"]
            print(f"★勝負R {label}: total={rs.total_yen} 単勝={ty}"
                  f"({100*ty/rs.total_yen:.0f}%) 複勝={len(fk)}leg 軸={t.horses if t else '?'}")
        else:
            n_normal += 1
            normal_max = max(normal_max, rs.total_yen)

    print(f"\n=== 集計 ===")
    print(f"勝負R: {n_shobu} / 通常R: {n_normal}")
    print(f"通常R total 最大: {normal_max}円 (通常レートに縮むはず)")
    print(f"cap超過: {n_over} 件 (0であるべき=runner番人を全R通る)")


if __name__ == "__main__":
    main()

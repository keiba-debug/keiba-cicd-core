#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase2: 買い方テンプレ × レース特性 backtest (Session 146)

bet_templates のテンプレを全レースに適用し、 **haraimodoshi 実配当** で精算して
「テンプレ × レース特性」で 死に馬券率 / 的中率 / 連敗 / maxDD / ROI を出す。
理想の「レース特性で取捨選択するセレクタ(Phase3)」の判断根拠データを作るのが目的。

★精算は haraimodoshi(実払戻) 照合 = W9 で指摘された「combo payout が事前オッズ近似」を
  解消。 的中した組み合わせのみ payout、 それ以外は 0。 flat 100円/点で評価
  (sizing は Phase3 の責務)。

レース特性:
  - 頭数帯      : <=12 / 13-15 / 16+
  - 2強度       : top2(composite上位2頭) の win_prob 合計 (堅い/中/混戦)
  - 軸EV帯      : ◎(composite1位) の win_prob×odds
  - 荒れ度      : 1番人気(最小odds)の単勝オッズ

CLI:
    python -m ml.analyze.backtest_bet_templates
    python -m ml.analyze.backtest_bet_templates --split-date 2026-01-01 --max-rest 4
"""

from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402
from core.db import get_connection  # noqa: E402


# ---------------------------------------------------------------------------
# haraimodoshi 実配当ローダー (全券種)
# ---------------------------------------------------------------------------

def _pi(s) -> int:
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0


def load_haraimodoshi(race_codes: List[str]) -> Dict[str, dict]:
    """RACE_CODE -> {bet_type: {key: payout_per_100yen}}。

    key: tansho/fukusho=馬番(int), umaren/wide/sanrenpuku=frozenset, umatan/sanrentan=tuple(着順)。
    """
    cols = ["RACE_CODE"]
    for i in range(1, 4):
        cols += [f"TANSHO{i}_UMABAN", f"TANSHO{i}_HARAIMODOSHIKIN"]
    for i in range(1, 6):
        cols += [f"FUKUSHO{i}_UMABAN", f"FUKUSHO{i}_HARAIMODOSHIKIN"]
    for i in range(1, 4):
        cols += [f"UMAREN{i}_KUMIBAN1", f"UMAREN{i}_KUMIBAN2", f"UMAREN{i}_HARAIMODOSHIKIN"]
    for i in range(1, 8):
        cols += [f"WIDE{i}_KUMIBAN1", f"WIDE{i}_KUMIBAN2", f"WIDE{i}_HARAIMODOSHIKIN"]
    for i in range(1, 7):
        cols += [f"UMATAN{i}_KUMIBAN1", f"UMATAN{i}_KUMIBAN2", f"UMATAN{i}_HARAIMODOSHIKIN"]
    for i in range(1, 4):
        cols += [f"SANRENPUKU{i}_KUMIBAN1", f"SANRENPUKU{i}_KUMIBAN2",
                 f"SANRENPUKU{i}_KUMIBAN3", f"SANRENPUKU{i}_HARAIMODOSHIKIN"]
    for i in range(1, 7):
        cols += [f"SANRENTAN{i}_KUMIBAN1", f"SANRENTAN{i}_KUMIBAN2",
                 f"SANRENTAN{i}_KUMIBAN3", f"SANRENTAN{i}_HARAIMODOSHIKIN"]
    col_str = ", ".join(cols)
    out: Dict[str, dict] = {}
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        for s in range(0, len(race_codes), 500):
            batch = race_codes[s:s + 500]
            ph = ",".join(["%s"] * len(batch))
            cur.execute(f"SELECT {col_str} FROM haraimodoshi WHERE RACE_CODE IN ({ph})", batch)
            for row in cur.fetchall():
                rc = row["RACE_CODE"].strip()
                pay: Dict[str, dict] = {bt_: {} for bt_ in
                                        ("tansho", "fukusho", "umaren", "wide",
                                         "umatan", "sanrenpuku", "sanrentan")}
                for i in range(1, 4):
                    u = _pi(row.get(f"TANSHO{i}_UMABAN")); p = _pi(row.get(f"TANSHO{i}_HARAIMODOSHIKIN"))
                    if u and p:
                        pay["tansho"][u] = p
                for i in range(1, 6):
                    u = _pi(row.get(f"FUKUSHO{i}_UMABAN")); p = _pi(row.get(f"FUKUSHO{i}_HARAIMODOSHIKIN"))
                    if u and p:
                        pay["fukusho"][u] = p
                for i in range(1, 4):
                    a = _pi(row.get(f"UMAREN{i}_KUMIBAN1")); b = _pi(row.get(f"UMAREN{i}_KUMIBAN2"))
                    p = _pi(row.get(f"UMAREN{i}_HARAIMODOSHIKIN"))
                    if a and b and p:
                        pay["umaren"][frozenset({a, b})] = p
                for i in range(1, 8):
                    a = _pi(row.get(f"WIDE{i}_KUMIBAN1")); b = _pi(row.get(f"WIDE{i}_KUMIBAN2"))
                    p = _pi(row.get(f"WIDE{i}_HARAIMODOSHIKIN"))
                    if a and b and p:
                        pay["wide"][frozenset({a, b})] = p
                for i in range(1, 7):
                    a = _pi(row.get(f"UMATAN{i}_KUMIBAN1")); b = _pi(row.get(f"UMATAN{i}_KUMIBAN2"))
                    p = _pi(row.get(f"UMATAN{i}_HARAIMODOSHIKIN"))
                    if a and b and p:
                        pay["umatan"][(a, b)] = p
                for i in range(1, 4):
                    a = _pi(row.get(f"SANRENPUKU{i}_KUMIBAN1")); b = _pi(row.get(f"SANRENPUKU{i}_KUMIBAN2"))
                    c = _pi(row.get(f"SANRENPUKU{i}_KUMIBAN3")); p = _pi(row.get(f"SANRENPUKU{i}_HARAIMODOSHIKIN"))
                    if a and b and c and p:
                        pay["sanrenpuku"][frozenset({a, b, c})] = p
                for i in range(1, 7):
                    a = _pi(row.get(f"SANRENTAN{i}_KUMIBAN1")); b = _pi(row.get(f"SANRENTAN{i}_KUMIBAN2"))
                    c = _pi(row.get(f"SANRENTAN{i}_KUMIBAN3")); p = _pi(row.get(f"SANRENTAN{i}_HARAIMODOSHIKIN"))
                    if a and b and c and p:
                        pay["sanrentan"][(a, b, c)] = p
                out[rc] = pay
        cur.close()
    return out


def ticket_payout(tk: bt.Ticket, race_pay: dict) -> int:
    """Ticket の 100円あたり払戻 (ハズレ=0)。"""
    table = race_pay.get(tk.bet_type) or {}
    if tk.bet_type in ("tansho", "fukusho"):
        return table.get(tk.horses[0], 0)
    if tk.bet_type in ("umaren", "wide", "sanrenpuku"):
        return table.get(frozenset(tk.horses), 0)
    if tk.bet_type in ("umatan", "sanrentan"):
        return table.get(tuple(tk.horses), 0)
    return 0


# ---------------------------------------------------------------------------
# レース特性
# ---------------------------------------------------------------------------

def race_features(race_eff) -> dict:
    s = race_eff.strengths
    n = len(s)
    axis = s[0] if s else None
    top2 = (s[0].win_prob + s[1].win_prob) if n >= 2 else (axis.win_prob if axis else 0.0)
    min_odds = min((x.odds for x in s if x.odds and x.odds > 0), default=0.0)
    axis_ev = (axis.win_prob * axis.odds) if (axis and axis.odds) else 0.0
    # 帯分け
    if n <= 12:
        fld = "頭数<=12"
    elif n <= 15:
        fld = "頭数13-15"
    else:
        fld = "頭数16+"
    if top2 >= 0.50:
        strg = "堅い(2強)"
    elif top2 >= 0.35:
        strg = "中"
    else:
        strg = "混戦"
    if axis_ev >= 1.1:
        evb = "軸EV>=1.1"
    elif axis_ev >= 0.9:
        evb = "軸EV0.9-1.1"
    else:
        evb = "軸EV<0.9"
    if min_odds and min_odds < 2.5:
        arr = "1人気<2.5(堅)"
    elif min_odds and min_odds < 4.0:
        arr = "1人気2.5-4"
    else:
        arr = "1人気4+(荒)"
    return {"頭数": fld, "強弱": strg, "軸EV": evb, "荒れ": arr}


# ---------------------------------------------------------------------------
# 集計
# ---------------------------------------------------------------------------

@dataclass
class Agg:
    n_races: int = 0
    points: int = 0
    cost: float = 0.0
    payout: float = 0.0
    hit_races: int = 0          # 1点でも的中したレース
    # 時系列 (テンプレ全体のみ): 連敗・maxDD
    cum_pnl: float = 0.0
    peak: float = 0.0
    max_dd: float = 0.0
    cur_streak: int = 0
    max_streak: int = 0

    def add_race(self, cost: float, payout: float, track_series: bool = False):
        self.n_races += 1
        self.cost += cost
        self.payout += payout
        hit = payout > 0
        if hit:
            self.hit_races += 1
        if track_series:
            self.cum_pnl += payout - cost
            self.peak = max(self.peak, self.cum_pnl)
            dd = self.peak - self.cum_pnl
            self.max_dd = max(self.max_dd, dd)
            if hit:
                self.cur_streak = 0
            else:
                self.cur_streak += 1
                self.max_streak = max(self.max_streak, self.cur_streak)

    @property
    def roi(self):
        return self.payout / self.cost * 100 if self.cost > 0 else 0.0

    @property
    def hit_rate(self):
        return self.hit_races / self.n_races * 100 if self.n_races else 0.0

    @property
    def dead_rate(self):
        return (1 - self.hit_races / self.n_races) * 100 if self.n_races else 0.0


def run(races, *, template_names, max_rest, split_date):
    preds, codes = [], []
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        if split_date and str(pred["race_id"])[:8] < split_date:
            continue
        if not any(int(e.get("finish_position") or 99) == 1 for e in pred.get("entries", [])):
            continue
        preds.append(pred)
        codes.append(str(pred["race_id"]))
    print(f"  races={len(preds)}  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi loaded: {len(haraimodoshi)}")

    overall: Dict[str, Agg] = {n: Agg() for n in template_names}
    cross: Dict[str, Dict[str, Dict[str, Agg]]] = {
        n: defaultdict(lambda: defaultdict(Agg)) for n in template_names}

    preds.sort(key=lambda p: str(p["race_id"]))
    for pred in preds:
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        ranking = [s.umaban for s in re_.strengths]  # composite 降順
        marks = bt.marks_from_ranking(ranking, max_rest=max_rest)
        feats = race_features(re_)
        rpay = haraimodoshi.get(str(pred["race_id"]), {})
        for name in template_names:
            tmpl = bt.get_template(name)
            tickets = bt.apply_template(tmpl, marks)
            if not tickets:
                continue
            cost = 100.0 * len(tickets)
            payout = sum(ticket_payout(tk, rpay) for tk in tickets) * 1.0
            overall[name].add_race(cost, payout, track_series=True)
            for dim, val in feats.items():
                cross[name][dim][val].add_race(cost, payout)
    return overall, cross


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--split-date", default=None, help="valid(>=)のみ (YYYY-MM-DD)")
    p.add_argument("--max-rest", type=int, default=4, help="△(ヒモ)の頭数上限")
    p.add_argument("--templates", default=None, help="カンマ区切り (既定=全テンプレ)")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    split = args.split_date.replace("-", "") if args.split_date else None
    names = ([x.strip() for x in args.templates.split(",")] if args.templates
             else bt.list_templates())

    print(f"backtest_cache: {len(races)} races"
          + (f"  valid>={args.split_date}" if split else "")
          + f"  max_rest={args.max_rest}")
    overall, cross = run(races, template_names=names, max_rest=args.max_rest, split_date=split)

    print(f"\n{'='*92}")
    print(f"  テンプレ別 (flat 100円/点・haraimodoshi実配当)")
    print(f"  {'template':<20}{'系統':<7}{'pts/R':>7}{'的中率':>8}{'死率':>7}"
          f"{'連敗':>5}{'maxDD':>9}{'ROI':>8}")
    print(f"  {'-'*88}")
    for n in names:
        a = overall[n]
        t = bt.get_template(n)
        pts_per_race = (a.cost / 100.0 / a.n_races) if a.n_races else 0
        print(f"  {n:<20}{t.system:<7}{pts_per_race:>7.1f}{a.hit_rate:>7.1f}%{a.dead_rate:>6.1f}%"
              f"{a.max_streak:>5}{a.max_dd:>9,.0f}{a.roi:>7.1f}%"
              + ("  [隔離]" if t.ringfenced else ""))
    print(f"  {'-'*88}")
    print(f"  pts/R=1レース平均点数 / 的中率=1点でも当たったレース率 / 死率=全外し率 / "
          f"連敗=最大連続全外し / maxDD=累積pnlの最大DD(円)")

    # レース特性クロス (ROI / 的中率)
    for dim in ("頭数", "強弱", "軸EV", "荒れ"):
        print(f"\n--- レース特性[{dim}] × テンプレ : ROI%% (的中率%%, n) ---")
        # 値の一覧を収集
        vals = sorted({v for n in names for v in cross[n][dim].keys()})
        header = "  {:<20}".format("template") + "".join(f"{v:>20}" for v in vals)
        print(header)
        for n in names:
            row = "  {:<20}".format(n)
            for v in vals:
                a = cross[n][dim].get(v)
                if a and a.n_races:
                    row += f"{a.roi:>6.0f}% ({a.hit_rate:>3.0f}%,{a.n_races:>4})"
                else:
                    row += f"{'-':>20}"
            print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())

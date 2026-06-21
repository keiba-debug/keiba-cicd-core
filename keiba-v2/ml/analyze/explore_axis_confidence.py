#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""① 頭の数 (◎への信頼度) 探索 — ◎の2着リスク信号 × n_head_max のクロス集計 (S172)。

動的点数 §5.0 ① の効きどころ探索。 現行 n_head=3 固定の本番フォメで、 ◎の「勝ち切らない
リスク (2着リスク)」信号でレースを3分位に層別し、 各層で n_head_max を 1〜5 に振ると成績が
どう動くかを ★1回のDBパス★ で見る。

仮説 (ふくだ知恵 [[maru-second-place-formation]] / §5.0 ①):
  ◎が「来るが勝ち切らない」(低 win_share / 過剰人気 / 接戦) レースほど妙味頭を複数立てる
  (n_head↑) のが効く (誰かが1着なら◎2-3着で配当が跳ねる)。 逆に◎が1強 (高 win_share /
  ◎の格が抜けている) なら頭を絞る (n_head↓) のが効く。

★発動レース集合は n_head に依存しない★ (select_head は候補が1頭でもあれば発動、 n_head_max は
  トリム上限なso)。 ゆえに層 (◎信号の分位) を固定したまま頭数だけ比較できる = クリーン。

精算 = haraimodoshi 実払戻 (リークなし)。 trim 用三連単 OD は確定値注入 (時系列なし=近似)。
本番ゲート (gap0.4/ev1.5/wp0.15) 維持 = 本番に発動するレース内での効きどころを見る。

CLI:
    python -m ml.analyze.explore_axis_confidence                 # win_share で層別
    python -m ml.analyze.explore_axis_confidence --signal win_ev
    python -m ml.analyze.explore_axis_confidence --all-signals   # 信号分布だけ先に
    python -m ml.analyze.explore_axis_confidence --start 2026-01 --end 2026-05-31
"""
from __future__ import annotations

import argparse
import io
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.odds_db import _parse_ninki, parse_odds_value  # noqa: E402
from ml.analyze.analyze_paddock_signal import load_paddock_marks  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.analyze.validate_sanrentan_formation import RaceAgg, _legs_to_bets  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.strategies import sanrentan_formation as sf  # noqa: E402
from ml.strategies.anaba_picks import load_anaba_backtest  # noqa: E402
from ml.strategies.role_split import win_share  # noqa: E402

DEFAULT_PER_RACE_CAP = 5200
BASE_NH = 3                       # 現行本番の n_head_max
N_HEADS = [1, 2, 3, 4, 5]        # 探索する頭数 (絞る ← 現行 → 増やす)
WALL = 72.5                       # 三連系 控除率の壁


def _load_all_trifecta_odds(codes: List[str]) -> Dict[str, dict]:
    """三連単確定オッズ (odds6_sanrentan) を ★全 rid バッチ一括取得★ → {rid: {kumiban: {odds,ninki}}}。

    get_final_trifecta_odds をレース毎に呼ぶと毎回 new connection → TIME_WAIT 累積で
    ephemeral port 枯渇 (WinError 10048)。 IN 句チャンクで接続数を 1423→数回に激減させる。
    """
    from core.db import query
    out: Dict[str, dict] = {}
    uniq = [c for c in dict.fromkeys(codes) if c]
    CH = 400
    for i in range(0, len(uniq), CH):
        chunk = uniq[i:i + CH]
        ph = ",".join(["%s"] * len(chunk))
        rows = query(
            f"SELECT RACE_CODE, KUMIBAN, ODDS, NINKI FROM odds6_sanrentan WHERE RACE_CODE IN ({ph})",
            tuple(chunk))
        for r in rows:
            o = parse_odds_value(r["ODDS"])
            if o is None:
                continue
            out.setdefault(str(r["RACE_CODE"]), {})[r["KUMIBAN"]] = {
                "odds": o, "ninki": _parse_ninki(r["NINKI"])}
    return out


def _axis_strength(race_eff):
    for s in race_eff.strengths:
        if s.umaban == race_eff.axis_umaban:
            return s
    return None


def _n_myomi_heads(race_eff) -> int:
    """◎以外の妙味頭候補数 (本番ゲート pred_w≥0.15 ∧ win_ev≥1.5・上限なし)。"""
    return len(sf.select_head(race_eff, race_eff.axis_umaban, n_max=99))


# 信号 = ◎の「勝ち切らないリスク (2着リスク)」を測る材料。 値の高低の意味はコメント参照。
SIGNALS = {
    # 低いほど「来るが勝ち切らない」= 2着リスク高 (フォメの旨味が出る場面)
    "win_share": lambda ax, eff: win_share(ax.pred_w, ax.pred_p),
    # 低いほど過剰人気 (オッズ安いのに期待値が低い = 市場が買いすぎ)
    "win_ev": lambda ax, eff: ax.win_ev,
    # ◎の格 (大きいほど抜け本命 = 1強寄り)
    "axis_gap": lambda ax, eff: sf.axis_gap(eff, eff.axis_umaban),
    # 予測着差 (向き=接戦か1強かはデータで確認)
    "margin": lambda ax, eff: ax.predicted_margin,
    # 妙味頭が何頭立つか (多いほど頭を増やせる余地)
    "n_myomi": lambda ax, eff: float(_n_myomi_heads(eff)),
}


def _fmt_row(label: str, s: dict, suffix: str = "") -> str:
    star = " ★" if s["med_roi"] >= WALL else ""
    return (f"    {label:16}{s['n_races']:>7}{s['avg_pts']:>6.1f}{s['roi']:>6.0f}%"
            f"{s['med_roi']:>6.0f}%{s['hit_race_pct']:>6.0f}%{s['big1000']:>7}"
            f"{s['max_pay']:>11,.0f}{s['pnl']:>+11,.0f}{star}{suffix}")


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start", default="2026-01")
    ap.add_argument("--end", default="2026-05-31")
    ap.add_argument("--strategy", default="concentrate")
    ap.add_argument("--per-race-cap", type=int, default=DEFAULT_PER_RACE_CAP)
    ap.add_argument("--signal", default="win_share", choices=list(SIGNALS))
    ap.add_argument("--all-signals", action="store_true", help="信号の分布だけ先に出して終了")
    args = ap.parse_args()

    from ml.export_formation_backtest import load_predictions_races
    races = load_predictions_races(start_date=args.start, end_date=args.end)
    print(f"predictions: {len(races)} races ({args.start}~{args.end}, 直前オッズ leak-free)")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    haraimodoshi = load_haraimodoshi(codes)
    anaba = load_anaba_backtest(codes)
    paddock = load_paddock_marks(codes)
    trifecta = _load_all_trifecta_odds(codes)
    print(f"  haraimodoshi={len(haraimodoshi)}  印4={len(anaba)}  パドック={len(paddock)}"
          f"  三連単OD={len(trifecta)}R")

    sig_fn = SIGNALS[args.signal]
    records = []          # (rid, signal_val, {nh: [Bet]})
    all_sig_vals: Dict[str, list] = defaultdict(list)
    n_eval = 0
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("sanrentan"):
            continue
        sel = bs.evaluate_and_select(r, strategy=args.strategy, ev_floor=bs.DEFAULT_EV_FLOOR)
        if sel is None:
            continue
        race_eff = be.process_race(r, axis=sel.axis_umaban)
        if race_eff is None or not race_eff.strengths:
            continue
        ax = _axis_strength(race_eff)
        if ax is None:
            continue
        n_eval += 1
        if n_eval % 200 == 0:
            print(f"   ... {n_eval} races", file=sys.stderr)
        st_odds = trifecta.get(rid, {})
        anaba_u = anaba.get(rid, [])
        pad = paddock.get(rid, {})
        per_nh = {}
        for nh in N_HEADS:
            rs = sz.size_race_sanrentan_formation(
                race_eff, sel, bankroll=10000, per_race_cap=args.per_race_cap,
                sanrentan_odds=st_odds, anaba_umabans=anaba_u, paddock_marks=pad,
                n_head_max=nh)
            per_nh[nh] = _legs_to_bets(rid, rs.legs, race_pay)
        if not per_nh[BASE_NH]:
            continue  # 本番 (n_head=3) で見送りのレースは対象外
        for name, fn in SIGNALS.items():
            v = fn(ax, race_eff)
            if v is not None:
                all_sig_vals[name].append(v)
        sval = sig_fn(ax, race_eff)
        if sval is None:
            continue
        records.append((rid, sval, per_nh))

    print(f"\n  発動レース (本番 n_head={BASE_NH}) = {len(records)}")

    # 全信号の分布 (バケット閾値・欠損率の参考)
    print("\n■ ◎信号の分布 (発動レース)")
    for name in SIGNALS:
        vals = sorted(all_sig_vals[name])
        if not vals:
            print(f"  {name:10} (値なし)")
            continue
        q = statistics.quantiles(vals, n=4) if len(vals) >= 4 else [vals[0]] * 3
        cov = len(vals) / len(records) * 100 if records else 0
        print(f"  {name:10} n={len(vals):4} ({cov:3.0f}%)  min={vals[0]:7.3f}  Q1={q[0]:7.3f}"
              f"  med={statistics.median(vals):7.3f}  Q3={q[2]:7.3f}  max={vals[-1]:7.3f}")
    if args.all_signals:
        return 0

    # 選択信号で3分位バケット
    sigs = sorted(s for _, s, _ in records)
    if len(sigs) < 9:
        print("  サンプル不足 (>=9 必要)")
        return 0
    tq = statistics.quantiles(sigs, n=3)
    t_lo, t_hi = tq[0], tq[1]
    b1, b2, b3 = f"Q1 低 <{t_lo:.2f}", f"Q2 中 {t_lo:.2f}-{t_hi:.2f}", f"Q3 高 >{t_hi:.2f}"

    def bucket(s: float) -> str:
        if s < t_lo:
            return b1
        if s > t_hi:
            return b3
        return b2

    BUCKETS = [b1, b2, b3]
    arms = {b: {nh: RaceAgg() for nh in N_HEADS} for b in BUCKETS}
    for rid, sval, per_nh in records:
        b = bucket(sval)
        for nh in N_HEADS:
            arms[b][nh].add_race(rid, per_nh[nh])

    print(f"\n■ 信号={args.signal} 別 × n_head_max クロス (現行=n_head{BASE_NH}・絞り↑広げ↓)")
    hdr = (f"    {'n_head':16}{'発動R':>7}{'点/R':>6}{'ROI':>7}{'月中央':>7}"
           f"{'的中R%':>7}{'≥1000':>7}{'最高配当':>11}{'PnL':>11}")
    for b in BUCKETS:
        print(f"\n  ◆ {b}")
        print(hdr)
        for nh in N_HEADS:
            s = arms[b][nh].summary()
            if not s:
                print(f"    n_head={nh}  (発動なし)")
                continue
            suffix = "  ←現行" if nh == BASE_NH else ""
            print(_fmt_row(f"n_head={nh}", s, suffix))
    print(f"\n  ★=月中央≥{WALL}% (三連系 控除率の壁)。 精算=haraimodoshi 実払戻 (リークなし)")
    print("  読み: 各 bucket で現行(n_head=3)より月中央/天井が伸びる頭数があれば、 その bucket は出し分けの効きどころ")
    return 0


if __name__ == "__main__":
    sys.exit(main())

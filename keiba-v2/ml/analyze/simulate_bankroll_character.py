#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""買い方キャラ別 2層バンクロールシミュレーション (Session 149 / T12)

bet_templates の買い方テンプレを「キャラ (characters.py)」単位で、 過去開催日を
複利で回し、 キャラごとの 総資金成長 / maxDD / Sharpe / 破産確率 を比較する。
simulate_bankroll_bettype (bettype 選定経路) のテンプレ語彙版。 複利・破産 MC・
メトリクスは bankroll_core を共有し、 買い目生成 (テンプレ展開 → weight 配分精算)
だけが違う。

★買い目生成・精算 (export_bet_template_lab._settle_template と同型):
  - markset: composite 序列 → ◎○▲△Ⅲ top5 (bt.marks_from_ranking) / または実 AI印 (崖カット)。
  - テンプレ展開: bt.apply_template → Ticket[] (順序系=着順, 順不同系=昇順)。
  - 精算: ticket_payout で haraimodoshi 実配当。 1点 stake = base_unit × weight、
    base_unit = 総資金 W × unit_fraction (比例ベット = 複利)。 weight 比は ROI 特性を保つ。

★検証規律 (bet-template-lab と同じ・データスヌーピング防止):
  - 複利軌道は全期間 (後知恵込みの表示用)。 正直な OOS は flat 集計の roi_valid (split分割)。
  - 月別 ROI 中央値で万馬券1本の上振れを排除。

CLI:
    python -m ml.analyze.simulate_bankroll_character
    python -m ml.analyze.simulate_bankroll_character --w0 300000 --split-date 2026-01-01
    python -m ml.analyze.simulate_bankroll_character --characters honmei,wide_kenjitsu --mc 1000
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import load_haraimodoshi, ticket_payout  # noqa: E402
from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.analyze.bankroll_core import (  # noqa: E402
    DEFAULT_MC, TrajectoryStats, compute_trajectory_stats,
)
from ml.ai_marks.assign import assign_ai_marks  # noqa: E402
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import characters as ch  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

DEFAULT_W0 = 300_000
DEFAULT_SPLIT = "2026-01-01"

# AI印 (記号) → テンプレ markset 語彙。 穴は最下位 Ⅲ に合流 (export_bet_template_lab と同じ)。
AI_TO_TEMPLATE_MARK = {"◎": "◎", "○": "○", "▲": "▲", "△": "△", "Ⅲ": "Ⅲ", "穴": "Ⅲ"}


def ai_marks_to_markset(ai_marks: Dict[int, str]) -> Dict[str, List[int]]:
    """assign_ai_marks の {umaban: 記号} をテンプレ markset {記号: [umaban]} に変換。"""
    ms: Dict[str, List[int]] = {}
    for uma, sym in ai_marks.items():
        t = AI_TO_TEMPLATE_MARK.get(sym)
        if t:
            ms.setdefault(t, []).append(int(uma))
    return ms


# ---------------------------------------------------------------------------
# Phase A: レースごとのキャラ別 100円ベース精算をキャッシュ (bankroll 非依存)
# ---------------------------------------------------------------------------

@dataclass
class TmplRaceCtx:
    """1 レースの bankroll 非依存コンテキスト。 settle[char_key] = (cost_100, payout_100)。"""
    rid: str
    date: str
    settle: Dict[str, Tuple[float, float]]


def settle_templates_cp(template_names, marks: Dict[str, List[int]], rpay: dict) -> Tuple[float, float]:
    """複数テンプレを 100円ベースで精算 → (cost, payout)。 1点 stake=100×weight・払戻も weight 比例。

    base_unit へのスケールは simulate_day_character 側で cost/payout に base_unit/100 を掛ける。
    """
    cost = payout = 0.0
    for name in template_names:
        for tk in bt.apply_template(bt.get_template(name), marks):
            cost += 100.0 * tk.weight
            p = ticket_payout(tk, rpay)
            if p > 0:
                payout += p * tk.weight
    return cost, payout


def build_tmpl_contexts(races, *, characters, haraimodoshi) -> Dict[str, List[TmplRaceCtx]]:
    """日付 -> [TmplRaceCtx]。 結果確定レースのみ。 全期間 (複利は全期間・OOS は集計側)。"""
    by_date: Dict[str, List[TmplRaceCtx]] = {}
    n_total = n_kept = 0
    # markset モードはキャラが使う分だけ計算 (composite は常時、ai は使うキャラが居れば)
    need_ai = any(c.mark_mode == "ai" for c in characters)
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        n_total += 1
        if not any(int(e.get("finish_position") or 99) == 1
                   for e in pred.get("entries", [])):
            continue
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        s = re_.strengths
        rid = str(pred["race_id"])
        rpay = haraimodoshi.get(rid, {})
        markset_by_mode: Dict[str, Dict[str, List[int]]] = {
            "composite": bt.marks_from_ranking([x.umaban for x in s]),
        }
        if need_ai:
            ai_res = assign_ai_marks(pred["entries"], step=2)
            markset_by_mode["ai"] = (ai_marks_to_markset(ai_res.marks)
                                     if not ai_res.skipped else {})
        settle: Dict[str, Tuple[float, float]] = {}
        for char in characters:
            marks = markset_by_mode.get(char.mark_mode, {})
            settle[char.key] = settle_templates_cp(char.templates, marks, rpay)
        by_date.setdefault(rid[:8], []).append(
            TmplRaceCtx(rid=rid, date=rid[:8], settle=settle))
        n_kept += 1
    print(f"  contexts: {n_kept}/{n_total} races kept, {len(by_date)} days")
    return dict(sorted(by_date.items()))


# ---------------------------------------------------------------------------
# Phase B: 1 開催日の買い目生成 (bankroll_core の simulate_day_fn 契約)
# ---------------------------------------------------------------------------

def simulate_day_character(ctxs: List[TmplRaceCtx], *, day_start: int, w_total: float,
                           char_key: str, unit_fraction: float) -> Tuple[float, float]:
    """1 開催日を時系列順に回す。 戻り: (day_cost, day_payout)。

    1点 base_unit = w_total × unit_fraction (総資金比例 = 複利)。 各レースの 100円ベース
    精算を base_unit/100 にスケール。 先着順 (rid 昇順) で day_start を超えたら見送り (live 再現)。
    """
    base_unit = w_total * unit_fraction
    voted = cost_sum = payout_sum = 0.0
    for ctx in sorted(ctxs, key=lambda c: c.rid):
        c100, p100 = ctx.settle.get(char_key, (0.0, 0.0))
        if c100 <= 0:
            continue
        cost = c100 * base_unit / 100.0
        if voted + cost > day_start:
            continue  # 予算超過は先着順で見送り (live 再現)
        payout = p100 * base_unit / 100.0
        voted += cost
        cost_sum += cost
        payout_sum += payout
    return cost_sum, payout_sum


# ---------------------------------------------------------------------------
# flat OOS 集計 (検証規律: roi_train/roi_valid/median_roi)
# ---------------------------------------------------------------------------

def _ym(date8: str) -> str:
    return f"{date8[:4]}-{date8[4:6]}"


def aggregate_char_flat(by_date: Dict[str, List[TmplRaceCtx]], char_key: str, *,
                        split: str) -> dict:
    """flat 100円ベースで 全期間/train/valid/月別中央値 ROI を算出 (後知恵防止の主軸)。"""
    cost = payout = 0.0
    cost_tr = pay_tr = cost_va = pay_va = 0.0
    monthly: Dict[str, dict] = defaultdict(
        lambda: {"inv": 0.0, "ret": 0.0, "fire": 0, "hits": 0})
    fire = hits = 0
    for date in sorted(by_date):
        for ctx in by_date[date]:
            c, p = ctx.settle.get(char_key, (0.0, 0.0))
            if c <= 0:
                continue
            cost += c
            payout += p
            fire += 1
            ym = _ym(date)
            monthly[ym]["inv"] += c
            monthly[ym]["ret"] += p
            monthly[ym]["fire"] += 1
            if p > 0:
                hits += 1
                monthly[ym]["hits"] += 1
            if date < split:
                cost_tr += c
                pay_tr += p
            else:
                cost_va += c
                pay_va += p
    roi = payout / cost * 100 if cost > 0 else 0.0
    roi_tr = pay_tr / cost_tr * 100 if cost_tr > 0 else 0.0
    roi_va = pay_va / cost_va * 100 if cost_va > 0 else 0.0

    months_sorted = sorted(monthly)
    roi_vals: List[float] = []
    monthly_out: List[dict] = []
    for m in months_sorted:
        mm = monthly[m]
        m_roi = mm["ret"] / mm["inv"] * 100 if mm["inv"] > 0 else 0.0
        roi_vals.append(m_roi)
        monthly_out.append({
            "month": m, "fire": mm["fire"], "inv": round(mm["inv"]),
            "ret": round(mm["ret"]), "hits": mm["hits"],
            "roi": round(m_roi, 1), "pnl": round(mm["ret"] - mm["inv"]),
        })
    median_roi = statistics.median(roi_vals) if roi_vals else 0.0
    plus = sum(1 for v in roi_vals if v >= 100)
    mid = len(months_sorted) // 2
    fh_inv = sum(monthly[m]["inv"] for m in months_sorted[:mid])
    fh_ret = sum(monthly[m]["ret"] for m in months_sorted[:mid])
    sh_inv = sum(monthly[m]["inv"] for m in months_sorted[mid:])
    sh_ret = sum(monthly[m]["ret"] for m in months_sorted[mid:])
    return {
        "fire": fire, "hits": hits,
        "hit_rate": round(hits / fire * 100, 1) if fire else 0.0,
        "roi": round(roi, 1), "roi_train": round(roi_tr, 1), "roi_valid": round(roi_va, 1),
        "median_roi": round(median_roi, 1), "plus_months": f"{plus}/{len(roi_vals)}",
        "roi_first_half": round(fh_ret / fh_inv * 100, 1) if fh_inv > 0 else 0.0,
        "roi_second_half": round(sh_ret / sh_inv * 100, 1) if sh_inv > 0 else 0.0,
        "monthly": monthly_out,
    }


# ---------------------------------------------------------------------------
# 1 キャラの複利 + flat 集計
# ---------------------------------------------------------------------------

@dataclass
class CharResult:
    char: ch.Character
    eff_w0: int
    day_fraction: float
    unit_fraction: float
    stats: TrajectoryStats
    flat: dict = field(default_factory=dict)


def run_character(char: ch.Character, by_date: Dict[str, List[TmplRaceCtx]], *,
                  w0: int, mc: int, split: str,
                  unit_override=None, day_override=None) -> CharResult:
    unit_f = unit_override if unit_override is not None else char.unit_fraction
    day_f = day_override if day_override is not None else char.day_fraction
    # ringfenced は初期資金を隔離枠 (総資金 × cap_pct) に。 補充なし=枯渇で停止 (w<=0 break)。
    eff_w0 = int(w0 * char.ringfence_cap_pct) if char.ringfenced else w0
    stats = compute_trajectory_stats(
        by_date, w0=eff_w0, day_fraction=day_f,
        simulate_day_fn=simulate_day_character,
        day_kwargs={"char_key": char.key, "unit_fraction": unit_f}, mc=mc)
    flat = aggregate_char_flat(by_date, char.key, split=split)
    return CharResult(char=char, eff_w0=eff_w0, day_fraction=day_f,
                      unit_fraction=unit_f, stats=stats, flat=flat)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--w0", type=int, default=DEFAULT_W0, help="初期総資金")
    p.add_argument("--split-date", default=DEFAULT_SPLIT, help="train/valid 分割 (OOS)")
    p.add_argument("--characters", default=None, help="カンマ区切り key (既定=全キャラ)")
    p.add_argument("--mc", type=int, default=DEFAULT_MC, help="破産確率 MC 試行数")
    p.add_argument("--unit-fraction", type=float, default=None, help="1点比率の全体上書き")
    p.add_argument("--day-fraction", type=float, default=None, help="day_fraction の全体上書き")
    p.add_argument("--max-races", type=int, default=None, help="先頭N件のみ (テスト用)")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    split = args.split_date.replace("-", "")
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    if args.max_races:
        races = races[:args.max_races]
    chars = ([ch.get_character(k.strip()) for k in args.characters.split(",")]
             if args.characters else ch.CHARACTERS)

    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]
    print(f"backtest_cache: {len(races)} races  W0={args.w0:,}  split={args.split_date}")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}  building contexts (process_race)...")
    by_date = build_tmpl_contexts(races, characters=chars, haraimodoshi=haraimodoshi)
    if not by_date:
        print("  [ERROR] no contexts built")
        return 1

    results = [run_character(c, by_date, w0=args.w0, mc=args.mc, split=split,
                             unit_override=args.unit_fraction,
                             day_override=args.day_fraction)
               for c in chars]

    print(f"\n{'='*112}")
    print(f"  {'character':<16}{'mode':>5}{'df%':>5}{'finalW':>12}{'growth':>9}"
          f"{'maxDD':>8}{'sharpe':>8}{'ruin%':>7}{'flatROI':>9}{'median':>8}"
          f"{'OOSvalid':>9}{'+月':>7}{'days':>6}")
    print(f"  {'-'*108}")
    for r in results:
        rf = " [隔離]" if r.char.ringfenced else ""
        od = " ⚠" if r.char.odds_dependent else ""
        st, fl = r.stats, r.flat
        print(f"  {r.char.name:<16}{r.char.mark_mode[:4]:>5}{r.day_fraction*100:>4.0f}%"
              f"{st.final_w:>12,.0f}{st.growth_pct:>+8.0f}%{st.max_dd_pct:>7.1f}%"
              f"{st.sharpe:>8.3f}{st.ruin_prob_pct:>6.1f}%{st.flat_roi_pct:>8.1f}%"
              f"{fl['median_roi']:>7.1f}%{fl['roi_valid']:>8.1f}%{fl['plus_months']:>7}"
              f"{st.bet_days:>6}{rf}{od}")
    print(f"  {'-'*108}")
    print("  finalW/growth/maxDD/ruin = 複利 (全期間・後知恵込み表示用)。")
    print("  median/OOSvalid/+月 = flat 100円集計の検証規律 (median=月別ROI中央値, "
          "OOSvalid=split以降, +月=ROI>=100%月)。 ⚠=オッズ依存・[隔離]=ringfence。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

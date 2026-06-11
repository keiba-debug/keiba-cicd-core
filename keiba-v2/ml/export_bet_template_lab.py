#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""買い方ラボ backtest 結果を JSON 出力 (Session 147 / web /analysis/bet-lab 用)

『馬券力の正体』テンプレ (bet_templates) × 勝負レース条件 (backtest_selector.CONDITIONS)
の検証結果を **SoT(単一の真実)** として JSON 化する。 web は読むだけ
(ledger-reader / niigata で確立した「Python artifact → web 表示」パターン)。

★ 数値は既存ラボ (backtest_selector / backtest_walkforward) と一致させるため、
  同じ backtest_cache + 同じ精算 (haraimodoshi 実配当) を使う。 後知恵の表示用で、
  OOS の正直な検証は cell の roi_train / roi_valid (split_date 分割) で見る。

出力 (テンプレ × 条件 の各セル):
  - 全期間   : fire / hits / hit_rate / roi
  - OOS      : roi_train (date<split) / roi_valid (date>=split)
  - 安定性   : median_roi (月別ROIの中央値) / avg_roi / plus_months ("6/11") /
               roi_first_half / roi_second_half  ← 万馬券1本の上振れを排除する主軸
  - 出現数   : per_day / month_inv / interval (ふくだ重視)
  - リスク   : max_dd (累積pnlの最大DD・円) / max_streak (最大連敗)
  - 系列     : monthly[] (月別 fire/inv/ret/hits/roi/pnl)
  - 明細     : hit_details[] (高配当 top30)

Output: data3/ml/bet_template_lab.json  (+ versions/v{version}/ にアーカイブ)

Usage:
    python -m ml.export_bet_template_lab
    python -m ml.export_bet_template_lab --split-date 2026-01-01
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config  # noqa: E402
from ml.ai_marks.assign import assign_ai_marks  # noqa: E402
from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.analyze.backtest_bet_templates import (  # noqa: E402
    load_haraimodoshi, ticket_payout,
)
from ml.analyze.backtest_selector import CONDITIONS  # noqa: E402
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies.role_split import detect_no_head  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

# ラボ版 (印ロジック/語彙/テンプレの版。 モデルversionとは別軸)。
#   改訂履歴は docs/composite_theory_log.md に記録。
#   1.0: 語彙統一(◎○▲△Ⅲ)+2モード / 1.1: 本命フォーメーション+配分(sizing)層
#   1.2: S148 買い方チューニング — 単勝二刀流+1人気弱ゲート条件 / weight変種 /
#        役割分化 (honmei_formation_rs = ○P型の頭捨て)
LAB_VERSION = "1.2"

# 役割分化 (S148 捨て馬券): honmei_formation に no_head (P型の頭捨て) を適用した
# 仮想テンプレ。 テンプレ定義は同じで、レース毎の W/P 乖離判定で三連単1列目が変わる。
ROLE_SPLIT_BASE = "honmei_formation"
ROLE_SPLIT_KEY = "honmei_formation_rs"

# ラボ画面に出す条件 (厳選)。 selector.CONDITIONS の崖条件は S148 で棄却済みのため
# 持ち込まない。 1人気弱系 (S148 最有望ゲート) はレコードの fav_rank / g_top2 を
# 使うためここでローカル定義。
LAB_CONDITION_KEYS = [
    "ALL (全レース)", "荒れ 1人気>=4", "軸強 EV>=1.1", "荒れ | 軸強",
    "荒れ & 多頭16+", "軸強 & 中頭数", "堅い2強",
]
LAB_CONDITIONS: Dict[str, Callable[[dict], bool]] = {
    **{k: CONDITIONS[k] for k in LAB_CONDITION_KEYS},
    "1人気弱 (AI△以下)": lambda r: r["fav_rank"] >= 4,
    "1人気弱 & 単勝G>=2.5": lambda r: r["fav_rank"] >= 4 and (r["g_top2"] or 0) >= 2.5,
}

# 印モード (C案 / Session 147)
#   ai        : 実運用の AI印 (assign_ai_marks step2 = 複勝率の崖でカット)。
#               画面の出走表に出る印で買ったら、を再現。 印が少ない (◎単独多い)。
#   composite : composite 序列から ◎○▲△Ⅲ を常に top5 に機械割当 (理論上限)。
#               印を最適配置したらどこまで行けるか。
MARK_MODES = ["ai", "composite"]
MARK_MODE_LABELS = {
    "ai": "実AI印 (崖カット)",
    "composite": "composite理論 (常にtop5)",
}

# ねじれ解消後 (Session 147): テンプレ語彙 = AI印ラダー = ◎○▲△Ⅲ で一致。
#   よってマッピングはほぼ恒等。穴 (別系統・低人気妙味) のみ最下位 Ⅲ に合流。
AI_TO_TEMPLATE_MARK = {"◎": "◎", "○": "○", "▲": "▲", "△": "△", "Ⅲ": "Ⅲ", "穴": "Ⅲ"}


def ai_marks_to_markset(ai_marks: Dict[int, str]) -> Dict[str, List[int]]:
    """assign_ai_marks の {umaban: 記号} をテンプレ markset {記号: [umaban]} に変換。"""
    ms: Dict[str, List[int]] = {}
    for uma, sym in ai_marks.items():
        t = AI_TO_TEMPLATE_MARK.get(sym)
        if t:
            ms.setdefault(t, []).append(int(uma))
    return ms

# 条件の説明 (web 表示用・CONDITIONS のキーに対応)
CONDITION_DESC: Dict[str, str] = {
    "ALL (全レース)": "全レースを機械的に購入 (基準線・控除率をどれだけ埋めるか)",
    "荒れ 1人気>=4": "1番人気の単勝オッズ 4倍以上 = 荒れ読み",
    "軸強 EV>=1.1": "◎(composite1位)の単勝EV>=1.1 = 軸が割安",
    "荒れ | 軸強": "荒れ or 軸強 のどちらか",
    "荒れ & 多頭16+": "荒れ かつ 16頭以上 (高配当の素地)",
    "軸強 & 中頭数": "軸強 かつ 15頭以下 (絞りやすい)",
    "堅い2強": "上位2頭の勝率合計 50%以上 = 堅い決着",
    "1人気弱 (AI△以下)": "1番人気馬の AI 評価 (composite順位) が4位以下 = AIは人気を信じていない。"
                          "⚠cache=確定オッズ判定の後知恵を含む (本番=直前オッズ判定の predictions 検証"
                          "では効果消滅 / S148 spot check)",
    "1人気弱 & 単勝G>=2.5": "1人気弱 かつ AI上位2頭の単勝合成オッズ 2.5倍以上。"
                            "⚠cache では ROI125% に見えたが、確定オッズでのゲート判定が後知恵 — "
                            "predictions (直前オッズ判定・リークなし) では ROI68% に消滅し本番組込みは棄却 "
                            "(S148)。後知恵ゲートの教材として残置",
}


# ---------------------------------------------------------------------------
# レコード構築 (backtest_selector.build_records をミラー + hit明細キャプチャ)
# ---------------------------------------------------------------------------

def _settle_template(name: str, marks: Dict[str, List[int]], rpay: dict,
                     *, no_head=()) -> dict:
    """1テンプレ × 1 markset の精算 → {cost, payout, hits[]}。

    各点の stake = 100 * ticket.weight (配分=sizing を効かせる)。 払戻も weight 比例。
    weight=1.0 のテンプレは従来通り flat 100円/点。
    no_head: 役割分化 (S148) — 順序系券種の1列目から外す馬番 (bet_templates 参照)。
    """
    tickets = bt.apply_template(bt.get_template(name), marks, no_head=no_head)
    cost = payout = 0.0
    hits: List[dict] = []
    for tk in tickets:
        stake = 100.0 * tk.weight
        cost += stake
        p = ticket_payout(tk, rpay)  # 100円あたり払戻
        if p > 0:
            won = p * tk.weight
            payout += won
            hits.append({
                "bet_type": tk.bet_type,
                "horses": list(tk.horses),
                "payout": int(won),
            })
    return {"cost": cost, "payout": payout, "hits": hits}


def build_lab_records(races, *, template_names, haraimodoshi) -> List[dict]:
    """各レース1レコード。 tpl[mode][name] = {cost, payout, hits[]}。

    2つの印モードを並走させる (C案 / Session 147):
      - composite : composite 序列から top5 へ機械割当 (理論上限・既存ラボと一致)。
      - ai        : assign_ai_marks(step2) の実 AI印 (複勝率の崖でカット)。
    条件用の特性 (fav_odds/axis_ev/top2/n) は印モード非依存なので strengths から1回。
    """
    recs: List[dict] = []
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        # 結果確定レースのみ (1着が存在)
        if not any(int(e.get("finish_position") or 99) == 1
                   for e in pred.get("entries", [])):
            continue
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        s = re_.strengths
        n = len(s)
        axis = s[0]
        fav_odds = min((x.odds for x in s if x.odds and x.odds > 0), default=0.0)
        axis_ev = (axis.win_prob * axis.odds) if (axis and axis.odds) else 0.0
        top2 = (s[0].win_prob + s[1].win_prob) if n >= 2 else axis.win_prob
        rid = str(pred["race_id"])
        rpay = haraimodoshi.get(rid, {})

        # 単勝多点ゲート条件用 (S148): 1番人気の composite 順位 / AI上位2頭の単勝合成G
        by_uma = {x.umaban: x for x in s}
        with_odds = [x for x in s if x.odds and x.odds > 0]
        fav_rank = 99
        if with_odds:
            fav_uma = min(with_odds, key=lambda x: x.odds).umaban
            fav_rank = next((i + 1 for i, x in enumerate(s) if x.umaban == fav_uma), 99)
        g_top2 = None
        if n >= 2 and s[0].odds and s[1].odds:
            g_top2 = 1.0 / (1.0 / s[0].odds + 1.0 / s[1].odds)

        # 2モードの markset
        markset_by_mode: Dict[str, Dict[str, List[int]]] = {
            "composite": bt.marks_from_ranking([x.umaban for x in s]),
        }
        ai_res = assign_ai_marks(pred["entries"], step=2)
        markset_by_mode["ai"] = ai_marks_to_markset(ai_res.marks) if not ai_res.skipped else {}

        tpl_data: Dict[str, Dict[str, dict]] = {}
        for mode in MARK_MODES:
            marks = markset_by_mode.get(mode, {})
            tpl_data[mode] = {name: _settle_template(name, marks, rpay)
                              for name in template_names}
            # 役割分化版 (S148 仮想テンプレ): 頭候補◎○▲の P型を三連単1列目から外す
            heads = [(marks[m][0], by_uma[marks[m][0]].pred_w, by_uma[marks[m][0]].pred_p)
                     for m in ("◎", "○", "▲")
                     if marks.get(m) and marks[m][0] in by_uma]
            nh = detect_no_head(heads) if len(heads) >= 2 else []
            tpl_data[mode][ROLE_SPLIT_KEY] = _settle_template(
                ROLE_SPLIT_BASE, marks, rpay, no_head=nh)
        recs.append({
            "rid": rid, "date": rid[:8], "n": n, "fav_odds": fav_odds,
            "axis_ev": axis_ev, "top2": top2, "fav_rank": fav_rank, "g_top2": g_top2,
            "tpl": tpl_data,
        })
    return recs


# ---------------------------------------------------------------------------
# セル集計 (1条件 × 1テンプレ)
# ---------------------------------------------------------------------------

def _ym(date8: str) -> str:
    return f"{date8[:4]}-{date8[4:6]}"


def aggregate_cell(recs: List[dict], *, cond: Callable, template: str, mode: str,
                   split: str, n_days_all: int, n_months_all: int) -> dict:
    """条件 cond に合致するレコードで (mode, template) の各種メトリクスを算出。"""
    monthly: Dict[str, dict] = defaultdict(
        lambda: {"fire": 0, "inv": 0.0, "ret": 0.0, "hits": 0})
    cost = payout = 0.0
    fire = hits = 0
    cost_tr = pay_tr = cost_va = pay_va = 0.0
    # rid 昇順で maxDD / 連敗
    fired_sorted = sorted((r for r in recs if cond(r)), key=lambda r: r["rid"])
    cum_pnl = peak = max_dd = 0.0
    streak = max_streak = 0
    hit_details: List[dict] = []

    for r in fired_sorted:
        cp = r["tpl"][mode][template]
        c, p = cp["cost"], cp["payout"]
        if c <= 0:
            continue
        cost += c
        payout += p
        fire += 1
        ym = _ym(r["date"])
        monthly[ym]["fire"] += 1
        monthly[ym]["inv"] += c
        monthly[ym]["ret"] += p
        is_hit = p > 0
        if is_hit:
            hits += 1
            monthly[ym]["hits"] += 1
        # train/valid
        if r["date"] < split:
            cost_tr += c
            pay_tr += p
        else:
            cost_va += c
            pay_va += p
        # 時系列リスク
        cum_pnl += p - c
        peak = max(peak, cum_pnl)
        max_dd = max(max_dd, peak - cum_pnl)
        if is_hit:
            streak = 0
        else:
            streak += 1
            max_streak = max(max_streak, streak)
        # hit明細
        for h in cp["hits"]:
            hit_details.append({
                "race_id": r["rid"],
                "bet_type": h["bet_type"],
                "horses": h["horses"],
                "payout": h["payout"],
            })

    roi = payout / cost * 100 if cost > 0 else 0.0
    roi_tr = pay_tr / cost_tr * 100 if cost_tr > 0 else 0.0
    roi_va = pay_va / cost_va * 100 if cost_va > 0 else 0.0

    # 月別系列 (発火月のみ・昇順)
    months_sorted = sorted(monthly.keys())
    monthly_out = []
    roi_vals: List[float] = []
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
    avg_roi = statistics.mean(roi_vals) if roi_vals else 0.0
    plus = sum(1 for v in roi_vals if v >= 100)

    # 前後半分割
    mid = len(months_sorted) // 2
    fh_inv = sum(monthly[m]["inv"] for m in months_sorted[:mid])
    fh_ret = sum(monthly[m]["ret"] for m in months_sorted[:mid])
    sh_inv = sum(monthly[m]["inv"] for m in months_sorted[mid:])
    sh_ret = sum(monthly[m]["ret"] for m in months_sorted[mid:])
    roi_fh = fh_ret / fh_inv * 100 if fh_inv > 0 else 0.0
    roi_sh = sh_ret / sh_inv * 100 if sh_inv > 0 else 0.0

    hit_details.sort(key=lambda x: -x["payout"])

    return {
        "condition": "",   # 呼び出し側で補完
        "mark_mode": mode,
        "template": template,
        "fire": fire,
        "hits": hits,
        "hit_rate": round(hits / fire * 100, 1) if fire else 0.0,
        "roi": round(roi, 1),
        "roi_train": round(roi_tr, 1),
        "roi_valid": round(roi_va, 1),
        "median_roi": round(median_roi, 1),
        "avg_roi": round(avg_roi, 1),
        "plus_months": f"{plus}/{len(roi_vals)}",
        "plus_month_count": plus,
        "n_months_fired": len(roi_vals),
        "per_day": round(fire / n_days_all, 3) if n_days_all else 0.0,
        "month_inv": round(cost / n_months_all) if n_months_all else 0,
        "interval": round(fire / hits, 1) if hits else None,
        "roi_first_half": round(roi_fh, 1),
        "roi_second_half": round(roi_sh, 1),
        "max_dd": round(max_dd),
        "max_streak": max_streak,
        "total_invested": round(cost),
        "total_return": round(payout),
        "monthly": monthly_out,
        "hit_details": hit_details[:30],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--split-date", default="2026-01-01", help="train/valid 分割")
    p.add_argument("--templates", default=None, help="カンマ区切り (既定=全テンプレ)")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    print("=" * 80)
    print("  Bet Template Lab → JSON Export (買い方ラボ / web /analysis/bet-lab)")
    print("=" * 80)

    args = parse_args()
    split = args.split_date.replace("-", "")
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    names = ([x.strip() for x in args.templates.split(",")] if args.templates
             else bt.list_templates())
    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]

    print(f"  backtest_cache: {len(races)} races  split={args.split_date}  vocab=◎○▲△Ⅲ")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}  building records (process_race)...")
    recs = build_lab_records(races, template_names=names, haraimodoshi=haraimodoshi)
    if not recs:
        print("  [ERROR] no records built")
        return 1

    all_days = {r["date"] for r in recs}
    n_days_all = len(all_days)
    months_all = sorted({_ym(r["date"]) for r in recs})
    n_months_all = len(months_all)
    print(f"  records={len(recs)}  days={n_days_all}  months={n_months_all} "
          f"({months_all[0]}~{months_all[-1]})")

    # セル集計 (印モード × 条件 × テンプレ)。 rs = 役割分化の仮想テンプレ行 (S148)。
    cell_names = list(names)
    if ROLE_SPLIT_BASE in names:
        cell_names.append(ROLE_SPLIT_KEY)
    cells: List[dict] = []
    for mode in MARK_MODES:
        for cond_name, cond in LAB_CONDITIONS.items():
            for name in cell_names:
                cell = aggregate_cell(recs, cond=cond, template=name, mode=mode,
                                      split=split, n_days_all=n_days_all,
                                      n_months_all=n_months_all)
                cell["condition"] = cond_name
                cells.append(cell)

    templates_meta = []
    for name in names:
        t = bt.get_template(name)
        templates_meta.append({
            "key": name, "label": t.label, "system": t.system,
            "ringfenced": t.ringfenced, "note": t.note,
        })
    if ROLE_SPLIT_KEY in cell_names:
        templates_meta.append({
            "key": ROLE_SPLIT_KEY,
            "label": "本命フォーメーション+役割分化 (P型の頭捨て)",
            "system": "当てる", "ringfenced": False,
            "note": "honmei_formation の三連単1列目から、W/P乖離で「1着に来ない(P型)」と"
                    "判定した頭候補を外す (S148 捨て馬券の機械化。発火1377R/2934Rで "
                    "三連単部分 BOX 96.9%→107.5%・コスト2/3)。三連複保険は不変。",
        })

    rids = sorted(r["rid"] for r in recs)
    result = {
        "created_at": datetime.now().isoformat(),
        "data_source": "backtest_cache + haraimodoshi (real payout / 後知恵表示・OOSはtrain/valid)。"
                       "⚠オッズを使う条件 (荒れ/軸EV/1人気弱/G) は確定オッズ判定 = 直前オッズで判定する"
                       "本番より甘い (S148 spot check で実証)",
        "period_start": f"{rids[0][:4]}-{rids[0][4:6]}-{rids[0][6:8]}",
        "period_end": f"{rids[-1][:4]}-{rids[-1][4:6]}-{rids[-1][6:8]}",
        "total_races": len(recs),
        "races_with_payouts": len(haraimodoshi),
        "split_date": args.split_date,
        "lab_version": LAB_VERSION,
        "mark_vocab": "◎○▲△Ⅲ",
        "composite_def": {
            "source": "bettype_efficiency.process_race (robust-z blend of W/P/AR)",
            "vocab": "◎○▲△Ⅲ (上位5頭の単独序列印)",
            "ai_mark_logic": "assign_ai_marks step2 (composite序列 + 複勝率の崖カット)",
        },
        "mark_modes": [{"key": m, "label": MARK_MODE_LABELS[m]} for m in MARK_MODES],
        "months": months_all,
        "conditions": [
            {"key": k, "label": k, "desc": CONDITION_DESC.get(k, "")}
            for k in LAB_CONDITIONS.keys()
        ],
        "templates": templates_meta,
        "cells": cells,
    }

    out_path = config.ml_dir() / "bet_template_lab.json"
    out_json = json.dumps(result, ensure_ascii=False, indent=2)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\n  Saved: {out_path}  ({len(out_json) // 1024} KB)")

    # version アーカイブ (formation exporter と同じ作法)
    meta_path = config.ml_dir() / "model_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            version = meta.get("version", "")
            if version:
                archive_dir = config.ml_dir() / "versions" / f"v{version}"
                archive_dir.mkdir(parents=True, exist_ok=True)
                (archive_dir / "bet_template_lab.json").write_text(out_json, encoding="utf-8")
                print(f"  Archive: {archive_dir / 'bet_template_lab.json'}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [warn] archive skipped: {e}")

    # サマリ (ALL 条件・印モード別の対比 = C案の主眼)
    for mode in MARK_MODES:
        print(f"\n  {'='*84}")
        print(f"  ◆ ALL (全レース) / 印モード= {MARK_MODE_LABELS[mode]}")
        print(f"  {'template':<20}{'fire':>6}{'的中率':>8}{'ROI':>7}{'中央値':>7}{'+月':>7}"
              f"{'maxDD':>9}{'連敗':>5}")
        for cell in cells:
            if cell["condition"] != "ALL (全レース)" or cell["mark_mode"] != mode:
                continue
            star = " ★" if cell["median_roi"] >= 100 else ""
            print(f"  {cell['template']:<20}{cell['fire']:>6}{cell['hit_rate']:>7.0f}%"
                  f"{cell['roi']:>6.0f}%{cell['median_roi']:>6.0f}%{cell['plus_months']:>7}"
                  f"{cell['max_dd']:>9,}{cell['max_streak']:>5}{star}")
    print(f"\n  ※ ai=実AI印(崖カット)で fire が減る/三連系が組めないレースが出る = 画面の印で買った実態。")
    print(f"  全 {len(cells)} セル ({len(MARK_MODES)}モード×条件{len(LAB_CONDITIONS)}"
          f"×テンプレ{len(cell_names)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

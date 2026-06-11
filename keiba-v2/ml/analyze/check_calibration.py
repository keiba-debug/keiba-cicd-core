#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W(勝率)・P(複勝率) モデルの較正診断 (Session 149 / Phase1 入口)

崖を P で引く前に「P が較正されてるか」を確認する (検証基本方針 原則2)。
予測確率 vs 実現頻度を Brier / ECE / reliability で測る。 確率帯・単勝オッズ帯別。
DB 非依存 (backtest_cache entries: pred_proba_w_cal / pred_proba_p / finish_position / odds)。

CLI: python -m ml.analyze.check_calibration
"""

from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.model_loader import load_model_safe  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402


def _brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else 0.0


def _ece(pairs, nbins=10):
    bins = [[] for _ in range(nbins)]
    for p, y in pairs:
        b = min(nbins - 1, int(p * nbins))
        bins[b].append((p, y))
    n = len(pairs)
    ece = 0.0
    rows = []
    for i, b in enumerate(bins):
        if not b:
            continue
        mp = sum(x[0] for x in b) / len(b)
        my = sum(x[1] for x in b) / len(b)
        ece += abs(mp - my) * len(b) / n
        rows.append((i / nbins, (i + 1) / nbins, len(b), mp, my))
    return ece, rows


def _report(name, pairs):
    print(f"\n  === {name}  (n={len(pairs)}) ===")
    if not pairs:
        print("  (データなし)")
        return
    br = _brier(pairs)
    ece, rows = _ece(pairs)
    base = sum(y for _, y in pairs) / len(pairs)
    print(f"  Brier={br:.4f}  ECE={ece:.4f}  実現ベース率={base:.3f}")
    print(f"  {'確率帯':>9}{'n':>8}{'予測平均':>9}{'実現率':>8}{'乖離':>9}")
    for lo, hi, cnt, mp, my in rows:
        flag = " ⚠過大" if (mp - my) >= 0.05 and cnt >= 20 else (
            " ⚠過小" if (my - mp) >= 0.05 and cnt >= 20 else "")
        print(f"  {lo:.1f}-{hi:.1f}{cnt:>10}{mp:>9.3f}{my:>8.3f}{mp - my:>+9.3f}{flag}")


def _band(od):
    return ("<2.9" if od < 3 else "3-9.9" if od < 10 else "10-49.9" if od < 50 else "50+")


def _odds_table(band_map, bands):
    print(f"  {'帯':>8}{'n':>8}{'ECE':>8}{'予測平均':>9}{'実現':>8}{'乖離':>9}")
    for b in bands:
        pr = band_map.get(b)
        if not pr:
            continue
        ece, _ = _ece(pr)
        base = sum(y for _, y in pr) / len(pr)
        avg = sum(p for p, _ in pr) / len(pr)
        flag = " ⚠過小" if (base - avg) >= 0.05 else (" ⚠過大" if (avg - base) >= 0.05 else "")
        print(f"  {b:>8}{len(pr):>8}{ece:>8.4f}{avg:>9.3f}{base:>8.3f}{avg - base:>+9.3f}{flag}")


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="W/P 較正診断 (raw vs cal / 確定 vs 直前オッズ)")
    ap.add_argument("--cutoff", type=int, default=None, metavar="MIN",
                    help="発走 MIN 分前の直前オッズでオッズ帯別を診断 (省略時=cache の確定オッズ)")
    args = ap.parse_args()

    races = load_backtest_cache()

    cutoff_odds = None
    if args.cutoff is not None:
        from core import odds_db
        rids = [str(r.get("race_id")) for r in races if r.get("race_id")]
        cutoff_odds = odds_db.batch_get_win_odds_at_cutoff(rids, minutes_before=args.cutoff)
        n_h = sum(len(v) for v in cutoff_odds.values())
        print(f"[cutoff] 発走{args.cutoff}分前の直前オッズ: {len(cutoff_odds)} races / {n_h} 頭 "
              f"(オッズ帯別を確定でなく直前オッズで分類)")

    # Session 150: backtest_cache の pred_proba_p は cal前の生スコア(raw, 和≈2.7)。
    # bet_engine が place_ev に使うのは cal_p(Isotonic) 適用後の絶対確率。
    # 「Session 149 の -0.438 過小評価」は raw を見ていた診断 → cal版で引き直す。
    bundle = load_model_safe("polaris")
    cal_p = (bundle.calibrators or {}).get("cal_p") if bundle and bundle.calibrators else None
    if cal_p is None:
        print("[WARN] cal_p 未ロード — raw のみ診断 (live polaris に calibrators.pkl が必要)")
    else:
        print(f"[cal_p] polaris v{bundle.version} の Isotonic(cal_p) を raw に適用して較正版を診断")

    w_pairs = []
    p_pairs_raw, p_pairs_cal = [], []
    ob_raw, ob_cal = defaultdict(list), defaultdict(list)
    w_sums, p_sums_raw, p_sums_cal = [], [], []
    has_odds = total = 0
    for r in races:
        pred = cache_race_to_pred(r)
        if pred is None:
            continue
        ents = [e for e in pred.get("entries", []) if e.get("umaban") is not None]
        if not any(int(e.get("finish_position") or 99) == 1 for e in ents):
            continue
        ws = 0.0
        raws, yts, ods = [], [], []
        rid = str(pred.get("race_id") or "")
        race_co = cutoff_odds.get(rid, {}) if cutoff_odds is not None else None
        for e in ents:
            try:
                fp = int(e.get("finish_position"))
            except (TypeError, ValueError):
                continue
            if fp <= 0:
                continue
            total += 1
            w = e.get("pred_proba_w_cal")
            if isinstance(w, (int, float)):
                w_pairs.append((float(w), 1 if fp == 1 else 0))
                ws += w
            p = e.get("pred_proba_p")  # = pred_proba_p_raw (cal前の生スコア)
            if not isinstance(p, (int, float)):
                continue
            if race_co is not None:
                od = (race_co.get(int(e["umaban"])) or {}).get("odds")  # 直前オッズ
            else:
                od = e.get("odds") or e.get("win_odds") or e.get("tan_odds")  # 確定
            raws.append(float(p))
            yts.append(1 if fp <= 3 else 0)
            ods.append(od if isinstance(od, (int, float)) and od > 0 else None)
        if not raws:
            continue
        w_sums.append(ws)
        raws_arr = np.asarray(raws, dtype=float)
        cals = cal_p.predict(raws_arr) if cal_p is not None else raws_arr
        p_sums_raw.append(float(raws_arr.sum()))
        p_sums_cal.append(float(np.asarray(cals).sum()))
        for raw, c, yt, od in zip(raws, cals, yts, ods):
            p_pairs_raw.append((raw, yt))
            p_pairs_cal.append((float(c), yt))
            if od is not None:
                has_odds += 1
                b = _band(od)
                ob_raw[b].append((raw, yt))
                ob_cal[b].append((float(c), yt))

    print(f"races(確定)={len(w_sums)}  horses={total}  odds付き={has_odds}")
    line = (f"  per-race 予測和:  W平均={sum(w_sums) / len(w_sums):.2f} (較正なら≈1)  "
            f"P_raw平均={sum(p_sums_raw) / len(p_sums_raw):.2f}")
    if cal_p is not None:
        line += f"  P_cal平均={sum(p_sums_cal) / len(p_sums_cal):.2f} (複勝3枠なら≈3)"
    print(line)

    _report("W 勝率 (pred_proba_w_cal vs 1着)", w_pairs)
    _report("P 複勝率 RAW (cal前 / pred_proba_p_raw vs 3着内)", p_pairs_raw)
    if cal_p is not None:
        _report("P 複勝率 CAL (Isotonic cal_p 適用後 vs 3着内) ★本命", p_pairs_cal)

    if has_odds:
        bands = ["<2.9", "3-9.9", "10-49.9", "50+"]
        print("\n  --- P 複勝率の較正・単勝オッズ帯別 (RAW cal前) ---")
        _odds_table(ob_raw, bands)
        if cal_p is not None:
            print("\n  --- P 複勝率の較正・単勝オッズ帯別 (CAL Isotonic後) ★結論 ---")
            _odds_table(ob_cal, bands)
    else:
        print("\n  (odds キー未検出 → オッズ帯別はスキップ。 確率帯別 reliability で判断)")

    print("\n  ※ ECE<0.05目安で較正OK。 予測>実現=過大評価(買うと損)、予測<実現=過小評価(妙味の源)。")
    print("  ※ RAW=レース内未正規化の生スコア(和≈2.7)。CAL=bet_engineがplace_ev算出に使う実確率。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

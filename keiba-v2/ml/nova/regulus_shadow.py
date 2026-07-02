#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regulus 本命 shadow トラッカー (Session 183)

Regulus は表示専用(payout非期待)だが、S183検証で「重賞(G1-G3)の本命精度が汎用を上回る」
という予想品質シグナルが出た(ただし n=111 で CI が広い)。実運用で n を積んで CI を締めるための
shadow 台帳。**賭けはしない** — 純粋な追跡記録。

各 `races/Y/M/D/regulus_scores.json`(3歳上芝OP+のみ・predict_regulus出力)の各レースで
Regulus 本命(rank_blend==1 / rank_p==1 / rank_w==1)を確定結果(race_*.json の finish_position/odds)と
突合し、グレード帯別に 単勝的中率/複勝内率/ROI + bootstrap CI を集計する。日次prep後に再実行で更新。

Usage:
    python -m ml.nova.regulus_shadow            # 台帳再構築 + サマリ表示
    python -m ml.nova.regulus_shadow --json     # サマリJSONも標準出力

Output: data3/ml/models/regulus/shadow_ledger.json
"""
from __future__ import annotations
import argparse, glob, io, json, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import numpy as np

from core import config

TIERS = {
    "重賞(G1-G3)": ["G1", "G2", "G3"], "G1": ["G1"], "G2": ["G2"], "G3": ["G3"],
    "Listed": ["Listed"], "OP": ["OP"], "全体(OP+)": ["G1", "G2", "G3", "Listed", "OP"],
}
SIGNALS = {"blend": "rank_blend", "P": "rank_p", "W": "rank_w"}


def _results_for_dir(day_dir: Path) -> dict:
    """race_id -> {umaban(str): (finish_position, odds)} を race_*.json から構築。"""
    out = {}
    for f in day_dir.glob("race_[0-9]*.json"):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        rid = str(r.get("race_id", ""))
        m = {}
        for e in r.get("entries", []):
            u = str(e.get("umaban"))
            fp = e.get("finish_position")
            od = e.get("odds")
            if fp is not None:
                m[u] = (fp, od)
        if m:
            out[rid] = m
    return out


def build_ledger():
    races_root = config.races_dir()
    rows = []
    for sf in glob.glob(str(races_root / "*" / "*" / "*" / "regulus_scores.json")):
        sp = Path(sf)
        day_dir = sp.parent
        try:
            scores = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        results = _results_for_dir(day_dir)
        date = scores.get("prediction_date") or "-".join(day_dir.parts[-3:])
        for rid, race in scores.get("races", {}).items():
            grade = race.get("grade")
            res = results.get(str(rid))
            if not res:
                continue  # 結果未確定 → skip
            entries = race.get("entries", {})
            row = {"date": date, "race_id": rid, "grade": grade,
                   "race_name": race.get("race_name"), "n_eligible": race.get("n_eligible")}
            got = False
            for sig, rank_key in SIGNALS.items():
                honmei = next((u for u, e in entries.items() if e.get(rank_key) == 1), None)
                if honmei is None or str(honmei) not in res:
                    continue
                fp, od = res[str(honmei)]
                if fp is None or fp <= 0:
                    continue
                row[f"{sig}_umaban"] = honmei
                row[f"{sig}_horse"] = entries[honmei].get("horse_name")
                row[f"{sig}_finish"] = fp
                row[f"{sig}_odds"] = od
                row[f"{sig}_win"] = int(fp == 1)
                row[f"{sig}_place"] = int(fp <= 3)
                got = True
            if got:
                rows.append(row)
    return rows


def _boot_ci(wins, oddss, n_iter=3000):
    """1レース1点賭けの race-cluster bootstrap ROI CI。"""
    wins = np.asarray(wins, float); oddss = np.asarray(oddss, float)
    n = len(wins)
    if n == 0:
        return 0.0, 0.0, 0.0
    pay = wins * np.nan_to_num(oddss)
    base = pay.sum() / n * 100
    rng = np.random.default_rng(42)
    idx = rng.integers(0, n, size=(n_iter, n))
    r = pay[idx].sum(1) / n * 100
    return round(float(base), 1), round(float(np.percentile(r, 5)), 1), round(float(np.percentile(r, 95)), 1)


def summarize(rows, sig="blend"):
    out = {}
    for name, grades in TIERS.items():
        sub = [r for r in rows if r.get("grade") in grades and f"{sig}_finish" in r]
        n = len(sub)
        if n == 0:
            out[name] = {"n": 0}
            continue
        wins = [r[f"{sig}_win"] for r in sub]
        places = [r[f"{sig}_place"] for r in sub]
        oddss = [r[f"{sig}_odds"] or 0 for r in sub]
        roi, lo, hi = _boot_ci(wins, oddss)
        hit_odds = [o for w, o in zip(wins, oddss) if w and o]
        out[name] = {
            "n": n, "win": sum(wins), "win_rate": round(sum(wins) / n * 100, 1),
            "place": sum(places), "place_rate": round(sum(places) / n * 100, 1),
            "roi": roi, "ci_low": lo, "ci_high": hi,
            "mean_hit_odds": round(float(np.mean(hit_odds)), 2) if hit_odds else 0.0,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = build_ledger()
    rows.sort(key=lambda r: (r["date"], r["race_id"]))
    summ = {sig: summarize(rows, sig) for sig in SIGNALS}

    dates = sorted({r["date"] for r in rows})
    ledger = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "note": "Regulus 本命 shadow 記録(表示専用・賭けなし)。重賞本命精度シグナルの n 蓄積用。",
        "n_races": len(rows),
        "date_range": [dates[0], dates[-1]] if dates else None,
        "summary": summ,
        "rows": rows,
    }
    out = config.ml_dir() / "models" / "regulus" / "shadow_ledger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[Regulus Shadow] {len(rows)} races ({ledger['date_range']}) -> {out}")
    for sig in SIGNALS:
        print(f"\n=== 本命定義: {sig} ({SIGNALS[sig]}==1) ===")
        print(f"{'帯':<12}|{'n':>4}|{'単勝的中':>8}|{'複勝内':>7}|{'単ROI':>7}|{'ROI 90%CI':>13}|{'的中平均odds':>10}")
        for name, s in summ[sig].items():
            if not s.get("n"):
                continue
            print(f"{name:<12}|{s['n']:>4}|{s['win_rate']:>7.1f}%|{s['place_rate']:>6.1f}%|"
                  f"{s['roi']:>6.1f}%|{('['+str(s['ci_low'])+','+str(s['ci_high'])+']'):>13}|{s['mean_hit_odds']:>10}")
    if args.json:
        print("\n" + json.dumps(summ, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""妙味穴・単勝 shadow sleeve (Session 169 / ふくだ「穴単勝枠を走らせてみよう」)

リスクゼロのペーパー運用。 毎開催「混戦で単勝高オッズ(市場が見限る)だがモデルARDが
高い(妙味)馬」を単勝で"買ったことにして"ログ → 実払戻で精算 → 資産曲線を貯める。
sim (bench_ana_tansho) の ROI 103.5% がライブで再現するか裏取りしてから実弾化する。

選定 (pre-race・リークなし): 高ARDクラスタ(max-ARD<=ard_gap) ∩ 単勝[lo,hi] ∩ 非1人気
  (odds_rank>=2)、 ARD降順 top_k。 combo/フォメに埋めると妙味が消える (bench_ana_formation
  実証) ので単勝単体で捕る。

精算: haraimodoshi 単勝 実払戻 (per100)。 ※金は賭けない (shadow)。

CLI:
  python -m ml.strategies.ana_tansho_shadow --date 2026-06-20 --log     # 買い目ログ
  python -m ml.strategies.ana_tansho_shadow --date 2026-06-20 --settle  # 実結果で精算
  python -m ml.strategies.ana_tansho_shadow --report                    # 累積成績
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import config  # noqa: E402

STAKE = 100  # ペーパー: 1点あたり ¥100 想定

DEFAULT_PARAMS = {"ard_gap": 5.0, "lo": 20.0, "hi": 100.0, "top_k": 1}


def _shadow_dir() -> Path:
    d = config.data_root() / "userdata" / "ana_tansho_shadow"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _picks_path(date_str: str) -> Path:
    return _shadow_dir() / f"picks_{date_str}.json"


def select_ana_tansho(pred_race: dict, *, ard_gap=5.0, lo=20.0, hi=100.0, top_k=1) -> list:
    """1レースの妙味穴・単勝 候補を返す (canonical 選定・sim と共通ロジック)。"""
    ents = [e for e in (pred_race.get("entries") or [])
            if e.get("umaban") and e.get("ar_deviation") is not None and e.get("odds")]
    if len(ents) < 5:
        return []
    amax = max(e["ar_deviation"] for e in ents)
    cands = [e for e in ents
             if amax - e["ar_deviation"] <= ard_gap
             and lo <= e["odds"] <= hi
             and (e.get("odds_rank") or 99) >= 2]
    cands = sorted(cands, key=lambda e: -e["ar_deviation"])[:top_k]
    out = []
    for e in cands:
        out.append({
            "umaban": e["umaban"],
            "horse_name": e.get("horse_name", ""),
            "ar_deviation": e["ar_deviation"],
            "odds": e["odds"],
            "odds_rank": e.get("odds_rank"),
            "ard_max": round(amax, 1),
        })
    return out


def _predictions(date_str: str) -> dict:
    y, m, d = date_str.split("-")
    p = config.races_dir() / y / m / d / "predictions.json"
    if not p.exists():
        raise FileNotFoundError(f"predictions.json なし: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def log_picks(date_str: str, params: dict = None, *, now: str = None) -> dict:
    """predictions.json から穴単勝を選定し picks_{date}.json に追記 (race 単位で冪等)。"""
    params = params or dict(DEFAULT_PARAMS)
    path = _picks_path(date_str)
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {"date": date_str, "params": params, "picks": [], "settled": False}
    already = {p["race_id"] for p in doc["picks"]}
    preds = _predictions(date_str)
    ts = now or datetime.now().isoformat(timespec="seconds")
    added = 0
    for race in preds.get("races", []):
        rid = str(race.get("race_id"))
        if rid in already:
            continue
        for pk in select_ana_tansho(race, **params):
            pk.update({"race_id": rid, "venue_name": race.get("venue_name", ""),
                       "race_number": race.get("race_number"), "logged_at": ts,
                       "stake": STAKE})
            doc["picks"].append(pk)
            added += 1
        if select_ana_tansho(race, **params):
            already.add(rid)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"date": date_str, "added": added, "total": len(doc["picks"]), "path": str(path)}


def settle(date_str: str) -> dict:
    """picks を haraimodoshi 単勝 実払戻で精算 (shadow・金は賭けない)。"""
    from ml.analyze.backtest_bet_templates import load_haraimodoshi
    path = _picks_path(date_str)
    if not path.exists():
        return {"error": f"picks なし: {path}"}
    doc = json.loads(path.read_text(encoding="utf-8"))
    rids = list({p["race_id"] for p in doc["picks"]})
    hp = load_haraimodoshi(rids)
    cost = payout = hit = big = 0
    for p in doc["picks"]:
        rp = hp.get(p["race_id"]) or {}
        per100 = (rp.get("tansho") or {}).get(p["umaban"], 0)
        pay = STAKE / 100.0 * per100 if per100 else 0.0
        p["settled_payout"] = pay
        p["won"] = bool(per100)
        cost += p["stake"]
        payout += pay
        if pay > 0:
            hit += 1
        if pay >= p["stake"] * 10:
            big += 1
    doc["settled"] = True
    doc["result"] = {
        "n": len(doc["picks"]), "cost": cost, "payout": payout,
        "pnl": payout - cost, "roi": (payout / cost * 100 if cost else 0),
        "hit": hit, "big_1000pct": big,
        "settled_at": datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc["result"]


def report() -> dict:
    """全 settled picks を集計 (累積 ROI / 資産曲線サマリ)。"""
    days = sorted(_shadow_dir().glob("picks_*.json"))
    tot_cost = tot_pay = tot_n = tot_hit = tot_big = 0
    cum = peak = maxdd = 0.0
    settled_days = 0
    rows = []
    for f in days:
        doc = json.loads(f.read_text(encoding="utf-8"))
        if not doc.get("settled"):
            continue
        r = doc["result"]
        settled_days += 1
        tot_cost += r["cost"]; tot_pay += r["payout"]; tot_n += r["n"]
        tot_hit += r["hit"]; tot_big += r["big_1000pct"]
        cum += r["pnl"]; peak = max(peak, cum); maxdd = max(maxdd, peak - cum)
        rows.append((doc["date"], r["n"], r["roi"], r["pnl"], r["big_1000pct"]))
    return {
        "settled_days": settled_days, "n_bet": tot_n,
        "roi": (tot_pay / tot_cost * 100 if tot_cost else 0),
        "pnl": tot_pay - tot_cost, "hit": (tot_hit / tot_n * 100 if tot_n else 0),
        "big_1000pct": tot_big, "max_dd": maxdd, "days": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--settle", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        r = report()
        print(f"\n=== 妙味穴・単勝 shadow 累積 ({r['settled_days']}開催) ===")
        print(f"  投票 {r['n_bet']}本 / ROI {r['roi']:.1f}% / PnL {r['pnl']:+,.0f}円(¥100/点) "
              f"/ 的中 {r['hit']:.1f}% / ≥1000% {r['big_1000pct']}回 / maxDD {r['max_dd']:,.0f}円")
        for d, n, roi, pnl, big in r["days"]:
            print(f"    {d}: {n}本 ROI {roi:.0f}% PnL {pnl:+,.0f} 天井{big}")
        return
    if not args.date:
        ap.error("--date 必須 (--log / --settle)")
    if args.log:
        print("log:", log_picks(args.date))
    if args.settle:
        print("settle:", settle(args.date))


if __name__ == "__main__":
    main()

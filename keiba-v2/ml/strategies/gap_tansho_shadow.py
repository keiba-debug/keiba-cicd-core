#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gap5単勝エッジ shadow sleeve (Session 174 / 市場較正エッジの forward 検証枠)

リスクゼロのペーパー運用。docs/market_calibration_edge_map.md で精密化した
**gap≥5単勝 × クラス局在エッジ** を単勝で"買ったことにして"ログ→実払戻で精算→
資産曲線を貯める。★S175 過学習監査の訂正★: S174 の `odds∈[15,30)→218%` は **best-of-search のノイズ(p=0.0625)
＝後知恵 band 選択の過学習**と判明し**棄却**(`ml/analyze/audit_gap_edge.py` / docs §8)。
forward が検証する committed エッジ = **broad (全オッズ)**:
  クラス∈{未勝利, 条件(1-3勝), 重賞} ∧ rank_w≤3 ∧ gap≥5 (gap=odds_rank-rank_w)、該当馬は全頭。
  → a-priori ROI **130%** / CI[81-187] / **P(null≥130%)=0.026** で較正市場を超える(エッジは実在)。
  win_ev≥1 は「モデルEV>1」のサニティゲートとして残す。odds帯フィルタは付けない。
  ※新馬/OPは除外 (新馬=モデルも盲目・OP=市場シャープ)。
  ※複勝/複勝に広げると -EV (S173 実証) なので単勝単体で捕る。
in-sample は高分散 (的中~5% / 連敗50-106 / CI下限81%)。~12点/月では forward CI が 100% を外すのに
~2年 → **forward は速い検証ゲートでなく長期ガードレール**。実弾化は deep フラクショナル(≤0.5%/bet)前提で先送り。

精算: haraimodoshi 単勝 実払戻 (per100)。 ※金は賭けない (shadow)。
本番投票 (bettype_auto.bat) とは完全分離 = 1円も賭けず影響なし。

CLI:
  python -m ml.strategies.gap_tansho_shadow --date 2026-06-21 --log     # 買い目ログ
  python -m ml.strategies.gap_tansho_shadow --date 2026-06-21 --settle  # 実払戻で精算
  python -m ml.strategies.gap_tansho_shadow --report                    # 累積成績
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import config  # noqa: E402
# dir非依存の汎用ヘルパは ana_tansho_shadow から流用 (DRY・ana本体は無改変)
from ml.strategies.ana_tansho_shadow import _predictions, _window_race_ids  # noqa: E402

STAKE = 100  # ペーパー: 1点あたり ¥100 想定

EDGE_BUCKETS = {"miSHOURI", "jouken", "juushou"}  # 未勝利 / 条件(1-3勝) / 重賞
# S175: committed = broad(全オッズ)。odds帯は過学習で棄却したので付けない (audit §8)。
DEFAULT_PARAMS = {
    "pred_rank_max": 3, "gap_min": 5, "odds_lo": 0.0, "odds_hi": 9999.0,
    "win_ev_floor": 1.0, "top_k": None,  # None=該当馬全頭 (committed broad と整合)
}
# in-sample ベンチ (forward 乖離監視用・docs/market_calibration_edge_map.md §8)
INSAMPLE_BROAD_ROI = 130.1   # committed: gap≥5×3クラス×全オッズ (P(null≥130%)=0.026)
INSAMPLE_BROAD_N = 413       # 13ヶ月OOS


def _bucket(grade) -> str:
    """grade をエッジ判定用クラスに正規化 (export_edge_validation.bucket と同一)。"""
    g = str(grade)
    if "新馬" in g:
        return "shinba"
    if "未勝利" in g:
        return "miSHOURI"
    if "クラス" in g:
        return "jouken"
    if g in ("OP", "Listed"):
        return "OP/L"
    if g.startswith("G"):
        return "juushou"
    return "other"


def _shadow_dir() -> Path:
    d = config.data_root() / "userdata" / "gap_tansho_shadow"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _picks_path(date_str: str) -> Path:
    return _shadow_dir() / f"picks_{date_str}.json"


def select_gap_tansho(pred_race: dict, *, pred_rank_max=3, gap_min=5, odds_lo=0.0,
                      odds_hi=9999.0, win_ev_floor=1.0, top_k=None) -> list:
    """1レースの gap5単勝エッジ候補を返す (canonical 選定・committed broad = DEFAULT_PARAMS と同一)。

    S175: odds帯は過学習で棄却 → 既定で全オッズ (odds_lo=0/odds_hi=9999)。詳細 audit §8。

    クラス判定は grade を優先し、空なら race_name にフォールバック (S176+: keibabook ビルダーは
    クラスを race_name に入れ grade='' のため、レース当日朝の predictions は grade 空 → grade だけ
    見ると全レース対象外で偽の0になる。重賞は race_name='○○ステークス' で G 判定不可な点は既知の限界)。
    """
    bucket = _bucket(pred_race.get("grade") or pred_race.get("race_name", ""))
    if bucket not in EDGE_BUCKETS:
        return []
    cands = []
    for e in (pred_race.get("entries") or []):
        umaban = e.get("umaban")
        rank_w = e.get("rank_w")
        odds_rank = e.get("odds_rank")
        odds = e.get("odds")
        win_ev = e.get("win_ev")
        if (not umaban or rank_w is None or odds_rank is None
                or odds is None or win_ev is None):
            continue
        gap = odds_rank - rank_w
        if (rank_w <= pred_rank_max and gap >= gap_min
                and odds_lo <= odds < odds_hi and win_ev >= win_ev_floor):
            cands.append({
                "umaban": umaban,
                "horse_name": e.get("horse_name", ""),
                "rank_w": rank_w,
                "odds_rank": odds_rank,
                "gap": gap,
                "odds": odds,
                "win_ev": round(float(win_ev), 2),
                "cls": bucket,
            })
    cands.sort(key=lambda c: -c["win_ev"])  # 信号強度(評価ベース)降順
    if top_k is not None:
        cands = cands[:top_k]
    return cands


def log_picks(date_str: str, params: dict = None, *, now: str = None,
              window_min: float = None) -> dict:
    """predictions.json から gap5単勝を選定し picks_{date}.json に追記 (race単位で冪等)。

    window_min 指定時は「投票窓内のレースのみ」記録 = 締切間際の bet 時オッズで記録。None=全レース。
    """
    params = params or dict(DEFAULT_PARAMS)
    path = _picks_path(date_str)
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {"date": date_str, "params": params, "picks": [], "settled": False}
    already = {p["race_id"] for p in doc["picks"]}
    try:
        preds = _predictions(date_str)
    except FileNotFoundError:
        # 非開催日 (predictions.json 無し) — 毎日走る scheduler 用に静かに no-op
        # (平日にトレースバックを吐き続けないため)。
        return {"date": date_str, "added": 0, "total": len(doc["picks"]),
                "skip": "no predictions (非開催日)", "path": str(path)}
    in_window = _window_race_ids(date_str, window_min) if window_min is not None else None
    ts = now or datetime.now().isoformat(timespec="seconds")
    added = 0
    for race in preds.get("races", []):
        rid = str(race.get("race_id"))
        if rid in already:
            continue
        if in_window is not None and rid not in in_window:
            continue
        picks = select_gap_tansho(race, **params)
        for pk in picks:
            pk.update({"race_id": rid, "venue_name": race.get("venue_name", ""),
                       "race_number": race.get("race_number"), "logged_at": ts,
                       "stake": STAKE})
            doc["picks"].append(pk)
            added += 1
        if picks:
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
    ap.add_argument("--today", action="store_true", help="--date を今日に")
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--settle", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--window", type=float, default=None,
                    help="投票窓(分): 締切 window 分前以内のレースのみ記録 = bet時オッズ "
                         "(standalone bat を数分おきに回す用・例 --window 8)")
    args = ap.parse_args()
    if args.today and not args.date:
        args.date = datetime.now().strftime("%Y-%m-%d")
    if args.report:
        r = report()
        print(f"\n=== gap5単勝エッジ shadow 累積 ({r['settled_days']}開催) ===")
        print(f"  投票 {r['n_bet']}本 / ROI {r['roi']:.1f}% / PnL {r['pnl']:+,.0f}円(100円/点) "
              f"/ 的中 {r['hit']:.1f}% / ≥1000% {r['big_1000pct']}回 / maxDD {r['max_dd']:,.0f}円")
        # in-sample ベンチ併記 (forward 乖離監視・docs §8)
        target_n = 300  # 的中~5%・~12点/月 → CI が 100% を外すのに ~300点(≈2年)
        delta = (f"{r['roi'] - INSAMPLE_BROAD_ROI:+.0f}pt" if r["n_bet"] else "—")
        print(f"  [in-sample committed: ROI {INSAMPLE_BROAD_ROI:.0f}% / n{INSAMPLE_BROAD_N} (P(null≥130%)=0.026)]")
        print(f"  forward 乖離 {delta} / 有意判定まで {r['n_bet']}/{target_n}点 "
              f"(forward は速い検証でなく長期ガードレール)")
        for d, n, roi, pnl, big in r["days"]:
            print(f"    {d}: {n}本 ROI {roi:.0f}% PnL {pnl:+,.0f} 天井{big}")
        return
    if not args.date:
        ap.error("--date 必須 (--log / --settle)")
    if args.log:
        print("log:", log_picks(args.date, window_min=args.window))
    if args.settle:
        print("settle:", settle(args.date))


if __name__ == "__main__":
    main()

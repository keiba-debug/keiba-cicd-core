# -*- coding: utf-8 -*-
"""コメAI pick × MLシグナル × 実払戻 の結合データセット + スリーブ実装形ポートフォリオ再現。

comment_a スリーブ (docs/comment_a_sleeve_design.md) が引用するエビデンス数値の再現器
(シズネレビュー 🔴-2 対応: 「照合可能でない数字を設計に書かない」)。

build:      picks(2024-2026) × predictions × haraimodoshi を結合した JSONL を生成
            (1行 = 1 pick。複勝実払戻 + ワイド/馬連 対 ML上位・1番人気・他pick + MLフィールド)
portfolio:  スリーブ実装形 (複2u [R4通過3u] : 単1u : ワイド×ML1位 1u) の実払戻ポートフォリオを
            年別に集計 (日付クラスタ bootstrap CI・尻尾除外)

Usage:
  python -m ml.analyze.comment_sleeve_dataset build --since 2024-01-01
  python -m ml.analyze.comment_sleeve_dataset portfolio            # 2025 / 2026 年別
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.db import query  # noqa: E402

DATA_ROOT = os.environ.get("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
OUT = os.path.join(DATA_ROOT, "analysis", "comment_pick_ml_dataset.jsonl")
CONF = {"高": "A", "中": "B", "低": "C"}
ML_FIELDS = ["rank_w", "rank_p", "win_ev", "place_ev", "pred_proba_w_cal",
             "pred_proba_p_raw", "place_odds_min", "odds_rank", "odds_move",
             "ar_deviation", "dev_gap", "closing_strength", "is_value_bet"]
R4_UPLIFT = 0.196  # comment_a_live.R4_UPLIFT と同値 (2025年実測のＡ印複勝率上乗せ)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _pairs(row, prefix, nmax, nkumi):
    out = {}
    for i in range(1, nmax + 1):
        ks = [(row.get(f"{prefix}{i}_KUMIBAN{j}") or "").strip() for j in range(1, nkumi + 1)]
        pay = (row.get(f"{prefix}{i}_HARAIMODOSHIKIN") or "").strip()
        if not all(ks) or not pay:
            continue
        try:
            if int(pay) > 0:
                out[tuple(sorted(int(k) for k in ks))] = int(pay)
        except ValueError:
            continue
    return out


def load_day_payouts(date):
    """haraimodoshi 日単位バッチ (1日1クエリ — 1クエリ1接続設計のポート枯渇対策)。"""
    ymd = date.replace("-", "")
    rows = query("SELECT * FROM haraimodoshi WHERE RACE_CODE LIKE %s", (ymd + "%",))
    out = {}
    for row in rows or []:
        rid = str(row.get("RACE_CODE"))
        fuku = {}
        for i in range(1, 6):
            u = (row.get(f"FUKUSHO{i}_UMABAN") or "").strip()
            p = (row.get(f"FUKUSHO{i}_HARAIMODOSHIKIN") or "").strip()
            try:
                if u and p and int(p) > 0:
                    fuku[int(u)] = int(p)
            except ValueError:
                continue
        out[rid] = {"fuku": fuku,
                    "wide": _pairs(row, "WIDE", 7, 2),
                    "umaren": _pairs(row, "UMAREN", 3, 2)}
    return out


def build(since: str, until: str, out_path: str) -> int:
    n_rows = 0
    picks_dir = os.path.join(DATA_ROOT, "comment_llm", "live")
    with open(out_path, "w", encoding="utf-8") as out:
        for pf in sorted(glob.glob(os.path.join(picks_dir, "picks_*.json"))):
            date = os.path.basename(pf)[len("picks_"):-len(".json")]
            if date < since or date > until:
                continue
            try:
                picks_day = json.load(open(pf, encoding="utf-8"))
            except Exception:
                continue
            if not picks_day:
                continue
            y, mm, dd = date.split("-")
            rdir = os.path.join(DATA_ROOT, "races", y, mm, dd)

            races = {}
            for f in glob.glob(os.path.join(rdir, "race_2*.json")):
                try:
                    j = json.load(open(f, encoding="utf-8"))
                except Exception:
                    continue
                races[str(j.get("race_id"))] = j

            model = {}
            ppath = os.path.join(rdir, "predictions.json")
            if os.path.exists(ppath):
                try:
                    pj = json.load(open(ppath, encoding="utf-8"))
                    for r in pj.get("races") or []:
                        model[str(r.get("race_id"))] = {
                            int(e["umaban"]): e for e in r.get("entries") or []
                            if e.get("umaban") is not None}
                except Exception:
                    pass

            day_pay = load_day_payouts(date)

            for race in picks_day:
                rid = str(race.get("race_id"))
                rj = races.get(rid)
                plist = [p for p in (race.get("picks") or []) if p.get("umaban") is not None]
                if not rj or not plist:
                    continue
                ent = {e["umaban"]: e for e in rj.get("entries") or []
                       if e.get("umaban") is not None}
                if not ent or all(not (e.get("finish_position") or 0) for e in ent.values()):
                    continue
                pay = day_pay.get(rid) or {}
                fuku = pay.get("fuku") or {}
                wide = pay.get("wide") or {}
                umrn = pay.get("umaren") or {}
                ment = model.get(rid) or {}
                ranked = sorted((e for e in ment.values() if e.get("rank_w")),
                                key=lambda e: e["rank_w"])
                ml_top = [int(e["umaban"]) for e in ranked[:4]]
                pop_map = {e.get("popularity"): u for u, e in ent.items()}
                pick_umas = [int(p["umaban"]) for p in plist
                             if (ent.get(int(p["umaban"])) or {}).get("finish_position")]

                for p in plist:
                    u = int(p["umaban"])
                    e = ent.get(u)
                    g = CONF.get(p.get("confidence"))
                    if e is None or g is None:
                        continue
                    fin = int(e.get("finish_position") or 0)
                    if fin == 0:
                        continue  # 取消/除外 = 返還 → 賭けなし
                    me = ment.get(u) or {}
                    partners = {}
                    nxt = [x for x in ml_top if x != u]
                    for tag, pu in (("ml1", nxt[0] if nxt else None),
                                    ("ml2", nxt[1] if len(nxt) > 1 else None),
                                    ("ml3", nxt[2] if len(nxt) > 2 else None),
                                    ("pop1", pop_map.get(1) if pop_map.get(1) != u
                                     else pop_map.get(2))):
                        if pu is None or pu == u:
                            continue
                        pe = ent.get(pu)
                        if pe is None or not (pe.get("finish_position") or 0):
                            continue
                        key = tuple(sorted([u, pu]))
                        pme = ment.get(pu) or {}
                        partners[tag] = {
                            "uma": pu, "pop": pe.get("popularity"),
                            "wide_pay": wide.get(key, 0) if wide else None,
                            "umaren_pay": umrn.get(key, 0) if umrn else None,
                            "p_win_ev": pme.get("win_ev"),
                            "p_rank_w": pme.get("rank_w"),
                        }
                    row = {
                        "date": date, "rid": rid, "uma": u, "grade": g,
                        "pop": e.get("popularity"), "odds": e.get("odds"), "fin": fin,
                        "grade_race": (rj.get("grade") or "").strip(),
                        "num_runners": rj.get("num_runners"),
                        "fuku_pay": fuku.get(u, 0) if fuku else None,
                        "partners": partners,
                        "n_picks_race": len(pick_umas),
                        **{k: me.get(k) for k in ML_FIELDS},
                    }
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    n_rows += 1
    print(f"[OK] {out_path} rows={n_rows}")
    return n_rows


# ---------------------------------------------------------------------------
# portfolio: スリーブ実装形 (複2u[R4で3u]/単1u/ワイド1u)
# ---------------------------------------------------------------------------

def _r4_pass(r) -> bool:
    p, o = r.get("pred_proba_p_raw"), r.get("place_odds_min")
    return (isinstance(p, (int, float)) and isinstance(o, (int, float))
            and o > 0 and (p + R4_UPLIFT) * o >= 1.0)


def _legs(r, w_fuku):
    """1 pick の (cost, pay) 脚リスト。単勝は確定オッズ×100 (JRA 単勝払戻と一致)。"""
    out = []
    if r.get("fuku_pay") is not None:
        tan = r["odds"] * 100 if (r["fin"] == 1 and isinstance(r["odds"], (int, float))) else 0
        out.append((100, tan))
        out.append((w_fuku * 100, r["fuku_pay"] * w_fuku))
    w = (r.get("partners") or {}).get("ml1")
    if w and w.get("wide_pay") is not None:
        out.append((100, w["wide_pay"]))
    return out


def portfolio(rows, *, r4_boost: bool, tail=5, iters=2000, seed=11):
    by_date = defaultdict(lambda: [0, 0])
    cost = ret = 0
    pays = []
    for r in rows:
        wf = 3 if (r4_boost and _r4_pass(r)) else 2
        for c, p in _legs(r, wf):
            cost += c
            ret += p
            by_date[r["date"]][0] += c
            by_date[r["date"]][1] += p
            if p > 0:
                pays.append(p)
    if not cost:
        return None
    pays.sort(reverse=True)
    dates = sorted(by_date)
    rng = random.Random(seed)
    boot = []
    for _ in range(iters):
        c = p = 0
        for d in rng.choices(dates, k=len(dates)):
            c += by_date[d][0]
            p += by_date[d][1]
        boot.append(p / c * 100)
    boot.sort()
    return {
        "n_picks": len(rows), "cost": cost,
        "roi": round(ret / cost * 100, 1),
        "roi_ex_tail": round((ret - sum(pays[:tail])) / cost * 100, 1),
        "ci95": [round(boot[int(0.025 * len(boot))], 1),
                 round(boot[int(0.975 * len(boot))], 1)],
        "p_roi_le_100": round(sum(1 for b in boot if b <= 100) / len(boot), 4),
    }


def run_portfolio(path: str):
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    for year in ("2025", "2026"):
        A = [r for r in rows if r["date"].startswith(year) and r["grade"] == "A"]
        if not A:
            continue
        n_r4 = sum(1 for r in A if _r4_pass(r))
        print(f"{year} A印 n={len(A)} R4通過={n_r4} ({100 * n_r4 / len(A):.0f}%)")
        for label, boost in (("2:1:1 (R4増額なし)", False), ("2:1:1 + R4複勝3u", True)):
            s = portfolio(A, r4_boost=boost)
            print(f"  {label:<18} roi={s['roi']} ex5={s['roi_ex_tail']} "
                  f"CI95={s['ci95']} p<=100={s['p_roi_le_100']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--since", default="2024-01-01")
    b.add_argument("--until", default="2026-12-31")
    b.add_argument("--out", default=OUT)
    p = sub.add_parser("portfolio")
    p.add_argument("--dataset", default=OUT)
    args = ap.parse_args()
    if args.cmd == "build":
        build(args.since, args.until, args.out)
    else:
        run_portfolio(args.dataset)


if __name__ == "__main__":
    main()

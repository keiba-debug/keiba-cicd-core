# -*- coding: utf-8 -*-
"""コメAI picks (markSet4 = comment_llm 人気薄ピックアップ) の実払戻バックテスト。

C-1 (edge_map §10) の後継。市場は全8券種効率的が確定済みなので、
コメAIエッジ (複勝的中率 +4.7pt) が単独で控除率を越えるかを
**haraimodoshi 実払戻** で検証する (従来集計の place_odds_min 下限試算を格上げ)。

入力:
  data3/comment_llm/live/picks_YYYY-MM-DD.json   … コメAI印 (confidence 高/中/低 → Ａ/Ｂ/Ｃ)
  data3/races/YYYY/MM/DD/race_*.json             … 着順・人気・グレード・頭数
  data3/races/YYYY/MM/DD/predictions.json        … rank_w (ワイドML併用ペア用)
  mykeibadb.haraimodoshi                          … 単勝/複勝/ワイド 実払戻 (同着自動対応)

戦略:
  fukusho    : pick を 100円複勝ベタ買い
  tansho     : pick を 100円単勝ベタ買い (参考・尻尾依存の既知)
  wide_ml1   : pick × モデル rank_w 1位 (pick 自身は除いて上位から1頭)
  wide_ml2   : pick × モデル上位2頭 (2点)
  wide_ml3   : pick × モデル上位3頭 (3点)
  wide_pop1  : pick × 1番人気 (pick 自身が1番人気なら2番人気)
  wide_pair  : 同一レースの pick 同士 (2頭以上いるレースのみ)

グレードフィルタ: all / Ａのみ / Ａ+Ｂ (wide_pair は両頭がフィルタ通過時のみ)

検証: 年別・月別 walk-forward、日付クラスタ bootstrap CI、的中上位尻尾除外 ROI、
      重賞/平場 × 年 クロス (backfill の LLM 記憶汚染チェック: 過去年の重賞だけ
      好成績なら LLM が結果を記憶している疑い)。

取消/除外 (確定レースで fin=0) は実運用で返還のため賭け自体をスキップ (件数は記録)。

Usage:
  python -m ml.analyze.backtest_comment_picks_payout                 # 全期間 (2022-12〜)
  python -m ml.analyze.backtest_comment_picks_payout --since 2023-01-01
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.db import query  # noqa: E402
from ml.settle_purchases import get_wide_payouts  # noqa: E402

DATA_ROOT = os.environ.get("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
PICKS_DIR = os.path.join(DATA_ROOT, "comment_llm", "live")
OUT_PATH = os.path.join(DATA_ROOT, "analysis", "comment_picks_payout_backtest.json")

CONF_TO_GRADE = {"高": "A", "中": "B", "低": "C"}
BET = 100  # 円/点

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# haraimodoshi: 単勝/複勝 実払戻 (1クエリ/レース。ワイドは settle_purchases 流用)
# ---------------------------------------------------------------------------

def get_tansho_fukusho_payouts(race_code: str):
    """{umaban: payout_per_100yen} を (単勝, 複勝) で返す。同着は複数行が載る。"""
    rows = query("SELECT * FROM haraimodoshi WHERE RACE_CODE = %s", (race_code,))
    tan, fuku = {}, {}
    if not rows:
        return tan, fuku
    row = rows[0]
    for i in range(1, 4):  # TANSHO1~3 (同着)
        u = (row.get(f"TANSHO{i}_UMABAN") or "").strip()
        p = (row.get(f"TANSHO{i}_HARAIMODOSHIKIN") or "").strip()
        try:
            if u and p and int(p) > 0:
                tan[int(u)] = int(p)
        except ValueError:
            continue
    for i in range(1, 6):  # FUKUSHO1~5 (同着で最大5頭)
        u = (row.get(f"FUKUSHO{i}_UMABAN") or "").strip()
        p = (row.get(f"FUKUSHO{i}_HARAIMODOSHIKIN") or "").strip()
        try:
            if u and p and int(p) > 0:
                fuku[int(u)] = int(p)
        except ValueError:
            continue
    return tan, fuku


# ---------------------------------------------------------------------------
# 日次ロード
# ---------------------------------------------------------------------------

def load_day_races(date: str):
    """{race_id: {fin/odds/pop per umaban, grade, race_name, num_runners}}"""
    y, mm, dd = date.split("-")
    rdir = os.path.join(DATA_ROOT, "races", y, mm, dd)
    races = {}
    for f in glob.glob(os.path.join(rdir, "race_2*.json")):
        if "race_info" in os.path.basename(f):
            continue
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        rid = str(j.get("race_id"))
        ent = {}
        for e in j.get("entries") or []:
            u = e.get("umaban")
            if u is None:
                continue
            try:
                fin = int(e.get("finish_position") or 0)
            except (TypeError, ValueError):
                fin = 0
            ent[int(u)] = {"fin": fin, "odds": e.get("odds"), "pop": e.get("popularity")}
        races[rid] = {
            "entries": ent,
            "grade": (j.get("grade") or "").strip(),
            "race_name": j.get("race_name") or "",
            "num_runners": j.get("num_runners") or len(ent),
        }
    return races


def load_day_model(date: str):
    """{race_id: [umaban を rank_w 昇順で]}"""
    y, mm, dd = date.split("-")
    pred_path = os.path.join(DATA_ROOT, "races", y, mm, dd, "predictions.json")
    model = {}
    if not os.path.exists(pred_path):
        return model
    try:
        pj = json.load(open(pred_path, encoding="utf-8"))
    except Exception:
        return model
    for r in pj.get("races") or []:
        rid = str(r.get("race_id"))
        pairs = []
        for e in r.get("entries") or []:
            rw = e.get("rank_w")
            u = e.get("umaban")
            if rw is not None and u is not None:
                try:
                    pairs.append((int(rw), int(u)))
                except (TypeError, ValueError):
                    continue
        model[rid] = [u for _, u in sorted(pairs)]
    return model


# ---------------------------------------------------------------------------
# ベット生成 + 決済
# ---------------------------------------------------------------------------

def is_graded(race_meta) -> bool:
    g = (race_meta.get("grade") or "").upper()
    return g.startswith("G") or "重賞" in (race_meta.get("race_name") or "")


def collect_bets(since: str, until: str):
    """全 picks を実払戻で決済した bet 行のリストを戦略別に返す。"""
    bets = defaultdict(list)   # strategy -> [bet]
    skips = defaultdict(int)
    n_picks = 0
    pops = []

    pick_files = sorted(glob.glob(os.path.join(PICKS_DIR, "picks_*.json")))
    for pf in pick_files:
        date = os.path.basename(pf)[len("picks_"):-len(".json")]
        if date < since or date > until:
            continue
        try:
            picks_day = json.load(open(pf, encoding="utf-8"))
        except Exception:
            skips["picks_json_error"] += 1
            continue
        if not picks_day:
            continue
        races = load_day_races(date)
        model = load_day_model(date)

        for race in picks_day:
            rid = str(race.get("race_id"))
            rmeta = races.get(rid)
            plist = [p for p in (race.get("picks") or []) if p.get("umaban") is not None]
            if not plist:
                continue
            if rmeta is None:
                skips["race_json_missing"] += len(plist)
                continue
            ent = rmeta["entries"]
            # 着順未確定レース (全 fin=0) はスキップ
            if not ent or all(v["fin"] == 0 for v in ent.values()):
                skips["race_unconfirmed"] += len(plist)
                continue

            tan_pay, fuku_pay = get_tansho_fukusho_payouts(rid)
            wide_pay = get_wide_payouts(rid)
            graded = is_graded(rmeta)
            ranked = model.get(rid) or []
            pop1 = next((u for u, v in ent.items() if v.get("pop") == 1), None)
            pop2 = next((u for u, v in ent.items() if v.get("pop") == 2), None)

            valid_picks = []  # (umaban, grade) 取消除く
            for p in plist:
                n_picks += 1
                g = CONF_TO_GRADE.get(p.get("confidence"))
                if g is None:
                    skips["no_grade"] += 1
                    continue
                u = int(p["umaban"])
                ev = ent.get(u)
                if ev is None or ev["fin"] == 0:
                    skips["scratched"] += 1  # 取消/除外 = 返還 → 賭けなし
                    continue
                if ev.get("pop"):
                    pops.append(ev["pop"])
                valid_picks.append((u, g))
                base = {"date": date, "grade": g, "graded": graded,
                        "pop": ev.get("pop"), "rid": rid}

                # 複勝 / 単勝 (発売なし・データ欠損は haraimodoshi 空 → 3着内でも配当0に
                # なり過小評価するため、辞書空ならスキップ)
                if fuku_pay:
                    pay = fuku_pay.get(u, 0) * BET // 100
                    bets["fukusho"].append({**base, "pay": pay})
                else:
                    skips["fukusho_no_table"] += 1
                if tan_pay or any(v["fin"] == 1 for v in ent.values()):
                    pay = tan_pay.get(u, 0) * BET // 100
                    bets["tansho"].append({**base, "pay": pay})

                # ワイド (辞書空 = 発売なし/未取得 → スキップ)
                if wide_pay:
                    def wbet(partner, strat):
                        if partner is None or partner == u:
                            return
                        pv = ent.get(partner)
                        if pv is None or pv["fin"] == 0:
                            return  # 相手取消 = 返還
                        key = tuple(sorted([u, partner]))
                        bets[strat].append({**base,
                                            "pay": wide_pay.get(key, 0) * BET // 100})

                    ml_partners = [x for x in ranked if x != u][:3]
                    if ml_partners:
                        wbet(ml_partners[0], "wide_ml1")
                        for x in ml_partners[:2]:
                            wbet(x, "wide_ml2")
                        for x in ml_partners:
                            wbet(x, "wide_ml3")
                    else:
                        skips["no_model"] += 1
                    wbet(pop1 if pop1 != u else pop2, "wide_pop1")
                else:
                    skips["wide_no_table"] += 1

            # pick 同士のワイド
            if wide_pay and len(valid_picks) >= 2:
                for i in range(len(valid_picks)):
                    for k in range(i + 1, len(valid_picks)):
                        u1, g1 = valid_picks[i]
                        u2, g2 = valid_picks[k]
                        key = tuple(sorted([u1, u2]))
                        bets["wide_pair"].append({
                            "date": date, "rid": rid, "graded": graded,
                            "grade": g1, "grade2": g2, "pop": None,
                            "pay": wide_pay.get(key, 0) * BET // 100})
    return bets, skips, n_picks, pops


# ---------------------------------------------------------------------------
# 集計
# ---------------------------------------------------------------------------

def _roi(rows):
    n = len(rows)
    if n == 0:
        return None
    return round(sum(r["pay"] for r in rows) / (n * BET) * 100, 1)


def summarize(rows, tail_cut=5, boot_iters=2000, seed=42):
    n = len(rows)
    if n == 0:
        return {"n": 0}
    pays = sorted((r["pay"] for r in rows if r["pay"] > 0), reverse=True)
    hits = len(pays)
    ret = sum(pays)
    cost = n * BET
    roi = ret / cost * 100

    # 日付クラスタ bootstrap (レース内相関を日単位で保守的に吸収)
    by_date = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)
    dates = sorted(by_date)
    rng = random.Random(seed)
    boot = []
    for _ in range(boot_iters):
        s_cost = s_ret = 0
        for d in rng.choices(dates, k=len(dates)):
            drows = by_date[d]
            s_cost += len(drows) * BET
            s_ret += sum(r["pay"] for r in drows)
        if s_cost:
            boot.append(s_ret / s_cost * 100)
    boot.sort()
    ci_lo = boot[int(0.025 * len(boot))] if boot else None
    ci_hi = boot[int(0.975 * len(boot))] if boot else None
    p_le_100 = sum(1 for b in boot if b <= 100) / len(boot) if boot else None

    by_year = {}
    for yr in sorted({r["date"][:4] for r in rows}):
        sub = [r for r in rows if r["date"][:4] == yr]
        by_year[yr] = {"n": len(sub), "roi": _roi(sub),
                       "hit": round(100 * sum(1 for r in sub if r["pay"] > 0) / len(sub), 1)}
    by_month = {m: _roi([r for r in rows if r["date"][:7] == m])
                for m in sorted({r["date"][:7] for r in rows})}
    pos_months = sum(1 for v in by_month.values() if v is not None and v > 100)

    return {
        "n": n, "hits": hits, "hit_rate": round(100 * hits / n, 1),
        "roi": round(roi, 1),
        "roi_ex_tail": round((ret - sum(pays[:tail_cut])) / cost * 100, 1),
        "tail_cut": tail_cut,
        "ci95": [round(ci_lo, 1), round(ci_hi, 1)] if ci_lo is not None else None,
        "p_roi_le_100": round(p_le_100, 4) if p_le_100 is not None else None,
        "by_year": by_year,
        "by_month": by_month,
        "months_over_100": f"{pos_months}/{len(by_month)}",
    }


def grade_filter(rows, allowed):
    out = []
    for r in rows:
        g2 = r.get("grade2")
        if g2 is not None:  # wide_pair は両頭通過
            if r["grade"] in allowed and g2 in allowed:
                out.append(r)
        elif r["grade"] in allowed:
            out.append(r)
    return out


def build(since: str, until: str):
    bets, skips, n_picks, pops = collect_bets(since, until)
    filters = {"all": {"A", "B", "C"}, "A": {"A"}, "AB": {"A", "B"}}
    strategies = {}
    for strat in sorted(bets):
        rows = bets[strat]
        strategies[strat] = {
            fname: summarize(grade_filter(rows, allowed))
            for fname, allowed in filters.items()
        }

    # LLM 記憶汚染チェック: 重賞/平場 × 年 (複勝)
    contamination = {}
    for label, cond in (("graded", True), ("non_graded", False)):
        sub = [r for r in bets.get("fukusho", []) if r["graded"] == cond]
        contamination[label] = {
            yr: {"n": len(s), "roi": _roi(s),
                 "hit": round(100 * sum(1 for r in s if r["pay"] > 0) / len(s), 1) if s else None}
            for yr in sorted({r["date"][:4] for r in sub})
            for s in [[r for r in sub if r["date"][:4] == yr]]
        }

    jst = timezone(timedelta(hours=9))
    meta = {
        "since": since, "until": until,
        "n_picks_raw": n_picks,
        "avg_pop": round(sum(pops) / len(pops), 2) if pops else None,
        "skips": dict(skips),
        "bet_unit_yen": BET,
        "generated_at": datetime.now(jst).isoformat(timespec="seconds"),
        "method": ("haraimodoshi 実払戻決済 (複勝=FUKUSHO1-5, ワイド=WIDE1-7, 単勝=TANSHO1-3)。"
                   "取消は返還=賭けなし。bootstrap は日付クラスタ2000回。"),
        "caveats": [
            "picks は 2026-07-02/03 backfill (リーク修正 06-28 後) — 過去走時点フィルタ有効",
            "2023-2025 の LLM 生成は事後 backfill = LLM が有名レース結果を記憶している汚染リスク → contamination 表で監視",
            "2023-2025 の predictions (rank_w) は当時モデルの in-sample の可能性 (ワイドML系のみ影響)",
            "picks 入力オッズは確定オッズ由来 (ライブは朝オッズ) — 選定母集団が僅かにズレる",
        ],
    }
    return {"meta": meta, "strategies": strategies,
            "contamination_check_fukusho": contamination}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2022-01-01")
    ap.add_argument("--until", default="2026-12-31")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    payload = build(args.since, args.until)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    m = payload["meta"]
    print(f"[OK] saved: {args.out}")
    print(f"  picks={m['n_picks_raw']} avg_pop={m['avg_pop']} skips={m['skips']}")
    for strat, filt in payload["strategies"].items():
        for fname, s in filt.items():
            if not s.get("n"):
                continue
            print(f"  {strat:<10} [{fname:<3}] n={s['n']:>6} hit={s['hit_rate']:>5}% "
                  f"roi={s['roi']:>6} ex{s['tail_cut']}={s['roi_ex_tail']:>6} "
                  f"ci95={s['ci95']} p<=100={s['p_roi_le_100']} "
                  f"m+={s['months_over_100']}")


if __name__ == "__main__":
    main()

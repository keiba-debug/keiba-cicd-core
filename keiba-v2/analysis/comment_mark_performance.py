# -*- coding: utf-8 -*-
"""
AIコメント印(markSet4 = comment_llm 人気薄ピックアップ Ａ高/Ｂ中/Ｃ低) の成績集計。

- 純粋集計: グレード別(Ａ/Ｂ/Ｃ)の勝率・複勝率・単勝回収率、月別walk-forward
- ML分析との組み合わせ: グレード × モデル勝率順位(rank_w<=3) / 単勝EV(win_ev>=1) のクロス集計

入力:
  data3/comment_llm/live/picks_YYYY-MM-DD.json   … 発生源(confidence: 高/中/低)
  data3/races/YYYY/MM/DD/race_*.json             … 着順・確定オッズ・人気
  data3/races/YYYY/MM/DD/predictions.json        … rank_w / win_ev
出力:
  data3/analysis/comment_mark_performance.json

Web: /analysis/comment-marks が本JSONを読んで表示する(表示専用・買い目に影響しない)。

使い方:
  python -m analysis.comment_mark_performance                # 2026-01-01 以降 全picks
  python -m analysis.comment_mark_performance --since 2026-04-01
"""
from __future__ import annotations
import argparse
import glob
import json
import os
from datetime import datetime, timezone, timedelta

DATA_ROOT = os.environ.get("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
PICKS_DIR = os.path.join(DATA_ROOT, "comment_llm", "live")
OUT_PATH = os.path.join(DATA_ROOT, "analysis", "comment_mark_performance.json")

# confidence(picks) → グレード
CONF_TO_GRADE = {"高": "Ａ", "中": "Ｂ", "低": "Ｃ"}
GRADE_ORDER = ["Ａ", "Ｂ", "Ｃ"]
GRADE_LABEL = {"Ａ": "Ａ(高確信)", "Ｂ": "Ｂ(中確信)", "Ｃ": "Ｃ(低確信)"}


def _load_day(date: str):
    """date=YYYY-MM-DD → (results, model) 辞書。key=(race_id, umaban)。"""
    y, mm, dd = date.split("-")
    rdir = os.path.join(DATA_ROOT, "races", y, mm, dd)
    results, model = {}, {}
    for f in glob.glob(os.path.join(rdir, "race_*.json")):
        if "race_info" in os.path.basename(f):
            continue
        try:
            j = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for e in j.get("entries") or []:
            fp = e.get("finish_position")
            try:
                fp = int(fp)
            except (TypeError, ValueError):
                fp = None
            results[(str(j.get("race_id")), str(e.get("umaban")))] = {
                "fin": fp,
                "odds": e.get("odds"),
                "pop": e.get("popularity"),
            }
    pred_path = os.path.join(rdir, "predictions.json")
    if os.path.exists(pred_path):
        try:
            pj = json.load(open(pred_path, encoding="utf-8"))
            for r in pj.get("races") or []:
                for e in r.get("entries") or []:
                    model[(str(r.get("race_id")), str(e.get("umaban")))] = {
                        "rank_w": e.get("rank_w"),
                        "win_ev": e.get("win_ev"),
                        "place_odds_min": e.get("place_odds_min"),
                    }
        except Exception:
            pass
    return results, model


def _collect(since: str):
    rows = []
    for pf in sorted(glob.glob(os.path.join(PICKS_DIR, "picks_*.json"))):
        date = os.path.basename(pf)[len("picks_"):-len(".json")]
        if date < since:
            continue
        try:
            picks = json.load(open(pf, encoding="utf-8"))
        except Exception:
            continue
        results, model = _load_day(date)
        for race in picks:
            rid = str(race.get("race_id"))
            for p in race.get("picks") or []:
                key = (rid, str(p.get("umaban")))
                r = results.get(key, {})
                m = model.get(key, {})
                grade = CONF_TO_GRADE.get(p.get("confidence"))
                if grade is None:
                    continue
                rows.append({
                    "date": date,
                    "month": date[:7],
                    "grade": grade,
                    "fin": r.get("fin"),
                    "odds": r.get("odds") if r.get("odds") is not None else p.get("odds"),
                    "pop": r.get("pop"),
                    "rank_w": m.get("rank_w"),
                    "win_ev": m.get("win_ev"),
                    "place_odds_min": m.get("place_odds_min"),
                })
    return rows


def _stat(sub, tail_cut=5):
    """着確定分のみで各種指標を返す。
      roi        = 単勝回収率(確定オッズ×100円均等)
      roi_ex_tail= 単勝回収率から的中の高配当上位 tail_cut 本を除いた値(尻尾依存の可視化)
      place_roi  = 複勝回収率(下限・place_odds_min×100。3着内で成立。監査と同じ保守的手法)
    """
    done = [r for r in sub if r.get("fin")]
    n = len(done)
    if n == 0:
        return {"n": 0, "wins": 0, "places": 0,
                "win_rate": None, "place_rate": None,
                "roi": None, "roi_ex_tail": None, "tail_cut": tail_cut,
                "place_roi": None, "place_n_priced": 0}
    wins = sum(1 for r in done if r["fin"] == 1)
    places = sum(1 for r in done if r["fin"] <= 3)

    # 単勝: 的中配当(円)のリスト
    win_payouts = sorted(
        (r["odds"] * 100 for r in done
         if r["fin"] == 1 and isinstance(r["odds"], (int, float))),
        reverse=True,
    )
    ret = sum(win_payouts)
    ret_ex = sum(win_payouts[tail_cut:])  # 上位 tail_cut 本を除外

    # 複勝(下限): 3着内 かつ place_odds_min>0 の頭のみで賭け→払戻を算出
    place_bets = [r for r in done
                  if isinstance(r.get("place_odds_min"), (int, float))
                  and r["place_odds_min"] > 0]
    place_n = len(place_bets)
    place_ret = sum(r["place_odds_min"] * 100 for r in place_bets if r["fin"] <= 3)

    return {
        "n": n, "wins": wins, "places": places,
        "win_rate": round(100 * wins / n, 1),
        "place_rate": round(100 * places / n, 1),
        "roi": round(ret / (100 * n) * 100, 1),
        "roi_ex_tail": round(ret_ex / (100 * n) * 100, 1),
        "tail_cut": tail_cut,
        "place_roi": round(place_ret / (100 * place_n) * 100, 1) if place_n else None,
        "place_n_priced": place_n,
    }


def build(since: str):
    rows = _collect(since)
    done = [r for r in rows if r.get("fin")]
    dates = sorted(set(r["date"] for r in rows))
    pops = [r["pop"] for r in done if r["pop"]]

    # 純粋集計: グレード別
    overall = []
    for g in GRADE_ORDER:
        s = _stat([r for r in rows if r["grade"] == g])
        s.update(grade=g, label=GRADE_LABEL[g])
        overall.append(s)
    total = _stat(rows)
    total.update(grade="計", label="全体")
    overall.append(total)

    # 月別 walk-forward (グレード別)
    months = sorted(set(r["month"] for r in rows))
    monthly_by_grade = {}
    for g in GRADE_ORDER + ["計"]:
        series = []
        for mth in months:
            if g == "計":
                sub = [r for r in rows if r["month"] == mth]
            else:
                sub = [r for r in rows if r["month"] == mth and r["grade"] == g]
            s = _stat(sub)
            s["month"] = mth
            series.append(s)
        monthly_by_grade[g] = series

    # ML組み合わせ: グレード × 条件(該当/非該当)
    def cross(cond_name, cond):
        out = []
        for g in GRADE_ORDER + ["計"]:
            base = rows if g == "計" else [r for r in rows if r["grade"] == g]
            yes = _stat([r for r in base if cond(r)])
            no = _stat([r for r in base if not cond(r)])
            out.append({"grade": g, "label": GRADE_LABEL.get(g, "全体"),
                        "yes": yes, "no": no})
        return {"name": cond_name, "cells": out}

    cross_rankw = cross("rank_w<=3 (モデル勝率上位3)",
                        lambda r: (r["rank_w"] or 99) <= 3)
    cross_winev = cross("win_ev>=1.0 (モデル単勝+EV)",
                        lambda r: (r["win_ev"] or 0) >= 1.0)

    jst = timezone(timedelta(hours=9))
    meta = {
        "date_from": dates[0] if dates else None,
        "date_to": dates[-1] if dates else None,
        "n_days": len(dates),
        "n_picks": len(rows),
        "n_finished": len(done),
        "avg_pop": round(sum(pops) / len(pops), 1) if pops else None,
        "generated_at": datetime.now(jst).isoformat(timespec="seconds"),
        "source": "comment_llm/live/picks_*.json + races + predictions",
        "grade_map": {"Ａ": "高確信", "Ｂ": "中確信", "Ｃ": "低確信"},
        "note": ("AIコメント印=markSet4=comment_llm 人気薄ピックアップ。"
                 "単勝回収率は確定オッズ×100円均等賭けの試算(表示専用)。"),
    }
    return {
        "meta": meta,
        "overall": overall,
        "monthly_by_grade": monthly_by_grade,
        "cross": [cross_rankw, cross_winev],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-01-01", help="集計開始日 YYYY-MM-DD")
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()

    payload = build(args.since)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    m = payload["meta"]
    print(f"[OK] saved: {args.out}")
    print(f"  range={m['date_from']}..{m['date_to']} days={m['n_days']} "
          f"picks={m['n_picks']} finished={m['n_finished']} avg_pop={m['avg_pop']}")
    for row in payload["overall"]:
        print(f"  {row['label']:<10} n={row['n']:>5} win%={row['win_rate']} "
              f"place%={row['place_rate']} roi={row['roi']} "
              f"roi_ex{row['tail_cut']}={row['roi_ex_tail']} place_roi={row['place_roi']}")


if __name__ == "__main__":
    main()

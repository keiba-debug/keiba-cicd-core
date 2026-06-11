#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Step X: P複勝率の2入力較正 原理確認 (raw + 直前オッズ → 複勝支払い)

案X = polaris-2.0 期間で版整合させ「2入力較正が人気馬の複勝過小評価(-0.44)を潰せるか」を
解析のみ(モデル不触・低リスク)で確認する踏み石。 効けば案Z(experiment.py パイプライン同梱)へ。

fit: logit(p) = a*logit(raw) + b*log(odds) + c。 ablation: raw単独 / odds単独 / 両方。
- train/valid 時系列分割 (既定 2026-01-01)
- y = 複勝支払い (出走頭数で top2/top3 を切替: 8頭以上=top3, 5-7頭=top2, 4頭以下=複勝なし)
- 直前オッズ = 発走 N 分前 (core.odds_db.batch_get_win_odds_at_cutoff)
- 版フィルタ = predictions.json の model_version (既定 polaris-2.0 のみ = raw 分布を揃える)

CLI: python -m ml.analyze.fit_place_odds_calibration [--cutoff 5] [--split 20260101]
                                                     [--versions polaris-2.0]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

RACES_DIR = Path("C:/KEIBA-CICD/data3/races")
BANDS = ["<2.9", "3-9.9", "10-49.9", "50+"]


def _logit(p, eps=1e-4):
    p = np.clip(np.asarray(p, dtype=float), eps, 1 - eps)
    return np.log(p / (1 - p))


def _ece(p, y, nbins=10):
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0, 1, nbins + 1)
    n = len(p)
    ece = 0.0
    for i in range(nbins):
        if i < nbins - 1:
            m = (p >= edges[i]) & (p < edges[i + 1])
        else:
            m = (p >= edges[i]) & (p <= 1.0)
        if m.sum() == 0:
            continue
        ece += abs(p[m].mean() - y[m].mean()) * m.sum() / n
    return ece


def _slots(starters):
    """複勝支払い枠数: 8頭以上=3, 5-7頭=2, 4頭以下=複勝発売なし(0)。"""
    return 0 if starters <= 4 else (2 if starters <= 7 else 3)


def _band(od):
    return "<2.9" if od < 3 else "3-9.9" if od < 10 else "10-49.9" if od < 50 else "50+"


def _version_by_day(days):
    out = {}
    for d in days:
        p = RACES_DIR / d[:4] / d[4:6] / d[6:8] / "predictions.json"
        if not p.exists():
            continue
        try:
            obj = json.load(open(p, encoding="utf-8"))
            out[d] = obj.get("model_version") if isinstance(obj, dict) else None
        except (ValueError, OSError):
            out[d] = None
    return out


def main():
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="P複勝率の2入力較正 原理確認 (案X)")
    ap.add_argument("--cutoff", type=int, default=5, help="発走N分前の直前オッズ")
    ap.add_argument("--split", default="20260101", help="train/valid 分割日 YYYYMMDD")
    ap.add_argument("--versions", default="polaris-2.0",
                    help="対象モデル版(カンマ区切り)。 空文字で全版")
    args = ap.parse_args()

    races = load_backtest_cache()
    days = sorted({str(r.get("race_id"))[:8] for r in races if r.get("race_id")})
    ver_by_day = _version_by_day(days)
    target_vers = {v.strip() for v in args.versions.split(",") if v.strip()} or None

    from core import odds_db
    rids = [str(r.get("race_id")) for r in races if r.get("race_id")]
    cutoff_odds = odds_db.batch_get_win_odds_at_cutoff(rids, minutes_before=args.cutoff)
    print(f"[odds] 発走{args.cutoff}分前の直前オッズ: {len(cutoff_odds)} races")

    rec = []  # (date, raw, odds, y, band)
    skip_ver = 0
    for r in races:
        rid = str(r.get("race_id") or "")
        d = rid[:8]
        if target_vers is not None and ver_by_day.get(d) not in target_vers:
            skip_ver += 1
            continue
        ents = r.get("entries", []) or []
        starters = sum(1 for e in ents
                       if isinstance(e.get("finish_position"), int) and e["finish_position"] > 0)
        slots = _slots(starters)
        if slots == 0:
            continue
        race_co = cutoff_odds.get(rid, {})
        for e in ents:
            um = e.get("umaban")
            fp = e.get("finish_position")
            raw = e.get("pred_proba_p_raw")
            if (um is None or not isinstance(fp, int) or fp <= 0
                    or not isinstance(raw, (int, float))):
                continue
            od = (race_co.get(int(um)) or {}).get("odds")
            if not isinstance(od, (int, float)) or od <= 0:
                continue
            rec.append((d, float(raw), float(od), 1 if fp <= slots else 0, _band(od)))

    print(f"レコード: {len(rec)}  (版フィルタ除外 {skip_ver} races, 対象版={target_vers})")
    tr = [x for x in rec if x[0] < args.split]
    va = [x for x in rec if x[0] >= args.split]
    print(f"train(<{args.split})={len(tr)}  valid(>={args.split})={len(va)}  "
          f"複勝支払い率 train={np.mean([x[3] for x in tr]):.3f} valid={np.mean([x[3] for x in va]):.3f}")
    if len(tr) < 100 or len(va) < 100:
        print("[ERR] train/valid サンプル不足")
        return 1

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, log_loss

    def feats(data, cols):
        raw = np.array([x[1] for x in data])
        od = np.array([x[2] for x in data])
        parts = []
        if "raw" in cols:
            parts.append(_logit(raw))
        if "odds" in cols:
            parts.append(np.log(od))
        return np.column_stack(parts)

    y_tr = np.array([x[3] for x in tr])
    y_va = np.array([x[3] for x in va])
    raw_va = np.array([x[1] for x in va])
    band_va = np.array([x[4] for x in va])

    models = {
        "baseline raw(無補正)": None,
        "A raw単独": ["raw"],
        "B odds単独": ["odds"],
        "C raw+odds ★": ["raw", "odds"],
    }
    results = {}
    for name, cols in models.items():
        if cols is None:
            p_va = np.clip(raw_va, 1e-4, 1 - 1e-4)  # raw をそのまま複勝確率(現状 place_ev の前提)
            coef = None
        else:
            clf = LogisticRegression(C=1e6, max_iter=2000)
            clf.fit(feats(tr, cols), y_tr)
            p_va = clf.predict_proba(feats(va, cols))[:, 1]
            coef = (dict(zip(cols, clf.coef_[0])), float(clf.intercept_[0]))
        bands = {}
        for b in BANDS:
            idx = band_va == b
            if idx.sum():
                bands[b] = (int(idx.sum()), float(p_va[idx].mean()),
                            float(y_va[idx].mean()), float(p_va[idx].mean() - y_va[idx].mean()))
        results[name] = {
            "ece": _ece(p_va, y_va),
            "ll": log_loss(y_va, np.clip(p_va, 1e-6, 1 - 1e-6)),
            "br": brier_score_loss(y_va, p_va),
            "bands": bands, "coef": coef,
        }

    print("\n=== valid(OOS) 全体較正 ===")
    print(f"  {'モデル':<20}{'ECE':>8}{'logloss':>10}{'Brier':>9}")
    for name in models:
        rr = results[name]
        print(f"  {name:<20}{rr['ece']:>8.4f}{rr['ll']:>10.4f}{rr['br']:>9.4f}")

    print("\n=== valid(OOS) オッズ帯別乖離 (予測-実現, マイナス=過小=妙味) ===")
    print(f"  {'モデル':<20}" + "".join(f"{b:>11}" for b in BANDS))
    for name in models:
        rr = results[name]["bands"]
        cells = [f"{rr[b][3]:+.3f}" if b in rr else "-" for b in BANDS]
        print(f"  {name:<20}" + "".join(f"{c:>11}" for c in cells))
    n29 = results["C raw+odds ★"]["bands"].get("<2.9")
    print(f"  (<2.9 n={n29[0] if n29 else 0}, 各帯 実現複勝率: " +
          ", ".join(f"{b}={results['baseline raw(無補正)']['bands'][b][2]:.3f}"
                    for b in BANDS if b in results['baseline raw(無補正)']['bands']) + ")")

    print("\n=== 係数 (logit空間) ===")
    for name in models:
        if results[name]["coef"]:
            coef, ic = results[name]["coef"]
            print(f"  {name}: intercept={ic:+.3f}  "
                  + "  ".join(f"{k}={v:+.3f}" for k, v in coef.items()))

    print("\n=== 結論 (success criteria: <2.9乖離 |<0.10|) ===")
    c = results["C raw+odds ★"]
    b = results["B odds単独"]
    c29 = c["bands"].get("<2.9")
    if c29:
        print(f"  C(raw+odds) <2.9乖離 {c29[3]:+.3f} → {'✅達成' if abs(c29[3]) < 0.10 else '❌未達'}")
    print(f"  raw寄与(妙味): C logloss {c['ll']:.4f} vs B(odds単独) {b['ll']:.4f} → "
          f"{'あり(rawがoddsを超える情報を持つ)' if c['ll'] < b['ll'] - 5e-4 else '小さい(複勝はほぼoddsで決まる)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

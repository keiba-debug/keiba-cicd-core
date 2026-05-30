#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W/P/ADR 強さ重み backtest (Session 140 宿題⑤ / bettype-selection-roadmap)

bettype_efficiency.compute_strengths の composite =
    (wW·z(pred_proba_w_cal) + wP·z(pred_proba_p) + wA·z(ar_deviation)) / (wW+wP+wA)
の重み (DEFAULT_WEIGHTS=(1,1,1)) が、 軸◎ (= composite 最上位) 選定の品質という観点で
最適かを backtest_cache (本番予測+結果の結合) で検証する。

★目的: 「等重み (1,1,1) からの逸脱は ROI で正当化する」 (ふくだ方針)。
  逸脱が walk-forward (時系列分割) で頑健に勝てなければ等重み維持が正しい。

★composite は重み和で正規化されるためスケール不変 ((2,1,1)==(1,0.5,0.5))。
  z-score は重み非依存なので race ごとに 1 回だけ算出し、 重みスイープは composite の
  再計算のみ (高速)。 軸(1,1,1) は compute_strengths と完全一致を別途検証済。

★評価指標 (軸◎の質の代理。 実運用は軸◎+ハーヴィルEV選択だが、 まず軸選定品質を測る):
  win_rate  : 軸が1着になった率
  top3_rate : 軸が3着内に入った率
  win_roi   : 軸単勝を毎レース1点フラット買いした回収率 Σ(win時odds)/n
  place_roi : 軸複勝を毎レース1点フラット買いした回収率 Σ(top3時place_odds_min)/n
  (W は backtest_cache に raw が無いため win_ev/odds で復元。 P は pred_proba_p_raw)

CLI:
    python -m ml.analyze.backtest_strength_weights                 # 全期間 + walk-forward
    python -m ml.analyze.backtest_strength_weights --metric place_roi --split-date 2026-01-01
    python -m ml.analyze.backtest_strength_weights --cache-suffix foo --top 10
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

# スイープする重みグリッド (各 0=そのシグナルを使わない)。 (0,0,0) は除外。
DEFAULT_GRID = (0.0, 0.5, 1.0, 2.0, 3.0)
BASELINE: Tuple[float, float, float] = (1.0, 1.0, 1.0)
METRICS = ("top3_rate", "win_rate", "win_roi", "place_roi")
DEFAULT_METRIC = "top3_rate"   # 軸の強さ判定品質を最も安定して測る (ROI はノイズ大)


# ---------------------------------------------------------------------------
# データ整形 (race ごとに z-score を 1 回だけ算出)
# ---------------------------------------------------------------------------

@dataclass
class RaceZ:
    """1 レースの重み非依存な前計算結果。"""
    date: str                       # YYYYMMDD
    umabans: List[int]
    zw: List[Optional[float]]
    zp: List[Optional[float]]
    za: List[Optional[float]]
    w_for_tiebreak: List[float]     # win_prob 代理 (W)。 compute_strengths のタイブレーク再現
    is_win: List[bool]
    is_top3: List[bool]
    odds: List[float]
    place_odds: List[Optional[float]]


def _W(e: dict) -> Optional[float]:
    """pred_proba_w_cal を win_ev/odds で復元 (cache に raw が無いため)。"""
    o = e.get("odds") or 0
    we = e.get("win_ev")
    if o > 0 and we is not None:
        return we / o
    return None


def _zscores(vals: List[Optional[float]]) -> List[Optional[float]]:
    pres = [v for v in vals if v is not None]
    if not pres:
        return [None] * len(vals)
    m = sum(pres) / len(pres)
    sd = (sum((v - m) ** 2 for v in pres) / len(pres)) ** 0.5
    if sd <= 1e-12:
        return [0.0 if v is not None else None for v in vals]
    return [((v - m) / sd if v is not None else None) for v in vals]


def prepare_races(races: List[dict]) -> List[RaceZ]:
    """各 race を RaceZ に変換。 結果不明 or 有効馬<3 はスキップ。"""
    out: List[RaceZ] = []
    for r in races:
        rid = str(r.get("race_id") or "")
        date = rid[:8] if len(rid) >= 8 else ""
        ents = [e for e in r.get("entries", []) if e.get("umaban") is not None]
        # 結果があるレースのみ (1着が居る = 確定)
        if not any((e.get("finish_position") in (1, "1")) for e in ents):
            continue
        rows = []
        for e in ents:
            w = _W(e)
            fp = e.get("finish_position")
            try:
                fp = int(fp)
            except (TypeError, ValueError):
                fp = 99
            rows.append({
                "umaban": int(e["umaban"]),
                "W": w,
                "P": e.get("pred_proba_p_raw"),
                "A": e.get("ar_deviation"),
                "odds": float(e.get("odds") or 0.0),
                "place_odds": e.get("place_odds_min"),
                "is_win": fp == 1,
                "is_top3": 1 <= fp <= 3,
            })
        if len(rows) < 3:
            continue
        zw = _zscores([r_["W"] for r_ in rows])
        zp = _zscores([r_["P"] for r_ in rows])
        za = _zscores([r_["A"] for r_ in rows])
        out.append(RaceZ(
            date=date,
            umabans=[r_["umaban"] for r_ in rows],
            zw=zw, zp=zp, za=za,
            w_for_tiebreak=[(r_["W"] or 0.0) for r_ in rows],
            is_win=[r_["is_win"] for r_ in rows],
            is_top3=[r_["is_top3"] for r_ in rows],
            odds=[r_["odds"] for r_ in rows],
            place_odds=[r_["place_odds"] for r_ in rows],
        ))
    return out


# ---------------------------------------------------------------------------
# 軸選定 + 評価
# ---------------------------------------------------------------------------

def _axis_index(rz: RaceZ, weights: Tuple[float, float, float]) -> int:
    """compute_strengths と同じ規則で軸 (composite 最上位) の index を返す。
    タイブレーク: (composite, win_prob代理W, -umaban) 降順。"""
    wW, wP, wA = weights
    best_i = 0
    best_key = None
    for i in range(len(rz.umabans)):
        parts = []
        if rz.zw[i] is not None:
            parts.append((wW, rz.zw[i]))
        if rz.zp[i] is not None:
            parts.append((wP, rz.zp[i]))
        if rz.za[i] is not None:
            parts.append((wA, rz.za[i]))
        wsum = sum(w for w, _ in parts)
        comp = (sum(w * z for w, z in parts) / wsum) if wsum > 0 else 0.0
        key = (round(comp, 4), rz.w_for_tiebreak[i], -rz.umabans[i])
        if best_key is None or key > best_key:
            best_key = key
            best_i = i
    return best_i


@dataclass
class WeightResult:
    weights: Tuple[float, float, float]
    n: int
    win_rate: float
    top3_rate: float
    win_roi: float
    place_roi: float
    n_place_betable: int       # place_odds_min が取れた軸の数 (place_roi の母数)


def evaluate(races: List[RaceZ], weights: Tuple[float, float, float]) -> WeightResult:
    n = len(races)
    wins = top3s = 0
    win_ret = 0.0
    place_ret = 0.0
    place_n = 0
    for rz in races:
        i = _axis_index(rz, weights)
        if rz.is_win[i]:
            wins += 1
            win_ret += rz.odds[i]
        if rz.is_top3[i]:
            top3s += 1
        # place ROI は place_odds_min が取れた軸のみ母数に入れる
        po = rz.place_odds[i]
        if po is not None and po > 0:
            place_n += 1
            if rz.is_top3[i]:
                place_ret += po
    return WeightResult(
        weights=weights, n=n,
        win_rate=wins / n if n else 0.0,
        top3_rate=top3s / n if n else 0.0,
        win_roi=win_ret / n if n else 0.0,
        place_roi=place_ret / place_n if place_n else 0.0,
        n_place_betable=place_n,
    )


def weight_grid(grid: Tuple[float, ...]) -> List[Tuple[float, float, float]]:
    combos = [w for w in product(grid, repeat=3) if sum(w) > 0]
    if BASELINE not in combos:
        combos.append(BASELINE)
    return combos


def metric_of(r: WeightResult, metric: str) -> float:
    return getattr(r, metric)


# ---------------------------------------------------------------------------
# レポート
# ---------------------------------------------------------------------------

def _fmt(r: WeightResult) -> str:
    w = "/".join(f"{x:g}" for x in r.weights)
    return (f"  W:P:A={w:<10} n={r.n:>4}  win={r.win_rate*100:5.1f}%  "
            f"top3={r.top3_rate*100:5.1f}%  winROI={r.win_roi*100:6.1f}%  "
            f"placeROI={r.place_roi*100:6.1f}%")


def run(races: List[RaceZ], *, grid: Tuple[float, ...], metric: str,
        split_date: Optional[str], top: int) -> None:
    combos = weight_grid(grid)
    print(f"\n=== 全期間 ({len(races)} races, {len(combos)} weight combos) ===")
    base_all = evaluate(races, BASELINE)
    print("baseline (1,1,1):")
    print(_fmt(base_all))

    all_res = sorted((evaluate(races, w) for w in combos),
                     key=lambda r: metric_of(r, metric), reverse=True)
    print(f"\n[全期間] {metric} 上位 {top}:")
    for r in all_res[:top]:
        flag = "  <- baseline" if r.weights == BASELINE else ""
        print(_fmt(r) + flag)
    base_rank = 1 + sum(1 for r in all_res if metric_of(r, metric) > metric_of(base_all, metric))
    print(f"  baseline (1,1,1) の {metric} 順位: {base_rank}/{len(all_res)}")

    # --- walk-forward ---
    if split_date:
        train = [rz for rz in races if rz.date < split_date]
        valid = [rz for rz in races if rz.date >= split_date]
        if not train or not valid:
            print(f"\n[walk-forward] split={split_date} で train/valid のどちらかが空 → skip")
            return
        print(f"\n=== walk-forward (train < {split_date} <= valid) ===")
        print(f"  train={len(train)} races / valid={len(valid)} races")
        # train で metric 最適な重みを選ぶ
        train_res = sorted((evaluate(train, w) for w in combos),
                           key=lambda r: metric_of(r, metric), reverse=True)
        best_w = train_res[0].weights
        print(f"  train 最適重み ({metric}): {best_w}")
        # valid で best_w vs baseline を比較
        v_best = evaluate(valid, best_w)
        v_base = evaluate(valid, BASELINE)
        print("  [valid] train最適重み:")
        print(_fmt(v_best))
        print("  [valid] baseline (1,1,1):")
        print(_fmt(v_base))
        delta = metric_of(v_best, metric) - metric_of(v_base, metric)
        # 採用判断の閾値 (pt)。 rate は小さく動くのでノイズ帯を厳しめに取る。
        noise = {"top3_rate": 1.0, "win_rate": 1.0, "win_roi": 5.0, "place_roi": 3.0}
        thr = noise.get(metric, 1.0) / 100.0
        if delta <= 0:
            verdict = "逸脱は valid で勝てない → 等重み (1,1,1) 維持が正当"
        elif delta < thr:
            verdict = f"差分 < ノイズ帯({thr*100:.0f}pt) → 有意でない、 等重み維持が無難"
        else:
            verdict = "ノイズ帯を超えて勝ち → 逸脱に意味あり (ただし下記注意)"
        print(f"  → valid {metric} 差分 (最適-baseline) = {delta*100:+.2f}pt … {verdict}")
        if metric == "win_roi":
            print("    ※ win_roi は単勝フラット買いの高分散指標。 magnitude は割引いて読むこと。")
        print("    ※ 本指標は『軸◎をフラット買いした場合』の代理。 本番は軸◎+ハーヴィルEV選択 "
              "なので、 重みを変える前に full-selection ROI で再検証すること。")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-suffix", default=None, help="backtest_cache_{suffix}.json")
    p.add_argument("--cache-path", default=None, help="明示 cache パス")
    p.add_argument("--metric", default=DEFAULT_METRIC, choices=METRICS)
    p.add_argument("--split-date", default="2026-01-01",
                   help="walk-forward の境界 (YYYY-MM-DD)。 内部は YYYYMMDD で比較")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--grid", default=None,
                   help="重みグリッド (カンマ区切り, 例 0,1,2)。 既定 0,0.5,1,2,3")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    grid = (tuple(float(x) for x in args.grid.split(",")) if args.grid
            else DEFAULT_GRID)
    cache_path = Path(args.cache_path) if args.cache_path else None
    races_raw = load_backtest_cache(path=cache_path, suffix=args.cache_suffix)
    races = prepare_races(races_raw)
    split = args.split_date.replace("-", "") if args.split_date else None
    run(races, grid=grid, metric=args.metric, split_date=split, top=args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())

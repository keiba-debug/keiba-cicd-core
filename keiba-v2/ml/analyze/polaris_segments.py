#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""polaris 2.0 条件別性能分析 (Session 122 Phase 2)

backtest_cache.json + race_*.json (metadata) を join し、
複数のセグメント軸ごとに ROI / Brier / Calibration / Sharpe / 期間A vs B を集計する。

Usage:
    python -m ml.analyze.polaris_segments
    python -m ml.analyze.polaris_segments --run-id v2.0_2026-05
    python -m ml.analyze.polaris_segments --top-n-jockey 50 --bootstrap 1000

Output:
    data3/analysis/polaris_segments/{run_id}/
        summary.md           — 全軸サマリ (人間用)
        segments.json        — 全集計データ (Web UI/再分析用)
        period_compare.json  — 期間A vs 期間B 差分
        meta.json            — 実行メタ (timestamp, args, n_races)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import config
from ml.utils.backtest_cache import load_backtest_cache, flatten_to_df
from ml.utils.filters import exclude_obstacle, is_obstacle, sample_size_marker, MIN_SAMPLE_DEFAULT
from ml.utils.race_io import enrich_with_race_meta
from ml.utils.roi import (
    Bet, calc_roi, calc_brier_score, calc_ece, calibration_curve,
    sharpe_ratio, max_drawdown, losing_streaks,
)
from ml.utils.segments import (
    bin_odds, bin_runners, bin_distance, bin_month, race_id_to_date,
    ODDS_LABELS, RUNNER_LABELS, DISTANCE_LABELS,
)


# ===========================================================================
# Data prep
# ===========================================================================

def load_and_enrich(verbose: bool = True) -> pd.DataFrame:
    """backtest_cache + race meta を join した DataFrame を返す"""
    t0 = time.time()
    races = load_backtest_cache(quiet=not verbose)
    if verbose:
        print(f"[1/3] backtest_cache loaded: {len(races):,} races ({time.time()-t0:.1f}s)")

    # 障害除外
    races = exclude_obstacle(races)
    if verbose:
        print(f"[2/3] obstacle excluded → {len(races):,} flat races")

    t1 = time.time()
    df = flatten_to_df(races)
    if verbose:
        print(f"      flatten_to_df → {len(df):,} entries ({time.time()-t1:.1f}s)")

    t2 = time.time()
    df = enrich_with_race_meta(df, verbose=False)
    if verbose:
        print(f"[3/3] enrich_with_race_meta done ({time.time()-t2:.1f}s)")

    df = derive_extra_columns(df)
    if verbose:
        print(f"      derived columns added (month, distance_band, etc.)")

    return df


def derive_extra_columns(df: pd.DataFrame) -> pd.DataFrame:
    """月・距離帯・オッズ帯・頭数帯・top1 フラグなどの派生列を追加"""
    df = df.copy()
    # date は flatten_to_df で既に YYYY-MM-DD で入っている
    df["month"] = df["date"].astype(str).str[:7]
    # 既に odds_band は flatten_to_df で入っているが念のため再生成
    if "odds_band" not in df.columns:
        df["odds_band"] = bin_odds(df["odds"])
    df["runner_band"] = bin_runners(df["num_runners"])
    # distance は enrich 後にあれば
    if "distance" in df.columns:
        df["distance_band"] = bin_distance(df["distance"].fillna(0).astype(int))
    # Top1 フラグ (rank_p == 1 と rank_w == 1)
    df["is_top1_p"] = df["rank_p"] == 1
    df["is_top1_w"] = df["rank_w"] == 1
    return df


# ===========================================================================
# Segment computation
# ===========================================================================

def _build_bets(seg_df: pd.DataFrame, model: str) -> list[Bet]:
    """セグメント内の Top1 (model別) を 100円単勝買いとみなして Bet 化

    model: 'p' (rank_p==1) | 'w' (rank_w==1)
    """
    if model == "p":
        sub = seg_df[seg_df["is_top1_p"] & (seg_df["odds"] > 0)]
    elif model == "w":
        sub = seg_df[seg_df["is_top1_w"] & (seg_df["odds"] > 0)]
    else:
        raise ValueError(f"unknown model: {model}")
    bets: list[Bet] = []
    for _, row in sub.iterrows():
        odds = float(row["odds"]) if row["odds"] else 0.0
        is_win = bool(row["is_win"])
        bets.append(Bet(
            race_id=str(row["race_id"]),
            cost=100.0,
            payout=odds * 100.0 if is_win else 0.0,
            is_hit=is_win,
            odds=odds,
            bet_type="win",
        ))
    return bets


def compute_segment(seg_df: pd.DataFrame, model: str = "p", bootstrap_n: int = 0) -> dict:
    """単一セグメントの統計量を返す

    Returns:
        {
            "n_entries": int,           # 馬単位のサンプル数
            "n_races": int,             # ユニーク race 数
            "top1_bets": int,           # Top1 のベット件数
            "win_roi": dict,            # RoiResult.as_dict (Top1 単勝)
            "brier": float,             # rank_p==1 候補 pred_p の Brier (vs is_win)
            "ece": float,               # 同 ECE
            "calibration": list[dict],  # キャリブレーション曲線データ
            "marker": str,              # サンプル数警告
        }
    """
    n_entries = len(seg_df)
    n_races_segment = seg_df["race_id"].nunique() if n_entries else 0
    bets = _build_bets(seg_df, model=model)
    n_races_bet = len({b.race_id for b in bets})

    roi_result = calc_roi(bets, bootstrap_n=bootstrap_n)

    # Brier/ECE は Top1 限定だとサンプルが減るので、セグメント全体の pred_p で測る
    valid_p = seg_df[(seg_df["pred_p"] > 0) & (seg_df["pred_p"] < 1)]
    if len(valid_p) > 10:
        brier = calc_brier_score(valid_p["is_top3"].astype(int).values,
                                 valid_p["pred_p"].values)
        ece = calc_ece(valid_p["is_top3"].astype(int).values,
                       valid_p["pred_p"].values, n_bins=10)
        calib = calibration_curve(valid_p["is_top3"].astype(int).values,
                                  valid_p["pred_p"].values, n_bins=10)
    else:
        brier = None
        ece = None
        calib = []

    return {
        "n_entries": int(n_entries),
        "n_races_segment": int(n_races_segment),  # セグメント該当 entry がある race 数
        "n_races_bet": int(n_races_bet),          # Top1 ベットを引いた race 数
        "top1_bets": len(bets),
        "win_roi": roi_result.as_dict(),
        "brier": float(brier) if brier is not None else None,
        "ece": float(ece) if ece is not None else None,
        "calibration": calib,
        "marker": sample_size_marker(len(bets)),
    }


def compute_axis(
    df: pd.DataFrame,
    column: str,
    *,
    top_n: Optional[int] = None,
    label_order: Optional[Sequence[str]] = None,
    model: str = "p",
    bootstrap_n: int = 0,
) -> "OrderedDict[str, dict]":
    """1軸の全セグメント統計を返す

    Args:
        df: 全データ
        column: 軸列名 (categorical or pd.Categorical)
        top_n: 出現頻度 Top N のみ集計 (jockey/trainer用)
        label_order: 順序固定 (binsの label)
        model: 'p' or 'w'
        bootstrap_n: Bootstrap CI のサンプル数 (0で無効)

    Returns:
        OrderedDict[segment_label -> stats]
    """
    if column not in df.columns:
        return OrderedDict()

    valid = df[df[column].notna() & (df[column] != "")]
    if valid.empty:
        return OrderedDict()

    if top_n is not None:
        top_values = valid[column].value_counts().head(top_n).index.tolist()
        valid = valid[valid[column].isin(top_values)]

    if label_order is not None:
        labels = label_order
    elif hasattr(valid[column], "cat") and valid[column].cat.ordered:
        labels = list(valid[column].cat.categories)
    else:
        # 出現頻度順 (top_n の場合) または辞書順
        if top_n is not None:
            labels = top_values
        else:
            labels = sorted(valid[column].astype(str).unique())

    out: "OrderedDict[str, dict]" = OrderedDict()
    for lbl in labels:
        seg = valid[valid[column].astype(str) == str(lbl)]
        if seg.empty:
            continue
        out[str(lbl)] = compute_segment(seg, model=model, bootstrap_n=bootstrap_n)
    return out


# ===========================================================================
# Period A / B split (Mann-Whitney for ROI consistency)
# ===========================================================================

def split_by_period(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """date の中央値で前半 (A) / 後半 (B) に分割

    Returns: (df_A, df_B, split_date_str)
    """
    sorted_dates = df["date"].dropna().sort_values()
    if sorted_dates.empty:
        return df.iloc[:0], df.iloc[:0], ""
    mid = sorted_dates.iloc[len(sorted_dates) // 2]
    df_a = df[df["date"] < mid].copy()
    df_b = df[df["date"] >= mid].copy()
    return df_a, df_b, str(mid)


def compare_periods(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    column: str,
    *,
    top_n: Optional[int] = None,
    label_order: Optional[Sequence[str]] = None,
    model: str = "p",
) -> "OrderedDict[str, dict]":
    """期間 A vs B でセグメント別 ROI を比較

    Returns: {label: {"a": {n, roi, hit_rate}, "b": {...}, "delta_roi": float}}
    """
    out: "OrderedDict[str, dict]" = OrderedDict()
    axis_a = compute_axis(df_a, column, top_n=top_n, label_order=label_order, model=model)
    axis_b = compute_axis(df_b, column, top_n=top_n, label_order=label_order, model=model)
    all_labels = list(dict.fromkeys(list(axis_a.keys()) + list(axis_b.keys())))
    for lbl in all_labels:
        a = axis_a.get(lbl, {})
        b = axis_b.get(lbl, {})
        a_roi = (a.get("win_roi") or {}).get("roi", 0)
        b_roi = (b.get("win_roi") or {}).get("roi", 0)
        out[lbl] = {
            "a": {
                "n_bets": (a.get("win_roi") or {}).get("n", 0),
                "roi": a_roi,
                "hit_rate": (a.get("win_roi") or {}).get("hit_rate", 0),
            },
            "b": {
                "n_bets": (b.get("win_roi") or {}).get("n", 0),
                "roi": b_roi,
                "hit_rate": (b.get("win_roi") or {}).get("hit_rate", 0),
            },
            "delta_roi": round(b_roi - a_roi, 1),
        }
    return out


# ===========================================================================
# Sharpe (monthly ROI series)
# ===========================================================================

def monthly_roi_series(df: pd.DataFrame, *, model: str = "p") -> dict:
    """月次 ROI 系列 + Sharpe + MaxDD + 連敗"""
    months = sorted(df["month"].dropna().unique())
    roi_series: list[float] = []
    pnl_series: list[float] = []
    monthly_rows = []
    cum_pnl = 0.0
    for m in months:
        sub = df[df["month"] == m]
        bets = _build_bets(sub, model=model)
        r = calc_roi(bets)
        roi_series.append(r.roi)
        pnl_series.append(r.pnl)
        cum_pnl += r.pnl
        monthly_rows.append({
            "month": m, "n_bets": r.n, "roi": r.roi,
            "pnl": r.pnl, "cum_pnl": cum_pnl, "hits": r.hits,
        })
    sharpe = sharpe_ratio(roi_series, periods_per_year=12)
    dd_amt, dd_pct = max_drawdown(np.cumsum(pnl_series))
    # 連敗は時系列順 hit列で
    hits_chronological = []
    for m in months:
        sub = df[df["month"] == m]
        bets = _build_bets(sub, model=model)
        hits_chronological.extend([1 if b.is_hit else 0 for b in bets])
    streaks = losing_streaks(hits_chronological)
    return {
        "monthly": monthly_rows,
        "sharpe": round(sharpe, 2),
        "max_dd_amount": round(dd_amt, 0),
        "max_dd_pct": round(dd_pct, 1),
        "losing_streaks": streaks,
    }


# ===========================================================================
# Top-level orchestration
# ===========================================================================

# 軸定義: (axis_name, df_column, top_n, label_order, display_name, period_split_ok)
# period_split_ok=False の軸は ΔROI 計算をスキップ (split_date 境界で意味を成さないため)
AXIS_DEFS = [
    ("odds_band",   "odds_band",     None, ODDS_LABELS,     "オッズ帯",         True),
    ("runners",     "runner_band",   None, RUNNER_LABELS,   "頭数帯",           True),
    ("grade",       "grade",         None, None,            "グレード",         True),
    ("track_type",  "track_type",    None, None,            "馬場 (芝/ダ)",     True),
    ("distance",    "distance_band", None, DISTANCE_LABELS, "距離帯",           True),
    ("month",       "month",         None, None,            "月別",             False),  # split境界に整列
    ("venue",       "venue_code",    None, None,            "会場 (場コード)",  True),
    ("jockey",      "jockey_code",   30,   None,            "騎手 Top30",       True),
    ("trainer",     "trainer_code",  30,   None,            "調教師 Top30",     True),
]


def run_analysis(
    *,
    model: str = "p",
    bootstrap_n: int = 0,
    verbose: bool = True,
) -> dict:
    """全軸の分析を実行し結果 dict を返す"""
    df = load_and_enrich(verbose=verbose)
    df_a, df_b, split_date = split_by_period(df)

    if verbose:
        print(f"\n[Split] period A: {len(df_a):,} entries (date < {split_date})")
        print(f"        period B: {len(df_b):,} entries (date >= {split_date})")

    results: dict = {
        "model": model,
        "total_entries": int(len(df)),
        "total_races": int(df["race_id"].nunique()),
        "split_date": split_date,
        "axes": {},
        "period_compare": {},
    }

    if verbose:
        print(f"\n[Axes] computing {len(AXIS_DEFS)} segment axes...")
    for axis_name, col, top_n, label_order, _, period_ok in AXIS_DEFS:
        if col not in df.columns:
            if verbose:
                print(f"  - {axis_name}: column '{col}' missing, skip")
            continue
        ts = time.time()
        results["axes"][axis_name] = compute_axis(
            df, col, top_n=top_n, label_order=label_order,
            model=model, bootstrap_n=bootstrap_n,
        )
        if period_ok:
            results["period_compare"][axis_name] = compare_periods(
                df_a, df_b, col, top_n=top_n, label_order=label_order, model=model,
            )
        if verbose:
            n = len(results["axes"][axis_name])
            print(f"  - {axis_name}: {n} segments ({time.time()-ts:.1f}s)")

    # 月次 ROI 系列
    if verbose:
        print(f"\n[Sharpe] computing monthly ROI series...")
    results["monthly"] = monthly_roi_series(df, model=model)

    return results


# ===========================================================================
# Output: Markdown + JSON
# ===========================================================================

def _fmt_roi(roi: float) -> str:
    s = f"{roi:+.1f}%"
    if roi >= 110:
        return f"**{s}** 🟢"
    if roi >= 90:
        return s
    return f"{s} 🔴"


def render_markdown(results: dict, *, run_id: str) -> str:
    """summary.md レンダリング"""
    lines: list[str] = []
    monthly = results.get("monthly", {})
    lines.append(f"# polaris {results['model'].upper()} セグメント分析 — {run_id}\n")
    lines.append(f"- 対象: **{results['total_races']:,}** races / {results['total_entries']:,} entries")
    lines.append(f"- モデル: polaris 2.0 (rank_{results['model']}==1 を 100円単勝買い)")
    lines.append(f"- 期間分割: A < `{results['split_date']}` ≤ B")
    if monthly:
        lines.append(f"- Sharpe (月次): **{monthly['sharpe']}**")
        lines.append(f"- MaxDD: {monthly['max_dd_amount']:,.0f}円 ({monthly['max_dd_pct']}%)")
        ls = monthly["losing_streaks"]
        lines.append(f"- 最長連敗: {ls['max_streak']}連敗 (損失 {ls['max_streak_loss']:,.0f}円)")
    lines.append("")

    # 軸ごとのテーブル
    for axis_name, col, top_n, _, display_name, _ in AXIS_DEFS:
        if axis_name not in results["axes"]:
            continue
        axis_data = results["axes"][axis_name]
        period_data = results["period_compare"].get(axis_name, {})
        if not axis_data:
            continue
        lines.append(f"## {display_name} ({axis_name})")
        lines.append("")
        lines.append("| セグメント | races | bets | 勝率 | 単勝ROI | ΔROI (B-A) | Brier | ECE | 警告 |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for label, stats in axis_data.items():
            roi = stats["win_roi"]
            delta = period_data.get(label, {}).get("delta_roi", "—")
            delta_str = f"{delta:+.1f}" if isinstance(delta, (int, float)) else delta
            brier_str = f"{stats['brier']:.4f}" if stats["brier"] is not None else "—"
            ece_str = f"{stats['ece']:.4f}" if stats["ece"] is not None else "—"
            lines.append(
                f"| {label} | {stats['n_races_bet']:,} | {roi['n']:,} | "
                f"{roi['hit_rate']:.1f}% | {_fmt_roi(roi['roi'])} | "
                f"{delta_str} | {brier_str} | {ece_str} | {stats['marker']} |"
            )
        lines.append("")

    # 月別ROI推移
    if monthly.get("monthly"):
        lines.append("## 月別 ROI 推移")
        lines.append("")
        lines.append("| 月 | n_bets | 勝率風 | ROI | P&L | 累積P&L |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for m in monthly["monthly"]:
            hit_rate = (m["hits"] / m["n_bets"] * 100) if m["n_bets"] else 0
            lines.append(
                f"| {m['month']} | {m['n_bets']:,} | {hit_rate:.1f}% | "
                f"{_fmt_roi(m['roi'])} | {m['pnl']:+,.0f} | {m['cum_pnl']:+,.0f} |"
            )
        lines.append("")

    lines.append(f"\n---")
    lines.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_")
    return "\n".join(lines)


def write_outputs(results: dict, *, output_dir: Path, run_id: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    md = render_markdown(results, run_id=run_id)
    (output_dir / "summary.md").write_text(md, encoding="utf-8")

    # JSON: 全集計データ
    segments_json = {
        "model": results["model"],
        "total_entries": results["total_entries"],
        "total_races": results["total_races"],
        "split_date": results["split_date"],
        "axes": results["axes"],
        "monthly": results.get("monthly"),
    }
    (output_dir / "segments.json").write_text(
        json.dumps(segments_json, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    (output_dir / "period_compare.json").write_text(
        json.dumps(results["period_compare"], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    (output_dir / "meta.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "model": results["model"],
            "total_races": results["total_races"],
            "total_entries": results["total_entries"],
            "split_date": results["split_date"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ===========================================================================
# CLI
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--run-id", default=None,
                   help="出力ディレクトリ名 (default: YYYYMMDD_HHMMSS)")
    p.add_argument("--model", choices=("p", "w"), default="p",
                   help="Top1 選定モデル (p=rank_p / w=rank_w, default p)")
    p.add_argument("--bootstrap", type=int, default=0,
                   help="Bootstrap CI のサンプル数 (default 0=無効; 重い)")
    p.add_argument("--output-root", default=None,
                   help=f"出力ルート (default: {config.data_root()}/analysis/polaris_segments)")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    verbose = not args.quiet

    if verbose:
        print(f"=== polaris_segments run_id={run_id} model={args.model} ===\n")

    t0 = time.time()
    results = run_analysis(
        model=args.model,
        bootstrap_n=args.bootstrap,
        verbose=verbose,
    )

    out_root = Path(args.output_root) if args.output_root \
        else config.data_root() / "analysis" / "polaris_segments"
    output_dir = out_root / run_id
    write_outputs(results, output_dir=output_dir, run_id=run_id)

    if verbose:
        print(f"\n[Done] {time.time()-t0:.1f}s total")
        print(f"  summary.md       → {output_dir / 'summary.md'}")
        print(f"  segments.json    → {output_dir / 'segments.json'}")
        print(f"  period_compare   → {output_dir / 'period_compare.json'}")
        print(f"  meta.json        → {output_dir / 'meta.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

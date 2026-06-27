#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gap5単勝エッジの検証結果を JSON 出力 (Session 174 / web /analysis/edge-validation 用)

市場較正マップ (docs/market_calibration_edge_map.md) で発見した
**gap≥5 単勝 × クラス局在エッジ** の検証結果を **SoT(単一の真実)** として JSON 化する。
web は読むだけ (bet_template_lab / formation で確立した「Python artifact → web 表示」パターン)。

エッジ定義:
  base    = pred_rank_w<=3 ∧ gap>=5   (gap = odds_rank - pred_rank_w = 市場が見限った度合い)
  edge    = base ∧ クラス∈{未勝利, 条件, 重賞}   (新馬/OP は除外: §市場非効率だがモデルも盲目)
  core    = edge ∧ odds∈[15,30) ∧ win_ev>=1.0   (精密化後の採用バケット)

数値は experiment.py --dump-test が吐いた df_test (13ヶ月OOS) を入力に、
単勝確定オッズ精算 (race結果JSON / 事前オッズと一致 = leak-free) で算出。

出力 (data3/ml/edge_validation.json):
  - edge_summary    : core の n/wins/ROI/CI・k(市場過小評価倍率)・実勝率vs市場implied・zero月・maxDD
  - class_map       : クラス別 gap≥5単勝 ROI (エッジ地図)
  - levers          : 精密化スイープ (odds帯/gap閾値/pred_rank/win_ev の単独の効き)
  - sizing_sim      : 固定額配分(0.5〜5%/bet)の bankroll 損益・maxDD (哲学§5準拠=オッズ非依存)
  - kelly_ref       : ケリー理論値 (固定額水準の上限サニティ参考のみ・§5で配分には不採用)
  - monthly         : core の月別 fire/wins/roi/pnl/cum_pnl
  - thickness_tiers : 評価ベースの厚み候補 (信号強度別 ROI・§5がOKする軸)

Usage:
    python -m ml.export_edge_validation
    python -m ml.export_edge_validation --pkl C:/tmp/df_test_danger.pkl
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config  # noqa: E402

# --- エッジ定義パラメータ (docs/market_calibration_edge_map.md S173/S174) ---
PRED_RANK_MAX = 3       # モデル上位3
GAP_MIN = 5             # odds_rank >= pred_rank_w + 5
ODDS_LO, ODDS_HI = 15.0, 30.0   # 市場が過剰に見限る帯 (スイートスポット)
WIN_EV_MIN = 1.0        # モデル単勝EV>1
EDGE_CLASSES = ["miSHOURI", "jouken", "juushou"]
SIZING_LEVELS = [0.005, 0.01, 0.02, 0.03, 0.05]
NBOOT = 1000
SEED = 42

CLASS_LABELS = {
    "shinba": "新馬", "miSHOURI": "未勝利", "jouken": "条件(1-3勝)",
    "OP/L": "OP/L", "juushou": "重賞", "other": "その他",
}
CLASS_ORDER = ["shinba", "miSHOURI", "jouken", "OP/L", "juushou"]


def bucket(g: str) -> str:
    g = str(g)
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


def load_df(pkl_path: str) -> pd.DataFrame:
    df = pd.read_pickle(pkl_path)
    df = df[df["finish_position"].notna() & (df["finish_position"] > 0)].copy()
    df["ym"] = df["race_id"].astype(str).str[:6]
    df["cls"] = df["grade"].apply(bucket)
    df["gap"] = df["odds_rank"] - df["pred_rank_w"]
    df["win_ret"] = df["is_win"] * df["odds"]
    return df


def roi_ci(s: pd.DataFrame, rng, col: str = "win_ret", nboot: int = NBOOT):
    """race単位リサンプリングのブートストラップ ROI と 95%CI。"""
    if len(s) == 0:
        return 0.0, 0.0, 0.0
    grp = [g[col].values for _, g in s.groupby("race_id")]
    boot = [np.concatenate([grp[i] for i in rng.integers(0, len(grp), len(grp))]).mean() * 100
            for _ in range(nboot)]
    return float(s[col].mean() * 100), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def cell_stats(s: pd.DataFrame) -> dict:
    """サブセットの共通サマリ (全て素のpython型)。"""
    n = int(len(s))
    wins = int(s["is_win"].sum()) if n else 0
    roi = round(float(s["win_ret"].mean()) * 100, 1) if n else 0.0
    mwin = s.groupby("ym")["is_win"].sum() if n else pd.Series(dtype=float)
    zero = int((mwin == 0).sum()) if n else 0
    nm = int(s["ym"].nunique()) if n else 0
    maxw = round(float(s.loc[s["is_win"] == 1, "odds"].max()), 1) if wins else 0.0
    hit = round(wins / n * 100, 1) if n else 0.0
    return dict(n=n, wins=wins, hit_rate=hit, roi=roi,
                zero_months=zero, n_months=nm, max_win_odds=maxw)


def sim_fixed(core: pd.DataFrame, stake_pct: float) -> dict:
    """固定額(絶対額)配分の bankroll シミュ。オッズでもbankrollでも動かさない(哲学§5/§3)。"""
    unit = stake_pct
    bank = 1.0
    peak = 1.0
    maxdd = 0.0
    lo = 1.0
    for _, r in core.iterrows():
        bank += (unit * (r["odds"] - 1)) if r["is_win"] == 1 else -unit
        peak = max(peak, bank)
        maxdd = min(maxdd, bank - peak)
        lo = min(lo, bank)
    return dict(
        level_pct=round(stake_pct * 100, 1),
        final_bank=round(bank, 3),
        net_pnl_pct=round((bank - 1) * 100, 0),
        max_dd_pct=round(maxdd * 100, 0),
        min_bank=round(lo, 3),
    )


def build_result(df: pd.DataFrame, pkl_path: str) -> dict:
    rng = np.random.default_rng(SEED)

    base = df[(df["pred_rank_w"] <= PRED_RANK_MAX) & (df["gap"] >= GAP_MIN)].copy()
    edge = base[base["cls"].isin(EDGE_CLASSES)].copy()
    # ★S175 committed = broad★: odds帯[15,30)で絞るのは best-of-search の後知恵=過学習
    #   (audit_gap_edge.py で P(null max≥218%)=0.0625 ＝ノイズと区別不能と判明・docs §8 で棄却)。
    #   ★committed broad = base ∩ 3クラス (= edge・audit_gap_edge.py:273 と同一)★ = ROI~130%/n413 /
    #   P(null≥130%)=0.026。 odds帯も win_ev ゲートも付けない (headline を doc §8 と一致させる)。
    #   ※ win_ev≥1.0 は live/shadow 選定の「モデルEV>1」サニティゲート (gap_tansho_shadow) で、
    #     headline 検証(=committed broad)には掛けない (audit と同条件)。
    core = edge.copy()
    core = core.sort_values("race_id").reset_index(drop=True)

    # --- class_map (gap≥5単勝 のクラス別 = エッジ地図) ---
    class_map = []
    for c in CLASS_ORDER:
        s = base[base["cls"] == c]
        if len(s) == 0:
            continue
        roi, lo, hi = roi_ci(s, rng)
        st = cell_stats(s)
        class_map.append(dict(
            cls=c, label=CLASS_LABELS[c], n=st["n"], wins=st["wins"],
            roi=round(roi, 1), ci_low=round(lo, 0), ci_high=round(hi, 0),
            is_edge=(c in EDGE_CLASSES),
        ))

    # --- levers (精密化スイープ・全て edge 3クラス上) ---
    levers: dict = {"odds_band": [], "gap": [], "pred_rank_w": [], "win_ev": []}
    for lo_b, hi_b in [(0, 7), (7, 15), (15, 30), (30, 60), (60, 99999)]:
        s = edge[(edge["odds"] >= lo_b) & (edge["odds"] < hi_b)]
        st = cell_stats(s)
        label = f"{lo_b}-{hi_b}" if hi_b < 99999 else f"{lo_b}+"
        # ★broad committed では特定の odds帯を core にしない★ (帯絞り=過学習で棄却・S175)。
        #   この sweep は「帯で絞ると ROI は上がるが分散も悪化＝過学習」を可視化する分析用に残す。
        levers["odds_band"].append(dict(label=label, n=st["n"], wins=st["wins"],
                                        roi=st["roi"], zero_months=st["zero_months"],
                                        is_core=False))
    for kgap in [5, 6, 7, 8, 10]:
        s = edge[edge["gap"] >= kgap]
        st = cell_stats(s)
        levers["gap"].append(dict(label=f">={kgap}", n=st["n"], wins=st["wins"],
                                  roi=st["roi"], zero_months=st["zero_months"]))
    for kr in [1, 2, 3]:
        s = edge[edge["pred_rank_w"] <= kr]
        st = cell_stats(s)
        levers["pred_rank_w"].append(dict(label=f"<={kr}", n=st["n"], wins=st["wins"],
                                          roi=st["roi"], zero_months=st["zero_months"]))
    for kev in [0.6, 0.8, 1.0, 1.2]:
        s = edge[edge["win_ev"] >= kev]
        st = cell_stats(s)
        levers["win_ev"].append(dict(label=f">={kev}", n=st["n"], wins=st["wins"],
                                     roi=st["roi"], zero_months=st["zero_months"],
                                     is_core=(abs(kev - WIN_EV_MIN) < 1e-9)))

    # --- edge_summary (core バケット) ---
    imp = 1.0 / core["odds"]
    p_act = float(core["is_win"].mean())
    imp_mean = float(imp.mean())
    k = p_act / imp_mean if imp_mean else 0.0
    roi_c, lo_c, hi_c = roi_ci(core, rng)
    sizing_1pct = sim_fixed(core, 0.01)
    edge_summary = dict(
        n=int(len(core)),
        wins=int(core["is_win"].sum()),
        hit_rate=round(p_act * 100, 1),
        roi=round(roi_c, 1),
        ci_low=round(lo_c, 0),
        ci_high=round(hi_c, 0),
        k_underrate=round(k, 2),
        actual_winrate=round(p_act * 100, 2),
        market_implied=round(imp_mean * 100, 2),
        zero_months=int((core.groupby("ym")["is_win"].sum() == 0).sum()),
        n_months=int(core["ym"].nunique()),
        max_dd_pct_at_1pct=sizing_1pct["max_dd_pct"],
    )

    # --- sizing_sim (固定額配分) ---
    sizing_sim = [sim_fixed(core, sp) for sp in SIZING_LEVELS]

    # --- kelly_ref (上限サニティ参考のみ・配分には§5で不採用) ---
    cb = core.copy()
    cb_imp = 1.0 / cb["odds"]
    cb["p_est"] = cb_imp * k
    cb["b"] = cb["odds"] - 1.0
    cb["f_full"] = (cb["p_est"] - (1 - cb["p_est"]) / cb["b"]).clip(lower=0)
    f_mean = float(cb["f_full"].mean())
    kelly_ref = dict(
        full_mean_pct=round(f_mean * 100, 1),
        full_median_pct=round(float(cb["f_full"].median()) * 100, 1),
        full_max_pct=round(float(cb["f_full"].max()) * 100, 1),
        quarter_pct=round(f_mean * 25, 1),
        half_pct=round(f_mean * 50, 1),
    )

    # --- monthly (core) ---
    mg = core.groupby("ym").agg(n=("is_win", "size"), wins=("is_win", "sum"),
                                ret=("win_ret", "sum"))
    monthly = []
    cum = 0.0
    for ym, r in mg.iterrows():
        n_m = int(r["n"])
        roi_m = float(r["ret"]) / n_m * 100 if n_m else 0.0
        pnl = float(r["ret"]) - n_m   # flat 1u stake
        cum += pnl
        monthly.append(dict(month=str(ym), n=n_m, wins=int(r["wins"]),
                            roi=round(roi_m, 1), pnl=round(pnl, 1), cum_pnl=round(cum, 1)))

    # --- thickness_tiers (評価ベース厚み・§5 OK) ---
    def tier(mask, label):
        st = cell_stats(core[mask])
        return dict(label=label, n=st["n"], wins=st["wins"], roi=st["roi"])

    thickness_tiers = [
        tier(core["cls"] == "juushou", "重賞"),
        tier(core["cls"] == "miSHOURI", "未勝利"),
        tier(core["cls"] == "jouken", "条件(1-3勝)"),
        tier(core["gap"] >= 7, "gap≥7 (強disdain)"),
        tier(core["pred_rank_w"] == 1, "pred_rank_w=1 (モデル断然)"),
        tier(core["win_ev"] >= 2.0, "win_ev≥2.0 (モデル強気)"),
    ]

    # --- picks (採用バケット core の明細・月6〜20件/13ヶ月計156件) ---
    picks = []
    for _, r in core.iterrows():
        odds_v = float(r["odds"])
        win_flag = int(r["is_win"])
        picks.append(dict(
            race_id=str(r["race_id"]),
            umaban=(int(r["umaban"]) if pd.notna(r["umaban"]) else None),
            horse_name=str(r["horse_name"]),
            cls=CLASS_LABELS.get(r["cls"], r["cls"]),
            odds=round(odds_v, 1),
            gap=int(r["gap"]),
            win_ev=round(float(r["win_ev"]), 2),
            pred_rank_w=int(r["pred_rank_w"]),
            is_win=win_flag,
            payout=(int(round(odds_v * 100)) if win_flag else 0),
            finish_position=(int(r["finish_position"]) if pd.notna(r["finish_position"]) else None),
            # 複勝配当=事前複勝最低オッズ×100 (3着以内のみ・最低保証額・確定払戻はこれ以上)
            place_pay=(int(round(float(r["place_odds_low"]) * 100))
                       if (pd.notna(r["finish_position"]) and int(r["finish_position"]) <= 3
                           and pd.notna(r["place_odds_low"])) else 0),
        ))

    months_sorted = sorted(core["ym"].unique())
    edge_def = dict(
        label="gap≥5 単勝 × クラス局在 (broad/全オッズ)",
        base_filter=f"pred_rank_w<={PRED_RANK_MAX} ∧ gap>={GAP_MIN} (gap=odds_rank-pred_rank_w)",
        edge_classes=["未勝利", "条件(1-3勝)", "重賞"],
        excluded_classes=["新馬", "OP/L"],
        refined_filter="全オッズ・3クラス (committed broad = base∩クラス・★odds帯フィルタは S175 で過学習棄却★)",
    )

    return {
        "created_at": datetime.now().isoformat(),
        "session": "S178 (broad committed・S175訂正反映)",
        "data_source": (
            "experiment.py --dump-test (df_test 13ヶ月OOS) / 単勝確定オッズ精算"
            "=事前オッズと一致(leak-free) / docs/market_calibration_edge_map.md"
        ),
        "pkl_source": str(pkl_path),
        "period_start": months_sorted[0] if months_sorted else "",
        "period_end": months_sorted[-1] if months_sorted else "",
        "n_months": int(len(months_sorted)),
        "edge_def": edge_def,
        "edge_summary": edge_summary,
        "class_map": class_map,
        "levers": levers,
        "sizing_sim": sizing_sim,
        "kelly_ref": kelly_ref,
        "monthly": monthly,
        "thickness_tiers": thickness_tiers,
        "picks": picks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="gap5単勝エッジ検証 → JSON出力")
    ap.add_argument("--pkl", default=r"C:/tmp/df_test_danger.pkl",
                    help="experiment.py --dump-test の出力 pickle")
    args = ap.parse_args()

    if not Path(args.pkl).exists():
        print(f"ERROR: pkl not found: {args.pkl}\n"
              f"  generate it via: python -m ml.experiment ... --dump-test {args.pkl}")
        return 1

    df = load_df(args.pkl)
    result = build_result(df, args.pkl)

    out_path = config.ml_dir() / "edge_validation.json"
    out_json = json.dumps(result, ensure_ascii=False, indent=2)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"Saved: {out_path}  ({len(out_json) // 1024} KB)")

    es = result["edge_summary"]
    print(f"  core: n={es['n']} wins={es['wins']} ROI={es['roi']}% "
          f"CI[{es['ci_low']:.0f}-{es['ci_high']:.0f}] k={es['k_underrate']} "
          f"zeroM={es['zero_months']}/{es['n_months']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""芝OP+ 特徴量アブレーション/前向き積み上げ harness (Session 177)

ふくだ方針: 「特徴量をものすごく絞った最悪の状態から地道に積み上げ、何が結果を良くするか追う」。
クラス別AUC(S177)で OP/Listed/G3 の識別力が未勝利/条件より低い=高情報を活かしきれてない疑い
→ どの特徴量グループが芝OP+ の精度を押し上げるかを、グループ単独 & 累積追加で測る。

効率の核: build を1回だけ実行して pickle 保存 → 以後は load して特徴量サブセットを高速総当たり。

Usage:
    python -m ml.nova.ablation_turf_op --build           # データ構築+キャッシュ (重い・1回だけ)
    python -m ml.nova.ablation_turf_op --target w        # キャッシュから ablation (速い)
    python -m ml.nova.ablation_turf_op --target w --scope all   # 汎用(全データ学習)で評価

Output:
    data3/ml/nova/turf_op/splits/{train,val,test}.pkl       (--build)
    data3/ml/nova/turf_op/ablation_{scope}_{target}.md/json (ablation)
"""
from __future__ import annotations
import argparse, io, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from core import config
from ml.experiment import (FEATURE_COLS_ALL, PARAMS_P, PARAMS_W, P_ONLY_FEATURES,
                           MARKET_FEATURES, build_dataset, build_pit_personnel_timeline,
                           load_data, parse_period_range, train_model)
from ml.features.baba_features import load_baba_index
from ml.nova.train_turf_op import filter_turf_op, _turf_mask, OP_GRADES, evaluate_top1_roi

SPLITS = config.ml_dir() / "nova" / "turf_op" / "splits"

# ---- 特徴量グループ定義 (順序 = 累積追加の順 / first-match-wins) ----
# (group, [keywords]) ; keyword は feature 名の部分一致
GROUP_RULES = [
    ("basic",        ["age","sex","distance","wakuban","futan","horse_weight","month","nichi",
                      "place_code","track_condition","track_type","entry_count","rest_weeks",
                      "days_since","career_stage","total_career_races","consumption_flag"]),
    ("form_level",   ["avg_finish_last3","prev_finish","best_finish_last5","finish_std_last5",
                      "win_rate_all","top3_rate_all","best_l3f_last5","last3f","prev_last3f",
                      "comeback_strength","l3_unrewarded"]),
    ("trajectory",  ["trend","growth","vs_pre","joushou","_change","slope","accel",
                      "position_gain","versatility","recent_form"]),
    ("speed_idx",   ["speed_idx"]),
    ("jrdb_idm",    ["jrdb_idm"]),
    ("jrdb_cid",    ["jrdb_cid"]),
    ("jrdb_other",  ["jrdb_ls","jrdb_ten","jrdb_agari","jrdb_start","jrdb_gekisou","jrdb_deokure",
                      "jrdb_furi","jrdb_mae_furi","jrdb_naka_furi","jrdb_ato_furi","jrdb_distance_apt",
                      "jrdb_pace","jrdb_kyakushitsu","jrdb_baba"]),
    ("training",    ["jrdb_cyb","jrdb_cha","oikiri","training_","kaiko"]),
    ("jockey",      ["jockey"]),
    ("trainer",     ["trainer"]),
    ("pedigree",    ["sire_","dam_","bms_","jrdb_kka"]),
    ("pace",        ["pace","rpci","lap33","tbw","prev_race_lap33"]),
    ("track_bias",  ["kaa_","venue","heavy_track","cushion","moisture","straight_distance",
                      "first_corner_dist","steep_course","distance_fitness","exact_distance",
                      "surface_switch","field_size","koukaku","height_diff"]),
    ("class_ctx",   ["grade_level","prev_grade","race_level","condition_top3","prev_race_entry"]),
    ("comments",    ["comment"]),
    ("closing",     ["closing","ck_","front_runner","running_style","kb_rating","distance_direction",
                      "bias_race_exp","high_pace_exp","pace_collapse","pace_sensitivity","pace_match"]),
]
GROUP_ORDER = [g for g, _ in GROUP_RULES] + ["misc"]


def assign_groups(features):
    groups = {g: [] for g in GROUP_ORDER}
    for f in features:
        placed = False
        for g, kws in GROUP_RULES:
            if any(k in f for k in kws):
                groups[g].append(f); placed = True; break
        if not placed:
            groups["misc"].append(f)
    return {g: v for g, v in groups.items() if v}


def do_build(args):
    t0 = time.time()
    print("[Build] load_data ...")
    idx = load_data(sire_cutoff=args.sire_cutoff)
    (history_cache, trainer_index, jockey_index, date_index, pace_index, kb_ext_index,
     training_summary_index, race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index, jrdb_cyb_index, jrdb_cha_index,
     jrdb_kka_index, jrdb_joa_index) = idx
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()
    baba_index = load_baba_index()
    common = dict(date_index=date_index, history_cache=history_cache, trainer_index=trainer_index,
        jockey_index=jockey_index, pace_index=pace_index, kb_ext_index=kb_ext_index, use_db_odds=True,
        training_summary_index=training_summary_index, race_level_index=race_level_index,
        pedigree_index=pedigree_index, sire_stats_index=sire_stats_index, pit_trainer_tl=pit_trainer_tl,
        pit_jockey_tl=pit_jockey_tl, baba_index=baba_index, jrdb_sed_index=jrdb_sed_index,
        jrdb_kyi_index=jrdb_kyi_index, jrdb_kaa_index=jrdb_kaa_index, jrdb_cyb_index=jrdb_cyb_index,
        jrdb_cha_index=jrdb_cha_index, jrdb_kka_index=jrdb_kka_index, jrdb_joa_index=jrdb_joa_index)
    SPLITS.mkdir(parents=True, exist_ok=True)
    for name, period in [("train", args.train_years), ("val", args.val_years), ("test", args.test_years)]:
        mn, mnm, mx, mxm = parse_period_range(period)
        print(f"[Build] {name} ({period}) ...")
        df = build_dataset(min_year=mn, max_year=mx, min_month=mnm, max_month=mxm, **common)
        df.to_pickle(SPLITS / f"{name}.pkl")
        print(f"  saved {name}.pkl: {len(df):,} rows")
    print(f"[Build] done {time.time()-t0:.0f}s")


def fit_eval(df_tr, df_va, df_te, feats, params, label_col):
    """学習して芝OP+ test の AUC / ROI を返す。"""
    feats = [f for f in feats if f in df_tr.columns]
    model, metrics, importance, pred_cal, cal, pred_raw = train_model(
        df_tr, df_va, df_te, feature_cols=feats, params=params, label_col=label_col,
        model_name="abl", num_boost_round=900)
    d = df_te.copy(); d["_p"] = pred_cal
    roi = evaluate_top1_roi(d, "_p")
    return {"n_feats": len(feats), "auc": metrics["auc"], "ece_cal": metrics["ece_calibrated"],
            "roi": roi["roi"], "winrate": roi["hit_rate"]}


def do_ablation(args):
    print("[Load] splits ...")
    tr = pd.read_pickle(SPLITS / "train.pkl")
    va = pd.read_pickle(SPLITS / "val.pkl")
    te = pd.read_pickle(SPLITS / "test.pkl")

    def age_filt(df, lbl):
        if args.min_age <= 0 or "age" not in df.columns:
            return df
        out = df[df["age"] >= args.min_age]
        print(f"  [{lbl}] age>={args.min_age}: {len(df):,} -> {len(out):,} ({df['race_id'].nunique()}->{out['race_id'].nunique()} races)")
        return out

    # 評価は常に「3歳以上 芝OP+」(ふくだ: 経験豊富な上位馬の対決に特化)
    te_op = age_filt(filter_turf_op(te, "Test"), "Test/age")
    if args.scope == "op":
        tr_use = age_filt(filter_turf_op(tr, "Train"), "Train/age")
        va_use = age_filt(filter_turf_op(va, "Val"), "Val/age")
    else:  # all (汎用学習→評価のみ3歳上芝OP+)
        tr_use, va_use = tr, va

    label_col = "is_top3" if args.target == "p" else "is_win"
    params = PARAMS_P if args.target == "p" else PARAMS_W
    base = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]
    if args.target == "w":
        base = [f for f in base if f not in P_ONLY_FEATURES]
    base = [f for f in base if f in tr.columns]
    groups = assign_groups(base)
    age_tag = f"age{args.min_age}up" if args.min_age > 0 else "allage"
    lines = [f"# {args.min_age}歳以上 芝OP+ アブレーション ({args.scope} train, target={args.target})",
             f"eval: 3歳以上(age>={args.min_age}) 芝OP+ {te_op['race_id'].nunique()} races / {len(te_op)} entries",
             f"train={len(tr_use):,} val={len(va_use):,}  全特徴量={len(base)}  num_boost=900",
             "グループ構成:"]
    for g, fl in groups.items():
        lines.append(f"  {g:12s} {len(fl):3d}: {', '.join(fl[:6])}{' ...' if len(fl)>6 else ''}")

    results = {"scope": args.scope, "target": args.target, "groups": {g: len(v) for g, v in groups.items()}}

    # (0) 全部入り (上限)
    full = fit_eval(tr_use, va_use, te_op, base, params, label_col)
    lines.append(f"\n## 全特徴量(上限): AUC={full['auc']:.4f} ECE={full['ece_cal']:.4f} ROI={full['roi']:.0f}% 勝率={full['winrate']}% (n_feats={full['n_feats']})")
    results["full"] = full

    # (1) グループ単独 (basic + そのグループ)
    lines.append("\n## ① グループ単独パワー (basic + 各グループ)")
    lines.append("| group | n_feat | AUC | ECE | ROI | 勝率 |")
    lines.append("|---|---|---|---|---|---|")
    basic = groups.get("basic", [])
    base_only = fit_eval(tr_use, va_use, te_op, basic, params, label_col)
    lines.append(f"| (basic単独) | {base_only['n_feats']} | {base_only['auc']:.4f} | {base_only['ece_cal']:.4f} | {base_only['roi']:.0f}% | {base_only['winrate']}% |")
    solo = {"basic_only": base_only}
    for g, fl in groups.items():
        if g == "basic":
            continue
        r = fit_eval(tr_use, va_use, te_op, basic + fl, params, label_col)
        solo[g] = r
        lines.append(f"| basic+{g} | {r['n_feats']} | {r['auc']:.4f} | {r['ece_cal']:.4f} | {r['roi']:.0f}% | {r['winrate']}% |")
    results["solo"] = solo

    # (2) 累積追加 (固定順)
    lines.append("\n## ② 累積追加 (固定順・学習曲線)")
    lines.append("| +group | n_feat | AUC | ΔAUC | ECE | ROI | 勝率 |")
    lines.append("|---|---|---|---|---|---|---|")
    cum, prev_auc, cumr = [], None, {}
    for g in GROUP_ORDER:
        if g not in groups:
            continue
        cum += groups[g]
        r = fit_eval(tr_use, va_use, te_op, cum, params, label_col)
        d = "" if prev_auc is None else f"{r['auc']-prev_auc:+.4f}"
        lines.append(f"| +{g} | {r['n_feats']} | {r['auc']:.4f} | {d} | {r['ece_cal']:.4f} | {r['roi']:.0f}% | {r['winrate']}% |")
        cumr[g] = r; prev_auc = r["auc"]
    results["cumulative"] = cumr

    out_md = config.ml_dir() / "nova" / "turf_op" / f"ablation_{age_tag}_{args.scope}_{args.target}.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    (config.ml_dir() / "nova" / "turf_op" / f"ablation_{age_tag}_{args.scope}_{args.target}.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Done] wrote {out_md}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser()
    p.add_argument("--build", action="store_true")
    p.add_argument("--target", default="w", choices=["p", "w"])
    p.add_argument("--scope", default="op", choices=["op", "all"])
    p.add_argument("--min-age", type=int, default=3,
                   help="馬齢下限(3=2歳除外で経験馬の対決に特化, 0=無効)")
    p.add_argument("--train-years", default="2020-2025.03")
    p.add_argument("--val-years", default="2025.04")
    p.add_argument("--test-years", default="2025.05-2026.05")
    p.add_argument("--sire-cutoff", default="2025-03-31")
    args = p.parse_args()
    if args.build:
        do_build(args)
    else:
        do_ablation(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

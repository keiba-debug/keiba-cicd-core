#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
モデル比較レポート (Session 119)

2つのpolarisバージョンを並べてAUC・特徴量数・importance Top差分を出力。
学習結果の評価を1コマンドで定型化する。

Usage:
    python -m ml.compare_models --base 2.1b --new 2.2-pace-fix
    python -m ml.compare_models --base 2.0 --new 2.1b --top 30
"""

import argparse
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def load_model_with_importance(version: str, model_name: str = "polaris"):
    """指定バージョンのpolarisモデルとmeta + importance を取得"""
    import lightgbm as lgb

    base_dir = config.ml_dir() / "models" / model_name
    legacy_versions = config.ml_dir() / "versions"
    # 探索パス候補
    candidates = [
        base_dir / "versions" / f"v{version}",
        base_dir / "versions" / version,
        base_dir / "live" if version in ("live", "active") else None,
        legacy_versions / f"v{model_name}-{version}",  # 例: vpolaris-2.1b
        legacy_versions / f"vpolaris-{version}",
        legacy_versions / version,
    ]
    ver_dir = None
    for c in candidates:
        if c is not None and c.exists():
            ver_dir = c
            break
    if ver_dir is None:
        raise FileNotFoundError(
            f"version '{version}' not found. tried: {[str(c) for c in candidates if c]}"
        )

    meta_path = ver_dir / "meta.json"
    if not meta_path.exists():
        meta_path = ver_dir / "model_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    importance = {}
    for tag in ("p", "w", "ar"):
        model_file = ver_dir / f"model_{tag}.txt"
        if not model_file.exists():
            continue
        booster = lgb.Booster(model_file=str(model_file))
        feats = meta.get("features_per_model", {}).get(tag) or meta.get("features_value", [])
        if len(feats) != booster.num_feature():
            # feat list 食い違い → booster側のnames使う
            feats = booster.feature_name()
        gains = booster.feature_importance(importance_type="gain")
        importance[tag] = dict(zip(feats, gains))

    return meta, importance


def fmt_top_diff(imp_a: dict, imp_b: dict, top: int):
    """両モデルの importance Top N を並べる + 差分強調"""
    a_sorted = sorted(imp_a.items(), key=lambda x: -x[1])[:top]
    b_sorted = sorted(imp_b.items(), key=lambda x: -x[1])[:top]
    # 共通特徴量集合
    a_top_set = {f for f, _ in a_sorted}
    b_top_set = {f for f, _ in b_sorted}

    # Top入りした/外れた
    new_in = b_top_set - a_top_set
    fell_out = a_top_set - b_top_set
    return a_sorted, b_sorted, new_in, fell_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="比較元バージョン (例: 2.1b)")
    ap.add_argument("--new", required=True, help="比較先バージョン (例: 2.2-pace-fix)")
    ap.add_argument("--top", type=int, default=20, help="importance Top表示数")
    ap.add_argument("--watch", nargs="*", default=[],
                    help="特定特徴量の rank/gain を両方で表示 (例: jrdb_pace_match)")
    args = ap.parse_args()

    print("=" * 78)
    print(f"Model Comparison:  base=v{args.base}  new=v{args.new}")
    print("=" * 78)

    try:
        meta_a, imp_a = load_model_with_importance(args.base)
        meta_b, imp_b = load_model_with_importance(args.new)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 1

    # === 全体スコア ===
    print(f"\n[Metrics]")
    print(f"  {'metric':<20} {'base':>14} {'new':>14}  diff")
    print(f"  {'-'*60}")
    metrics_a = meta_a.get("metrics") or {}
    metrics_b = meta_b.get("metrics") or {}
    # 直接 meta に含まれる場合と sub-dict の場合あり
    fields = [
        ("p_auc", "P AUC"), ("w_auc", "W AUC"), ("ar_mae", "AR MAE"),
        ("p_brier", "P Brier"), ("w_brier", "W Brier"),
        ("p_ece", "P ECE"), ("w_ece", "W ECE"),
    ]
    for key, label in fields:
        va = metrics_a.get(key) or meta_a.get(key)
        vb = metrics_b.get(key) or meta_b.get(key)
        if va is None and vb is None:
            continue
        sa = f"{va:.4f}" if isinstance(va, (int, float)) else "-"
        sb = f"{vb:.4f}" if isinstance(vb, (int, float)) else "-"
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            d = vb - va
            sign = "+" if d >= 0 else ""
            ds = f"{sign}{d:.4f}"
        else:
            ds = ""
        print(f"  {label:<20} {sa:>14} {sb:>14}  {ds}")

    # === 特徴量数 ===
    fp_a = meta_a.get("features_per_model", {})
    fp_b = meta_b.get("features_per_model", {})
    print(f"\n[Feature Counts]")
    print(f"  {'model':<8} {'base':>6} {'new':>6}  diff")
    print(f"  {'-'*30}")
    for tag in ("p", "w", "ar"):
        na = len(fp_a.get(tag, []) or meta_a.get("features_value", []))
        nb = len(fp_b.get(tag, []) or meta_b.get("features_value", []))
        diff = nb - na
        sign = "+" if diff >= 0 else ""
        print(f"  {tag.upper():<8} {na:>6} {nb:>6}  {sign}{diff}")

    # === 新規/削除特徴量 ===
    feats_a = set(meta_a.get("features_value", []))
    feats_b = set(meta_b.get("features_value", []))
    added = feats_b - feats_a
    removed = feats_a - feats_b
    print(f"\n[Feature Diff]")
    print(f"  追加 (+{len(added)}): {sorted(added) if added else '(なし)'}")
    print(f"  削除 (-{len(removed)}): {sorted(removed) if removed else '(なし)'}")

    # === watched 特徴量 ===
    if args.watch:
        print(f"\n[Watched Features]")
        for tag in ("p", "w"):
            ia = imp_a.get(tag, {})
            ib = imp_b.get(tag, {})
            sa = sorted(ia.items(), key=lambda x: -x[1])
            sb = sorted(ib.items(), key=lambda x: -x[1])
            ra = {f: i + 1 for i, (f, _) in enumerate(sa)}
            rb = {f: i + 1 for i, (f, _) in enumerate(sb)}
            print(f"  --- {tag.upper()} model ---")
            print(f"  {'feature':<40} {'base_gain':>10} {'base#':>5}  {'new_gain':>10} {'new#':>5}")
            for f in args.watch:
                ga = ia.get(f, 0)
                gb = ib.get(f, 0)
                rkA = ra.get(f, 999)
                rkB = rb.get(f, 999)
                print(f"  {f:<40} {ga:>10.0f} {rkA:>5d}  {gb:>10.0f} {rkB:>5d}")

    # === Top N importance ===
    print(f"\n[Importance Top {args.top}]")
    for tag in ("p", "w"):
        ia = imp_a.get(tag, {})
        ib = imp_b.get(tag, {})
        if not ia or not ib:
            continue
        a_top, b_top, new_in, fell_out = fmt_top_diff(ia, ib, args.top)
        print(f"\n  --- {tag.upper()} model ---")
        print(f"  {'rank':>4}  {'BASE'.center(48)}  {'NEW'.center(48)}")
        for i in range(args.top):
            af, ag = (a_top[i] if i < len(a_top) else ("", 0))
            bf, bg = (b_top[i] if i < len(b_top) else ("", 0))
            af_mark = " ← OUT" if af in fell_out else ""
            bf_mark = " ← NEW" if bf in new_in else ""
            print(f"  {i+1:>4}  {af:<32} {ag:>10.0f}{af_mark[:5]:>6}  "
                  f"{bf:<32} {bg:>10.0f}{bf_mark[:5]:>6}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

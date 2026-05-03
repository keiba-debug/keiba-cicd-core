#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
学習前プリフライトチェック (Session 119)

新特徴量の追加・修正後、experiment.py で長時間学習を回す前に
- 新特徴量がdataframeに乗っているか
- 値分布が正常か (分散ゼロでないか)
- Optuna済み feature list に含まれているか (P_ONLY追加 or --no-optuna 要検討)
を1分以内で検証する。

Usage:
    python -m ml.preflight                    # 直近1日のpredict.py で smoke test
    python -m ml.preflight --date 2026-04-26  # 特定日
"""

import argparse
import io
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def find_latest_predictable_date() -> str | None:
    root = Path(config.races_dir())
    for y in sorted(os.listdir(root), reverse=True):
        if not y.isdigit():
            continue
        for m in sorted(os.listdir(root / y), reverse=True):
            for d in sorted(os.listdir(root / y / m), reverse=True):
                day_dir = root / y / m / d
                if not day_dir.is_dir():
                    continue
                if any(day_dir.glob("race_[0-9]*.json")):
                    return f"{y}-{m}-{d}"
    return None


def diff_against_active_model() -> tuple[set, set, set]:
    """現行 active model の features_value vs コード上の FEATURE_COLS_ALL を diff"""
    from ml.experiment import FEATURE_COLS_ALL
    code_set = set(FEATURE_COLS_ALL)

    meta_path = config.ml_dir() / "models" / "polaris" / "live" / "meta.json"
    if not meta_path.exists():
        return code_set, set(), set()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    saved = set(meta.get("features_value", []))

    added = code_set - saved
    removed = saved - code_set
    return code_set, added, removed


def load_optuna_features() -> dict[str, list[str]]:
    """Optuna済み feature list を読み込み (新特徴量との照合に使用)"""
    optuna_path = config.ml_dir().parent / "keiba-v2" / "ml" / "optuna" / "optuna_best_params.json"
    candidates = [
        Path("ml/optuna/optuna_best_params.json"),
        config.ml_dir() / "optuna" / "optuna_best_params.json",
        Path(__file__).parent / "optuna" / "optuna_best_params.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return {
                    "p": data.get("p", {}).get("feature_cols", []),
                    "w": data.get("w", {}).get("feature_cols", []),
                    "ar": data.get("ar", {}).get("feature_cols", []),
                }
            except Exception:
                pass
    return {}


def smoke_test_features(date: str, target_features: list[str]) -> dict:
    """指定日でpredict.pyを試走し、feature_snapshotから値分布チェック"""
    print(f"\n[Smoke Test] Running predict.py for {date} (no-db)...")
    proc = subprocess.run(
        ["python", "-m", "ml.predict", "--date", date, "--no-db"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    if proc.returncode != 0:
        print(f"  [FAIL] predict.py exit={proc.returncode}")
        print(proc.stderr[-500:])
        return {}

    sn_path = Path(config.races_dir()) / date.replace("-", "/") / "feature_snapshot.json"
    if not sn_path.exists():
        # 日付パスが違うかもしれない
        y, m, d = date.split("-")
        sn_path = Path(config.races_dir()) / y / m / d / "feature_snapshot.json"
    if not sn_path.exists():
        print(f"  [FAIL] feature_snapshot.json not found at {sn_path}")
        return {}

    snap = json.loads(sn_path.read_text(encoding="utf-8"))
    races = snap.get("races", [])
    n_entries = sum(len(r.get("entries", [])) for r in races)
    print(f"  [OK] {len(races)} races, {n_entries} entries, snapshot loaded")

    # 各 target feature の分布を集計
    results = {}
    for feat in target_features:
        vals = []
        nans = 0
        for r in races:
            for e in r.get("entries", []):
                v = (e.get("features") or {}).get(feat)
                if v is None:
                    nans += 1
                else:
                    vals.append(v)
        results[feat] = {
            "n_total": n_entries,
            "n_nan": nans,
            "n_valid": len(vals),
            "nan_rate": nans / max(1, n_entries),
            "unique": len(set(round(float(v), 4) for v in vals if isinstance(v, (int, float)))),
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
            "mean": sum(vals) / len(vals) if vals else None,
            "top5": Counter(round(float(v), 2) for v in vals if isinstance(v, (int, float))).most_common(5),
        }
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (省略時は最新)")
    ap.add_argument("--no-smoke", action="store_true", help="predict.py 試走をスキップ")
    args = ap.parse_args()

    print("=" * 78)
    print("Preflight Check — 学習前の特徴量配管検証")
    print("=" * 78)

    # === Step 1: コード vs active model の diff ===
    print("\n[Step 1] FEATURE_COLS_ALL vs active model 比較")
    code_set, added, removed = diff_against_active_model()
    print(f"  コード上の特徴量数: {len(code_set)}")
    print(f"  追加 (+{len(added)}): {sorted(added) if added else '(なし)'}")
    print(f"  削除 (-{len(removed)}): {sorted(removed) if removed else '(なし)'}")

    if not added and not removed:
        print("\n  [SKIP] 特徴量変更なし。preflightは不要。")
        return 0

    # === Step 2: Optuna list との照合 ===
    print("\n[Step 2] Optuna済み feature list との照合")
    optuna = load_optuna_features()
    if not optuna:
        print("  [INFO] Optuna list 見つからず (--use-optuna なしで学習する想定)")
    else:
        for model_name in ("p", "w", "ar"):
            opt_set = set(optuna.get(model_name, []))
            missing = added - opt_set
            if missing:
                print(f"  [WARN] {model_name.upper()}モデルOptuna list 外の新特徴量: {sorted(missing)}")
                print(f"         → P_ONLY_FEATURES に追加するか --use-optuna を外す必要あり")
            else:
                print(f"  [OK] {model_name.upper()}モデル: 新特徴量はOptuna listに含まれる or 追加なし")

    # === Step 3: 試走で値分布チェック ===
    if args.no_smoke:
        print("\n[Step 3] --no-smoke 指定により試走スキップ")
        return 0

    date = args.date or find_latest_predictable_date()
    if not date:
        print("\n[Step 3] [SKIP] 試走可能な日が見つからず")
        return 0

    if not added:
        print("\n[Step 3] 新特徴量がないため smoke test スキップ")
        return 0

    print(f"\n[Step 3] {date} で smoke test 実行")
    results = smoke_test_features(date, sorted(added))

    print(f"\n  {'feature':<40} {'NaN率':>7} {'unique':>6} {'min':>7} {'max':>7} {'mean':>7}  Top5値")
    print("  " + "-" * 110)
    issues = []
    for feat, st in sorted(results.items()):
        nan_pct = f"{100 * st['nan_rate']:5.1f}%"
        if st["n_valid"] == 0:
            print(f"  {feat:<40} {nan_pct:>7} {'':>6} {'':>7} {'':>7} {'':>7}  [全NaN]")
            issues.append(f"{feat}: 全レコードでNaN — データ取得に失敗してる可能性")
            continue
        unique = st["unique"]
        mn, mx, mean = st["min"], st["max"], st["mean"]
        top5 = " ".join(f"{v}({n})" for v, n in st["top5"])
        print(f"  {feat:<40} {nan_pct:>7} {unique:>6} {mn:>7.2f} {mx:>7.2f} {mean:>7.2f}  {top5}")
        if unique <= 1:
            issues.append(f"{feat}: unique={unique} (定数) — 学習に寄与しない")
        if st["nan_rate"] >= 0.9:
            issues.append(f"{feat}: NaN率 {100*st['nan_rate']:.1f}% — データ未流入の可能性")
        if unique <= 5 and st["nan_rate"] < 0.5:
            top_v, top_n = st["top5"][0]
            if top_n / st["n_valid"] >= 0.7:
                issues.append(f"{feat}: {top_v}に{100*top_n/st['n_valid']:.0f}%張り付き — 死特徴量化リスク")

    print()
    if issues:
        print(f"  ⚠️  Issues検出 ({len(issues)}件):")
        for i in issues:
            print(f"    - {i}")
        return 1
    else:
        print("  ✅ 全特徴量 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""ライブpredictions 検証ハーネス (Session 152 / backlog E-009)

その日打った生予測 (predictions.json) を T-5直前オッズ・実払戻と突合し、
gap>=k バケット別に [較正乖離 / 単勝ROI / 複勝ROI / ブートCI / n / 平均オッズ] を測る。
単勝は T-5実行価格、複勝は確定配当で精算（T-5複勝オッズ不在のため・fukusho_payout 注記参照）。
predictions の `cache_freshness` メタ (Session 152 ③) があれば劣化/健全を仕分けできる。

3用途の共通土台 (= E-009「補助オプション採否を gap>=k ROI/CIで判定するテンプレ」):
  - 過去再評価     : 劣化期間(2026-03-21〜06-07)を流し stale バイアスを gap軸で定量化
  - 今後の健全検証 : is_stale=false が貯まるごとに同じ道具で較正/妙味を本測定
  - 将来オプション : 補助オプション適用前後で同じ指標を比較し採否判定 (拡張口: apply_option)

設計原則:
  - 後知恵回避     : 帯分け・ROI精算は T-5直前オッズ (odds_db.batch_get_win_odds_at_cutoff)
  - gap は再計算しない: predictions の vb_gap(P) / win_vb_gap(W) を直読み
  - 読み取り専用   : 本番データは一切書き換えない

Usage:
  python -m ml.analyze.validate_live_predictions --start 2026-03-21 --end 2026-06-07
  python -m ml.analyze.validate_live_predictions --start 2026-03-21 --end 2026-06-07 --gap w --json
  python -m ml.analyze.validate_live_predictions --start 2026-06-13 --end 2026-06-30 --split-freshness
"""

import argparse
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # keiba-v2

from core import odds_db  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402

RACES_DIR = Path("C:/KEIBA-CICD/data3/races")
ODDS_BANDS = [(0.0, 3.0, "<2.9"), (3.0, 10.0, "3-9.9"), (10.0, 50.0, "10-49.9"), (50.0, 1e9, "50+")]
GAP_THRESHOLDS = [0, 2, 4, 6]
MIN_N = 30  # この件数未満のセルは指標を出さない（小標本ノイズ抑制）

# gap 選択 → predictions の gap フィールド (P=vb_gap, W=win_vb_gap)
GAP_FIELD = {"p": "vb_gap", "w": "win_vb_gap"}
GAP_ORDER = [f">={k}" for k in GAP_THRESHOLDS]      # gap軸の表示順 (累積バケット)
BAND_ORDER = [name for _, _, name in ODDS_BANDS]    # odds帯軸の表示順 (排他)


# ============================ 純粋関数（テスト対象） ============================

def odds_band(od):
    """単勝オッズ → 帯ラベル。"""
    for lo, hi, name in ODDS_BANDS:
        if lo <= od < hi:
            return name
    return "?"


def gap_buckets(gap, thresholds=GAP_THRESHOLDS):
    """gap が満たす全 gap>=k の累積ラベル。gap=5 → ['>=0','>=2','>=4']。None/欠損は空。"""
    if gap is None:
        return []
    return [f">={k}" for k in thresholds if gap >= k]


def _row_labels(r, axis):
    """row が属する軸ラベル群。axis=gap は累積(複数)、axis=band は排他(1帯)。"""
    if axis == "gap":
        return gap_buckets(r["gap"])
    b = odds_band(r["cutoff_odds"])
    return [b] if b != "?" else []


def freshness_label(is_stale):
    """cache_freshness メタの is_stale → 表示ラベル。None=メタ無し(劣化期間/旧形式)。"""
    if is_stale is None:
        return "unknown"
    return "stale" if is_stale else "fresh"


def bootstrap_roi(payouts, n_boot=1000, ci=0.95, seed=42):
    """bet単位リサンプルで単勝ROIのCI。payouts=各betの払戻(円)、bet=100円固定。"""
    if not payouts:
        return {"roi": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0}
    arr = np.asarray(payouts, dtype=float)
    n = len(arr)
    bet_total = n * 100.0
    roi = arr.sum() / bet_total * 100.0
    rng = np.random.default_rng(seed)
    boots = [rng.choice(arr, size=n, replace=True).sum() / bet_total * 100.0 for _ in range(n_boot)]
    a = (1.0 - ci) / 2.0
    return {
        "roi": round(roi, 1),
        "ci_low": round(float(np.percentile(boots, a * 100)), 1),
        "ci_high": round(float(np.percentile(boots, (1 - a) * 100)), 1),
        "n": n,
    }


def calibration_gap(preds, hits):
    """予測平均 - 実現平均 (マイナス=過小評価)。空なら None。"""
    if not preds:
        return None
    return round(float(np.mean(preds) - np.mean(hits)), 4)


def fukusho_payout(fuku, umaban):
    """確定複勝配当 (100円あたり払戻)。in-the-money 外/欠損は 0。

    精算方針の非対称（意図的）:
      単勝は T-5直前オッズ (実行価格) で精算し後知恵を避けるが、複勝は odds_db に
      T-5複勝オッズが無いため、確定配当 (haraimodoshi fukusho) で精算する。複勝配当は
      単勝最終配当より変動が小さく、ゲート（意思決定）でなく精算に使う限り後知恵の影響は小さい。
    """
    if umaban is None or not fuku:
        return 0.0
    try:
        return float(fuku.get(int(umaban), 0) or 0)
    except (ValueError, TypeError):
        return 0.0


# ============================ IO ============================

def collect_rows(start, end, gap_sel):
    """期間 [start,end] (YYYYMMDD) の predictions.json から entry 行を集める。

    cache_freshness メタ (Session 152 ③ 以降のみ存在) も各行に伝播。
    """
    gap_field = GAP_FIELD[gap_sel]
    rows = []
    days = set()
    for p in sorted(RACES_DIR.glob("2026/*/*/predictions.json")):
        d = p.parent
        key = f"{d.parts[-3]}{d.parts[-2]}{d.parts[-1]}"
        if not (start <= key <= end):
            continue
        try:
            obj = json.load(open(p, encoding="utf-8"))
        except (ValueError, OSError) as e:
            print(f"  [skip] {key}: {e}")
            continue
        ver = str(obj.get("model_version") or "?")
        fresh = obj.get("cache_freshness")  # dict or None
        is_stale = (fresh or {}).get("is_stale")  # True/False/None
        day = f"{d.parts[-3]}-{d.parts[-2]}-{d.parts[-1]}"
        days.add(day)
        for r in obj.get("races") or []:
            rid = str(r.get("race_id") or "")
            if not rid:
                continue
            for e in r.get("entries") or []:
                w = e.get("pred_proba_w_cal")
                if w is None:
                    w = e.get("pred_proba_w")
                rows.append({
                    "rid": rid, "day": day, "version": ver, "is_stale": is_stale,
                    "umaban": e.get("umaban"),
                    "p_raw": e.get("pred_proba_p_raw"),
                    "w_cal": w,
                    "gap": e.get(gap_field),
                })
    return rows, sorted(days)


def enrich(rows):
    """払戻(正解) と T-5直前オッズ(後知恵回避) を join。未確定/オッズ欠損は除外。"""
    rids = sorted({r["rid"] for r in rows})
    pay = load_haraimodoshi(rids)
    co = odds_db.batch_get_win_odds_at_cutoff(rids, minutes_before=5)
    out = []
    n_unsettled = n_no_odds = 0
    for r in rows:
        rid = r["rid"]
        rec = pay.get(rid) or {}
        tan = rec.get("tansho") or {}
        fuku = rec.get("fukusho") or {}
        if not tan and not fuku:
            n_unsettled += 1
            continue
        um = r["umaban"]
        ent = (co.get(rid) or {}).get(int(um)) if um is not None else None
        od = (ent or {}).get("odds")
        if not isinstance(od, (int, float)) or od <= 0:
            n_no_odds += 1
            continue
        r2 = dict(r)
        r2["cutoff_odds"] = float(od)
        r2["tansho_hit"] = 1 if (um is not None and int(um) in tan) else 0
        r2["fukusho_hit"] = 1 if (um is not None and int(um) in fuku) else 0
        r2["fukusho_payout"] = fukusho_payout(fuku, um)  # 確定複勝配当(100円あたり)
        out.append(r2)
    return out, {"unsettled": n_unsettled, "no_cutoff_odds": n_no_odds, "kept": len(out)}


# ============================ 集計 ============================

def measure(rows, axis="gap", split_freshness=False):
    """axis (gap=gap>=k累積 / band=odds帯排他) × (鮮度) ごとに較正乖離・単勝ROI・平均オッズを集計。

    返り値: { freshness_label: { label: {metrics...} } }
    split_freshness=False なら freshness_label は "all" 一括。
    """
    grp = defaultdict(lambda: {"p_pred": [], "p_hit": [], "w_pred": [], "w_hit": [],
                               "tan_payout": [], "fuku_payout": [], "odds": []})
    for r in rows:
        flab = freshness_label(r["is_stale"]) if split_freshness else "all"
        od = r["cutoff_odds"]
        for lab in _row_labels(r, axis):
            g = grp[(flab, lab)]
            if isinstance(r["p_raw"], (int, float)):
                g["p_pred"].append(float(r["p_raw"]))
                g["p_hit"].append(r["fukusho_hit"])
            if isinstance(r["w_cal"], (int, float)):
                g["w_pred"].append(float(r["w_cal"]))
                g["w_hit"].append(r["tansho_hit"])
            g["tan_payout"].append(od * 100.0 if r["tansho_hit"] else 0.0)
            g["fuku_payout"].append(r.get("fukusho_payout", 0.0))  # 確定配当で精算
            g["odds"].append(od)

    out = defaultdict(dict)
    for (flab, lab), g in grp.items():
        n = len(g["tan_payout"])
        if n < MIN_N:
            continue
        roi = bootstrap_roi(g["tan_payout"])
        froi = bootstrap_roi(g["fuku_payout"])
        out[flab][lab] = {
            "n_bets": n,
            "cal_gap_p": calibration_gap(g["p_pred"], g["p_hit"]),
            "p_pred_mean": round(float(np.mean(g["p_pred"])), 4) if g["p_pred"] else None,
            "p_hit_mean": round(float(np.mean(g["p_hit"])), 4) if g["p_hit"] else None,
            "cal_gap_w": calibration_gap(g["w_pred"], g["w_hit"]),
            "w_pred_mean": round(float(np.mean(g["w_pred"])), 4) if g["w_pred"] else None,
            "w_hit_mean": round(float(np.mean(g["w_hit"])), 4) if g["w_hit"] else None,
            "tansho_roi": roi["roi"],
            "tansho_roi_ci": [roi["ci_low"], roi["ci_high"]],
            "fukusho_roi": froi["roi"],
            "fukusho_roi_ci": [froi["ci_low"], froi["ci_high"]],
            "avg_odds": round(float(np.mean(g["odds"])), 1),
        }
    return dict(out)


def row_month(day):
    """行の day("YYYY-MM-DD") → 月キー "YYYY-MM"。欠損は None。"""
    if not day or len(day) < 7:
        return None
    return day[:7]


def monthly_breakdown(rows, gap_min=None, min_n=MIN_N):
    """walk-forward: 月別に単勝/複勝ROIをブートCI付きで集計（後知恵防止の持続性チェック）。

    集計値の幸運な窓に騙されないため、エッジが複数月で一貫するかを月単位で見る。
    gap_min を指定すると gap>=gap_min の bet のみで月別 ROI を測る（補助オプションの
    採否を「特定 gap 帯で各月とも勝てるか」で判定する用途）。

    返り値: { "YYYY-MM": {n_bets, tansho_roi, tansho_roi_ci, fukusho_roi,
                          fukusho_roi_ci, avg_odds} }（n<min_n の月は除外）
    """
    grp = defaultdict(lambda: {"tan_payout": [], "fuku_payout": [], "odds": []})
    for r in rows:
        if gap_min is not None:
            g_ = r.get("gap")
            if g_ is None or g_ < gap_min:
                continue
        m = row_month(r.get("day"))
        if m is None:
            continue
        od = r["cutoff_odds"]
        cell = grp[m]
        cell["tan_payout"].append(od * 100.0 if r["tansho_hit"] else 0.0)
        cell["fuku_payout"].append(r.get("fukusho_payout", 0.0))
        cell["odds"].append(od)

    out = {}
    for m in sorted(grp):
        cell = grp[m]
        n = len(cell["tan_payout"])
        if n < min_n:
            continue
        roi = bootstrap_roi(cell["tan_payout"])
        froi = bootstrap_roi(cell["fuku_payout"])
        out[m] = {
            "n_bets": n,
            "tansho_roi": roi["roi"],
            "tansho_roi_ci": [roi["ci_low"], roi["ci_high"]],
            "fukusho_roi": froi["roi"],
            "fukusho_roi_ci": [froi["ci_low"], froi["ci_high"]],
            "avg_odds": round(float(np.mean(cell["odds"])), 1),
        }
    return out


# ============================ 補助オプション差込口 ============================
# 将来の補助オプション（例: danger-model の composite割引 / 3着回避 / 配分）を、
# 同じ gap-ROI/CI・walk-forward 指標で「適用前後」比較するための純関数フック。
# 各オプションは enrich 済み行リストを受け取り変換後の行リストを返す（rows -> rows）。
# 行を増やさない／payout・cutoff_odds・hit は改竄しないこと（精算の整合を保つため、
# 変換は「どの bet を残すか」「予測値(p_raw/w_cal/gap)をどう補正するか」に限る）。
# danger-model 着手時は dangerフラグで割引・除外する関数をここに登録し --option で評価する。

def opt_none(rows):
    """恒等（baseline）。"""
    return rows


def opt_high_conviction(rows):
    """gap>=2 の高確信 bet のみ残す（差込口の動作例・分析用フィルタ）。"""
    return [r for r in rows if isinstance(r.get("gap"), (int, float)) and r["gap"] >= 2]


# name -> callable(rows) -> rows。danger 等を足すときはここに1行追加するだけ。
OPTION_REGISTRY = {
    "none": opt_none,
    "high_conviction": opt_high_conviction,
}


# ============================ レポート ============================

def print_report(result, days, enrich_stats, gap_sel, split_freshness, axis):
    order = GAP_ORDER if axis == "gap" else BAND_ORDER
    axis_name = "gap>=k" if axis == "gap" else "odds帯"

    if axis == "gap":  # ヘッダは先頭(gap軸)で一度だけ
        print(f"\n{'='*78}")
        print(f"  ライブpredictions 検証ハーネス (E-009) — gap基準={gap_sel} (vb_gap=P / win_vb_gap=W)")
        print(f"{'='*78}")
        if days:
            print(f"  対象日: {len(days)}日 ({days[0]} 〜 {days[-1]})")
        print(f"  bet採用: {enrich_stats['kept']:,} (未確定除外 {enrich_stats['unsettled']:,} / "
              f"直前オッズ欠損 {enrich_stats['no_cutoff_odds']:,})")
        print(f"  乖離=予測-実現(マイナス=過小) / ROI=100%トントン / CI=bet単位ブート95%")

    for flab in result:
        tag = ""
        if split_freshness:
            tag = (f" 鮮度={flab}"
                   f"({'メタ無=劣化期間/旧形式' if flab == 'unknown' else 'cache_freshnessメタ'})")
        print(f"\n  [{axis_name}軸]{tag}")
        print(f"  {axis_name:<8}{'n':>6}{'P複勝乖離':>12}{'W単勝乖離':>12}"
              f"{'単勝ROI':>9}{'単ROI CI':>15}{'複勝ROI':>9}{'複ROI CI':>15}{'平均odds':>9}")
        cells = result[flab]
        for lab in order:
            if lab not in cells:
                continue
            c = cells[lab]
            cgp = f"{c['cal_gap_p']:+.3f}" if c["cal_gap_p"] is not None else "-"
            cgw = f"{c['cal_gap_w']:+.3f}" if c["cal_gap_w"] is not None else "-"
            ci = f"[{c['tansho_roi_ci'][0]:.0f},{c['tansho_roi_ci'][1]:.0f}]"
            fci = f"[{c['fukusho_roi_ci'][0]:.0f},{c['fukusho_roi_ci'][1]:.0f}]"
            print(f"  {lab:<8}{c['n_bets']:>6}{cgp:>12}{cgw:>12}"
                  f"{c['tansho_roi']:>8.0f}%{ci:>15}{c['fukusho_roi']:>8.0f}%{fci:>15}"
                  f"{c['avg_odds']:>9.1f}")
    print()


def print_monthly(monthly, gap_min):
    """walk-forward 月別 ROI テーブル（単勝/複勝・bet単位CI）。"""
    scope = f"gap>={gap_min}" if gap_min is not None else "全bet"
    print(f"\n  [walk-forward 月別] 対象={scope}（各月とも勝てるか＝後知恵防止の持続性チェック）")
    print(f"  {'月':<9}{'n':>6}{'単勝ROI':>9}{'単ROI CI':>15}{'複勝ROI':>9}{'複ROI CI':>15}{'平均odds':>9}")
    if not monthly:
        print(f"  （各月とも n<{MIN_N} で表示なし）")
        print()
        return
    for m, c in monthly.items():
        ci = f"[{c['tansho_roi_ci'][0]:.0f},{c['tansho_roi_ci'][1]:.0f}]"
        fci = f"[{c['fukusho_roi_ci'][0]:.0f},{c['fukusho_roi_ci'][1]:.0f}]"
        print(f"  {m:<9}{c['n_bets']:>6}{c['tansho_roi']:>8.0f}%{ci:>15}"
              f"{c['fukusho_roi']:>8.0f}%{fci:>15}{c['avg_odds']:>9.1f}")
    print()


def main():
    # 日本語コンソール出力 (Shift-JIS端末対策)。import時でなく CLI実行時のみ差し替える
    # （トップレベルに置くと pytest の stdout capture を壊し I/O error になる）。
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Validate live predictions by gap>=k ROI/CI (E-009)")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--gap", choices=["p", "w"], default="p", help="バケット軸 gap (p=vb_gap, w=win_vb_gap)")
    ap.add_argument("--split-freshness", action="store_true",
                    help="cache_freshness メタで stale/fresh/unknown に分けて対比")
    ap.add_argument("--monthly", action="store_true",
                    help="walk-forward: 月別に単勝/複勝ROIを出し持続性を確認（後知恵防止）")
    ap.add_argument("--monthly-gap", type=int, default=None,
                    help="--monthly の gap>=N フィルタ（特定gap帯で各月勝てるか。既定=全bet）")
    ap.add_argument("--option", choices=list(OPTION_REGISTRY), default="none",
                    help="補助オプションを適用し baseline と同指標で前後比較（差込口・既定none）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    start = args.start.replace("-", "")
    end = args.end.replace("-", "")

    rows, days = collect_rows(start, end, args.gap)
    if not rows:
        print("対象predictionsなし")
        sys.exit(0)
    rows, enrich_stats = enrich(rows)

    def _measure_all(rs):
        return {ax: measure(rs, axis=ax, split_freshness=args.split_freshness)
                for ax in ("gap", "band")}

    # baseline は常に算出。--option 指定時は変換後も算出し前後比較。
    variants = [("baseline", rows)]
    if args.option != "none":
        variants.append((f"option={args.option}", OPTION_REGISTRY[args.option](rows)))

    measured = [(label, rs, _measure_all(rs),
                 monthly_breakdown(rs, gap_min=args.monthly_gap) if args.monthly else None)
                for label, rs in variants]

    if args.json:
        payload = {"days": days, "enrich": enrich_stats, "gap_sel": args.gap,
                   "variants": [{"label": label, "n_rows": len(rs), "results": res,
                                 "monthly": ({"gap_min": args.monthly_gap, "rows": mo}
                                             if mo is not None else None)}
                                for label, rs, res, mo in measured]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for label, rs, res, mo in measured:
            if args.option != "none":
                print(f"\n{'#'*78}\n  ## {label}  (bet {len(rs):,})\n{'#'*78}")
            for ax in ("gap", "band"):
                print_report(res[ax], days, enrich_stats, args.gap, args.split_freshness, ax)
            if mo is not None:
                print_monthly(mo, args.monthly_gap)


if __name__ == "__main__":
    main()

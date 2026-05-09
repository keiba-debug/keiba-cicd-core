"""新潟千直 Phase 1 検証① 枠順バイアス

仮説:
  H01: 8枠複勝率約40% vs 1枠約6%（4倍以上の差）
  H02: 1-5枠で10%、6枠で倍化、7-8枠で跳ねる「ホッケースティック型」分布

検証軸:
  1. 全体集計（枠別 出走/勝率/3着内率/単勝ROI/95%信頼区間）
  2. 年代別（2020-2022 vs 2023-2026）で非定常性チェック
  3. ホッケースティック型検証（枠グループ化）
  4. 頭数別（16/17/18頭立て）
  5. 馬場状態別（良 vs 稍重以上）

出力:
  - Markdown（docs/ml-experiments/v8.x_vega_niigata1000_phase1_verification.md）
  - 補助CSV（同ディレクトリ配下）
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

# 親ディレクトリ追加（パッケージ化済みなので本来不要だが念のため）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.niigata1000 import load_dataset


REPORT_PATH = Path(
    "C:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2/docs/ml-experiments/"
    "v8.x_vega_niigata1000_phase1_verification.md"
)
CSV_DIR = REPORT_PATH.parent / "v8.x_vega_niigata1000_phase1_data"


def beta_ci(success: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    """Beta-Binomial credible interval (Jeffreys prior風: success+1, total-success+1)"""
    if total == 0:
        return (0.0, 0.0)
    a = success + 1
    b = total - success + 1
    return (float(beta.ppf(alpha / 2, a, b)), float(beta.ppf(1 - alpha / 2, a, b)))


def aggregate(df: pd.DataFrame, group_col) -> pd.DataFrame:
    """枠順別集計（is_win/is_top3/単勝ROI + 95%CI）"""
    grouped = df.groupby(group_col, dropna=False).agg(
        n=("is_win", "size"),
        wins=("is_win", "sum"),
        top3=("is_top3", "sum"),
        win_payoff=("win_payoff", "sum"),
    )
    grouped = grouped.reset_index()
    grouped["win_rate"] = grouped["wins"] / grouped["n"]
    grouped["top3_rate"] = grouped["top3"] / grouped["n"]
    grouped["win_roi"] = grouped["win_payoff"] / (grouped["n"] * 100.0)

    win_ci = grouped.apply(lambda r: beta_ci(int(r["wins"]), int(r["n"])), axis=1)
    grouped["win_rate_lo"] = [c[0] for c in win_ci]
    grouped["win_rate_hi"] = [c[1] for c in win_ci]
    top3_ci = grouped.apply(lambda r: beta_ci(int(r["top3"]), int(r["n"])), axis=1)
    grouped["top3_rate_lo"] = [c[0] for c in top3_ci]
    grouped["top3_rate_hi"] = [c[1] for c in top3_ci]

    return grouped


def fmt_table(g: pd.DataFrame, group_label: str) -> str:
    lines = [
        f"| {group_label} | 出走 | 勝 | 3着内 | 勝率 | 95%CI(勝) | 3着内率 | 95%CI(3着内) | 単勝ROI |",
        f"|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in g.iterrows():
        key = r.iloc[0]
        lines.append(
            f"| {key} | {int(r['n'])} | {int(r['wins'])} | {int(r['top3'])} | "
            f"{r['win_rate']*100:.1f}% | "
            f"[{r['win_rate_lo']*100:.1f}, {r['win_rate_hi']*100:.1f}] | "
            f"{r['top3_rate']*100:.1f}% | "
            f"[{r['top3_rate_lo']*100:.1f}, {r['top3_rate_hi']*100:.1f}] | "
            f"{r['win_roi']*100:.1f}% |"
        )
    return "\n".join(lines)


def waku_group(w):
    """枠番をホッケースティック想定の3グループに"""
    if w in (1, 2, 3, 4, 5):
        return "1-5枠（内）"
    if w == 6:
        return "6枠（中）"
    if w in (7, 8):
        return "7-8枠（外）"
    return f"?{w}"


def hokey_stick_check(df: pd.DataFrame) -> str:
    """ホッケースティック型: 1-5/6/7-8 のグループ間段階差検証"""
    df2 = df.copy()
    df2["frame_grp"] = df2["wakuban"].apply(waku_group)
    g = aggregate(df2, "frame_grp")
    # 並び替え
    order = ["1-5枠（内）", "6枠（中）", "7-8枠（外）"]
    g["_ord"] = g["frame_grp"].apply(lambda x: order.index(x) if x in order else 99)
    g = g.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)

    body = fmt_table(g.rename(columns={"frame_grp": "枠グループ"}), "枠グループ")

    # 段階差サマリ
    rates = dict(zip(g["frame_grp"], g["top3_rate"]))
    if all(k in rates for k in order):
        ratio_6_15 = rates["6枠（中）"] / max(rates["1-5枠（内）"], 1e-9)
        ratio_78_15 = rates["7-8枠（外）"] / max(rates["1-5枠（内）"], 1e-9)
        body += (
            f"\n\n**段階差**: "
            f"6枠/1-5枠 = {ratio_6_15:.2f}倍, "
            f"7-8枠/1-5枠 = {ratio_78_15:.2f}倍"
        )
    return body


def era_compare(df: pd.DataFrame) -> str:
    """年代別（2020-2022 vs 2023-2026）枠順バイアス比較"""
    df_e1 = df[df["year"].between(2020, 2022)]
    df_e2 = df[df["year"].between(2023, 2026)]

    out = []
    out.append("#### 2020-2022")
    out.append(f"レース数: {df_e1['race_id'].nunique()}, 出走: {len(df_e1)}\n")
    out.append(fmt_table(aggregate(df_e1, "wakuban"), "枠"))

    out.append("\n#### 2023-2026")
    out.append(f"レース数: {df_e2['race_id'].nunique()}, 出走: {len(df_e2)}\n")
    out.append(fmt_table(aggregate(df_e2, "wakuban"), "枠"))

    # 1-2枠×追込仮説（簡易: 1-2枠の3着内率が後期で上昇したか）
    inner_e1 = df_e1[df_e1["wakuban"].isin([1, 2])]["is_top3"].mean()
    inner_e2 = df_e2[df_e2["wakuban"].isin([1, 2])]["is_top3"].mean()
    out.append(
        f"\n**1-2枠（内枠）3着内率の年代変化**: "
        f"{inner_e1*100:.1f}% (前期) → {inner_e2*100:.1f}% (後期), "
        f"差 {(inner_e2-inner_e1)*100:+.1f}pt"
    )

    return "\n".join(out)


def num_runners_split(df: pd.DataFrame) -> str:
    """頭数別バイアス（16/17/18頭）"""
    out = []
    for n in [16, 17, 18]:
        sub = df[df["num_runners"] == n]
        if sub.empty:
            continue
        out.append(f"\n#### {n}頭立て（{sub['race_id'].nunique()}R, {len(sub)}走）")
        out.append(fmt_table(aggregate(sub, "wakuban"), "枠"))
    return "\n".join(out)


def baba_split(df: pd.DataFrame) -> str:
    """馬場状態別バイアス（良 vs 稍重以上）"""
    df2 = df.copy()
    df2["baba_grp"] = df2["track_condition"].apply(
        lambda x: "良" if x == "良" else "稍重以上"
    )
    out = []
    for grp_name in ["良", "稍重以上"]:
        sub = df2[df2["baba_grp"] == grp_name]
        if sub.empty:
            continue
        out.append(f"\n#### {grp_name}（{sub['race_id'].nunique()}R, {len(sub)}走）")
        out.append(fmt_table(aggregate(sub, "wakuban"), "枠"))
    return "\n".join(out)


def main() -> None:
    print("Loading dataset...")
    ds = load_dataset()
    df = ds.horses
    print(f"Loaded: {ds.n_races}R / {ds.n_horses}走")

    # finish_position が欠損している馬は除外（出走取消等）
    df = df[df["finish_position"].notna()].copy()
    print(f"After dropping no-finish: {len(df)}走")

    CSV_DIR.mkdir(parents=True, exist_ok=True)

    # ===== セクション組立 =====
    sections: list[str] = []

    # 1. 全体集計
    overall = aggregate(df, "wakuban")
    overall.to_csv(CSV_DIR / "01_frame_overall.csv", index=False, encoding="utf-8-sig")
    sections.append("### 1. 全体集計（枠別）")
    sections.append(f"\n対象: {df['race_id'].nunique()}R, {len(df)}走\n")
    sections.append(fmt_table(overall, "枠"))

    # 2. ホッケースティック型
    sections.append("\n\n### 2. ホッケースティック型検証（H02）")
    sections.append(hokey_stick_check(df))

    # 3. 年代別
    sections.append("\n\n### 3. 年代別非定常性検証")
    sections.append(era_compare(df))

    # 4. 頭数別
    sections.append("\n\n### 4. 頭数別バイアス")
    sections.append(num_runners_split(df))

    # 5. 馬場状態別
    sections.append("\n\n### 5. 馬場状態別バイアス")
    sections.append(baba_split(df))

    # 結論セクション（簡易）
    overall_top3_1 = overall.loc[overall["wakuban"] == 1, "top3_rate"].iloc[0] if 1 in overall["wakuban"].values else 0
    overall_top3_8 = overall.loc[overall["wakuban"] == 8, "top3_rate"].iloc[0] if 8 in overall["wakuban"].values else 0
    sections.append("\n\n### 6. 結論サマリ")
    sections.append(
        f"- **H01検証**: 1枠3着内率 {overall_top3_1*100:.1f}% vs 8枠 {overall_top3_8*100:.1f}% "
        f"（差 {(overall_top3_8 - overall_top3_1)*100:+.1f}pt, 比 {overall_top3_8/max(overall_top3_1, 1e-9):.1f}倍）"
    )
    sections.append("- **H02検証**: 上記「ホッケースティック型検証」表を参照")
    sections.append("- **特徴量化候補**:")
    sections.append("  - `frame_outer_flag`: 枠6+ で1, 枠1-5 で0")
    sections.append("  - `frame_outer_strong_flag`: 枠7-8 で1（より強いシグナル）")
    sections.append("  - `frame_number`: 連続値（線形フィットで使う場合）")
    sections.append("  - `frame_x_runners`: 枠順×頭数 の交互作用（少頭数で枠意味薄説の検証）")

    # ===== レポート出力 =====
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "# vega-niigata1000 Phase 1 仮説検証レポート\n\n"
        f"作成: {datetime.now().strftime('%Y-%m-%d')}\n"
        "対象: 新潟芝1000m全レース（2020-2026）\n\n"
        "Phase 0 Web調査（60仮説）の経験的検証。各カテゴリで仮説を「強支持/弱支持/不支持」に分類し、"
        "特徴量化候補を抽出する。\n\n"
        "---\n\n"
    )

    section_body = (
        "## 検証① 枠順バイアス\n\n"
        "**対象仮説**:\n"
        "- H01: 8枠複勝率約40% vs 1枠約6%（4倍以上の差）\n"
        "- H02: 1-5枠で10%、6枠で倍化、7-8枠で跳ねる「ホッケースティック型」\n"
        "- 年代非定常性: 2023年以降1-2枠×追込が約4倍に台頭\n\n"
        + "\n".join(sections)
        + "\n\n---\n\n"
    )

    if not REPORT_PATH.exists():
        REPORT_PATH.write_text(header + section_body, encoding="utf-8")
    else:
        # 既存に同じセクションがあるなら置換、なければ追記
        existing = REPORT_PATH.read_text(encoding="utf-8")
        marker = "## 検証① 枠順バイアス"
        next_marker_candidates = ["## 検証②", "## 検証③", "## 検証④", "## 検証⑤"]
        if marker in existing:
            # 既存セクションを切り出して置換
            start = existing.index(marker)
            end = len(existing)
            for nm in next_marker_candidates:
                idx = existing.find(nm, start + 1)
                if idx != -1 and idx < end:
                    end = idx
            new_existing = existing[:start] + section_body + existing[end:]
            REPORT_PATH.write_text(new_existing, encoding="utf-8")
        else:
            REPORT_PATH.write_text(existing + section_body, encoding="utf-8")

    print(f"\nReport written: {REPORT_PATH}")
    print(f"CSV dir: {CSV_DIR}")


if __name__ == "__main__":
    main()

"""新潟千直 Phase 1 検証② 脚質・展開

千直は直線レースで corner 情報がないため、ペースタイムから脚質を推定:
  - pre_2f = time_sec - last_3f （前半2F=400m）
  - pre_2f_dev = (各馬の pre_2f) - (race平均 pre_2f)
  - last_3f_dev = (各馬の last_3f) - (race平均 last_3f)
  - 4象限分類（前半速/遅 × 上がり速/遅）

仮説:
  - 「逃げ20.8% / 先行8.6% / 差し / 追込1.9%」（先行絶対有利）
  - ただし「2023年以降1-2枠×追込が約4倍に台頭」（年代非定常性）

検証軸:
  1. 全体集計（脚質4象限別 出走/勝率/3着内率/単勝ROI）
  2. 年代別比較（前期 vs 後期）
  3. 枠順×脚質クロス（外枠×先行 vs 内枠×追込 など）
  4. 馬場状態×脚質
  5. 連続値での脚質×3着内率の関係（pre_2f_dev、last_3f_dev単体）
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.niigata1000 import load_dataset


REPORT_PATH = Path(
    "C:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2/docs/ml-experiments/"
    "v8.x_vega_niigata1000_phase1_verification.md"
)
CSV_DIR = REPORT_PATH.parent / "v8.x_vega_niigata1000_phase1_data"


def beta_ci(success: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    a = success + 1
    b = total - success + 1
    return (float(beta.ppf(alpha / 2, a, b)), float(beta.ppf(1 - alpha / 2, a, b)))


def aggregate(df: pd.DataFrame, group_col) -> pd.DataFrame:
    grouped = df.groupby(group_col, dropna=False).agg(
        n=("is_win", "size"),
        wins=("is_win", "sum"),
        top3=("is_top3", "sum"),
        win_payoff=("win_payoff", "sum"),
    ).reset_index()
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


def add_running_style(df: pd.DataFrame) -> pd.DataFrame:
    """脚質指標カラムを追加"""
    df = df.copy()
    # 前半2F = 全体タイム - 上がり3F（last_3f が 0/None の馬は欠損）
    df["last_3f_valid"] = df["last_3f"].where(df["last_3f"].notna() & (df["last_3f"] > 0))
    df["pre_2f"] = df["time_sec"] - df["last_3f_valid"]

    # race 内偏差
    df["pre_2f_race_mean"] = df.groupby("race_id")["pre_2f"].transform("mean")
    df["last_3f_race_mean"] = df.groupby("race_id")["last_3f_valid"].transform("mean")
    df["pre_2f_dev"] = df["pre_2f"] - df["pre_2f_race_mean"]  # 負=テン速い
    df["last_3f_dev"] = df["last_3f_valid"] - df["last_3f_race_mean"]  # 負=上がり速い

    # 4象限分類（中央値で分割）
    def classify(row):
        p, l = row["pre_2f_dev"], row["last_3f_dev"]
        if pd.isna(p) or pd.isna(l):
            return "不明"
        # 厳密中央値ではなく0で分割（race平均に対する位置）
        if p < 0 and l < 0:
            return "①テン速＆末脚速（強馬）"
        if p < 0 and l >= 0:
            return "②テン速＆末脚遅（先行・逃げ）"
        if p >= 0 and l < 0:
            return "③テン遅＆末脚速（差し・追込）"
        return "④テン遅＆末脚遅（凡走）"

    df["running_style"] = df.apply(classify, axis=1)
    return df


def quartile_split(df: pd.DataFrame, col: str, label_prefix: str) -> pd.DataFrame:
    """連続値カラムを四分位で分割して集計"""
    df2 = df.copy()
    valid = df2[df2[col].notna()].copy()
    if len(valid) == 0:
        return pd.DataFrame()
    quartiles = pd.qcut(valid[col], q=4, labels=[
        f"Q1（{label_prefix}最速）",
        f"Q2（{label_prefix}速）",
        f"Q3（{label_prefix}遅）",
        f"Q4（{label_prefix}最遅）",
    ], duplicates="drop")
    valid["quartile"] = quartiles
    return aggregate(valid, "quartile")


def main() -> None:
    print("Loading dataset...")
    ds = load_dataset()
    df = ds.horses
    df = df[df["finish_position"].notna()].copy()
    print(f"Loaded: {len(df)}走")

    # 脚質追加
    df = add_running_style(df)
    valid_style = df[df["running_style"] != "不明"].copy()
    print(f"With valid running style: {len(valid_style)}走 / {len(df)}走")

    CSV_DIR.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # 1. 全体集計（脚質4象限別）
    overall = aggregate(valid_style, "running_style")
    # ソート順: ①〜④
    style_order = [
        "①テン速＆末脚速（強馬）",
        "②テン速＆末脚遅（先行・逃げ）",
        "③テン遅＆末脚速（差し・追込）",
        "④テン遅＆末脚遅（凡走）",
    ]
    overall["_ord"] = overall["running_style"].apply(lambda x: style_order.index(x) if x in style_order else 99)
    overall = overall.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    overall.to_csv(CSV_DIR / "02_running_style_overall.csv", index=False, encoding="utf-8-sig")

    sections.append("### 1. 脚質4象限別（全体）")
    sections.append(f"\n対象: {valid_style['race_id'].nunique()}R, {len(valid_style)}走\n")
    sections.append(fmt_table(overall.rename(columns={"running_style": "脚質"}), "脚質"))

    # 2. 連続値での脚質分析
    sections.append("\n\n### 2. 連続値分析")
    sections.append("\n#### 前半2F偏差（テン速さ、四分位）")
    pre_q = quartile_split(valid_style, "pre_2f_dev", "テン")
    if not pre_q.empty:
        sections.append(fmt_table(pre_q.rename(columns={"quartile": "前半2F偏差"}), "前半2F偏差"))

    sections.append("\n#### 上がり3F偏差（末脚、四分位）")
    last_q = quartile_split(valid_style, "last_3f_dev", "上がり")
    if not last_q.empty:
        sections.append(fmt_table(last_q.rename(columns={"quartile": "上がり3F偏差"}), "上がり3F偏差"))

    # 3. 年代別比較
    sections.append("\n\n### 3. 年代別比較")
    for era_label, year_range in [("2020-2022", (2020, 2022)), ("2023-2026", (2023, 2026))]:
        sub = valid_style[valid_style["year"].between(*year_range)]
        sub_agg = aggregate(sub, "running_style")
        sub_agg["_ord"] = sub_agg["running_style"].apply(lambda x: style_order.index(x) if x in style_order else 99)
        sub_agg = sub_agg.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
        sections.append(f"\n#### {era_label}（{sub['race_id'].nunique()}R, {len(sub)}走）")
        sections.append(fmt_table(sub_agg.rename(columns={"running_style": "脚質"}), "脚質"))

    # 4. 枠×脚質クロス
    sections.append("\n\n### 4. 枠×脚質クロス")
    valid_style["frame_grp"] = valid_style["wakuban"].apply(
        lambda w: "1-5枠（内）" if w in (1, 2, 3, 4, 5) else "6-8枠（外）"
    )
    cross = valid_style.groupby(["frame_grp", "running_style"], dropna=False).agg(
        n=("is_win", "size"),
        wins=("is_win", "sum"),
        top3=("is_top3", "sum"),
        roi_total=("win_payoff", "sum"),
    ).reset_index()
    cross["win_rate"] = cross["wins"] / cross["n"]
    cross["top3_rate"] = cross["top3"] / cross["n"]
    cross["win_roi"] = cross["roi_total"] / (cross["n"] * 100.0)

    cross["_ord"] = cross["running_style"].apply(lambda x: style_order.index(x) if x in style_order else 99)
    cross = cross.sort_values(["frame_grp", "_ord"]).drop(columns="_ord")
    cross.to_csv(CSV_DIR / "02_frame_x_style.csv", index=False, encoding="utf-8-sig")

    cross_lines = [
        "| 枠グループ | 脚質 | 出走 | 勝 | 3着内 | 勝率 | 3着内率 | 単勝ROI |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in cross.iterrows():
        cross_lines.append(
            f"| {r['frame_grp']} | {r['running_style']} | {int(r['n'])} | "
            f"{int(r['wins'])} | {int(r['top3'])} | "
            f"{r['win_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(cross_lines))

    # 5. 馬場×脚質クロス
    sections.append("\n\n### 5. 馬場状態×脚質クロス")
    valid_style["baba_grp"] = valid_style["track_condition"].apply(
        lambda x: "良" if x == "良" else "稍重以上"
    )
    cross_b = valid_style.groupby(["baba_grp", "running_style"], dropna=False).agg(
        n=("is_win", "size"),
        wins=("is_win", "sum"),
        top3=("is_top3", "sum"),
        roi_total=("win_payoff", "sum"),
    ).reset_index()
    cross_b["win_rate"] = cross_b["wins"] / cross_b["n"]
    cross_b["top3_rate"] = cross_b["top3"] / cross_b["n"]
    cross_b["win_roi"] = cross_b["roi_total"] / (cross_b["n"] * 100.0)
    cross_b["_ord"] = cross_b["running_style"].apply(lambda x: style_order.index(x) if x in style_order else 99)
    cross_b = cross_b.sort_values(["baba_grp", "_ord"]).drop(columns="_ord")

    bb_lines = [
        "| 馬場 | 脚質 | 出走 | 勝 | 3着内 | 勝率 | 3着内率 | 単勝ROI |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in cross_b.iterrows():
        bb_lines.append(
            f"| {r['baba_grp']} | {r['running_style']} | {int(r['n'])} | "
            f"{int(r['wins'])} | {int(r['top3'])} | "
            f"{r['win_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(bb_lines))

    # 6. 結論
    style_top3 = dict(zip(overall["running_style"], overall["top3_rate"]))
    sections.append("\n\n### 6. 結論サマリ")
    sections.append("- **脚質4象限別 3着内率**:")
    for s in style_order:
        if s in style_top3:
            sections.append(f"  - {s}: {style_top3[s]*100:.1f}%")
    sections.append("- **特徴量化候補**:")
    sections.append("  - `pre_2f_dev`: 前半2F偏差（連続値、テン速さの定量化）")
    sections.append("  - `last_3f_dev`: 上がり3F偏差（連続値、末脚の定量化）")
    sections.append("  - `running_style_4q`: 4象限カテゴリ")
    sections.append("  - `pre_2f_dev × frame_outer`: 外枠先行馬の交互作用")
    sections.append(
        "- ⚠️ **注意**: 千直での脚質はレース内ペース後だしジャンケン的なため、"
        "「予想時に使える脚質特徴量」としては馬の過去走脚質傾向（KYI予想脚質や過去走通過順位）を別途用意する必要あり。"
        "本検証は「結果として速かった脚質パターン」の同定であり、予測モデルへの直接投入は不可。"
    )

    # ===== レポート出力 =====
    section_body = (
        "## 検証② 脚質・展開（直線レース版）\n\n"
        "**対象仮説**:\n"
        "- 「逃げ20.8% / 先行8.6% / 差し / 追込1.9%」(Web調査 H59)\n"
        "- 千直は corner なしのため、`pre_2f = time_sec - last_3f` と `last_3f` を race内偏差化して4象限分類\n\n"
        + "\n".join(sections)
        + "\n\n---\n\n"
    )

    existing = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else ""
    marker = "## 検証② 脚質・展開"
    next_markers = ["## 検証③", "## 検証④", "## 検証⑤", "## 検証⑥"]

    if marker in existing:
        start = existing.index(marker)
        end = len(existing)
        for nm in next_markers:
            idx = existing.find(nm, start + 1)
            if idx != -1 and idx < end:
                end = idx
        new_content = existing[:start] + section_body + existing[end:]
        REPORT_PATH.write_text(new_content, encoding="utf-8")
    else:
        REPORT_PATH.write_text(existing + section_body, encoding="utf-8")

    print(f"\nReport written: {REPORT_PATH}")


if __name__ == "__main__":
    main()

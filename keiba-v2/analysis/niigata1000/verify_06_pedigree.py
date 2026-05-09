"""新潟千直 Phase 1 検証⑥ 血統

仮説:
  - 父サンデー系×牡馬は壊滅（アイビスSDで0-2-1-25、特に父サンデー×牡は0-1-0-14）
  - 千直適性血統あり（パシフィカス系/ストームキャット系/サクラユタカオー系等）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.niigata1000 import load_dataset
from analysis.niigata1000._helpers import (
    add_running_style,
    aggregate_with_strong,
    fmt_table_with_strong,
    upsert_section,
    attach_pedigree,
    CSV_DIR,
)


def main() -> None:
    print("Loading dataset...")
    ds = load_dataset()
    df = ds.horses
    df = df[df["finish_position"].notna()].copy()
    df = add_running_style(df)
    print(f"Dataset: {len(df)}走")

    print("Attaching pedigree...")
    df = attach_pedigree(df)
    sex_label = {"1": "牡", "2": "牝", "3": "セン"}
    df["sex_label"] = df["sex_cd"].map(sex_label).fillna("不明")
    print("  done")

    sections: list[str] = []

    # 1. 父系統別
    sections.append("### 1. 父系統別")
    line_agg = aggregate_with_strong(df, "sire_line")
    line_agg = line_agg.sort_values("n", ascending=False).reset_index(drop=True)
    line_agg.to_csv(CSV_DIR / "06_sire_line.csv", index=False, encoding="utf-8-sig")
    sections.append(fmt_table_with_strong(line_agg.rename(columns={"sire_line": "父系統"}), "父系統"))

    # 2. 父系統×性別
    sections.append("\n\n### 2. 父系統×性別クロス（H父サンデー×牡馬壊滅仮説検証）")
    cross = df.groupby(["sire_line", "sex_label"], dropna=False).agg(
        n=("is_win", "size"),
        wins=("is_win", "sum"),
        top3=("is_top3", "sum"),
        strong=("is_strong_horse", "sum"),
        roi_total=("win_payoff", "sum"),
    ).reset_index()
    cross["win_rate"] = cross["wins"] / cross["n"]
    cross["top3_rate"] = cross["top3"] / cross["n"]
    cross["strong_rate"] = cross["strong"] / cross["n"]
    cross["win_roi"] = cross["roi_total"] / (cross["n"] * 100.0)
    cross = cross[cross["n"] >= 30]  # サンプル少すぎ除外
    cross = cross.sort_values(["sire_line", "sex_label"]).reset_index(drop=True)

    cross_lines = [
        "| 父系統 | 性別 | 出走 | 勝 | 3着内 | 強馬 | 勝率 | 3着内率 | 強馬率 | 単勝ROI |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in cross.iterrows():
        cross_lines.append(
            f"| {r['sire_line']} | {r['sex_label']} | {int(r['n'])} | "
            f"{int(r['wins'])} | {int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['strong_rate']*100:.1f}% | {r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(cross_lines))

    # 3. 個別父馬ランキング（出走30以上）
    sections.append("\n\n### 3. 個別父馬ランキング（出走30以上、3着内率順）")
    sire_agg = aggregate_with_strong(df, "sire_name")
    sire_agg = sire_agg[sire_agg["n"] >= 30].copy()
    sire_agg = sire_agg.sort_values("top3_rate", ascending=False).reset_index(drop=True)
    sire_agg.head(20).to_csv(CSV_DIR / "06_sire_ranking.csv", index=False, encoding="utf-8-sig")

    # 上位15
    sire_lines = [
        "| 父馬 | 出走 | 勝 | 3着内 | 強馬 | 勝率 | 3着内率 | 強馬率 | 単勝ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in sire_agg.head(15).iterrows():
        sire_lines.append(
            f"| {r['sire_name']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['strong_rate']*100:.1f}% | {r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(sire_lines))

    # 4. 単勝ROI上位の父馬
    sections.append("\n\n### 4. 単勝ROI 上位父馬（出走30以上、ROI高い順）")
    sire_roi = sire_agg.sort_values("win_roi", ascending=False).head(10)
    roi_lines = [
        "| 父馬 | 出走 | 勝 | 3着内 | 単勝ROI | 3着内率 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in sire_roi.iterrows():
        roi_lines.append(
            f"| {r['sire_name']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | "
            f"{r['win_roi']*100:.1f}% | {r['top3_rate']*100:.1f}% |"
        )
    sections.append("\n".join(roi_lines))

    # 5. 母父系統別
    sections.append("\n\n### 5. 母父系統別")
    bms_line_agg = aggregate_with_strong(df, "bms_line")
    bms_line_agg = bms_line_agg.sort_values("n", ascending=False).reset_index(drop=True)
    sections.append(fmt_table_with_strong(bms_line_agg.rename(columns={"bms_line": "母父系統"}), "母父系統"))

    # 6. 父サンデー×牡馬詳細（H仮説検証）
    sections.append("\n\n### 6. 父サンデー系×牡馬の詳細（仮説検証）")
    sun_male = df[(df["sire_line"] == "サンデー系") & (df["sex_label"] == "牡")]
    sun_male_agg_total = {
        "n": len(sun_male),
        "wins": int(sun_male["is_win"].sum()),
        "top3": int(sun_male["is_top3"].sum()),
        "strong": int(sun_male["is_strong_horse"].sum()),
    }
    sections.append(
        f"\n父サンデー系×牡馬: 出走 {sun_male_agg_total['n']}, "
        f"勝 {sun_male_agg_total['wins']}, "
        f"3着内 {sun_male_agg_total['top3']}, "
        f"強馬 {sun_male_agg_total['strong']}"
    )
    if sun_male_agg_total["n"] > 0:
        win_rate = sun_male_agg_total["wins"] / sun_male_agg_total["n"]
        top3_rate = sun_male_agg_total["top3"] / sun_male_agg_total["n"]
        sections.append(
            f"勝率: {win_rate*100:.1f}%, 3着内率: {top3_rate*100:.1f}%"
        )
        # アイビスSDのみ
        sun_male_aibis = sun_male[sun_male["race_name"].str.contains("アイビス", na=False)]
        sections.append(
            f"\nアイビスSDのみ: 出走 {len(sun_male_aibis)}, "
            f"勝 {int(sun_male_aibis['is_win'].sum())}, "
            f"3着内 {int(sun_male_aibis['is_top3'].sum())}"
        )

    # 7. 結論
    sections.append("\n\n### 7. 結論サマリ")
    sections.append("- **父系統別 3着内率**:")
    for _, r in line_agg.iterrows():
        sections.append(f"  - {r['sire_line']}: {r['top3_rate']*100:.1f}% ({int(r['n'])}走)")
    sections.append("- **特徴量化候補**:")
    sections.append("  - `sire_line`: 父系統カテゴリ")
    sections.append("  - `is_sunday_sire`: サンデー系フラグ")
    sections.append("  - `sire_name`: 個別父馬（重要そうな父のみOne-hot）")
    sections.append("  - `bms_line`: 母父系統")
    sections.append("  - `sire_x_sex`: 父系統×性別の交互作用")

    section_body = (
        "## 検証⑥ 血統\n\n"
        "**対象仮説**:\n"
        "- 父サンデー系×牡馬は壊滅（アイビスSDで0-2-1-25）\n"
        "- 千直適性血統がある（特定父系・母父系）\n\n"
        + "\n".join(sections)
        + "\n\n---\n\n"
    )

    upsert_section(
        "## 検証⑥ 血統",
        section_body,
        ["## 検証⑦", "## 検証⑧"],
    )
    print("Section ⑥ written")


if __name__ == "__main__":
    main()

"""新潟千直 Phase 1 検証③ 性別バイアス

仮説:
  - 牝馬有利、特に近年。アイビスSDで牝馬13勝/牡馬7勝、2020年から牝馬5連勝
  - 父サンデー系×牡馬は壊滅（0-1-0-14）
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
    CSV_DIR,
)

SEX_LABELS = {"1": "牡", "2": "牝", "3": "セン"}


def main() -> None:
    print("Loading dataset...")
    ds = load_dataset()
    df = ds.horses
    df = df[df["finish_position"].notna()].copy()
    df = add_running_style(df)
    df["sex_label"] = df["sex_cd"].map(SEX_LABELS).fillna("不明")
    print(f"Loaded: {len(df)}走")

    CSV_DIR.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []

    # 1. 全体集計
    overall = aggregate_with_strong(df, "sex_label")
    overall.to_csv(CSV_DIR / "03_sex_overall.csv", index=False, encoding="utf-8-sig")
    sections.append("### 1. 全体集計（性別）")
    sections.append(f"\n対象: {df['race_id'].nunique()}R, {len(df)}走\n")
    sections.append(fmt_table_with_strong(overall.rename(columns={"sex_label": "性別"}), "性別"))

    # 2. 年代別
    sections.append("\n\n### 2. 年代別比較")
    for era_label, year_range in [("2020-2022", (2020, 2022)), ("2023-2026", (2023, 2026))]:
        sub = df[df["year"].between(*year_range)]
        sub_agg = aggregate_with_strong(sub, "sex_label")
        sections.append(f"\n#### {era_label}（{sub['race_id'].nunique()}R, {len(sub)}走）")
        sections.append(fmt_table_with_strong(sub_agg.rename(columns={"sex_label": "性別"}), "性別"))

    # 3. 性別×枠順クロス
    sections.append("\n\n### 3. 性別×枠グループクロス")
    df["frame_grp"] = df["wakuban"].apply(
        lambda w: "1-5枠（内）" if w in (1, 2, 3, 4, 5) else "6-8枠（外）"
    )
    cross = df.groupby(["sex_label", "frame_grp"], dropna=False).agg(
        n=("is_win", "size"),
        wins=("is_win", "sum"),
        top3=("is_top3", "sum"),
        strong=("is_strong_horse", "sum"),
        win_payoff=("win_payoff", "sum"),
    ).reset_index()
    cross["win_rate"] = cross["wins"] / cross["n"]
    cross["top3_rate"] = cross["top3"] / cross["n"]
    cross["strong_rate"] = cross["strong"] / cross["n"]
    cross["win_roi"] = cross["win_payoff"] / (cross["n"] * 100.0)

    cross_lines = [
        "| 性別 | 枠グループ | 出走 | 勝 | 3着内 | 強馬 | 勝率 | 3着内率 | 強馬率 | 単勝ROI |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in cross.iterrows():
        cross_lines.append(
            f"| {r['sex_label']} | {r['frame_grp']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['strong_rate']*100:.1f}% | {r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(cross_lines))

    # 4. 牝馬限定戦の影響を排除した分析
    sections.append("\n\n### 4. 牝馬限定戦の影響排除（混合戦のみ）")
    open_sex = df[~df["is_female_only"]].copy()
    open_agg = aggregate_with_strong(open_sex, "sex_label")
    sections.append(
        f"\n対象（牝馬限定戦除外）: {open_sex['race_id'].nunique()}R, {len(open_sex)}走\n"
    )
    sections.append(fmt_table_with_strong(open_agg.rename(columns={"sex_label": "性別"}), "性別"))

    # 5. 年齢別×性別（若駒×牝馬か古馬×牡馬か）
    sections.append("\n\n### 5. 年齢×性別クロス")
    df["age_grp"] = df["age"].apply(
        lambda a: "2歳" if a == 2 else ("3歳" if a == 3 else ("4-5歳" if a in (4, 5) else "6歳以上") if a is not None else "不明")
    )
    age_sex = df.groupby(["age_grp", "sex_label"], dropna=False).agg(
        n=("is_win", "size"),
        top3=("is_top3", "sum"),
        strong=("is_strong_horse", "sum"),
        win_payoff=("win_payoff", "sum"),
    ).reset_index()
    age_sex["top3_rate"] = age_sex["top3"] / age_sex["n"]
    age_sex["strong_rate"] = age_sex["strong"] / age_sex["n"]
    age_sex["win_roi"] = age_sex["win_payoff"] / (age_sex["n"] * 100.0)

    age_lines = [
        "| 年齢 | 性別 | 出走 | 3着内 | 強馬 | 3着内率 | 強馬率 | 単勝ROI |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in age_sex.iterrows():
        if r["n"] < 20:  # サンプル少すぎは除外
            continue
        age_lines.append(
            f"| {r['age_grp']} | {r['sex_label']} | {int(r['n'])} | "
            f"{int(r['top3'])} | {int(r['strong'])} | "
            f"{r['top3_rate']*100:.1f}% | {r['strong_rate']*100:.1f}% | "
            f"{r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(age_lines))

    # 6. 結論
    sections.append("\n\n### 6. 結論サマリ")
    sex_top3 = dict(zip(overall["sex_label"], overall["top3_rate"]))
    sex_roi = dict(zip(overall["sex_label"], overall["win_roi"]))
    sex_strong = dict(zip(overall["sex_label"], overall["strong_rate"]))
    for s in ["牡", "牝", "セン"]:
        if s in sex_top3:
            sections.append(
                f"- {s}: 3着内率 {sex_top3[s]*100:.1f}%, "
                f"強馬率 {sex_strong[s]*100:.1f}%, "
                f"単勝ROI {sex_roi[s]*100:.1f}%"
            )
    sections.append("- **特徴量化候補**:")
    sections.append("  - `is_mare` （牝馬フラグ）")
    sections.append("  - `sex × age` クロス（若い牝馬の優位）")
    sections.append("  - `sex × frame_outer` （外枠×牝馬の追い風）")

    section_body = (
        "## 検証③ 性別バイアス\n\n"
        "**対象仮説**:\n"
        "- 牝馬有利（アイビスSD牝馬13勝/牡馬7勝、2020年から牝馬5連勝）\n"
        "- 父サンデー系×牡馬は壊滅（次の検証⑥で確認）\n\n"
        + "\n".join(sections)
        + "\n\n---\n\n"
    )

    upsert_section(
        "## 検証③ 性別バイアス",
        section_body,
        ["## 検証④", "## 検証⑤", "## 検証⑥"],
    )
    print(f"Section ③ written")


if __name__ == "__main__":
    main()

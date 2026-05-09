"""新潟千直 Phase 1 検証⑦ 騎手・厩舎

仮説:
  - 永島まなみ単勝回収率544%
  - 菊沢親子コンビ（菊沢隆徳厩舎×菊沢一樹騎手）複勝率50%超
  - 千直巧者騎手・厩舎が存在
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


def main() -> None:
    print("Loading dataset...")
    ds = load_dataset()
    df = ds.horses
    df = df[df["finish_position"].notna()].copy()
    df = add_running_style(df)
    print(f"Dataset: {len(df)}走")

    sections: list[str] = []

    # ========================================
    # 1. 騎手ランキング
    # ========================================
    sections.append("### 1. 騎手別（3着内率順、出走20以上）")
    jockey_agg = aggregate_with_strong(df, "jockey_name")
    jockey_agg_20 = jockey_agg[jockey_agg["n"] >= 20].copy()
    jockey_agg_20 = jockey_agg_20.sort_values("top3_rate", ascending=False).reset_index(drop=True)
    jockey_agg_20.head(20).to_csv(CSV_DIR / "07_jockey_top3.csv", index=False, encoding="utf-8-sig")

    j_lines = [
        "| 騎手 | 出走 | 勝 | 3着内 | 強馬 | 勝率 | 3着内率 | 強馬率 | 単勝ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in jockey_agg_20.head(15).iterrows():
        j_lines.append(
            f"| {r['jockey_name']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['strong_rate']*100:.1f}% | {r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(j_lines))

    # 2. 騎手ROIランキング
    sections.append("\n\n### 2. 騎手ROIランキング（出走15以上、ROI高順）")
    jockey_agg_15 = jockey_agg[jockey_agg["n"] >= 15].sort_values("win_roi", ascending=False).head(10)
    j_roi_lines = [
        "| 騎手 | 出走 | 勝 | 3着内 | 強馬 | 単勝ROI | 3着内率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in jockey_agg_15.iterrows():
        j_roi_lines.append(
            f"| {r['jockey_name']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_roi']*100:.1f}% | {r['top3_rate']*100:.1f}% |"
        )
    sections.append("\n".join(j_roi_lines))

    # 3. 永島まなみ個別検証
    sections.append("\n\n### 3. 永島まなみ個別検証（H：単勝回収率544%仮説）")
    nagashima = df[df["jockey_name"].str.contains("永島", na=False)]
    if len(nagashima) > 0:
        n = len(nagashima)
        wins = int(nagashima["is_win"].sum())
        top3 = int(nagashima["is_top3"].sum())
        roi = nagashima["win_payoff"].sum() / (n * 100.0) * 100
        sections.append(
            f"\n出走: {n}, 勝: {wins}, 3着内: {top3}, "
            f"勝率: {wins/n*100:.1f}%, 3着内率: {top3/n*100:.1f}%, "
            f"単勝ROI: {roi:.1f}%"
        )
        # 年代別
        for era_label, year_range in [("2020-2022", (2020, 2022)), ("2023-2026", (2023, 2026))]:
            sub = nagashima[nagashima["year"].between(*year_range)]
            if len(sub) > 0:
                roi_sub = sub["win_payoff"].sum() / (len(sub) * 100.0) * 100
                sections.append(
                    f"  - {era_label}: 出走 {len(sub)}, 勝 {int(sub['is_win'].sum())}, "
                    f"ROI {roi_sub:.1f}%"
                )
    else:
        sections.append("永島騎手の千直騎乗データなし")

    # ========================================
    # 4. 厩舎ランキング
    # ========================================
    sections.append("\n\n### 4. 厩舎別（3着内率順、出走15以上）")
    trainer_agg = aggregate_with_strong(df, "trainer_name")
    trainer_15 = trainer_agg[trainer_agg["n"] >= 15].copy()
    trainer_15 = trainer_15.sort_values("top3_rate", ascending=False).reset_index(drop=True)
    trainer_15.head(20).to_csv(CSV_DIR / "07_trainer_top3.csv", index=False, encoding="utf-8-sig")

    t_lines = [
        "| 厩舎 | 出走 | 勝 | 3着内 | 強馬 | 勝率 | 3着内率 | 強馬率 | 単勝ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in trainer_15.head(15).iterrows():
        t_lines.append(
            f"| {r['trainer_name']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['strong_rate']*100:.1f}% | {r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(t_lines))

    # 5. 厩舎ROIランキング
    sections.append("\n\n### 5. 厩舎ROIランキング（出走10以上、ROI高順）")
    trainer_10 = trainer_agg[trainer_agg["n"] >= 10].sort_values("win_roi", ascending=False).head(10)
    t_roi_lines = [
        "| 厩舎 | 出走 | 勝 | 3着内 | 強馬 | 単勝ROI | 3着内率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in trainer_10.iterrows():
        t_roi_lines.append(
            f"| {r['trainer_name']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_roi']*100:.1f}% | {r['top3_rate']*100:.1f}% |"
        )
    sections.append("\n".join(t_roi_lines))

    # 6. 菊沢親子コンビ個別検証
    sections.append("\n\n### 6. 菊沢親子コンビ検証（H：複勝率50%超仮説）")
    kikusawa_combo = df[
        df["trainer_name"].str.contains("菊沢", na=False)
        & df["jockey_name"].str.contains("菊沢", na=False)
    ]
    if len(kikusawa_combo) > 0:
        n = len(kikusawa_combo)
        wins = int(kikusawa_combo["is_win"].sum())
        top3 = int(kikusawa_combo["is_top3"].sum())
        roi = kikusawa_combo["win_payoff"].sum() / (n * 100.0) * 100
        sections.append(
            f"\n菊沢厩舎×菊沢騎手コンビ: 出走 {n}, 勝 {wins}, 3着内 {top3}\n"
            f"勝率 {wins/n*100:.1f}%, 3着内率 {top3/n*100:.1f}%, 単勝ROI {roi:.1f}%"
        )
    else:
        sections.append("菊沢親子コンビの千直データなし")

    # 厩舎単独
    kikusawa_t = df[df["trainer_name"].str.contains("菊沢", na=False)]
    if len(kikusawa_t) > 0:
        t_count = kikusawa_t["trainer_name"].value_counts().to_dict()
        sections.append(f"\n菊沢系厩舎の千直出走分布: {t_count}")

    # ========================================
    # 7. 騎手×外枠クロス（外枠を活かす騎手）
    # ========================================
    sections.append("\n\n### 7. 騎手×外枠（出走10以上、外枠ROI高順）")
    df["frame_grp"] = df["wakuban"].apply(
        lambda w: "外枠（6-8）" if w in (6, 7, 8) else "内枠（1-5）"
    )
    outer = df[df["frame_grp"] == "外枠（6-8）"]
    outer_jock = aggregate_with_strong(outer, "jockey_name")
    outer_jock = outer_jock[outer_jock["n"] >= 10].sort_values("win_roi", ascending=False).head(10)
    o_lines = [
        "| 騎手 | 外枠出走 | 勝 | 3着内 | 単勝ROI | 3着内率 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in outer_jock.iterrows():
        o_lines.append(
            f"| {r['jockey_name']} | {int(r['n'])} | {int(r['wins'])} | "
            f"{int(r['top3'])} | "
            f"{r['win_roi']*100:.1f}% | {r['top3_rate']*100:.1f}% |"
        )
    sections.append("\n".join(o_lines))

    # ========================================
    # 8. 結論
    # ========================================
    sections.append("\n\n### 8. 結論サマリ")
    if len(jockey_agg_20) > 0:
        top_jock = jockey_agg_20.iloc[0]
        sections.append(f"- **千直巧者騎手TOP**: {top_jock['jockey_name']} - 3着内 {top_jock['top3_rate']*100:.1f}% ({int(top_jock['n'])}走)")
    if len(trainer_15) > 0:
        top_trn = trainer_15.iloc[0]
        sections.append(f"- **千直巧者厩舎TOP**: {top_trn['trainer_name']} - 3着内 {top_trn['top3_rate']*100:.1f}% ({int(top_trn['n'])}走)")
    sections.append("- **特徴量化候補**:")
    sections.append("  - `jockey_choku_top3_rate`: 騎手の千直3着内率（過去全レース、リーク注意）")
    sections.append("  - `jockey_choku_strong_rate`: 騎手の千直強馬率")
    sections.append("  - `trainer_choku_top3_rate`: 厩舎の千直3着内率")
    sections.append("  - `is_choku_kichou_combo`: 千直得意騎手×千直得意厩舎フラグ")
    sections.append("  - 個別騎手・厩舎のOne-hotは過学習リスク高、平滑化レートで使うのが安全")

    section_body = (
        "## 検証⑦ 騎手・厩舎\n\n"
        "**対象仮説**:\n"
        "- 永島まなみ単勝回収率544%\n"
        "- 菊沢親子コンビ（菊沢隆徳厩舎×菊沢一樹騎手）複勝率50%超\n"
        "- 千直巧者騎手・厩舎が存在\n\n"
        + "\n".join(sections)
        + "\n\n---\n\n"
    )

    upsert_section(
        "## 検証⑦ 騎手・厩舎",
        section_body,
        ["## 検証⑧", "## Phase 1 最終結論"],
    )
    print("Section ⑦ written")


if __name__ == "__main__":
    main()

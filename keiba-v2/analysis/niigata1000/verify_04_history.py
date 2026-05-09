"""新潟千直 Phase 1 検証④⑤ 過去走履歴

検証④ 前走距離:
  H44: アイビスSD3着以内30頭中29頭が前走1000-1200m
  → 前走距離別の3着内率/強馬率/ROI

検証⑤ 千直リピーター:
  - 過去の新潟芝1000m 経験回数 vs 3着内率/強馬率
  - 初千直の壁検証
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
    attach_past_info,
    load_history_cache,
    CSV_DIR,
)


def prev_distance_bucket(d) -> str:
    if pd.isna(d) or d is None:
        return "前走なし"
    d = int(d)
    if d <= 1000:
        return "1000m"
    if d <= 1200:
        return "1100-1200m"
    if d <= 1400:
        return "1300-1400m"
    if d <= 1600:
        return "1500-1600m"
    return "1700m+"


def main() -> None:
    print("Loading dataset...")
    ds = load_dataset()
    df = ds.horses
    df = df[df["finish_position"].notna()].copy()
    df = add_running_style(df)
    print(f"Dataset: {len(df)}走")

    print("Loading history cache...")
    cache = load_history_cache()
    print(f"  {len(cache)} horses in cache")

    print("Attaching past info...")
    df = attach_past_info(df, cache)
    print("  done")

    df["prev_dist_bucket"] = df["prev_distance"].apply(prev_distance_bucket)

    sections: list[str] = []
    sections.append("### 1. 前走距離別（検証④）")

    # 1. 前走距離別の集計
    overall = aggregate_with_strong(df, "prev_dist_bucket")
    bucket_order = ["1000m", "1100-1200m", "1300-1400m", "1500-1600m", "1700m+", "前走なし"]
    overall["_ord"] = overall["prev_dist_bucket"].apply(
        lambda x: bucket_order.index(x) if x in bucket_order else 99
    )
    overall = overall.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    overall.to_csv(CSV_DIR / "04_prev_distance.csv", index=False, encoding="utf-8-sig")

    sections.append(f"\n対象: {df['race_id'].nunique()}R, {len(df)}走\n")
    sections.append(fmt_table_with_strong(overall.rename(columns={"prev_dist_bucket": "前走距離"}), "前走距離"))

    # 短距離前走（1000-1200m）vs それ以外
    sections.append("\n#### 短距離前走（1000-1200m）vs それ以外")
    df["prev_short"] = df["prev_dist_bucket"].apply(
        lambda x: "1000-1200m" if x in ("1000m", "1100-1200m") else (
            "前走なし" if x == "前走なし" else "1300m+"
        )
    )
    short_agg = aggregate_with_strong(df, "prev_short")
    sections.append(fmt_table_with_strong(short_agg.rename(columns={"prev_short": "前走距離区分"}), "前走距離区分"))

    # 2. アイビスSD（OPの新潟1000m G3）個別検証
    sections.append("\n\n### 2. アイビスSD個別検証（H44）")
    # アイビスSDは 7-8月の重賞、grade=G3、新潟2回目以降
    # race_name で抽出
    aibis = df[df["race_name"].str.contains("アイビス", na=False)]
    if len(aibis) > 0:
        sections.append(f"アイビスSD出走: {aibis['race_id'].nunique()}R, {len(aibis)}走")
        # 3着内馬の前走距離
        top3_aibis = aibis[aibis["is_top3"]]
        if len(top3_aibis) > 0:
            dist_dist = top3_aibis["prev_dist_bucket"].value_counts()
            sections.append("\n**3着内馬の前走距離分布**:\n")
            sections.append("| 前走距離 | 該当頭数 |")
            sections.append("|---|---:|")
            for k, v in dist_dist.items():
                sections.append(f"| {k} | {v} |")
            short_count = sum(1 for x in top3_aibis["prev_dist_bucket"] if x in ("1000m", "1100-1200m"))
            sections.append(
                f"\n→ 前走1000-1200m: {short_count}/{len(top3_aibis)}頭 "
                f"({short_count/len(top3_aibis)*100:.0f}%)"
            )

    # 3. 前走着順別
    sections.append("\n\n### 3. 前走着順別")
    df["prev_finish_bucket"] = df["prev_finish"].apply(
        lambda f: "前走なし" if pd.isna(f) or f is None else (
            "前走1着" if int(f) == 1 else (
                "前走2-3着" if 2 <= int(f) <= 3 else (
                    "前走4-5着" if 4 <= int(f) <= 5 else "前走6着以下"
                )
            )
        )
    )
    pf_agg = aggregate_with_strong(df, "prev_finish_bucket")
    pf_order = ["前走1着", "前走2-3着", "前走4-5着", "前走6着以下", "前走なし"]
    pf_agg["_ord"] = pf_agg["prev_finish_bucket"].apply(
        lambda x: pf_order.index(x) if x in pf_order else 99
    )
    pf_agg = pf_agg.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    sections.append(fmt_table_with_strong(pf_agg.rename(columns={"prev_finish_bucket": "前走着順"}), "前走着順"))

    # 4. 千直リピーター（検証⑤）
    sections.append("\n\n### 4. 千直リピーター（検証⑤）")
    df["choku_count_bucket"] = df["niigata_1000m_count"].apply(
        lambda c: "初千直" if c == 0 else (
            "2回目" if c == 1 else (
                "3-4回目" if 2 <= c <= 3 else "5回目以上"
            )
        )
    )
    choku_agg = aggregate_with_strong(df, "choku_count_bucket")
    choku_order = ["初千直", "2回目", "3-4回目", "5回目以上"]
    choku_agg["_ord"] = choku_agg["choku_count_bucket"].apply(
        lambda x: choku_order.index(x) if x in choku_order else 99
    )
    choku_agg = choku_agg.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    choku_agg.to_csv(CSV_DIR / "05_choku_repeater.csv", index=False, encoding="utf-8-sig")
    sections.append(fmt_table_with_strong(choku_agg.rename(columns={"choku_count_bucket": "千直経験"}), "千直経験"))

    # 5. 千直経験者の過去成績別
    sections.append("\n\n### 5. 千直経験者の過去3着内率別")
    rep_df = df[df["niigata_1000m_count"] > 0].copy()
    rep_df["past_choku_top3_bucket"] = rep_df["niigata_1000m_top3_rate"].apply(
        lambda r: "過去千直 3着内率0%" if r == 0 else (
            "過去千直 3着内率<33%" if r < 0.33 else (
                "過去千直 3着内率33-66%" if r < 0.66 else "過去千直 3着内率>=66%"
            )
        )
    )
    rep_agg = aggregate_with_strong(rep_df, "past_choku_top3_bucket")
    rep_order = ["過去千直 3着内率0%", "過去千直 3着内率<33%", "過去千直 3着内率33-66%", "過去千直 3着内率>=66%"]
    rep_agg["_ord"] = rep_agg["past_choku_top3_bucket"].apply(
        lambda x: rep_order.index(x) if x in rep_order else 99
    )
    rep_agg = rep_agg.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    sections.append(
        f"\n対象: 千直経験者のみ {rep_df['race_id'].nunique()}R, {len(rep_df)}走\n"
    )
    sections.append(fmt_table_with_strong(rep_agg.rename(columns={"past_choku_top3_bucket": "過去千直成績"}), "過去千直成績"))

    # 6. 中間隔（rest_days）
    sections.append("\n\n### 6. 前走間隔（rest_days）")
    def rest_bucket(d):
        if pd.isna(d) or d is None:
            return "前走なし"
        d = int(d)
        if d <= 14:
            return "中1-2週"
        if d <= 28:
            return "中3-4週"
        if d <= 56:
            return "中5-8週"
        if d <= 90:
            return "中9-12週"
        return "13週以上"

    df["rest_bucket"] = df["days_since_prev"].apply(rest_bucket)
    rest_agg = aggregate_with_strong(df, "rest_bucket")
    rest_order = ["中1-2週", "中3-4週", "中5-8週", "中9-12週", "13週以上", "前走なし"]
    rest_agg["_ord"] = rest_agg["rest_bucket"].apply(
        lambda x: rest_order.index(x) if x in rest_order else 99
    )
    rest_agg = rest_agg.sort_values("_ord").drop(columns="_ord").reset_index(drop=True)
    sections.append(fmt_table_with_strong(rest_agg.rename(columns={"rest_bucket": "前走間隔"}), "前走間隔"))

    # 7. 結論
    sections.append("\n\n### 7. 結論サマリ")
    short_top3 = short_agg.loc[short_agg["prev_short"] == "1000-1200m", "top3_rate"]
    long_top3 = short_agg.loc[short_agg["prev_short"] == "1300m+", "top3_rate"]
    if not short_top3.empty and not long_top3.empty:
        sections.append(
            f"- **前走短距離（1000-1200m）3着内率 {short_top3.iloc[0]*100:.1f}% "
            f"vs 1300m+ {long_top3.iloc[0]*100:.1f}%** "
            f"（差 {(short_top3.iloc[0]-long_top3.iloc[0])*100:+.1f}pt）"
        )
    if "初千直" in choku_agg["choku_count_bucket"].values:
        first_top3 = choku_agg.loc[choku_agg["choku_count_bucket"] == "初千直", "top3_rate"].iloc[0]
        sections.append(f"- **初千直 3着内率: {first_top3*100:.1f}%**")
    if "5回目以上" in choku_agg["choku_count_bucket"].values:
        rep5_top3 = choku_agg.loc[choku_agg["choku_count_bucket"] == "5回目以上", "top3_rate"].iloc[0]
        sections.append(f"- **5回目以上 3着内率: {rep5_top3*100:.1f}%**")

    sections.append("- **特徴量化候補**:")
    sections.append("  - `prev_distance` （連続値）")
    sections.append("  - `is_short_prev` （1000-1200m前走フラグ）")
    sections.append("  - `niigata_1000m_count` （千直経験回数）")
    sections.append("  - `niigata_1000m_top3_rate` （過去千直成績、5戦以上で平滑化）")
    sections.append("  - `is_first_choku` （初千直フラグ）")
    sections.append("  - `prev_finish` （前走着順）")
    sections.append("  - `days_since_prev` （前走間隔）")

    section_body = (
        "## 検証④⑤ 過去走履歴（前走距離・千直リピーター）\n\n"
        "**対象仮説**:\n"
        "- H44: アイビスSD3着以内30頭中29頭が前走1000-1200m\n"
        "- 千直経験馬は初千直より好走率高い（経験の壁）\n\n"
        + "\n".join(sections)
        + "\n\n---\n\n"
    )

    upsert_section(
        "## 検証④⑤ 過去走履歴",
        section_body,
        ["## 検証⑥", "## 検証⑦", "## 検証⑧"],
    )
    print("Section ④⑤ written")


if __name__ == "__main__":
    main()

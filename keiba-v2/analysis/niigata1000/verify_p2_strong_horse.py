"""新潟千直 Phase 2: 強馬の事前特徴量検証

ターゲットラベル: is_strong_horse（結果脚質①強馬かつ3着内）
ユーザー指示: 「結果として速かった馬につながる戦績や履歴・血統・調教師パターンを探す」

検証軸:
  ① 過去走脚質指標 × is_strong_horse
     - past_corner_first_avg_5（過去5走の前半通過順位）
     - past_last_3f_avg_5 / past_last_3f_min_5
     - past_short_avg_l3f（過去短距離の上がり3F）
  ② 父・厩舎・騎手 × 強馬率の交互作用詳細
  ③ 過去千直経験時のパフォーマンス × 今回強馬の関係
  ④ 統合: 「強馬になりやすい馬」の typical profile
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.niigata1000 import load_dataset
from analysis.niigata1000._helpers import (
    add_running_style,
    aggregate_with_strong,
    attach_pedigree,
    attach_past_running_style,
    fmt_table_with_strong,
    upsert_section,
    CSV_DIR,
    REPORT_PATH,
)


REPORT_PHASE2 = REPORT_PATH.parent / "v8.x_vega_niigata1000_phase2_strong_horse.md"


def quartile_split(df: pd.DataFrame, col: str, label_prefix: str = "") -> pd.DataFrame:
    df2 = df.copy()
    valid = df2[df2[col].notna()].copy()
    if len(valid) == 0:
        return pd.DataFrame()
    try:
        quartiles = pd.qcut(valid[col], q=4, labels=[
            f"Q1（{label_prefix}最小）",
            f"Q2",
            f"Q3",
            f"Q4（{label_prefix}最大）",
        ], duplicates="drop")
    except ValueError:
        return pd.DataFrame()
    valid["quartile"] = quartiles
    return aggregate_with_strong(valid, "quartile")


def main() -> None:
    print("Loading dataset...")
    ds = load_dataset()
    df = ds.horses
    df = df[df["finish_position"].notna()].copy()
    df = add_running_style(df)
    print(f"Dataset: {len(df)}走")

    print("Attaching past running style indicators...")
    df = attach_past_running_style(df)

    print("Attaching pedigree...")
    df = attach_pedigree(df)
    sex_label = {"1": "牡", "2": "牝", "3": "セン"}
    df["sex_label"] = df["sex_cd"].map(sex_label).fillna("不明")
    print("  done")

    sections: list[str] = []

    # ===== ① 過去走脚質指標 × is_strong_horse =====
    sections.append("### ① 過去走脚質指標 × 強馬率\n")

    sections.append("#### A. 過去5走 前半通過順位平均（先行傾向）")
    cf_q = quartile_split(df, "past_corner_first_avg_5", "通過")
    if not cf_q.empty:
        cf_q.to_csv(CSV_DIR / "p2_corner_first_avg.csv", index=False, encoding="utf-8-sig")
        sections.append(fmt_table_with_strong(cf_q.rename(columns={"quartile": "前半通過順位平均"}), "前半通過順位平均"))
    sections.append(
        "\n→ Q1（先行型）と Q4（追込型）で 強馬率 がどう違うか確認"
    )

    sections.append("\n#### B. 過去5走 上がり3F平均（末脚力）")
    l3f_avg_q = quartile_split(df, "past_last_3f_avg_5", "上がり")
    if not l3f_avg_q.empty:
        l3f_avg_q.to_csv(CSV_DIR / "p2_last_3f_avg.csv", index=False, encoding="utf-8-sig")
        sections.append(fmt_table_with_strong(l3f_avg_q.rename(columns={"quartile": "過去5走上がり3F平均"}), "過去5走上がり3F平均"))

    sections.append("\n#### C. 過去5走 上がり3F ベスト")
    l3f_min_q = quartile_split(df, "past_last_3f_min_5", "ベスト上がり")
    if not l3f_min_q.empty:
        l3f_min_q.to_csv(CSV_DIR / "p2_last_3f_min.csv", index=False, encoding="utf-8-sig")
        sections.append(fmt_table_with_strong(l3f_min_q.rename(columns={"quartile": "ベスト上がり3F"}), "ベスト上がり3F"))

    sections.append("\n#### D. 過去短距離（1000-1200m）上がり3F平均")
    short_l3f_q = quartile_split(df, "past_short_avg_l3f", "短距離上がり")
    if not short_l3f_q.empty:
        short_l3f_q.to_csv(CSV_DIR / "p2_short_l3f.csv", index=False, encoding="utf-8-sig")
        sections.append(fmt_table_with_strong(short_l3f_q.rename(columns={"quartile": "短距離上がり3F平均"}), "短距離上がり3F平均"))

    # ===== ② 父・厩舎・騎手 × 強馬率（出走20以上） =====
    sections.append("\n\n### ② 強馬を生み出す父・厩舎・騎手TOP\n")

    sections.append("#### A. 父馬 強馬率TOP（出走30以上）")
    sire_agg = aggregate_with_strong(df, "sire_name")
    sire_strong = sire_agg[sire_agg["n"] >= 30].sort_values("strong_rate", ascending=False).head(15)
    sire_strong.to_csv(CSV_DIR / "p2_sire_strong.csv", index=False, encoding="utf-8-sig")
    s_lines = [
        "| 父馬 | 出走 | 強馬 | 強馬率 | 3着内率 | 単勝ROI |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in sire_strong.iterrows():
        s_lines.append(
            f"| {r['sire_name']} | {int(r['n'])} | {int(r['strong'])} | "
            f"{r['strong_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(s_lines))

    sections.append("\n#### B. 厩舎 強馬率TOP（出走15以上）")
    trn_agg = aggregate_with_strong(df, "trainer_name")
    trn_strong = trn_agg[trn_agg["n"] >= 15].sort_values("strong_rate", ascending=False).head(15)
    trn_strong.to_csv(CSV_DIR / "p2_trainer_strong.csv", index=False, encoding="utf-8-sig")
    t_lines = [
        "| 厩舎 | 出走 | 強馬 | 強馬率 | 3着内率 | 単勝ROI |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in trn_strong.iterrows():
        t_lines.append(
            f"| {r['trainer_name']} | {int(r['n'])} | {int(r['strong'])} | "
            f"{r['strong_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(t_lines))

    sections.append("\n#### C. 騎手 強馬率TOP（出走20以上）")
    jck_agg = aggregate_with_strong(df, "jockey_name")
    jck_strong = jck_agg[jck_agg["n"] >= 20].sort_values("strong_rate", ascending=False).head(15)
    jck_strong.to_csv(CSV_DIR / "p2_jockey_strong.csv", index=False, encoding="utf-8-sig")
    j_lines = [
        "| 騎手 | 出走 | 強馬 | 強馬率 | 3着内率 | 単勝ROI |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in jck_strong.iterrows():
        j_lines.append(
            f"| {r['jockey_name']} | {int(r['n'])} | {int(r['strong'])} | "
            f"{r['strong_rate']*100:.1f}% | {r['top3_rate']*100:.1f}% | "
            f"{r['win_roi']*100:.1f}% |"
        )
    sections.append("\n".join(j_lines))

    # ===== ③ 過去千直経験時のパフォーマンス × 強馬 =====
    sections.append("\n\n### ③ 過去千直経験パフォーマンス × 今回強馬\n")
    rep_df = df[df["past_choku_finish_avg"].notna()].copy()
    sections.append(f"対象: 千直経験馬 {len(rep_df)}走\n")

    if len(rep_df) > 30:
        # 過去千直 平均着順別
        rep_df["past_choku_finish_bucket"] = rep_df["past_choku_finish_avg"].apply(
            lambda x: "1-3着平均" if x <= 3 else (
                "4-6着平均" if x <= 6 else (
                    "7-10着平均" if x <= 10 else "11着以下平均"
                )
            )
        )
        bucket_agg = aggregate_with_strong(rep_df, "past_choku_finish_bucket")
        order = ["1-3着平均", "4-6着平均", "7-10着平均", "11着以下平均"]
        bucket_agg["_o"] = bucket_agg["past_choku_finish_bucket"].apply(
            lambda x: order.index(x) if x in order else 99
        )
        bucket_agg = bucket_agg.sort_values("_o").drop(columns="_o").reset_index(drop=True)
        sections.append("#### A. 過去千直平均着順 × 今回強馬率")
        sections.append(fmt_table_with_strong(bucket_agg.rename(columns={"past_choku_finish_bucket": "過去千直平均着順"}), "過去千直平均着順"))

        # 過去千直 上がり3F平均別
        l3f_choku_q = quartile_split(rep_df, "past_choku_last_3f_avg", "千直上がり")
        if not l3f_choku_q.empty:
            sections.append("\n#### B. 過去千直 上がり3F平均 × 今回強馬率")
            sections.append(fmt_table_with_strong(l3f_choku_q.rename(columns={"quartile": "過去千直上がり3F平均"}), "過去千直上がり3F平均"))

    # ===== ④ 統合: 強馬の typical profile =====
    sections.append("\n\n### ④ 強馬の typical profile（強馬率上位 vs 下位の比較）\n")

    strong_df = df[df["is_strong_horse"]].copy()
    non_strong_df = df[~df["is_strong_horse"] & df["is_top3"]].copy()  # 3着内だが①強馬以外

    profile_rows = []
    for col, label in [
        ("past_corner_first_avg_5", "過去5走 前半通過順位平均"),
        ("past_last_3f_avg_5", "過去5走 上がり3F平均"),
        ("past_last_3f_min_5", "過去5走 上がり3Fベスト"),
        ("past_short_avg_l3f", "過去短距離 上がり3F平均"),
        ("past_short_count", "過去短距離経験回数"),
        ("total_career_races_p2", "通算出走数"),
        ("age", "年齢"),
        ("popularity", "人気"),
        ("odds", "単勝オッズ"),
        ("horse_weight", "馬体重"),
    ]:
        s_mean = strong_df[col].mean() if col in strong_df.columns else None
        ns_mean = non_strong_df[col].mean() if col in non_strong_df.columns else None
        all_mean = df[col].mean() if col in df.columns else None
        profile_rows.append({
            "指標": label,
            "強馬平均": s_mean,
            "他3着内馬平均": ns_mean,
            "全体平均": all_mean,
        })

    p_lines = [
        "| 指標 | 強馬平均 | 他3着内馬平均 | 全体平均 |",
        "|---|---:|---:|---:|",
    ]
    for row in profile_rows:
        sm = f"{row['強馬平均']:.2f}" if row["強馬平均"] is not None and not pd.isna(row["強馬平均"]) else "-"
        nsm = f"{row['他3着内馬平均']:.2f}" if row["他3着内馬平均"] is not None and not pd.isna(row["他3着内馬平均"]) else "-"
        am = f"{row['全体平均']:.2f}" if row["全体平均"] is not None and not pd.isna(row["全体平均"]) else "-"
        p_lines.append(f"| {row['指標']} | {sm} | {nsm} | {am} |")
    sections.append("\n".join(p_lines))

    # ===== ⑤ 結論 =====
    sections.append("\n\n### ⑤ 結論サマリ（強馬予測の事前指標）\n")
    sections.append("- **特徴量化推奨（事前判定用）**:")
    sections.append("  - `past_corner_first_avg_5`: 過去5走の前半通過順位平均（先行傾向）")
    sections.append("  - `past_last_3f_min_5`: 過去5走のベスト上がり3F（末脚ピーク）")
    sections.append("  - `past_short_avg_l3f`: 過去短距離での上がり3F平均（千直適性の代理）")
    sections.append("  - `sire_strong_rate`: 父馬の千直強馬率（5走以上で平滑化）")
    sections.append("  - `trainer_strong_rate`: 厩舎の千直強馬率")
    sections.append("  - `jockey_strong_rate`: 騎手の千直強馬率")
    sections.append("  - `past_choku_finish_avg`: 過去千直平均着順（経験馬のみ）")
    sections.append("  - `past_choku_last_3f_avg`: 過去千直上がり3F平均（経験馬のみ）")
    sections.append("\n- **予想時の判断ヒント**:")
    sections.append("  1. 「過去5走の前半通過順位 + 上がり3Fベスト」のセットで強馬候補を選別")
    sections.append("  2. 父・厩舎・騎手の強馬率TOPと一致する馬を優遇")
    sections.append("  3. 過去千直経験馬は「平均着順」と「上がり3F平均」を併用")
    sections.append("\n- **次フェーズ（ルールエンジン v0.1）への入力**:")
    sections.append("  - 上記特徴量を用いた段階判定ロジックの設計")
    sections.append("  - polaris予測値との統合方法（重み付き和 / AND条件 / 説明文生成）")

    section_body = (
        "# vega-niigata1000 Phase 2: 強馬予測の事前特徴量検証\n\n"
        "作成: 2026-05-09\n"
        "対象: 新潟芝1000m 全135R / 2,230走（2020-2026）\n"
        "ターゲット: `is_strong_horse`（結果脚質①テン速＆末脚速 かつ 3着内）\n\n"
        "**目的**: 「結果として速かった馬」を事前に判定するための特徴量を発見する。\n"
        "Phase 1 検証②で「結果脚質①強馬」が 3着内率54.7%、ROI 170% という支配的な性能を持つことを確認。\n"
        "本Phaseでは、この強馬になる馬の事前指標（過去走脚質、血統、厩舎、騎手）を解明する。\n\n"
        "---\n\n"
        + "\n".join(sections)
        + "\n\n---\n\n"
    )

    REPORT_PHASE2.write_text(section_body, encoding="utf-8")
    print(f"Phase 2 report written: {REPORT_PHASE2}")


if __name__ == "__main__":
    main()

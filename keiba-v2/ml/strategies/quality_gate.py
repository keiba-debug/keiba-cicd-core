#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-002 低信頼データ減点 — quality メタ消費の共通ゲート（純化版 / Session 153）。

E-001 で各分析JSONに付与した quality:{metric, ci95, effective_n, algo, selected, source}
を消費し、買い目側（E-003 接戦タイブレーク / E-004 出遅れフィルタ）が使う
「信頼性を織り込んだ採用値」を返す純関数群。

設計原則（E001仕様 §7 / Q3 確定）:
- 減点の主役は **ci95.lower 一本**。小標本・選抜系(selected)ほど下限が下がり、自然に控えめになる
  （例: 接戦 rank1 10/13=0.769 → ci95.lower=0.451。生率でなく下限で比較すれば上振れに騙されない）。
- CI幅 × effective_n × stability を掛け合わせる多段補正はしない（三重補正禁止＝過小評価馬の妙味を
  自分で消さない方向に倒す）。
- ci95 が無い（null / 欠損 / quality 不在）エントリは点推定にフォールバック（情報を捨てない）。
- stability_flag は E-006 表示向け。E-002 の値計算には使わない（is_low_confidence は表示タグ補助のみ）。

このモジュールは純関数のみ。分析JSONの読み込み・キー構造の解釈は呼び出し側の責務。
"""

from typing import Optional


def reliable_value(quality: Optional[dict], point_estimate: float,
                   *, mode: str = "lower") -> float:
    """quality メタから「信頼性を織り込んだ採用値」を返す。

    ci95 があれば下限(lower)＝控えめな値、無ければ point_estimate にフォールバック。
    買い目で率を比較・足切りする際は点推定でなくこの値を使う（小標本上振れに騙されない）。

    Args:
        quality: 分析エントリの quality dict（None / 非dict でも安全）
        point_estimate: フォールバック用の点推定（その分析の率そのもの）
        mode: "lower"（通常・控えめ）/ "upper"（最楽観・稀なケース）

    Returns:
        ci95[mode] か、取れなければ point_estimate
    """
    if not isinstance(quality, dict):
        return point_estimate
    ci = quality.get("ci95")
    if not isinstance(ci, dict):
        return point_estimate
    v = ci.get(mode)
    return v if v is not None else point_estimate


def is_low_confidence(quality: Optional[dict], min_effective_n: int = 0) -> bool:
    """このエントリが「低信頼（表示で注意喚起したい）」かを返す（E-005/E-006 表示タグ補助）。

    判定: quality 不在 / stability_flag=insufficient / effective_n < min_effective_n。
    ※ 値の減点には使わない（減点は reliable_value=ci95.lower に一本化）。表示タグ判定専用。
    """
    if not isinstance(quality, dict):
        return True
    if quality.get("stability_flag") == "insufficient":
        return True
    eff = quality.get("effective_n")
    if eff is None:
        return True
    return eff < min_effective_n

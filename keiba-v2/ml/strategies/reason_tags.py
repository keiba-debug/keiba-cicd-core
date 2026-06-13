#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-005 理由タグ — レース表に出す「接戦◎ / 出遅れ注意 / 低信頼」を組み立てる純関数。

各分析（jockey_close / slow_start）の reader を消費し、馬1頭ぶんの reason_tags
（{type,label,level,detail,low_confidence}）を返す。**表示専用**＝買う/買わない・スコアには
一切影響しない（E-003/E-004 で買い目層への介入は ROI を動かさない/逆効果と実証済みのため、
出遅れ等は「情報」として出す）。

タグ定義:
- close_finish（接戦◎）: 騎手が接戦に強い。jockey_close reliable(ci95.lower) >= 閾値。level=good。
- slow_start（出遅れ注意）: 馬が出遅れ常習 or 逃げ馬×出遅れ or 騎手が出遅れ多い。level=caution。
- low_confidence（低信頼）: 上記タグの根拠データが小標本（effective_n 過少 / stability=insufficient）。
  ＝「このタグは薄いデータに乗っている」というメタ警告。level=warn。

reliable_value=ci95.lower 採用で小標本の上振れに ◎ を付けない（[[quality_gate]]）。
純関数。JSON 読み込みは reader（jockey_close / slow_start）の責務。
"""

from typing import Dict, List, Optional

from ml.strategies.jockey_close import jockey_close_reliable
from ml.strategies.quality_gate import is_low_confidence
from ml.strategies.slow_start import jockey_slow_start_reliable

# --- 閾値（分析分布に基づき選択的にチューニング） ---
CLOSE_FINISH_MARK = 0.45          # jockey close ci.lower（>=0.45 で 22/152 騎手＝上位~14%で◎）
CLOSE_FINISH_MIN_EFF_N = 20       # 接戦試行これ未満は low_confidence（>=0.47 帯では稀）
SLOW_HORSE_HABITUAL = 0.30        # 馬出遅れ率これ以上で常習
SLOW_HORSE_FRONT = 0.20           # 逃げ馬はこの率でも注意（プラン崩壊しやすい）
SLOW_HORSE_MIN_N = 4              # 出遅れ判定に要する最小試行数（N過少の上振れを弾く）
FRONT_RUNNER_MAX = 0.25           # 1角通過比率これ以下＝逃げ/先行
SLOW_JOCKEY_RELIABLE = 0.30       # 騎手出遅れ ci.lower（max ~0.39 → 上位のみ）
SLOW_JOCKEY_MIN_EFF_N = 30


def build_reason_tags(
    *,
    jockey_code: Optional[str],
    ketto_num: Optional[str],
    horse_ss_rate: Optional[float],
    first_corner_ratio: Optional[float],
    jclose_map: Dict[str, dict],
    ss_jmap: Dict[str, dict],
    ss_hmap: Dict[str, dict],
) -> List[dict]:
    """馬1頭の reason_tags リストを返す（表示専用・空なら []）。

    Args:
        jockey_code: 騎手コード
        ketto_num: 血統登録番号
        horse_ss_rate: predictions の horse_slow_start_rate（特徴量。-1/None=不明）
        first_corner_ratio: 1角通過比率（avg_first_corner_ratio。逃げ判定用）
        jclose_map: jockey_close reader の map
        ss_jmap / ss_hmap: slow_start reader の (jockey_map, horse_map)
    """
    tags: List[dict] = []
    any_low_conf = False

    # --- 接戦◎ ---
    jc_entry = jclose_map.get(str(jockey_code)) if jockey_code else None
    if jc_entry is not None:
        cw = jockey_close_reliable(jclose_map, jockey_code)
        if cw >= CLOSE_FINISH_MARK:
            # 接戦は稀少イベントで stability_flag が構造的に insufficient になりがち。
            # そのため低信頼判定は effective_n のみで行う（stability は使わない）。
            _eff = (jc_entry.get("quality") or {}).get("effective_n")
            low = (_eff is None) or (_eff < CLOSE_FINISH_MIN_EFF_N)
            any_low_conf = any_low_conf or low
            tags.append({
                "type": "close_finish",
                "label": "接戦◎",
                "level": "good",
                "detail": f"騎手接戦勝率 {cw:.0%}(下限)",
                "low_confidence": low,
            })

    # --- 出遅れ注意 ---
    # 馬の出遅れは ss_hmap（rate + total_with_hassou=N）優先で N過少の上振れを弾く。
    # map に無い場合のみ特徴量 horse_ss_rate にフォールバック（N不明＝判定に使うが控えめ）。
    h_entry = ss_hmap.get(str(ketto_num)) if ketto_num else None
    if h_entry is not None:
        h_ss = float(h_entry.get("slow_start_rate", 0.0) or 0.0)
        h_n = int(h_entry.get("total_with_hassou", 0) or 0)
    elif horse_ss_rate is not None and horse_ss_rate >= 0:
        h_ss, h_n = float(horse_ss_rate), None  # 特徴量フォールバック（N不明）
    else:
        h_ss, h_n = None, None
    is_front = (first_corner_ratio is not None and 0 <= first_corner_ratio <= FRONT_RUNNER_MAX)
    j_ss = jockey_slow_start_reliable(ss_jmap, jockey_code)

    # N>=4=採用 / N不明(特徴量フォールバック)=採用 / N<4=不採用（N過少の上振れを出さない）
    n_ok = (h_n is None) or (h_n >= SLOW_HORSE_MIN_N)
    rate_hit = h_ss is not None and (
        h_ss >= SLOW_HORSE_HABITUAL or (is_front and h_ss >= SLOW_HORSE_FRONT))
    horse_risk = n_ok and rate_hit
    jockey_risk = j_ss >= SLOW_JOCKEY_RELIABLE
    if horse_risk or jockey_risk:
        reasons = []
        if horse_risk:
            reasons.append(f"馬出遅れ{h_ss:.0%}" + ("(逃げ)" if is_front else ""))
        if jockey_risk:
            reasons.append(f"騎手出遅れ{j_ss:.0%}(下限)")
        low = False
        if jockey_risk and not horse_risk:
            j_entry = ss_jmap.get(str(jockey_code)) if jockey_code else None
            low = is_low_confidence(j_entry.get("quality") if j_entry else None,
                                    min_effective_n=SLOW_JOCKEY_MIN_EFF_N)
        any_low_conf = any_low_conf or low
        tags.append({
            "type": "slow_start",
            "label": "出遅れ注意",
            "level": "caution",
            "detail": " / ".join(reasons),
            "low_confidence": low,
        })

    # --- 低信頼（上記タグが薄いデータに乗っている場合のメタ警告） ---
    if any_low_conf:
        tags.append({
            "type": "low_confidence",
            "label": "低信頼",
            "level": "warn",
            "detail": "根拠データが小標本",
            "low_confidence": True,
        })

    return tags

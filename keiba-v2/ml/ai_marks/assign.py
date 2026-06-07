# -*- coding: utf-8 -*-
"""AI予想印の変換ロジック (純関数)。

predictions.json の races[].entries[] から、W(校正済勝率) / P(校正済複勝率) /
ADR(ar_deviation) を race 内 robust z-score 加重和して composite を作り、
最高スコアの馬を ◎ にする。

設計: docs/auto-purchase/22_AI_MARKS_DESIGN.md §1
原則 (シズネレビュー反映):
  - rank-based: composite 最高 = ◎。動的閾値ゼロ、再現性のため固定ルール。
  - Step1 は ◎ 1頭のみ。○▲△Ⅲ穴は書かない (穴は Themis 上 EV配分側へ)。
  - ADR 全欠損/分散ゼロは「明示的に成分を落とした」と notes に記録 (silent degradation 禁止)。
  - I/O なし・乱数なし・DB 非依存。同一入力 → 同一出力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, Optional, Sequence, Tuple

# 平坦分布ガードの閾値 (composite=z空間)。隣接 gap の最大がこれ未満なら撃ちなし。
# Step1 (◎のみ) 専用。Step2 は複勝率の崖で頭数を決めるため、ほぼ平坦でも撃つ。
FLAT_EPS = 0.10

# 印の序列 (composite 降順で先頭から割当)。Step2 で ◎○▲△Ⅲ まで対応。
MARK_LADDER = ("◎", "○", "▲", "△", "Ⅲ")

# Step2 の頭数決定 (ふくだ 2026-06-07):
#   序列 (◎○▲△Ⅲ) は composite 総合で決め、頭数は複勝率(P)の「崖」で打ち切る。
#   composite 降順に並べ、前馬との複勝率比 prev/cur がこれ以上なら「勝負圏の崖」と
#   見て打ち切り。累積%でなく比率なので同確率を分断せず、頭数・確率水準にロバスト。
#   旧・段差ベース (BREAK_GAP, composite-z空間) は多頭数で◎単独になり撤廃。
#   「1頭抜けてる=自信あり」等の自信度は馬印に出さず別途レース印へ移管。
CLIFF_RATIO = 2.5

# 穴印 (Themis 整合)。設計 §4-E:「穴は確率を持ち上げて◎扱いするな、信頼度の補正係数」。
#   - 序列印 (◎○▲△Ⅲ) とは **完全に別系統** で判定する。
#   - odds/popularity を印判定の直接材料にしない (シズネ赤旗 R5)。
#     代わりに win_ev (= pred_proba_w_cal × 単勝odds、確率に立脚した妙味) を使う。
#     確率を起点にしているので「オッズで序列を上げる」Themis 逸脱には当たらない。
#   - **乱発防止 (絶対閾値を使わない)**: win_ev>1 の高オッズ馬は EV の構造特性で
#     ほぼ全レースに出る (5/31 検証 22/24R)。「人が見落とす妙味の押さえ」に絞るため、
#     絶対水準でなく **レース内で win_ev が突出しているか** で判定する:
#       (a) 序列印が付かなかった馬の中で win_ev 最大の馬を穴候補とし、
#       (b) その win_ev が「穴候補2位より ANA_BREAK 以上高い」=妙味が1頭に集中している
#           レースのときだけ穴を打つ。団子なら付けない (今日の穴はこのレース、を表現)。
#   - odds 下限は「低人気=妙味の前提」として残す (人気馬を穴と呼ばない最低条件)。
#   - 既定 OFF (実験扱い)。CLI --ana / assign_ai_marks(enable_ana=True) で明示有効化。
ANA_MIN_ODDS = 6.0       # 穴候補の単勝オッズ下限 (低人気=妙味の前提)
ANA_BREAK = 1.5          # 穴候補トップが2位候補より突出している段差 (win_ev 空間)
ANA_MAX_COUNT = 1        # 1レースに打つ穴の最大頭数 (乱発防止)


@dataclass
class AiMarkResult:
    """1 レース分の AI印決定結果。"""
    marks: Dict[int, str]                      # {umaban: '◎'}  Step1 は 0〜1頭
    skipped: bool                              # True = 撃ちなし
    skip_reason: Optional[str]                 # 'too_few_runners' / 'flat_distribution' / ...
    adr_used: bool                             # ADR 成分を composite に入れたか
    composite: Dict[int, float]                # {umaban: composite_score}  監査用
    weights: Tuple[float, float, float]        # 適用した (wW, wP, wA)
    notes: List[str] = field(default_factory=list)


def _robust_z(values: Sequence[Optional[float]]) -> List[float]:
    """median / MAD ベースの robust z-score。

    - None は median 補完 (呼び出し側で「一部欠損」を扱う際に使う)。
    - MAD=0 のとき std にフォールバック、std も 0 (全頭同値) なら全頭 0 を返す。
    外れ値 (圧倒的人気で w_cal 突出、ADR の <30/>70 帯域) に頑健。
    """
    present = [v for v in values if v is not None]
    if not present:
        return [0.0] * len(values)
    med = median(present)
    filled = [med if v is None else v for v in values]
    abs_dev = [abs(v - med) for v in filled]
    mad = median(abs_dev)
    if mad > 0:
        # 1.4826 = 正規分布で MAD を std に揃えるスケール係数
        scale = 1.4826 * mad
        return [(v - med) / scale for v in filled]
    # MAD=0: std フォールバック
    n = len(filled)
    mean = sum(filled) / n
    var = sum((v - mean) ** 2 for v in filled) / n
    std = var ** 0.5
    if std > 0:
        return [(v - mean) / std for v in filled]
    return [0.0] * n  # 全頭同値 → 分散ゼロ


def _variance(values: Sequence[float]) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / n


def assign_ai_marks(
    entries: List[dict],
    weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    step: int = 1,
    enable_ana: bool = False,
) -> AiMarkResult:
    """ML予想スコア → AI印。

    step=1: ◎ 1頭のみ。
    step=2: 序列は composite 総合 (◎○▲△Ⅲ の順)、頭数は複勝率(P)の崖で決定
            (前馬との P 比が CLIFF_RATIO 以上で打ち切り。上限5・最低◎1。
             少頭数は cap=頭数-1 で全頭印を防止。ふくだ 2026-06-07)。
            enable_ana=True なら崖の外の妙味馬に穴を別系統で付加。

    Args:
        entries: predictions.json の races[].entries[]。
            各 dict から umaban / pred_proba_w_cal / pred_proba_p / ar_deviation を使う。
            step=2 で enable_ana=True のとき win_ev / odds も使う (穴判定、§4-E)。
        weights: (wW, wP, wA)。既定 (1,1,1)。
        step: 1=◎のみ / 2=◎○▲△Ⅲ (序列=composite, 頭数=複勝率の崖)。
        enable_ana: True なら穴印を別系統で付加 (step=2 のみ有効、既定 OFF=実験扱い)。

    Returns:
        AiMarkResult。撃ちなしのとき marks={} かつ skipped=True。
    """
    wW, wP, wA = weights
    notes: List[str] = []

    # --- Step 0: 早期撃ちなし (出走 < 3頭) ---
    valid = [e for e in entries if e.get("umaban") is not None]
    n = len(valid)
    if n < 3:
        return AiMarkResult(
            marks={}, skipped=True, skip_reason="too_few_runners",
            adr_used=False, composite={}, weights=weights,
            notes=[f"出走 {n} 頭 (<3) のため撃ちなし"],
        )

    umabans = [int(e["umaban"]) for e in valid]

    def _col(key: str) -> List[Optional[float]]:
        out: List[Optional[float]] = []
        for e in valid:
            v = e.get(key)
            out.append(float(v) if isinstance(v, (int, float)) else None)
        return out

    w_vals = _col("pred_proba_w_cal")
    p_vals = _col("pred_proba_p")
    a_vals = _col("ar_deviation")

    # --- Step 2: ADR 欠損/分散ゼロの明示処理 ---
    a_present = [v for v in a_vals if v is not None]
    adr_all_missing = len(a_present) == 0
    adr_zero_var = (not adr_all_missing) and _variance(a_present) == 0.0
    adr_used = not (adr_all_missing or adr_zero_var)
    if adr_all_missing:
        notes.append("ADR全欠損のため2軸(W,P)判定に縮退")
    elif adr_zero_var:
        notes.append("ADR分散ゼロのため2軸(W,P)判定に縮退")
    else:
        n_missing = sum(1 for v in a_vals if v is None)
        if n_missing:
            notes.append(f"ADR一部欠損 {n_missing}/{n} 頭を median 補完")

    # W も P も使えないなら撃ちなし
    w_present = [v for v in w_vals if v is not None]
    p_present = [v for v in p_vals if v is not None]
    if not w_present and not p_present:
        return AiMarkResult(
            marks={}, skipped=True, skip_reason="no_score",
            adr_used=False, composite={}, weights=weights,
            notes=notes + ["W/P スコアが全欠損"],
        )

    # --- Step 1: race 内 robust z-score ---
    z_w = _robust_z(w_vals)
    z_p = _robust_z(p_vals)
    z_a = _robust_z(a_vals) if adr_used else [0.0] * n

    # W も P も ADR も分散ゼロ (全頭同スコア) → 撃ちなし
    if _variance(z_w) == 0.0 and _variance(z_p) == 0.0 and (not adr_used or _variance(z_a) == 0.0):
        return AiMarkResult(
            marks={}, skipped=True, skip_reason="flat_distribution",
            adr_used=adr_used, composite={u: 0.0 for u in umabans}, weights=weights,
            notes=notes + ["W/P/ADR が全頭平坦のため撃ちなし"],
        )

    # --- Step 3: composite 合成 (重み正規化) ---
    denom = wW + wP + (wA if adr_used else 0.0)
    if denom <= 0:
        denom = 1.0
    composite: Dict[int, float] = {}
    for i, u in enumerate(umabans):
        s = wW * z_w[i] + wP * z_p[i] + (wA * z_a[i] if adr_used else 0.0)
        composite[u] = s / denom

    # --- Step 4: 平坦分布ガード (Step1 のみ) ---
    # Step2 は「常に◎○▲△Ⅲ穴 を振る」(ふくだ 2026-06-07) ため、ほぼ平坦でも撃つ。
    # 完全フラット (全頭同スコア=分散ゼロ) は上の Step1/Step3 で既に撃ちなし済み。
    ranked = sorted(umabans, key=lambda u: (-composite[u], _tiebreak_rank(valid, u)))
    if step <= 1:
        sorted_scores = [composite[u] for u in ranked]
        adjacent_gaps = [sorted_scores[i] - sorted_scores[i + 1] for i in range(len(sorted_scores) - 1)]
        if adjacent_gaps and max(adjacent_gaps) < FLAT_EPS:
            return AiMarkResult(
                marks={}, skipped=True, skip_reason="flat_distribution",
                adr_used=adr_used, composite=composite, weights=weights,
                notes=notes + [f"隣接gap最大 {max(adjacent_gaps):.3f} < {FLAT_EPS} で撃ちなし"],
            )

    # --- Step 5: 印割当 ---
    if step <= 1:
        # Step1: ◎ 1頭のみ (composite 最高、同点は rank_w 昇順)。
        marks = {ranked[0]: "◎"}
    else:
        # Step2: 序列は composite 総合 (◎○▲△Ⅲ の順)。頭数は複勝率(P)の「崖」で決める。
        #   composite 降順に並べ、前馬との複勝率比が CLIFF_RATIO 以上開いた所で打ち切り
        #   (= 勝負圏の崖)。累積%と違い同確率を分断しない。少頭数は cap で全頭印を防ぐ。
        #   自信度シグナル (◎が抜けてる等) は馬印に出さず別途レース印へ移管。
        p_med = median([v for v in p_vals if v is not None]) if p_present else 0.0
        p_by_uma = {umabans[i]: (p_vals[i] if p_vals[i] is not None else p_med)
                    for i in range(n)}
        cap = min(len(MARK_LADDER), max(1, n - 1))  # 5頭立てで5頭印を物理的に防ぐ
        n_marks = 1
        for i in range(1, cap):
            prev_p = p_by_uma[ranked[i - 1]]
            cur_p = p_by_uma[ranked[i]]
            if cur_p <= 0 or prev_p / cur_p >= CLIFF_RATIO:
                notes.append(
                    f"複勝率の崖 {prev_p:.3f}→{cur_p:.3f} "
                    f"(比 {prev_p / cur_p:.1f} ≥ {CLIFF_RATIO}) で {n_marks}頭に絞り"
                )
                break
            n_marks += 1
        marks = {ranked[i]: MARK_LADDER[i] for i in range(n_marks)}

        # 穴印 (別系統・Themis 整合)。崖の外の妙味馬に付加。
        if enable_ana:
            ana_added = _assign_ana(valid, marks, notes)
            if ana_added:
                notes.append(f"穴印 {ana_added}頭を妙味の押さえとして付加")

    return AiMarkResult(
        marks=marks, skipped=False, skip_reason=None,
        adr_used=adr_used, composite=composite, weights=weights, notes=notes,
    )


def _assign_ana(valid: List[dict], marks: Dict[int, str], notes: List[str]) -> int:
    """穴印を別系統で付加する (§4-E Themis 整合)。付けた頭数を返す。

    乱発防止のため絶対閾値でなく「レース内で win_ev が突出しているか」で判定する。
    序列印 (◎○▲△Ⅲ) が付いていない & odds >= ANA_MIN_ODDS (低人気) の馬を穴候補とし、
    win_ev 降順に並べて
      - 候補が1頭だけ → そのまま穴
      - 候補が2頭以上 → トップの win_ev が2位より ANA_BREAK 以上高い (=妙味が1頭に集中)
        ときだけトップを穴に。団子 (僅差で複数) なら付けない。
    最大 ANA_MAX_COUNT 頭。

    odds/popularity を序列の直接材料にはしない (composite で序列を決め、穴は別系統の
    妙味フラグ)。win_ev は確率起点なので「確率を持ち上げて◎扱い」する Themis 逸脱を避ける。
    """
    candidates = []
    for e in valid:
        u = int(e["umaban"])
        if u in marks:  # 既に序列印が付いている馬は対象外
            continue
        win_ev = e.get("win_ev")
        odds = e.get("odds")
        if not isinstance(win_ev, (int, float)) or not isinstance(odds, (int, float)):
            continue
        if win_ev > 0 and odds >= ANA_MIN_ODDS:
            candidates.append((u, float(win_ev)))

    if not candidates:
        return 0
    candidates.sort(key=lambda kv: -kv[1])

    # 突出判定: 2頭以上いるなら トップ - 2位 >= ANA_BREAK のときだけ穴。
    if len(candidates) >= 2:
        gap = candidates[0][1] - candidates[1][1]
        if gap < ANA_BREAK:
            notes.append(
                f"穴候補 win_ev 突出せず (top {candidates[0][1]:.2f} - "
                f"2位 {candidates[1][1]:.2f} = {gap:.2f} < {ANA_BREAK}) のため穴なし"
            )
            return 0

    added = 0
    for u, _ev in candidates[:ANA_MAX_COUNT]:
        marks[u] = "穴"
        added += 1
    return added


def _tiebreak_rank(valid: List[dict], umaban: int) -> int:
    """composite 同点時の tiebreak: rank_w 昇順 (校正済勝率1位を優先)。

    rank_w 欠損は大きな値で後ろに送る。
    """
    for e in valid:
        if int(e["umaban"]) == umaban:
            rw = e.get("rank_w")
            return int(rw) if isinstance(rw, (int, float)) else 9999
    return 9999

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レース分類 v2 — 統合分類モジュール

33ラップ理論 + ch5(L3F閾値) + RPCI を統合した多基準レース分類。
sr_parser.py と race_type_standards.py の重複ロジックを統一。
"""

from typing import Dict, List, Optional

# ── v2 分類タイプ ────────────────────────────────

TREND_V2_TYPES = [
    'sprint',               # 瞬発戦（L3F + RPCI 一致）
    'sprint_mild',          # 軽瞬発（RPCI のみ瞬発シグナル）
    'long_sprint',          # ロンスパ（L4加速 + 中盤緩み）
    'even',                 # 平均ペース
    'sustained_hp',         # 持続:ハイペース（RPCI低 + L3遅い）
    'sustained_strong',     # 持続:強L3（RPCI低 + L3速い）
    'sustained_doroashi',   # 持続:道悪
]

TREND_V2_LABELS = {
    'sprint': '瞬発',
    'sprint_mild': '軽瞬発',
    'long_sprint': 'ロンスパ',
    'even': '平均',
    'sustained_hp': '持続HP',
    'sustained_strong': '持続強L3',
    'sustained_doroashi': '持続道悪',
}

# v2 → v1 後方互換マッピング
V2_TO_V1 = {
    'sprint': 'sprint_finish',
    'sprint_mild': 'sprint_finish',
    'long_sprint': 'long_sprint',
    'even': 'even_pace',
    'sustained_hp': 'front_loaded',
    'sustained_strong': 'front_loaded_strong',
    'sustained_doroashi': 'front_loaded',
}


# ── 33ラップ算出 ─────────────────────────────────

def compute_lap33(lap_times: List[float], distance: int) -> Optional[float]:
    """
    33ラップ値を算出。
    33ラップ = (残り6F-3F区間タイム) - (残り3F-Goalタイム)
    プラス → 瞬発力勝負（後半加速）、マイナス → 持久力勝負（前傾ラップ）

    6F (1200m) 以上のレースのみ算出可能。
    """
    if not lap_times or len(lap_times) < 6:
        return None
    l3_sum = sum(lap_times[-3:])          # 残り3F-Goal
    l6_l3_sum = sum(lap_times[-6:-3])     # 残り6F-3F
    return round(l6_l3_sum - l3_sum, 2)


def compute_last_nf(lap_times: List[float], n: int) -> Optional[float]:
    """ラスト N ハロンの合計タイムを算出。"""
    if not lap_times or len(lap_times) < n:
        return None
    return round(sum(lap_times[-n:]), 1)


# ── L3F 閾値判定（ch5） ─────────────────────────

def _l3f_signal(l3: float, distance: int, track_type: str) -> str:
    """
    L3F絶対値による瞬発/持続判定。
    ch5: 芝1800m+ → L3≤34.4確定瞬発, ≤35.5瞬発, ≥36.0持続
    """
    if track_type == 'turf':
        if distance >= 1800:
            if l3 <= 34.4:
                return 'sprint'
            if l3 <= 35.5:
                return 'sprint'
            if l3 >= 36.0:
                return 'sustained'
            return 'neutral'
        elif distance >= 1400:
            # 短めの距離はL3が構造的に速くなるため閾値を引き下げ
            if l3 <= 33.9:
                return 'sprint'
            if l3 <= 35.0:
                return 'sprint'
            if l3 >= 35.5:
                return 'sustained'
            return 'neutral'
        else:
            # 芝1200m: L3F閾値は不適切（全体が6Fで構造が異なる）
            return 'neutral'
    else:
        # ダート: ch6の閾値
        if distance >= 1700:
            if l3 >= 37.8:
                return 'sustained'
            return 'neutral'
        else:
            if l3 >= 37.3:
                return 'sustained'
            return 'neutral'


# ── RPCI 判定 ────────────────────────────────────

def _rpci_signal(rpci: float, course_avg_rpci: Optional[float] = None) -> str:
    """
    RPCI値による瞬発/持続判定。
    RPCI = last_3f / (first_3f + last_3f) * 100
    高RPCI → 後半遅い → 前傾（ハイペース）→ sustained
    低RPCI → 後半速い → 後傾（スロー）→ sprint
    コース平均RPCIが利用可能なら相対判定、なければ絶対判定。
    """
    if course_avg_rpci is not None:
        diff = rpci - course_avg_rpci
        if diff >= 1.5:
            return 'sustained'
        if diff <= -1.5:
            return 'sprint'
        return 'neutral'
    # 絶対値フォールバック
    if rpci >= 51:
        return 'sustained'
    if rpci <= 48:
        return 'sprint'
    return 'neutral'


# ── 33ラップ判定 ─────────────────────────────────

def _lap33_signal(lap33: float, course_avg_lap33: Optional[float] = None) -> str:
    """
    33ラップ値による瞬発/持続判定。
    コース平均33ラップが利用可能なら相対判定。
    """
    if course_avg_lap33 is not None:
        diff = lap33 - course_avg_lap33
        if diff >= 0.5:
            return 'sprint'
        if diff <= -0.5:
            return 'sustained'
        return 'neutral'
    # 絶対値フォールバック
    if lap33 >= 0.5:
        return 'sprint'
    if lap33 <= -0.5:
        return 'sustained'
    return 'neutral'


# ── ロンスパ検出 ─────────────────────────────────

def _is_long_sprint(lap_times: List[float]) -> bool:
    """
    ロンスパ戦の検出。
    ラスト4-5F付近からペースアップが始まり、末脚を長く使うパターン。
    判定条件（全てAND）:
      1. L4目の1Fが L3平均より0.8秒以上遅い（明確な加速ポイント）
      2. L5目もL3平均より遅い（L4だけの一時的変動ではない）
      3. L3区間内で減速していない（L3-1F ≤ L3-3F、失速パターンを除外）
    """
    if not lap_times or len(lap_times) < 5:
        return False
    l3_per_f = sum(lap_times[-3:]) / 3
    fourth_from_last = lap_times[-4]
    fifth_from_last = lap_times[-5] if len(lap_times) >= 6 else fourth_from_last

    # 条件1: L4目が L3平均より0.8秒以上遅い
    if fourth_from_last - l3_per_f < 0.8:
        return False
    # 条件2: L5目もL3平均より遅い（L4-5F区間で緩んでいた）
    if fifth_from_last <= l3_per_f:
        return False
    # 条件3: L3区間で失速していない（最終Fが3F前より遅くない）
    if lap_times[-1] > lap_times[-3] + 0.3:
        return False
    return True


# ── 統合分類 ─────────────────────────────────────

def classify_race_v2(
    rpci: Optional[float],
    l3: Optional[float],
    l4: Optional[float],
    s3: Optional[float],
    s4: Optional[float],
    distance: int,
    track_type: str,
    track_condition: str = '',
    lap_times: Optional[List[float]] = None,
    course_avg_l3: Optional[float] = None,
    course_avg_rpci: Optional[float] = None,
    course_avg_lap33: Optional[float] = None,
) -> Dict:
    """
    多基準レース分類 v2。

    Returns: {
        'trend_v2': str,          # v2分類タイプ
        'trend_v1': str,          # v1後方互換タイプ
        'lap33': float | None,    # 33ラップ連続値
        'trend_detail': {
            'l3f_signal': str,    # 'sprint' | 'sustained' | 'neutral'
            'rpci_signal': str,
            'lap33_signal': str,
            'confidence': float,  # 0-1
        }
    }
    """
    # デフォルト
    result = {
        'trend_v2': 'even',
        'trend_v1': 'even_pace',
        'lap33': None,
        'trend_detail': {
            'l3f_signal': 'neutral',
            'rpci_signal': 'neutral',
            'lap33_signal': 'neutral',
            'confidence': 0.5,
        },
    }

    if rpci is None or l3 is None:
        return result

    # ── Step 1: 各判定シグナルを算出 ──

    l3f_sig = _l3f_signal(l3, distance, track_type)
    rpci_sig = _rpci_signal(rpci, course_avg_rpci)

    lap33 = compute_lap33(lap_times, distance) if lap_times else None
    lap33_sig = _lap33_signal(lap33, course_avg_lap33) if lap33 is not None else 'neutral'

    result['lap33'] = lap33
    result['trend_detail']['l3f_signal'] = l3f_sig
    result['trend_detail']['rpci_signal'] = rpci_sig
    result['trend_detail']['lap33_signal'] = lap33_sig

    # ── Step 2: 道悪判定 ──

    is_doroashi = track_condition in ('重', '不良')

    # ── Step 3: ロンスパ検出 ──

    long_sprint = _is_long_sprint(lap_times) if lap_times else False

    # ── Step 4: シグナル集約 → 最終分類 ──

    signals = [l3f_sig, rpci_sig, lap33_sig]
    sprint_count = signals.count('sprint')
    sustained_count = signals.count('sustained')
    # lap33_sig が neutral の場合（データなし）はカウントしない
    active_signals = sum(1 for s in signals if s != 'neutral')
    if active_signals == 0:
        active_signals = 1  # ゼロ除算防止

    if sprint_count >= 2 and not long_sprint:
        # 2つ以上のシグナルが瞬発（ロンスパパターンなし）→ 瞬発戦
        trend_v2 = 'sprint'
        confidence = sprint_count / active_signals
    elif long_sprint and sprint_count >= 1:
        # ロンスパ: L4-5F加速パターン + 瞬発シグナルあり
        trend_v2 = 'long_sprint'
        confidence = 0.8
    elif sprint_count >= 2:
        # 2つ以上のシグナルが瞬発 + ロンスパパターンあり → ロンスパ
        trend_v2 = 'long_sprint'
        confidence = 0.8
    elif sprint_count == 1 and sustained_count == 0:
        # 1つだけ瞬発、残りneutral → 軽瞬発
        trend_v2 = 'sprint_mild'
        confidence = 0.5
    elif sustained_count >= 2:
        # 2つ以上のシグナルが持続
        if is_doroashi:
            trend_v2 = 'sustained_doroashi'
        elif l3 is not None and course_avg_l3 is not None and l3 <= course_avg_l3 * 1.03:
            trend_v2 = 'sustained_strong'
        elif rpci is not None and rpci <= 47:
            trend_v2 = 'sustained_hp'
        else:
            trend_v2 = 'sustained_hp'
        confidence = sustained_count / active_signals
    elif sustained_count == 1 and sprint_count == 0:
        # 1つだけ持続 → 持続寄りだが弱い
        if is_doroashi:
            trend_v2 = 'sustained_doroashi'
        else:
            trend_v2 = 'sustained_hp'
        confidence = 0.5
    else:
        # 混在 or 全てneutral → 平均
        trend_v2 = 'even'
        confidence = 0.5

    result['trend_v2'] = trend_v2
    result['trend_v1'] = V2_TO_V1.get(trend_v2, 'even_pace')
    result['trend_detail']['confidence'] = round(confidence, 2)

    return result

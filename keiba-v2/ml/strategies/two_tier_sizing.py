#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""two_tier_sizing — 勝負R / 見送りR の2層分類サイザー (Session 165 / three_tier 再走)

★★★【棄却・参照用】Session 165 で本番不採用が確定★★★
  ceiling 見送りゲートは 1000%→400% に緩めても害と着順検証で実証された
  (bench_two_tier_v0.py: 見送りレースの 8-9割は◎が3着内に来て AI印4頭で400%超を回収していた)。
  二層化自体も全買い fixed_grade_v2 に大きく劣後 (ROI/winR/破綻)。
  ★本番は fixed_grade_v2 を維持。 このモジュールは registry 残置 (参照用) のみ。★
  ★再び見送り/天井ゲートを実装したくなったら docs/auto_purchase_sizing_design.md §3.7 を必ず読む★
  (162→163→164→165 と3回試して全て害＝[[feedback_odds_gate_hindsight]] の構造的な罠)。

設計正本: docs/auto_purchase_sizing_design.md / メモリ [[bet-adjustment-items]] [[payout-ceiling-strategy]]

★three_tier_v0 (Session 164) の再走 = ふくだ判定で確定したスコープを反映★:
  - (Q1) ceiling_floor_R = 1000% → ★400%★ (的中率25% × 400% = 損益分岐100%)。
  - (Q3) 三層 → ★二層化★ (様子見廃止)。勝負でないレースは ★全て見送り★。
         様子見の「広く薄く」は [[character-betting-personas]] (キャラ別エンタメ枠) へ移譲。
  - Q2 (bankroll=1,000,000 で破綻させず比較) / Q4 (same-case を AI印4頭券面に絞る) は
         bench (ml/analyze/bench_two_tier_v0.py) 側で対応。サイザー本体は影響なし。

★中核アイデア★ (three_tier の中で実払戻成績の証明がある「勝負R」だけを残す):
  - ★勝負R (◎が tansho_ippon 4条件AND を満たす ∧ ceiling_R >= 400%)★
      → ★fixed_grade_v2 を per_race_cap = bankroll × 15% でそのまま wrap★。
        v2 の山型・複0・使い切り保証・swap無効化・fit_legs_to_cap を全て継承する
        (ロジック重複ゼロ・本番 v2 と同じ実払戻成績 = Session 163 +45,700 を継承)。
  - ★見送りR (勝負でない or ceiling_R < 400%)★
      → 空 RaceSizing (Kelly/swap/上乗せ いずれも触らない)。
        ただし ★ceiling_R が +inf (情報不足) なら見送らない★ ([[feedback_odds_gate_hindsight]]
        規律 = 情報不足は買う側に倒す)。

★判定順序★ (= 結果を決める): 見送り(ceiling) > 勝負 > 見送り(非勝負)。
  ① ceiling_R < 400% → miokuri (最強の弾き手。 ただし +inf=情報不足は買う側に倒す)
  ② tansho_ippon 4条件 AND ∧ selected_plans 非空 → shobu
  ③ それ以外 → miokuri (= 様子見廃止)

★純粋関数モジュール★ (副作用なし・I/O なし・DB アクセスなし)。 fixed_grade_v2 / three_tier の
  compute_ceiling_R / _is_shobu_from_pred は import 再利用 (ロジック重複ゼロ)。
  registry 登録は bettype_sizing 側 (SIZERS 辞書) で行うが、 DEFAULT_SIZER は
  ★fixed_grade_v1 のまま維持★ (本サイザーは opt-in 運用 = bat の --sizing two_tier_v0)。

★重大な注意 (本番投入前の必須検証)★:
  ceiling_R は core/odds_db.get_all_combo_odds の ★確定 combo オッズ (時系列なし)★ 由来
  (three_tier.compute_ceiling_R 経由)。 = ライブの predictions 直前オッズでは再現できない
  ([[feedback_odds_gate_hindsight]] 罠)。 bench (実払戻バックテスト) で改善傾向を測る目的では
  許容するが、 ★本番投入前にはライブ再現可能な ceiling 算出への置換 (◎単勝ベース等) が必須★。
  Session 164 で「odds_source を docstring 化」ルールを立てた反省を踏まえて明記する。
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from ml.strategies.bettype_sizing import (
    RaceSizing,
    size_race_fixed_grade_v2,
)
from ml.strategies.three_tier_sizing import (
    MARGIN_MAX_DEFAULT,
    _is_shobu_from_pred,
    compute_ceiling_R,
)


# ---------------------------------------------------------------------------
# 定数 (ふくだ要望を満たす本番値)
# ---------------------------------------------------------------------------

TWO_TIER_SIZER = "two_tier_v0"

# 勝負R の per_race cap (残高に対する割合)。 ふくだ要望「勝負15%」を直訳。
TIER_SHARE_SHOBU = 0.15      # 勝負R = bankroll × 15%

# 見送り閾値 (Q1: ceiling<400% なら見送り)。 400% = 合成オッズ4倍。
#   ceiling_R = race_eff.plans の synthetic_odds 最大 × 100 (倍率→回収率%)。
#   ★Session 164 で 1000% は厳しすぎ (堅い高的中Rを切る) と判定 → 400% に緩和★。
#   400% の根拠 = 的中率25% × 400% = 損益分岐100% (ふくだ判定)。
#   ★骨格段階・要実払戻検証★ ([[feedback_odds_gate_hindsight]] 規律 = 検証宿題)。
CEILING_FLOOR_DEFAULT_R = 400.0

# 勝負R 判定の期待値下限 (★C 定義★)。 ふくだ判定 Session 165:
#   旧案の tansho_ippon 4条件 (★win_vb_gap>=3 = 過小評価中穴★) は 679R 中 7件しか拾わず、
#   二層化 (様子見廃止) と組むと「年に数件しか買わない」超保守戦略になり機能しなかった。
#   bench 試算で勝負層を 「is_value_bet ∧ win_ev>=1.3」(=C) に広げると 117件/679R・ROI 88.7%
#   (試算中最良) になったため、 ★two_tier の勝負定義を C に切替★。
#   tansho_ippon 4条件に戻したい場合は shobu_predicate=_is_shobu_from_pred を渡す経路を残す。
SHOBU_WIN_EV_MIN = 1.3


# ---------------------------------------------------------------------------
# 勝負判定 (★C 定義 = is_value_bet ∧ win_ev>=1.3★)
# ---------------------------------------------------------------------------

def _is_shobu_relaxed(pred_race: Optional[dict], axis_umaban: int,
                      *, win_ev_min: float = SHOBU_WIN_EV_MIN,
                      margin_max: int = MARGIN_MAX_DEFAULT) -> bool:
    """軸◎ entry の C 条件 (is_value_bet ∧ win_ev>=win_ev_min) を判定。

    ★two_tier_v0 (Session 165) の既定勝負判定★。 tansho_ippon 4条件から
    ★win_vb_gap>=3 (過小評価中穴=679R中17件しか通らない) と rank_w==1 を外した★ 緩和版。
    bench 試算で 117件/679R・ROI 88.7% (試算中最良)。

    条件:
      ① is_value_bet == True       (VB Floor 通過 = novelty/ARd/dev_gap いずれか)
      ② win_ev >= win_ev_min       (期待値 1.3 以上 = 妙味あり)
      (margin_max は互換のため受け取るが C 定義では未使用。 tansho_ippon 厳格版に戻す場合は
       shobu_predicate=_is_shobu_from_pred を渡す経路を使う)

    bets.json は読まない (stale 回避)。 None 安全 (ev=0 で弾く)。
    """
    if not pred_race:
        return False
    entries = pred_race.get("entries") or []
    e = next((x for x in entries if int(x.get("umaban") or -1) == int(axis_umaban)), None)
    if e is None:
        return False
    if not e.get("is_value_bet"):
        return False
    ev = e.get("win_ev") or 0.0
    return float(ev) >= float(win_ev_min)


# ShobuPredicate = (pred_race, axis_umaban, *, margin_max) -> bool
ShobuPredicate = Callable[..., bool]
DEFAULT_SHOBU_PREDICATE: ShobuPredicate = _is_shobu_relaxed


# ---------------------------------------------------------------------------
# 2層分類
# ---------------------------------------------------------------------------

def classify_tier(
    race_eff,
    selection,
    *,
    pred_race: Optional[dict] = None,
    recommend_flag: Optional[bool] = None,
    ceiling_R: Optional[float] = None,
    ceiling_floor_R: float = CEILING_FLOOR_DEFAULT_R,
    margin_max: int = MARGIN_MAX_DEFAULT,
    shobu_predicate: ShobuPredicate = DEFAULT_SHOBU_PREDICATE,
) -> Tuple[str, dict]:
    """2層分類。 返値 = (tier, info)

    tier in {'shobu', 'miokuri'}  (★様子見 'kanshi' は廃止★)

    判定順序 (★この順を厳守★):
      ① 見送り (ceiling_R < floor。 最強の弾き手。 ただし情報不足=+inf なら買う側に倒す)
      ② 勝負  (shobu_predicate=True ∧ selected_plans 非空。 既定 C=is_value_bet ∧ win_ev>=1.3)
      ③ 見送り (それ以外 = 様子見廃止)
    """
    info: dict = {"ceiling_R": None, "recommend_flag": None,
                  "reason": None,
                  "selected_count": len(selection.selected_plans) if selection else 0}

    # ① ceiling 自動計算
    if ceiling_R is None:
        ceiling_R = compute_ceiling_R(race_eff)
    info["ceiling_R"] = ceiling_R

    # ② recommend_flag 自動計算 (pred_race が渡されているとき)
    if recommend_flag is None:
        axis = getattr(race_eff, "axis_umaban", None) if race_eff is not None else None
        recommend_flag = shobu_predicate(pred_race, axis,
                                         margin_max=margin_max) if axis is not None else False
    info["recommend_flag"] = bool(recommend_flag)

    # ----- 判定順序 -----

    # (1) 見送り: ceiling_R < floor は最強の弾き手 (勝負フラグより優先)
    #     ★ただし ceiling_R = +inf (情報不足) は見送らない=安全側=買う★
    if ceiling_R < ceiling_floor_R:
        info["reason"] = (f"miokuri: ceiling_R={ceiling_R:.0f}% < "
                          f"floor={ceiling_floor_R:.0f}%")
        return "miokuri", info

    ceiling_str = f"{ceiling_R:.0f}%" if ceiling_R != float("inf") else "+inf"

    # (2) 勝負: tansho_ippon 4条件 AND ∧ selected_plans 非空
    if bool(recommend_flag):
        if not selection or not selection.selected_plans:
            info["reason"] = "shobu→miokuri: recommend_flag=True だが selected_plans 空"
            return "miokuri", info
        info["reason"] = f"shobu: recommend_flag=True ceiling_R={ceiling_str}"
        return "shobu", info

    # (3) 見送り (それ以外 = 様子見廃止。 普通レースは買わない)
    info["reason"] = f"miokuri: 非勝負R (flag=False) ceiling_R={ceiling_str} = 様子見廃止"
    return "miokuri", info


# ---------------------------------------------------------------------------
# サイザー本体 (2層別配分)
# ---------------------------------------------------------------------------

def size_race_two_tier(
    race_eff,
    selection,
    *,
    bankroll: int,
    per_race_cap: int = 0,           # ★無視 (tier 配分が常に優先)★
    kelly_fraction: float = 0.25,    # 互換 (勝負R で v2 に渡す)
    per_bet_cap_pct: float = 0.10,   # 互換 (勝負R で v2 に渡す)
    combo_share_of_residual: float = 1.0,
    weight_key: str = "ev",
    pred_race: Optional[dict] = None,
    recommend_flag: Optional[bool] = None,
    ceiling_R: Optional[float] = None,
    tier_share_shobu: float = TIER_SHARE_SHOBU,
    ceiling_floor_R: float = CEILING_FLOOR_DEFAULT_R,
    margin_max: int = MARGIN_MAX_DEFAULT,
    shobu_predicate: ShobuPredicate = DEFAULT_SHOBU_PREDICATE,
) -> RaceSizing:
    """2層分類 → tier 別配分。 fixed_grade_v2 と同じシグネチャ + 二層パラメータ。

    勝負R = fixed_grade_v2 wrap (per_race_cap = bankroll × 15%)
    見送りR = 空 RaceSizing (Kelly/swap/上乗せ 全て触らない)
    """
    rid = getattr(race_eff, "race_id", "unknown")

    # 1) 分類
    tier, classify_info = classify_tier(
        race_eff, selection,
        pred_race=pred_race, recommend_flag=recommend_flag, ceiling_R=ceiling_R,
        ceiling_floor_R=ceiling_floor_R, margin_max=margin_max,
        shobu_predicate=shobu_predicate,
    )
    warnings: List[str] = [f"two_tier={tier} {classify_info['reason']}"]

    # 2) 見送り → 空 RaceSizing
    if tier == "miokuri":
        return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0,
                          combo_yen=0, per_race_cap=0, warnings=warnings)

    # 3) 勝負 → fixed_grade_v2 wrap (cap だけ tier で上書き)
    cap = max(0, int(bankroll * tier_share_shobu))
    if cap <= 0:
        warnings.append("shobu: cap<=0 (bankroll 不足) → 空")
        return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0,
                          combo_yen=0, per_race_cap=0, warnings=warnings)
    rs = size_race_fixed_grade_v2(
        race_eff, selection,
        bankroll=bankroll, per_race_cap=cap,
        kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct,
        combo_share_of_residual=combo_share_of_residual, weight_key=weight_key,
    )
    rs.warnings.insert(
        0, warnings[0] + f" cap={cap} (bankroll×{tier_share_shobu:.0%})")
    return rs


# ---------------------------------------------------------------------------
# registry 登録 (bettype_sizing.SIZERS に追加)
# ---------------------------------------------------------------------------
# ★DEFAULT_SIZER は変更しない★ (本サイザーは opt-in 運用 = bat の --sizing two_tier_v0)。

def _register_sizer() -> None:
    """SIZERS 辞書に two_tier_v0 を登録 (べき等)。"""
    try:
        from ml.strategies import bettype_sizing as _bs
        if TWO_TIER_SIZER not in _bs.SIZERS:
            _bs.SIZERS[TWO_TIER_SIZER] = size_race_two_tier
    except ImportError:
        # bettype_sizing が読めない環境 (テスト隔離等) では何もしない
        pass


_register_sizer()

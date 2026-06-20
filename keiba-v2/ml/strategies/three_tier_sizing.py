#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""three_tier_sizing — 勝負R / 様子見R / 見送りR の3層分類サイザー (Session 164 / 設計案B)

設計正本: docs/auto_purchase_sizing_design.md / メモリ [[bet-adjustment-items]]
ふくだ要望 (6項目) を ★全て満たす★ 設計案B (様子見専用配分派) の実装。

★中核アイデア★:
  - ★勝負R (◎が tansho_ippon 4条件AND を満たす)★
      → ★fixed_grade_v2 を per_race_cap = bankroll × 15% でそのまま wrap★。
        v2 の山型・複0・使い切り保証・swap無効化・fit_legs_to_cap を全て継承する
        (ロジック重複ゼロ・本番 v2 と同じ実払戻成績 = Session 163 +45,700 を継承)。
  - ★様子見R (勝負でも見送りでもない普通レース)★
      → ★KANSHI_SHARES 自前配分★ (per_race_cap = bankroll × 3%)。
        ふくだ「複以外の全券種に薄く撒く」を直訳: 単/馬連/ワイド/馬単/三連複/三連単。
        ★fukusho は含めない★ ([[character-betting-personas]] へ移譲)。
        様子見専用 ★券種ゲート★ (W>=25% / P>=50% or 60%) を独立に持つ。
        ゲート不通過券種の share は ★捨てる★ (再正規化しない=広く薄くの本義)。
  - ★見送りR (ceiling_R < 1000%)★
      → 空 RaceSizing (Kelly/swap/上乗せ いずれも触らない)。
        ただし ★ceiling_R が +inf (情報不足) なら見送らない★ ([[feedback_odds_gate_hindsight]]
        規律 = 情報不足は買う側に倒す)。

★判定順序★ (= 結果を決める): 見送り > 勝負 > 様子見 (見送りが最強の弾き手・最初に判定)。
  ただし ceiling_R = +inf (情報不足) は見送らない=安全側=買う。

★純粋関数モジュール★ (副作用なし・I/O なし・DB アクセスなし)。 fixed_grade_v2 は import のみ
  で一切変更しない。 registry 登録は bettype_sizing 側 (SIZERS 辞書) で行うが、 DEFAULT_SIZER は
  ★fixed_grade_v2 のまま維持★ (本サイザーは opt-in 運用 = bat の --sizing three_tier_v0)。

★重大な注意 (本番投入前の必須検証)★:
  ceiling_floor_R = 1000% は ★骨格段階・要実払戻検証★ ([[feedback_odds_gate_hindsight]] 規律)。
  Session 163 で SKIP_MAX_ODDS_FLOOR を 5.0→0.0 に無効化した経緯から、 1000% は更に厳しいので
  「降りる対象の方が ROI 高い」リスクが残る。 ml/analyze/bench_three_tier_v0.py 相当を回す宿題。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from ml.strategies.bettype_sizing import (
    ANCHOR_BET_TYPES,
    BET_UNIT_YEN,
    MIN_BET_YEN,
    RaceSizing,
    SizedLeg,
    _alloc_inverse_odds,
    _legs_key,
    _max_synthetic_odds,
    fit_legs_to_cap,
    size_race_fixed_grade_v2,
)


# ---------------------------------------------------------------------------
# 定数 (ふくだ要望 6項目を満たす本番値)
# ---------------------------------------------------------------------------

THREE_TIER_SIZER = "three_tier_v0"

# tier 別の per_race cap (残高に対する割合)。 ふくだ要望①「勝負15% / 様子見3%」を直訳。
TIER_SHARE_SHOBU = 0.15      # 勝負R = bankroll × 15%
TIER_SHARE_KANSHI = 0.03     # 様子見R = bankroll × 3%

# 見送り閾値 (ふくだ要望②「ceiling<1000% なら見送り」)。 1000% = 合成オッズ10倍。
#   ceiling_R = race_eff.plans の synthetic_odds 最大 × 100 (倍率→回収率%)。
#   ★骨格段階・要実払戻検証★ ([[feedback_odds_gate_hindsight]] 規律 = 検証宿題)。
CEILING_FLOOR_DEFAULT_R = 1000.0

# 勝負判定 (tansho_ippon 4条件 AND) の margin 上限。
#   backtest 整合 = ★60 固定★ (bet_engine.PRESETS['tansho_ippon'].win_max_predicted_margin)。
#   ライブ再現したい場合は scheduler 側で 76 を渡す経路だけ残す (LIVE_MARGIN_OFFSET=16)。
MARGIN_MAX_DEFAULT = 60

# 様子見R 専用 券種ゲート (W=軸の勝率 / P=軸の複勝確率)。 ふくだ要望④。
#   W>=25% → 単/馬単/三連単 (頭固定の3券種)
#   P>=50% (頭数<8) or 60% (頭数>=8) → 馬連/ワイド/三連複 (連系の3券種)
#   三連複は ★常に 60%★ (8頭以上前提の券種だから)。
KANSHI_W_MIN_DEFAULT = 0.25
KANSHI_P_MIN_SMALL_DEFAULT = 0.50    # 頭数 < 8 (= 7頭以下) のときの P 閾値
KANSHI_P_MIN_LARGE_DEFAULT = 0.60    # 頭数 >= 8 / 三連複は常にこちら
KANSHI_SMALL_THRESHOLD = 8           # 8 未満 = 小頭数

# 様子見R の券種別シェア (合計 1.00、 ★fukusho 含まない★)。 ふくだ要望③「複以外の全券種」直訳。
#   ゲート不通過券種の share は ★捨てる★ (再正規化しない=広く薄くの本義)。
#   合計 = 0.10 + 0.20 + 0.20 + 0.15 + 0.20 + 0.15 = 1.00
KANSHI_SHARES_DEFAULT: Dict[str, float] = {
    "tansho":     0.10,    # 単 (アンカー・W>=25% で出る)
    "umaren":     0.20,    # 馬連 (P>=50%/60% で出る)
    "wide":       0.20,    # ワイド (P>=50%/60% で出る)
    "umatan":     0.15,    # 馬単 (W>=25% で出る)
    "sanrenpuku": 0.20,    # 三連複 (P>=60% で出る・常に大頭数閾値)
    "sanrentan":  0.15,    # 三連単 (W>=25% で出る)
    # ★fukusho は含めない★ = ふくだ「複以外」直訳 + [[character-betting-personas]] へ移譲。
}


# ---------------------------------------------------------------------------
# 補助関数
# ---------------------------------------------------------------------------

def compute_ceiling_R(race_eff) -> float:
    """配当の天井を回収率 % で返す (1000.0 = 1000% = 合成10倍)。

    全 plan の synthetic_odds 最大 × 100。 情報不足 (全欠損 or plans 空) は ★+inf★ を返す
    ([[feedback_odds_gate_hindsight]] 規律 = 情報不足は買う側に倒す = 見送らない)。

    印 top-3 でフィルタしない (案A同型): plan は selection 経路で「軸+相手 N頭」に既に絞られて
    いる = 印 top-3 等価。
    """
    if race_eff is None:
        return float("inf")
    plans = getattr(race_eff, "plans", None)
    if not plans:
        return float("inf")
    top = _max_synthetic_odds(race_eff)   # Optional[float] (倍率)
    if top is None:
        return float("inf")               # 情報不足=安全側=買う (見送らない)
    return float(top) * 100.0             # 倍率 → 回収率 %


def _is_shobu_from_pred(pred_race: Optional[dict], axis_umaban: int,
                        *, margin_max: int = MARGIN_MAX_DEFAULT) -> bool:
    """軸◎ entry の tansho_ippon 4 条件 AND を再計算。

    条件 (bet_engine.PRESETS['tansho_ippon'] と完全に同じ):
      ① rank_w == 1               (W順位1位 = 最強)
      ② win_vb_gap >= 3            (odds_rank - rank_w が3以上 = 過小評価)
      ③ win_ev >= 1.3              (期待値1.3以上)
      ④ predicted_margin <= 60     (能力値=IDM scale。 ライブは 76 を渡す経路あり)
      かつ
      ⑤ is_value_bet == True       (VB Floor 通過 = novelty/ARd/dev_gap いずれか)

    bets.json は読まない (stale 問題回避・[[gotchas]])。 None 安全 (rank_w=99/gap=0/ev=0/margin=999)。
    """
    if not pred_race:
        return False
    entries = pred_race.get("entries") or []
    e = next((x for x in entries if int(x.get("umaban") or -1) == int(axis_umaban)), None)
    if e is None:
        return False
    if not e.get("is_value_bet"):
        return False
    rank_w = e.get("rank_w") or 99
    gap = e.get("win_vb_gap") or 0
    ev = e.get("win_ev") or 0.0
    margin = e.get("predicted_margin")
    if margin is None:
        margin = 999
    return (int(rank_w) == 1
            and int(gap) >= 3
            and float(ev) >= 1.3
            and float(margin) <= float(margin_max))


def _passes_kanshi_gates(
    race_eff,
    *,
    w_min: float = KANSHI_W_MIN_DEFAULT,
    p_min_small: float = KANSHI_P_MIN_SMALL_DEFAULT,
    p_min_large: float = KANSHI_P_MIN_LARGE_DEFAULT,
    small_threshold: int = KANSHI_SMALL_THRESHOLD,
) -> Tuple[Set[str], dict]:
    """様子見R 専用 券種ゲート判定。

    軸◎ の W (=win_prob) と P3 (=fukusho plan.hit_prob 優先・無ければ pred_p フォールバック) で
    {tansho, umatan, sanrentan} (頭固定3券種) と {umaren, wide} (連系小頭数券種) と
    {sanrenpuku} (連系大頭数券種) を ★独立に★ 通過判定する。

    返値: (passed_set, info_dict)
      passed_set = {'tansho','umaren','wide','umatan','sanrenpuku','sanrentan'} の部分集合
      info_dict = {'w_axis': float|None, 'p_axis': float|None, 'p_floor': float, 'n_runners': int}
    """
    passed: Set[str] = set()
    info: dict = {"w_axis": None, "p_axis": None, "p_floor": p_min_large, "n_runners": 0}

    if race_eff is None:
        return passed, info

    axis = getattr(race_eff, "axis_umaban", None)
    n_runners = getattr(race_eff, "num_runners", None) or 0
    info["n_runners"] = int(n_runners)
    strengths = getattr(race_eff, "strengths", None) or []
    plans = getattr(race_eff, "plans", None) or []

    # (a) W ゲート: 軸◎ の win_prob (= HorseStrength.win_prob = 正規化 pred_proba_w_cal)
    axis_strength = next((s for s in strengths if s.umaban == axis), None)
    w_axis = float(axis_strength.win_prob) if axis_strength is not None else None
    info["w_axis"] = w_axis
    if w_axis is not None and w_axis >= w_min:
        passed.update({"tansho", "umatan", "sanrentan"})

    # (b) P ゲート: 軸◎ の P3 (top3 確率)。 真実源 = fukusho plan.hit_prob (ハーヴィル正本)。
    #     fukusho plan が無いケース (オッズ未取得等) は HorseStrength.pred_p をフォールバック。
    fukusho_plan = next((p for p in plans
                        if getattr(p, "bet_type", None) == "fukusho"), None)
    p_axis: Optional[float] = None
    if fukusho_plan is not None:
        hp = getattr(fukusho_plan, "hit_prob", None)
        if hp is not None:
            p_axis = float(hp)
    if p_axis is None and axis_strength is not None:
        pp = getattr(axis_strength, "pred_p", None)
        if pp is not None:
            p_axis = float(pp)
    info["p_axis"] = p_axis

    if p_axis is not None:
        # 連系 (馬連/ワイド): 頭数で閾値を切替
        p_small_floor = p_min_small if int(n_runners) < int(small_threshold) else p_min_large
        info["p_floor"] = p_small_floor
        if p_axis >= p_small_floor:
            passed.update({"umaren", "wide"})
        # 三連複: 常に大頭数閾値 (★8頭以上前提の券種だから★)
        if p_axis >= p_min_large:
            passed.add("sanrenpuku")

    return passed, info


def _kanshi_effective_bet_types(passed: Set[str], selection) -> Set[str]:
    """ゲート通過 ∧ selection.selected_plans に存在 = EV/vs_tansho の最終AND。

    selection は bettype_selection が EV>=1.0 (combo は 0.85) かつ vs_tansho=='gt' で既に
    絞った後の結果。 ここで AND を取ることで「ゲート通過 ∧ 広げる相対妙味あり ∧ EV良し」を
    満たした券種だけが残る。
    """
    if selection is None:
        return set()
    sel_types: Set[str] = {sp.bet_type for sp in selection.selected_plans}
    return passed & sel_types


def classify_tier(
    race_eff,
    selection,
    *,
    pred_race: Optional[dict] = None,
    recommend_flag: Optional[bool] = None,
    ceiling_R: Optional[float] = None,
    ceiling_floor_R: float = CEILING_FLOOR_DEFAULT_R,
    margin_max: int = MARGIN_MAX_DEFAULT,
) -> Tuple[str, dict]:
    """3層分類。 返値 = (tier, info)

    tier in {'shobu', 'kanshi', 'miokuri'}

    判定順序 (★この順を厳守★):
      ① 見送り (最強の弾き手・最初に判定。 ただし情報不足なら買う側に倒す)
      ② 勝負  (tansho_ippon 4条件 AND)
      ③ 様子見 (それ以外。 selected_plans 空なら fallback で 'miokuri')
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
        recommend_flag = _is_shobu_from_pred(pred_race, axis,
                                              margin_max=margin_max) if axis is not None else False
    info["recommend_flag"] = bool(recommend_flag)

    # ----- 判定順序 -----

    # (1) 見送り: ceiling_R < floor は最強の弾き手 (勝負フラグより優先)
    #     ★ただし ceiling_R = +inf (情報不足) は見送らない=安全側=買う★
    if ceiling_R < ceiling_floor_R:
        info["reason"] = (f"miokuri: ceiling_R={ceiling_R:.0f}% < "
                          f"floor={ceiling_floor_R:.0f}%")
        return "miokuri", info

    # (2) 勝負: tansho_ippon 4条件 AND
    if bool(recommend_flag):
        if not selection or not selection.selected_plans:
            info["reason"] = "shobu→miokuri: recommend_flag=True だが selected_plans 空"
            return "miokuri", info
        ceiling_str = f"{ceiling_R:.0f}%" if ceiling_R != float("inf") else "+inf"
        info["reason"] = f"shobu: recommend_flag=True ceiling_R={ceiling_str}"
        return "shobu", info

    # (3) 様子見 (それ以外)
    if not selection or not selection.selected_plans:
        info["reason"] = "miokuri: selected_plans 空 (kanshi fallback)"
        return "miokuri", info
    ceiling_str = f"{ceiling_R:.0f}%" if ceiling_R != float("inf") else "+inf"
    info["reason"] = f"kanshi: ceiling_R={ceiling_str} / flag=False"
    return "kanshi", info


# ---------------------------------------------------------------------------
# サイザー本体 (3層別配分)
# ---------------------------------------------------------------------------

def size_race_three_tier(
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
    tier_share_kanshi: float = TIER_SHARE_KANSHI,
    ceiling_floor_R: float = CEILING_FLOOR_DEFAULT_R,
    margin_max: int = MARGIN_MAX_DEFAULT,
    kanshi_shares: Optional[Dict[str, float]] = None,
    kanshi_w_min: float = KANSHI_W_MIN_DEFAULT,
    kanshi_p_min_small: float = KANSHI_P_MIN_SMALL_DEFAULT,
    kanshi_p_min_large: float = KANSHI_P_MIN_LARGE_DEFAULT,
    kanshi_small_threshold: int = KANSHI_SMALL_THRESHOLD,
) -> RaceSizing:
    """3層分類 → tier 別配分。 fixed_grade_v2 と同じシグネチャ + 三層パラメータ。

    勝負R = fixed_grade_v2 wrap (per_race_cap = bankroll × 15%)
    様子見R = KANSHI_SHARES 自前配分 (per_race_cap = bankroll × 3%)
    見送りR = 空 RaceSizing (Kelly/swap/上乗せ 全て触らない)
    """
    rid = getattr(race_eff, "race_id", "unknown")
    shares = kanshi_shares if kanshi_shares is not None else KANSHI_SHARES_DEFAULT

    # 1) 分類
    tier, classify_info = classify_tier(
        race_eff, selection,
        pred_race=pred_race, recommend_flag=recommend_flag, ceiling_R=ceiling_R,
        ceiling_floor_R=ceiling_floor_R, margin_max=margin_max,
    )
    warnings: List[str] = [f"three_tier={tier} {classify_info['reason']}"]

    # 2) 見送り → 空 RaceSizing
    if tier == "miokuri":
        return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0,
                          combo_yen=0, per_race_cap=0, warnings=warnings)

    # 3) 勝負 → fixed_grade_v2 wrap (cap だけ tier で上書き)
    if tier == "shobu":
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

    # 4) 様子見 → KANSHI_SHARES 自前配分
    cap = max(0, int(bankroll * tier_share_kanshi))
    if cap <= 0:
        warnings.append("kanshi: cap<=0 (bankroll 不足) → 空")
        return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0,
                          combo_yen=0, per_race_cap=0, warnings=warnings)

    axis = getattr(race_eff, "axis_umaban", None)
    axis_odds = getattr(race_eff, "axis_odds", None)
    plans = getattr(race_eff, "plans", None) or []

    # (4a) 券種ゲート評価
    passed, gate_info = _passes_kanshi_gates(
        race_eff,
        w_min=kanshi_w_min, p_min_small=kanshi_p_min_small,
        p_min_large=kanshi_p_min_large, small_threshold=kanshi_small_threshold,
    )
    effective = _kanshi_effective_bet_types(passed, selection)
    w_disp = f"{gate_info['w_axis']:.2f}" if gate_info["w_axis"] is not None else "N/A"
    p_disp = f"{gate_info['p_axis']:.2f}" if gate_info["p_axis"] is not None else "N/A"
    warnings.append(f"kanshi gates: passed={sorted(passed)} "
                    f"effective={sorted(effective)} "
                    f"W={w_disp} P={p_disp}/{gate_info['p_floor']:.2f}")

    if not effective:
        warnings.append("kanshi: 全券種ゲート不通過 → 見送り相当")
        return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0,
                          combo_yen=0, per_race_cap=cap, warnings=warnings)

    # (4b) eff_by_key (best plan 選定用)。 入れ子 (馬連◎-相手2/3/4) の重複買い回避。
    eff_by_key: Dict[Tuple[str, tuple], "object"] = {}
    for p in plans:
        eff_by_key.setdefault((p.bet_type, _legs_key(p.legs)), p)

    # 券種ごとに最良 plan を選ぶ (EV 最大 → 同点なら点数多い方 = v1/v2 と同型 dedup)
    best_plan_by_type: Dict[str, "object"] = {}
    for (bt, _lk), pl in eff_by_key.items():
        if bt not in effective:
            continue
        if pl.expected_return is None and bt not in ("tansho", "fukusho"):
            continue   # 市場オッズ未取得の combo は買わない (EV 計算不能)
        cur = best_plan_by_type.get(bt)
        if cur is None or (
            (pl.expected_return or 0.0, len(pl.legs)) >
            ((cur.expected_return or 0.0), len(cur.legs))
        ):
            best_plan_by_type[bt] = pl

    legs: List[SizedLeg] = []

    # (4c) 券種ごとに bucket = cap × share を割り当てる
    #      ★ゲート不通過 / plan 無し券種の share は捨てる (再正規化しない)★
    for bt, share in shares.items():
        if bt not in effective:
            continue
        bucket = (int(cap * share) // BET_UNIT_YEN) * BET_UNIT_YEN
        if bucket < MIN_BET_YEN:
            continue

        if bt == "tansho":
            # 単勝 leg = 軸◎ 1点
            if axis is None or axis_odds is None or axis_odds <= 1.0:
                warnings.append("kanshi tansho: axis_odds 無効でスキップ")
                continue
            plan = best_plan_by_type.get("tansho")
            label = plan.label if plan else "単勝 ◎"
            hit = plan.hit_prob if plan else None
            legs.append(SizedLeg(rid, "tansho", [axis], bucket, label,
                                 axis_odds, None, hit,
                                 f"kanshi tansho share={share:.0%}"))
        else:
            # 複合券種 = plan 内 leg を逆オッズ配分
            plan = best_plan_by_type.get(bt)
            if plan is None or not plan.legs:
                warnings.append(f"kanshi {bt}: plan 無くスキップ")
                continue
            for leg, o, amt in _alloc_inverse_odds(plan.legs, plan.odds_legs, bucket):
                if amt < MIN_BET_YEN:
                    continue
                legs.append(SizedLeg(rid, bt, list(leg), amt, plan.label,
                                     o, plan.expected_return, plan.hit_prob,
                                     f"kanshi {bt} share={share:.0%}"))

    # (4d) 使い切り保証 ★無し★ (様子見は捨てる=広く薄くの本義)。
    #      勝負R との明確な役割分担: 勝負=使い切る・様子見=広く薄く。

    # (4e) per_race cap で最終 truncate (アンカー保護)
    pre_total = sum(l.amount for l in legs)
    n_dropped = 0
    if cap > 0 and pre_total > cap:
        legs, n_dropped = fit_legs_to_cap(legs, cap)
        warnings.append(f"per_race按分 {pre_total}->{sum(l.amount for l in legs)} "
                        f"drop={n_dropped}")

    total = sum(l.amount for l in legs)
    anchor_yen = sum(l.amount for l in legs if l.bet_type in ANCHOR_BET_TYPES)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=anchor_yen,
                      combo_yen=total - anchor_yen, per_race_cap=cap,
                      n_dropped=n_dropped, warnings=warnings)


# ---------------------------------------------------------------------------
# registry 登録 (bettype_sizing.SIZERS に追加)
# ---------------------------------------------------------------------------
# ★DEFAULT_SIZER は変更しない★ (本サイザーは opt-in 運用 = bat の --sizing three_tier_v0)。
# 循環 import を避けるため、 ここで bettype_sizing.SIZERS に直接登録する (bettype_sizing が
#   先に load された後で本モジュールが import される前提)。 import 時の副作用を最小化。

def _register_sizer() -> None:
    """SIZERS 辞書に three_tier_v0 を登録 (べき等)。"""
    try:
        from ml.strategies import bettype_sizing as _bs
        if THREE_TIER_SIZER not in _bs.SIZERS:
            _bs.SIZERS[THREE_TIER_SIZER] = size_race_three_tier
    except ImportError:
        # bettype_sizing が読めない環境 (テスト隔離等) では何もしない
        pass


_register_sizer()

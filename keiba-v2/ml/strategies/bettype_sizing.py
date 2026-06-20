#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""multi-bettype サイジング層 (Session 140 / 全レース multi-bettype 自動投票 v1)

bettype_selection が選んだ券種 (SelectedPlan) に「いくら賭けるか」を割り当てる純関数層。
DB/IO/subprocess なし。 bettype_scheduler から呼ばれる。

★方針 (ふくだ判断 Session140): 「アンカー◎単/複 = 既存 freebudget Kelly」+「複合 = per_race
  残予算を EV 比例配分 (plan 内は逆オッズ)」。
  複合券種の各 leg (馬連3点等) は ★排反/相関★ (同時に的中しない) なので、 naive per-leg
  Kelly は oversize になり理論的に誤り。 → 複合は plan 単位の固定予算 (per_race 残) を
  EV 比例で配分し、 plan 内 leg は合成オッズ定義 (stakeₖ∝1/oₖ) と整合する逆オッズ配分。
  元本リスクの主はアンカー Kelly、 複合は上限内の widen に留める (保守)。

★アンカーの Kelly 式は freebudget.py:182-190 を忠実にミラー (同額になることを test で担保)。
  アンカー◎単: p = 軸の pred_proba_w_cal (= HorseStrength.pred_w, calibrated), odds = axis_odds。
  アンカー◎複: p = fukusho plan の hit_prob (harville place 確率), odds = place_odds_min (最低値=保守)。

入力: be.RaceEfficiency (各 plan の odds_legs/EV/hit_prob) + bettype_selection.BetSelection。
出力: RaceSizing (SizedLeg のリスト + 内訳)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ml.strategies.kelly import BET_UNIT_YEN, MIN_BET_YEN, kelly_amount
from ml.strategies import bettype_fund as bf  # noqa: E402

# アンカー (◎単/複) = 排反/相関の無い独立 1 点なので Kelly を厳密適用してよい券種。
ANCHOR_BET_TYPES = ("tansho", "fukusho")
# 券種が順序系 (馬単/三連単 = 着順) か。 template_flat の odds 照合で frozenset/tuple を切替。
BET_SPEC_ORDERED: Dict[str, bool] = {
    "tansho": False, "fukusho": False, "umaren": False, "wide": False,
    "umatan": True, "sanrenpuku": False, "sanrentan": True,
}
# 各サイザーの登録名 (★名前は固定★。 DEFAULT_SIZER は「既定で使う名前」を指すだけにする。
#   registry のキーは KELLY_SIZER 等の固定名を使い、 既定差し替えで key が壊れないようにする)。
KELLY_SIZER = "anchor_kelly_combo_ev"
ADAPTIVE_SIZER = "adaptive_fund"

# ---------------------------------------------------------------------------
# fixed_grade_v1: 評価ベース固定配分サイザー (ふくだ Session 161 / 配分チューニング)
# ---------------------------------------------------------------------------
# 動機: 現行 size_race は単勝アンカーを Kelly (bankroll=10000固定) で出すため本命でも
#   100〜200円に潰れ、 ライブ実測で単勝シェアが 3.5% しかない (combo が per_race 残予算を
#   丸ごと食う)。 ふくだ方針 [[feedback-betting-philosophy]] §5「配分はオッズで歪めない」を
#   文字通り実装し、 単勝/複(or wide) を ◎の格 (composite) で決める ★固定割合★ にする。
#   ★Kelly は呼ばない★ (これが核心。 オッズが額を支配しない)。
#
# tier は ★◎の格 = composite gap (◎ と ○ の差)★ で分ける (オッズ非依存)。 絶対 z でなく
#   gap を使う理由: z-score 上位 1 位はどのレースでも平均より高く出る (常に strong 化) ため
#   団子と本命断然を区別できない。 「◎が○からどれだけ抜けているか」= ふくだの言う「◎の格」。
#   share は per_race_cap に対する割合 (tansho, place_or_wide)。 残りは従来通り combo に EV
#   比例で回す (方針3=フォメ据え置き → strong でも combo を半分残す)。
#   6/13 実測の gap 分布: 四分位 0.25 / 0.64 / 1.38 (min 0.03 / max 2.35)。
FIXED_GRADE_SIZER = "fixed_grade_v1"
# ★本番既定サイザー (Session 161 でふくだ判断: fixed_grade_v1 を本番昇格)★。
#   scheduler/race CLI の --sizing 既定 = これ。 bat は --sizing 未指定なのでこの値が live に効く。
#   Kelly に戻すときは KELLY_SIZER を指すだけ (registry の名前は不変なので安全)。
DEFAULT_SIZER = FIXED_GRADE_SIZER
GRADE_STRONG_GAP = 1.0    # composite gap(◎-○) >= → strong ◎ (本命が抜けている)
GRADE_WEAK_GAP = 0.4      # < → weak ◎ (◎と○が僅差の団子)
#                          tansho  place_or_wide   (残り = combo residual)
FIXED_SHARES = {
    "strong": (0.30, 0.20),   # 30%単 / 20%複or wide / 50%combo (本命断然=単を厚く・combo半分維持)
    "mid":    (0.25, 0.15),   # 25 / 15 / 60
    "weak":   (0.15, 0.10),   # 軸が僅差なら単を薄く・combo(流し)に逃がす (15/10/75)
}
# 複勝 place_odds_min がこの値未満 = 低オッズ薄利非対称 → 同じ◎軸のワイドに置換するロジック。
#   ★Session 161 で ★無効化 (0.0)★ に確定★。 ふくだ「人気馬複勝は薄利」の直感は配分の見た目
#   としては正しいが、 ★predictions 実払戻 (haraimodoshi) で検証したら置換は一律マイナス★:
#     floor 1.9→-1.8pt / 1.5→-1.4 / 1.3→-1.1 / 1.2→-0.6 / 1.1→-0.3 (全て複勝維持OFFが最良・単調)。
#   理由: 低オッズ複勝は ★当たりやすく実回収率が高い★ (現行期 fuku ROI 84% > wide 74%)。
#   薄利非対称のデメリットを高的中の回収が上回る → 置換しない方が常に良い。
#   [[feedback_odds_gate_hindsight]] 規律の実例 (cache logic で良く見えたオッズ条件が実払戻で消失)。
#   floor=0.0 で place_odds はどの値でも floor 未満にならず置換は発火しない (= 複勝固定額で維持)。
#   コードは残置 (将来 券種別/条件別に再検証する場合の足場)。 sweep: c:/tmp/v3b_swap_sweep.py。
WIDE_SWAP_PLACE_ODDS_FLOOR = 0.0


# ---------------------------------------------------------------------------
# fixed_grade_v2: v1 + ★見送り★ + ★堅いレースほど combo を厚く★ (ふくだ Session 162)
# ---------------------------------------------------------------------------
# 動機 [[feedback_betting_philosophy]] §4: ふくだ「そもそもの始まり = 単で当てても儲からない
#   レースは、 三連単でどうかも考えてあげる」。 ◎が断然 (単勝が安い) レースは単で当てても天井が
#   低い → ★単/複を薄くして combo (馬連〜三連単) を厚くし配当を作る★。 それでも作れる買い目の
#   配当の天井が低ければ ★見送る (降りる)★。 元々 evaluate_and_select で見送れていた機能を、
#   「買い目の最高配当」基準で明示的に持つ。
#
# v1 との差分は配分のみ (Kelly 不使用・固定配分・swap 無効は v1 と同じ):
#   ★FIXED_SHARES を ★逆転★★: v1 は strong=単30%厚く だったが、 ふくだ構想では strong
#       (◎断然=単安い) こそ単を薄く combo を厚くする。 weak (団子) は軸不確実 → 単薄く流しへ。
#       = strong も weak も単は薄め、 mid (手頃な◎) で単を一番厚く取る山型。
#
# ★★★見送りゲートは ★実払戻で害と確定 → 無効化 (SKIP_MAX_ODDS_FLOOR=0.0)★ (Session 163)★★★。
#   検証: validate_v2_skip_gate.py が predictions (直前オッズ=本番同条件・リークなし) で見送り対象を
#   haraimodoshi 実払戻で精算 → ★降りる対象の方が買う群より ROI が高かった★ (2期間で再現):
#     2026/01-03 (679R): keep 78.5% vs ★skip 94.5%(的中87%)★ / ゲート無し全体 80.6%。
#     2025/09-12 (1075R): keep 77.3% vs ★skip 92.2%(的中79%)★ / ゲート無し全体 79.3%。
#   floor を 3〜8倍どこに振っても買う群 ROI はゲート無し全体を一度も超えない (儲かる設定が無い)。
#   機構: 「配当の天井が低い」=◎断然で堅い (的中率高) レース → 低オッズ単複が手堅く回収する。
#   Session 161 の複勝→ワイド置換棄却と完全に同じ罠 ([[feedback_odds_gate_hindsight]])。
#   → ★floor=0.0 で見送りゲートを止める★ (空 RaceSizing は返らない=全レース買う)。 配分の山型は維持。
#   コードは残置 (将来 別の見送り軸=オッズ非依存特性で再設計する場合の足場)。
FIXED_GRADE_V2_SIZER = "fixed_grade_v2"
# ★★★Session 163: 複勝をメイン馬券から外した (複 share=0)★★★
#   ふくだ「ワイドや単より安く数十円取りにいくだけの複に意味があるのか」→ 実払戻で裏取り:
#     現行 v2 の複は ★53% が「ゴミ複」(複オッズ<1.5倍 & combo に埋もれ)★、 複が当たっても
#     利益の中央値 80円・57% が +100円未満 (数十円ゴミ)。 ROI 85% に見えたのは「+30〜80円の
#     手堅い的中」が回収率を支えていただけ = ★金は増えないが当たった感だけ・予算が単/comboを削る★。
#   ふくだ設計: 複勝の価値 (高的中・死なない ROI85%) は ★複勝専門キャラ (転がし党/本命党)★ が
#     別 bankroll で回収する → メインは「天井を取る」(単+combo・ボーナス作戦) に専念。
#   = 複 share を 0 にし、 その予算を combo に回す ([[character-betting-personas]] へ複勝を移譲)。
#   ★トレードオフ (承知の上)★: メイン単体の ROI は実払戻で -0.7〜-1.5pt・的中率 58→37% に落ちる
#     (複の手堅い回収を失う)。 が、 複勝はキャラが拾うので ★システム全体では収益源は失わない★
#     (見かけの ROI 低下 = 複勝を別レイヤーに移譲しただけ)。 検証: compare_fukusho_share.py。
#   ★strong は単を薄く combo へ・mid で単最厚・weak は流しへ★ (山型) は維持。 第2要素は 0。
FIXED_SHARES_V2 = {
    "strong": (0.15, 0.0),    # ◎断然 → 単薄く 15/0/85 (複なし・combo=85%厚く=天井狙い)
    "mid":    (0.30, 0.0),    # 手頃な◎ → 単を一番厚く 30/0/70
    "weak":   (0.15, 0.0),    # 団子=軸不確実 → 単薄く流しへ 15/0/85
}
# 見送り閾値: このレースで作れる最高の合成オッズ (配当の天井) がこの倍率未満なら降りる。
#   ★Session 163 で実払戻検証 → 害と確定 → 0.0 (無効化)★。 floor>0 だと「堅い高的中レース」を
#   捨てて ROI を落とす ([[feedback_odds_gate_hindsight]] の罠)。 0.0 で _skip_max_odds_floor>0
#   ガードに掛からず空 RaceSizing は返らない (= 全レース買う)。 再設計時は ★オッズ非依存特性★ で。
SKIP_MAX_ODDS_FLOOR = 0.0


def _legs_key(legs) -> tuple:
    """plan.legs (List[List[int]]) を hashable key 化 (順序保持)。"""
    return tuple(tuple(int(h) for h in leg) for leg in legs)


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------

@dataclass
class SizedLeg:
    race_id: str
    bet_type: str
    horses: List[int]            # 買い目の馬番 (馬単/三連単は順序保持)
    amount: int                  # 100円単位
    plan_label: str
    leg_odds: Optional[float]    # この点の市場オッズ (None=未取得)
    ev: Optional[float]          # 所属 plan の期待リターン (アンカーは None)
    hit_prob: Optional[float]
    note: str = ""


@dataclass
class RaceSizing:
    race_id: str
    legs: List[SizedLeg]
    total_yen: int
    anchor_yen: int
    combo_yen: int
    per_race_cap: int
    n_dropped: int = 0
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Kelly (アンカー専用) は ml/strategies/kelly.py が SSoT。 freebudget の単勝
# サイジングと同一式 (同額になることを test で担保)。 上の import で kelly_amount を
# 取り込み、 size_race から呼ぶ。
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# per_race cap 按分 (freebudget_scheduler.fit_result_to_cap と同型 + アンカー保護)
# ---------------------------------------------------------------------------

def fit_legs_to_cap(legs: List[SizedLeg], cap: int, *,
                    unit: int = BET_UNIT_YEN) -> Tuple[List[SizedLeg], int]:
    """legs 合計が cap 超なら per_race 以内に按分 (比例縮小→最低unit→低EV drop)。

    ★アンカー (単/複) 保護★: drop は低 EV 順だが、 アンカーの並べ替えキーを +inf 扱いに
    して最後まで残す (複合を先に落とす)。 縮小のみなので 1 点が元値や per_bet_cap を超える
    ことはない。 戻り: (新 legs, dropped 数)。
    """
    total = sum(l.amount for l in legs)
    if cap <= 0 or total <= cap or not legs:
        return legs, 0
    factor = cap / total
    scaled: List[SizedLeg] = []
    for l in legs:
        s = int((l.amount * factor) // unit * unit)
        s = max(unit, s)
        scaled.append(SizedLeg(l.race_id, l.bet_type, l.horses, s, l.plan_label,
                               l.leg_odds, l.ev, l.hit_prob, l.note))
    cur = sum(l.amount for l in scaled)
    dropped = 0
    if cur > cap:
        # 低 EV 順に drop。 アンカーは +inf で最後まで残す (複合を先に落とす)。
        def drop_key(l: SizedLeg) -> float:
            if l.bet_type in ANCHOR_BET_TYPES:
                return float("inf")
            return l.ev if l.ev is not None else 0.0
        order = sorted(range(len(scaled)), key=lambda i: drop_key(scaled[i]))
        keep = [True] * len(scaled)
        for i in order:
            if cur <= cap:
                break
            cur -= scaled[i].amount
            keep[i] = False
            dropped += 1
        scaled = [l for l, k in zip(scaled, keep) if k]
    return scaled, dropped


# ---------------------------------------------------------------------------
# 複合: plan 内 leg を逆オッズ配分
# ---------------------------------------------------------------------------

def _alloc_inverse_odds(legs: List[List[int]], odds_legs: List[Optional[float]],
                        budget: int, *, unit: int = BET_UNIT_YEN,
                        min_bet: int = MIN_BET_YEN,
                        mode: str = "inverse") -> List[Tuple[List[int], Optional[float], int]]:
    """budget を plan 内の各 leg に重み配分 (100円単位、 min 未満は 0)。

    ★mode (Session 168 / 天井変種・既定 inverse = 本番不変)★:
      - "inverse": wᵢ=1/oᵢ (低オッズ=的中寄りに厚く・★天井を抑える★・本番既定)。
      - "flat"   : wᵢ=1    (各点均等・高オッズ点にも同額 → 天井が上がる)。
      - "odds"   : wᵢ=oᵢ   (高オッズ=高配当点に厚く → ★天井を最大化★)。

    オッズ欠損の leg は present の平均重みを割り当て (均等寄り)。 全欠損なら均等配分。
    端数は最大重み leg に寄せて budget を超えない範囲で。 戻り: [(leg, odds, amount), ...]。
    """
    n = len(legs)
    if n == 0 or budget < min_bet:
        return [(leg, (odds_legs[i] if i < len(odds_legs) else None), 0)
                for i, leg in enumerate(legs)]
    present = [(odds_legs[i] if i < len(odds_legs) else None) for i in range(n)]
    if mode == "flat":
        inv = [1.0 for _ in present]
    elif mode == "odds":
        inv = [float(o) if (o and o > 0) else None for o in present]
    else:  # "inverse" (本番既定)
        inv = [(1.0 / o) if (o and o > 0) else None for o in present]
    known = [w for w in inv if w is not None]
    fill = (sum(known) / len(known)) if known else 1.0
    weights = [w if w is not None else fill for w in inv]
    wsum = sum(weights) or 1.0
    amounts = [int((budget * (w / wsum)) // unit) * unit for w in weights]
    amounts = [a if a >= min_bet else 0 for a in amounts]
    # 端数を最大重み leg から順に unit 単位で budget 内まで上乗せ
    leftover = budget - sum(amounts)
    if leftover >= unit:
        for i in sorted(range(n), key=lambda i: weights[i], reverse=True):
            while leftover >= unit and amounts[i] >= min_bet:
                amounts[i] += unit
                leftover -= unit
                break  # 1 leg 1 回だけ上乗せ (薄く広く)
            if leftover < unit:
                break
    return [(legs[i], present[i], amounts[i]) for i in range(n)]


# ---------------------------------------------------------------------------
# 複合 leg サイジング (size_race / fixed_grade で共通。 方針3=フォメ据え置きを共有コード化)
# ---------------------------------------------------------------------------

def _size_combo_legs(rid: str, race_eff, selection, eff_by_key: dict, combo_budget: int, *,
                     weight_key: str = "ev",
                     exclude_keys: frozenset = frozenset(),
                     alloc_mode: str = "inverse",
                     allowed_types: Optional[frozenset] = None) -> List[SizedLeg]:
    """選定 plan の複合券種を combo_budget に EV 比例で配分 → plan 内 alloc_mode で配分。

    ★券種ごとに 1 plan へ dedup★ (最良 EV、 同点なら広い=点数多い方)。 入れ子幅の重複買い回避。
    exclude_keys: (bet_type, _legs_key(legs)) の集合。 アンカーで既に買った plan (例 swapped
    wide) を combo から除外して二重買いを防ぐ。

    ★alloc_mode (Session 168・既定 inverse = 本番不変)★: plan 内 leg の配分方式
      ("inverse"/"flat"/"odds"。 _alloc_inverse_odds に委譲)。 天井変種の検証用。
    ★allowed_types (Session 168・既定 None = 全券種)★: 指定すると ★その券種だけ★ に集中
      (例 frozenset({"sanrenpuku","sanrentan"}) で三連系のみ)。 None なら従来どおり全 combo。
    """
    if combo_budget < MIN_BET_YEN:
        return []
    best_by_type: Dict[str, object] = {}
    for sp in selection.selected_plans:
        if sp.bet_type in ANCHOR_BET_TYPES:
            continue
        if allowed_types is not None and sp.bet_type not in allowed_types:
            continue
        key = (sp.bet_type, _legs_key(sp.legs))
        if key in exclude_keys:
            continue
        plan = eff_by_key.get(key)
        if plan is None or plan.expected_return is None:
            continue   # 市場オッズ未取得 (EV 計算不能) の plan は買わない
        cur = best_by_type.get(sp.bet_type)
        if cur is None or (plan.expected_return, len(plan.legs)) > \
                (cur.expected_return, len(cur.legs)):
            best_by_type[sp.bet_type] = plan
    combo_plans: List[Tuple[object, float]] = []
    for plan in best_by_type.values():
        w = plan.expected_return if weight_key == "ev" else (plan.hit_prob or 0.0)
        if w and w > 0:
            combo_plans.append((plan, float(w)))

    out: List[SizedLeg] = []
    if not combo_plans:
        return out
    wsum = sum(w for _, w in combo_plans) or 1.0
    for plan, w in combo_plans:
        plan_budget = int(combo_budget * (w / wsum))
        if plan_budget < MIN_BET_YEN:
            continue
        for leg, o, amt in _alloc_inverse_odds(plan.legs, plan.odds_legs, plan_budget,
                                               mode=alloc_mode):
            if amt >= MIN_BET_YEN:
                out.append(SizedLeg(rid, plan.bet_type, list(leg), amt, plan.label,
                                    o, plan.expected_return, plan.hit_prob,
                                    "combo EV-prop / inverse-odds"))
    return out


# ---------------------------------------------------------------------------
# サイザー本体
# ---------------------------------------------------------------------------

def size_race(race_eff, selection, *, bankroll: int, per_race_cap: int,
              kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
              combo_share_of_residual: float = 1.0,
              weight_key: str = "ev") -> RaceSizing:
    """RaceEfficiency + BetSelection → 各 leg に amount を付けた RaceSizing。

    アンカー◎単/複 = freebudget Kelly。 複合 = per_race 残予算を EV 比例 → plan 内逆オッズ。
    最終 fit_legs_to_cap で per_race 以内に収める (アンカー保護)。
    """
    legs: List[SizedLeg] = []
    warnings: List[str] = []
    rid = race_eff.race_id
    axis = race_eff.axis_umaban
    axis_odds = race_eff.axis_odds
    # ★bettype_efficiency は同一券種で複数の幅 (馬連◎-相手2/3/4 等、入れ子) を別 plan として
    #   出す。 選定 plan を (bet_type, legs) で正確にマッチし、 複合は券種ごとに 1 つへ dedup
    #   (入れ子の重複買いを防ぐ)。 by_type で潰すと別幅の plan を二重サイジングしてしまう。
    eff_by_key = {(p.bet_type, _legs_key(p.legs)): p for p in race_eff.plans}
    axis_strength = next((s for s in race_eff.strengths if s.umaban == axis), None)
    axis_pred_w = axis_strength.pred_w if axis_strength else None

    sel_tansho = next((sp for sp in selection.selected_plans if sp.bet_type == "tansho"), None)
    sel_fukusho = next((sp for sp in selection.selected_plans if sp.bet_type == "fukusho"), None)

    # (A) アンカー◎単 = freebudget Kelly (p=軸 pred_w calibrated, odds=axis_odds)
    if sel_tansho is not None:
        amt = kelly_amount(axis_pred_w, axis_odds, bankroll=bankroll,
                           kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
        if amt >= MIN_BET_YEN:
            tp = eff_by_key.get(("tansho", _legs_key(sel_tansho.legs)))
            legs.append(SizedLeg(rid, "tansho", [axis], amt,
                                 tp.label if tp else "単勝 ◎", axis_odds,
                                 None, (tp.hit_prob if tp else None),
                                 "anchor freebudget Kelly"))

    # (A') アンカー◎複 = Kelly (p=fukusho hit_prob, odds=place_odds_min 最低値=保守)
    if sel_fukusho is not None:
        fp = eff_by_key.get(("fukusho", _legs_key(sel_fukusho.legs)))
        if fp is not None:
            f_odds = fp.odds_legs[0] if fp.odds_legs else None
            amt = kelly_amount(fp.hit_prob, f_odds, bankroll=bankroll,
                               kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
            if amt >= MIN_BET_YEN:
                legs.append(SizedLeg(rid, "fukusho", [axis], amt, fp.label, f_odds,
                                     None, fp.hit_prob, "anchor place Kelly (保守)"))

    anchor_yen = sum(l.amount for l in legs)

    # (B) 複合 = per_race 残予算を EV 比例で各 plan に配分 → plan 内逆オッズ
    cap_for_residual = per_race_cap if per_race_cap > 0 else bankroll
    residual = max(0, cap_for_residual - anchor_yen)
    combo_budget = int(residual * combo_share_of_residual)
    legs.extend(_size_combo_legs(rid, race_eff, selection, eff_by_key, combo_budget,
                                 weight_key=weight_key))

    # (C) per_race cap で最終 truncate (アンカー保護)
    pre_total = sum(l.amount for l in legs)
    n_dropped = 0
    if per_race_cap > 0 and pre_total > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
        warnings.append(f"per_race按分 {pre_total}->{sum(l.amount for l in legs)} "
                        f"drop={n_dropped}")

    total = sum(l.amount for l in legs)
    anchor_yen = sum(l.amount for l in legs if l.bet_type in ANCHOR_BET_TYPES)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=anchor_yen,
                      combo_yen=total - anchor_yen, per_race_cap=per_race_cap,
                      n_dropped=n_dropped, warnings=warnings)


def size_race_adaptive(race_eff, selection, *, bankroll: int, per_race_cap: int,
                       kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
                       combo_share_of_residual: float = 1.0,
                       weight_key: str = "ev") -> RaceSizing:
    """P2b: BetSelection の fund_mode / kelly_boost + decide_fund で増額・大穴流し・降りる。

    selection.requested_strategy=='adaptive' か fund_mode 付きを想定。 非 adaptive でも
    fund フィールドが無ければ decide_fund を再計算する (dry-run 整合)。
    """
    fund_mode = getattr(selection, "fund_mode", None)
    kelly_boost = getattr(selection, "kelly_boost", 1.0) or 1.0
    if fund_mode is None and selection.requested_strategy == "adaptive":
        decision = bf.decide_fund(
            race_eff, ev_floor=selection.ev_floor, bankroll=bankroll,
            kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
        fund_mode = decision.mode
        kelly_boost = decision.kelly_boost
    elif fund_mode is None:
        decision = bf.decide_fund(
            race_eff, ev_floor=selection.ev_floor, bankroll=bankroll,
            kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
        fund_mode = decision.mode
        kelly_boost = decision.kelly_boost
    else:
        decision = bf.decide_fund(
            race_eff, ev_floor=selection.ev_floor, bankroll=bankroll,
            kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)

    if fund_mode == "skip_all" or not selection.selected_plans:
        return RaceSizing(
            race_id=race_eff.race_id, legs=[], total_yen=0, anchor_yen=0,
            combo_yen=0, per_race_cap=per_race_cap, n_dropped=0,
            warnings=["adaptive: skip_all (降りる)"],
        )

    boosted_kelly = min(kelly_fraction * kelly_boost, 1.0)
    rs = size_race(
        race_eff, selection, bankroll=bankroll, per_race_cap=per_race_cap,
        kelly_fraction=boosted_kelly, per_bet_cap_pct=per_bet_cap_pct,
        combo_share_of_residual=combo_share_of_residual, weight_key=weight_key,
    )

    # 大穴100円流し (selection 側で combo を fund していても sizing で 1 点追加)
    if decision.longshot_yen >= MIN_BET_YEN and decision.longshot_horses:
        ls_key = (decision.longshot_bet_type, _legs_key([decision.longshot_horses]))
        dup = any(
            l.bet_type == decision.longshot_bet_type and l.horses == decision.longshot_horses
            for l in rs.legs
        )
        if not dup:
            rs.legs.append(SizedLeg(
                race_eff.race_id, decision.longshot_bet_type or "umaren",
                list(decision.longshot_horses), decision.longshot_yen,
                decision.longshot_label or "大穴流し",
                decision.longshot_odds, None, None,
                "adaptive longshot flow (100円)"))
            rs.combo_yen += decision.longshot_yen
            rs.total_yen += decision.longshot_yen

    if per_race_cap > 0 and rs.total_yen > per_race_cap:
        rs.legs, n_drop = fit_legs_to_cap(rs.legs, per_race_cap)
        rs.n_dropped += n_drop
        rs.total_yen = sum(l.amount for l in rs.legs)
        rs.anchor_yen = sum(l.amount for l in rs.legs if l.bet_type in ANCHOR_BET_TYPES)
        rs.combo_yen = rs.total_yen - rs.anchor_yen
        rs.warnings.append(f"adaptive cap fit drop={n_drop}")

    if fund_mode:
        rs.warnings.insert(0, f"adaptive/{fund_mode}: {decision.reason}")
    return rs


# ---------------------------------------------------------------------------
# fixed_grade_v1: 評価ベース固定配分サイザー
# ---------------------------------------------------------------------------

def _round_unit(yen: float, *, unit: int = BET_UNIT_YEN) -> int:
    """yen を 100円単位に切り捨て (負値は 0)。"""
    if yen <= 0:
        return 0
    return (int(yen) // unit) * unit


def _composite_gap(race_eff, axis: int) -> float:
    """◎ (axis) と ○ (axis を除く composite 最上位) の composite 差 = 「◎の格」。

    strengths は通常 composite 降順だが順序に依存せず最大2値から算出する。 軸が単独 (相手
    不在) なら gap=axis_composite。 軸が strengths に無ければ 0.0 (weak 扱い)。
    """
    comps = {s.umaban: s.composite for s in race_eff.strengths}
    axis_c = comps.get(axis)
    if axis_c is None:
        return 0.0
    others = [c for u, c in comps.items() if u != axis]
    if not others:
        return axis_c
    return axis_c - max(others)


def _grade_tier(gap: float) -> str:
    """◎の格 (composite gap ◎-○) から tier 名 ('strong'/'mid'/'weak') を返す。"""
    if gap >= GRADE_STRONG_GAP:
        return "strong"
    if gap < GRADE_WEAK_GAP:
        return "weak"
    return "mid"


def _max_synthetic_odds(race_eff) -> Optional[float]:
    """race_eff.plans の最大 synthetic_odds (= このレースで作れる配当の天井)。 無ければ None。

    見送りゲート用: 単/複/combo どう組んでも当たって配当が小さいレースを判定する基準。
    """
    vals = [p.synthetic_odds for p in race_eff.plans
            if p.synthetic_odds is not None and p.synthetic_odds > 0]
    return max(vals) if vals else None


def size_race_fixed_grade(race_eff, selection, *, bankroll: int, per_race_cap: int,
                          kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
                          combo_share_of_residual: float = 1.0,
                          weight_key: str = "ev",
                          _shares_table: Optional[dict] = None,
                          _skip_max_odds_floor: float = 0.0) -> RaceSizing:
    """評価ベース固定配分 (ふくだ Session 161)。 単勝/複(or wide) を ◎の格 (composite) で
    決める ★固定割合★ に。 ★Kelly は呼ばない★ (オッズが額を支配しない・哲学§5)。

    - 単勝◎ = cap × tansho_frac (固定・オッズ非依存。 axis_odds が有効なら必ず emit)。
    - 第2アンカー = 複勝◎ (cap × anchor2_frac)。 ただし place_odds_min が低い (薄利非対称) なら
      同じ◎軸の ★ワイドに置換★ (方針2)。
    - 残り = combo に EV 比例で回す (size_race と同じ _size_combo_legs。 方針3=フォメ据え置き)。

    kelly_fraction / per_bet_cap_pct は他サイザーとのシグネチャ互換のため受け取るが未使用。
    _shares_table: tier→(単,複) の配分表 (None=FIXED_SHARES=v1既定)。 v2 は FIXED_SHARES_V2 を渡す。
    _skip_max_odds_floor: >0 なら ★見送りゲート★。 最大合成オッズ (配当の天井) がこの倍率未満なら
      空 RaceSizing を返す (= 降りる)。 0.0 (既定) = 見送りなし = v1 挙動。
    """
    legs: List[SizedLeg] = []
    warnings: List[str] = []
    rid = race_eff.race_id
    axis = race_eff.axis_umaban
    axis_odds = race_eff.axis_odds
    eff_by_key = {(p.bet_type, _legs_key(p.legs)): p for p in race_eff.plans}
    axis_strength = next((s for s in race_eff.strengths if s.umaban == axis), None)
    if axis_strength is None:
        warnings.append("axis strength 不明 → weak tier 扱い")

    # ★見送りゲート (v2)★: 配当の天井 < floor なら降りる (単で当てても儲からない & combo でも
    #   作れない)。 floor=0 (v1) はスキップしない。 最高合成オッズが取れない (オッズ全欠損) 場合は
    #   判定できないので ★降りない★ (情報不足で見送ると取りこぼす → 安全側=買う)。
    if _skip_max_odds_floor > 0:
        top = _max_synthetic_odds(race_eff)
        if top is not None and top < _skip_max_odds_floor:
            warnings.append(f"見送り: 配当の天井 合成{top:.1f}倍 < {_skip_max_odds_floor:.1f}倍 "
                            f"(単で当てても儲からない・comboでも作れない)")
            return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0, combo_yen=0,
                              per_race_cap=per_race_cap, warnings=warnings)

    gap = _composite_gap(race_eff, axis)
    tier = _grade_tier(gap)
    shares = _shares_table if _shares_table is not None else FIXED_SHARES
    tansho_frac, anchor2_frac = shares[tier]
    cap = per_race_cap if per_race_cap > 0 else bankroll

    sel_tansho = next((sp for sp in selection.selected_plans if sp.bet_type == "tansho"), None)
    sel_fukusho = next((sp for sp in selection.selected_plans if sp.bet_type == "fukusho"), None)

    # (A) 単勝◎ = 固定額 (cap × tansho_frac)。 ★Kelly でなく固定★。
    if sel_tansho is not None and axis_odds is not None and axis_odds > 1.0:
        amt = _round_unit(cap * tansho_frac)
        if amt >= MIN_BET_YEN:
            tp = eff_by_key.get(("tansho", _legs_key(sel_tansho.legs)))
            legs.append(SizedLeg(rid, "tansho", [axis], amt,
                                 tp.label if tp else "単勝 ◎", axis_odds,
                                 None, (tp.hit_prob if tp else None),
                                 f"fixed grade={tier} ({tansho_frac:.0%})"))

    # (A') 第2アンカー = 複勝◎ or (低オッズなら) ワイド置換。
    anchor2_amt = _round_unit(cap * anchor2_frac)
    fukusho_plan = eff_by_key.get(("fukusho", _legs_key(sel_fukusho.legs))) if sel_fukusho else None
    place_odds = (fukusho_plan.odds_legs[0]
                  if fukusho_plan and fukusho_plan.odds_legs else None)
    swapped_wide_key = None
    swap = place_odds is not None and place_odds < WIDE_SWAP_PLACE_ODDS_FLOOR
    if swap and anchor2_amt >= MIN_BET_YEN:
        # 同じ◎軸の best ワイド plan を選ぶ (EV、 同点なら広い)。 EV 計算可能な plan のみ。
        wide_plan = None
        for (bt, lk), plan in eff_by_key.items():
            if bt != "wide" or plan.expected_return is None:
                continue
            if wide_plan is None or (plan.expected_return, len(plan.legs)) > \
                    (wide_plan.expected_return, len(wide_plan.legs)):
                wide_plan = plan
        if wide_plan is not None:
            emitted = False
            for leg, o, amt in _alloc_inverse_odds(wide_plan.legs, wide_plan.odds_legs,
                                                   anchor2_amt):
                if amt >= MIN_BET_YEN:
                    legs.append(SizedLeg(rid, "wide", list(leg), amt, wide_plan.label,
                                         o, wide_plan.expected_return, wide_plan.hit_prob,
                                         f"fukusho->wide swap (place {place_odds:.1f}<"
                                         f"{WIDE_SWAP_PLACE_ODDS_FLOOR})"))
                    emitted = True
            if emitted:
                swapped_wide_key = ("wide", _legs_key(wide_plan.legs))
                warnings.append(f"複勝→ワイド置換 (place {place_odds:.1f}<"
                                f"{WIDE_SWAP_PLACE_ODDS_FLOOR}・薄利非対称回避)")
            else:
                swap = False   # ワイド配分が全て min 割れ → 複勝へフォールバック
        else:
            swap = False       # ワイド plan/オッズ無し → 複勝へフォールバック
    # 非 swap (= 複勝オッズが floor 以上 / place_odds 不明 / ワイド欠損) は複勝アンカー。
    if not swap and fukusho_plan is not None and place_odds is not None \
            and anchor2_amt >= MIN_BET_YEN:
        legs.append(SizedLeg(rid, "fukusho", [axis], anchor2_amt, fukusho_plan.label,
                             place_odds, None, fukusho_plan.hit_prob,
                             f"fixed place anchor grade={tier} ({anchor2_frac:.0%})"))

    anchor_yen = sum(l.amount for l in legs)

    # (B) 複合 = per_race 残予算を EV 比例 (size_race と同じ。 swapped wide は exclude で二重買い回避)。
    residual = max(0, cap - anchor_yen)
    combo_budget = int(residual * combo_share_of_residual)
    exclude = frozenset([swapped_wide_key]) if swapped_wide_key else frozenset()
    combo_legs = _size_combo_legs(rid, race_eff, selection, eff_by_key, combo_budget,
                                  weight_key=weight_key, exclude_keys=exclude)
    legs.extend(combo_legs)

    # (B') ★使い切り保証 (ふくだ Session 163)★: combo が出ない/出ても薄いレースで cap が大量に
    #   余ると「単400だけ」で 3000円中 400円しか使わない問題が起きる。 ★余った予算を単勝◎に
    #   上乗せ★ して cap を使い切る (ふくだ「残余は単に上乗せ・複は復活させない」)。
    #   axis_odds が無効 (単勝が買えない) ときは上乗せできないのでそのまま (無理に他券種に回さない)。
    combo_used = sum(l.amount for l in combo_legs)
    leftover = cap - anchor_yen - combo_used
    if leftover >= BET_UNIT_YEN and axis_odds is not None and axis_odds > 1.0:
        tansho_leg = next((l for l in legs if l.bet_type == "tansho"), None)
        topup = (leftover // BET_UNIT_YEN) * BET_UNIT_YEN
        if tansho_leg is not None:
            # 既存の単勝◎に上乗せ (金額を増やす)。
            tansho_leg.amount += topup
            tansho_leg.note += f" +使い切り上乗せ{topup}"
        elif sel_tansho is not None and topup >= MIN_BET_YEN:
            # 単勝 leg が無い (tier 配分が min 割れ等) → 残余で単勝◎を新規に立てる。
            tp = eff_by_key.get(("tansho", _legs_key(sel_tansho.legs)))
            legs.insert(0, SizedLeg(rid, "tansho", [axis], topup,
                                    tp.label if tp else "単勝 ◎", axis_odds,
                                    None, (tp.hit_prob if tp else None),
                                    f"使い切り (combo不足の残余{topup}を単へ)"))
        if topup > 0:
            warnings.append(f"使い切り: 残余{topup}を単勝◎に上乗せ (combo不足)")

    # (C) per_race cap で最終 truncate (アンカー保護)
    pre_total = sum(l.amount for l in legs)
    n_dropped = 0
    if per_race_cap > 0 and pre_total > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
        warnings.append(f"per_race按分 {pre_total}->{sum(l.amount for l in legs)} "
                        f"drop={n_dropped}")

    total = sum(l.amount for l in legs)
    anchor_yen = sum(l.amount for l in legs if l.bet_type in ANCHOR_BET_TYPES)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=anchor_yen,
                      combo_yen=total - anchor_yen, per_race_cap=per_race_cap,
                      n_dropped=n_dropped, warnings=warnings)


def size_race_fixed_grade_v2(race_eff, selection, *, bankroll: int, per_race_cap: int,
                             kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
                             combo_share_of_residual: float = 1.0,
                             weight_key: str = "ev") -> RaceSizing:
    """v1 + ★堅いレースほど combo を厚く★ (ふくだ Session 162 / 見送りは Session 163 で無効化)。

    v1 (size_race_fixed_grade) に ★FIXED_SHARES_V2 (strong=単薄く combo厚く)★ を渡すラッパ。
    配分・swap・cap 按分は v1 と同一。 strong (◎断然=単で儲からない) で単/複を薄く (15/15) →
    residual=70% が combo に回る (= _size_combo_legs が EV 比例で三連複/三連単へ厚く配分)。
    ふくだ「単で当てても儲からないなら三連単で」を配分で表現。

    ★見送りゲートは Session 163 で実払戻検証 → 害と確定 → SKIP_MAX_ODDS_FLOOR=0.0 で無効化★。
    floor=0 なので _skip_max_odds_floor>0 ガードに掛からず、 全レース買い目を出す (空 RaceSizing は
    返らない)。 詳細 = SKIP_MAX_ODDS_FLOOR 定義のコメント / validate_v2_skip_gate.py。
    """
    return size_race_fixed_grade(
        race_eff, selection, bankroll=bankroll, per_race_cap=per_race_cap,
        kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct,
        combo_share_of_residual=combo_share_of_residual, weight_key=weight_key,
        _shares_table=FIXED_SHARES_V2, _skip_max_odds_floor=SKIP_MAX_ODDS_FLOOR)


# ===========================================================================
# shobu_rate: 「勝負条件 = 単勝一本」のレースだけ単勝を厚くする (Session 166)
# ===========================================================================
# ふくだ確定方針 (2026-06-20) + 検証 (docs/shobu_rate_sizing_design.md):
#   「◎の単勝がおいしい」と AI が判断した勝負レースだけ ★単勝を厚く★ 買う。
#   他のレースは普段どおり (v2 配分) ・★見送りはしない★ (S162-165 で見送りゲートは害確定)。
#
# 勝負条件 = tansho_H の 4 条件 (rank_w◎ で判定。 ★composite◎ ではない★)。
#   検証は rank_w=1 の単勝で +9,780円/ROI108.3% を出した。 一方 selection/combo の軸は
#   composite◎ で、 両者は cache 上 35.9% しか一致しない。 ★単勝の対象馬は rank_w◎ で固定★
#   しないと検証が再現しない (combo は composite◎軸のまま = それで良い)。
#
# 検証で確定した中身 (docs §3):
#   - 単勝は ★勝負R だけ★ 買う (他R で薄く張ると全体を食う。 勝負R だけがプラス)。
#   - 複勝は ★足さない★ (保険にならず薄利で黒字を食う)。
#   - 勝負R 以外は ★単勝なしで combo に cap をフルに回す★ (Session 167・抜いた単勝(-EV)分を
#     +EV の combo へ。 端数は浮く。 旧版は v2 委譲→単勝除外で単勝share分を浮かせていた)。
#
# 金額 = 基準金額 × レート は ★scheduler 側の per_race_cap 算出★ で配線する (このサイザーは
#   受け取った per_race_cap を「勝負R なら単勝に厚く充てる」だけ)。 勝負R は cap が勝負レート
#   (15%) で来る前提なので、 その cap の大半を rank_w◎ の単勝へ。
# ---------------------------------------------------------------------------
SHOBU_RATE_SIZER = "shobu_rate"

# 勝負条件 (tansho_H) の 4 条件。 ★ここが SSoT★ (simulate_strategy_redesign.tansho_H と同値)。
SHOBU_MAX_RANK_W = 1       # ◎が Win モデルで 1 位
SHOBU_MIN_VB_GAP = 3       # 市場人気とのズレ >= 3 (AI評価が人気より高い = 妙味)
SHOBU_MIN_WIN_EV = 1.3     # 単勝 EV >= 1.3
SHOBU_MAX_MARGIN = 60      # 予測着差 <= 60 (接戦すぎない = 勝ち切れる)

# 勝負R で rank_w◎ の単勝に充てる cap 割合。 残りは combo (普段どおり)。
#   検証は「勝負R は単勝のみが最良」だが、 ふくだ「combo は普段どおり」も尊重し単勝を主役に
#   厚く・combo は残予算で出す山型にする。 0.70 = cap の 7 割を単勝、 3 割を combo。
SHOBU_TANSHO_SHARE = 0.70
# レート既定 (ふくだ確定 Session 166): 通常5% / 勝負15%。 per_race_cap は ★勝負レート上限★
#   (基準金額×勝負レート) で来る前提なので、 通常R は cap を (通常/勝負) 倍に縮める。
SHOBU_NORMAL_RATE_PCT = 5.0
SHOBU_SHOBU_RATE_PCT = 15.0

# ★combo 内配分の方式 (Session 168 / 天井変種を実データ検証 → ふくだ判断 A で本番採用)★。
#   検証 (ml/analyze/bench_ceiling_variants.py・健全2期間・実払戻):
#     - 逆オッズ(旧既定 inverse): combo 内で低オッズ=的中寄りの点に厚く張る → ★ROIもDDも一番悪い★。
#       的中してるようで控除率込みでチャラにならない本命 combo に金を集め、 谷が深くなる。
#     - フラット(flat): 各点均等。 ★ROI +2〜3pt・maxDD -30%・的中率は同じ★ (両期間で逆オッズに優越)。
#       = ノーコストの地力UP。 ★通常R (98%) はこれを採用★。
#     - オッズ比例(odds): 高オッズ=高配当点に厚く → ★1000%超的中がほぼ倍増★ (天井中央480→1149%)。
#       代償=的中率↓(28→23%)・ROIは数pt減・DD振れ大。 黒字化はしない (上振れをROIとDDで買う取引)。
#       = [[payout-ceiling-strategy]] の「天井を取る」。 ★高確信の勝負R (2%) だけ採用★ (ROI 損失を限定)。
#   ★三連系だけに絞る (allowed_types=三連) はやりすぎ★ で ROI/的中崩壊・DD膨張 → 不採用 (検証で確認)。
SHOBU_NORMAL_COMBO_ALLOC = "flat"    # 通常R combo = フラット (B1採用・地力UP)
SHOBU_SHOBU_COMBO_ALLOC = "odds"     # 勝負R combo = オッズ比例 (B2・高確信で天井狙い)


def _shobu_axis(race_eff):
    """勝負条件の軸 = rank_w=1 の HorseStrength を返す (無ければ None)。

    ★composite◎ (race_eff.axis_umaban) ではなく rank_w◎★ を使うのが核心 (上のコメント参照)。
    """
    cands = [s for s in race_eff.strengths if s.rank_w == 1]
    return cands[0] if cands else None


def is_shobu_race(race_eff) -> bool:
    """このレースが「勝負条件 = 単勝一本」を満たすか (tansho_H の 4 条件 / rank_w◎)。

    1 つでも素性が欠損していれば False (条件を満たすと判定できない → 勝負にしない)。
    """
    ax = _shobu_axis(race_eff)
    if ax is None:
        return False
    if ax.win_vb_gap is None or ax.win_ev is None or ax.predicted_margin is None:
        return False
    if (ax.odds or 0) <= 1.0:
        return False
    return (
        (ax.rank_w or 99) <= SHOBU_MAX_RANK_W
        and ax.win_vb_gap >= SHOBU_MIN_VB_GAP
        and ax.win_ev >= SHOBU_MIN_WIN_EV
        and ax.predicted_margin <= SHOBU_MAX_MARGIN
    )


def size_race_shobu_rate(race_eff, selection, *, bankroll: int, per_race_cap: int,
                         kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
                         combo_share_of_residual: float = 1.0,
                         weight_key: str = "ev",
                         normal_rate_pct: float = SHOBU_NORMAL_RATE_PCT,
                         shobu_rate_pct: float = SHOBU_SHOBU_RATE_PCT,
                         combo_alloc_mode: str = SHOBU_NORMAL_COMBO_ALLOC,
                         shobu_combo_alloc_mode: str = SHOBU_SHOBU_COMBO_ALLOC,
                         combo_allowed_types: Optional[frozenset] = None) -> RaceSizing:
    """勝負条件レースだけ rank_w◎ の単勝を厚くするサイザー (Session 166)。

    ★per_race_cap は「勝負レート上限」(基準金額×勝負レート) で来る前提★ (runner の番人を
      勝負R が通れるように。 freebudget_scheduler.read_per_race_cap 参照)。
    - 勝負R (is_shobu_race=True): cap (=勝負レート) × SHOBU_TANSHO_SHARE を ★rank_w◎ の単勝★
      に充て、 残りを combo に EV 比例 (複勝は足さない)。
    - 非勝負R: cap を ★通常レートに縮めて★ (cap × normal/shobu)、 ★単勝なしで combo に cap を
      フルに回す★ (EV比例・複勝なし。 抜いた単勝(-EV)分を +EV の combo へ。 端数は浮く)。

    ★単勝は勝負R だけ・複勝は足さない・見送りはしない★ (docs/shobu_rate_sizing_design.md §3.3)。

    ★combo 内配分 (Session 168・実データ検証で本番採用)★:
      - 通常R combo = combo_alloc_mode (既定 flat = SHOBU_NORMAL_COMBO_ALLOC)。
      - 勝負R combo = shobu_combo_alloc_mode (既定 odds = SHOBU_SHOBU_COMBO_ALLOC)。
      根拠は SHOBU_*_COMBO_ALLOC 定数のコメント / bench_ceiling_variants.py 参照。
    """
    if not is_shobu_race(race_eff):
        # ★通常レート = 単勝を買わず combo に cap をフルに回す (設計書§3.3)★。
        #   cap は勝負レート上限で来るので通常レートに縮める。
        normal_cap = per_race_cap
        if per_race_cap > 0 and shobu_rate_pct > 0 and normal_rate_pct > 0:
            normal_cap = _round_unit(per_race_cap * normal_rate_pct / shobu_rate_pct)
            normal_cap = max(MIN_BET_YEN, normal_cap)
        # 単勝は買わない (◎単勝は -EV のことが多い= docs §3.1 で毎レース薄い単は -65,800円)。
        #   ★抜いた予算を浮かせず +EV の combo に cap フルで回す★ (ふくだ Session 167)。
        #   「通常R は combo しか買わないのだから cap で combo を買うのが自然」。 浮かせる(0 EV)
        #   より、 抜いた単勝(-EV)分を combo(EV比例で買う+EVの点のみ)に回す方が良い。
        #   複勝も足さない。 combo は EV 比例+100円単位なので cap ぴったりにならず端数(〜100円)は浮く
        #   (EV 比例の比率を崩してまで埋めない)。 -EV の点(wide/三連複/三連単が floor 未満)には回らない。
        rid = race_eff.race_id
        eff_by_key = {(p.bet_type, _legs_key(p.legs)): p for p in race_eff.plans}
        combo_budget = int(normal_cap * combo_share_of_residual)
        legs = _size_combo_legs(rid, race_eff, selection, eff_by_key, combo_budget,
                                weight_key=weight_key, exclude_keys=frozenset(),
                                alloc_mode=combo_alloc_mode,
                                allowed_types=combo_allowed_types)
        total = sum(l.amount for l in legs)
        n_dropped = 0
        if normal_cap > 0 and total > normal_cap:
            legs, n_dropped = fit_legs_to_cap(legs, normal_cap)
            total = sum(l.amount for l in legs)
        return RaceSizing(
            race_id=rid, legs=legs, total_yen=total, anchor_yen=0, combo_yen=total,
            per_race_cap=normal_cap, n_dropped=n_dropped,
            warnings=["通常レート: 単勝なし・comboにcapフル (設計書§3.3)"])

    rid = race_eff.race_id
    warnings: List[str] = ["勝負レート: tansho_H 4条件 → rank_w◎の単勝を厚く"]
    legs: List[SizedLeg] = []
    cap = per_race_cap if per_race_cap > 0 else bankroll
    ax = _shobu_axis(race_eff)
    eff_by_key = {(p.bet_type, _legs_key(p.legs)): p for p in race_eff.plans}

    # (A) 単勝 = rank_w◎ に cap × SHOBU_TANSHO_SHARE。 ★composite◎ ではなく rank_w◎★。
    sel_tansho = next((sp for sp in selection.selected_plans if sp.bet_type == "tansho"), None)
    tansho_amt = _round_unit(cap * SHOBU_TANSHO_SHARE)
    axis_odds = ax.odds
    if tansho_amt >= MIN_BET_YEN and axis_odds is not None and axis_odds > 1.0:
        tp = eff_by_key.get(("tansho", _legs_key(sel_tansho.legs))) if sel_tansho else None
        legs.append(SizedLeg(rid, "tansho", [ax.umaban], tansho_amt,
                             "単勝 ◎(勝負・rank_w)", axis_odds,
                             None, (tp.hit_prob if tp else None),
                             f"勝負レート: rank_w◎単勝 ({SHOBU_TANSHO_SHARE:.0%})"))

    anchor_yen = sum(l.amount for l in legs)

    # (B) combo = 残予算を EV 比例 (普段どおり)。 複勝は足さない (検証で害)。
    residual = max(0, cap - anchor_yen)
    combo_budget = int(residual * combo_share_of_residual)
    combo_legs = _size_combo_legs(rid, race_eff, selection, eff_by_key, combo_budget,
                                  weight_key=weight_key, exclude_keys=frozenset(),
                                  alloc_mode=shobu_combo_alloc_mode,
                                  allowed_types=combo_allowed_types)
    legs.extend(combo_legs)

    # (B') 使い切り保証: combo が薄く cap が余れば単勝◎に上乗せ (v1 と同じ思想)。
    combo_used = sum(l.amount for l in combo_legs)
    leftover = cap - anchor_yen - combo_used
    if leftover >= BET_UNIT_YEN and axis_odds is not None and axis_odds > 1.0:
        topup = (leftover // BET_UNIT_YEN) * BET_UNIT_YEN
        tansho_leg = next((l for l in legs if l.bet_type == "tansho"), None)
        if tansho_leg is not None:
            tansho_leg.amount += topup
            tansho_leg.note += f" +使い切り{topup}"
            warnings.append(f"使い切り: 残余{topup}を勝負単勝に上乗せ")

    # (C) per_race cap で最終 truncate (アンカー=単勝 保護)
    pre_total = sum(l.amount for l in legs)
    n_dropped = 0
    if per_race_cap > 0 and pre_total > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
        warnings.append(f"per_race按分 {pre_total}->{sum(l.amount for l in legs)} drop={n_dropped}")

    total = sum(l.amount for l in legs)
    anchor_yen = sum(l.amount for l in legs if l.bet_type in ANCHOR_BET_TYPES)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=anchor_yen,
                      combo_yen=total - anchor_yen, per_race_cap=per_race_cap,
                      n_dropped=n_dropped, warnings=warnings)


# ---------------------------------------------------------------------------
# template_flat: 買い方ラボのテンプレを ★そのまま★ 実戦化するサイザー (Session 162)
# ---------------------------------------------------------------------------
# 動機 [[bet-template-lab]] / [[feedback_long_term_right_way]]: 買い方ラボ (bet_templates の
#   複勝堅実党/ワイド堅実党/三連複1頭軸 等) は backtest で控除率を埋め長期妙味を検証済だが、
#   自動投票 (fixed_grade/Kelly sizing) とは別系統で ★一切配線されていなかった★ (Session 161 発覚)。
#   このサイザーは「検証した買い方をそのまま実行」する正攻法の土台 = ラボの買い目生成パスを
#   投票に直結する。
#
# ★ラボ backtest との完全一致を担保する設計★ (backtest_bet_templates.py:252-258 と同一パス):
#   - 印付け = marks_from_ranking(composite 降順) = ★崖カット無しの composite 理論モード★。
#     ラボの★成績 (複勝堅実党 maxDD最小 / ワイド堅実党 中央値98% / 三連複1頭軸 中央値105%) は
#     この composite 理論モードの数字。 実 AI印 (崖カット assign_ai_marks) は使わない
#     (使うと買い目が変わり backtest 成績と乖離する)。
#   - 配分 = 全 Ticket 一律 flat_stake (ラボ backtest = 100円/点 flat)。 ROI は不変、 絶対額のみ
#     flat_stake でスケール。 weight/役割による傾斜は ★かけない★ (ラボの数字を歪めないため)。
#   - selection は使わない (テンプレが買い目を全決定 = bettype_selection/efficiency 判断をバイパス)。
#     race_eff は composite 序列 (strengths) と各点の市場オッズ (plans) のためだけに使う。
#
# テンプレ実点数は最大 12点 (honmei_formation)。 flat 100円なら最大 1,200円 < per_race_cap
#   (既定 3,000円) なので fit_legs_to_cap は通常発火しない (= 檻は安全弁として残るが成績一致)。
TEMPLATE_FLAT_SIZER = "template_flat"
DEFAULT_TEMPLATE = "fukusho_korogashi"   # 複勝堅実党 (maxDD 最小・死なない・転がし素地)
FLAT_STAKE_YEN = 100                     # ラボ backtest と同じ 100円/点 (スケールは ROI 不変)


def _ranking_from_strengths(race_eff) -> List[int]:
    """race_eff.strengths から composite 降順の馬番リスト。

    strengths は通常 composite 降順だが rank_composite があればそれで厳密ソート
    (backtest は降順前提で並びをそのまま使う = ここも同義)。
    """
    ss = list(race_eff.strengths)
    if all(s.rank_composite is not None for s in ss) and ss:
        ss = sorted(ss, key=lambda s: s.rank_composite)
    else:
        ss = sorted(ss, key=lambda s: s.composite, reverse=True)
    return [s.umaban for s in ss]


def _odds_for_ticket(bet_type: str, horses, eff_by_key: dict):
    """Ticket の (bet_type, horses) に対応する市場オッズを race_eff.plans から引く (表示用)。

    plans は legs=List[List[int]] (1点=1 leg) の入れ子で、 1点プランも複数点プランもある。
    対象 horses を含む plan の該当 leg のオッズを返す。 無ければ None (額には影響しない)。
    """
    want = tuple(int(h) for h in horses)
    want_set = frozenset(want)
    ordered = BET_SPEC_ORDERED.get(bet_type, False)
    for (bt_, _lk), plan in eff_by_key.items():
        if bt_ != bet_type:
            continue
        for i, leg in enumerate(plan.legs):
            lt = tuple(int(h) for h in leg)
            match = (lt == want) if ordered else (frozenset(lt) == want_set)
            if match:
                if plan.odds_legs and i < len(plan.odds_legs):
                    return plan.odds_legs[i]
                return None
    return None


def size_race_template_flat(race_eff, selection, *, bankroll: int, per_race_cap: int,
                            kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
                            combo_share_of_residual: float = 1.0,
                            weight_key: str = "ev",
                            template_name: str = DEFAULT_TEMPLATE,
                            flat_stake: int = FLAT_STAKE_YEN) -> RaceSizing:
    """買い方ラボのテンプレを composite 序列に適用し、 全点 flat_stake で投票化する。

    ラボ backtest (backtest_bet_templates) と ★同一の買い目生成パス★:
      marks_from_ranking(composite降順) → apply_template(template) → 各 Ticket を flat_stake。

    kelly_fraction / per_bet_cap_pct / combo_share_of_residual / weight_key はシグネチャ互換の
    ため受け取るが未使用 (配分はオッズ非依存の flat)。 template_name / flat_stake はファクトリ
    make_template_sizer が部分適用する (条件出し分けは別サイザーで template_name を切替)。
    """
    # 遅延 import (bet_templates は純関数層・循環なしだが import 順序を軽くする)
    from ml.strategies import bet_templates as bt

    legs: List[SizedLeg] = []
    warnings: List[str] = []
    rid = race_eff.race_id

    if not race_eff.strengths:
        warnings.append("strengths 不在 → 買い目生成不可")
        return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0, combo_yen=0,
                          per_race_cap=per_race_cap, warnings=warnings)

    ranking = _ranking_from_strengths(race_eff)
    marks = bt.marks_from_ranking(ranking)
    tmpl = bt.get_template(template_name)
    tickets = bt.apply_template(tmpl, marks)
    if not tickets:
        warnings.append(f"template={template_name} の買い目が空 (印不足)")
        return RaceSizing(race_id=rid, legs=[], total_yen=0, anchor_yen=0, combo_yen=0,
                          per_race_cap=per_race_cap, warnings=warnings)

    eff_by_key = {(p.bet_type, _legs_key(p.legs)): p for p in race_eff.plans}
    stake = max(MIN_BET_YEN, (int(flat_stake) // BET_UNIT_YEN) * BET_UNIT_YEN)
    for tk in tickets:
        horses = list(tk.horses)
        odds = _odds_for_ticket(tk.bet_type, horses, eff_by_key)
        legs.append(SizedLeg(rid, tk.bet_type, horses, stake,
                             f"{tmpl.label} [{tk.role}]", odds, None, None,
                             f"template={template_name} flat {stake}/点"))

    # per_race cap で最終 truncate (アンカー保護。 ラボは無上限だが実戦の檻は安全弁として尊重。
    #   テンプレ最大 12点 × flat 100 = 1,200円 < 既定 cap 3,000 なので通常は発火しない)。
    pre_total = sum(l.amount for l in legs)
    n_dropped = 0
    if per_race_cap > 0 and pre_total > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
        warnings.append(f"per_race按分 {pre_total}->{sum(l.amount for l in legs)} "
                        f"drop={n_dropped} (★ラボ成績と乖離: flat_stake/テンプレ点数を見直し)")

    total = sum(l.amount for l in legs)
    anchor_yen = sum(l.amount for l in legs if l.bet_type in ANCHOR_BET_TYPES)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=anchor_yen,
                      combo_yen=total - anchor_yen, per_race_cap=per_race_cap,
                      n_dropped=n_dropped, warnings=warnings)


def make_template_sizer(template_name: str = DEFAULT_TEMPLATE,
                        flat_stake: int = FLAT_STAKE_YEN) -> "SizerFn":
    """template_name / flat_stake を部分適用した SizerFn を返す (scheduler が --template で注入)。

    Step2 (条件出し分け) は「レース特性 → template_name を選ぶ」別サイザーを作って差すだけ。
    """
    def _sizer(race_eff, selection, **kw) -> RaceSizing:
        kw.pop("template_name", None)
        kw.pop("flat_stake", None)
        return size_race_template_flat(race_eff, selection,
                                       template_name=template_name,
                                       flat_stake=flat_stake, **kw)
    return _sizer


# ---------------------------------------------------------------------------
# template_select: レース特性でテンプレを出し分ける (Session 162 / Step2)
# ---------------------------------------------------------------------------
# ★★★検証で棄却 (Session 162 / 本番不採用)★★★
#   predictions 実払戻 (2026-01〜03-16・679R) で 単一 fukusho_korogashi(ROI 85.9%/中央値86.9%)
#   vs この出し分け SELECT(82.2%/83.3%) を比較 → ★出し分けは単一複勝堅実党に負けた★。
#   原因: 出し分けの根拠にした backtest_selector マトリクス「堅い2強→三連複 99%」が
#   ★cache 精算 (combo payout の事前オッズ近似) の artifact★ で、 predictions 実払戻では
#   三連複1頭軸は全体 75.4% と最弱。 まさに [[feedback_odds_gate_hindsight]] / W9 の罠
#   (combo の cache payout は信用できない)。 単一複勝堅実党が全月・全候補で最強・最安定だった
#   = ラボ当初結論「複勝堅実党 = maxDD最小・死なない基盤」と一致。
#   → ★本番は template_flat:fukusho_korogashi (単一) を採用★。 本コードは将来 (combo を実払戻で
#   再検証する / 別の出し分け軸を試す) ときの足場として残置 (registry 登録も維持)。 ★既定にはしない★。
#
# 動機 [[bet-template-lab]]: ふくだ方針「レース条件で出し分け」。 ラボ backtest_selector の
#   条件×テンプレ valid(OOS) ROI マトリクスから、 各レース特性帯のベストテンプレを選ぶ。
# 出し分けルールは ★オッズ非依存特性★ のみで判定する (後知恵回避 [[feedback_odds_gate_hindsight]]):
#   top2 (composite上位2頭の win_prob 合計)。 fav_odds/axis_ev は使わない。
#   - 堅い2強 (top2>=0.5): sanrenpuku_1jiku に振る。 それ以外: fukusho_korogashi。
#   ※この振り分け自体が cache artifact 由来 → 上記のとおり実払戻で棄却済み。
TEMPLATE_SELECT_SIZER = "template_select"
SELECT_STRONG_TOP2 = 0.50    # composite上位2頭の win_prob 合計がこれ以上 = 堅い2強
SELECT_TEMPLATE_STRONG = "sanrenpuku_1jiku"   # 堅い2強 → 三連複1頭軸 (配当取り)
SELECT_TEMPLATE_DEFAULT = "fukusho_korogashi"  # それ以外 → 複勝堅実党 (堅実・死なない)


def _top2_winprob(race_eff) -> float:
    """composite 上位2頭の win_prob 合計 (オッズ非依存・backtest_selector の top2 と同義)。"""
    ss = list(race_eff.strengths)
    if all(s.rank_composite is not None for s in ss) and ss:
        ss = sorted(ss, key=lambda s: s.rank_composite)
    else:
        ss = sorted(ss, key=lambda s: s.composite, reverse=True)
    if not ss:
        return 0.0
    if len(ss) == 1:
        return float(ss[0].win_prob or 0.0)
    return float((ss[0].win_prob or 0.0) + (ss[1].win_prob or 0.0))


def select_template(race_eff) -> str:
    """レース特性 → テンプレ名 (★オッズ非依存特性のみ★で判定)。

    堅い2強 (top2 >= SELECT_STRONG_TOP2) → 三連複1頭軸 (配当)。 それ以外 → 複勝堅実党 (堅実)。
    """
    if _top2_winprob(race_eff) >= SELECT_STRONG_TOP2:
        return SELECT_TEMPLATE_STRONG
    return SELECT_TEMPLATE_DEFAULT


def size_race_template_select(race_eff, selection, *, bankroll: int, per_race_cap: int,
                              kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
                              combo_share_of_residual: float = 1.0,
                              weight_key: str = "ev",
                              flat_stake: int = FLAT_STAKE_YEN) -> RaceSizing:
    """レース特性でテンプレを出し分けて全点 flat で投票化する (Step2)。

    select_template で名前を決め、 あとは size_race_template_flat に委譲 (買い目生成・額付与は
    Step1 と完全に同じ = ラボ backtest と一致)。
    """
    name = select_template(race_eff)
    return size_race_template_flat(race_eff, selection, bankroll=bankroll,
                                   per_race_cap=per_race_cap, template_name=name,
                                   flat_stake=flat_stake)


# ---------------------------------------------------------------------------
# プラガブルサイザー登録
# ---------------------------------------------------------------------------

SizerFn = Callable[..., RaceSizing]
SIZERS: Dict[str, SizerFn] = {
    KELLY_SIZER: size_race,                 # 旧既定 (anchor_kelly_combo_ev)。 名前は固定
    ADAPTIVE_SIZER: size_race_adaptive,
    FIXED_GRADE_SIZER: size_race_fixed_grade,  # = DEFAULT_SIZER (本番既定)
    # fixed_grade_v2 = v1 + 見送り + 堅いR(◎断然)で combo厚く (Session162・ふくだ「単で儲からない→三連単」)
    FIXED_GRADE_V2_SIZER: size_race_fixed_grade_v2,
    # shobu_rate = 勝負条件(tansho_H 4条件・rank_w◎)のレースだけ単勝を厚く・他はv2 (Session166)
    SHOBU_RATE_SIZER: size_race_shobu_rate,
    # template_flat = ラボのテンプレ (既定 DEFAULT_TEMPLATE) を全点 flat で実戦化。
    #   scheduler が --template でテンプレ名を渡すと make_template_sizer で差し替える。
    TEMPLATE_FLAT_SIZER: size_race_template_flat,
    # template_select = レース特性 (オッズ非依存 top2) でテンプレを出し分け (Step2)。
    TEMPLATE_SELECT_SIZER: size_race_template_select,
}


def get_sizer(name: str) -> SizerFn:
    if name not in SIZERS:
        raise ValueError(f"unknown sizer: {name!r} (allowed: {tuple(SIZERS)})")
    return SIZERS[name]

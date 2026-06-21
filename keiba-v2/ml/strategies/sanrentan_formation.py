#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三連単フォーメーション 買い目生成エンジン (Session 171 / 天井狙いの土台)

ふくだの買い方知恵 [[maru-second-place-formation]] を現行アーキ (bettype_efficiency の
RaceEfficiency) に載せる純関数層。 ★今日の土台★ = 最小で動く器を作り、 将来ここに
「馬の選び方 (候補抽出)」「切り捨て方 (trim)」「強弱のつけ方 (配分)」を積んでいく。

────────────────────────────────────────────────────────────────────────
戦略 (S170 ふくだ確定仕様):
  抜けた1番人気の ◎ (= composite トップ・信頼する本命) を、 ★1着でなく2-3着に流す★。
  1着は「W勝率はあるが市場が軽視している妙味馬 (伏兵)」に取らせて配当を跳ねさせる。

  買い目1:  頭[H] → ◎ (2着固定) → 3着候補[T]
  買い目2:  頭[H] → 連軸候補[R] → ◎ (3着固定)

  - 頭[H]        : pred_proba_w_cal ≥ 0.12 ∧ win_ev 上位 (= 勝つ力はあるが妙味)。 ◎は除く。
  - 連軸候補[R]  : composite 上位 (○▲)。 ◎は除く。
  - 3着候補[T]   : ★多角ピック★ = composite上位(○▲△Ⅲ) ∪ 印4(LLM穴馬) ∪ パドック印(S/A)。
                   AI総合点が見落とす3着の妙味を拾い、 高配当の3着付けで天井を上げる
                   ([[feedback_no_stacking_across_stars_nebula]] の視点独立)。
  - 候補頭数は ★レース可変★ (基準を満たす馬数で自然に決まる。 固定しない)。

trim (点数オーバー時):
  最大 max_points (既定36) を超えたら ★ハーヴィルEV (的中確率 × 三連単オッズ) の低い買い目から
  切り捨て★。 単純な低オッズ切り (人気サイドを切る) でなく「妙味の薄い買い目」を削る
  ([[feedback_betting_philosophy]] §4 ハーヴィル哲学と一貫)。

データの出所 (全て RaceEfficiency / 引数で渡る・DB/IO はサイザー側が解決):
  - 軸◎      : race_eff.axis_umaban (composite トップ)
  - pred_w   : HorseStrength.pred_w   (= pred_proba_w_cal・キャリブレ済勝率。 頭の 0.12 判定)
  - win_ev   : HorseStrength.win_ev   (= 単勝期待値。 頭の妙味判定)
  - win_prob : HorseStrength.win_prob (= 正規化勝率。 ハーヴィル入力)
  - composite: HorseStrength.composite / rank_composite (○▲△Ⅲ の序列)
  - 印4      : anaba_umabans (ml.strategies.anaba_picks)
  - パドック : paddock_marks (ml.analyze.analyze_paddock_signal.load_paddock_marks の {umaban: mark})
  - 三連単OD : sanrentan_odds {'010203': odds} (core.odds_db.get_all_combo_odds['sanrentan'])

★純関数のみ★ (DB/IO なし)。 三連単オッズ・印4・パドック印は ★呼び出し側 (サイザー)★ が
  解決して渡す。 これで backtest (履歴注入) と live (DB/ファイル) の両方が同じ生成ロジックを通る。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ml.strategies import harville as hv

# ── 既定パラメータ (ふくだ S171「判定をシビアに」→ sweep 実払戻で確定。 上書き可) ──
#   sweep (sweep_sanrentan_formation・2026-01〜05・1423R 実払戻) で「シビアにすると壁を超える」と
#   実証: ev1.0/wp0.12/gap0.0 (v1) は月中央69% (控除率の壁72.5%以下) → ev1.5/wp0.15/gap0.4 で
#   月中央90%・発動11%・maxDD半減・天井維持。 = ★この既定が S171 本番値★ (docs §4)。
DEFAULT_WIN_PROB_FLOOR = 0.15   # 頭: pred_proba_w_cal がこれ以上 (勝つ力。 0.12→0.15 でシビアに)
DEFAULT_HEAD_EV_FLOOR = 1.5     # 頭: win_ev がこれ以上 (妙味。 1.0→1.5 が壁超えの最大の効き目)
DEFAULT_N_HEAD_MAX = 3          # 頭候補の最大頭数 (win_ev 上位から)
DEFAULT_N_RENJIKU = 2           # 連軸候補 = composite 上位 (○▲) の頭数
DEFAULT_N_THIRD_COMPOSITE = 4   # 3着候補に入れる composite 上位 (◎除く ○▲△Ⅲ) の頭数
DEFAULT_PADDOCK_MARKS = ("S", "A")  # 3着候補に拾うパドック印 (S/A は別格・上位)
DEFAULT_MAX_POINTS = 36         # 三連単の最大点数 (これを超えたら hv_ev 低い順に切る)
# ★購入/見送りゲート (ふくだ S171「判定をシビアに」)★ = ◎の格 (composite gap ◎-○)。
#   0.0=ゲート無し (v1)。 >0 なら ◎が○からこの差以上抜けている (= 信頼できる抜け本命) レース
#   だけ買う。 ◎を2-3着に置く戦略の前提「信頼する◎」を ★オッズ非依存★ で課す
#   ([[feedback_odds_gate_hindsight]] の罠を踏まない)。 実データ sweep で 0.4 を採用 (S171 本番値)。
DEFAULT_MIN_AXIS_GAP = 0.4
# ★過剰人気◎ 見送りゲート (S172・explore_axis_confidence で発見)★ = ◎の win_ev (単勝EV)。
#   0.0=ゲート無し。 >0 なら ◎の win_ev (pred_w × 直前オッズ) がこれ未満 = 市場が買いすぎ (過剰人気)
#   のレースを見送る。 ◎を2-3着に固定するフォメは ◎が安い (過剰人気) と三連単配当が伸びず控除率に
#   負ける (探索: ◎win_ev<0.78 の50R が ROI49%・PnL-44,740 = 大負けの主犯。 切ると -31k→+13k)。
#   ★直前オッズベース=後知恵でない ([[feedback_odds_gate_hindsight]])★。
#   ★本番値=0.6 (S172): sweep (実払戻5ヶ月) で 発動152→135R・全期間ROI 88→100%・PnL -31k→+920・
#   ≥1000R=5/最高81,390 維持・各月で現行を悪化させず1-3月改善。 0.7+ は3月の当たりまで切って悪化。
#   (注: 月中央は4-5月が全config全ハズレ=三連単フォメは月単位で0/大勝ちの2極=指標として脆い。
#    判断は全期間ROI/PnL/天井で。 直近の取りこぼしは selection_engine_design の本丸へ。)
DEFAULT_MIN_AXIS_WIN_EV = 0.6

# 役割ラベル (◎をどこに置いたか・分析/表示用)
ROLE_MARU_2ND = "maru2"   # 買い目1: 頭 → ◎(2着) → 3着候補
ROLE_MARU_3RD = "maru3"   # 買い目2: 頭 → 連軸 → ◎(3着)


@dataclass
class FormationLeg:
    """三連単 1 点 (着順 = (1着, 2着, 3着))。"""
    horses: Tuple[int, int, int]
    hv_prob: float                  # ハーヴィル的中確率 (正規化勝率ベース)
    odds: Optional[float]           # 三連単市場オッズ (None = 未取得)
    hv_ev: Optional[float]          # 的中確率 × オッズ (None = オッズ欠損)
    role: str                       # ROLE_MARU_2ND / ROLE_MARU_3RD


@dataclass
class FormationResult:
    race_id: str
    axis: int                       # ◎ (composite トップ)
    head_set: List[int]             # 頭候補
    renjiku_set: List[int]          # 連軸候補
    third_set: List[int]            # 3着候補 (多角ピック)
    legs: List[FormationLeg]        # trim 後・hv_ev 降順 (高妙味が先頭)
    n_before_trim: int = 0          # trim 前の総点数
    warnings: List[str] = field(default_factory=list)

    @property
    def n_points(self) -> int:
        return len(self.legs)


# ---------------------------------------------------------------------------
# 候補抽出 (馬の選び方 — 将来ここを差し替えて拡張する)
# ---------------------------------------------------------------------------

def _by_umaban(race_eff) -> Dict[int, object]:
    return {s.umaban: s for s in race_eff.strengths}


def _composite_order(race_eff) -> List[int]:
    """composite 降順の馬番リスト (rank_composite があればそれで厳密ソート)。"""
    ss = list(race_eff.strengths)
    if ss and all(s.rank_composite is not None for s in ss):
        ss = sorted(ss, key=lambda s: s.rank_composite)
    else:
        ss = sorted(ss, key=lambda s: s.composite, reverse=True)
    return [s.umaban for s in ss]


def axis_gap(race_eff, axis: int) -> float:
    """◎ (axis) の格 = composite gap (◎ − ○=axis除く最上位)。 ◎単独なら axis_composite。

    bettype_sizing._composite_gap と同義 (オッズ非依存)。 購入/見送りゲートに使う。
    """
    comps = {s.umaban: s.composite for s in race_eff.strengths}
    ac = comps.get(axis)
    if ac is None:
        return 0.0
    others = [c for u, c in comps.items() if u != axis]
    return (ac - max(others)) if others else ac


def select_head(race_eff, axis: int, *,
                win_prob_floor: float = DEFAULT_WIN_PROB_FLOOR,
                ev_floor: float = DEFAULT_HEAD_EV_FLOOR,
                n_max: int = DEFAULT_N_HEAD_MAX) -> List[int]:
    """頭(1着)候補 = pred_proba_w_cal ≥ floor ∧ win_ev ≥ ev_floor の馬 (◎除く)・win_ev 降順 n_max 頭。

    「勝つ力はある (W勝率≥12%) が市場が軽視 (EV高=妙味)」= 配当を跳ねさせる伏兵。 ◎は2-3着に
    置くので頭からは除外する。 win_ev/pred_w 欠損馬は候補にしない (妙味判定不能)。
    """
    cands = []
    for s in race_eff.strengths:
        if s.umaban == axis:
            continue
        if s.pred_w is None or s.win_ev is None:
            continue
        if s.pred_w < win_prob_floor:
            continue
        if ev_floor > 0 and s.win_ev < ev_floor:
            continue
        cands.append(s)
    cands.sort(key=lambda s: (s.win_ev or 0.0), reverse=True)
    return [s.umaban for s in cands[:n_max]]


def select_renjiku(race_eff, axis: int, *, n: int = DEFAULT_N_RENJIKU) -> List[int]:
    """連軸候補 = composite 上位 (○▲) n 頭 (◎除く)。 買い目2 の2着に置く。"""
    order = [u for u in _composite_order(race_eff) if u != axis]
    return order[:n]


def select_third(race_eff, axis: int, *,
                 anaba_umabans: Sequence[int] = (),
                 paddock_marks: Optional[Dict[int, str]] = None,
                 n_composite: int = DEFAULT_N_THIRD_COMPOSITE,
                 paddock_keep: Sequence[str] = DEFAULT_PADDOCK_MARKS) -> List[int]:
    """3着候補 = composite上位(○▲△Ⅲ) ∪ 印4(LLM穴馬) ∪ パドック印(S/A) ・◎除外・順序保持dedup。

    視点独立で AI総合点が見落とす3着の妙味を足す ([[feedback_no_stacking_across_stars_nebula]])。
    composite を先頭に、 印4、 パドック の順で重複を除いて連結する。
    """
    out: List[int] = []

    def _add(u):
        try:
            iu = int(u)
        except (TypeError, ValueError):
            return
        if iu != axis and iu not in out:
            out.append(iu)

    # composite 上位 (◎除く ○▲△Ⅲ)
    for u in [x for x in _composite_order(race_eff) if x != axis][:n_composite]:
        _add(u)
    # 印4 (LLM穴馬)
    for u in (anaba_umabans or []):
        _add(u)
    # パドック印 (S/A など)
    if paddock_marks:
        keep = {str(m).upper() for m in paddock_keep}
        for u, mk in paddock_marks.items():
            if str(mk).upper() in keep:
                _add(u)
    return out


# ---------------------------------------------------------------------------
# ハーヴィル確率 / 三連単オッズ
# ---------------------------------------------------------------------------

def _kumiban_ordered(a: int, b: int, c: int) -> str:
    """三連単の組番 (6桁・着順保持・ゼロ埋め)。 get_all_combo_odds['sanrentan'] のキー形式。"""
    return f"{a:02d}{b:02d}{c:02d}"


def _odds_lookup(sanrentan_odds: Optional[Dict[str, object]], a: int, b: int, c: int) -> Optional[float]:
    if not sanrentan_odds:
        return None
    ent = sanrentan_odds.get(_kumiban_ordered(a, b, c))
    if ent is None:
        return None
    if isinstance(ent, dict):
        o = ent.get("odds")
        return float(o) if o else None
    try:
        return float(ent)
    except (TypeError, ValueError):
        return None


def _norm_win_probs(race_eff) -> Dict[int, float]:
    """ハーヴィル入力 = 各馬の正規化勝率 {umaban: win_prob} (strengths は normalize 済)。"""
    return {s.umaban: float(s.win_prob or 0.0) for s in race_eff.strengths}


# ---------------------------------------------------------------------------
# 買い目組み立て + trim
# ---------------------------------------------------------------------------

def _make_leg(win_probs, sanrentan_odds, a, b, c, role) -> FormationLeg:
    p = hv.sanrentan_prob(win_probs, a, b, c)
    o = _odds_lookup(sanrentan_odds, a, b, c)
    ev = (p * o) if (o is not None and p > 0) else None
    return FormationLeg(horses=(a, b, c), hv_prob=p, odds=o, hv_ev=ev, role=role)


def trim_by_hv_ev(legs: List[FormationLeg], max_points: int) -> List[FormationLeg]:
    """点数が max_points を超えたら hv_ev の低い買い目から切り捨て、 hv_ev 降順で返す。

    オッズ欠損 (hv_ev None) の点は EV 評価不能 → 最優先で切る (-1 扱い)。 妙味の高い (hv_ev 大)
    買い目が残る = 天井を取りにいく。 [[feedback_betting_philosophy]] §4。
    """
    def _key(l: FormationLeg) -> float:
        return l.hv_ev if l.hv_ev is not None else -1.0
    ordered = sorted(legs, key=_key, reverse=True)
    if max_points > 0 and len(ordered) > max_points:
        ordered = ordered[:max_points]
    return ordered


def build_formation(race_eff, sanrentan_odds: Optional[Dict[str, object]] = None, *,
                    anaba_umabans: Sequence[int] = (),
                    paddock_marks: Optional[Dict[int, str]] = None,
                    win_prob_floor: float = DEFAULT_WIN_PROB_FLOOR,
                    head_ev_floor: float = DEFAULT_HEAD_EV_FLOOR,
                    n_head_max: int = DEFAULT_N_HEAD_MAX,
                    n_renjiku: int = DEFAULT_N_RENJIKU,
                    n_third_composite: int = DEFAULT_N_THIRD_COMPOSITE,
                    paddock_keep: Sequence[str] = DEFAULT_PADDOCK_MARKS,
                    max_points: int = DEFAULT_MAX_POINTS,
                    min_axis_gap: float = DEFAULT_MIN_AXIS_GAP,
                    min_axis_win_ev: float = DEFAULT_MIN_AXIS_WIN_EV) -> FormationResult:
    """RaceEfficiency → 三連単フォーメーションの買い目 (FormationResult)。

    買い目1: 頭 → ◎(2着) → 3着候補   /   買い目2: 頭 → 連軸 → ◎(3着)。
    各点に ハーヴィル確率 × 三連単オッズ (hv_ev) を付与し、 max_points 超は hv_ev 低い順に trim。
    sanrentan_odds が None なら hv_ev は全 None (trim は prob 順にならず点数だけで切る = フォールバック)。
    min_axis_gap>0 なら ◎の格 (composite gap) がこれ未満のレースは ★見送り★ (買い目なし)。
    min_axis_win_ev>0 なら ◎の win_ev (単勝EV) がこれ未満 (過剰人気◎) のレースも見送り (S172)。
    """
    rid = race_eff.race_id
    axis = race_eff.axis_umaban
    warnings: List[str] = []

    if not race_eff.strengths:
        return FormationResult(rid, axis, [], [], [], [], 0, ["strengths 不在 → 買い目なし"])

    # 購入/見送りゲート: ◎の格 (composite gap) が薄い = 信頼できる抜け本命でない → 見送り。
    if min_axis_gap > 0:
        gap = axis_gap(race_eff, axis)
        if gap < min_axis_gap:
            return FormationResult(
                rid, axis, [], [], [], [], 0,
                [f"見送り: ◎の格 gap{gap:.2f} < {min_axis_gap:.2f} (信頼できる抜け本命でない)"])

    # 過剰人気◎ 見送りゲート (S172): ◎の win_ev (単勝EV) が薄い = 市場が買いすぎ → 見送り。
    if min_axis_win_ev > 0:
        ax = next((s for s in race_eff.strengths if s.umaban == axis), None)
        aev = ax.win_ev if ax is not None else None
        if aev is None or aev < min_axis_win_ev:
            shown = f"{aev:.2f}" if aev is not None else "--"
            return FormationResult(
                rid, axis, [], [], [], [], 0,
                [f"見送り: ◎win_ev {shown} < {min_axis_win_ev:.2f} (過剰人気◎)"])

    head_set = select_head(race_eff, axis, win_prob_floor=win_prob_floor,
                           ev_floor=head_ev_floor, n_max=n_head_max)
    renjiku_set = select_renjiku(race_eff, axis, n=n_renjiku)
    third_set = select_third(race_eff, axis, anaba_umabans=anaba_umabans,
                             paddock_marks=paddock_marks, n_composite=n_third_composite,
                             paddock_keep=paddock_keep)

    if not head_set:
        warnings.append("頭候補なし (pred_w≥floor ∧ win_ev≥floor を満たす非◎馬が不在) → 買い目なし")
        return FormationResult(rid, axis, head_set, renjiku_set, third_set, [], 0, warnings)

    win_probs = _norm_win_probs(race_eff)
    legs: List[FormationLeg] = []
    seen: set = set()

    # 買い目1: 頭 → ◎(2着) → 3着候補
    for h in head_set:
        for t in third_set:
            if len({h, axis, t}) != 3:
                continue
            key = (h, axis, t)
            if key in seen:
                continue
            seen.add(key)
            legs.append(_make_leg(win_probs, sanrentan_odds, h, axis, t, ROLE_MARU_2ND))

    # 買い目2: 頭 → 連軸 → ◎(3着)
    for h in head_set:
        for r in renjiku_set:
            if len({h, r, axis}) != 3:
                continue
            key = (h, r, axis)
            if key in seen:
                continue
            seen.add(key)
            legs.append(_make_leg(win_probs, sanrentan_odds, h, r, axis, ROLE_MARU_3RD))

    n_before = len(legs)
    if not legs:
        warnings.append("買い目0点 (候補が軸と被る等) → 買い目なし")
        return FormationResult(rid, axis, head_set, renjiku_set, third_set, [], 0, warnings)

    if not sanrentan_odds:
        warnings.append("三連単オッズ未取得 → hv_ev 評価なし (点数だけで trim)")

    legs = trim_by_hv_ev(legs, max_points)
    if n_before > len(legs):
        warnings.append(f"trim: {n_before}点 → {len(legs)}点 (hv_ev 低い順に切り捨て・max {max_points})")

    return FormationResult(rid, axis, head_set, renjiku_set, third_set, legs, n_before, warnings)

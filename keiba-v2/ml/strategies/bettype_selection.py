#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""券種選択ロジック — 券種効率ビュー (Phase2) の plans[] から「絞る/降りる」を決める
(Session 139 / bettype-selection-roadmap Phase 3 = 選択ロジック + 妙味軸オプション)

設計思想: [[bettype-selection-roadmap]] 構想1 Phase3 / [[feedback_betting_philosophy]] §4
  Phase2 (bettype_efficiency) は「各券種プランの (的中確率, 合成オッズ, 期待リターン)」を
  並べて見せるだけの判断支援。 Phase3 はそこから「実際にどの券種を買うか / 降りるか」を
  決める。 ふくだ方針 (Session 137): EV>1 で全 fund する機械判断ではなく、 予想ベース +
  合成オッズ判断で券種を絞る (時に単だけ / 馬連だけ / 見送り許容)。

★★★シズネ Session 138 置き土産 (誤誘導防止 = 本モジュールの核心制約):
  vs_tansho ('合成オッズ <> 単オッズ') は「広げる相対妙味」であって EV の絶対水準ではない。
  控除率 (単20%/三連系27.5%) があるため市場オッズベースでは通常ほぼ全プランで EV<1.0
  (期待マイナス) が常態。 「合成 > 単」でも EV<1.0 はあり得る → 「広げ得 ≠ 儲かる」。
  ∴ fund 判断には vs_tansho を使わない。 EV の絶対水準 (should_fund) で判断する。
  vs_tansho は「広げる相対妙味」の参考表示にとどめ、 decision_reason で必ず注意喚起する。

プリセット (--strategy):
  concentrate     : 保守 (既定)。 単勝◎を基本 fund。 複合券種は EV>=floor かつ
                    vs_tansho=='gt' (広げる相対妙味あり) の両方を満たすものだけ追加。
                    → 「広げる意味がある時だけ広げる」。
  ev_floor        : 券種問わず EV>=floor を全 fund (Phase2 的挙動の足切り版)。
  spread_if_worth : concentrate より緩い。 vs_tansho=='gt' なら EV<floor でも残すが
                    decision_reason に「※EV<1 (控除率下の常態)」を明示警告。
  hole_seeker     : 妙味軸オプション。 軸を composite最強でなく妙味軸 (穴志向) に差し替え、
                    その軸で再評価したプランから選ぶ。 --taste で軸選定モードを指定。
  (skip_all)      : 明示指定ではなく、 上記いずれでも fund 対象 0 件のとき自動で落ちる状態。

妙味軸オプション (--taste, hole_seeker 用):
  popularity_gap_max : z(勝率) - z(人気) が最大の馬を軸に。 市場が過小評価する馬 (穴)。
  ev_min             : 合成オッズが妙味のある (= EV>=floor で配当の高い) プランを優先。

入出力:
  入力  : predictions.json (process_race 経由で RaceEfficiency を生成)
  出力  : betting_selection.json (selective_loader v2.0 互換 schema,
                                  source="bettype_selection", amount は付けない=候補段階)

CLI:
    python -m ml.strategies.bettype_selection --date 2026-05-30 --strategy concentrate
    python -m ml.strategies.bettype_selection --date today --strategy ev_floor --ev-floor 1.0
    python -m ml.strategies.bettype_selection --race 2026053005021101 \
        --strategy hole_seeker --taste popularity_gap_max
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_fund as bf  # noqa: E402
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402

ARTIFACT_NAME = "betting_selection.json"
SCHEMA_VERSION = "2.0"          # selective_loader 互換 (ALLOWED_VERSIONS)
SOURCE = "bettype_selection"    # selective_loader.ALLOWED_SOURCES に追加した source

# fund 判定の既定 EV floor。 1.0 = 期待値プラスのみ fund。
# 運用上はプリセット (spread_if_worth) や --ev-floor で緩めるが、 既定は数学的中立点。
DEFAULT_EV_FLOOR = 1.0

# 基準券種 = 軸◎そのものの買い方 (広げる券種ではない)。 vs_tansho を持たず、
# 「広げる/降りる」の選択対象外。 fund 判定でも複合券種と分けて常に採用候補とする。
# (単勝は EV=None=基準、 複勝も axis_place が無ければ EV=None で同列に扱う)
BASE_BET_TYPES = ("tansho", "fukusho")

STRATEGIES = ("concentrate", "ev_floor", "spread_if_worth", "hole_seeker", "adaptive")
TASTES = ("popularity_gap_max", "ev_min")

# 「広げ得 ≠ 儲かる」を decision_reason / select_reason に必ず織り込む共通文言
SPREAD_CAVEAT = "※合成オッズの比較 (vs単) は『広げる相対妙味』であって期待値の符号ではない (広げ得≠儲かる)"


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------

@dataclass
class SelectedPlan:
    bet_type: str
    label: str
    legs: List[List[int]]
    hit_prob: float
    expected_return: Optional[float]   # EV = Σpₖ/Σ(1/oₖ)。 単勝は None
    synthetic_odds: Optional[float]    # 合成オッズ G。 単勝は None
    vs_tansho: Optional[str]           # 'lt'/'gt'/None (参考表示のみ。 fund 判断には未使用)
    select_reason: str                 # なぜこのプランを fund するか


@dataclass
class SkippedPlan:
    bet_type: str
    label: str
    expected_return: Optional[float]
    vs_tansho: Optional[str]
    skip_reason: str                   # 「EV<floor」「合成<単で広げ妙味薄」等


@dataclass
class BetSelection:
    race_id: str
    date: Optional[str]
    venue_name: Optional[str]
    race_number: Optional[int]
    grade: str
    axis_umaban: int
    axis_name: str
    axis_odds: Optional[float]
    strategy: str                      # 結果の状態 (skip_all を含む実効戦略)
    requested_strategy: str            # CLI 指定の戦略 (skip_all 自動フォールバック前)
    ev_floor: float
    taste: Optional[str]               # 妙味軸モード (hole_seeker 時) or None
    specialist: Optional[str]
    selected_plans: List[SelectedPlan]
    skipped_plans: List[SkippedPlan]
    decision_reason: str               # 「広げ得≠儲かる」を必ず含意
    fund_mode: Optional[str] = None    # P2b: skip_all/tansho_only/boost/longshot_flow/spread
    fund_reason: Optional[str] = None  # P2b: decide_fund の理由
    kelly_boost: float = 1.0           # P2b: sizing 増額倍率
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# fund 判定 (シズネ置き土産の本体) — EV 絶対水準のみで判断、 vs_tansho は使わない
# ---------------------------------------------------------------------------

def should_fund(plan: "be.Plan", *, ev_floor: float = DEFAULT_EV_FLOOR) -> bool:
    """このプランを fund 対象とするか。 複合券種は ★EV の絶対水準のみで判断する★。

    - 基準券種 (単勝/複勝 = 軸◎そのもの = アンカー): ★常に fund★。
      ふくだ方針「単勝◎を基本fund」(Session 137/139)。 「広げる」対象でなく軸◎の
      素直な買い方なので EV floor で足切りしない。 EV<1.0 (低オッズ本命など) でも
      候補に残し EV を情報として見せる。 -EV 保護は下流の Kelly サイジングが担う
      (候補段階は amount 無し)。 → -EV は _base_reason で正直に注記する。
    - 複合券種 (馬連〜三連単): EV (expected_return) >= ev_floor のときだけ True。
      EV が None (市場オッズ未取得) なら判定不能 → False (買わない)。

    ★vs_tansho は一切参照しない★ (合成>単でも EV<1.0 はあり得るため。 シズネ Session 138)。
    """
    if plan.bet_type in BASE_BET_TYPES:
        return True
    if plan.expected_return is None:
        return False
    return plan.expected_return >= ev_floor


def _has_relative_spread_merit(plan: "be.Plan") -> bool:
    """vs_tansho=='gt' = 単オッズより合成オッズが高い = 広げる『相対』妙味あり。

    ★これは期待値の符号ではない (広げ得≠儲かる)。 concentrate の『広げる時だけ広げる』
    判断や spread_if_worth の残置条件など、 fund そのものではなく『どの券種に広げるか』の
    補助フィルタとしてのみ使う。 should_fund (EV絶対水準) と必ず AND で使うこと。
    """
    return plan.vs_tansho == "gt"


# ---------------------------------------------------------------------------
# 妙味軸オプション (穴志向)
# ---------------------------------------------------------------------------

def find_taste_axis(race_eff: "be.RaceEfficiency", taste: str) -> Optional[int]:
    """妙味軸 (穴志向) の軸馬番を返す。 該当無しなら None (= composite 軸を維持)。

    popularity_gap_max:
        「model は (相応に) 強いと見ているのに 市場人気が低い = 過小評価」 の馬を軸にする。
        乖離は ★外れ値に頑健な順位差★ で測る:
            gap = 人気ランク (odds 昇順 1=最人気) − model ランク (composite 降順 1=最評価)
        gap が大 = 市場が model より低く評価 = 過小評価。 gap<=0 (市場 >= model) なら
        過小評価でないので軸を動かさない (None)。

        ★model ランクは composite (W/P/ADR 総合 = AI印◎の基準) で測る。
          旧実装は win_prob 順位 (win_rank) を使っていたが、win_prob は団子レースで多数が
          同値になり (実例 5/31 京都12R: 9頭が同一 win_prob)、同値を馬番で割って付けた順位は
          無意味。その結果 composite 中位 (例 11/18 位) の longshot が「win_rank 上位の過小評価馬」と
          誤認され軸に選ばれていた (京都12R ⑯=77倍 / 京都8R ⑥=60倍 をライブ投票)。
          ふくだ方針「評価した馬の中で妙味を買う」= composite (実評価) で候補を絞り gap も測る。
          2 段フロア: ① composite top-3 のみ ② win_prob>=1/n (ハーヴィル入力の最低勝率)。★
    ev_min:
        合成オッズが最も妙味のある (= EV>=floor を満たし synthetic_odds が最大の)
        プランの軸を返す。 軸そのものは Phase2 の composite 最強と同じだが、
        「広げて妙味を取りに行く」意図を taste で記録する。 → 軸差し替えはしない。
    """
    if taste == "popularity_gap_max":
        # 候補 = 市場オッズが立ち (odds>0) かつ model が非自明な勝率を与える (win_prob>0) 馬。
        present = [s for s in race_eff.strengths
                   if s.odds is not None and s.odds > 0 and s.win_prob > 0]
        if not present:
            return None
        n = len(present)
        # 人気ランク (odds 昇順, 1=最人気) と model ランク (composite 降順, 1=最評価)。
        # ★model ランクは composite (= AI印◎の基準) で測る。 win_prob 順位は団子レースで
        #   同値が多発し (同値を馬番で割る) composite 中位の longshot を上位と誤認するため使わない。
        pop_rank = {s.umaban: i for i, s in
                    enumerate(sorted(present, key=lambda s: (s.odds, s.umaban)), start=1)}
        comp_rank = {s.umaban: i for i, s in
                     enumerate(sorted(present, key=lambda s: (-s.composite, -s.win_prob, s.umaban)),
                               start=1)}
        # 候補フロア (2段)。 単なる人気薄を軸に選ばない & ハーヴィルが意味を保つための必須ガード:
        #   ① model 順位 floor: composite top-3 のみ (= model の明確な上位)。
        #      旧 top-third (ceil(n/3)) は大頭数で境界が緩み、 composite 境界の平均馬が極端
        #      オッズ (実例 6/6 venue2 R6 ⑦=120倍/composite rank5/z 全0.2前後) で gap 最大に
        #      なり軸に選ばれた。 「評価した“強い”馬の中で妙味を買う」(ふくだ S141) に合わせ
        #      top-3 へ締める。
        #   ② 絶対勝率 floor: win_prob >= 1/n (一様ランダム超え) = ハーヴィル入力の最低勝率。
        support_cut = min(n, 3)
        prob_floor = 1.0 / n
        cands = [s for s in present
                 if comp_rank[s.umaban] <= support_cut and s.win_prob >= prob_floor]
        if not cands:
            return None       # 過小評価できる contender 不在 → 軸据え置き (composite 維持)
        # gap = pop_rank - comp_rank の最大。 同値は composite 上位 → 馬番昇順 で決定的に。
        best = max(cands, key=lambda s: (pop_rank[s.umaban] - comp_rank[s.umaban],
                                         -comp_rank[s.umaban], -s.umaban))
        if pop_rank[best.umaban] - comp_rank[best.umaban] <= 0:
            return None       # 過小評価でない (市場 >= model 評価) → 軸据え置き
        return best.umaban
    if taste == "ev_min":
        # ev_min は軸差し替えしない (合成妙味の高いプラン優先は select 側で扱う)。
        return race_eff.axis_umaban
    return None


# ---------------------------------------------------------------------------
# 選択ロジック (プリセット)
# ---------------------------------------------------------------------------

def _to_selected(plan: "be.Plan", reason: str) -> SelectedPlan:
    return SelectedPlan(
        bet_type=plan.bet_type, label=plan.label, legs=plan.legs,
        hit_prob=plan.hit_prob, expected_return=plan.expected_return,
        synthetic_odds=plan.synthetic_odds, vs_tansho=plan.vs_tansho,
        select_reason=reason,
    )


def _to_skipped(plan: "be.Plan", reason: str) -> SkippedPlan:
    return SkippedPlan(
        bet_type=plan.bet_type, label=plan.label,
        expected_return=plan.expected_return, vs_tansho=plan.vs_tansho,
        skip_reason=reason,
    )


def _base_reason(p) -> str:
    kind = "単勝" if p.bet_type == "tansho" else "複勝"
    base = f"軸◎の{kind} (基準券種・アンカー)"
    # アンカー自身が -EV (EV<1.0) のときは正直に注記 (シズネ流の誤誘導防止)。
    if p.expected_return is not None and p.expected_return < DEFAULT_EV_FLOOR:
        return f"{base} ※EV={p.expected_return:.2f}<1.0 (本命だが期待値マイナス寄り)"
    return base


def _select_concentrate(plans, ev_floor) -> Tuple[list, list]:
    """基準券種 (単/複) + (EV>=floor かつ vs_tansho=='gt') の複合券種だけ fund。"""
    selected, skipped = [], []
    for p in plans:
        if p.bet_type in BASE_BET_TYPES:
            # 基準券種 (◎単/複) はアンカー = 常に fund (should_fund 契約)。
            selected.append(_to_selected(p, _base_reason(p)))
            continue
        funded = should_fund(p, ev_floor=ev_floor)
        merit = _has_relative_spread_merit(p)
        if funded and merit:
            selected.append(_to_selected(
                p, f"EV={p.expected_return:.2f}>=floor かつ合成>単 (広げる相対妙味あり)"))
        elif not funded:
            ev_s = f"{p.expected_return:.2f}" if p.expected_return is not None else "N/A"
            skipped.append(_to_skipped(p, f"EV={ev_s}<floor({ev_floor}) → 降りる"))
        else:  # funded but no relative merit
            skipped.append(_to_skipped(
                p, "EV>=floor だが合成<=単 (広げる相対妙味薄) → 単に集中"))
    return selected, skipped


def _select_ev_floor(plans, ev_floor) -> Tuple[list, list]:
    """券種問わず EV>=floor を全 fund (基準券種 単/複 は EV 無しでも採用)。"""
    selected, skipped = [], []
    for p in plans:
        if should_fund(p, ev_floor=ev_floor):
            if p.bet_type in BASE_BET_TYPES:
                selected.append(_to_selected(p, _base_reason(p)))
            else:
                selected.append(_to_selected(p, f"EV={p.expected_return:.2f}>=floor({ev_floor})"))
        else:
            ev_s = f"{p.expected_return:.2f}" if p.expected_return is not None else "N/A"
            skipped.append(_to_skipped(p, f"EV={ev_s}<floor({ev_floor})"))
    return selected, skipped


def _select_spread_if_worth(plans, ev_floor) -> Tuple[list, list]:
    """concentrate より緩い。 EV>=floor は当然 fund。 加えて EV<floor でも
    vs_tansho=='gt' なら『相対妙味あり』として残す (ただし select_reason に
    『※EV<1 (控除率下の常態)。 期待値マイナス寄り』を明示警告)。"""
    selected, skipped = [], []
    for p in plans:
        if p.bet_type in BASE_BET_TYPES:
            selected.append(_to_selected(p, _base_reason(p)))   # アンカー = 常に fund
            continue
        if should_fund(p, ev_floor=ev_floor):
            selected.append(_to_selected(p, f"EV={p.expected_return:.2f}>=floor({ev_floor})"))
        elif _has_relative_spread_merit(p):
            ev_s = f"{p.expected_return:.2f}" if p.expected_return is not None else "N/A"
            selected.append(_to_selected(
                p, f"合成>単 (広げる相対妙味あり) で残置。 ただし EV={ev_s}<floor "
                   f"= 控除率下の常態、 期待値マイナス寄り (広げ得≠儲かる)"))
        else:
            ev_s = f"{p.expected_return:.2f}" if p.expected_return is not None else "N/A"
            skipped.append(_to_skipped(p, f"EV={ev_s}<floor かつ合成<=単 → 降りる"))
    return selected, skipped


def _select_adaptive(plans, ev_floor, decision: bf.FundDecision) -> Tuple[list, list]:
    """P2b: bettype_efficiency + decide_fund で券種を出し分け (vs_tansho 不使用)。"""
    selected, skipped = [], []
    raw_sel, raw_skip = bf.filter_plans_for_fund(plans, decision, ev_floor=ev_floor)
    for p, reason in raw_sel:
        selected.append(_to_selected(p, reason))
    for p, reason in raw_skip:
        skipped.append(_to_skipped(p, reason))
    return selected, skipped


def _select_hole_seeker(plans, ev_floor, taste) -> Tuple[list, list]:
    """妙味軸での評価結果から、 EV>=floor のプランを fund (ev_floor と同じ足切り)。
    軸が既に妙味軸へ差し替わっている前提 (select_plans が再評価して渡す)。
    taste=ev_min のときは EV>=floor かつ合成オッズ最大のプランを優先表示順に。"""
    selected, skipped = [], []
    for p in plans:
        if should_fund(p, ev_floor=ev_floor):
            if p.bet_type in BASE_BET_TYPES:
                kind = "単勝" if p.bet_type == "tansho" else "複勝"
                selected.append(_to_selected(p, f"妙味軸◎の{kind} (taste={taste})"))
            else:
                selected.append(_to_selected(
                    p, f"妙味軸 (taste={taste}) で EV={p.expected_return:.2f}>=floor"))
        else:
            ev_s = f"{p.expected_return:.2f}" if p.expected_return is not None else "N/A"
            skipped.append(_to_skipped(p, f"EV={ev_s}<floor({ev_floor})"))
    if taste == "ev_min":
        # 合成オッズ (配当妙味) 降順で並べ替え (単勝は synthetic_odds=None → 末尾)
        selected.sort(key=lambda sp: (sp.synthetic_odds is not None,
                                      sp.synthetic_odds or 0.0), reverse=True)
    return selected, skipped


def select_plans(
    race_eff: "be.RaceEfficiency",
    *,
    strategy: str = "concentrate",
    ev_floor: float = DEFAULT_EV_FLOOR,
    taste: Optional[str] = None,
    bankroll: int = 10000,
    kelly_fraction: float = 0.25,
    per_bet_cap_pct: float = 0.10,
) -> BetSelection:
    """RaceEfficiency (Phase2) の plans[] から fund 対象を選ぶ。

    ★fund 判定は should_fund (EV絶対水準) が唯一の門番★。 vs_tansho は
    『どの券種に広げるか』の補助フィルタとしてのみ使い、 fund の可否を単独で決めない。
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy!r} (allowed: {STRATEGIES})")

    requested = strategy
    eff = race_eff
    used_taste = None
    warnings = list(race_eff.warnings)
    fund_mode: Optional[str] = None
    fund_reason: Optional[str] = None
    kelly_boost = 1.0

    if strategy == "concentrate":
        selected, skipped = _select_concentrate(eff.plans, ev_floor)
    elif strategy == "ev_floor":
        selected, skipped = _select_ev_floor(eff.plans, ev_floor)
    elif strategy == "spread_if_worth":
        selected, skipped = _select_spread_if_worth(eff.plans, ev_floor)
    elif strategy == "adaptive":
        decision = bf.decide_fund(
            eff, ev_floor=ev_floor, bankroll=bankroll,
            kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
        fund_mode = decision.mode
        fund_reason = decision.reason
        kelly_boost = decision.kelly_boost
        selected, skipped = _select_adaptive(eff.plans, ev_floor, decision)
    elif strategy == "hole_seeker":
        used_taste = taste or "popularity_gap_max"
        if used_taste not in TASTES:
            raise ValueError(f"unknown taste: {used_taste!r} (allowed: {TASTES})")
        selected, skipped = _select_hole_seeker(eff.plans, ev_floor, used_taste)
    else:  # pragma: no cover - guarded above
        selected, skipped = [], []

    # 実効戦略 + decision_reason。
    # ★基準券種 (単/複) は通常 selected に入るので「fund 対象 0 件」は稀だが、 複合券種が
    #   一切残らない (= 基準のみ) ケースは「広げる妙味なし → 軸に集中」を明示する。
    combo_selected = [s for s in selected if s.bet_type not in BASE_BET_TYPES]
    eff_strategy = strategy
    if strategy == "adaptive" and fund_mode == "skip_all":
        eff_strategy = "skip_all"
        selected = []
        skipped = [_to_skipped(p, fund_reason or "降りる") for p in eff.plans]
        decision = f"{fund_reason or '降りる'}。 {SPREAD_CAVEAT}"
    elif not selected:
        # 基準券種すら無い (= プラン自体が空 / 軸不明等) → 完全見送り
        eff_strategy = "skip_all"
        decision = f"fund 対象なし → 全見送り。 {SPREAD_CAVEAT}"
    elif strategy == "adaptive" and fund_mode:
        decision = f"adaptive/{fund_mode}: {fund_reason}。 {SPREAD_CAVEAT}"
    elif not combo_selected:
        decision = (f"複合券種に fund 対象なし (EV<floor={ev_floor} 等) → 単勝◎に集中。 "
                    f"{SPREAD_CAVEAT}")
    else:
        n = len(combo_selected)
        decision = (f"{strategy}: 複合券種 {n} 件を fund (いずれも EV 絶対水準で判定)。 "
                    f"{SPREAD_CAVEAT}")

    return BetSelection(
        race_id=eff.race_id, date=eff.date, venue_name=eff.venue_name,
        race_number=eff.race_number, grade=eff.grade,
        axis_umaban=eff.axis_umaban, axis_name=eff.axis_name,
        axis_odds=eff.axis_odds,
        strategy=eff_strategy, requested_strategy=requested, ev_floor=ev_floor,
        taste=used_taste, specialist=eff.specialist,
        selected_plans=selected, skipped_plans=skipped,
        decision_reason=decision, warnings=warnings,
        fund_mode=fund_mode, fund_reason=fund_reason, kelly_boost=kelly_boost,
    )


# ---------------------------------------------------------------------------
# レース評価 (Phase2 を呼んで入力を作り、 選択を返す)
# ---------------------------------------------------------------------------

def evaluate_and_select(
    pred_race: dict,
    *,
    strategy: str = "concentrate",
    ev_floor: float = DEFAULT_EV_FLOOR,
    taste: Optional[str] = None,
    axis: Optional[int] = None,
    weights: Tuple[float, float, float] = be.DEFAULT_WEIGHTS,
    n_partners: int = be.DEFAULT_N_PARTNERS,
) -> Optional[BetSelection]:
    """predictions の 1 race を Phase2 で評価 → 妙味軸差し替え → 選択。

    hole_seeker のとき: まず軸指定なしで一度評価し find_taste_axis で妙味軸を決め、
    その軸で再評価してから選択する (軸差し替えは harville 勝率入力に影響するため
    必ず再評価する。 ev_min は軸を変えないので再評価不要)。
    """
    re_ = be.process_race(pred_race, axis=axis, weights=weights, n_partners=n_partners)
    if re_ is None:
        return None

    if strategy == "hole_seeker" and axis is None:
        used_taste = taste or "popularity_gap_max"
        taxis = find_taste_axis(re_, used_taste)
        if taxis is not None and taxis != re_.axis_umaban:
            # 軸を妙味軸へ差し替えて再評価 (合成オッズ・EV が軸依存のため)
            re_ = be.process_race(pred_race, axis=taxis, weights=weights,
                                  n_partners=n_partners)
            if re_ is None:
                return None

    return select_plans(re_, strategy=strategy, ev_floor=ev_floor, taste=taste)


# ---------------------------------------------------------------------------
# artifact 出力 (selective_loader v2.0 互換)
# ---------------------------------------------------------------------------

def selection_to_dict(sel: BetSelection) -> dict:
    return asdict(sel)


def _selection_to_bets(sel: BetSelection) -> List[dict]:
    """selected_plans を selective_loader 互換の bets[] に展開。

    各プランの各 leg (買い目の点) を 1 bet にし、 軸馬番を umaban に置く
    (selective_loader は単勝系の umaban 検証のみ。 複合券種の脚は extra に保持)。
    selective_loader 必須フィールド: race_id / umaban / horse_name(非空) / odds(>0) /
    source。 全 leg は軸◎から広げるので horse_name=軸名・odds=軸の単勝オッズ を共通で持たせる
    (odds は「ライブ市場が立っているか」の >0 ゲート用。 複合オッズは synthetic_odds 等の
    extra に保持)。 amount は付けない (候補段階 = 表示専用。 require_funded=True の
    vote-mode で弾かれる = 誤って -EV 候補を投票しない安全。 Session 137 流儀)。

    ★軸の単勝オッズが未確定 (None/<=0) のレースは bets[] に出さない (selective_loader の
    odds>0 検証に通らないため。 構造化 selections には残るので表示は失わない)。
    ★同一 race の複数プランは umaban=軸 で重複するため selective_loader が「重複 bet」警告を
    出すが非致命 (複合券種の投票経路は未配線。 現状 bets[] の主用途は前方互換)。
    """
    out: List[dict] = []
    axis_name = (sel.axis_name or "").strip() or f"馬{sel.axis_umaban}"
    axis_odds = sel.axis_odds
    if axis_odds is None or axis_odds <= 0:
        return out
    for sp in sel.selected_plans:
        for leg in sp.legs:
            out.append({
                "race_id": sel.race_id,
                "umaban": int(leg[0]),          # 軸 (1頭目)。 検証は単勝 umaban 互換
                "horse_name": axis_name,        # 軸名 (selective_loader 必須・非空)
                "odds": float(axis_odds),       # 軸の単勝オッズ (>0 ゲート用)
                "source": SOURCE,
                "venue_name": sel.venue_name,
                "race_number": sel.race_number,
                "grade": sel.grade,
                # --- メタ (extra に保持される。 投票経路はまだ単勝のみ実行) ---
                "bet_type": sp.bet_type,
                "legs": leg,
                "label": sp.label,
                "hit_prob": sp.hit_prob,
                "expected_return": sp.expected_return,
                "synthetic_odds": sp.synthetic_odds,
                "vs_tansho": sp.vs_tansho,
                "strategy": sel.strategy,
                "ev_floor": sel.ev_floor,
                "select_reason": sp.select_reason,
            })
    return out


def write_selection(date_dir: Path, selections: List[BetSelection], *,
                    strategy: str, ev_floor: float,
                    taste: Optional[str]) -> Path:
    """betting_selection.json を date_dir に書き出し (selective_loader 互換 schema)。"""
    bets: List[dict] = []
    for sel in selections:
        bets.extend(_selection_to_bets(sel))
    payload = {
        "strategy": "selective",          # selective_loader 互換のため固定
        "version": SCHEMA_VERSION,
        "description": (
            f"bettype_selection (strategy={strategy}, ev_floor={ev_floor}"
            f"{', taste=' + taste if taste else ''}) — 候補段階 (amount 無し)。 "
            f"fund 判断は EV 絶対水準。 vs_tansho は相対妙味のみ (広げ得≠儲かる)"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selection_strategy": strategy,
        "ev_floor": ev_floor,
        "taste": taste,
        "n_races": len(selections),
        "n_bets": len(bets),
        "selections": [selection_to_dict(s) for s in selections],
        "bets": bets,
    }
    out_path = date_dir / ARTIFACT_NAME
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return out_path


def resolve_date(date_str: str) -> str:
    if date_str.strip().lower() == "today":
        return datetime.now().strftime("%Y-%m-%d")
    return date_str


def process_date(
    date_str: str, *,
    strategy: str = "concentrate",
    ev_floor: float = DEFAULT_EV_FLOOR,
    taste: Optional[str] = None,
    weights: Tuple[float, float, float] = be.DEFAULT_WEIGHTS,
    n_partners: int = be.DEFAULT_N_PARTNERS,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print(f"  [{date_str}] predictions.json なし → スキップ")
        return {"date": date_str, "n_races": 0, "skipped": True}

    races = predictions.get("races", []) or []
    selections: List[BetSelection] = []
    for r in races:
        sel = evaluate_and_select(
            r, strategy=strategy, ev_floor=ev_floor, taste=taste,
            weights=weights, n_partners=n_partners)
        if sel is not None:
            selections.append(sel)

    if not dry_run:
        out_path = write_selection(day_dir, selections, strategy=strategy,
                                   ev_floor=ev_floor, taste=taste)
        if verbose:
            print(f"  [{date_str}] {len(selections)} races → {out_path}")
    return {"date": date_str, "n_races": len(selections), "skipped": False}


# ---------------------------------------------------------------------------
# CLI 表示
# ---------------------------------------------------------------------------

def _print_selection(sel: BetSelection) -> None:
    print(f"\n=== {sel.race_id} {sel.venue_name or '?'} {sel.race_number or '?'}R "
          f"{sel.grade} ===")
    taste = f" taste={sel.taste}" if sel.taste else ""
    spec = f" specialist={sel.specialist}" if sel.specialist else ""
    eff = "" if sel.strategy == sel.requested_strategy else f" → {sel.strategy}"
    print(f"軸◎ {sel.axis_umaban}番 {sel.axis_name} 単{(sel.axis_odds or 0):.1f}倍  "
          f"strategy={sel.requested_strategy}{eff} ev_floor={sel.ev_floor}{taste}{spec}")
    print(f"  判断: {sel.decision_reason}")
    print(f"  ◎ fund 対象 ({len(sel.selected_plans)} 件):")
    for sp in sel.selected_plans:
        ev = f"{sp.expected_return:.2f}" if sp.expected_return is not None else "--"
        g = f"{sp.synthetic_odds:.1f}" if sp.synthetic_odds is not None else "--"
        print(f"    ✅ {sp.label:<16} EV={ev:>5} 合成={g:>6}  {sp.select_reason}")
    if sel.skipped_plans:
        print(f"  ✖ 降りた券種 ({len(sel.skipped_plans)} 件):")
        for sk in sel.skipped_plans:
            ev = f"{sk.expected_return:.2f}" if sk.expected_return is not None else "--"
            print(f"    ✖ {sk.label:<16} EV={ev:>5}  {sk.skip_reason}")
    for w in sel.warnings:
        print(f"  ⚠ {w}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--race", help="単一レース (race_code 16桁) を stdout 表示")
    g.add_argument("--date", help="日付の全レース → JSON artifact (today 可)")
    p.add_argument("--strategy", default="concentrate", choices=STRATEGIES,
                   help="選択戦略 (default concentrate)")
    p.add_argument("--ev-floor", type=float, default=DEFAULT_EV_FLOOR,
                   help=f"fund する EV 下限 (default {DEFAULT_EV_FLOOR})")
    p.add_argument("--taste", default=None, choices=TASTES,
                   help="妙味軸モード (hole_seeker 用)")
    p.add_argument("--axis", type=int, default=None, help="軸馬番を上書き (--race時)")
    p.add_argument("--weights", default=None, help="W,P,ADR 重み (例: 2,1,1)")
    p.add_argument("--n-partners", type=int, default=be.DEFAULT_N_PARTNERS)
    p.add_argument("--dry-run", action="store_true", help="JSON 書かず表示のみ")
    p.add_argument("--json", action="store_true", help="--race を JSON で stdout 出力")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    weights = be._parse_weights(args.weights)

    if args.race:
        date_guess = f"{args.race[:4]}-{args.race[4:6]}-{args.race[6:8]}"
        day_dir = date_dir_for(date_guess)
        predictions = load_predictions(day_dir)
        if predictions is None:
            print(f"predictions.json が見つからない ({date_guess})")
            return 1
        pred_race = next((r for r in predictions.get("races", [])
                          if str(r.get("race_id")) == args.race), None)
        if pred_race is None:
            print(f"race {args.race} が predictions に無い")
            return 1
        sel = evaluate_and_select(
            pred_race, strategy=args.strategy, ev_floor=args.ev_floor,
            taste=args.taste, axis=args.axis, weights=weights,
            n_partners=args.n_partners)
        if sel is None:
            print("評価不能 (entries 無し)")
            return 1
        if args.json:
            print(json.dumps(selection_to_dict(sel), ensure_ascii=False, indent=2))
        else:
            _print_selection(sel)
        return 0

    result = process_date(args.date, strategy=args.strategy, ev_floor=args.ev_floor,
                          taste=args.taste, weights=weights,
                          n_partners=args.n_partners, dry_run=args.dry_run)
    print(f"\n[Done] {result.get('n_races', 0)} races (strategy={args.strategy})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

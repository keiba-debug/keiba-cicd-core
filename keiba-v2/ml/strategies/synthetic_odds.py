#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合成オッズ・トリガミ検出ユーティリティ (Session 148 / 買い方チューニング F1)

bet_templates が生成するプラン (Ticket 群 = 複数券種併用・weight 配分付き) に対し
「このプランは買う価値のある形か」を判定する純関数層。

  - 合成オッズ G = 1/Σ(1/oₖ)   … inverse-odds staking の標準定義 (ふくだの「合成2倍」感覚。
    bettype_efficiency.synthetic_and_ev と同定義だが、こちらは Ticket 群を直接受ける)
  - 実配分 (stakeₖ = stake_unit × weightₖ) での「その点だけ当たった場合のリターン」
        hit_return(k) = oₖ·stakeₖ / total_stake
    複勝/ワイドは多重的中で実際は上振れもあるが、「その点しか当たらない」結果は
    現実に起こるので worst 側の保守値として正しい。
  - トリガミ点 (hit_return < 1.0 = 当たったのに損) の列挙
  - 合成オッズフロアまでの greedy 点削減 (相手の広さ可変・「降りる」判断の道具)

DB/IO 非依存。市場オッズは odds_of(Ticket) -> float|None で注入する
(backtest = odds_db 確定組合せオッズ / 本番将来 = T-5分 時系列オッズに差し替え可)。

哲学整合 (feedback_betting_philosophy §4/§5):
  合成オッズは L1(買い目構成)/L3(買うか降りるか) の判断に使う。
  L2(いくら = weight) には使わない — weight は評価ベースで与えられた入力として扱うだけ。
注意 (シズネ置き土産): G や hit_return は「プランの形の良さ」であって EV の符号ではない。
  ゲートに使うときは相対比較 (vs 単勝) でなく絶対水準 (例 G >= 2.0) で切ること。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from ml.strategies.bet_templates import Ticket

OddsOf = Callable[[Ticket], Optional[float]]

# 順序あり券種 (kumiban を着順のまま並べる)
_ORDERED = {"umatan": True, "sanrentan": True,
            "umaren": False, "wide": False, "sanrenpuku": False}


# ---------------------------------------------------------------------------
# odds_db (get_all_combo_odds) -> OddsOf アダプタ
# ---------------------------------------------------------------------------

def kumiban(horses: Sequence[int], *, ordered: bool) -> str:
    """馬番列 -> KUMIBAN 文字列 (順不同は昇順ソート)。例 (2,1)->'0102' / ordered '0201'。"""
    seq = list(horses) if ordered else sorted(horses)
    return "".join(f"{int(u):02d}" for u in seq)


def make_odds_lookup(all_odds: Dict[str, dict]) -> OddsOf:
    """core.odds_db.get_all_combo_odds() の戻り値から OddsOf を作る。

    tansho/fukusho は umaban int キー、組合せ系は KUMIBAN 文字列キー。
    fukusho は odds_low (保守値)。ワイドの 'odds' は odds_low 採用済み (odds_db 仕様)。
    """
    def _of(tk: Ticket) -> Optional[float]:
        table = (all_odds or {}).get(tk.bet_type) or {}
        if tk.bet_type in ("tansho", "fukusho"):
            ent = table.get(int(tk.horses[0]))
            if not ent:
                return None
            o = ent.get("odds") if tk.bet_type == "tansho" else ent.get("odds_low")
            return float(o) if o else None
        ordered = _ORDERED.get(tk.bet_type)
        if ordered is None:
            return None
        ent = table.get(kumiban(tk.horses, ordered=ordered))
        if not ent:
            return None
        o = ent.get("odds")
        return float(o) if o else None
    return _of


# ---------------------------------------------------------------------------
# プラン分析 (合成オッズ・hit_return 分布・トリガミ)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TicketView:
    ticket: Ticket
    odds: Optional[float]          # 市場オッズ (None = 未取得)
    stake: float                   # 実配分 (stake_unit × weight)
    hit_return: Optional[float]    # この点「だけ」当たった場合の 払戻 / 総投資


@dataclass
class PlanAnalysis:
    views: List[TicketView]
    total_stake: float
    g: Optional[float]             # 合成オッズ (inverse-odds 標準定義・weight 非依存)
    coverage: float                # オッズを取得できた点の割合
    worst_hit_return: Optional[float]
    best_hit_return: Optional[float]
    torigami: List[TicketView]     # hit_return < 1.0 の点

    @property
    def has_torigami(self) -> bool:
        return len(self.torigami) > 0


def analyze_plan(tickets: Sequence[Ticket], odds_of: OddsOf,
                 *, stake_unit: float = 100.0) -> PlanAnalysis:
    """プラン全体の合成オッズ・実配分 hit_return 分布・トリガミ点を計算。

    stakeₖ = stake_unit × weightₖ (ラボ精算と同じ規約)。オッズ未取得 (None) の点は
    G から除外して coverage に反映、hit_return も None (トリガミ判定にも入れない)。
    """
    pre: List[tuple] = []
    total = 0.0
    inv_sum = 0.0
    n_funded = 0
    for tk in tickets:
        o = odds_of(tk)
        st = stake_unit * (tk.weight if tk.weight else 1.0)
        total += st
        pre.append((tk, o, st))
        if o is not None and o > 0:
            inv_sum += 1.0 / o
            n_funded += 1
    g = (1.0 / inv_sum) if inv_sum > 0 else None
    coverage = (n_funded / len(pre)) if pre else 0.0

    views: List[TicketView] = []
    hrs: List[float] = []
    for tk, o, st in pre:
        hr = (o * st / total) if (o is not None and o > 0 and total > 0) else None
        views.append(TicketView(tk, o, st, hr))
        if hr is not None:
            hrs.append(hr)
    return PlanAnalysis(
        views=views, total_stake=total, g=g, coverage=coverage,
        worst_hit_return=min(hrs) if hrs else None,
        best_hit_return=max(hrs) if hrs else None,
        torigami=[v for v in views if v.hit_return is not None and v.hit_return < 1.0],
    )


# ---------------------------------------------------------------------------
# 合成オッズフロアまでの点削減 (相手の広さ可変・降りる判断)
# ---------------------------------------------------------------------------

@dataclass
class PruneResult:
    kept: List[Ticket]
    dropped: List[Ticket]
    g_before: Optional[float]
    g_after: Optional[float]
    g_floor: float = 0.0

    @property
    def reached_floor(self) -> bool:
        """floor を満たせたか。False = このプランでは floor 不達 → 「降りる」判断材料。"""
        return self.g_after is not None and self.g_after >= self.g_floor


def prune_to_floor(tickets: Sequence[Ticket], odds_of: OddsOf, g_floor: float,
                   *, protect_roles: Sequence[str] = (),
                   max_drop: Optional[int] = None) -> PruneResult:
    """合成オッズ G が g_floor 以上になるまで低オッズ点から greedy に削る。

    G = 1/Σ(1/oₖ) は低オッズ点 (1/o が大きい) が支配する → 低オッズ順に外すのが最短。
    - protect_roles の点 (例 ROLE_INSURANCE) は削らない (保険を守って広さだけ調整する用)。
    - オッズ None の点は G に寄与しないので削減対象にしない (情報なしで切らない)。
    - 削り尽くしても floor に届かないプランは **一切削らず** そのまま返す
      (reached_floor=False) → 中途半端に痩せたプランを誤って買わせない。降りる判断へ。
    """
    pairs = [(tk, odds_of(tk)) for tk in tickets]
    funded = [(tk, o) for tk, o in pairs if o is not None and o > 0]

    def _g(items: List[tuple]) -> Optional[float]:
        s = sum(1.0 / o for _, o in items)
        return (1.0 / s) if s > 0 else None

    g_before = _g(funded)
    protect_set = set(protect_roles)
    droppable = sorted((x for x in funded if x[0].role not in protect_set),
                       key=lambda x: x[1])

    dropped_set: set = set()
    cur = list(funded)
    g_cur = g_before
    n_drop = 0
    for tk, o in droppable:
        if g_cur is not None and g_cur >= g_floor:
            break
        if max_drop is not None and n_drop >= max_drop:
            break
        cur = [x for x in cur if x[0] is not tk]
        dropped_set.add(id(tk))
        n_drop += 1
        g_cur = _g(cur)

    if g_cur is None or g_cur < g_floor:
        # 届かなかった → ロールバック (一切削らず返す)。 reached_floor=False を見て降りる。
        return PruneResult(kept=[tk for tk, _ in pairs], dropped=[],
                           g_before=g_before, g_after=g_before, g_floor=g_floor)

    kept = [tk for tk, _ in pairs if id(tk) not in dropped_set]
    dropped = [tk for tk, _ in pairs if id(tk) in dropped_set]
    return PruneResult(kept=kept, dropped=dropped, g_before=g_before, g_after=g_cur,
                       g_floor=g_floor)

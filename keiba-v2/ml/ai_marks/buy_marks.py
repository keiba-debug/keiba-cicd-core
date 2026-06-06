# -*- coding: utf-8 -*-
"""購入 ledger (purchase_ledger v2) → 買い軸印 (軸=◆ / 相手=◇) の抽出 (純関数)。

設計: docs/auto-purchase/23_AI_MARK_VOTE_SYNC_DESIGN.md (案C)

出所 = ledger v2 (= 税務 SoT)。scheduler_state ではなく ledger を起点にする (条件②)。
  - **軸** = 1 portfolio 内の全 ticket の raw_legs.horses の **積集合**。
    アンカー型戦略 (◎単 + ◎-相手の馬連/ワイド/馬単…) は全 leg が軸を含むので
    積集合 = {軸} になる。単票 (tansho/fukusho 1点) は積集合 = {その馬} = 軸。
  - **相手** = portfolio 内に登場する全馬 (和集合) から軸を除いた残り。
  - 積集合が空 (box/formation 等で共通馬なし) のときは軸なし = 全馬を相手 (◇) にする
    (honest fallback。明示 axis_umaban が要るケースは ledger writer 拡張で将来対応)。

複数 portfolio が同一レースにある場合:
  - ある portfolio で軸なら ◆、それ以外で登場するだけなら ◇ (軸が優先)。
  - `superseded_by_repair` の portfolio は除外 (Session 137 修復の旧 portfolio。settle と同様)。

I/O なし・DB 非依存・乱数なし。同一入力 → 同一出力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

AXIS_MARK = "◆"
PARTNER_MARK = "◇"


@dataclass
class RaceBuyMarks:
    """1 レース分の買い軸印 抽出結果。"""
    race_id: str
    axes: List[int]                       # 軸 (◆) の馬番 (昇順)
    partners: List[int]                   # 相手 (◇) の馬番 (昇順)
    marks: Dict[int, str]                 # {umaban: '◆'|'◇'} (DAT writer へ渡す形)
    n_portfolios: int                     # 集計対象 portfolio 数 (superseded 除外後)
    notes: List[str] = field(default_factory=list)


def _ticket_horses(ticket: dict) -> List[int]:
    """ticket.raw_legs.horses を int リストで返す (不正は空)。"""
    raw = ticket.get("raw_legs") or {}
    horses = raw.get("horses")
    if not isinstance(horses, list):
        return []
    out: List[int] = []
    for h in horses:
        try:
            v = int(h)
        except (TypeError, ValueError):
            continue
        if 1 <= v <= 18:
            out.append(v)
    return out


def _portfolio_axis_and_all(portfolio: dict) -> tuple[Set[int], Set[int]]:
    """1 portfolio から (軸集合, 登場全馬集合) を返す。

    軸 = 全 ticket horses の積集合。ticket が 1 枚も無ければ ({}, {})。
    """
    horse_sets: List[Set[int]] = []
    for t in portfolio.get("tickets", []):
        hs = set(_ticket_horses(t))
        if hs:
            horse_sets.append(hs)
    if not horse_sets:
        return set(), set()
    axis = set(horse_sets[0])
    all_horses: Set[int] = set()
    for hs in horse_sets:
        axis &= hs
        all_horses |= hs
    return axis, all_horses


def extract_race_buy_marks(race: dict) -> RaceBuyMarks:
    """ledger の 1 race dict → RaceBuyMarks。

    Args:
        race: {"race_id": str, "portfolios": [...]} 形式 (ledger v2)。
    """
    race_id = str(race.get("race_id", ""))
    notes: List[str] = []
    axes: Set[int] = set()
    all_horses: Set[int] = set()
    n_active = 0
    n_superseded = 0

    for pf in race.get("portfolios", []):
        if pf.get("superseded_by_repair"):
            n_superseded += 1
            continue
        axis_pf, all_pf = _portfolio_axis_and_all(pf)
        if not all_pf:
            continue
        n_active += 1
        axes |= axis_pf
        all_horses |= all_pf

    if n_superseded:
        notes.append(f"superseded_by_repair {n_superseded} portfolio を除外")

    partners = all_horses - axes
    if all_horses and not axes:
        notes.append("全 ticket に共通馬なし (box/formation?) のため軸なし=全馬を相手扱い")

    marks: Dict[int, str] = {}
    for u in sorted(axes):
        marks[u] = AXIS_MARK
    for u in sorted(partners):
        marks[u] = PARTNER_MARK

    return RaceBuyMarks(
        race_id=race_id,
        axes=sorted(axes),
        partners=sorted(partners),
        marks=marks,
        n_portfolios=n_active,
        notes=notes,
    )


def extract_buy_marks_from_ledger(ledger: dict) -> List[RaceBuyMarks]:
    """ledger 全体 → 各 race の RaceBuyMarks リスト (買い目のあるレースのみ)。

    Args:
        ledger: {"races": [...], ...} (purchase_ledger v2)。
    Returns:
        marks が空でないレースの RaceBuyMarks リスト (ledger の race 順)。
    """
    out: List[RaceBuyMarks] = []
    for race in ledger.get("races", []):
        rbm = extract_race_buy_marks(race)
        if rbm.marks:
            out.append(rbm)
    return out

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""戦略エンジン共通インターフェース

各券種戦略 (tansho/wide/umaren/sanrentan) はこのモジュールの抽象基底クラスを継承する。
詳細設計: docs/auto-purchase/09_MY_MARKS_AND_STRATEGY.md §5.2

設計原則:
  - 戦略は副作用を持たない pure function 寄り (入出力契約のみ)
  - 金額決定は bankroll レイヤの責務 (戦略は stake_hint のみ提案)
  - エンジン側で predictions / odds / my_marks を引いて RaceContext を組み立てる
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ml.features.my_marks import MyMark


# ===========================================================================
# 券種定義
# ===========================================================================

# 券種コード (TARGET 投票 CSV / IPAT 投票指示で使う表記に合わせる)
KIND_TANSHO = "tansho"        # 単勝
KIND_FUKUSHO = "fukusho"      # 複勝
KIND_UMAREN = "umaren"        # 馬連
KIND_UMATAN = "umatan"        # 馬単
KIND_WIDE = "wide"            # ワイド
KIND_SANRENPUKU = "sanrenpuku"  # 三連複
KIND_SANRENTAN = "sanrentan"  # 三連単


# ===========================================================================
# データクラス
# ===========================================================================

@dataclass
class RaceContext:
    """戦略エンジンへ渡す 1 レース分の入力"""
    race_id: str
    date: str                         # 'YYYY-MM-DD'
    venue_name: Optional[str]
    race_number: Optional[int]
    grade: Optional[str]
    track_type: Optional[str]
    distance: Optional[int]
    num_runners: Optional[int]
    race_confidence: Optional[float]  # polaris の race_confidence
    # entries: predictions.json の各馬 dict (umaban / odds / rank_p / rank_w / pred_proba_* など)
    entries: List[dict] = field(default_factory=list)
    # 馬番 → My印 (DAT + my_marks_v2 マージ済)
    my_marks: Dict[int, MyMark] = field(default_factory=dict)

    def find_entry(self, umaban: int) -> Optional[dict]:
        for e in self.entries:
            if int(e.get("umaban") or 0) == umaban:
                return e
        return None


@dataclass
class Bet:
    """戦略エンジンが生成する 1 単位の買い目候補

    Step 1: kind=tansho / horses=[◎馬番] / stake_hint=100 円
    Step 2 以降で kind/horses/legs を拡張 (フォーメーション等)
    """
    race_id: str
    kind: str                                # KIND_* 定数
    horses: List[int]                        # 単勝なら 1 頭、ワイドBOXなら複数 等
    stake_hint: int                          # 推奨額 (Step1 では固定 100。bankroll が最終確定)
    # メタ情報
    reason: str = ""                         # 「My印◎」「rank_p==1」等、選定理由
    mark_pattern: str = ""                   # 印パターンラベル (例: "1strong", "2strong")
    odds: Optional[float] = None             # 主役馬のオッズ snapshot (記録用)
    expected_value: Optional[float] = None   # EV snapshot (記録用)
    strategy_name: str = ""                  # 戦略名 (tansho_marker, selective_grade_top 等)
    formation_type: Optional[str] = None     # Step3以降で flat/formation/box などを区別
    raw_legs: Optional[dict] = None          # 三連単フォメ等の生表記 (ledger schema 14)


# ===========================================================================
# 抽象基底クラス
# ===========================================================================

class BettingStrategy(ABC):
    """戦略エンジン抽象基底クラス

    各戦略はこのクラスを継承し、 generate() を実装する。
    """

    name: str = ""             # サブクラスで上書き必須 (例: "tansho_marker")
    kind: str = ""             # サブクラスで上書き必須 (KIND_* のいずれか)

    @abstractmethod
    def generate(self, ctx: RaceContext) -> List[Bet]:
        """1 レース分の買い目候補を返す。 対象外なら空リスト。

        副作用は持たない。 ファイル書き込みやログは呼び出し元責務。
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} kind={self.kind!r}>"

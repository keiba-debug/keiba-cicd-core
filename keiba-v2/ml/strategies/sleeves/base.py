# -*- coding: utf-8 -*-
"""Sleeve 契約 — 買い目スリーブの抽象 (Session 176 / スリーブ・オーケストレーション §2.1)。

★契約は「ana ＋ 毛色違い(複勝/combo系)も載る」汎用形で切る★ (ふくだ S176・単勝専用に過剰適合させない):
  - size_race は ★券種非依存★ の RaceSizing を返す (単勝/複勝/combo どれでも脚に持てる)。
  - settle_day は ★当該スリーブ分にフィルタ済の votes★ を受ける (B別建て・§4)。
  - bankroll/day_cap/config は ★per-sleeve★ (隔離口座)。

スリーブは ★投票/タイミング/lock/halt を持たない★ (Orchestrator が集約)。当日開始時に freeze() で
サイジング入力を凍結し、以降のパスは凍結スナップショットで size_race する (gap と同じ日次凍結)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ml.strategies.bettype_sizing import RaceSizing


@dataclass(frozen=True)
class SleeveDisplay:
    """ActiveMethodCard / active-method API 用の表示メタ (S176 で確立した形)。"""
    label: str            # 短い方式名 (例: 逆張り単（ぎゃくばりたん）)
    thesis: str           # 「こういう買い目を狙ってるよ」(人間語)
    bet_type: str         # 主な券種
    results_link: Optional[str]   # 検証結果ページ (None 可)


class Sleeve:
    """買い目スリーブの契約。 実装は下記を提供する (Orchestrator がこの契約だけに依存する)。

    クラス属性:
      key:     str            一意キー (state/台帳/タグに使う・例 "gap_tansho")
      display: SleeveDisplay  表示メタ

    メソッド:
      is_enabled() -> bool                         master switch (config の <key>_enabled)
      freeze() -> dict                             当日開始時の凍結スナップショット
                                                   {"bankroll":int, "day_cap":int, ...sizing params}
      size_race(pred_race, snapshot) -> RaceSizing|None   凍結スナップショットで買い目+サイズ
      settle_day(date_str, votes) -> dict          ★votes は当該スリーブ分のみ★ で実払戻精算→台帳
    """
    key: str = "base"
    display: SleeveDisplay = SleeveDisplay("base", "", "", None)

    def is_enabled(self) -> bool:  # pragma: no cover - 抽象
        raise NotImplementedError

    def freeze(self, *, per_race_cap: int) -> dict:  # pragma: no cover - 抽象
        raise NotImplementedError

    def size_race(self, pred_race: dict, snapshot: dict) -> Optional[RaceSizing]:  # pragma: no cover
        raise NotImplementedError

    def settle_day(self, date_str: str, votes: dict) -> dict:  # pragma: no cover - 抽象
        raise NotImplementedError

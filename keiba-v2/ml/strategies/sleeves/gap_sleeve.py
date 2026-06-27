# -*- coding: utf-8 -*-
"""GapSleeve — 逆張り単（gap単勝）を Sleeve 契約に載せる薄いアダプタ (Session 176 / §8-1)。

gap_tansho_live が既に {config, 残高, サイズ, 台帳} を持つので、ここは委譲するだけ。
★現 gap_tansho_scheduler と挙動完全一致★ になるよう、freeze の bankroll/day_cap/bet_pct と
size_race の `size_gap_race` 呼び出しを gap_tansho_scheduler._run_pass_inner と同値にする。
"""
from __future__ import annotations

from typing import Optional

from ml.strategies import gap_tansho_live as gl
from ml.strategies.bettype_sizing import RaceSizing
from ml.strategies.sleeves.base import Sleeve, SleeveDisplay


class GapSleeve(Sleeve):
    key = "gap_tansho"
    display = SleeveDisplay(
        label="逆張り単（ぎゃくばりたん）",
        thesis=(
            "市場が見限った（人気薄の）馬を、AIの勝率評価が上回る「過小評価」のときだけ"
            "単勝で買う高配狙いのスリーブ。gap≥5（AI上位なのに人気薄）を未勝利・条件・重賞クラスに限定。"
        ),
        bet_type="単勝1点（逆張り・高配狙い）",
        results_link="/analysis/edge-validation",
    )

    def is_enabled(self) -> bool:
        return gl.read_gap_config().enabled

    def freeze(self, *, per_race_cap: int) -> dict:
        """当日開始時の凍結スナップショット (gap_tansho_scheduler の bankroll/day_cap 凍結と同値)。"""
        cfg = gl.read_gap_config()
        bal = gl.account_balance(cfg)
        day_cap = max(gl.MIN_BET_YEN, int(bal * cfg.day_pct / 100 // 100 * 100))
        return {"bankroll": bal, "day_cap": day_cap, "bet_pct": cfg.bet_pct,
                "day_pct": cfg.day_pct, "per_race_cap": per_race_cap,
                "source": cfg.source}

    def size_race(self, pred_race: dict, snapshot: dict) -> Optional[RaceSizing]:
        rs = gl.size_gap_race(pred_race, balance=snapshot["bankroll"],
                              bet_pct=snapshot["bet_pct"],
                              per_race_cap=snapshot["per_race_cap"])
        if rs is not None:
            for leg in rs.legs:
                leg.sleeve = self.key   # B別建ての帰属タグ (amount/bet_spec には無影響)
        return rs

    def settle_day(self, date_str: str, votes: dict) -> dict:
        """votes (当該スリーブ分にフィルタ済) を実払戻で精算し gap 専用台帳に蓄積。"""
        return gl.settle_gap_day(date_str, votes)

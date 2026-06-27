# -*- coding: utf-8 -*-
"""HonmeiEvSleeve — 本命EV単 を Sleeve 契約に載せる薄いアダプタ (Session 177 / §8-2)。

honmei_ev_live が {config, 残高, サイズ, 台帳} を持つので、ここは委譲するだけ (GapSleeve と同型)。
口座(config/残高/台帳)は gap とは ★完全隔離★。安全機構・投票は Orchestrator が集約。
"""
from __future__ import annotations

from typing import Optional

from ml.strategies import honmei_ev_live as hl
from ml.strategies.bettype_sizing import RaceSizing
from ml.strategies.sleeves.base import Sleeve, SleeveDisplay


class HonmeiEvSleeve(Sleeve):
    key = "honmei_ev"
    display = SleeveDisplay(
        label="本命EV単（ほんめいいーぶぃーたん）",
        thesis=(
            "AIの本命(勝率1位)を、市場がまだ過小評価していて(gap≥3)、期待値が高く(EV≥1.3)、"
            "接戦で勝ち切れる(margin≤60)ときだけ単勝1点で買う本命妙味のスリーブ。"
            "推奨馬券画面の主力プリセット tansho_ippon と同一条件 (現行シミュ Flat ROI 108.3%)。"
        ),
        bet_type="単勝1点（本命・妙味/期待値狙い）",
        results_link="/analysis/honmei-ev-validation",
    )

    def is_enabled(self) -> bool:
        return hl.read_honmei_ev_config().enabled

    def freeze(self, *, per_race_cap: int) -> dict:
        """当日開始時の凍結スナップショット (gap と同値の bankroll/day_cap 凍結)。"""
        cfg = hl.read_honmei_ev_config()
        bal = hl.account_balance(cfg)
        day_cap = max(hl.MIN_BET_YEN, int(bal * cfg.day_pct / 100 // 100 * 100))
        return {"bankroll": bal, "day_cap": day_cap, "bet_pct": cfg.bet_pct,
                "day_pct": cfg.day_pct, "per_race_cap": per_race_cap,
                "source": cfg.source}

    def size_race(self, pred_race: dict, snapshot: dict) -> Optional[RaceSizing]:
        rs = hl.size_honmei_ev_race(pred_race, balance=snapshot["bankroll"],
                                    bet_pct=snapshot["bet_pct"],
                                    per_race_cap=snapshot["per_race_cap"])
        if rs is not None:
            for leg in rs.legs:
                leg.sleeve = self.key   # B別建ての帰属タグ
        return rs

    def settle_day(self, date_str: str, votes: dict) -> dict:
        """votes (当該スリーブ分にフィルタ済) を実払戻で精算し 本命EV単 専用台帳に蓄積。"""
        return hl.settle_honmei_ev_day(date_str, votes)

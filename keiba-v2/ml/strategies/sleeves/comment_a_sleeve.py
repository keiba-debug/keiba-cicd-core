# -*- coding: utf-8 -*-
"""CommentASleeve — コメＡ3点セット を Sleeve 契約に載せる薄いアダプタ (Session 189)。

comment_a_live が {config, 残高, サイズ, 台帳} を持つので、ここは委譲するだけ
(GapSleeve / HonmeiEvSleeve と同型)。口座は gap/honmei と ★完全隔離★。
安全機構・投票は Orchestrator が集約。設計正本 = docs/comment_a_sleeve_design.md。
"""
from __future__ import annotations

from typing import Optional

from ml.strategies import comment_a_live as cl
from ml.strategies.bettype_sizing import RaceSizing
from ml.strategies.sleeves.base import Sleeve, SleeveDisplay


class CommentASleeve(Sleeve):
    key = "comment_a"
    display = SleeveDisplay(
        label="深読み三点（ふかよみさんてん）",
        thesis=(
            "競馬新聞の関係者コメントをAI (ローカルLLM) が行間まで深読みし、高確信で拾った"
            "人気薄「Ａ印」を複勝2:単勝1:ワイド(×ML本命)1 の3点セットで買うスリーブ。"
            "複勝の的中率エッジ(人気マッチ+20pt)が本体で、単勝が配当の天井・ワイドが分散平準化を担当。"
            "オッズと確率の歪みを撃つ既存2本に対し、これは言葉の歪みを撃つ。"
            "モデルEVゲート(R4)通過時は複勝を増額。"
        ),
        bet_type="複勝+単勝+ワイド (3点セット・人気薄Ａ印)",
        results_link="/analysis/comment-marks",
    )

    def is_enabled(self) -> bool:
        cfg = cl.read_comment_a_config()
        if not cfg.enabled:
            return False
        if cl.dd_stopped(cfg):
            # ★ハードDDストップ (ふくだ確定 S189: 初期残高の50%割れ=15万円)★
            import sys
            print(f"[comment_a] ⛔ ハードDDストップ発動中 (残高{cl.account_balance(cfg):,}円 < "
                  f"初期{cfg.initial_bankroll_yen:,}×{cl.DD_STOP_FLOOR_PCT}%) → 投票しない。"
                  f"再開は原因究明のうえ増資/config 変更で", file=sys.stderr)
            return False
        return True

    def freeze(self, *, per_race_cap: int) -> dict:
        """当日開始時の凍結スナップショット (gap/honmei と同値の bankroll/day_cap 凍結)。"""
        cfg = cl.read_comment_a_config()
        bal = cl.account_balance(cfg)
        day_cap = max(cl.MIN_BET_YEN, int(bal * cfg.day_pct / 100 // 100 * 100))
        return {"bankroll": bal, "day_cap": day_cap, "bet_pct": cfg.bet_pct,
                "day_pct": cfg.day_pct, "r4_boost": cfg.r4_boost,
                "per_race_cap": per_race_cap, "source": cfg.source}

    def size_race(self, pred_race: dict, snapshot: dict) -> Optional[RaceSizing]:
        rs = cl.size_comment_a_race(pred_race, balance=snapshot["bankroll"],
                                    bet_pct=snapshot["bet_pct"],
                                    per_race_cap=snapshot["per_race_cap"],
                                    r4_boost=bool(snapshot.get("r4_boost", True)))
        if rs is not None:
            for leg in rs.legs:
                leg.sleeve = self.key   # B別建ての帰属タグ
        return rs

    def settle_day(self, date_str: str, votes: dict) -> dict:
        """votes (当該スリーブ分にフィルタ済) を実払戻で精算し comment-a 専用台帳に蓄積。"""
        return cl.settle_comment_a_day(date_str, votes)

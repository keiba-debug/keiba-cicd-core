#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""当日の回収額 (払戻) 算出 — 日次予算ゲートを「収支 (純損失) ベース」にするための部品。

背景 (ふくだ 2026-06-13 観察):
    自動投票の日次上限ゲートは従来「投票額の単純累計 (voted_yen)」で判定していた。
    これは「入金額 = 最大損失 = その日に賭ける総額の上限」 (Session145) という意図的な
    保守設計だが、 「的中して戻ってきた払戻 (回収額)」を一切考慮しないため、 実際には
    IPAT 残高が残っているのに「日次予算上限」で投票を止めてしまう (グロス過大評価)。

    IPAT は的中レースの払戻を当日中に口座残高へ反映し、 その金で次のレースを買い直せる
    (ふくだ確認済)。 そこで本部品は scheduler が自分で投票した記録 (state["votes"]) の
    うち着順確定済みのレースだけ mykeibadb の確定配当で払戻を計算し合計する。 これを
    voted_yen から引いた net_spent (= 純投資 = 純損失) を日次上限と比較することで、
    「回収できた金額を考慮」する。

    ★安全性は壊れない★: net_spent ベースでも「最大損失 ≤ 入金額」は保たれる。 入金額を
    超えて賭けた分は必ず回収した払戻から出ているため、 純損失の上限は依然として入金額。
    現行グロス上限は単に過剰に保守的だっただけ。

設計原則:
  - フェイルセーフ: DB エラー・結果未確定・配当未取得は「回収 0 (未回収)」扱い。
    回収を ★過大評価しない★ = 上限を緩めすぎない = 安全側 (最悪でも現行グロス挙動に縮退)。
  - 払戻計算は settle_ledger.compute_payout を流用 (単勝/複勝/馬連/ワイド/馬単/三連複/三連単)。
  - read-only。 ledger も DB も書かない。 着順は race JSON → DB フォールバック (確定後 DB が live)。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _legs_from_vote(v: dict) -> list[dict]:
    """1 vote 記録から settle 可能な leg list を取り出す。

    bettype:    v["legs"] = [{bet_type, horses, amount, ...}, ...]
    freebudget: v["legs"] = [{bet_type:"tansho", horses:[umaban], amount}, ...]
    旧 state (legs フィールド無し) は [] を返す = そのレースの回収 0 扱い (安全側)。
    """
    legs = v.get("legs")
    out: list[dict] = []
    if not isinstance(legs, list):
        return out
    for lg in legs:
        if not isinstance(lg, dict):
            continue
        bt = lg.get("bet_type")
        horses = lg.get("horses")
        amount = lg.get("amount")
        if (bt and isinstance(horses, list) and horses
                and isinstance(amount, int) and amount > 0):
            try:
                out.append({"bet_type": bt, "horses": [int(h) for h in horses],
                            "amount": int(amount)})
            except (TypeError, ValueError):
                continue
    return out


def compute_recovery(date_str: str, votes: dict, *,
                     races_dir: Optional[Path] = None) -> dict:
    """votes (= state["votes"]) から当日の確定済み回収額 (払戻合計) を算出する。

    対象: exit_code==0 (投票成功) かつ leg を持つレース。

    Returns:
        {"recovered_yen": int,     # 確定済みレースの払戻合計
         "settled_races": int,     # 着順確定 + 払戻計算できたレース数
         "pending_races": int,     # 未確定/エラーで回収0扱いにしたレース数
         "detail": {race_id: {"status": "settled"|"pending"|"error", "payout": int}}}

    失敗時 (import 不能・全レース未確定) でも recovered_yen=0 を返す (フェイルセーフ)。
    """
    result = {"recovered_yen": 0, "settled_races": 0, "pending_races": 0,
              "detail": {}}

    targets: dict[str, list[dict]] = {}
    for rid, v in (votes or {}).items():
        if not isinstance(v, dict) or v.get("exit_code") != 0:
            continue
        legs = _legs_from_vote(v)
        if legs:
            targets[rid] = legs
    if not targets:
        return result  # 投票実績なし → DB に触らず即返す

    # 重い依存 (DB/settle) は対象がある時だけ遅延 import。 失敗は安全側 (回収0)。
    try:
        from core import config
        from ml import settle_ledger as SL
    except Exception as e:  # noqa: BLE001
        print(f"[day_recovery] import 失敗 → 回収0 (安全側): {e}", file=sys.stderr)
        return result

    if races_dir is None:
        try:
            y, m, d = date_str.split("-")
            races_dir = config.races_dir() / y / m / d
        except Exception as e:  # noqa: BLE001
            print(f"[day_recovery] races_dir 解決失敗 → 回収0: {e}", file=sys.stderr)
            return result

    caches: dict = {}
    total = 0
    for rid, legs in targets.items():
        try:
            fps, num_runners = SL.get_finish_positions(rid, races_dir)
        except Exception as e:  # noqa: BLE001
            print(f"[day_recovery] {rid} 着順取得失敗 → pending 扱い: {e}",
                  file=sys.stderr)
            result["detail"][rid] = {"status": "error", "payout": 0}
            result["pending_races"] += 1
            continue
        if not fps or all(fp == 0 for fp in fps.values()):
            result["detail"][rid] = {"status": "pending", "payout": 0}
            result["pending_races"] += 1
            continue

        race_payout = 0
        for i, leg in enumerate(legs):
            ticket = {"ticket_id": f"{rid}#rec{i}", "bet_type": leg["bet_type"],
                      "formation_type": "single", "total_amount": leg["amount"],
                      "raw_legs": {"horses": leg["horses"]}}
            try:
                r, _status = SL.compute_payout(ticket, fps, num_runners, rid, caches)
            except Exception as e:  # noqa: BLE001
                print(f"[day_recovery] {rid} payout 計算失敗 → 0: {e}", file=sys.stderr)
                continue
            # r is None (的中だが配当未取得/未対応) は回収0扱い = 安全側
            if r is not None:
                race_payout += int(r.get("payout", 0) or 0)
        result["detail"][rid] = {"status": "settled", "payout": race_payout}
        result["settled_races"] += 1
        total += race_payout

    result["recovered_yen"] = total
    return result

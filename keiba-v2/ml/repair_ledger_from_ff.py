#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""5/30 ledger 修復 — FF CSV (実投票正本) + audit JSONL (受付確定) から再構築 (Session 137)

背景 (Session 135-136):
  record_tansho_vote が umaban1 だけ見て全券種を tansho に潰し、 idempotency 衝突で
  過少記録 (11点→3点) + bet_type 乖離 (京都4R 実=馬単→記録=単勝) が起きた。
  Session 136 で記録コードは本治療済 (record_portfolio_votes)。 本スクリプトは
  既に潰れて記録された 5/30 ledger を、 一次記録 (FF CSV) から正本化する。

ソースの信頼順:
  1. FF CSV (C:/TFJV/TXT/FF{date}_*.CSV) = runner が IPAT に送った買い目正本 (race_id/券種/馬番/金額)
  2. audit JSONL (target_clicker/audit_{YYYY-MM}.jsonl) の clicked entry = 受付確定 (race_id/受付番号/件数/合計)
  突合: FF CSV のユニーク買い目を race_id 別に集計し、 audit の (n_bets, total_yen) に一致する集合を採用。

修復方針 (シズネ Session 136: 上書きせず追記):
  - 既存 portfolio は削除せず `superseded_by_repair` フラグ + 理由を付ける
  - 正しい買い目を record_portfolio_votes で新規 portfolio として追記 (notes に reconstruct 明記)
  - LEDGER_REPAIRED event に旧→新の差分を焼き込む (監査証跡)
  - settle/display は superseded portfolio を集計から除外する (別途対応)

Usage:
  python -m ml.repair_ledger_from_ff --date 2026-05-30 --dry-run   # 計画表示のみ
  python -m ml.repair_ledger_from_ff --date 2026-05-30 --apply     # 実書き込み
"""

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.purchase_ledger.writer import (
    LEDGER_DIR, record_portfolio_votes, _load_ledger, _make_event,
    _append_event, _update_index, _now_iso,
)
from ml.utils.atomic_write import write_json_atomic

CODE2NAME = {0: "tansho", 1: "fukusho", 2: "wakuren", 3: "umaren",
             4: "wide", 5: "umatan", 6: "sanrenpuku", 7: "sanrentan"}
# 順序意味あり券種 (馬単/三連単) は買い目順序を保持、 他は正規化(sort)
_ORDER_SENSITIVE = {"umatan", "sanrentan"}


def _jv_txt_dir() -> Path:
    import os
    return Path(os.getenv("JV_DATA_ROOT", "C:/TFJV")) / "TXT"


def _norm_horses(bet_type: str, horses: tuple) -> tuple:
    return tuple(horses) if bet_type in _ORDER_SENSITIVE else tuple(sorted(horses))


def load_ff_bets(date: str) -> dict:
    """FF CSV 群を読み race_id -> Counter[(bet_type, horses_norm, amount)] を返す"""
    date_compact = date.replace("-", "")
    byrace: dict = defaultdict(Counter)
    for f in sorted(glob.glob(str(_jv_txt_dir() / f"FF{date_compact}_*.CSV"))):
        for line in Path(f).read_text(encoding="cp932").splitlines():
            if not line.strip():
                continue
            p = line.split(",")
            try:
                rid = p[0]
                bt = CODE2NAME[int(p[2])]
                horses = tuple([int(p[3])] + [int(x) for x in (p[4], p[5]) if x and x != "0"])
                amt = int(p[6])
            except (ValueError, IndexError, KeyError):
                continue
            byrace[rid][(bt, _norm_horses(bt, horses), amt)] += 1
    return byrace


def load_confirmed_votes(date: str) -> dict:
    """audit JSONL の clicked 確定 entry を race_id -> {receipt, time, n_bets, total} で返す"""
    ym = date[:7]
    path = config.userdata_dir() / "target_clicker" / f"audit_{ym}.jsonl"
    if not path.exists():
        return {}
    out = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if e.get("action") != "clicked" or not e.get("success"):
            continue
        rid = str(e.get("race_id", ""))
        if not rid.startswith(date.replace("-", "")):
            continue
        out[rid] = {
            "receipt_number": e.get("receipt_number"),
            "receipt_time": e.get("receipt_time"),
            "n_bets": e.get("n_bets"),
            "total_yen": e.get("receipt_total_yen") or e.get("total_yen"),
            "clicked_at": e.get("clicked_at"),
        }
    return out


def select_voted_bets(uniq: Counter, n_bets: int, total_yen: int):
    """FF ユニーク買い目から、 受付の (n_bets, total) に一致する集合を選ぶ。

    Returns: (bets:list[(bet_type,horses,amount)], ok:bool, note:str)
    """
    keys = list(uniq.keys())
    # ケース1: ユニーク件数が受付件数に一致し合計も一致 → 全採用 (11点/単一の正常系)
    if len(keys) == n_bets and sum(a for _, _, a in keys) == total_yen:
        return keys, True, "uniq全採用"
    # ケース2: 単一買い (n_bets==1) → 金額が合計に一致する1点を採用 (重複書き込みの曖昧性解消)
    if n_bets == 1:
        cands = [k for k in keys if k[2] == total_yen]
        if len(cands) == 1:
            return cands, True, f"金額一致1点採用 (他{len(keys)-1}点は未投票FF)"
        return cands, False, f"単一だが候補{len(cands)}件で曖昧"
    return keys, False, f"uniq{len(keys)}件 != n_bets{n_bets} (要手動確認)"


def ledger_current_bets(race: dict) -> list:
    """既存 ledger race の (superseded でない) ticket を (bet_type, horses_norm, amount) で返す"""
    out = []
    for pf in race.get("portfolios", []):
        if pf.get("superseded_by_repair"):
            continue
        for t in pf.get("tickets", []):
            bt = t.get("bet_type")
            horses = tuple(t.get("raw_legs", {}).get("horses", []))
            out.append((bt, _norm_horses(bt, horses), t.get("total_amount")))
    return out


def main():
    ap = argparse.ArgumentParser(description="Repair ledger from FF CSV + audit (Session 137)")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    date = args.date
    dry = not args.apply

    ff = load_ff_bets(date)
    confirmed = load_confirmed_votes(date)
    ledger_path = LEDGER_DIR / f"{date}.json"
    ledger = _load_ledger(ledger_path)
    race_by_id = {r["race_id"]: r for r in ledger.get("races", [])}

    plans = []
    for rid, info in sorted(confirmed.items()):
        uniq = ff.get(rid, Counter())
        voted, ok, note = select_voted_bets(uniq, info["n_bets"], info["total_yen"])
        cur = sorted(ledger_current_bets(race_by_id.get(rid, {})))
        want = sorted(voted)
        need_repair = ok and (Counter(cur) != Counter(want))
        plans.append({
            "race_id": rid, "receipt": info["receipt_number"],
            "n_bets": info["n_bets"], "total": info["total_yen"],
            "match_ok": ok, "note": note,
            "current": cur, "want": want, "need_repair": need_repair,
        })

    # 表示
    print(f"\n=== Ledger 修復プラン {date} ({'DRY-RUN' if dry else 'APPLY'}) ===")
    for p in plans:
        flag = "🔧修復要" if p["need_repair"] else ("✓一致" if p["match_ok"] else "⚠手動確認")
        print(f"\n[{flag}] {p['race_id']} 受付{p['receipt']} ({p['n_bets']}点/{p['total']}円) {p['note']}")
        if p["need_repair"] or not p["match_ok"]:
            print(f"   現ledger ({len(p['current'])}点): " +
                  ", ".join(f"{b}{list(h)}:{a}" for b, h, a in p["current"]))
            print(f"   正本FF   ({len(p['want'])}点): " +
                  ", ".join(f"{b}{list(h)}:{a}" for b, h, a in p["want"]))

    repair_targets = [p for p in plans if p["need_repair"]]
    print(f"\n修復対象: {len(repair_targets)} レース / 一致: "
          f"{sum(1 for p in plans if p['match_ok'] and not p['need_repair'])} / "
          f"要手動: {sum(1 for p in plans if not p['match_ok'])}")

    if dry:
        print("\n(dry-run: 書き込みなし。 --apply で実行)")
        return

    # === APPLY ===
    repaired = 0
    for p in repair_targets:
        rid = p["race_id"]
        race = race_by_id.get(rid)
        if race is None:
            continue
        # 旧 portfolio を superseded マーク (削除しない)
        old_snapshot = []
        for pf in race.get("portfolios", []):
            if pf.get("superseded_by_repair"):
                continue
            pf["superseded_by_repair"] = True
            pf["superseded_at"] = _now_iso()
            pf["superseded_reason"] = "Session137 FF CSV正本化: 旧記録は記録バグ(全券種tansho潰し+過少記録)による暫定値"
            old_snapshot.append({"portfolio_id": pf["portfolio_id"],
                                 "tickets": [(t["bet_type"], t["raw_legs"].get("horses"), t["total_amount"])
                                             for t in pf.get("tickets", [])]})
        # LEDGER_REPAIRED event (旧→新 差分を監査証跡に焼く)
        ev = _make_event("LEDGER_REPAIRED", rid, None, None,
                         by="ml.repair_ledger_from_ff",
                         source="FF_CSV+audit",
                         old=old_snapshot,
                         new=[(b, list(h), a) for b, h, a in p["want"]],
                         reason="Session136記録バグ(過少記録3/11+bet_type乖離)の一次記録からの正本化")
        ledger.setdefault("events", []).append(ev)
        _append_event(ev)

    # 旧 superseded マークを先に保存 (record_portfolio_votes が再読込するため)
    write_json_atomic(ledger_path, ledger)

    # 正しい買い目を新規 portfolio として追記
    info_by_id = confirmed
    for p in repair_targets:
        rid = p["race_id"]
        info = info_by_id[rid]
        tickets = [{
            "bet_type": b, "horses": list(h), "amount": a,
            "strategy_name": "manual_cli",
            "pattern_label": "その他",
            "notes": "audit_reconstruct_session137",
        } for b, h, a in p["want"]]
        res = record_portfolio_votes(
            race_id=rid, portfolio_strategy="manual_cli", tickets=tickets,
            receipt_number=info["receipt_number"], receipt_time=info["receipt_time"],
            clicked_at=info["clicked_at"])
        print(f"  {rid}: {res.action} ({len(tickets)}点) {res.portfolio_id}")
        if res.action == "recorded":
            repaired += 1

    print(f"\n修復完了: {repaired} レース正本化。 旧 portfolio は superseded フラグで保全。")


if __name__ == "__main__":
    main()

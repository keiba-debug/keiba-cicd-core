#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ledger v2 writer (Session 129 / Step 1 minimal subset)

設計: 14_LEDGER_SCHEMA.md §1.2, §2, §3, §6, §10.1

公開 API:
  record_tansho_vote(...) -> RecordResult
      単勝 1 点 = 1 portfolio × 1 ticket を ledger に追記。
      idempotency_key で重複検査済。
      SUBMITTED + (receipt あれば) IPAT_CONFIRMED イベントも記録。

  record_vote_failure(...) -> RecordResult
      投票失敗 (timeout/rejected/error) を VOTE_FAILED イベントで記録。
      ticket は作らない (お金が動いていないので)。

ファイル:
  data3/userdata/purchase_ledger/{YYYY-MM-DD}.json
  data3/userdata/purchase_ledger/events_{YYYY-MM}.jsonl  ← イベントは別途 jsonl 保存 (検索性)
  data3/userdata/purchase_ledger/_index.jsonl            ← SHA256 追記台帳
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from ml.purchase_ledger.idempotency import (
    date_from_race_id,
    make_portfolio_idempotency_key,
    make_ticket_idempotency_key,
    race_no_from_race_id,
    venue_code_from_race_id,
)
from ml.utils.atomic_write import write_json_atomic
from ml.utils.jsonl_append import append_jsonl


LEDGER_DIR = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")) \
    / "userdata" / "purchase_ledger"

LEDGER_VERSION = 2


@dataclass
class RecordResult:
    success: bool
    action: str                     # "recorded" / "duplicate" / "error"
    reason: str
    portfolio_id: Optional[str] = None
    ticket_id: Optional[str] = None
    ledger_path: Optional[str] = None


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ledger_path_for(race_id: str) -> Path:
    """race_id から ledger ファイルパスを返す"""
    date = date_from_race_id(race_id)
    if not date:
        raise ValueError(f"invalid race_id (cannot derive date): {race_id}")
    return LEDGER_DIR / f"{date}.json"


def _load_ledger(path: Path) -> dict:
    """既存 ledger を読む。 無ければ空の v2 ledger を返す"""
    if not path.exists():
        return {
            "version": LEDGER_VERSION,
            "date": path.stem,
            "races": [],
            "events": [],
        }
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        # 破損 ledger は事故処理 — 自動修復しない。 ふくだに報告
        raise RuntimeError(f"ledger JSON 破損: {path}: {e}")


def _find_or_create_race(ledger: dict, race_id: str) -> dict:
    """ledger.races[] から race_id を探す。 無ければ新規追加して返す"""
    for race in ledger["races"]:
        if race.get("race_id") == race_id:
            return race
    new_race = {
        "race_id": race_id,
        "state": "SUBMITTED",
        "portfolios": [],
    }
    ledger["races"].append(new_race)
    return new_race


def _assign_portfolio_seq(race: dict) -> str:
    """同一 race 内で未使用の portfolio seq (A/B/C/...) を返す"""
    used = {
        (p.get("portfolio_id") or "").split("-")[-1]
        for p in race.get("portfolios", [])
    }
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if c not in used:
            return c
    raise RuntimeError(f"portfolio seq A-Z 全使用済: race_id={race.get('race_id')}")


def _make_portfolio_id(race_id: str, seq: str) -> str:
    """pf-{YYYYMMDD}-{venue}{race_no}-{seq} (14 §3.1)"""
    date_compact = race_id[0:8]
    venue = venue_code_from_race_id(race_id)
    race_no = race_no_from_race_id(race_id)
    return f"pf-{date_compact}-{venue}{race_no}-{seq}"


def _find_duplicate_portfolio(race: dict, idempotency_key: str) -> Optional[dict]:
    for p in race.get("portfolios", []):
        if p.get("idempotency_key") == idempotency_key:
            return p
    return None


def _update_index(ledger_path: Path, ledger: dict) -> None:
    """SHA256 追記台帳 (_index.jsonl) を更新 (14 §7.2)"""
    try:
        content = json.dumps(ledger, ensure_ascii=False, sort_keys=True)
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        ticket_count = sum(
            len(p.get("tickets", []))
            for r in ledger.get("races", [])
            for p in r.get("portfolios", [])
        )
        total_amount = sum(
            t.get("total_amount", 0)
            for r in ledger.get("races", [])
            for p in r.get("portfolios", [])
            for t in p.get("tickets", [])
        )
        portfolio_count = sum(
            len(r.get("portfolios", []))
            for r in ledger.get("races", [])
        )
        entry = {
            "date": ledger.get("date"),
            "sha256": sha256,
            "updated_at": _now_iso(),
            "ticket_count": ticket_count,
            "total_amount": total_amount,
            "portfolio_count": portfolio_count,
        }
        append_jsonl(LEDGER_DIR / "_index.jsonl", entry)
    except Exception as e:
        print(f"[ledger] _index.jsonl 更新失敗 (本体は保存済): {e}", file=sys.stderr)


def _append_event(event: dict) -> None:
    """events_{YYYY-MM}.jsonl にイベントを追記 (14 §6, §8 events 肥大化対策)"""
    now = datetime.now()
    month_path = LEDGER_DIR / f"events_{now.strftime('%Y-%m')}.jsonl"
    append_jsonl(month_path, event)


def _make_event(event_type: str, race_id: str, portfolio_id: Optional[str],
                ticket_id: Optional[str], **payload) -> dict:
    """ledger event を構築 (14 §6)"""
    return {
        "id": f"evt-{uuid.uuid4().hex[:12]}",
        "at": _now_iso(),
        "type": event_type,
        "race_id": race_id,
        "portfolio_id": portfolio_id,
        "ticket_id": ticket_id,
        "payload": payload,
    }


def record_tansho_vote(
    *,
    race_id: str,
    umaban: int,
    amount: int,
    strategy_name: str,
    portfolio_strategy: Optional[str] = None,
    pattern_label: str = "その他",
    notes: str = "",
    ev_at_decision: Optional[float] = None,
    receipt_number: Optional[str] = None,
    receipt_time: Optional[str] = None,
    clicked_at: Optional[str] = None,
) -> RecordResult:
    """単勝 1 点投票成立を ledger に記録 (Step 1 minimal subset)。

    Args:
        race_id: 16 桁 race_id
        umaban: 馬番 (1-18)
        amount: 金額 (円)
        strategy_name: 戦略ラベル (例: "selective_v3_emerging_w")
        portfolio_strategy: portfolio_strategy (省略時は strategy_name と同じ)
        pattern_label: 後付け分類用ラベル (省略時 "その他")
        notes: 自由欄
        ev_at_decision: 判断時点 EV (省略可)
        receipt_number: IPAT 受付番号 (4 桁) — あれば IPAT_CONFIRMED event も記録
        receipt_time: IPAT 受付時刻
        clicked_at: click 時刻 ISO8601 — submitted_at として記録

    Returns:
        RecordResult。 同一 idempotency_key の portfolio が既存なら
        action="duplicate" + 既存 portfolio_id を返す (新規作らない)。
    """
    if not isinstance(race_id, str) or len(race_id) != 16:
        return RecordResult(success=False, action="error",
                             reason=f"invalid race_id: {race_id!r}")
    if not isinstance(umaban, int) or umaban <= 0:
        return RecordResult(success=False, action="error",
                             reason=f"invalid umaban: {umaban!r}")
    if not isinstance(amount, int) or amount <= 0:
        return RecordResult(success=False, action="error",
                             reason=f"invalid amount: {amount!r}")

    p_strategy = portfolio_strategy or strategy_name
    bet_type = "tansho"
    raw_legs = {"horses": [umaban]}
    now = _now_iso()

    # ticket 骨格 (idempotency 計算用)
    ticket_skel = {
        "bet_type": bet_type,
        "raw_legs": raw_legs,
        "total_amount": amount,
    }
    portfolio_idempotency = make_portfolio_idempotency_key(
        race_id, p_strategy, [ticket_skel],
    )
    ticket_idempotency = make_ticket_idempotency_key(
        race_id, bet_type, raw_legs, strategy_name,
    )

    ledger_path = _ledger_path_for(race_id)

    try:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger = _load_ledger(ledger_path)
    except Exception as e:
        return RecordResult(success=False, action="error",
                             reason=f"ledger load failed: {e}")

    race = _find_or_create_race(ledger, race_id)

    # 重複検査 (Session 128 のような同じ投票を 2 回 click した場合)
    dup = _find_duplicate_portfolio(race, portfolio_idempotency)
    if dup is not None:
        return RecordResult(
            success=True, action="duplicate",
            reason="既存 portfolio と idempotency 一致 — スキップ",
            portfolio_id=dup["portfolio_id"],
            ticket_id=(dup["tickets"][0]["ticket_id"] if dup.get("tickets") else None),
            ledger_path=str(ledger_path),
        )

    # 新規 portfolio + ticket
    seq = _assign_portfolio_seq(race)
    portfolio_id = _make_portfolio_id(race_id, seq)
    ticket_id = f"{portfolio_id}#t1"

    ticket = {
        "ticket_id": ticket_id,
        "strategy_name": strategy_name,
        "formation_type": "single",
        "pattern_label": pattern_label,
        "raw_legs": raw_legs,
        "notes": notes,
        "bet_type": bet_type,
        "total_amount": amount,
        "idempotency_key": ticket_idempotency,
        "created_at": now,
        "submitted_at": clicked_at or now,
    }
    if ev_at_decision is not None:
        ticket["ev_at_decision"] = ev_at_decision
    if receipt_number:
        ticket["ipat_confirmed_at"] = now
        ticket["ipat_receipt_number"] = receipt_number
        if receipt_time:
            ticket["ipat_receipt_time"] = receipt_time

    portfolio = {
        "portfolio_id": portfolio_id,
        "portfolio_strategy": p_strategy,
        "created_at": now,
        "tickets": [ticket],
        "portfolio_total": amount,
        "idempotency_key": portfolio_idempotency,
    }
    race["portfolios"].append(portfolio)

    # イベント追記 (本体 events[] + jsonl 両方)
    events_to_add = []
    events_to_add.append(_make_event(
        "FF_WRITTEN", race_id, portfolio_id, ticket_id,
        count=1, amount=amount,
    ))
    events_to_add.append(_make_event(
        "TARGET_IMPORTED", race_id, portfolio_id, ticket_id,
        by="target_clicker",
    ))
    events_to_add.append(_make_event(
        "APPROVED", race_id, portfolio_id, ticket_id,
        by="target_clicker.auto_vote",
    ))
    if receipt_number:
        events_to_add.append(_make_event(
            "IPAT_CONFIRMED", race_id, portfolio_id, ticket_id,
            by="target_clicker.auto_vote",
            receipt_number=receipt_number,
            receipt_time=receipt_time,
        ))
    for ev in events_to_add:
        ledger["events"].append(ev)
        _append_event(ev)

    ok = write_json_atomic(ledger_path, ledger)
    if not ok:
        return RecordResult(success=False, action="error",
                             reason="atomic write failed", portfolio_id=portfolio_id)

    _update_index(ledger_path, ledger)

    return RecordResult(
        success=True, action="recorded",
        reason="portfolio + ticket 追記成功",
        portfolio_id=portfolio_id, ticket_id=ticket_id,
        ledger_path=str(ledger_path),
    )


def record_vote_failure(
    *,
    race_id: str,
    failure_action: str,                # "timeout" / "rejected" / "error"
    reason: str,
    attempted_amount: Optional[int] = None,
    attempted_umaban: Optional[int] = None,
    strategy_name: Optional[str] = None,
) -> RecordResult:
    """投票失敗を VOTE_FAILED イベントで記録 (ticket は作らない)。

    race_id が分からない (FF 送信前の dialog 検出失敗等) ケースもあるので、
    その場合は events_{YYYY-MM}.jsonl のみ追記 (本体 ledger は触らない)。
    """
    return _record_failure_event(
        event_type="VOTE_FAILED",
        race_id=race_id,
        payload={
            "failure_action": failure_action,
            "reason": reason,
            "attempted_amount": attempted_amount,
            "attempted_umaban": attempted_umaban,
            "strategy_name": strategy_name,
            "by": "target_clicker.auto_vote",
        },
    )


def record_ipat_start_failure(
    *,
    race_ids: list[str],
    reason: str,
    strategies_tried: Optional[list[str]] = None,
    attempted_total_yen: Optional[int] = None,
) -> RecordResult:
    """IPAT 投票起動失敗 (menu_runner.step3_start_ipat の全戦略失敗) を記録 (Session 130 / シズネ N)。

    投票ダイアログまで到達できなかった = お金は動いていない。
    1 回の runner.py 実行で複数 race_id を投票しようとしていた場合、 全 race_id に対して
    IPAT_START_FAILED event を残す (どの bets 群が未投票になったか分かるように)。

    ticket は作らない。
    """
    if not race_ids:
        # race_id 不明でも events jsonl だけは残す
        return _record_failure_event(
            event_type="IPAT_START_FAILED",
            race_id="",
            payload={
                "reason": reason,
                "strategies_tried": strategies_tried or [],
                "attempted_total_yen": attempted_total_yen,
                "by": "target_clicker.menu_runner",
            },
        )
    last_result: Optional[RecordResult] = None
    for rid in race_ids:
        last_result = _record_failure_event(
            event_type="IPAT_START_FAILED",
            race_id=rid,
            payload={
                "reason": reason,
                "strategies_tried": strategies_tried or [],
                "attempted_total_yen": attempted_total_yen,
                "by": "target_clicker.menu_runner",
            },
        )
    return last_result or RecordResult(success=True, action="recorded",
                                        reason="IPAT_START_FAILED recorded")


def record_target_save_failure(
    *,
    race_ids: list[str],
    reason: str,
    receipt_numbers: Optional[list[str]] = None,
    error_type: Optional[str] = None,
) -> RecordResult:
    """TARGET 買い目データ保存失敗を記録 (Session 130 / シズネ M)。

    重要: IPAT 投票自体は成立済 (受付番号取得済) = JRA 側でお金は動いている。
    TARGET 側の「買い目データ」 への保存だけが失敗した状態 = TARGET 履歴と
    IPAT 履歴が乖離する可能性 = ふくだに手動操作 (F10 + はい) を求める必要がある。

    rollback は不可能 (IPAT は受付済)。 代わりに ledger に TARGET_SAVE_FAILED
    event を残し、 ふくだ手動対応の要否を明示する。
    """
    last_result: Optional[RecordResult] = None
    receipts = receipt_numbers or []
    if not race_ids:
        return _record_failure_event(
            event_type="TARGET_SAVE_FAILED",
            race_id="",
            payload={
                "reason": reason,
                "error_type": error_type,
                "receipt_numbers": receipts,
                "ipat_already_committed": True,
                "manual_action_required": "TARGET ウィンドウで F10 + 「はい」 を手動押下、 または無視 (TARGET 履歴のみ未保存)",
                "by": "target_clicker.menu_runner.finalize_save_to_target",
            },
        )
    for rid in race_ids:
        last_result = _record_failure_event(
            event_type="TARGET_SAVE_FAILED",
            race_id=rid,
            payload={
                "reason": reason,
                "error_type": error_type,
                "receipt_numbers": receipts,
                "ipat_already_committed": True,
                "manual_action_required": "TARGET ウィンドウで F10 + 「はい」 を手動押下、 または無視",
                "by": "target_clicker.menu_runner.finalize_save_to_target",
            },
        )
    return last_result or RecordResult(success=True, action="recorded",
                                        reason="TARGET_SAVE_FAILED recorded")


def record_ipat_session_expired_postvote(
    *,
    race_id: str,
    detected_phase: str,                  # "vote_dialog_timeout" / "result_dialog_timeout" / "explicit_error_dialog"
    detected_dialog_title: Optional[str] = None,
    matched_keyword: Optional[str] = None,
    vote_already_clicked: bool = False,   # True なら投票 click は実行済 (受付不明 = manual_review)
    pattern_source: str = "default",
) -> RecordResult:
    """IPAT セッション切れの事後検知を記録 (Session 132 / Phase 4-C-full)

    18 §1.3 Phase 4-C-full の検知 3 パターン:
      ① vote_dialog_timeout:   投票内容確認 dialog が出ない → セッション切れ可能性
      ② result_dialog_timeout: 投票 click 後「投票終了」 が出ない → 投票成立不明 (manual_review)
      ③ explicit_error_dialog: 「再ログイン」 等のエラーダイアログ検出

    Args:
        detected_phase: 上記 3 種のいずれか
        vote_already_clicked: True なら投票ボタンは押した = 受付状態不明 = ふくだ手動照合必須
        pattern_source: detect_session_expired_dialog の pattern_source ("default"/"file")

    後続:
        record_ipat_session_recovered() or record_ipat_session_recovery_failed() で
        復旧結果も記録する。
    """
    return _record_failure_event(
        event_type="IPAT_SESSION_EXPIRED_POSTVOTE",
        race_id=race_id,
        payload={
            "detected_phase": detected_phase,
            "detected_dialog_title": detected_dialog_title,
            "matched_keyword": matched_keyword,
            "vote_already_clicked": vote_already_clicked,
            "manual_review_required": vote_already_clicked,
            "pattern_source": pattern_source,
            "by": "target_clicker.auto_vote (session_expired hook)",
        },
    )


def record_ipat_session_recovered(
    *,
    race_id: str,
    elapsed_sec: float,
    steps_completed: list[str],
) -> RecordResult:
    """IPAT セッション復旧成功を記録 (Session 132 / Phase 4-C-full)

    `recover_ipat_session()` が action="recovered" を返したときに呼ぶ。
    投票継続が許可される状態を表す。
    """
    return _record_failure_event(
        event_type="IPAT_SESSION_RECOVERED",
        race_id=race_id,
        payload={
            "elapsed_sec": round(elapsed_sec, 2),
            "steps_completed": list(steps_completed),
            "by": "target_clicker.launcher.recover_ipat_session",
        },
    )


def record_ipat_session_recovery_failed(
    *,
    race_id: str,
    failure_action: str,                  # "manual_required" / "timeout" / "error"
    reason: str,
    elapsed_sec: Optional[float] = None,
    steps_completed: Optional[list[str]] = None,
) -> RecordResult:
    """IPAT セッション復旧失敗を記録 (Session 132 / Phase 4-C-full)

    `recover_ipat_session()` が success=False を返したときに呼ぶ。
    呼び出し側 (runner.py) は残りレースの投票を abort する想定。
    """
    return _record_failure_event(
        event_type="IPAT_SESSION_RECOVERY_FAILED",
        race_id=race_id,
        payload={
            "failure_action": failure_action,
            "reason": reason,
            "elapsed_sec": round(elapsed_sec, 2) if elapsed_sec is not None else None,
            "steps_completed": list(steps_completed or []),
            "manual_action_required": (
                "TARGET ウィンドウから手動で IPAT 投票を再起動して暗証番号を入力してください"
            ),
            "by": "target_clicker.launcher.recover_ipat_session",
        },
    )


def _record_failure_event(
    *,
    event_type: str,
    race_id: str,
    payload: dict,
) -> RecordResult:
    """失敗系 event 共通記録ヘルパ (ticket なし、 events_jsonl + ledger.events[] 両方)。

    race_id が 16 桁有効なら ledger 本体にも追記、 不明なら jsonl のみ。
    """
    now = _now_iso()
    event = {
        "id": f"evt-{uuid.uuid4().hex[:12]}",
        "at": now,
        "type": event_type,
        "race_id": race_id or None,
        "portfolio_id": None,
        "ticket_id": None,
        "payload": payload,
    }
    _append_event(event)
    if race_id and len(race_id) == 16:
        try:
            ledger_path = _ledger_path_for(race_id)
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger = _load_ledger(ledger_path)
            ledger.setdefault("events", []).append(event)
            ok = write_json_atomic(ledger_path, ledger)
            if ok:
                _update_index(ledger_path, ledger)
        except Exception as e:
            print(f"[ledger] {event_type} 記録失敗 (jsonl は記録済): {e}",
                  file=sys.stderr)
    return RecordResult(
        success=True, action="recorded",
        reason=f"{event_type} recorded",
    )

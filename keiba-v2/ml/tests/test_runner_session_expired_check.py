#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""runner._check_recent_session_expired_events のテスト (Session 133)

シズネ Session 132 レビュー 🔴-1 修正 B 実装の単体テスト。

対象:
  - runner._check_recent_session_expired_events()
  - runner.parse_args() で --ignore-recent-session-expired / --session-expired-window-min

方針:
  - tmp_path を KEIBA_DATA_ROOT に差し替えて events_{YYYY-MM}.jsonl を構築。
  - now 引数で時刻を固定、 cutoff 境界の前後を検証。
  - 実 ledger 書込み (writer.py) には依存しない (生 JSON Lines を直書き)。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_runner_session_expired_check.py -v
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.target_clicker import runner as runner_mod
from ml.target_clicker.runner import (
    _check_recent_session_expired_events,
    parse_args,
)


# =====================================================================
# Fixture: tmp_path を KEIBA_DATA_ROOT にして events_jsonl を構築
# =====================================================================

@pytest.fixture
def tmp_ledger_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KEIBA_DATA_ROOT", str(tmp_path))
    d = tmp_path / "userdata" / "purchase_ledger"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_event(jsonl_path: Path, event: dict) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _make_event(at: datetime,
                event_type: str = "IPAT_SESSION_EXPIRED_POSTVOTE",
                race_id: str = "2026053108010101",
                vote_already_clicked: bool = False,
                detected_phase: str = "vote_dialog_timeout") -> dict:
    return {
        "id": f"evt-test-{at.isoformat()}",
        "at": at.isoformat(timespec="seconds"),
        "type": event_type,
        "race_id": race_id,
        "portfolio_id": None,
        "ticket_id": None,
        "payload": {
            "detected_phase": detected_phase,
            "vote_already_clicked": vote_already_clicked,
        },
    }


# =====================================================================
# _check_recent_session_expired_events: 検出ロジック
# =====================================================================

class TestCheckRecentSessionExpired:

    def test_no_ledger_dir_returns_empty(self, tmp_path, monkeypatch):
        """ledger ディレクトリ不在でも例外を出さず空 list"""
        monkeypatch.setenv("KEIBA_DATA_ROOT", str(tmp_path / "nonexistent"))
        result = _check_recent_session_expired_events(now=datetime(2026, 5, 31, 10, 0))
        assert result == []

    def test_no_jsonl_returns_empty(self, tmp_ledger_dir):
        """jsonl 不在でも空 list"""
        result = _check_recent_session_expired_events(now=datetime(2026, 5, 31, 10, 0))
        assert result == []

    def test_single_recent_event_detected(self, tmp_ledger_dir):
        """1h 以内 1 件 → 検出される"""
        now = datetime(2026, 5, 31, 10, 0)
        ev = _make_event(at=now - timedelta(minutes=30))
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", ev)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 1
        assert result[0]["type"] == "IPAT_SESSION_EXPIRED_POSTVOTE"

    def test_old_event_not_detected(self, tmp_ledger_dir):
        """1h より古い → 検出されない"""
        now = datetime(2026, 5, 31, 10, 0)
        ev = _make_event(at=now - timedelta(minutes=90))
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", ev)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert result == []

    def test_window_boundary_inclusive(self, tmp_ledger_dir):
        """境界 (= now - window_min) は inclusive で検出される"""
        now = datetime(2026, 5, 31, 10, 0)
        ev = _make_event(at=now - timedelta(minutes=60))
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", ev)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 1

    def test_multiple_events_sorted_newest_first(self, tmp_ledger_dir):
        """複数件は新しい順にソートされる"""
        now = datetime(2026, 5, 31, 10, 0)
        events = [
            _make_event(at=now - timedelta(minutes=50)),
            _make_event(at=now - timedelta(minutes=10)),
            _make_event(at=now - timedelta(minutes=30)),
        ]
        for ev in events:
            _write_event(tmp_ledger_dir / "events_2026-05.jsonl", ev)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 3
        # 新しい順 (-10 minutes が最初)
        ats = [datetime.fromisoformat(e["at"]) for e in result]
        assert ats[0] > ats[1] > ats[2]

    def test_other_event_types_ignored(self, tmp_ledger_dir):
        """他の type (VOTE_FAILED 等) は無視"""
        now = datetime(2026, 5, 31, 10, 0)
        events = [
            _make_event(at=now - timedelta(minutes=10), event_type="VOTE_FAILED"),
            _make_event(at=now - timedelta(minutes=10), event_type="IPAT_SESSION_RECOVERED"),
            _make_event(at=now - timedelta(minutes=10),
                        event_type="IPAT_SESSION_EXPIRED_POSTVOTE"),  # これだけ拾う
        ]
        for ev in events:
            _write_event(tmp_ledger_dir / "events_2026-05.jsonl", ev)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 1
        assert result[0]["type"] == "IPAT_SESSION_EXPIRED_POSTVOTE"

    def test_broken_json_line_skipped(self, tmp_ledger_dir):
        """JSON parse 失敗行は skip、 残りは正常に処理"""
        now = datetime(2026, 5, 31, 10, 0)
        jsonl = tmp_ledger_dir / "events_2026-05.jsonl"
        # 1 行目: 破損
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write("{ this is not valid json\n")
        # 2 行目: 正常
        _write_event(jsonl, _make_event(at=now - timedelta(minutes=10)))
        # 3 行目: 空行
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write("\n")

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 1

    def test_event_without_at_field_skipped(self, tmp_ledger_dir):
        """at field 不在の event は skip"""
        now = datetime(2026, 5, 31, 10, 0)
        bad_event = {
            "id": "evt-no-at",
            "type": "IPAT_SESSION_EXPIRED_POSTVOTE",
            "race_id": "2026053108010101",
            "payload": {},
        }
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", bad_event)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert result == []

    def test_event_with_invalid_at_skipped(self, tmp_ledger_dir):
        """at field 不正フォーマットは skip"""
        now = datetime(2026, 5, 31, 10, 0)
        bad_event = {
            "id": "evt-bad-at",
            "at": "not-a-datetime",
            "type": "IPAT_SESSION_EXPIRED_POSTVOTE",
            "race_id": "2026053108010101",
            "payload": {},
        }
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", bad_event)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert result == []

    def test_month_boundary_reads_previous_month(self, tmp_ledger_dir):
        """月初 0 時付近、 前月の jsonl も読まれる"""
        # 6/1 00:30 — 1h 窓 = 5/31 23:30 まで遡る
        now = datetime(2026, 6, 1, 0, 30)
        prev = _make_event(at=datetime(2026, 5, 31, 23, 45))  # 前月 jsonl 行き
        cur = _make_event(at=datetime(2026, 6, 1, 0, 15))     # 現月 jsonl 行き
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", prev)
        _write_event(tmp_ledger_dir / "events_2026-06.jsonl", cur)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 2
        types = [e["type"] for e in result]
        assert all(t == "IPAT_SESSION_EXPIRED_POSTVOTE" for t in types)

    def test_payload_preserved_in_result(self, tmp_ledger_dir):
        """payload (vote_already_clicked / detected_phase) が結果に残る"""
        now = datetime(2026, 5, 31, 10, 0)
        ev = _make_event(
            at=now - timedelta(minutes=10),
            vote_already_clicked=True,
            detected_phase="result_dialog_timeout",
        )
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", ev)

        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 1
        payload = result[0].get("payload", {})
        assert payload.get("vote_already_clicked") is True
        assert payload.get("detected_phase") == "result_dialog_timeout"

    def test_custom_window_minutes(self, tmp_ledger_dir):
        """window_minutes パラメータが効く (10 分窓では 30 分前 event は拾わない)"""
        now = datetime(2026, 5, 31, 10, 0)
        ev = _make_event(at=now - timedelta(minutes=30))
        _write_event(tmp_ledger_dir / "events_2026-05.jsonl", ev)

        # 10 分窓 → 30 分前は範囲外
        result = _check_recent_session_expired_events(window_minutes=10, now=now)
        assert result == []
        # 60 分窓 → 範囲内
        result = _check_recent_session_expired_events(window_minutes=60, now=now)
        assert len(result) == 1


# =====================================================================
# parse_args: 新フラグの default / 指定動作
# =====================================================================

class TestParseArgs:

    def test_ignore_recent_session_expired_default_false(self, monkeypatch):
        """--ignore-recent-session-expired のデフォルトは False"""
        monkeypatch.setattr(sys, "argv", [
            "runner",
            "--bet", "2026053108010101:tansho:5:100",
        ])
        args = parse_args()
        assert args.ignore_recent_session_expired is False

    def test_ignore_recent_session_expired_true_when_specified(self, monkeypatch):
        """指定で True"""
        monkeypatch.setattr(sys, "argv", [
            "runner",
            "--bet", "2026053108010101:tansho:5:100",
            "--ignore-recent-session-expired",
        ])
        args = parse_args()
        assert args.ignore_recent_session_expired is True

    def test_session_expired_window_min_default_60(self, monkeypatch):
        """--session-expired-window-min のデフォルトは 60"""
        monkeypatch.setattr(sys, "argv", [
            "runner",
            "--bet", "2026053108010101:tansho:5:100",
        ])
        args = parse_args()
        assert args.session_expired_window_min == 60

    def test_session_expired_window_min_custom(self, monkeypatch):
        """--session-expired-window-min カスタム値"""
        monkeypatch.setattr(sys, "argv", [
            "runner",
            "--bet", "2026053108010101:tansho:5:100",
            "--session-expired-window-min", "30",
        ])
        args = parse_args()
        assert args.session_expired_window_min == 30

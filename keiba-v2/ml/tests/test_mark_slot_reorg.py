# -*- coding: utf-8 -*-
"""印スロット再編 (docs/auto-purchase/26) + AI評価 遡及 backfill のテスト。

- AI評価のデフォルト書込み先が markSet=2 (旧6) になったこと。
- markSet=2 への round-trip / markSet=1 (手動) 拒否は維持。
- backfill: 当日以降 (>=cutoff) ガード / 過去日の遡及書込み (markSet=2) / dry-run。

env 隔離: JV_DATA_ROOT (DAT 書込み先) と KEIBA_DATA_ROOT (predictions/audit) を tmp に。
本番 TFJV / data3 は一切触らない。
"""

import json

import pytest

from ml.ai_marks import dat_writer
import ml.features.my_marks as mm
from ml.ai_marks.write_ai_marks import process_date
from ml.ai_marks.backfill_ai_marks import run_backfill
from datetime import date


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """JV_DATA_ROOT (DAT) と KEIBA_DATA_ROOT (predictions/audit) を tmp に逃がす。"""
    jv = tmp_path / "jv"
    data = tmp_path / "data3"
    monkeypatch.setenv("JV_DATA_ROOT", str(jv))
    monkeypatch.setenv("KEIBA_DATA_ROOT", str(data))
    return jv, data


def _race(rid, n=8):
    """composite が明確に降順になる entries (assign が撃ちなしにならない)。"""
    entries = []
    for i in range(1, n + 1):
        entries.append({
            "umaban": i,
            "pred_proba_w_cal": round(0.55 - i * 0.04, 4),
            "pred_proba_p": round(0.80 - i * 0.05, 4),
            "ar_deviation": 62 - i * 3,
            "horse_name": f"テスト{i}",
        })
    return {"race_id": rid, "venue_name": "京都",
            "race_number": int(rid[-2:]), "entries": entries}


def _write_preds(data_root, date_str, races):
    y, m, d = date_str.split("-")
    p = data_root / "races" / y / m / d / "predictions.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"races": races, "vb_refreshed_at": None}), encoding="utf-8")
    return p


# --- 1. リナンバー: デフォルト書込み先が markSet=2 ---

def test_default_slot_is_2(sandbox):
    jv, _ = sandbox
    assert dat_writer._MARK_SLOT_AI == 2
    rid = "2026053108030101"          # 京都3回1日目1R
    n = dat_writer.write_ai_marks_to_dat(rid, {8: "◎"})   # mark_set 省略=既定2
    assert n == 1
    marks = mm.load_my_marks(rid, mark_set=2)
    assert marks[8].mark_symbol == "◎"
    assert (jv / "MY_DATA" / "UmaMark2").exists()
    # markSet=6 (旧スロット) には書かれていない
    assert not (jv / "MY_DATA" / "UmaMark6").exists()


def test_step2_roundtrip_slot2(sandbox):
    rid = "2026053108030101"
    marks = {8: "◎", 3: "○", 5: "▲", 1: "△", 9: "Ⅲ", 12: "穴"}
    n = dat_writer.write_ai_marks_to_dat(rid, marks, mark_set=2)
    assert n == 6
    got = mm.load_my_marks(rid, mark_set=2)
    for uma, sym in marks.items():
        assert got[uma].mark_symbol == sym


def test_slot1_still_rejected(sandbox):
    with pytest.raises(ValueError, match="手動印専用"):
        dat_writer.write_ai_marks_to_dat("2026053108030101", {8: "◎"}, mark_set=1)


# --- 2. process_date: apply で markSet=2 に書く / dry は書かない ---

def test_process_date_apply_writes_slot2(sandbox):
    jv, data = sandbox
    rid = "2026053108030101"
    _write_preds(data, "2026-05-31", [_race(rid)])
    res = process_date("2026-05-31", step=2, apply=True, mark_set=2, verbose=False)
    assert res["ok"] and res["marked"] == 1 and res["written"] >= 1
    got = mm.load_my_marks(rid, mark_set=2)
    assert got[1].mark_symbol == "◎"           # 1番が composite 最上位 → ◎


def test_process_date_dry_no_write(sandbox):
    jv, data = sandbox
    rid = "2026053108030101"
    _write_preds(data, "2026-05-31", [_race(rid)])
    res = process_date("2026-05-31", step=2, apply=False, mark_set=2, verbose=False)
    assert res["ok"] and res["written"] == 0
    assert not (jv / "MY_DATA" / "UmaMark2").exists()   # DAT 未作成


def test_process_date_no_predictions(sandbox):
    res = process_date("2099-01-01", apply=False, verbose=False)
    assert res["ok"] is False and res["reason"] == "no_predictions"


# --- 3. backfill: 当日以降ガード / 過去日遡及 ---

def test_backfill_guard_skips_cutoff_and_future(sandbox):
    jv, data = sandbox
    rid = "2026060608030101"
    _write_preds(data, "2026-06-06", [_race(rid)])   # predictions はあるが…
    res = run_backfill(date(2026, 6, 6), date(2026, 6, 6),
                       cutoff=date(2026, 6, 6), step=2, apply=True, mark_set=2)
    assert res["days_guarded"] == 1            # 当日(>=cutoff)はガード
    assert res["days_processed"] == 0 and res["written"] == 0
    assert not (jv / "MY_DATA").exists()       # 1頭も書いていない


def test_backfill_processes_past(sandbox):
    jv, data = sandbox
    rid = "2026053108030101"
    _write_preds(data, "2026-05-31", [_race(rid)])
    res = run_backfill(date(2026, 5, 31), date(2026, 5, 31),
                       cutoff=date(2026, 6, 6), step=2, apply=True, mark_set=2)
    assert res["days_processed"] == 1 and res["written"] >= 1
    got = mm.load_my_marks(rid, mark_set=2)
    assert got[1].mark_symbol == "◎"
    assert (jv / "MY_DATA" / "UmaMark2").exists()


def test_backfill_dry_run_no_write(sandbox):
    jv, data = sandbox
    rid = "2026053108030101"
    _write_preds(data, "2026-05-31", [_race(rid)])
    res = run_backfill(date(2026, 5, 31), date(2026, 5, 31),
                       cutoff=date(2026, 6, 6), step=2, apply=False, mark_set=2)
    assert res["days_processed"] == 1 and res["written"] == 0
    assert not (jv / "MY_DATA").exists()


def test_backfill_allow_today_override(sandbox):
    """--allow-today 相当: ガードを外すと当日も書く (非推奨だが動作確認)。"""
    jv, data = sandbox
    rid = "2026060608030101"
    _write_preds(data, "2026-06-06", [_race(rid)])
    res = run_backfill(date(2026, 6, 6), date(2026, 6, 6),
                       cutoff=date(2026, 6, 6), step=2, apply=True, mark_set=2,
                       allow_today=True)
    assert res["days_guarded"] == 0 and res["days_processed"] == 1 and res["written"] >= 1

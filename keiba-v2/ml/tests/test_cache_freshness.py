# -*- coding: utf-8 -*-
"""ml.cache_freshness のユニットテスト（Session 152）

合成キャッシュで鮮度判定ロジックを検証。本番 JSON には触れない。
"""

from ml.cache_freshness import (
    check_freshness,
    format_status,
    get_history_max_date,
    get_index_max_date,
    _days_between,
)

# 各馬の走歴は日付昇順ソート済み（build_horse_history の不変条件）
HISTORY = {
    "k1": [{"race_date": "2026-05-01"}, {"race_date": "2026-06-07"}],
    "k2": [{"race_date": "2026-03-01"}],
    "k3": [],  # 出走なし馬（末尾参照を踏まない）
}
INDEX = {
    "2026-01-04": ["r1"],
    "2026-06-07": ["r2", "r3"],
    "2026-05-31": ["r4"],
}


def test_index_max_date():
    assert get_index_max_date(INDEX) == "2026-06-07"


def test_index_max_date_empty():
    assert get_index_max_date({}) is None


def test_history_max_date_uses_last_run():
    # 各馬の末尾の最大 = k1 の 2026-06-07（k2 の末尾 3/01 より新しい）
    assert get_history_max_date(HISTORY) == "2026-06-07"


def test_history_max_date_empty():
    assert get_history_max_date({}) is None


def test_days_between():
    assert _days_between("2026-06-01", "2026-06-15") == 14
    assert _days_between("2026-06-07", "2026-06-07") == 0


def test_fresh_within_threshold():
    f = check_freshness("2026-06-10", history_cache=HISTORY, date_index=INDEX)
    assert f["history_max_date"] == "2026-06-07"
    assert f["index_max_date"] == "2026-06-07"
    assert f["history_gap_days"] == 3
    assert f["index_gap_days"] == 3
    assert f["is_stale"] is False


def test_stale_beyond_threshold():
    # index は新しいが history が 3ヶ月凍結 → stale（gap の大きい方で判定）
    stale_hist = {"k": [{"race_date": "2026-03-15"}]}
    f = check_freshness("2026-06-12", history_cache=stale_hist, date_index=INDEX)
    assert f["history_gap_days"] == 89
    assert f["is_stale"] is True


def test_threshold_boundary():
    # gap == threshold は stale でない（> で判定）、gap == threshold+1 は stale
    idx = {"2026-06-01": ["r"]}
    hist = {"k": [{"race_date": "2026-06-01"}]}
    assert check_freshness("2026-06-15", history_cache=hist, date_index=idx,
                           warn_threshold_days=14)["is_stale"] is False  # gap 14
    assert check_freshness("2026-06-16", history_cache=hist, date_index=idx,
                           warn_threshold_days=14)["is_stale"] is True   # gap 15


def test_quick_skips_history():
    # quick=True は history を読まない（None のまま、index のみで判定）
    f = check_freshness("2026-06-10", history_cache=HISTORY, date_index=INDEX, quick=True)
    assert f["history_max_date"] is None
    assert f["history_gap_days"] is None
    assert f["index_gap_days"] == 3
    assert f["is_stale"] is False


def test_quick_detects_stale_index():
    old_idx = {"2026-03-17": ["r"]}
    f = check_freshness("2026-06-12", date_index=old_idx, quick=True)
    assert f["is_stale"] is True


def test_format_status_strings():
    fresh = check_freshness("2026-06-10", history_cache=HISTORY, date_index=INDEX)
    assert "[OK]" in format_status(fresh)
    assert "fresh" in format_status(fresh)
    stale = check_freshness("2026-09-12", history_cache=HISTORY, date_index=INDEX)
    assert "[WARN]" in format_status(stale)
    assert "STALE" in format_status(stale)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""notify.build_daily_plan_text の金額読み上げテスト (Session 134 🔴-2)

Session 134 で追加した:
  - bets_summary の各 dict に amount キーがあれば「N 番 X円」 と読み上げ
  - amount が None / 0 / 非int なら従来通り「N 番」 のみ
  - 不均等案分時に二重認証ゲートの内容承認解像度を保つ

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_notify_daily_plan_amount.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.target_clicker.notify import build_daily_plan_text


class TestBuildDailyPlanTextWithAmount:

    def test_amount_present_is_read(self):
        """amount が int で読み上げられる (Session 134 🔴-2)"""
        text = build_daily_plan_text(
            bets_summary=[
                {"race_id": "2026053108010101", "umaban": 6,
                 "venue_name": "新潟", "race_number": 8, "amount": 500},
            ],
            total_yen=500,
        )
        assert "新潟8R 単勝 6 番 500円" in text
        assert "合計 1 件、 500円" in text

    def test_unequal_amounts_all_read(self):
        """不均等案分: 各 bet の金額が個別に読み上げられる"""
        text = build_daily_plan_text(
            bets_summary=[
                {"race_id": "2026053108010101", "umaban": 6,
                 "venue_name": "新潟", "race_number": 8, "amount": 500},
                {"race_id": "2026053106010801", "umaban": 1,
                 "venue_name": "京都", "race_number": 8, "amount": 200},
                {"race_id": "2026053106010802", "umaban": 3,
                 "venue_name": "京都", "race_number": 9, "amount": 100},
            ],
            total_yen=800,
        )
        assert "500円" in text
        assert "200円" in text
        assert "100円" in text
        assert "合計 3 件、 800円" in text

    def test_amount_none_fallback_to_legacy(self):
        """amount=None → 従来通り 「N 番」 のみ (Session 128 互換)"""
        text = build_daily_plan_text(
            bets_summary=[
                {"race_id": "2026053108010101", "umaban": 6,
                 "venue_name": "新潟", "race_number": 8},
                # amount キー無し
            ],
            total_yen=100,
        )
        assert "新潟8R 単勝 6 番" in text
        assert "円" not in text.split("単勝 6 番")[1].split("。")[0]  # 「6 番」 のすぐ後に円無し

    def test_amount_zero_treated_as_missing(self):
        """amount=0 → 金額読み上げなし (異常値防御)"""
        text = build_daily_plan_text(
            bets_summary=[
                {"race_id": "2026053108010101", "umaban": 6,
                 "venue_name": "新潟", "race_number": 8, "amount": 0},
            ],
            total_yen=0,
        )
        # amount=0 は読み上げない (None と同等扱い)
        assert "0円" not in text.split("単勝")[1].split("。")[0]

    def test_amount_str_treated_as_missing(self):
        """amount='500' (str) → 型違反として読み上げなし (防御)"""
        text = build_daily_plan_text(
            bets_summary=[
                {"race_id": "2026053108010101", "umaban": 6,
                 "venue_name": "新潟", "race_number": 8, "amount": "500"},
            ],
            total_yen=500,
        )
        # str は無視されて 「6 番」 のみ
        assert "500円" not in text.split("単勝")[1].split("。")[0]

    def test_max_detail_truncation_keeps_amount(self):
        """max_detail=2 で 4 件 → 上 2 件 だけ金額読み上げ + 「他 2 件」"""
        text = build_daily_plan_text(
            bets_summary=[
                {"race_id": "2026053108010101", "umaban": 6,
                 "venue_name": "新潟", "race_number": 8, "amount": 500},
                {"race_id": "2026053106010802", "umaban": 1,
                 "venue_name": "京都", "race_number": 8, "amount": 400},
                {"race_id": "2026053106010803", "umaban": 3,
                 "venue_name": "京都", "race_number": 9, "amount": 300},
                {"race_id": "2026053106010804", "umaban": 5,
                 "venue_name": "京都", "race_number": 10, "amount": 200},
            ],
            total_yen=1400,
            max_detail=2,
        )
        assert "500円" in text
        assert "400円" in text
        assert "他 2 件" in text
        assert "合計 4 件、 1400円" in text

    def test_empty_bets_no_amount_section(self):
        """空 bets[] → 既存挙動維持"""
        text = build_daily_plan_text(bets_summary=[], total_yen=0)
        assert "本日の投票プランが空です" in text
        assert "円" not in text  # 「空」 メッセージなので金額無し

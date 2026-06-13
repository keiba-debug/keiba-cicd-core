#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-003 接戦タイブレーク（騎手 close_win_rate）のテスト。

- jockey_close リーダー / reliable 純関数
- apply_win_per_race_limit の同点解消（close_lookup 有無で挙動差）
"""

import json

from ml.strategies.jockey_close import load_jockey_close_map, jockey_close_reliable
from ml.bet_engine import BetRecommendation, apply_win_per_race_limit


# --- リーダー ---

def _write_json(tmp_path, payload):
    p = tmp_path / "jockey_close_finish.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def test_load_map_builds_code_index(tmp_path):
    p = _write_json(tmp_path, {"ranking": [
        {"code": "01220", "close_win_rate": 0.769,
         "quality": {"ci95": {"lower": 0.451, "upper": 0.828}}},
        {"code": "05366", "close_win_rate": 0.40,
         "quality": {"ci95": {"lower": 0.30, "upper": 0.51}}},
    ]})
    m = load_jockey_close_map(p)
    assert set(m.keys()) == {"01220", "05366"}
    assert m["01220"]["close_win_rate"] == 0.769


def test_load_map_missing_file_returns_empty(tmp_path):
    assert load_jockey_close_map(tmp_path / "nope.json") == {}


def test_load_map_broken_json_returns_empty(tmp_path):
    p = tmp_path / "jockey_close_finish.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_jockey_close_map(p) == {}


def test_load_map_no_ranking_returns_empty(tmp_path):
    p = _write_json(tmp_path, {"summary": {}})
    assert load_jockey_close_map(p) == {}


# --- reliable 純関数: ci95.lower 採用 ---

def test_reliable_uses_ci_lower():
    jmap = {"01220": {"close_win_rate": 0.769,
                      "quality": {"ci95": {"lower": 0.451, "upper": 0.828}}}}
    # 生率 0.769 でなく下限 0.451（小標本上振れに騙されない）
    assert jockey_close_reliable(jmap, "01220") == 0.451


def test_reliable_unknown_jockey_zero():
    jmap = {"01220": {"close_win_rate": 0.7, "quality": {"ci95": {"lower": 0.4}}}}
    assert jockey_close_reliable(jmap, "99999") == 0.0


def test_reliable_missing_code_zero():
    assert jockey_close_reliable({}, None) == 0.0
    assert jockey_close_reliable({}, "") == 0.0


def test_reliable_no_quality_falls_back_to_point():
    jmap = {"01220": {"close_win_rate": 0.5}}
    assert jockey_close_reliable(jmap, "01220") == 0.5


# --- apply_win_per_race_limit: 同点タイブレーク ---

def _win_rec(umaban, vb_score, dev_gap=0.5, odds=10.0):
    return BetRecommendation(
        race_id="R1", umaban=umaban, horse_name=f"H{umaban}",
        bet_type="単勝", strength="normal",
        win_amount=100, place_amount=0,
        vb_score=vb_score, dev_gap=dev_gap, odds=odds,
        kelly_capped=0.1,  # 降格時に複勝へ（取り消しでなく）
    )


def test_tiebreak_prefers_higher_close_reliable():
    # vb_score 同点・dev_gap/odds も同点 → 騎手接戦勝率で決まる
    a = _win_rec(1, vb_score=5.0)
    b = _win_rec(2, vb_score=5.0)
    close_lookup = {("R1", 1): 0.20, ("R1", 2): 0.45}  # 馬2の騎手が接戦強い
    recs = apply_win_per_race_limit([a, b], max_win=1, close_lookup=close_lookup)
    kept = [r for r in recs if r.bet_type == "単勝"]
    demoted = [r for r in recs if r.bet_type == "複勝"]
    assert [r.umaban for r in kept] == [2]      # 接戦勝率の高い馬2が単勝で残る
    assert [r.umaban for r in demoted] == [1]   # 馬1は複勝に降格


def test_no_lookup_keeps_legacy_order():
    # close_lookup なし → 従来の dev_gap → odds 優先（接戦は無関係）
    a = _win_rec(1, vb_score=5.0, dev_gap=1.0)
    b = _win_rec(2, vb_score=5.0, dev_gap=0.5)
    recs = apply_win_per_race_limit([a, b], max_win=1, close_lookup=None)
    kept = [r for r in recs if r.bet_type == "単勝"]
    assert [r.umaban for r in kept] == [1]  # dev_gap 高い馬1が残る


def test_tiebreak_only_breaks_real_ties():
    # vb_score に差があれば接戦勝率は逆転させない（買い判定は変えない）
    a = _win_rec(1, vb_score=6.0)  # 高スコア
    b = _win_rec(2, vb_score=5.0)
    close_lookup = {("R1", 1): 0.10, ("R1", 2): 0.50}  # 馬2が接戦強くても…
    recs = apply_win_per_race_limit([a, b], max_win=1, close_lookup=close_lookup)
    kept = [r for r in recs if r.bet_type == "単勝"]
    assert [r.umaban for r in kept] == [1]  # vb_score 優先、馬1が残る


def test_under_limit_no_demotion():
    a = _win_rec(1, vb_score=5.0)
    recs = apply_win_per_race_limit([a], max_win=2, close_lookup={("R1", 1): 0.4})
    assert recs[0].bet_type == "単勝"

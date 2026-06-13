#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-005 reason_tags / slow_start reader のテスト（表示専用タグ）。"""

import json

from ml.strategies.slow_start import (
    load_slow_start_maps, jockey_slow_start_reliable, horse_slow_start_rate,
)
from ml.strategies.reason_tags import build_reason_tags


# --- slow_start reader ---

def test_load_slow_start_maps(tmp_path):
    p = tmp_path / "slow_start_analysis.json"
    p.write_text(json.dumps({
        "jockey_ranking": [{"jockey_code": "01029", "slow_start_rate": 0.45,
                            "quality": {"ci95": {"lower": 0.388, "upper": 0.51}, "effective_n": 233}}],
        "horse_stats": [{"ketto_num": "2020104329", "slow_start_rate": 0.5}],
    }, ensure_ascii=False), encoding="utf-8")
    jmap, hmap = load_slow_start_maps(p)
    assert "01029" in jmap and "2020104329" in hmap
    assert jockey_slow_start_reliable(jmap, "01029") == 0.388  # ci.lower
    assert horse_slow_start_rate(hmap, "2020104329") == 0.5


def test_slow_start_missing_file(tmp_path):
    assert load_slow_start_maps(tmp_path / "nope.json") == ({}, {})


def test_slow_start_unknown_codes_zero():
    assert jockey_slow_start_reliable({}, "x") == 0.0
    assert horse_slow_start_rate({}, None) == 0.0


# --- reason_tags ---

JCLOSE = {"01220": {"close_win_rate": 0.769,
                    "quality": {"ci95": {"lower": 0.48, "upper": 0.83}, "effective_n": 13,
                                "stability_flag": "insufficient"}},
          "05366": {"close_win_rate": 0.55,
                    "quality": {"ci95": {"lower": 0.50, "upper": 0.62}, "effective_n": 120,
                                "stability_flag": "stable"}}}
SS_J = {"01029": {"slow_start_rate": 0.45,
                  "quality": {"ci95": {"lower": 0.35, "upper": 0.55}, "effective_n": 200}}}
SS_H = {}


def _tags(**kw):
    base = dict(jockey_code=None, ketto_num=None, horse_ss_rate=None,
               first_corner_ratio=None, jclose_map=JCLOSE, ss_jmap=SS_J, ss_hmap=SS_H)
    base.update(kw)
    return build_reason_tags(**base)


def test_close_finish_tag_fires_on_high_reliable():
    # 05366: ci.lower 0.50 >= 0.45 → 接戦◎、effective_n 120 → 低信頼でない
    tags = _tags(jockey_code="05366")
    types = {t["type"] for t in tags}
    assert "close_finish" in types
    assert "low_confidence" not in types


def test_close_finish_low_confidence_meta_tag():
    # 01220: ci.lower 0.46 >= 0.45 → ◎ だが effective_n 13 < 20 → 低信頼タグも出る
    tags = _tags(jockey_code="01220")
    types = {t["type"] for t in tags}
    assert "close_finish" in types and "low_confidence" in types
    cf = next(t for t in tags if t["type"] == "close_finish")
    assert cf["low_confidence"] is True


def test_no_close_tag_when_reliable_low():
    # close ci.lower 0.30 < 0.45 → ◎ なし
    jclose = {"09": {"close_win_rate": 0.6, "quality": {"ci95": {"lower": 0.30}}}}
    tags = build_reason_tags(jockey_code="09", ketto_num=None, horse_ss_rate=None,
                             first_corner_ratio=None, jclose_map=jclose, ss_jmap={}, ss_hmap={})
    assert tags == []


def test_slow_start_habitual_horse():
    tags = _tags(jockey_code="05366", horse_ss_rate=0.35)  # >=0.30 常習
    ss = [t for t in tags if t["type"] == "slow_start"]
    assert ss and "馬出遅れ" in ss[0]["detail"]


def test_slow_start_front_runner_lower_threshold():
    # 逃げ馬(1角0.1) は ss 0.22 でも注意（常習閾値0.30未満でも）
    tags = _tags(jockey_code="05366", horse_ss_rate=0.22, first_corner_ratio=0.1)
    assert any(t["type"] == "slow_start" for t in tags)
    # 非逃げ(0.5)なら 0.22 では出ない
    tags2 = _tags(jockey_code="05366", horse_ss_rate=0.22, first_corner_ratio=0.5)
    assert not any(t["type"] == "slow_start" for t in tags2)


def test_slow_start_jockey_risk():
    # 騎手 01029 ss ci.lower 0.35 >= 0.30 → 出遅れ注意（馬データなし）
    tags = _tags(jockey_code="01029")
    assert any(t["type"] == "slow_start" for t in tags)


def test_empty_when_no_signals():
    # 接戦/出遅れどのmapにも居ない騎手・低出遅れ馬・非逃げ → タグなし
    assert _tags(jockey_code="99999", horse_ss_rate=0.05, first_corner_ratio=0.5) == []

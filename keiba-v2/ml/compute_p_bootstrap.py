#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""experiment result JSON の race_predictions から P Top1 Bootstrap ROI を算出"""
import json
import sys
import numpy as np
from pathlib import Path

def bootstrap_top1(races, n_boot=1000):
    rng = np.random.default_rng(42)
    ids = list(races.keys())
    n = len(ids)
    rois = []
    total_bet = n * 100
    base_ret = sum(races[i] for i in ids)
    base_roi = base_ret / total_bet * 100
    for _ in range(n_boot):
        sampled = rng.choice(ids, size=n, replace=True)
        ret = sum(races[i] for i in sampled)
        rois.append(ret / total_bet * 100)
    arr = np.array(rois)
    return {
        "top1_win_roi": round(base_roi, 1),
        "top1_win_roi_ci_low": round(float(np.percentile(arr, 2.5)), 1),
        "top1_win_roi_ci_high": round(float(np.percentile(arr, 97.5)), 1),
        "n_races": n,
    }


def from_result(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    race_returns = {}
    for race in data.get("race_predictions", []):
        rid = race["race_id"]
        top = min(race["horses"], key=lambda h: h["place_rank"])
        ret = top["odds"] * 100 if top.get("actual_position") == 1 else 0
        race_returns[rid] = ret
    return bootstrap_top1(race_returns)


if __name__ == "__main__":
    print(json.dumps(from_result(sys.argv[1]), ensure_ascii=False, indent=2))

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ML特徴量キャッシュの鮮度チェック（Session 152）

horse_history_cache.json / race_date_index.json の最大 race_date と
予測対象レース日（または今日）のギャップを測り、3ヶ月凍結事故（Session 151,
[[ml-cache-staleness-incident]]）の再発を検知する。

3層の再発防止で共用する単一ソース:
  ①検知  : ml.predict が予測直前に check_freshness() を呼び、stale なら警告print
  ③検証可能性: predictions.json の 'cache_freshness' メタに同じ dict を埋め込む
  ②監視  : keiba-status-check が `python -m ml.cache_freshness --quick` で朝イチ確認

予防層（毎回 ②-4.5 で再構築）はスキル keiba-data-prep 側。ここは「漏れたら気づく」係。

Usage:
    python -m ml.cache_freshness                 # 今日基準・本番キャッシュの鮮度を表示
    python -m ml.cache_freshness --date 2026-06-13
    python -m ml.cache_freshness --quick --json  # 237MBロードを省く（status-check用）
"""

import argparse
import json
import sys
from datetime import date as _date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config

# 開催間隔のラグ（確定SE同期待ちで数日遅れは常態）を踏まえた警告閾値。
# 中1週でも7日、3ヶ月凍結なら90日。14日なら正常運用は素通り・凍結は確実に捕捉。
DEFAULT_WARN_THRESHOLD_DAYS = 14


def _load_json(path: Path):
    if not path.exists():
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def get_index_max_date(date_index: dict = None):
    """race_date_index.json の最大日付（キーが YYYY-MM-DD）。軽量。"""
    if date_index is None:
        date_index = _load_json(config.indexes_dir() / "race_date_index.json")
    if not date_index:
        return None
    return max(date_index.keys())


def get_history_max_date(history_cache: dict = None):
    """horse_history_cache の全馬を通じた最大 race_date。

    各馬の走歴は build_horse_history で日付昇順ソート済みなので、末尾 [-1] のみ
    走査すれば足りる（547,618走の全スキャン不要 = 60,322頭の末尾だけ）。
    history_cache=None だと 237MB を読むので、predict 側は load 済みの dict を渡すこと。
    status-check は quick=True で本関数自体を呼ばない。
    """
    if history_cache is None:
        history_cache = _load_json(config.ml_dir() / "horse_history_cache.json")
    if not history_cache:
        return None
    mx = None
    for runs in history_cache.values():
        if runs:
            d = runs[-1].get('race_date')
            if d and (mx is None or d > mx):
                mx = d
    return mx


def _days_between(d_from: str, d_to: str) -> int:
    return (_date.fromisoformat(d_to) - _date.fromisoformat(d_from)).days


def check_freshness(target_date: str, history_cache: dict = None, date_index: dict = None,
                    warn_threshold_days: int = DEFAULT_WARN_THRESHOLD_DAYS,
                    quick: bool = False) -> dict:
    """両キャッシュの最大走日と target_date のギャップを測り dict で返す。

    quick=True なら horse_history_cache の 237MB ロードを省き race_date_index のみで判定
    （status-check 用の軽量パス）。is_stale は2つのギャップの大きい方が閾値超で True。
    """
    idx_max = get_index_max_date(date_index)
    hist_max = None if quick else get_history_max_date(history_cache)
    idx_gap = _days_between(idx_max, target_date) if idx_max else None
    hist_gap = None if hist_max is None else _days_between(hist_max, target_date)
    gaps = [g for g in (idx_gap, hist_gap) if g is not None]
    is_stale = bool(gaps) and max(gaps) > warn_threshold_days
    return {
        'target_date': target_date,
        'history_max_date': hist_max,
        'index_max_date': idx_max,
        'history_gap_days': hist_gap,
        'index_gap_days': idx_gap,
        'warn_threshold_days': warn_threshold_days,
        'quick': quick,
        'is_stale': is_stale,
    }


def format_status(fresh: dict) -> str:
    """生出力用の1行サマリ（SJIS端末でも化けないよう ASCII 主体）。"""
    if fresh['is_stale']:
        return (
            f"[WARN] ML cache STALE: history max={fresh['history_max_date']} "
            f"(gap {fresh['history_gap_days']}d), index max={fresh['index_max_date']} "
            f"(gap {fresh['index_gap_days']}d) vs target {fresh['target_date']} "
            f"> threshold {fresh['warn_threshold_days']}d. "
            f"Rebuild: keiba-data-prep step 2-4.5 "
            f"(build_race_index + build_horse_history)."
        )
    return (
        f"[OK] ML cache fresh: history max={fresh['history_max_date']}, "
        f"index max={fresh['index_max_date']} vs target {fresh['target_date']} "
        f"(gap <= {fresh['warn_threshold_days']}d)."
    )


def main():
    ap = argparse.ArgumentParser(description='Check ML feature cache freshness')
    ap.add_argument('--date', help='Target race date YYYY-MM-DD (default: today)')
    ap.add_argument('--quick', action='store_true',
                    help='Skip 237MB horse_history load; judge by race_date_index only')
    ap.add_argument('--threshold', type=int, default=DEFAULT_WARN_THRESHOLD_DAYS)
    ap.add_argument('--json', action='store_true', help='Emit JSON')
    args = ap.parse_args()

    target = args.date or _date.today().isoformat()
    fresh = check_freshness(target, warn_threshold_days=args.threshold, quick=args.quick)
    if args.json:
        print(json.dumps(fresh, ensure_ascii=False, indent=2))
    else:
        print(format_status(fresh))
    # stale を exit code で返す（status-check / CI が拾える）
    sys.exit(1 if fresh['is_stale'] else 0)


if __name__ == '__main__':
    main()

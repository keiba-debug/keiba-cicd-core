#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-001 coverage 検証 — 全分析JSONの鮮度メタを一括点検。

keiba-data-prep ①-2（集計再計算）の直後に実行し、各分析の coverage.to_date が
直近開催日に到達したかを確認する。「再生成が走った」と「正しい期間のデータに
なった」は別物で、created_at（生成時刻）だけでは jockey_close_finish の 3ヶ月凍結
のような鮮度ギャップを検知できなかった（S-3 / ml-cache-staleness-incident 同型）。

Usage:
    python -m analysis.check_coverage                       # 一覧表示のみ
    python -m analysis.check_coverage --expect 2026-06-07   # to_date < expect を STALE 警告し exit 1
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config

# (label, relpath, meta_key, lag_days)
#   meta_key = coverage/schema_version が入る親キー（None=top-level）
#   lag_days = 元データの構造的遅延の許容日数。--expect 判定で expect-lag_days まで猶予。
#     RPCI(pace/lap)・IDM(JRDB確定)は seiseki より数日〜2週遅れて確定するため、
#     直近開催が未反映でも即異常ではない（false STALE を防ぐ）。
TARGETS = [
    ('調教師',   'analysis/trainer_patterns.json',   'metadata', 0),
    ('調教',     'analysis/training_analysis.json',  'metadata', 0),
    ('出遅れ',   'analysis/slow_start_analysis.json', None,      0),
    ('騎手接戦', 'analysis/jockey_close_finish.json', None,      0),
    ('血統',     'indexes/sire_stats_index.json',    'meta',     0),
    # E-010 拡張（Session 155）
    ('RPCI',     'analysis/race_type_standards.json', 'metadata', 10),
    ('IDM',      'analysis/idm_standards.json',       'metadata', 21),
    ('レイティング', 'analysis/rating_standards.json', 'metadata', 0),
]


def _meta(d: dict, key) -> dict:
    return d.get(key, {}) if key else d


def main() -> int:
    ap = argparse.ArgumentParser(description="E-001 coverage 検証")
    ap.add_argument('--expect', help='期待する最低 to_date (YYYY-MM-DD)。未達は STALE')
    args = ap.parse_args()

    root = config.data_root()
    ng = 0
    print(f"{'分析':<8} {'schema':<16} {'from':<12} {'to':<12} {'granularity':<10} status")
    print("-" * 72)
    for label, rel, mkey, lag_days in TARGETS:
        p = root / rel
        if not p.exists():
            print(f"{label:<8} (missing: {rel})")
            ng += 1
            continue
        d = json.loads(p.read_text(encoding='utf-8'))
        meta = _meta(d, mkey)
        sv = meta.get('schema_version') or d.get('schema_version') or '-'
        cov = meta.get('coverage') or d.get('coverage') or {}
        frm = cov.get('from_date', '-')
        to = cov.get('to_date', '-')
        gran = cov.get('granularity', 'day')
        status = 'OK'
        # granularity=year は to_date が年末（未来日）になるので日次 expect 判定から除外。
        # lag_days を引いた緩和 expect で判定（構造遅延ソースの false STALE 回避）。
        if args.expect and to != '-' and gran != 'year':
            eff_expect = args.expect
            if lag_days:
                eff_expect = (datetime.strptime(args.expect, '%Y-%m-%d')
                              - timedelta(days=lag_days)).strftime('%Y-%m-%d')
            if to < eff_expect:
                status = f'STALE(<{eff_expect})'
                ng += 1
        if sv == '-':
            status = 'NO_SCHEMA'
            ng += 1
        print(f"{label:<8} {sv:<16} {frm:<12} {to:<12} {gran:<10} {status}")

    if ng:
        print(f"\n[WARN] {ng} 件が STALE / 欠落 / schema未付与")
        return 1
    print("\n[OK] 全分析の coverage 健全")
    return 0


if __name__ == '__main__':
    sys.exit(main())

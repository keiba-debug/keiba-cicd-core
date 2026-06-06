# -*- coding: utf-8 -*-
"""AI評価印 (markSet=2) を過去レースに遡及付与する backfill ランナー。

印スロット再編 (docs/auto-purchase/26_MARK_SLOT_MAP.md) 後、 既存 predictions.json を
使って過去開催に AI評価印を一括で書く。 各日は write_ai_marks.process_date を再利用。

★前提・注意 (26 §6):
  - 既存 predictions.json をそのまま使う (再 predict しない)。 直近分は当時のライブ予測、
    過去分 (〜2026-04 一括再生成) は最新 polaris 系の後追い予測 = 「後知恵」。
    → **表示・レビュー用**。 成績検証には使わない (leakage)。 検証は OOS/walk-forward で別途。
  - AI評価 (composite) はレース前特徴量中心なので遡及しやすい。 AI購入軸 (markSet=3) は
    投票時点オッズが要るため本スクリプトの対象外 (別途)。

★安全ガード:
  - **当日以降 (>= --cutoff、 既定=今日) は書かない**。 開催当日のパイプライン/投票に影響させない。
    過去分のみ。 --allow-today で明示的に解除可 (非推奨)。
  - 書込み先 markSet は既定 2 (AI評価)。 1 (手動) は dat_writer が拒否。
  - 書込み先ベースは JV_DATA_ROOT (既定 C:/TFJV)。 試走は `JV_DATA_ROOT=<sandbox>` で逃がす。

使用例:
  # サンドボックス試走 (本番 TFJV を触らない)
  JV_DATA_ROOT=C:/tmp/sandbox_jv python -m ml.ai_marks.backfill_ai_marks \
      --start 2026-05-01 --end 2026-05-31 --step 2 --apply
  # 本番 (非開催日に)
  python -m ml.ai_marks.backfill_ai_marks --start 2025-06-08 --end 2026-06-05 --step 2 --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from typing import Tuple

from ml.ai_marks.dat_writer import _MARK_SLOT_AI
from ml.ai_marks.write_ai_marks import _parse_weights, process_date


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def run_backfill(
    start: date,
    end: date,
    *,
    cutoff: date,
    weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    step: int = 2,
    ana: bool = False,
    mark_set: int = _MARK_SLOT_AI,
    apply: bool = False,
    allow_today: bool = False,
    verbose: bool = False,
) -> dict:
    """[start, end] の各日に AI評価印を遡及付与。 当日以降 (>=cutoff) は allow_today でない限りスキップ。"""
    if start > end:
        raise ValueError(f"start {start} > end {end}")

    totals = {"days_processed": 0, "days_no_pred": 0, "days_guarded": 0,
              "races": 0, "marked": 0, "skipped": 0, "written": 0, "marks_total": 0}
    per_day = []
    for d in _daterange(start, end):
        if not allow_today and d >= cutoff:
            totals["days_guarded"] += 1
            print(f"  [GUARD] {d} は当日以降 (>= {cutoff}) のためスキップ "
                  f"(--allow-today で解除)", file=sys.stderr)
            continue
        res = process_date(d.isoformat(), weights=weights, step=step, ana=ana,
                           apply=apply, mark_set=mark_set, verbose=verbose)
        if not res["ok"]:
            totals["days_no_pred"] += 1
            continue
        totals["days_processed"] += 1
        for k in ("races", "marked", "skipped", "written", "marks_total"):
            totals[k] += res[k]
        per_day.append(res)
        tag = "APPLY" if apply else "dry"
        print(f"  {d} [{tag}] races={res['races']} 印あり={res['marked']} "
              f"撃ちなし={res['skipped']} 書込={res['written']}頭")

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n[backfill] {mode} mark_set={mark_set} step={step} "
          f"期間 {start}〜{end} (cutoff={cutoff})")
    print(f"[backfill] 処理日={totals['days_processed']} / "
          f"predictions無={totals['days_no_pred']} / ガード(当日以降)={totals['days_guarded']}")
    print(f"[backfill] 印あり={totals['marked']}R 計{totals['marks_total']}印 "
          f"撃ちなし={totals['skipped']}R 書込={totals['written']}頭")
    if not apply:
        print("[backfill] (dry-run: DAT 未書込み。 --apply で実書込み)")
    totals["per_day"] = per_day
    return totals


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AI評価印 (markSet=2) 過去レース遡及付与")
    ap.add_argument("--start", required=True, type=_parse_date, help="開始日 YYYY-MM-DD")
    ap.add_argument("--end", required=True, type=_parse_date, help="終了日 YYYY-MM-DD (含む)")
    ap.add_argument("--weights", type=_parse_weights, default=(1.0, 1.0, 1.0),
                    help="(wW,wP,wA) 既定 1,1,1")
    ap.add_argument("--step", type=int, default=2, choices=(1, 2),
                    help="1=◎のみ / 2=◎○▲△Ⅲ 段差 (既定 2)")
    ap.add_argument("--ana", action="store_true", help="穴印を別系統で付加 (step=2のみ)")
    ap.add_argument("--mark-set", type=int, default=_MARK_SLOT_AI,
                    help=f"書込み先 markSet (既定 {_MARK_SLOT_AI}=AI評価)")
    ap.add_argument("--cutoff", type=_parse_date, default=None,
                    help="この日以降は書かない (既定=今日)。 当日運用保護")
    ap.add_argument("--allow-today", action="store_true",
                    help="(非推奨) 当日以降ガードを解除")
    ap.add_argument("--apply", action="store_true",
                    help="DAT に実書込み (未指定は dry-run)")
    ap.add_argument("--verbose", action="store_true", help="各レースの印を表示")
    args = ap.parse_args(argv)

    cutoff = args.cutoff or date.today()
    res = run_backfill(args.start, args.end, cutoff=cutoff, weights=args.weights,
                       step=args.step, ana=args.ana, mark_set=args.mark_set,
                       apply=args.apply, allow_today=args.allow_today,
                       verbose=args.verbose)
    return 0 if (res["days_processed"] > 0 or res["days_no_pred"] > 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())

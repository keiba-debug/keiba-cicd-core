# -*- coding: utf-8 -*-
"""AI予想印 書込み CLI。

predictions.json を読み、各レースに assign_ai_marks を適用して ◎ を決定する。
  --dry-run (既定) : 決定結果を表示。DAT は書かない。監査ログも書かない。
  --apply          : DAT (markSet=6) に書込み + 監査ログ追記。

設計: docs/auto-purchase/22_AI_MARKS_DESIGN.md §2 / §5 SC-4

使用例:
  python -m ml.ai_marks.write_ai_marks --date 2026-05-31                    # dry-run (Step1 ◎のみ)
  python -m ml.ai_marks.write_ai_marks --date 2026-05-31 --step 2           # ◎○▲△Ⅲ 段差ベース
  python -m ml.ai_marks.write_ai_marks --date 2026-05-31 --step 2 --ana     # 穴も付加 (実験)
  python -m ml.ai_marks.write_ai_marks --date 2026-05-31 --weights 0.5,2,0.5
  python -m ml.ai_marks.write_ai_marks --date 2026-05-31 --step 2 --apply   # 実書込み
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

from ml.ai_marks.assign import assign_ai_marks
from ml.ai_marks.audit_log import append_audit
from ml.ai_marks.dat_writer import write_ai_marks_to_dat


def _data_root() -> Path:
    return Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))


def _predictions_path(date: str) -> Path:
    y, m, d = date.split("-")
    return _data_root() / "races" / y / m / d / "predictions.json"


def _parse_weights(s: str) -> Tuple[float, float, float]:
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("weights は 'wW,wP,wA' の3値 (例 1,1,1)")
    try:
        return tuple(float(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise argparse.ArgumentTypeError(f"weights が数値でない: {s!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AI予想印 (markSet=6) 書込み")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--weights", type=_parse_weights, default=(1.0, 1.0, 1.0),
                    help="(wW,wP,wA) 既定 1,1,1")
    ap.add_argument("--step", type=int, default=1, choices=(1, 2),
                    help="1=◎のみ / 2=◎○▲△Ⅲ 段差ベース (既定 1)")
    ap.add_argument("--ana", action="store_true",
                    help="穴印を別系統で付加 (step=2 のみ有効、実験扱い)")
    ap.add_argument("--apply", action="store_true",
                    help="DAT に実書込み + 監査ログ (未指定は dry-run)")
    args = ap.parse_args(argv)

    pred_path = _predictions_path(args.date)
    if not pred_path.exists():
        print(f"[ai-marks] predictions.json なし: {pred_path}", file=sys.stderr)
        return 2

    with open(pred_path, encoding="utf-8") as f:
        pred = json.load(f)

    races = pred.get("races", [])
    mode = "APPLY" if args.apply else "DRY-RUN"
    ana_tag = " +穴" if (args.step >= 2 and args.ana) else ""
    print(f"[ai-marks] {args.date} {mode} step={args.step}{ana_tag} "
          f"weights={args.weights} races={len(races)}")
    print(f"[ai-marks] predictions vb_refreshed_at={pred.get('vb_refreshed_at')}")
    print()

    now_iso = datetime.now().isoformat(timespec="seconds") if args.apply else None

    n_marked = 0       # 印を1つ以上立てたレース数
    n_skipped = 0
    n_written = 0
    n_marks_total = 0  # 全レース合計の印数 (Step2 で ◎○▲△Ⅲ穴 を含む)
    for race in races:
        rid = race.get("race_id", "")
        venue = race.get("venue_name", "")
        rno = race.get("race_number", "")
        entries = race.get("entries", [])
        result = assign_ai_marks(
            entries, weights=args.weights, step=args.step, enable_ana=args.ana,
        )

        # 監査用 composite top3 (馬番:score)
        comp_top3 = sorted(result.composite.items(), key=lambda kv: -kv[1])[:3]
        audit_rec = {
            "race_id": rid,
            "step": args.step,
            "weights": list(result.weights),
            "marks": {str(u): m for u, m in result.marks.items()},
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
            "adr_used": result.adr_used,
            "composite_top3": [[u, round(s, 4)] for u, s in comp_top3],
            "notes": result.notes,
        }

        if result.skipped:
            n_skipped += 1
            note = f" ({'; '.join(result.notes)})" if result.notes else ""
            print(f"  {venue} {rno:>2}R  撃ちなし [{result.skip_reason}]{note}")
            if args.apply:
                append_audit(args.date, audit_rec, ts=now_iso)
            continue

        n_marked += 1
        n_marks_total += len(result.marks)
        adr_tag = "" if result.adr_used else " [ADR縮退]"
        # 印を序列順 (◎○▲△Ⅲ穴) に並べて表示
        order = {"◎": 0, "○": 1, "▲": 2, "△": 3, "Ⅲ": 4, "穴": 5}
        ordered = sorted(result.marks.items(), key=lambda kv: (order.get(kv[1], 9), kv[0]))
        cells = []
        for u, sym in ordered:
            hm = next((e for e in entries if int(e.get("umaban", -1)) == u), {})
            name = (hm.get("horse_name") or "?")[:6]
            cells.append(f"{sym}{u:>2}{name}")
        print(f"  {venue} {rno:>2}R  " + " ".join(cells) + adr_tag)

        if args.apply:
            try:
                w = write_ai_marks_to_dat(rid, result.marks, mark_set=6)
                n_written += w
                append_audit(args.date, audit_rec, ts=now_iso)
            except Exception as e:  # noqa: BLE001
                print(f"    [WARN] DAT書込み失敗 {rid}: {e}", file=sys.stderr)
                audit_rec["write_error"] = str(e)
                append_audit(args.date, audit_rec, ts=now_iso)

    print()
    avg = (n_marks_total / n_marked) if n_marked else 0.0
    print(f"[ai-marks] 印あり={n_marked}R (計{n_marks_total}印 / 平均{avg:.1f}印/R)  "
          f"撃ちなし={n_skipped}R", end="")
    if args.apply:
        print(f"  → markSet=6 に {n_written}頭 書込み + 監査ログ追記")
    else:
        print("  (dry-run: DAT 未書込み)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

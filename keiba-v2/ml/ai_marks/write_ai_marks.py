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
from ml.ai_marks.dat_writer import _MARK_SLOT_AI, write_ai_marks_to_dat


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


def process_date(
    date: str,
    *,
    weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    step: int = 1,
    ana: bool = False,
    apply: bool = False,
    mark_set: int = _MARK_SLOT_AI,
    verbose: bool = True,
) -> dict:
    """1 日分の predictions に AI評価印を割当 (apply 時は DAT 書込み + 監査)。

    単発 CLI (main) と 遡及 backfill (backfill_ai_marks) の共通コア。
    Returns: {ok, races, marked, skipped, written, marks_total} (ok=False は predictions 無し)。
    """
    pred_path = _predictions_path(date)
    if not pred_path.exists():
        if verbose:
            print(f"[ai-marks] predictions.json なし: {pred_path}", file=sys.stderr)
        return {"ok": False, "date": date, "reason": "no_predictions",
                "races": 0, "marked": 0, "skipped": 0, "written": 0, "marks_total": 0}

    with open(pred_path, encoding="utf-8") as f:
        pred = json.load(f)

    races = pred.get("races", [])
    if verbose:
        mode = "APPLY" if apply else "DRY-RUN"
        ana_tag = " +穴" if (step >= 2 and ana) else ""
        print(f"[ai-marks] {date} {mode} step={step}{ana_tag} mark_set={mark_set} "
              f"weights={weights} races={len(races)}")
        print(f"[ai-marks] predictions vb_refreshed_at={pred.get('vb_refreshed_at')}")
        print()

    now_iso = datetime.now().isoformat(timespec="seconds") if apply else None

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
            entries, weights=weights, step=step, enable_ana=ana,
        )

        # 監査用 composite top3 (馬番:score)
        comp_top3 = sorted(result.composite.items(), key=lambda kv: -kv[1])[:3]
        audit_rec = {
            "race_id": rid,
            "step": step,
            "mark_set": mark_set,
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
            if verbose:
                note = f" ({'; '.join(result.notes)})" if result.notes else ""
                print(f"  {venue} {rno:>2}R  撃ちなし [{result.skip_reason}]{note}")
            if apply:
                append_audit(date, audit_rec, ts=now_iso)
            continue

        n_marked += 1
        n_marks_total += len(result.marks)
        if verbose:
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

        if apply:
            try:
                w = write_ai_marks_to_dat(rid, result.marks, mark_set=mark_set)
                n_written += w
                append_audit(date, audit_rec, ts=now_iso)
            except Exception as e:  # noqa: BLE001
                print(f"    [WARN] DAT書込み失敗 {rid}: {e}", file=sys.stderr)
                audit_rec["write_error"] = str(e)
                append_audit(date, audit_rec, ts=now_iso)

    if verbose:
        print()
        avg = (n_marks_total / n_marked) if n_marked else 0.0
        print(f"[ai-marks] 印あり={n_marked}R (計{n_marks_total}印 / 平均{avg:.1f}印/R)  "
              f"撃ちなし={n_skipped}R", end="")
        if apply:
            print(f"  → markSet={mark_set} に {n_written}頭 書込み + 監査ログ追記")
        else:
            print("  (dry-run: DAT 未書込み)")

    return {"ok": True, "date": date, "races": len(races), "marked": n_marked,
            "skipped": n_skipped, "written": n_written, "marks_total": n_marks_total}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AI評価印 (markSet=2) 書込み")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--weights", type=_parse_weights, default=(1.0, 1.0, 1.0),
                    help="(wW,wP,wA) 既定 1,1,1")
    ap.add_argument("--step", type=int, default=1, choices=(1, 2),
                    help="1=◎のみ / 2=◎○▲△Ⅲ 段差ベース (既定 1)")
    ap.add_argument("--ana", action="store_true",
                    help="穴印を別系統で付加 (step=2 のみ有効、実験扱い)")
    ap.add_argument("--mark-set", type=int, default=_MARK_SLOT_AI,
                    help=f"書込み先 markSet (既定 {_MARK_SLOT_AI}=AI評価)。1 は手動印で禁止")
    ap.add_argument("--apply", action="store_true",
                    help="DAT に実書込み + 監査ログ (未指定は dry-run)")
    args = ap.parse_args(argv)

    res = process_date(args.date, weights=args.weights, step=args.step, ana=args.ana,
                       apply=args.apply, mark_set=args.mark_set)
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""買い軸印 (markSet=8) 書込み CLI。

purchase_ledger v2 ({date}.json) を読み、 実際に購入した 軸(◆)+相手(◇) を抽出して
TARGET DAT の markSet=8 に書く。AI評価印 (markSet=6 ◎○▲△Ⅲ穴) とは別スロットで、
評価と買い目の意味を分離する (設計書 23 案C)。

  --dry-run (既定) : 抽出結果を表示。DAT は書かない。監査ログも書かない。
  --apply          : DAT (markSet=8) に書込み + 監査ログ追記。

★重要 (条件⑥): 買い軸印は **表示用**。購入の正本は purchase_ledger (税務 SoT)。
                印は ledger から導出した派生表示であり、印を編集しても購入記録は変わらない。

設計: docs/auto-purchase/23_AI_MARK_VOTE_SYNC_DESIGN.md (案C)

使用例:
  python -m ml.ai_marks.write_buy_marks --date 2026-05-31            # dry-run
  python -m ml.ai_marks.write_buy_marks --date 2026-05-31 --apply    # markSet=8 へ実書込み
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Windows コンソール (cp932) で — や◆◇ を表示できるよう utf-8 に揃える (runner.py と同様)。
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ml.ai_marks.audit_log import append_audit
from ml.ai_marks.buy_marks import extract_race_buy_marks
from ml.ai_marks.dat_writer import write_buy_marks_to_dat

# 監査レコードに必ず残す注記 (条件⑥)。
DISPLAY_ONLY_NOTE = "買い軸印は表示用 — 購入の正本は purchase_ledger (税務SoT)"
_AUDIT_SUBDIR = "buy_audit"


def _ledger_path(date: str) -> Path:
    root = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))
    return root / "userdata" / "purchase_ledger" / f"{date}.json"


def _venue_rno(race_id: str) -> str:
    """race_id 16桁 → '東京12R' 風の短ラベル (表示用、失敗時は末尾)。"""
    venue = {
        "01": "札", "02": "函", "03": "福", "04": "新", "05": "東",
        "06": "中", "07": "名", "08": "京", "09": "阪", "10": "小",
    }
    try:
        v = venue.get(race_id[8:10], race_id[8:10])
        rno = int(race_id[14:16])
        return f"{v}{rno:>2}R"
    except Exception:  # noqa: BLE001
        return race_id[-4:]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="買い軸印 (markSet=8) 書込み")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true",
                    help="DAT (markSet=8) に実書込み + 監査ログ (未指定は dry-run)")
    args = ap.parse_args(argv)

    lp = _ledger_path(args.date)
    if not lp.exists():
        print(f"[buy-marks] ledger なし: {lp}", file=sys.stderr)
        return 2

    try:
        with open(lp, encoding="utf-8") as f:
            ledger = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[buy-marks] ledger 読込失敗: {e}", file=sys.stderr)
        return 2

    races = ledger.get("races", [])
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[buy-marks] {args.date} {mode} races={len(races)}  ({DISPLAY_ONLY_NOTE})")
    print()

    now_iso = datetime.now().isoformat(timespec="seconds") if args.apply else None

    n_marked = 0
    n_written = 0
    for race in races:
        rbm = extract_race_buy_marks(race)
        if not rbm.marks:
            continue
        n_marked += 1
        label = _venue_rno(rbm.race_id)
        axis_s = "".join(f"◆{u}" for u in rbm.axes) or "(軸なし)"
        partner_s = "".join(f"◇{u}" for u in rbm.partners) or "(相手なし)"
        note = f"  [{'; '.join(rbm.notes)}]" if rbm.notes else ""
        print(f"  {label}  {axis_s} {partner_s}  pf={rbm.n_portfolios}{note}")

        audit_rec = {
            "race_id": rbm.race_id,
            "mark_set": 8,
            "axes": rbm.axes,
            "partners": rbm.partners,
            "marks": {str(u): m for u, m in rbm.marks.items()},
            "n_portfolios": rbm.n_portfolios,
            "notes": rbm.notes,
            "display_only_note": DISPLAY_ONLY_NOTE,
        }

        if args.apply:
            try:
                w = write_buy_marks_to_dat(rbm.race_id, rbm.marks, mark_set=8)
                n_written += w
            except Exception as e:  # noqa: BLE001
                print(f"    [WARN] DAT書込み失敗 {rbm.race_id}: {e}", file=sys.stderr)
                audit_rec["write_error"] = str(e)
            append_audit(args.date, audit_rec, ts=now_iso, subdir=_AUDIT_SUBDIR)

    print()
    if args.apply:
        print(f"[buy-marks] 印あり={n_marked}R → markSet=8 に {n_written}頭 書込み + 監査ログ追記")
    else:
        print(f"[buy-marks] 印あり={n_marked}R  (dry-run: DAT 未書込み)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

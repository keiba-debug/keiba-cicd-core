# -*- coding: utf-8 -*-
"""買い軸印 (markSet=3) 書込み CLI。

purchase_ledger v2 ({date}.json) を読み、 実際に購入した 軸(★)+相手(☆) を抽出して
TARGET DAT の markSet=3 に書く。AI評価印 (markSet=2 ◎○▲△Ⅲ穴) とは別スロットで、
評価と買い目の意味を分離する (設計書 23 案C)。

  --dry-run (既定) : 抽出結果を表示。DAT は書かない。監査ログも書かない。
  --apply          : DAT (markSet=3) に書込み + 監査ログ追記。

★重要 (条件⑥): 買い軸印は **表示用**。購入の正本は purchase_ledger (税務 SoT)。
                印は ledger から導出した派生表示であり、印を編集しても購入記録は変わらない。

設計: docs/auto-purchase/23_AI_MARK_VOTE_SYNC_DESIGN.md (案C)

使用例:
  python -m ml.ai_marks.write_buy_marks --date 2026-05-31            # dry-run
  python -m ml.ai_marks.write_buy_marks --date 2026-05-31 --apply    # markSet=3 へ実書込み
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# Windows コンソール (cp932) で — や★☆ を表示できるよう utf-8 に揃える (runner.py と同様)。
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


def _resolve_dates(base_date: str, catchup_days: int) -> List[str]:
    """基準日 + 直近 catchup_days 日の YYYY-MM-DD を新しい順 (base 含む) で返す。

    settle_ledger._resolve_dates と同慣習。投票後の遅延 settle を翌日以降の run で
    拾うのと同じく、 買い軸印も「前日分が後から確定した portfolio」を冪等 catch-up する。
    """
    base = datetime.strptime(base_date, "%Y-%m-%d")
    return [(base - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(max(0, catchup_days) + 1)]


def _apply_one_date(date: str, *, apply: bool, missing_ledger_ok: bool) -> int:
    """1 日分の買い軸印を抽出 (apply なら markSet=3 に書込み)。 終了コードを返す。

    missing_ledger_ok=True (catch-up/--today) のとき ledger 不在は no-op (exit 0)。
    単発 --date 指定の手動実行では従来通り ledger 不在を exit 2 にする。
    """
    lp = _ledger_path(date)
    if not lp.exists():
        if missing_ledger_ok:
            print(f"[buy-marks] {date} ledger なし → スキップ (非開催/未投票日)")
            return 0
        print(f"[buy-marks] ledger なし: {lp}", file=sys.stderr)
        return 2

    try:
        with open(lp, encoding="utf-8") as f:
            ledger = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[buy-marks] ledger 読込失敗: {e}", file=sys.stderr)
        return 2

    races = ledger.get("races", [])
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[buy-marks] {date} {mode} races={len(races)}  ({DISPLAY_ONLY_NOTE})")
    print()

    now_iso = datetime.now().isoformat(timespec="seconds") if apply else None

    n_marked = 0
    n_written = 0
    for race in races:
        rbm = extract_race_buy_marks(race)
        if not rbm.marks:
            continue
        n_marked += 1
        label = _venue_rno(rbm.race_id)
        axis_s = "".join(f"★{u}" for u in rbm.axes) or "(軸なし)"
        partner_s = "".join(f"☆{u}" for u in rbm.partners) or "(相手なし)"
        note = f"  [{'; '.join(rbm.notes)}]" if rbm.notes else ""
        print(f"  {label}  {axis_s} {partner_s}  pf={rbm.n_portfolios}{note}")

        audit_rec = {
            "race_id": rbm.race_id,
            "mark_set": 3,
            "axes": rbm.axes,
            "partners": rbm.partners,
            "marks": {str(u): m for u, m in rbm.marks.items()},
            "n_portfolios": rbm.n_portfolios,
            "notes": rbm.notes,
            "display_only_note": DISPLAY_ONLY_NOTE,
        }

        if apply:
            try:
                w = write_buy_marks_to_dat(rbm.race_id, rbm.marks, mark_set=3)
                n_written += w
            except Exception as e:  # noqa: BLE001
                print(f"    [WARN] DAT書込み失敗 {rbm.race_id}: {e}", file=sys.stderr)
                audit_rec["write_error"] = str(e)
            append_audit(date, audit_rec, ts=now_iso, subdir=_AUDIT_SUBDIR)

    print()
    if apply:
        print(f"[buy-marks] {date} 印あり={n_marked}R → markSet=3 に {n_written}頭 書込み + 監査ログ追記")
    else:
        print(f"[buy-marks] {date} 印あり={n_marked}R  (dry-run: DAT 未書込み)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="買い軸印 (markSet=3) 書込み")
    ap.add_argument("--date", help="YYYY-MM-DD (省略時は --today)")
    ap.add_argument("--today", action="store_true",
                    help="今日の日付を基準にする (settle_auto と同慣習)")
    ap.add_argument("--catchup-days", type=int, default=0,
                    help="基準日に加えて直近 N 日も処理 (前日確定の遅延 portfolio を拾う冪等 catch-up)")
    ap.add_argument("--apply", action="store_true",
                    help="DAT (markSet=3) に実書込み + 監査ログ (未指定は dry-run)")
    args = ap.parse_args(argv)

    if args.today:
        base_date = datetime.now().strftime("%Y-%m-%d")
    elif args.date:
        base_date = args.date
    else:
        ap.error("--date YYYY-MM-DD または --today が必要")

    dates = _resolve_dates(base_date, args.catchup_days)
    # catch-up (複数日) / --today では ledger 不在を no-op 扱い。 単発 --date のみ厳格 (exit 2)。
    missing_ok = args.today or args.catchup_days > 0
    worst = 0
    for d in dates:
        rc = _apply_one_date(d, apply=args.apply, missing_ledger_ok=missing_ok)
        worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""フル自動投票オーケストレータ (Session 128 で selective 統合)

CLI 一発で:
  1. 買い目仕様 (CLI / JSON / 日付) を FF CSV 書き出し
  2. TARGET メニュー「ファイル → 買い目取り込み」 → 最新 FF CSV を選択
  3. TARGET メニュー「IPAT 連動投票」 → 投票内容確認ダイアログ (多段 fallback)
  4. target_clicker.click_vote_button() で [投票] + [OK] click

設計: docs/auto-purchase/16_TARGET_AUTOCLICK.md §7-8

Usage:
  # 単発: 単勝1点
  python -m ml.target_clicker.runner \\
      --bet 2026052404010301:tansho:5:100 \\
      --confirm

  # 複数件: --bet を複数指定
  python -m ml.target_clicker.runner \\
      --bet 2026052404010301:tansho:5:100 \\
      --bet 2026052404010301:umaren:5/7:200 \\
      --confirm

  # selective_bets.json から一括 (今日の開催)
  python -m ml.target_clicker.runner \\
      --from-date today --amount 100 --confirm

  # 特定日の selective を投票
  python -m ml.target_clicker.runner \\
      --from-date 2026-05-31 --amount 100 --confirm

  # 上限明示 (auto を使わない)
  python -m ml.target_clicker.runner \\
      --from-date today --amount 100 \\
      --max-yen 1000 --max-bets 7 --confirm

注意:
  - --max-yen / --max-bets はデフォルト auto (bets[] 合計と件数で自動設定)
  - bankroll config.json (limit_mode=absolute) の per_day_max_yen を超えると abort
  - --no-bankroll-check で skip 可能だが推奨しない
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import date as date_cls, datetime
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ml.target_clicker.auto_vote import click_vote_button
from ml.target_clicker.ff_writer import FfBet, BET_TYPE_CODE, parse_bet_spec, write_ff_csv


BANKROLL_CONFIG_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "bankroll" / "config.json"


def selective_bets_path_for_date(d: date_cls) -> Path:
    """data3/races/{yyyy}/{mm}/{dd}/selective_bets.json を返す"""
    root = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))
    return root / "races" / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}" / "selective_bets.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--bet", action="append", default=[],
                   help="買い目仕様 race_id:bet_type:horses:amount (複数指定可)")
    p.add_argument("--from-json", type=Path, default=None,
                   help="selective_bets.json のような JSON から一括読み込み")
    p.add_argument("--from-date", default=None,
                   help="YYYY-MM-DD または 'today': data3/races/yyyy/mm/dd/selective_bets.json を自動解決")
    p.add_argument("--amount", type=int, default=100,
                   help="--from-json/--from-date 時の 1 件あたり金額 (default=100)")

    p.add_argument("--confirm", action="store_true",
                   help="実 click (なければ FF CSV 出力だけして click は dry-run)")
    p.add_argument("--max-yen", default=None,
                   help="合計金額上限 (default=auto: bets合計*1.0)")
    p.add_argument("--max-bets", default=None,
                   help="ベット数上限 (default=auto: len(bets))")
    p.add_argument("--no-bankroll-check", action="store_true",
                   help="bankroll config.json の per_day_max_yen チェックをスキップ")
    p.add_argument("--dialog-timeout", type=int, default=60,
                   help="投票ダイアログ待機 (default=60)")
    p.add_argument("--no-menu", action="store_true",
                   help="TARGET メニュー操作をスキップ (FF CSV 書き出しだけ。 click もスキップ)")
    p.add_argument("--no-click", action="store_true",
                   help="投票ダイアログ検出と click をスキップ (FF CSV + menu までで止める)")
    p.add_argument("--ipat-strategies", default=None,
                   help="step3_start_ipat の試行順 (カンマ区切り、 default=menu,uia,win32,shortcut,coords)")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def _resolve_from_date(arg: str) -> Path:
    if arg.lower() == "today":
        d = date_cls.today()
    else:
        d = datetime.strptime(arg, "%Y-%m-%d").date()
    p = selective_bets_path_for_date(d)
    if not p.exists():
        raise FileNotFoundError(f"selective_bets.json not found for {d}: {p}")
    return p


def load_bets_from_args(args: argparse.Namespace) -> list[FfBet]:
    """--bet 複数 + --from-json + --from-date をマージして FfBet list を返す"""
    bets: list[FfBet] = []
    for spec in args.bet:
        bets.append(parse_bet_spec(spec))

    json_paths: list[Path] = []
    if args.from_json:
        json_paths.append(args.from_json)
    if args.from_date:
        json_paths.append(_resolve_from_date(args.from_date))

    for jp in json_paths:
        with open(jp, encoding="utf-8") as f:
            data = json.load(f)
        # selective_bets.json 形式: bets[].race_id, umaban → 単勝 N 円
        for b in data.get("bets", []):
            bets.append(FfBet(
                race_id=str(b["race_id"]),
                bet_type=BET_TYPE_CODE["tansho"],
                umaban=int(b["umaban"]),
                amount=args.amount,
            ))
    return bets


def _resolve_max_limit(arg_value, *, auto_fn, kind: str) -> int:
    """--max-yen / --max-bets の auto 解決 (None or 'auto' なら関数で計算)"""
    if arg_value is None or str(arg_value).lower() == "auto":
        v = auto_fn()
        return v
    try:
        return int(arg_value)
    except ValueError:
        raise ValueError(f"--max-{kind} must be int or 'auto', got: {arg_value!r}")


def _read_bankroll_per_day_limit() -> int:
    """bankroll config.json から per_day_max_yen を読む (limit_mode=absolute 前提)"""
    if not BANKROLL_CONFIG_PATH.exists():
        return 0
    try:
        with open(BANKROLL_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        settings = cfg.get("settings", {})
        if settings.get("limit_mode") == "absolute":
            return int(settings.get("per_day_max_yen", 0))
        return 0
    except Exception:
        return 0


def main() -> int:
    args = parse_args()
    verbose = not args.quiet

    def vprint(msg: str) -> None:
        if verbose:
            print(msg)

    bets = load_bets_from_args(args)
    if not bets:
        print("[error] no bets specified (--bet ... or --from-json ... or --from-date ...)",
              file=sys.stderr)
        return 2

    total_yen = sum(b.amount for b in bets)
    n_bets = len(bets)

    # max-yen / max-bets の auto 解決
    max_yen = _resolve_max_limit(args.max_yen, auto_fn=lambda: total_yen, kind="yen")
    max_bets = _resolve_max_limit(args.max_bets, auto_fn=lambda: n_bets, kind="bets")

    vprint(f"[runner] {n_bets} bets prepared, total={total_yen}円")
    vprint(f"[runner] limits: max_yen={max_yen} max_bets={max_bets}")
    for b in bets:
        vprint(f"  - {b}")

    # bankroll check (per_day_max_yen)
    if not args.no_bankroll_check:
        day_limit = _read_bankroll_per_day_limit()
        if day_limit > 0 and total_yen > day_limit:
            print(f"[error] total={total_yen}円 > bankroll per_day_max_yen={day_limit}円 — abort",
                  file=sys.stderr)
            print("  --no-bankroll-check で skip 可能だが本当に妥当か確認のこと",
                  file=sys.stderr)
            return 5
        if day_limit > 0:
            vprint(f"[runner] bankroll check: OK ({total_yen} <= {day_limit})")

    # Step 1: FF CSV 書き出し
    try:
        ff_path = write_ff_csv(bets)
    except Exception as e:
        print(f"[runner] FF CSV write failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 3
    vprint(f"[runner] FF CSV written: {ff_path}")

    # Step 2: TARGET メニュー操作
    if not args.no_menu:
        try:
            from ml.target_clicker import menu_runner
            ipat_strategies = (args.ipat_strategies.split(",")
                                if args.ipat_strategies else None)
            # step1 (CSV 取込) → step3 (IPAT 起動) の順 (取込確定は投票後)
            if not menu_runner.step1_open_csv_select(ff_path, verbose=verbose):
                print("[runner] step1 (CSV 選択) failed", file=sys.stderr)
                return 4
            if not menu_runner.step3_start_ipat(verbose=verbose,
                                                 strategies=ipat_strategies):
                print("[runner] step3 (IPAT 起動) failed — "
                      "投票内容確認ダイアログまで TARGET で手動進行してください",
                      file=sys.stderr)
                # IPAT 起動失敗 → click も無理。 ここで返す
                return 4
        except Exception as e:
            print(f"[runner] menu operation failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 4

    # --no-menu の場合は click も飛ばす (menu スキップ = TARGET 操作なし = dialog 出ない)
    skip_click = args.no_click or args.no_menu
    if skip_click:
        vprint("[runner] --no-click / --no-menu のため投票ダイアログ click はスキップ")
        return 0

    # Step 3: 投票ダイアログ → click + OK
    result = click_vote_button(
        confirm=args.confirm,
        max_yen=max_yen,
        max_bets=max_bets,
        timeout_sec=args.dialog_timeout,
        verbose=verbose,
    )

    vprint(f"\n[result] success={result.success} action={result.action}")
    if result.content:
        vprint(f"  total={result.content.total_yen}円 bets={result.content.n_bets} "
               f"limit={result.content.limit_yen}円")
    if result.receipt:
        vprint(f"  受付番号={result.receipt.receipt_number} 時刻={result.receipt.receipt_time}")

    # Step 4 (投票成功時のみ): TARGET 買い目データに保存
    #   投票後の「買い目一括処理」 ウィンドウ から OK F10 + 「はい」
    if result.success and result.action == "clicked" and not args.no_menu:
        vprint("\n[runner] TARGET 買い目データへの保存実行 (OK F10 + はい)")
        try:
            from ml.target_clicker import menu_runner
            saved = menu_runner.finalize_save_to_target(verbose=verbose)
            vprint(f"[runner] TARGET 保存: {'成功' if saved else '失敗 (手動で OK 押してください)'}")
        except Exception as e:
            vprint(f"[runner] TARGET 保存例外: {type(e).__name__}: {e}")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI: python -m ml.target_clicker --dry-run / --confirm

例:
  # まず dry-run (検出+検証のみ、 click しない)
  python -m ml.target_clicker --dry-run --timeout 60

  # 実投票 (上限 100円・1ベット を超えたら reject)
  python -m ml.target_clicker --confirm --max-yen 100 --max-bets 1

  # selective 6 件まとめて 100円ずつ投票したいなら max-yen 600 / max-bets 6
  python -m ml.target_clicker --confirm --max-yen 600 --max-bets 6
"""

from __future__ import annotations

import argparse
import sys

from ml.target_clicker.auto_vote import click_vote_button


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--confirm", action="store_true",
                   help="実際に [投票] ボタンを click する (デフォルトは dry-run)")
    p.add_argument("--dry-run", action="store_true",
                   help="dry-run (検出+検証のみ、 click しない)。 デフォルト挙動だが明示用に受け付ける")
    p.add_argument("--max-yen", type=int, default=100,
                   help="合計金額の上限 (超えたら reject、 default=100)")
    p.add_argument("--max-bets", type=int, default=1,
                   help="ベット数の上限 (超えたら reject、 default=1)")
    p.add_argument("--timeout", type=int, default=30,
                   help="投票ダイアログ待機タイムアウト秒 (default=30)")
    p.add_argument("--no-close-result", action="store_true",
                   help="投票後の「投票終了」ダイアログを OK で閉じない (デフォルト: 閉じる)")
    p.add_argument("--result-timeout", type=int, default=10,
                   help="「投票終了」ダイアログ待機タイムアウト秒 (default=10)")
    p.add_argument("--no-notify", action="store_true",
                   help="TTS 音声通知を抑制 (Session 129)")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    result = click_vote_button(
        confirm=args.confirm,
        max_yen=args.max_yen,
        max_bets=args.max_bets,
        timeout_sec=args.timeout,
        close_result=not args.no_close_result,
        result_timeout_sec=args.result_timeout,
        verbose=not args.quiet,
        notify=not args.no_notify,
    )
    if not args.quiet:
        print(f"\n[result] success={result.success} action={result.action} reason={result.reason}")
        if result.content:
            print(f"  total={result.content.total_yen}円 bets={result.content.n_bets} "
                  f"limit={result.content.limit_yen}円")
        if result.receipt:
            print(f"  受付番号={result.receipt.receipt_number} 時刻={result.receipt.receipt_time} "
                  f"受付ベット数={result.receipt.receipt_bets} "
                  f"受付合計={result.receipt.receipt_total_yen}円 closed={result.result_closed}")
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())

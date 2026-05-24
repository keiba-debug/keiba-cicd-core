"""TARGET 投票ダイアログ自動押下 (Session 127)

責務:
  - TARGET の「投票内容確認」 ダイアログを検出
  - 内容の検証 (合計金額 <= max_yen, ベット数 <= max_bets)
  - 検証 OK なら [投票] ボタンを click

使用例:
  python -m ml.target_clicker --dry-run             # 検出してログのみ
  python -m ml.target_clicker --confirm --max-yen 500   # 実投票 (上限500円)

設計背景: docs/auto-purchase/16_TARGET_AUTOCLICK.md (起草予定)
"""

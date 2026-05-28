"""purchase_ledger パッケージ (Session 129)

ledger v2 (docs/auto-purchase/14_LEDGER_SCHEMA.md) の Python writer。
Step 1 (単勝 1 点) の minimal subset 実装。

  - writer: record_tansho_vote() — 投票成功時に portfolio + ticket を追記
  - idempotency: idempotency key + raw_legs 正規化

ファイル配置:
  data3/userdata/purchase_ledger/{YYYY-MM-DD}.json   ← ledger 本体
  data3/userdata/purchase_ledger/_index.jsonl        ← SHA256 追記台帳
"""

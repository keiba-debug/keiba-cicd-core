# -*- coding: utf-8 -*-
"""AI予想印 (markSet=6) — ML予想スコアを ◎ に変換し TARGET 馬印スロットへ書く。

設計: docs/auto-purchase/22_AI_MARKS_DESIGN.md
- assign.py        : スコア → 印 の純関数 (I/O・DB非依存)
- dat_writer.py    : markSet=6 専用 DAT writer (バイト互換)
- write_ai_marks.py: CLI (predictions.json → 印決定 → 監査ログ → DAT書込み)
- cleanup_danger_slot1.py : markSet=1 の残存「危」をピンポイント除去
"""

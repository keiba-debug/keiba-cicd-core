# Phase1 実装指示: 馬の直近3走バックフィルとMD新聞反映（2025-08-23）

## 目的
- organized配下の `seiseki_*.json` を走査し、出走馬ごとに直近3走の履歴特徴量を生成・蓄積し、MD新聞に可視化する。

## 成果物（必須）
1) `accumulator_cli`（新規）: organizedスキャン→直近3走抽出→特徴量算出→蓄積JSON保存
2) `integrator_cli`（改修）: 出走馬ごとに `history_features` を統合
3) `markdown_cli`（改修）: 出走表に「適性/割安」列を追加（表示のみ、簡易算出）

---

## 入出力I/F
- accumulator_cli
  - 入力: `--date 2025/08/23` or `--start-date --end-date`
  - 入力: `--runs 3`（固定値でOK）, `--source organized`（Phase1固定）
  - 出力: `Z:/KEIBA-CICD/data/accumulated/horses/{horse_id}.json`（upsert）
- integrator_cli
  - 入力: 従来通り（integrated JSON生成）
  - 出力: `race_info.horses[].history_features` を出走馬に付帯
- markdown_cli
  - 入力: 従来通り（integrated JSON参照）
  - 出力: 出走表に列追加、展開セクションに1行サマリ

---

## 特徴量定義（最低限）
- `last3f_mean_3`: 直近3走の上り3F平均
- `passing_style`: 直近3走の通過順からタイプ推定（逃/先/差/追）
- `course_distance_perf`: 同コース×距離の成績（`runs/win/in3`）
- `recency_days`: 最終出走からの日数
- `value_flag`: 簡易割安判定（近走指数簡易合成 vs 予想人気の乖離）

---

## 設計メモ
- organized探索: `Z:/KEIBA-CICD/data/organized/YYYY/MM/DD/**/seiseki_*.json`
- 馬ID正規化: shutsuba側のIDとseisekiのIDを正規化（不一致時は馬名+母父等でフォールバックせずスキップ）
- 3走抽出: 日付降順で3件。足りない場合はある分のみ
- 蓄積: 既存ファイルがあれば上書き更新（historyは最大12件まで保持可、Phase1は3件のみでも可）

---

## 実装ステップ
1. accumulator_cli 実装
   - `python -m src.accumulator_cli horse-history backfill --date 2025/08/23 --runs 3 --source organized`
   - ロジック: 対象日の `integrated_*.json` から馬ID集合→organizedを遡り3走収集→特徴量算出→保存
2. integrator_cli 改修
   - `history_features` の読み込み→各馬へマージ（存在しない馬はスキップ）
3. markdown_cli 改修
   - 出走表末尾に `適性/割安` 列を追加
   - 展開セクションに `脚質タイプ: 先行/差し 等 | 直近上り3F: 35.1 | 近走評価: 割安?` を1行表示

---

## 受入基準（AC）
- AC1: accumulator_cli が対象日の全出走馬について直近3走の特徴量を生成
- AC2: integrated JSON に `history_features` が付与される
- AC3: MD新聞に `適性/割安` 列と1行サマリが表示される（体裁崩れ無し）
- AC4: 生成時間の増分が+5%以内

## テスト
- 単体: 特徴量算出（平均/タイプ推定/日数計算）の正当性
- 統合: 出走馬と蓄積JSONのID照合、欠損時スキップの安全性
- E2E: 8/23の1開催で backfill→integrate→markdown の一連実行

---

## 実行コマンド例（PowerShell）
```powershell
# 1) 直近3走バックフィル
python -m src.accumulator_cli horse-history backfill --date 2025/08/23 --runs 3 --source organized

# 2) 統合（history_features 付与）
python -m src.integrator_cli batch --date 2025/08/23

# 3) Markdown生成
python -m src.markdown_cli batch --date 2025/08/23 --organized
```

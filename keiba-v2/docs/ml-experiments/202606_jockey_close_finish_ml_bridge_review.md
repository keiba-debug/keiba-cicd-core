# 騎手接戦分析（`/analysis/jockey-close-finish`）見直しメモ（ML連携観点）

作成日: 2026-06-11  
対象:
- `web/src/app/analysis/jockey-close-finish/page.tsx`
- `web/src/app/api/analysis/jockey-close-finish/route.ts`
- `analysis/jockey_close_finish.py`
- `builders/build_jockey_master.py`
- `ml/features/jockey_features.py`
- `ml/experiment.py`
- `ml/predict.py`

## Rules事前確認

- ✅ 添付ルール確認済み（日本語回答・自律実行方針を適用）
- ⚠️ 指定の必須ルールファイル
  - `.cursor/rules/basic/pmbok_paths.mdc`
  - `.cursor/rules/basic/00_master_rules.mdc`
  はワークスペース探索で未検出（会話内ルールを優先適用）

## 1. 先に結論（優先度順）

1. **接戦分析はML特徴量として既に接続済みだが、分析ページの運用導線が弱く、鮮度管理に課題がある**  
   `jockey_close_win_rate` は `JOCKEY_FEATURES` に採用済み。  
   一方、分析JSON生成は手動スクリプト依存で、UIに再集計ボタンがない。
2. **UIの一部指標が誤解を招く可能性がある**  
   「全体接戦勝率」は定義上ほぼ 50% になりやすく、比較指標として情報量が低い。
3. **サンプルサイズ依存のノイズ制御が弱い**  
   最低接戦数 `>=10` でランキング化しており、下位サンプル帯の率分散が大きい。
4. **ML接続はPIT対応されているが、分析JSONとMLで計算経路が二重化している**  
   学習/推論は PITタイムライン利用、分析ページは `jockeys.json` 派生。  
   値の差異が発生した際に原因追跡が難しい。

## 2. 現状確認（実装・実データ）

### 2.1 ページ/API/生成フロー

- ページは `/api/analysis/jockey-close-finish` を参照。
- APIは `data3/analysis/jockey_close_finish.json` をそのまま返却。
- 生成は `python -m analysis.jockey_close_finish`（手動）。
- 管理画面コマンド (`commands.ts`) に専用アクションがなく、ページ上にも `RecalcButton` が無い。

### 2.2 データ鮮度

- API `created_at`: `2026-03-17T20:37:57`（確認時点）
- 他分析の生成日（2026-06系）と比べると更新遅延がある。

### 2.3 実データの概況

- `summary`:
  - `total_jockeys`: 330
  - `qualified_jockeys`: 152
  - `total_close_finishes`: 15,112
  - `year_from-year_to`: 2020-2026
- 接戦数分布（`close_total>=10`）:
  - `10-19`: 36
  - `20-49`: 34
  - `50-99`: 35
  - `100+`: 47

補足:
- summary の `total_races` は実装上「騎手年次の `runs` 合計」で、レース数というより延べ騎乗数に近い。
- `overall_close_win_rate` は理論上 0.5 に近づく（各接戦で勝者1・敗者1を同数カウントするため）。

### 2.4 ML側の現況

- `ml/features/jockey_features.py` に `jockey_close_win_rate` 実装済み。
- `ml/experiment.py` で `JOCKEY_FEATURES` に含まれ、学習利用。
- `predict.py` / `experiment.py` ともに PITタイムライン (`pit_jockey_tl`) で取得可能。
- つまりML接続自体は成立している（未接続ではない）。

## 3. 主な課題

### 3.1 分析データ更新の運用負債

分析ページは鮮度が価値だが、再集計導線が弱く古いJSONを参照しやすい。  
モデル改善議論の前提データとしては不安定。

### 3.2 指標設計の説明不足（基準値問題）

`overall_close_win_rate` が 50% 近辺になるのは定義上自然。  
これを「良し悪し指標」として表示すると、意思決定に寄与しにくい。

### 3.3 小標本騎手の過大評価リスク

閾値10は探索には有効だが、ランキング用途ではノイズが大きい。  
CIやベイズ収縮がなく、上位の入れ替わりが激しくなり得る。

### 3.4 分析系と学習系の二重実装

- 分析ページ: `jockeys.json` / `jockey_close_finish.json` 系
- ML: PITタイムラインから動的算出

ロジック差・期間差が生じた際、検証コストが高い。

## 4. ML接続の改善方針

## 4.1 フェーズ1（短期）: 分析運用の整備

実施項目:

- 管理画面アクションに `analyze_jockey_close_finish`（相当）を追加
- ページに `RecalcButton` を追加
- ヘッダ表示を改善:
  - `data_created_at`
  - `source_jockey_master_built_at`
  - `data_window`

## 4.2 フェーズ2（中期）: 指標の信頼度を明示

`analysis/jockey_close_finish.py` 出力へ追加:

- `ci95_low/high`（Wilsonまたはベータ事後）
- `effective_n`
- `stability_flag`
- 収縮率（raw→smoothed の差）

UI改善:
- 率単体ではなく `rate ± CI` と `n` をセット表示
- 小標本をランキング上で減衰表示

## 4.3 フェーズ3（中期）: ML向け特徴量の拡張

現在の `jockey_close_win_rate` に加えて以下を検討:

- `jockey_close_total_t-1`（経験量）
- `jockey_close_bias_track_t-1`（芝/ダ差）
- `jockey_close_bias_distance_t-1`（距離帯差）
- `jockey_close_form_trend_t-1`（直近2年 - 過去年）

交差特徴:

- `jockey_close_win_rate_t-1 × race_level`
- `jockey_close_win_rate_t-1 × track_type`
- `jockey_close_win_rate_t-1 × expected_margin_bucket`

## 5. 実装チケット案

1. `web/src/lib/admin/commands.ts` / `api/admin/execute/route.ts`
   - 接戦分析再計算アクション追加
2. `web/src/app/analysis/jockey-close-finish/page.tsx`
   - 再計算ボタン・鮮度メタ表示・CI表示追加
3. `analysis/jockey_close_finish.py`
   - CI/安定性メタ出力
   - `summary.total_races` の定義見直し（実レース数と延べ騎乗数を分離）
4. `ml/features/jockey_features.py`
   - 条件別/トレンド系のPIT特徴を段階追加

## 6. 最小実行セット（まず1スプリント）

まずは以下を優先:

- A. 再集計導線追加（管理画面 + ページ）
- B. `rate + CI + n` 表示に変更
- C. `jockey_close_total_t-1` を追加して既存特徴とアブレーション比較

この3点で、  
分析の鮮度問題を解消しつつ、MLへの接続品質を一段上げられる。


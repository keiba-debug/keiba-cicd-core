# 出遅れ分析（`/analysis/slow-start`）見直しメモ（ML連携観点）

作成日: 2026-06-11  
対象:
- `web/src/app/analysis/slow-start/page.tsx`
- `web/src/app/api/admin/slow-start/route.ts`
- `builders/build_slow_start_analysis.py`
- `ml/features/slow_start_features.py`
- `ml/experiment.py`
- `ml/predict.py`

## Rules事前確認

- ✅ 添付ルール確認済み（日本語回答・自律実行方針を適用）
- ⚠️ 指定の必須ルールファイル
  - `.cursor/rules/basic/pmbok_paths.mdc`
  - `.cursor/rules/basic/00_master_rules.mdc`
  はワークスペース内探索で未検出（会話内ルールを優先適用）

## 1. 先に結論（優先度順）

1. **`/analysis/slow-start` は可視化としては十分だが、ML学習資産としては未接続に近い**  
   `slow_start_features.py` は実装済みだが、`experiment.py` の `SLOW_START_FEATURES` はコメントアウトされ現行モデルで無効。
2. **画面の集計は“説明用の静的集計JSON”で、PIT（時点整合）特徴量として再利用されていない**  
   `slow_start_analysis.json` は全期間再集計成果物であり、そのまま学習投入はリークリスク。
3. **統計的信頼度の指標が不足**  
   騎手・馬の出遅れ率にCIや有意差が無く、小標本ノイズと実シグナルの切り分けが難しい。
4. **説明変数設計が粗く、出遅れの“条件依存性”が欠落**  
   枠順・馬場・距離・発馬地点などの条件分解がなく、平均化で信号が薄まりやすい。

## 2. 現状確認（実装・実データ）

### 2.1 ページ/API/生成の流れ

- `/analysis/slow-start` は3タブ:
  - 騎手ランキング
  - 直近の出遅れ
  - 馬の出遅れ履歴
- APIは `data3/analysis/slow_start_analysis.json` をそのまま返却。
- 再集計は `RecalcButton(actionId="rebuild_slow_start")` で `python -m builders.build_slow_start_analysis` を実行。

### 2.2 `slow_start_analysis.json` の現況

- `generated_at`: 2026-06-05T22:51:08
- `coverage`:
  - `from_date`: 2022-12-24
  - `to_date`: 2026-05-31
  - `races_with_hassou`: 11,217
  - `total_entries`: 156,038
  - `total_slow_starts`: 33,749
- 件数:
  - `jockey_ranking`: 190
  - `recent_incidents`: 33,749
  - `horse_stats`: 15,208

補足:
- 騎手出遅れ率の平均（30騎乗以上）: 約22.3%
- `build_slow_start_analysis.py` は `race_extras.hassou` が存在するレースに限定して集計（品質担保意図は妥当）

### 2.3 ML側の現況

- `ml/features/slow_start_features.py` では次の3特徴量を算出:
  - `horse_slow_start_rate`
  - `horse_slow_start_last5`
  - `horse_slow_start_resilience`
- ただし `ml/experiment.py` では `SLOW_START_FEATURES` がコメントアウトされ、現行学習に未採用。
- `predict.py` / `experiment.py` 内では `compute_slow_start_features()` 自体は呼ばれるが、モデル特徴量としては使われない状態。
- 既存ドキュメントでも「importance 0 により無効化」と明記されている。

## 3. 主な課題

### 3.1 UI分析とML学習の分断

可視化ページで蓄積した出遅れ知見が、現行モデルの改善に接続されていない。  
結果として「見えるが、予測には効かせていない」状態。

### 3.2 変数定義が粗く、条件依存シグナルを落としている

現行3特徴量は馬ごとの平均傾向に寄りすぎており、  
実際に効きやすい `枠順×距離×馬場×脚質` の相互作用を表現できていない。

### 3.3 信頼度/不確実性の不足

騎手・馬の率を提示しても、  
標本サイズに応じた不確実性（CI、事後分布、収縮推定）がないため運用判断がぶれやすい。

### 3.4 PIT設計の明文化不足

`slow_start_features.py` 自体は `race_date` 以前のみ参照でPIT配慮があるが、  
`slow_start_analysis.json` は全期間集計のため、画面数値をそのまま特徴量化するとリークし得る。

## 4. ML接続の改善方針

## 4.1 フェーズ1（短期）: 分析JSONに信頼度メタを追加

`build_slow_start_analysis.py` 出力へ追加:

- `ci95_low/high`（騎手率・馬率）
- `n_effective`（実効標本）
- `stability_flag`（例: n>=80 and CI幅<=閾値）
- `last_updated_at` / `window`（集計期間）

UI改善:
- 率の横に CI と `n` を常時表示
- 小標本（低信頼）に警告バッジ

## 4.2 フェーズ2（中期）: 出遅れ特徴量の再設計（条件付き）

既存3特徴量に加え、以下の条件付き特徴を追加:

- `horse_slow_start_rate_gate_group_t-1`（内/中/外）
- `horse_slow_start_rate_surface_t-1`（芝/ダ）
- `horse_slow_start_rate_distance_band_t-1`
- `jockey_slow_start_rate_t-1`
- `jockey_slow_start_penalty_top3_t-1`（出遅れ時の成績悪化幅）

交差特徴:

- `slow_start_rate_t-1 × draw_group`
- `slow_start_rate_t-1 × avg_first_corner_ratio`
- `jockey_slow_start_rate_t-1 × start_gate_bias`

## 4.3 フェーズ3（中期）: 採用判定をAUC依存からROI中心へ

再導入判定は次を必須化:

- `gap>=k`（k=2..5）ごとの ROI / 回収率 / 件数
- ブートストラップCIでの有意改善確認
- `Win` と `Place` を別評価（出遅れ影響は目的関数依存）

## 5. 実装チケット案

1. `builders/build_slow_start_analysis.py`
   - CI・stability・標本メタ出力の追加
   - 条件別集計（枠/距離帯/馬場）を追加
2. `ml/features/slow_start_features.py`
   - 条件付き `*_t-1` 特徴量へ拡張
   - 騎手側の出遅れ率特徴を追加
3. `ml/experiment.py`
   - `SLOW_START_FEATURES` を段階的再有効化（アブレーション前提）
4. `web/src/app/analysis/slow-start/page.tsx`
   - CI表示、低信頼警告、条件別ビュー追加

## 6. 最小実行セット（まず1スプリント）

まずは以下だけ実施:

- A. `slow_start_analysis.json` に CI + stability + n を追加
- B. `horse_slow_start_rate_t-1` と `jockey_slow_start_rate_t-1` の2特徴のみ再評価
- C. `gap>=k` で ROI差分（CI付き）を出し、採用/棄却を判断

この順なら、既存ページ価値を維持しながら  
低リスクで ML接続を再開できる。


# レースペース分析（/analysis/rpci）見直しメモ（ML連携観点）

作成日: 2026-06-11  
対象: `web/src/app/analysis/rpci/page.tsx`, `analysis/race_type_standards.py`, `ml/features/pace_features.py`, `ml/experiment.py`

## 1. 先に結論（優先度順）

1. **データ整合性の是正が最優先**  
   `courses` は92件だが `race_trend_v2_distribution` は102件。サンプル1〜9件のコースが混在し、UI上の比較とML特徴の安定性を下げている。  
2. **/analysis/rpci の知見が学習に未接続**  
   画面で使っている `by_distance_group_baba` / `runner_adjustments` / `similar_courses` が、現行の学習パイプラインで未使用。  
3. **PIT（時点整合）を前提にしたコース事前分布を作るべき**  
   いまの `race_type_standards.json` は全期間集計で、学習にそのまま投入すると将来情報混入リスクが高い。  
4. **特徴量設計は「単体追加」ではなく gap 条件との交差で評価**  
   既存方針どおり、AUC単独ではなく `gap>=k` 条件下ROIで採否する運用に寄せる。

## 2. 現状確認（2026-06-11時点）

`/api/admin/rpci-standards` 取得結果から確認:

- `courses`: 92
- `distance_groups`: 8
- `lap33_courses`: 88
- `race_trend_v2_distribution`: 102
- `metadata.years`: `2020-2026`
- `metadata.created_at`: `2026-06-05T22:46:58.235152`

差分詳細:

- `race_trend_v2_distribution` のみ存在するコースが10件
- それらはサンプル `1〜9件`（例: `Sapporo_Turf_1000m` は1件）
- `courses` 側の最小サンプルは10件（= 統計採用閾値あり）

## 3. 問題点（ML接続で詰まりやすい点）

### 3.1 データ採用基準の不一致

- `analysis/race_type_standards.py` では `courses` 集計時に実質 `len(records) >= 10` を採用閾値としている。
- 一方で `race_trend_v2_distribution` は全レースを分布化しており、低サンプルコースも混ざる。
- 結果として、画面の「コース別ベース統計」と「傾向分布」が同じ母集団でない。

**影響**

- UIでの比較解釈が揺れる。
- ML側で trend 比率を使うとき、低サンプルノイズが入りやすい。

### 3.2 分析画面の情報が学習特徴へ流れていない

- `ml/experiment.py` の `build_pace_index()` はレースJSONの `pace` 情報のみを読み込む。
- `ml/features/pace_features.py` は馬の過去レース由来特徴を作るが、`race_type_standards.json` のコース事前分布（馬場別/頭数補正/類似コース）を参照していない。

**影響**

- `/analysis/rpci` で発見した「条件別の構造」が、学習時には使われない。
- 分析→改善のループが分断される。

### 3.3 PIT安全な「事前分布」レイヤがない

- `race_type_standards.py` は全期間から基準値を再計算する設計。
- 将来のレースに関する情報を含む統計を、過去期間学習に使うとリークになる。

**影響**

- バックテスト過大評価のリスク。
- OOSで再現性が落ちる。

### 3.4 trend_v2 の扱いが順序化に寄りすぎ

- `pace_features.py` で `trend_v2` を `0..6` の整数エンコードで投入している。
- `sprint`→`sustained_doroashi` を連続序数として扱うのは、意味構造とずれる可能性がある。

**影響**

- 木モデルでは吸収可能な場合もあるが、分割バイアスを誘発しうる。
- 解釈時に「距離」を持つカテゴリとして誤読しやすい。

## 4. 改善案（実装順）

## 4.1 フェーズ1: 整合性と安定性の土台（短期）

1. `race_trend_v2_distribution` 生成時に以下を追加  
   - `sample_count` を明示格納  
   - `is_reliable` フラグ（例: `sample_count >= 30`）  
   - もしくは `courses` に存在するキーのみを既定表示対象にする
2. APIレスポンスに品質メタを追加  
   - `low_sample_courses_count`  
   - `trend_only_courses_count`  
   - `coverage_ratio_lap33` など
3. `/analysis/rpci` 側で低サンプルに薄色/警告バッジ

## 4.2 フェーズ2: ML接続用のPIT特徴量（中期）

`analysis` 由来を直接モデルへ流すのではなく、**時点整合した事前分布特徴**を作る:

- `course_prior_rpci_mean_t-1`
- `course_prior_rpci_stdev_t-1`
- `course_prior_trend_v2_probs_t-1`（7次元）
- `course_prior_lap33_mean_t-1`
- `course_prior_baba_shift_t-1`（良→稍重以上の差）
- `course_prior_runner_offset_t-1`（頭数帯補正）

さらに馬ごとに適性差分を作る:

- `horse_recent_avg_lap33 - course_prior_lap33_mean_t-1`
- `horse_dominant_trend_prob - course_prior_trend_v2_prob`
- `horse_style × course_prior_runner_offset_t-1` 交差

## 4.3 フェーズ3: 評価軸の固定（中期）

既存ドキュメント方針に合わせて、採否基準を固定:

- 主指標: `gap>=6`（または運用閾値）での ROI / CI下限 / 件数
- 従指標: AUC, Logloss, calibration
- 不採用条件: AUC改善のみで gap-ROI を悪化させるもの

## 5. `/analysis/rpci` 画面の改善案（ML接続特化）

追加タブ（例: `ML連携`）として下記を表示:

1. **コース信頼度テーブル**  
   `sample_count`, `stdev`, `is_reliable`, `last_update`, `drift_1y`
2. **特徴量候補エクスポート**  
   コースごとの事前分布をCSV/JSON出力（学習前処理に直結）
3. **適性差分プレビュー**  
   任意馬の過去ラップ特性とコース事前分布との差分を可視化
4. **gap条件での即席効果確認**  
   `gap>=k` フィルタ時のサマリー（件数/ROI/平均人気）を簡易表示

## 6. 実装チケット（そのまま切れる粒度）

1. `analysis/race_type_standards.py`  
   - trend分布に `sample_count` / `is_reliable` 追加  
   - 低サンプル扱いポリシーを明文化
2. `web/src/app/api/admin/rpci-standards/route.ts`  
   - 品質メタ（coverage/stability）を返却
3. `web/src/app/analysis/rpci/page.tsx`  
   - 低サンプル警告UI + ML連携タブ（export導線）
4. `ml/` 側  
   - `course_priors_timeline`（PIT）生成ジョブ  
   - `pace_features.py` に差分特徴を段階導入（ablation必須）

## 7. まず着手する最小セット（推奨）

最初の1スプリントは以下のみで十分:

- A. trend分布の低サンプル明示
- B. APIに品質メタ追加
- C. `gap>=6` での `trend_match` 後付け検証スクリプト追加

これで「見える化」と「採否判断」が先に整い、過剰な特徴量追加で再び市場寄り化するリスクを抑えられる。


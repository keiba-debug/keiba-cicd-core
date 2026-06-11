# 調教分析（`/analysis/trainer-patterns`）見直しメモ（ML連携観点）

作成日: 2026-06-11  
対象:
- `web/src/app/analysis/trainer-patterns/page.tsx`
- `web/src/app/api/admin/trainer-patterns/route.ts`
- `web/src/lib/data/trainer-patterns-reader.ts`
- `analysis/training_analysis.py`
- `analysis/trainer_patterns.py`
- `ml/features/training_features.py`
- `ml/experiment.py`

## Rules事前確認

- ✅ 添付ルール確認済み（日本語回答・自律実行方針を適用）
- ⚠️ 指定の必須ルールファイル
  - `.cursor/rules/basic/pmbok_paths.mdc`
  - `.cursor/rules/basic/00_master_rules.mdc`
  はワークスペース内で探索したが見つからず（現行ルール本文ベースで実施）

## 1. 先に結論（優先度順）

1. **`/analysis/trainer-patterns` は表示・運用支援としては有用だが、ML特徴量への橋渡しは未実装**  
   `training_analysis.json` / `trainer_patterns.json` のパターン情報は、学習パイプラインで直接参照されていない。
2. **現行パターンは“全期間集計”のため、そのまま学習に入れると時点リーク（PIT違反）リスクが高い**  
   `--since 2023` で再集計した固定成果物を当日判断に使う構造。
3. **信頼度判定がヒューリスティック中心で、不確実性管理が弱い**  
   `high/medium/low` は `sample_size` と `lift` 閾値だけで決定され、CI/検定/FDRがない。
4. **識別子の扱いが UI分析とML学習で不一致**  
   分析スクリプトは馬名マッチ（`training_summary`）、ML側は `ketto_num` マッチで設計されており、接続時にズレやすい。

## 2. 現状確認（実装・実データ）

### 2.1 ページ/APIの役割

- `/analysis/trainer-patterns` は2タブ構成:
  - `調教分析`（全体集計）
  - `調教 x 調教師`（調教師別ベストパターン）
- APIは `training_analysis.json` を優先し、なければ `trainer_patterns.json` をフォールバック。
- コメント更新は `trainer_comments.json` へ保存（運用メモ用途）。

### 2.2 生成データの現況（`training_analysis.json`）

- `since`: 2023
- `created_at`: 2026-06-05
- `total_records`: 148,512
- `trainers`: 215
- `best_patterns_total`: 714
- `overall.top3_rate`: 0.219
- 調教師平均 `top3_rate`: 0.2066

パターン信頼度内訳:
- `high`: 220
- `medium`: 358
- `low`: 136

補足:
- `22/215` 調教師は `best_patterns` なし。
- パターン抽出条件は `sample >= 8` かつ  
  `top3_rate >= 0.25` **または** `lift >= 0.05`（実装上は両方チェックに近い運用）。

### 2.3 ML側の現況

- MLは `training_features.py` の個票特徴（`ck_laprank_*`, `oikiri_*`, `rest_weeks` 等）を使用。
- `ml/experiment.py` に `TRAINING_FEATURES` として統合済み。
- 一方で以下は未接続:
  - `training_analysis.json` の `overall` 集計
  - `trainer best_patterns` の一致/不一致
  - パターン信頼度（`confidence` / `lift`）のPIT版特徴量

## 3. 主な課題

### 3.1 UI分析資産とML入力資産の分断

`/analysis/trainer-patterns` で見える「調教師×調教条件の相性」は、  
学習時には使われず、実質的に“可視化専用知見”になっている。

影響:
- 画面上の洞察がモデル精度/ROI改善に還元されない。
- 分析運用と学習運用の二重管理になりやすい。

### 3.2 PIT非対応のまま特徴量化するとリークしやすい

現行 `training_analysis.json` は再計算時点の全履歴集計。  
この値を過去レースの特徴量にそのまま入れると future leakage の温床になる。

影響:
- バックテスト過大評価
- 実運用での再現性低下

### 3.3 統計的な信頼度ガードが不足

`compute_confidence()` は閾値ベース:
- `sample>=50 && lift>=0.05 => high`
- `sample>=20 => medium`
- それ以外 `low`

影響:
- 多重比較（多数パターン探索）で偶然ヒットを拾いやすい。
- 調教師ごとのサンプル偏りを吸収しきれない。

### 3.4 ID設計・マッチング設計の不統一

- `analysis/training_analysis.py` の収集は `horse_name` で `training_summary` と照合。
- ML本線は `ketto_num` 主体で時系列管理。

影響:
- 同名/表記揺れ時の取りこぼし、接続時のキー不整合。
- 将来のPIT特徴量化で実装複雑度が増す。

## 4. ML接続の改善方針

## 4.1 フェーズ1（短期）: 分析JSONを“ML投入可能形式”へ拡張

`training_analysis.py` 出力に次を追加:

- パターンごとの `ci95_low/high`（top3_rate, lift）
- `p_value` または簡易 `z_score`
- `stability_flag`（例: n>=40 かつ CI幅<=閾値）
- `effective_sample_size`
- `last_updated_at` / `data_window`

UI側改善:
- 低信頼パターンの警告表示
- ソート軸を `lift` 単独でなく `lift × reliability` へ

## 4.2 フェーズ2（中期）: PIT版「調教師パターン事前分布」特徴量を新設

新規特徴量（レース日tの直前情報のみ使用）:

- `trainer_pattern_hit_rate_t-1`
- `trainer_pattern_lift_t-1`
- `trainer_pattern_confidence_t-1`
- `trainer_pattern_match_count_t-1`
- `trainer_pattern_best_score_t-1`

組み合わせ特徴:

- `trainer_pattern_lift_t-1 × ck_laprank_score`
- `trainer_pattern_lift_t-1 × oikiri_is_slope`
- `trainer_pattern_hit_rate_t-1 × track_type`

重要:
- `race_date < t` のデータのみで再計算するタイムライン化（PITインデックス）を必須化。

## 4.3 フェーズ3（中期）: 学習・推論で同一ロジックを共通化

推奨構成:

1. `analysis/training_analysis.py` に PITタイムライン出力を追加（例: `trainer_pattern_timeline.parquet`）。
2. `ml/features/` に `trainer_pattern_features.py` を新設し、学習/推論で共通利用。
3. `web/src/lib/data/trainer-patterns-reader.ts` は表示専用に限定し、  
   モデル投入は必ず `ml/features` 経由に一本化。

## 5. 実装チケット案

1. `analysis/training_analysis.py`
   - パターン統計へ CI・検定・安定性フラグを追加
   - `horse_name` マッチ依存を減らし `ketto_num` 優先に寄せる
2. `ml/features/`（新規）
   - `trainer_pattern_features.py` 作成
   - PITタイムラインから `*_t-1` 特徴量を生成
3. `ml/experiment.py`
   - 新特徴量の追加と `MARKET`/`P_ONLY` 区分検証
4. `web/src/app/analysis/trainer-patterns/page.tsx`
   - 信頼度（CI幅・stability）表示を追加
   - “ML接続候補”タグを表示して運用と開発の認識を揃える

## 6. 最小実行セット（まず1スプリント）

まずは以下だけ実施するのが低リスク:

- A. `training_analysis.json` に CI と stability を追加（UI警告込み）
- B. PIT版 `trainer_pattern_lift_t-1` と `trainer_pattern_hit_rate_t-1` の2特徴量だけ試験導入
- C. `gap>=k`（k=2..5）で ROI / 的中率 / サンプル数 / CI を比較し採用判定

この順で進めると、既存UI価値を維持しつつ、  
リークを避けた形でML改善に接続できる。


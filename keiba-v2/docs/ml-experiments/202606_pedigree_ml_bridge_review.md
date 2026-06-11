# 血統分析（`/analysis/pedigree`）見直しメモ（ML連携観点）

作成日: 2026-06-11  
対象:
- `web/src/app/analysis/pedigree/page.tsx`
- `web/src/app/api/admin/pedigree/route.ts`
- `builders/build_sire_stats.py`
- `ml/features/pedigree_features.py`
- `ml/experiment.py`
- `ml/predict.py`

## Rules事前確認

- ✅ 添付ルール確認済み（日本語回答・自律実行方針を適用）
- ⚠️ 指定の必須ルールファイル
  - `.cursor/rules/basic/pmbok_paths.mdc`
  - `.cursor/rules/basic/00_master_rules.mdc`
  はワークスペース探索で未検出（会話内ルールを優先適用）

## 1. 先に結論（優先度順）

1. **血統分析UIは説明力が高い一方で、ML接続は「一部採用・一部意図的除外」の過渡状態**  
   `sire/bms` 系は学習利用されるが、`dam_top3_rate` はリーク/支配リスクで除外されている。
2. **UI表示とML採用セットにズレがある**  
   APIは `dam` も返すが、`/analysis/pedigree` は `sire` と `bms` タブのみ（`dam` は非表示）。
3. **PIT（時点整合）を厳密適用していない運用が残る**  
   `build_pit_sire_timeline()` は実装済みだが、`experiment.py` では無効化され静的index利用が基本。
4. **条件別指標の信頼性はカテゴリで大きく差がある**  
   `dam` は種類数が多くサンプル希薄なため、条件別指標の欠落率が高い（平滑化依存が強い）。

## 2. 現状確認（実装・実データ）

### 2.1 ページ/APIの構成

- ページは `sire_stats_index.json` を取得してランキング表示。
- UIタブは `種牡馬(sire)` / `母父(bms)` の2つ。
- APIレスポンスには `dam` も含まれるが、UIでは使っていない。

### 2.2 `sire_stats_index.json` の現況

- `built_at`: 2026-06-05T22:50:44
- `total_races`: 22,805
- `total_entries`: 311,559
- `matched_entries`: 311,332
- `unique_sires`: 862
- `unique_dams`: 15,050
- `unique_bms`: 1,345
- `cutoff`: `None`（全期間集計）

条件指標の充足率（概算）:
- `sire`: `fresh_advantage` 46.2%, `finish_type_pref` 22.0%
- `bms`: `fresh_advantage` 49.4%, `finish_type_pref` 23.0%
- `dam`: `fresh_advantage` 17.3%, `finish_type_pref` 0.7%

補足:
- `dam` の中央値出走数は 13 と小さく、条件別指標が欠落しやすい。

### 2.3 ML側の現況

- `ml/features/pedigree_features.py` は `sire/dam/bms` の全系列を取得可能。
- `ml/experiment.py` の `PEDIGREE_FEATURES` は以下方針:
  - `sire_top3_rate`, `bms_top3_rate` は採用
  - `dam_top3_rate` は除外（コードコメント上「リーク+22%支配」）
  - `dam_fresh_advantage`, `dam_tight_penalty`, `dam_*_pref/maturity` は採用
- `experiment.py` には `--sire-cutoff` とリーク警告が実装されているが、
  実運用では cutoff 未指定ケースが残ると将来情報混入リスクが残る。
- PITタイムライン関数は存在するが、現状は無効化（AUC悪化/ROI不利の判断による）。

## 3. 主な課題

### 3.1 UIとML採用ポリシーの不整合

UIは `dam` 非表示、MLは `dam` 一部採用という非対称状態。  
運用者が「画面で見えるもの」と「モデルで使うもの」を一致して把握しづらい。

### 3.2 `dam_top3_rate` の扱いがブラックボックス化しやすい

`v5.11` 文書では `dam_top3_rate` が非常に強力とされる一方、  
現行コードでは支配・リーク懸念で除外しており、意思決定根拠が散在。

影響:
- 特徴量採用の再現性・説明責任が弱くなる。
- 将来の再検証時に同じ議論を繰り返しやすい。

### 3.3 PIT運用が「機能はあるが常用されない」状態

`build_pit_sire_timeline()` を無効化して静的集計に依存しているため、  
期間設定や cutoff の使い方を誤るとリークの温床になり得る。

### 3.4 高カーディナリティ領域の不確実性管理不足

`dam` はサンプルが薄い対象が多く、ベイズ平滑化だけでは十分でないケースがある。  
CIや収縮強度の可視化がないため、UI上は過信しやすい。

## 4. ML接続の改善方針

## 4.1 フェーズ1（短期）: 可視化と採用ポリシーの整合

実施項目:

- `/analysis/pedigree` に `dam` タブを追加（ただし低信頼バッジ付き）
- 各指標に `n` と `confidence_band`（CI幅）を表示
- 「モデル採用中/除外中」タグを指標単位で明示
  - 例: `dam_top3_rate` は「除外中（支配/リーク懸念）」を表示

## 4.2 フェーズ2（中期）: PIT-safe 血統特徴量運用の標準化

実施項目:

- 実験時は `--sire-cutoff` を必須化（未指定はエラー化）
- cutoff生成を自動化:
  - 学習レンジに応じて `sire_stats_index_cutoff_YYYYMMDD.json` を事前生成
- `dam_top3_rate` 再採用は以下条件を満たした場合のみ:
  - cutoff適用下での OOT AUC / ROI 改善
  - SHAP支配率が閾値以内
  - `gap>=k` ROI改善がCIで有意

## 4.3 フェーズ3（中期）: 高カーディナリティ対策を強化

実施項目:

- `dam` 系には追加収縮（階層ベイズ/empirical Bayes）を導入
- 特徴量としては point estimate だけでなく:
  - `posterior_mean`
  - `posterior_var`（またはCI幅）
  - `effective_n`
  をセットで投入

これにより「効いているように見えるが不安定」な特徴の過学習を抑制する。

## 5. 実装チケット案

1. `web/src/app/analysis/pedigree/page.tsx`
   - `dam` タブ追加
   - 信頼度/採用状態バッジ追加
2. `builders/build_sire_stats.py`
   - 各指標のCI幅/有効サンプル数を出力
   - cutoff前提の生成フローをCLIで強制
3. `ml/experiment.py`
   - `--sire-cutoff` 必須化
   - `dam_top3_rate` 再評価フラグ（ablation用）追加
4. `docs/ml-experiments/`
   - `dam_top3_rate` 採用可否の判定基準を1ファイルに集約

## 6. 最小実行セット（まず1スプリント）

まずは以下のみ実施が現実的:

- A. `pedigree` UIに `dam` 表示 + 低信頼警告を追加
- B. 実験実行時 `--sire-cutoff` を必須化
- C. `dam_top3_rate` の再評価を cutoff固定のablationで再実施（ROI/CI付き）

この3点で、  
「見える分析」と「安全なML接続」の不整合を最小コストで解消できる。


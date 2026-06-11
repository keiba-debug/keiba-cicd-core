# IDM分析（`/analysis/idm`）見直しメモ（ML連携観点）

作成日: 2026-06-11  
対象:
- `web/src/app/analysis/idm/page.tsx`
- `analysis/idm_standards.py`
- `web/src/lib/data/idm-standards-reader.ts`
- `ml/features/jrdb_features.py`
- `ml/experiment.py`

## 1. 先に結論（優先度順）

1. **`/analysis/idm` の知見が ML 学習に未接続**  
   現状は可視化用途が中心で、`idm_standards.json` を学習特徴量として使っていない。  
2. **集計軸が粗く、条件依存の情報が消えている**  
   スクリプト側では `track` / `month` を収集しているが、出力はクラス集約のみ。  
3. **小サンプルフォールバックは実務上有効だが、統計的には改善余地が大きい**  
   2歳重賞などが全年齢プールへ寄るため、若駒の基準が鈍る。  
4. **ML導入時は PIT（時点整合）必須**  
   全期間再集計の基準値をそのまま学習に使うと将来情報混入リスクがある。

## 2. 現状確認（2026-06-11）

`C:/KEIBA-CICD/data3/analysis/idm_standards.json` の実データを確認:

- `years`: `2023-2026`
- `created_at`: `2026-06-05T22:49:29.900352`
- `total_races`: `11246`
- `by_grade`: `20` カテゴリ
- `by_race_name`: `131` レース
- `sample_count`（カテゴリ単位）: min `44`, median `153.5`, max `3178`
- 小サンプルフォールバックカテゴリ: `5`

補足:
- フロントの `/analysis/idm` は `getIDMStandards()` で静的JSONを直接読み込む構造（API経由なし）。
- 管理画面にも IDＭ専用再計算ボタンはなく、実行導線は `python -m analysis.idm_standards` の手動運用。

## 3. 主要な課題

### 3.1 分析画面と学習パイプラインの断絶

- `analysis/idm_standards.py` はクラス別に「全馬平均」「勝ち馬平均」を整備している。
- しかし `ml/experiment.py` 側は `jrdb_features.py` 由来の馬個別特徴を使用し、`idm_standards.json` を参照していない。

結果:
- `/analysis/idm` で見える「クラス基準との差」が、モデルの説明変数に反映されない。
- 分析で得た示唆を特徴量へ還元するループが弱い。

### 3.2 集計設計が「クラス一軸」に偏る

`scan_data()` では `track` / `month` を保持しているが、`calculate_stats()` はクラス統合のみ。

結果:
- 芝/ダ、季節、開催進行などのコンテキスト差が埋もれる。
- 同クラスでも時期/条件で IDM 分布がズレる可能性を無視する形になる。

### 3.3 フォールバック方式の情報劣化

- 小サンプル（`MIN_SAMPLE_COUNT=30`）時は、`G1_2歳` などを `G1` プールへ置換。
- 安定化には有効だが、2歳戦固有の分布特性を捨てることになる。

結果:
- 若駒カテゴリの基準が「大人寄り」に補正される。
- レース別比較（特に2歳重賞）の精度が落ちやすい。

### 3.4 ML視点での不確実性指標が不足

出力は mean/stdev/median/min/max 中心で、以下が無い:
- 推定誤差（SE, CI）
- 信頼度フラグ（stable/unstable）
- 期間ドリフト（直近年 vs 過去年）

結果:
- そのまま特徴量化すると、ノイズの大きい基準値が混ざる恐れがある。

## 4. ML接続に向けた改善方針

## 4.1 フェーズ1（短期）: 可視化品質とデータ品質の明示

`idm_standards.json` に次を追加:

- `winner_ci95_low/high`, `all_ci95_low/high`
- `stability_flag`（例: `sample_count>=80` かつ `stdev` 閾値内）
- `drift_recent_1y`（直近1年平均との差）

`/analysis/idm` 側:

- 低信頼カテゴリに警告バッジ
- フォールバック使用中カテゴリを明示（既存 `pool` 表示を拡張）
- クラス別ランキングに加え、信頼度順ソートを追加

## 4.2 フェーズ2（中期）: PIT安全な基準値特徴量を生成

`analysis/idm_standards.py` の別系統として、学習用に時点整合した事前分布を生成:

- `course_or_grade_prior_idm_mean_t-1`
- `course_or_grade_prior_winner_idm_mean_t-1`
- `prior_gap_win_minus_all_t-1`
- `prior_stability_t-1`

馬レベルの差分特徴:

- `jrdb_pre_idm - prior_winner_idm_mean_t-1`
- `jrdb_idm_avg3 - prior_all_idm_mean_t-1`
- `jrdb_idm_last - prior_winner_idm_mean_t-1`

これで「馬の能力値」と「クラス期待値」の相対関係を直接モデル化できる。

## 4.3 フェーズ3（中期）: 市場寄り化を避ける運用ルール

既存方針に合わせ、採否は以下で固定:

- 主指標: `gap>=k` 条件下 ROI / CI下限 / bet件数
- 従指標: AUC, calibration
- 不採用条件: AUCのみ改善し、gap条件ROIが悪化

補足:
- `jrdb_pre_idm` は既に MARKET扱いで、VALUEモデルから除外されている。  
  新規IDM特徴も「市場相関」を先に監査してから投入する。

## 5. 実装チケット案（この順で着手）

1. `analysis/idm_standards.py`
   - CI/安定性/ドリフト指標を出力
   - フォールバックを固定置換から「部分プーリング近似（重み混合）」へ拡張
2. `web/src/app/analysis/idm/page.tsx`
   - 信頼度表示、ドリフト列、フィルタ（クラス帯/信頼度）追加
3. 学習前処理（新規）
   - `idm_priors_timeline` 生成（PIT対応）
4. `ml/features/jrdb_features.py` または派生特徴量モジュール
   - IDM相対特徴（priorとの差分）を段階投入

## 6. 最小実行セット（まず1スプリント）

最初は以下だけで十分:

- A. `idm_standards.json` に信頼度メタ（CI + stability）追加
- B. `/analysis/idm` に「低信頼/フォールバック」可視化
- C. 学習投入前に後付け検証スクリプトで  
  `gap>=6` × `IDM相対優位` のROI差分を確認

この3点を先に終えると、実装コストを抑えつつ「IDM分析をMLへ接続する前提」が揃う。


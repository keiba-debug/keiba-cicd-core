# KeibaCICD モデル構成 & 特徴量定義書

**予測パイプライン experiment.py / predict.py で使用する全モデル・全特徴量の一覧**

最終更新: 2026-02-22 (Session 43)

---

## 0. バージョニング方針

### 統一バージョン（v5.x）
特徴量パイプラインの変更は全5モデルに影響する。新特徴量の追加・既存特徴量の変更時は全モデルを再訓練し、統一バージョンを付与する。

```
v5.5 → 全モデル再訓練（新特徴量追加）
```

### チャクラサフィックス（v5.x-ckN）
チャクラ固有の変更（target設計、損失関数、レースレベル補正等）は分類4モデルに影響しない。チャクラのみ再訓練し、サフィックスで区別する。

```
v5.5-ck2 → チャクラだけtarget設計を変更
```

### 将来の分離
絶対能力指数（レースレベル補正込み）に移行する段階で、チャクラの訓練データ構造自体が分類モデルと異なるため、独立バージョン管理に移行する。

```
分類モデル: v6.0    チャクラ: ck-1.0
```

---

## 1. モデル構成

### 1.1 5モデル一覧

| 表示名 | 内部キー | 役割 | 特徴量セット | ラベル | 手法 |
|--------|----------|------|-------------|--------|------|
| **好走 市場** | accuracy / Model A | 3着内予測（全特徴量） | FEATURE_COLS_ALL | is_top3 | LightGBM 分類 |
| **好走 独自** | value / Model V | 3着内予測（市場系除外） | FEATURE_COLS_VALUE | is_top3 | LightGBM 分類 |
| **勝利 市場** | win_accuracy / Model W | 1着予測（全特徴量） | FEATURE_COLS_ALL | is_win | LightGBM 分類 |
| **勝利 独自** | win_value / Model WV | 1着予測（市場系除外） | FEATURE_COLS_VALUE | is_win | LightGBM 分類 |
| **チャクラ** | regression / Reg B | 能力予測（着差回帰） | FEATURE_COLS_VALUE | target_margin | LightGBM 回帰 (Huber) |

### 1.2 モデルの役割

**市場モデル（好走 市場 / 勝利 市場）**: オッズ・人気を含む全特徴量で予測。市場の合意を反映した確率を出力。

**独自モデル（好走 独自 / 勝利 独自）**: 市場系特徴量を除外して予測。独自の能力評価に基づく確率を出力。

**Value Bet戦略**: 独自モデルが高評価 × 市場モデルが低評価 → 市場が過小評価している馬（Gap = 人気順位 - VR）。

**チャクラ（能力予測）**: 勝ち馬との着差（秒）を回帰予測。値が小さいほど能力が高い。bet_engineのmarginフィルタとして使用（gap>=5 & margin<=1.2 で Win ROI 119.9%）。将来的に絶対能力指数へ発展予定。

### 1.3 キャリブレーション

| モデル | 手法 | 効果 |
|--------|------|------|
| 好走 市場 / 独自 | — | ECE < 0.005（キャリブレーション良好） |
| 勝利 市場 / 独自 | IsotonicRegression | ECE 0.13 → 0.003（劇的改善） |
| チャクラ | — | 回帰のため ECE 不適用 |

- EV計算には calibrated 確率を使用。ランキングは raw（順序不変）。

---

## 2. 特徴量一覧（FEATURE_COLS_ALL）

### 2.1 基本特徴量 (BASE_FEATURES)

**生成:** `ml/features/base_features.py` — `extract_base_features(entry, race)`

**データソース:** レースJSON (race_{race_id}.json)

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| age | 馬齢 | int | 2〜10 | 0 |
| sex | 性別 (牡=0, 牝=1, セ=2) | int | 0〜2 | 0 |
| futan | 斤量 | float | 50〜60 | 0 |
| horse_weight | 馬体重 | int | 400〜550 | 0 |
| horse_weight_diff | 馬体重増減 | int | -30〜+30 | 0 |
| wakuban | 枠番 | int | 1〜8 | 0 |
| distance | 距離 (m) | int | 1000〜3600 | 0 |
| track_type | 芝=0, ダ=1 | int | 0, 1 | 0 |
| track_condition | 馬場 (良=0〜不良=3) | int | 0〜3 | 0 |
| entry_count | 出走頭数 | int | 4〜18 | 0 |
| month | 開催月 | int | 1〜12 | 0 |
| nichi | 開催日 (1=開幕週〜8=最終週) | int | 1〜8 | 0 |

---

### 2.2 市場系特徴量（独自モデル・チャクラでは除外）

| 特徴量名 | 説明 | 型 | 生成箇所 |
|----------|------|-----|----------|
| odds | 単勝オッズ | float | base_features / DB上書き |
| popularity | 人気順 | int | base_features / DB上書き |
| odds_rank | レース内オッズ順位 | float | groupby rank |
| popularity_trend | 今走人気 − 前走人気 | int | rotation_features |

---

### 2.3 過去走特徴量 (PAST_FEATURES)

**生成:** `ml/features/past_features.py` — `compute_past_features()`

**データソース:** horse_history_cache.json（race_date より前のみ使用）

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| avg_finish_last3 | 直近3走の平均着順 | float | 1〜18 | -1 |
| best_finish_last5 | 直近5走の最高着順 | int | 1〜18 | -1 |
| last3f_avg_last3 | 直近3走の上がり3F平均 | float | 33〜42s | -1 |
| days_since_last_race | 前走からの日数 | int | 7〜365 | -1 |
| win_rate_all | 通算勝率 | float | 0〜1 | -1 |
| top3_rate_all | 通算複勝率 | float | 0〜1 | -1 |
| total_career_races | 通算出走数 | int | 0〜100+ | 0 |
| recent_form_trend | 直近3走の着順トレンド | int | -15〜+15 | -1 |
| venue_top3_rate | 同会場での複勝率 | float | 0〜1 | -1 |
| track_type_top3_rate | 同トラック複勝率 | float | 0〜1 | -1 |
| distance_fitness | ±200m以内の複勝率 | float | 0〜1 | -1 |
| prev_race_entry_count | 前走出走頭数 | int | 4〜18 | -1 |
| entry_count_change | 出走頭数の変化 | int | -14〜+14 | -1 |
| best_l3f_last5 | 直近5走の上がり3F最速 | float | 33〜42s | None |
| finish_std_last5 | 直近5走着順の標準偏差 | float | 0〜8 | None |
| comeback_strength_last5 | 道中→着順の回復度 | float | -1〜1 | None |
| win_rate_smoothed | ベイズ平滑化勝率 (α=1, β=12) | float | 0.08前後 | None |
| top3_rate_smoothed | ベイズ平滑化複勝率 (α=2.5, β=7.5) | float | 0.25前後 | None |
| venue_top3_rate_smoothed | 会場別ベイズ平滑化複勝率 | float | 0〜1 | None |
| track_type_top3_rate_smoothed | 芝/ダ別ベイズ平滑化複勝率 | float | 0〜1 | None |
| distance_fitness_smoothed | 距離適性ベイズ平滑化複勝率 | float | 0〜1 | None |
| career_stage | キャリア段階 (0=初出走〜4=11+) | int | 0〜4 | 0 |

---

### 2.4 調教師特徴量 (TRAINER_FEATURES)

**生成:** `ml/features/trainer_features.py`

**データソース:** trainers.json

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| trainer_win_rate | 調教師の勝率 | float | 0〜0.15 | -1 |
| trainer_top3_rate | 調教師の複勝率 | float | 0〜0.5 | -1 |
| trainer_venue_top3_rate | 同会場での複勝率 | float | 0〜0.5 | -1 |

---

### 2.5 騎手特徴量 (JOCKEY_FEATURES)

**生成:** `ml/features/jockey_features.py`

**データソース:** jockeys.json

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| jockey_win_rate | 騎手の勝率 | float | 0〜0.15 | -1 |
| jockey_top3_rate | 騎手の複勝率 | float | 0〜0.5 | -1 |
| jockey_venue_top3_rate | 同会場での複勝率 | float | 0〜0.5 | -1 |

---

### 2.6 脚質特徴量 (RUNNING_STYLE_FEATURES)

**生成:** `ml/features/running_style_features.py`

**データソース:** horse_history の corners

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| avg_first_corner_ratio | 直近5走の1角通過比率平均 | float | 0〜1 | -1 |
| avg_last_corner_ratio | 直近5走の最終角通過比率平均 | float | 0〜1 | -1 |
| position_gain_last5 | (1角順位−着順)/頭数 平均 | float | -0.5〜0.5 | -1 |
| front_runner_rate | 直近5走で1角3番手以内率 | float | 0〜1 | -1 |
| pace_sensitivity | 先行時と非先行時の着順差 | float | -5〜+5 | -1 |
| closing_strength | 最終角順位−着順 平均 | float | -10〜+10 | -1 |
| running_style_consistency | 1角比率の標準偏差 | float | 0〜0.5 | -1 |
| last_race_corner1_ratio | 前走の1角順位/頭数 | float | 0〜1 | -1 |

---

### 2.7 ローテ・コンディション特徴量 (ROTATION_FEATURES)

**生成:** `ml/features/rotation_features.py`

**データソース:** horse_history、race

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 | 独自モデル |
|----------|------|-----|------|--------|-----------|
| futan_diff | 今走−前走斤量 | float | -5〜+5 | -1 | ○ |
| futan_diff_ratio | 斤量変化率 | float | -0.1〜0.1 | -1 | ○ |
| weight_change_ratio | 馬体重変化率 | float | -0.1〜0.1 | -1 | ○ |
| prev_race_popularity | 前走人気順 | int | 1〜18 | -1 | ○ |
| jockey_change | 騎手乗り替わり | int | 0, 1 | None | ○ |
| prev_grade_level | 前走グレードレベル | int | 1〜10 | None | × 市場系 |
| grade_level_diff | 今走−前走グレード差 | int | -9〜+9 | None | × 市場系 |
| venue_rank_diff | 会場ランク差 | int | -4〜+4 | None | × 市場系 |
| is_koukaku_venue | 降格ローテ: 栗東馬割合 | int | 0, 1 | None | ○ |
| is_koukaku_female | 降格ローテ: 混合→牝限 | int | 0, 1 | None | ○ |
| is_koukaku_season | 降格ローテ: 冬春→夏 | int | 0, 1 | None | ○ |
| is_koukaku_age | 降格ローテ: 馬齢 | int | 0 | None | ○ |
| is_koukaku_distance | 降格ローテ: 距離短縮 | int | 0, 1 | None | ○ |
| is_koukaku_turf_to_dirt | 降格ローテ: 芝→ダート | int | 0, 1 | None | ○ |
| is_koukaku_handicap | 降格ローテ: ハンデ戦 | int | 0, 1 | None | ○ |
| koukaku_rote_count | 降格ローテ該当数 | int | 0〜5 | None | ○ |

---

### 2.8 ペース特徴量 (PACE_FEATURES)

**生成:** `ml/features/pace_features.py`

**データソース:** race_trend_index.json、horse_history

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| avg_race_rpci_last3 | 直近3走のRPCI平均 | float | 45〜55 | -1 |
| prev_race_rpci | 前走のRPCI | float | 45〜55 | -1 |
| consumption_flag | 前走RPCI≤46 & 間隔≤21日 | int | 0, 1 | 0 |
| last3f_vs_race_l3_last3 | (馬L3−レースL3) 3走平均 | float | -3〜+3 | -1 |
| steep_course_experience | 急坂場出走割合 | float | 0〜1 | -1 |
| steep_course_top3_rate | 急坂場での複勝率 | float | 0〜1 | -1 |
| l3_unrewarded_rate_last5 | 上がり速いのに着外率 | float | 0〜1 | None |
| avg_lap33_last3 | 直近3走の平均33ラップ | float | -6〜+2 | None |
| prev_race_lap33 | 前走の33ラップ | float | -6〜+2 | None |
| best_trend_top3_rate | trend_v2別で最良の複勝率 | float | 0〜1 | None |
| worst_trend_top3_rate | trend_v2別で最悪の複勝率 | float | 0〜1 | None |
| trend_versatility | 適性のばらつき | float | 0〜0.3 | None |

---

### 2.9 調教特徴量 (TRAINING_FEATURES)

**生成:** `ml/features/training_features.py`

**データソース:** kb_ext (keibabook)、training_summary.json (CK_DATA)

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 | 独自モデル |
|----------|------|-----|------|--------|-----------|
| training_arrow_value | 調教矢印 | int | -2〜+2 | -1 | ○ |
| oikiri_5f | 追い切り5Fタイム | float | 58〜72s | -1 | ○ |
| oikiri_3f | 追い切り3Fタイム | float | 34〜42s | -1 | ○ |
| oikiri_1f | 追い切り1Fタイム | float | 11〜14s | -1 | ○ |
| oikiri_intensity_code | 脚色 | int | -1〜4 | -1 | ○ |
| oikiri_has_awase | 併せ馬 | int | 0, 1 | -1 | ○ |
| training_session_count | セッション数 | int | 1〜10 | -1 | ○ |
| rest_weeks | 休養週数 | int | 1〜8 | -1 | ○ |
| oikiri_is_slope | 坂路コース | int | 0, 1 | -1 | ○ |
| kb_rating | KBレーティング | float | 40〜75 | None | ○ |
| ck_laprank_score | CK lapRankスコア (1〜16) | int | 1〜16 | None | × 市場系 |
| ck_laprank_class | lapRankクラス (D=0〜SS=5) | int | 0〜5 | None | × 市場系 |
| ck_laprank_accel | 加速コード | int | -1〜1 | None | × 市場系 |
| ck_time_rank | タイムランク | int | 1〜5 | None | × 市場系 |
| ck_final_laprank_score | 最終追切lapRankスコア | int | 1〜16 | None | × 市場系 |
| ck_final_time4f | 最終追切4Fタイム | float | 48〜72s | None | × 市場系 |
| ck_final_lap1 | 最終追切ラスト1F | float | 11〜17s | None | × 市場系 |

---

### 2.10 KB印特徴量 (KB_MARK_FEATURES)

**データソース:** kb_ext

| 特徴量名 | 説明 | 型 | 独自モデル |
|----------|------|-----|-----------|
| kb_mark_point | KB印ポイント | float | × 市場系 |
| kb_aggregate_mark_point | KB総合印ポイント | float | × 市場系 |

---

### 2.11 スピード指数特徴量 (SPEED_FEATURES)

**生成:** `ml/features/speed_features.py`

**データソース:** kb_ext → speed_indexes

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| speed_idx_latest | 前走のスピード指数 | float | 40〜75 | -1 |
| speed_idx_best5 | 直近5走の最高値 | float | 40〜75 | -1 |
| speed_idx_avg3 | 直近3走の平均 | float | 40〜75 | -1 |
| speed_idx_trend | 前走−2走前 | float | -15〜+15 | 0 |
| speed_idx_std | 直近5走の標準偏差 | float | 0〜10 | -1 |

---

### 2.12 コメントNLP特徴量 (COMMENT_FEATURES)

**生成:** `ml/features/comment_features.py`

**データソース:** kb_ext → stable_comment, previous_race_interview

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 | 独自モデル |
|----------|------|-----|------|--------|-----------|
| comment_stable_condition | 厩舎談話の仕上がり度 | int | -3〜+3 | None | ○ |
| comment_stable_confidence | 厩舎談話の自信度 | int | -3〜+3 | None | ○ |
| comment_stable_mark | ヘッダーマーク | int | 0〜4 | None | × 市場系 |
| comment_stable_excuse_flag | 言い訳キーワード有無 | int | 0/1 | None | ○ |
| comment_interview_condition | 前走インタビュー仕上がり | int | -3〜+3 | None | ○ |
| comment_interview_excuse_score | 前走不利・敗因スコア | float | -3〜+3 | None | ○ |
| comment_memo_condition | 次走メモ仕上がり | int | -3〜+3 | None | ○ |
| comment_memo_trouble_score | 次走メモトラブルスコア | float | -3〜+3 | None | ○ |
| comment_has_stable | 厩舎談話あり | int | 0, 1 | None | ○ |
| comment_has_interview | インタビューあり | int | 0, 1 | None | ○ |

---

### 2.13 出遅れ特徴量 (SLOW_START_FEATURES) — 無効化

実験済み・importance 0 のため現行では無効化。

---

## 3. 独自モデル・チャクラで除外される市場系特徴量 (MARKET_FEATURES)

```
odds, popularity, odds_rank, popularity_trend
kb_mark_point, kb_aggregate_mark_point
ck_laprank_score, ck_laprank_class, ck_laprank_accel
ck_time_rank, ck_final_laprank_score, ck_final_time4f, ck_final_lap1
prev_grade_level, grade_level_diff, venue_rank_diff
comment_stable_mark
win_rate_smoothed, top3_rate_smoothed
venue_top3_rate_smoothed, track_type_top3_rate_smoothed, distance_fitness_smoothed
```

---

## 4. データソース一覧

| ソース | パス/取得元 | 用途 |
|--------|-------------|------|
| レースJSON | data3/races/YYYY/MM/DD/race_{id}.json | 基本・出走表 |
| horse_history_cache | build_horse_history 出力 | 過去走・脚質・ペース |
| trainers.json | data3/analysis/ | 調教師統計 |
| jockeys.json | data3/analysis/ | 騎手統計 |
| race_trend_index.json | data3/analysis/ | RPCI, trend_v2, lap33 |
| kb_ext | data3/keibabook/YYYY/MM/DD/kb_ext_{id}.json | 調教・スピード・コメント |
| training_summary | data3/races/YYYY/MM/DD/temp/training_summary.json | CK_DATA lapRank |
| DB事前オッズ | mykeibadb | odds, popularity |

---

## 5. 特徴量数サマリ

| カテゴリ | 数 | 市場モデル | 独自モデル/チャクラ |
|----------|-----|-----------|-------------------|
| 基本 | 12 | ○ | ○ |
| 市場系 | 4 | ○ | × |
| 過去走 | 22 | ○ | 16 (smoothed等除外) |
| 調教師 | 3 | ○ | ○ |
| 騎手 | 3 | ○ | ○ |
| 脚質 | 8 | ○ | ○ |
| ローテ | 16 | ○ | 13 |
| ペース | 12 | ○ | ○ |
| 調教 | 17 | ○ | 10 |
| KB印 | 2 | ○ | × |
| スピード | 5 | ○ | ○ |
| コメント | 10 | ○ | 9 |
| **合計** | **約110** | **FEATURE_COLS_ALL** | **FEATURE_COLS_VALUE** |

---

## 6. 実装ファイル対応表

| カテゴリ | ファイル | 主な関数 |
|----------|----------|----------|
| 基本 | base_features.py | extract_base_features |
| 過去走 | past_features.py | compute_past_features |
| 調教師 | trainer_features.py | get_trainer_features |
| 騎手 | jockey_features.py | get_jockey_features |
| 脚質 | running_style_features.py | compute_running_style_features |
| ローテ | rotation_features.py | compute_rotation_features |
| ペース | pace_features.py | compute_pace_features |
| 調教 | training_features.py | compute_training_features |
| スピード | speed_features.py | compute_speed_features |
| コメント | comment_features.py | compute_comment_features |

---

## 7. EV計算・bet_engine

### EV計算
- **単勝EV** = P(win) × 単勝オッズ（勝利 独自モデル、正規化後）
- **複勝EV** = P(top3) × 複勝最低オッズ（好走 独自モデル、**生確率 pred_b_raw を使う**、sum≈3.0）
- 頭向き度 = P(win) / P(top3)

### bet_engine（購入プラン）
- **Win**: rule-based（gap + チャクラmarginフィルタ）。ECEが悪くKelly不適。
- **Place**: EV + Kelly sizing。ECEが良好。
- **最適プリセット**: win_only（gap>=5, margin<=1.2, ROI 119.9%）

### 4プリセット
| プリセット | 内部キー | 内容 |
|-----------|---------|------|
| 単勝のみ | win_only | gap>=5 & margin<=1.2 の単勝のみ |
| 堅実 | conservative | 厳格条件の単勝+複勝 |
| 標準 | standard | 標準条件の単勝+複勝 |
| 攻め | aggressive | 緩い条件で積極投資 |

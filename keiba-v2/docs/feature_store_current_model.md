# [ARCHIVED] KeibaCICD 現行モデル 特徴量定義書

> **このドキュメントはアーカイブ済みです（2026-02-22 Session 43）。**
> 後継ドキュメント → `keiba-v2/docs/models_and_features.md`

**実験パイプライン experiment.py で使用する特徴量の一覧**

最終更新: 2026年2月

---

## 1. モデル構成概要

| モデル | 用途 | 特徴量セット | ラベル |
|--------|------|--------------|--------|
| **Model A** | 全特徴量（市場系含む） | FEATURE_COLS_ALL | is_top3 / is_win |
| **Model B (Value)** | VB用（市場系除外） | FEATURE_COLS_VALUE | is_top3 / is_win |
| **Model W** | 単勝予測 | PARAMS_W (Aベース) | is_win |
| **Model WV** | 単勝+複勝 | PARAMS_WV (Bベース) | is_win |
| **Reg B** | 着差回帰 | FEATURE_COLS_VALUE | target_margin |

---

## 2. 特徴量一覧（FEATURE_COLS_ALL）

### 2.1 基本特徴量 (BASE_FEATURES)

**生成:** `ml/features/base_features.py` — `extract_base_features(entry, race)`

**データソース:** レースJSON (race_{race_id}.json) の entries / race

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| age | 馬齢 | int | 2〜10程度 | 0 |
| sex | 性別 (牡=0, 牝=1, セ=2) | int | 0, 1, 2 | 0 |
| futan | 斤量 | float | 50〜60程度 | 0 |
| horse_weight | 馬体重 | int | 400〜550程度 | 0 |
| horse_weight_diff | 馬体重増減 | int | -30〜+30程度 | 0 |
| wakuban | 枠番 | int | 1〜8 | 0 |
| distance | 距離 (m) | int | 1000〜3600 | 0 |
| track_type | 芝=0, ダ=1 | int | 0, 1 | 0 |
| track_condition | 馬場 (良=0, 稍重=1, 重=2, 不良=3) | int | 0〜3 | 0 |
| entry_count | 出走頭数 | int | 4〜18 | 0 |
| month | 開催月 | int | 1〜12 | 0 |
| nichi | 開催日 (race_id[12:14], 1=開幕週〜8=最終週) | int | 1〜8 | 0 |

---

### 2.2 市場系特徴量 (Model Bでは除外)

| 特徴量名 | 説明 | 型 | 生成箇所 |
|----------|------|-----|----------|
| odds | 単勝オッズ | float | base_features / DB事前オッズで上書き |
| popularity | 人気順 | int | base_features / DB ninki で上書き |
| odds_rank | レース内オッズ順位 (1=本命) | float | `df.groupby('race_id')['odds'].rank(method='min')` |
| popularity_trend | 今走人気 − 前走人気 (正=人気落ち) | int | rotation_features |

---

### 2.3 過去走特徴量 (PAST_FEATURES)

**生成:** `ml/features/past_features.py` — `compute_past_features()`

**データソース:** horse_history_cache.json（race_date より前の走歴のみ使用）

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| avg_finish_last3 | 直近3走の平均着順 | float | 1〜18 | -1 |
| best_finish_last5 | 直近5走の最高着順（最小値） | int | 1〜18 | -1 |
| last3f_avg_last3 | 直近3走の上がり3F平均 | float | 33〜42秒程度 | -1 |
| days_since_last_race | 前走からの間隔（日数） | int | 7〜365 | -1 |
| win_rate_all | 通算勝率 | float | 0〜1 | -1 |
| top3_rate_all | 通算複勝率 | float | 0〜1 | -1 |
| total_career_races | 通算出走数 | int | 0〜100+ | 0 |
| recent_form_trend | 直近3走の着順トレンド（正=上昇傾向） | int | -15〜+15 | -1 |
| venue_top3_rate | 同会場での複勝率 | float | 0〜1 | -1 |
| track_type_top3_rate | 同トラック（芝/ダ）での複勝率 | float | 0〜1 | -1 |
| distance_fitness | ±200m以内の複勝率 | float | 0〜1 | -1 |
| prev_race_entry_count | 前走出走頭数 | int | 4〜18 | -1 |
| entry_count_change | 出走頭数の変化 | int | -14〜+14 | -1 |
| best_l3f_last5 | 直近5走の上がり3F最速 | float | 33〜42秒 | None |
| finish_std_last5 | 直近5走着順の標準偏差 | float | 0〜8 | None |
| comeback_strength_last5 | 道中最悪順位から着順への回復度 | float | -1〜1 | None |
| win_rate_smoothed | ベイズ平滑化勝率 (α=1, β=12) | float | 0.08前後 | None |
| top3_rate_smoothed | ベイズ平滑化複勝率 (α=2.5, β=7.5) | float | 0.25前後 | None |
| venue_top3_rate_smoothed | 会場別ベイズ平滑化複勝率 | float | 0〜1 | None |
| track_type_top3_rate_smoothed | 芝/ダ別ベイズ平滑化複勝率 | float | 0〜1 | None |
| distance_fitness_smoothed | 距離適性ベイズ平滑化複勝率 | float | 0〜1 | None |
| career_stage | キャリア段階 (0=初出走, 1=2戦目, 2=3-5戦, 3=6-10戦, 4=11+) | int | 0〜4 | 0 |

---

### 2.4 調教師特徴量 (TRAINER_FEATURES)

**生成:** `ml/features/trainer_features.py` — `get_trainer_features(trainer_code, venue_code, trainer_index)`

**データソース:** trainers.json

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| trainer_win_rate | 調教師の勝率 | float | 0〜0.15 | -1 |
| trainer_top3_rate | 調教師の複勝率 | float | 0〜0.5 | -1 |
| trainer_venue_top3_rate | 同会場での複勝率 (10走以上) | float | 0〜0.5 | -1 |

---

### 2.5 騎手特徴量 (JOCKEY_FEATURES)

**生成:** `ml/features/jockey_features.py` — `get_jockey_features(jockey_code, venue_code, jockey_index)`

**データソース:** jockeys.json

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| jockey_win_rate | 騎手の勝率 | float | 0〜0.15 | -1 |
| jockey_top3_rate | 騎手の複勝率 | float | 0〜0.5 | -1 |
| jockey_venue_top3_rate | 同会場での複勝率 (10走以上) | float | 0〜0.5 | -1 |

---

### 2.6 脚質特徴量 (RUNNING_STYLE_FEATURES)

**生成:** `ml/features/running_style_features.py` — `compute_running_style_features()`

**データソース:** horse_history の corners（通過位置 [1C, 2C, 3C, 4C]）

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| avg_first_corner_ratio | 直近5走の 1角通過順位/頭数 平均 | float | 0〜1 | -1 |
| avg_last_corner_ratio | 直近5走の 最終角通過順位/頭数 平均 | float | 0〜1 | -1 |
| position_gain_last5 | (1角順位 − 着順)/頭数 の平均 | float | -0.5〜0.5 | -1 |
| front_runner_rate | 直近5走で 1角3番手以内 の割合 | float | 0〜1 | -1 |
| pace_sensitivity | 先行時と非先行時の着順差 | float | -5〜+5 | -1 |
| closing_strength | 直近3走の (最終角順位 − 着順) 平均 | float | -10〜+10 | -1 |
| running_style_consistency | 1角比率の標準偏差（低=安定） | float | 0〜0.5 | -1 |
| last_race_corner1_ratio | 前走の 1角順位/頭数 | float | 0〜1 | -1 |

---

### 2.7 ローテ・コンディション特徴量 (ROTATION_FEATURES)

**生成:** `ml/features/rotation_features.py` — `compute_rotation_features()`

**データソース:** horse_history（前走）、race（今回条件）

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 | Model B |
|----------|------|-----|------|--------|---------|
| futan_diff | 今走斤量 − 前走斤量 | float | -5〜+5 | -1 | ○ |
| futan_diff_ratio | 斤量変化率 | float | -0.1〜0.1 | -1 | ○ |
| weight_change_ratio | 馬体重変化率 | float | -0.1〜0.1 | -1 | ○ |
| prev_race_popularity | 前走人気順 | int | 1〜18 | -1 | ○ |
| jockey_change | 騎手乗り替わり (0/1) | int | 0, 1 | None | ○ |
| prev_grade_level | 前走グレードレベル (G1=1〜新馬=10) | int | 1〜10 | None | × MARKET |
| grade_level_diff | 今走−前走 (正=降級) | int | -9〜+9 | None | × MARKET |
| venue_rank_diff | 会場ランク差 (正=降格方向) | int | -4〜+4 | None | × MARKET |
| is_koukaku_venue | ①栗東馬割合降格 | 0/1 | 0, 1 | None | ○ |
| is_koukaku_female | ②混合→牝限 | 0/1 | 0, 1 | None | ○ |
| is_koukaku_season | ③冬春→夏 | 0/1 | 0, 1 | None | ○ |
| is_koukaku_age | ④馬齢 | 0/1 | 0 | None | ○ |
| is_koukaku_distance | ⑤距離短縮 | 0/1 | 0, 1 | None | ○ |
| is_koukaku_turf_to_dirt | ⑥芝→ダート | 0/1 | 0, 1 | None | ○ |
| is_koukaku_handicap | ⑦ハンデ戦 | 0/1 | 0, 1 | None | ○ |
| koukaku_rote_count | 降格ローテ該当数 | int | 0〜5 | None | ○ |

---

### 2.8 ペース特徴量 (PACE_FEATURES)

**生成:** `ml/features/pace_features.py` — `compute_pace_features()`

**データソース:** pace_index (race_trend_index.json)、horse_history

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| avg_race_rpci_last3 | 直近3走のレースRPCI平均 | float | 45〜55 | -1 |
| prev_race_rpci | 前走のRPCI | float | 45〜55 | -1 |
| consumption_flag | 前走RPCI≤46 かつ 間隔≤21日 | 0/1 | 0, 1 | 0 |
| last3f_vs_race_l3_last3 | (馬L3 − レースL3) の3走平均 | float | -3〜+3 | -1 |
| steep_course_experience | 急坂場(中山/阪神)での出走割合 | float | 0〜1 | -1 |
| steep_course_top3_rate | 急坂場での複勝率 | float | 0〜1 | -1 |
| l3_unrewarded_rate_last5 | 上がり速いのに着外だったレース率 | float | 0〜1 | None |
| avg_lap33_last3 | 直近3走の平均33ラップ (l3−s3) | float | -6〜+2 | None |
| prev_race_lap33 | 前走の33ラップ | float | -6〜+2 | None |
| best_trend_top3_rate | trend_v2別で最良の複勝率 | float | 0〜1 | None |
| worst_trend_top3_rate | trend_v2別で最悪の複勝率 | float | 0〜1 | None |
| trend_versatility | 適性のばらつき（標準偏差） | float | 0〜0.3 | None |

---

### 2.9 調教特徴量 (TRAINING_FEATURES)

**生成:** `ml/features/training_features.py` — `compute_training_features()`

**データソース:** kb_ext (keibabook)、training_summary.json (CK_DATA)

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 | Model B |
|----------|------|-----|------|--------|---------|
| training_arrow_value | 調教矢印 (-2〜+2) | int | -2〜+2 | -1 | ○ |
| oikiri_5f | 追い切り5Fタイム | float | 58〜72秒 | -1 | ○ |
| oikiri_3f | 追い切り3Fタイム | float | 34〜42秒 | -1 | ○ |
| oikiri_1f | 追い切り1Fタイム | float | 11〜14秒 | -1 | ○ |
| oikiri_intensity_code | 脚色 (-1〜4) | int | -1〜4 | -1 | ○ |
| oikiri_has_awase | 併せ馬 (0/1) | int | 0, 1 | -1 | ○ |
| training_session_count | セッション数 | int | 1〜10 | -1 | ○ |
| rest_weeks | 休養週数 (中N週→N) | int | 1〜8 | -1 | ○ |
| oikiri_is_slope | 坂路コース (0/1) | int | 0, 1 | -1 | ○ |
| kb_rating | KBレーティング | float | 40〜75 | None | ○ |
| ck_laprank_score | CK lapRank スコア (1〜16) | int | 1〜16 | None | × MARKET |
| ck_laprank_class | lapRankクラス (D=0〜SS=5) | int | 0〜5 | None | × MARKET |
| ck_laprank_accel | 加速コード (+1/0/-1) | int | -1〜1 | None | × MARKET |
| ck_time_rank | タイムランク (1〜5) | int | 1〜5 | None | × MARKET |
| ck_final_laprank_score | 最終追切lapRankスコア | int | 1〜16 | None | × MARKET |
| ck_final_time4f | 最終追切4Fタイム | float | 48〜72秒 | None | × MARKET |
| ck_final_lap1 | 最終追切ラスト1F | float | 11〜17秒 | None | × MARKET |

---

### 2.10 KB印特徴量 (KB_MARK_FEATURES) — Model Bでは除外

**データソース:** kb_ext

| 特徴量名 | 説明 | 型 | Model B |
|----------|------|-----|---------|
| kb_mark_point | KB印ポイント | float | × MARKET |
| kb_aggregate_mark_point | KB総合印ポイント | float | × MARKET |

---

### 2.11 スピード指数特徴量 (SPEED_FEATURES)

**生成:** `ml/features/speed_features.py` — `compute_speed_features()`

**データソース:** kb_ext → entries[umaban].speed_indexes

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 |
|----------|------|-----|------|--------|
| speed_idx_latest | 前走のスピード指数 | float | 40〜75 | -1 |
| speed_idx_best5 | 直近5走の最高値 | float | 40〜75 | -1 |
| speed_idx_avg3 | 直近3走の平均 | float | 40〜75 | -1 |
| speed_idx_trend | 前走−2走前 (正=上昇) | float | -15〜+15 | 0 |
| speed_idx_std | 直近5走の標準偏差 | float | 0〜10 | -1 |

---

### 2.12 コメントNLP特徴量 (COMMENT_FEATURES)

**生成:** `ml/features/comment_features.py` — `compute_comment_features()`

**データソース:** kb_ext → stable_comment, previous_race_interview

| 特徴量名 | 説明 | 型 | 値域 | 欠損時 | Model B |
|----------|------|-----|------|--------|---------|
| comment_stable_condition | 厩舎談話の仕上がり度 | int | -3〜+3 | None | ○ |
| comment_stable_confidence | 厩舎談話の自信度 | int | -3〜+3 | None | ○ |
| comment_stable_mark | ヘッダーマーク (◎=4等) | int | 0〜4 | None | × MARKET |
| comment_stable_excuse_flag | 言い訳キーワード有無 | int | 0/1 | None | ○ |
| comment_interview_condition | 前走インタビューの仕上がり度 | int | -3〜+3 | None | ○ |
| comment_interview_excuse_score | 前走不利・敗因スコア | float | -3〜+3 | None | ○ |
| comment_memo_condition | 次走メモの仕上がり度 | int | -3〜+3 | None | ○ |
| comment_memo_trouble_score | 次走メモのトラブルスコア | float | -3〜+3 | None | ○ |
| comment_has_stable | 厩舎談話あり (0/1) | int | 0, 1 | None | ○ |
| comment_has_interview | インタビューあり (0/1) | int | 0, 1 | None | ○ |

---

### 2.13 出遅れ特徴量 (SLOW_START_FEATURES)

**生成:** `ml/features/slow_start_features.py` — `compute_slow_start_features()`

**状態:** 実験済み・importance 0 のため現行では無効化（コメントアウト）

| 特徴量名 | 説明 | 型 | 備考 |
|----------|------|-----|------|
| horse_slow_start_rate | 過去の出遅れ率 | float | 無効化 |
| horse_slow_start_last5 | 直近5走の出遅れ回数 | int | 無効化 |
| horse_slow_start_resilience | 出遅れ時の複勝圏率 | float | 無効化 |

---

## 3. Model B (Value) で除外される特徴量 (MARKET_FEATURES)

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
| pace_index | race_trend_index.json | RPCI, trend_v2, lap33 |
| kb_ext | data3/keibabook/YYYY/MM/DD/kb_ext_{id}.json | 調教・スピード・コメント |
| training_summary | data3/races/YYYY/MM/DD/temp/training_summary.json | CK_DATA lapRank |
| DB事前オッズ | mykeibadb | odds, popularity |

---

## 5. 特徴量数サマリ

| カテゴリ | 数 | Model A | Model B |
|----------|-----|---------|---------|
| 基本 | 12 | ○ | ○ |
| 市場系 | 4 | ○ | × |
| 過去走 | 22 | ○ | 16 (smoothed 等除外) |
| 調教師 | 3 | ○ | ○ |
| 騎手 | 3 | ○ | ○ |
| 脚質 | 8 | ○ | ○ |
| ローテ | 16 | ○ | 13 |
| ペース | 11 | ○ | ○ |
| 調教 | 17 | ○ | 10 |
| KB印 | 2 | ○ | × |
| スピード | 5 | ○ | ○ |
| コメント | 10 | ○ | 9 |
| 出遅れ | 0 | (無効) | (無効) |
| **合計** | **約110** | **FEATURE_COLS_ALL** | **FEATURE_COLS_VALUE** |

---

## 6. 実装ファイル対応表

| モジュール | ファイル | 主な関数 |
|------------|----------|----------|
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
| 出遅れ | slow_start_features.py | compute_slow_start_features |

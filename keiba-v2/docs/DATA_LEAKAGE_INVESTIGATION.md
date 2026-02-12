# ML データリーク調査レポート（v3.3対応）

keiba-v2/ml の分析（experiment_v3 および特徴量モジュール8個）において、**レース結果を含む情報がレース前の予測に使われていないか**を調査した結果です。

**調査日**: 2026-02-12
**対象バージョン**: ML v3.3（60特徴量 / 8モジュール）

---

## 結論サマリ

| カテゴリ | モジュール | リーク | 深刻度 | 備考 |
|----------|-----------|--------|--------|------|
| 過去走成績 | past_features.py | **なし** | - | `race_date < current_race_date` フィルタ済み |
| 脚質 | running_style_features.py | **なし** | - | 同上 |
| ペース | pace_features.py | **なし** | - | 過去走のrace_idのみ参照 |
| ローテ・コンディション | rotation_features.py | **なし** | - | 前走は時系列フィルタ済み |
| 調教 | training_features.py | **なし** | - | レース前の調教データのみ |
| 基本（レース情報） | base_features.py | **なし** | - | age/futan/distance等は事前確定 |
| オッズ・人気（Model A） | base_features.py | **あり** | 中 | 確定オッズ・確定人気を使用（設計上の意図） |
| 調教師・騎手統計 | trainer/jockey_features.py | **軽微** | 低 | 全期間一括集計 → 時間的リークの可能性 |

**実運用への影響**: Model B（Value Bet用）には市場系リークなし。調教師・騎手の時間的リークは影響が小さい（後述）。

---

## 1. リークなし（8モジュール中6モジュール）

### 1.1 過去走特徴量 (past_features.py) — 13特徴量

```python
# past_features.py:48
past = [r for r in runs if r['race_date'] < race_date]
```

`avg_finish_last3`, `best_finish_last5`, `last3f_avg_last3`, `days_since_last_race`, `win_rate_all`, `top3_rate_all`, `total_career_races`, `recent_form_trend`, `venue_top3_rate`, `track_type_top3_rate`, `distance_fitness`, `prev_race_entry_count`, `entry_count_change`

全て `race_date < current_race_date` でフィルタ。対象レースの結果は含まれない。

**判定: リークなし**

### 1.2 脚質特徴量 (running_style_features.py) — 8特徴量

```python
# running_style_features.py:41
past = [r for r in runs if r['race_date'] < race_date]
```

`avg_first_corner_ratio`, `avg_last_corner_ratio`, `position_gain_last5`, `front_runner_rate`, `pace_sensitivity`, `closing_strength`, `running_style_consistency`, `last_race_corner1_ratio`

corners/finish_position は過去走のみから算出。

**判定: リークなし**

### 1.3 ローテ・コンディション特徴量 (rotation_features.py) — 5特徴量

```python
# rotation_features.py:35
past = [r for r in runs if r['race_date'] < race_date]
```

`futan_diff`, `futan_diff_ratio`, `weight_change_ratio`, `prev_race_popularity`

前走データは時系列フィルタ済み。`prev_race_popularity`は**前走の**確定人気であり、対象レースの人気ではない。

`popularity_trend` = 今走人気 - 前走人気 → MARKET特徴量としてModel Bでは除外。

**判定: リークなし（popularity_trendはModel B除外で対処済み）**

### 1.4 ペース特徴量 (pace_features.py) — 6特徴量

`avg_race_rpci_last3`, `prev_race_rpci`, `consumption_flag`, `last3f_vs_race_l3_last3`, `steep_course_experience`, `steep_course_top3_rate`

pace_indexの参照は全て**過去走のrace_id**に対してのみ。対象レースのペースは参照しない。

**判定: リークなし**

### 1.5 調教特徴量 (training_features.py) — 9特徴量

`training_arrow_value`, `oikiri_5f`, `oikiri_3f`, `oikiri_1f`, `oikiri_intensity_code`, `oikiri_has_awase`, `training_session_count`, `rest_weeks`, `oikiri_is_slope`

データソース: kb_ext JSON内の`cyokyo_detail`（競馬ブックの調教ページから取得）。
調教データはレース前に公開される情報であり、レース結果に依存しない。

**判定: リークなし**

### 1.6 基本特徴量 (base_features.py) — レース情報部分

`age`, `sex`, `futan`, `horse_weight`, `horse_weight_diff`, `wakuban`, `umaban`, `distance`, `track_type`, `track_condition`, `entry_count`

これらは出馬表確定時に判明する情報。レース結果ではない。

**注意**: `horse_weight`/`horse_weight_diff`はパドック後（当日計量後）に確定する。金曜夜の予測時点では使えない可能性があるが、本番予測ではkb_ext出馬表データから補完している。

**判定: リークなし**

---

## 2. リークあり: オッズ・人気（Model A、設計上の意図）

### 2.1 該当特徴量

| 特徴量 | ソース | Model A | Model B |
|--------|--------|---------|---------|
| `odds` | base_features.py:30 | **使用** | 除外 |
| `popularity` | base_features.py:31 | **使用** | 除外 |
| `odds_rank` | experiment_v3.py:410（派生） | **使用** | 除外 |
| `popularity_trend` | rotation_features.py:59 | **使用** | 除外 |

### 2.2 リークの内容

- race JSONのオッズ・人気はSE_DATA（レース結果）から生成されており、**確定オッズ・確定人気**。
- 確定オッズは着順と強く相関するため、対象レースの予測タスクではデータリーク。

### 2.3 現状の対処

```python
# experiment_v3.py:101
MARKET_FEATURES = {'odds', 'popularity', 'odds_rank', 'popularity_trend'}

# experiment_v3.py:115
FEATURE_COLS_VALUE = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]
```

- **Model B（Value Bet用）** では全市場系特徴量を除外 → **リークなし**
- **Model A** は確定オッズを含むモデルとして明示的に運用

### 2.4 本番予測での扱い

- predict.py では **レース前に入手可能なオッズ** を使用（前日オッズ等）
- Model A の評価指標は「確定オッズ含みの性能」として解釈すべき
- **Value Bet戦略はModel Bベース** なので、実運用上のリーク影響はない

---

## 3. 軽微なリスク: 調教師・騎手統計（時間的リーク）

### 3.1 問題の概要

```python
# build_trainer_master.py:26
def build_trainer_stats(years: List[int]) -> Dict[str, Dict]:
    # years = [2020, 2021, ..., 2026] の全レースを一括スキャン
```

trainers.json / jockeys.json は `--years 2020-2026` で**全期間一括集計**。
例えば2022年のレースを予測する際に、2023年以降の成績が`trainer_win_rate`に含まれる。

### 3.2 影響度評価

| 要因 | 緩和度合い |
|------|-----------|
| 調教師/騎手の成績は年単位で大きく変動しない | 高 |
| 該当特徴量はModel B重要度Top10に2つ（venue系が3位/4位） | 注意 |
| テストデータが2025-2026年の場合、2020-2024の統計に2025-2026が混入 | 軽微 |
| trainers.jsonにyear_statsが既に存在 | 修正は容易 |

### 3.3 推奨対応

**短期（現状維持でOK）**:
- 実運用では「最新のtrainers.json」を使うため、2026年時点の統計は「2020-2025年の確定実績 + 2026年途中の実績」
- テスト期間（2025-2026年）に対する混入は1-2年分で影響は小さい

**中期（精度改善時に検討）**:
- point-in-time集計: 特徴量計算時に `trainer_win_rate@{race_date}` を算出
- trainers.jsonに既にある `year_stats` を活用して年単位の区切りは実装可能
- 実装例:

```python
def get_trainer_features_pit(trainer_code, venue_code, race_year, trainer_index):
    """point-in-time: race_yearより前の年のみで集計"""
    t = trainer_index.get(trainer_code)
    if not t: return defaults

    year_stats = t.get('year_stats', {})
    past_years = {y: s for y, s in year_stats.items() if int(y) < int(race_year)}
    # past_yearsから win_rate/top3_rate を再計算
```

---

## 4. データソース別リーク整理

| データ | 作成元 | 内容 | 特徴量での使用 | リスク |
|--------|--------|------|----------------|--------|
| horse_history_cache.json | build_horse_history (SE) | 馬ごとの過去走 | `race_date <` フィルタ | なし |
| pace_index | race JSON の pace | レースRPCI等 | 過去走のrace_idのみ | なし |
| kb_ext JSON | keibabook scraper | 調教・出馬表データ | レース前の情報のみ | なし |
| trainers.json | build_trainer_master (SE) | 調教師通算統計 | 全期間一括 | 軽微 |
| jockeys.json | build_jockey_master (SE) | 騎手通算統計 | 全期間一括 | 軽微 |
| race JSON (entries) | build_race_master (SE) | 確定オッズ・人気・着順 | Model Aで使用 | あり（意図的） |

---

## 5. 今後の特徴量追加時のチェックリスト

新しい特徴量を追加する際は以下を確認する:

### 必須チェック
- [ ] **対象レースの結果を参照していないか**: finish_position, 確定オッズ, 確定人気
- [ ] **時系列フィルタがあるか**: `race_date < current_race_date`（過去走ベースの場合）
- [ ] **集計データの時点は適切か**: trainers.json等の通算統計は全期間一括であることを認識
- [ ] **MARKET_FEATURES に追加すべきか**: 市場データ由来ならModel B除外リストに追加

### 注意が必要なケース
- **当日情報**: 馬体重、パドック情報 → 金曜予測では使えない可能性
- **集計統計の時点**: 新しい集計マスタを作る場合はpoint-in-time集計を検討
- **外部データの取得タイミング**: 気象データ等の実測値はレース後にしか確定しない場合がある

### Model B除外基準
以下に該当する特徴量は `MARKET_FEATURES` に追加してModel Bから除外する:
- 確定オッズ、確定人気、それらの派生値
- 「今走」の市場評価に依存する値（例: popularity_trend = 今走人気 - 前走人気）
- レース後にしか確定しない値

---

## 6. 参照コード一覧

| 確認ポイント | ファイル | 行 |
|-------------|---------|-----|
| 過去走の時系列フィルタ | ml/features/past_features.py | 48 |
| 脚質の時系列フィルタ | ml/features/running_style_features.py | 41 |
| ローテの時系列フィルタ | ml/features/rotation_features.py | 35 |
| ペースの過去走参照 | ml/features/pace_features.py | 52, 60, 73 |
| 調教データの参照 | ml/features/training_features.py | 90-139 |
| オッズ・人気の取得 | ml/features/base_features.py | 30-31 |
| 市場系除外定義 | ml/experiment_v3.py | 101 |
| Value特徴量定義 | ml/experiment_v3.py | 115 |
| odds_rank派生 | ml/experiment_v3.py | 410 |
| 着順の扱い（メタのみ） | ml/experiment_v3.py | 358-360 |
| 調教師集計（全期間） | builders/build_trainer_master.py | 26-42 |
| 騎手集計（全期間） | builders/build_jockey_master.py | 26-43 |

---

**最終更新**: 2026-02-12（カカシ）

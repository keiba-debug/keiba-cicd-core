# vega-niigata1000 データ辞書（Phase 3a 実装の単一の真実）

> 設計書 §14（v0.2.1）と完全一致。ここが**実装・テスト・キャリブの単一の真実**。
> 設計書本体: `keiba-v2/docs/projects/vega_niigata1000_rule_engine.md`

## 1. 馬個別特徴量（§14.1）

`compute_horse_features(ketto_num, cutoff_date, history_cache) -> dict` で一括算出する。
全関数で `cutoff_date` 当日は **含めない**（strict less than）。

| 列名 | 型 | 定義 | 算出窓 | 欠損時 |
|---|---|---|---|---|
| `total_career_races_at_cutoff` | int | `cutoff_date` 未満の通算出走数 | 全期間 | 0 |
| `niigata_1000m_count` | int | 過去千直出走回数 (`venue_code=='04' AND distance==1000 AND track_type=='turf'`) | 全期間 | 0 |
| `niigata_1000m_top3_count` | int | 上記のうち `finish_position <= 3` | 全期間 | 0 |
| `past_choku_top3_rate` | float \| None | top3_count / count（経験ゼロは None） | 全期間 | None |
| `past_choku_finish_avg` | float \| None | 過去千直平均着順（finish_position 有効値のみ） | 全期間 | None |
| `past_choku_last_3f_avg` | float \| None | 過去千直の上がり3F平均（`last_3f > 0` のみ） | 全期間 | None |
| `past_corner_first_avg_5` | float \| None | 過去5走の前半通過順位平均（`corners[0] not in (None, 0)`） | 直近5走 | None |
| `past_corner_first_min_5` | int \| None | 過去5走のベスト前半通過順位 | 直近5走 | None |
| `past_last_3f_avg_5` | float \| None | 過去5走の上がり3F平均（`last_3f > 0` のみ） | 直近5走 | None |
| `past_last_3f_min_5` | float \| None | 過去5走のベスト上がり3F | 直近5走 | None |
| `past_short_count` | int | 過去短距離(1000-1200m turf)出走回数 | 全期間 | 0 |
| `past_short_avg_l3f` | float \| None | 過去短距離の上がり3F平均 | 全期間 | None |
| `prev_distance` | int \| None | 前走距離 | 直近1走 | None |
| `prev_finish` | int \| None | 前走着順 | 直近1走 | None |
| `days_since_prev` | int \| None | (cutoff_date - 前走 race_date).days | 直近1走 | None |
| `is_first_choku` | bool | `niigata_1000m_count == 0` の派生フラグ | 全期間 | True（経験ゼロ） |

### 重要ルール
- 「過去5走」= 過去走を `race_date` 昇順ソートし末尾5件
- `corners` が空配列 `[]` の千直はカウントから除外（前半通過順位は存在しない）
- `last_3f` が `None` または `<= 0` の走はカウントから除外
- `finish_position` が `None` または `<= 0` の走は finish 系の集計から除外
- `cutoff_date` は ISO 形式 `YYYY-MM-DD` の文字列。比較は文字列比較（ISO ソート性に依存）
- `days_since_prev` のみ datetime 演算が必要

## 2. 関係者特徴量（§14.2、実装済 ✅）

`compute_relation_features(jockey_code, trainer_code, cutoff_date, history_cache, snapshot_root) -> dict`

| 列名 | 型 | 定義 | 算出窓 | 欠損時 |
|---|---|---|---|---|
| `jockey_choku_n` | int | 騎手の千直出走回数 | 直近2年 | 0 |
| `jockey_choku_top3_rate` | float \| None | 騎手の千直3着内率 | 直近2年 | None |
| `jockey_choku_strong_rate` | float \| None | 騎手の千直強馬率 | 直近2年 | None |
| `trainer_choku_n` | int | 厩舎の千直出走回数 | 直近2年 | 0 |
| `trainer_choku_top3_rate` | float \| None | 厩舎の千直3着内率 | 直近2年 | None |
| `trainer_choku_strong_rate` | float \| None | 厩舎の千直強馬率 | 直近2年 | None |

### 強馬の定義（Phase 2 と同じ）
1走の race-level 平均からの偏差で判定:
- `pre_2f = time_sec - last_3f`
- `pre_2f_dev = pre_2f - mean(pre_2f in race) < 0` (テン速い)
- `last_3f_dev = last_3f - mean(last_3f in race) < 0` (末脚速い)
- かつ `finish_position <= 3`

→ 上記すべて満たす走を `is_strong=True` でカウント。

### §8.2 base + delta - expired ロジック
1. `base` = 前月末スナップショット (`{YYYY-MM}.json`、直近2年集計済み)
2. `cutoff_2y = cutoff_date - 730 days`
3. `delta_start = max(月初 of cutoff, cutoff_2y)`
4. `delta` = `[delta_start, cutoff_date)` の集計（同月内 + 2年窓スライド適用）
5. `expired` = `[base.window_start, cutoff_2y)` の集計（base にあるが新窓外、控除）
6. `total_n = base.n + delta.n - expired.n` 等。`n < 5` なら rate は None

### snapshot 仕様
- 場所: `data3/indexes/niigata1000_relations/{YYYY-MM}.json`
- snapshot_date = 月末日、window_start = snapshot_date - 730 days (inclusive)
- 形式: `{snapshot_ym, snapshot_date, window_start, window_end, jockeys: {code: {n, top3, strong}}, trainers: {...}}`
- 生成: `python -m analysis.niigata1000.snapshot_builder --start 2020-01 --end 2026-04`

## 3. 血統特徴量（§14.3、Phase 3a で実装）

| 列名 | 型 | 出所 | 欠損時 |
|---|---|---|---|
| `sire_id` | str | pedigree_index | "" |
| `sire_name` | str | sire_stats_index | "?" |
| `sire_line` | str | classify_sire_line() | "不明" |
| `bms_id` | str | pedigree_index | "" |
| `bms_name` | str | sire_stats_index | "?" |
| `bms_line` | str | classify_sire_line() | "不明" |

`classify_sire_line` は `_helpers.classify_sire_line` を再利用。

## 4. 環境変数（§14.4、race-level）

`compute_race_env(race_dict) -> dict` で一括算出。

| 列名 | 型 | 定義 |
|---|---|---|
| `track_condition_grp` | str | "良" → "良" / その他("稍重"/"重"/"不良") → "稍重以上" |
| `era` | str | `race_date < '2023-01-01'` → "2020-2022" / それ以外 → "2023-2026" |
| `is_full_field` | bool | `num_runners >= 16` |
| `race_type` | str | race_name に "アイビスサマーダッシュ" → "G3アイビスSD" / grade=="OP" → "OP" / その他 → "条件戦" |

## 5. サンプル閾値ルール（§14.5）

- 騎手・厩舎の率系: 直近2年で出走 < 5回なら算出せず None（信頼度に反映）
- 父・母父の率系: 直近2年で出走 < 10回なら None
- 馬の千直成績: 全期間で 0回なら `is_first_choku = True` を立てる

## 6. リーク防止規約（§8）

- 全特徴量は `cutoff_date` 必須引数
- `cutoff_date` 当日は **含めない**（`race_date < cutoff_date`）
- 関係者・血統の集計窓統計は月次スナップショット + 当月内差分集計（§8.2）

## 7. テスト設計（Phase 3a TDD）

### 固定 Pin（実データ依存、固定不変）
- `2018106612`: 千直経験豊富（cutoff_date 変動の挙動検証用）
- `2023104705`: 2025-06-29 デビュー馬（欠損時挙動検証用）

### 必須テストケース
- (a) 各特徴量が定義通り算出される（reference cutoff）
- (b) `cutoff_date` 強制: cutoff 当日のレースは含まれない
- (c) `cutoff_date` 変動: cutoff を変えると結果が変わる（リーク防止）
- (d) 欠損時: 仕様通り None / 0 / True を返す
- (e) サンプル閾値: §14.5 の閾値ルールに従う（関係者特徴量で実装）
- (f) 同月内リーク: 月内中旬の cutoff で月末レースが入らない（関係者特徴量で実装）

### 環境変数テスト
- (g) §14.4 の各分類が境界値含めて正しい

---

更新履歴:
- 2026-05-09: Phase 3a 実装着手時に新設（§14 v0.2.1 に準拠）

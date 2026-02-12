# ML データリーク調査レポート

keiba-v2/ml の分析（experiment_v3 および特徴量モジュール）において、**レース結果を含む情報がレース前の予測に使われていないか**を調査した結果です。

## 結論サマリ

| カテゴリ | リークの有無 | 備考 |
|----------|--------------|------|
| 過去走・上がり3F・ペース・脚質 | **なし** | すべて「対象レースより前」のデータのみ使用 |
| 着順（finish_position） | **なし** | ラベル・分析用のみで特徴量には未使用 |
| オッズ・人気（Model A） | **あり** | 確定オッズ・確定人気を特徴量に使用 |
| 調教師・騎手統計 | **時間的リークの可能性** | 全期間一括集計のため未来情報が含まれる可能性 |

---

## 1. 過去走・レース結果由来の特徴量（リークなし）

### 1.1 過去走特徴量（past_features.py）

- **last3f_avg_last3**  
  直近3走の**過去レース**の「上がり3F」の平均。  
  `past = [r for r in runs if r['race_date'] < race_date]` で対象レースより前のみ使用。
- **avg_finish_last3, best_finish_last5, win_rate_all, top3_rate_all** 等  
  いずれも `race_date < race_date` でフィルタした過去走のみから算出。
- コメントで「時系列リーク防止: race_date より前のレースのみ使用」と明記されている。

**判定: データリークなし。**

### 1.2 ペース特徴量（pace_features.py）

- **avg_race_rpci_last3, prev_race_rpci, last3f_vs_race_l3_last3**  
  すべて `past`（対象レースより前の走）の `race_id` で pace_index を参照。  
  対象レースの RPCI や L3 は参照していない。
- pace_index は「過去のレースの結果ペース」を格納しているが、参照しているのは**過去走の race_id** のみ。

**判定: データリークなし。**

### 1.3 脚質特徴量（running_style_features.py）

- **corners, finish_position**  
  `past = [r for r in runs if r['race_date'] < race_date]` の過去走のみから算出。  
  対象レースのコーナー通過順位・着順は使っていない。

**判定: データリークなし。**

### 1.4 対象レースの着順（experiment_v3.py）

- `finish_position` は `entry.get('finish_position')` で取得しているが、  
  - 特徴量リスト（FEATURE_COLS_ALL / FEATURE_COLS_VALUE）には**含まれていない**。  
  - ラベル（is_top3, is_win）および分析用メタ情報としてのみ使用。

**判定: データリークなし。**

### 1.5 対象レースのペース（race.pace）

- base_features.py で `pace = race.get('pace') or {}` を取得しているが、  
  **return する辞書には一切含めていない**（未使用変数）。
- ペース特徴量では pace_index を「過去走の race_id」に対してのみ参照。

**判定: データリークなし。**

---

## 2. オッズ・人気（Model A でリークあり）

### 2.1 データの意味

- race JSON（`race_{race_id}.json`）は build_race_master 等で SE_DATA（レース結果）から生成されている。
- SE_DATA のオッズ・人気は **確定オッズ・確定人気**（レース確定後の値）に相当。
- base_features.py で `entry.get('odds')`, `entry.get('popularity')` をそのまま特徴量に利用している。

### 2.2 どこで使われているか

- **FEATURE_COLS_ALL（Model A）** に `odds`, `popularity`, `odds_rank`, `popularity_trend` が含まれる。
- **popularity_trend**（rotation_features）は「今走人気 − 前走人気」。  
  「今走人気」は対象レースの確定人気なので、同じく結果後にしか分からない情報。

### 2.3 リークの内容

- 確定オッズ・確定人気はレース結果（特に着順）と強く相関するため、  
  **「そのレースの結果を予測する」タスクで特徴量に使うとデータリーク**となる。
- Model A の評価（AUC 等）は「結果が分かった後の市場情報を含めた場合の性能」と解釈する必要がある。

### 2.4 Model B の扱い

- **FEATURE_COLS_VALUE（Model B）** では `MARKET_FEATURES = {'odds', 'popularity', 'odds_rank', 'popularity_trend'}` を**除外**している。
- オッズ・人気系を特徴量に含めないため、**この部分のデータリークはなし**。

---

## 3. 調教師・騎手統計（時間的リークの可能性）

### 3.1 集計方法

- **trainers.json**（build_trainer_master）、**jockeys.json**（build_jockey_master）は、  
  SE_DATA を **指定年範囲で一括スキャン** して集計している。
- 集計時に「このレース日時点までの実績のみ」といった**時点区切りはしていない**。

### 3.2 何が問題か

- 例: 2022年12月のレースを予測するとき、  
  `trainer_win_rate` / `jockey_top3_rate` には 2023年以降の成績も含まれ得る。
- 学習・評価で「過去のレース」をサンプルにする場合、  
  その時点では知り得ない**未来の実績**が特徴量に含まれる → **時間的リーク（temporal leakage）**。

### 3.3 推奨

- 調教師・騎手統計を**レース日時点で区切った集計**（point-in-time）に変更することを推奨。
- 例: 対象レースの `race_date` より前のレースのみで win_rate / top3_rate を再計算し、  
  その時点の統計を特徴量に使う。

---

## 4. データソースの整理

| データ | 作成元 | 内容 | 特徴量での使用 |
|--------|--------|------|----------------|
| horse_history_cache.json | build_horse_history (SE_DATA) | 馬ごとの過去走（race_date, last_3f, finish_position 等） | 過去走のみ（race_date &lt; 対象日）で使用 → OK |
| pace_index | race JSON の pace | レース単位の RPCI, l3, s3 等 | 過去走の race_id のみ参照 → OK |
| trainers.json / jockeys.json | build_*_master (SE_DATA) | 調教師・騎手の通算勝率等 | 全期間一括 → 時間的リークの可能性 |
| race_{id}.json (entries) | SE_DATA 等 | 確定オッズ・確定人気・着順 | オッズ・人気を Model A で特徴量に使用 → リークあり |

---

## 5. 推奨アクション

1. **Model A の解釈**  
   - オッズ・人気を含むモデルとして明示し、  
     「確定オッズ・確定人気を利用した場合の性能」であることをドキュメント・コメントで明記する。

2. **本番予測（レース前）で使うモデル**  
   - オッズ・人気を使わない **Model B（FEATURE_COLS_VALUE）** をベースにする。  
   - 本番では「レース前時点で入手可能なオッズ・人気」を使う場合は、  
     確定値ではなく**事前オッズ・事前人気**を別データソースから渡す設計にする。

3. **調教師・騎手統計**  
   - 学習・評価時は「対象レースの race_date より前のレースのみ」で  
     win_rate / top3_rate を計算する point-in-time 集計に変更することを検討する。

4. **コード上の明示**  
   - past_features.py と同様に、  
     - オッズ・人気が「確定値であること」  
     - 調教師・騎手が「現状は全期間集計であること」  
     をコメントや docstring で明記すると、今後の変更時にもリーク防止しやすい。

---

## 6. 参照コード一覧

- 過去走の時系列フィルタ: `ml/features/past_features.py` 46行目付近 `past = [r for r in runs if r['race_date'] < race_date]`
- ペースの参照: `ml/features/pace_features.py` 52, 60, 73行目（いずれも `r['race_id']` は過去走）
- 脚質の参照: `ml/features/running_style_features.py` 41行目 `past = [r for r in runs if r['race_date'] < race_date]`
- 着順の扱い: `ml/experiment_v3.py` 284–286（スキップ条件）, 357–358（メタ・ラベルのみ）
- 市場系除外: `ml/experiment_v3.py` 100–114行目 `MARKET_FEATURES`, `FEATURE_COLS_VALUE`
- オッズ・人気の取得: `ml/features/base_features.py` 30–31行目
- 調教師・騎手集計: `builders/build_trainer_master.py`, `builders/build_jockey_master.py`（年範囲一括スキャン）

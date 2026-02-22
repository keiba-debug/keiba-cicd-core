# AI特徴量リスト

ML予測モデル（v4.0）で使用中の実装済み特徴量と、ブログ考察から抽出した候補特徴量の管理。

> **次期アイデア集**: `insights/model/next_features_and_targets.md` — 目的変数拡張・未使用データ活用の詳細計画

---

## 実装済み特徴量（v4.0 / Model A: 78, Model B: 72）

> **正規リスト**: 各特徴量モジュール (`keiba-v2/ml/features/`) が唯一の正。
> Model B除外 = 市場データに依存する特徴量（odds, popularity系）

### base_features.py — 基本特徴量（15個）

| 特徴量 | 説明 | Model B |
|--------|------|---------|
| `age` | 年齢 | o |
| `sex` | 性別（牡=0, 牝=1, セ=2） | o |
| `futan` | 斤量 | o |
| `horse_weight` | 馬体重 | o |
| `horse_weight_diff` | 馬体重前走比較 | o |
| `wakuban` | 枠番 | o |
| `umaban` | 馬番 | o |
| `distance` | 距離 | o |
| `track_type` | 芝=0, ダート=1 | o |
| `track_condition` | 良=0, 稍重=1, 重=2, 不良=3 | o |
| `entry_count` | 出走頭数 | o |
| `odds` | オッズ | **除外** |
| `popularity` | 人気順位 | **除外** |
| `month` | 月（1-12）[v4.0] | o |
| `nichi` | 開催日（1=開幕〜8=最終週、馬場の荒れ度）[v4.0] | o |

### past_features.py — 過去走成績（16個）

| 特徴量 | 説明 |
|--------|------|
| `avg_finish_last3` | 直近3走平均着順 |
| `best_finish_last5` | 直近5走最高着順 |
| `last3f_avg_last3` | 直近3走上がり3F平均 |
| `days_since_last_race` | 前走からの日数 |
| `win_rate_all` | 通算勝率 |
| `top3_rate_all` | 通算3着以内率 |
| `total_career_races` | 総走行数 |
| `recent_form_trend` | 近走トレンド（正=上昇） |
| `venue_top3_rate` | 場所別3着以内率 |
| `track_type_top3_rate` | トラックタイプ別3着以内率 |
| `distance_fitness` | 距離適性（±200m） |
| `prev_race_entry_count` | 前走出走頭数 |
| `entry_count_change` | 出走頭数の変化 |
| `best_l3f_last5` | 直近5走の上がり3F最速値 [v4.0] |
| `finish_std_last5` | 直近5走の着順標準偏差（小=安定、大=ムラ）[v4.0] |
| `comeback_strength_last5` | 直近5走の盛り返し強度（道中最悪順位→着順の回復度）[v4.0] |

### trainer_features.py — 調教師（4個）

| 特徴量 | 説明 |
|--------|------|
| `trainer_win_rate` | 調教師勝率 |
| `trainer_top3_rate` | 調教師3着以内率 |
| `trainer_venue_top3_rate` | 調教師場所別3着以内率 |
| `trainer_total_runs` | 調教師総走行数 |

### jockey_features.py — 騎手（4個）

| 特徴量 | 説明 |
|--------|------|
| `jockey_win_rate` | 騎手勝率 |
| `jockey_top3_rate` | 騎手3着以内率 |
| `jockey_venue_top3_rate` | 騎手場所別3着以内率 |
| `jockey_total_runs` | 騎手総走行数 |

### running_style_features.py — 脚質（8個）[v3.1]

| 特徴量 | 説明 |
|--------|------|
| `avg_first_corner_ratio` | 直近5走 第1コーナー順位比率平均（0=逃げ, 1=追込） |
| `avg_last_corner_ratio` | 直近5走 最終コーナー順位比率平均 |
| `position_gain_last5` | 直近5走 ポジション上げ幅 |
| `front_runner_rate` | 直近5走 先行率（corners[0]<=3の割合） |
| `pace_sensitivity` | ペース感応度（先行時vs非先行時の着順差） |
| `closing_strength` | 直近3走 クロージング力（最終corner - finish） |
| `running_style_consistency` | 脚質一貫性（標準偏差） |
| `last_race_corner1_ratio` | 前走 第1コーナー順位比率 |

### rotation_features.py — ローテ・コンディション（6個）[v3.1]

| 特徴量 | 説明 | Model B |
|--------|------|---------|
| `futan_diff` | 斤量変化（今走-前走） | o |
| `futan_diff_ratio` | 斤量変化率 | o |
| `weight_change_ratio` | 馬体重変化率 | o |
| `prev_race_popularity` | 前走人気順位 | o |
| `popularity_trend` | 人気トレンド（今走-前走） | **除外** |
| `jockey_change` | 騎手乗り替わりフラグ（0/1）[v4.0] | o |

### pace_features.py — ペース（7個）[v3.1]

| 特徴量 | 説明 |
|--------|------|
| `avg_race_rpci_last3` | 直近3走 レースRPCI平均 |
| `prev_race_rpci` | 前走RPCI |
| `consumption_flag` | 消耗フラグ（前走RPCI<=46 & 中間隔<=21日） |
| `last3f_vs_race_l3_last3` | (馬L3 - レースL3)の3走平均 |
| `steep_course_experience` | 急坂場（中山/阪神）出走割合 |
| `steep_course_top3_rate` | 急坂場での3着以内率 |
| `l3_unrewarded_rate_last5` | 上がりが速いのに着外のレース率（展開不利馬の検出）[v4.0] |

### speed_features.py — スピード指数（5個）[v3.5]

| 特徴量 | 説明 |
|--------|------|
| `speed_idx_latest` | 前走のスピード指数 |
| `speed_idx_best5` | 過去5走の最高値 |
| `speed_idx_avg3` | 直近3走の平均 |
| `speed_idx_trend` | トレンド（前走 - 2走前） |
| `speed_idx_std` | 過去5走の標準偏差（安定性） |

### training_features.py — 調教・KB印（12個）[v3.3 + v4.0]

| 特徴量 | 説明 | Model B |
|--------|------|---------|
| `training_arrow_value` | 調教矢印（-2〜+2） | o |
| `oikiri_5f` | 追い切り5Fタイム | o |
| `oikiri_3f` | 追い切り3Fタイム | o |
| `oikiri_1f` | 追い切り1Fタイム | o |
| `oikiri_intensity_code` | 脚色コード（0=馬なり〜4=一杯） | o |
| `oikiri_has_awase` | 併せ馬有無（0/1） | o |
| `training_session_count` | 調教セッション数 | o |
| `rest_weeks` | 休養週数 | o |
| `oikiri_is_slope` | 坂路コースフラグ（0/1） | o |
| `kb_mark_point` | 本誌印ポイント（◎=8〜無印=0）[v4.0] | **除外** |
| `kb_aggregate_mark_point` | 全記者総合ポイント [v4.0] | **除外** |
| `kb_rating` | keibabookレーティング（独自評価値）[v4.0] | o |

### 設計ルール

- **欠損値**: NaN（LightGBMネイティブ処理に委ねる。v3.5で-1 fillna廃止）
- **時系列リーク防止**: `race_date < current_race_date` でフィルタ必須
- **Model B除外基準**: オッズ・人気など市場データに依存するもの（6個: odds, popularity, odds_rank, popularity_trend, kb_mark_point, kb_aggregate_mark_point）

---

## 候補特徴量（ブログ考察からの抽出）

以下は未実装の候補特徴量。実装難度・期待効果を考慮して優先順位を決める。

### ペース・展開系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| 同レース逃げ馬頭数 | 逃げ脚質馬の数→ペース予測 | 中 | 未 |
| 予想ペース指数 | 逃げ馬の持ちタイム・頭数からのペース推定 | 高 | 未 |
| 当該馬の脚質×逃げ馬頭数 | 交互作用（差し馬×ハイペース=有利） | 中 | 未 |
| 出遅れ率 | 1角順位の急落からの推定 | 中 | 未 |

### 脚質サブタイプ系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| ペース別好走率差 | スロー好走率-ハイ好走率 | 低 | 未 |
| 平均仕掛けポイント | ポジション上昇開始コーナー | 中 | 未（`closing_strength`で部分カバー） |
| 上がり3F相対値 | 馬L3-レース平均L3 | 低 | 部分実装（`last3f_vs_race_l3_last3`） |
| 3-4角ポジション変動 | 捲り型vs直線勝負型の分類 | 低 | 未 |

### ポジショニング系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| ポジショニングコスト | 枠×脚質の期待1角順位との乖離 | 中 | 未 |
| 1コーナーまでの距離 | コース×距離のルックアップ | 低 | 未 |
| 枠番不利度 | 枠番/(1角距離/100) | 低 | 未 |
| ボトルネック強度 | 頭数/1角距離 | 低 | 未 |

### 馬場・コース系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| 馬場状態×馬体重 | 重馬場での重い馬の不利 | 低 | 未 |
| 気温/風速 | 気象庁アメダスデータ連携 | 中 | 未 |
| 含水率推定値 | 降水量-蒸発量の連続値 | 高 | 未 |

### 騎手・調教師・馬主系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| 馬主タイプ | クラブ/個人の5分類 | 中 | 未 |
| 馬主過去1年勝率 | 馬の質の代理変数 | 中 | 未 |

### マクリ・ペースクラッシャー系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| マクリ率 | 1角-3角の大幅ポジション上昇率 | 中 | 未 |
| 騎手マクリ率 | 騎手の過去1年のマクリ使用率 | 中 | 未 |
| ペースクラッシャー候補度 | マクリ率×騎手×条件補正 | 中 | 未 |

### 着順分布・安定度系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| 着順標準偏差(5走) | 安定型vs一発型 | 低 | ✅ `finish_std_last5` [v4.0] |
| 盛り返し強度 | (最悪位置-着順)/(頭数-1) | 低 | ✅ `comeback_strength_last5` [v4.0] |
| 盛り返し率(5走) | 戦意が強いタイプの検出 | 低 | 未 |

### パフォーマンス評価系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| 前走1着との着差(秒差) | 着順より情報量が多い連続値 | 低 | 未 |
| 上がり3F順位vs着順ギャップ | 展開不利の検出（巻き返し候補） | 低 | ✅ `l3_unrewarded_rate_last5` [v4.0] |
| 上がり3F最速(5走) | 末脚のピーク能力 | 低 | ✅ `best_l3f_last5` [v4.0] |
| クラス補正着順 | 異クラス成績の比較可能化 | 中 | 未 |
| スピード指数 | 走破タイムの馬場差・距離標準化 | 高 | 未 |

### ローテーション系

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| 間隔カテゴリ(5分類) | 超短/短/標準/長/超長 | 低 | 未（`days_since_last_race`で連続値カバー） |
| 休養明けN戦目 | 叩き2戦目の検出 | 低 | 未 |
| 調教師の平均出走間隔 | 厩舎のローテ方針 | 中 | 未 |

### オッズ・市場系（Model Aのみ）

| 特徴量 | 説明 | 実装難度 | 実装状況 |
|---|---|---|---|
| オッズ乖離度 | AI予測勝率とオッズ逆算勝率の差 | 中 | 未（v5.0で実装予定） |
| 馬主クラブフラグ | 応援馬券によるオッズ歪み指標 | 低 | 未 |

---

## 次の実装優先度（ML改善時の参考）

### 高優先（低難度×効果期待大）
- ~~着順標準偏差、盛り返し強度~~ → ✅ v4.0実装済
- ~~上がり3F順位vs着順ギャップ~~ → ✅ v4.0実装済（`l3_unrewarded_rate_last5`）
- 追い切りタイムのコース別・馬場別正規化（既存`oikiri_*`の強化）
- **前走レースレベル（レーティング版）**（Sprint 2重点項目）

### 中優先（中難度×有望）
- ポジショニングコスト系（枠×脚質の交互作用）
- 展開シミュレーション（逃げ馬頭数×脚質）← tenkai_dataで一部実現可能
- consumption_flag条件緩和（28日以内、RPCI<=48）

### 低優先（高難度 or 効果未知）
- 気象データ連携（外部API依存）
- スピード指数/タイムランク（馬場差推定が困難）← B-9 Phase 2で段階的に
- 三連単EV計算（v5.0以降）

> **詳細計画**: `insights/model/next_features_and_targets.md` のSprint 2/3参照

---

**最終更新**: 2026-02-14（カカシ）

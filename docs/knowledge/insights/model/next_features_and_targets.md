# 次期特徴量・目的変数アイデア集

> 現行v3.5（65特徴量, 目的変数is_top3）を踏まえ、新たなアイデアを**実装しやすい順**に整理。
> 各アイデアに「データ準備済か」「コード変更量」「期待効果の根拠」を明記。

---

## Part A: 目的変数の拡張

### A-1. is_win（1着予測）モデルの追加 ★実装即可

**現状**: is_top3のみ。is_winは評価用に計算済だが学習に未使用。

**提案**: Model C として1着予測モデルを追加。
```
Model A: is_top3（精度モデル、全特徴量）
Model B: is_top3（Valueモデル、市場系除外）
Model C: is_win（単勝モデル、全特徴量）  ← NEW
```

**根拠**:
- 複勝と単勝では「勝つ馬」と「3着に来る馬」の性質が異なる（ability_is_not_scalar §3）
- 安定好走型（タイプB）はis_top3では高スコアだがis_winでは低い
- 馬券種別に最適なモデルを使い分け: 単勝/馬単→Model C、複勝/ワイド→Model A

**工数**: experiment_v3.pyの学習ループに1モデル追加のみ。特徴量は共用。
**リスク**: 低。is_top3の学習に影響なし。

---

### A-2. ランキング学習（LambdaRank） ★中期

**現状**: 二値分類（is_top3）→ 着順の序列情報を捨てている。

**提案**: LightGBMの `objective='lambdarank'` でレース内順位を直接学習。
```python
# 着順をrelevanceラベルに変換
# 1着=5, 2着=4, 3着=3, 4着=2, 5着=1, 6着以下=0
params = {'objective': 'lambdarank', 'metric': 'ndcg'}
```

**根拠**:
- 「1着と2着の差」「3着と4着の差」を学習できる
- 3着内/外の二値より情報量が豊富
- Harville公式で組合せ馬券確率に変換可能

**工数**: experiment_v3.pyの目的関数変更 + group_queryパラメータ設定。
特徴量モジュールは変更不要。
**リスク**: 中。キャリブレーションの方法が変わる（確率出力ではなくスコア出力）。

---

### A-3. 着差ベース回帰 ★中期

**現状**: 着順（序数）のみ使用。着差（連続値）は捨てている。

**提案**: 「1着との着差（秒）」を目的変数とした回帰モデル。
```
target = time - winner_time  # 0.0 = 1着、正の値 = 遅い
```

**根拠**:
- 0.1秒差の5着 vs 3秒差の5着は全く違う（alternative_target_variables §着差）
- 「接戦で負けた馬」を検出 → 次走の巻き返し候補
- 回帰出力をsoftmaxで確率化すればHarvilleと統合可能

**工数**: SE_DATAの`time`フィールドから計算。データ準備は容易。
**リスク**: 中。距離・馬場差の標準化が必要（2000m良と1200m重の1秒は別物）。

---

### A-4. Multi-task学習 ★長期

**提案**: is_top3 + is_win + 着差を同時に学習するマルチタスクモデル。
**工数**: LightGBMではネイティブ非対応。PyTorch/NNに移行が必要。
**リスク**: 高。アーキテクチャ刷新。Phase 4以降。

---

## Part B: 新特徴量アイデア（実装容易順）

### Tier 1: データ準備済・コード数行 ★すぐやれる

#### B-1. 競馬ブック印・レーティング

**データ**: kb_ext JSONの `honshi_mark`, `mark_point`, `rating`, `aggregate_mark_point`

**提案する特徴量**:
| 特徴量 | 説明 | Model B |
|--------|------|---------|
| `kb_mark_point` | 本誌印ポイント（◎=5, ○=4, ▲=3, △=2, ×=1, 無=0） | 除外（市場相関高） |
| `kb_aggregate_mark_point` | 全記者総合ポイント | 除外 |
| `kb_rating` | keibabookレーティング値 | o（独自指標） |
| `kb_mark_consensus` | 印の一致度（全員◎=高、ばらつき=低） | o |

**根拠**:
- プロの目利き情報が数値化済みなのに未使用
- `kb_rating`は市場オッズと独立した能力評価 → Model Bに投入可能
- 印のばらつき（consensus）は「見解が割れる馬」= 妙味ある馬の検出

**工数**: training_features.pyに10行追加程度。kb_ext既存のフィールドを読むだけ。

---

#### B-2. 展開予想データ（tenkai_data）

**データ**: kb_ext JSONの `tenkai_data` → 各馬の予想ポジション（逃げ/好位/中位/後方）

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `predicted_position_category` | 逃げ=0, 好位=1, 中位=2, 後方=3 |
| `num_front_runners` | 同レース内の逃げ予想馬の数 |
| `pace_forecast` | 予想ペース（H=0, M=1, S=2） |
| `position_vs_style_match` | 予想ポジションと過去脚質の一致度 |

**根拠**:
- 現行のペース特徴量は過去走RPCIベース（過去のレースのペース）
- tenkai_dataは「今回のレースの展開予想」→ 直接的な情報
- 逃げ馬頭数は候補特徴量に既にリストアップ済みだが、tenkai_dataから直接取れる

**工数**: pace_features.pyに20行追加。kb_extのtenkai_dataフィールドをパース。

---

#### B-3. 上がり3F順位 vs 着順ギャップ

**データ**: horse_history_cacheの `last_3f` + `finish_position`

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `l3_rank_vs_finish_gap_last3` | 直近3走の（上がり3F順位 - 着順）平均。正=脚はあるが展開不利 |
| `l3_rank_best_last5` | 直近5走の上がり3F最高順位 |

**根拠**:
- features.md高優先に既にリスト。考察でも繰り返し言及
- 「上がり最速だが4着」= 展開不利で力を出せなかった → 巻き返し候補
- past_features.pyに追加。レース内での上がり順位計算が必要

**工数**: past_features.pyにヘルパー関数追加。horse_historyにlast_3fデータあり。

---

#### B-4. 着順標準偏差・安定度

**データ**: horse_history_cacheの `finish_position`

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `finish_std_last5` | 直近5走着順の標準偏差（小=安定、大=ムラ） |
| `comeback_strength_last5` | 盛り返し強度: (コーナー最悪順位-着順)/頭数 の平均 |

**根拠**:
- ability_is_not_scalar: タイプA（安定）vsタイプC（一発型）を数値化
- 馬券種別最適化: 安定型→複勝・ワイド、一発型→単勝・三連単1着固定
- horse_performance_distribution の核心概念を特徴量化

**工数**: past_features.pyに15行。既存データから計算可能。

---

#### B-5. 騎手乗り替わりフラグ

**データ**: horse_history_cacheの `jockey_code`

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `jockey_change` | 騎手乗り替わり（0=継続, 1=変更） |
| `jockey_quality_diff` | 新騎手top3率 - 旧騎手top3率（正=グレードアップ） |

**根拠**:
- 乗り替わりは市場が過剰反応する要因の一つ
- 有名→無名騎手への乗り替わりでオッズ上昇 → Value機会
- 逆に無名→有名への乗り替わりは期待先行でオッズ過小

**工数**: rotation_features.pyに15行。horse_historyの前走jockey_codeと比較。

---

#### B-6. コース詳細（track_cd細分化）

**データ**: SE_DATAの `track_cd`（現在は芝=0/ダート=1に丸めている）

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `course_direction` | 左回り=0, 右回り=1 |
| `course_variant` | 内回り=0, 外回り=1, A/Bコース=2 |

**根拠**:
- 左右回りで得意不得意が分かれる馬は多い（特に若馬）
- 阪神内回り vs 外回りは全く別コース（コーナー角度・直線長）
- track_cdは10=芝左、11=芝右、17=芝右外 等で詳細区分あり

**工数**: base_features.pyのtrack_cd解析を細分化。マッピングテーブル追加。

---

#### B-7. 季節性・開催週

**データ**: race_dateから計算

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `month` | 月（1-12） |
| `meet_week` | 開催何週目（1=開幕週、8=最終週） |
| `is_first_week` | 開幕週フラグ（馬場が良い→先行有利傾向） |

**根拠**:
- 開幕週は芝が荒れておらず内枠・先行有利（競馬の常識）
- 最終週は馬場が荒れて外差し有利
- 冬場は芝の成長が遅く馬場差が大きい

**工数**: base_features.pyに5行。race_dateから計算。
開催週の算出にはkaisai_data JSONの参照が必要。

---

### Tier 2: データ準備済・中規模変更 ★次のスプリント

#### B-8. 複勝オッズ（place odds）

**データ**: mykeibadb `odds1_fukusho_jikeiretsu`（時系列）

**提案する特徴量**:
| 特徴量 | 説明 | Model B |
|--------|------|---------|
| `place_odds` | 複勝オッズ | 除外 |
| `win_place_odds_ratio` | 単勝オッズ / 複勝オッズ | 除外 |

**根拠**:
- `win_place_odds_ratio` は馬の「安定度」の市場評価
  - 比率が高い = 「勝つ可能性は低いが3着には来る」と市場が評価
  - タイプBの検出に使える
- 単勝オッズだけでは捉えられない市場の見方

**工数**: experiment_v3.pyのDB取得クエリに複勝テーブルを追加。
predict.pyにも同様の修正。

---

#### B-9. 前走レースレベル（相手関係） ★重点項目

「G1の5着」と「未勝利の5着」を区別する情報がモデルに不足している。
2段階アプローチでレースレベルを推定する。

##### Phase 1: レーティングベース（Sprint 2で実装可能）

**データ**: kb_ext_index（全レースのkb_ext JSON）の `rating` フィールド

**設計**:
```
前走race_id → kb_ext_index[prev_race_id] → 全出走馬のrating取得 → 集計
```

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `prev_race_avg_rating` | 前走出走メンバーのkb_rating平均（レースレベル） |
| `prev_race_max_rating` | 前走出走メンバーのkb_rating最高値（トップレベル） |
| `prev_race_rating_rank` | 前走レース内での自馬のrating順位 |
| `class_change` | クラス変動（昇級=1, 同級=0, 降級=-1） |

**実装方式**:
```python
# compute_features_for_race 内で:
# 1. 全レースのkb_ext_indexは既にメモリにある
# 2. horse_history_cacheから前走race_idを取得
# 3. kb_ext_index[prev_race_id].entries の全rating集計

def compute_prev_race_level(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
    kb_ext_index: dict,  # 既存のインデックスを流用
) -> dict:
    past = [r for r in history_cache.get(ketto_num, []) if r['race_date'] < race_date]
    if not past:
        return {'prev_race_avg_rating': None, ...}

    prev_race_id = past[-1]['race_id']
    prev_kb = kb_ext_index.get(prev_race_id)
    if not prev_kb:
        return {'prev_race_avg_rating': None, ...}

    ratings = [e.get('rating') for e in prev_kb['entries'].values() if e.get('rating')]
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        max_rating = max(ratings)
    ...
```

**工数**: 中。新規モジュール `race_level_features.py` 作成。
kb_ext_indexは既にexperiment_v3.pyのcompute_features_for_raceに渡されているため、
引数の追加だけで利用可能。predict.pyにも同様のkb_ext_index参照を追加。

**注意点**:
- kb_ext未スクレイピングの古いレースではrating=Noneが多い → LightGBMのNaN処理に委ねる
- ratingのカバレッジ: kb_ext 10,000レース中、rating付きは要確認
- 将来Phase 2で精度向上したら、Phase 1のrating特徴量と比較してどちらが有用か検証

##### Phase 2: タイムランクベース（中長期）

**設計思想**:
走破タイムからスピード指数を算出し、レース全体の水準をレベル化する。

```
レースレベル = f(出走馬の走破タイム分布, 馬場差, 距離基準タイム)
```

**必要な前処理**:
1. **距離別基準タイム**: 各距離の過去N年の平均走破タイム
2. **馬場差推定**: 同日・同コース・同距離の複数レースから馬場補正値を推定
   - 当日開催の全レースのタイムを距離基準タイムと比較
   - 中央値の差 = その日の馬場差
3. **スピード指数計算**: `SI = (基準タイム - 走破タイム + 馬場差) × 距離係数`

**レースレベル指標**:
| 指標 | 説明 |
|------|------|
| `race_time_rank` | レース1着タイムのスピード指数（高=ハイレベル） |
| `race_avg_si` | レース上位3頭の平均スピード指数 |
| `race_level_class` | A/B/C/D/Eの5段階分類 |

**前走レースレベル特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `prev_race_time_rank` | 前走のレースタイムランク |
| `prev_race_si_self` | 前走での自馬のスピード指数 |
| `prev_race_si_rank` | 前走レース内での自馬SI順位 |
| `si_trend_last3` | 直近3走のSIトレンド（改善/悪化） |

**実装ロードマップ**:
1. 距離別基準タイムの算出スクリプト作成
2. 馬場差推定ロジック実装（同日同コースの全レースから推定）
3. スピード指数計算モジュール作成
4. レースレベル分類の閾値設定（AUC等で検証）
5. 特徴量モジュールへの統合

**工数**: 大。馬場差推定のロジック設計が最大のボトルネック。
「keibabookのスピード指数（`speed_indexes`）」をベースラインとして、
自前SI計算はPhase 2の精度を超えた場合のみ採用。

**根拠**:
- 「G1で5着」と「未勝利で5着」を区別する情報がモデルに必要
- Phase 1（rating）でまず効果を確認し、Phase 2で精密化
- 馬場差推定は困難だが、一度基盤を作れば全特徴量に波及効果がある

---

#### B-10. 調教セッション詳細

**データ**: kb_ext JSONの `cyokyo_detail.sessions`（2-9セッション/馬）

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `training_intensity_trend` | セッション間の追い切り強度変化（仕上げ過程） |
| `training_total_5f_load` | 全セッション5Fタイム合計（練習量） |
| `training_best_vs_avg_gap` | 最速セッション - 平均（ポテンシャル） |
| `training_awase_win_rate` | 併せ馬での先着率 |

**根拠**:
- 現行は追い切り（最終調教）のサマリーのみ使用
- 仕上げ過程（徐々に強度上げ → 最終で一杯）は仕上がりの良さを示す
- 併せ馬での先着/遅れは直接的な能力比較

**工数**: training_features.pyを拡張。sessions配列のパースロジック追加。

---

#### B-11. 血統特徴量

**データ**: horse_history_cache or UM_DATAの血統情報

**提案する特徴量**:
| 特徴量 | 説明 |
|--------|------|
| `sire_distance_top3_rate` | 父の産駒の当該距離帯での複勝率 |
| `sire_track_type_top3_rate` | 父の産駒の芝/ダート別複勝率 |
| `sire_track_cond_top3_rate` | 父の産駒の馬場状態別複勝率 |
| `broodmare_sire_top3_rate` | 母父の産駒の全体複勝率 |

**根拠**:
- 血統は距離適性・馬場適性の最も基本的な指標
- 特に若馬（データ少）で威力を発揮: 過去走がなくても血統から推定可能
- 「ディープインパクト産駒は東京芝2400mで強い」等の常識を数値化

**工数**: 新規モジュール `blood_features.py` 作成。
種牡馬別・条件別の集計テーブルを事前構築する必要あり。

---

### Tier 3: 新規データ取得・大規模変更 ★将来

#### B-12. JRA-VAN調教データ（HC/WC_DATA）

**データ**: C:/TFJV/HC_DATA, WC_DATA（バイナリ、パーサー未実装）

**提案する特徴量**:
- 坂路4F/3F/2F/1F全ラップ
- コース調教10F〜1F全ラップ
- 調教回数・頻度（JRA-VAN公式データで網羅的）
- keibabook調教データとの突合・補完

**根拠**: keibabook調教データはスクレイピング依存でカバレッジに限界。
JRA-VANネイティブデータは全馬の全調教を網羅。

**工数**: HC/WCパーサーの新規実装が必要。バイナリフォーマット解析→JSON変換。

---

#### B-13. 馬主クラブ分類・応援馬券効果

**データ**: UM_DATAの `owner_name`

**提案する特徴量**:
| 特徴量 | 説明 | Model B |
|--------|------|---------|
| `owner_type` | 個人/中小クラブ/大手クラブの3分類 | o |
| `owner_club_size_estimate` | クラブの推定会員数（大=応援馬券大） | 除外 |

**根拠**: market_structural_inefficiencies §4「応援馬券バイアス」
- DMMバヌーシー等の大手クラブ馬は応援馬券でオッズが下がる
- Model Bでowner_typeを使えば「大手クラブ馬の能力」を分離評価
- EV計算時に応援馬券効果を割り引く

**工数**: owner_nameのクラブ名辞書作成（手動50件程度）+ base_features拡張。

---

#### B-14. パフォーマンススコア目的変数

**提案**: 着順の代わりにパフォーマンススコアを目的変数にする。
```
score = クラス基準値 + 着差補正(α) + 上がり3F補正(β) + 斤量補正(γ)
```

**根拠**: alternative_target_variables の3層構造設計。
G1の10着 > 未勝利の1着を自然に表現。

**工数**: 大。クラス基準値・補正係数の設計が恣意的。
回帰式の妥当性検証に大量の実験が必要。

---

## Part C: 推奨実装ロードマップ

### Sprint 1: 既存データ活用の即効特徴量 ✅ 実装済 (v4.0)

| # | アイデア | 変更ファイル | 新特徴量数 | 状態 |
|---|---------|-------------|-----------|------|
| B-1 | KB印・レーティング | training_features.py | +3 | ✅ `kb_mark_point`, `kb_aggregate_mark_point`, `kb_rating` |
| B-3 | 上がり3F最速・L3未報酬率 | past_features.py, pace_features.py | +2 | ✅ `best_l3f_last5`, `l3_unrewarded_rate_last5` |
| B-4 | 着順標準偏差・盛り返し | past_features.py | +2 | ✅ `finish_std_last5`, `comeback_strength_last5` |
| B-5 | 騎手乗り替わり | rotation_features.py | +1 | ✅ `jockey_change` |
| B-7 | 季節・開催日 | base_features.py | +2 | ✅ `month`, `nichi` |

**計**: +11特徴量（Model A: 67→78, Model B: 63→72）
- `kb_mark_point`, `kb_aggregate_mark_point` はMARKET扱い（Model B除外）

### Sprint 2（次）: レースレベル + 中規模データ統合

| # | アイデア | 変更ファイル | 新特徴量数 | 備考 |
|---|---------|-------------|-----------|------|
| B-9 Phase1 | **前走レースレベル（レーティング版）** | 新規race_level_features.py | +3-4 | ★重点。kb_ext_indexのrating集計 |
| B-2 | 展開予想データ | pace_features.py | +3-4 | tenkai_dataの逃げ馬頭数等 |
| B-6 | コース詳細 | base_features.py | +2 | 左右回り・内外コース |
| B-8 | 複勝オッズ | experiment_v3.py, predict.py | +2 | 単複比率 |
| A-1 | is_winモデル追加 | experiment_v3.py | (目的変数) | Model C |

### Sprint 3（中期）: 新モジュール・アーキテクチャ

| # | アイデア | 変更ファイル | 備考 |
|---|---------|-------------|------|
| B-9 Phase2 | **前走レースレベル（タイムランク版）** | 新規speed_index_engine.py | 馬場差推定→SI→レースレベル |
| B-10 | 調教セッション詳細 | training_features.py | セッション配列パース |
| B-11 | 血統特徴量 | 新規blood_features.py | 種牡馬別集計テーブル |
| A-2 | ランキング学習 | experiment_v3.py | 目的関数変更 |
| B-13 | 馬主クラブ分類 | base_features.py | クラブ名辞書作成 |

---

## Part D: 実験時の注意事項

### 1. 特徴量追加の検証プロトコル

```
1. ベースライン計測（現行v3.5のAUC/Brier/ECE）
2. 特徴量追加（1カテゴリずつ）
3. 同一split条件で再学習
4. AUC差 + Brier差 + ECE差を記録
5. Value Bet ROI（gap≥3）を再計算
6. 効果なし or 悪化の特徴量は除外
```

### 2. 目的変数変更時の注意

- is_top3 → is_win: 正例比率が30%→7%に激減。`is_unbalance`対策必要
- ランキング学習: 確率出力ではなくスコア → キャリブレーション方法が変わる
- 着差回帰: 距離・馬場の標準化が必須。外れ値（大差負け）の処理

### 3. 市場系特徴量の分類基準

| 分類 | Model A | Model B | 判断基準 |
|------|---------|---------|---------|
| 市場直接 | o | × | odds, popularity |
| 市場間接 | o | △要検討 | kb_mark_point（印=市場と相関） |
| 独立評価 | o | o | kb_rating（独自算出値） |
| 能力代理 | o | o | owner_type（馬の質の間接指標） |

---

**タグ**: #特徴量 #目的変数 #モデル設計 #ロードマップ #v4計画
**最終更新**: 2026-02-14（カカシ）

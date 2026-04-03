# 妙味度名鑑 知見の実装・検証プラン

> Session 113 (2026-03-20)
> 前提: `myomido_meikan_analysis.md` の分析結果に基づく

---

## Phase 0: データ検証（本書の仮説を自前データで確認）

MLに組み込む前に、まず自前データで本書の主張が再現できるか確認する。
これ自体がデータ理解を深め、後の特徴量設計に直結する。

### 検証0-1: 複勝オッズの人気バイアス確認
**目的**: 「低オッズ馬ほど複勝回収率が高い（約10%差）」は本当か？
**方法**:
- horse_history_cache + mykeibadb.odds1_fukushoから複勝オッズを取得
- 複勝オッズ帯別（1倍台/2倍台/.../10倍以上）に複勝回収率を集計
- グラフ化して構造的偏りの有無・程度を確認
**データ**: mykeibadb（複勝オッズはDB限定、2020年以降が現実的）
**工数**: 小（分析スクリプト1本）
**意義**: 偏りが確認できればbet_engineの補正係数に直結

### 検証0-2: ダート種牡馬の過小評価確認
**目的**: 「ダート系種牡馬は常に過小評価」は自前データでも成立するか？
**方法**:
- horse_history_cacheから種牡馬×馬場(芝/ダート)別に単勝回収率を集計
- 種牡馬を「芝系」「ダート系」「両刀」に分類
- 各グループの平均単勝回収率を比較
**データ**: horse_history_cache（odds + finish_position + sire_id）
**工数**: 小
**意義**: 確認できれば sire_surface_type をbet_engine補助指標に

### 検証0-3: 種牡馬×距離変更の回収率差
**目的**: 「エピファネイア距離短縮-6399 / キズナ距離延長+3684」レベルの差が再現できるか？
**方法**:
- horse_history_cacheから前走距離を取得
- 距離変更方向(短縮/延長/同距離)×種牡馬別に単勝回収率を集計
- 主要種牡馬20頭程度で短縮ROI vs 延長ROIの差を確認
**データ**: horse_history_cache（prev_distance計算可能）
**工数**: 中（前走距離の紐付けが必要）
**意義**: 差が大きければ★★★の交互作用特徴量の根拠になる

### 検証0-4: 騎手/厩舎の「条件別回収率」安定性
**目的**: 条件別回収率は年度を跨いで安定するか？（= 予測に使えるか）
**方法**:
- horse_history_cacheから騎手×条件(芝/ダート/競馬場)別に年度別回収率を算出
- 前年の回収率と翌年の回収率の相関を検証
- 相関が高い条件 = 予測力がある = 特徴量として有用
**データ**: horse_history_cache
**工数**: 中
**意義**: 相関が低ければ特徴量にしても意味がない（本書の時間重み付けの妥当性検証にもなる）

### 検証0-5: 知名度変化と妙味度の関係
**目的**: 「人気が急上昇した騎手/厩舎は妙味度が下がる」は定量化できるか？
**方法**:
- 騎手/厩舎ごとに半年単位の「平均人気順位」を計算
- 平均人気が急上昇（= 人気馬に多く乗るようになった）した期間の回収率変化を確認
- 人気度変化率と回収率変化の相関を検証
**データ**: horse_history_cache（popularity フィールド）
**工数**: 中
**意義**: 有意であればbet_engineの「人気急上昇」ディスカウント要因に

---

## Phase 1: 一時インデックス構築（特徴量の前段階）

Phase 0で効果が確認された項目について、レース予測時に参照可能なインデックスを構築する。
sire_stats_index.json と同じ発想で、条件別の補正回収率を事前計算して保存。

### 1-1: jockey_myomido_index.json
**構造**:
```json
{
  "01134": {
    "overall": { "myomido": 103, "profit": 1200, "runs": 450 },
    "turf": { "myomido": 98, "runs": 200 },
    "dirt": { "myomido": 108, "runs": 250 },
    "place_01": { "myomido": 112, "runs": 45 },
    "sprint": { "myomido": 105, "runs": 180 },
    "mid": { "myomido": 101, "runs": 200 },
    "long": { "myomido": 97, "runs": 70 },
    "heavy": { "myomido": 115, "runs": 60 },
    "yearly": {
      "2021": { "myomido": 95, "runs": 80 },
      "2022": { "myomido": 102, "runs": 90 },
      ...
    }
  }
}
```
**算出方法**: 本書の3ステップ簡略版
1. 単勝回収率ベース（複勝オッズがDB限定のため）
2. 人気帯別の期待回収率との差分で人気バイアス近似除去
3. 年度重み 0.2→1.0 + runs重み

### 1-2: sire_dist_change_index.json
**構造**:
```json
{
  "sire_id_xxx": {
    "shorten": { "roi": 85, "top3_rate": 0.22, "runs": 150 },
    "extend": { "roi": 112, "top3_rate": 0.35, "runs": 130 },
    "same": { "roi": 95, "top3_rate": 0.28, "runs": 400 },
    "shorten_edge": -10,
    "extend_edge": 17
  }
}
```
**意義**: pedigree_features.pyで直接参照可能。LightGBMに入れるのは `shorten_edge` / `extend_edge` のスカラー値。

### 1-3: trainer_rotation_index.json
**構造**:
```json
{
  "01202": {
    "layoff_1st": { "top3_rate": 0.28, "roi": 95, "runs": 80 },
    "layoff_2nd": { "top3_rate": 0.32, "roi": 110, "runs": 70 },
    "layoff_3rd": { "top3_rate": 0.30, "roi": 100, "runs": 65 },
    "consecutive": { "top3_rate": 0.18, "roi": 70, "runs": 20 }
  }
}
```

---

## Phase 2: ML特徴量化

Phase 1のインデックスからMLモデル用の特徴量を抽出する。

### 2-1: 妙味度系特徴量（bet_engine/Wモデル向け）

```python
# jockey_features.py に追加
jockey_myomido_overall    # 騎手の全体妙味度
jockey_myomido_surface    # 騎手×当該馬場の妙味度
jockey_myomido_course     # 騎手×当該競馬場の妙味度
jockey_myomido_confidence # 妙味度の信頼度（runs数ベース）
```

**注意点**:
- Pモデル（着順予測）には入れない方がよい可能性
  - 妙味度は「回収率」の指標であり「勝率」とは異なる
  - Pモデルは純粋な能力予測に集中すべき
- **Wモデル（勝率予測 = 市場との乖離検出）には効果大の可能性**
- bet_engineの補助指標としても直接使える

### 2-2: 種牡馬×距離変更交互作用（P/Wモデル両方向け）

```python
# pedigree_features.py に追加
sire_dist_change_edge     # 種牡馬の距離変更適性（短縮/延長時の成績差）
sire_dist_shorten_top3    # 距離短縮時のtop3率
sire_dist_extend_top3     # 距離延長時のtop3率
```

**これはPモデルにも有用** — 距離変更への適性は純粋な能力指標

### 2-3: 厩舎×ローテーション交互作用

```python
# trainer_features.py に追加
trainer_layoff_performance  # 厩舎の休み明け適性（全体top3率との差分）
trainer_consecutive_penalty # 厩舎の連闘時ペナルティ
```

---

## Phase 3: bet_engine拡張

ML特徴量とは別に、bet_engine側で直接活用できる知見。

### 3-1: 人気バイアス補正係数

```python
# bet_engine.py に追加
def popularity_bias_correction(place_odds):
    """複勝オッズ帯別の期待回収率補正"""
    if place_odds < 1.5:
        return 1.05  # 低オッズ帯は実際には回収率が高い
    elif place_odds < 3.0:
        return 1.02
    elif place_odds < 10.0:
        return 1.00  # 基準
    else:
        return 0.95  # 高オッズ帯はまぐれ込み
```
※ Phase 0-1の検証結果で実際の係数を決定

### 3-2: 妙味度スコアによるbet調整

```python
# bet_engine.py に追加
def myomido_adjustment(jockey_myomido, sire_myomido, trainer_myomido):
    """3者の妙味度合計でbet金額を調整"""
    combined = (jockey_myomido + sire_myomido + trainer_myomido) / 3
    if combined > 110:
        return 1.2   # 妙味度高 → ベット増額
    elif combined > 100:
        return 1.0   # 中立
    else:
        return 0.8   # 妙味度低 → ベット減額
```

### 3-3: 人気度変化率ディスカウント

```python
# 直近6ヶ月の平均人気 vs 過去1年の平均人気を比較
# 人気急上昇中 → 妙味度低下中と推定してベット控えめ
def popularity_trend_discount(recent_avg_pop, historical_avg_pop):
    trend = recent_avg_pop / historical_avg_pop  # <1 = 人気上昇
    if trend < 0.8:  # 20%以上人気上昇
        return 0.85  # 15%ディスカウント
    return 1.0
```

---

## Phase 4: Web表示・分析ツール

### 4-1: 妙味度ダッシュボード（/demo/myomido）
- 騎手/種牡馬/厩舎の妙味度ランキング
- 条件別のヒートマップ（競馬場×騎手の妙味度マトリクス等）
- 本書のランキングとの比較表示

### 4-2: レース画面への統合
- 各出走馬の「妙味度スコア」をバッジ表示
- 騎手/種牡馬/厩舎の条件マッチング状況

---

## 実施スケジュール案

| Phase | 内容 | 前提条件 | 優先度 |
|-------|------|----------|--------|
| **0-1** | 複勝人気バイアス検証 | なし | ★★ |
| **0-2** | ダート種牡馬過小評価検証 | なし | ★★ |
| **0-3** | 種牡馬×距離変更検証 | なし | ★★★ |
| **0-4** | 条件別回収率安定性検証 | なし | ★★★ |
| **0-5** | 知名度変化と回収率 | なし | ★ |
| **1-1** | jockey_myomido_index | 0-4で相関確認 | ★★ |
| **1-2** | sire_dist_change_index | 0-3で差確認 | ★★★ |
| **1-3** | trainer_rotation_index | 0-4で相関確認 | ★ |
| **2-1** | 妙味度ML特徴量 | Phase1完了 | ★★ |
| **2-2** | 種牡馬×距離変更特徴量 | 1-2完了 | ★★★ |
| **2-3** | 厩舎×ローテ特徴量 | 1-3完了 | ★ |
| **3-1** | 人気バイアス補正 | 0-1完了 | ★★ |
| **3-2** | 妙味度bet調整 | Phase1完了 | ★★ |
| **3-3** | 人気変化ディスカウント | 0-5完了 | ★ |

### 推奨する初手
**Phase 0-3（種牡馬×距離変更）と Phase 0-4（条件別回収率安定性）を並行実施**
→ 両方とも horse_history_cache だけで完結し、結果次第でPhase 1-2/2-2に直結する

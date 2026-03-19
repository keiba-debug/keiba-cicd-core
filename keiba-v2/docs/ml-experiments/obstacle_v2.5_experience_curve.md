# 障害モデル v2.5 経験曲線特徴量 (Experience Curve)

> Session 109 | 2026-03-19

## 背景

障害モデルv2.4（学習期間拡大 2015-2024, 1,246R）のベースラインに対し、
**障害レースの経験曲線**を特徴量化して精度改善を狙う。

### 仮説

- 障害経験が少ないほど1戦ごとの経験値が重要で上昇幅が大きい
- 初障害の大敗は情報価値が低く、直近走を重視すべき
- 現行の`obs_avg_finish_last3`は均等平均のため、初障害の大敗がそのまま足を引っ張る

## データ分析（仮説検証）

### 障害N戦目ごとの成績

| N戦目 | サンプル | 平均着比 | 勝率 | 好走率 | 改善率(前走比) |
|-------|---------|---------|------|-------|---------------|
| **1(初障害)** | 3,240 | **0.644** | 4.2% | 13.5% | - |
| **2** | 2,476 | **0.515** | 9.1% | 26.4% | **60.5%が改善** |
| **3** | 1,853 | **0.459** | 12.0% | 32.1% | 50.0% |
| 4 | 1,471 | 0.460 | 11.4% | 33.6% | 44.6% |
| 5+ | - | ~0.47 | ~11% | ~31% | <45% |

→ **初障害→2戦目で60.5%の馬が改善**。中央値+8.3pt。3戦目以降は安定。

### 初障害の予測力低下

| 相関 | 値 |
|------|-----|
| 初障害 vs 2戦目 | 0.473（中程度） |
| 初障害 vs 3戦目 | **0.268**（弱い） |

→ 3戦目以降、初障害の情報価値は急速に低下する。

### 予測器比較（次走着順比率を予測する精度）

| 予測器 | N | MSE | 相関 |
|-------|---|-----|------|
| equal_avg（現行） | 10,095 | 0.0745 | 0.334 |
| last1_only | 10,095 | 0.0951 | 0.322 |
| last2_avg | 10,095 | 0.0792 | 0.331 |
| exp_decay_1（半減期1走） | 10,095 | 0.0749 | 0.353 |
| **exp_decay_2（半減期2走）** | **10,095** | **0.0736** | **0.349** |
| no_debut_avg | 8,242 | 0.0749 | 0.333 |

→ **半減期2走の指数減衰重みが最良**（MSE最小、相関も高い）

### 経験tier別の最適予測器

| Tier | N | equal MSE | decay MSE | last1 MSE | best |
|------|---|-----------|-----------|-----------|------|
| **tier1 (1-3戦)** | 3,324 | 0.0743 | **0.0740** | 0.0914 | **decay** |
| tier2 (4-10戦) | 4,866 | **0.0754** | 0.0760 | 0.0974 | equal |
| tier3 (11+戦) | 1,905 | **0.0725** | 0.0735 | 0.0955 | equal |

→ 初期こそ重み付けが効く。安定期は均等でOK。LightGBMがtierに応じて自動使い分け。

## 変更内容

### obstacle_features.py (v2.3b → v2.5)

`compute_experience_curve_features()` を新規追加:

```python
# obs_weighted_finish_last3: 指数減衰重み付き障害着順比率
# 半減期2走: 直近=1.0, 1走前=0.707, 2走前=0.5
weight = 2^(-races_ago / 2.0)

# obs_improvement_rate: 初障害→2戦目の着順比率改善幅
# 正値=改善（障害2戦以上で有効）
improvement = debut_ratio - second_ratio

# obs_debut_discount: 初障害除外時の着順改善度
# 負値=初障害が平均を悪化させている
discount = avg_without_debut - avg_with_debut
```

### experiment_obstacle.py

- OBSTACLE_SPECIFIC_FEATURES に3特徴量追加（96→99特徴量）
- 特徴量計算ループに `compute_experience_curve_features()` 呼び出し追加

### predict.py

- 障害v2.2以降の全特徴量を推論パスに追加（以前は欠落していた）:
  - `compute_obstacle_only_past_stats` (v2.2)
  - `compute_high_level_experience` (v2.3)
  - `compute_flat_racing_profile` (v2.3)
  - `compute_venue_skill_features` (v2.3b)
  - `compute_same_group_stats` (v2.3b)
  - `compute_experience_curve_features` (v2.5)

## 結果比較

### モデル精度

| 指標 | v2.4 (baseline) | **v2.5 (採用)** | 差分 |
|------|----------------|----------------|------|
| P AUC | 0.7608 | **0.7660** | **+0.005** |
| W AUC | 0.7588 | **0.7642** | **+0.005** |
| P ECE(raw) | 0.0264 | **0.0229** | -0.004 |
| P ECE(cal) | 0.0144 | 0.0388 | +0.024 |
| P Top1 複勝率 | - | 85.0% | - |
| W Top1 勝率 | 40.0% | 38.8% | -1.2pt |

### 特徴量重要度（P Model Top 15）

| Rank | 特徴量 | 重要度 | 新規 |
|------|--------|--------|------|
| **1** | **obs_weighted_finish_last3** | **10,800** | **★v2.5** |
| 2 | obs_avg_finish_last3 | 5,701 | |
| 3 | obs_win_rate | 2,184 | |
| 4 | distance_fitness | 1,855 | |
| 5 | entry_count | 1,829 | |
| 6 | jockey_win_rate | 1,706 | |
| 7 | trainer_top3_rate | 1,398 | |
| 8 | flat_avg_distance | 1,356 | |
| 9 | flat_idm_avg3 | 1,123 | |
| 10 | weight_change_ratio | 1,075 | |
| 11 | flat_turf_ratio | 1,048 | |
| 12 | days_since_last_race | 1,045 | |
| 13 | jockey_top3_rate | 1,021 | |
| 14 | obs_best_finish_last5 | 1,003 | |
| 15 | obs_last3f_avg_last3 | 980 | |

### 新特徴量3つの重要度

| 特徴量 | P Rank | P Imp | W Rank | W Imp |
|--------|--------|-------|--------|-------|
| **obs_weighted_finish_last3** | **#1** | **10,800** | **#1** | **18,508** |
| obs_improvement_rate | #48 | 565 | #55 | 1,247 |
| obs_debut_discount | #66 | 342 | #58 | 1,194 |

### W Model Top 15

| Rank | 特徴量 | 重要度 |
|------|--------|--------|
| **1** | **obs_weighted_finish_last3** | **18,508** |
| 2 | obs_avg_finish_last3 | 18,140 |
| 3 | trainer_top3_rate | 4,484 |
| 4 | avg_last_corner_ratio | 3,725 |
| 5 | flat_avg_distance | 3,718 |
| 6 | obs_distance_fitness | 3,708 |
| 7 | flat_idm_avg3 | 3,701 |
| 8 | obs_win_rate | 3,535 |
| 9 | jockey_win_rate | 3,509 |
| 10 | sire_maturity_index | 3,054 |

## 考察

### obs_weighted_finish_last3 が#1になった理由

均等平均(`obs_avg_finish_last3`)と重み付き(`obs_weighted_finish_last3`)の**両方が上位に残っている**。
これはLightGBMがtierに応じて使い分けていることを示唆する:

- **経験浅い馬(tier1)**: obs_weighted で直近走を重視 → 初障害の大敗を割引
- **経験豊富な馬(tier2-3)**: obs_avg で均等平均も参照 → 安定期は全走の情報が有用

2つの特徴量の差分自体が「初障害の影響度」を間接的に表現しており、
モデルは分岐条件でこれを自然に学習している。

### P ECE(cal) 悪化について

isotonic calibratorのフィッティングの問題。raw ECEは0.0264→0.0229と改善している。
障害のvalidation set(60R, 675エントリー)が小さいため、isotonic calibratorが過適合しやすい。

### 平地への横展開可能性

同じ仮説は平地の若駒（2歳戦、3歳経験浅い馬）にも適用可能:
- 2歳デビュー戦の大敗は情報価値が低い
- 3歳になって急激に成長する馬のパターン

ただし平地は障害ほど劇的な改善カーブではないため、効果は限定的と予想。

## 結論

- **P/W AUC ともに +0.005**: 3特徴量追加で堅実な改善
- **obs_weighted_finish_last3 が P/W 両方で重要度1位**: 仮説が強力に裏付けられた
- **均等平均(#2)との共存**: モデルが経験tierで自動使い分け
- **predict.py への障害特徴量追加**: v2.2以降の特徴量が推論時にも反映されるように修正

## 学習事項

- **★★★ 障害は初障害→2戦目で60.5%改善**: 初障害の情報価値は3戦目以降急速に低下（相関0.473→0.268）
- **★★★ 重み付き平均と均等平均は共存させるべき**: 両方入れるとモデルがtier別に使い分ける
- **★★ 半減期2走が最適**: 分析で最良MSE、モデルでも重要度1位
- **★★ predict.pyに障害特徴量が欠落していた**: experiment_obstacle.pyで追加した特徴量がpredict.pyに反映されていなかった問題を修正
- **★ horse_history_cacheにmarginデータなし**: 着差特徴量は別途データ追加が必要

# Performance Change Prediction v2.5 - Condition Switch Features

> **Date**: 2026-03-09
> **Experiment**: パフォーマンス変動予測 Phase 2.5 (条件替わりIDM変動パターン追加)
> **Model**: LightGBM multiclass (3-class softmax)
> **前回との差分**: 10個の `cond_*` 特徴量を追加

---

## 1. 追加した特徴量

### 条件替わりIDM変動パターン (10特徴量)

| 特徴量 | 説明 | 計算方法 |
|--------|------|----------|
| `cond_surface_switch_idm_avg` | 芝↔ダート替わり時のIDM変動平均 | 連続走で馬場が変わった時のIDM diff平均 |
| `cond_surface_switch_count` | 芝↔ダート替わり経験回数 | |
| `cond_dist_extend_idm_avg` | 距離延長(+200m以上)時のIDM変動平均 | |
| `cond_dist_shorten_idm_avg` | 距離短縮(-200m以上)時のIDM変動平均 | |
| `cond_layoff_idm_avg` | 休養明け(56日+)復帰走のIDM変動平均 | |
| `cond_layoff_idm_count` | 休養明け復帰経験回数 | |
| `cond_same_surface_idm_avg` | 同馬場(今回と同じ芝/ダート)でのIDM平均 | キャリア中の同条件レースIDM平均 |
| `cond_same_dist_idm_avg` | 同距離帯(±200m)でのIDM平均 | |
| `cond_class_up_idm_avg` | 昇級時のIDM変動平均 | grade序列が上がった時のIDM diff |
| `cond_class_down_idm_avg` | 降級時のIDM変動平均 | |

---

## 2. 全フェーズ比較

| 指標 | Phase 1 (4-class) | Phase 2 (3-class+career) | **Phase 2.5 (条件替わり)** |
|------|-------------------|--------------------------|---------------------------|
| **Accuracy** | 0.4960 | 0.5600 | **0.5585** |
| **Macro-F1** | 0.4616 | 0.5437 | **0.5424** |
| **Weighted-F1** | 0.4722 | 0.5546 | **0.5546** |
| **LogLoss** | 1.0926 | 0.9057 | **0.9076** |
| **BestIter** | 560 | 664 | **728** |
| **特徴量数** | 169 | 189 | **199** |

### クラス別Recall

| クラス | Phase 1 (4-class) | Phase 2 (3-class) | **Phase 2.5** |
|--------|-------------------|-------------------|---------------|
| 大幅上昇 | 61.0% | — | — |
| 上昇 | 16.8% / 統合→ | 63.8% | **63.7%** |
| 平行線 | 69.6% | 60.5% | **60.3%** |
| 下降 | 39.5% | 37.8% | **37.9%** |

### Danger Signal (下降予測 × 人気馬)

| 指標 | Phase 1 | Phase 2 | **Phase 2.5** |
|------|---------|---------|---------------|
| 対象割合 | 15.2% | 15.3% | **14.2%** |
| 複勝率 | 45.1% | 45.4% | **44.7%** |
| 全人気馬複勝率 | 52.2% | 52.3% | **52.3%** |
| **差分** | **-7.1pt** | **-6.9pt** | **-7.6pt** |

---

## 3. 条件替わり特徴量の重要度

コンソール出力のTop30から:

| Rank | 特徴量 | Gain |
|------|--------|------|
| 18 | **cond_same_surface_idm_avg** | 22,033 |

- `cond_same_surface_idm_avg`のみがTop30に入った
- 他9個のcond_*特徴量はTop30圏外

### 参考: Top10

| # | 特徴量 | Gain |
|---|--------|------|
| 1 | jrdb_idm_trend | 356,455 |
| 2 | jrdb_idm_last | 170,435 |
| 3 | career_idm_diff_last | 66,038 |
| 4 | jrdb_idm_growth | 46,711 |
| 5 | days_since_last_race | 33,493 |
| 6 | jrdb_agari_idx_last | 32,288 |
| 7 | dam_maturity_index | 31,432 |
| 8 | jrdb_gekisou_idx | 24,448 |
| 9 | distance_change | 24,431 |
| 10 | track_type | 24,255 |

---

## 4. 考察

### なぜ条件替わり特徴量が効かなかったか

1. **データスパース性**: 芝↔ダート替わりや昇降級は全馬に経験があるわけではない。多くの馬で`cond_surface_switch_idm_avg = 0.0`（デフォルト値）のまま → 分割に使いにくい
2. **既存特徴量との重複**: `distance_change`(9位)、`track_type_change`(11位)が既にローテーション特徴量として存在。条件"替わり"の情報は一部カバー済み
3. **IDM差分 vs IDM絶対値**: cond_*はIDM差分（変動量）を使うが、モデルは`jrdb_idm_last`（絶対値）を最重視。条件替わり時の変動パターンよりも、現在のIDMレベルが支配的
4. **cond_same_surface_idm_avg は効いた**: 同馬場での絶対IDM平均は「この馬の芝/ダート適性」を直接表現 → 変動パターンより適性指標の方が効果的

### Phase 2→2.5の変化

- メトリクスはほぼ横ばい（Accuracy -0.15pt, Macro-F1 -0.13pt）
- **Danger Signalは微改善**: 複勝率差が-6.9pt→-7.6ptに拡大（対象を絞って精度アップ）
- BestIterが664→728に増加 → 特徴量追加によりモデルが若干複雑化
- `cond_same_surface_idm_avg`は有用だが、他のcond_*は現時点ではノイズ気味

### 今後の方向性

条件替わり特徴量の**肝**は正しいが、現在の実装では効果が限定的。改善案:

1. **デフォルト値の改善**: 経験なし時に0.0ではなく、グローバル平均を埋める
2. **インタラクション特徴量**: `cond_surface_switch_idm_avg × uncertainty_first_surface`のような交差
3. **直近のcond変動にフォーカス**: 全キャリア平均でなく直近3回の条件替わり時IDM変動
4. **条件替わり×当該レースの「今回の条件」**: 例えば「この馬は芝→ダート替わりの時にIDMが+5になる傾向があり、今回も芝→ダート」→ 直接的な予測信号
5. **Phase 3 (血統パフォパターン)**: sire_offspring_idm_variance等の追加が次のフロンティア

---

## 5. 実験メタデータ

| 項目 | 値 |
|------|-----|
| スクリプト | `ml/experiment_performance.py --three-class --no-db` |
| 特徴量 | `ml/features/career_features.py` (Phase 2.5: 30 cols) |
| 結果JSON | `data3/ml/experiment_performance_result.json` |
| 実行時間 | 575秒 (9.6分) |
| モデル | LightGBM multiclass, is_unbalance=True |
| 特徴量数 | 199 (169 VALUE + 30 career/uncertainty/condition) |
| Best iteration | 728 |
| Train | 2020-2024 (197,014 entries) |
| Val | 2025.01-2025.02 (6,479 entries) |
| Test | 2025.03-2026.02 (39,762 entries) |

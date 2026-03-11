# Performance Change Stacking v2 - K-fold OOF + dam_top3_rate除外

> **Date**: 2026-03-09
> **Experiment**: K-fold OOFスタッキング + Optunaリストからdam_top3_rate除外
> **方式**: 5-fold OOFでPerf予測を生成 → P/W/ARスタッキング

---

## 1. 変更点（v1 Stackからの差分）

### A. K-fold OOF (5-fold)
- 訓練データ(2020-2024)を5分割
- 各foldでPerfモデルを学習、未使用foldに予測
- Val/Testは全訓練データで学習したfull Perfモデルで予測
- perf_labelが計算不可(前走IDMなし)の行はfull modelでフォールバック

### B. Optuna dam_top3_rate除外
- `optuna_best_params.json`から3モデル全てのfeatureリストでdam_top3_rate除外
  - P: 139→138 features
  - W: 145→144 features
  - AR: 155→154 features
- **注意**: v7.3 baselineは`--exclude-features`で除外していたが、Optunaリストには残存していた。今回初めてOptunaリストからも除外

---

## 2. OOF Fold精度

| Fold | Accuracy | Best Iter |
|------|----------|-----------|
| 1 | 0.5631 | 831 |
| 2 | 0.5637 | 734 |
| 3 | 0.5624 | 849 |
| 4 | 0.5652 | 819 |
| 5 | 0.5602 | 774 |
| **平均** | **0.5629** | 801 |
| Full model | 0.5604 | 728 |

- 全fold安定（0.560-0.565）→ Perfモデル自体にリークなし
- OOF平均がfull modelよりわずかに高い（fold数の分散）
- perf_labelなし行: 32,299/229,313 (14.1%) → full modelでフォールバック

---

## 3. P/W/ARモデル結果

### AUC / 精度

| 指標 | v7.3 baseline | v1 Stack (リーク+no OOF) | **v2 OOF Stack** | v2 vs v7.3 |
|------|--------------|--------------------------|------------------|------------|
| P AUC | 0.713 | 0.7126 | **0.7794** | **+0.066** |
| W AUC | 0.749 | 0.749 | **0.7954** | **+0.046** |
| AR MAE | 0.706 | 0.706 | **0.682** | **-0.024** |
| AR Corr | 0.59 | 0.59 | **0.6187** | **+0.029** |
| P Features | 169 | 172 | **141** | -28 |
| W Features | 169 | 172 | **147** | -22 |
| AR Features | 169 | 172 | **157** | -12 |

### VB ROI (Place)

| Gap | v7.3 | v1 Stack | **v2 OOF** |
|-----|------|----------|------------|
| gap>=2 | — | — | **87.0%** |
| gap>=3 | 108.7% | 111.1% | **88.0%** |
| gap>=4 | 111.2% | 113.3% | **87.6%** |
| gap>=5 | 115.9% | 118.8% | **92.5%** |

### VB ROI (Win)

| Gap | **v2 OOF** |
|-----|------------|
| gap>=3 | 85.6% |
| gap>=5 | **106.0%** |

### Hit Rate

| 指標 | v7.3 | v1 Stack | **v2 OOF** |
|------|------|----------|------------|
| P Top1 好走率 | 57.0% | 57.5% | **64.2%** |
| W Top1 勝率 | 31.9% | 32.1% | **32.3%** |

### Feature Importance (Place P Top 10)

| # | Feature | Gain |
|---|---------|------|
| 1 | avg_finish_last3 | 179,646 |
| 2 | prev_race_popularity | 93,646 |
| 3 | prev_finish | 67,337 |
| 4 | track_type_top3_rate | 61,922 |
| 5 | dam_maturity_index | 45,704 |
| 6 | jockey_top3_rate | 37,581 |
| 7 | jrdb_idm_last | 32,239 |
| 8 | jrdb_gekisou_idx | 27,808 |
| 9 | age | 25,035 |
| 10 | entry_count_change | 23,717 |

**perf_pred_* はTop10圏外** — v1ではTop3-8だったのがOOFで大幅後退

---

## 4. 考察

### A. AUC大幅改善の原因分析

P AUC +6.6pt, W AUC +4.6ptは異常な改善幅。考えられる原因:

1. **Optuna dam_top3_rate除外の影響**: v7.3では`--exclude-features`で除外していたが、Optunaのfeatureリストにはdam_top3_rateが残っていた。Optunaの最適化時にdam_top3_rateが含まれていたため、他の特徴量の選択がリーク特徴量に依存していた可能性
2. **特徴量数の削減**: P 169→141, W 169→147 — dam_top3_rate除外により特徴量構成が変化
3. **Perfスタッキング自体の効果は不明**: Perfなしのdam_top3_rate除外baselineがないため切り分け不可

### B. VB ROI悪化の原因

1. **予測確率分布の変化**: AUC改善 = ランキング精度向上だが、確率キャリブレーションが変化
2. **gap計算への影響**: P予測確率が変わることでgap値の分布が変化 → 従来のgap閾値が最適でなくなった可能性
3. **dam_top3_rate除外の副作用**: Optunaパラメータはdam_top3_rate込みで最適化されていた。除外後は再Optuna最適化が必要

### C. Perf特徴量の真の寄与

v1ではPerf特徴量がTop3-8だったが、OOFでは圏外。これは:
- **v1のPerf重要度は楽観バイアスによる水増し**: 訓練データ上でPerfモデルが自身のデータを予測 → 情報リーク
- **OOFでは真の予測力のみが残る**: OOF予測はノイジーなため、他の確立された特徴量(avg_finish_last3等)に重要度で負ける
- Perf特徴量が完全に無駄ではない（AUC自体は改善）が、支配的特徴量ではない

---

## 5. 次のステップ

### 必須: 効果の切り分け
1. **dam_top3_rate Optuna除外 baseline（Perfなし）**: `experiment.py --use-optuna --sire-cutoff 2025-02-28 --no-db`
   - これでAUC改善がdam_top3_rate除外効果なのかPerf Stack効果なのか切り分け可能

### Perfスタッキングの改善
2. **Optuna再最適化**: dam_top3_rate除外後のfeatureリストでOptuna再実行
3. **VB ROI改善**: gap閾値の再最適化、または確率キャリブレーション調整

---

## 6. 実験メタデータ

| 項目 | 値 |
|------|-----|
| スクリプト | `experiment.py --perf-stack --use-optuna --sire-cutoff 2025-02-28 --no-db` |
| OOF | 5-fold KFold, shuffle=True, random_state=42 |
| Perfモデル | model_perf.txt (3-class, 205 features) |
| Perf fold精度 | 0.560-0.565 (5 folds) |
| 追加特徴量 | perf_pred_up, perf_pred_stable, perf_pred_down |
| 実行時間 | 2,065秒 (34.4分) |
| liveモデル | v7.3に復元済み |

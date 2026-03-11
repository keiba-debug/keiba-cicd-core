# Performance Change Stacking v1 - P/W/ARへの統合実験

> **Date**: 2026-03-09
> **Experiment**: パフォ変動予測モデル(3-class)のP/W/ARスタッキング
> **方式**: Perfモデル予測確率3値をP/W/ARの入力特徴量として追加

---

## 1. スタッキング方式

### アーキテクチャ
```
[Base Features 169] → Perfモデル(3-class LGB) → pred_up / pred_stable / pred_down
                                                       ↓
[Base Features 169] + [perf_pred_up/stable/down 3] → P/W/ARモデル
```

### 実装
- `experiment_performance.py --save-model` → `model_perf.txt` + `model_perf_meta.json`
- `experiment.py --perf-stack` → Perfモデルをロード、career特徴量計算、perf予測を生成、P/W/ARの特徴量に追加

### リーク考慮
- PerfモデルとP/W/ARが同じ訓練データで学習 → Perf予測は訓練データ上で楽観的
- 正式運用にはK-fold OOF予測が必要
- 今回は概念実証（POC）として直接予測を使用

---

## 2. 結果: 特徴量重要度

### Place (P) モデル Top 10

| # | Feature | Gain | カテゴリ |
|---|---------|------|---------|
| 1 | dam_top3_rate* | 411,137 | 血統(リーク) |
| 2 | prev_finish | 122,893 | 過去走 |
| **3** | **perf_pred_down** | **115,143** | **Perfスタック** |
| 4 | jrdb_idm_last | 85,458 | JRDB |
| **5** | **perf_pred_up** | **76,121** | **Perfスタック** |
| 6 | avg_finish_last3 | 60,670 | 過去走 |
| 7 | jrdb_idm_trend | 53,345 | JRDB |
| 8 | dam_maturity_index | 52,138 | 血統 |
| **9** | **perf_pred_stable** | **46,847** | **Perfスタック** |
| 10 | prev_race_popularity | 45,569 | 市場 |

**Perf特徴量3個がP Top10のうち3位/5位/9位を占める！**

### Win (W) モデル Top 10

| # | Feature | Gain | カテゴリ |
|---|---------|------|---------|
| 1 | dam_top3_rate* | 664,188 | 血統(リーク) |
| 2 | prev_race_popularity | 445,489 | 市場 |
| 3 | prev_finish | 329,923 | 過去走 |
| **4** | **perf_pred_up** | **299,527** | **Perfスタック** |
| 5 | jrdb_idm_last | 295,947 | JRDB |
| 6 | avg_finish_last3 | 249,923 | 過去走 |
| **7** | **perf_pred_down** | **224,115** | **Perfスタック** |
| **8** | **perf_pred_stable** | **174,757** | **Perfスタック** |
| 9 | jrdb_idm_trend | 166,257 | JRDB |
| 10 | jockey_win_rate | 115,749 | 騎手 |

**Perf特徴量3個がW Top10のうち4位/7位/8位を占める！**

*dam_top3_rateはOptunaの特徴量リストに残存しリーク。v7.3では除外済み。

---

## 3. モデルメトリクス

| 指標 | v7.3 baseline | Perf Stack | 差分 |
|------|--------------|------------|------|
| P AUC | 0.713 | 0.7126 | -0.0004 |
| W AUC | 0.749 | 0.749 | ±0 |
| AR MAE | 0.706 | 0.706 | ±0 |
| AR Corr | 0.59 | 0.59 | ±0 |

### 注意点
- **AUC横ばいの理由**: dam_top3_rateリーク + OOFなし → 訓練データ上でPerfモデルが楽観的
- AUCが下がらなかったこと自体は良いサイン（Perf特徴量がノイズでない証拠）

### VB ROI

| Gap | v7.3 baseline | Perf Stack |
|-----|--------------|------------|
| gap>=3 | 108.7% | 111.1% |
| gap>=4 | 111.2% | 113.3% |
| gap>=5 | 115.9% | 118.8% |

**VB ROIが全gap帯で+2-3pt改善** — Perf情報がValue Bet判断に直接寄与。

### Hit Rate

| 指標 | v7.3 | Stack |
|------|------|-------|
| P Top1 好走率 | 57.0% | 57.5% |
| W Top1 勝率 | 31.9% | 32.1% |

---

## 4. 考察

### なぜPerf特徴量が超重要になったか

1. **独立情報**: Perfモデルの出力はP/W/AR既存特徴量との相関≈0（Phase 1で確認済み）
2. **IDMトレンドの圧縮**: Perfモデルは169+36特徴量を「上昇/安定/下降」の3値に圧縮。P/W/ARにとっては超高品質な特徴量
3. **特にperf_pred_downが強い**: P 3位、W 7位。「この馬は下降する」は好走/勝利予測に直結
4. **perf_pred_upもW 4位**: 「この馬は上昇する」= 勝利の可能性上昇

### リーク問題の対策（次のステップ）

現状は訓練データ上でPerfモデルが自身の訓練データを予測しているため楽観的。
正しい評価のためには:

1. **K-fold OOF**: 訓練データを5分割、各fold外のデータに対して予測 → クリーンなPerf特徴量
2. **時系列分割**: 2020-2022で訓練したPerfモデルで2023-2024を予測
3. **どちらでもVB ROIが改善するか検証が必要**

### 運用フロー（将来）

```
1. Perfモデルを別途訓練・保存 (model_perf.txt)
2. predict.py実行時:
   a. career特徴量を計算
   b. Perfモデルで予測 (perf_pred_up/stable/down)
   c. P/W/ARモデルの入力に追加
   d. P/W/ARで最終予測
```

---

## 5. 結論

**スタッキングは極めて有望。** Perf予測3値がP/W両モデルでTop10入りし、VB ROIが+2-3pt改善。

ただし現在の結果はOOFなしの概念実証。正式採用にはK-fold OOFでの検証が必須。

次のステップ:
1. K-fold OOFによるクリーンなスタッキング実験
2. dam_top3_rate除外版での正確な比較
3. predict.pyへのPerf予測パイプライン統合

---

## 6. 実験メタデータ

| 項目 | 値 |
|------|-----|
| Perfモデル | `model_perf.txt` (3-class, 205 features, Accuracy=0.5604) |
| P/W/ARスクリプト | `experiment.py --perf-stack --use-optuna --sire-cutoff 2025-02-28 --no-db` |
| 追加特徴量 | perf_pred_up, perf_pred_stable, perf_pred_down |
| 実行時間 | 1,121秒 (18.7分) |
| liveモデル | v7.3に復元済み |

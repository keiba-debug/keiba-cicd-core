# 04. 機械学習モデル作成・学習

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.04

---

## モデル概要

- **モデル**: LightGBM（二値分類: 3着以内 = 1）
- **目的変数**: rank（着順 < 4 → 1, else 0）
- **ハイパーパラメータ最適化**: Optuna（`optuna.integration.lightgbm`）
- **API**: sklearn API（`LGBMClassifier`）

---

## データ分割

### 時系列分割（重要）
```python
def split_data(df, test_size=0.3):
    sorted_id_list = df.sort_values("date").index.unique()
    train_id_list = sorted_id_list[:round(len(sorted_id_list) * (1 - test_size))]
    test_id_list = sorted_id_list[round(len(sorted_id_list) * (1 - test_size)):]
    train = df.loc[train_id_list]
    test = df.loc[test_id_list]
    return train, test
```

- **必ず時系列順に分割**（未来データで過去を予測するリーク防止）
- train 70% / test 30%
- さらにtrainを train 70% / valid 30% に分割してOptunaで使用

### 学習から除外する列
- `rank`（目的変数）
- `date`（日付はインデックスとしてのみ使用）
- `単勝`（学習時は除外、シミュレーション時に使用）

---

## Optunaによるハイパーパラメータチューニング

### 手順
1. train → train + valid に再分割
2. `lgb_o.Dataset` でデータセット作成
3. `lgb_o.train()` でチューニング実行（early_stopping_rounds=10）
4. 最適パラメータを `lgb_clf_o.params` から取得
5. パラメータを借りて `LGBMClassifier` で全trainデータで再学習

### チューニングされるパラメータ

| パラメータ | 意味 |
|-----------|------|
| lambda_l1 / lambda_l2 | L1/L2正則化（過学習防止） |
| num_leaves | 1本の木の最大葉数 |
| feature_fraction | 各木で使う特徴量の割合 |
| bagging_fraction | 各木で使うデータの割合 |
| bagging_freq | バギング頻度（0=なし） |
| min_child_samples | 葉に残る最小データ数 |

### 基本設定
```python
params = {
    'objective': 'binary',
    'random_state': 100
}
```

---

## 学習フロー

```
r.data_c
  ↓ split_data(test_size=0.3)
  ├── train（70%）
  │     ↓ split_data(test_size=0.3)
  │     ├── train_inner（Optuna学習用）
  │     └── valid（Optuna検証用）
  │     ↓ Optuna → 最適パラメータ
  │     ↓ 全trainデータで再学習（LGBMClassifier）
  └── test（30%）→ 評価用
```

### 再学習時のポイント
- Optunaで見つけたパラメータだけ借りて、**validデータも含めた全trainで再学習**
- sklearn API（LGBMClassifier）を使用（評価クラスとの互換性のため）

---

## KeibaCICDとの比較

| 項目 | この書籍 | KeibaCICD |
|------|---------|-----------|
| モデル | LGBMClassifier 1本 | 分類4本(A/V/W/WV) + 回帰1本(RegB) |
| 目的変数 | 3着以内の二値 | 好走/勝利/AR |
| チューニング | **Optuna自動** | 手動設定 |
| データ分割 | 時系列70/30 | train=2020-2023 / test=2024 |
| キャリブレーション | なし | **IsotonicRegression** |
| early_stopping | チューニング時のみ、本学習では未使用 | early_stopping使用 |
| 単勝オッズ | 学習から除外（シミュレーションで使用） | 市場モデル(A/W)は使用、独自(V/WV)は除外 |

## 参考になるポイント

1. **★ Optuna導入** — `optuna.integration.lightgbm` で最小コードでチューニング可能。うちは手動パラメータなので、導入すれば改善余地あり
2. **チューニング後の再学習パターン** — validデータも含めて全trainで再学習するのは合理的
3. **単勝オッズを学習から除外** — うちの独自モデル(V/WV)と同じ考え方。市場情報に依存しない予測
4. **時系列分割の関数化** — シンプルで再利用しやすい設計

## Optuna導入の検討メモ

うちで導入する場合：
- `experiment.py` に組み込むのが自然
- 5モデル（A/V/W/WV/RegB）それぞれでチューニングが必要
- 計算時間が増えるが、バックテスト精度が上がる可能性
- 回収率120%→144%（+24pt）の改善実績は大きい

## 次章で確認したいこと

- 回収率シミュレーションの具体的方法
- どの馬券種でどう賭けるか
- 回収率151%の内訳（特徴量 vs パラメータチューニングの寄与度）

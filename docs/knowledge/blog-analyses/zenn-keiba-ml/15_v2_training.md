# 15. 【v2.1.1】modules/training/の解説

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.15

---

## モジュール構成

```
modules/training/
├── _data_splitter.py       # 訓練/検証/テスト分割
├── _keiba_ai.py            # 競馬AI本体
├── _keiba_ai_factory.py    # モデルの生成/保存/ロード
└── _model_wrapper.py       # LightGBMのラッパー（チューニング+学習）
```

---

## データ分割（DataSplitter）

```
featured_data
  ↓ split_by_date(test_size=0.3)
  ├── train_data (70%)
  │     ↓ split_by_date(valid_size=0.3)
  │     ├── train_data_optuna (49%) → Optunaの学習用
  │     └── valid_data_optuna (21%) → Optunaの検証用
  └── test_data (30%) → 最終評価用
```

- 時系列順にsort → 時系列分割（未来リーク防止）
- 単勝オッズ(`TANSHO_ODDS`)は学習から除外、テスト時のシミュレーション用に保持

---

## Optunaによるハイパーパラメータチューニング（ModelWrapper）

```python
def tune_hyper_params(self, datasets):
    params = {'objective': 'binary'}
    lgb_clf_o = lgb_o.train(
        params,
        datasets.lgb_train_optuna,
        valid_sets=(datasets.lgb_train_optuna, datasets.lgb_valid_optuna),
        verbose_eval=100,
        early_stopping_rounds=10,
        optuna_seed=100
    )
    # num_iterations, early_stopping_round を除外して適用
    tunedParams = {k: v for k, v in lgb_clf_o.params.items()
                   if k not in ['num_iterations', 'early_stopping_round']}
    self.__lgb_model.set_params(**tunedParams)
```

### ポイント
- `optuna.integration.lightgbm` を使用（Optunaの簡易版API）
- チューニング後、`num_iterations`と`early_stopping_round`は除外して再学習
- 再学習は**全trainデータ**（valid含む）で行う
- `optuna_seed=100` でチューニング結果を再現可能に

### チューニング後の学習
```python
def train(self, datasets):
    self.__lgb_model.fit(datasets.X_train.values, datasets.y_train.values)
    # AUC出力
    auc_train = roc_auc_score(y_train, model.predict_proba(X_train)[:, 1])
    auc_test = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
```

---

## KeibaAI（本体）

### 主要メソッド
| メソッド | 機能 |
|---------|------|
| train_with_tuning() | Optuna → 学習 |
| train_without_tuning() | 外部パラメータで学習 |
| get_params() / set_params() | パラメータ取得/設定 |
| feature_importance() | 特徴量重要度 |
| calc_score(X, score_policy) | 予測スコア算出 |
| decide_action(score_table, bet_policy) | 馬券決定 |

### Strategy パターン
- `calc_score()`は**ScorePolicy**を受け取る → スコア算出ロジックを差し替え可能
- `decide_action()`は**BetPolicy**を受け取る → 購入戦略を差し替え可能
- 詳細はCh.16（policies）で解説

---

## KeibaAIFactory（ファクトリー）

```python
class KeibaAIFactory:
    @staticmethod
    def create(featured_data, test_size=0.3, valid_size=0.3) -> KeibaAI:
        datasets = DataSplitter(featured_data, test_size, valid_size)
        return KeibaAI(datasets)

    @staticmethod
    def save(keibaAI, version_name):
        # models/YYYYMMDD/version_name.pickle に保存
        dill.dump(keibaAI, f)

    @staticmethod
    def load(filepath) -> KeibaAI:
        return dill.load(f)
```

- **dill**でシリアライズ（pickleより柔軟、lambda等も保存可能）
- モデル + データセット + パラメータを一体で保存
- `models/日付/バージョン名.pickle` の命名規則

---

## KeibaCICDとの比較

| 項目 | この書籍 v2 | KeibaCICD v4 |
|------|-----------|-------------|
| チューニング | **Optuna自動** (`lgb_o.train`) | 手動パラメータ |
| データ分割 | 70/30 時系列分割 | train=2020-2023 / test=2024 |
| モデル数 | 1本（二値分類） | 5本（A/V/W/WV/RegB） |
| 保存形式 | dill（モデル+データ一体） | pickle（モデルのみ） |
| バージョン管理 | `models/日付/名前.pickle` | `data3/ml/versions/v5.6/` |
| 評価指標 | AUC（train/test） | AUC + ECE + VB ROI |
| キャリブレーション | なし | IsotonicRegression |
| ScorePolicy | Strategy パターン | predict.pyに固定 |
| BetPolicy | Strategy パターン | bet_engine.pyのプリセット |

## 参考になるポイント

1. **★ `optuna.integration.lightgbm`の簡易チューニング** — わずか数行でハイパーパラメータ自動最適化。うちのml-debug-procedure.mdに書いた`optuna.create_study`方式より簡単だが柔軟性は劣る
2. **ScorePolicy / BetPolicy のStrategy パターン** — スコア算出・購入判断のロジックを差し替え可能にする設計。うちのbet_engine.pyのプリセットに近い思想
3. **dillによるモデル+データ一体保存** — 再現性が高い。うちはモデルとデータが別管理
4. **Factory Methodパターン** — create/save/loadを1クラスに集約。オブジェクト生成と処理の分離
5. **チューニング後にearly_stopping除外して全データ再学習** — 検証データも学習に使える合理的なアプローチ

## Optuna導入の具体的な方法（うちの場合）

### 方式A: 簡易版（この書籍方式）
```python
import optuna.integration.lightgbm as lgb_o
lgb_clf_o = lgb_o.train(params, lgb_train, valid_sets=...)
```
- メリット: 最小コード、すぐ試せる
- デメリット: チューニング対象パラメータのカスタマイズ不可

### 方式B: カスタム版（ml-debug-procedure.md方式）
```python
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50)
```
- メリット: 対象パラメータ・範囲を自由に設定
- デメリット: コード量が多い

### 推奨
- まずは方式Aで効果を確認 → 効果あれば方式Bに移行

## 次章で確認したいこと

- Ch.16 policies（スコア算出・購入戦略の詳細）
- Ch.17 simulation（回収率シミュレーション）

# 競馬予測AI 構築しながら学ぶ機械学習プラン

**目標**: 実際に動くシステムを作りながら、機械学習の基礎から実践までを習得する

このプランでは、KeibaCICDの既存データを使って、段階的に機械学習モデルを構築していきます。
各ステップで**理論→実装→検証**のサイクルを回し、確実に理解を深めます。

---

## 📚 前提知識

### 必要なスキル
- Python基礎（関数、クラス、ライブラリのインポート）
- pandas基礎（DataFrame操作）
- ファイル入出力

### 不要なスキル（これから学ぶ）
- 機械学習理論
- 統計学
- アルゴリズムの詳細

---

## 🎯 学習の全体像

```
Phase 0: 環境構築と基礎理解（1日）
   ↓
Phase 1: データ理解と可視化（2-3日）
   ↓
Phase 2: 特徴量エンジニアリング（3-4日）
   ↓
Phase 3: はじめての機械学習モデル（2-3日）
   ↓
Phase 4: モデル評価とチューニング（3-4日）
   ↓
Phase 5: バックテストと運用（2-3日）
```

**合計**: 約2週間で基礎的な予測システムが完成

---

## Phase 0: 環境構築と基礎理解（1日）

### 🎯 このPhaseで学ぶこと
- 機械学習の基本概念（教師あり学習、分類問題）
- 必要なライブラリの役割
- 開発環境のセットアップ

### 📦 必要なライブラリをインストール

```powershell
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET

# 機械学習用ライブラリ
pip install pandas numpy scikit-learn lightgbm matplotlib seaborn jupyter

# 既存のcommon.jravanライブラリも使います
```

### 💡 機械学習の基本概念を理解する

#### 1. 教師あり学習とは？

```
[入力データ]     →     [モデル]     →     [予測結果]
馬の情報、調教                            着順予測
レース条件など                            (1着になるか？)

学習時: 過去のレース結果（答え）を使ってモデルを訓練
予測時: 未来のレースに対して予測を行う
```

#### 2. 分類問題（Classification）

競馬予測は「**2値分類問題**」として扱います：
- **Positive (1)**: 馬券圏内（1-3着）
- **Negative (0)**: 馬券圏外（4着以下）

#### 3. 使用するモデル

| モデル | 特徴 | 学習用途 |
|--------|------|----------|
| ロジスティック回帰 | シンプル、解釈しやすい | 基礎を学ぶ |
| LightGBM | 高精度、実用的 | 実戦投入 |

### 📝 実践課題: Jupyter Notebookで基礎を試す

```powershell
# Jupyter起動
jupyter notebook
```

新規ノートブック作成: `notebooks/00_getting_started.ipynb`

```python
# セル1: ライブラリのインポート確認
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
import lightgbm as lgb
import matplotlib.pyplot as plt
import seaborn as sns

print("✓ All libraries imported successfully!")

# セル2: 既存のcommon.jravanライブラリを試す
import sys
sys.path.insert(0, '..')

from common.jravan import (
    get_horse_id_by_name,
    analyze_horse_training,
    get_horse_info
)

# 実際に馬のデータを取得してみる
horse_name = "ドウデュース"
horse_info = get_horse_info(horse_name)
print(f"馬名: {horse_info['name']}")
print(f"調教師: {horse_info['trainer_name']}")

# 調教データも取得
training = analyze_horse_training(horse_name, "20260125")
if training.get("final"):
    print(f"最終追切: {training['final']['time_4f']:.1f}秒")
```

### ✅ Phase 0 チェックリスト

- [ ] ライブラリがすべてインストールできた
- [ ] Jupyter Notebookが起動できた
- [ ] common.jravanから馬のデータが取得できた
- [ ] 機械学習の基本概念（教師あり学習、分類問題）を理解した

---

## Phase 1: データ理解と可視化（2-3日）

### 🎯 このPhaseで学ぶこと
- データの形式と意味
- EDA（探索的データ分析）の基本
- 可視化による洞察の発見
- データ品質の確認

### 📊 Step 1-1: レースデータを読み込む

**ノートブック**: `notebooks/01_data_exploration.ipynb`

```python
import pandas as pd
from pathlib import Path

# レース結果データのパス
# （実際のパスは環境に合わせて調整）
race_results_path = Path("../data/race_results.csv")

# データ読み込み
df = pd.read_csv(race_results_path)

# 基本情報の確認
print(f"データ件数: {len(df)}")
print(f"カラム数: {len(df.columns)}")
print("\nカラム一覧:")
print(df.columns.tolist())

# 最初の5行を表示
df.head()
```

### 📈 Step 1-2: データの分布を可視化する

```python
import matplotlib.pyplot as plt
import seaborn as sns

# 日本語フォント設定（Windows）
plt.rcParams['font.sans-serif'] = ['MS Gothic']
plt.rcParams['axes.unicode_minus'] = False

# 1. 着順の分布
plt.figure(figsize=(10, 6))
sns.countplot(data=df, x='着順')
plt.title('着順の分布')
plt.xlabel('着順')
plt.ylabel('頭数')
plt.show()

# 2. 人気の分布
plt.figure(figsize=(10, 6))
sns.countplot(data=df, x='人気')
plt.title('人気の分布')
plt.xlabel('人気')
plt.ylabel('頭数')
plt.show()

# 3. 人気と着順の関係
plt.figure(figsize=(12, 8))
sns.heatmap(pd.crosstab(df['人気'], df['着順']), annot=True, fmt='d', cmap='YlOrRd')
plt.title('人気 vs 着順のクロス集計')
plt.show()
```

**学ぶポイント**:
- `countplot`: カテゴリごとの件数を棒グラフで表示
- `heatmap`: 2つのカテゴリの関係を色で可視化
- 人気と着順の相関を目で確認できる

### 🔍 Step 1-3: 目的変数を作る

機械学習では「**何を予測したいか**」を明確にする必要があります。

```python
# 目的変数: 馬券圏内（1-3着）かどうか
df['target'] = (df['着順'] <= 3).astype(int)

# 確認
print("目的変数の分布:")
print(df['target'].value_counts())

# 可視化
plt.figure(figsize=(8, 6))
sns.countplot(data=df, x='target')
plt.title('目的変数の分布（0=圏外, 1=圏内）')
plt.xticks([0, 1], ['圏外(4着以下)', '圏内(1-3着)'])
plt.show()
```

**学ぶポイント**:
- 目的変数（target）は予測したい値
- 2値分類: 0 or 1 で表現
- クラスの不均衡を確認（圏内と圏外の比率）

### 📊 Step 1-4: 調教データを統合する

```python
from common.jravan import analyze_horse_training

# サンプル: 最初の100レースに調教データを追加
sample_df = df.head(100).copy()

# 調教データを取得する関数
def get_training_features(row):
    """レース情報から調教データを取得"""
    try:
        training = analyze_horse_training(
            row['horse_id'],
            row['race_date'],
            days_back=14
        )

        if training.get('final'):
            return {
                'training_count': training.get('total_count', 0),
                'final_4f_time': training['final']['time_4f'],
                'has_good_time': int(training.get('has_good_time', False)),
                'n_sakamichi': training.get('n_sakamichi', 0),
            }
        else:
            return {
                'training_count': 0,
                'final_4f_time': 0,
                'has_good_time': 0,
                'n_sakamichi': 0,
            }
    except Exception as e:
        print(f"エラー: {e}")
        return {'training_count': 0, 'final_4f_time': 0, 'has_good_time': 0, 'n_sakamichi': 0}

# 調教データを追加（時間がかかるので最初は少数で試す）
training_features = sample_df.apply(get_training_features, axis=1, result_type='expand')
sample_df = pd.concat([sample_df, training_features], axis=1)

# 確認
print(sample_df[['horse_id', 'training_count', 'final_4f_time', 'has_good_time']].head())
```

**学ぶポイント**:
- `apply`: DataFrameの各行に関数を適用
- 既存のcommon.jravanライブラリを活用
- エラーハンドリングの重要性

### ✅ Phase 1 チェックリスト

- [ ] レースデータを読み込めた
- [ ] 着順、人気の分布を可視化できた
- [ ] 目的変数（target）を作成できた
- [ ] 調教データを統合できた
- [ ] データの傾向を理解できた

---

## Phase 2: 特徴量エンジニアリング（3-4日）

### 🎯 このPhaseで学ぶこと
- 特徴量（Feature）とは何か
- ドメイン知識を活かした特徴量設計
- カテゴリ変数のエンコーディング
- 数値の正規化・標準化

### 💡 特徴量とは？

機械学習モデルへの入力データ。競馬予測では：

| カラム名 | 特徴量の種類 | 例 |
|----------|-------------|-----|
| 性別 | カテゴリ | 牡、牝 |
| 年齢 | 数値 | 3, 4, 5... |
| 斤量 | 数値 | 54.0, 57.0... |
| 距離 | 数値 | 1200, 1600, 2000... |
| 馬場状態 | カテゴリ | 良、稍重、重、不良 |
| 調教本数 | 数値 | 8, 10, 12... |
| 最終追切タイム | 数値 | 51.2, 52.5... |

### 📝 Step 2-1: 基本的な特徴量を準備

**ノートブック**: `notebooks/02_feature_engineering.ipynb`

```python
import pandas as pd
import numpy as np

# データ読み込み（Phase 1で作成したデータ）
df = pd.read_csv("../data/race_results_with_training.csv")

# 1. 数値特徴量
numerical_features = [
    'age',           # 年齢
    'weight',        # 斤量
    'distance',      # 距離
    'popularity',    # 人気
    'training_count', # 調教本数
    'final_4f_time',  # 最終追切4Fタイム
]

# 2. カテゴリ特徴量
categorical_features = [
    'sex',           # 性別
    'track_code',    # 競馬場コード
    'track_condition', # 馬場状態
    'race_class',    # レースクラス
]

print(f"数値特徴量: {len(numerical_features)}個")
print(f"カテゴリ特徴量: {len(categorical_features)}個")
```

### 🔢 Step 2-2: カテゴリ変数をエンコーディング

機械学習モデルは数値しか扱えないので、カテゴリを数値に変換します。

#### One-Hot Encoding

```python
from sklearn.preprocessing import OneHotEncoder

# 性別をOne-Hotエンコーディング
# 例: 牡 → [1, 0, 0], 牝 → [0, 1, 0], セ → [0, 0, 1]

encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
sex_encoded = encoder.fit_transform(df[['sex']])

# DataFrameに変換
sex_df = pd.DataFrame(
    sex_encoded,
    columns=[f'sex_{cat}' for cat in encoder.categories_[0]]
)

print(sex_df.head())
```

**学ぶポイント**:
- One-Hot: カテゴリごとに0/1のフラグを立てる
- `sparse_output=False`: 密な配列で返す
- `handle_unknown='ignore'`: 未知のカテゴリを無視

#### Label Encoding（順序がある場合）

```python
from sklearn.preprocessing import LabelEncoder

# 馬場状態（良 < 稍重 < 重 < 不良）
condition_map = {'良': 0, '稍重': 1, '重': 2, '不良': 3}
df['track_condition_encoded'] = df['track_condition'].map(condition_map)

print(df[['track_condition', 'track_condition_encoded']].head())
```

### 📊 Step 2-3: 数値の標準化

数値のスケールが異なると学習がうまくいかないため、標準化します。

```python
from sklearn.preprocessing import StandardScaler

# 標準化: 平均0、分散1に変換
scaler = StandardScaler()

numerical_cols = ['age', 'weight', 'distance', 'training_count', 'final_4f_time']
df[numerical_cols] = scaler.fit_transform(df[numerical_cols])

print("標準化後の統計量:")
print(df[numerical_cols].describe())
```

**学ぶポイント**:
- StandardScaler: (x - 平均) / 標準偏差
- すべての特徴量が同じスケールになる
- モデルの学習が安定する

### 🎨 Step 2-4: ドメイン知識を活かした特徴量

競馬の知識を使って新しい特徴量を作ります。

```python
# 1. 距離変化量（前走からの距離差）
df['distance_change'] = df.groupby('horse_id')['distance'].diff().fillna(0)

# 2. 斤量変化量
df['weight_change'] = df.groupby('horse_id')['weight'].diff().fillna(0)

# 3. 休み明けフラグ（前走から30日以上）
df['race_date_dt'] = pd.to_datetime(df['race_date'])
df['days_since_last'] = df.groupby('horse_id')['race_date_dt'].diff().dt.days.fillna(0)
df['is_after_rest'] = (df['days_since_last'] >= 30).astype(int)

# 4. 昇級戦フラグ（前走よりクラスが上）
class_order = {'新馬': 0, '未勝利': 1, '1勝': 2, '2勝': 3, '3勝': 4, 'オープン': 5, 'G3': 6, 'G2': 7, 'G1': 8}
df['class_code'] = df['race_class'].map(class_order)
df['prev_class'] = df.groupby('horse_id')['class_code'].shift(1).fillna(0)
df['is_class_up'] = (df['class_code'] > df['prev_class']).astype(int)

# 5. 調教評価（好タイムあり×坂路本数）
df['training_score'] = df['has_good_time'] * df['n_sakamichi']

print("新規特徴量:")
print(df[['distance_change', 'weight_change', 'is_after_rest', 'is_class_up', 'training_score']].head(10))
```

**学ぶポイント**:
- `groupby().diff()`: グループ内での差分
- `fillna(0)`: 欠損値を0で埋める
- ドメイン知識が重要（距離変化、昇級戦など）

### ✅ Phase 2 チェックリスト

- [ ] 特徴量の概念を理解できた
- [ ] カテゴリ変数をエンコーディングできた
- [ ] 数値を標準化できた
- [ ] 競馬知識を活かした特徴量を作成できた
- [ ] 最終的な特徴量セットが準備できた

---

## Phase 3: はじめての機械学習モデル（2-3日）

### 🎯 このPhaseで学ぶこと
- 学習データとテストデータの分割
- モデルの訓練（fit）
- 予測（predict）の実行
- 精度評価の基本

### 📚 機械学習の流れ

```
1. データ分割
   └─ 学習用（過去データ）とテスト用（未来データ）に分ける

2. モデル訓練
   └─ 学習用データでモデルを学習させる

3. 予測
   └─ テスト用データで予測を行う

4. 評価
   └─ 予測がどれくらい当たったかを測る
```

### 📝 Step 3-1: データを時系列で分割

**重要**: 競馬データは時系列なので、ランダムに分割してはいけません。

```python
import pandas as pd
from datetime import datetime

# データ読み込み
df = pd.read_csv("../data/race_results_featured.csv")

# 日付でソート
df['race_date_dt'] = pd.to_datetime(df['race_date'])
df = df.sort_values('race_date_dt')

# 時系列分割: 2024年12月31日までを学習、2025年以降をテスト
split_date = '2024-12-31'

train_df = df[df['race_date'] <= split_date].copy()
test_df = df[df['race_date'] > split_date].copy()

print(f"学習データ: {len(train_df)}件 ({train_df['race_date'].min()} ～ {train_df['race_date'].max()})")
print(f"テストデータ: {len(test_df)}件 ({test_df['race_date'].min()} ～ {test_df['race_date'].max()})")
```

**学ぶポイント**:
- 時系列データはランダム分割NG
- 未来のデータで過去を予測してはいけない（データリーケージ）
- テストデータは実戦を想定

### 🤖 Step 3-2: ロジスティック回帰で学習

シンプルなモデルから始めます。

```python
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score

# 特徴量と目的変数を分離
feature_cols = [
    'age', 'weight', 'distance', 'popularity',
    'training_count', 'final_4f_time', 'has_good_time',
    'distance_change', 'weight_change', 'is_after_rest',
    'is_class_up', 'training_score'
]

X_train = train_df[feature_cols].fillna(0)
y_train = train_df['target']

X_test = test_df[feature_cols].fillna(0)
y_test = test_df['target']

# モデル作成と学習
model = LogisticRegression(max_iter=1000, random_state=42)
model.fit(X_train, y_train)

print("✓ モデル学習完了!")

# 予測
y_pred = model.predict(X_test)
y_pred_proba = model.predict_proba(X_test)[:, 1]  # 確率値

# 精度評価
accuracy = accuracy_score(y_test, y_pred)
auc = roc_auc_score(y_test, y_pred_proba)

print(f"正解率: {accuracy:.3f}")
print(f"AUC: {auc:.3f}")
```

**学ぶポイント**:
- `fit()`: モデルを学習
- `predict()`: 0 or 1 の予測
- `predict_proba()`: 確率値（0～1）
- AUC: 0.5なら当てずっぽう、1.0なら完璧

### 📊 Step 3-3: 特徴量の重要度を確認

どの特徴量が効いているかを見ます。

```python
import matplotlib.pyplot as plt

# 係数（重要度）を取得
coefficients = pd.DataFrame({
    'feature': feature_cols,
    'coefficient': model.coef_[0]
})

# 絶対値でソート
coefficients['abs_coef'] = coefficients['coefficient'].abs()
coefficients = coefficients.sort_values('abs_coef', ascending=False)

# 可視化
plt.figure(figsize=(10, 8))
plt.barh(coefficients['feature'], coefficients['coefficient'])
plt.xlabel('係数')
plt.title('特徴量の重要度（ロジスティック回帰）')
plt.tight_layout()
plt.show()

print(coefficients)
```

**学ぶポイント**:
- 正の係数: 値が大きいほど圏内になりやすい
- 負の係数: 値が大きいほど圏外になりやすい
- 重要度を見て特徴量を改善

### 🚀 Step 3-4: LightGBMで高精度化

より強力なモデルを試します。

```python
import lightgbm as lgb

# LightGBM用のデータセット
train_data = lgb.Dataset(X_train, label=y_train)
test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

# パラメータ設定
params = {
    'objective': 'binary',        # 2値分類
    'metric': 'auc',              # AUCで評価
    'boosting': 'gbdt',           # 勾配ブースティング
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'verbose': -1
}

# 学習
gbm = lgb.train(
    params,
    train_data,
    num_boost_round=1000,
    valid_sets=[test_data],
    callbacks=[lgb.early_stopping(stopping_rounds=50)]
)

print("✓ LightGBM学習完了!")

# 予測
y_pred_gbm_proba = gbm.predict(X_test)
y_pred_gbm = (y_pred_gbm_proba > 0.5).astype(int)

# 評価
accuracy_gbm = accuracy_score(y_test, y_pred_gbm)
auc_gbm = roc_auc_score(y_test, y_pred_gbm_proba)

print(f"LightGBM 正解率: {accuracy_gbm:.3f}")
print(f"LightGBM AUC: {auc_gbm:.3f}")
```

**学ぶポイント**:
- LightGBMは多くの決定木を組み合わせる
- `early_stopping`: 過学習を防ぐ
- ロジスティック回帰より高精度になることが多い

### ✅ Phase 3 チェックリスト

- [ ] データを時系列で分割できた
- [ ] ロジスティック回帰で学習・予測できた
- [ ] AUCの意味を理解できた
- [ ] 特徴量の重要度を確認できた
- [ ] LightGBMで高精度化できた

---

## Phase 4: モデル評価とチューニング（3-4日）

### 🎯 このPhaseで学ぶこと
- 混同行列（Confusion Matrix）
- 適合率（Precision）と再現率（Recall）
- しきい値の調整
- ハイパーパラメータチューニング

### 📊 Step 4-1: 混同行列で詳細分析

```python
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns

# 混同行列
cm = confusion_matrix(y_test, y_pred_gbm)

# 可視化
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
plt.title('混同行列')
plt.xlabel('予測値')
plt.ylabel('実際の値')
plt.xticks([0.5, 1.5], ['圏外(0)', '圏内(1)'])
plt.yticks([0.5, 1.5], ['圏外(0)', '圏内(1)'])
plt.show()

print(cm)
```

**混同行列の読み方**:

```
                予測
              圏外  圏内
実際 圏外   [TN   FP]
     圏内   [FN   TP]

TN (True Negative):  圏外を圏外と正しく予測
FP (False Positive): 圏外を圏内と誤予測
FN (False Negative): 圏内を圏外と誤予測（見逃し）
TP (True Positive):  圏内を圏内と正しく予測
```

### 📈 Step 4-2: 適合率と再現率

```python
from sklearn.metrics import precision_score, recall_score, f1_score

precision = precision_score(y_test, y_pred_gbm)
recall = recall_score(y_test, y_pred_gbm)
f1 = f1_score(y_test, y_pred_gbm)

print(f"適合率 (Precision): {precision:.3f}")
print(f"再現率 (Recall): {recall:.3f}")
print(f"F1スコア: {f1:.3f}")

# 詳細レポート
print("\n分類レポート:")
print(classification_report(y_test, y_pred_gbm, target_names=['圏外', '圏内']))
```

**指標の意味**:
- **適合率**: 圏内と予測したうち、実際に圏内だった割合（的中率）
- **再現率**: 実際の圏内のうち、正しく予測できた割合（網羅率）
- **F1スコア**: 適合率と再現率の調和平均

### 🎚️ Step 4-3: しきい値の調整

馬券戦略に応じてしきい値を変えます。

```python
# しきい値を変えて適合率・再現率を計算
thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]

results = []
for threshold in thresholds:
    y_pred_custom = (y_pred_gbm_proba > threshold).astype(int)
    precision = precision_score(y_test, y_pred_custom)
    recall = recall_score(y_test, y_pred_custom)

    results.append({
        'threshold': threshold,
        'precision': precision,
        'recall': recall,
        'n_predictions': y_pred_custom.sum()  # 買い目数
    })

results_df = pd.DataFrame(results)
print(results_df)

# 可視化
fig, ax1 = plt.subplots(figsize=(10, 6))

ax1.plot(results_df['threshold'], results_df['precision'], 'b-', label='適合率')
ax1.plot(results_df['threshold'], results_df['recall'], 'r-', label='再現率')
ax1.set_xlabel('しきい値')
ax1.set_ylabel('スコア')
ax1.legend(loc='upper left')

ax2 = ax1.twinx()
ax2.plot(results_df['threshold'], results_df['n_predictions'], 'g--', label='買い目数')
ax2.set_ylabel('買い目数', color='g')
ax2.legend(loc='upper right')

plt.title('しきい値と評価指標の関係')
plt.show()
```

**学ぶポイント**:
- しきい値を上げる → 的中率↑、買い目数↓（堅実）
- しきい値を下げる → 的中率↓、買い目数↑（積極的）
- 戦略に応じて調整

### ⚙️ Step 4-4: ハイパーパラメータチューニング

LightGBMのパラメータを最適化します。

```python
from sklearn.model_selection import TimeSeriesSplit
import optuna

# Optuna目的関数
def objective(trial):
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'boosting': 'gbdt',
        'num_leaves': trial.suggest_int('num_leaves', 20, 100),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.6, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.6, 1.0),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 7),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
        'verbose': -1
    }

    # 時系列クロスバリデーション
    tscv = TimeSeriesSplit(n_splits=3)
    auc_scores = []

    for train_idx, valid_idx in tscv.split(X_train):
        X_tr, X_val = X_train.iloc[train_idx], X_train.iloc[valid_idx]
        y_tr, y_val = y_train.iloc[train_idx], y_train.iloc[valid_idx]

        train_data = lgb.Dataset(X_tr, label=y_tr)
        valid_data = lgb.Dataset(X_val, label=y_val)

        model = lgb.train(params, train_data, num_boost_round=500, valid_sets=[valid_data],
                         callbacks=[lgb.early_stopping(stopping_rounds=30)])

        y_pred = model.predict(X_val)
        auc = roc_auc_score(y_val, y_pred)
        auc_scores.append(auc)

    return np.mean(auc_scores)

# 最適化実行
study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50, show_progress_bar=True)

print(f"ベストAUC: {study.best_value:.4f}")
print("ベストパラメータ:")
print(study.best_params)
```

**学ぶポイント**:
- Optunaで自動的にパラメータを探索
- TimeSeriesSplit: 時系列データ用のクロスバリデーション
- AUCを最大化するパラメータを見つける

### ✅ Phase 4 チェックリスト

- [ ] 混同行列を作成・理解できた
- [ ] 適合率・再現率の意味を理解できた
- [ ] しきい値を調整できた
- [ ] ハイパーパラメータチューニングを実行できた
- [ ] モデルの性能を最大限に引き出せた

---

## Phase 5: バックテストと運用（2-3日）

### 🎯 このPhaseで学ぶこと
- バックテストの実装
- 回収率の計算
- モデルの保存と読み込み
- 実運用への展開

### 💰 Step 5-1: 回収率シミュレーション

```python
import pandas as pd

# テストデータに予測確率を追加
test_df_eval = test_df.copy()
test_df_eval['pred_proba'] = y_pred_gbm_proba
test_df_eval['pred_class'] = y_pred_gbm

# しきい値0.6で買い目を選択
threshold = 0.6
bet_df = test_df_eval[test_df_eval['pred_proba'] >= threshold].copy()

print(f"買い目数: {len(bet_df)}")

# 的中数と的中率
hit_count = (bet_df['target'] == 1).sum()
hit_rate = hit_count / len(bet_df) if len(bet_df) > 0 else 0

print(f"的中数: {hit_count}")
print(f"的中率: {hit_rate:.1%}")

# 回収率計算（仮にオッズ情報がある場合）
# ここでは単勝オッズがあると仮定
if 'win_odds' in bet_df.columns:
    bet_df['return'] = bet_df.apply(
        lambda row: row['win_odds'] * 100 if row['target'] == 1 else 0,
        axis=1
    )

    total_bet = len(bet_df) * 100  # 1点100円
    total_return = bet_df['return'].sum()
    recovery_rate = (total_return / total_bet) * 100

    print(f"\n投資額: {total_bet:,}円")
    print(f"払戻額: {total_return:,.0f}円")
    print(f"収支: {total_return - total_bet:+,.0f}円")
    print(f"回収率: {recovery_rate:.1f}%")
```

### 📊 Step 5-2: 月次収支の可視化

```python
import matplotlib.pyplot as plt

# 月ごとに集計
bet_df['race_month'] = pd.to_datetime(bet_df['race_date']).dt.to_period('M')

monthly_stats = bet_df.groupby('race_month').apply(
    lambda g: pd.Series({
        'bet_count': len(g),
        'hit_count': (g['target'] == 1).sum(),
        'total_return': g['return'].sum() if 'return' in g.columns else 0,
        'total_bet': len(g) * 100
    })
).reset_index()

monthly_stats['recovery_rate'] = (monthly_stats['total_return'] / monthly_stats['total_bet']) * 100

# 可視化
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# 回収率の推移
ax1.bar(range(len(monthly_stats)), monthly_stats['recovery_rate'], alpha=0.7)
ax1.axhline(y=100, color='r', linestyle='--', label='損益分岐点')
ax1.set_xlabel('月')
ax1.set_ylabel('回収率 (%)')
ax1.set_title('月次回収率の推移')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 買い目数と的中数
ax2.bar(range(len(monthly_stats)), monthly_stats['bet_count'], alpha=0.5, label='買い目数')
ax2.bar(range(len(monthly_stats)), monthly_stats['hit_count'], alpha=0.7, label='的中数')
ax2.set_xlabel('月')
ax2.set_ylabel('件数')
ax2.set_title('月次買い目数と的中数')
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

print(monthly_stats)
```

### 💾 Step 5-3: モデルの保存

```python
import joblib

# モデル保存
model_path = "../data/models/lightgbm_model.pkl"
joblib.dump(gbm, model_path)
print(f"✓ モデル保存完了: {model_path}")

# スケーラーも保存
scaler_path = "../data/models/scaler.pkl"
joblib.dump(scaler, scaler_path)
print(f"✓ スケーラー保存完了: {scaler_path}")

# 特徴量リストも保存
import json
feature_info = {
    'features': feature_cols,
    'threshold': 0.6,
    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}

with open("../data/models/model_info.json", "w", encoding="utf-8") as f:
    json.dump(feature_info, f, ensure_ascii=False, indent=2)

print("✓ モデル情報保存完了")
```

### 🚀 Step 5-4: 新しいレースの予測

```python
def predict_new_race(race_data):
    """
    新しいレースの予測を行う

    Args:
        race_data: 予測対象のDataFrame

    Returns:
        予測結果を含むDataFrame
    """
    # モデル読み込み
    model = joblib.load("../data/models/lightgbm_model.pkl")
    scaler = joblib.load("../data/models/scaler.pkl")

    with open("../data/models/model_info.json", "r", encoding="utf-8") as f:
        model_info = json.load(f)

    feature_cols = model_info['features']
    threshold = model_info['threshold']

    # 特徴量準備
    X_new = race_data[feature_cols].fillna(0)

    # 予測
    pred_proba = model.predict(X_new)
    pred_class = (pred_proba >= threshold).astype(int)

    # 結果を追加
    result = race_data.copy()
    result['pred_proba'] = pred_proba
    result['pred_class'] = pred_class
    result['recommended'] = (pred_proba >= threshold)

    # 推奨買い目のみ返す
    return result[result['recommended']].sort_values('pred_proba', ascending=False)

# 使用例
# new_race_df = pd.read_csv("../data/upcoming_races.csv")
# recommendations = predict_new_race(new_race_df)
# print(recommendations[['horse_name', 'pred_proba', 'umaban']])
```

### 📝 Step 5-5: 予測レポート生成

```python
def generate_prediction_report(predictions, race_info):
    """
    予測結果のレポートを生成
    """
    report = f"""
# 競馬予測レポート

## レース情報
- 日付: {race_info['date']}
- 競馬場: {race_info['track']}
- レース番号: {race_info['race_num']}R
- 距離: {race_info['distance']}m

## 推奨買い目（{len(predictions)}点）

"""

    for idx, row in predictions.iterrows():
        report += f"""
### {row['umaban']}番 {row['horse_name']}
- **予測確率**: {row['pred_proba']:.1%}
- 性齢: {row['sex']}{row['age']}歳
- 斤量: {row['weight']}kg
- 調教評価: {row['training_score']:.1f}
- 最終追切: {row['final_4f_time']:.1f}秒

"""

    return report

# レポート出力例
# race_info = {'date': '2026-02-01', 'track': '東京', 'race_num': 11, 'distance': 2000}
# report = generate_prediction_report(recommendations, race_info)
# print(report)
```

### ✅ Phase 5 チェックリスト

- [ ] バックテストを実装できた
- [ ] 回収率を計算できた
- [ ] 月次収支を可視化できた
- [ ] モデルを保存・読み込みできた
- [ ] 新しいレースの予測ができた
- [ ] 予測レポートを生成できた

---

## 🎓 卒業課題: 総合演習

すべてのPhaseを組み合わせて、実戦的なシステムを構築します。

### 課題1: 週末レース自動予測システム

```python
"""
週末のレースを自動予測するスクリプト
毎週金曜日に実行
"""

from common.jravan import build_race_id, get_horse_info, analyze_horse_training
import pandas as pd
from datetime import datetime, timedelta

def predict_weekend_races():
    """週末レースを予測"""

    # 1. 今週末の日付を取得
    today = datetime.now()
    saturday = today + timedelta(days=(5 - today.weekday()))
    sunday = saturday + timedelta(days=1)

    # 2. レースデータ取得（実装は環境に応じて）
    races = get_weekend_races([saturday, sunday])

    # 3. 各レースの出走馬データを準備
    all_predictions = []

    for race in races:
        race_id = race['race_id']
        horses = race['horses']

        # 特徴量作成
        race_df = prepare_race_features(horses, race)

        # 予測
        predictions = predict_new_race(race_df)
        predictions['race_id'] = race_id

        all_predictions.append(predictions)

    # 4. レポート生成
    report = generate_weekend_report(all_predictions)

    # 5. 保存
    output_file = f"predictions_{saturday.strftime('%Y%m%d')}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✓ 予測完了: {output_file}")

# 実行
if __name__ == "__main__":
    predict_weekend_races()
```

### 課題2: モデル性能モニタリング

```python
"""
モデルの性能を継続的に監視
週次で実行し、性能劣化を検知
"""

def monitor_model_performance():
    """モデル性能を監視"""

    # 最新1ヶ月のレース結果を取得
    recent_results = get_recent_race_results(days=30)

    # 予測を実行
    predictions = predict_new_race(recent_results)

    # 実際の結果と比較
    actual = recent_results['target']
    predicted = predictions['pred_class']

    # 評価指標を計算
    from sklearn.metrics import accuracy_score, roc_auc_score

    accuracy = accuracy_score(actual, predicted)
    auc = roc_auc_score(actual, predictions['pred_proba'])

    # 基準値と比較
    baseline_accuracy = 0.65
    baseline_auc = 0.70

    if accuracy < baseline_accuracy or auc < baseline_auc:
        print("⚠️ モデル性能が低下しています。再学習を検討してください。")
        print(f"現在の正解率: {accuracy:.3f} (基準: {baseline_accuracy})")
        print(f"現在のAUC: {auc:.3f} (基準: {baseline_auc})")
    else:
        print("✓ モデル性能は正常です。")

    # ログ保存
    log_performance(accuracy, auc)
```

### 課題3: モデル再学習パイプライン

```python
"""
定期的にモデルを再学習するスクリプト
月1回実行
"""

def retrain_model():
    """モデルを再学習"""

    print("=== モデル再学習開始 ===")

    # 1. 最新データを取得
    print("1. データ取得中...")
    df = load_latest_race_data()

    # 2. 特徴量エンジニアリング
    print("2. 特徴量作成中...")
    df_featured = create_all_features(df)

    # 3. データ分割
    print("3. データ分割中...")
    train_df, test_df = split_data_by_date(df_featured, split_date='2025-12-31')

    # 4. モデル学習
    print("4. モデル学習中...")
    model = train_lightgbm_model(train_df, test_df)

    # 5. 評価
    print("5. モデル評価中...")
    metrics = evaluate_model(model, test_df)

    # 6. 前回モデルと比較
    print("6. 性能比較中...")
    previous_metrics = load_previous_metrics()

    if metrics['auc'] > previous_metrics['auc']:
        print(f"✓ 性能向上: AUC {previous_metrics['auc']:.4f} → {metrics['auc']:.4f}")

        # 7. モデル保存
        print("7. モデル保存中...")
        save_model(model, metrics)
        print("✓ 新しいモデルを保存しました。")
    else:
        print(f"⚠️ 性能低下: AUC {previous_metrics['auc']:.4f} → {metrics['auc']:.4f}")
        print("古いモデルを維持します。")

    print("=== 再学習完了 ===")
```

---

## 📚 さらに学ぶために

### 推奨リソース

#### 書籍
1. **「Pythonではじめる機械学習」** - scikit-learnの基礎
2. **「Kaggleで勝つデータ分析の技術」** - 実践的な特徴量エンジニアリング
3. **「前処理大全」** - データ前処理のベストプラクティス

#### オンラインコース
1. **Coursera: Machine Learning** (Andrew Ng) - 機械学習の理論
2. **Kaggle Learn** - 無料の実践チュートリアル

#### コミュニティ
1. **Kaggle** - 競馬予測コンペティション
2. **GitHub** - 競馬予測プロジェクトの事例

### 発展的なトピック

#### 1. アンサンブル学習
複数のモデルを組み合わせて精度向上

```python
from sklearn.ensemble import VotingClassifier

ensemble = VotingClassifier(
    estimators=[
        ('lr', LogisticRegression()),
        ('lgbm', lgb.LGBMClassifier()),
        ('xgb', xgb.XGBClassifier())
    ],
    voting='soft'
)
```

#### 2. ディープラーニング
ニューラルネットワークで複雑なパターンを学習

```python
from tensorflow import keras

model = keras.Sequential([
    keras.layers.Dense(128, activation='relu'),
    keras.layers.Dropout(0.3),
    keras.layers.Dense(64, activation='relu'),
    keras.layers.Dense(1, activation='sigmoid')
])
```

#### 3. 強化学習
最適な賭け戦略を学習

```python
# Q-learning for betting strategy
# 状態: レース状況、アクション: 賭け金額
```

#### 4. 自然言語処理（NLP）
厩舎コメントやニュースから情報抽出

```python
from transformers import pipeline

sentiment = pipeline("sentiment-analysis", model="bert-base-japanese")
comment = "好調を維持している"
result = sentiment(comment)
```

---

## 🏁 まとめ

### 学んだこと

| Phase | 学習内容 | 実装したもの |
|-------|----------|--------------|
| 0 | 環境構築、ML基礎 | Jupyter環境、ライブラリ |
| 1 | データ理解、可視化 | EDA、目的変数作成 |
| 2 | 特徴量エンジニアリング | エンコーディング、標準化、ドメイン特徴量 |
| 3 | モデル学習、予測 | ロジスティック回帰、LightGBM |
| 4 | 評価、チューニング | 混同行列、しきい値調整、ハイパーパラメータ最適化 |
| 5 | バックテスト、運用 | 回収率計算、モデル保存、予測システム |

### 次のステップ

1. **精度向上**
   - 新しい特徴量の追加（血統、コース適性など）
   - アンサンブル学習の導入
   - ハイパーパラメータの再最適化

2. **システム化**
   - 自動データ更新パイプライン
   - Webダッシュボード（Streamlit/Dash）
   - LINE/Slack通知機能

3. **実運用**
   - 少額から実戦投入
   - 収支記録とフィードバック
   - モデルの定期的な再学習

### 継続的な改善

```
週次サイクル:
  金曜: 週末レース予測
  土日: 結果確認、実績記録
  月曜: パフォーマンス分析

月次サイクル:
  月初: モデル性能レビュー
  月中: 特徴量改善検討
  月末: モデル再学習
```

---

**おめでとうございます！** 🎉

あなたは今、機械学習の基礎から実践的な競馬予測AIまでを習得しました。
ここからは実際に運用しながら、継続的に改善していきましょう。

---

*作成日: 2026-01-30*
*対象: KeibaCICD プロジェクト*

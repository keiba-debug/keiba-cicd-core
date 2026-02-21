# ML デバッグ・強化 開発手順書

keiba-v2 の ML パイプラインを Jupyter Notebook で段階的にデバッグ・検証・強化するための実践的手順書。

---

## 概要: 2つの開発モード

| モード | 目的 | ツール |
|--------|------|--------|
| **探索モード** | 特徴量分析・仮説検証・可視化 | Jupyter Notebook |
| **実験モード** | フルモデル学習・バックテスト・バージョン管理 | `python -m ml.experiment` CLI |

**基本フロー**: Notebook で仮説検証 → experiment.py で本番実験 → バックテスト → デプロイ

---

## 1. 環境セットアップ

```bash
cd c:\KEIBA-CICD\_keiba\keiba-cicd-core
pip install jupyter ipykernel matplotlib seaborn shap
```

Cursor/VSCode で `.ipynb` ファイルを開き、右上でカーネル（keiba-v2 の venv）を選択。

---

## 2. Notebook テンプレート

### Cell 0: 初期化（全ノートブック共通）

```python
import sys
from pathlib import Path

ROOT = Path(r"c:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2")
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'MS Gothic'  # 日本語表示
plt.style.use('seaborn-v0_8-whitegrid')

from core import config
print(f"Data root: {config.data_root()}")
```

### Cell 1: データロード

```python
from ml.experiment import load_data

history_cache, trainer_index, jockey_index, \
    date_index, pace_index, kb_ext_index, training_summary_index = load_data()

print(f"馬: {len(history_cache):,}")
print(f"レース日: {len(date_index):,}")
print(f"KB ext: {len(kb_ext_index):,}")
```

> **所要時間**: 約2-3分（pace_index/kb_ext_index構築がボトルネック）

### Cell 2: データセット構築

```python
from ml.experiment import build_dataset

# 3-way split: train / val(early stopping) / test(純粋評価)
df_train = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                         pace_index, kb_ext_index, 2020, 2023,
                         training_summary_index=training_summary_index)
df_val   = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                         pace_index, kb_ext_index, 2024, 2024,
                         training_summary_index=training_summary_index)
df_test  = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                         pace_index, kb_ext_index, 2025, 2026,
                         training_summary_index=training_summary_index)

print(f"Train: {len(df_train):,} entries")
print(f"Val:   {len(df_val):,} entries")
print(f"Test:  {len(df_test):,} entries")
```

> **所要時間**: 約5-10分（全レースの特徴量計算）

---

## 3. デバッグ用ノートブック一覧

### 3.1 特徴量診断 (`notebooks/01_feature_diagnosis.ipynb`)

**目的**: 新特徴量の品質チェック、欠損率、分布、相関を確認

```python
from ml.experiment import FEATURE_COLS_ALL, FEATURE_COLS_VALUE, MARKET_FEATURES

# --- 欠損率チェック ---
missing = df_train[FEATURE_COLS_ALL].isnull().mean().sort_values(ascending=False)
print("=== 欠損率 Top 20 ===")
print(missing.head(20))

# --- 分布確認（ヒストグラム） ---
target_features = ['horse_slow_start_rate', 'comment_stable_condition']  # 確認したい特徴量
fig, axes = plt.subplots(1, len(target_features), figsize=(5*len(target_features), 4))
for ax, feat in zip(axes, target_features):
    df_train[feat].dropna().hist(bins=50, ax=ax)
    ax.set_title(feat)
plt.tight_layout()
plt.show()

# --- 目的変数との相関 ---
corr = df_train[FEATURE_COLS_ALL + ['is_top3', 'is_win']].corr()
top3_corr = corr['is_top3'].drop(['is_top3', 'is_win']).abs().sort_values(ascending=False)
print("\n=== is_top3 相関 Top 20 ===")
print(top3_corr.head(20))

# --- 特徴量間の多重共線性チェック ---
import seaborn as sns
fig, ax = plt.subplots(figsize=(16, 14))
sns.heatmap(corr[FEATURE_COLS_ALL].loc[FEATURE_COLS_ALL].abs(),
            cmap='YlOrRd', vmin=0, vmax=1, ax=ax)
ax.set_title('特徴量相関ヒートマップ')
plt.tight_layout()
plt.show()
```

### 3.2 モデル学習＆評価 (`notebooks/02_model_training.ipynb`)

**目的**: モデル学習の過程を可視化、ハイパーパラメータの影響を確認

```python
from ml.experiment import (
    train_model, FEATURE_COLS_ALL, FEATURE_COLS_VALUE,
    PARAMS_A, PARAMS_B, PARAMS_W, PARAMS_WV
)

# --- Model A (Place Accuracy) ---
model_a, metrics_a, importance_a, pred_a = train_model(
    df_train, df_val, df_test, FEATURE_COLS_ALL, PARAMS_A,
    label_col='is_top3', model_name='Model A'
)
print(f"Model A: AUC={metrics_a['auc']}, ECE={metrics_a['ece']}")

# --- 特徴量重要度 Top 30 ---
imp_df = pd.DataFrame.from_dict(importance_a, orient='index', columns=['gain'])
imp_df = imp_df.sort_values('gain', ascending=False)

fig, ax = plt.subplots(figsize=(10, 8))
imp_df.head(30).plot.barh(ax=ax)
ax.set_title('Model A 特徴量重要度 Top 30')
ax.invert_yaxis()
plt.tight_layout()
plt.show()
```

### 3.3 キャリブレーション分析 (`notebooks/03_calibration.ipynb`)

**目的**: 予測確率の信頼性を確認（ECE、キャリブレーションカーブ）

```python
from sklearn.calibration import calibration_curve

def plot_calibration(y_true, y_pred, model_name, n_bins=10):
    prob_true, prob_pred = calibration_curve(y_true, y_pred, n_bins=n_bins)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], 'k--', label='完全キャリブレーション')
    ax.plot(prob_pred, prob_true, 'o-', label=model_name)
    ax.set_xlabel('予測確率')
    ax.set_ylabel('実際の正例率')
    ax.set_title(f'{model_name} キャリブレーションカーブ')
    ax.legend()
    plt.tight_layout()
    plt.show()

# Model A
plot_calibration(df_test['is_top3'].values, pred_a, 'Model A')

# Model B
plot_calibration(df_test['is_top3'].values, pred_b, 'Model B')
```

### 3.4 Value Bet 分析 (`notebooks/04_value_bet_analysis.ipynb`)

**目的**: VB戦略の有効性をオッズ帯・トラック別に深掘り

```python
from ml.experiment import calc_value_bet_analysis, collect_value_bet_picks

# --- 全4モデルの予測を追加 ---
df_test['pred_proba_a'] = model_a.predict(df_test[FEATURE_COLS_ALL])
df_test['pred_proba_v'] = model_b.predict(df_test[FEATURE_COLS_VALUE])
df_test['pred_rank_a'] = df_test.groupby('race_id')['pred_proba_a'].rank(ascending=False)
df_test['pred_rank_v'] = df_test.groupby('race_id')['pred_proba_v'].rank(ascending=False)

# --- VB gap別 ROI ---
vb_results = calc_value_bet_analysis(df_test)
vb_df = pd.DataFrame(vb_results)
print(vb_df.to_string(index=False))

# --- 芝/ダート別 VB分析 ---
for track in ['芝', 'ダート']:
    subset = df_test[df_test['track_type'] == (1 if track == '芝' else 2)]
    if len(subset) == 0:
        continue
    vb = calc_value_bet_analysis(subset)
    print(f"\n--- {track} ---")
    print(pd.DataFrame(vb).to_string(index=False))

# --- VB候補のオッズ分布 ---
picks = collect_value_bet_picks(df_test, min_gap=3)
picks_df = pd.DataFrame(picks)
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
picks_df[picks_df['is_top3']==1]['odds'].hist(bins=30, ax=axes[0], alpha=0.7, label='的中')
picks_df[picks_df['is_top3']==0]['odds'].hist(bins=30, ax=axes[0], alpha=0.7, label='不的中')
axes[0].set_title('VB候補のオッズ分布')
axes[0].legend()
picks_df.groupby('gap')['is_top3'].mean().plot.bar(ax=axes[1])
axes[1].set_title('gap別 複勝的中率')
plt.tight_layout()
plt.show()
```

### 3.5 SHAP値分析 (`notebooks/05_shap_analysis.ipynb`)

**目的**: 個別予測の理由を解明、特徴量の非線形効果を把握

```python
import shap

# Model A の SHAP値計算（テストセットのサブセットで実行、全件だと時間かかる）
sample = df_test.sample(min(2000, len(df_test)), random_state=42)
X_sample = sample[FEATURE_COLS_ALL]

explainer = shap.TreeExplainer(model_a)
shap_values = explainer.shap_values(X_sample)

# --- Summary Plot ---
shap.summary_plot(shap_values, X_sample, max_display=30)

# --- 個別の予測を説明 ---
# 例: VB候補のうち、最もgapが大きかった馬
idx = picks_df['gap'].idxmax()
vb_horse = picks_df.loc[idx]
race_entries = sample[sample['race_id'] == vb_horse['race_id']]
if len(race_entries) > 0:
    horse_idx = race_entries.index[0]
    shap.force_plot(explainer.expected_value, shap_values[horse_idx],
                    X_sample.loc[horse_idx], matplotlib=True)

# --- 特定特徴量の部分依存 ---
shap.dependence_plot('comment_stable_condition', shap_values, X_sample)
```

### 3.6 特徴量実験 (`notebooks/06_feature_experiment.ipynb`)

**目的**: 新特徴量の追加/除外の影響をクイック検証

```python
# --- Ablation Study: 特徴量グループ別の寄与度 ---
from ml.experiment import train_model, PARAMS_A, PARAMS_B

feature_groups = {
    'BASE': BASE_FEATURES + ['odds', 'popularity', 'odds_rank'],
    'PAST': PAST_FEATURES,
    'RUNNING_STYLE': RUNNING_STYLE_FEATURES,
    'ROTATION': ROTATION_FEATURES,
    'PACE': PACE_FEATURES,
    'TRAINING': TRAINING_FEATURES + KB_MARK_FEATURES,
    'SPEED': SPEED_FEATURES,
    'COMMENT': COMMENT_FEATURES,
    'SLOW_START': SLOW_START_FEATURES,
}

# 1グループずつ除外して影響を測定
results = []
baseline_cols = FEATURE_COLS_ALL.copy()
_, baseline_metrics, _, _ = train_model(
    df_train, df_val, df_test, baseline_cols, PARAMS_A,
    label_col='is_top3', model_name='Baseline'
)

for group_name, group_features in feature_groups.items():
    ablated_cols = [f for f in baseline_cols if f not in group_features]
    _, metrics, _, _ = train_model(
        df_train, df_val, df_test, ablated_cols, PARAMS_A,
        label_col='is_top3', model_name=f'w/o {group_name}'
    )
    delta = metrics['auc'] - baseline_metrics['auc']
    results.append({
        'group': group_name,
        'features': len(group_features),
        'auc_without': metrics['auc'],
        'delta': delta,
    })

results_df = pd.DataFrame(results).sort_values('delta')
print(results_df.to_string(index=False))

fig, ax = plt.subplots(figsize=(10, 5))
results_df.plot.barh(x='group', y='delta', ax=ax, color='coral')
ax.axvline(x=0, color='k', linewidth=0.5)
ax.set_title('特徴量グループ除外時のAUC変化（負=重要）')
plt.tight_layout()
plt.show()
```

### 3.7 エラー分析 (`notebooks/07_error_analysis.ipynb`)

**目的**: モデルが間違えるケースのパターン分析

```python
# --- 予測追加 ---
df_test['pred_proba_a'] = pred_a
df_test['pred_rank_a'] = df_test.groupby('race_id')['pred_proba_a'].rank(ascending=False)

# --- 高確信ミス: モデルが上位予測したが凡走した馬 ---
high_conf_miss = df_test[
    (df_test['pred_rank_a'] == 1) &  # モデルTop1
    (df_test['finish_position'] > 5)   # 5着以下
].copy()
high_conf_miss = high_conf_miss.sort_values('pred_proba_a', ascending=False)

print(f"=== 高確信ミス: {len(high_conf_miss)} 件 ===")
print(high_conf_miss[['date', 'venue_name', 'horse_name', 'pred_proba_a',
                       'odds_rank', 'finish_position']].head(20).to_string())

# --- 穴馬的中: オッズ上位10位以下で3着以内 ---
upset_hits = df_test[
    (df_test['odds_rank'] >= 10) &
    (df_test['is_top3'] == 1) &
    (df_test['pred_rank_a'] <= 5)  # モデルがTop5に入れていたか
]
print(f"\n=== 穴馬的中 (オッズ10位以下, 3着以内): {len(upset_hits)} 件 ===")

# --- トラック別・距離帯別のAUC ---
from sklearn.metrics import roc_auc_score

for track in [1, 2]:  # 1=芝, 2=ダート
    subset = df_test[df_test['track_type'] == track]
    if len(subset) < 100:
        continue
    auc = roc_auc_score(subset['is_top3'], subset['pred_proba_a'])
    track_name = '芝' if track == 1 else 'ダート'
    print(f"{track_name}: AUC={auc:.4f} (n={len(subset):,})")

    # 距離帯別
    for dist_range, label in [
        ((0, 1400), '短距離'), ((1400, 1800), 'マイル'),
        ((1800, 2200), '中距離'), ((2200, 9999), '長距離')
    ]:
        s = subset[(subset['distance'] >= dist_range[0]) & (subset['distance'] < dist_range[1])]
        if len(s) >= 50:
            auc_d = roc_auc_score(s['is_top3'], s['pred_proba_a'])
            print(f"  {label}: AUC={auc_d:.4f} (n={len(s):,})")
```

---

## 4. 新特徴量の追加手順

### Step 1: 仮説を立てる
「この情報は勝敗に影響するはずだが、現在のモデルは考慮していない」

### Step 2: データ確認（Notebook）
```python
# 例: 出遅れ率 × 着順の関係
df_test.groupby(pd.cut(df_test['horse_slow_start_rate'], bins=5))['is_top3'].mean()
```

### Step 3: 特徴量モジュール作成
`ml/features/xxx_features.py` に `compute_xxx_features()` 関数を作成

### Step 4: experiment.py に統合
1. `XXX_FEATURES` リストを定義
2. `FEATURE_COLS_ALL` に追加
3. `MARKET_FEATURES` に該当するものがあれば追加
4. `compute_features_for_race()` に呼び出し追加

### Step 5: Notebook でクイック検証
```python
# 既存のdf_train/val/testに新特徴量を追加して学習
new_features = FEATURE_COLS_ALL + ['new_feat1', 'new_feat2']
model_new, metrics_new, _, pred_new = train_model(
    df_train, df_val, df_test, new_features, PARAMS_A,
    label_col='is_top3', model_name='Model A (new)'
)
print(f"AUC: {metrics_a['auc']} → {metrics_new['auc']} (Δ={metrics_new['auc']-metrics_a['auc']:+.4f})")
```

### Step 6: フル実験
```bash
python -m ml.experiment --version 5.5
```

### Step 7: バックテスト
```bash
python -m ml.backtest_vb --version 5.5
```

### Step 8: 判定基準
| 指標 | 改善条件 | 重要度 |
|------|---------|--------|
| Place VB gap≥5 ROI | +2pp 以上 | ★★★★★ 最重要 |
| Model A AUC | 変動 ±0.002 以内 | ★★★ |
| Model B AUC | 低下 0.005 以内 | ★★ |
| ECE | 0.005 未満維持 | ★★★ |
| Win VB gap≥5 ROI | +2pp 以上 | ★★★★ |

> **重要な教訓**: AUC改善 ≠ ROI改善。Model B の精度が上がりすぎると市場との乖離が縮まり VB 効果が死ぬ。

---

## 5. ハイパーパラメータチューニング

### 5.1 Notebook でのグリッドサーチ

```python
import itertools

param_grid = {
    'num_leaves': [31, 63, 127],
    'learning_rate': [0.01, 0.03, 0.05],
    'max_depth': [6, 7, 8],
}

results = []
for nl, lr, md in itertools.product(
    param_grid['num_leaves'],
    param_grid['learning_rate'],
    param_grid['max_depth'],
):
    params = {**PARAMS_A, 'num_leaves': nl, 'learning_rate': lr, 'max_depth': md}
    _, metrics, _, _ = train_model(
        df_train, df_val, df_test, FEATURE_COLS_ALL, params,
        label_col='is_top3', model_name=f'nl={nl},lr={lr},md={md}'
    )
    results.append({'num_leaves': nl, 'learning_rate': lr, 'max_depth': md,
                    'auc': metrics['auc'], 'ece': metrics['ece']})

results_df = pd.DataFrame(results).sort_values('auc', ascending=False)
print(results_df.head(10).to_string(index=False))
```

### 5.2 Optuna による自動チューニング

```python
import optuna

def objective(trial):
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'num_leaves': trial.suggest_int('num_leaves', 31, 255),
        'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.1, log=True),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.6, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.6, 1.0),
        'bagging_freq': trial.suggest_int('bagging_freq', 1, 10),
        'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.01, 10.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.01, 10.0, log=True),
        'max_depth': trial.suggest_int('max_depth', 4, 10),
        'verbose': -1,
    }
    _, metrics, _, _ = train_model(
        df_train, df_val, df_test, FEATURE_COLS_ALL, params,
        label_col='is_top3', model_name=f'Trial {trial.number}'
    )
    return metrics['auc']

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50)

print(f"Best AUC: {study.best_value:.4f}")
print(f"Best params: {study.best_params}")
```

---

## 6. デバッグチェックリスト

### 新特徴量が効かないとき
- [ ] 欠損率が高すぎないか（>50%なら要注意）
- [ ] 分散がゼロに近くないか（定数特徴量）
- [ ] 既存特徴量と相関 > 0.9 ではないか（冗長）
- [ ] MARKET_FEATURES に入れるべきものが VALUE に入っていないか
- [ ] LightGBM の feature_fraction が低すぎないか（特徴量増加時は 0.8 推奨）

### ROI が下がったとき
- [ ] Model B の AUC が上がりすぎていないか（市場との乖離が縮小）
- [ ] 新特徴量が MARKET 系ではないか（人気に織り込み済みの情報）
- [ ] テスト期間が短すぎないか（分散が大きい）
- [ ] ECE が悪化していないか（キャリブレーション崩れ）

### AUC が下がったとき
- [ ] 新特徴量にノイズが多くないか（辞書拡充版 v5.3b の教訓）
- [ ] データリークがないか（将来情報が特徴量に含まれていないか）
- [ ] NaN の扱いが変わっていないか

---

## 7. 実験記録テンプレート

各実験の結果は `ml-experiment-log.md` に以下のフォーマットで記録:

```markdown
### vX.Y — 実験名 (YYYY-MM-DD)

**変更点**:
- (何を追加/変更/削除したか)

**結果**:
| モデル | vX.Y-1 AUC | vX.Y AUC | Delta |
|--------|-----------|----------|-------|
| Model A | 0.XXXX | 0.XXXX | +0.XXXX |
| Model B | 0.XXXX | 0.XXXX | +0.XXXX |
| Model W | 0.XXXX | 0.XXXX | +0.XXXX |
| Model WV | 0.XXXX | 0.XXXX | +0.XXXX |

**VB ROI**:
- Place gap≥5: XXX.X% → XXX.X% (ΔXX.Xpp)
- Win gap≥5: XXX.X% → XXX.X% (ΔXX.Xpp)

**判定**: ✅ 採用 / ❌ 不採用 / 🔄 要追加検証

**学習事項**: (何がわかったか)
```

---

## 8. ファイル構成

```
keiba-v2/
├── notebooks/                    # ← 新規作成
│   ├── 01_feature_diagnosis.ipynb
│   ├── 02_model_training.ipynb
│   ├── 03_calibration.ipynb
│   ├── 04_value_bet_analysis.ipynb
│   ├── 05_shap_analysis.ipynb
│   ├── 06_feature_experiment.ipynb
│   └── 07_error_analysis.ipynb
├── ml/
│   ├── experiment.py             # フル実験（CLI）
│   ├── predict.py                # 本番予測
│   ├── backtest_vb.py            # VBバックテスト
│   └── features/                 # 特徴量モジュール群
└── docs/
    ├── ml-debug-procedure.md     # ← 本ファイル
    └── jupyter_notebook_procedure.md
```

---

## 9. 典型的なセッション例

### シナリオ: 「騎手乗り替わり×過去相性」特徴量を追加したい

1. **Notebook Cell**: 過去データで「乗り替わり時の勝率」を調べる
2. **Notebook Cell**: 騎手×馬の過去組み合わせ勝率を計算
3. **Notebook Cell**: 新特徴量を df_train に追加して分布・相関確認
4. **Notebook Cell**: Model A/B を学習して AUC/ECE 変化を確認
5. **Notebook Cell**: VB ROI の変化を確認
6. 結果が良ければ → `ml/features/jockey_features.py` に実装
7. `python -m ml.experiment --version 5.5` でフル実験
8. `ml-experiment-log.md` に記録
9. 判定基準（§4 Step 8）に基づき採用/不採用を決定

---

## 10. 注意事項

- **データリーク厳禁**: 特徴量計算時に「レース当日以降の情報」を使わないこと
- **テストセットは神聖**: df_test で何度もチューニングしない。仮説検証は df_val で
- **辞書は少数精鋭**: NLP特徴量で「曖昧な語を追加するとノイズになる」教訓（v5.3b）
- **MARKET分類は慎重に**: 新特徴量がオッズと相関 > 0.3 なら MARKET_FEATURES に入れることを検討
- **feature_fraction**: 特徴量が増えたら 0.7 → 0.8 に上げる（LightGBM がサンプルしやすくする）

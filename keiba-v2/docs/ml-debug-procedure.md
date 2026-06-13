# ML デバッグ・実験 開発手順書

keiba-v2 の ML パイプラインを段階的にデバッグ・検証・強化するための実践的手順書。

> **最終更新**: 2026-06-13（Session 156 全面改訂 — 旧版 2026-02-21 は Model A/B 時代の記述で現行と乖離していたため、
> 現行コード（P/W/AR + model_registry + E-008/E-009）で全文裏取りして書き直した）

---

## 概要: 2つの開発モード

| モード | 目的 | ツール |
|--------|------|--------|
| **探索モード** | 特徴量分析・仮説検証・可視化 | Jupyter Notebook（テンプレは §3） |
| **実験モード** | フルモデル学習・バックテスト・バージョン管理 | `python -m ml.experiment` CLI |

**基本フロー**: §0 プリフライト → Notebook で仮説検証 → experiment.py で本番実験 → 検証ハーネスで採否判定 → （採用時のみ）live昇格

---

## 0. 実験前プリフライト（必須）★

**教訓**: ML特徴量キャッシュが3ヶ月凍結したまま実験・ライブ予測が走り続けた事故（2026-06 Session 151 発覚）。
`experiment.py` は `horse_history_cache.json` と `race_date_index.json` を直読みするため、
**キャッシュが古いと「宣言したtest期間」と「実際のtestデータ」が黙ってズレる**
（実例: v8.4 は test宣言 2025-07〜2026-05 に対し実データ 2026-03 止まり）。

```bash
cd keiba-cicd-core/keiba-v2

# 1. MLキャッシュ鮮度チェック（race_date_index / horse_history_cache の被覆末日を確認）
python -m ml.cache_freshness                # --quick --json で軽量版（status-check用）

# 2. 古ければ再構築（keiba-data-prep スキル ②-4.5 と同じ手順）
python -m builders.build_race_index
python -m builders.build_horse_history

# 3. 分析JSONの被覆チェック（quality_meta/coverage 付き分析の凍結検知）
python -m analysis.check_coverage --expect <直近開催日>   # lag_days許容あり（RPCI=10日/IDM=21日）

# 4. predict.py の smoke test（ライブ系を触る前に）
python -m ml.preflight                      # --date YYYY-MM-DD で特定日
```

**実験を始める前に確認する4点**:
- [ ] `race_date_index.json` の max 日付が直近開催日か
- [ ] `horse_history_cache.json` が同日まで含むか（`ml.cache_freshness`）
- [ ] test期間として使う月のレースが実際にデータセットに乗るか（build後の件数を月別に確認）
- [ ] 血統系を使うなら `--sire-cutoff` の指定値（§4 Step 6 参照）

---

## 1. 環境セットアップ

```bash
cd c:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2
# venv 実体: keiba-v2/.venv/Scripts/python.exe（Session 121 で独立化）
pip install jupyter ipykernel matplotlib seaborn shap   # 探索モード用（任意）
```

Cursor/VSCode で `.ipynb` を開き、カーネルに keiba-v2 の venv を選択。
※ `notebooks/` ディレクトリは現状リポジトリに無い。以下のセル例は任意のNotebookに貼って使うテンプレート。

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

`load_data()` は **17要素 tuple** を返す（JRDB 7種を含む）。E-008 以降、血統リーク防止のため
cutoff の扱いに注意（cutoff付きファイルが無い場合は既定で停止）。

```python
from ml.experiment import load_data

(history_cache, trainer_index, jockey_index,
 date_index, pace_index, kb_ext_index, training_summary_index,
 race_level_index, pedigree_index, sire_stats_index,
 jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index,
 jrdb_cyb_index, jrdb_cha_index, jrdb_kka_index, jrdb_joa_index) = load_data(
    sire_cutoff="2025-06-30",   # test開始より前の日付を指定（PITリーク防止）
)

print(f"馬: {len(history_cache):,} / レース日: {len(date_index):,} / KYI: {len(jrdb_kyi_index):,}")
```

> **所要時間**: 数分（インデックス読込がボトルネック。jrdb_kyi_index は500MB）

### Cell 2: データセット構築

```python
from ml.experiment import build_dataset

common = dict(
    training_summary_index=training_summary_index,
    race_level_index=race_level_index,
    pedigree_index=pedigree_index,
    sire_stats_index=sire_stats_index,
    jrdb_sed_index=jrdb_sed_index, jrdb_kyi_index=jrdb_kyi_index,
    jrdb_kaa_index=jrdb_kaa_index, jrdb_cyb_index=jrdb_cyb_index,
    jrdb_cha_index=jrdb_cha_index, jrdb_kka_index=jrdb_kka_index,
    jrdb_joa_index=jrdb_joa_index,
)

# 3-way split: train / val(early stopping) / test(純粋評価)
df_train = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                         pace_index, kb_ext_index, 2020, 2024, **common)
df_val   = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                         pace_index, kb_ext_index, 2025, 2025, max_month=6, **common)
df_test  = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                         pace_index, kb_ext_index, 2025, 2026, min_month=7, **common)

print(f"Train: {len(df_train):,} / Val: {len(df_val):,} / Test: {len(df_test):,}")
# ★ test の月別件数を必ず確認（キャッシュ凍結だと末尾の月が黙って消える）
print(df_test['date'].str[:7].value_counts().sort_index().tail(6))
```

> JRDB index を渡し忘れると該当特徴量が全欠損のまま学習が走る（エラーにならない）。
> 件数と欠損率の確認を省略しないこと。

---

## 3. デバッグ用ノートブックテンプレ

現行モデルは **P (Place/is_top3) / W (Win/is_win) / AR (着差回帰)** の3本 + IsotonicRegression キャリブレーター。
ハイパラは `PARAMS_P` / `PARAMS_W` / `PARAMS_AR`（experiment.py）。

### 3.1 特徴量診断

```python
from ml.experiment import FEATURE_COLS_ALL, FEATURE_COLS_VALUE, MARKET_FEATURES, P_ONLY_FEATURES

# --- 欠損率チェック ---
missing = df_train[FEATURE_COLS_ALL].isnull().mean().sort_values(ascending=False)
print(missing.head(20))

# --- 分布確認 ---
target_features = ['jrdb_cid_score', 'horse_slow_start_rate']  # 確認したい特徴量
fig, axes = plt.subplots(1, len(target_features), figsize=(5*len(target_features), 4))
for ax, feat in zip(axes, target_features):
    df_train[feat].dropna().hist(bins=50, ax=ax)
    ax.set_title(feat)
plt.tight_layout(); plt.show()

# --- 目的変数との相関 / 多重共線性 ---
corr = df_train[FEATURE_COLS_ALL + ['is_top3', 'is_win']].corr()
print(corr['is_top3'].drop(['is_top3', 'is_win']).abs().sort_values(ascending=False).head(20))
```

### 3.2 モデル学習＆評価

```python
from ml.experiment import train_model, FEATURE_COLS_VALUE, PARAMS_P

# P モデル（VALUE特徴量 = MARKET除外）
model_p, metrics_p, importance_p, pred_p = train_model(
    df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_P,
    label_col='is_top3', model_name='P'
)
print(f"P: AUC={metrics_p['auc']}, ECE={metrics_p['ece']}")

# 特徴量重要度 Top 30
imp_df = pd.DataFrame.from_dict(importance_p, orient='index', columns=['gain'])
imp_df.sort_values('gain', ascending=False).head(30).plot.barh(figsize=(10, 8))
plt.gca().invert_yaxis(); plt.tight_layout(); plt.show()
```

### 3.3 キャリブレーション分析

```python
from sklearn.calibration import calibration_curve

def plot_calibration(y_true, y_pred, model_name, n_bins=10):
    prob_true, prob_pred = calibration_curve(y_true, y_pred, n_bins=n_bins)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], 'k--')
    ax.plot(prob_pred, prob_true, 'o-', label=model_name)
    ax.set_xlabel('予測確率'); ax.set_ylabel('実際の正例率'); ax.legend()
    plt.tight_layout(); plt.show()

plot_calibration(df_test['is_top3'].values, pred_p, 'P')
```

> ライブ予測の較正検証は Notebook より `ml/analyze/check_calibration.py` /
> `ml/analyze/validate_live_predictions.py`（E-009）の方が早い。較正の検証は
> 「ライブvs再推論の同一馬join」が最強の診断（Session 151 の教訓）。

### 3.4 Value Bet 分析

**現行の VB gap 定義**（experiment.py:3247）: 市場順位とモデル順位の直接乖離。

```
vb_gap     = (odds_rank - pred_rank_p).clip(lower=0)   # 複勝系
win_vb_gap = (odds_rank - pred_rank_w).clip(lower=0)   # 単勝系
```

```python
from ml.experiment import calc_value_bet_analysis, collect_value_bet_picks

df_test['pred_proba_p'] = model_p.predict(df_test[FEATURE_COLS_VALUE])
df_test['pred_rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(ascending=False)

vb_results = calc_value_bet_analysis(df_test, rank_col='pred_rank_p')
print(pd.DataFrame(vb_results).to_string(index=False))

picks = collect_value_bet_picks(df_test, min_gap=3)
```

### 3.5 SHAP値分析

```python
import shap

sample = df_test.sample(min(2000, len(df_test)), random_state=42)
X_sample = sample[FEATURE_COLS_VALUE]
explainer = shap.TreeExplainer(model_p)
shap_values = explainer.shap_values(X_sample)
shap.summary_plot(shap_values, X_sample, max_display=30)
```

### 3.6 特徴量アブレーション（グループ別寄与度）

```python
from ml.experiment import train_model, PARAMS_P

# 1グループずつ除外して影響を測定（CLI なら --exclude-features / --prune-bottom）
results = []
for group_name, group_features in feature_groups.items():   # 任意のグループ辞書
    ablated = [f for f in FEATURE_COLS_VALUE if f not in group_features]
    _, metrics, _, _ = train_model(df_train, df_val, df_test, ablated, PARAMS_P,
                                   label_col='is_top3', model_name=f'w/o {group_name}')
    results.append({'group': group_name, 'auc_without': metrics['auc']})
```

### 3.7 エラー分析（高確信ミス / 穴馬的中 / 条件別AUC）

```python
from sklearn.metrics import roc_auc_score

df_test['pred_rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(ascending=False)

# 高確信ミス: モデルTop1 で5着以下
high_conf_miss = df_test[(df_test['pred_rank_p'] == 1) & (df_test['finish_position'] > 5)]

# トラック別AUC
for track in [1, 2]:  # 1=芝, 2=ダート
    subset = df_test[df_test['track_type'] == track]
    if len(subset) >= 100:
        print(f"{'芝' if track==1 else 'ダート'}: "
              f"AUC={roc_auc_score(subset['is_top3'], subset['pred_proba_p']):.4f}")
```

---

## 4. 新特徴量の追加手順

### Step 1: 仮説を立てる
「この情報は勝敗に影響するはずだが、現在のモデルは考慮していない」
→ success criteria を先に明文化する（どの指標がどれだけ動いたら採用か）。

### Step 2: データ確認（Notebook）
```python
df_test.groupby(pd.cut(df_test['new_feat'], bins=5))['is_top3'].mean()
```

### Step 3: 特徴量モジュール作成
`ml/features/xxx_features.py` に `compute_xxx_features()` と `XXX_FEATURE_COLS` を定義。
JRDB系なら `docs/jrdb_data_inventory.md`（v2）で「インデックス到達済みか」を先に確認
（KYI はインデックスに約75フィールド格納済み＝特徴量関数を書くだけで届くものが多い）。

### Step 4: experiment.py に統合
1. import + `FEATURE_COLS_ALL` への追加
2. **市場相関が濃いものは `MARKET_FEATURES` へ**（オッズ・人気・印・指数系。
   VALUE側に入れると VB 差別化を壊す — v7.0 で JRDB事前指数6個を除外した教訓）
3. P にだけ効かせたいものは `P_ONLY_FEATURES` へ
4. `compute_features_for_race()` に呼び出し追加
5. predict.py 側の特徴量計算にも同じ呼び出しを配線（experiment と predict は別経路）

### Step 5: Notebook でクイック検証
```python
new_features = FEATURE_COLS_VALUE + ['new_feat1', 'new_feat2']
model_new, metrics_new, _, _ = train_model(df_train, df_val, df_test, new_features,
                                           PARAMS_P, label_col='is_top3')
```

### Step 6: フル実験（CLI）

```bash
# 特徴量を変更した場合 --version は必須（未指定だと差分検出で exit 1）
# 血統統計を使うため --sire-cutoff も必須（E-008: 未指定は exit 2。test開始より前の日付）
# live を切り替えたくない実験は必ず --no-set-active
python -m ml.experiment --version 2.5 ^
    --train-years 2020-2025.06 --val-years 2025.07 --test-years 2025.08-2026.05 ^
    --sire-cutoff 2025-07-31 --no-set-active
```

主要オプション: `--exclude-features` / `--prune-bottom N` / `--use-optuna` / `--time-decay` /
`--margin-mode adjusted` / `--allow-sire-leak`（本番最終学習で全データを使う時の明示オプトアウト）

> ⚠ **experiment.py は実行のたびに live のモデルファイル（ml_dir直下 + models/polaris/live/）を上書きする**。
> `--no-set-active` が守るのは registry の active_version ポインタだけ。
> 実験後にライブ運用へ戻すには §6 の `restore_live` を必ず実行する。

### Step 7: 採否判定（検証ハーネス）

```bash
# モデル比較: フル学習なしで backtest_cache ベースの即比較
python -m ml.backtest_bet_engine --cache-suffix <suffix>    # プリセット別 ROI
#   --test-years 2025.05-2026.05 で test 期間をオーバーライド可（既定は model_meta の split.test。
#   backtest_cache.json のフル再生成＝期間拡張はこのオーバーライドで行う。Session 157 実績:
#   --test-years 2025.05-2026.05 --sire-cutoff 2025-03-31 → 3,653R / 2026-05まで）
python -m ml.backtest_vb                                     # VB gap別 ROI

# 買い目層オプションの採否: E-009 ハーネス（単勝T-5/複勝確定の ROI + ブートCI + 月別 walk-forward）
python -m ml.analyze.validate_live_predictions --monthly --option <name>
```

### Step 8: 判定基準

| 指標 | 条件 | 備考 |
|------|------|------|
| gap別 ROI **ブートCI下限** | ベースライン超過 | 点推定でなく CI で判定（v8.4 の判定方式） |
| 月別 walk-forward | 特定 gap 帯で各月プラス | 幸運な窓に騙されない（E-009 `--monthly`） |
| P/W AUC | 参考値 | AUC改善 ≠ ROI改善 |
| ECE | 悪化しない | キャリブレーション崩れ検知 |

> **重要な教訓**:
> - AUC改善 ≠ ROI改善。VALUE側の精度が上がりすぎると市場との乖離が縮み VB が死ぬ。
> - 「入替/除外が起きること ≠ 収支が良くなること」（E-003/E-004 の連続実証）。
>   買い目層への新規介入はまず効かない。効くなら特徴量、効かないなら表示・運用（UI）へ。

---

## 5. ハイパーパラメータチューニング

```bash
python -m ml.experiment --use-optuna ...    # 本番実験に統合済み（モデル別特徴量リスト対応）
python -m ml.optuna_tuner                    # 単体チューナー
```

Notebook での手動グリッドサーチは `PARAMS_P` をベースに `train_model` を回す（§3.6 と同型）。

---

## 6. バージョン管理・ロールバック ★

### 構成要素

| 要素 | 場所 | 役割 |
|------|------|------|
| `model_registry.json` | `data3/ml/` | **唯一の真実**。モデル×バージョン一覧 + `active_version` |
| live モデル | `data3/ml/` 直下（旧構造）+ `data3/ml/models/polaris/live/`（新構造） | predict.py が読む実体。両方に同内容が書かれる |
| アーカイブ | `data3/ml/models/polaris/archive/v{ver}/` + `data3/ml/versions/v{ver}/`（旧） | 上書き前に自動退避（冪等） |
| `ml/model_loader.py` | — | `load_model("polaris", version=...)` でパス解決・ロード（新→旧フォールバック） |

### experiment.py 実行時に起きること（保存フロー）

1. 旧バージョンを `versions/v{old}/` にアーカイブ（`core/versioning.archive_before_save`、冪等）
2. `ml_dir` 直下に model_p/w/ar.txt + calibrators.pkl + model_meta.json を**上書き**
3. 新構造 `models/polaris/live/` にもコピー（上書き前に旧liveを `archive/v{prev}/` へ退避）
4. registry に `register_version`（**既定で active_version も切替**。`--no-set-active` で抑止）

### よく使うコマンド

```bash
# バージョン一覧 / 現在の active
python -m ml.predict --list-versions
python -m ml.switch_model --current

# 実験後にライブへ戻す（ファイルコピーのみ・registry は触らない — レース中も安全）
# ⚠ restore_live は現 live をアーカイブしない。実験モデルを残したい場合は
#   restore 前に live/ → models/polaris/archive/v{ver}/ へ手動コピーすること
#   （v8.4 初回で 2.4b の実体が消失した実例あり。Session 157 で退避手順を実施）
python -m ml.restore_live polaris 2.3
python -m ml.restore_live polaris 2.3 --dry-run

# active_version の正式切替（昇格・ロールバック両方）
python -m ml.set_active polaris 2.5
python -m ml.set_active polaris --list

# 旧バージョンでの予測（一時的な検証）
python -m ml.predict --date 2026-06-13 --model-version 2.2
```

### 昇格（live化）の標準手順

1. `--no-set-active` で実験 → 検証ハーネスで採否判定
2. 採用なら `python -m ml.set_active polaris <ver>`（restore_live 済みなら再学習 or archive からコピー）
3. `python -m ml.preflight` で smoke test
4. `ml_experiment_log.md` に記録 + `docs/ml-experiments/` に詳細レポート
5. 不採用なら `python -m ml.restore_live polaris <旧ver>` で復旧（v8.4 で実証済みの手順）

---

## 7. デバッグチェックリスト

### 新特徴量が効かないとき
- [ ] 欠損率が高すぎないか（>50%なら要注意）
- [ ] 分散がゼロに近くないか（定数特徴量 — pace_match 死特徴量化の教訓）
- [ ] 既存特徴量と相関 > 0.9 ではないか（冗長）
- [ ] MARKET_FEATURES に入れるべきものが VALUE に入っていないか
- [ ] **experiment 側に足して predict 側に配線し忘れていないか**（学習時のみ存在→ライブで全欠損）
- [ ] JRDB index を build_dataset に渡し忘れていないか（黙って全欠損になる）

### ROI が下がったとき
- [ ] VALUE側の AUC が上がりすぎていないか（市場との乖離が縮小）
- [ ] 新特徴量が MARKET 系ではないか（人気に織り込み済みの情報）
- [ ] テスト期間が短すぎないか / **test の月別件数が宣言期間と一致しているか**（キャッシュ凍結検知）
- [ ] ECE が悪化していないか
- [ ] オッズ条件は確定オッズで判定していないか（後知恵 — predictions の直前オッズで再検証）

### AUC が下がったとき
- [ ] 新特徴量にノイズが多くないか
- [ ] データリークがないか（血統 cutoff / 将来情報。E-008 で血統は既定ガード済み）
- [ ] NaN の扱いが変わっていないか（LightGBM ネイティブに委ねる方針）

### ライブ予測がおかしいとき
- [ ] §0 のキャッシュ鮮度（人気馬の過小評価はキャッシュ凍結の典型症状）
- [ ] `model_meta.json` の version が想定どおりか（実験でliveを上書きしたまま戻し忘れ）
- [ ] ライブvs再推論の同一馬join で「ライブ時点で何が欠けていたか」を定量化

---

## 8. 実験記録テンプレート

実験は `docs/ml_experiment_log.md` に記録（新しいものが上）。詳細は `docs/ml-experiments/vX.Y_名前.md` に分離。

```markdown
## vX.Y / 実験名 (YYYY-MM-DD, セッション)

### 背景
（仮説と success criteria）

### 分割
train / val / test（★testの実データ月別件数も記録 — 宣言とのズレ検知）

### 結果
| 指標 | 旧 | 新 |
|------|----|----|
| P AUC / W AUC | | |
| gap別 ROI（ブートCI下限） | | |

### 判定
採用 / 不採用（理由・CI根拠）・live切替の有無（--no-set-active / restore_live / set_active）

→ 詳細: docs/ml-experiments/vX.Y_xxx.md
```

---

## 9. predictions にフィールドを追加したときの表示更新チェックリスト ★

モデル/予測の出力を変えたら web 側の更新漏れを防ぐ（詳細は `ML_SOURCE_GUIDE.md` §8）:

- [ ] `web/src/lib/data/predictions-reader.ts` — `PredictionEntry` 型に追加（オプショナル `?` で後方互換）
- [ ] `web/src/lib/data/ml-prediction-reader.ts` — `MlHorsePrediction` + `convertV4Entry()`（races-v2 経路）
- [ ] 表示コンポーネント — `predictions/components/vb-table.tsx` / `components/race-v2/HorseEntryTable.tsx`
- [ ] フィルタ/買い目に関与するなら `predictions-content.tsx` の state / bet-engine
- [ ] `npx tsc --noEmit` で型チェック・古い predictions.json でも壊れないこと
- [ ] 動的サブルートの `force-dynamic` 指定（無いと未来日レースが静的キャッシュ→404）

参考実装パターン: reason_tags（E-005, Session 154）= predict.py 付与 → reader 型 → `ReasonTagBadges` 表示。

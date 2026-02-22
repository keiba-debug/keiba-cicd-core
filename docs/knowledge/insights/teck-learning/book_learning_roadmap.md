# 書籍×プロジェクト 実践学習ロードマップ

所有書籍の各章を、keiba-v2 の実際のコード・データ・開発タスクと紐づけた学習計画。
「読むだけ」ではなく、**プロジェクトのコードを動かし・改善しながら学ぶ**ことを重視する。

> 📖 **ML学習ロードマップ**: [ml_learning_roadmap.md](ml_learning_roadmap.md) の Level 0〜5, DE と対応。
> 🔧 **DE実践**: [data_engineering_roadmap.md](data_engineering_roadmap.md) の Phase 1-5 と対応。
> 🧭 **考察の全体像**: [考察マスター](../../consideration_master.md) のテーママップと合わせて読む。
>
> 最終更新: 2026-02-16

---

## 所有書籍

| 略称 | タイトル | 著者 | 性格 |
|------|----------|------|------|
| **DS入門** | ゼロからはじめるデータサイエンス 第2版 | Joel Grus | DS の原理をゼロから Python で実装。「中身を理解する」本 |
| **DE基礎** | データエンジニアリングの基礎 | Joe Reis & Matt Housley | DE のライフサイクル・アーキテクチャ・技術選定の教科書 |
| **DS設計** | データサイエンス設計マニュアル | Steven Skiena | DS プロジェクトの設計思想。数学・統計・ML を横断的に俯瞰 |
| **FE実践** | 事例で学ぶ特徴量エンジニアリング | Sinan Ozdemir | 5つのケーススタディで特徴量の作成・選択・管理を実践的に学ぶ |

---

## 学習フェーズの全体像

```
Phase A: データを見る目を養う（統計・可視化・確率）
  │  DS入門 Ch 3,5,6,7 / DS設計 Ch 2,5,6 / FE実践 Ch 2(評価指標)
  │  → keiba-v2: horse_history_cache を使った EDA
  │
Phase B: データを整える力をつける（前処理・取得・品質）
  │  DS入門 Ch 9,10 / DE基礎 Ch 1-4 / DS設計 Ch 3 / FE実践 Ch 3
  │  → keiba-v2: parsers, builders, data3/
  │
Phase C: モデルの仕組みを理解する（回帰・決定木・アンサンブル）
  │  DS入門 Ch 11,14,15,16,17 / DS設計 Ch 9,11
  │  → keiba-v2: experiment_v3.py, LightGBM パラメータ
  │
Phase D: 特徴量とモデル評価を磨く（特徴量設計・評価指標）★FE実践の主戦場
  │  DS設計 Ch 4 / DS入門 Ch 8 / DE基礎 Ch 8,9 / FE実践 Ch 1,2,4,7
  │  → keiba-v2: ml/features/ 全8モジュール, BETTING_STRATEGY
  │
Phase E: パイプラインと運用基盤（ETL・自動化・監視）
  │  DE基礎 Ch 5,6,7,8,9 / FE実践 Ch 8
  │  → keiba-v2: builders/, keibabook/, data3/ → SQL Server
  │
Phase F: 発展トピック（DL・NLP・クラスタリング・ネットワーク）
     DS入門 Ch 18,19,20,21,22,24 / DS設計 Ch 8,10,12 / FE実践 Ch 5,6
     → 将来のモデル拡張に備える
```

---

## Phase A: データを見る目を養う

**ゴール**: keiba-v2 の実データで統計・可視化・確率を体感する。
**ML学習ロードマップ対応**: Level 0-1〜0-6

### 読む順序と実践

| 順 | 書籍 | 章 | テーマ | keiba-v2 実践 |
|----|------|-----|--------|---------------|
| A-1 | DS入門 | Ch 3 データの可視化 | matplotlib 基礎、棒/折れ線/散布図 | `horse_history_cache.json` から馬体重分布・着順分布・上がり3Fのヒストグラムを描く |
| A-2 | DS設計 | Ch 6 データの可視化 | 可視化の原則、チャート選択 | オッズ vs 着順の散布図、競馬場別勝率の棒グラフ、RPCIの時系列推移を設計する |
| A-3 | DS入門 | Ch 5 統計 | 平均・分散・相関・Simpson のパラドックス | `past_features.py` の `win_rate_all`, `top3_rate_all` を条件別（芝/ダート、距離帯）にクロス集計。Simpson のパラドックスが競馬場×馬場状態で起きないか確認 |
| A-4 | DS設計 | Ch 5 統計分析 | 分布、仮説検定、p値の注意点 | Model A vs Model B の AUC 差が統計的に有意かブートストラップで検定。「有意だが効果量は？」を考える |
| A-5 | DS入門 | Ch 6 確率 | 条件付き確率、ベイズ | 単勝確率 → 馬連・三連単の条件付き確率（Harville）を Ch 6 の確率論で理論的に理解する |
| A-6 | DS入門 | Ch 7 仮説と推定 | 信頼区間、p値、A/Bテスト | ROI 104.7% (gap≥3) の95%信頼区間をブートストラップで計算。「偶然ではないか」を検証する |
| A-7 | DS設計 | Ch 2 数学の基礎知識 | 確率、組合せ、対数 | ケリー基準の数学的導出を理解。対数効用関数 → `BETTING_STRATEGY.md` の数式の意味を深掘り |

### 実践課題

```python
# A-1: horse_history_cache を読み込んで基本統計
import json
import pandas as pd

with open('data3/ml/horse_history_cache.json') as f:
    cache = json.load(f)

# 全走歴をフラットなDataFrameに
rows = []
for ketto, runs in cache.items():
    for r in runs:
        r['ketto_num'] = ketto
        rows.append(r)
df = pd.DataFrame(rows)

# 課題1: df.describe() で全カラムの統計量を確認
# 課題2: 着順分布のヒストグラム
# 課題3: 上がり3F (last_3f) と着順の散布図
# 課題4: 芝/ダート × 距離帯のクロス集計（勝率）
# 課題5: オッズと着順の相関係数 + 散布図
```

```python
# A-6: ROI の信頼区間（ブートストラップ）
# ml_experiment_v3_result.json の value_bets データを使用
import numpy as np

# 各賭けの損益を配列にする
# profits = [各賭けの profit]  # 的中時: (odds/3.5)*100-100, 外れ時: -100

n_boot = 10000
roi_samples = []
for _ in range(n_boot):
    sample = np.random.choice(profits, size=len(profits), replace=True)
    roi_samples.append(sample.sum() / (len(sample) * 100) * 100 + 100)

print(f"ROI 95%CI: [{np.percentile(roi_samples, 2.5):.1f}%, {np.percentile(roi_samples, 97.5):.1f}%]")
```

**対応する keiba-v2 ファイル**:
- `data3/ml/horse_history_cache.json` — 全馬の走歴データ
- `ml/experiment_v3.py` — `calc_roi_analysis()`, `calc_value_bet_analysis()`
- `docs/BETTING_STRATEGY.md` — EV計算、ケリー基準の実装設計

---

## Phase B: データを整える力をつける

**ゴール**: データの取得→解析→構造化のパイプラインを理解し改善できるようになる。
**ML学習ロードマップ対応**: Level DE-1, DE-2
**DEロードマップ対応**: Phase 1-2

### 読む順序と実践

| 順 | 書籍 | 章 | テーマ | keiba-v2 実践 |
|----|------|-----|--------|---------------|
| B-1 | DE基礎 | Ch 1 データエンジニアリング概説 | DE の役割、ステークホルダー、スキル | 自プロジェクトの成熟度マップ（`data_engineering_roadmap.md` §2）と照合。自分はどの段階か |
| B-2 | DE基礎 | Ch 2 ライフサイクル | 生成→取り込み→変換→サービング→メタデータ | `fast_batch_cli → parsers → JSON → [断絶] → 分析` のフローを Ch 2 のライフサイクルで再解釈。どこが弱いか |
| B-3 | DS入門 | Ch 9 データの取得 | スクレイピング、API、ファイル読み込み | `keibabook/scraper.py`, `batch_scraper.py` のコードを読み、Ch 9 のパターンと比較。エラーハンドリングやリトライは十分か |
| B-4 | DS設計 | Ch 3 データマンジング | 正規化、欠損処理、結合、型変換 | `se_parser.py` の 555バイト固定長 → dict 変換を読む。欠損値（-1埋め）の設計方針を Ch 3 の知見で評価 |
| B-5 | DS入門 | Ch 10 データの操作 | クレンジング、変換、次元削除 | `build_horse_history.py` のキャッシュ構築ロジックを読み、データ変換パターンを理解する |
| B-6 | DE基礎 | Ch 3 アーキテクチャ設計 | バッチ vs ストリーム、モノリス vs マイクロサービス | keiba-v2 のバッチアーキテクチャが適切か。レース当日のリアルタイム予測に必要な設計変更は |
| B-7 | DE基礎 | Ch 4 テクノロジの選択 | ツール選定の判断基準 | JSON vs SQL Server vs DuckDB。`data_engineering_roadmap.md` の技術スタック選定を Ch 4 の基準で再評価 |
| B-8 | FE実践 | Ch 3 ヘルスケア事例 | 構造化データの欠損処理・変換パターン | `se_parser.py` の -1 埋め・欠損戦略を Ch 3 のアプローチ（中央値補完、フラグ化、多重代入）と比較。`build_horse_history.py` のキャッシュ構築で情報が落ちている箇所はないか |

### 実践課題

```python
# B-3: keibabook スクレイパーのエラーハンドリング調査
# keibabook/scraper.py を読み、以下を確認:
#   - リトライ機構はあるか？
#   - レート制限への対応は？
#   - レスポンスの検証（空HTML、エラーページ）は？
# Ch 9 のベストプラクティスと比較し、改善点をリストアップ

# B-4: se_parser.py のフォーマット理解
# core/jravan/se_parser.py を読み、以下を実践:
#   - 555バイトの各フィールド位置と型を理解
#   - パース失敗時の挙動を確認
#   - docs/DATA_SPEC.md のフォーマット仕様と照合

# B-5: データ品質プロファイリング（Phase A の EDA を発展）
import json
import pandas as pd

# horse_history_cache からデータ品質レポート
with open('data3/ml/horse_history_cache.json') as f:
    cache = json.load(f)

# 課題: 年別の欠損率推移を可視化
# - last_3f が 0 の割合（年別）
# - corners が空の割合（年別）
# - odds が 0 の割合（年別）
# → 品質が年によって変わるか？ フォーマット変更の痕跡はあるか？
```

**対応する keiba-v2 ファイル**:
- `core/jravan/se_parser.py`, `sr_parser.py`, `um_parser.py` — JRA-VAN バイナリパーサー
- `builders/build_race_master.py`, `build_horse_history.py` — データ構築パイプライン
- `keibabook/scraper.py`, `batch_scraper.py` — Web スクレイピング
- `core/config.py` — パス管理・環境設定
- `docs/DATA_SPEC.md` — JRA-VAN フォーマット仕様

---

## Phase C: モデルの仕組みを理解する

**ゴール**: LightGBM が「なぜ動くか」を原理から理解し、パラメータ調整の根拠を持つ。
**ML学習ロードマップ対応**: Level 1-1, 2-2, 2-3

### 読む順序と実践

| 順 | 書籍 | 章 | テーマ | keiba-v2 実践 |
|----|------|-----|--------|---------------|
| C-1 | DS入門 | Ch 11 機械学習 | 教師あり/なし、バイアス-バリアンス、過学習 | `experiment_v3.py` の train/test 分割を読み、なぜ時系列分割が必要か Ch 11 の理論で説明する |
| C-2 | DS入門 | Ch 14 単純な線形回帰 | 最小二乗法、勾配降下法 | 着順予測をまず線形回帰で試みる。`past_features` だけで重回帰 → LightGBM との精度差を体感 |
| C-3 | DS入門 | Ch 15 重回帰分析 | 多変数、多重共線性、正則化 | 62特徴量の相関行列を計算。多重共線性のペア（例: `odds` と `popularity`）を発見し、Ch 15 の知見を適用 |
| C-4 | DS入門 | Ch 16 ロジスティック回帰 | 確率出力、シグモイド、クロスエントロピー | `is_top3` をロジスティック回帰で予測 → `predict_proba` → キャリブレーション曲線を描く。LightGBM との比較 |
| C-5 | DS入門 | Ch 17 決定木 | エントロピー、情報利得、剪定 | LightGBM の1本の木を可視化（`lgb.plot_tree()`）。`num_leaves=63` と `max_depth=7` の意味を Ch 17 で理解 |
| C-6 | DS設計 | Ch 9 回帰 | 線形/ロジスティック/正則化 | Ch 9 の正則化理論 → `PARAMS_A` の `reg_alpha=0.1`, `reg_lambda=1.0` がどう過学習を防ぐか解釈 |
| C-7 | DS設計 | Ch 11 機械学習 | アンサンブル、ブースティング、ランダムフォレスト | ブースティングの逐次学習の仕組みを理解。`n_estimators=1500` + `early_stopping=50` の意味。バギングとの違い |
| C-8 | DS入門 | Ch 8 勾配降下法 | SGD、学習率、収束 | `learning_rate=0.03` の意味を勾配降下法の理論から理解。小さいほど慎重だが遅い、のトレードオフ |

### 実践課題

```python
# C-2/C-4: ベースラインモデルの構築
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import roc_auc_score
import lightgbm as lgb

# experiment_v3.py の build_dataset() でデータを構築済みと仮定
# df_train, df_test が手元にある状態で:

# ベースライン1: ロジスティック回帰
lr = LogisticRegression(max_iter=1000)
lr.fit(X_train, y_train)
pred_lr = lr.predict_proba(X_test)[:, 1]
print(f"LogReg AUC: {roc_auc_score(y_test, pred_lr):.4f}")

# ベースライン2: LightGBM (keiba-v2 PARAMS_A)
# → AUC の差を確認。「アルゴリズムの差」vs「特徴量の差」を体感

# C-3: 相関行列
import seaborn as sns
corr = df_train[FEATURE_COLS_ALL].corr()
# 相関 > 0.8 のペアを抽出
high_corr = [(c1, c2, corr.loc[c1, c2])
             for c1 in corr.columns for c2 in corr.columns
             if c1 < c2 and abs(corr.loc[c1, c2]) > 0.8]

# C-5: 決定木の可視化
import lightgbm as lgb
lgb.plot_tree(model_a, tree_index=0, figsize=(20, 10))
# → どの特徴量で最初に分岐しているか？ odds? past_features? training?
```

**対応する keiba-v2 ファイル**:
- `ml/experiment_v3.py` — `PARAMS_A`, `PARAMS_B`, `train_model()`, `build_dataset()`
- `ml/features/base_features.py` — 基本特徴量の定義
- `docs/BETTING_STRATEGY.md` — モデル評価指標の定義

---

## Phase D: 特徴量とモデル評価を磨く

**ゴール**: 特徴量エンジニアリングの考え方を身につけ、評価指標の意味を深く理解する。
**ML学習ロードマップ対応**: Level 0-3, 1-3, 1-4, 3

### 読む順序と実践

| 順 | 書籍 | 章 | テーマ | keiba-v2 実践 |
|----|------|-----|--------|---------------|
| D-1 | DS設計 | Ch 4 スコアとランキング | 順位付け、正規化、重み付け | `speed_features.py` のスピード指数（最新/最高/平均/トレンド/安定性）は Ch 4 のスコアリングそのもの。設計思想を比較 |
| D-2 | DS設計 | Ch 7 数理モデル | シミュレーション、推定、最適化 | ケリー基準の最適化 → Ch 7 の最適化理論で理解。モンテカルロシミュレーションで破産確率を推定 |
| D-3 | DS入門 | Ch 8 勾配降下法 | ミニバッチ、確率的勾配降下法 | Optuna のベイズ最適化（TPE）の内部で何が起きているかの概念理解。勾配降下法との対比 |
| D-4 | FE実践 | Ch 1-2 特徴量の基本 | データ尺度、特徴量の改善/作成/選択/抽出/学習 | 75特徴量を4尺度（名義・順序・間隔・比例）で分類。`base_features.py` の Label Encoding は順序尺度として妥当か？ 特徴量の「改善 vs 作成 vs 選択」フレームワークで8モジュールを棚卸し |
| D-5 | FE実践 | Ch 7 時系列: デイトレード | ラグ特徴量、ローリング特徴量、多項式特徴量 | `past_features.py` の `avg_finish_last3`, `best_l3f_last5` はローリング集約そのもの。Ch 7 のラグ特徴量設計パターンで新特徴量の着想を得る。`speed_features.py` のトレンド計算を多項式特徴量で発展 |
| D-6 | FE実践 | Ch 4 バイアスと公平性 | Yeo-Johnson変換、公平性指標、AIF360 | オッズの右に歪んだ分布を Yeo-Johnson 変換で正規化する効果を検証。VB判定が特定の人気帯・馬場・距離に偏っていないかの公平性分析 |

### 特徴量モジュール × 書籍の対応

keiba-v2 の8つの特徴量モジュールそれぞれについて、関連する書籍の章を示す。

| モジュール | 特徴量数 | 関連する書籍の章 | 学びのポイント |
|-----------|---------|----------------|---------------|
| `base_features.py` | 11 | DS設計 Ch 3 / **FE実践 Ch 2** | カテゴリ変数のエンコーディング（`sex_map`, `track_map`, `baba_map`）。**Ch 2 の4尺度分類で Label Encoding の妥当性を再検討** |
| `past_features.py` | 13 | DS入門 Ch 5,10 / **FE実践 Ch 7** | 集約統計量（平均、最大、勝率）の設計。**Ch 7 のラグ・ローリング特徴量パターンで新特徴量を着想** |
| `trainer_features.py` | 3 | DS入門 Ch 16 | Target Encoding の一種（調教師の勝率で置換）。少数サンプル問題 → 正則化の発想 |
| `jockey_features.py` | 3 | DS入門 Ch 16 | trainer と同じ構造。交差して使うと多重共線性が生じないか |
| `running_style_features.py` | 8 | DS設計 Ch 4 / **FE実践 Ch 7** | コーナー順位を正規化（`/num_runners`）してスコア化。**Ch 7 のローリング特徴量で脚質の安定性を時系列化** |
| `rotation_features.py` | 4 | DS入門 Ch 14-15 / **FE実践 Ch 7** | 差分特徴量（`futan_diff`）、比率特徴量。**Ch 7 のラグ特徴量設計で間隔・斤量変化の時系列パターンを発展** |
| `pace_features.py` | 6 | DS設計 Ch 7 | RPCI という物理量に基づくモデリング。`consumption_flag` はドメイン知識による二値化 |
| `speed_features.py` | 5 | DS設計 Ch 4 / **FE実践 Ch 7** | 複数のスコア集約（最新/最高/平均/トレンド/安定性）。**Ch 7 の多項式特徴量でトレンド計算を発展** |
| `training_features.py` | 7+ | **FE実践 Ch 2,3** | CK_DATA 由来の調教特徴量。**Ch 2 の特徴量選択手法で MARKET_FEATURES 分類の根拠を強化。Ch 3 の欠損処理でタイムレベル欠損への対応を改善** |

### 実践課題

```python
# D-1: 特徴量重要度の分析
# experiment_v3.py 実行後の importance_a / importance_b を比較

# 課題1: Model A と Model B で重要度が大きく異なる特徴量は何か？
#         → 市場系を除くと何が「浮上」してくるか

# 課題2: 各特徴量カテゴリ別の重要度合計
categories = {
    'base': BASE_FEATURES,
    'past': PAST_FEATURES,
    'trainer': TRAINER_FEATURES,
    'jockey': JOCKEY_FEATURES,
    'running_style': RUNNING_STYLE_FEATURES,
    'rotation': ROTATION_FEATURES,
    'pace': PACE_FEATURES,
    'training': TRAINING_FEATURES,
    'speed': SPEED_FEATURES,
}
for cat, feats in categories.items():
    total = sum(importance_b.get(f, 0) for f in feats)
    print(f"{cat:>15}: {total:>10,}")

# 課題3: SHAP値で個別の馬の予測を分解
import shap
explainer = shap.TreeExplainer(model_b)
shap_values = explainer.shap_values(X_test)
shap.summary_plot(shap_values, X_test, feature_names=FEATURE_COLS_VALUE)
```

```python
# D-4: 75特徴量の4尺度分類（FE実践 Ch 2）
# Ch 2 の名義・順序・間隔・比例の4尺度で全特徴量を分類
scale_classification = {
    'nominal': ['sex', 'track_type', 'baba', 'running_style'],  # 名義: 順序なし
    'ordinal': ['class_code', 'timeLevel'],  # 順序: 大小関係あり
    'interval': [],  # 間隔: ゼロ点が任意
    'ratio': ['odds', 'weight', 'last_3f', 'avg_finish_last3'],  # 比例: 自然なゼロ点
}
# 課題: Label Encoding は「順序尺度」に適用すべき。名義尺度に使っていないか？
# 課題: 比例尺度の特徴量に対数変換が有効なケースは？（オッズの右裾）

# D-5: ラグ特徴量の再設計（FE実践 Ch 7）
# past_features.py の既存ラグ設計 vs Ch 7 のパターン
# 課題1: avg_finish_last3 は単純平均。指数加重移動平均（EWMA）の方が直近重視で有効か？
# 課題2: speed_trend は線形回帰の傾き。多項式（2次）フィットで「加速/減速/V字回復」を捉えられるか？
# 課題3: Ch 7 の「ラグ特徴量 × ローリング特徴量の組合せ」で新特徴量:
#   - lag1_finish - rolling_avg_5 = 「直近走の偏差」
#   - rolling_std_5（着順のばらつき）→ finish_std_last5 として既に実装済み！
```

**対応する keiba-v2 ファイル**:
- `ml/features/` — 8モジュール全て（+ training_features.py）
- `ml/experiment_v3.py` — `calc_hit_analysis()`, `calc_value_bet_analysis()`
- `docs/DATA_LEAKAGE_INVESTIGATION.md` — 62特徴量のリーク監査

---

## Phase E: パイプラインと運用基盤

**ゴール**: データの流れを端から端まで自動化し、品質を保証する。
**ML学習ロードマップ対応**: Level DE-1〜DE-3
**DEロードマップ対応**: Phase 2-4

### 読む順序と実践

| 順 | 書籍 | 章 | テーマ | keiba-v2 実践 |
|----|------|-----|--------|---------------|
| E-1 | DE基礎 | Ch 5 ソースシステム | ファイル、DB、API、メッセージキュー | keiba-v2 のソースは 3 系統: JRA-VAN バイナリ / keibabook HTML / mykeibadb MySQL。Ch 5 の分類で整理 |
| E-2 | DE基礎 | Ch 6 ストレージ | ファイルシステム、オブジェクトストレージ、DB | 現在の `data3/` JSON ファイルシステムは適切か？ SQL Server への移行メリットを Ch 6 の基準で評価 |
| E-3 | DE基礎 | Ch 7 データ取り込み | バッチ vs ストリーム、増分 vs 全量 | `builders/` のフルビルド vs 日次差分更新。`build_race_master.py --years 2020-2026` は全量。増分戦略は |
| E-4 | DE基礎 | Ch 8 クエリ・変換 | SQL、データモデリング、dbt | `build_dataset()` の pandas 変換を SQL クエリで実現する設計。スター/スノーフレークスキーマ |
| E-5 | DE基礎 | Ch 9 ML へのデータ提供 | 特徴量ストア、MLパイプライン | `horse_history_cache.json` は事実上の特徴量ストア。Ch 9 の基準で評価し改善する |
| E-6 | DS入門 | Ch 24 データベースと SQL | テーブル設計、JOIN、集約 | SQL Server の既存スキーマ定義を読み、`horse_history_cache` 相当の SQL クエリを書く |
| E-7 | DE基礎 | Ch 10 セキュリティ | 暗号化、アクセス制御、データガバナンス | 競馬データの取り扱い。スクレイピングの法的リスク。JRA-VAN 利用規約の確認 |
| E-8 | FE実践 | Ch 8 特徴量ストア | Hopsworks、特徴量ビュー、来歴管理 | `horse_history_cache.json` は事実上の特徴量キャッシュ。Ch 8 の設計（ポイントインタイム結合、特徴量ビュー、来歴追跡）で本格的な特徴量ストアへの発展を設計。ML版 `data_engineering_roadmap.md` Phase 5 と統合 |

### 実践課題

```
# E-2/E-3: データフロー図の作成
# 現在のフロー:
#   JRA-VAN Binary → se_parser → build_race_master → race_*.json
#                                                         ↓
#                   build_horse_history → horse_history_cache.json
#                                                         ↓
#   keibabook HTML → batch_scraper → kb_ext_*.json        ↓
#                                         ↓               ↓
#                          experiment_v3.py: build_dataset() → DataFrame
#                                                                ↓
#                                                          train_model() → model_a.txt
#
# 課題: このフローを DE基礎 Ch 2 のライフサイクル図に当てはめて再描画
# 課題: Ch 7 の取り込みパターン（バッチ/マイクロバッチ/ストリーム）で分類

# E-4: SQL で特徴量計算を再現
# 例: trainer_win_rate を SQL で計算
#
# SELECT
#   trainer_code,
#   COUNT(*) as total_runs,
#   SUM(CASE WHEN finish_position = 1 THEN 1 ELSE 0 END) as wins,
#   CAST(SUM(CASE WHEN finish_position = 1 THEN 1 ELSE 0 END) AS FLOAT)
#     / COUNT(*) as win_rate
# FROM race_entries
# WHERE race_date < '2025-01-01'
# GROUP BY trainer_code
# HAVING COUNT(*) >= 30;

# E-5: horse_history_cache の品質チェック
# - 欠損率レポート（年別・フィールド別）
# - データ鮮度チェック（最新レースの日付）
# - 整合性チェック（race_id の形式、finish_position の範囲）
```

**対応する keiba-v2 ファイル**:
- `builders/` — 全ビルダーモジュール
- `keibabook/batch_scraper.py` — バッチスクレイピング
- `core/db.py`, `core/odds_db.py` — MySQL 連携
- `core/config.py` — パス管理
- `data_engineering_roadmap.md` — Phase 1-5 の実践計画

---

## Phase F: 発展トピック

**ゴール**: 将来の拡張（映像解析、NLP、クラスタリング等）に備えた知識の土台を作る。
**ML学習ロードマップ対応**: Level 2-4〜2-6

### 読む順序と実践

| 順 | 書籍 | 章 | テーマ | keiba-v2 での将来の活用 |
|----|------|-----|--------|-------------------------|
| F-0a | FE実践 | Ch 5 NLP: 感情分析 | BoW、TF-IDF、BERT転移学習 | `danwa_parser.py` の調教師コメントを特徴量化。「前向き/慎重/期待大」のセンチメントスコア化。Ch 5 の BoW → TF-IDF → BERT の段階的アプローチで実装コストを見積もる |
| F-0b | FE実践 | Ch 6 CV: 物体認識 | HOG、VGG-11、PCA | 将来の映像解析の基礎知識。Ch 6 の PCA による次元削減は62特徴量の圧縮にも転用可能 |
| F-1 | DS入門 | Ch 4 線形代数 | ベクトル・行列・固有値 | 「能力はスカラーではなくベクトル」（`ability_is_not_scalar.md`）の数理的理解。能力ベクトル×条件ベクトル |
| F-2 | DS設計 | Ch 8 線形代数 | SVD、次元削減、PCA | 62特徴量の次元削減。PCA で何次元に情報が集中しているかを確認 |
| F-3 | DS入門 | Ch 20 クラスタリング | k-means、階層クラスタリング | 馬のタイプ分類（安定強者/安定好走/一発型）をクラスタリングで自動検出。`horse_performance_distribution.md` |
| F-4 | DS入門 | Ch 18,19 ニューラルネット/DL | パーセプトロン、逆伝播 | 将来の映像解析・NLP の基礎知識。TabNet 等の表形式 DL の前提理解 |
| F-5 | DS入門 | Ch 21 自然言語処理 | TF-IDF、n-gram、トピックモデル | `keibabook/parsers/danwa_parser.py` の調教師コメントの特徴量化。NLP で「前向き/慎重/期待大」を数値化 |
| F-6 | DS入門 | Ch 12 k近傍法 | 類似度、距離関数 | 類似馬検索。「この馬と似た過去走パターンの馬」を k-NN で探索 |
| F-7 | DS設計 | Ch 10 ネットワーク分析 | グラフ、中心性、PageRank | 種牡馬ネットワーク。「この種牡馬の産駒はどの馬場・距離に強いか」のグラフ分析 |
| F-8 | DS設計 | Ch 12 ビッグデータ | MapReduce、分散処理 | 現時点では不要だが、データ量が増えたときのスケーリング戦略として知っておく |

---

## 書籍章 → keiba-v2 逆引き表

各書籍の全章について、プロジェクトとの関連度と対応コードを一覧化する。

### DS入門（ゼロからはじめるデータサイエンス 第2版）

| 章 | テーマ | 関連度 | Phase | keiba-v2 対応 |
|----|--------|--------|-------|---------------|
| 1 | イントロダクション | △ | - | 全体像の理解 |
| 2 | Python速習 | △ | - | 既に Python 使用中。復習用 |
| **3** | **データの可視化** | **★★★** | **A** | horse_history_cache の EDA、キャリブレーションプロット |
| 4 | 線形代数 | ★ | F | 能力ベクトル理論、PCA |
| **5** | **統計** | **★★★** | **A** | 特徴量の分布、相関分析、条件別集計 |
| **6** | **確率** | **★★★** | **A** | Harville、条件付き確率、ベイズ更新 |
| **7** | **仮説と推定** | **★★★** | **A** | ROI の信頼区間、モデル差の検定 |
| **8** | **勾配降下法** | **★★** | **C/D** | LightGBM の learning_rate、Optuna |
| **9** | **データの取得** | **★★★** | **B** | keibabook スクレイパー、JRA-VAN パーサー |
| **10** | **データの操作** | **★★★** | **B** | builders、データ変換パイプライン |
| **11** | **機械学習** | **★★★** | **C** | experiment_v3.py 全体 |
| 12 | k近傍法 | ★ | F | 類似馬検索（将来） |
| 13 | ナイーブベイズ | △ | - | 競馬では使いにくい |
| **14** | **単純な線形回帰** | **★★** | **C** | ベースラインモデル |
| **15** | **重回帰分析** | **★★** | **C** | 多重共線性の理解、正則化 |
| **16** | **ロジスティック回帰** | **★★★** | **C** | 確率出力の基礎、キャリブレーション |
| **17** | **決定木** | **★★★** | **C** | LightGBM の構成要素、可視化 |
| 18 | ニューラルネットワーク | ★ | F | DL 基礎（将来） |
| 19 | ディープラーニング | ★ | F | 映像解析（将来） |
| **20** | **クラスタリング** | **★★** | **F** | 馬タイプ自動分類 |
| **21** | **自然言語処理** | **★★** | **F** | 調教師コメントの特徴量化 |
| 22 | ネットワーク分析 | ★ | F | 種牡馬ネットワーク（将来） |
| 23 | リコメンドシステム | △ | - | 直接の用途なし |
| **24** | **データベースとSQL** | **★★** | **E** | SQL Server、ETL |
| 25 | MapReduce | △ | - | 現時点では不要 |
| 26 | データ倫理 | ★ | - | スクレイピング倫理、データ利用の責任 |
| 27 | 前進しよう | △ | - | モチベーション |

### DE基礎（データエンジニアリングの基礎）

| 章 | テーマ | 関連度 | Phase | keiba-v2 対応 |
|----|--------|--------|-------|---------------|
| **1** | **DE概説** | **★★★** | **B** | プロジェクト成熟度の自己評価 |
| **2** | **ライフサイクル** | **★★★** | **B** | データフローの全体設計 |
| **3** | **アーキテクチャ設計** | **★★★** | **B** | バッチ vs リアルタイム、JSON vs DB |
| **4** | **テクノロジ選択** | **★★** | **B** | 技術スタック（Prefect, pandera 等）の判断基準 |
| **5** | **ソースシステム** | **★★★** | **E** | JRA-VAN / keibabook / mykeibadb |
| **6** | **ストレージ** | **★★★** | **E** | data3/ JSON → SQL Server 移行 |
| **7** | **データ取り込み** | **★★★** | **E** | builders のバッチ取り込み設計 |
| **8** | **クエリ・変換** | **★★★** | **E** | pandas 変換 → SQL 変換への移行 |
| **9** | **ML へのデータ提供** | **★★★** | **E** | horse_history_cache、特徴量ストア |
| 10 | セキュリティ | ★★ | E | データ取り扱い、法的リスク |
| 11 | DE の未来 | ★ | - | トレンド把握 |

### DS設計（データサイエンス設計マニュアル）

| 章 | テーマ | 関連度 | Phase | keiba-v2 対応 |
|----|--------|--------|-------|---------------|
| 1 | DSとは | ★ | - | 全体像の理解 |
| **2** | **数学の基礎** | **★★** | **A** | ケリー基準の数学、対数効用 |
| **3** | **データマンジング** | **★★★** | **B** | パーサー、エンコーディング、欠損処理 |
| **4** | **スコアとランキング** | **★★★** | **D** | speed_features、running_style の正規化 |
| **5** | **統計分析** | **★★★** | **A** | 仮説検定、p値の注意点、効果量 |
| **6** | **データの可視化** | **★★★** | **A** | チャート選択、可視化設計の原則 |
| **7** | **数理モデル** | **★★** | **D** | シミュレーション、ケリー最適化 |
| 8 | 線形代数 | ★ | F | 次元削減、PCA |
| **9** | **回帰** | **★★★** | **C** | 線形/ロジスティック/正則化 |
| 10 | ネットワーク分析 | ★ | F | 種牡馬ネットワーク（将来） |
| **11** | **機械学習** | **★★★** | **C** | アンサンブル、ブースティング |
| 12 | ビッグデータ | △ | F | スケーリング（将来） |
| 13 | 最後に一言 | ★ | - | キャリア指針 |

### FE実践（事例で学ぶ特徴量エンジニアリング）

| 章 | テーマ | 関連度 | Phase | keiba-v2 対応 |
|----|--------|--------|-------|---------------|
| **1** | **特徴量エンジニアリング入門** | **★★** | **D** | 特徴量設計の全体思想を整理。「いつ・どの手法を使うか」のフレームワーク |
| **2** | **特徴量の基本** | **★★★** | **D** | 4データ尺度（名義/順序/間隔/比例）で75特徴量を分類。特徴量の改善/作成/選択/抽出/学習の5つのアプローチで8モジュールを棚卸し |
| **3** | **ヘルスケア: COVID-19** | **★★** | **B/D** | 構造化データの欠損処理パターン。se_parser の -1埋め戦略、training_features の欠損処理を比較評価 |
| **4** | **バイアスと公平性** | **★★** | **D** | Yeo-Johnson変換でオッズ分布を正規化。VB判定の人気帯バイアス検証。AIF360の公平性指標 |
| **5** | **NLP: 感情分析** | **★★** | **F** | BoW/TF-IDF/BERT。danwa_parser 調教師コメントの特徴量化（将来） |
| 6 | CV: 物体認識 | ★ | F | HOG/VGG-11/PCA。映像解析の基礎、PCA による特徴量圧縮 |
| **7** | **時系列: デイトレード** | **★★★** | **D** | ラグ/ローリング/多項式特徴量。past_features/speed_features/rotation_features に直結。EWMA・多項式トレンドで発展 |
| **8** | **特徴量ストア** | **★★★** | **E** | Hopsworks、特徴量ビュー、来歴管理。horse_history_cache → 本格的特徴量ストアへの設計指針 |
| 9 | まとめと展望 | ★ | - | 最新トレンド把握 |

---

## 推奨学習スケジュール

### 最初の1ヶ月: Phase A（データを見る目）

```
Week 1: DS入門 Ch 3 (可視化) + DS設計 Ch 6 (可視化)
        → horse_history_cache で EDA 実践
Week 2: DS入門 Ch 5 (統計) + DS設計 Ch 5 (統計分析)
        → 特徴量の分布・相関分析
Week 3: DS入門 Ch 6 (確率) + Ch 7 (仮説と推定)
        → ROI の信頼区間、Harville の確率論
Week 4: DS設計 Ch 2 (数学) + 復習
        → ケリー基準の数学的理解
```

### 2ヶ月目: Phase B + C 並行

```
Week 5-6: DE基礎 Ch 1-3 (DE概説〜アーキテクチャ)
           + DS入門 Ch 9-10 (データ取得・操作)
           + FE実践 Ch 3 (ヘルスケア事例 — 欠損処理パターン)
           → parsers / builders のコードリーディング
           → データ品質プロファイリング実践
Week 7-8: DS入門 Ch 11, 14-17 (ML〜決定木)
           + DS設計 Ch 9, 11 (回帰、ML)
           → ベースラインモデル構築
           → experiment_v3.py の完全理解
```

### 3ヶ月目: Phase D + E ★FE実践の主戦場

```
Week 9-10: FE実践 Ch 1-2 (特徴量の基本フレームワーク)
            + DS設計 Ch 3-4 (マンジング、スコア)
            → 75特徴量を4尺度で分類・棚卸し
            → 特徴量モジュール全8本のコードリーディング
Week 11:   FE実践 Ch 7 (時系列: デイトレード) ★最重要章
            → past_features/speed_features のラグ・ローリング設計を再評価
            → EWMA/多項式トレンドの新特徴量をプロトタイプ
Week 12:   FE実践 Ch 4 (バイアスと公平性)
            + DE基礎 Ch 5-9 (ソース〜ML提供)
            + FE実践 Ch 8 (特徴量ストア)
            → VB判定のバイアス検証
            → horse_history_cache → 特徴量ストア設計
            → SHAP 分析の実践
```

### 4ヶ月目以降: Phase F（必要に応じて）

```
FE実践 Ch 5 (NLP) + DS入門 Ch 21 → 調教師コメント特徴量（優先度高）
FE実践 Ch 6 (CV) + DS入門 Ch 18-19 → 映像解析の基礎
DS入門 Ch 20 (クラスタリング) → 馬タイプ自動分類
DS入門 Ch 4 (線形代数) + DS設計 Ch 8 → PCA、能力ベクトル
```

---

## 学習のコツ

### 1. 「読む → 動かす → 書く」のサイクル

```
読む: 書籍の章を読む（概念・理論）
  ↓
動かす: keiba-v2 のコードで実際にデータを扱う
  ↓
書く: 発見・疑問を knowledge/insights/ に記録する
  ↓
繰り返す
```

### 2. 書籍をそのまま読まなくてよい

- **DS入門**: Ch 2 (Python速習), Ch 13 (ナイーブベイズ), Ch 23 (リコメンド), Ch 25 (MapReduce) は飛ばしてOK
- **DE基礎**: Ch 11 (未来) は読み物として。Ch 10 (セキュリティ) は必要時に
- **DS設計**: Ch 1, Ch 12, Ch 13 は概要把握のみでOK
- **FE実践**: Ch 6 (CV) は将来の映像解析まで後回しでOK。Ch 9 (まとめ) は読み物として

### 3. 4冊の使い分け

```
「なぜそうなるか」を知りたい　→ DS入門（原理からPythonで実装）
「何を選ぶべきか」を知りたい　→ DE基礎（判断基準とトレードオフ）
「どう設計すべきか」を知りたい → DS設計（プロジェクト視点の俯瞰）
「どう作り・管理するか」　　　→ FE実践（事例で特徴量を磨く）★ NEW
```

4冊の関係:
```
DS入門（理論基盤）─→ DS設計（設計俯瞰）
    ↓                       ↓
FE実践（特徴量実践）←──────┘
    ↓
DE基礎（運用基盤）← FE実践 Ch 8（特徴量ストア）
```

### 4. keiba-v2 のコードは最高の教材

- 75特徴量×9モジュール = 実践的な特徴量エンジニアリングの教科書（FE実践 Ch 2,7 と直結）
- `experiment_v3.py` = ML パイプラインの教科書
- `data3/` のJSON構造 = データモデリングの教材
- `docs/DATA_LEAKAGE_INVESTIGATION.md` = データリーク対策の教材
- `docs/BETTING_STRATEGY.md` = 確率論・期待値・資金管理の教材
- `horse_history_cache.json` = 特徴量ストアの原型（FE実践 Ch 8 と直結）

---

## タグ

`#モデル` `#特徴量` `#確率論` `#前処理` `#データソース` `#運用`

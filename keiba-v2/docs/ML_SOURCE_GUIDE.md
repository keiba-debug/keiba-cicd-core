# ML期待値ベット抽出プロジェクト ソース解説

> JRA-VAN + 競馬ブックデータを活用し、機械学習で期待値の高いベットを抽出するプロジェクトのソースコード解説。
> 開発中ソースや状況を正しく理解するためのガイド。

**最終更新**: 2026-02-22

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [アーキテクチャ概要](#2-アーキテクチャ概要)
3. [ディレクトリ構成](#3-ディレクトリ構成)
4. [MLモジュール詳細](#4-mlモジュール詳細)
5. [予測パイプライン](#5-予測パイプライン)
6. [買い目エンジン (bet_engine)](#6-買い目エンジン-bet_engine)
7. [特徴量エンジニアリング](#7-特徴量エンジニアリング)
8. [Web Predictions画面](#8-web-predictions画面)
9. [実験・バックテスト](#9-実験バックテスト)
10. [関連ドキュメント一覧](#10-関連ドキュメント一覧)

---

## 1. プロジェクト概要

### 目的

- **期待値ベースの馬券購入支援**: 機械学習で「市場が過小評価している馬（Value Bet）」を検出し、期待値の高いベットを推奨する
- **Value Bet戦略**: Model A（市場含む）と Model B（市場系除外）の順位乖離（Gap）を利用
- **単勝・複勝の推奨**: Win ROI 119.9%、gap>=6+EV>=1.2+m<=0.8 で統計的有意なCI下限>100%を達成

### 技術スタック

| 領域 | 技術 |
|------|------|
| ML | LightGBM (分類4本 + 回帰1本), IsotonicRegression (キャリブレーション) |
| 言語 | Python 3.11, TypeScript |
| Web | Next.js 16, React 19 |
| データ | JRA-VAN (C:\TFJV), mykeibadb (MySQL), 競馬ブックスクレイピング |

---

## 2. アーキテクチャ概要

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           データソース                                        │
│  JRA-VAN (TFJV)  競馬ブック (Web)  mykeibadb (事前オッズ・確定オッズ)          │
└─────────────────────┬────────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  builders/  マスタJSON構築                                                    │
│  build_race_master, build_horse_master, build_horse_history, ...              │
└─────────────────────┬────────────────────────────────────────────────────────┘
                      │ data3/races, data3/masters, data3/keibabook
                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  ml/  機械学習パイプライン                                                    │
│                                                                              │
│  experiment.py ────► モデル訓練 (LightGBM)  ────► model_a/b.txt, model_w/wv   │
│                     calibrators.pkl, model_reg_b.txt                          │
│                                                                              │
│  predict.py ───────► 当日予測  ────► predictions_live.json                    │
│                     bet_engine.py で買い目推奨を生成                           │
└─────────────────────┬────────────────────────────────────────────────────────┘
                      │ predictions_live.json
                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  web/src/app/predictions/  Predictions 画面                                   │
│  レース一覧、Value Bet候補、推奨買い目、ROI分析、TARGET連携                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. ディレクトリ構成

```
keiba-v2/
├── ml/                          # 機械学習モジュール
│   ├── experiment.py            # メイン実験・訓練スクリプト
│   ├── predict.py               # 当日予測・predictions_live.json 生成
│   ├── bet_engine.py            # 買い目推奨エンジン (Python側ロジック)
│   ├── backtest_bet_engine.py   # bet_engine バックテスト
│   ├── backtest_vb.py           # VB均一買いバックテスト
│   ├── experiment_regression.py # 着差回帰実験
│   ├── experiment_lambdarank.py # LambdaRank実験
│   ├── features/                # 特徴量エンジニアリング
│   │   ├── base_features.py
│   │   ├── past_features.py
│   │   ├── trainer_features.py
│   │   ├── jockey_features.py
│   │   ├── running_style_features.py
│   │   ├── rotation_features.py
│   │   ├── pace_features.py
│   │   ├── training_features.py
│   │   ├── speed_features.py
│   │   ├── comment_features.py
│   │   ├── slow_start_features.py
│   │   ├── margin_target.py
│   │   └── training_features.py
│   └── tests/
│       └── test_bet_engine.py
│
├── web/src/app/predictions/     # Predictions 画面 (Next.js)
│   ├── page.tsx                 # ページエントリ
│   ├── predictions-content.tsx  # メインコンテンツ
│   ├── lib/
│   │   ├── bet-logic.ts         # 予算リスケール・均等配分
│   │   ├── types.ts
│   │   └── helpers.tsx
│   └── components/
│       ├── bet-recommendations.tsx
│       ├── vb-table.tsx
│       ├── race-card.tsx
│       ├── filter-bar.tsx
│       ├── roi-summary.tsx
│       └── ...
│
└── docs/                        # ドキュメント
    ├── ML_SOURCE_GUIDE.md       # 本ドキュメント
    ├── models_and_features.md   # モデル・特徴量定義
    ├── BETTING_STRATEGY.md      # ベッティング戦略
    ├── ml-experiments/          # 実験レポート
    │   ├── README.md
    │   ├── v5.6_ev_gap_analysis.md
    │   └── ...
    └── ...
```

---

## 4. MLモジュール詳細

### 4.1 experiment.py

**役割**: モデル訓練・評価パイプライン。LightGBMで4つの分類モデル（A/B/W/WV）と1つの回帰モデル（Reg B）を学習する。

**主な処理フロー**:

1. **データロード**: `load_data()` で horse_history_cache, trainer_index, jockey_index, date_index 等を取得
2. **データセット構築**: `build_dataset()` で train/val/test を年別に構築（デフォルト: train=2020-2024, test=2025-2026）
3. **特徴量**: `FEATURE_COLS_ALL`（全特徴量）と `FEATURE_COLS_VALUE`（市場系除外）を定義
4. **訓練**:
   - `train_model()` で分類モデル (A, B, W, WV) を訓練
   - `train_regression_model()` で Reg B（着差回帰）を訓練
   - IsotonicRegression で Win モデルをキャリブレーション
5. **バックテスト**: VB均一買い、bet_engine ROI を計算
6. **出力**: model_meta.json, model_*.txt, calibrators.pkl, model_reg_b.txt

**起動方法**:
```powershell
python -m ml.experiment [--train-years 2020-2024] [--test-years 2025-2026]
```

**特徴量定義場所**:
- `BASE_FEATURES`, `PAST_FEATURES`, `TRAINER_FEATURES`, ... は experiment.py 内で定義
- 各特徴量の実計算は `ml/features/` 配下モジュールで実行

---

### 4.2 predict.py

**役割**: 当日の全レースに対して予測を実行し、`predictions_live.json` を生成する。bet_engine で買い目推奨も生成。

**主な処理フロー**:

1. **モデルロード**: `load_model_and_meta()` で model_a, model_b, model_w, model_wv, calibrators, model_reg_b をロード
2. **マスタロード**: history_cache, trainer_index, jockey_index, pace_index, kb_ext_index
3. **レース取得**: `get_races_for_date(date)` で race_{id}.json を読み込み
4. **DB事前オッズ**: mykeibadb から単勝・複勝オッズを取得（`batch_get_pre_race_odds`, `batch_get_place_odds`）
5. **各レース予測**: `predict_race()` で特徴量構築→推論→EV計算→VB gap計算
6. **買い目推奨**: `generate_recommendations()` で4プリセット（win_only, conservative, standard, aggressive）の推奨を生成
7. **保存**: `data3/ml/predictions_live.json` と `data3/races/YYYY/MM/DD/predictions.json`

**起動方法**:
```powershell
python -m ml.predict --date 2026-02-22
python -m ml.predict --latest
python -m ml.predict --model-version 5.0
python -m ml.predict --list-versions
```

---

### 4.3 モデル構成

| モデル | 用途 | 特徴量 | ラベル |
|--------|------|--------|--------|
| Model A | 複勝予測（市場含む） | FEATURE_COLS_ALL | is_top3 |
| Model B | 複勝予測（市場除外） | FEATURE_COLS_VALUE | is_top3 |
| Model W | 単勝予測（市場含む） | FEATURE_COLS_ALL | is_win |
| Model WV | 単勝予測（市場除外） | FEATURE_COLS_VALUE | is_win |
| Reg B | 着差回帰（margin） | FEATURE_COLS_VALUE | target_margin |

**Value Bet の考え方**:
- `vb_gap = odds_rank - rank_v` （人気順位 − Model B順位）
- gap が大きいほど「市場が過小評価している馬」
- gap >= 3 で VB とみなす（`VALUE_BET_MIN_GAP`）

---

## 5. 予測パイプライン

### predict_race() の処理内容

1. **特徴量構築**  
   各馬に対して以下を順に実行:
   - `extract_base_features` → 基本・オッズ等
   - `compute_past_features` → 過去走
   - `get_trainer_features`, `get_jockey_features`
   - `compute_running_style_features`
   - `compute_rotation_features`
   - `compute_pace_features`
   - `compute_training_features` (調教)
   - `compute_speed_features`
   - `compute_comment_features`
   - `compute_slow_start_features`

2. **推論**  
   - Place: model_a.predict(), model_b.predict()
   - Win: model_w.predict(), model_wv.predict()
   - Margin: model_reg_b.predict()

3. **EV計算**  
   - 単勝EV = calibrated P(win) × 単勝オッズ
   - 複勝EV = calibrated P(top3) × 複勝最低オッズ

4. **VB判定**  
   - `is_value_bet = (vb_gap >= VALUE_BET_MIN_GAP) and (odds_rank > 0)`

---

## 6. 買い目エンジン (bet_engine)

### 6.1 概要

`ml/bet_engine.py` は、Python側で買い目推奨を一元生成するモジュール。predict.py と experiment.py の両方から利用される。

**設計原則**:
- **Win**: ルールベース（gap + margin）。Win ECE が悪いため Kelly は使わない
- **Place**: gap + margin + calibrated EV + 1/4 Kelly
- **1レース1単勝制約**: 2番目以降の単勝候補は複勝に降格
- **4プリセット**: win_only, standard, conservative, aggressive

### 6.2 主要関数

| 関数 | 役割 |
|------|------|
| `evaluate_win(gap, margin, params, is_danger)` | 単勝対象かどうか、ベット倍率を返す |
| `evaluate_place(gap, margin, p_top3, place_odds, params, is_danger)` | 複勝対象かどうか、Kelly割合を返す |
| `calc_kelly_fraction(prob, odds)` | Kelly Criterion 計算 |
| `detect_danger(entries, threshold)` | 危険馬検出（comment_memo_trouble_score） |
| `generate_recommendations(race_predictions, params, budget)` | 全レースの推奨買い目を生成 |
| `apply_single_win_constraint(recs)` | 1レース1単勝制約適用 |
| `apply_budget(recs, budget, params)` | Kelly→実金額に変換し予算内にスケーリング |

### 6.3 プリセット

| プリセット | win_min_gap | win_max_margin | place_min_gap | place_max_margin | place_min_ev |
|-----------|-------------|----------------|---------------|------------------|--------------|
| win_only | 5 | 1.2 | 99(無効) | - | - |
| conservative | 5 | 1.2 | 5 | 0.8 | 1.2 |
| standard | 4 | 1.2 | 4 | 0.8 | 1.2 |
| aggressive | 3 | 1.5 | 2 | 1.5 | 0.9 |

### 6.4 バックテスト用

- `df_to_race_predictions(df_test)`: DataFrame → generate_recommendations 入力形式
- `calc_bet_engine_roi(recs, race_predictions)`: 推奨買い目の実ROI計算

---

## 7. 特徴量エンジニアリング

### 7.1 モジュール一覧

| ファイル | 主な関数 | 役割 |
|----------|----------|------|
| base_features.py | extract_base_features | 馬齢・性別・斤量・オッズ等 |
| past_features.py | compute_past_features | 過去走・着差・上がり3F等 |
| trainer_features.py | get_trainer_features | 調教師勝率・距離適性 |
| jockey_features.py | get_jockey_features | 騎手勝率・乗替わり効果 |
| running_style_features.py | compute_running_style_features | 脚質・展開適性 |
| rotation_features.py | compute_rotation_features | 降格ローテ・レースレベル |
| pace_features.py | compute_pace_features | RPCI・33ラップ等 |
| training_features.py | compute_training_features | CK_DATA調教・KB印 |
| speed_features.py | compute_speed_features | スピード指数 |
| comment_features.py | compute_comment_features | 厩舎コメントNLP |
| slow_start_features.py | compute_slow_start_features | 出遅れ（現状無効化） |
| margin_target.py | add_margin_target_to_df | 着差ターゲット生成 |

### 7.2 特徴量の分類

- **MARKET**: オッズ・人気・odds_rank・KB印・CK_DATA調教等 → Model B では除外
- **VALUE**: 過去走・調教師・騎手・脚質・ペース・コメントNLP等 → Model B に含める

詳細は `keiba-v2/docs/models_and_features.md` を参照。

---

## 8. Web Predictions画面

### 8.1 構成

| コンポーネント | 役割 |
|----------------|------|
| page.tsx | ルート。predictions_live.json を読み込み PredictionsContent に渡す |
| predictions-content.tsx | メイン。フィルタ・オッズ・ROI・推奨買い目・VB候補を統合 |
| bet-recommendations.tsx | 推奨買い目一覧。プリセット選択・予算変更・TARGET書込み |
| vb-table.tsx | Value Bet候補テーブル。ソート・VB印反映 |
| race-card.tsx | レース単位の出馬表 |
| filter-bar.tsx | 会場・芝/ダ・gap・EV・margin・betOnly フィルタ |
| roi-summary.tsx | ROIサマリー（全VB / 推奨のみ / 推奨外） |

### 8.2 データフロー

1. **入力**: `predictions_live.json`（predict.py の出力）
2. **オッズ更新**: `/api/odds/db-latest` でリアルタイムオッズ取得（当日は30秒ごと）
3. **推奨買い目**: サーバー側 bet_engine が生成した `recommendations[preset].bets` を使用
4. **予算変更**: `bet-logic.ts` の `rescaleBudget()` でユーザー予算に按分
5. **TARGET連携**: `/api/target-marks/auto-vb`, `/api/target-marks/auto-bet` でVB印・買い目を書き込み

### 8.3 bet-logic.ts

- `BET_CONFIG`: defaultBudget=30000, minBet=100, betUnit=100
- `rescaleBudget(recs, newBudget, baseBudget)`: サーバーの30,000円基準をユーザー予算に按分
- `equalDistribute(recs, budget)`: 均等配分モード（Kellyではなく均等割り）

---

## 9. 実験・バックテスト

### 9.1 スクリプト一覧

| スクリプト | 役割 |
|------------|------|
| backtest_bet_engine.py | bet_engine 各プリセットのROIをバックテスト |
| backtest_vb.py | VB均一買いのROI分析（gap閾値別） |
| experiment_regression.py | 着差回帰の実験 |
| experiment_lambdarank.py | LambdaRankの実験 |
| ci_power_analysis.py | Bootstrap CI・検出力分析 |
| cumulative_pnl_analysis.py | 累積損益分析 |
| analyze_margin_vb.py | margin と VB の相関分析 |
| verify_bet_engine_params.py | bet_engine パラメータ検証 |

### 9.2 実験レポート

- `keiba-v2/docs/ml-experiments/README.md`: 実験一覧・ROI推移・学び
- 個別レポート: `v5.6_ev_gap_analysis.md`, `v5.5_bootstrap_ci_pruning.md` 等
- `docs/ml-experiments/`: 旧実験レポート（v3.0〜v5.4）

---

## 10. 関連ドキュメント一覧

| ドキュメント | パス | 内容 |
|--------------|------|------|
| モデル・特徴量定義 | keiba-v2/docs/models_and_features.md | 5モデル構成、特徴量一覧、EV計算 |
| ベッティング戦略 | keiba-v2/docs/BETTING_STRATEGY.md | EV計算、Kelly、リスク管理 |
| ML実験レポート | keiba-v2/docs/ml-experiments/README.md | バージョン別ROI・AUC・学び |
| 特徴量戦略 | keiba-v2/docs/feature_engineering_strategy.md | 特徴量設計方針 |
| トレーニング仕様 | keiba-v2/docs/TRAINING_SPEC.md | 訓練データ仕様 |
| データ仕様 | keiba-v2/docs/DATA_SPEC.md | データ形式 |
| ドメインモデル | keiba-v2/docs/DOMAIN_MODEL.md | ドメイン概念 |

---

## 付録: クイックリファレンス

### よく使うコマンド

```powershell
# 予測実行
python -m ml.predict --date 2026-02-22

# モデル訓練
python -m ml.experiment

# bet_engine バックテスト
python -m ml.backtest_bet_engine

# 利用可能モデル一覧
python -m ml.predict --list-versions
```

### 主要設定値

| 項目 | 値 |
|------|-----|
| VALUE_BET_MIN_GAP | 3 |
| デフォルト予算 | 30,000円 |
| win_only 推奨 | gap>=5, margin<=1.2 |
| 訓練期間 | 2020-2024（デフォルト） |
| テスト期間 | 2025-2026（デフォルト） |

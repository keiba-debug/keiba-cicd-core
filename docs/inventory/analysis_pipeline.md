# KeibaCICD 分析パイプライン インベントリ

> 最終更新: 2026-05-16, Session 121
> 対象: `keiba-v2/ml/` 配下 全 98 ファイル (約 51,000 行)
> 目的: `polaris 条件別性能分析` 新規実装に向けた既存資産の全棚卸し
> 関連: WebViewer 側・builders 側のインベントリは別ファイルで作成予定

---

## 1. 全体像（パイプライン図）

```
                   ┌─── horse_history_cache.json (馬走履歴, 36k馬)
                   ├─── jrdb_*_index.json (SED/KYI/KAA/CYB/CHA/KKA/UKC/JOA)
                   ├─── kb_ext_*.json (keibabook拡張: 印/コメント/調教/スピード指数)
                   ├─── pedigree_index/sire_stats_index/race_level_index
                   ├─── pace_index (RPCI/lap33/race_trend)
                   └─── baba CSV (cushion/moistureG)
                                │
                                ▼
            ┌──────────  ml/features/  ──────────┐
            │ base/past/trainer/jockey/         │
            │ running_style/rotation/pace/      │
            │ training/speed/comment/pedigree/  │
            │ baba/track_bias/career/jrdb/      │
            │ closing_race/obstacle/margin_     │
            │ target/slow_start                 │
            └────────────┬───────────────────────┘
                         │ (compute_features_for_race)
                         ▼
       ┌──── ml/experiment.py (3模型: P/W/AR LightGBM) ──┐
       │                                                  │
       │  分岐:                                           │
       │    ml/experiment_obstacle.py (障害2模型 P/W)    │
       │    ml/experiment_closing.py (差し決着レベル予測) │
       │    ml/experiment_unified.py (P+W+AR統合検証)    │
       │    ml/experiment_lambdarank.py (LambdaRank比較) │
       │    ml/experiment_regression.py (着差回帰実験)   │
       │    ml/experiment_performance.py (IDM diff予測) │
       │    ml/experiment_speed_idx.py (Speed Index回帰) │
       │    ml/experiment_deviation_gap.py (偏差値gap)   │
       │                                                  │
       │  Optuna: optuna_tuner.py / optuna_tuner_obstacle│
       │  Preflight: preflight.py                         │
       └────────────┬─────────────────────────────────────┘
                    │ live model + meta + calibrators
                    ▼
            ┌── ml/model_loader.py (ModelBundle統一)──┐
            │  polaris / enif(障害) / eclipse(差し決着)│
            └────────────┬─────────────────────────────┘
                         │
                         ▼
            ┌─── ml/predict.py (リアルタイム1日分推論) ───┐
            │  ml/predict_closing.py (差し決着追記)       │
            │  ml/batch_predict.py (期間一括, データ1回ロード)│
            └────────────┬─────────────────────────────────┘
                         │ predictions.json
                         ▼
                  ml/enrich_novelty.py (novelty後付)
                         │
                         ▼
            ┌──── ml/bet_engine.py (買い目戦略) ─────┐
            │  PRESETS, generate_recommendations,    │
            │  adaptive_kelly, sanrentan_formation   │
            └────────────┬───────────────────────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
  ml/generate_bets.py  ml/vb_refresh.py  ml/win5_pick.py
   (買い目生成)        (実行時オッズ再計算)  (WIN5推奨)
            │            │            │
            ▼            ▼            ▼
                  bets.json / win5_picks.json

                         │
                         ▼ (検証)
       ┌─── ml/backtest_bet_engine.py (live model BT)  ─┐
       │  ml/extend_backtest_cache.py (キャッシュ追記)  │
       │  ml/backtest_vb.py (VB条件グリッドサーチ)      │
       │  ml/simulate_bankroll.py (バンクロール複利)    │
       │  ml/bankroll_simulator.py (モンテカルロ)       │
       │  ml/simulate_multi_leg.py (馬連/ワイド/馬単)   │
       │  ml/simulate_sanrentan*.py (三連単4種)         │
       │  ml/simulate_formation.py (条件型フォーメ)     │
       │  ml/simulate_distortion.py (Harville歪み)      │
       │  ml/simulate_strategy_redesign.py (新プリ)     │
       │  ml/win5_*.py (10本のWIN5戦略シミュ)           │
       │  ml/obstacle_place_wide_backtest.py            │
       └────────────────────────────────────────────────┘
                         │
                         ▼
                  ml/analyze_*.py (24本の分析スクリプト)
                  ml/cumulative_pnl_analysis.py 等
```

---

## 2. カテゴリ別サマリ表

| カテゴリ | 件数 | 主要ファイル | 総行数 |
|---|---:|---|---:|
| A. 学習系 (Experiment + Optuna) | 11 | experiment.py, experiment_obstacle.py, experiment_closing.py, optuna_tuner.py | ~10,200 |
| B. 予測系 (Predict + Loader) | 5 | predict.py, batch_predict.py, predict_closing.py, model_loader.py | ~3,500 |
| C. 馬券生成系 (Bet engine + Refresh) | 5 | bet_engine.py, generate_bets.py, vb_refresh.py, win5_pick.py | ~4,800 |
| D. 分析系 (Analyze*) | 28 | analyze_predictions.py, analyze_polaris_weakness.py, monthly_analysis.py, etc | ~11,800 |
| E. 検証系 (Backtest + Simulate) | 18 | backtest_bet_engine.py, simulate_*.py, win5_*sim.py, bankroll_*.py | ~13,500 |
| F. 特徴量モジュール (ml/features/) | 19 | base, past, trainer, jockey, pace, training, baba, jrdb, etc | ~5,800 |
| G. その他 (utility / IO) | 12 | feature_snapshot, model管理, settle_purchases, etc | ~2,400 |
| **合計** | **98** | | **~51,000** |

注: `experiment_v3.py` は `experiment.py` への薄いリダイレクトのみ (6 行)。
注: `ci_power_analysis.py` は分析系に分類。

---

## 3. 学習系 (A)

### 3.1 ml/experiment.py — メイン3モデル学習 (3,572 行)
- **目的**: LightGBM 3モデル(P/W/AR) 学習評価パイプライン。 polaris の本体。
- **入力**: `horse_history_cache.json`, `race_*.json`, `kb_ext_*.json`, JRDB各種インデックス, `pedigree_index/sire_stats_index/race_level_index/pace_index/baba`, `mykeibadb` 確定オッズ
- **出力**: `models/polaris/live/{model_p,model_w,model_ar}.txt`, `calibrators.pkl`, `meta.json`, `versions/v{N}/`, `ml_experiment_v3_result.json`
- **カバー範囲**:
  - LightGBM binary (P: is_top3, W: is_win) + Huber regression (AR: time_behind_winner)
  - Train/Val/Test 期間分割、Walk-Forward 風
  - Bayesian time-weighting (`_compute_time_weights`)
  - Isotonic calibration (`calibrate_isotonic`)
  - 評価: Brier (`calc_brier_score`)、ECE (`calc_ece`)、AUC、ROI解析(`calc_roi_analysis`)
  - VB バックテスト (`calc_value_bet_analysis`, `calc_vb_bootstrap_ci`)、bootstrap CI
  - グリッド集計: `calc_gap_margin_grid`, `calc_gap_ard_grid`
  - 軸別: 芝/ダート分割 (`run_track_split_experiment`)
- **主要関数**: `load_data`, `build_dataset`, `compute_features_for_race`, `train_model`, `train_regression_model`, `build_pit_personnel_timeline`, `build_pit_sire_timeline`, `parse_period_range`, `main`
- **連携先**: `predict.py`、`batch_predict.py`、`optuna_tuner.py`、`experiment_*.py` 全派生、`monthly_analysis.py`、`backtest_bet_engine.py` などが import
- **最終更新気配**: **現役** (polaris-2.1b 系の本体)
- 主要参照: `c:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\ml\experiment.py:200-294` (特徴量定義), `:924` (load_data), `:1342` (build_dataset), `:1490-1535` (キャリブレーション/評価)

### 3.2 ml/experiment_obstacle.py — 障害レース専用 (748 行)
- **目的**: 障害レース用 P/W 2モデル(`enif`)学習。市場系除外で VALUE 戦略のみ
- **入力**: experiment.py の load_data + 障害特徴量
- **出力**: `models/enif/live/{model_p,model_w}.txt`, `calibrators_obstacle.pkl`, `meta.json`
- **カバー範囲**:
  - 障害固有: 経験・難易度(10-53段階)・コース属性・3軸分類(器用/平地力/飛越/総合)
  - ベイズ平滑化済み騎手/調教師障害成績(PIT-safe)
  - 平地IDM・ハイレベル経験・降格転戦・着差(time_behind_winner)
- **主要関数**: `build_obstacle_dataset`, `main`
- **連携先**: `predict.py`(`predict_obstacle_race`)、`optuna_tuner_obstacle.py`、`analyze_obstacle_multi.py`、`obstacle_place_wide_backtest.py`
- **最終更新気配**: **現役** (v2.5b 着差特徴量導入後)

### 3.3 ml/experiment_closing.py — 差し決着レベル予測 (590 行)
- **目的**: 「3着以内に差し/追込が2頭以上」を予測するレースレベル分類 (1行=1レース)
- **入力**: experiment.py の load_data + `CourseClosingTimeline`
- **出力**: `models/eclipse/live/model_closing.txt`, `calibrators.pkl`, `meta.json`
- **カバー範囲**:
  - レースレベル binary classification、scale_pos_weight=8.5(不均衡対応)
  - 7グループ × ~30特徴量(コース特性/メンバー脚質分布/ペース予測/コース歴史統計/馬場/距離延長/ラップ)
- **主要関数**: `train_closing_model`, `build_course_timeline`, `build_closing_dataset`, `calc_subset_analysis`
- **連携先**: `predict_closing.py`(本番)、`backtest_bet_engine.py`
- **最終更新気配**: **現役** (Session 116で eclipse 化、predict_closing.py 統合)

### 3.4 ml/experiment_lambdarank.py — LambdaRank比較実験 (582 行)
- **目的**: binary classification vs LambdaRank(レース内ranking) の比較検証
- **入力**: experiment.py の build_dataset
- **出力**: 比較レポート (`ml_lambdarank_result.json`)
- **カバー範囲**: NDCG@1/@3/@5、Top1勝率、ECE、VB ROI、IsotonicでP変換
- **主要関数**: `prepare_ranking_data`, `train_lambdarank`, `calibrate_scores`, `compute_ndcg`, `evaluate_vb_strategy`
- **連携先**: 単独実験
- **最終更新気配**: **実験的** (実装済みだが production には未採用)

### 3.5 ml/experiment_regression.py — 着差回帰実験 (675 行)
- **目的**: AR モデル(Huber 回帰)単体での性能検証 + 確率変換比較
- **入力**: build_dataset + `margin_target.add_margin_target_to_df`
- **出力**: `ml_regression_result.json`
- **カバー範囲**: MAE/RMSE/R²、NDCG、Top-N、Isotonic で回帰スコア→ P(win)/P(top3)
- **主要関数**: `train_regression_model`, `compute_ndcg`, `calc_regression_hit_analysis`, `calc_regression_roi`, `derive_probabilities`
- **連携先**: 結果は experiment.py の本流 AR に統合済み
- **最終更新気配**: **レガシー寄り**(本流 AR と機能重複)

### 3.6 ml/experiment_unified.py — P+W+AR統合検証 (611 行)
- **目的**: Margin回帰 / LambdaRank / Finish位置回帰 の3アプローチを統合モデル候補として比較
- **出力**: 比較レポート
- **カバー範囲**: Top1 Win率、Top1 ROI、Brier/ECE、VB再現率
- **主要関数**: `make_lambdarank_groups`, `make_relevance_labels`, `calibrate_scores`, `compute_ece`, `evaluate_model`
- **最終更新気配**: **実験的**

### 3.7 ml/experiment_speed_idx.py — Speed Index 回帰実験 (486 行)
- **目的**: TARGET の SP file スピード指数を回帰ターゲットに使うモデル
- **入力**: SP files + 馬場差/ペース補正
- **主要関数**: `load_speed_index`, `load_baba_data`, `load_pace_data`, `race_id_to_rx_code`, `add_speed_idx_target`
- **最終更新気配**: **実験的**(production 非採用)

### 3.8 ml/experiment_deviation_gap.py — 偏差値gap比較 (391 行)
- **目的**: 現行 `gap = odds_rank - rank_p` vs 偏差値ベース `z_model - z_market` の品質比較
- **主要関数**: `compute_deviation_gap`, `vb_analysis`
- **連携先**: 結果は `bet_engine.py` の dev_gap 系 VB Floor に取り込み済み
- **最終更新気配**: **実験完了** (採用済み)

### 3.9 ml/experiment_performance.py — IDM diff 4-class分類 (646 行)
- **目的**: 「前走比 IDM 差分」を 4 クラス(大幅上昇/上昇/平行/下降)で分類するモデル
- **カバー範囲**: クラス閾値 +10/+4/-4/-5、multiclass LightGBM
- **主要関数**: `idm_diff_to_label_4`, `idm_diff_to_label_3`, `add_idm_diff_target`, `train_multiclass_model`, `analyze_practical_value`, `augment_career_features`
- **連携先**: `analyze_idm_diff.py` でカテゴリ閾値を決定 → ここで学習
- **最終更新気配**: **実験的**(`model_perf.txt` 系、live 採用は未)

### 3.10 ml/optuna_tuner.py — polaris ハイパラ + 特徴量グループ最適化 (455 行)
- **目的**: P/W/AR モデル別に LightGBM ハイパラ + 特徴量グループ ON/OFF を Optuna 最適化
- **入力**: experiment.py のデータ + `FEATURE_GROUPS`
- **出力**: `data3/ml/optuna/best_params_p.json` 等 + SQLite study DB (中断再開可)
- **主要関数**: `suggest_params`, `select_features`, `create_objective`, `run_optimization`, `save_combined_results`
- **連携先**: experiment.py が `--use-optuna` で読み込む
- **最終更新気配**: **現役** (P:103t / W:100t / AR:80t で適用済み)

### 3.11 ml/optuna_tuner_obstacle.py — 障害版 Optuna (398 行)
- **目的**: 障害 P/W モデルの ハイパラ最適化
- **出力**: `best_params_obstacle_p.json`, `best_params_obstacle_w.json`
- **最終更新気配**: **現役**

---

## 4. 予測系 (B)

### 4.1 ml/predict.py — リアルタイム1日分推論 (2,049 行)
- **目的**: 1日分(または指定race_id)の predictions.json を生成。Polaris + Enif の両方を呼ぶ
- **入力**: race_*.json, kb_ext_*.json, masters, JRDB index, mykeibadb 事前オッズ, live model
- **出力**: `races/YYYY/MM/DD/predictions.json` (entries に rank_p/rank_w/ar_deviation/win_ev/place_ev/vb_gap/dev_gap/market_signal/novelty_* 等)
- **カバー範囲**: 平地+障害、isotonic calibration、market_signal判定、novelty filter、VB floor
- **主要関数**: `compute_market_signal`, `load_model_and_meta`, `load_obstacle_model`, `load_master_data`, `load_keibabook_ext`, `get_keibabook_features`, `predict_race`, `predict_obstacle_race`, `get_races_for_date`, `get_latest_date`, `main`
- **連携先**: `batch_predict.py`、`predict_closing.py`、`vb_refresh.py`、`generate_bets.py` が呼ぶ
- **最終更新気配**: **現役** (Session 116 で model_loader 経由化)
- 参照: `c:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\ml\predict.py:71-107` (market_signal判定), `:787-1535` (predict_race の本体)

### 4.2 ml/predict_closing.py — 差し決着追記推論 (285 行)
- **目的**: eclipse モデルで closing_race_proba をレースレベル追記
- **入力**: predictions.json + experiment_closing データセット
- **出力**: predictions.json の races[*].closing_race_proba 追記
- **主要関数**: `load_closing_model`, `predict_closing_for_date`, `main`
- **最終更新気配**: **現役**

### 4.3 ml/batch_predict.py — 期間一括推論 (413 行)
- **目的**: from-to 期間を 1 回ロードで一括予測。バックテストデータ整備用
- **入力**: date_index で期間内全日付走査
- **出力**: 各日の predictions.json (オプション: with-bets で bets.json も)
- **主要関数**: `get_all_dates`, `predict_date`, `main`
- **連携先**: `extend_backtest_cache.py` が結果を取り込む
- **最終更新気配**: **現役** (Session 116 で 24日714レース動作確認)

### 4.4 ml/model_loader.py — 統一モデルローダー (464 行)
- **目的**: `model_registry.json` を唯一の真実として ModelBundle を返す。polaris/enif/eclipse 全対応
- **入力**: `data3/ml/model_registry.json`, `models/{name}/live/`, `models/{name}/versions/v{N}/`
- **出力**: `ModelBundle` dataclass (`model_p`/`model_w`/`model_ar`/`calibrators`/`meta`/`source`)
- **主要関数**: `load_model`, `load_model_safe`, `get_active_version`, `list_models`, `list_versions`, `register_version`, `set_active_version`, `invalidate_cache`
- **連携先**: predict.py / batch_predict.py / predict_closing.py / experiment.py 各所
- **最終更新気配**: **現役** (Session 116 新規)
- 参照: `c:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\ml\model_loader.py:39-90` (ModelBundle)

### 4.5 ml/preflight.py — 学習前スモーク (225 行)
- **目的**: 新特徴量追加後、experiment.py 本走前に1分以内で
  - 新特徴量が dataframe に乗ってるか
  - 分散ゼロでないか
  - Optuna 済み feature_list に含まれてるか
  を検証
- **主要関数**: `find_latest_predictable_date`, `diff_against_active_model`, `load_optuna_features`, `smoke_test_features`, `main`
- **最終更新気配**: **現役** (Session 119 新規)

---

## 5. 馬券生成系 (C)

### 5.1 ml/bet_engine.py — 買い目戦略エンジン (2,430 行) [核]
- **目的**: PRESET 駆動の買い目推奨を一元生成。 predict + experiment 両方が利用
- **入力**: predictions.json 由来の entries (calibrated proba/ARd/win_ev/odds/gap 等)
- **出力**: `List[BetRecommendation]` (umaban/bet_type/amount/expected_value/strategy_name 等)
- **カバー範囲**:
  - VB Floor 定数(EV>=1.0, ARd>=50, ARd-VB ARd>=65 etc, novelty filter)
  - 単勝/複勝/単複/ワイド(激戦/障害)/馬連/馬単(障害)/三連単フォーメーション
  - `BetStrategyParams`(プリセット定義), `PRESETS` (tansho_ippon ほか旧 standard/wide/aggressive)
  - Adaptive: `AdaptiveRule`, `RaceContext`, `compute_race_context`
  - Kelly: `calc_kelly_fraction`, `apply_kelly_sizing`, `apply_adaptive_kelly`
  - 配分: `apply_cross_allocation`, `apply_budget`, `rescale_budget`
  - 評価: `compute_vb_score`, `detect_danger`, `calc_bet_engine_roi`
- **主要関数**: `passes_novelty_filter`, `load_grade_offsets`, `get_grade_key`, `evaluate_win`, `evaluate_place`, `generate_recommendations`, `apply_win_per_race_limit`, `df_to_race_predictions`, `recommendations_summary`, `generate_adaptive_recommendations`
- **連携先**: 全て(predict.py、generate_bets.py、vb_refresh.py、backtest_bet_engine.py、simulate_*.py、win5_pick.py、analyze_allocation.py 等多数)
- **最終更新気配**: **現役・最重要** (web UI bet-logic.ts と双方向同期)
- 参照: `c:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\ml\bet_engine.py:48-83` (VB Floor 定数), `:147-501` (PRESETS), `:852-1440` (generate_recommendations)

### 5.2 ml/generate_bets.py — 買い目独立生成 (433 行)
- **目的**: predictions.json → bets.json に分離。戦略変更時の推論やり直し不要化
- **入力**: predictions.json
- **出力**: `races/YYYY/MM/DD/bets.json`
- **主要関数**: `load_predictions`, `apply_bet_engine`, `strip_betting_fields`, `main`
- **連携先**: `vb_refresh.py` が利用、web UI が読む
- **最終更新気配**: **現役**

### 5.3 ml/vb_refresh.py — 実行時オッズ再計算 (284 行)
- **目的**: ML 推論結果を保持しつつ最新オッズで VB/EV/買い目を再計算
- **入力**: predictions.json + mykeibadb 直前オッズ
- **出力**: predictions.json 更新 + bets.json 再生成
- **主要関数**: `refresh_race_vb`, `main`
- **連携先**: Windows Task Scheduler で定期実行(`vb_refresh.bat`)
- **最終更新気配**: **現役**

### 5.4 ml/win5_pick.py — WIN5推奨ピッカー (476 行)
- **目的**: WIN5 対象 5 レースに対しプラン別の推奨馬を出力(combo_sim と戦略同一)
- **入力**: predictions.json
- **出力**: win5_picks.json (Plan E/N/CG3/A/C)
- **カバー範囲**: rank_w Top2 固定 / 頭数適応 / 自信度可変 / WP合算
- **主要関数**: `rw_top`, `wps_sorted`, `kb_mark_top`, `idm_top`, `_conf_gap`, `plan_e_select`, `plan_n_select`, `plan_cg3_select`, `plan_a_select`, `plan_c_select`, `get_win5_race_ids`, `extract_pick_info`, `print_picks`, `save_json`, `main`
- **連携先**: web UI(/win5)
- **最終更新気配**: **現役** (Session 117 polaris 2.1b 採用)

### 5.5 ml/win5_variable.py — 可変点数シミュ (634 行)
- **目的**: 各レースの rank_w 上位の数値で 1-5 頭を可変選択。条件外週は購入なし
- **主要クラス**: `Win5Race`, `Win5Week`, `RaceEntry`, `RacePrediction`
- **主要関数**: `load_win5_schedule`, `load_backtest_cache`, `get_top_entries`, `variable_select`, `build_rules`, `simulate_week`, `run_simulation`, `print_report`, `main`
- **最終更新気配**: **現役** (E系から派生した実験的シミュ)

---

## 6. 分析系 (D) — 最大セクション

### 6.1 ml/analyze_predictions.py — 集計レポ (518 行)
- **目的**: predictions.json × race_*.json × mykeibadb 確定オッズ で VB 馬・購入プランの実成績集計
- **入力**: predictions.json (全期間)、race_*.json、`batch_get_place_odds`
- **出力**: 標準出力テーブル
- **カバー範囲**: ValueBet 馬の VB ROI、各プリセットの的中/ROI、月別、自信度別
- **主要関数**: `load_race_results`, `load_confirmed_place_odds`, `fmt_yen`, `analyze_predictions`
- **最終更新気配**: **現役**

### 6.2 ml/analyze_betting_strategy.py — 連敗+配分戦略 (961 行)
- **目的**: 連敗ストリーク分析 + 単複配分比較 + 自信度別配分効果検証
- **入力**: predictions.json全期間 + 確定複勝オッズ
- **カバー範囲**:
  - 連敗ストリーク (最大連敗、95%分位連敗)
  - 単単100/単複70-30/単複50-50/複勝のみ 等の比較
  - 自信度ティア(strong/medium/weak)別配分
- **主要関数**: `load_race_results`, `load_confirmed_place_odds`, `collect_bet_timeline`, `analyze_streaks`, `simulate_allocation`, `simulate_strength_allocation`, `main`
- **最終更新気配**: **現役** (Session 90付近の連敗対策で使用)

### 6.3 ml/analyze_polaris_weakness.py — polaris 弱点抽出 (500 行) [本タスクの最良の出発点]
- **目的**: polaris(v7.9 baseモデル)が苦手なパターンを特定。 Stars/Nebula 系の設計根拠
- **入力**: `backtest_cache.json`
- **出力**: 標準出力 + マークダウン形式
- **カバー範囲**:
  - 市場相関分析(rank_p vs odds_rank 相関、Top1/Top3 一致率)
  - 大穴検出率(odds>=10、>=20 で polaris が拾えてるか)
  - オッズ帯別キャリブレーション
  - 条件別弱点(track_type/grade/age_class/num_runners 別 ROI/Brier)
  - 偽陽性パターン(rank_p<=3 だが finish>=4 のケース)
  - VB gap 効果、closing_strength 効果
- **主要関数**: `load_backtest_flat`, `analyze_market_correlation`, `analyze_upset_detection`, `analyze_odds_band_calibration`, `analyze_condition_weakness`, `analyze_false_positives`, `analyze_roi_comparison`, `analyze_ev_effectiveness`, `analyze_vb_gap_value`, `analyze_closing_strength_impact`, `summarize_weaknesses`, `main`
- **最終更新気配**: **現役** (Session 114-115 で Stars/Nebula 設計時に作成)
- **★ 注**: 本タスクで最も流用しやすいスクリプト。 `load_backtest_flat` がそのまま使える

### 6.4 ml/monthly_analysis.py — 月別実績分析 (395 行) [流用候補★]
- **目的**: v5.5 live model で 2025/01-2026/02 月別 ROI・条件別成績・当たり馬分布
- **入力**: experiment.py の load_data + 保存済み v5.5 model
- **出力**: 月別 ROI テーブル + bootstrap CI
- **カバー範囲**: 月別 ROI、`filter_win_only`/`filter_selective` 系の戦略フィルタ
- **主要関数**: `load_v55_models`, `predict_on_df`, `bootstrap_roi_ci`, `filter_win_only`, `filter_selective`, `calc_roi`, `main`
- **連携先**: `ability_turf_dirt_analysis.py`, `cumulative_pnl_analysis.py`, `market_divergence_analysis.py` が import
- **最終更新気配**: **半レガシー** (v5.5 hardcode、 polaris 2.1b で再利用には改修必要)

### 6.5 ml/cumulative_pnl_analysis.py — 累積P&L + 連敗 (357 行)
- **目的**: 3条件の累積 P&L チャート + 連敗統計
- **入力**: monthly_analysis の data
- **出力**: matplotlib (Agg) チャート PNG
- **主要関数**: `load_v55_models`, `predict_on_df`, `filter_bets`, `calc_pnl_series`, `calc_monthly_pnl`, `calc_max_drawdown`, `calc_losing_streaks`, `calc_consecutive_loss_months`, `main`
- **最終更新気配**: **半レガシー**

### 6.6 ml/market_divergence_analysis.py — 市場乖離スコア (239 行)
- **目的**: margin × odds の市場乖離スコアで的中馬の弁別性を検証
- **候補スコア**: `margin/odds`, `gap × 1/odds`, `gap × margin/odds`
- **連携先**: monthly_analysis から import
- **最終更新気配**: **半レガシー**

### 6.7 ml/ability_turf_dirt_analysis.py — 芝/ダ能力スコア (217 行)
- **目的**: ability_score(=-pred_margin)の芝/ダート別分布・ROI・最適閾値
- **連携先**: monthly_analysis から import
- **最終更新気配**: **半レガシー**(v5.5依存)

### 6.8 ml/analyze_baba_features.py — 馬場分類 (469 行)
- **目的**: クッション値+含水率で馬場「性格」分類して好走パターン分析
- **入力**: `data3/analysis/baba/cushion*.csv` + `moistureG_*.csv` + race_*.json
- **カバー範囲**: turf/dirt × 硬さ × 湿度 9分類、track_condition との追加情報量
- **主要関数**: `read_baba_csv`, `parse_csv_id`, `load_baba_data`, `load_race_entries`, `classify_moisture`, `analyze`, `analyze_waku`, `analyze_condition_cross`, `analyze_venue_distance_cross`, `analyze_position_gain`, `analyze_waku_style_cross`, `analyze_kaisai_progression`, `analyze_first_corner_distance`
- **最終更新気配**: **現役**

### 6.9 ml/analyze_baba_report.py — 馬場会場別レポ (1,087 行)
- **目的**: 会場 × 含水率/クッション × 脚質の相関分析。マップ生成
- **カバー範囲**: 10会場別、ダート不良→前/内、芝硬い→外差し 等
- **主要関数**: `read_csv`, `parse_csv_id`, `load_all_baba`, `load_race_results`, `classify_turf_baba`, `classify_dirt_baba`, `analyze`
- **連携先**: 結果は `features/baba_features.py` 設計に反映
- **最終更新気配**: **現役**

### 6.10 ml/analyze_market_signal.py — 市場シグナル分析 (315 行)
- **目的**: market_signal × VB状態/rank_p/ARd/月別 のクロス集計(ValueBet再設計 Phase2)
- **入力**: predictions.json (全期間)
- **主要関数**: `collect_data`, `calc_stats`, `main`
- **最終更新気配**: **現役** (Session 110 の 1.2/0.5 倍率最適化に使用)

### 6.11 ml/analyze_base_odds.py — JRDB基準オッズ検証 (364 行)
- **目的**: JRDB KYI base_odds vs 実オッズ vs モデル予測のバックテスト
- **入力**: `jrdb_kyi_index.json` + race_*.json + predictions
- **カバー範囲**: smart money 仮説、モデル推奨馬のオッズ帯別 ROI
- **主要関数**: `load_kyi_index`, `load_races_with_results`, `load_predictions_index`, `analyze`
- **最終更新気配**: **現役** (market_signal の根拠)

### 6.12 ml/analyze_base_odds_v2.py — 基準オッズクロス分析v2 (509 行)
- **目的**: ARd × オッズ変動 → 複勝率向上の可能性。 race_confidence × オッズ変動
- **主要関数**: `load_all_data`, `build_records`, `print_table`, `calc_stats`, `analyze_cross`
- **最終更新気配**: **現役**

### 6.13 ml/analyze_idm_diff.py — IDM差分分布 (243 行)
- **目的**: 前走比 IDM 差分(当該レース - 前走)の分布分析
- **入力**: `horse_history_cache.json` + `jrdb_sed_index.json`
- **連携先**: 結果が `experiment_performance.py` のカテゴリ閾値に反映
- **最終更新気配**: **実験的**

### 6.14 ml/analyze_margin_vb.py — predicted margin × VB (234 行)
- **目的**: VB 候補内の predicted margin 分布 × 的中率・ROI で margin filter 最適閾値探索
- **主要関数**: `roi_by_bins`
- **連携先**: 結果は `bet_engine.py` の `win_max_predicted_margin` に反映
- **最終更新気配**: **実験完了** (採用済み)

### 6.15 ml/analyze_novelty.py — novelty 帯別精度 (256 行)
- **目的**: enrich_novelty 後の predictions.json で novelty_score 帯別の VB ROI/単勝ROI/Brier
- **入力**: predictions.json (novelty_*補完済み)
- **カバー範囲**: novelty 帯ごとの単勝 ROI、複勝率、Brier、VB 候補の novelty 分布
- **主要関数**: `iter_date_dirs`, `build_results`, `fmt_pct`, `fmt_roi`, `main`
- **連携先**: 結果が `bet_engine.NOVELTY_VB_MAX_SCORE` 等に反映
- **最終更新気配**: **現役** (Session 119)

### 6.16 ml/analyze_obstacle_multi.py — 障害多券種 (298 行)
- **目的**: 障害レースの単勝/馬単/馬連/ワイドの券種別 ROI バックテスト
- **入力**: predictions.json (障害)
- **主要関数**: `load_obstacle_predictions`, `analyze`
- **最終更新気配**: **現役**

### 6.17 ml/analyze_sanrentan_distortion.py — 三連単歪み (974 行)
- **目的**: O6(odds6_sanrentan)実オッズ vs Harville 推定の歪みパターン発見
- **入力**: mykeibadb `odds6_sanrentan` + backtest_cache
- **カバー範囲**:
  - H1: Harville は穴薄を過小評価
  - H2: 1着人気→2着穴の馬単型が過大
  - H3: モデルEV>1 三連単 vs フォーメ戦略
  - H4: ConfGap<0.10 + FavOdds 3-4 フィルター
  - H5: 歪み率大組み合わせに的中集中
- **主要関数**: `load_o6_odds`, `load_sanrentan_payouts`, `harville_prob`, `load_predictions_with_results`, `analyze`, `main`
- **連携先**: `simulate_distortion.py`、`simulate_sanrentan_ev.py`、`simulate_sanrentan_ev_filtered.py`
- **最終更新気配**: **現役** (Session 103-105 三連単フォーメ戦略の根拠)

### 6.18 ml/analyze_shap.py — SHAP 比較 (219 行)
- **目的**: Model P vs Model AR の特徴量寄与比較(gain-based importance)
- **入力**: `model_p.txt`, `model_ar.txt`, meta
- **主要関数**: `load_models_and_meta`, `compare_global_importance`, `shap_analysis_with_backtest`, `analyze_split_patterns`, `main`
- **最終更新気配**: **半レガシー** (旧 ML_DIR hardcode、ModelLoader化未)

### 6.19 ml/analyze_divergence.py — V×AR 乖離 (204 行)
- **目的**: V(P確率)1位なのに ARd 下位、 ARd 1位なのに V 下位のケース別勝率比較
- **入力**: backtest_cache
- **主要関数**: `load_cache`, `analyze_divergence`, `print_stats`, `print_examples`, `analyze_feature_correlation`, `analyze_odds_band`, `main`
- **最終更新気配**: **現役** (market_signal "鉄板"/"軸向き" の根拠)

### 6.20 ml/analyze_allocation.py — 配分戦略比較 (283 行)
- **目的**: bet_engine の選定後に 傾斜 vs 均等 × クロス vs 均等単複の金額配分比較
- **入力**: backtest_cache + PRESETS
- **主要関数**: `load_cache`, `cache_to_predictions`, `calc_roi`, `apply_allocation`, `main`
- **最終更新気配**: **現役**

### 6.21 ml/analyze_simple_strategy.py — シンプル戦略 (605 行)
- **目的**: rank_w=1 単勝、 ワイド戦略等のシンプル戦略のROI検証
- **入力**: backtest_cache
- **主要関数**: `load_cache`, `calc_roi`, `fmt_roi`, `main`
- **最終更新気配**: **現役**

### 6.22 ml/analyze_teppan_deep.py — 鉄板深掘り (357 行)
- **目的**: 「鉄板馬」(market_signal=鉄板)のオッズ帯・人気・複合フィルター別成績
- **入力**: predictions.json + haraimodoshi DB
- **主要関数**: `get_wide_map`, `get_umaren_map`, `main`
- **最終更新気配**: **現役**

### 6.23 ml/analyze_teppan_extra.py — 鉄板追加 (319 行)
- **目的**: analyze_teppan_deep の派生分析(追加軸)
- **最終更新気配**: **現役**

### 6.24 ml/analyze_teppan_wide_umaren.py — 鉄板軸ワイド/馬連 (557 行)
- **目的**: market_signal=鉄板 馬を軸にしたワイド・馬連バックテスト
- **入力**: predictions + mykeibadb haraimodoshi
- **主要関数**: `load_haraimodoshi`, `parse_wide_payouts`, `parse_umaren_payouts`, `load_finish_positions`, `main`
- **最終更新気配**: **現役**

### 6.25 ml/analyze_wide_strategy.py — 激戦ワイドv1 (504 行)
- **目的**: ワイド hit rate >= 50% with 1-3 tickets の条件探索
- **入力**: backtest_cache
- **主要関数**: `load_data`, `get_entry_count_bin`, `get_confidence_bin`, `get_ard_gap_bin`, `check_wide_hit`, `analyze`
- **最終更新気配**: **現役** (激戦ワイドの根拠)

### 6.26 ml/analyze_wide_strategy_v2.py — 激戦ワイドv2 (344 行)
- **目的**: v1 のベスト発見の深掘り(pair_agree=3、 P top3 combo with <=10 entries 等)
- **主要関数**: `compute_race_features`, `print_table`, `main`
- **最終更新気配**: **現役**

### 6.27 ml/analyze_wide_v3.py — 激戦ワイドROI改善 (615 行)
- **目的**: 419 件 ROI 89% 赤字 → オッズフロア・頭数制限・ARd/P% 条件追加
- **主要関数**: `check_umaren_hit`, `get_wide_odds_from_db`, `get_umaren_odds_from_db`, `estimate_wide_odds`, `compute_race_data`, `print_row`
- **最終更新気配**: **現役** (オッズフロア 2.0 採用済み)

### 6.28 ml/analyze_win5_topn.py — WIN5 winner rank (301 行)
- **目的**: WIN5 勝ち馬が rank_w の Top N に何回入るか
- **入力**: backtest_cache
- **最終更新気配**: **現役**

### 6.29 ml/ci_power_analysis.py — CI 検出力 (253 行)
- **目的**: Bootstrap CI 幅と件数の関係。何件あれば許容範囲か理論推定
- **入力**: experiment 結果 JSON
- **主要関数**: `load_session44_data`, `extrapolate_ci`, `required_n_for_ci_width`, `required_n_for_significance`
- **最終更新気配**: **現役** (戦略検証時の CI チェック)

### 6.30 ml/compare_ard_tiers.py — ARd ティア比較 (296 行)
- **目的**: bet_engine PRESET の段階gap現行 vs 提案を backtest_cache で即比較
- **入力**: backtest_cache + PRESETS
- **最終更新気配**: **現役**

### 6.31 ml/investigate_ard_value.py — ARd 価値調査 (386 行)
- **目的**: ARd 高いのに rank_v が低い馬の漏れ調査。 ARd-VB ルート設計の根拠
- **入力**: backtest_cache
- **連携先**: bet_engine `VB_FLOOR_ARD_VB_*` に反映
- **最終更新気配**: **現役**

### 6.32 ml/compare_models.py — モデル比較レポ (196 行)
- **目的**: 2 polaris バージョンを並べて AUC・特徴量数・importance Top 差分
- **入力**: `models/polaris/{live,versions/v*}/`
- **主要関数**: `load_model_with_importance`, `fmt_top_diff`, `main`
- **最終更新気配**: **現役** (Session 119)

### 6.33 ml/verify_bet_engine_params.py — VB engine 検証 (564 行)
- **目的**: bet-engine.py 実装パラメータ確定の 3 検証(キャリブ品質/calibrated EV分布/統合C ROI)
- **最終更新気配**: **半レガシー**

---

### 6.X 「指標 × ファイル」マトリクス

| 指標 / ファイル | AUC | Brier | ECE | ROI単 | ROI複 | ROIワイド | ROI馬連 | ROI三連単 | Sharpe | 連敗 | MaxDD | キャリブ曲線 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| experiment.py | ✅ | ✅ | ✅ | ✅ | ✅ | - | - | - | - | - | - | ✅ |
| experiment_obstacle.py | ✅ | ✅ | - | ✅ | ✅ | ✅ | ✅ | - | - | - | - | - |
| experiment_closing.py | ✅ | ✅ | - | - | - | - | - | - | - | - | - | - |
| experiment_lambdarank.py | (NDCG) | - | ✅ | ✅ | - | - | - | - | - | - | - | - |
| experiment_regression.py | - | - | - | ✅ | ✅ | - | - | - | - | - | - | - |
| analyze_predictions.py | - | - | - | ✅ | ✅ | - | - | - | - | - | - | - |
| analyze_betting_strategy.py | - | - | - | ✅ | ✅ | - | - | - | - | ✅ | - | - |
| analyze_polaris_weakness.py | - | (帯別) | - | ✅ | - | - | - | - | - | - | - | ✅ |
| monthly_analysis.py | - | - | - | ✅ | - | - | - | - | - | - | - | - |
| cumulative_pnl_analysis.py | - | - | - | - | - | - | - | - | - | ✅ | ✅ | - |
| backtest_bet_engine.py | - | - | - | ✅ | ✅ | ✅ | ✅ | ✅ | - | - | - | - |
| backtest_vb.py | - | - | - | ✅ | ✅ | - | - | - | - | - | - | - |
| simulate_bankroll.py | - | - | - | ✅ | ✅ | ✅ | ✅ | - | (Kelly) | ✅ | ✅ | - |
| bankroll_simulator.py | - | - | - | ✅ | - | - | - | - | - | ✅ | ✅ | - |
| analyze_market_signal.py | - | - | - | ✅ | ✅ | - | - | - | - | - | - | - |
| analyze_wide_v3.py | - | - | - | - | - | ✅ | ✅ | - | - | - | - | - |
| analyze_sanrentan_distortion.py | - | - | - | - | - | - | - | ✅ | - | - | - | - |
| analyze_novelty.py | - | (帯別) | - | ✅ | ✅ | - | - | - | - | - | - | - |
| analyze_divergence.py | - | - | - | ✅ | ✅ | - | - | - | - | - | - | - |
| ci_power_analysis.py | - | - | - | (CI) | - | - | - | - | - | - | - | - |

注: Sharpe比は production には未導入。 simulate_bankroll が Kelly fraction を扱う程度。

### 6.Y 「セグメント軸 × ファイル」マトリクス

| 軸 / ファイル | 馬場 | 距離帯 | グレード | 頭数 | 騎手 | 調教師 | 会場 | 月別 | 年齢区分 | クラス | 馬場状態 | ハンデ戦 | 締切前/直前 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| experiment.py | ✅(track_split) | - | (offset) | - | - | - | - | - | - | - | - | - | - |
| analyze_polaris_weakness.py | ✅ | (odds_band) | ✅ | ✅ | - | - | - | - | ✅ | ✅ | - | - | - |
| analyze_baba_features.py | ✅ | ✅ | - | - | - | - | ✅ | - | - | - | ✅ | - | - |
| analyze_baba_report.py | ✅ | ✅ | - | - | - | - | ✅ | - | - | - | ✅ | - | - |
| ability_turf_dirt_analysis.py | ✅ | - | - | - | - | - | - | - | - | - | - | - | - |
| monthly_analysis.py | - | - | - | - | - | - | - | ✅ | - | - | - | - | - |
| analyze_market_signal.py | - | - | - | - | - | - | - | ✅ | - | - | - | - | - |
| analyze_base_odds.py | - | - | - | - | - | - | - | - | - | - | - | - | (smart money) |
| analyze_wide_strategy.py | - | - | - | ✅ | - | - | - | - | - | - | - | - | - |
| analyze_wide_v3.py | - | - | - | ✅ | - | - | - | - | - | - | - | - | - |
| analyze_obstacle_multi.py | (障害) | ✅(難度) | - | - | ✅ | ✅ | ✅ | - | - | - | - | - | - |
| analyze_novelty.py | (novelty軸) | - | - | - | - | - | - | - | - | - | - | - | - |
| win5_adaptive_wps.py | - | - | - | ✅ | - | - | - | - | - | - | - | ✅ | - |
| win5_simulator.py | - | - | - | ✅ | - | - | - | - | - | - | - | (handicap) | - |

**主要な空白 (本タスクで補完すべき)**:
- 騎手/調教師/会場/距離帯/月別/ハンデ戦 を一つの polaris 条件別分析で網羅したものは存在しない
- 既存の analyze_polaris_weakness が最も近いが 馬場×グレード×頭数×年齢区分 までで、騎手・調教師・距離帯・月別・会場・直前/締切前 は未カバー
- ハンデ戦判定は win5_adaptive_wps.py 内のみで本格的な分析無し

---

## 7. 検証系 (E)

### 7.1 ml/backtest_bet_engine.py — bet_engine BT (1,239 行)
- **目的**: live model + bet_engine の各 PRESET でテストデータ実 ROI
- **入力**: experiment.py の build_dataset + live model
- **出力**: PRESET別 ROI、bootstrap CI
- **主要関数**: `compute_closing_probas`, `main`
- **最終更新気配**: **現役**

### 7.2 ml/extend_backtest_cache.py — BT キャッシュ追記 (214 行)
- **目的**: predictions.json + race_*.json から backtest_cache 形式に追記
- **出力**: `data3/ml/backtest_cache.json`
- **最終更新気配**: **現役**

### 7.3 ml/backtest_vb.py — VB 条件グリッド (547 行)
- **目的**: ml_experiment_v3_result.json から VB フィルタ条件の全組み合わせで単/複 ROI 算出
- **カバー範囲**: gap × EV × proba_A × proba_V × odds_range × track_type グリッド
- **主要関数**: `load_experiment_data`, `load_race_metadata`, `load_db_place_odds`, `build_horse_records`, `calc_roi`, `run_grid_search`, `print_track_comparison`, `print_model_p_top1_analysis`
- **最終更新気配**: **半レガシー** (Session 44 頃の旧結果形式)

### 7.4 ml/simulate_bankroll.py — バンクロール複利 (852 行)
- **目的**: bet_engine.generate_recommendations の買い目で複利シミュ、 haraimodoshi で実精算
- **対応**: 単/複/単複/ワイド/馬連/馬単 (障害)
- **主要関数**: `load_cache`, `load_haraimodoshi`, `group_by_date`, `settle_bet`, `calc_kelly`, `get_bet_ev`, `calc_bet_kelly_fraction`, `run_simulation`, `main`
- **最終更新気配**: **現役**

### 7.5 ml/bankroll_simulator.py — モンテカルロ (611 行)
- **目的**: 戦略×フィルタ別バンクロールシミュ、 bootstrap で CI/破産確率
- **主要クラス**: `Bet`, `SimConfig`, `SimResult`, `MCResult`
- **主要関数**: `extract_bets`, `calc_bet_size`, `simulate_once`, `calc_monthly_pnl`, `monte_carlo`, `generate_report`, `main`
- **最終更新気配**: **現役**

### 7.6 ml/simulate_multi_leg.py — 多券種BT + 当日推奨 (1,177 行)
- **目的**: 馬連・ワイド・馬単・三連複 のBT + `--today` で当日推奨
- **戦略 A-K** の各 evaluate 関数
- **主要関数**: `get_ard_top_n`, `get_danger_horses`, `get_vb_candidates`, `evaluate_A`〜`K`, `run_all_strategies`, `print_summary`, `print_monthly`, `print_top_hits`, `generate_recommendations`, `generate_sanrentan_formation`, `generate_distortion_sanrentan`, `print_recommendations`
- **最終更新気配**: **現役**

### 7.7 ml/simulate_sanrentan.py — 三連単フォーメ (634 行)
- **目的**: backtest_cache × haraimodoshi(三連単実配当) で複数フォーメ戦略 BT
- **主要関数**: `harville_prob` 系 (簡易版), `compute_race_confidence`, `has_danger_horse`, `by_rank_w`, `by_rank_p`, `by_ard`, `by_ard_ev`, `by_vb`, `exclude_danger`, `generate_formation_tickets`, `SanrentanStrategy`, `StratResult`, `run_backtest`, `print_summary`
- **最終更新気配**: **現役**

### 7.8 ml/simulate_sanrentan_ev.py — Synthetic EV (670 行)
- **目的**: Harville 公式でモデル確率から全組み合わせ確率合成、実配当との EV ベースBT
- **主要関数**: `extract_win_probs`, `extract_market_probs`, `harville_prob`, `compute_all_trifecta_probs`, `compute_distortions`, `run_ev_backtest`, `analyze_winning_distortions`
- **最終更新気配**: **現役**

### 7.9 ml/simulate_sanrentan_ev_filtered.py — 三連単 EV 絞り込み (187 行)
- **目的**: フィルター付き Distortion 戦略 BT (8 フィルタプリセット)
- **連携**: simulate_sanrentan_ev からの軽量派生
- **最終更新気配**: **現役**

### 7.10 ml/simulate_formation.py — 条件型フォーメ (1,027 行)
- **目的**: 人気馬2着固定/3着固定 + VB head 等の条件特化フォーメBT
- **主要クラス**: `FormationTickets`, `PatternResult`
- **主要関数**: `analyze_entries`, `pattern_fav_2nd`, `pattern_fav_3rd`, `pattern_vb_head`, `prune_by_distortion`, `check_race_filter`, `pattern_combo_fav2_vb1`, `run_formation_backtest`, `verify_example_races`, `print_summary`/`print_monthly`/`print_hits`
- **連携先**: `export_formation_backtest.py` (web UI 用 JSON 化)
- **最終更新気配**: **現役**

### 7.11 ml/simulate_distortion.py — Harville 歪み BT (549 行)
- **目的**: H5b 発見ベース戦略 (FavOdds<3.0 AND ConfGap<0.10、歪み 2.0-3.0) を BT + バンクロールsim
- **主要関数**: `run_strategy`, `simulate_bankroll`
- **最終更新気配**: **現役**

### 7.12 ml/simulate_strategy_redesign.py — 戦略再設計 (1,083 行)
- **目的**: 新プリセット(単勝系 A-E / 馬連系 A-D / 複勝系 A-C) BT + バンクロール
- **主要関数**: `load_cache`, `load_haraimodoshi`, `extract_tansho_bets`, `extract_umaren_bets`, `extract_fukusho_bets`, `calc_bet_size`, `run_simulation`, `extract_combo_bets`, `export_json`
- **連携先**: 採用された PRESET (tansho_ippon 等) は bet_engine に反映
- **最終更新気配**: **現役** (Session 117 戦略整理時)

### 7.13 ml/export_formation_backtest.py — フォーメBT JSON出力 (423 行)
- **目的**: predictions.json ベース(リークなし) でフォーメBT結果を web UI 用に出力
- **出力**: `data3/ml/formation_backtest.json`
- **EXTENDED_STRATEGIES**: VB_45F3 ベースライン + フィルタ複合 (track_type/grade/odds_band 等)
- **主要関数**: `analyze_pred_entries`, `check_race_filter`, `check_ext_filter`, `build_vb_head_tickets`, `load_predictions_races`, `run_backtest`
- **最終更新気配**: **現役**

### 7.14 ml/win5_simulator.py — WIN5 シミュ (1,447 行)
- **目的**: WIN5 過去レースに各種カバレッジ戦略を適用、何点で的中できたか
- **入力**: mykeibadb `win5/win5_haraimodoshi` + backtest_cache
- **戦略**: top_n / best_union / w_ar_p_combo / ard_threshold / danger_exclude_top_n / type_adaptive / budget
- **主要クラス**: `Win5Race/Week`, `RaceEntry`, `RacePrediction`, `WeekResult`, `RaceExtra`
- **主要関数**: `enrich_with_keibabook`, `load_race_extras`, `enrich_with_jockey_info`, `classify_race_type`, `calc_target_score`, `simulate_week`, `aggregate_results`, `print_coverage_analysis`, `print_summary`, `print_hit_details`, `build_aggregation_tables`, `analyze_winner_ranks`
- **最終更新気配**: **現役**

### 7.15 ml/win5_combo_sim.py — WIN5 精密週次 (568 行)
- **目的**: polaris 2.1b の rank_w 単独優位を反映した精密 WIN5
- **メインプラン**: E (rank_w Top2)/N (頭数適応)/CG3 (自信度可変)/A (WP合算)/C (WP頭数適応)
- **主要関数**: 各 plan_select、 simulate_plan、 simulate_combined、 analyze_plan
- **最終更新気配**: **現役** (Session 117)

### 7.16 ml/win5_strategy_search.py — WIN5 戦略探索 (452 行)
- **目的**: P系・Union系・Hybrid を 200 点以内で網羅
- **主要関数**: `select_fixed`, `select_union`, `select_variable`, `select_p_proba_topn`, `select_ev_topn`, `select_consensus`, `build_strategies`, `simulate`
- **最終更新気配**: **現役**

### 7.17 ml/win5_raw_signal_sim.py — WIN5 生データ (427 行)
- **目的**: ML 非依存、競馬ブック印 + JRDB IDM + オッズ等の生データで WIN5 検証
- **主要関数**: `rank_by_kb_mark`, `rank_by_kb_rating`, `rank_by_jrdb_idm`, `rank_by_odds`, `rank_by_kb_ai`, `union_kb_jrdb`, `consensus_kb_odds`, `union_all3`, `rank_by_model_w`/`p`, `build_strategies`, `simulate`
- **最終更新気配**: **現役**

### 7.18 ml/win5_hybrid_combo.py — WIN5 Hybrid (210 行)
- **目的**: raw signal + model combo を組み合わせた WIN5 シミュ
- **最終更新気配**: **現役**

### 7.19 ml/win5_adaptive_wps.py — WIN5 適応 WPs (246 行)
- **目的**: WPs1 位勝率・出走頭数・ハンデ戦フラグで Top1-4 可変選択
- **★ 注**: 本タスクの「ハンデ戦判定」サンプル実装あり
- **最終更新気配**: **現役**

### 7.20 ml/obstacle_place_wide_backtest.py — 障害 複勝/ワイド (265 行)
- **目的**: 障害 P モデル予測 × haraimodoshi で 単/複/ワイド ROI 横断
- **最終更新気配**: **現役**

---

## 8. 特徴量モジュール (F) — ml/features/

| ファイル | 行数 | 役割 | 主要関数/定数 |
|---|---:|---|---|
| `base_features.py` | 152 | レースJSON直読み: 年齢/性別/斤量/馬体/距離/月/開催日 + コース静的属性(直線距離・高低差・1角距離) | `STRAIGHT_DISTANCE`, `HEIGHT_DIFF`, `FIRST_CORNER_DIST`, `extract_base_features` |
| `past_features.py` | 468 | 過去走成績: avg/best finish, last3f, win_rate(ベイズ平滑化), career_stage, prev→現在直接比較(v5.45), 着差 tbw(v7.7) | `compute_past_features`, `parse_margin_to_seconds` |
| `trainer_features.py` | 109 | 調教師統計 (5桁code 100%match) + PIT timeline | `build_trainer_index`, `get_trainer_features`, `_pit_lookup` |
| `jockey_features.py` | 119 | 騎手統計 + 接戦勝率 + PIT timeline | `build_jockey_index`, `get_jockey_features` |
| `running_style_features.py` | 96 | 脚質: corners 配列から avg_first/last_corner_ratio, front_runner_rate, closing_strength 等 | `compute_running_style_features` |
| `rotation_features.py` | 229 | ローテ + 降格ローテ(7パターン) + 騎手乗替 + 斤量変化 | `compute_rotation_features` |
| `pace_features.py` | 316 | RPCI/lap33/race_trend_v2、急坂コース経験、余力ラップ系 | `compute_pace_features`, `_last_nf`, TREND_V2_ENCODE |
| `training_features.py` | 256 | 競馬ブック調教(脚色/併せ馬/oikiri各F) + KB印 + CK_DATA lapRank | `compute_training_features`, `INTENSITY_MAP` |
| `speed_features.py` | 90 | kb_ext speed_indexes (latest/best5/avg3/trend/std) | `compute_speed_features` |
| `comment_features.py` | 343 | 厩舎談話/前走インタビュー/次走メモ NLP辞書スコア | `compute_comment_features`, CONDITION_POSITIVE/NEGATIVE 等 |
| `slow_start_features.py` | 118 | 出遅れ率(発走状況) — kb_ext.is_slow_start から計算。**現状 importance 0 で除外中** | `compute_slow_start_features` |
| `pedigree_features.py` | 207 | sire/dam/bms top3率、瞬発/持続、休み明け得意/苦手、成長曲線 | `build_sire_index`, `_bayesian_rate` |
| `baba_features.py` | 163 | 馬場クッション値・含水率(芝/ダ別) | `load_baba_index`, `get_baba_features`, `race_id_to_baba_key` |
| `track_bias_features.py` | 273 | KAA当日バイアス(芝内外/直線/外差し) + SED前崩れ経験/Hペース経験 | TRACK_BIAS_RACE_FEATURES, `compute_track_bias_features` |
| `career_features.py` | 432 | 全キャリア + jrdb_sed_index、 IDM トレンド・安定性・ピーク距離 + novelty_score (未知数) | `compute_career_features`, `_normalize_track_type` |
| `jrdb_features.py` | 426 | SED 事後IDM 履歴(idm_last/avg3/max5/trend/std) + KYI 事前IDM/総合/騎手/調教/厩舎指数 + CID/LS時系列 (v8.1) | `race_id_to_jrdb_key`, `compute_jrdb_features`, `JRDB_FEATURE_COLS` |
| `closing_race_features.py` | 471 | 差し決着レースレベル特徴量 7グループ ~30個 + `CourseClosingTimeline` | `is_closer`, `compute_closing_label`, `compute_closing_race_features` |
| `obstacle_features.py` | 1,198 | 障害固有(難度/経験/騎手障害成績/直線路面/同系統 etc) v2.0-v2.5b | 全 18 関数 (compute_obstacle_*) |
| `margin_target.py` | 311 | 着差ターゲット計算 (走破タイム M:SS.T → 秒、同タイム着順0.02s分離、5秒キャップ) | `parse_time_str`, `add_margin_target_to_df` |

---

## 9. その他 (G) — utility / IO

| ファイル | 行数 | 役割 | 連携 |
|---|---:|---|---|
| `feature_snapshot.py` | 130 | レース単位の特徴量を `features_{race_id}.json` 保存。リーク検出・差分比較用 | experiment.py / predict.py が任意で書き出し |
| `enrich_novelty.py` | 253 | 過去 predictions に novelty_*/ar_deviation_adj/is_value_bet を後付 | `analyze_novelty.py` に渡す |
| `extend_backtest_cache.py` | 214 | predictions + race_*.json → backtest_cache 追記 | バックテストキャッシュ更新 |
| `set_active.py` | 128 | archive/v{N}/ → live/ コピーで切替 | Session 119 新規 |
| `switch_model.py` | 160 | 旧 versions/ 構造用切替 | Session 119 set_active.py で代替 |
| `compare_models.py` | 196 | 2 polaris バージョンを並べて AUC/importance Top 差分 | (分析系にも該当) |
| `preflight.py` | 225 | 学習前スモークテスト | experiment.py 本走前 |
| `generate_registration.py` | 339 | 特別登録データ → `registration.json` 生成 | web UI(特別登録ページ) |
| `settle_purchases.py` | 547 | mykeibadb 確定配当で purchases/{date}.json を精算(単/複/馬連/馬単/ワイド) | 購入ログ自動反映 |
| `tests/test_bet_engine.py` | - | bet_engine ユニットテスト (pytest) | CI 用 |
| `experiment_v3.py` | 6 | `ml.experiment` への後方互換リダイレクト | レガシー |
| `ml/__init__.py` | 1 | package marker | - |

---

## 10. 重複・統合候補

> **★Session 122 リファクタ進捗** (2026-05-17): Phase 0 で `ml/utils/` 5 モジュール新設、Phase 1 で call site 47ファイル統合済み。 詳細は各サブセクションのステータス参照。 ROI 計算 (10.1) は既存スクリプト挙動の再現性保持のため意図的にスキップ。

### 10.1 ROI 計算ロジックの分散
ROI を独自実装している箇所が多い:

| ファイル | 関数 | 用途 |
|---|---|---|
| `experiment.py` | `calc_roi_analysis` | 学習評価 |
| `bet_engine.py` | `calc_bet_engine_roi` | プリセット評価 |
| `analyze_polaris_weakness.py` | `analyze_roi_comparison` | 弱点分析 |
| `analyze_simple_strategy.py` | `calc_roi` | シンプル戦略 |
| `analyze_allocation.py` | `calc_roi` | 配分戦略 |
| `monthly_analysis.py` | `calc_roi` | 月別 |
| `simulate_bankroll.py` | `settle_bet` | バンクロール |
| `bankroll_simulator.py` | `simulate_once` | モンテカルロ |
| `simulate_strategy_redesign.py` | `run_simulation` | プリセット再設計 |
| `simulate_sanrentan.py` | `run_backtest` | 三連単 |
| `simulate_sanrentan_ev.py` | `run_ev_backtest` | Synthetic EV |
| `analyze_wide_strategy.py` | (inline) | ワイドv1 |
| `analyze_wide_strategy_v2.py` | (inline) | ワイドv2 |
| `analyze_wide_v3.py` | `calc_roi` | ワイドv3 |
| `obstacle_place_wide_backtest.py` | (inline) | 障害複/ワイド |

**統合候補**: `ml/utils/roi.py` 新規作成 → `calc_roi(bets: List[Bet]) -> RoiResult` を提供。 RoiResult に hit_rate / mean_odds / p&l / bootstrap_ci を集約。

**ステータス (2026-05-17)**: ⚠️ **モジュールは作成済 (Phase 0) だが既存 call site の置換は意図的にスキップ**。 既存 BT 結果の再現性100%保証のため、ローカル `calc_roi` は touch せず、新規スクリプト (`polaris_segments.py` / `polaris_hybrid.py` / 将来の analyze スクリプト) のみで `ml.utils.roi.calc_roi` を使う方針。

### 10.2 backtest_cache.json ローダーの重複
hardcode の `Path("C:/KEIBA-CICD/data3/ml/backtest_cache.json")` が 14 ファイル以上で再実装。

**統合候補**: `ml/utils/cache.py` に `load_backtest_cache()`, `flatten_to_df()` を集約。 既に `simulate_sanrentan_ev.load_backtest_cache` が複数の simulate に import されているのでベース化はそこから。

**ステータス (2026-05-17)**: ✅ **完了 — Phase 1.1 [commit 7da1b93]**。`ml/utils/backtest_cache.py` 新設 + 20 ファイルの hardcode path / ローカル loader 削除。 `load_backtest_cache(path=None, suffix=None)` + `flatten_to_df()` + `cache_to_predictions()` + `build_lookup()` 提供。 検証: 20/20 module import OK、`analyze_polaris_weakness.load_backtest_flat` で 2,934 races / 40,327 entries 完全一致。

### 10.3 セグメント分割の hardcode
オッズ帯/頭数帯/ARd帯/gap帯 のビン分割が散在(`analyze_polaris_weakness.py`、`analyze_wide_strategy.py`、`analyze_market_signal.py`、`analyze_predictions.py`、`analyze_betting_strategy.py`、`analyze_novelty.py` 等)。

**統合候補**: `ml/utils/segments.py` → `bin_odds`/`bin_runners`/`bin_ard`/`bin_gap`/`bin_novelty`/`bin_confidence` の共通関数化。

**ステータス (2026-05-17)**: ✅ **完了 — Phase 1.4 [commit d0b775b]**。 `ml/utils/segments.py` 新設、`bin_odds/runners/gap/ev/distance/ard/novelty/confidence` + `bin_month` + `race_id_to_date/month` + `is_handicap` 提供。 `analyze_polaris_weakness` の 4 箇所 (runner/ev/gap/cs band) を統合、odds_band 集計値リファクタ前後で完全一致。 default labels は `ODDS_LABELS` `RUNNER_LABELS` 等として export。

### 10.4 mykeibadb 払戻ローダー重複
- `simulate_multi_leg.load_haraimodoshi`, `simulate_bankroll.load_haraimodoshi`, `simulate_strategy_redesign.load_haraimodoshi`
- `simulate_sanrentan.load_sanrentan_payouts` / `simulate_sanrentan_ev.load_sanrentan_payouts` / `analyze_sanrentan_distortion.load_sanrentan_payouts`
- `analyze_teppan_wide_umaren.load_haraimodoshi`、`analyze_teppan_deep.py`, `analyze_teppan_extra.py` 内に再実装

**統合候補**: `core/payouts_db.py` に `get_payouts(race_codes, bet_types=...)` を一元化(既に `core/odds_db.py` がオッズ用に存在)。

**ステータス (2026-05-17)**: 📋 **未着手**。 Phase 0-4.5 では触れていない (Session 123 以降のリファクタ候補)。

### 10.5 race_*.json 走査と結果抽出
`analyze_predictions.load_race_results` / `analyze_betting_strategy.load_race_results` / `analyze_market_signal.collect_data` / `enrich_novelty.build_race_meta` / `analyze_novelty.build_results` / `extend_backtest_cache.load_results_from_race_json` で類似実装。

**統合候補**: `ml/utils/race_io.py` に `load_race_result(race_id)`/`iter_race_results(start, end)` を集約。

**ステータス (2026-05-17)**: ✅ **完了 — Phase 1.2 [commit 892f5d4]** + **Phase 2 拡張 [commit 404ca57]**。 `ml/utils/race_io.py` 新設、`iter_date_dirs/date_dir_for/iter_race_files/load_race/load_race_results/load_predictions/iter_predictions` 提供。 7 ファイルの重複 loader を統合。 後方互換: `load_race_results` の戻り値に `"finish"` + `"finish_position"` 両キー含む。 Phase 2 で `fetch_race_meta`/`enrich_with_race_meta` 追加 (backtest_cache → race metadata 補完用、空文字 fillna 対応)。

### 10.6 三連単/Harville の重複
`analyze_sanrentan_distortion.harville_prob` / `simulate_sanrentan_ev.harville_prob` / `simulate_sanrentan.harville_prob` / (`simulate_distortion`/`simulate_formation` は ev から import で統合済)。

**統合候補**: `ml/utils/harville.py` に統一(`compute_all_trifecta_probs` 含む)。

**ステータス (2026-05-17)**: 📋 **未着手**。 Phase 0-4.5 では触れていない (Session 123 以降のリファクタ候補)。

### 10.7 障害レース除外フィルタの重複 (NEW)
**Session 122 で新規発見**。 `track_type == 'obstacle'` / `'障害'` / `'steeplechase'` + `race_name に '障' 含む` の判定が 19 ファイルで散在。

**ステータス (2026-05-17)**: ✅ **完了 — Phase 1.3 [commit e6f93da]**。 `ml/utils/filters.py` 新設、`is_obstacle()` / `exclude_obstacle()` / `split_by_obstacle()` 提供 (`steeplechase` も検出対象に含めた)。 19 ファイルの判定ロジックを統合。 bet_engine.py / experiment_obstacle.py / features/obstacle_features.py は障害固有処理 (セマンティック判定) のため非変更。

---

## 11. リファクタ余地

### 11.1 命名の不統一
- `analyze_*.py` (24本) と `*_analysis.py` (4本: monthly/market_divergence/cumulative_pnl/ability_turf_dirt/ci_power) が混在。テーマ別ディレクトリ化推奨:
  - `analyze/segment/` (条件別性能), `analyze/market/`, `analyze/strategy/`, `analyze/sanrentan/`, `analyze/win5/`

### 11.2 旧 ML_DIR ハードコード
`analyze_shap.py`、`switch_model.py`、 backtest 一部が `C:/KEIBA-CICD/data3/ml` ハードコード。 `core/config.ml_dir()` 経由に統一すべき。

### 11.3 v5.5 ハードコード呪縛
`monthly_analysis.py`/`cumulative_pnl_analysis.py`/`market_divergence_analysis.py`/`ability_turf_dirt_analysis.py` は全て `load_v55_models` を介する。 polaris 2.1b で再利用するには `model_loader` ベースに刷新が必要。

### 11.4 切替系の重複
`set_active.py` (Session 119) と `switch_model.py` の機能重複。 後者をレガシー化して deprecate コメント追加が望ましい。

### 11.5 experiment.py の肥大化
3,572 行は単体ファイルとして肥大。 build_dataset / compute_features_for_race / train_model / 評価関数 / main の責任分離が候補。 ただし predict.py や派生 experiment_* が深く import するため大手術になる。

### 11.6 hardcode prefix リスト
`analyze_baba_features.py`/`analyze_baba_report.py` 内の `TURF_PREFIXES = {'00','03','04','0B'}` は `features/baba_features.py` の同名定数と重複。 統一する。

---

## 12. 「polaris 条件別性能分析」 新規実装で再利用できる既存資産

### 12.1 最も近い既存スクリプト
| 流用度 | スクリプト | 使える機能 | 制約 |
|---|---|---|---|
| ★★★ | `analyze_polaris_weakness.py` | `load_backtest_flat()` でフラット DF 化、 odds_band/track_type/grade/age_class/num_runners 別の集計枠組み、 ROI/Brier/false_positive 計算 | 月別/騎手/調教師/会場/距離帯/ハンデ戦/直前は未実装 |
| ★★★ | `analyze_market_signal.py` | predictions.json + race_*.json 全期間走査と 月別集計の足回り | market_signal 軸限定 |
| ★★ | `monthly_analysis.py` | 月別ROI / bootstrap CI / filter_win_only | v5.5 ハードコード、 model_loader 化要 |
| ★★ | `analyze_predictions.py` | 全期間 predictions × 確定オッズ突合、 PRESET別 ROI | 軸が PRESET 単位 |
| ★★ | `cumulative_pnl_analysis.py` | MaxDD / 連敗 / 月別連敗 計算 | v5.5 ハードコード |
| ★★ | `ci_power_analysis.py` | CI幅 vs 件数の理論推定 | 入力フォーマット限定 |
| ★ | `bankroll_simulator.py` | Bootstrap で破産確率 / CI / 月別損益 | bankroll 視点で条件分析向きでない |

### 12.2 流用できる関数 (短く言及)
- `experiment.calc_roi_analysis(df, pred_col)` — モデル列で sort して上位N の ROI を返す
- `experiment.calc_brier_score`, `calc_ece` — キャリブレーション評価
- `experiment.calc_vb_bootstrap_ci` — bootstrap で VB ROI の CI 計算
- `analyze_polaris_weakness.load_backtest_flat` — backtest_cache を行=馬 DataFrame に
- `analyze_market_signal.collect_data`, `calc_stats` — predictions × race 突合の参照実装
- `analyze_betting_strategy.analyze_streaks` — 連敗ストリーク計算(95%分位連敗)
- `cumulative_pnl_analysis.calc_max_drawdown`, `calc_losing_streaks`, `calc_consecutive_loss_months` — DD/連敗
- `bet_engine.compute_vb_score`, `passes_novelty_filter`, `get_grade_key`, `load_grade_offsets` — VB判定の再利用
- `bet_engine.calc_kelly_fraction` — Kelly 計算
- `bankroll_simulator.monte_carlo` — Bootstrap CI、 破産確率

### 12.3 不足してる機能 (本タスクで新規実装すべき)
| 機能 | 既存 | 補完が必要 |
|---|---|---|
| Sharpe 比 | 無 | ★ 月次/週次 ROI 系列の標準偏差→Sharpe |
| Sortino 比 | 無 | (Sharpe と同時に) |
| 期間A/B 比較 (前半/後半 ROI 比較) | 無 | ★ Walk-Forward 風の期間分割 + 差分検定 (Mann-Whitney など) |
| ハンデ戦判定 | `win5_adaptive_wps.py` 内のみ | ★ `race.is_handicap` を統一抽出する util |
| 距離帯セグメント | `analyze_baba_*.py` で limited | ★ `bin_distance` 統一 (1200/1400/1600/1800/2000/2200+/2400+/3000+) |
| 騎手別 ROI | 個別 race_*.json から組み立て要 | ★ jockey_code 集計 |
| 調教師別 ROI | 同上 | ★ trainer_code 集計 |
| 会場別 ROI | `analyze_baba_*.py` で limited | ★ venue_code 統一集計 |
| 月別 ROI (polaris 2.1b で) | `monthly_analysis.py` v5.5 のみ | ★ polaris-2.0/2.1b で再実装 |
| 締切前/直前オッズ別 ROI | 無 (vb_refresh は再計算のみ) | ★ オッズ snapshot の時刻別比較 |
| 複合セグメント (track × grade × num_runners) | `analyze_polaris_weakness` が一部 | ★ pivot table の汎用化 |
| Recall/Precision per segment | 限定的 | ★ confusion matrix per segment |
| 反証可能性 (件数が n<30 のセグメントを赤フラグ) | 無 | ★ サンプル数チェッカー |
| キャリブレーション曲線 per segment | `analyze_polaris_weakness` で odds_band のみ | ★ 全セグメント共通化 |
| 障害レースを混ぜずに排除する utility | あちこちで個別 `track_type=='obstacle'` filter | ★ 統一フィルタ |

### 12.4 推奨アーキテクチャ案

**ステータス (2026-05-17)**: ✅ **大半実装完了 — Session 122 Phase 0-4.5** (`payouts.py` / `harville.py` のみ未着手)

```
ml/
├── analyze/                       ✅ Phase 2/4 で新設
│   ├── __init__.py                ✅
│   ├── polaris_segments.py        ✅ Phase 2 [404ca57] — 9軸セグメント分析、約430行
│   ├── polaris_hybrid.py          ✅ Phase 4/4.3 [372d179/c33cac9] — P×W ハイブリッド戦略 7+10 評価
│   └── ...既存analyze系の移動...    📋 Phase 5+ 候補
│
├── strategies/                    ✅ Phase 4.1 で新設 (NEW)
│   ├── __init__.py                ✅
│   └── selective.py               ✅ Phase 4.1 [d073938] — 実戦投入戦略エンジン
│                                     (extract/write_selective_bets, CLI --date/--start/--end)
│                                     Phase 4.4 [54650ea] で odds_rank/vb_gap 追加
│
├── utils/                         ✅ Phase 0 で新設 [4f6ade0]
│   ├── __init__.py                ✅
│   ├── backtest_cache.py          ✅ load_backtest_cache/flatten_to_df/cache_to_predictions/build_lookup
│   ├── race_io.py                 ✅ iter_date_dirs/load_race/load_race_results/iter_predictions
│                                     + Phase 2 で fetch_race_meta/enrich_with_race_meta 追加
│   ├── payouts.py                 📋 未着手 (Section 10.4)
│   ├── roi.py                     ✅ Bet/RoiResult + calc_roi/bootstrap_ci/sharpe/sortino
│                                     + max_drawdown/losing_streaks/brier/ece/calibration_curve
│   ├── segments.py                ✅ bin_odds/runners/gap/ev/distance/ard/novelty/confidence
│                                     + race_id_to_date/month + is_handicap
│   ├── harville.py                📋 未着手 (Section 10.6)
│   └── filters.py                 ✅ is_obstacle/exclude_obstacle/split_by_obstacle
│                                     + has_min_samples/filter_win_only/filter_selective
│
└── tests/                         ✅ pytest 94件全通過
    ├── test_utils_filters.py
    ├── test_utils_segments.py
    ├── test_utils_roi.py
    ├── test_utils_backtest_cache.py
    └── test_utils_race_io.py
```

`ml/analyze/polaris_segments.py` (✅ 実装済 [Phase 2]):
1. ✅ `load_backtest_cache()` → flat df
2. ✅ 9軸 (odds_band/runners/grade/track_type/distance/month/venue/jockey/trainer) を `segments.py` で生成
3. ✅ 各軸ごとに `calc_roi`/`calc_brier`/`calc_calibration_curve` を実行
4. ✅ n<30 セグメントを `sample_size_marker` で警告フラグ出力
5. ✅ 期間 A (前半) vs 期間 B (後半) で `compare_periods` 差分計算 (Mann-Whitney は未実装)
6. ✅ 結果を `data3/analysis/polaris_segments/{run_id}/` 配下に summary.md + segments.json + period_compare.json + meta.json 出力
7. ✅ Web UI ダッシュボード `/analysis/polaris-segments` [Phase 3: be7203d] + Run 比較モード [Phase 3.1: 8820dc7]

→ `analyze_polaris_weakness.py` の大半カバー + 騎手/調教師/会場/距離/月/ハンデ等の不足軸も網羅。 実行時間 6.6秒 (2,934 races / 40,327 entries)。

#### Phase 4 拡張: ハイブリッド戦略と実戦投入 (12.5)
[Phase 4 / 4.3 で polaris_hybrid.py に 7+10 戦略]:
- baseline 2 (P_only / W_only) + Hybrid-{Grade/Odds/Concur} + Concur+Grade + Selective
- Sel_v2 sweep (信頼度 p>=0.40/0.45/0.50) → **ROI 半減 (203% → 108%)**
- Sel_v3 sweep (市場乖離 vb_gap>=2/3/4 + not_fav1 + not_top2 + p<=0.40) → **ROI 倍増 (203% → 381%)**

[Phase 4.1/4.2/4.4/4.5 で実戦投入]:
- `ml/strategies/selective.py` — `selective_bets.json` 自動生成 (重賞のみ rank_p==1 + odds_rank/vb_gap 含む)
- `vb_refresh.py` 連携 — predictions.json 保存後に自動で selective_bets.json も生成
- `/analysis/selective-bets` ダッシュボード — 日付ピッカー + 戦略タグ表示 (baseline/not_fav1/not_top2/gap≥3/gap≥4)
- `/predictions` レースヘッダーに 🎯 Selective + 🔥 v3 バッジ統合

#### 確立された戦略原則
**「市場と一致するシグナルは ROI を下げる、乖離するシグナルこそ収益源」** (Phase 4.3 で定量化)
- Sel_v2 (モデル信頼度高フィルタ = 市場一致) → ROI ダウン
- Sel_v3 (vb_gap = モデル vs 市場の乖離フィルタ) → ROI アップ
- → Session 119 「視点独立性は ROI 源泉」原則がモデル内部 (P モデル vs 市場ランク) でも観測

---

## 付録: ファイル更新気配サマリ

- **★Session 122 新規 (2026-05-17)**:
  - `ml/utils/{filters,segments,roi,backtest_cache,race_io}.py` (Phase 0)
  - `ml/analyze/polaris_segments.py` (Phase 2) + `ml/analyze/polaris_hybrid.py` (Phase 4/4.3)
  - `ml/strategies/selective.py` (Phase 4.1/4.4) — 実戦投入用
  - `ml/tests/test_utils_*.py` (pytest 94件)
  - `web/src/app/analysis/polaris-segments/page.tsx` + `selective-bets/page.tsx` (Phase 3/4.1)
  - `web/src/app/api/analysis/polaris-segments/route.ts` + `selective-bets/route.ts`
- **現役・最重要**: experiment.py, predict.py, batch_predict.py, model_loader.py, bet_engine.py, generate_bets.py, vb_refresh.py (★Phase 4.2 で selective 連動追加)
- **現役**: experiment_obstacle/closing, predict_closing, optuna_tuner系, preflight, set_active, win5_pick/combo_sim/variable/raw_signal_sim/strategy_search/adaptive_wps/hybrid_combo, simulate_bankroll/multi_leg/sanrentan/sanrentan_ev/sanrentan_ev_filtered/formation/distortion/strategy_redesign, backtest_bet_engine, backtest_vb, bankroll_simulator, extend_backtest_cache, export_formation_backtest, settle_purchases, generate_registration, compare_models, analyze_predictions/polaris_weakness/baba_features/baba_report/market_signal/base_odds/base_odds_v2/divergence/allocation/simple_strategy/teppan_deep/teppan_extra/teppan_wide_umaren/wide_strategy/wide_strategy_v2/wide_v3/win5_topn/sanrentan_distortion/obstacle_multi/novelty/betting_strategy, compare_ard_tiers, investigate_ard_value, ci_power_analysis, enrich_novelty, feature_snapshot, obstacle_place_wide_backtest
  - ★Phase 1.1-1.4 で 47ファイルが ml.utils.{backtest_cache, race_io, filters, segments} に依存するよう統合済み
- **実験的(production 非採用)**: experiment_lambdarank, experiment_unified, experiment_speed_idx, experiment_performance, experiment_regression, experiment_deviation_gap (採用済), analyze_idm_diff, analyze_shap
- **半レガシー**: monthly_analysis, cumulative_pnl_analysis, market_divergence_analysis, ability_turf_dirt_analysis (v5.5 hardcode), backtest_vb (旧結果フォーマット), verify_bet_engine_params, switch_model (set_active で代替), experiment_v3 (リダイレクト)

---

## 13. Session 122 で確立した戦略原則 (2026-05-17)

Phase 2-4.5 の分析から、 polaris 2.0 / Selective 戦略について以下が定量的に確認された:

1. **重賞限定 (Selective) が最強の単一戦略**: 166 bets / ROI 203% / P&L +¥17,110 (BT)
2. **市場乖離フィルタが ROI を爆発的に伸ばす**:
   - Sel_v3 not_fav1 (1番人気除外): bets 119 / ROI 247% / P&L +¥17,470 (BT)
   - Sel_v3 gap≥3 (vb_gap >= 3): bets 73 / ROI 320% / P&L +¥16,030 (BT)
   - Sel_v3 gap≥4: bets 54 / ROI 381% / P&L +¥15,190 (BT)
3. **信頼度フィルタは ROI を下げる**:
   - Sel_v2 p>=0.45 (Top1 複勝確率高): bets 53 / ROI 108% / P&L +¥440 (BT)
   - → 「モデル確信 = 市場一致 = オッズ付かない」
4. **W 単独は Sharpe 30.88 だが累計 -¥37,770** — Sharpe 単独で判定するな
5. **Hybrid-Concur (P==W 一致) は ROI 改善せず** — Session 119 stacking 失敗と同じ「P と W は独立視点でなく相関高」
6. **新馬・1勝クラスは polaris の苦手領域** — 1,229 bets / ROI 76-83% (BT)
7. **OOS (2026-04~05, 18 bets)**: baseline +81% / not_fav1 +128% / gap≥3 +174% — サンプル少ないが v3 が baseline を上回る方向で一貫

詳細は `memory/niche-specialist-strategy.md` 参照。
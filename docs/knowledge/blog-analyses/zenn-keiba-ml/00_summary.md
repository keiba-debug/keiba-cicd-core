# Zenn「競馬予想で始める機械学習〜完全版〜」全体まとめ

> 著者: dijzpeb | 価格: 3,900円 | 387,872字 | コミュニティ ~1,400名
> 分析日: 2026-02-25 (Session 50)

---

## 書籍の全体像

| 区分 | 章 | 内容 | まとめファイル |
|------|---|------|-------------|
| v1基礎 | Ch.01 | はじめに・技術スタック | 01_about.md |
| v1基礎 | Ch.02 | スクレイピング（netkeiba.com） | 02_scraping.md |
| v1基礎 | Ch.03 | データ処理・特徴量作成 | 03_data_processing.md |
| v1基礎 | Ch.04 | LightGBM + Optuna学習 | 04_model_training.md |
| v1基礎 | Ch.05 | 回収率シミュレーション・Sharpe比 | 05_model_evaluation.md |
| v1基礎 | Ch.06 | 実際の購入結果 | 06_actual_betting.md |
| v2設計 | Ch.08 | v2アーキテクチャ概要 | 08_v2_overview.md |
| v2設計 | Ch.09 | ディレクトリ構成・実行フロー | 09_v2_directory_and_execution.md |
| v2設計 | Ch.10 | 定数モジュール | 10_v2_constants.md |
| v2実装 | Ch.13 | 前処理Processor群 | 13_v2_preprocessing_part1.md |
| v2実装 | Ch.14 | DataMerger・特徴量エンジニアリング | 14_v2_preprocessing_part2.md |
| v2実装 | Ch.15 | 学習モジュール（Optuna統合） | 15_v2_training.md |
| v2実装 | Ch.16 | ScorePolicy・BetPolicy | 16_v2_policies.md |
| v2実装 | Ch.17 | シミュレーション・プロット | 17_v2_simulation.md |
| スキップ | Ch.07 | （v1→v2の橋渡し、概要のみ） | — |
| スキップ | Ch.11-12 | スクレイピング実装詳細（JRA-VAN使用のため不要） | — |

---

## 書籍 vs KeibaCICD 全体比較

| 項目 | この書籍 | KeibaCICD v4 |
|------|---------|-------------|
| **データソース** | netkeiba.comスクレイピング | JRA-VANバイナリ直読 |
| **モデル** | LightGBM 1本（二値分類） | 5本（A/V/W/WV/RegB） |
| **ハイパーパラメータ** | **Optuna自動最適化** | 手動設定 |
| **血統** | **62列 LabelEncoding→category** | 未実装（A-0予定） |
| **point-in-time** | **日付ループ + date < @date** | 一部未対応（A-4予定） |
| **キャリブレーション** | なし | IsotonicRegression |
| **スコア変換** | 4種ScorePolicy（Strategy） | AR偏差値（固定） |
| **購入戦略** | 7券種 BetPolicy（Strategy） | 単複のみ 3プリセット |
| **評価指標** | AUC + ROI + **Sharpe比** | AUC + ECE + VB ROI |
| **信頼区間** | 解析的σ（独立同分布仮定） | Bootstrap CI（仮定なし） |
| **特徴量数** | ~205列（血統62列含む） | ~118列（v5.6） |
| **エンティティID** | 5種直接投入（category） | 集計特徴量のみ |
| **閾値探索** | 線形スイープ + 可視化 | 固定プリセット |

### うちの優位点
- **5モデル体制** — 市場/独自 × 好走/勝利 + 能力回帰で多角的評価
- **Gapフィルター** — 市場評価と独自評価の乖離を利用（単一モデルには不可能）
- **IsotonicRegression** — キャリブレーション済み確率でEV計算が正確
- **Bootstrap CI** — 分布仮定不要の頑健な信頼区間
- **JRA-VANデータ** — バイナリ直読で高品質・高速（スクレイピング不要）
- **keibabook拡張** — 調教データ・コメントNLP等の独自データソース

### 書籍の優位点
- **Optuna** — ハイパーパラメータ自動最適化（+24pt ROI改善の実績）
- **血統62列** — 5世代血統をcategory特徴量化
- **point-in-time完全対応** — 日付ごとのフィルタでリーク完全防止
- **7券種シミュレーション** — 三連複BOX等の高配当券種も対応
- **Sharpe比** — 回収率の安定性も定量評価
- **体系的特徴量生成** — TARGET_COLS × GROUP_COLS × N_RACES の直積で自動生成

---

## KeibaCICDに取り入れるべき項目

### Tier 1: 高優先度（ROI直結）

| # | 項目 | 出典 | 既存関連 | 期待効果 | 実装難度 |
|---|------|------|---------|---------|---------|
| **1** | **Optuna導入** | Ch.04, 15 | ml-debug-procedure.md（テンプレあり） | **+24pt ROI**（書籍実績） | 低〜中 |
| **2** | **血統62列特徴量（A-0）** | Ch.03, 14 | UM_DATAに血統データあり | 特徴量+87列、書籍で高重要度 | 中 |
| **3** | **point-in-time化（A-4）** | Ch.03, 14 | horse_historyキャッシュ一部対応 | リーク排除→真のモデル性能把握 | 中〜高 |

#### Optuna導入の具体的方法
```
方式A（簡易版・まず試す）:
  import optuna.integration.lightgbm as lgb_o
  lgb_clf_o = lgb_o.train(params, lgb_train, valid_sets=..., optuna_seed=100)

方式B（カスタム版・効果確認後）:
  study = optuna.create_study(direction='maximize')
  study.optimize(objective, n_trials=50)
```
- まず方式Aで5モデルそれぞれの効果を確認
- 効果あれば方式Bでパラメータ範囲をカスタマイズ
- **注意**: チューニング後にearly_stopping除外して全trainデータで再学習

#### 血統特徴量の具体的方法
```
1. UM_DATAから5世代血統（父/母/父父/父母/母父/母母...計62頭）を取得
2. ketto_numをLabelEncoding
3. LightGBMのcategorical_feature指定（category型）
4. → LightGBMが自動的に有効な分割を学習
```
- 書籍の方式はシンプルだがカーディナリティが高い（数万種）
- 過学習リスクあり → まず父/母父の2列から試して効果検証

#### point-in-time化の具体的方法
```
# 書籍方式（参考）
for date in sorted(unique_dates):
    past_data = horse_results.query('date < @date')
    # past_dataから集計

# うちの場合（horse_historyキャッシュ方式を拡張）
for race in sorted_races:
    for horse in race.entries:
        history = get_history_before(horse_id, race_date)  # date < race_date
        features = compute_features(history)
```

### Tier 2: 中優先度（分析・評価改善）

| # | 項目 | 出典 | 期待効果 | 実装難度 |
|---|------|------|---------|---------|
| **4** | **Sharpe比の導入** | Ch.05 | 回収率の安定性を定量評価 | 低 |
| **5** | **閾値スイープ可視化** | Ch.17 | 最適条件の探索的発見 | 低〜中 |
| **6** | **体系的特徴量生成** | Ch.14 | 特徴量追加の効率化・網羅性 | 中 |

#### Sharpe比の計算
```python
sharpe = (roi - 1.0) / std_roi
# std_roi = returns_per_race.std() * sqrt(n_races) / total_bet
```
- backtest_bet_engine.pyの出力に1行追加するだけ
- 既存のBootstrap CIと併用で安定性評価が充実

#### 閾値スイープ
- うちの場合は多条件（gap, EV, AR偏差値）なので単純1Dスイープは不適
- **代替案**: 1条件ずつ固定しながら残りをスイープする偏微分的アプローチ
- Jupyter notebook上で実験的に実行（experiment.pyの拡張）

### Tier 3: 低優先度（将来検討）

| # | 項目 | 出典 | メモ |
|---|------|------|------|
| 7 | 7券種シミュレーション | Ch.17 | 三連複BOX等は買い目膨大、慎重に |
| 8 | エンティティID直接投入 | Ch.03, 14 | horse_id/jockey_idをcategory化。過学習リスク大 |
| 9 | frozen dataclass化 | Ch.10 | constants.pyの品質向上。機能変更なし |
| 10 | Strategyパターン化 | Ch.16 | ScorePolicy/BetPolicyの設計改善。現状でも動く |
| 11 | dill一体保存 | Ch.15 | モデル+データの再現性向上。運用変更あり |
| 12 | 流し戦略（2閾値） | Ch.16 | 軸+相手の概念。うちのGap+rankで類似実現済み |

---

## 書籍から学んだ設計思想

1. **Strategy パターンの徹底** — ScorePolicy/BetPolicyの差し替え容易性。うちのプリセットは実質同じだが分離度が低い
2. **Template Method + 抽象クラス** — AbstractDataProcessorで処理を統一。保守性重視
3. **frozen dataclass** — 定数のイミュータブル保証。Pythonらしい安全設計
4. **Factory Method** — create/save/loadの集約。オブジェクト生成と処理の分離
5. **メソッドチェーン** — FeatureEngineering の宣言的な特徴量追加。可読性向上
6. **直積による体系的生成** — TARGET_COLS × GROUP_COLS × N_RACES。手動定義より網羅的

---

## 次のアクション

### 即座に着手可能
1. **Sharpe比追加** → backtest_bet_engine.pyに1行追加（Tier 2-4、10分で完了）
2. **Optuna方式A実験** → Jupyterでlgb_o.trainを試す（Tier 1-1）

### 既存ロードマップとの対応
| 書籍の知見 | 既存ロードマップ | 優先度変化 |
|-----------|----------------|----------|
| Optuna | 未登録 | **新規追加・高優先** |
| 血統62列 | A-0（血統特徴量） | 変更なし（元からTier 1） |
| point-in-time | A-4（point-in-time化） | 変更なし（元からTier 1） |
| Sharpe比 | 未登録 | **新規追加・中優先** |
| 閾値スイープ | 未登録 | 新規追加・中優先 |

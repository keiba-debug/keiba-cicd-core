# ML v2: デュアルモデル + 前走成績特徴量

**日付**: 2026-02-09
**種別**: モデルアーキテクチャ変更 + 特徴量エンジニアリング

---

## 概要

単一モデルからデュアルモデル（精度/Value）に変更し、前走成績15特徴量を追加。
Value Bet戦略（Model Bの市場独立予測とオッズの乖離）で初めてROI 100%超えを達成。

## 変更内容

### モデルアーキテクチャ
- **Model A（精度）**: 全特徴量（市場系含む）で3着以内を予測
- **Model B（Value）**: 市場系特徴量（odds, popularity, mark_point等）を除外
- **Value Bet**: odds_rank - Model_B_rank >= 3 の乖離を検出

### 特徴量追加 (15個)
| カテゴリ | 特徴量 |
|---------|--------|
| 前走成績 | avg_finish_last3, best_finish_last5, last3f_avg_last3, days_since_last_race |
| 通算成績 | win_rate_all, top3_rate_all, total_career_races, recent_form_trend |
| コース適性 | venue_top3_rate, track_type_top3_rate, distance_fitness |
| クラス/ローテ | prev_race_entry_count, entry_count_change, rating_trend_last3 |
| 調教師 | trainer_top3_rate (マッチ率0.5%、ほぼNaN) |

## 結果

| 指標 | v1 | v2 | 変化 |
|------|-----|-----|------|
| Model A AUC | 0.7936 | 0.7944 | +0.0008 |
| Model B AUC | - | 0.7635 | 新規 |
| 特徴量数 A/B | 17/- | 32/27 | +15 |
| VB gap>=3 ROI | - | 104.7% | 新規 |
| VB gap>=4 ROI | - | 112.1% | 新規 |

## 学び

- **Value Bet戦略が有効**: 市場価格と実力の乖離から利益を得る構造が成立
- **trainer_top3_rateは実質機能していない**: keibabook IDとJVN IDの不一致でマッチ率0.5%
- **horse_history_cache**: 17,335頭、約10,700ファイルを1回ずつ読む方式が効率的
- **rating_deviationがModel B重要度1位**: レーティング偏差（市場情報なし）が実力指標として有力

## ファイル

- `TARGET/ml/scripts/ml_experiment_v2.py`
- `data2/target/ml/ml_experiment_v2_result.json`

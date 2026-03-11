# Multi-Objective Model Design — パフォーマンス変動予測

> **Status**: Phase 1完了（2026-03-09） — ベースラインAcc=49.6%, Macro-F1=0.46
> **目的**: 既存P/W/ARモデルを補完する「パフォ変動予測」を段階的に構築

---

## 1. ゴール

### 最終形
各出走馬に対して、前走比パフォーマンス変動の**確率分布**を出力する：

```
馬名          大幅上昇  上昇    平行線   下降
ドウデュース    1%      30%     60%      9%     → 安定（エントロピー低）
メイショウ      20%     25%     30%     25%     → 読めない（エントロピー高）
```

### 利用方法
1. **P/W/ARモデルへのスタッキング入力** — 変動確率を追加特徴量として投入
2. **Web UI表示** — 確率分布バーで直感的に可視化
3. **bet_engine判断材料** — 「下降確率が高い人気馬」を自動で危険馬判定

---

## 2. ターゲット変数の定義

### 2.1 IDM差分ベース（推奨）

```
target = 当該レースのIDM(SED事後) - 前走のIDM(SED事後)
```

| カテゴリ | IDM差分 | 意味 |
|---------|--------|------|
| 大幅上昇 | >= +8 | 明確な成長・好転 |
| 上昇 | +2 ~ +7 | 穏やかな上昇 |
| 平行線 | -2 ~ +1 | ほぼ同水準 |
| 下降 | <= -3 | パフォーマンス低下 |

> **閾値は要チューニング**: IDM差分の分布を確認して、各カテゴリが概ね 10%/30%/40%/20% 程度になるよう調整

### 2.2 代替案: 着順差分ベース

```
target = 前走着順 - 当該着順  (正=改善)
```

- メリット: シンプル、全レースで利用可能
- デメリット: レースレベル差を反映しない（G1→未勝利の着順改善は無意味）
- → IDMベースの方が優秀。IDMがない場合のfallbackとして検討

### 2.3 訓練/推論の整合性

```
訓練時: 前走IDM(SED) と 当該レースIDM(SED) → 両方事後データ → リーク無し
推論時: 前走IDM(SED) は既知 → OK
         当該レースIDM → 未知（これが予測対象）
```

前走IDMは推論時に既知なので問題なし。当該レースのIDMは「予測結果」なので使わない。

---

## 3. 特徴量設計

### Phase 1: 既存特徴量の流用（最速）

既に `past_features.py` と `jrdb_features.py` にある特徴量をそのまま使える：

| 特徴量 | ソース | パフォ変動との関係 |
|--------|-------|------------------|
| `jrdb_idm_trend` | jrdb_features | 直近IDM - 平均IDM（上昇/下降トレンド） |
| `jrdb_idm_std` | jrdb_features | IDM分散（ムラ度） |
| `jrdb_idm_vs_pre` | jrdb_features | 過去平均IDM - 事前IDM（乖離度） |
| `jrdb_idm_growth` | jrdb_features | 最新IDM - キャリア平均（成長度） |
| `recent_form_trend` | past_features | 着順の改善/悪化トレンド |
| `speed_idx_trend` | speed_features | スピード指数の変化傾向 |
| `finish_std_last5` | past_features | 着順の安定度 |
| `career_stage` | past_features | キャリアフェーズ(0-4) |
| `total_career_races` | past_features | 総走数 |
| `days_since_last_race` | past_features | 休養日数 |
| `distance_change` | past_features | 距離変更 |
| `track_type_change` | past_features | 芝↔ダート変更 |
| `age` | base_features | 年齢 |
| `sire_maturity_index` | pedigree_features | 血統の早熟/晩成傾向 |

→ **これだけで最初の実験は可能**

### Phase 2: キャリア全走特徴量（新規）

`horse_history_cache.json` から全走データを使って新特徴量を作る：

```python
# past_features.py に追加 or 新ファイル career_features.py

# IDMベース（horse_history + JRDB SED IDMを結合が必要）
career_idm_slope         # 全走IDMの線形回帰傾斜（成長速度）
career_idm_std           # 全キャリアIDM標準偏差（ムラ度）
career_best_vs_recent    # ベストIDM - 直近3走平均（ピークからの距離）
career_idm_peak_recency  # ベストIDMが何走前か（ピーク鮮度）

# 着順ベース（IDM不要、horse_historyだけで計算可能）
career_finish_slope      # 着順の線形回帰傾斜
career_consistency       # 着順の変動係数(CV)
career_improvement_runs  # 直近5走中、前走比改善した回数

# コンテキスト
career_class_progression # グレードの推移（昇級/降級トレンド）
career_weight_trend      # 体重の変動トレンド
```

### Phase 3: 血統グローバル特徴量（新規）

`sire_stats` を拡張して産駒のパフォ変動パターンを集計：

```python
# build_sire_stats.py に追加 or 新ビルダー

# 産駒の変動傾向
sire_offspring_idm_variance    # 産駒のIDM分散平均（ムラ馬を出す種馬か）
sire_offspring_peak_age        # 産駒の平均ピーク年齢
sire_offspring_growth_rate     # 2-3歳間のIDM上昇率中央値
sire_offspring_longevity       # 5歳以降のIDM維持率

# 状況適応
sire_distance_switch_impact    # 距離変更時のIDM変動幅
sire_surface_switch_impact     # 芝↔ダート変更時の変動幅
sire_layoff_recovery           # 休養明けのIDM回復率

# BMS（母父）にも同様に適用 → 合計 7×2 = 14 特徴量
```

### Phase 4: 不確実性特徴量

モデルが「振り幅」を学習するための明示的な特徴量：

```python
uncertainty_career_short    # キャリア3走以下フラグ
uncertainty_first_surface   # 初芝/初ダートフラグ
uncertainty_first_distance  # 初距離帯フラグ
uncertainty_first_venue     # 初コースフラグ
uncertainty_long_layoff     # 長期休養(20週+)フラグ
uncertainty_equipment_change # ブリンカー等の装備変更
uncertainty_jockey_change   # 騎手乗替フラグ
uncertainty_class_jump      # 2段階以上の昇級
```

これらの特徴量があると、multiclass softmaxの出力が自然と「確率が分散する」
（例: 初芝の馬 → 大幅上昇と下降の両方に確率が分配される）

---

## 4. モデルアーキテクチャ

### 4.1 単体モデル（Phase 1-2）

```
LightGBM multiclass (num_class=4, objective=multiclass)
  入力: 既存特徴量 + キャリア特徴量
  出力: [P(大幅上昇), P(上昇), P(平行線), P(下降)]
  評価: multi_logloss, confusion matrix, calibration
```

### 4.2 スタッキング統合（Phase 3以降）

```
                    ┌──────────────────┐
                    │ パフォ変動モデル │
                    │  (multiclass)    │
                    └────────┬─────────┘
                             │ [4確率値]
                             ▼
┌─────────┐  ┌─────────┐  ┌─────────────────┐
│ Pモデル  │  │ Wモデル  │  │ ARモデル        │
│(is_top3) │  │(is_win)  │  │(着差回帰)       │
└─────────┘  └─────────┘  └─────────────────┘
  既存169特徴量 + パフォ変動4確率値 = 173特徴量
```

パフォ変動の確率値をP/W/ARの入力特徴量として追加。
「上昇確率が高い馬」がP%やW%で上方修正される効果を期待。

### 4.3 エントロピーベース信頼度（後処理）

```python
import numpy as np

def performance_confidence(proba: list[float]) -> float:
    """確率分布のエントロピーから信頼度を算出"""
    entropy = -sum(p * np.log(p + 1e-9) for p in proba)
    max_entropy = np.log(len(proba))  # 一様分布のエントロピー
    confidence = 1.0 - (entropy / max_entropy)  # 0-1スケール
    return confidence

# 使用例
proba_stable = [0.01, 0.30, 0.60, 0.09]  # confidence ≈ 0.55
proba_unknown = [0.25, 0.25, 0.25, 0.25]  # confidence ≈ 0.00
proba_certain = [0.02, 0.05, 0.90, 0.03]  # confidence ≈ 0.72
```

---

## 5. 実装ロードマップ

### Phase 1: データ調査 + ベースライン（1セッション）

**目標**: IDM差分の分布を確認し、既存特徴量だけでベースラインモデルを構築

1. **IDM差分データの作成**
   - `horse_history_cache` + JRDB SED IDM を結合
   - 全レースのIDM差分(当該 - 前走)を計算
   - 分布を可視化してカテゴリ閾値を決定

2. **ベースラインモデル訓練**
   - `experiment.py` をベースに `experiment_performance.py` を新規作成
   - 既存の全特徴量(169個)をそのまま入力
   - LightGBM multiclass で4クラス分類
   - 評価: accuracy, macro-F1, confusion matrix, calibration plot

3. **結果分析**
   - 特徴量重要度の確認（パフォ変動に効く特徴量は何か）
   - クラスごとの精度差（「下降」は予測しやすいか等）
   - 既存P/W/ARとの相関（独立した情報を持っているか）

**成果物**: ベースライン精度レポート + IDM差分分布分析

### Phase 2: キャリア全走特徴量（1-2セッション）

1. `career_features.py` 新規作成
   - horse_historyから全走IDMを取得（JRDB SED結合が必要）
   - career_idm_slope, career_idm_std, career_best_vs_recent 等
   - 着順ベースの代替特徴量も並行実装

2. 不確実性フラグ特徴量の追加
   - uncertainty_* 系の特徴量を past_features.py に追加

3. モデル再訓練 + Phase 1との比較

**成果物**: キャリア特徴量追加による精度改善レポート

### Phase 3: 血統パフォパターン（1-2セッション）

1. `build_sire_stats.py` 拡張
   - 産駒のIDM変動パターンを集計
   - PIT対応（バックテスト安全性確保）

2. `pedigree_features.py` に変動系特徴量追加

3. モデル再訓練 + Phase 2との比較

**成果物**: 血統特徴量追加による精度改善レポート

### Phase 4: スタッキング統合（1セッション）

1. パフォ変動モデルの出力(4確率値)をP/W/AR入力に追加
2. P/W/ARモデル再訓練
3. バックテストで既存モデルとの比較
   - 的中率向上するか
   - EV計算の精度向上するか
   - Danger Alert の精度向上するか

**成果物**: スタッキング効果レポート + 本番モデル更新判断

### Phase 5: Web UI表示（1セッション）

1. `predict.py` にパフォ変動予測を追加
2. predictions.json に確率分布を出力
3. Web UIに確率分布バー + 信頼度バッジを表示
4. Danger Alert / VBテーブルとの連動

---

## 6. 技術的考慮事項

### リーク防止
- **ターゲット(当該レースIDM)は事後データ** → 訓練時のみ使用、推論時は使わない
- **前走IDMは推論時に既知** → 特徴量として安全
- **PIT**: キャリア全走特徴量は `race_date` でフィルタ済み（既存パターンに従う）

### クラス不均衡
- 「大幅上昇」は少数派（推定10%以下）
- LightGBM `class_weight='balanced'` or `is_unbalance=True`
- 少数クラスのF1に特に注意

### 評価指標
- **primary**: multi_logloss（確率分布の質を測る）
- **secondary**: macro-F1, 各クラスF1, calibration
- **実用指標**: スタッキング後のP/W/AR精度変化

### モデルサイズ
- 独立モデルなので既存パイプラインに影響しない
- `model_perf.txt` として `data3/ml/` に保存
- 推論コスト: 1回の追加LightGBM predict（<100ms）

---

## 7. 将来の拡張（Phase 6+）

### 他のサブモデル候補

| サブモデル | ターゲット | データ有無 | 難易度 | P/W/AR補完度 |
|-----------|-----------|----------|--------|-------------|
| **パフォ変動** | IDM差分4クラス | ✅ JRDB SED | ★★☆ | ◎ 高い |
| 上がり3F予測 | last_3f回帰 | ✅ horse_history | ★★☆ | ○ 中程度 |
| 先行争い予測 | 1角順位 | ✅ corners[0] | ★★☆ | ○ 中程度 |
| 出遅れ予測 | deokure flag | ✅ JRDB SED | ★☆☆ | △ 限定的 |
| ペース予測 | RPCI回帰 | ✅ race単位 | ★★★ | ○ 中程度 |
| 隊列予測 | 4角順位 | ✅ corners[3] | ★★★ | ◎ 高い |

### 統合アーキテクチャ（最終形）

```
Sub-models (Phase 1-3 各モデル):
  パフォ変動  → [4確率値]
  上がり3F    → [予測タイム]
  先行争い    → [1角順位予測]
  ペース      → [RPCI予測]
       ↓ 全出力を結合
  ┌─────────────────────────────┐
  │ P/W/AR メインモデル         │
  │ 169既存 + サブモデル出力    │
  └─────────────────────────────┘
```

---

## 8. 参考: 既存データの活用度

```
✅ 即使用可能:
  - horse_history_cache.json (36,585馬の全走データ)
  - JRDB SED IDM (過去走IDM)
  - sire_stats (血統統計)
  - 既存169特徴量

⚡ 要加工:
  - horse_history × JRDB SED結合 (IDM全走歴)
  - sire_stats拡張 (変動パターン集計)
  - 不確実性フラグ計算

❌ 未取得:
  - なし（必要なデータは全て手元にある）
```

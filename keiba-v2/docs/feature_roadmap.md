# KeibaCICD 特徴量ロードマップ

**独自分析指標の特徴量化 — 構想と未実装仕様**

最終更新: 2026-02-22 (Session 43)

> 現行モデル構成・実装済み特徴量は → [models_and_features.md](./models_and_features.md)
> チャクラ(能力予測)の将来設計は → [ml-target-design.md](../../docs/ml-target-design.md) ※memory参照

---

## 1. 戦略的背景

### なぜ独自特徴量が必要か

JRA-VANの生データは公開情報。同じデータをそのまま投入するだけでは差別化が困難。

現在の gap + チャクラmarginフィルタは有効（Win ROI 119.9%）だが、「**なぜgapが生まれるのか**」の構造的な説明が不足。独自分析で中間指標を生成し、市場の歪みを構造的に捕らえることが次の精度向上の核心。

### 設計原則

1. **1馬1レースあたり1数値** — モデル投入には数値化が必須
2. **相対値** — その馬にとっての偏差、レース内での相対位置
3. **学習=推論の同一ロジック** — データリーク防止
4. **サンプル不足時のフォールバック** — ベイズ平滑化で全体平均に引き戻す

---

## 2. Phase一覧と実装ステータス

| Phase | テーマ | ステータス | 主な特徴量 |
|-------|--------|-----------|-----------|
| **0** | 障害レース除外 | ⚠️ 未着手 | フィルタ追加のみ |
| **1** | 調教偏差スコア | 🔶 部分実装 | training_deviation, trainer_pattern_score, course_change_flag |
| **2** | レベル落差スコア | 🔶 部分実装 | prev_race_level(mean値), current_race_level, level_drop_score |
| **3** | ラップタイプ適性 | 🔶 部分実装 | predicted_race_type, horse_sprint/sustained_score, type_match_score |
| **4** | 展開負けスコア | ⚠️ 未着手 | hidden_perf_score, agari_rank_vs_finish, pace_disadvantage_flag |

🔶 = 関連する特徴量が既に実装されているが、ここで定義する中間指標は未実装

---

## 3. Phase 0: 障害レース除外

**優先度: 高** | **依存: なし** | **工数: 小**

障害レースは平地とは別競技（飛越能力・落馬リスクが支配的）。全体の約5%。除外で平地モデルのノイズ削減。

**対応:** experiment.py / predict.py でフィルタ追加のみ。

---

## 4. Phase 1: 調教偏差スコア

**依存: なし** | **データソース:** training_summary.json, training_analysis.json, trainer_patterns.json

### 実装済み（models_and_features.md参照）

| 特徴量 | 現行名 | 備考 |
|--------|--------|------|
| training_lap_rank | ck_laprank_score | LAPRANK_SCORES で16段階数値化済み |
| training_time_rank | ck_time_rank | 1〜5段階 |

### 未実装

#### 4.1 training_deviation（調教偏差）

馬ごとの過去N走平均lapRankからの偏差。普段Bの馬が今回Aなら正=仕上げ良好。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | -5〜+5（想定） |
| 欠損時 | 0（偏差なし） |
| 算出 | 今回lapRankスコア − 直近5走平均lapRankスコア |
| 前提条件 | **過去のtraining_summary蓄積が必要**（現在は当日分のみ） |
| リーク対策 | 過去走のみ。当日走は除外。 |

#### 4.2 trainer_pattern_score（調教師パターン一致度）

調教師のbest_patternとの一致度。trainer_patterns.json の lift を利用。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | 0〜1（lift正規化後） |
| 欠損時 | 0 |
| 算出 | best_patternsの条件と今回調教のマッチ → 該当liftを採用（複数一致時は最大値） |

#### 4.3 course_change_flag（調教コース変更）

調教コース種別の変化（コース→坂路等）。

| 項目 | 内容 |
|------|------|
| 型 | int (0/1) |
| 値域 | 0=変化なし, 1=変化あり |
| 欠損時 | 0 |
| ソース | training_summary.json: weekendLocation, weekAgoLocation |

### Phase 1 未解決事項
- [ ] training_summary.json の過去分蓄積仕組み（training_deviationの前提）
- [ ] trainer_patterns.json の pattern name と training_summary のマッチングロジック

---

## 5. Phase 2: レベル落差スコア（降格ローテ）

**依存: なし** | **データソース:** rating_standards.json, horse_history

### 実装済み

| 特徴量 | 現行名 | 備考 |
|--------|--------|------|
| グレード差（序数） | prev_grade_level, grade_level_diff | ordinalスケール (G1=1〜新馬=10) |
| 会場ランク差 | venue_rank_diff | 市場系扱い |
| 降格ローテ7パターン | is_koukaku_* | Session 33実装 |

### 未実装

#### 5.1 prev_race_level（レーティングmean値）

前走のレースレベルをrating_standards.jsonのmean値で定量化。ordinalより情報量が多い。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | 50〜68（未勝利50.68〜G1古馬67.81） |
| 欠損時 | 全体中央値（約55） |
| ソース | rating_standards.json: by_grade[grade].rating.mean |
| 前提 | by_gradeキー（G1_古馬等）とDB gradeのマッピング |

#### 5.2 current_race_level（今回レースレベル）

今回のレースレベル。グレードmean or 出走メンバーから推定。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | 50〜68 |
| 欠損時 | グレードmeanで代替 |
| リーク | 出走表確定後であれば問題なし |

#### 5.3 level_drop_score（レベル落差）

prev_race_level − current_race_level。正=今回の方がレベル低い=有利。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | -15〜+15 |
| 欠損時 | 0 |

#### 5.4 competitiveness_score（混戦度）

mean_race_stdevの相対値。高値=混戦=単勝が読みにくい。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | 1.5〜2.7 |
| ソース | rating_standards.json: competitiveness.mean_race_stdev |

#### 5.5 venue_level_offset（会場レベル偏差）

競馬場×芝/ダのレベル偏差（東京芝 > 小倉芝 等）。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | -2〜+2（全体平均からの偏差） |
| ソース | rating_standards.json: venue_stats |

### Phase 2 未解決事項
- [ ] rating_standards.json の by_grade キーと DB grade のマッピング表
- [ ] 今回レースレベルを出走メンバーから推定する場合の計算コスト

---

## 6. Phase 3: ラップタイプ適性

**依存: なし** | **データソース:** race_trend_index.json, race_type_standards.json, horse_history

### 実装済み

| 特徴量 | 現行名 | 備考 |
|--------|--------|------|
| 前走のtrend_v2 | (pace_features内で使用) | TREND_V2_ENCODE で数値化 |
| タイプ別複勝率 | best_trend_top3_rate, worst_trend_top3_rate | 直近走のtrend_v2別集計 |
| 適性ばらつき | trend_versatility | 標準偏差 |

### 未実装

#### 6.1 predicted_race_type（レースタイプ事前推定）

コース×距離 + 出走頭数補正でRPCIを推定 → thresholds でタイプ判定。

| 項目 | 内容 |
|------|------|
| 型 | int（7カテゴリ数値化） |
| 値域 | sprint=0〜sustained_doroashi=6 |
| ソース | race_type_standards.json: thresholds, runner_adjustments |
| 前提 | predict.py実行時の出走頭数取得 |

#### 6.2 horse_sprint_score / horse_sustained_score

瞬発戦/持続戦での過去成績スコア。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | 0〜1（複勝率、ベイズ平滑化） |
| 欠損時 | 0.5（中立） |
| ソース | race_trend_index.json + horse_history |

#### 6.3 type_match_score

predicted_race_type × 馬の適性のマッチ度。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | 0〜1 |
| 欠損時 | 0.5 |
| 算出 | sprint系→sprint_score、sustained系→sustained_score を重視 |

#### 6.4 similar_course_score

race_type_standards.json の similar_courses を参照した類似コース成績。

### Phase 3 未解決事項
- [ ] 馬×タイプ別成績の集計テーブルの更新タイミングとストレージ設計
- [ ] race_type_standards.json の similar_courses キーの構造確認
- [ ] predicted_race_type 算出時の出走頭数取得タイミング

---

## 7. Phase 4: 展開負けスコア

**依存: Phase 3** | **データソース:** race_trend_index.json, horse_history

### 実装済み（関連）

| 特徴量 | 現行名 | 備考 |
|--------|--------|------|
| 上がり速いのに着外率 | l3_unrewarded_rate_last5 | 類似コンセプト |

### 未実装

#### 7.1 hidden_perf_score（展開負けスコア）

着順以上の能力発揮度。瞬発戦で上がり最速級だが着外 → 展開負けの可能性。

| 項目 | 内容 |
|------|------|
| 型 | float |
| 値域 | 0〜1（正規化） |
| 欠損時 | 0 |

```python
# 概念ロジック
if (
    trend_v2 in ['sprint', 'sprint_mild']  # 瞬発戦
    and agari_rank <= 2                      # 上がり最速級
    and finish_position >= 4                 # 着順は凡走
    and corner4_position >= 10               # 4角後方
):
    hidden_performance_score = high
```

#### 7.2 agari_rank_vs_finish（上がり順位−着順乖離）

| 項目 | 内容 |
|------|------|
| 型 | int |
| 値域 | -17〜+17（正=脚を使ったが届かなかった） |
| 欠損時 | 0 |
| 算出 | agari_rank − finish_position |

#### 7.3 pace_disadvantage_flag（ペース不利フラグ）

| 項目 | 内容 |
|------|------|
| 型 | int (0/1) |
| 算出 | trend_v2 in [sprint, sprint_mild] & corners[0] >= 10 → 1 |

### VBとの関連性

展開負けスコアが高い馬は次走で展開が向けば巻き返す確率が高い。オッズは前走着順に引きずられるため過小評価されやすい。**gap + チャクラmargin + hidden_perf の3軸フィルタ**で、より精度の高いVB検出が期待できる。

### Phase 4 未解決事項
- [ ] 上がり3F順位（agari_rank）の算出方法 — 同レース全馬のlast_3fが必要
- [ ] 4角通過位置 — horse_history.corners[3] で取得可能か確認
- [ ] hidden_perf_score をbet_engineフィルタにするか、特徴量にするか

---

## 8. 芝/ダート分割の検討

| 対象 | 優先度 | 理由 |
|------|--------|------|
| 障害レース | 高 | 平地とは別競技。除外でノイズ削減 |
| 芝 vs ダート | 中 | 重要特徴量の優先順位が異なるが、LightGBMが内部分岐可能 |

芝/ダート分割は実験で効果検証後に判断。

---

## 9. パイプライン設計

### 実装パターン

```python
# 統一パターン: ml/features/{theme}_score.py
class ThemeScoreGenerator:
    def __init__(self, analysis_data):
        self.data = analysis_data

    def compute_score(self, horse_id, race_id) -> dict:
        """1馬1レースのスコアを算出"""
        return {'feature_name': value, ...}

    def batch_generate(self, entries) -> pd.DataFrame:
        """バッチ生成（学習データ構築用）"""
        ...
```

### ファイル構成（想定）

```
ml/features/
├── (既存10モジュール)
├── training_score.py   # Phase 1: 調教偏差
├── race_level.py       # Phase 2: レベル落差
├── lap_type.py         # Phase 3: ラップタイプ適性
└── hidden_perf.py      # Phase 4: 展開負け
```

### bet_engine への影響

新特徴量はモデル精度向上を通じて間接的にbet_engineに影響。フィルタロジック（gap + margin）の変更は不要。将来的に hidden_perf_score を直接フィルタに追加する可能性はバックテスト結果次第。

---

## 10. 検証方法

各Phaseは独立検証可能。1指標ずつ追加してバックテストで確認。

- **バックテストROI**: bet_engine + 新特徴量モデルでROI改善するか
- **ECE**: キャリブレーション精度の維持
- **特徴量重要度**: LightGBMのfeature importanceで上位に入るか
- **gap相関分析**: 新スコアとgapの相関

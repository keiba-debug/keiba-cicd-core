# vega-niigata1000 ルールエンジン v0.2 設計書

> 作成: 2026-05-09
> v0.1 → v0.2 改訂: 設計レビュー指摘5点反映（スコア空間/リーク防止/除外仕様/データ辞書/重複加点）
> ステータス: 設計確定 / Phase 3a 実装待ち
> 関連: [Phase 1検証レポート](../ml-experiments/v8.x_vega_niigata1000_phase1_verification.md), [Phase 2強馬予測](../ml-experiments/v8.x_vega_niigata1000_phase2_strong_horse.md)

---

## 1. 概要・目的

### 1.1 プロジェクト全体
新潟芝1000M直線（千直）に特化した予想分析エンジン。

### 1.2 当初の構想と転換
- 当初: polaris から独立した千直専用LightGBM
- **転換理由**: Phase 1検証で判明
  - 学習可能サンプル約70R（JRDB完全データ）で独立LightGBMは過学習リスク
  - 2023年以降に枠順×脚質バイアスが変化する **年代非定常性**
  - 一方で枠順・血統・厩舎・騎手の **明確なROI差** がデータで裏付け
- **結論**: 独立MLではなく、**polaris + 千直バイアス補正レイヤー（ルールエンジン）** で実装

### 1.3 v0.1 の目的
1. Phase 1+2 検証の発見をルール化し、polaris予測値を補正
2. 各馬に「**なぜこのスコアか**」を完全に説明できるトレース生成
3. polaris単独ROIに対する明確な改善（バックテスト実証）
4. WebUI（コース事典・odds-race）への入力源

---

## 2. アーキテクチャ全体図

```
[出走馬リスト + race context]
        ↓
[polaris 予測値（既存）= pred_proba_p ∈ [0,1]]──┐
        ↓                                        │
[RuleEngine v0.2]                                 │
        ↓                                        │
        ├─ STEP A: 環境補正（race-level）         │
        ├─ STEP B: 枠順分岐                       │
        │   ├─ 外枠ルート (6-8)                   │
        │   └─ 内枠救済ルート (1-2) → B'          │
        ├─ STEP C: 馬本体評価                     │
        │   ├─ C-1 血統                          │
        │   ├─ C-2 過去走脚質                    │
        │   └─ C-3 属性                          │
        ├─ STEP D: 関係者評価                     │
        ├─ STEP E: ローテ評価                     │
        └─ STEP F: 警戒/除外                      │
        ↓                                        │
[rule_logit (logit空間) + 説明トレース + is_rejected]│
        ↓                                        ↓
        └─[統合: sigmoid(logit(p) + rule_logit)]─┘
        ↓
[display_score (UI), selection_score (ランキング)]
+ 説明文 + 信頼度 + is_rejected
```

---

## 3. STEP 詳細仕様（加減点は **logit空間値**）

### 3.0 加減点単位の換算（参考）

logit空間値とその典型的な確率空間効果（基底確率別）：

| logit加減点 | p=0.10 → | p=0.20 → | p=0.40 → | 効果分類 |
|---:|---:|---:|---:|---|
| +1.00 | 0.23 (+0.13) | 0.40 (+0.20) | 0.65 (+0.25) | 強加点 |
| +0.50 | 0.15 (+0.05) | 0.29 (+0.09) | 0.52 (+0.12) | 中加点 |
| +0.20 | 0.12 (+0.02) | 0.23 (+0.03) | 0.45 (+0.05) | 弱加点 |
| -0.50 | 0.06 (-0.04) | 0.13 (-0.07) | 0.29 (-0.11) | 中減点 |

→ 強い条件は logit ±0.6〜1.0、弱条件は ±0.1〜0.3 が目安

### STEP A: 環境補正（race-level、馬独立）

レース全体で1度計算。後続STEPの分岐条件として使う：

| 変数 | 出所 | 値域 |
|---|---|---|
| `track_condition_grp` | race.track_condition | "良" / "稍重以上" |
| `era` | race.date | "2020-2022" / "2023-2026" |
| `is_full_field` | race.num_runners >= 16 | bool |
| `race_type` | race.grade / race_name | "G3アイビスSD" / "OP" / "条件戦" |

加減点なし（条件変数のみ）。

### STEP B: 枠順分岐

`wakuban` で大きく分岐：

| wakuban | base_logit | コメント |
|---|---:|---|
| 8 | +0.50 | 圧倒的最強枠 |
| 7 (era=後期) | +0.50 | 後期7枠ROI 107% |
| 7 (era=前期) | +0.25 | |
| 6 | +0.20 | 中間枠 |
| 3-5 | -0.10 | 中弱 |
| 1-2 | → STEP B' へ | 内枠救済ルート分岐 |

**条件追加**:
- `track_condition_grp == "稍重以上"` AND `wakuban >= 7` → さらに **+0.20**

### STEP B': 内枠救済（1-2枠の場合のみ、択一適用）

```
if past_choku_top3_rate >= 0.5 AND niigata_1000m_count >= 2:
    base = +0.25  # 過去千直巧者
elif past_corner_first_avg_5 < 4.0:
    base = +0.10  # 先行型は内ラチ走り抜けの可能性
else:
    base = -0.40  # 内枠×実力不明（強い割引）
```

⚠️ B' は `base` 設定。STEP C-1 の血統加点とは独立に積み上げる。

### STEP C: 馬本体評価

各サブSTEP内で **クリップ上限** あり（後述）。

#### C-1: 血統（合計クリップ ±0.50）
| 条件 | logit加減点 |
|---|---:|
| `sire_name == "ロードカナロア"` | +0.30 |
| `sire_name == "ビッグアーサー"` | +0.25 |
| `sire_name in {"ダイワメジャー", "スクリーンヒーロー", "ディスクリートキャット"}` | +0.20 |
| `sire_line == "キングカメハメハ系" AND sex == "牝"` | +0.25 |
| `sire_line == "サンデー系" AND sex == "牡"` | -0.15 |
| `bms_line == "キングカメハメハ系"` | +0.15 |
| `sire_name in {"キンシャサノキセキ", "モーリス", "キズナ"}` | -0.10 |

`TOP_SIRE_LIST = {"ロードカナロア", "ビッグアーサー", "ダイワメジャー", "スクリーンヒーロー", "ディスクリートキャット"}`

#### C-2: 過去走脚質（合計クリップ ±0.30）
| 条件 | logit加減点 |
|---|---:|
| `past_corner_first_avg_5 <= 4.0` | +0.15 (先行型) |
| `past_last_3f_min_5 <= 33.5` | +0.15 (末脚ベスト速い) |
| 上記2つ両立 | +0.10 (強馬候補ボーナス) |
| `past_corner_first_avg_5 >= 8.0` | -0.10 (追込型は不利) |

#### C-3: 属性（合計クリップ ±0.15）
| 条件 | logit加減点 |
|---|---:|
| `age == 3 AND sex == "牝"` | +0.10 |
| `age >= 7` | -0.10 |
| `sex == "セン"` | -0.10 (近年弱い) |

### STEP D: 関係者評価（合計クリップ ±0.60）

#### D-1: コンビ判定
| 条件 | logit加減点 |
|---|---:|
| (jockey, trainer) == ("菊沢一樹", "菊沢隆徳") | +0.40 |
| その他「千直得意騎手×千直得意厩舎」一致 | +0.20 |

#### D-2: 騎手単独
| 条件 | logit加減点 |
|---|---:|
| `jockey_choku_strong_rate >= 0.25` (鮫島・荻野・丹内・三浦・佐々木) | +0.20 |
| `jockey_name == "永島まなみ" AND wakuban >= 6` | +0.25 |
| `jockey_choku_top3_rate >= 0.30 AND jockey_choku_n >= 30` | +0.15 |
| `jockey_choku_top3_rate < 0.10 AND jockey_choku_n >= 15` | -0.10 |

#### D-3: 厩舎単独
| 条件 | logit加減点 |
|---|---:|
| `trainer_choku_strong_rate >= 0.25` (斎藤誠・嘉藤貴行・菊沢隆徳・鈴木伸尋・竹内正洋) | +0.20 |
| `trainer_choku_top3_rate >= 0.30 AND trainer_choku_n >= 15` | +0.15 |

### STEP E: ローテ評価（合計クリップ ±0.30）

| 条件 | logit加減点 |
|---|---:|
| `prev_distance in (1000, 1100, 1200)` | +0.10 |
| `prev_distance >= 1700` | -0.15 |
| `prev_finish in (4, 5)` | +0.20 (巻き返し穴) |
| `prev_finish == 1 AND prev_distance <= 1200` | -0.10 (過剰人気) |
| `35 <= days_since_prev <= 56` | +0.10 (中5-8週) |
| `days_since_prev >= 91` | -0.20 (休み明け弱い) |

### STEP F: 警戒/除外フィルター（**緩い**方針）

REJECT 条件（OR）:
1. `niigata_1000m_count >= 3 AND niigata_1000m_top3_count == 0` (千直3戦以上で全敗)
2. `age >= 8 AND prev_finish >= 6` (高齢×前走凡走)
3. `sire_line == "サンデー系" AND sex == "牡" AND age >= 5 AND past_short_count == 0` (サンデー牡×古馬×短距離未経験)

REJECT 馬は `is_rejected = true` 立てる。**display_score は計算するが、selection_score は None**（次節）。

### 全体クリップ
```
total_rule_logit ∈ [-1.5, +2.0]  (ハード上限)
```

---

## 4. polaris との統合（logit空間加算 + 除外）

### 4.1 統合関数

```python
import math

def integrate(polaris_p: float, rule_logit: float, is_rejected: bool) -> dict:
    # polaris確率を logit に変換
    p_clipped = max(min(polaris_p, 0.999), 0.001)
    polaris_logit = math.log(p_clipped / (1 - p_clipped))

    # logit 空間で加算
    final_logit = polaris_logit + rule_logit

    # sigmoid で確率に戻す
    display_score = 1 / (1 + math.exp(-final_logit))

    # 除外時は selection_score を None に
    selection_score = None if is_rejected else display_score

    return {
        "display_score": display_score,
        "selection_score": selection_score,
        "polaris_p": polaris_p,
        "rule_logit": rule_logit,
        "final_logit": final_logit,
        "delta_p": display_score - polaris_p,  # 説明文用
        "is_rejected": is_rejected,
    }
```

### 4.2 スコア仕様（API契約）

| フィールド | 型 | 用途 | 除外時 |
|---|---|---|---|
| `display_score` | float [0,1] | UI表示、常に計算 | 値あり（補正後の確率） |
| `selection_score` | float [0,1] or None | ランキング、バックテスト | **None**（母集団から除外） |
| `is_rejected` | bool | 除外フラグ | true |
| `delta_p` | float | 「補正幅 +X.X%」表示用 | 計算可能 |

### 4.3 バックテスト時のルール
- 推奨上位N頭の選定: `selection_score is not None` でフィルタ → top-N
- ROI計算: `selection_score` が None の馬は買わない扱い
- UIランキング: `display_score` で並び（除外馬も「除外推奨」で表示）

---

## 5. 加減点キャリブレーション（ハイブリッド）

### 5.1 強条件（命中率差駆動、自動算出）
対象: 出走数50以上 or ROI 100%超の条件

スコアの数学的単位は **3着内率の logit差**（確率予測モデルとの統合のため）。
ROI（収支）はスクリーニング条件として使うが、加減点の大きさは命中率差で決定する。

```
condition_p = 条件成立時の 3着内率
overall_p   = 全体の 3着内率
rule_logit  = logit(condition_p) - logit(overall_p)
clip rule_logit to [-1.0, +1.0]
```

例: 8枠 3着内 36.6% / 全体 18.1% → logit(0.366) - logit(0.181) = -0.549 - (-1.510) = +0.961 → clip +1.0

#### ROI差からの参照式（参考）
ROI差はスコアサイズの妥当性チェックに使う：
```
roi_diff = (条件成立時 単勝ROI) - (全体 単勝ROI)
# 例: 父ロードカナロア ROI 179% / 全体 60% → diff +119pt
# 命中率差駆動の rule_logit と ROI差の符号が一致することを確認
```
ROI差と命中率差の符号が逆の場合は、人気バイアスが効いている可能性があるため再キャリブ対象。

### 5.2 弱条件（手動設定）
ROI差不明確 / サンプル30未満 → v0.2 では手動設定、運用後に再キャリブ。

### 5.3 キャリブレーションスクリプト（Phase 3b）
`analysis/niigata1000/calibrate_rule_score.py`
- 検証レポートCSV → ROI差テーブル
- 強条件は自動算出、弱条件は YAML から読込
- 結果を `rule_definitions_v0_2.yaml` に出力

---

## 6. 説明文生成（詳細レベル）

### フォーマット

```
🐎 [umaban]番 [horse_name]（[sex_label][age]歳）
   polaris: [polaris_p×100:.1f]% → 千直補正 [delta_p×100:+.1f]% → 最終: [display_score×100:.1f]%
   信頼度: [confidence_label]   {"⚠️除外推奨" if is_rejected else ""}

   STEP B (枠順): [base_explanation]
     [✅/⚠️] [detail]                logit [score:+.2f]  (≈ +X.X%)
   STEP C-1 (血統):
     [✅/⚠️] [detail]                logit [score:+.2f]  (≈ +X.X%)
   STEP C-2 (過去走脚質): ...
   STEP D (関係者): ...
   STEP E (ローテ): ...
   ─────────────
   合計: logit [rule_logit:+.2f]  (≈ [delta_p×100:+.1f]%)
```

### ルール定義 YAML スキーマ

```yaml
- id: frame_8
  step: B
  condition: "wakuban == 8"
  logit_score: +0.50
  explanation: "枠8（外枠最強、3着内36.6%）"
  source: "Phase 1 §1 全体集計"
- id: koudou_kanaroa
  step: C-1
  condition: "sire_name == 'ロードカナロア'"
  logit_score: +0.30
  explanation: "父ロードカナロア（千直ROI 179%、3着内27.6%）"
  source: "Phase 1 §6 個別父馬ランキング"
```

---

## 7. 信頼度計算（サンプル数ベース）

```python
def compute_confidence(features) -> str:
    sample_sizes = [
        features.total_career_races_at_cutoff,         # 馬の通算経験
        features.niigata_1000m_count_at_cutoff + 5,    # 千直経験（未経験は base 5）
        features.sire_recent_2y_runs,                   # 父の直近2年出走
        features.trainer_recent_2y_runs,                # 厩舎の直近2年出走
        features.jockey_recent_2y_runs,                 # 騎手の直近2年出走
    ]
    min_sample = min(sample_sizes)
    if min_sample >= 30:
        return "高"
    elif min_sample >= 10:
        return "中"
    else:
        return "低"
```

---

## 8. リーク防止規約（v0.2 改訂版）

### 8.1 全特徴量に `cutoff_date` 必須引数

```python
def compute_jockey_choku_strong_rate(jockey_code: str, cutoff_date: str) -> float:
    """
    cutoff_date 未満（< cutoff_date）の千直レースのみで集計。
    cutoff_date 当日は **含めない**。
    """
    ...
```

### 8.2 月次スナップショット + 当月内差分集計（同月内リーク防止）

**v0.1 の問題**: 「月次集計表参照」だけだと同月内の未来レース混入。

**v0.2 修正**:

```python
def jockey_choku_strong_rate(jockey_code, cutoff_date):
    cutoff = parse_date(cutoff_date)
    cutoff_2y = cutoff - timedelta(days=730)  # 直近2年窓の開始日

    # 1. 前月末までの月次スナップショット（事前計算済み、不変）
    #    スナップショット側で「snapshot_date - 2年 〜 snapshot_date」で集計済み
    #    cutoff の前月末スナップショットを参照することで、自動的に 2年窓に収まる
    base_month = (cutoff.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    base_stats = monthly_snapshot[base_month]  # {n, strong_count} 直近2年集計済み

    # 2. 当月初〜cutoff_date 未満の差分集計（リアルタイム）
    #    cutoff_2y も適用して、月をまたいで2年窓から外れた古いレースを除外
    month_start = cutoff.replace(day=1)
    delta_window_start = max(month_start, cutoff_2y)  # ★ 2年窓を適用
    delta_runs = aggregate_choku_runs(
        jockey_code=jockey_code,
        date_range=(delta_window_start, cutoff),  # 開始 <= date < cutoff
    )

    # 3. base が含む「2年窓から外れた古いレース」を控除
    #    snapshot_date 時点では 2年窓内だが、cutoff 時点では窓外になったレース
    expired_runs = aggregate_choku_runs(
        jockey_code=jockey_code,
        date_range=(base_stats["snapshot_window_start"], cutoff_2y),
    )

    # 4. 統合: base + delta - expired
    total_n = base_stats["n"] + delta_runs["n"] - expired_runs["n"]
    total_strong = base_stats["strong"] + delta_runs["strong"] - expired_runs["strong"]

    if total_n < 5:  # サンプル閾値（信頼度に反映）
        return None
    return total_strong / total_n
```

**実装ポイント**:
- 月次スナップショットは「snapshot_date 時点で直近2年」で集計済み
- 当月内 delta は **cutoff_2y 以降のみ** 集計（古いレース混入防止）
- 月をまたいで2年窓から外れた expired を base から控除（窓のスライド対応）

### 8.3 集計窓（v0.2 確定）

| 統計対象 | 窓 |
|---|---|
| 騎手の千直成績 | **直近2年ローリング** |
| 厩舎の千直成績 | 直近2年ローリング |
| 父の千直成績 | 直近2年ローリング |
| 母父の千直成績 | 直近2年ローリング |
| 当該馬の千直成績 | 全期間（馬個別、サンプル少のため） |
| 当該馬の前走情報 | 直近1走 |
| 当該馬の過去5走脚質 | 直近5走 |

### 8.4 検証用テストケース（Phase 3a で実装）
- リーク防止テスト: 各特徴量関数で `cutoff_date` を変えて結果が変わることを確認
- 同月内リーク防止: cutoff_date を月内中旬に設定し、月末レースのデータが入らないことを確認

---

## 9. 実装フェーズ分け

### Phase 3a: データ準備層
- `analysis/niigata1000/features.py` - cutoff_date 必須の特徴量計算関数群
- `analysis/niigata1000/snapshot_builder.py` - 月次スナップショット事前計算
- `analysis/niigata1000/data_dictionary.md` - データ辞書（§14準拠）
- リーク防止テストケース

### Phase 3b: RuleEngine v0.2 コア
- `analysis/niigata1000/rules/v0_2_definitions.yaml` - ルール定義
- `analysis/niigata1000/rule_engine.py` - RuleEngine クラス
- `analysis/niigata1000/calibrate_rule_score.py` - 自動キャリブレーション
- `analysis/niigata1000/integrator.py` - polaris統合関数
- `analysis/niigata1000/explainer.py` - 説明文ジェネレータ

### Phase 3c: バックテスト
- 過去135Rで polaris単独 vs polaris+rule の比較
- ROI/3着内率/各STEPの寄与度分解
- レポート: `docs/ml-experiments/v8.x_vega_niigata1000_phase3_backtest.md`

### Phase 3d: WebUI連携
- `/odds-race` 千直開催時の千直アイコン表示
- `/demo/course/niigata-1000m` コース事典ページ
- 説明文 inline 展開
- 信頼度バッジ表示

---

## 10. 検証・バックテスト方針

### 比較対象
1. polaris単独
2. polaris + rule (v0.2)
3. ルール単独（参考、ROIだけ）

### 指標
- 上位3頭推奨の3着内率
- 単勝ROI / 複勝ROI
- 信頼度別精度（高/中/低の各セグメント）
- 除外馬の3着内率（除外が妥当だったか）

### 訓練/テスト分割
- 時系列split: 2020-2024 → 2025-2026
- 全特徴量で `cutoff_date` 厳守

### 失敗判定基準
- polaris単独からROIが悪化したら → ルール再キャリブ or 除外
- 説明文が不自然と判断されたら → ルール削除

---

## 11. データソース一覧

| データ | 場所 | 用途 |
|---|---|---|
| レース JSON | `data3/races/YYYY/MM/DD/race_*.json` | 基本情報、結果、JRDB事前指標 |
| horse_history_cache | `data3/ml/horse_history_cache.json` (248MB) | 過去走履歴 |
| pedigree_index | `data3/indexes/pedigree_index.json` | 父/母/母父ID |
| sire_stats_index | `data3/indexes/sire_stats_index.json` | 父・母父名・統計 |
| polaris予測 | `data3/races/YYYY/MM/DD/predictions_polaris-2.0.json` | `entries[].pred_proba_p` 等 |

### polaris予測スキーマ（実コード確認済み）
```
races[].entries[]:
  pred_proba_p: 複勝予測確率 [0,1]
  pred_proba_p_raw: raw値
  pred_proba_w: 単勝予測確率
  pred_proba_w_cal: calibrated版
```

→ **`pred_proba_p` を統合関数の入力**として使用（複勝予測ベース）

---

## 12. 残課題・将来拡張

### v0.3 候補
- 風データ取得（向かい風/追い風）
- パドック評価
- 当日オッズ動向（急騰馬/急落馬）
- ルールの自動学習（強化学習的アプローチ）

### Web可視化
- **分析結果ページ** (ユーザーアイデア): Phase 1+2 検証結果のリッチHTMLダッシュボード化
- 父・厩舎・騎手の強馬率インデックス（時系列）

---

## 13. 確定設計まとめ（v0.2）

| 項目 | 確定内容 |
|---|---|
| アーキテクチャ | STEP A〜F の階層構造 |
| polaris統合 | **logit空間加算**: `sigmoid(logit(p) + rule_logit)` |
| polaris出力 | 確率 [0,1]（実コード確認済み: `pred_proba_p`） |
| 加減点単位 | **logit空間値**（±0.1〜1.0レンジ） |
| 説明文 | 全加減点を詳細表示（logit値 + 確率差換算） |
| 加減点キャリブ | ハイブリッド（強条件 ROI差自動、弱条件 手動） |
| 除外仕様 | **display_score（常時）/ selection_score（除外時None）分離** |
| 信頼度 | サンプル数ベース（高/中/低） |
| リーク防止 | `cutoff_date` 必須、**月次スナップショット + 当月内差分集計** |
| 集計窓 | **直近2年ローリング**（騎手/厩舎/父/母父） |
| クリップ | STEP内（C-1: ±0.50, D: ±0.60 等）+ 全体 [-1.5, +2.0] |

---

## 14. データ辞書（v0.2 新設）

### 14.1 馬個別特徴量

| 列名 | 型 | 定義 | 算出式 | 算出窓 | 欠損時 | リーク対策 |
|---|---|---|---|---|---|---|
| `total_career_races_at_cutoff` | int | 該当日付前の通算出走数 | `len([r for r in runs if r.race_date < cutoff])` | 全期間 | 0 | cutoff必須 |
| `niigata_1000m_count` | int | 過去千直出走回数 | `len([r for r in past_runs if r.is_choku])` | 全期間 | 0 | cutoff必須 |
| `niigata_1000m_top3_count` | int | 過去千直3着内回数 | 上記の中で finish_position <= 3 | 全期間 | 0 | cutoff必須 |
| `past_choku_top3_rate` | float | 過去千直3着内率 | top3_count / count | 全期間 | None | cutoff必須 |
| `past_choku_finish_avg` | float | 過去千直平均着順 | mean(finish_position of choku) | 全期間 | None | cutoff必須 |
| `past_choku_last_3f_avg` | float | 過去千直の上がり3F平均 | mean(last_3f of choku where last_3f > 0) | 全期間 | None | cutoff必須 |
| `past_corner_first_avg_5` | float | 過去5走の前半通過順位平均 | mean(corners[0] of last 5) | 直近5走 | None | cutoff必須 |
| `past_corner_first_min_5` | float | 過去5走のベスト前半通過順位 | min(corners[0] of last 5) | 直近5走 | None | cutoff必須 |
| `past_last_3f_avg_5` | float | 過去5走の上がり3F平均 | mean(last_3f of last 5) | 直近5走 | None | cutoff必須 |
| `past_last_3f_min_5` | float | 過去5走のベスト上がり3F | min(last_3f of last 5) | 直近5走 | None | cutoff必須 |
| `past_short_count` | int | 過去短距離(1000-1200m)出走回数 | count of short runs | 全期間 | 0 | cutoff必須 |
| `past_short_avg_l3f` | float | 過去短距離の上がり3F平均 | mean(last_3f of short runs) | 全期間 | None | cutoff必須 |
| `prev_distance` | int | 前走距離 | last_run.distance | 直近1走 | None | cutoff必須 |
| `prev_finish` | int | 前走着順 | last_run.finish_position | 直近1走 | None | cutoff必須 |
| `days_since_prev` | int | 前走からの間隔（日） | (cutoff_date - last_run.race_date).days | 直近1走 | None | cutoff必須 |

### 14.2 関係者特徴量（直近2年ローリング）

| 列名 | 型 | 定義 | 算出窓 | 欠損時 |
|---|---|---|---|---|
| `jockey_choku_n` | int | 騎手の千直出走回数 | 直近2年 | 0 |
| `jockey_choku_top3_rate` | float | 騎手の千直3着内率 | 直近2年 | None |
| `jockey_choku_strong_rate` | float | 騎手の千直強馬率 | 直近2年 | None |
| `trainer_choku_n` | int | 厩舎の千直出走回数 | 直近2年 | 0 |
| `trainer_choku_top3_rate` | float | 厩舎の千直3着内率 | 直近2年 | None |
| `trainer_choku_strong_rate` | float | 厩舎の千直強馬率 | 直近2年 | None |

### 14.3 血統特徴量

| 列名 | 型 | 定義 | 算出窓 | 欠損時 |
|---|---|---|---|---|
| `sire_id` | str | 父ID | pedigree_index | "" |
| `sire_name` | str | 父馬名 | sire_stats_index | "?" |
| `sire_line` | str | 父系統（簡易分類） | classify_sire_line() | "不明" |
| `bms_id` | str | 母父ID | pedigree_index | "" |
| `bms_name` | str | 母父馬名 | sire_stats_index | "?" |
| `bms_line` | str | 母父系統 | classify_sire_line() | "不明" |

### 14.4 環境変数（race-level）

| 列名 | 型 | 定義 |
|---|---|---|
| `track_condition_grp` | str | "良" / "稍重以上" |
| `era` | str | "2020-2022" / "2023-2026" |
| `is_full_field` | bool | `num_runners >= 16` |
| `race_type` | str | "G3アイビスSD" / "OP" / "条件戦" |

### 14.5 サンプル閾値ルール

- 騎手・厩舎の率系: **直近2年で出走 < 5回**なら算出せず None（信頼度に反映）
- 父・母父の率系: 直近2年で出走 < 10回なら None
- 馬の千直成績: 全期間で 0回（未経験）なら明示的に `is_first_choku = true`

---

## 15. v0.1 → v0.2 改訂履歴

### v0.2.0 主要改訂（指摘5点）
| 指摘 | 対応 |
|---|---|
| polaris_predスケール矛盾（ロジット vs 確率） | **確率[0,1]で確定**（実コード確認）、統合は **logit空間加算** に変更 |
| リーク防止と月次キャッシュ衝突 | **月次スナップショット + 当月内差分集計** ハイブリッドに変更、§8で詳細化 |
| 除外時の出力仕様曖昧（None vs low value） | **display_score / selection_score 分離**、§4.2 でAPI契約明確化 |
| 変数定義の網羅性不足 | **§14 データ辞書** 新設、全特徴量の算出式・窓・欠損時挙動を表形式で固定 |
| 同一根拠の重複加点 | **STEP内クリップ + 全体クリップ** を §3 に明記、B'とC-1の関係も明示 |

### v0.2.1 微修正（実装着手前の追加レビュー）
| 指摘 | 対応 |
|---|---|
| STEP F の変数名 `past_choku_top3_count` がデータ辞書と不整合 | データ辞書側 `niigata_1000m_top3_count` に統一 |
| §8.2 のコード例で「直近2年フィルタ」が説明だけで未適用 | コード例に **cutoff_2y による delta_window_start 適用** + **expired_runs 控除** を追加 |
| §5.1 見出し「ROI差駆動」と式の「3着内率 logit差」がズレ | 見出しを **「命中率差駆動」** に修正、ROI差は参照式として併記 |

---

設計確定。Phase 3a 着手待ち。

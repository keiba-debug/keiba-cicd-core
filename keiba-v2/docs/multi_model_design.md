# 複数モデル基礎設計（Multi-Model Architecture）

## 1. 背景と目的

### 課題
- 現行v7.9は好走確率(P)・勝利確率(W)を高精度で予測するが、**人気と相関が高く高配当馬を取りにくい**
- avg_finish_last3が支配的 → 人気順とほぼ同じ予測 → 妙味馬の発見力が弱い
- 単一モデルでは「精度向上」と「高配当発見」がトレードオフ

### 解決策
- **視点の異なる複数モデル**を構築し、それぞれの「注目馬」を抽出
- モデルごとに異なるラベル・特徴量・学習戦略を持たせる
- kazemachiキャラクターと紐付け、Web画面に「〇〇の注目馬」として表示

---

## 2. モデル一覧（案）

| ID | モデル名 | キャラ | 予測ターゲット | 特徴 |
|----|---------|--------|--------------|------|
| **base** | ベースモデル | ナルミ | P%(3着内)/W%(勝利)/AR(着差) | 現行v7.9。精度重視 |
| **gekisou** | 激走馬抽出 | ソラ | 人気薄好走(odds>=10 & top3) | 穴馬パターン学習 |
| **blood** | 血統特化 | ゲン | コース×距離×血統の好走率 | 種牡馬/母父統計ベース |
| **residual** | 残差モデル | 氷河期男 | 市場が見落とす好走 | オッズ残差の予測 |
| **ensemble** | 調停モデル | マキ | 複数モデルの統合推奨 | 各モデルの注目馬を集約 |

---

## 3. アーキテクチャ

### 3.1 ソースコード構成

既存のexperiment.py(2800行超)はそのまま維持し、新モデルは独立したディレクトリで開発する。
共通処理は段階的にcommon/に切り出す。

```
ml/
  # === 共通基盤（全モデルが使う） ===
  common/                          # 段階的に切り出し（NEW）
    dataset.py                     # build_dataset（データ読み込み・特徴量計算）
    trainer.py                     # train_model（LightGBM学習・評価の共通ロジック）
    evaluator.py                   # AUC/ROI/hit分析の共通関数

  features/                        # 既存のまま（全モデルが参照可能）
    past_features.py
    jrdb_features.py
    pedigree_features.py
    ...

  # === 既存baseモデル（現行のまま） ===
  experiment.py                    # base学習パイプライン（v7.9〜）
  predict.py                       # base推論

  # === 追加モデル（モデル別ディレクトリ） ===
  models/
    gekisou/                       # ソラ — 激走馬抽出
      config.py                    # 特徴量リスト、ラベル定義、ハイパーパラメータ
      experiment.py                # python -m ml.models.gekisou.experiment --version 1.0
      predict.py                   # python -m ml.models.gekisou.predict --date 2026-04-05
      features.py                  # gekisou固有の特徴量（必要なら）
    blood/                         # ゲン — 血統特化
      config.py
      experiment.py
      predict.py
    residual/                      # 氷河期男 — 残差モデル
      config.py
      experiment.py
      predict.py
    ensemble.py                    # マキ — 全モデル統合推奨ロジック

  predict_multi.py                 # 複数モデル統合予測（base結果に追加モデル予測を付加）
```

#### 各モデルのconfig.pyの役割
```python
# ml/models/gekisou/config.py の例
MODEL_ID = 'gekisou'
DISPLAY_NAME = 'ソラ'
LABEL_COL = 'is_upset'           # 独自ラベル
FEATURE_COLS = [...]             # 独自特徴量セット
PARAMS = { 'objective': 'binary', 'scale_pos_weight': 20, ... }
DATA_FILTER = None               # 全データ使用（条件特化なら 'turf,op+' 等）
```

#### 段階的移行計画
1. **Phase 1**: 既存experiment.pyはそのまま。gekisouを`ml/models/gekisou/`に新規作成
2. **Phase 2**: gekisou/bloodで共通化した処理を`ml/common/`に切り出し
3. **Phase 3**: 既存experiment.pyの共通部分をcommonからimportするようリファクタ（任意）

### 3.2 データ（学習済みモデル）構成

各モデルが**独立してバージョン管理**される。
baseをv8.0にしてもgekisou v1.0はそのまま動く。

```
data3/ml/
  # === base model（既存） ===
  model_p.txt                      # base P（ライブ）
  model_w.txt                      # base W（ライブ）
  model_ar.txt                     # base AR（ライブ）
  model_meta.json                  # base meta（version, features, split）
  versions/                        # base アーカイブ（既存）
    v7.9/
    v7.7c/
    ...

  # === 追加モデル（モデル別ディレクトリ） ===
  models/                          # NEW
    gekisou/
      model.txt                    # ライブモデル
      model_meta.json              # version: "1.0", features, label, split
      versions/                    # gekisou独自のアーカイブ
        v1.0/
        v1.1/
    blood/
      model.txt
      model_meta.json
      versions/
        v1.0/
    residual/
      ...
```

#### model_meta.jsonの仕様（全モデル共通フォーマット）
```json
{
  "model_id": "gekisou",
  "version": "1.0",
  "display_name": "ソラ",
  "label": "is_upset",
  "features": ["prev_tbw", "jrdb_training_idx", ...],
  "feature_count": 45,
  "split": { "train": "2020 ~ 2025-03", "val": "2025-04", "test": "2025-05 ~ 2026-03" },
  "data_filter": null,
  "created_at": "2026-04-01T12:00:00",
  "metrics": { "auc": 0.72, "hit_rate": 0.08, ... }
}
```

### 3.3 予測結果の出力

```
data3/races/YYYY/MM/DD/
  predictions.json                 # 既存（base model予測）— フォーマット変更なし
  multi_predictions.json           # 追加モデル予測結果（NEW）
```

#### multi_predictions.jsonフォーマット
```json
{
  "created_at": "2026-04-05T08:30:00",
  "model_versions": {
    "gekisou": "1.0",
    "blood": "1.2"
  },
  "races": [{
    "race_id": "...",
    "entries": [{
      "umaban": 1,
      "horse_name": "...",
      "models": {
        "gekisou": { "score": 0.82, "rank": 2, "featured": true, "label": "激走候補" },
        "blood":   { "score": 0.65, "rank": 5, "featured": false }
      }
    }]
  }]
}
```

### 3.4 Web表示

### 3.2 predictions.json拡張

```json
{
  "races": [{
    "race_id": "...",
    "entries": [{
      "umaban": 1,
      "horse_name": "...",
      // --- 既存 (base model) ---
      "pred_proba_p": 0.35,
      "pred_proba_w": 0.12,
      // --- 追加モデル注目フラグ ---
      "multi_model": {
        "gekisou": { "score": 0.82, "featured": true, "label": "激走候補" },
        "blood":   { "score": 0.65, "featured": false },
        "residual": { "score": 0.45, "featured": true, "label": "割安" }
      }
    }]
  }]
}
```

### 3.4 Web表示

```
レース画面 → 各馬の横に注目アイコン

  1 ディープインパクト  P:35% W:12%  [ソラ] [ゲン]
  2 キタサンブラック    P:28% W:08%  [氷河期男]
  3 イクイノックス      P:42% W:18%

注目馬リスト (/predictions)
  ソラの激走候補:     3R-5番, 7R-2番, 11R-8番
  ゲンの血統推し:     5R-1番, 8R-6番
  氷河期男の割安馬:   2R-7番, 9R-3番
```

---

## 4. 各モデル詳細設計

### 4.1 gekisou（激走馬抽出）— ソラ

**ラベル**: `is_upset = (finish_position <= 3) & (odds >= 10.0)`
- 単勝10倍以上で3着以内 = 人気薄好走

**特徴量戦略**:
- 人気・オッズ系は**除外**（人気が低いことは前提条件で、特徴量にしない）
- 重視: 前走不利(furi_adj)、休み明け、馬具変更、調教指数急上昇、コース替わり
- JRDB: training_idx、stable_idx、deokure_adj（出遅れ補正=前走で力を出しきれなかった証拠）

**学習の注意点**:
- 正例が非常に少ない（全体の3-5%程度）→ SMOTE or scale_pos_weight
- is_upsetのROIが高い馬のパターンを学習（勝っただけでなく回収に貢献する馬）

### 4.2 blood（血統特化）— ゲン

**ラベル**: 既存と同じ（is_top3 / is_win）

**特徴量戦略**:
- 血統特徴量を**大幅強化**: 種牡馬×コース、種牡馬×距離、種牡馬×馬場、母父×距離
- 既存pedigree_features + sire_statsを深堀り
- 他の特徴量は最小限（血統の視点に特化）

**出力**: 「この血統はこのコースで走る」確率。baseモデルと乖離が大きい馬が注目馬

### 4.3 residual（残差モデル）— 氷河期男

**ラベル**: `residual = actual_finish_position - expected_from_odds`
- オッズから期待される着順と実際の着順の差（負=期待以上の走り）

**Step 1**: odds → expected_finish のベースライン回帰モデル
**Step 2**: residualを予測する第2モデル（特徴量: JRDB指数、調教、不利歴、ローテ等）

**出力**: 「市場が過小評価している度合い」スコア

### 4.4 ensemble（調停）— マキ

- 各モデルの注目馬を集約
- 複数モデルが同時に注目 = 高信頼度
- 1モデルだけ注目 = その視点からの穴候補
- Web画面でフィルタリング可能に

---

## 5. 実装ロードマップ

### Phase 1: 基盤整備
- [ ] multi_predictions.json の出力フォーマット確定
- [ ] predict_multi.py の骨組み（baseモデル結果を読んで追加モデル予測を付加）
- [ ] Web: レース画面に注目アイコン表示の仕組み

### Phase 2: 最初のサブモデル
- [ ] gekisou モデルの実験（ラベル設計 → 学習 → 評価）
- [ ] blood モデルの実験（血統特徴量強化 → 学習 → 評価）

### Phase 3: 残差モデル + 統合
- [ ] residual モデルの実験
- [ ] ensemble ロジック実装
- [ ] Web: 注目馬リストにキャラクター表示

### Phase 4: kazemachi連携
- [ ] キャラクターアイコンのWeb組み込み
- [ ] 「〇〇の注目馬」セクション
- [ ] 各キャラの的中率・ROI追跡

---

## 5b. 条件特化モデル（レース条件でフィルタして学習）

キャラ紐付けとは別軸で、**特定条件に特化したモデル群**も構築する。
条件特化で発見した有効特徴量はbaseモデル(v7.9)にフィードバック → 本体バージョンアップにも貢献。

| ID | 条件 | 学習データ | 特化する特徴量 | 期待効果 |
|----|------|----------|--------------|---------|
| **turf_op** | 芝OP以上 | 芝+OP/重賞/G1のみ | 血統(大種牡馬の適性)、実績(重賞好走歴)、斤量差 | 重賞予想の精度UP |
| **dirt_sprint** | ダート1400m以下 | ダート短距離のみ | テン指数、枠番、砂被り経験、ダート替わり | 前半速度の重要性を反映 |
| **local** | ローカル開催 | 札幌/函館/福島/新潟/小倉 | コースバイアス、騎手の場慣れ、輸送有無 | ローカル癖の学習 |
| **maiden** | 新馬/未勝利 | 新馬+未勝利のみ | 血統(初出走の種牡馬成績)、調教指数、厩舎力 | データ少ない馬の評価力 |
| **longdist** | 芝2400m以上 | 芝長距離のみ | スタミナ血統、ローテ間隔、馬体重推移 | 長距離適性の深堀り |

### 条件特化モデルの構築パターン
```
1. baseモデルと同じ構造（LightGBM binary classification）
2. 学習データをフィルタ（例: track_type='turf' & grade IN ('OP','G3','G2','G1')）
3. 特徴量は条件に合わせてカスタマイズ（一部追加、一部削除）
4. 評価: 同条件のテストデータでbaseモデルと比較
5. base超えした特徴量 → v7.x本体にフィードバック
```

### キャラとの紐付け例
- ゲン: turf_op + blood（芝の重賞を血統で読む男）
- ソラ: gekisou + maiden（新馬戦の直感と大穴狙い）
- 氷河期男: dirt_sprint + residual（ダート短距離の割安馬）

---

## 6. 設計原則

1. **baseモデルは触らない** — v7.9は安定して動いてる。追加モデルは独立して構築
2. **predictions.jsonは拡張のみ** — 既存フォーマットを壊さない。追加モデルはmulti_predictions.jsonに分離
3. **各モデルは独立して評価** — 個別にAUC/ROIを計測。アンサンブルは最後
4. **特徴量の差別化が命** — 同じ特徴量で学習したら同じ予測になる。各モデルの個性=特徴量の選択
5. **キャラクターとの紐付けは表示層** — MLロジックとキャラ設定は分離。紐付けはWeb/UIで行う
6. **疎結合** — 各モデルは独立してバージョンアップ・ロールバックできる。「全モデル同時更新しないと動かない」は絶対避ける
7. **ソース分離** — モデル別にディレクトリを分け、config.py/experiment.py/predict.pyを持つ。共通処理はcommon/に段階的に切り出す
8. **model_meta.json統一フォーマット** — 全モデルが同じメタデータ構造を持つ。model_id/version/features/split/metricsを必須フィールドにする

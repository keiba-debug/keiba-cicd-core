# nova スペシャリストモデル — 設計書 v0

新馬・1勝クラス専用のスペシャリストモデル群。 polaris 2.0 の苦手領域 (合計 1,229 bets / ROI 76–83%) を救うのが目的。

## 背景

Session 122 `polaris_segments` 集計 (Test 2025-05〜2026-03 / 2,934R) で、 polaris 2.0 の grade 軸性能が二極化していることが定量化された。

| グレード | bets | 勝率 | ROI | 解釈 |
|---|---:|---:|---:|---|
| **新馬** | 576 | 21.4% | **+75.9%** 🔴 | polaris 苦手 (赤字) |
| **1勝クラス** | 653 | 20.1% | **+82.6%** 🔴 | polaris 苦手 (赤字) |
| 未勝利 | 735 | 24.1% | +113% 🟢 | polaris 強い → 対象外 |
| G1 | 20 | 35.0% | +385% 🟢 | Selective がカバー |
| G3 | 59 | 22.0% | +265% 🟢 | Selective がカバー |

vega-niigata1000 のような「polaris+ルールエンジン」 では母集団が小さい (70R) 場合に過学習リスクで採用したが、 nova 対象は **1,229 bets** と十分なので **独立 LightGBM** が現実的。

## 命名

`nova` (新星) — Stars 系命名体系 (`multi-model-naming.md`) で「残差・市場過小評価」 を表す。 新馬の "新" とも語感が一致。 サブモデル単位の命名:

- **nova_debut**: 新馬戦専用 (576 bets/年)
- **nova_emerging**: 1勝クラス専用 (653 bets/年)

将来サブモデルが増える場合は同じ命名規則 (`nova_<class>`)。

## アーキテクチャ

サブモデル間で特徴量利用可能性が大きく違うため **2 サブモデル分離** を採用。

### nova_emerging (1勝クラス特化) — Phase 1 で着手

| 項目 | 値 |
|---|---|
| 対象 grade | `1勝クラス` |
| 特徴量セット | polaris 2.0 と同じ (`FEATURE_COLS_ALL`) |
| 学習期間 | Train 2020-01〜2025-03 / Val 2025-04 / Test 2025-05〜2026-03 |
| ターゲット | is_top3 (P モデルのみ Phase 1)、 後に is_win (W) も追加 |
| パラメータ | polaris 2.0 と同じ `PARAMS_P` (Optuna 後でいい) |
| sire_cutoff | `2025-04-30` (テスト期間リーク防止) |

過去走が 3〜5 戦あるので polaris と同じスタックで学習データだけ絞る形。 **「同じ仕組みで grade を絞った時、 polaris の苦手を取り戻せるか」** がここでの検証仮説。

### nova_debut (新馬特化) — Phase 2 以降

| 項目 | 値 |
|---|---|
| 対象 grade | `新馬` |
| 特徴量セット | **過去走依存特徴量を除外**: `past_features`, `running_style_features`, `rotation_features`, `pace_features`, `jrdb_sed/cyb` (前走情報) |
| 残す特徴量 | `base`, `trainer`, `jockey`, `training_features` (CK_DATA 調教), `speed_features`, `pedigree_features`, `jrdb_kyi/kaa/cha/kka/joa` |
| ターゲット | is_top3 (P)、 is_win (W) は後 |
| 注意 | デビュー馬の前走情報は当然ゼロ。 血統・調教・厩舎・騎手・パドック (`base_odds_v2` 系) で勝負 |

Phase 2 着手前に **新馬データの欠損率を実測** する。 過去走依存特徴量を消したら何が残るかをデータドリブンで決める。

## 統合方式

vega-niigata1000 の `predict_overlay.py` 同パターン。 polaris の出力を **置き換え** ではなく **追加フィールド** として共存させる。

```
predictions.json (entry 単位)
  pred_proba_p          # polaris P (既存)
  pred_proba_w_cal      # polaris W (既存)
  rank_p                # polaris rank (既存)
  nova: {               # 新規 (nova_emerging または nova_debut が発動した時のみ)
    sub_model: "emerging" | "debut",
    pred_proba_p_nova,
    rank_p_nova,
    polaris_p,          # 元の値を保存して explainability 確保
  }
```

WebUI 側で「nova 推奨が polaris と違う場合」 を視覚化する。 vega 同様 batch_predict/predict/vb_refresh の 3 経路フックが必要。

## ディレクトリ構成

```
keiba-v2/ml/nova/
├── README.md                    # ディレクトリ案内 (この設計書へのリンク)
├── __init__.py
├── train_emerging.py            # Phase 1 学習
├── train_debut.py               # Phase 2 学習
├── evaluate.py                  # polaris vs nova の比較レポート
└── predict_overlay.py           # predict.py から呼ばれる overlay

data3/ml/nova/
├── emerging/
│   ├── model_p.txt
│   └── model_meta.json
└── debut/
    ├── model_p.txt
    └── model_meta.json
```

## Phase 計画

| Phase | 内容 | 完了条件 |
|---|---|---|
| 0 | 設計書 (この文書) + ディレクトリ作成 | このファイルが merge される |
| **1** | **nova_emerging 学習 (P モデルのみ) + polaris との Test 比較** | **rank_p Top1 ROI が polaris baseline (82.6%) を 110% 以上に押し上げる、 または 劣化する場合は失敗を明確化して原因分析** |
| 2 | nova_debut 学習 (P モデルのみ) | 同上 (新馬 ROI 75.9% → 110%+ または失敗分析) |
| 3 | nova_emerging + nova_debut の W モデル追加 | rank_w 比較も追加 |
| 4 | predict_overlay.py + 3 経路統合 | 当日 predictions.json に `nova` フィールドが書き込まれる |
| 5 | WebUI 統合 (specialist タブに nova 追加) | `/specialist/[raceId]` で nova タブが表示される |

各 Phase ごとに **失敗で打ち切り可能**。 Phase 1 で polaris に勝てなければ Phase 2-5 は再設計。

## 評価指標

Phase 1-2 では以下を Test 期間 (2025-05〜2026-03 / 2,934R 中の対象クラス分) で集計:

- **rank_p Top1 単勝 ROI** ← 主指標 (polaris 比 +pt)
- **rank_p Top1 勝率** (Top1 が 1 着になる率)
- **rank_p Top1 複勝 ROI** (Top1 が 3 着内に来る率 × 複勝オッズ)
- **Brier score** (確率予測の精度)
- **ECE (Expected Calibration Error)** (確率キャリブレーション)

これらをポラリスと同じ集計関数 (`ml/utils/roi.py`) で出すことで apples-to-apples 比較を担保。

## 既知のリスク

1. **過学習リスク**: 学習データ ~5 年 × 1勝クラス比率 (~25%?) で実効サンプルが少なくなる可能性。 LightGBM の `min_data_in_leaf` を上げる、 `num_leaves` を下げる等の調整余地あり
2. **市場の歪み消失**: Session 122 で確立した **「市場と乖離するシグナルが ROI 源泉」** 原則と整合的か? nova が polaris と似た予測を出すなら ROI は上がらない可能性
3. **データ不足の grade 切り出し**: 新馬は 1 頭あたり過去走ゼロ。 学習データの効果が薄い可能性 → Phase 2 で実測
4. **時期依存性**: polaris_segments で 2025-11 月だけ ROI 60.1% と弱い等の月別バラつきがあり、 nova も同じ弱点を引き継ぐ可能性

## 関連メモリ・ドキュメント

- メモリ: `niche-specialist-strategy.md` (この戦略の上位ノート)
- メモリ: `multi-model-naming.md` (Stars/Nebula 命名)
- メモリ: `niigata-1000m-project.md` (vega 成功例、 overlay 設計のリファレンス)
- レポート: `data3/analysis/polaris_segments/polaris_2.0_v1/segments.json` (苦手領域の定量化)
- 設計書: `docs/projects/vega_niigata1000_rule_engine.md` (overlay パターンのリファレンス)

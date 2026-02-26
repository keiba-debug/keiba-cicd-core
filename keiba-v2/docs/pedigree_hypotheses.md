# 血統仮説リスト

> 作成: 2026-02-26 Session 51
> ステータス: 仮説収集 → 順次検証中

## 概要

v5.7でID直接投入（LabelEncoding + categorical_feature）は過学習で失敗。
代わりに、競馬知識に基づく仮説を1つずつデータ検証し、有効なものだけ特徴量化する。

## 仮説一覧

| # | 仮説 | 条件変数 | ステータス |
|---|------|---------|-----------|
| H0 | ベースライン（sire/bms基本勝率） | - | ✅ v5.8 デプロイ |
| H1 | 枠順×頭数の血統差 | wakuban, entry_count | 未着手 |
| H2 | ペース変化耐性 | RPCI変化量 | 未着手 |
| H3 | 休み明け上昇型 | days_since_last_race >= 56 | ✅ v5.8 デプロイ |
| H4 | 間隔詰め疲労型 | days_since_last_race <= 21 | ✅ v5.8 デプロイ |
| H5 | 瞬発vs持続適性 | rpci (>=53/<=49) | ⚠️ v5.9 低カバレッジ |
| H6 | 成長曲線（早熟/晩成） | age (<=3/>=4) | ✅ v5.9 Model B #4 |

---

## H0: ベースライン統計

### 定義
種牡馬(sire)と母父(bms)の産駒全体の勝率・複勝率。
他の条件付き仮説の基盤となる数値。

### 特徴量
- `sire_top3_rate`: 父産駒のベイズ平滑化複勝率
- `bms_top3_rate`: 母父産駒のベイズ平滑化複勝率

### ベイズ平滑化
- Beta-Binomial posterior mean: `(top3 + 2.5) / (total + 10.0)`
- 出走10回未満のsire/bmsでも安全に使える

---

## H1: 枠順×頭数の血統差

### 仮説
多頭数レースの内枠よりも、小頭数レースの外枠の方が成績が上がる血統がある。
逆に、内枠巧者の血統もある。

### 条件
- **内枠**: wakuban <= entry_count * 0.33
- **外枠**: wakuban >= entry_count * 0.67
- **多頭数**: entry_count >= 14
- **小頭数**: entry_count <= 12

### 期待特徴量
- `sire_inner_gate_top3_rate`: 内枠時の複勝率
- `sire_outer_gate_top3_rate`: 外枠時の複勝率
- `sire_gate_preference`: 外枠率 - 内枠率（正=外枠有利型）

---

## H2: ペース変化耐性

### 仮説
前走よりも厳しいペース（RPCIが低い=前傾）になると成績を落とす血統と、
逆にタフなペースで浮上する血統がある。

### 条件
- **ペース悪化**: 今走RPCI < 前走RPCI - 5（前傾化）
- **ペース緩和**: 今走RPCI > 前走RPCI + 5（後傾化）

### 期待特徴量
- `sire_pace_tough_top3_rate`: ペース悪化時の複勝率
- `sire_pace_sensitivity`: ペース悪化時率 - 通常時率

---

## H3: 休み明け上昇型

### 仮説
長期休養明け（8週以上）のレースで、使い込むほどに調子を上げる血統がある。
休み明け初戦は凡走しても、叩き2戦目で変わる。

### 条件
- **休み明け(fresh)**: days_since_last_race >= 56（8週以上）
- **通常**: 22 <= days_since_last_race <= 55
- **デビュー戦**: days_since_last_race == None → 除外

### 期待特徴量
- `sire_fresh_top3_rate`: 休み明け時の複勝率
- `sire_fresh_advantage`: fresh率 - normal率（正=休み明け得意）

---

## H4: 間隔詰め疲労型

### 仮説
中1週〜中2週の連戦で成績を落とす（疲労が抜けにくい）血統がある。
逆に、間隔を詰めて使っても落ちない頑健な血統もある。

### 条件
- **間隔詰め(tight)**: days_since_last_race <= 21（中2週以内）
- **通常**: 22 <= days_since_last_race <= 55

### 期待特徴量
- `sire_tight_top3_rate`: 間隔詰め時の複勝率
- `sire_tight_penalty`: tight率 - normal率（負=詰め使い苦手）

---

## H5: 瞬発vs持続適性

### 仮説
上がりの速い瞬発力勝負と、ラップが均一な持続力勝負とで
明確に得意不得意が分かれる血統がある。

### 条件
- **瞬発レース**: lap33 < -3.0（上がりが全体ラップより3秒以上速い）
- **持続レース**: lap33 > -1.0（上がりと全体ラップの差が小さい）
- RPCIでも代替可: RPCI <= 49（後傾=瞬発寄り）/ RPCI >= 53（前傾=持続寄り）

### 期待特徴量
- `sire_sprint_finish_top3_rate`: 瞬発レースでの複勝率
- `sire_sustained_top3_rate`: 持続レースでの複勝率
- `sire_finish_type_preference`: 瞬発率 - 持続率

---

## H6: 成長曲線（早熟/晩成）

### 仮説
2-3歳で高い勝率を示すが4歳以降に下降する早熟型と、
3歳後半〜4歳から本格化する晩成型が血統で分かれる。

### 条件
- **若駒期**: age <= 3
- **本格期**: age >= 4

### 期待特徴量
- `sire_young_top3_rate`: 3歳以下の複勝率
- `sire_mature_top3_rate`: 4歳以上の複勝率
- `sire_maturity_index`: mature率 - young率（正=晩成型）

---

## 次回セッション引継ぎノート（Session 53 → 次回）

### Session 53 完了: オフセット修正 → 3パターン実験 → v5.10デプロイ

#### オフセットバグ修正（前半）
- um_parser.py Ketto3Info: @250→@204(父), @296→@250(母), @434→@388(母父)
- 検証: コントレイル(2017101835)の@204=ディープインパクト確認
- pedigree_index/sire_stats_index 再ビルド済み

#### ML再実験結果（後半）
3パターンで体系的に比較:

| 実験 | A AUC | B AUC | Preset standard | wide |
|------|:---:|:---:|:---:|:---:|
| 血統なし(0) | 0.8225 | 0.7837 | 118.7% | 114.4% |
| H0+H3/H4(6) | 0.8250 | 0.7876 | 134.1% | 116.6% |
| **All14** | **0.8251** | **0.7880** | **136.3%** | **137.5%** |

→ **All14がベスト**。v5.10としてデプロイ済み。

**重要発見**: 母馬(dam)効果 > 父馬(sire)効果
- v5.8(バグデータ)のsire_top3_rate=#1(227K)は実は母の産駒成績だった
- 正しいデータではbms_top3_rate=#8(17K)に落ち着く

### 次回タスク候補（優先度順）

#### 1. 母馬(dam)統計量の追加
- sire_stats_indexに母(dam)カテゴリを追加
- バグデータ時代に母の産駒成績が最強予測因子だったことが確認済み
- build_sire_stats.pyにdam集計ロジック追加 → pedigree_features.pyに dam_top3_rate等

#### 2. Optuna導入 + シード固定
- ハイパーパラメータ最適化
- LightGBM bagging_seedの固定（run-to-run variance軽減）

#### 3. 残り仮説の検証（H1, H2）
- H1 枠順×頭数: wakuban/entry_count条件付き集計
- H2 ペース変化耐性: RPCI変化量条件付き集計

#### 4. Point-in-Time化
- trainer/jockey masterの時点別集計

### 関連ファイル
| ファイル | 役割 |
|---------|------|
| `core/jravan/um_parser.py` | UM_DATAパーサー（**オフセット修正済み**） |
| `builders/build_sire_stats.py` | sire/bms統計builder（H0-H6 + 名前抽出） |
| `builders/build_pedigree_index.py` | 馬→sire/bmsマッピングbuilder |
| `ml/features/pedigree_features.py` | 特徴量モジュール（9フィールド×sire/bms） |
| `ml/experiment.py` | v5.10: PEDIGREE_FEATURES=14特徴量 |
| `data3/indexes/sire_stats_index.json` | 統計インデックス（0.6MB, 780 sires + 1,259 BMS） |
| `data3/indexes/pedigree_index.json` | 馬→sire/bmsマッピング（4,119 unique sires） |
| `web/src/app/analysis/pedigree/page.tsx` | 血統分析Webページ |
| `docs/ml-experiments/v5.10_pedigree_corrected.md` | 実験レポート |

# 血統仮説リスト

> 作成: 2026-02-26 Session 51
> ステータス: 仮説収集 → 順次検証中

## 概要

v5.7でID直接投入（LabelEncoding + categorical_feature）は過学習で失敗。
代わりに、競馬知識に基づく仮説を1つずつデータ検証し、有効なものだけ特徴量化する。

## 仮説一覧

| # | 仮説 | 条件変数 | ステータス |
|---|------|---------|-----------|
| H0 | ベースライン（sire/bms基本勝率） | - | 検証中 |
| H1 | 枠順×頭数の血統差 | wakuban, entry_count | 未着手 |
| H2 | ペース変化耐性 | RPCI変化量 | 未着手 |
| H3 | 休み明け上昇型 | days_since_last_race >= 56 | 検証中 |
| H4 | 間隔詰め疲労型 | days_since_last_race <= 21 | 検証中 |
| H5 | 瞬発vs持続適性 | rpci, lap33 | 未着手 |
| H6 | 成長曲線（早熟/晩成） | age, finish | 未着手 |

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
- RPCIでも代替可: RPCI >= 55（後傾=瞬発寄り）/ RPCI <= 45（前傾=持続寄り）

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

## 次回セッション引継ぎノート（Session 51 → 次回）

### 完了済み
- **H0 ベースライン**: sire/bms_top3_rate → v5.8デプロイ済み、Model B #1特徴量
- **H3 休み明け**: sire/bms_fresh_advantage → v5.8デプロイ済み、有効
- **H4 間隔詰め**: sire/bms_tight_penalty → v5.8デプロイ済み、有効
- **インフラ**: pedigree_index.json + sire_stats_index.json + builder全部完成

### 次回タスク候補

#### 1. 血統分析Webページ（web-roadmap #14）
- **パターン**: 出遅れ分析ページと同じ（builder JSON → API → Frontend）
- **データソース**: `data3/indexes/sire_stats_index.json`（既存、2.8MB）
- **タブ案**: 種牡馬ランキング / 休み明け耐性 / 間隔詰め耐性 / 母父統計
- **UI変更**: 再集計ボタンをAdmin→各分析ページに移動
  - 出遅れ分析ページにも「出遅れデータ再集計」ボタン
  - 血統分析ページに「血統統計再集計」ボタン
  - 各ページがPython builderをAPI経由で実行する形
- **参考実装**: `/analysis/slow-start` + `/api/admin/build-slow-start`

#### 2. 残り仮説の検証（H1, H2, H5, H6）
- build_sire_stats.py を拡張して条件付き集計を追加
- 各仮説のデータ検証 → 有効なら特徴量化 → 実験
- **優先度**: H5(瞬発/持続) > H6(成長曲線) > H1(枠順) > H2(ペース)

#### 3. 分析ページ再集計ボタン設計
- **現状**: Admin画面の「ツール」セクションに全builder集約
- **目標**: 各分析ページ内に対応する再集計ボタンを配置
  - 分析ページから直接API呼び出し → builder実行 → 画面リフレッシュ
  - Admin側は残してもOK（一括実行用）

### 関連ファイル
| ファイル | 役割 |
|---------|------|
| `builders/build_sire_stats.py` | sire/bms統計builder（--analyzeで分析出力） |
| `ml/features/pedigree_features.py` | 特徴量モジュール |
| `data3/indexes/sire_stats_index.json` | 統計インデックス |
| `data3/indexes/pedigree_index.json` | 馬→sire/bmsマッピング |
| `web/app/analysis/slow-start/` | 参考: 出遅れ分析ページ |
| `web/app/api/admin/` | 参考: builder実行API |
| `docs/roadmap/web-roadmap.md` | #14 血統分析ページ仕様 |

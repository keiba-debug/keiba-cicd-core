# 調教評価ブラッシュアップ検討メモ（書籍照合 × 現状棚卸し）

作成日: 2026-07-02
対象:
- `web/src/lib/data/target-training-reader.ts`
- `ml/features/training_features.py`
- `ml/features/jrdb_features.py`
- `analysis/training_analysis.py`
- `jrdb/parser.py`
- 参考書籍: 「調教タイムの読み方」（book-digest済み、notes/shots/調教タイムの読み方/）

## 1. 先に結論（優先度順）

1. **書籍が説く「加速/減速ラップ」「東西別絶対閾値」は、すでに`calculateLapRank()`/`calculateTimeLevel()`で書籍以上の精度で実装済み。** ここへの追加投資は不要。
2. **本当のギャップは書籍とは無関係に既に社内文書化済みだった** — 「UI分析資産（`training_analysis.json`等）がML特徴量パイプラインに未接続」という、`202606_trainer_patterns_ml_bridge_review.md` / `feature_roadmap.md` Phase1で特定済み・未実装の課題。車輪の再発明を避け、そちらを優先すべき。
3. **書籍から得られた、既存資産がカバーしていない新規性は1点のみ**: JRDB CHA (`本追切`) の テンF (`ten_e`/`ten_e_idx`) が、パース済みだが特徴量化されておらず、かつ現行のCK_DATAベース分類（Lap2/Lap1 = 追い切り終盤2Fのみ）が構造的に見えない「調教序盤」を捉える唯一の手段。低コストで試す価値あり。

## 2. 現状確認（実装・実データ）

### 2.1 加速/減速ラップ分類 — 実装済み、書籍と整合

`calculateLapRank()` (`target-training-reader.ts:727-776`) が Lap2（終い2F目）と Lap1（終い1F）を比較し、
S/A/B/C/D の5分類 + 加速(+)/同(=)/減速(-) を算出。書籍の「A3: 終い11秒台加速」に相当する
分類（`baseRank='A'`: `l1<12.0 && l2>=12.0`）はコードにそのまま存在する。

### 2.2 絶対時計閾値（東西別）— 実装済み、書籍より精密

`TIME_LEVEL_THRESHOLDS` (`target-training-reader.ts:791-796`) は 美浦坂路/栗東坂路/美浦コース/栗東コース
の4区分×5段階で、2023年10月の美浦坂路改修後の実データから算出済み（コメントに明記）。

書籍の「栗東坂路53秒台以下」に対応する値は栗東坂路Level4閾値=53.5、美浦坂路Level4=54.5 と、
書籍の水準とほぼ一致。**書籍の静的な閾値より、実データ較正済みの現行実装の方が精度が高い。**

### 2.3 東西(美浦/栗東)判定 — 複数箇所で実装済み

- `TrainingRecord.location`（`target-training-reader.ts:69`, WC0=Miho/WC1=Ritto）
- `derive_tozai()`（`analysis/training_analysis.py:220-234`、調教師の主戦場推定）

### 2.4 調教師別シグネチャパターン — 実装済み、ただしML未接続（既知）

`analysis/training_analysis.py`の`compute_trainer_analysis()`が215調教師×714パターンを検出済み
（`202606_trainer_patterns_ml_bridge_review.md`記載の実データ）。書籍が言う「矢作芳人=A2ラップ」
的な厩舎シグネチャは、この仕組みで統計的に代替・拡張されている。

**既知の未接続問題**: この分析結果（`training_analysis.json`/`trainer_patterns.json`）は
`training_features.py`が読む`ck_training`（training_summary.json由来）とは別の生成物であり、
学習パイプラインに接続されていない。`feature_roadmap.md` Phase1（`training_deviation`,
`trainer_pattern_score`, `course_change_flag`）として設計済み、ステータスは🔶未実装。
ブロッカーは「training_summary.jsonが当日分のみ保持、過去蓄積の仕組みがない」（同ドキュメント記載）。

### 2.5 JRDB CHA（本追切）— パース済みだが大部分未使用

`jrdb/parser.py`の`parse_cha_line()`は以下を抽出済み:

| フィールド | 内容 | ML特徴量化 |
|---|---|---|
| `oikiri_idx` | 追切指数（総合） | ✅ `jrdb_cha_oikiri_idx` |
| `shimai_e_idx` | 終い指数 | ✅ `jrdb_cha_shimai_idx` |
| `oikiri_type` | 追切種類(一杯/強目/馬なり) | ✅ `jrdb_cha_oikiri_type` |
| `ten_e` / `ten_e_idx` | **テンF（最初の1-2ハロン）生タイム・指数** | ❌ 未使用 |
| `chukan_e` / `chukan_e_idx` | 中間F指数 | ❌ 未使用 |
| `youbi` | 調教曜日 | ❌ 未使用 |
| `oikiri_course` | 調教コース | ❌ 未使用（`training_features.py`は坂/非坂の二値のみ） |

**重要な非重複ポイント**: CK_DATA（2.1節の`calculateLapRank`）が見ているのは
Lap2/Lap1 = 追い切り「終盤2F」のみ。テンF（追い切り序盤）はCK_DATAの構造上そもそも
含まれておらず、JRDB CHAの`ten_e_idx`だけが持つ独自情報。「スタートから飛ばすタイプ」
「テンは控えて終いを使うタイプ」の判別は、既存のどの分析軸にも存在しない。

## 3. 書籍手法との照合表

| 書籍の手法 | 現行実装 | 判定 |
|---|---|---|
| 加速ラップ(A)/減速ラップ(B)分類 | `calculateLapRank()` | ✅ 実装済み・書籍と一致 |
| 終い11秒台加速（A3相当） | `baseRank='A'`ロジック | ✅ 実装済み |
| コース別絶対時計閾値（栗東坂路53秒台等） | `TIME_LEVEL_THRESHOLDS` | ✅ 実装済み・書籍より精密（実データ較正） |
| 東西(美浦/栗東)の区別 | `location`, `derive_tozai()` | ✅ 実装済み |
| 前週土日のタイミング | `weekendLocation/weekendLap`(TrainingSummary) | ✅ データ保持済み（ただしML特徴量化はされていない） |
| 厩舎シグネチャ（調教師別パターン） | `trainer_patterns.json` | 🔶 分析は実装済み、ML未接続（Phase1既知課題） |
| テンF（序盤ラップ）の活用 | JRDB CHA `ten_e_idx` | ❌ 未使用・書籍からの新規提案 |

## 4. 改善方針

### 4.1 優先度1: Phase1（既知）を進める — 本メモのスコープ外だが再確認を推奨

`feature_roadmap.md`のPhase1未解決事項（training_summary.json過去蓄積の仕組み）に着手すれば、
`trainer_pattern_score`等が動き出し、書籍の「厩舎シグネチャ」相当の情報がMLに接続される。
これは書籍の有無に関係なく既に最優先課題として文書化済み。

### 4.2 優先度2（書籍由来の新規提案）: JRDB CHAのテンF特徴量を追加

- `jrdb_features.py`のCHA処理ブロック（307-319行付近）に `ten_e_idx` を追加。
- 新特徴量案: `jrdb_cha_ten_idx`（テン指数）, `jrdb_cha_chukan_idx`（中間指数）、
  および `jrdb_cha_accel_pattern`（テン→中間→終いの指数推移から算出する3値の加速パターン。
  CK_DATAのLap2/Lap1比較とは異なる区間を見るため、相関が低ければ独立情報として有効な可能性）。
- 検証方法: 既存の`ck_laprank_accel`との相関を確認 → 相関が低ければ独立特徴量として
  LightGBMのfeature importanceで効果測定。

### 4.3 優先度3: youbi（調教曜日）は現状据え置き

`weekendLocation`/`weekAgoLocation`で「前週土日」「1週前水木」の区別は既に
`training_summary.json`で保持されているため、CHAの`youbi`を別途特徴量化する必要性は低い。
着手する場合も優先度は4.2より低い。

## 5. 実装チケット案

1. `ml/features/jrdb_features.py`
   - CHA処理ブロックに `ten_e_idx`, `chukan_e_idx` を追加（数行の追加、低コスト）
   - 新特徴量 `jrdb_cha_ten_idx`, `jrdb_cha_chukan_idx` を`result`辞書と`FEATURE_NAMES`リストに追加
2. 検証スクリプト（`ml/experiment.py`等）
   - 新特徴量と既存`ck_laprank_accel`の相関確認
   - 追加前後でのAUC/VB ROI比較（既存の検証パターンに準拠）
3. 本メモのPhase1再確認
   - `feature_roadmap.md` Phase1のブロッカー（training_summary過去蓄積）着手可否を別途判断

## 6. 所感

書籍「調教タイムの読み方」の内容は、KeibaCICDの現行実装（特に`calculateLapRank`/
`TIME_LEVEL_THRESHOLDS`）に対してほぼ全て後追い、あるいは実データ較正の分だけ現行実装が
書籍を上回っている。今回の書籍消化から生まれた実質的な新規提案は「JRDB CHAのテンF未使用」
1点のみで、これも低コスト・低リスクな追加検証として位置づけるのが妥当。

---

> 本メモは検討用ドラフト。実装は上記チケットのレビュー後に判断する。

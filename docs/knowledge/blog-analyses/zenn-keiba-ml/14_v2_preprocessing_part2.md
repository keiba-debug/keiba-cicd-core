# 14. 【v2.1.1】modules/preprocessing/の解説(後半)

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.14

---

## DataMerger: 馬の過去成績集計＋テーブル結合

### マージ順序
```
1. _merge_race_info()       → レース情報をレース結果に結合
2. _merge_horse_results()   → 馬の過去成績を集計して結合 ★メイン
3. _merge_horse_info()      → 馬の基本情報（birthday, breeder_id）を結合
4. _merge_peds()            → 血統62列を結合
```

### 過去成績集計のロジック（_merge_horse_results）

#### point-in-time処理
```python
# dateより過去に絞る → リーク防止
self._horse_results.query('date < @date').query('index in @horse_id_list')
```
- 日付ごとにループし、**その日より前のデータのみ使用**
- これが「リーク」防止の核心

#### 集計パターン
| 集計 | N走 | グループ | 接尾辞例 |
|------|-----|---------|---------|
| 全体平均 | 5走 | horse_idのみ | `_5R` |
| 全体平均 | 9走 | horse_idのみ | `_9R` |
| 全体平均 | 全走 | horse_idのみ | `_allR` |
| 距離別 | 5走 | horse_id × course_len | `_course_len_5R` |
| 距離別 | 9走 | horse_id × course_len | `_course_len_9R` |
| 距離別 | 全走 | horse_id × course_len | `_course_len_allR` |
| 芝ダ別 | 5走 | horse_id × race_type | `_race_type_5R` |
| 芝ダ別 | 9走 | horse_id × race_type | `_race_type_9R` |
| 芝ダ別 | 全走 | horse_id × race_type | `_race_type_allR` |
| 場所別 | 5走 | horse_id × 開催 | `_開催_5R` |
| 場所別 | 9走 | horse_id × 開催 | `_開催_9R` |
| 場所別 | 全走 | horse_id × 開催 | `_開催_allR` |

#### 集計対象列（TARGET_COLS）
```python
TARGET_COLS = [
    '着順', '賞金', '着差',
    'first_corner', 'final_corner',
    'first_to_rank', 'first_to_final', 'final_to_rank',
    'time_seconds'
]
```

#### 生成される特徴量数（概算）
- 9 TARGET_COLS × (1全体 + 3グループ) × (5R + 9R + allR) = 9 × 4 × 3 = **108列**
- + interval（出走間隔）
- + 血統62列
- + カテゴリ変数ダミー/エンコード

---

## FeatureEngineering: カテゴリ変数処理

### 処理一覧（メソッドチェーン）

| メソッド | 処理 | 方式 |
|---------|------|------|
| add_interval() | 前走からの経過日数 | date - latest |
| add_agedays() | 日齢 | date - birthday |
| dumminize_ground_state() | 馬場状態 | ダミー変数化 |
| dumminize_race_type() | 芝/ダート/障害 | ダミー変数化 |
| dumminize_sex() | 性別 | ダミー変数化 |
| dumminize_weather() | 天気 | ダミー変数化 |
| encode_horse_id() | 馬ID | **ラベルエンコード→category** |
| encode_jockey_id() | 騎手ID | **ラベルエンコード→category** |
| encode_trainer_id() | 調教師ID | **ラベルエンコード→category** |
| encode_owner_id() | 馬主ID | **ラベルエンコード→category** |
| encode_breeder_id() | 生産者ID | **ラベルエンコード→category** |
| dumminize_kaisai() | 開催場所 | ダミー変数化 |
| dumminize_around() | 回り（左/右/直線） | ダミー変数化 |
| dumminize_race_class() | クラス（新馬〜G1） | ダミー変数化 |

### ダミー変数化 vs ラベルエンコード の使い分け
- **カテゴリ数が少ない** → ダミー変数化（weather: 6種、ground_state: 4種 等）
- **カテゴリ数が多い** → ラベルエンコード + category型（horse_id: 数万、jockey_id: 数百 等）
- ラベルエンコードは**過学習しやすい**ので注意

### 訓練↔出馬表の列数統一
- `pd.Categorical()` でMaster定数から全カテゴリを登録
- ダミー変数化時に存在しないカテゴリも列が作られる（全て0）

### ラベルエンコードのマスタ管理
```
1. data/master/horse_id.csv からマスタ読み込み
2. 新しいIDがあればマスタに追加
3. マスタを使ってエンコード
4. category型に変換
```
- 訓練時と予測時で**同じラベルが付与される**ことを保証

---

## ShutubaDataMerger（出馬表版）

- DataMergerを継承
- `merge()`をオーバーライド: `_merge_race_info()`を**スキップ**（出馬表にはレース情報が含まれているため）
- それ以外の処理はDataMergerと同じ

---

## KeibaCICDとの比較

| 項目 | この書籍 v2 | KeibaCICD v4 |
|------|-----------|-------------|
| 過去成績集計 | DataMerger (5R/9R/allR × 4グループ) | past_features.py (5R/all × 条件別) |
| point-in-time | `date < @date` フィルタ | horse_historyキャッシュ（**一部未対応: A-4**） |
| 集計対象 | 着順,賞金,着差,通過順位,タイム(9列) | 着順,賞金,上がり,通過順位等 |
| エンティティID | horse/jockey/trainer/owner/breeder(5種) | 使用せず（集計特徴量のみ） |
| マスタ管理 | CSVでID→ラベル対応保持 | なし（IDは集計のキーとしてのみ使用） |
| 出走間隔 | add_interval() | rotation_features.py |
| 日齢 | add_agedays() | base_features.py（age） |
| 血統 | 62列category | **未実装（A-0予定）** |
| 特徴量数(概算) | ~180列 | ~118列(v5.6) |

## 参考になるポイント

1. **★ 過去成績集計の体系的設計** — TARGET_COLS × GROUP_COLS × N_RACES の直積で特徴量を自動生成。うちは手動で個別定義しているが、この方式の方がスケーラブル
2. **★ point-in-timeの実装** — 日付ごとにループして`date < @date`でフィルタ。うちのA-4（point-in-time化）実装時にこのパターンが参考になる
3. **エンティティID 5種のcategory投入** — horse/jockey/trainer/owner/breeder。うちは集計特徴量のみだが、直接ID投入の方が情報量は多い（過学習リスクあり）
4. **マスタCSVによるID管理** — 訓練時と予測時のラベル一貫性を保証。うちはIDを直接投入しないので不要だが、投入する場合は必須の仕組み
5. **メソッドを列ごとに分離する設計思想** — 変更の影響範囲を最小化。保守性重視

## 特徴量数の比較メモ

この書籍の特徴量（概算）:
- 過去成績集計: 9 × 4 × 3 = 108列
- 基本特徴量: ~15列（枠番,馬番,斤量,体重,年齢,n_horses等）
- 血統: 62列
- ダミー変数: ~15列
- エンティティID: 5列
- **合計: ~205列**

うち(v5.6): 118列（市場モデル）/ 96列（独自モデル）
→ 差分の大部分は血統62列とエンティティID5種

## 次章で確認したいこと

- Ch.15 training（学習の詳細、Optunaの組み込み方）
- Ch.16-17 simulation（回収率シミュレーション）

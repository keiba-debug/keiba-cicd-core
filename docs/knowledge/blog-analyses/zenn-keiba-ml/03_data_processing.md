# 03. データ加工・前処理

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.03

---

## クラス構成

```
DataProcessor（抽象クラス）
├── Results（訓練データ）
└── ShutubaTable（出馬表＝予測用データ）

HorseResults（馬の過去成績）
Peds（血統データ）
```

## データ加工パイプライン（4段階）

```
raw data
  ↓ preprocessing()        … 前処理（型変換・不要列削除・特徴量抽出）
  ↓ merge_horse_results()  … 馬の過去成績を結合
  ↓ merge_peds()           … 血統データを結合
  ↓ process_categorical()  … カテゴリ変数処理
  → data_c（学習/予測用データ完成）
```

---

## preprocessing() で作られる特徴量

### Results（訓練データ）
| 特徴量 | 変換方法 |
|--------|---------|
| rank | 着順 < 4 → 1, else 0（**3着以内の二値分類**） |
| 性 | 性齢の1文字目（牡/牝/セ） |
| 年齢 | 性齢の2文字目以降 |
| 体重 | 馬体重から括弧前を抽出 |
| 体重変化 | 馬体重の括弧内 |
| 単勝 | float変換（オッズ） |
| course_len | 距離 // 100（例: 2000m → 20） |
| 開催 | race_idの5-6桁目（場所コード） |
| n_horses | 同一race_idの出走数 |

- **削除される列**: タイム、着差、調教師、性齢、馬体重、馬名、騎手、人気、着順

### ShutubaTable（出馬表）
- Resultsとほぼ同じ処理だが、着順・単勝等のレース結果列がない
- 使用列: 枠、馬番、斤量、course_len、weather、race_type、ground_state、date、horse_id、jockey_id、性、年齢、体重、体重変化、開催、n_horses

---

## HorseResults（馬の過去成績）の特徴量

### 通過順位から派生する特徴量
| 特徴量 | 定義 | 意味 |
|--------|------|------|
| first_corner | 最初のコーナー位置 | スタート後の位置取り |
| final_corner | 最終コーナー位置 | 4角の位置 |
| final_to_rank | final_corner - 着順 | **追い上げ力**（正=追い込み成功） |
| first_to_rank | first_corner - 着順 | 全体の位置変動 |
| first_to_final | first_corner - final_corner | 道中の位置変動 |

### 集計方法
- **過去N走の平均**: n_samples = [5, 9, 'all'] の3パターン
- **集計対象**: 着順、賞金、着差、first_corner、final_corner、final_to_rank、first_to_rank、first_to_final
- **条件別集計**: 全体平均 + 距離別 + 芝/ダート別 + 開催場所別
- **出走間隔**: `(当日date - 直近5走の最新date).days` → interval列

### point-in-time処理
- `filtered_df = target_df[target_df['date'] < date]` で**未来データのリーク防止**
- 各開催日ごとにmergeして全日程をconcat

---

## 血統データ（Peds）の処理

- 5世代62頭分の血統テーブル → `peds_0` 〜 `peds_61` の62列
- **LabelEncoding → category型** に変換
- LightGBMのcategory feature機能でそのまま投入
  - 整数category型（0始まり連続整数）が必要
  - LightGBMが内部で最適な分割を自動学習

---

## カテゴリ変数の処理

| 変数 | 処理方法 |
|------|---------|
| horse_id | LabelEncoder → category型 |
| jockey_id | LabelEncoder → category型 |
| weather | ダミー変数化（get_dummies） |
| race_type | ダミー変数化 |
| ground_state | ダミー変数化 |
| 性 | ダミー変数化 |

- **訓練↔出馬表の列数整合**: pd.Categoricalで全カテゴリを登録してからダミー変数化
- LabelEncoderは訓練時に作成し、出馬表にも同じものを適用

---

## KeibaCICDとの比較

| 項目 | この書籍 | KeibaCICD |
|------|---------|-----------|
| 目的変数 | **rank（3着以内=1）の二値分類** | 好走(top3)二値 + 勝利二値 + AR回帰 |
| 過去成績集計 | 5走/9走/全走の平均 | horse_historyキャッシュから特徴量生成 |
| 条件別集計 | 距離別・芝ダ別・場所別 | 距離別・芝ダ別・場所別（同様） |
| 通過順位特徴量 | first/final_corner + 差分3種 | running_style_features（脚質系） |
| 血統 | 62列LabelEncoding→category | **未実装（A-0予定）** |
| カテゴリ処理 | LabelEncoder + get_dummies | LabelEncoder（LightGBM category） |
| point-in-time | `date < date` フィルタ | **一部未対応（A-4予定）** |
| horse_id/jockey_id | category型で直接投入 | 使用せず（集計特徴量のみ） |

## 参考になるポイント

1. **★ 血統62列のLabelEncoding→category** — A-0実装時にこの方式が最もシンプル。LightGBMのcategory feature機能に任せる
2. **★ point-in-timeの実装パターン** — `date < date`で未来リーク防止。うちのA-4実装時に参考
3. **通過順位の差分特徴量** — `final_to_rank`（追い上げ力）は面白い。うちのrunning_style_featuresにもあるが、命名が明確
4. **horse_id/jockey_idをcategory型で直接投入** — エンティティ埋め込み的なアプローチ。LightGBMが内部で学習する。うちは集計特徴量のみなので別アプローチ
5. **条件別の過去成績平均** — 距離別・芝ダ別・場所別に分けて集計するのはうちと同じ戦略。N走の選び方（5/9/all）は参考になる
6. **出走間隔(interval)** — うちのrotation_features.pyと同じ発想

## 次章で確認したいこと

- LightGBMのモデル学習の具体的な設定（パラメータ、Optuna）
- 回収率シミュレーションの方法
- 馬券種別ごとの購入戦略

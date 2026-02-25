# 09. 【v2.1.1】ディレクトリ構成と実行コード

> 出典: Zenn「競馬予想で始める機械学習〜完全版〜」Ch.09

---

## ディレクトリ構成

```
.
├── main.ipynb                    # 実行エントリポイント
├── data/
│   ├── html/                     # スクレイピングしたHTML(bin)を保存
│   │   ├── horse/
│   │   ├── ped/
│   │   └── race/
│   ├── master/                   # マスタデータ
│   ├── raw/                      # 加工前pickle
│   │   ├── results.pickle
│   │   ├── horse_results.pickle
│   │   ├── race_info.pickle
│   │   ├── peds.pickle
│   │   ├── return_tables.pickle
│   │   └── horse_info.pickle
│   └── tmp/                      # 一時ファイル
├── models/                       # 学習済みモデル保存
└── modules/                      # ソースコード本体
    ├── constants/                # 定数定義
    ├── preparing/                # スクレイピング〜rawデータ作成
    ├── preprocessing/            # 前処理・特徴量エンジニアリング
    ├── training/                 # モデル学習
    ├── policies/                 # 予測スコア算出ロジック・購入戦略
    └── simulation/               # 回収率シミュレーション
```

---

## モジュール構成の設計思想

| モジュール | 責務 |
|-----------|------|
| **preparing** | データ取得（スクレイピング・HTML保存・raw生成） |
| **preprocessing** | 前処理・テーブル結合・特徴量エンジニアリング |
| **training** | モデル学習・保存・ロード（KeibaAIFactory） |
| **policies** | 予測スコア算出ポリシー・馬券購入戦略 |
| **simulation** | 回収率シミュレーション・プロット |
| **constants** | パス・カラム名等の定数 |

---

## 実行フロー（main.ipynb）

### 学習フロー
```
1. preparing: スクレイピング → HTML保存 → rawデータ生成 → pickle保存
2. preprocessing: Processor群で前処理 → DataMergerで結合
3. preprocessing: FeatureEngineering（チェーン呼び出し）
4. training: KeibaAIFactory.create() → train_with_tuning()
5. simulation: Simulator + BetPolicy → 回収率プロット
```

### 予測フロー（レース当日）
```
前日:
  - race_id取得 → horse_id取得
  - 馬の過去成績・血統を再スクレイピング（skip=False）
  - Processor更新

当日:
  - create_active_race_id_list() で馬体重発表済みレース取得
  - 各レースごとにループ:
    - 出馬表スクレイピング
    - ShutubaDataMerger → FeatureEngineering
    - calc_score() → 予測スコア表示
```

---

## 特徴量エンジニアリング（チェーンパターン）

```python
feature_engineering = preprocessing.FeatureEngineering(data_merger)\
    .add_interval()\          # 出走間隔
    .add_agedays()\           # 日齢
    .dumminize_ground_state()\ # 馬場状態ダミー変数
    .dumminize_race_type()\   # 芝/ダートダミー変数
    .dumminize_sex()\         # 性別ダミー変数
    .dumminize_weather()\     # 天気ダミー変数
    .encode_horse_id()\       # 馬IDエンコード
    .encode_jockey_id()\      # 騎手IDエンコード
    .encode_trainer_id()\     # 調教師IDエンコード
    .encode_owner_id()\       # 馬主IDエンコード
    .encode_breeder_id()\     # 生産者IDエンコード
    .dumminize_kaisai()\      # 開催場所ダミー変数
    .dumminize_around()\      # 回り（左/右）ダミー変数
    .dumminize_race_class()   # レースクラスダミー変数
```

### v1からの追加特徴量
| 特徴量 | 備考 |
|--------|------|
| interval | 出走間隔（v1の6/6追加と同じ） |
| agedays | **日齢**（v1にはなかった） |
| trainer_id | **調教師ID**（v1にはなかった） |
| owner_id | **馬主ID**（v1にはなかった） |
| breeder_id | **生産者ID**（v1にはなかった） |
| around | **コースの回り**（v1にはなかった） |
| race_class | **レースクラス**（v1にはなかった） |

---

## 馬の過去成績の集計対象

```python
TARGET_COLS = [
    'RANK',           # 着順
    'PRIZE',          # 賞金
    'RANK_DIFF',      # 着差
    'first_corner',   # 1角位置
    'final_corner',   # 4角位置
    'first_to_rank',  # 1角→着順
    'first_to_final', # 1角→4角
    'final_to_rank',  # 4角→着順
    'time_seconds'    # 走破タイム（秒）★v2で追加
]

GROUP_COLS = [
    'course_len',     # 距離別
    'race_type',      # 芝/ダート別
    'PLACE'           # 開催場所別
]
```

- **time_seconds** がv2で追加 — 走破タイムの集計が入った

---

## HTMLキャッシュ方式

- スクレイピング結果をHTML(bin)として保存し、再利用
- `skip=True`: 既存HTMLがあればスキップ
- `skip=False`: 上書き（最新データが必要な場合）
- `update_master`: スクレイピング日付を記録してトラッキング

---

## KeibaCICDとの比較

| 項目 | この書籍 v2 | KeibaCICD v4 |
|------|-----------|-------------|
| エントリポイント | main.ipynb（Jupyter） | CLIスクリプト群 |
| データ保存 | pickle | JSON |
| HTMLキャッシュ | bin保存 + skip機能 | JRA-VAN直読（キャッシュ不要） |
| モジュール分割 | 6モジュール | builders/ + ml/ + analysis/ + web/ |
| 特徴量追加パターン | FeatureEngineeringチェーン | features/モジュール個別追加 |
| エンコード対象 | horse/jockey/trainer/owner/breeder | horse/jockey（集計特徴量） |
| 走破タイム | time_seconds（v2追加） | speed_features.py |

## 参考になるポイント

1. **FeatureEngineeringのチェーンパターン** — メソッドチェーンで特徴量追加を宣言的に記述。可読性高い
2. **owner_id / breeder_id のエンコード** — 馬主・生産者もcategory特徴量に。うちのinsightsにも「owner_as_feature.md」があるが未実装
3. **HTMLキャッシュ + skip機能** — スクレイピング効率化。うちはJRA-VANなので不要だが設計思想は参考
4. **time_seconds の過去成績集計** — うちのspeed_features.pyと同じ方向性
5. **KeibaAIFactory（ファクトリーパターン）** — モデルの生成・保存・ロードを1クラスに集約

## 次章で確認したいこと

- Ch.10 定数定義の詳細
- Ch.11以降 preparing/preprocessingの具体的実装

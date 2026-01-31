# 馬情報スクレイピングシステム ドキュメント

## 概要
馬情報スクレイピングシステムは、競馬ブックサイトから馬の詳細情報を取得し、体系的に管理するためのツールです。

## 主な機能

1. **馬プロファイル管理**
   - 馬ごとの情報を `{horse_id}_{馬名}.md` 形式で保存
   - 自動生成データとユーザー追記可能な領域を分離
   - 既存のレースデータから馬情報を抽出
   - 過去成績の時系列テーブル表示

2. **データ取得方法**
   - 整理済みMDファイルからの馬情報抽出
   - 開催日指定による一括プロファイル生成
   - WIN5対象レースに特化した処理

## 使用方法

### 推奨: horse_profile_cli を使用

```bash
# 特定日のWIN5対象馬プロファイルを生成
python -m src.horse_profile_cli --date 2025/09/14 --win5

# 特定日の全レース出走馬プロファイルを生成
python -m src.horse_profile_cli --date 2025/09/14 --all

# 過去成績を含む詳細プロファイルを生成
python -m src.horse_profile_cli --date 2025/09/14 --win5 --with-history

# 特定の馬IDのプロファイルを生成
python -m src.horse_profile_cli --horse-id 0936453 --horse-name カムニャック

# 特定のレースファイルから馬情報を抽出
python -m src.horse_profile_cli --race-file Z:/KEIBA-CICD/data/organized/2025/09/14/阪神/202504010411.md
```

### Python スクリプトから実行

```python
from src.scrapers.horse_profile_manager import HorseProfileManager

# マネージャーのインスタンスを作成
manager = HorseProfileManager()

# WIN5対象馬のプロファイルを更新
results = manager.update_win5_horses("2025/09/14")

# 詳細プロファイルを生成
manager.create_horse_profile("0936453", "カムニャック", include_history=True)
```

### fast_batch_cli との統合実行

```bash
# データ取得と馬プロファイル生成を一括実行
python -m src.fast_batch_cli full --start 2025/09/14 --end 2025/09/14 --horse-profiles --win5-only

# 全オプション指定の例
python -m src.fast_batch_cli full \
  --start 2025/09/14 \
  --end 2025/09/14 \
  --data-types seiseki,shutsuba,cyokyo,danwa,syoin,paddok \
  --horse-profiles \
  --win5-only \
  --delay 0.5 \
  --max-workers 8
```

### 個別の馬情報を取得

```python
# 特定の馬のプロファイルを作成
manager.create_horse_profile("0936453", "カムニャック")
```

### レースファイルから馬情報を抽出

```python
from pathlib import Path

# レースファイルから出走馬情報を抽出
race_file = Path("Z:/KEIBA-CICD/data/organized/2025/09/14/阪神/202504010411.md")
horses = manager.extract_horses_from_race(race_file)

for horse_id, horse_name, horse_data in horses:
    print(f"{horse_id}: {horse_name}")
```

## ファイル構造

### プロファイルファイルの保存場所
```
Z:/KEIBA-CICD/data/horses/profiles/
├── 0936453_カムニャック.md
├── 0886989_ヤマニンループ.md
└── ...
```

### プロファイルファイルの形式

```markdown
# 馬プロファイル: {馬名}

## 基本情報
- **馬ID**: {horse_id}
- **馬名**: {馬名}
- **性齢**: {性齢}
- **更新日時**: {日時}

## 最近の成績
[レースファイルから抽出した情報]

---
## ユーザーメモ
[ユーザーが自由に追記できる領域]
```

## プロファイルファイル形式

### 標準プロファイル
```markdown
# 馬プロファイル: {馬名}

## 基本情報
- 馬ID, 馬名, 性齢, 騎手, 斤量

## 最近の出走情報
- オッズ, AI指数, 本誌印, 短評

## 分析メモ
- 強み, 弱み, 狙い目条件

## ユーザーメモ
（自由記入領域）
```

### 詳細プロファイル（--with-history オプション）
```markdown
## 過去成績分析

### 成績サマリー
| 項目 | 1着 | 2着 | 3着 | 着外 | 勝率 | 連対率 | 複勝率 |

### 最近10走の成績
| 日付 | 競馬場 | レース | 着順 | 騎手 | 距離 | 馬場 | タイム | 上がり |

### 距離別成績
| 距離 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 特記事項 |

### 馬場状態別成績
| 馬場 | 出走数 | 勝利 | 連対 | 複勝 | 勝率 | 特記事項 |
```

## API リファレンス

### horse_profile_cli コマンドラインオプション

| オプション | 説明 | 例 |
|-----------|------|-----|
| `--date` | 対象日付 (YYYY/MM/DD) | `--date 2025/09/14` |
| `--win5` | WIN5対象レースのみ処理 | `--win5` |
| `--all` | 全レースの出走馬を処理 | `--all` |
| `--with-history` | 過去成績を含む詳細プロファイル | `--with-history` |
| `--horse-id` | 特定の馬IDを指定 | `--horse-id 0936453` |
| `--horse-name` | 馬名を指定 | `--horse-name カムニャック` |
| `--race-file` | 特定のレースファイルを指定 | `--race-file {path}` |
| `--output-dir` | 出力ディレクトリを指定 | `--output-dir {path}` |

### HorseProfileManager クラス

#### `create_horse_profile(horse_id, horse_name, horse_data=None, include_history=False)`
馬のプロファイルファイルを作成または更新します。

**パラメータ:**
- `horse_id`: 馬のID
- `horse_name`: 馬名
- `horse_data`: 馬の追加情報（オプション）
- `include_history`: 過去成績を含めるか（デフォルト: False）

**戻り値:**
- 作成されたプロファイルファイルのパス

#### `update_win5_horses(date)`
指定日のWIN5対象馬のプロファイルを更新します。

**パラメータ:**
- `date`: 日付（例: "2025/09/14"）

**戻り値:**
- レースごとの処理結果

## 今後の拡張予定

1. **競馬ブックからの直接スクレイピング**
   - `https://p.keibabook.co.jp/db/uma/{horse_id}/kanzen` からの詳細情報取得
   - 過去レース成績の自動取得

2. **データの自動更新**
   - 定期的なプロファイル更新
   - レース結果の自動反映

3. **分析機能の追加**
   - 馬の傾向分析
   - パフォーマンス指標の計算

## トラブルシューティング

### エンコーディングエラーが発生する場合
ファイルの読み書きは UTF-8 で行われます。エラーが発生する場合は、システムの文字コード設定を確認してください。

### ファイルが見つからない場合
`Z:/KEIBA-CICD/data/` ディレクトリが存在することを確認してください。

## 関連ファイル

- **実装コード**: `keiba-cicd-core/KeibaCICD.keibabook/src/scrapers/horse_profile_manager.py`
- **プロファイル保存先**: `Z:/KEIBA-CICD/data/horses/profiles/`
- **レースデータ**: `Z:/KEIBA-CICD/data/organized/`

## 更新履歴

- 2025-09-13: v2.0
  - `horse_profile_cli` コマンドラインツールを追加
  - 開催日指定による馬プロファイル一括更新機能
  - 過去成績の時系列テーブル表示機能を実装
  - `--with-history` オプションで詳細プロファイル生成

- 2025-09-13: v1.0
  - 基本的な馬プロファイル管理機能を実装
  - WIN5対象馬の一括処理機能を追加
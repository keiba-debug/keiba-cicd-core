# 競馬データ取得システム v2.0 - APIリファレンス

## 📋 概要

競馬データ取得システム v2.0（リファクタリング完了版）の各モジュール・クラス・関数の詳細仕様書です。

**最終更新**: 2025年2月4日  
**システムバージョン**: v2.0  
**アーキテクチャ**: 統合CLI + モジュール化

---

## 🗂 システム構成

### 新しいアーキテクチャ（v2.0）

```
src/keibabook/
├── 📁 batch/                   # 🆕 統合バッチ処理システム
│   ├── core/
│   │   ├── __init__.py
│   │   └── common.py           # 共通ユーティリティ
│   ├── data_fetcher.py         # データ取得モジュール
│   └── __init__.py
├── 📁 scrapers/                # スクレイパーモジュール
│   ├── __init__.py
│   ├── base_scraper.py
│   ├── keibabook_scraper.py
│   ├── requests_scraper.py
│   └── legacy_scrapers.py      # 🆕 レガシー機能統合
├── 📁 parsers/                 # パーサーモジュール
├── 📁 utils/                   # ユーティリティ
├── batch_cli.py                # 🆕 統合CLIシステム
├── main.py                     # 従来エントリーポイント
└── auth.py                     # 認証機能
```

---

## 🚀 統合CLIシステム（batch_cli.py）

### 概要
新しい統合コマンドラインインターフェース。3つのサブコマンドで全機能を提供。

### 基本構文
```bash
python -m src.keibabook.batch_cli <subcommand> [options]
```

### サブコマンド

#### 1. schedule - レース日程取得
レース日程を取得してレースIDを生成・保存

```bash
python -m src.keibabook.batch_cli schedule \
  --start-date YYYY/MM/DD \
  [--end-date YYYY/MM/DD] \
  [--delay SECONDS] \
  [--debug]
```

**引数**:
- `--start-date`: 取得開始日（必須）
- `--end-date`: 取得終了日（省略時は開始日と同じ）
- `--delay`: リクエスト間隔（デフォルト: 3秒）
- `--debug`: デバッグモード

**実行例**:
```bash
# 単日取得
python -m src.keibabook.batch_cli schedule --start-date 2025/02/04

# 期間取得
python -m src.keibabook.batch_cli schedule \
  --start-date 2025/02/01 \
  --end-date 2025/02/07 \
  --delay 5
```

#### 2. data - レースデータ取得
既存のレースIDを使用してデータを取得

```bash
python -m src.keibabook.batch_cli data \
  --start-date YYYY/MM/DD \
  [--end-date YYYY/MM/DD] \
  [--data-types TYPE1,TYPE2,...] \
  [--delay SECONDS] \
  [--debug]
```

**引数**:
- `--start-date`: 取得開始日（必須）
- `--end-date`: 取得終了日（省略時は開始日と同じ）
- `--data-types`: データタイプ（デフォルト: seiseki,shutsuba,cyokyo）
- `--delay`: リクエスト間隔（デフォルト: 3秒）
- `--debug`: デバッグモード

**データタイプ**:
- `seiseki`: レース成績
- `shutsuba`: 出馬表
- `cyokyo`: 調教データ
- `danwa`: 厩舎の話

**実行例**:
```bash
# 成績のみ取得
python -m src.keibabook.batch_cli data \
  --start-date 2025/02/04 \
  --data-types seiseki

# 全データタイプ取得
python -m src.keibabook.batch_cli data \
  --start-date 2025/02/04 \
  --data-types seiseki,shutsuba,cyokyo,danwa
```

#### 3. full - 全処理実行
日程取得からデータ取得まで一括実行

```bash
python -m src.keibabook.batch_cli full \
  --start-date YYYY/MM/DD \
  [--end-date YYYY/MM/DD] \
  [--data-types TYPE1,TYPE2,...] \
  [--delay SECONDS] \
  [--wait-between-phases SECONDS] \
  [--debug]
```

**引数**:
- `--start-date`: 取得開始日（必須）
- `--end-date`: 取得終了日（省略時は開始日と同じ）
- `--data-types`: データタイプ（デフォルト: seiseki,shutsuba,cyokyo）
- `--delay`: リクエスト間隔（デフォルト: 3秒）
- `--wait-between-phases`: Phase間待機時間（デフォルト: 5秒）
- `--debug`: デバッグモード

**実行例**:
```bash
# 基本的な全処理
python -m src.keibabook.batch_cli full --start-date 2025/02/04

# カスタム設定での全処理
python -m src.keibabook.batch_cli full \
  --start-date 2025/02/01 \
  --end-date 2025/02/07 \
  --data-types seiseki,shutsuba \
  --delay 5 \
  --wait-between-phases 10 \
  --debug
```

---

## 🔧 バッチ処理モジュール（batch/）

### 📁 batch/core/common.py

#### 主要関数

##### `parse_date(date_str: str) -> datetime.date`
日付文字列をdateオブジェクトに変換

**引数**:
- `date_str`: 日付文字列（YYYY/MM/DD, YY/MM/DD）

**戻り値**: `datetime.date`オブジェクト

**例外**: `ValueError` - 無効な日付形式

**使用例**:
```python
from src.keibabook.batch import parse_date

date_obj = parse_date("2025/02/04")  # datetime.date(2025, 2, 4)
date_obj = parse_date("25/02/04")    # datetime.date(2025, 2, 4)
```

##### `setup_batch_logger(name: str) -> logging.Logger`
バッチ処理用のロガーを設定

**引数**:
- `name`: ロガー名

**戻り値**: 設定済み`logging.Logger`

**使用例**:
```python
from src.keibabook.batch import setup_batch_logger

logger = setup_batch_logger('my_batch')
logger.info("バッチ処理を開始します")
```

##### `ensure_batch_directories() -> Dict[str, Path]`
必要なディレクトリを作成し、パス辞書を返す

**戻り値**: ディレクトリパスの辞書

**使用例**:
```python
from src.keibabook.batch import ensure_batch_directories

dirs = ensure_batch_directories()
print(dirs['seiseki'])  # Path to seiseki directory
```

##### `create_authenticated_session() -> requests.Session`
Cookie認証付きセッションを作成

**戻り値**: 認証済み`requests.Session`

**使用例**:
```python
from src.keibabook.batch import create_authenticated_session

session = create_authenticated_session()
response = session.get("https://p.keibabook.co.jp/...")
```

#### BatchStats クラス

**概要**: バッチ処理の統計情報を管理

```python
class BatchStats:
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_races: int = 0
        self.success_count: int = 0
        self.error_count: int = 0
        self.skipped_count: int = 0
        self.successful_items: List[str] = []
        self.error_items: List[str] = []
```

**主要メソッド**:

##### `start() -> None`
統計記録を開始

##### `finish() -> None`
統計記録を終了

##### `add_success(item_id: str) -> None`
成功アイテムを追加

##### `add_error(item_id: str) -> None`
エラーアイテムを追加

##### `add_skip() -> None`
スキップカウントを増加

##### `print_summary(logger: logging.Logger) -> None`
統計サマリーをログ出力

##### `to_dict() -> Dict[str, Any]`
統計情報を辞書形式で取得

**使用例**:
```python
from src.keibabook.batch import BatchStats

stats = BatchStats()
stats.start()

# 処理実行
stats.add_success("202502041211")
stats.add_error("202502041212")

stats.finish()
stats.print_summary(logger)
```

### 📁 batch/data_fetcher.py

#### DataFetcher クラス

**概要**: データ取得の統合クラス

```python
class DataFetcher:
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = setup_batch_logger('data_fetcher')
        self.session = create_authenticated_session()
        self.dirs = ensure_batch_directories()
```

**主要メソッド**:

##### `load_race_ids(date: datetime.date) -> List[Dict[str, str]]`
指定日のレースID情報を読み込み

**引数**:
- `date`: 対象日

**戻り値**: レースID情報のリスト

##### `fetch_race_schedule_page(date: datetime.date) -> Optional[str]`
レース日程ページのHTMLを取得

**引数**:
- `date`: 対象日

**戻り値**: HTMLコンテンツまたはNone

##### `extract_race_ids_from_html(html_content: str, date: datetime.date) -> Dict[str, List[Dict[str, str]]]`
HTMLからレースID情報を抽出

**引数**:
- `html_content`: HTMLコンテンツ
- `date`: 対象日

**戻り値**: 開催場所別レース情報

##### `fetch_race_data(race_id: str, data_type: str) -> Optional[str]`
指定レース・データタイプのHTMLを取得

**引数**:
- `race_id`: レースID（12桁）
- `data_type`: データタイプ（seiseki/shutsuba/cyokyo/danwa）

**戻り値**: HTMLコンテンツまたはNone

##### `fetch_period_schedule(start_date: datetime.date, end_date: datetime.date, delay: int = 3) -> None`
期間内のレース日程を取得

**引数**:
- `start_date`: 開始日
- `end_date`: 終了日
- `delay`: リクエスト間隔（秒）

##### `fetch_period_data(start_date: datetime.date, end_date: datetime.date, data_types: List[str], delay: int = 3) -> None`
期間内のレースデータを取得

**引数**:
- `start_date`: 開始日
- `end_date`: 終了日
- `data_types`: データタイプのリスト
- `delay`: リクエスト間隔（秒）

**使用例**:
```python
from src.keibabook.batch import DataFetcher, parse_date

fetcher = DataFetcher(debug=True)

# 日程取得
start_date = parse_date("2025/02/04")
end_date = parse_date("2025/02/07")
fetcher.fetch_period_schedule(start_date, end_date)

# データ取得
fetcher.fetch_period_data(start_date, end_date, ['seiseki', 'shutsuba'])
```

---

## 🕷️ スクレイパーモジュール（scrapers/）

### 📁 scrapers/legacy_scrapers.py

#### RaceIdExtractor クラス

**概要**: レースID抽出ユーティリティ

##### `extract_from_url(url: str) -> Optional[str]`（静的メソッド）
URLからレースIDを抽出

**引数**:
- `url`: 対象URL

**戻り値**: レースID（12桁）またはNone

**使用例**:
```python
from src.keibabook.scrapers import RaceIdExtractor

race_id = RaceIdExtractor.extract_from_url(
    "https://p.keibabook.co.jp/cyuou/seiseki/202502041211"
)
print(race_id)  # "202502041211"
```

##### `parse_race_id(race_id: str) -> Tuple[str, str, str]`（静的メソッド）
レースIDを分解

**引数**:
- `race_id`: レースID（12桁）

**戻り値**: (日付, 会場, レース番号)のタプル

**例外**: `ValueError` - 無効なレースID形式

**使用例**:
```python
date_part, venue_part, race_part = RaceIdExtractor.parse_race_id("202502041211")
print(f"日付: {date_part}, 会場: {venue_part}, レース: {race_part}")
# 日付: 20250204, 会場: 12, レース: 11
```

#### 特殊データ用スクレイパー

##### DanwaScraper クラス
談話記事のスクレイピング

##### SyutubaScraper クラス
出馬表のスクレイピング

##### DanwaTableScraper クラス
厩舎の話テーブルのスクレイピング

##### CyokyoSemekaisetuScraper クラス
調教攻め解説のスクレイピング

**使用例**:
```python
from src.keibabook.scrapers import DanwaScraper
from src.keibabook.batch import create_authenticated_session

session = create_authenticated_session()
scraper = DanwaScraper(session)

url = "https://p.keibabook.co.jp/cyuou/danwa/0/202502041211"
data = scraper.scrape_danwa(url)
if data:
    scraper.save_danwa(data)
```

### 📁 scrapers/keibabook_scraper.py

#### KeibabookScraper クラス

**概要**: 競馬ブック専用Seleniumスクレイパー

**主要メソッド**:

##### `scrape_seiseki_page(race_id: str, save_html_path: str = None) -> str`
成績ページをスクレイピング

**引数**:
- `race_id`: レースID
- `save_html_path`: HTMLファイル保存パス（オプション）

**戻り値**: HTMLコンテンツ

### 📁 scrapers/requests_scraper.py

#### RequestsScraper クラス

**概要**: 軽量HTTP requests スクレイパー

**主要メソッド**:

##### `scrape_seiseki_page(race_id: str, save_html_path: str = None) -> str`
成績ページをスクレイピング（HTTP直接）

---

## 📊 データモデル

### Pydantic モデル

#### DanwaData
```python
class DanwaData(BaseModel):
    race_id: str
    horse_number: int
    horse_name: str
    stable_comment: str
    article_id: str
    scraped_at: str
```

#### SyutubaHorseData
```python
class SyutubaHorseData(BaseModel):
    race_id: str
    horse_number: int
    horse_name: str
    sex_age: str
    jockey: str
    trainer: str
    short_comment: str
```

#### DanwaTableHorseData
```python
class DanwaTableHorseData(BaseModel):
    race_id: str
    horse_number: int
    horse_name: str
    stable_comment: str
```

#### CyokyoSemekaisetuData
```python
class CyokyoSemekaisetuData(BaseModel):
    race_id: str
    horse_number: int
    horse_name: str
    attack_explanation: str
```

---

## 🔧 従来システム（互換性維持）

### 📁 main.py

#### 基本使用方法
```bash
python src/keibabook/main.py \
  --race-id RACE_ID \
  --mode MODE \
  [--use-requests] \
  [--debug]
```

**引数**:
- `--race-id`: レースID（12桁）
- `--mode`: 実行モード
  - `scrape_and_parse`: スクレイピング + パース
  - `parse_only`: パースのみ
  - `multi_type`: 複数データタイプ処理
- `--use-requests`: requests スクレイパーを使用
- `--debug`: デバッグモード

**実行例**:
```bash
# 成績データの取得・パース
python src/keibabook/main.py \
  --race-id 202502041211 \
  --mode scrape_and_parse

# 複数データタイプの処理
python src/keibabook/main.py \
  --race-id 202502041211 \
  --mode multi_type \
  --data-types seiseki syutuba cyokyo
```

---

## 🔄 パフォーマンス指標

### 推奨設定（v2.0）

| 項目 | 推奨値 | 説明 |
|------|--------|------|
| リクエスト間隔 | 3秒以上 | サーバー負荷軽減 |
| タイムアウト | 30秒 | ネットワーク安定性 |
| リトライ回数 | 3回 | エラー対応 |
| 同時接続数 | 1 | シーケンシャル処理 |
| Phase間待機 | 5秒以上 | 処理安定性 |

### メモリ・ストレージ使用量

| 項目 | 使用量 | 備考 |
|------|--------|------|
| HTMLファイル | 100KB/ファイル | 平均値 |
| JSONファイル | 50KB/ファイル | パース後 |
| メモリ使用量 | 50-100MB | 通常動作時 |
| ログファイル | 10MB/日 | 推定値 |

---

## 🚨 エラーハンドリング

### 共通例外

| 例外 | 発生場面 | 対処方法 |
|------|----------|----------|
| `ValueError` | 無効な引数・データ | 引数確認・修正 |
| `FileNotFoundError` | ファイル未発見 | パス確認・作成 |
| `requests.RequestException` | ネットワークエラー | 接続確認・リトライ |
| `TimeoutError` | タイムアウト | 待機時間調整 |

### カスタムエラーパターン

#### 認証エラー
```python
# エラー例
# AuthenticationError: Cookie expired

# 対処法
# 1. .envファイルのCookie更新
# 2. ブラウザで再ログイン後、新しいCookie取得
```

#### レースID未発見エラー
```python
# エラー例
# RaceIdNotFoundError: No race found for date 2025/02/04

# 対処法
# 1. 日付の確認
# 2. 開催の有無確認
# 3. 日程取得の再実行
```

---

## 🔍 デバッグ・ログ

### ログレベル

| レベル | 用途 | 設定方法 |
|--------|------|----------|
| `DEBUG` | 詳細デバッグ | `LOG_LEVEL=DEBUG` |
| `INFO` | 通常情報 | `LOG_LEVEL=INFO` |
| `WARNING` | 警告 | `LOG_LEVEL=WARNING` |
| `ERROR` | エラー | `LOG_LEVEL=ERROR` |

### デバッグコマンド
```bash
# 詳細ログ付き実行
python -m src.keibabook.batch_cli full \
  --start-date 2025/02/04 \
  --debug

# 特定モジュールのログ確認
grep "DataFetcher" logs/*.log

# エラーログのみ確認
grep "ERROR" logs/*.log
```

---

## 🔗 インポート・使用方法

### 基本インポート
```python
# 統合バッチシステム
from src.keibabook.batch import (
    DataFetcher, 
    parse_date, 
    setup_batch_logger,
    BatchStats
)

# スクレイパー
from src.keibabook.scrapers import (
    KeibabookScraper,
    RequestsScraper,
    RaceIdExtractor
)

# レガシースクレイパー
from src.keibabook.scrapers import (
    DanwaScraper,
    SyutubaScraper,
    DanwaData,
    SyutubaHorseData
)
```

### 実用的な使用例
```python
from src.keibabook.batch import DataFetcher, parse_date
from src.keibabook.scrapers import RaceIdExtractor

# データ取得の基本フロー
fetcher = DataFetcher(debug=True)

# 日程取得
start_date = parse_date("2025/02/04")
fetcher.fetch_period_schedule(start_date, start_date)

# データ取得
fetcher.fetch_period_data(start_date, start_date, ['seiseki'])

# レースID解析
race_id = "202502041211"
date_part, venue_part, race_part = RaceIdExtractor.parse_race_id(race_id)
print(f"Date: {date_part}, Venue: {venue_part}, Race: {race_part}")
```

---

## 📞 サポート・リファレンス

### 関連ドキュメント
- [workflow_guide.md](workflow_guide.md) - 完全ワークフロー
- [configuration_guide.md](configuration_guide.md) - 設定・カスタマイズ
- [data_specification.md](data_specification.md) - データ仕様
- [troubleshooting.md](troubleshooting.md) - トラブルシューティング

### バージョン履歴
- **v2.0** (2025-02-04): リファクタリング完了、統合CLI実装
- **v1.0** (初期版): 基本スクレイピング・パース機能

---

**最終更新**: 2025年2月4日  
**システムバージョン**: v2.0  
**API安定性**: 安定版
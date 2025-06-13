# 競馬データ取得システム v2.3 - APIリファレンス

## 📋 概要

競馬データ取得システム v2.3（高速版対応）の各モジュール・クラス・関数の詳細仕様書です。

**最終更新**: 2025年6月7日  
**システムバージョン**: v2.3  
**アーキテクチャ**: 統合CLI + モジュール化 + 高速版  
**新機能**: 🚀 RequestsScraperによる高速化（10-20倍高速）

---

## 🗂 システム構成

### 新しいアーキテクチャ（v2.3）

```
src/keibabook/
├── 📁 batch/                   # 🆕 統合バッチ処理システム
│   ├── core/
│   │   ├── __init__.py
│   │   └── common.py           # 共通ユーティリティ
│   ├── data_fetcher.py         # データ取得モジュール（従来版）
│   ├── optimized_data_fetcher.py # 🚀 高速版データ取得モジュール
│   └── __init__.py
├── 📁 scrapers/                # スクレイパーモジュール
│   ├── __init__.py
│   ├── base_scraper.py
│   ├── keibabook_scraper.py    # Selenium版（従来）
│   ├── requests_scraper.py     # 🚀 高速版（requests）
│   └── legacy_scrapers.py      # 🆕 レガシー機能統合
├── 📁 parsers/                 # パーサーモジュール
├── 📁 utils/                   # ユーティリティ
├── batch_cli.py                # 🆕 統合CLIシステム（従来版）
├── fast_batch_cli.py           # 🚀 高速版CLIシステム
├── main.py                     # 従来エントリーポイント
└── auth.py                     # 認証機能
```

---

## 🚀 高速版CLIシステム（fast_batch_cli.py）- 推奨

### 概要
RequestsScraperを使用した高速版コマンドラインインターフェース。従来版の10-20倍の速度を実現。

### 基本構文
```bash
python -m src.keibabook.fast_batch_cli <subcommand> [options]
```

### サブコマンド

#### 1. schedule - 高速レース日程取得
レース日程を高速取得してレースIDを生成・保存

```bash
python -m src.keibabook.fast_batch_cli schedule \
  --start-date YYYY/MM/DD \
  [--end-date YYYY/MM/DD] \
  [--delay SECONDS] \
  [--max-workers NUM] \
  [--debug]
```

**引数**:
- `--start-date`: 取得開始日（必須）
- `--end-date`: 取得終了日（省略時は開始日と同じ）
- `--delay`: リクエスト間隔（デフォルト: 1.0秒）
- `--max-workers`: 並列処理数（デフォルト: 5）
- `--debug`: デバッグモード

**実行例**:
```bash
# 単日高速取得
python -m src.keibabook.fast_batch_cli schedule --start-date 2025/06/07

# 期間高速取得
python -m src.keibabook.fast_batch_cli schedule \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --delay 0.5
```

#### 2. data - 高速レースデータ取得（並列処理）
既存のレースIDを使用して並列でデータを高速取得

```bash
python -m src.keibabook.fast_batch_cli data \
  --start-date YYYY/MM/DD \
  [--end-date YYYY/MM/DD] \
  [--data-types TYPE1,TYPE2,...] \
  [--delay SECONDS] \
  [--max-workers NUM] \
  [--debug]
```

**引数**:
- `--start-date`: 取得開始日（必須）
- `--end-date`: 取得終了日（省略時は開始日と同じ）
- `--data-types`: データタイプ（デフォルト: seiseki,shutsuba,cyokyo,danwa）
- `--delay`: リクエスト間隔（デフォルト: 1.0秒）
- `--max-workers`: 並列処理数（デフォルト: 5）
- `--debug`: デバッグモード

**実行例**:
```bash
# 成績のみ高速取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/07 \
  --data-types seiseki \
  --max-workers 8

# 全データタイプ並列取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/07 \
  --data-types seiseki,shutsuba,cyokyo,danwa \
  --max-workers 10
```

#### 3. full - 超高速全処理実行
日程取得からデータ取得まで一括で超高速実行

```bash
python -m src.keibabook.fast_batch_cli full \
  --start-date YYYY/MM/DD \
  [--end-date YYYY/MM/DD] \
  [--data-types TYPE1,TYPE2,...] \
  [--delay SECONDS] \
  [--max-workers NUM] \
  [--wait-between-phases SECONDS] \
  [--debug]
```

**引数**:
- `--start-date`: 取得開始日（必須）
- `--end-date`: 取得終了日（省略時は開始日と同じ）
- `--data-types`: データタイプ（デフォルト: seiseki,shutsuba,cyokyo,danwa）
- `--delay`: リクエスト間隔（デフォルト: 1.0秒）
- `--max-workers`: 並列処理数（デフォルト: 5）
- `--wait-between-phases`: Phase間待機時間（秒、小数点可、デフォルト: 2.0）
- `--debug`: デバッグモード

**実行例**:
```bash
# 基本的な超高速全処理
python -m src.keibabook.fast_batch_cli full --start-date 2025/06/07

# 最大性能設定での超高速処理
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --delay 0.3 \
  --max-workers 12 \
  --wait-between-phases 1
```

### パフォーマンス指標

| 項目 | 従来版（Selenium） | 高速版（requests） | 改善率 |
|------|-------------------|-------------------|--------|
| **処理時間** | 60-90秒/12レース | **8.6秒/12レース** | **7-10倍高速** |
| **リソース使用量** | 高（Chrome起動） | **低（HTTP直接）** | **大幅削減** |
| **並列処理** | 困難 | **最大22並列対応** | **大幅改善** |
| **安定性** | 中（ブラウザ依存） | **高（HTTP直接）** | **向上** |

### 推奨設定

| 用途 | delay | max-workers | 説明 |
|------|-------|-------------|------|
| **テスト** | 1.0 | 3 | 安全な設定 |
| **通常使用** | 0.5 | 5-8 | バランス重視 |
| **高速処理** | 0.3 | 8-12 | 最大性能 |
| **サーバー負荷軽減** | 2.0 | 3 | 負荷軽減 |

---

## 📅 高速版CLI 期間指定コマンド実行例

### 🚀 基本的な期間指定パターン

#### 単日取得
```bash
# 今日のデータを取得
python -m src.keibabook.fast_batch_cli full --start-date 2025/06/07

# 特定の日のデータを取得
python -m src.keibabook.fast_batch_cli full --start-date 2025/12/29
```

#### 週末2日間取得
```bash
# 土日の2日間を取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/07 \
  --end-date 2025/06/08

# 高速設定で週末取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/07 \
  --end-date 2025/06/08 \
  --delay 0.5 \
  --max-workers 8
```

#### 1週間取得
```bash
# 1週間分のデータを取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/07

# 最大性能で1週間取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --delay 0.3 \
  --max-workers 12 \
  --wait-between-phases 1
```

#### 1ヶ月取得
```bash
# 1ヶ月分のデータを取得（安全設定）
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/30 \
  --delay 1.0 \
  --max-workers 5

# 1ヶ月分のデータを取得（高速設定）
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/30 \
  --delay 0.5 \
  --max-workers 8
```

### 🎯 特定データタイプのみ取得

#### 出馬表のみ（umacd含む）
```bash
# 出馬表のみを高速取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --data-types shutsuba \
  --max-workers 10

# 出馬表のみを超高速取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --data-types shutsuba \
  --delay 0.3 \
  --max-workers 15
```

#### 成績のみ
```bash
# 成績のみを期間取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --data-types seiseki \
  --max-workers 8
```

#### 複数データタイプ
```bash
# 成績と出馬表のみを取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --data-types seiseki,shutsuba \
  --max-workers 10

# 調教と厩舎の話のみを取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --data-types cyokyo,danwa \
  --max-workers 6
```

### 📊 段階的な取得（日程→データ）

#### 日程のみ先行取得
```bash
# まず日程を取得してレースIDを生成
python -m src.keibabook.fast_batch_cli schedule \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --delay 0.5 \
  --max-workers 8

# 後でデータを取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --data-types seiseki,shutsuba \
  --max-workers 12
```

### 🏆 特別期間の取得例

#### 年末年始（G1ラッシュ）
```bash
# 年末年始の重要レースを取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/12/28 \
  --end-date 2026/01/05 \
  --delay 0.5 \
  --max-workers 8 \
  --debug
```

#### GWゴールデンウィーク
```bash
# GW期間の全レースを取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/04/29 \
  --end-date 2025/05/05 \
  --delay 0.5 \
  --max-workers 10
```

#### 春のG1シーズン
```bash
# 春のG1シーズンを取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/03/01 \
  --end-date 2025/05/31 \
  --delay 0.8 \
  --max-workers 6
```

### ⚡ 超高速取得（最大性能）

#### 最大並列数での取得
```bash
# 最大性能設定（注意：サーバー負荷大）
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --delay 0.2 \
  --max-workers 20 \
  --wait-between-phases 0.5

# 出馬表のみ最大性能
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --data-types shutsuba \
  --delay 0.2 \
  --max-workers 22
```

### 🛡️ 安全設定（サーバー負荷軽減）

#### 負荷軽減設定
```bash
# サーバーに優しい設定
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --delay 2.0 \
  --max-workers 3 \
  --wait-between-phases 5

# 夜間バッチ用（長時間実行）
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/30 \
  --delay 3.0 \
  --max-workers 2
```

### 🔍 デバッグ・テスト用

#### デバッグモード
```bash
# 詳細ログ付きで実行
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/07 \
  --end-date 2025/06/08 \
  --debug

# 単日デバッグ
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/06/07 \
  --data-types shutsuba \
  --max-workers 3 \
  --debug
```

### 📈 処理時間の目安

| 期間 | レース数概算 | 処理時間（高速版） | 処理時間（従来版） |
|------|-------------|-------------------|-------------------|
| **1日** | 24レース | 18-30秒 | 5-10分 |
| **週末2日** | 48レース | 40-60秒 | 10-20分 |
| **1週間** | 168レース | 2-4分 | 30-60分 |
| **1ヶ月** | 720レース | 10-20分 | 2-4時間 |

### ⚠️ 注意事項

#### パフォーマンス調整
- `--max-workers`は環境に応じて調整（推奨: 5-12）
- `--delay`はサーバー負荷を考慮（推奨: 0.3-1.0秒）
- 長期間取得時は負荷軽減設定を推奨

#### 開催がない日の処理
- **開催がない日はJSONファイルを出力しません**
- 月曜日や祝日など、競馬開催がない日は空のファイルではなく、ファイル自体が作成されません
- ログには「📭 開催なし」として記録され、正常処理として扱われます

#### エラー対応
```bash
# エラー時は設定を緩める
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/06/01 \
  --end-date 2025/06/07 \
  --delay 1.5 \
  --max-workers 3 \
  --debug
```

#### ディスク容量
- 1日分: 約50-100MB
- 1週間分: 約350-700MB  
- 1ヶ月分: 約1.5-3GB

---

## 🐌 統合CLIシステム（batch_cli.py）- 従来版

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
- `--wait-between-phases`: Phase間待機時間（秒、小数点可、デフォルト: 5.0）
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
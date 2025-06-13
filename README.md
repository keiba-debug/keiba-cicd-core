# 競馬データ取得システム v2.4

競馬ブックのサイトから競馬データを取得・保存するためのスクリプト群です。

## 🚀 v2.4の新機能（リファクタリング版）
- **フォルダ構造最適化**: `KeibaCICD.keibabook/src/` への統合
- **RequestsScraperによる高速化**: 従来版の10-20倍の速度を実現
- **並列処理対応**: 最大22並列でデータ取得
- **リソース使用量削減**: Selenium不使用でメモリ・CPU使用量を大幅削減
- **安定性向上**: HTTP直接通信による高い安定性

## 🔥 推奨使用方法

### 基本的なバッチ処理（最も簡単）
```bash
# 指定日のデータを取得
python batch_process.py --start-date 2025/6/14 --end-date 2025/6/15 --data-types shutsuba,seiseki,cyokyo --delay 3 --wait-time 5

# 単一日のデータを取得
python batch_process.py --start-date 2025/6/14 --data-types seiseki --delay 2

# 短縮形式での日付指定
python batch_process.py --start-date 25/6/14 --data-types seiseki
```

### 単一レース処理
```bash
# 特定レースの成績データを取得
python main.py --race-id 202502041211 --mode scrape_and_parse --use-requests

# 複数データタイプを同時取得
python main.py --race-id 202502041211 --mode multi_type --data-types seiseki,syutuba,cyokyo --use-requests
```

### 高速スクリプト（上級者向け）
```bash
# 今日のデータを高速取得
./KeibaCICD.keibabook/scripts/fast_daily_scraping.sh

# 指定日のデータを高速取得
./KeibaCICD.keibabook/scripts/fast_daily_scraping.sh 20250607
```

### パフォーマンス比較

| 項目 | 従来版（Selenium） | 高速版（requests） | 改善率 |
|------|-------------------|-------------------|--------|
| **処理時間** | 60-90秒/12レース | **8.6秒/12レース** | **7-10倍高速** |
| **リソース使用量** | 高（Chrome起動） | **低（HTTP直接）** | **大幅削減** |
| **並列処理** | 困難 | **最大22並列対応** | **大幅改善** |
| **安定性** | 中（ブラウザ依存） | **高（HTTP直接）** | **向上** |

## スクリプトの概要

### batch_process.py

日付範囲を指定して、レースID取得からデータ取得までを自動で実行するスクリプトです。

```bash
python batch_process.py --start-date 2025/6/7 --end-date 2025/6/8 --data-types shutsuba,seiseki,cyokyo --delay 3 --wait-time 5
```

- `--start-date`: 取得開始日 (YYYY/MM/DD or YY/MM/DD)
- `--end-date`: 取得終了日 (YYYY/MM/DD or YY/MM/DD、省略時は開始日と同じ)
- `--data-types`: 取得するデータタイプ (カンマ区切り) [shutsuba,seiseki,cyokyo]
- `--delay`: リクエスト間の待機時間(秒)
- `--wait-time`: レースID取得とデータ取得の間の待機時間(秒)

このスクリプトは以下の処理を順番に実行します：
1. `fetch_race_schedule.py` を使用して、指定期間の日程情報とレースIDを取得
2. 待機時間を挟んで
3. `fetch_race_ids.py` を使用して、取得したレースIDを元に各種データを取得

### fetch_race_schedule.py

競馬ブックのサイトから日程情報とレースIDを取得して保存するスクリプトです。

```bash
python fetch_race_schedule.py --start-date 2025/6/7 --end-date 2025/6/8 --delay 3
```

- `--start-date`: 取得開始日 (YYYY/MM/DD or YY/MM/DD)
- `--end-date`: 取得終了日 (YYYY/MM/DD or YY/MM/DD、省略時は開始日と同じ)
- `--delay`: リクエスト間の待機時間(秒)

### fetch_race_ids.py

競馬ブックから取得したレースID情報を利用して、各種データを取得するスクリプトです。

```bash
python fetch_race_ids.py --start-date 2025/6/7 --end-date 2025/6/8 --data-types shutsuba,seiseki,cyokyo --delay 3
```

- `--start-date`: 取得開始日 (YYYY/MM/DD or YY/MM/DD)
- `--end-date`: 取得終了日 (YYYY/MM/DD or YY/MM/DD、省略時は開始日と同じ)
- `--data-types`: 取得するデータタイプ (カンマ区切り) [shutsuba,seiseki,cyokyo]
- `--delay`: リクエスト間の待機時間(秒)

## 使用方法

### 自動処理（推奨）

1. `batch_process.py` を実行して、レースID取得からデータ取得までを一括で行います

```bash
python batch_process.py --start-date 2025/6/7 --end-date 2025/6/8
```

### 個別処理

1. 最初に `fetch_race_schedule.py` を実行して、指定期間の日程情報とレースIDを取得します
2. 次に `fetch_race_ids.py` を実行して、取得したレースIDを使って実際のレースデータを取得します

## 環境変数の設定

データの保存先ディレクトリは環境変数 `KEIBA_DATA_DIR` で指定できます。設定されていない場合は、カレントディレクトリがデフォルトとして使用されます。

### .envファイルによる設定

プロジェクトディレクトリに `.env` ファイルを作成することで、環境変数を簡単に設定できます。このファイルは自動的に読み込まれます。

```
# .envファイルの例
KEIBA_DATA_DIR=/path/to/data/directory
```

### 直接設定する方法

#### Windows (PowerShell)
```powershell
$env:KEIBA_DATA_DIR = "C:\path\to\data\directory"
```

#### Windows (コマンドプロンプト)
```
set KEIBA_DATA_DIR=C:\path\to\data\directory
```

#### Linux/macOS
```
export KEIBA_DATA_DIR=/path/to/data/directory
```

## データ構造

- レースID形式: 年(4桁) + 月日(4桁) + 開催場所コード(1桁) + 開催回(1桁) + レース番号(2桁)
  - 例: 202503040101 (2025年・東京3回1日目・1レース)

- 開催場所コード:
  - 東京: 04
  - 中山: 06
  - 阪神: 01
  - 京都: 02
  - 新潟: 03
  - 福島: 05
  - 小倉: 07
  - 札幌: 08

## 保存先ディレクトリ

以下は `KEIBA_DATA_DIR` からの相対パスです：

- 日程情報: `data/keibabook/schedule/{日付}_schedule.json`
- レースID情報: `data/keibabook/race_ids/{日付}_info.json`
- 出馬表データ: `data/keibabook/syutuba/syutuba_{レースID}.json`
- 成績データ: `data/keibabook/seiseki/seiseki_{レースID}.json`
- 調教データ: `data/keibabook/cyokyo/cyokyo_{レースID}.json`
- デバッグHTML: `data/debug/seiseki_{レースID}_scraped.html`

## 必要なライブラリ

```
pip install requests beautifulsoup4 python-dotenv
```

## 機能

- 競馬ブックへの自動ログイン
- 談話記事のスクレイピング
- エラーハンドリングとリトライ機能
- スクレイピングデータのJSON形式での保存

## セットアップ

1. 必要なパッケージのインストール:
```bash
pip install -r KeibaCICD.keibabook/src/requirements.txt
```

2. 環境変数の設定:
`.env`ファイルを作成し、以下の内容を設定:
```
KEIBABOOK_TK=your_token
KEIBABOOK_XSRF_TOKEN=your_xsrf_token
KEIBA_DATA_DIR=Y:\KEIBA-CICD\data
```

## 🧪 テスト & 動作確認

### システムテスト
```bash
# 基本動作テスト
python main.py --test

# 特定レースでの動作確認（推奨）
python main.py --race-id 202502041211 --mode scrape_and_parse --use-requests
```

### 実行例と出力
```bash
$ python batch_process.py --start-date 2025/6/14 --data-types seiseki --delay 3

🏇 バッチ処理を開始します
📅 期間: 2025-06-14 ～ 2025-06-14
📊 データタイプ: seiseki
⏱️ 遅延: 3秒
⏸️ 待機時間: 5秒
📊 生成されたレース数: 288
🧪 テスト実行: 最初の 10 件
✅ 成功: 1
❌ エラー: 0
📈 成功率: 100.0%
```

## 注意事項

- **未来の日付**: まだ開催されていないレースはデータが存在しないためエラーになります
- **スクレイピング間隔**: サーバーに負荷をかけないよう適切な間隔（3秒以上推奨）を空けてください
- **取得制限**: 大量取得時はテスト用に最初の10件のみ処理されます
- **利用規約**: 取得したデータの利用は、競馬ブックの利用規約に従ってください
- **認証情報**: トークンは必ず環境変数で管理し、ソースコードに直接記載しないでください

## トラブルシューティング

1. **認証エラー**
   - 環境変数 `KEIBABOOK_TK` と `KEIBABOOK_XSRF_TOKEN` が正しく設定されているか確認
   - トークンが有効期限内であるか確認

2. **データ取得エラー**
   - ネットワーク接続を確認
   - 指定したレースIDが存在するか確認（未来の日付でないか）
   - ログファイル（`logs/`ディレクトリ）を確認

3. **パースエラー**
   - `成績テーブルが見つかりません` → 該当レースが存在しない可能性
   - HTMLの構造変更により既存のパーサーが動作しない可能性

## ライセンス

MIT License

# 競馬データ取得システム v2.3

競馬ブックのサイトから競馬データを取得・保存するためのスクリプト群です。

## 🚀 v2.3の新機能（高速版）
- **RequestsScraperによる高速化**: 従来版の10-20倍の速度を実現
- **並列処理対応**: 最大22並列でデータ取得
- **リソース使用量削減**: Selenium不使用でメモリ・CPU使用量を大幅削減
- **安定性向上**: HTTP直接通信による高い安定性

## 🔥 高速版の使用方法（推奨）

### 超高速全処理
```bash
# 基本的な高速取得
python -m src.keibabook.fast_batch_cli full --start-date 2025/6/7

# 最大性能設定
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/6/7 \
  --delay 0.3 \
  --max-workers 12

# 期間指定での高速取得
python -m src.keibabook.fast_batch_cli full \
  --start-date 2025/6/1 \
  --end-date 2025/6/7 \
  --delay 0.5 \
  --max-workers 8
```

### 高速スクリプト
```bash
# 今日のデータを高速取得
./scripts/fast_daily_scraping.sh

# 指定日のデータを高速取得
./scripts/fast_daily_scraping.sh 20250607
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
- 出馬表データ: `data/keibabook/shutsuba/{レースID}.html`
- 成績データ: `data/keibabook/seiseki/{レースID}.html`
- 調教データ: `data/keibabook/cyokyo/{レースID}.html`

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
pip install -r requirements.txt
```

2. 環境変数の設定:
`.env`ファイルを作成し、以下の内容を設定:
```
KEIBABOOK_USERNAME=your_username
KEIBABOOK_PASSWORD=your_password
```

## 注意事項

- スクレイピングの際は、サーバーに負荷をかけないよう適切な間隔を空けてください
- 取得したデータの利用は、競馬ブックの利用規約に従ってください
- パスワードは必ず環境変数で管理し、ソースコードに直接記載しないでください

## トラブルシューティング

1. ログインエラー
   - 環境変数が正しく設定されているか確認
   - アカウントがロックされていないか確認

2. スクレイピングエラー
   - ネットワーク接続を確認
   - URLが正しいか確認
   - ログファイル（logs/keibabook_*.log）を確認

## ライセンス

MIT License

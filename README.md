# 競馬データ取得システム v2.4

競馬ブックのサイトから競馬データを取得・保存するためのスクリプト群です。

## 🚀 v2.4の新機能（リファクタリング版）
- **フォルダ構造最適化**: `KeibaCICD.keibabook/src/` への統合
- **RequestsScraperによる高速化**: 従来版の10-20倍の速度を実現
- **並列処理対応**: 最大22並列でデータ取得
- **リソース使用量削減**: Selenium不使用でメモリ・CPU使用量を大幅削減
- **安定性向上**: HTTP直接通信による高い安定性

## 🔥 推奨使用方法（統合CLI）

まず作業ディレクトリを移動します。

```bash
cd KeibaCICD.keibabook
```

### 基本的な実行例（従来版CLI）
```bash
# レース日程の取得
python -m src.batch_cli schedule --start-date 2025/06/14

# レースデータの取得（成績のみ）
python -m src.batch_cli data --start-date 2025/06/14 --data-types seiseki

# 日程→データの一括実行
python -m src.batch_cli full --start-date 2025/06/14
```

### 高速版（実験的）
```bash
# 高速日程取得
python -m src.fast_batch_cli schedule --start-date 2025/06/14 --delay 0.5

# 高速データ取得（並列）
python -m src.fast_batch_cli data --start-date 2025/06/14 --data-types seiseki,shutsuba --delay 0.5
```

### Windows PowerShell 実行例
```powershell
# 作業ディレクトリへ移動
Set-Location KeibaCICD.keibabook

# 環境変数（例）
$env:KEIBA_DATA_ROOT_DIR = "C:\\keiba_data"
$env:LOG_LEVEL = "INFO"

# 従来版CLI
python -m src.batch_cli full --start-date 2025/06/14

# 高速版CLI（実験）
python -m src.fast_batch_cli data --start-date 2025/06/14 --data-types seiseki --delay 0.5 --max-workers 8
```

### WSL の注意点
- `.env` は必ず `KeibaCICD.keibabook/.env` に配置してください
- `KEIBA_DATA_ROOT_DIR` は WSL 上のパス（例: `/mnt/c/keiba_data`）で指定してください
- Windows 側の PowerShell で実行する場合は `C:\keiba_data` のように Windows パスで指定してください

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

## スクリプトの概要（現行）
- 統合CLI（従来版）: `src/keibabook/batch_cli.py`
- 統合CLI（高速版）: `src/keibabook/fast_batch_cli.py`
- 単体レースエントリーポイント（互換）: `src/keibabook/main.py`

## 使用方法（まとめ）

1. `cd KeibaCICD.keibabook`
2. 統合CLI（従来版）を実行
   - `python -m src.batch_cli full --start-date 2025/06/14`
3. 高速版が必要なら
   - `python -m src.fast_batch_cli full --start-date 2025/06/14 --delay 0.5`

## 環境変数の設定

- 保存先ディレクトリは環境変数 `KEIBA_DATA_ROOT_DIR` で指定します。
- `.env` は `KeibaCICD.keibabook/.env` に配置します。

### .envファイル例（KeibaCICD.keibabook/.env）
```
KEIBA_DATA_ROOT_DIR=/path/to/data
LOG_LEVEL=INFO
KEIBABOOK_SESSION=...
KEIBABOOK_TK=...
KEIBABOOK_XSRF_TOKEN=...
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

すべてのJSONは `KEIBA_DATA_ROOT_DIR` 直下に保存されます。

- レース日程: `nittei_YYYYMMDD.json`
- レースID情報: `race_ids/YYYYMMDD_info.json`
- 出馬表: `shutsuba_{race_id}.json`
- 成績: `seiseki_{race_id}.json`
- 調教: `cyokyo_{race_id}.json`

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
KEIBA_DATA_DIR=Z:\KEIBA-CICD\data
```

## 🧪 テスト & 動作確認（互換エントリーポイント）
```bash
# 基本動作テスト（KeibaCICD.keibabook 配下）
cd KeibaCICD.keibabook
python src/keibabook/main.py --test

# 特定レースでの動作確認
python src/keibabook/main.py --race-id 202502041211 --mode scrape_and_parse --use-requests
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

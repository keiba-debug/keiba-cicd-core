# 競馬ブックスクレイピングシステム

競馬ブックのWebサイトから成績データ、インタビュー、次走へのメモなどを自動取得するシステムです。

## 📋 現在取得可能なデータ

- ✅ **レース基本情報**: レース名、開催日、開催場所、レース条件
- ✅ **出馬表情報**: 馬番、馬名、性齢、騎手、厩舎、馬体重、増減
- ✅ **成績情報**: 着順、枠番、タイム、着差、通過順位、上り3F、単勝人気、単勝オッズ
- ✅ **コメント情報**: 厩舎コメント、調教コメント、インタビュー、次走へのメモ

## 🏗️ プロジェクト構造

```
keiba-cicd-core/
├── docs/                           # ドキュメント
│   └── keibabook_seiseki_spec.md   # 技術仕様書
├── src/                            # ソースコード
│   ├── parsers/                    # データ抽出パーサー
│   │   ├── base_parser.py          # 基本パーサークラス
│   │   └── seiseki_parser.py       # 成績ページパーサー
│   ├── scrapers/                   # Webスクレイパー
│   │   ├── base_scraper.py         # 基本スクレイパークラス
│   │   └── keibabook_scraper.py    # 競馬ブックスクレイパー
│   └── utils/                      # ユーティリティ
│       ├── config.py               # 設定管理
│       └── logger.py               # ログ管理
├── tests/                          # テストファイル
│   ├── test_new_seiseki_parser.py  # 成績パーサーテスト
│   └── test_integration.py         # 統合テスト
├── data/                           # データ保存ディレクトリ
│   ├── keibabook/
│   │   ├── seiseki/               # 成績データ
│   │   └── shutsuba/              # 出馬表データ
│   └── debug/                     # デバッグ用HTMLファイル
├── logs/                           # ログファイル
├── main.py                         # メイン実行ファイル
├── requirements.txt                # 依存関係
└── README.md                       # このファイル
```

## 🚀 セットアップ

### 1. プロジェクトのクローン

```bash
git clone <repository-url>
cd keiba-cicd-core
```

### 2. 依存関係のインストール

#### 仮想環境の作成（推奨）

```bash
# 仮想環境の作成
python3 -m venv venv

# 仮想環境の有効化（Linux/Mac）
source venv/bin/activate

# 仮想環境の有効化（Windows）
venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt
```

#### システム全体にインストール（非推奨）

```bash
pip install -r requirements.txt
```

#### Ubuntuでのシステムパッケージを使用（代替方法）

```bash
sudo apt update
sudo apt install -y python3-bs4 python3-lxml python3-selenium
```

### 3. ChromeDriverのインストール

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install chromium-chromedriver

# または最新版をダウンロード
wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/LATEST_RELEASE/chromedriver_linux64.zip
unzip /tmp/chromedriver.zip -d /tmp/
sudo mv /tmp/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver
```

#### macOS
```bash
# Homebrewを使用
brew install chromedriver

# または手動インストール
curl -O https://chromedriver.storage.googleapis.com/LATEST_RELEASE/chromedriver_mac64.zip
unzip chromedriver_mac64.zip
sudo mv chromedriver /usr/local/bin/
```

#### Windows
```bash
# Chocolateyを使用
choco install chromedriver

# または手動でダウンロード
# https://chromedriver.chromium.org/ からダウンロードして
# PATHの通った場所に配置
```

### 4. 環境変数の設定

#### 方法1: .envファイルを使用（推奨）

```bash
# .envファイルを作成
cat > .env << 'EOF'
# 競馬ブック認証情報
KEIBABOOK_SESSION="eyJpdiI6IlExU0ExSitBVy..."
KEIBABOOK_TK="def502001a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8"
KEIBABOOK_XSRF_TOKEN="qWeFy8uI9oP0aSdF2gH3jK4lM5nQ6wE7rT8yU9iO0pA1sD2fG3hJ4kL5"

# アプリケーション設定
DEBUG="false"
HEADLESS="true"
LOG_LEVEL="INFO"
EOF
```

#### 方法2: 環境変数を直接設定

```bash
# Linux/Mac
export KEIBABOOK_SESSION="your_session_cookie"
export KEIBABOOK_TK="your_tk_cookie"
export KEIBABOOK_XSRF_TOKEN="your_xsrf_token"
export DEBUG="false"
export HEADLESS="true"

# Windows（コマンドプロンプト）
set KEIBABOOK_SESSION=your_session_cookie
set KEIBABOOK_TK=your_tk_cookie
set KEIBABOOK_XSRF_TOKEN=your_xsrf_token
set DEBUG=false
set HEADLESS=true

# Windows（PowerShell）
$env:KEIBABOOK_SESSION="your_session_cookie"
$env:KEIBABOOK_TK="your_tk_cookie"
$env:KEIBABOOK_XSRF_TOKEN="your_xsrf_token"
$env:DEBUG="false"
$env:HEADLESS="true"
```

### 5. 初期ディレクトリの作成

```bash
# 必要なディレクトリを作成
mkdir -p data/{keibabook/{seiseki,shutsuba},debug} logs
```

## 💻 使用方法・起動サンプル

### 🎯 基本的な使用パターン

#### 1. 成績データの完全取得（スクレイピング＋パース）

```bash
# 東京優駿（ダービー）の成績を取得
python main.py --race-id 202502041211 --mode scrape_and_parse

# 成功例の出力:
# 2025-02-04 12:00:00 - main - INFO - レースID 202502041211 のデータ取得を開始します
# 2025-02-04 12:00:01 - main - INFO - === データのスクレイピング ===
# 2025-02-04 12:00:05 - main - INFO - === データのパース ===
# 2025-02-04 12:00:06 - main - INFO - === 結果の保存 ===
# 2025-02-04 12:00:06 - main - INFO - ✅ 処理が完了しました
# 2025-02-04 12:00:06 - main - INFO - 出走頭数: 18頭
# 2025-02-04 12:00:06 - main - INFO - インタビュー有り: 16頭
# 2025-02-04 12:00:06 - main - INFO - メモ有り: 14頭
# 2025-02-04 12:00:06 - main - INFO - 保存先: data/keibabook/seiseki/seiseki_202502041211.json
```

#### 2. HTMLファイルのパースのみ（既にHTMLファイルがある場合）

```bash
# 保存済みのHTMLファイルをパース
python main.py --race-id 202502041211 --mode parse_only --html-file data/debug/seiseki_202502041211_full.html

# デバッグ用HTMLファイルを使用
python main.py --race-id 202502041211 --mode parse_only --html-file data/debug/seiseki_sample.html
```

#### 3. HTMLファイルを保存せずに実行

```bash
# HTMLファイルを保存しない（メモリ効率重視）
python main.py --race-id 202502041211 --mode scrape_and_parse --no-save-html
```

### 🧪 テスト・検証パターン

#### 1. 全体テストの実行

```bash
# 統合テストを実行
python main.py --test

# 実行結果例:
# 統合テストを実行します...
# 2025-02-04 12:00:00 - main - INFO - 実行中: 成績パーサーテスト
# 2025-02-04 12:00:01 - main - INFO - ✅ 成績パーサーテスト: 成功
# 2025-02-04 12:00:01 - main - INFO - 実行中: パーサーバリデーションテスト
# 2025-02-04 12:00:01 - main - INFO - ✅ パーサーバリデーションテスト: 成功
# 2025-02-04 12:00:01 - main - INFO - 実行中: 統合テスト
# 2025-02-04 12:00:05 - main - INFO - ✅ 統合テスト: 成功
# 2025-02-04 12:00:05 - main - INFO - 実行中: エラーハンドリングテスト
# 2025-02-04 12:00:06 - main - INFO - ✅ エラーハンドリングテスト: 成功
# 2025-02-04 12:00:06 - main - INFO - テスト結果: 4/4 成功
```

#### 2. 個別テストの実行

```bash
# 成績パーサーのテストのみ
python tests/test_new_seiseki_parser.py

# 統合テストのみ
python tests/test_integration.py
```

### 🐛 デバッグ・開発パターン

#### 1. デバッグモードでの実行

```bash
# デバッグモードを有効化
export DEBUG="true"
python main.py --race-id 202502041211 --mode scrape_and_parse

# ブラウザを表示して実行（ヘッドレスモードを無効化）
export HEADLESS="false"
python main.py --race-id 202502041211 --mode scrape_and_parse
```

#### 2. ログレベルの調整

```bash
# 詳細なログを出力
export LOG_LEVEL="DEBUG"
python main.py --race-id 202502041211 --mode scrape_and_parse

# エラーレベルのみ
export LOG_LEVEL="ERROR"
python main.py --race-id 202502041211 --mode scrape_and_parse
```

### 📊 実際のレースIDサンプル

```bash
# 2024年の主要レース例
python main.py --race-id 202406021011 --mode scrape_and_parse  # 東京優駿（ダービー）
python main.py --race-id 202405051011 --mode scrape_and_parse  # 皐月賞
python main.py --race-id 202410201111 --mode scrape_and_parse  # 菊花賞
python main.py --race-id 202404141111 --mode scrape_and_parse  # 桜花賞
python main.py --race-id 202405121111 --mode scrape_and_parse  # オークス

# 複数レースの連続実行例
for race_id in 202406021011 202405051011 202410201111; do
    echo "Processing race: $race_id"
    python main.py --race-id $race_id --mode scrape_and_parse
    sleep 10  # アクセス間隔を空ける
done
```

### 🔧 設定カスタマイズの例

#### config.pyファイルのカスタマイズ

```bash
# カスタム設定でテスト
cat > custom_config.py << 'EOF'
import sys
sys.path.insert(0, 'src')
from utils.config import Config

# タイムアウト時間を延長
Config.DEFAULT_TIMEOUT = 20
Config.DEFAULT_SLEEP_TIME = 5.0

# リトライ回数を増加
Config.MAX_RETRY_COUNT = 5

print("カスタム設定を適用しました")
EOF

python custom_config.py
python main.py --race-id 202502041211 --mode scrape_and_parse
```

### ⚡ バッチ処理・自動化の例

#### 1. 日次実行スクリプト

```bash
# daily_scraping.sh
#!/bin/bash

echo "$(date): 日次スクレイピングを開始"

# 環境変数を読み込み
source .env

# 今日のレースID一覧を取得（要実装）
race_ids=(
    "202502041211"
    "202502041212"
    "202502041213"
)

for race_id in "${race_ids[@]}"; do
    echo "$(date): レース $race_id を処理中..."
    python main.py --race-id $race_id --mode scrape_and_parse
    
    if [ $? -eq 0 ]; then
        echo "$(date): レース $race_id の処理が完了"
    else
        echo "$(date): レース $race_id の処理でエラーが発生" >&2
    fi
    
    # アクセス間隔を空ける
    sleep 30
done

echo "$(date): 日次スクレイピングが完了"
```

#### 2. crontabでの定期実行

```bash
# crontabの設定例
# 毎日21:00に実行
0 21 * * * cd /path/to/keiba-cicd-core && ./daily_scraping.sh >> logs/cron.log 2>&1

# 毎週日曜日の21:00に実行
0 21 * * 0 cd /path/to/keiba-cicd-core && ./weekly_scraping.sh >> logs/cron.log 2>&1
```

## 📊 出力データ形式

### JSON形式（例）

```json
{
  "race_info": {
    "race_name": "第92回　東京優駿(GI)"
  },
  "results": [
    {
      "着順": "1",
      "枠番": "7",
      "馬番": "13",
      "馬名": "クロワデュノール",
      "性齢": "牡3",
      "騎手": "北村友",
      "タイム": "2.23.7",
      "着差": "",
      "通過順位": "****",
      "上り3F": "34.2",
      "単勝人気": "1",
      "単勝オッズ": "2.1",
      "馬体重": "504",
      "増減": "+4",
      "厩舎": "栗斉藤崇",
      "interview": "僕がダービージョッキーになれたというより...",
      "memo": "１頭だけ落ち着き払っていた。歩様も軽く..."
    }
  ]
}
```

### ファイル出力の場所

```bash
# 成績データ
data/keibabook/seiseki/seiseki_202502041211.json

# デバッグ用HTML
data/debug/seiseki_202502041211_scraped.html

# ログファイル
logs/main_20250204_120000.log
logs/test_seiseki_parser_20250204_120000.log
```

## 🔧 設定

### Config クラス

`src/utils/config.py` で以下の設定を管理：

- **ディレクトリパス**: データ保存先、ログ保存先
- **URL設定**: 競馬ブックのベースURL、成績ページURL
- **スクレイピング設定**: User-Agent、タイムアウト、待機時間
- **Cookie設定**: 必要なCookieの管理

### ログ設定

`src/utils/logger.py` でログの設定を管理：

- **ログレベル**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **出力先**: コンソール、ファイル
- **フォーマット**: タイムスタンプ、ロガー名、レベル、メッセージ

## 🧪 テスト

### テスト構成

1. **単体テスト**: パーサー、スクレイパーの個別機能をテスト
2. **統合テスト**: スクレイピング〜パース〜保存の一連の流れをテスト
3. **エラーハンドリングテスト**: 異常系のテスト

### テスト実行

```bash
# 全テストの実行
python main.py --test

# 個別テストの実行
python tests/test_new_seiseki_parser.py
python tests/test_integration.py
```

## 🚨 トラブルシューティング

### よくある問題と解決策

#### 1. ChromeDriverが見つからない

```bash
# エラー例
selenium.common.exceptions.WebDriverException: Message: 'chromedriver' executable needs to be in PATH.

# 解決策
which chromedriver  # パスを確認
sudo apt install chromium-chromedriver  # Ubuntu
brew install chromedriver  # macOS
```

#### 2. 認証エラー（Cookie関連）

```bash
# エラー例
❌ エラーが発生しました: 取得したHTMLコンテンツに問題があります

# 解決策：Cookieを最新に更新
# 1. ブラウザで競馬ブックにログイン
# 2. 開発者ツールでCookieを確認
# 3. .envファイルを更新
```

#### 3. モジュールが見つからない

```bash
# エラー例
ModuleNotFoundError: No module named 'bs4'

# 解決策
pip install beautifulsoup4
# または
sudo apt install python3-bs4
```

#### 4. ディレクトリ作成エラー

```bash
# エラー例
PermissionError: [Errno 13] Permission denied: 'data'

# 解決策
mkdir -p data/{keibabook/{seiseki,shutsuba},debug} logs
chmod 755 data logs
```

#### 5. メモリ不足

```bash
# 大量データ処理時のメモリ節約
python main.py --race-id 202502041211 --mode scrape_and_parse --no-save-html
```

### デバッグ方法

```bash
# 1. 詳細ログで実行
export DEBUG="true"
export LOG_LEVEL="DEBUG"
python main.py --race-id 202502041211 --mode scrape_and_parse

# 2. ブラウザを表示して確認
export HEADLESS="false"
python main.py --race-id 202502041211 --mode scrape_and_parse
```

## 🚨 注意事項

### アクセス制限

- 過度なアクセスは避けてください
- 適切な間隔を空けてリクエストを送信してください
- エラー発生時は適切な待機時間を設定してください

### データ品質

- インタビューやメモが空欄の場合があります
- 一部の馬はインタビューやメモが存在しない場合があります
- データの欠損は正常な動作として許容されます

### エラー処理

- ネットワークエラー
- パースエラー
- データ不整合
- アクセス制限

## 📈 今後の拡張予定

### 改善点

- [ ] エラー発生時のリトライ処理の実装
- [ ] データのバリデーション強化
- [ ] パフォーマンスの最適化
- [ ] 並列処理の実装

### 拡張性

- [ ] 他レースへの対応
- [ ] 過去レースの一括取得
- [ ] リアルタイム更新への対応
- [ ] データ分析・可視化機能の追加

## 🤝 貢献

プロジェクトへの貢献を歓迎します：

1. Issue の報告
2. 機能提案
3. プルリクエスト
4. ドキュメントの改善

## 📝 ライセンス

このプロジェクトは個人利用・研究目的での使用を想定しています。
商用利用の際は、競馬ブックの利用規約を確認してください。

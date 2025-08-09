# 競馬ブックスクレイピングシステム - セットアップ＆動作確認ガイド（保存先は `KEIBA_DATA_ROOT_DIR`）

## 🚀 目次
1. [システム要件](#1-システム要件)
2. [初期セットアップ](#2-初期セットアップ)
3. [Cookie設定](#3-cookie設定)
4. [動作確認](#4-動作確認)
5. [トラブルシューティング](#5-トラブルシューティング)

## 1. システム要件

### 必須環境
- **OS**: Windows 10/11, macOS, Linux (Ubuntu 20.04+推奨)
- **Python**: 3.8以上
- **Chrome**: 最新版推奨
- **メモリ**: 4GB以上
- **ディスク**: 2GB以上の空き容量

### 事前準備
1. **Python3のインストール確認**
   ```bash
   python3 --version
   # または
   python --version
   ```

2. **pipのインストール確認**
   ```bash
   pip3 --version
   # または
   pip --version
   ```

3. **Gitのインストール確認**
   ```bash
   git --version
   ```

## 2. 初期セットアップ

### 2.1 プロジェクトディレクトリの確認
```bash
# 現在のプロジェクトディレクトリに移動
cd /path/to/keiba-cicd-core

# プロジェクト構造を確認
ls -la
```

### 2.2 自動セットアップ (推奨)
```bash
# セットアップスクリプトを実行
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 2.3 手動セットアップ (セットアップスクリプトが使えない場合)

#### 2.3.1 仮想環境の作成
```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境を有効化
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

#### 2.3.2 依存関係のインストール
```bash
# 依存関係をインストール
pip install -r requirements.txt
```

#### 2.3.3 ディレクトリ構造の作成
```bash
# 必要なディレクトリを作成
mkdir -p data/keibabook/seiseki
mkdir -p data/keibabook/shutsuba
mkdir -p data/debug
mkdir -p logs
```

#### 2.3.4 ChromeDriverのインストール
**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install chromium-chromedriver
```

**macOS:**
```bash
brew install chromedriver
```

**Windows:**
```bash
# Chocolateyを使用
choco install chromedriver
# または手動ダウンロード: https://chromedriver.chromium.org/
```

## 3. Cookie設定

### 3.1 競馬ブックへのログイン
1. ブラウザで https://p.keibabook.co.jp/ にアクセス
2. ログインを行う

### 3.2 Cookieの取得
1. **F12キー** を押して開発者ツールを開く
2. **Application** タブをクリック
3. **Storage** → **Cookies** → **https://p.keibabook.co.jp** を選択
4. 以下のCookieの値をコピー：
   - `keibabook_session`
   - `tk`
   - `XSRF-TOKEN`

### 3.3 環境変数ファイルの設定
`.env` ファイルを作成・編集：
```bash
# 実際のCookie値を設定
KEIBABOOK_SESSION="your_actual_session_cookie_here"
KEIBABOOK_TK="your_actual_tk_cookie_here"
KEIBABOOK_XSRF_TOKEN="your_actual_xsrf_token_here"

# アプリケーション設定
DEBUG="false"
HEADLESS="true"
LOG_LEVEL="INFO"

# スクレイピング設定
DEFAULT_TIMEOUT="10"
DEFAULT_SLEEP_TIME="2.0"
MAX_RETRY_COUNT="3"
```

## 4. 動作確認

### 4.1 基本動作テスト
```bash
# システムテストを実行
python -m src.main --test
```

### 4.2 パース機能のテスト (既存HTMLファイルがある場合)
```bash
# 既存のHTMLファイルをパースしてテスト
python -m src.main --mode parse_only --html-file data/debug/sample.html --race-id 202502041211
```

### 4.3 実際のスクレイピング＆パース (Cookie設定が完了している場合)
```bash
# 実際のレースデータを取得してパース
python -m src.main --race-id 202502041211 --mode scrape_and_parse
```

### 4.4 デバッグモードでの実行
```bash
# デバッグモード（ブラウザが表示される）
python -m src.main --race-id 202502041211 --mode scrape_and_parse --debug
```

## 5. 動作確認の詳細手順

### 5.1 Step 1: システム確認
```bash
# 1. Python環境の確認
python --version

# 2. 依存関係の確認
pip list | grep -E "(selenium|beautifulsoup4|pandas)"

# 3. ChromeDriverの確認
chromedriver --version
```

### 5.2 Step 2: 基本テストの実行
```bash
# テストモードで動作確認
python src/keibabook/main.py --test
```

**期待される出力:**
```
[INFO] 統合テストを実行します
[INFO] 実行中: 成績パーサーテスト
[INFO] 実行中: パーサーバリデーションテスト
[INFO] 実行中: 統合テスト
[SUCCESS] ✅ すべてのテストが成功しました
```

### 5.3 Step 3: HTMLパースのテスト
```bash
# 既存のHTMLファイルがある場合
python -m src.main --mode parse_only --html-file seiseki_result.json --race-id test001
```

### 5.4 Step 4: フルスクレイピングテスト
```bash
# 実際のスクレイピングを実行
python -m src.main --race-id 202502041211 --mode scrape_and_parse
```

**期待される出力:**
```
[INFO] レースID 202502041211 のデータ取得を開始します
[INFO] === データのスクレイピング ===
[INFO] === データのパース ===
[INFO] === 結果の保存 ===
[SUCCESS] ✅ 処理が完了しました
[INFO] 出走頭数: 18頭
[INFO] インタビュー有り: 16頭
[INFO] メモ有り: 14頭
[INFO] 保存先: data/keibabook/seiseki/seiseki_202502041211.json
```

### 5.5 Step 5: 出力ファイルの確認
```bash
# 生成されたJSONファイルを確認
ls -la data/keibabook/seiseki/
cat data/keibabook/seiseki/seiseki_202502041211.json | head -20
```

## 6. トラブルシューティング

### 6.1 よくある問題と解決方法

#### 問題1: `ModuleNotFoundError: No module named 'selenium'`
**解決方法:**
```bash
# 仮想環境を確認
source venv/bin/activate  # Linux/macOS
# または
venv\Scripts\activate     # Windows

# 依存関係を再インストール
pip install -r requirements.txt
```

#### 問題2: `WebDriverException: 'chromedriver' executable needs to be in PATH`
**解決方法:**
```bash
# ChromeDriverのインストール
# Ubuntu:
sudo apt-get install chromium-chromedriver

# macOS:
brew install chromedriver

# Windows:
choco install chromedriver
```

#### 問題3: `Cookie認証エラー`
**解決方法:**
1. ブラウザで再度ログイン
2. 新しいCookieを取得
3. `.env`ファイルを更新

#### 問題4: `timeout occurred`
**解決方法:**
```bash
# デバッグモードで実行
python src/keibabook/main.py --race-id 202502041211 --mode scrape_and_parse --debug
```

### 6.2 ログファイルの確認
```bash
# 最新のログを確認
tail -f logs/main.log

# エラーログのみを確認
grep -i error logs/main.log
```

### 6.3 デバッグHTMLファイルの確認
```bash
# スクレイピングで取得したHTMLファイルを確認
ls -la data/debug/
```

## 7. 次のステップ

### 7.1 定期実行の設定
```bash
# 日次スクレイピングスクリプトの確認
cat scripts/daily_scraping.sh

# 実行権限を付与
chmod +x scripts/daily_scraping.sh
```

### 7.2 データ分析
```bash
# 取得したデータの分析
python -c "
import json
with open('data/keibabook/seiseki/seiseki_202502041211.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    print(f'レース名: {data[\"race_info\"][\"race_name\"]}')
    print(f'出走頭数: {len(data[\"results\"])}頭')
"
```

## 8. サポート

### 8.1 コマンドラインヘルプ
```bash
python main.py --help
```

### 8.2 設定ファイルの確認
```bash
# 現在の設定を確認
cat .env
```

### 8.3 プロジェクト構造の確認
```bash
# プロジェクト全体の構造を表示
tree . -I '__pycache__|*.pyc|venv'
```

---

## 📝 注意事項

1. **Cookie有効期限**: Cookieは一定期間で無効になります。定期的に更新してください。
2. **利用規約遵守**: 競馬ブックの利用規約を守り、適切な間隔でアクセスしてください。
3. **データバックアップ**: 重要なデータは定期的にバックアップを取ってください。

## 🎯 成功の指標

- [ ] テストモードが正常に動作する
- [ ] HTMLパースが正常に動作する
- [ ] 実際のスクレイピングが成功する
- [ ] JSONファイルが正常に生成される
- [ ] インタビュー・メモデータが取得できる 

---

## 9. Windows PowerShell / WSL 補足

### 9.1 Windows PowerShell 例
```powershell
# 作業ディレクトリへ移動
Set-Location KeibaCICD.keibabook

# 保存先ディレクトリ（例）
$env:KEIBA_DATA_ROOT_DIR = "C:\\keiba_data"

# 従来版CLIの実行
python -m src.batch_cli full --start-date 2025/06/14

# 高速版CLI（実験）
python -m src.fast_batch_cli data --start-date 2025/06/14 --data-types seiseki --delay 0.5 --max-workers 8
```

### 9.2 WSL の注意点
- `.env` は必ず `KeibaCICD.keibabook/.env` に配置してください
- `KEIBA_DATA_ROOT_DIR` は WSL 側のパス（例: `/mnt/c/keiba_data`）で指定してください
- Windows 側で PowerShell 実行時は `C:\keiba_data` のように Windows パスで指定してください
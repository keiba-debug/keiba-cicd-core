# 競馬データ取得システム - トラブルシューティングガイド

## 📋 概要

競馬データ取得システムで発生する可能性のある問題と解決方法をまとめたガイドです。

**最終更新**: 2025年6月7日  
**バージョン**: v2.0

---

## 🚨 よくある問題と解決方法

### 1. 環境変数関連の問題

#### 問題: 環境変数が読み込まれない
```
エラー例: KEIBA_DATA_DIR環境変数が設定されていません
```

**原因**:
- 環境変数が設定されていない
- .envファイルが存在しない
- .envファイルの形式が間違っている

**解決方法**:

##### Windows PowerShell
```powershell
# 現在の環境変数を確認
echo $env:KEIBA_DATA_DIR

# 環境変数を設定
$env:KEIBA_DATA_DIR = "C:\path\to\data"

# 永続的な設定（システム環境変数）
[Environment]::SetEnvironmentVariable("KEIBA_DATA_DIR", "C:\path\to\data", "User")
```

##### Linux/Mac
```bash
# 現在の環境変数を確認
echo $KEIBA_DATA_DIR

# 環境変数を設定
export KEIBA_DATA_DIR="/path/to/data"

# 永続的な設定（.bashrcまたは.zshrcに追加）
echo 'export KEIBA_DATA_DIR="/path/to/data"' >> ~/.bashrc
```

##### .envファイルの作成
```bash
# プロジェクトルートに.envファイルを作成
cat > .env << EOF
KEIBA_DATA_DIR=./data
LOG_LEVEL=INFO
EOF
```

---

### 2. ネットワーク・接続関連の問題

#### 問題: 404エラーが多発する
```
エラー例: HTTP 404 Not Found for URL: https://p.keibabook.co.jp/cyuou/shutsuba/202506071101
```

**原因**:
- 指定した日付に競馬開催がない
- レースIDが存在しない
- 競馬ブックサイトの構造変更

**解決方法**:

##### 1. 実際の開催日程を確認
```bash
# 競馬ブックサイトで開催日程を確認
# https://p.keibabook.co.jp/cyuou/nittei/

# 実際の開催日で再実行（統合CLI）
python -m src.batch_cli full --start-date 2024/12/28
```

##### 2. ログファイルで詳細確認
```bash
# エラーログを確認
grep "404" logs/fetch_data_*.log
grep "ERROR" logs/fetch_data_*.log

# 最新ログをリアルタイム監視
tail -f logs/fetch_data_*.log
```

##### 3. 段階的なテスト（統合CLI）
```bash
# 1日分のみでテスト（成績のみ）
python -m src.batch_cli data --start-date 2024/12/28 --data-types seiseki

# 成功したら他のデータタイプも試行
python -m src.batch_cli data --start-date 2024/12/28 --data-types shutsuba,cyokyo
```

#### 問題: タイムアウトエラー
```
エラー例: requests.exceptions.Timeout: HTTPSConnectionPool
```

**原因**:
- ネットワーク接続が不安定
- サーバーの応答が遅い
- リクエスト間隔が短すぎる

**解決方法**:

##### リクエスト間隔を延長（統合CLI）
```bash
# 間隔を5秒に延長
python -m src.batch_cli full --start-date 2025/6/7 --delay 5

# さらに長い間隔（10秒）
python -m src.batch_cli full --start-date 2025/6/7 --delay 10
```

##### ネットワーク接続確認
```bash
# 競馬ブックサイトへの接続確認
ping p.keibabook.co.jp

# DNS解決確認
nslookup p.keibabook.co.jp
```

---

### 3. ファイル・ディレクトリ関連の問題

#### 問題: ディレクトリ作成エラー
```
エラー例: PermissionError: [Errno 13] Permission denied: 'data/keibabook'
```

**原因**:
- ディレクトリの書き込み権限がない
- 親ディレクトリが存在しない
- パス形式が間違っている

**解決方法**:

##### Windows
```powershell
# 権限確認
Get-Acl data/

# ディレクトリ作成
New-Item -ItemType Directory -Path "data\keibabook\shutsuba" -Force
New-Item -ItemType Directory -Path "data\keibabook\seiseki" -Force
New-Item -ItemType Directory -Path "data\keibabook\cyokyo" -Force
```

##### Linux/Mac
```bash
# 権限確認
ls -la data/

# 権限修正
chmod 755 data/
chmod -R 755 data/keibabook/

# ディレクトリ作成
mkdir -p data/keibabook/{shutsuba,seiseki,cyokyo,schedule,race_ids}
```

#### 問題: ファイルが見つからない
```
エラー例: FileNotFoundError: [Errno 2] No such file or directory: 'data/keibabook/race_ids/20250607_info.json'
```

**原因**:
- レースID取得処理が実行されていない
- ファイルパスが間違っている
- 前の処理でエラーが発生している

**解決方法**:

##### ファイル存在確認
```bash
# ファイル一覧確認
ls -la data/keibabook/race_ids/
ls -la data/keibabook/schedule/

# 特定ファイルの確認
test -f data/keibabook/race_ids/20250607_info.json && echo "存在" || echo "不存在"
```

##### 段階的な実行
```bash
# 1. まずレースID取得のみ実行
python src/keibabook/fetch_race_schedule.py --start-date 2025/6/7

# 2. ファイル作成確認
ls data/keibabook/race_ids/

# 3. データ取得実行
python src/keibabook/fetch_race_ids.py --start-date 2025/6/7
```

---

### 4. Python・依存関係の問題

#### 問題: モジュールが見つからない
```
エラー例: ModuleNotFoundError: No module named 'requests'
```

**原因**:
- 必要なライブラリがインストールされていない
- 仮想環境が有効化されていない
- Pythonのバージョンが古い

**解決方法**:

##### 依存関係の再インストール
```bash
# 依存関係確認
pip list

# 必要なライブラリをインストール
pip install -r requirements.txt

# 個別インストール
pip install requests beautifulsoup4 python-dotenv loguru
```

##### Python環境確認
```bash
# Pythonバージョン確認
python --version

# pipバージョン確認
pip --version

# インストール済みパッケージ確認
pip list | grep -E "(requests|beautifulsoup4|python-dotenv|loguru)"
```

#### 問題: 仮想環境の問題
```
エラー例: 仮想環境外でのパッケージ競合
```

**解決方法**:

##### 仮想環境の作成・使用
```bash
# 仮想環境作成
python -m venv keiba_env

# 仮想環境有効化（Windows）
keiba_env\Scripts\activate

# 仮想環境有効化（Linux/Mac）
source keiba_env/bin/activate

# 依存関係インストール
pip install -r requirements.txt
```

---

### 5. データ形式・パース関連の問題

#### 問題: JSONファイルの形式エラー
```
エラー例: json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**原因**:
- JSONファイルが空または破損している
- ファイル書き込み中にプロセスが中断された
- 文字エンコーディングの問題

**解決方法**:

##### ファイル内容確認
```bash
# ファイルサイズ確認
ls -la data/keibabook/race_ids/20250607_info.json

# ファイル内容確認（先頭10行）
head -10 data/keibabook/race_ids/20250607_info.json

# JSON形式確認
python -m json.tool data/keibabook/race_ids/20250607_info.json
```

##### ファイル再生成
```bash
# 問題のあるファイルを削除
rm data/keibabook/race_ids/20250607_info.json

# レースID取得を再実行
python src/keibabook/fetch_race_schedule.py --start-date 2025/6/7
```

#### 問題: HTMLパースエラー
```
エラー例: AttributeError: 'NoneType' object has no attribute 'find'
```

**原因**:
- HTMLの構造が期待と異なる
- 競馬ブックサイトの仕様変更
- 取得したHTMLが不完全

**解決方法**:

##### HTMLファイル確認
```bash
# HTMLファイルサイズ確認
ls -la data/keibabook/shutsuba/202506071101.html

# HTMLファイル内容確認（先頭部分）
head -50 data/keibabook/shutsuba/202506071101.html

# 特定要素の存在確認
grep -i "table" data/keibabook/shutsuba/202506071101.html
```

##### デバッグモードでの実行
```python
# デバッグ用スクリプト
from bs4 import BeautifulSoup

with open('data/keibabook/shutsuba/202506071101.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
print(f"HTMLサイズ: {len(html)} bytes")
print(f"タイトル: {soup.title.string if soup.title else 'なし'}")

# テーブル要素確認
tables = soup.find_all('table')
print(f"テーブル数: {len(tables)}")
```

---

### 6. ログ・デバッグ関連

#### 問題: ログファイルが作成されない
```
エラー例: ログ出力されない、ログファイルが空
```

**原因**:
- ログディレクトリの権限問題
- ログレベルの設定問題
- ログ設定の初期化エラー

**解決方法**:

##### ログディレクトリ確認
```bash
# ログディレクトリ作成
mkdir -p logs

# 権限設定
chmod 755 logs/

# ログファイル一覧確認
ls -la logs/
```

##### ログレベル設定
```bash
# 環境変数でログレベル設定
export LOG_LEVEL=DEBUG

# .envファイルに追加
echo "LOG_LEVEL=DEBUG" >> .env
```

##### 手動ログ確認
```python
# ログ動作確認スクリプト
import logging
from pathlib import Path

# ログディレクトリ作成
Path("logs").mkdir(exist_ok=True)

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/test.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("ログテスト: 正常に動作しています")
```

---

## 🔍 診断コマンド集

### システム環境確認
```bash
# Python環境
python --version
pip --version

# 環境変数確認
echo $KEIBA_DATA_DIR  # Linux/Mac
echo $env:KEIBA_DATA_DIR  # Windows PowerShell

# ディスク容量確認
df -h .  # Linux/Mac
Get-PSDrive C  # Windows PowerShell
```

### ネットワーク確認
```bash
# 接続確認
ping p.keibabook.co.jp

# DNS確認
nslookup p.keibabook.co.jp

# HTTPアクセス確認
curl -I https://p.keibabook.co.jp/
```

### ファイル・ディレクトリ確認（`KEIBA_DATA_ROOT_DIR` 直下）
```bash
# プロジェクト構造確認
tree -L 3  # Linux/Mac
Get-ChildItem -Recurse -Depth 2  # Windows PowerShell

# データディレクトリ確認
ls -la "$KEIBA_DATA_ROOT_DIR"/
ls -la logs/

# ファイルサイズ確認
du -sh data/  # Linux/Mac
Get-ChildItem data/ -Recurse | Measure-Object -Property Length -Sum  # Windows PowerShell
```

### Windows PowerShell 例（診断）
```powershell
# 作業ディレクトリへ移動
Set-Location KeibaCICD.keibabook

# 環境変数確認
echo $env:KEIBA_DATA_ROOT_DIR

# JSON保存先の確認
Get-ChildItem -Force $env:KEIBA_DATA_ROOT_DIR
Get-ChildItem -Force (Join-Path $env:KEIBA_DATA_ROOT_DIR 'race_ids')
```

### WSL の注意
- `.env` は必ず `KeibaCICD.keibabook/.env` に配置
- `KEIBA_DATA_ROOT_DIR` は `/mnt/c/...` などのLinuxパスで指定

---

## 🚀 パフォーマンス最適化

### メモリ使用量の監視
```python
import psutil
import os

def check_memory():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"メモリ使用量: {memory_info.rss / 1024 / 1024:.2f} MB")
    print(f"仮想メモリ: {memory_info.vms / 1024 / 1024:.2f} MB")

check_memory()
```

### ディスク使用量の監視
```bash
# データディレクトリのサイズ
du -sh data/

# ログディレクトリのサイズ
du -sh logs/

# 古いログファイルの削除（30日以上前）
find logs/ -name "*.log" -mtime +30 -delete
```

---

## 📞 サポート・問い合わせ

### 問題報告時に含める情報

1. **エラーメッセージ**: 完全なエラーメッセージとスタックトレース
2. **実行コマンド**: 実行したコマンドライン
3. **環境情報**: OS、Pythonバージョン、依存関係バージョン
4. **ログファイル**: 関連するログファイルの内容
5. **再現手順**: 問題を再現するための手順

### ログファイルの収集
```bash
# 最新のログファイルを収集
tar -czf debug_logs_$(date +%Y%m%d).tar.gz logs/

# 設定ファイルも含める
tar -czf debug_info_$(date +%Y%m%d).tar.gz logs/ .env requirements.txt
```

### 環境情報の収集
```bash
# 環境情報をファイルに出力
cat > debug_env.txt << EOF
Python Version: $(python --version)
Pip Version: $(pip --version)
OS: $(uname -a)
Current Directory: $(pwd)
Environment Variables:
$(env | grep KEIBA)
Installed Packages:
$(pip list)
EOF
```

---

## 🔄 予防策・ベストプラクティス

### 1. 定期的なメンテナンス
```bash
# 週次メンテナンススクリプト
#!/bin/bash
# weekly_maintenance.sh

echo "=== 週次メンテナンス開始 ==="

# 古いログファイル削除
find logs/ -name "*.log" -mtime +7 -delete

# ディスク使用量確認
echo "データディレクトリサイズ:"
du -sh data/

# 依存関係更新確認
echo "更新可能なパッケージ:"
pip list --outdated

echo "=== 週次メンテナンス完了 ==="
```

### 2. バックアップ戦略
```bash
# データバックアップスクリプト
#!/bin/bash
# backup_data.sh

BACKUP_DIR="backup/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# データファイルをバックアップ
cp -r data/keibabook/ $BACKUP_DIR/
cp -r logs/ $BACKUP_DIR/

# 圧縮
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR/
rm -rf $BACKUP_DIR/

echo "バックアップ完了: $BACKUP_DIR.tar.gz"
```

### 3. 監視・アラート
```python
# 簡易監視スクリプト
import os
import smtplib
from pathlib import Path
from datetime import datetime, timedelta

def check_system_health():
    issues = []
    
    # ディスク容量チェック
    disk_usage = os.statvfs('.')
    free_space = disk_usage.f_bavail * disk_usage.f_frsize / (1024**3)  # GB
    if free_space < 1:  # 1GB未満
        issues.append(f"ディスク容量不足: {free_space:.2f}GB")
    
    # 最新ログファイルチェック
    log_files = list(Path('logs/').glob('*.log'))
    if log_files:
        latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
        last_modified = datetime.fromtimestamp(latest_log.stat().st_mtime)
        if datetime.now() - last_modified > timedelta(days=1):
            issues.append(f"ログファイルが古い: {latest_log}")
    
    return issues

# 使用例
issues = check_system_health()
if issues:
    print("⚠️ システムの問題:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("✅ システム正常")
```

---

**🎯 問題が解決しない場合は、上記の診断コマンドを実行して詳細情報を収集し、ログファイルと合わせて確認してください。** 
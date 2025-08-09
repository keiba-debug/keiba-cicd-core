# 競馬データ取得システム - 使用例とサンプルコード

## 📋 概要

競馬データ取得システムの具体的な使用例とサンプルコードを紹介します。

**最終更新**: 2025年6月7日  
**バージョン**: v2.0

---

## 🚀 基本的な使用例

### 1. 自動データ取得（統合CLI）

#### 1日分のデータを取得（従来版）
```bash
# 2025年6月7日のデータを一括取得
python -m src.batch_cli full --start-date 2025/06/07
```

#### 期間指定でのデータ取得（従来版）
```bash
# 2025年6月7日〜8日のデータを一括取得
python -m src.batch_cli full --start-date 2025/06/07 --end-date 2025/06/08 --delay 5
```

#### 特定データタイプのみ取得（従来版）
```bash
# 成績データのみ取得
python -m src.batch_cli data --start-date 2025/06/07 --data-types seiseki

# 出馬表と調教データのみ取得
python -m src.batch_cli data --start-date 2025/06/07 --data-types shutsuba,cyokyo
```

---

## 🔧 詳細設定での使用例

### 1. リクエスト間隔の調整（従来版）

#### サーバー負荷を考慮した設定
```bash
# リクエスト間隔を5秒に設定
python -m src.batch_cli full --start-date 2025/06/07 --delay 5
```

#### 高速取得設定（注意：サーバー負荷に配慮）
```bash
# 高速版CLI（requests）
python -m src.fast_batch_cli full --start-date 2025/06/07 --delay 0.5 --max-workers 10
```

### 2. 環境変数を使用した設定

#### PowerShellでの環境変数設定
```powershell
# データ保存先を指定
$env:KEIBA_DATA_ROOT_DIR = "D:\\keiba_data"

# 実行
python -m src.batch_cli full --start-date 2025/06/07
```

#### .envファイルでの設定
```bash
# .envファイルを作成
echo "KEIBA_DATA_ROOT_DIR=/path/to/data" > KeibaCICD.keibabook/.env

# 実行（.envファイルが自動読み込みされる）
cd KeibaCICD.keibabook
python -m src.keibabook.batch_cli full --start-date 2025/06/07
```

---

## 🗂 個別スクリプトの使用例

### 1. レースID取得のみ

#### 基本的なレースID取得
```bash
# 2025年6月7日の日程とレースIDを取得
python src/keibabook/fetch_race_schedule.py --start-date 2025/6/7
```

#### 期間指定でのレースID取得
```bash
# 2025年6月7日〜8日の日程とレースIDを取得
python src/keibabook/fetch_race_schedule.py --start-date 2025/6/7 --end-date 2025/6/8 --delay 3
```

### 2. データ取得のみ

#### 既存レースIDを使用したデータ取得
```bash
# 事前にレースIDが取得済みの場合
python src/keibabook/fetch_race_ids.py --start-date 2025/6/7 --data-types shutsuba,seiseki,cyokyo
```

#### 特定データタイプのみ取得
```bash
# 成績データのみ取得
python src/keibabook/fetch_race_ids.py --start-date 2025/6/7 --data-types seiseki

# 調教データのみ取得
python src/keibabook/fetch_race_ids.py --start-date 2025/6/7 --data-types cyokyo
```

---

## 📊 データ活用例

### 1. 取得したデータの確認

#### JSONファイルの内容確認
```bash
# Windows PowerShell
Get-Content $env:KEIBA_DATA_ROOT_DIR\race_ids\20250607_info.json | ConvertFrom-Json

# Linux/Mac
cat "$KEIBA_DATA_ROOT_DIR"/race_ids/20250607_info.json | jq .
```

#### HTMLファイルの確認
```bash
# ファイル一覧表示
ls "$KEIBA_DATA_ROOT_DIR"/  # 直下に JSON が保存されます
ls "$KEIBA_DATA_ROOT_DIR"/race_ids/
```

### 2. Pythonでのデータ読み込み

#### レースID情報の読み込み
```python
import json
from pathlib import Path

# レースID情報を読み込み
import os
race_ids_file = Path(os.path.join(os.environ.get("KEIBA_DATA_ROOT_DIR", "data"), "race_ids", "20250607_info.json"))
with open(race_ids_file, 'r', encoding='utf-8') as f:
    race_data = json.load(f)

# レースID一覧を表示
race_ids = [race['race_id'] for race in race_data]
print(f"取得されたレースID数: {len(race_ids)}")
for race_id in race_ids:
    print(f"- {race_id}")
```

#### HTMLファイルの解析
```python
from bs4 import BeautifulSoup
from pathlib import Path

# 出馬表HTMLファイルを読み込み（必要時のみ。通常はHTMLを保存しません）
html_file = Path(os.path.join(os.environ.get("KEIBA_DATA_ROOT_DIR", "data"), "shutsuba_202506071101.html"))
if html_file.exists():
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    print(f"HTMLファイルサイズ: {len(html_content)} bytes")
    print(f"タイトル: {soup.title.string if soup.title else 'なし'}")
else:
    print("HTMLファイルが見つかりません")
```

---

## 🔄 定期実行の設定例

### 1. Windows タスクスケジューラー

#### 毎日自動実行の設定（PowerShell）
```powershell
# タスクスケジューラーでの設定例
# 1. タスクスケジューラーを開く
# 2. 基本タスクの作成
# 3. 以下のコマンドを設定

# 実行プログラム: python
# 引数: -m src.keibabook.batch_cli full --start-date $(Get-Date -Format "yyyy/M/d")
# 開始場所: C:\path\to\keiba-cicd-core\KeibaCICD.keibabook
```

#### PowerShellスクリプトでの自動化
```powershell
# daily_keiba_fetch.ps1
$today = Get-Date -Format "yyyy/M/d"
$logFile = "logs/daily_fetch_$(Get-Date -Format 'yyyyMMdd').log"

Write-Host "競馬データ取得開始: $today"

try {
python -m src.batch_cli full --start-date $today 2>&1 | Tee-Object -FilePath $logFile
    Write-Host "取得完了: $today"
} catch {
    Write-Error "取得失敗: $_"
    exit 1
}
```

### 2. Linux/Mac cron設定

#### 毎日午前9時に実行
```bash
# crontabに追加
0 9 * * * cd /path/to/keiba-cicd-core && python src/keibabook/batch_process.py --start-date $(date +\%Y/\%m/\%d) >> logs/cron.log 2>&1
```

---

## 🚨 エラー対応例

### 1. 404エラーが発生した場合

#### ログの確認
```bash
# 最新のログファイルを確認
tail -f logs/fetch_data_*.log

# エラー行のみ抽出
grep "404" logs/fetch_data_*.log
grep "ERROR" logs/fetch_data_*.log
```

#### 実際の開催日程の確認
```bash
# 競馬ブックサイトで実際の開催日程を確認
# https://p.keibabook.co.jp/cyuou/nittei/

# 正しい日付での再実行
python src/keibabook/batch_process.py --start-date 2024/12/28  # 実際の開催日
```

### 2. 環境変数エラーの対応

#### 環境変数の確認
```bash
# Windows PowerShell
echo $env:KEIBA_DATA_DIR

# Linux/Mac
echo $KEIBA_DATA_DIR
```

#### .envファイルの作成
```bash
# .envファイルを作成
cat > .env << EOF
KEIBA_DATA_DIR=./data
LOG_LEVEL=INFO
EOF
```

### 3. ディレクトリ権限エラーの対応

#### 権限の確認と修正
```bash
# Linux/Mac
ls -la data/
chmod 755 data/
chmod -R 755 data/keibabook/

# Windows PowerShell
Get-Acl data/
```

---

## 📈 パフォーマンス最適化例

### 1. 大量データ取得時の設定

#### 1週間分のデータを効率的に取得
```bash
# 段階的な取得（推奨）
python src/keibabook/batch_process.py --start-date 2024/12/21 --end-date 2024/12/22 --delay 5
python src/keibabook/batch_process.py --start-date 2024/12/23 --end-date 2024/12/24 --delay 5
python src/keibabook/batch_process.py --start-date 2024/12/25 --end-date 2024/12/26 --delay 5
```

#### 特定データタイプのみ先行取得
```bash
# まず成績データのみ取得
python src/keibabook/batch_process.py --start-date 2024/12/21 --end-date 2024/12/27 --data-types seiseki

# 次に出馬表データを取得
python src/keibabook/batch_process.py --start-date 2024/12/21 --end-date 2024/12/27 --data-types shutsuba

# 最後に調教データを取得
python src/keibabook/batch_process.py --start-date 2024/12/21 --end-date 2024/12/27 --data-types cyokyo
```

### 2. メモリ使用量の監視

#### Pythonでのメモリ監視
```python
import psutil
import os

def monitor_memory():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"メモリ使用量: {memory_info.rss / 1024 / 1024:.2f} MB")

# スクリプト実行前後でメモリ使用量を確認
monitor_memory()
# データ取得処理
monitor_memory()
```

---

## 🔍 デバッグ・開発例

### 1. 開発時のテスト実行

#### 小規模テスト
```bash
# 1日分のみでテスト
python src/keibabook/batch_process.py --start-date 2024/12/28 --data-types seiseki --delay 1
```

#### ドライラン（実際の取得は行わない）
```python
# 将来実装予定の機能
python src/keibabook/batch_process.py --start-date 2025/6/7 --dry-run
```

### 2. カスタムスクリプトの作成

#### 特定レースのみ取得するスクリプト
```python
#!/usr/bin/env python3
# custom_race_fetch.py

import sys
import subprocess
from pathlib import Path

def fetch_specific_races(race_ids, data_types=None):
    """特定のレースIDのデータを取得"""
    if data_types is None:
        data_types = ["shutsuba", "seiseki", "cyokyo"]
    
    for race_id in race_ids:
        print(f"レース {race_id} のデータを取得中...")
        # 実際の実装では、fetch_race_ids.pyの関数を直接呼び出し
        # ここでは簡略化してコマンド実行
        cmd = [
            "python", "src/keibabook/fetch_race_ids.py",
            "--start-date", "2024/12/28",  # 適切な日付に変更
            "--data-types", ",".join(data_types)
        ]
        subprocess.run(cmd)

if __name__ == "__main__":
    # 特定のレースIDを指定
    target_races = ["202412281101", "202412281102", "202412281103"]
    fetch_specific_races(target_races)
```

---

## 📚 応用例

### 1. データ分析との連携

#### 取得データの統計分析
```python
import json
import pandas as pd
from pathlib import Path

def analyze_race_data(date_str):
    """取得したレースデータの基本統計"""
    race_ids_file = Path(f"data/keibabook/race_ids/{date_str}_info.json")
    
    if not race_ids_file.exists():
        print(f"データファイルが見つかりません: {race_ids_file}")
        return
    
    with open(race_ids_file, 'r', encoding='utf-8') as f:
        race_data = json.load(f)
    
    # 基本統計
    total_races = len(race_data)
    venues = set(race['kaisaimei'] for race in race_data)
    
    print(f"=== {date_str} レースデータ統計 ===")
    print(f"総レース数: {total_races}")
    print(f"開催場所: {', '.join(venues)}")
    
    # 開催場所別レース数
    venue_counts = {}
    for race in race_data:
        venue = race['kaisaimei']
        venue_counts[venue] = venue_counts.get(venue, 0) + 1
    
    print("\n開催場所別レース数:")
    for venue, count in venue_counts.items():
        print(f"  {venue}: {count}レース")

# 使用例
analyze_race_data("20250607")
```

### 2. 外部システムとの連携

#### データベースへの保存
```python
import sqlite3
import json
from pathlib import Path

def save_to_database(date_str):
    """取得したデータをSQLiteデータベースに保存"""
    # データベース接続
    conn = sqlite3.connect('keiba_data.db')
    cursor = conn.cursor()
    
    # テーブル作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS races (
            race_id TEXT PRIMARY KEY,
            race_name TEXT,
            kaisaimei TEXT,
            race_no TEXT,
            course TEXT,
            date TEXT
        )
    ''')
    
    # データ読み込み
    race_ids_file = Path(f"data/keibabook/race_ids/{date_str}_info.json")
    with open(race_ids_file, 'r', encoding='utf-8') as f:
        race_data = json.load(f)
    
    # データ挿入
    for race in race_data:
        cursor.execute('''
            INSERT OR REPLACE INTO races 
            (race_id, race_name, kaisaimei, race_no, course, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            race['race_id'],
            race['race_name'],
            race['kaisaimei'],
            race['race_no'],
            race['course'],
            date_str
        ))
    
    conn.commit()
    conn.close()
    print(f"データベースに保存完了: {len(race_data)}件")

# 使用例
save_to_database("20250607")
```

---

## 🎯 実運用での推奨パターン

### 1. 日次運用パターン
```bash
# 毎日午前9時に前日のデータを取得
python src/keibabook/batch_process.py --start-date $(date -d "yesterday" +%Y/%m/%d)
```

### 2. 週次運用パターン
```bash
# 毎週月曜日に前週のデータを一括取得
for i in {1..7}; do
    date=$(date -d "$i days ago" +%Y/%m/%d)
    python src/keibabook/batch_process.py --start-date $date --delay 5
    sleep 60  # 1分間隔
done
```

### 3. 月次運用パターン
```bash
# 月初に前月のデータを確認・補完
python src/keibabook/batch_process.py --start-date 2024/12/01 --end-date 2024/12/31 --data-types seiseki
```

---

**🎉 これらの使用例を参考に、用途に応じてシステムをカスタマイズしてください！** 
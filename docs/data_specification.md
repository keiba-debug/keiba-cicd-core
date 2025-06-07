# 競馬ブックスクレイピングシステム - データ仕様書

## 📊 概要

競馬ブック（https://p.keibabook.co.jp/）から取得可能なデータと保存構造に関する仕様書です。

**更新日**: 2025年6月7日  
**バージョン**: v2.3（高速版対応）  
**対象ドメイン**: `p.keibabook.co.jp`  
**出力形式**: JSON専用（HTMLファイルは保存しません）  
**保存方式**: 同一フォルダ保存（data/keibabook/直下）  
**新機能**: 🚀 RequestsScraperによる高速化（10-20倍高速）

---

## 🗂 取得可能データ一覧

### 1. レース成績データ (seiseki)
- **ページタイプ**: レース結果
- **実装状況**: ✅ **完全実装済み（JSON）**
- **URL構造**: `https://p.keibabook.co.jp/cyuou/seiseki/{race_id}`
- **サンプルURL**: `https://p.keibabook.co.jp/cyuou/seiseki/202502041211`

### 2. 出馬表データ (shutsuba) 
- **ページタイプ**: 出走予定馬
- **実装状況**: ✅ **完全実装済み（JSON）**
- **URL構造**: `https://p.keibabook.co.jp/cyuou/shutsuba/{race_id}`
- **サンプルURL**: `https://p.keibabook.co.jp/cyuou/shutsuba/202503040111`

### 3. 調教データ (cyokyo)
- **ページタイプ**: 調教タイム・評価
- **実装状況**: ✅ **完全実装済み（JSON）**
- **URL構造**: `https://p.keibabook.co.jp/cyuou/cyokyo/0/0/{race_id}`
- **サンプルURL**: `https://p.keibabook.co.jp/cyuou/cyokyo/0/0/202503040111`

### 4. 厩舎の話データ (danwa)
- **ページタイプ**: 厩舎関係者コメント
- **実装状況**: ✅ **完全実装済み（JSON）**
- **URL構造**: `https://p.keibabook.co.jp/cyuou/danwa/0/{race_id}`
- **サンプルURL**: `https://p.keibabook.co.jp/cyuou/danwa/0/202503040111`

### 5. レース日程データ (nittei)
- **ページタイプ**: 開催スケジュール
- **実装状況**: ✅ **完全実装済み（JSON）**
- **URL構造**: `https://p.keibabook.co.jp/cyuou/nittei/{date_str}`
- **サンプルURL**: `https://p.keibabook.co.jp/cyuou/nittei/20250304`

---

## 🗃 ディレクトリ構造（同一フォルダ保存）

```
keiba-cicd-core/
├── data/
│   └── keibabook/                  # 📊 すべてのJSONファイル（同一フォルダ）
│       ├── race_ids/               # レースID情報
│       │   └── YYYYMMDD_info.json
│       ├── nittei_YYYYMMDD.json    # 日程JSON
│       ├── seiseki_{race_id}.json  # 成績JSON
│       ├── shutsuba_{race_id}.json # 出馬表JSON
│       ├── cyokyo_{race_id}.json   # 調教JSON
│       └── danwa_{race_id}.json    # 厩舎の話JSON
└── logs/                           # ログファイル
    ├── batch_cli_*.log
    └── data_fetcher_*.log
```

**注意**: v2.2では全JSONファイルが `data/keibabook/` 直下に保存されます。サブディレクトリは使用しません。

---

## 🚀 システム使用方法

### 🔥 高速版（推奨）- RequestsScraperを使用

#### 1. 超高速全データタイプ取得（最大性能）
```bash
# 全データタイプを超高速取得（10-20倍高速化）
python -m src.keibabook.fast_batch_cli full --start-date 2025/6/7

# 最大性能設定（並列処理 + 短縮間隔）
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

#### 2. 高速データ取得（並列処理）
```bash
# seisekiのみ高速取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/6/7 \
  --data-types seiseki \
  --max-workers 8

# 複数データタイプ並列取得
python -m src.keibabook.fast_batch_cli data \
  --start-date 2025/6/7 \
  --data-types seiseki,shutsuba,cyokyo,danwa \
  --max-workers 10
```

#### 3. 高速日程取得
```bash
# レース日程を高速取得
python -m src.keibabook.fast_batch_cli schedule --start-date 2025/6/7
```

### 📊 パフォーマンス比較

| 項目 | 従来版（Selenium） | 高速版（requests） | 改善率 |
|------|-------------------|-------------------|--------|
| **処理時間** | 60-90秒/12レース | **8.6秒/12レース** | **7-10倍高速** |
| **リソース使用量** | 高（Chrome起動） | **低（HTTP直接）** | **大幅削減** |
| **並列処理** | 困難 | **最大22並列対応** | **大幅改善** |
| **安定性** | 中（ブラウザ依存） | **高（HTTP直接）** | **向上** |

### ⚙️ 推奨設定

| 用途 | delay | max-workers | 説明 |
|------|-------|-------------|------|
| **テスト** | 1.0 | 3 | 安全な設定 |
| **通常使用** | 0.5 | 5-8 | バランス重視 |
| **高速処理** | 0.3 | 8-12 | 最大性能 |
| **サーバー負荷軽減** | 2.0 | 3 | 負荷軽減 |

### 🐌 従来版（互換性維持）

#### 1. 全データタイプ自動取得
```bash
# 全データタイプ（seiseki, shutsuba, cyokyo, danwa）+ nittei を自動取得
python -m src.keibabook.batch_cli full --start-date 2025/1/7

# 期間指定
python -m src.keibabook.batch_cli full --start-date 2025/1/1 --end-date 2025/1/7

# 待機時間調整
python -m src.keibabook.batch_cli full --start-date 2025/1/7 --delay 5
```

#### 2. 特定データタイプのみ取得
```bash
# seisekiのみ取得
python -m src.keibabook.batch_cli data --start-date 2025/1/7 --data-types seiseki

# 複数データタイプ指定
python -m src.keibabook.batch_cli data --start-date 2025/1/7 --data-types seiseki,shutsuba

# 調教データのみ取得
python -m src.keibabook.batch_cli data --start-date 2025/1/7 --data-types cyokyo
```

#### 3. 日程のみ取得
```bash
# レース日程のみ取得
python -m src.keibabook.batch_cli schedule --start-date 2025/1/7
```

### 自動化スクリプト

#### Linux/macOS
```bash
# 今日のデータを取得
./scripts/daily_scraping.sh

# 指定日のデータを取得
./scripts/daily_scraping.sh 20250107
```

#### Windows
```powershell
# 全処理実行
.\scripts\daily_batch_v2.ps1 -Date "2025/1/7" -Mode "full"

# データのみ取得
.\scripts\daily_batch_v2.ps1 -Date "2025/1/7" -Mode "data"
```

### デバッグモード
```bash
# 詳細ログでの実行
python -m src.keibabook.batch_cli full --start-date 2025/1/7 --debug
```

---

## 📋 JSON データ仕様

### 1. レース成績データ (seiseki)

#### ファイル形式
- **形式**: JSON
- **エンコーディング**: UTF-8
- **命名規則**: `seiseki_YYYYMMDDHHMM.json`
- **保存場所**: `data/keibabook/`

#### データ構造
```json
{
  "race_info": {
    "race_name": "2025年1月7日東京11R第９２回 東京優駿(ＧＩ)"
  },
  "results": [
    {
      "着順": "1",
      "My印": "",
      "本紙": "◎",
      "枠番": "7",
      "馬番": "13",
      "馬名": "クロワデュノール",
      "性齢": "牡3",
      "重量": "57",
      "騎手": "",
      "騎手_2": "ルメール",
      "タイム": "2.23.7",
      "着差": "",
      "通過順位": "****",
      "4角位置": "*",
      "前半3F": "*",
      "上り3F": "34.2",
      "単人気": "1",
      "単勝オッズ": "2.1",
      "馬体重": "504",
      "増減": "+4",
      "厩舎": "栗斉藤崇",
      "interview": "騎手インタビュー内容...",
      "memo": "次走への展望..."
    }
  ]
}
```

#### フィールド詳細
| フィールド名 | データ型 | 例 | 説明 |
|-------------|----------|---|------|
| `race_name` | String | "2025年1月7日東京11R第９２回 東京優駿(ＧＩ)" | レース正式名称 |
| `着順` | String | "1", "2", "18" | 着順 |
| `My印` | String | "", "*" | ユーザー印（通常空） |
| `本紙` | String | "*", "◎", "○" | 競馬ブック本紙予想印 |
| `枠番` | String | "1"～"8" | 枠番 |
| `馬番` | String | "1"～"18" | 馬番 |
| `馬名` | String | "クロワデュノール" | 競走馬名 |
| `性齢` | String | "牡3", "牝4", "セ5" | 性別・年齢 |
| `重量` | String | "57", "56", "54" | 斤量（kg） |
| `騎手` | String | "" | 空フィールド（colspan対応のため） |
| `騎手_2` | String | "北村友", "ルメール" | 騎手名 |
| `タイム` | String | "2.23.7", "1.34.2" | 走破タイム |
| `着差` | String | "", "3/4", "クビ", "大差" | 前走馬との着差 |
| `通過順位` | String | "****", "12-12-8-5" | 各コーナー通過順位 |
| `4角位置` | String | "*", "5", "12" | 4角での位置 |
| `前半3F` | String | "*", "35.2" | 前半3ハロンタイム |
| `上り3F` | String | "34.2", "33.7" | 上り3ハロンタイム |
| `単人気` | String | "1", "5", "12" | 単勝人気順位 |
| `単勝オッズ` | String | "2.1", "15.9", "77.5" | 単勝オッズ |
| `馬体重` | String | "504", "466" | 馬体重（kg） |
| `増減` | String | "+4", "-2", "0" | 前走からの馬体重増減 |
| `厩舎` | String | "栗斉藤崇", "美手塚久" | 厩舎名（所属・調教師名） |
| `interview` | String | "騎手コメント..." | 騎手インタビュー（勝利馬等） |
| `memo` | String | "次走への展望..." | 次走へのメモ（上位馬等） |

### 2. 出馬表データ (shutsuba)

#### ファイル形式
- **保存場所**: `data/keibabook/`
- **命名規則**: `shutsuba_YYYYMMDDHHMM.json`

#### データ構造
```json
{
  "race_info": {
    "race_name": "レース名",
    "race_date": "開催日",
    "venue": "開催場所"
  },
  "horses": [
    {
      "枠番": "1",
      "馬番": "1",
      "馬名": "馬名",
      "性齢": "牡3",
      "斤量": "57",
      "騎手": "騎手名",
      "厩舎": "厩舎名",
      "馬主": "馬主名",
      "生産者": "生産者名",
      "父": "父馬名",
      "母": "母馬名",
      "母父": "母父馬名"
    }
  ]
}
```

### 3. 調教データ (cyokyo)

#### ファイル形式
- **保存場所**: `data/keibabook/`
- **命名規則**: `cyokyo_YYYYMMDDHHMM.json`

#### データ構造
```json
{
  "race_info": {
    "race_name": "レース名"
  },
  "training_data": [
    {
      "馬番": "1",
      "馬名": "馬名",
      "調教日": "2025-01-05",
      "調教場": "栗東坂路",
      "調教タイム": "52.0",
      "調教評価": "B",
      "調教コメント": "調教コメント内容",
      "騎乗者": "騎乗者名"
    }
  ]
}
```

### 4. 厩舎の話データ (danwa)

#### ファイル形式
- **保存場所**: `data/keibabook/`
- **命名規則**: `danwa_YYYYMMDDHHMM.json`

#### データ構造
```json
{
  "race_info": {
    "race_name": "レース名"
  },
  "comments": [
    {
      "馬番": "1",
      "馬名": "馬名",
      "厩舎": "厩舎名",
      "コメント": "厩舎関係者のコメント内容",
      "コメント日": "2025-01-06"
    }
  ]
}
```

### 5. レース日程データ (nittei)

#### ファイル形式
- **保存場所**: `data/keibabook/`
- **命名規則**: `nittei_YYYYMMDD.json`

#### データ構造
```json
{
  "date": "20250107",
  "kaisai_data": {
    "東京": [
      {
        "race_no": "1",
        "race_name": "3歳未勝利",
        "course": "芝1600m",
        "race_id": "202501070111"
      }
    ],
    "中山": [
      {
        "race_no": "1",
        "race_name": "3歳未勝利",
        "course": "ダ1200m",
        "race_id": "202501070611"
      }
    ]
  },
  "total_races": 24,
  "kaisai_count": 2
}
```

---

## 🎯 レースID仕様

### 形式
- **桁数**: 12桁
- **構成**: `YYYYMMDDVRRR`
  - `YYYY`: 年（4桁）
  - `MM`: 月（2桁）
  - `DD`: 日（2桁）
  - `V`: 会場コード（1桁）
  - `RRR`: レース番号（3桁、ゼロ埋め）

### 会場コード一覧
| コード | 会場名 | 備考 |
|--------|--------|------|
| 1 | 札幌 | 夏季開催 |
| 2 | 函館 | 夏季開催 |
| 3 | 福島 | |
| 4 | 新潟 | |
| 5 | 東京 | メイン会場 |
| 6 | 中山 | |
| 7 | 中京 | |
| 8 | 京都 | |
| 9 | 阪神 | |
| 10 | 小倉 | |

### サンプル
- `202501070511`: 2025年1月7日・東京（5）・11R
- `202501070111`: 2025年1月7日・東京（5）・1R

---

## ⚙️ 設定・認証

### 必要Cookie
1. **keibabook_session**: セッションID
2. **tk**: トークン
3. **XSRF-TOKEN**: CSRF保護トークン

### 環境変数設定（.env）
```bash
KEIBABOOK_SESSION="実際のセッション値"
KEIBABOOK_TK="実際のtk値"
KEIBABOOK_XSRF_TOKEN="実際のXSRF値"
```

### 取得方法
1. https://p.keibabook.co.jp/ でログイン
2. F12 → Application → Cookies → p.keibabook.co.jp
3. 上記3つのCookie値をコピー

---

## 📈 データ活用例

### 基本的な分析
```python
import json

# レース成績データの読み込み
with open('data/keibabook/seiseki_202501070511.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 基本情報
race_name = data['race_info']['race_name']
horse_count = len(data['results'])

# 勝利馬情報
winner = data['results'][0]
winner_name = winner['馬名']
winner_time = winner['タイム']
winner_odds = winner['単勝オッズ']

print(f"レース: {race_name}")
print(f"勝利馬: {winner_name} (タイム: {winner_time}, オッズ: {winner_odds})")
```

### 複数データタイプの統合分析
```python
import json
from pathlib import Path

race_id = "202501070511"

# 各データタイプを読み込み
data_types = ['seiseki', 'shutsuba', 'cyokyo', 'danwa']
race_data = {}

for data_type in data_types:
    file_path = f'data/keibabook/{data_type}_{race_id}.json'
    if Path(file_path).exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            race_data[data_type] = json.load(f)

# 統合分析
print(f"取得データタイプ: {list(race_data.keys())}")
```

### 日付別ファイル検索
```python
import glob

# 特定日のすべてのJSONファイルを取得
date_str = "20250107"
json_files = glob.glob(f'data/keibabook/*{date_str}*.json')

print(f"{date_str}のファイル数: {len(json_files)}")
for file_path in sorted(json_files):
    print(f"  - {file_path}")
```

---

## 🚨 注意事項

### 1. 利用規約遵守
- 競馬ブックの利用規約を必ず守る
- 適切な間隔でのアクセス（3秒以上推奨）
- 過度な負荷をかけない

### 2. Cookie有効期限
- Cookieは定期的に無効になる
- ログインエラー時は新しいCookieを取得

### 3. データ精度
- JSONパース結果の妥当性確認
- エラーログの定期チェック
- データバックアップの実施

### 4. システム制限
- 実装済み: 全5種類のデータタイプ
- 地方競馬は未対応
- HTMLファイルは保存されません
- 全JSONファイルは同一フォルダに保存

---

## 🔄 今後の拡張予定

### Phase 1: パフォーマンス向上
- 並列処理の導入
- キャッシュ機能の実装
- リアルタイム監視

### Phase 2: 機能拡張
- 地方競馬対応
- オッズデータ取得
- 血統情報の詳細化

### Phase 3: 分析機能
- データ分析ツールの統合
- 可視化機能
- 予測モデルとの連携

---

**📞 サポート**: 設定ファイルやログファイルを確認してトラブルシューティングを実施してください。 

## 📁 ファイル出力仕様

### ファイル命名規則
- **nittei（日程）**: `nittei_YYYYMMDD.json`
- **seiseki（成績）**: `seiseki_YYYYMMDDHHMM.json`
- **shutsuba（出馬表）**: `shutsuba_YYYYMMDDHHMM.json`
- **cyokyo（調教）**: `cyokyo_YYYYMMDDHHMM.json`
- **danwa（厩舎の話）**: `danwa_YYYYMMDDHHMM.json`

### 保存場所
- **統一ディレクトリ**: `data/keibabook/` 直下
- **環境変数対応**: `KEIBA_KEIBABOOK_DIR` で変更可能

### 開催がない日の処理
- **開催がない日はJSONファイルを出力しません**
- 月曜日や祝日など、競馬開催がない日は空のファイルではなく、ファイル自体が作成されません
- システムログには「📭 開催なし」として記録され、正常処理として扱われます
- バッチ処理は成功として完了します 
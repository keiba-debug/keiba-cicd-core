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

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

環境変数で競馬ブック用のCookieを設定します：

```bash
export KEIBABOOK_SESSION="your_session_cookie"
export KEIBABOOK_TK="your_tk_cookie"
export KEIBABOOK_XSRF_TOKEN="your_xsrf_token"
export DEBUG="false"
export HEADLESS="true"
```

### 3. ChromeDriverのインストール

Seleniumを使用するため、ChromeDriverが必要です：

```bash
# Ubuntuの場合
sudo apt-get update
sudo apt-get install chromium-chromedriver

# macOSの場合
brew install chromedriver

# Windowsの場合
# https://chromedriver.chromium.org/ からダウンロード
```

## 💻 使用方法

### 基本的な使用方法

```bash
# 成績データをスクレイピング＋パース
python main.py --race-id 202502041211 --mode scrape_and_parse

# HTMLファイルのパースのみ
python main.py --race-id 202502041211 --mode parse_only --html-file data/debug/seiseki.html

# テストの実行
python main.py --test
```

### オプション

- `--race-id`: レースID（必須、--testモード以外）
- `--mode`: 実行モード
  - `scrape_and_parse`: スクレイピング＋パース（デフォルト）
  - `parse_only`: HTMLファイルのパースのみ
- `--html-file`: HTMLファイルのパス（parse_onlyモード用）
- `--test`: テストモードで実行
- `--no-save-html`: HTMLファイルを保存しない

### 個別テストの実行

```bash
# 成績パーサーのテスト
python tests/test_new_seiseki_parser.py

# 統合テスト
python tests/test_integration.py
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

# 競馬ブック データ取得システム - ドキュメント

## 📊 システム概要

競馬ブック（keibabook.co.jp）から競馬データを自動取得・分析するシステムの統合ドキュメントです。

**最終更新**: 2025年2月4日  
**システムバージョン**: v2.0（リファクタリング完了）  
**主要機能**: レース日程取得、データ取得、統計分析

---

## 🗂️ ドキュメント構成

### 📋 基本ドキュメント
| ファイル | 対象読者 | 内容 |
|---------|---------|------|
| [setup_guide.md](setup_guide.md) | 初回利用者 | 環境構築・初期設定 |
| [api_reference.md](api_reference.md) | 開発者 | APIリファレンス |
| [configuration_guide.md](configuration_guide.md) | 運用者 | 設定・カスタマイズ |

### 📊 データ関連
| ファイル | 対象読者 | 内容 |
|---------|---------|------|
| [data_specification.md](data_specification.md) | データ分析者 | データ構造・仕様 |
| [usage_examples.md](usage_examples.md) | 利用者 | 実用例・サンプル |

### 🔧 運用・保守
| ファイル | 対象読者 | 内容 |
|---------|---------|------|
| [troubleshooting.md](troubleshooting.md) | 運用者 | トラブル対応 |
| [workflow_guide.md](workflow_guide.md) | 全ユーザー | 完全ワークフロー |

---

## 🚀 クイックスタート

### 1. 環境構築
```bash
# 依存関係インストール
pip install -r requirements.txt

# 設定ファイル生成
python -m src.keibabook.batch_cli --help
```

### 2. 基本的な使用方法
```bash
# レース日程取得
python -m src.keibabook.batch_cli schedule --start-date 2025/02/01

# レースデータ取得  
python -m src.keibabook.batch_cli data --start-date 2025/02/01 --data-types seiseki

# 全処理実行（日程→データ）
python -m src.keibabook.batch_cli full --start-date 2025/02/01
```

### 3. 既存システムとの互換性
```bash
# 従来のmain.pyも引き続き利用可能
python src/keibabook/main.py --race-id 202502041211 --mode scrape_and_parse
```

---

## 🏗️ システム構成

### 新しい統合アーキテクチャ（v2.0）

```
src/keibabook/
├── 📁 batch/                   # 🆕 統合バッチ処理システム
│   ├── core/
│   │   └── common.py           # 共通ユーティリティ
│   ├── data_fetcher.py         # データ取得モジュール
│   └── __init__.py
├── 📁 scrapers/                # スクレイパーモジュール
│   ├── legacy_scrapers.py      # 🆕 レガシー機能統合
│   ├── requests_scraper.py     
│   └── keibabook_scraper.py
├── 📁 parsers/                 # パーサーモジュール
├── 📁 utils/                   # ユーティリティ
├── batch_cli.py                # 🆕 統合CLIシステム
├── main.py                     # 従来メインエントリーポイント
└── auth.py                     # 認証機能
```

### リファクタリング効果
- **ファイル数**: 28個 → 11個（**61%削減**）
- **重複コード**: 大幅削除
- **保守性**: モジュール化により向上
- **新機能**: 統合CLI、統計管理、進捗表示

---

## 📚 主要機能

### 🔄 バッチ処理システム（v2.0）
新しい統合CLIシステムで以下の機能を提供：

1. **レース日程取得** (`schedule`)
   - 競馬ブックからレース日程を取得
   - レースIDの自動生成・保存

2. **レースデータ取得** (`data`)
   - 成績、出馬表、調教、厩舎の話データ
   - 並列処理対応

3. **全処理実行** (`full`)
   - 日程取得からデータ取得まで一括実行
   - 進捗表示・統計サマリー

### 🛠️ 従来機能（互換性維持）
- 単一レースの詳細取得
- HTMLパース・データ抽出
- 認証・セッション管理

---

## 💡 使用例

### 基本的なワークフロー
```bash
# 1. 今週のレース日程を取得
python -m src.keibabook.batch_cli schedule \
  --start-date $(date +%Y/%m/%d) \
  --end-date $(date -d '+7 days' +%Y/%m/%d)

# 2. 今日のレースデータを取得
python -m src.keibabook.batch_cli data \
  --start-date $(date +%Y/%m/%d) \
  --data-types seiseki,shutsuba

# 3. 特定レースの詳細分析
python src/keibabook/main.py \
  --race-id 202502041211 \
  --mode scrape_and_parse
```

### 自動化スクリプト
```bash
# Windows PowerShell
.\scripts\daily_batch.ps1

# Linux/macOS
./scripts/daily_batch.sh
```

---

## ⚙️ 設定・カスタマイズ

### 環境変数設定
```bash
# .env ファイル
KEIBA_DATA_DIR=/path/to/data           # データ保存先
KEIBABOOK_SESSION=session_value        # 認証情報
KEIBABOOK_TK=tk_value                  # 認証トークン
LOG_LEVEL=INFO                         # ログレベル
```

### 詳細設定
- **ディレクトリ構造**: [configuration_guide.md](configuration_guide.md)
- **認証設定**: [setup_guide.md](setup_guide.md)
- **データ形式**: [data_specification.md](data_specification.md)

---

## 🔍 トラブルシューティング

### よくある問題
1. **認証エラー** → Cookieの更新が必要
2. **パースエラー** → HTMLファイルの構造確認
3. **ファイル権限** → ディレクトリの権限設定

### デバッグ方法
```bash
# 詳細ログ付きで実行
python -m src.keibabook.batch_cli full \
  --start-date 2025/02/01 \
  --debug

# 設定確認
python tools/config_manager.py --show
```

詳細は [troubleshooting.md](troubleshooting.md) を参照

---

## 🆕 v2.0の新機能

### 統合CLIシステム
- 3つのサブコマンド（schedule/data/full）
- 進捗表示・統計情報
- エラーハンドリング強化

### 共通ユーティリティ
- 重複コードの統合
- 統一されたログ・設定管理
- BatchStats による詳細統計

### レガシー機能の保持
- 既存の main.py は変更なし
- 全ての旧機能が legacy_scrapers.py で利用可能
- 設定ファイルの互換性維持

---

## 🔗 関連リンク

- **プロジェクトルート**: `../../`
- **スクリプト集**: `../../scripts/`
- **設定ファイル**: `../../.env`
- **ログファイル**: `../../logs/`

---

## 📞 サポート

### 開発者向け
- API詳細: [api_reference.md](api_reference.md)
- 設定方法: [configuration_guide.md](configuration_guide.md)

### 利用者向け
- 導入方法: [setup_guide.md](setup_guide.md)
- 使用例: [usage_examples.md](usage_examples.md)

### 運用者向け
- 自動化: `../scripts/`
- 監視: [troubleshooting.md](troubleshooting.md)

---

**最終更新**: 2025年2月4日  
**リファクタリング**: v1.0 → v2.0 完了  
**次期計画**: 並列処理、WebUI、機械学習連携
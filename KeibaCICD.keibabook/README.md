# KeibaCICD.keibabook

> 競馬ブックWebスクレイピング・データ統合モジュール

競馬ブックWebサイトから成績・出馬表・調教・談話データを自動取得し、統合します。

---

## 🎯 主要機能

- **Webスクレイピング**: 競馬ブックから自動データ取得
- **並列処理**: 最大22並列でデータ取得（高速版）
- **データ統合**: 複数データソースの統合（RaceDataIntegrator）
- **JSON/Markdown出力**: 統合レース情報・Markdown新聞生成

---

## 🚀 クイックスタート

### 1. セットアップ

```bash
cd KeibaCICD.keibabook
python -m venv venv
source venv/Scripts/activate
pip install -r src/requirements.txt
```

### 2. 環境変数設定

`.env` ファイルを作成：
```ini
KEIBA_DATA_ROOT_DIR=E:\share\KEIBA-CICD\data2
JV_DATA_ROOT_DIR=E:\TFJV

# 競馬ブック認証（要手動設定）
KEIBABOOK_SESSION=your_session_token
KEIBABOOK_TK=your_tk_token
KEIBABOOK_XSRF_TOKEN=your_xsrf_token
```

**Cookie取得方法**:
1. Chrome/Edgeで `https://p.keibabook.co.jp/` にログイン
2. 開発者ツール（F12）→ Application → Cookies
3. `SESSION`, `TK`, `XSRF-TOKEN` の値をコピー
4. `.env` ファイルに貼り付け

### 3. データ取得

```bash
# 2026-02-08の全レースデータ取得（高速版・推奨）
python src/fast_batch_cli.py --date 2026-02-08

# 統合JSON生成
python src/integrator_cli.py --date 2026-02-08

# Markdown新聞生成
python src/markdown_cli.py --date 2026-02-08
```

---

## 📊 主要CLIツール

### fast_batch_cli.py ⭐推奨

高速版バッチ処理（requestsベース、並列対応）

```bash
# 基本的な使い方
python src/fast_batch_cli.py --date 2026-02-08

# 東京のみ取得
python src/fast_batch_cli.py --date 2026-02-08 --venue 東京

# 成績データのみ取得
python src/fast_batch_cli.py --date 2026-02-08 --type seiseki
```

---

### batch_cli.py

従来版バッチ処理（Seleniumベース）

```bash
# 日程→データの一括実行
python src/batch_cli.py full --start-date 2026-02-08
```

---

### integrator_cli.py

統合JSON生成（RaceDataIntegrator）

```bash
python src/integrator_cli.py --date 2026-02-08
```

**出力**: `C:/KEIBA-CICD/data2/organized/2026/02/08/{競馬場}/integrated_{RACE_ID}.json`

---

### markdown_cli.py

Markdown新聞生成

```bash
python src/markdown_cli.py --date 2026-02-08
```

**出力**: `C:/KEIBA-CICD/data2/organized/2026/02/08/{競馬場}/{RACE_ID}.md`

---

## 📁 ディレクトリ構成

```
KeibaCICD.keibabook/
├── src/
│   ├── scrapers/           # Webスクレイパー
│   │   ├── requests_scraper.py    # 高速版（推奨）
│   │   └── keibabook_scraper.py   # Selenium版
│   ├── parsers/            # HTMLパーサー
│   │   ├── seiseki_parser.py      # 成績
│   │   ├── syutuba_parser.py      # 出馬表
│   │   ├── cyokyo_parser.py       # 調教
│   │   └── danwa_parser.py        # 談話
│   ├── integrator/         # データ統合
│   │   ├── race_data_integrator.py
│   │   └── markdown_generator_enhanced.py
│   ├── batch/              # バッチ処理
│   ├── fast_batch_cli.py   # 高速版CLI ⭐
│   ├── batch_cli.py        # 従来版CLI
│   ├── integrator_cli.py   # 統合CLI
│   └── markdown_cli.py     # Markdown新聞CLI
├── api/                    # FastAPI管理サーバー
└── gui/                    # Next.js管理画面
```

---

## ⚡ パフォーマンス

| 項目 | 従来版（Selenium） | 高速版（requests） | 改善率 |
|------|-------------------|-------------------|--------|
| **処理時間** | 60-90秒/12レース | **8.6秒/12レース** | **7-10倍高速** |
| **リソース使用量** | 高（Chrome起動） | **低（HTTP直接）** | **大幅削減** |
| **並列処理** | 困難 | **最大22並列対応** | **大幅改善** |
| **安定性** | 中（ブラウザ依存） | **高（HTTP直接）** | **向上** |

---

## 📚 ドキュメント

### はじめに読むドキュメント

- **[MODULE_OVERVIEW.md](../../ai-team/knowledge/MODULE_OVERVIEW.md)** - keibabookモジュール詳細
- **[SETUP_GUIDE.md](../../ai-team/knowledge/SETUP_GUIDE.md)** - 環境構築手順
- **[ARCHITECTURE.md](../../ai-team/knowledge/ARCHITECTURE.md)** - システム全体構成

---

## ⚠️ 注意事項

- **未来の日付**: まだ開催されていないレースはデータが存在しないためエラーになります
- **スクレイピング間隔**: サーバーに負荷をかけないよう適切な間隔を空けてください
- **Cookie有効期限**: Cookie が期限切れの場合は再取得が必要です
- **利用規約**: 取得したデータの利用は、競馬ブックの利用規約に従ってください

---

## 🔗 関連モジュール

- **[KeibaCICD.TARGET](../KeibaCICD.TARGET/)** - データ分析モジュール
- **[KeibaCICD.WebViewer](../KeibaCICD.WebViewer/)** - プレゼンテーションモジュール

---

**プロジェクトオーナー**: ふくだ君
**最終更新**: 2026-02-06

# KeibaCICD v3.0

> **毎週の競馬予想でプラス収支を実現し、推理エンターテインメントとして競馬を楽しむ**

競馬データの自動収集・分析・可視化を行う統合システムです。

---

## 🏗️ システム構成

KeibaCICDは3つの独立モジュールで構成されています：

```
┌─────────────────────┐
│ KeibaCICD.keibabook │  データ収集層
│  Webスクレイピング  │  競馬ブックからデータ取得
└──────────┬──────────┘
           │
           ↓ JSON/Markdown
    ┌──────────────┐
    │ 共有データストア │
    └──────┬───────┘
           │
    ┌──────┴────────┬─────────────┐
    ↓               ↓             ↓
┌────────────┐ ┌────────────┐ ┌──────────────┐
│ KeibaCICD  │ │ KeibaCICD  │ │  KeibaCICD   │
│  .TARGET   │ │.WebViewer  │ │  .JraVanSync │
│ 分析・ML   │ │ Web表示    │ │  補助ツール  │
└────────────┘ └────────────┘ └──────────────┘
```

---

## 📦 モジュール概要

### 1. [KeibaCICD.keibabook](./KeibaCICD.keibabook/) - データ収集層

**役割**: 競馬ブックWebサイトからのデータスクレイピング・統合

**主要機能**:
- 成績・出馬表・調教・談話データの自動取得
- レース情報の統合（JSON/Markdown出力）
- 並列処理による高速化（最大22並列）

**技術**: Python 3.11+, requests, Selenium, BeautifulSoup

**クイックスタート**:
```bash
cd KeibaCICD.keibabook
python src/fast_batch_cli.py --date 2026-02-08
```

---

### 2. [KeibaCICD.TARGET](./KeibaCICD.TARGET/) - データ分析層

**役割**: JRA-VANデータ解析・機械学習予測

**主要機能**:
- JRA-VAN統合ライブラリ（ID変換・データアクセス）
- PCI（ペース指数）分析
- 機械学習による勝率予測（LightGBM/XGBoost）
- 期待値計算（オッズ×勝率）

**技術**: Python 3.8+, LightGBM, XGBoost, scikit-learn

**クイックスタート**:
```bash
cd KeibaCICD.TARGET
python scripts/training_summary.py 2026-02-08
```

---

### 3. [KeibaCICD.WebViewer](./KeibaCICD.WebViewer/) - プレゼンテーション層

**役割**: データ可視化・Web UI

**主要機能**:
- レース情報のWeb表示
- 馬プロファイル表示
- JRA映像マルチビュー
- メモ機能・資金管理

**技術**: Next.js 16, React 19, TypeScript, Tailwind CSS

**クイックスタート**:
```bash
cd KeibaCICD.WebViewer
npm run dev
# http://localhost:3000
```

---

## 📚 ドキュメント

### 🎯 はじめに読むドキュメント

| ドキュメント | 内容 | 対象者 |
|------------|------|--------|
| **[ARCHITECTURE.md](ai-team/knowledge/ARCHITECTURE.md)** | システム全体構成・データフロー | 全員 ⭐ |
| **[SETUP_GUIDE.md](ai-team/knowledge/SETUP_GUIDE.md)** | 環境構築手順 | 初回セットアップ時 ⭐ |
| **[MODULE_OVERVIEW.md](ai-team/knowledge/MODULE_OVERVIEW.md)** | 各モジュール詳細・API | 開発者 |
| **[CLAUDE.md](ai-team/knowledge/CLAUDE.md)** | AIエージェントチーム統合ガイドライン | AIエージェント |
| **[DATA_SPECIFICATION.md](ai-team/knowledge/DATA_SPECIFICATION.md)** | データ仕様書 | 全員 |

### 📖 詳細ドキュメント

- **[プロジェクト計画](./docs/project/project-plan.md)** - 3年計画・フェーズ定義
- **[開発ガイドライン](./docs/development/development-guidelines.md)** - コーディング規約
- **[JRA-VAN使用ガイド](./KeibaCICD.TARGET/docs/jravan/USAGE_GUIDE.md)** - JRA-VANライブラリ

---

## 🚀 クイックスタート

### 1. 環境構築

```bash
# リポジトリクローン
git clone <repository-url> c:/KEIBA-CICD/_keiba
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core

# データディレクトリ作成
mkdir -p C:/KEIBA-CICD/data2
```

詳細は **[SETUP_GUIDE.md](ai-team/knowledge/SETUP_GUIDE.md)** を参照。

---

### 2. データ収集（keibabook）

```bash
cd KeibaCICD.keibabook
python -m venv venv
source venv/Scripts/activate
pip install -r src/requirements.txt

# 2026-02-08のデータ取得
python src/fast_batch_cli.py --date 2026-02-08
python src/integrator_cli.py --date 2026-02-08
```

---

### 3. データ分析（TARGET）

```bash
cd KeibaCICD.TARGET
python -m venv venv
source venv/Scripts/activate
pip install -r ml/requirements.txt

# 馬名インデックス構築
python scripts/horse_id_mapper.py --build-index

# 調教データ集計
python scripts/training_summary.py 2026-02-08
```

---

### 4. Web表示（WebViewer）

```bash
cd KeibaCICD.WebViewer
npm install
npm run dev
# http://localhost:3000 を開く
```

---

## 🔧 環境変数

### keibabook / TARGET

`.env` ファイルを作成：

```ini
# データディレクトリ
KEIBA_DATA_ROOT_DIR=E:\share\KEIBA-CICD\data2
JV_DATA_ROOT_DIR=E:\TFJV

# 競馬ブック認証（要手動設定）
KEIBABOOK_SESSION=your_session_token
KEIBABOOK_TK=your_tk_token
KEIBABOOK_XSRF_TOKEN=your_xsrf_token
```

### WebViewer

`.env.local` ファイルを作成：

```ini
DATA_ROOT=C:/KEIBA-CICD/data2
JV_DATA_ROOT_DIR=C:/TFJV
```

---

## 📊 データフロー

```
競馬ブックWeb
    ↓ [スクレイピング]
KeibaCICD.keibabook
    ↓ [JSON/Markdown]
共有データストア (C:/KEIBA-CICD/data2/)
    ↓
┌───────────┴───────────┐
↓                       ↓
KeibaCICD.TARGET    KeibaCICD.WebViewer
    ↓                       ↓
予測結果JSON         ブラウザUI
```

詳細は **[ARCHITECTURE.md](ai-team/knowledge/ARCHITECTURE.md)** を参照。

---

## 🎯 プロジェクトの目的

**毎週の競馬予想でプラス収支を実現し、推理エンターテインメントとして競馬を楽しむ**

これは競馬システムを作ることが目的ではなく、**実際に馬券を当てること**が目的です。

### 設計思想

- **データ駆動**: 複数ソースからの自動データ取得
- **AI協調**: 専門エキスパートAIチームによる分析
- **期待値重視**: オッズ×勝率による投資判断
- **継続改善**: 予想と結果の記録・学習

---

## 🆘 サポート

- **GitHub Issues**: `https://github.com/your-org/keiba-cicd/issues`
- **AIエージェント**: カカシ（AI相談役）に質問
- **ドキュメント**: `ai-team/knowledge/` 配下

---

## 📝 バージョン履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| **v3.0** | 2026-02-06 | ドキュメント統一・アーキテクチャ整理（カカシ） |
| v2.4 | 2025-06 | keibabook高速版CLI、並列処理対応 |
| v2.0 | 2025 | RaceDataIntegrator統合、TARGET ML実装 |
| v1.0 | 2024 | 初版リリース |

---

**プロジェクトオーナー**: ふくだ君
**AI相談役**: カカシ
**最終更新**: 2026-02-06

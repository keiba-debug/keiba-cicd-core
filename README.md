# KeibaCICD v3.0

> **毎週の競馬予想でプラス収支を実現し、推理エンターテインメントとして競馬を楽しむ**

競馬データの自動収集・分析・可視化を行う統合システムです。

---

## 📑 目次

- [システム構成](#-システム構成)
- [モジュール概要](#-モジュール概要)
- [ドキュメント](#-ドキュメント)
- [クイックスタート](#-クイックスタート)
- [WebViewer 起動・運用](#-webviewer-起動運用)
- [環境変数](#-環境変数)
- [データフロー](#-データフロー)
- [プロジェクトの目的](#-プロジェクトの目的)
- [サポート](#-サポート)
- [バージョン履歴](#-バージョン履歴)

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
    ┌──────┴────────┬─────────────┬─────────────┐
    ↓               ↓             ↓             ↓
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐
│ KeibaCICD  │ │ KeibaCICD  │ │ KeibaCICD  │ │  KeibaCICD   │
│  .TARGET   │ │.WebViewer  │ │    .AI     │ │  .JraVanSync │
│ 分析・ML   │ │ Web表示    │ │ ML予想     │ │  補助ツール  │
└────────────┘ └────────────┘ └────────────┘ └──────────────┘
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

### 4. [KeibaCICD.AI](./KeibaCICD.AI/) - ML予想・期待値計算層

**役割**: 機械学習による予想・期待値計算・購入戦略

**主要機能**:
- データ読み込み（target_reader.py）
- 資金管理（Bankroll Management）
- ML予想（v4.0以降: LightGBM/XGBoost）
- 期待値計算（v5.0以降）

**技術**: Python 3.8+, LightGBM, XGBoost（将来）

**クイックスタート**:
```bash
cd KeibaCICD.AI
python tools/target_reader.py
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

### 📖 目的別ガイド

<details>
<summary>プロジェクト全体を理解したい</summary>

→ [ai-team/knowledge/CLAUDE.md](ai-team/knowledge/CLAUDE.md) - チームガイドライン v1.0

</details>

<details>
<summary>データ構造を知りたい</summary>

→ [ai-team/knowledge/DATA_SPECIFICATION.md](ai-team/knowledge/DATA_SPECIFICATION.md) - データ仕様統一版

</details>

<details>
<summary>WebViewer APIを使いたい</summary>

→ [KeibaCICD.WebViewer/docs/api/WEBVIEWER_API_SPECIFICATION.md](./KeibaCICD.WebViewer/docs/api/WEBVIEWER_API_SPECIFICATION.md) - 全34API詳細

</details>

<details>
<summary>JRA-VANデータを使いたい</summary>

→ [KeibaCICD.TARGET/docs/jravan/](./KeibaCICD.TARGET/docs/jravan/) - JRA-VAN統一仕様書

</details>

<details>
<summary>AIエージェントを実装したい</summary>

→ [ai-team/knowledge/AI_DATA_ACCESS_GUIDE.md](ai-team/knowledge/AI_DATA_ACCESS_GUIDE.md) - AI実装完全ガイド

</details>

<details>
<summary>ML戦略・投資フレームワークを知りたい</summary>

→ [ai-team/ml/docs/BETTING_STRATEGY_FRAMEWORK.md](ai-team/ml/docs/BETTING_STRATEGY_FRAMEWORK.md) - 投資戦略フレームワーク

</details>

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

## 🖥️ WebViewer 起動・運用

### 起動方法

```powershell
# 環境変数設定
$env:DATA_ROOT= "C:\KEIBA-CICD\data2"
$env:JV_DATA_ROOT_DIR = "C:\TFJV"

cd .\keiba-cicd-core\KeibaCICD.WebViewer
npm run dev
```

ブラウザで http://localhost:3000 を開きます。

### 主要ページ

| ページ | URL | 説明 |
|:---|:---|:---|
| トップ | http://localhost:3000 | 日付選択・レース一覧 |
| 管理画面 | http://localhost:3000/admin | keibabookデータ取得・バッチ実行 |
| 馬検索 | http://localhost:3000/horses | 馬名検索・プロファイル表示 |
| マルチビュー | http://localhost:3000/multi-view | JRA映像並列表示（2画面/4画面） |

### トラブルシューティング

<details>
<summary>馬場コンディション（クッション値・含水率）が表示されない場合</summary>

レース結果分析画面で「馬場: クッション ○○ / G前 ○○% …」が出ないときは、次を確認してください。

1. **JV_DATA_ROOT_DIR**
   - BABA の CSV は `JV_DATA_ROOT_DIR/_BABA` を参照します
   - 未設定時は `C:\TFJV` になります

2. **race_info.json と kaisai_data**
   - 該当日の `race_info.json` に `kaisai_data` があること
   - kaisai_data から「回・日」を取得して BABA の RX_ID を組み立てます

3. **BABA の CSV ファイル**
   - `JV_DATA_ROOT_DIR/_BABA` の下に以下のファイルが必要:
     - `cushion2026.csv`（クッション値）
     - `moistureG_2026.csv`（ゴール前含水率）
     - `moisture4_2026.csv`（4コーナー含水率）

4. **デバッグAPI**
   - `http://localhost:3000/api/debug/baba?date=2026-01-25&track=京都&raceId=202601250809`
   - どこで止まっているか確認できます

</details>

<details>
<summary>レース一覧が「この月にはレースデータがありません」となる場合</summary>

- レース一覧は次のどちらかで「データあり」とみなします:
  1. 競馬場フォルダ＋MD出走表（.md）がある日
  2. `race_info.json`（`kaisai_data` あり）がある日
- 日付一覧はキャッシュ `DATA_ROOT/cache/race_date_index.json` を参照します。データを追加した場合は **インデックス再構築**（`POST /api/admin/rebuild-index` または管理画面）が必要です。
- 詳しい原因と確認手順: [keiba-v2/web/docs/トラブルシュート_レース一覧.md](keiba-v2/web/docs/トラブルシュート_レース一覧.md)

</details>

<details>
<summary>Turbopack FATAL エラーが出る場合</summary>

Next.js 16では開発時にTurbopackがデフォルトで使われます。エラーが出る場合:

```powershell
cd .\keiba-cicd-core\KeibaCICD.WebViewer
npm run dev  # webpack で起動（推奨）
```

- Node.js >=20.9.0 が必要です
- `npm run dev` を使用（`next dev` を直接実行しない）

</details>

---

## 🔧 環境変数

### keibabook / TARGET

`.env` ファイルを作成：

```ini
# データディレクトリ
KEIBA_DATA_ROOT_DIR=C:\KEIBA-CICD\data2
JV_DATA_ROOT_DIR=C:\TFJV

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
**最終更新**: 2026-02-07

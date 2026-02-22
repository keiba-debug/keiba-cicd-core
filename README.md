# KeibaCICD v5.8

> **毎週の競馬予想でプラス収支を実現し、推理エンターテインメントとして競馬を楽しむ**

JRA-VANデータ + 競馬ブックデータを統合し、機械学習で期待値ベースの馬券購入を支援するシステムです。

---

## 📑 目次

- [システム構成](#-システム構成)
- [クイックスタート](#-クイックスタート)
- [主要モジュール](#-主要モジュール)
- [WebViewer](#-webviewer)
- [ML パイプライン](#-ml-パイプライン)
- [ディレクトリ構成](#-ディレクトリ構成)
- [環境変数](#-環境変数)
- [バージョン履歴](#-バージョン履歴)

---

## 🏗️ システム構成

```
┌──────────────┐   ┌──────────────┐
│   JRA-VAN    │   │  競馬ブック   │
│  (C:\TFJV)   │   │ (Webスクレイピング)│
└──────┬───────┘   └──────┬───────┘
       │                   │
       ↓                   ↓
┌─────────────────────────────────────┐
│       keiba-v2 (Python)             │
│  builders/ → races/masters JSON     │
│  ml/       → LightGBM予測           │
│  keibabook/→ 調教・談話データ        │
└──────────────────┬──────────────────┘
                   │
                   ↓ JSON (data3/)
┌─────────────────────────────────────┐
│       keiba-v2/web (Next.js)        │
│  レース一覧・馬詳細・ML分析          │
│  Value Bet・買い目・RPCI分析         │
└─────────────────────────────────────┘
```

**技術スタック**: Python 3.11 + LightGBM + Next.js 16 + React 19 + TypeScript + MySQL(mykeibadb)

---

## 🚀 クイックスタート

### 前提条件

- Python 3.11+
- Node.js 20.9+
- JRA-VANデータ（`C:\TFJV`）
- MySQL（mykeibadb — オッズ時系列用）

### 1. WebViewer 起動

```powershell
cd keiba-v2\web
npm install          # 初回のみ
npm run dev:turbo    # http://localhost:3000
```

### 2. データ構築（Python）

```powershell
# venv有効化
cd keiba-v1\KeibaCICD.keibabook
.venv\Scripts\Activate.ps1

# レース・馬マスタ構築
cd ..\..\keiba-v2
python -m builders.build_race_master
python -m builders.build_horse_master
python -m builders.build_horse_history

# インデックス構築
python -m builders.build_race_index
python -m builders.build_horse_name_index
```

### 3. 競馬ブックデータ取得

```powershell
# venv有効化済みの状態で
cd keiba-v2
python -m keibabook.batch_scraper --date 2026-02-22
python -m keibabook.ext_builder --date 2026-02-22
```

### 4. ML 予測実行

```powershell
cd keiba-v2
python -m ml.predict --date 2026-02-22
```

---

## 📦 主要モジュール

すべて `keiba-v2/` 配下に統合されています。

| モジュール | 内容 |
|-----------|------|
| `core/` | 設定・定数・DB接続・JRA-VANパーサー・データモデル |
| `builders/` | JRA-VANデータからレース/馬/調教師/騎手マスタJSON構築 |
| `ml/` | LightGBMモデル訓練(`experiment.py`)・予測(`predict.py`)・バックテスト |
| `ml/features/` | 特徴量エンジニアリング（10モジュール、91特徴量） |
| `analysis/` | レーティング基準・レース分類・調教師パターン分析 |
| `keibabook/` | 競馬ブックスクレイピング・調教パース・拡張データ構築 |
| `web/` | Next.js WebViewer（後述） |

### 特徴量モジュール一覧

| ファイル | 特徴量 | 分類 |
|---------|--------|------|
| `base_features.py` | 馬齢・性別・斤量・枠番・オッズ等 | MARKET/BASE |
| `past_features.py` | 過去走成績・着差・上がり3F等 | VALUE |
| `trainer_features.py` | 調教師勝率・距離適性等 | VALUE |
| `jockey_features.py` | 騎手勝率・乗替わり効果等 | VALUE |
| `running_style_features.py` | 脚質・展開適性 | VALUE |
| `rotation_features.py` | 降格ローテ・レースレベル判定 | VALUE |
| `pace_features.py` | ラップ分析・RPCI・33ラップ | VALUE |
| `speed_features.py` | スピード指数・距離適性 | VALUE |
| `training_features.py` | CK_DATA調教タイム・レベル | MARKET |
| `comment_features.py` | 厩舎コメントNLPスコア | VALUE(+1 MARKET) |

---

## 🖥️ WebViewer

### 起動

```powershell
cd keiba-v2\web
npm run dev:turbo    # Turbopack（高速）
# または
npm run dev          # webpack（安定）
```

ブラウザで http://localhost:3000 を開く。

### 主要ページ

| ページ | パス | 説明 |
|:---|:---|:---|
| レース一覧 | `/` | 日付選択・開催レース一覧 |
| レース詳細 | `/races-v2/[raceId]` | 出馬表・オッズ・過去走 |
| ML予測 | `/predictions` | 当日全レース予測・Value Bet・買い目 |
| ML分析 | `/analysis/ml` | モデル精度・特徴量重要度・ROI分析 |
| RPCI分析 | `/analysis/rpci` | ペース分析・ラップチャート |
| 馬検索 | `/horses` | 馬名検索・馬詳細プロファイル |
| 調教師分析 | `/analysis/trainer-patterns` | 調教師パターン・ローテ傾向 |
| 管理画面 | `/admin` | データ取得・インデックス再構築 |
| マルチビュー | `/multi-view` | JRA映像並列表示 |
| 資金管理 | `/bankroll` | 収支記録・資金配分 |
| オッズボード | `/odds-board` | リアルタイムオッズ一覧 |

---

## 🤖 ML パイプライン

> **ソース解説**: 開発中ソースの詳細解説は [`keiba-v2/docs/ML_SOURCE_GUIDE.md`](keiba-v2/docs/ML_SOURCE_GUIDE.md) を参照。

### モデル構成（v5.3）

| モデル | 目的 | 特徴量 |
|--------|------|--------|
| Model A | 複勝予測（全特徴量） | 91 (MARKET + VALUE) |
| Model B | 複勝予測（市場情報なし） | 62 (VALUE only) |
| Model W | 単勝予測（全特徴量） | 91 (MARKET + VALUE) |
| Model WV | 単勝予測（市場情報なし） | 62 (VALUE only) |

### Value Bet 戦略

- **VB gap** = Model A確率 − Model B確率
- gap が大きい馬 = 市場が過小評価している馬
- VB gap ≥ 5 で Place ROI 137.3%（v5.3バックテスト）

### 実験・訓練

```powershell
cd keiba-v2
python -m ml.experiment    # モデル訓練 + バックテスト
python -m ml.predict --date 2026-02-22  # 当日予測
```

---

## 📁 ディレクトリ構成

```
keiba-cicd-core/
├── keiba-v2/              ← 現行コード（v4アーキテクチャ）
│   ├── core/              設定・パーサー・モデル定義
│   │   ├── jravan/        JRA-VANバイナリパーサー
│   │   ├── models/        データクラス
│   │   └── store/         データストア
│   ├── builders/          マスタJSON構築
│   ├── ml/                機械学習
│   │   └── features/      特徴量エンジニアリング（10モジュール）
│   ├── analysis/          レーティング・分類・パターン分析
│   ├── keibabook/         競馬ブック連携
│   └── web/               Next.js WebViewer
│       └── src/app/       App Router ページ・API
├── keiba-v1/              レガシー（venvのみ使用）
├── ai-team/               AIチーム設定・ナレッジ
└── docs/                  ロードマップ等
```

### データディレクトリ

```
C:\KEIBA-CICD\data3/       ← v4データストア
├── races/                 20,415レースJSON (2020-2026)
├── masters/               馬211,681 + 調教師351 + 騎手329
├── keibabook/             競馬ブック拡張データ (10,665件)
├── ml/                    モデル・予測・実験結果
│   └── versions/          過去モデルアーカイブ (v5.3〜v3.5)
├── indexes/               各種インデックス
└── analysis/              分析結果キャッシュ

C:\TFJV/                   ← JRA-VANデータ
```

---

## 🔧 環境変数

`keiba-v2/web/.env.local`:

```ini
DATA_ROOT=C:/KEIBA-CICD/data3
JV_DATA_ROOT_DIR=C:/TFJV
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=mykeibadb
```

Python側は `keiba-v2/core/config.py` でデフォルトパスを管理（通常は環境変数不要）。

---

## 📝 バージョン履歴

| バージョン | Session | 内容 |
|-----------|---------|------|
| **v5.8** | 35 | コメントNLP特徴量 + ML v5.3 |
| v5.7 | 34 | モデルバージョニング + Predictions全面改修 + 買い目プリセット |
| v5.6 | 33 | 降格ローテ + レースレベル + ML v5.2b |
| v5.5 | 30-32 | ラップ分析v2(33ラップ+7分類) + ML v5.1-5.2 |
| v5.4 | 28-29 | 馬詳細3層リビルド + enrichment修正 |
| v5.3 | 27 | ナビ再構成 + Value Betブランディング |
| v5.1-5.2 | 25-26 | 推奨買い目 + 危険な人気馬 + DB補完 |
| v5.0 | 24 | Win/Placeデュアルモデル + EV計算 |
| v4.8-4.10 | 21-23 | 調教分析 + VBバックテスト + CK_DATA特徴量 |
| v4.6-4.7 | 15-20 | mykeibadb + ML v3-4 + ketto_numバグ修正 |
| v3.1-4.5 | 1-13 | JRA-VAN移行 + data3基盤整備 |

---

**プロジェクトオーナー**: ふくだ君
**AI相談役**: カカシ
**最終更新**: 2026-02-21

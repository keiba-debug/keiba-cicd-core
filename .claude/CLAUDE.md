# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

**KeibaCICD** — 競馬予想支援システム。毎週の競馬予想でプラス収支を実現し、推理エンターテインメントとして競馬を楽しむ。システムを作ることが目的ではなく、**実際に馬券を当てること**が目的。

### 現在の優先事項

1. **確率推定モデルの構築** — LightGBMで各馬の勝率を確率出力 + キャリブレーション
2. **EV計算の実装** — AI予測確率×オッズ > 1.0 の馬券を全て抽出
3. **購入ログの自動記録** — タイムスタンプ付き改ざん防止記録（税務要件）

### 参照ドキュメント

- **チームガイドライン**: `ai-team/knowledge/CLAUDE.md`
- **データ仕様書**: `ai-team/knowledge/DATA_SPECIFICATION.md`
- **ナレッジベース索引**: `docs/knowledge/README.md`
- **考察マスター**: `docs/knowledge/consideration_master.md`
- **ML学習ロードマップ**: `docs/knowledge/insights/learning/ml_learning_roadmap.md`
- **ドメインモデル**: `keiba-v2/docs/DOMAIN_MODEL.md`
- **JRA-VANデータ仕様**: `keiba-v2/docs/DATA_SPEC.md`

---

## アーキテクチャ

### データフロー全体像

```
JRA-VAN Binary (C:/TFJV)          keibabook.com (スクレイピング)
  SE/SR/UM/CK_DATA                     │
       │                               │
       ▼                               ▼
  keiba-v2/core/jravan/         keiba-v2/keibabook/
  (バイナリパーサー)              (batch_scraper.py)
       │                               │
       ▼                               ▼
  keiba-v2/builders/  ──────►  JSON (C:/KEIBA-CICD/data3)
  (race/horse/trainer)          races/, masters/, indexes/
                                       │
                    ┌──────────────────┤
                    ▼                  ▼
             keiba-v2/ml/        MySQL (mykeibadb)
             (LightGBM)          odds tables
                    │                  │
                    ▼                  ▼
              predictions     keiba-v2/web/ (Next.js)
                              API Routes → React UI
```

### サブプロジェクト構成

| ディレクトリ | 技術 | 役割 |
|---|---|---|
| `keiba-v2/web/` | Next.js 16 + React 19 + Tailwind 4 + shadcn/ui | メインWeb UI |
| `keiba-v2/ml/` | Python + LightGBM + scikit-learn | ML予測パイプライン |
| `keiba-v2/core/` | Python | 設定・DB接続・JRA-VANパーサー・データモデル |
| `keiba-v2/builders/` | Python | race/horse/trainerマスタ構築 |
| `keiba-v2/keibabook/` | Python | 競馬ブックスクレイピング |
| `keiba-v2/analysis/` | Python | レース種別・レーティング・調教師パターン分析 |
| `keiba-v1/` | Python/C#/Next.js | レガシー（参照用、一部のツールは現役） |

### Web⇔Python統合方式

- Next.js API Routes が MySQL (`mysql2`) とファイルシステム (`data3/`) に直接アクセス
- 重い計算は Python スクリプトをシェル実行
- ML予測結果は JSON + MySQL に書き出し、Web側が読む

---

## 開発コマンド

### Web (keiba-v2/web/)

```bash
cd keiba-cicd-core/keiba-v2/web

npm run dev           # 開発サーバー (webpack)
npm run dev:turbo     # 開発サーバー (Turbo、高速)
npm run build         # プロダクションビルド (standalone for IIS)
npm run start         # プロダクションサーバー起動
npm run lint          # ESLint
```

### Python (keiba-v2/)

```bash
cd keiba-cicd-core/keiba-v2

# 依存関係 (pyproject.toml: Python >=3.10)
pip install -e .

# ML実験
python -m ml.experiment_v3
python -m ml.predict

# テスト
python test_parsers.py

# Linter: ruff (line-length=100)
ruff check .
```

### データ取得パイプライン (PowerShell)

```powershell
cd keiba-cicd-core/keiba-v1/tools

# 日次バッチ（スクレイピング→統合→Markdown→整理→インデックス）
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Date 2026/02/15

# 日付範囲指定
powershell -ExecutionPolicy Bypass -File .\run_daily.ps1 -Date 2026/02/15 -EndDate 2026/02/16 -Delay 0.5 -MaxWorkers 8
```

### C# / .NET (keiba-v1/KeibaCICD.JraVanSync/)

```bash
cd keiba-cicd-core/keiba-v1/KeibaCICD.JraVanSync

dotnet build JraVanSync.sln
dotnet test JraVanSync.sln
dotnet run --project src/JraVanSync.Console/JraVanSync.Console.csproj
```

---

## 環境変数

```ini
# データディレクトリ
KEIBA_DATA_ROOT=C:/KEIBA-CICD/data3
DATA_ROOT=C:/KEIBA-CICD/data2
JV_DATA_ROOT_DIR=C:/TFJV

# MySQL
MYKEIBADB_HOST=localhost
MYKEIBADB_PORT=3306
MYKEIBADB_USER=root
MYKEIBADB_PASS=test123!
MYKEIBADB_DB=mykeibadb

# keibabook認証（ブラウザCookieから取得）
KEIBABOOK_SESSION=<cookie>
KEIBABOOK_TK=<tk>
KEIBABOOK_XSRF_TOKEN=<xsrf>
```

設定は `keiba-v2/web/.env.local` と `keiba-v2/.env` に配置。
Python側の設定管理: `keiba-v2/core/config.py`

---

## ID体系

| ID種別 | 形式 | 例 |
|---|---|---|
| JRA-VAN 馬ID | 10桁数値 | `2019103487` (ドウデュース) |
| JRA-VAN レースID | 16桁 `YYYYMMDDJJKKNNRR` | `2026012406010208` |

- ID変換は必ず `common.jravan` ライブラリ経由で行う
- 既存スクリプト（`parse_ck_data.py` 等）は直接インポートしない

---

## コーディングルール

### Python
- ruff: `line-length = 100`
- JRA-VANデータは `common.jravan` 統一インターフェースを使用
- ML特徴量は `keiba-v2/ml/features/` に個別モジュールとして追加
- 新しいJRA-VANデータタイプを追加する場合は `docs/jravan/data-types/` にドキュメント追加

### Web (TypeScript/React)
- shadcn/ui コンポーネント: `src/components/ui/` (new-yorkスタイル)
- Import alias: `@/components`, `@/ui`, `@/lib`
- `cn()` ユーティリティ (`clsx` + `tailwind-merge`) でクラス結合
- サーバーコンポーネント優先。インタラクティブ部分のみ `'use client'`

### 競馬AI戦略の核心原則

- **EV > 1.0を全て購入**: 回収率最大化ではなく収支最大化
- **確率論的競馬観**: 「勝つ馬」ではなく「勝率23%の馬」と予測
- **Themis原則**: 購入決定の入力は「確率・オッズ・バンクロール残高」の3つだけ
- **過学習回避**: 小サンプル×多条件分け = 疑似科学。Walk-Forward Validationで検証
- **評価はキャリブレーション**: 的中率ではなくブライアスコアで測る

---

## あなたの役割

**名前**: カカシ（はたけカカシ）
**役割**: AI相談役・技術リーダー
**立場**: ふくだ君のよき相談役、エキスパートチームの指導者

**性格**: 冷静、経験豊富、的確なアドバイス

**チーム詳細**: `ai-team/experts/TEAM_ROSTER.md`

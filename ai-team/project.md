# KeibaCICD プロジェクトガイドライン

## プロジェクト概要

KeibaCICDは、JRA-VANデータとML予測を活用した競馬データ分析・予想システムです。
期待値ベースの合理的な馬券購入を通じて、持続的なプラス収支の実現を目指しています。

### ビジョン
毎週の競馬予想でプラス収支を実現し、推理エンターテインメントとして競馬を楽しむ

### 現在のフェーズ
- **開始時期**: 2025年6月
- **現在バージョン**: v4.5（2026年2月）
- **開発段階**: ML予測運用中、Value Bet戦略で実収支プラス達成

### 収支実績（2026-02-08時点）
- **月間**: +57,310（180.9% ROI）
- **通算**: +56,010（166.8%）

---

## 技術スタック

### フロントエンド（WebViewer）
- **フレームワーク**: Next.js 14 (App Router)
- **UI**: React 18 + TypeScript
- **スタイリング**: Tailwind CSS
- **データ読み込み**: Server Components + fs直接読み込み（SWR不使用）
- **検索系**: API Routes (`/api/races/search` 等)

### バックエンド（Pythonバッチ処理）
- **言語**: Python 3.11+ (venv: `keiba-v2/.venv`)
- **ML**: LightGBM（デュアルモデル: Model A精度 / Model B Value）
- **スクレイピング**: Requests + BeautifulSoup4（競馬ブック）
- **データ処理**: Pandas, NumPy
- **可視化**: Matplotlib

### データストア
- **メインデータ**: JSONファイル（`data3/`配下）
- **インデックス**: JSONベースのインデックスファイル
- **JRA-VANデータ**: バイナリファイル直接パース（`C:/TFJV`）
- **DB不使用**: PostgreSQL/MongoDB等は使わない設計方針

### インフラ
- **ローカル実行**: Windows 10 Pro
- **バージョン管理**: Git
- **コンテナ/CI**: 不使用（ローカル完結）

### 外部連携
- **JRA-VAN Data Lab**: TARGET経由バイナリデータ（SE/SR/UM/KS等）
- **競馬ブック**: Webスクレイピング（nittei/syutuba/cyokyo/seiseki等）

---

## プロジェクト構造

```
_keiba/
├── keiba-cicd-core/
│   ├── keiba-v2/                    # v4メインコードベース
│   │   ├── web/                     # Next.js WebViewer
│   │   │   ├── app/                 # App Router pages
│   │   │   │   ├── races/           # レース一覧・詳細
│   │   │   │   ├── search/          # 検索ページ
│   │   │   │   ├── admin/           # 管理画面
│   │   │   │   └── api/             # API Routes
│   │   │   ├── components/          # UIコンポーネント
│   │   │   └── lib/                 # データ読み込み・ユーティリティ
│   │   ├── core/                    # Python基盤
│   │   │   ├── config.py            # パス設定
│   │   │   ├── constants.py         # 定数
│   │   │   └── jravan/              # JRA-VANパーサー群
│   │   │       ├── race_id.py       # 16桁race_id変換
│   │   │       ├── se_parser.py     # 成績データ
│   │   │       ├── sr_parser.py     # レース詳細
│   │   │       └── um_parser.py     # 馬登録データ
│   │   ├── core/models/             # データモデル
│   │   │   ├── race.py, horse.py    # v4モデル
│   │   │   └── keibabook_ext.py     # KB拡張モデル
│   │   ├── builders/                # マスタデータ構築
│   │   │   ├── build_race_master.py
│   │   │   ├── build_horse_master.py
│   │   │   ├── build_trainer_master.py
│   │   │   ├── build_jockey_master.py
│   │   │   ├── build_horse_history.py
│   │   │   └── build_*_index.py     # 各種インデックス
│   │   ├── analysis/                # 分析スクリプト
│   │   │   ├── rating_standards.py
│   │   │   ├── race_type_standards.py
│   │   │   └── trainer_patterns.py
│   │   ├── ml/                      # ML予測
│   │   │   ├── experiment_v3.py     # 実験・学習スクリプト
│   │   │   ├── predict.py           # 予測実行
│   │   │   └── features/            # 特徴量モジュール群
│   │   │       ├── base_features.py
│   │   │       ├── past_features.py
│   │   │       ├── trainer_features.py
│   │   │       ├── jockey_features.py
│   │   │       ├── running_style_features.py
│   │   │       ├── rotation_features.py
│   │   │       ├── pace_features.py
│   │   │       └── training_features.py
│   │   └── keibabook/               # 競馬ブック連携
│   │       ├── scraper.py           # 単体スクレイパー
│   │       ├── batch_scraper.py     # バッチ実行
│   │       ├── ext_builder.py       # KB拡張データ構築
│   │       ├── cyokyo_parser.py     # 調教HTMLパーサー
│   │       ├── cyokyo_enricher.py   # 調教データ補強
│   │       └── parsers/             # 各ページパーサー
│   │           ├── nittei, syutuba, danwa, syoin
│   │           ├── paddok, seiseki, babakeikou
│   │           └── ...
│   ├── KeibaCICD.AI/tools/          # レガシー（bankroll_manager等、API経由）
│   ├── ai-team/                     # プロジェクトドキュメント
│   └── docs/                        # 技術ドキュメント
│       └── ml-experiments/          # ML実験ログ
└── data3/                           # v4データルート (553 MB)
    ├── races/                       # 19,404レースJSON (2020-2026)
    ├── masters/                     # 馬211,681 + 調教師351 + 騎手329
    ├── keibabook/                   # 10,665 kb_ext JSON
    ├── ml/                          # モデル + キャッシュ + 予測結果
    ├── indexes/                     # race_date, horse_name, trainer_kb
    ├── analysis/                    # rating_standards, race_type_standards等
    └── userdata/                    # bankroll/purchases/predictions
```

---

## ID体系

| 対象 | 形式 | 例 | ソース |
|------|------|-----|--------|
| race_id | 16桁 `YYYYMMDDJJKKNNRR` | 2026012406010208 | JRA-VAN |
| horse_id | 10桁 ketto_num | 2019105283 | JRA-VAN |
| trainer_id | 5桁コード | 01155 | JRA-VAN |
| jockey_id | 5桁コード | 01126 | JRA-VAN |

**注意**: keibabook場所コード != JRA-VAN場所コード。変換はvenue_name（日本語）経由で行う。

---

## 主要機能（実装済み）

### 1. データ収集・構築パイプライン
- **JRA-VANバイナリパース**: SE（成績）/ SR（レース詳細）/ UM（馬登録）/ KS（騎手）
- **マスタデータ構築**: レース・馬・調教師・騎手の統合JSON生成
- **競馬ブックスクレイピング**: 日程/出馬表/調教/成績/パドック/談話/馬場傾向
- **調教詳細パース**: 全セッション構造化 + kb_extへの埋め込み
- **race_info.json**: 開催情報（レース名・発走時刻）の補完データ

### 2. ML予測システム (v3.3)
- **デュアルモデル**: Model A（全特徴量・精度重視）+ Model B（市場系除外・Value重視）
- **特徴量**: 60個（基本/過去走/調教師/騎手/脚質/ローテ/ペース/調教）
- **Value Bet戦略**: odds_rank vs Model B rankの乖離でROI向上
- **成果**: Model B AUC 0.7823, VB gap>=5 ROI 139.0%

### 3. WebViewer
- **レース一覧**: 日付別レース表示（race_info.json補完対応）
- **レース詳細**: 出走表 + ML予測スコア + Value Bet表示
- **検索**: レース名・馬名検索
- **管理画面**: 基本情報構築 / 直前情報・結果情報構築 / ML予測実行

### 4. 分析機能
- **レーティング基準値**: 条件別（芝/ダート × クラス × 距離帯）の基準タイム
- **レースタイプ基準値**: 馬場 × ペース × 脚質の相関分析
- **調教師パターン**: 調教師別の好走パターン辞書

---

## アーキテクチャ方針

### 設計原則
1. **バッチ処理 → JSON → フロントエンド**: Backend API分離は不要
2. **Server Components優先**: メインページはfs直接読み込み、SWRは使わない
3. **検索系のみAPI Route**: クライアントからfetchが必要な機能のみ
4. **JRA-VAN直接パース**: ketto_num/trainer_cd等のネイティブIDで100%マッチ

### データフロー
```
【データ構築（随時）】
JRA-VAN バイナリ → Pythonパーサー → data3/races/ + masters/ JSON

【週次パイプライン（金曜夜）】
1. 基本情報構築: JRA-VAN → レース・馬マスタ更新
2. KBスクレイプ: 出馬表・調教データ取得 → kb_ext JSON
3. ML予測: 特徴量生成 → LightGBM予測 → predictions JSON

【レース当日（土日）】
WebViewer → data3/ JSON読み込み → 出走表 + 予測スコア表示
```

---

## 環境設定

### パス設定
| 変数 | パス | 用途 |
|------|------|------|
| `DATA3_ROOT` | `C:/KEIBA-CICD/data3` | v4データルート（唯一） |
| `JV_DATA_ROOT_DIR` | `C:/TFJV` | JRA-VANバイナリ |
| `v2Path` | `keiba-v2/` | Pythonコード実行パス |
| Python venv | `keiba-v2/.venv` | Python仮想環境 |

### 環境変数（.env）
```bash
KEIBABOOK_SESSION=xxx    # 競馬ブック認証セッション
KEIBABOOK_TK=xxx         # 認証トークン
KEIBABOOK_XSRF_TOKEN=xxx # XSRFトークン
```

---

## 開発ガイドライン

### コーディング規約
- **Python**: PEP 8準拠、型ヒント推奨
- **TypeScript**: strictモード、Server Components優先
- **データ型注意**: `last_3f`はfloat(42.7)、`horse_weight_diff`はint(-4) — TS側でstring期待時は`String()`ラッパー必須

### ファイル操作の注意
- **211K JSONファイルのフルパースは遅い**: regex抽出で10倍以上高速化
- **Windows環境**: `move`ではなく`mv`を使用
- **data2/は変更禁止**: 旧データ、参照のみ

---

## チーム構成

### 現在（v4.x）

| 役割 | 担当 | 内容 |
|------|------|------|
| **オーナー** | ふくだ君 | 方針決定・最終判断 |
| **技術リード** | カカシ | 設計・実装・相談 |

### 将来（v5.1〜 MCPエージェント化時）

| エージェント | 愛称 | 担当 |
|------------|------|------|
| Orchestrator | ベンゲル | 全体統括 |
| Data Tracker | キバ | データ収集・異常検知 |
| ML Predictor | アルテタ | ML予想 |
| Expected Value | エバちゃん | 期待値計算 |
| Betting Strategy | シカマル | 購入戦略 |
| Record Keeper | サイ | 実行記録 |
| Race Analyzer | ひなた | 結果分析 |
| Continuous Learner | ナルト | 改善学習 |

---

**最終更新**: 2026-02-12（カカシ）
**承認**: ふくだ君

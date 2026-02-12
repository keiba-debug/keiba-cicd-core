# KeibaCICD プロジェクトガイドライン

## プロジェクト概要

KeibaCICDは、エンジニアリング手法を活用した競馬データ分析システムです。
期待値ベースの合理的な競馬予測を通じて、持続的な価値創造を目指す発展途上のプロジェクトです。

### ビジョン
エンジニアリング手法を活用し、競馬を通じて人生を持続的に豊かにすることを目的とした、期待値ベースの合理的な競馬予測・分析システムの構築

### 現在のフェーズ
- **開始時期**: 2025年6月
- **現在状況**: 基盤構築フェーズ（Phase 1）
- **開発段階**: 初期実装段階

## 技術スタック

### バックエンド
- **言語**: Python 3.11+
- **フレームワーク**: FastAPI
- **スクレイピング**: Requests + BeautifulSoup4（高速版）/ Selenium（レガシー版）
- **非同期処理**: asyncio, aiohttp
- **タスクキュー**: Celery + Redis

### データストア
- **メインDB**: PostgreSQL 15+
- **ドキュメントDB**: MongoDB
- **検索エンジン**: Elasticsearch（日本語対応）
- **キャッシュ**: Redis
- **データレイク**: S3互換ストレージ

### フロントエンド（計画中）
- **フレームワーク**: Next.js 14
- **UI**: React 18 + TypeScript
- **状態管理**: Redux Toolkit
- **3D可視化**: Three.js
- **グラフ**: Chart.js / D3.js

### インフラストラクチャ
- **コンテナ**: Docker
- **オーケストレーション**: Kubernetes
- **CI/CD**: GitHub Actions
- **監視**: Prometheus + Grafana
- **ログ管理**: ELK Stack

### 外部連携
- **データソース**: 
  - 競馬ブック（スクレイピング）
  - JRA-VAN Data Lab（SDK連携予定）
- **API**: REST API + GraphQL（予定）
- **リアルタイム**: WebSocket

## プロジェクト構造

```
_keiba/
├── keiba-cicd-core/               # コアプロジェクト
│   ├── KeibaCICD.keibabook/      # 競馬ブックスクレイピング
│   │   ├── src/                   # ソースコード
│   │   │   ├── batch/            # バッチ処理
│   │   │   ├── scrapers/         # スクレイパー
│   │   │   ├── parsers/          # パーサー
│   │   │   └── integrator/       # データ統合
│   │   ├── scripts/              # 実行スクリプト
│   │   └── docs/                 # ドキュメント
│   ├── KeibaCICD.JraVanSync/     # JRA-VAN連携（開発中）
│   │   ├── src/                  # C#/.NETソース
│   │   └── docs/                 # ドキュメント
│   ├── docs/                      # プロジェクトドキュメント
│   │   ├── architecture/         # アーキテクチャ設計
│   │   ├── database/             # DB設計
│   │   ├── api/                  # API仕様
│   │   └── project/              # プロジェクト計画
│   └── tasks/                     # タスク管理
├── ai-context/                    # AIエージェント設定
│   ├── experts/                    # チームメンバー定義
│   └── project.md                # このファイル
└── JRA-VAN Data Lab. SDK/        # JRA-VAN SDK

```

## 主要機能（実装済み）

### 1. データ収集システム
- **競馬ブックスクレイピング**: 
  - 高速版（RequestsScraper）: 8.6秒/12レース
  - レガシー版（Selenium）: 60-90秒/12レース
- **並列処理**: 最大22並列
- **データタイプ**: 
  - nittei（日程）
  - seiseki（成績）
  - shutsuba（出馬表）
  - cyokyo（調教）

### 2. データ処理
- **バッチCLI**: 統合コマンドラインインターフェース
- **パーサー**: HTML→JSON変換
- **データ検証**: 基本的な整合性チェック

## 計画中の機能

### Phase 1: 基盤構築（2025年6-8月）
- ✅ スクレイピングシステム構築
- ⬜ データベース設計・構築
- ⬜ API基盤構築
- ⬜ CI/CD構築

### Phase 2: コア機能開発（2025年9-12月）
- ⬜ 期待値計算システム
- ⬜ 馬キャラクター分析
- ⬜ レース質分析
- ⬜ 機械学習モデル構築

### Phase 3: 高度機能開発（2026年1-3月）
- ⬜ 3D可視化（レースフロー表示）
- ⬜ JRA-VAN連携
- ⬜ リアルタイム分析

## 開発ガイドライン

### コーディング規約
- **Python**: PEP 8準拠
- **型ヒント**: 必須（Python 3.11+）
- **ドキュメント**: docstring必須
- **テスト**: pytest使用、カバレッジ80%以上目標

### Git運用
- **ブランチ戦略**: 
  - main: 本番環境
  - develop: 開発環境
  - feature/: 機能開発
- **コミット**: Conventional Commits形式

### 環境変数
```bash
# .env ファイル例
KEIBA_DATA_ROOT_DIR=/path/to/data  # データ保存先
LOG_LEVEL=INFO                     # ログレベル
KEIBABOOK_SESSION=xxx              # 認証セッション
KEIBABOOK_TK=xxx                   # 認証トークン
KEIBABOOK_XSRF_TOKEN=xxx          # XSRFトークン
```

## 品質基準

### データ品質
- **取得成功率**: 95%以上
- **データ整合性**: 必須フィールド100%
- **更新頻度**: 日次バッチ

### システム品質
- **API応答時間**: 95%ile < 200ms
- **稼働率**: 99.9%以上（目標）
- **同時接続**: 50ユーザー以上

### セキュリティ
- **認証**: JWT Bearer Token
- **暗号化**: TLS 1.3
- **データ保護**: 個人情報の適切な管理

## AIエージェントチーム

### 分析系
- **ANALYST**: 総合分析統括
- **STRATEGIST**: レース展開戦略
- **EVALUATOR**: 馬質評価
- **HANDICAPPER**: ハンディキャップ分析

### 実行系
- **SCRAPER**: データ収集
- **TRACKER**: リアルタイム追跡
- **EXECUTOR**: 実行管理

### 管理系
- **COMMANDER**: 全体統括
- **INVESTOR**: 投資判断
- **GUARDIAN**: リスク管理
- **LEARNER**: 継続学習

## 現在の課題

1. **データ基盤**:
   - データベース未構築
   - データ品質検証ルール未実装
   - ETLパイプライン未整備

2. **分析機能**:
   - 期待値計算ロジック未実装
   - 機械学習モデル未構築
   - 統計分析フレームワーク未整備

3. **運用基盤**:
   - 監視システム未構築
   - エラーハンドリング改善必要
   - ドキュメント整備継続必要

## 今後の優先事項

1. **短期（1ヶ月）**:
   - PostgreSQL/MongoDBセットアップ
   - 基本的なAPI実装
   - データ品質検証実装

2. **中期（3ヶ月）**:
   - 期待値計算システム構築
   - 基本的な予測モデル実装
   - Webインターフェース開発

3. **長期（6ヶ月）**:
   - JRA-VAN連携実装
   - 高度な分析機能実装
   - 本番環境構築・運用開始

## リソース

### ドキュメント
- [システムアーキテクチャ](../keiba-cicd-core/docs/architecture/system-overview.md)
- [データベース設計](../keiba-cicd-core/docs/database/database-design.md)
- [API設計](../keiba-cicd-core/docs/api/api-design.md)
- [プロジェクト計画](../keiba-cicd-core/docs/project/project-plan.md)

### 開発環境セットアップ
```bash
# リポジトリクローン
git clone [repository-url]

# Python環境セットアップ
cd keiba-cicd-core/KeibaCICD.keibabook
pip install -r src/requirements.txt

# 環境変数設定
cp .env.example .env
# .envファイルを編集

# 動作確認
python -m src.batch_cli --help
```

## 連絡事項

このプロジェクトは2025年6月に開始したばかりの発展途上のプロジェクトです。
チーム全体で協力しながら、段階的に機能を追加・改善していく予定です。

技術的な課題や改善提案は積極的に共有し、より良いシステムを構築していきましょう。
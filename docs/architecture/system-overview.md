# KeibaCICD システムアーキテクチャ概要

## 1. システム概要

### 1.1 プロダクトビジョン
KeibaCICDは、エンジニアリング手法を活用した競馬データ分析システムです。期待値ベースの合理的な予測により、感情的な予想からデータドリブンな分析への移行を支援し、持続可能な競馬の楽しみ方を提供します。

### 1.2 主要機能
- **期待値計算システム**: 全出走馬の勝率算出とオッズ比較
- **馬キャラクター分析**: 馬の個性と特性の可視化
- **レース質分析**: コース特性と展開予想の統合分析
- **3D可視化**: レースフローの直感的な表現
- **収支管理**: 長期的な投資管理とメンタルケア

## 2. システム全体構成

### 2.1 アーキテクチャ概要図

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Next.js App   │  │  3D Visualizer  │  │  Dashboard  │ │
│  │   (App Router)  │  │   (Three.js)    │  │   (D3.js)   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   FastAPI       │  │   C#/.NET API   │  │   Auth API  │ │
│  │  (Analysis)     │  │  (JRA-VAN)      │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Internal Network
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Data Processing Layer                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  Scraping       │  │   ML Pipeline   │  │  ETL Jobs   │ │
│  │  (Keibabook)    │  │   (Analysis)    │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Database Connections
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Storage Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   PostgreSQL    │  │    MongoDB      │  │    Redis    │ │
│  │ (Structured)    │  │  (Documents)    │  │   (Cache)   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ Elasticsearch   │  │   File Storage  │                  │
│  │   (Search)      │  │    (Assets)     │                  │
│  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 技術スタック詳細

#### Frontend
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **3D Graphics**: Three.js, React Three Fiber
- **Charts**: D3.js, Recharts
- **Animation**: Framer Motion
- **State Management**: Zustand
- **HTTP Client**: Axios

#### Backend APIs
- **Analysis API**: FastAPI (Python 3.11+)
- **JRA-VAN API**: ASP.NET Core (C# 12)
- **Authentication**: JWT + OAuth 2.0
- **API Documentation**: OpenAPI/Swagger

#### Data Processing
- **Scraping**: Python (既存keibabook)
- **ML/Analytics**: Python (scikit-learn, pandas, numpy)
- **NLP**: spaCy, transformers
- **ETL**: Apache Airflow (将来的)

#### Data Storage
- **Primary DB**: PostgreSQL 15+
- **Document Store**: MongoDB 7+
- **Cache**: Redis 7+
- **Search**: Elasticsearch 8+
- **File Storage**: MinIO (S3互換)

#### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Orchestration**: Kubernetes (将来的)
- **Monitoring**: Prometheus, Grafana
- **Logging**: ELK Stack

## 3. データフロー設計

### 3.1 データ取得フロー

```
External Sources → Scraping Layer → Raw Data Storage → Processing → Structured Storage
     │                  │               │                │              │
JRA-VAN API         Keibabook       MongoDB          FastAPI      PostgreSQL
競馬ブック           Scraper        (Raw JSON)       Analytics    (Structured)
```

### 3.2 分析処理フロー

```
Structured Data → ML Pipeline → Analysis Results → Cache → Frontend
      │              │              │             │         │
  PostgreSQL    Feature Eng.    Predictions    Redis    Next.js
  MongoDB       Model Training   Probabilities  Cache    Dashboard
```

### 3.3 リアルタイム更新フロー

```
External Updates → WebSocket → Cache Update → Frontend Notification
      │              │            │               │
   オッズ変更      FastAPI      Redis Update    Live Update
   出走変更        Server       Invalidation    (WebSocket)
```

## 4. セキュリティアーキテクチャ

### 4.1 認証・認可
- **認証方式**: JWT + Refresh Token
- **認可**: RBAC (Role-Based Access Control)
- **外部認証**: OAuth 2.0 (Google, GitHub)
- **API保護**: Rate Limiting, CORS

### 4.2 データ保護
- **暗号化**: TLS 1.3 (通信), AES-256 (保存)
- **機密情報**: 環境変数、Secrets管理
- **アクセス制御**: Database-level permissions
- **監査ログ**: 全API呼び出しの記録

### 4.3 インフラセキュリティ
- **ネットワーク**: VPC, Security Groups
- **コンテナ**: 最小権限の原則
- **脆弱性管理**: 定期的なセキュリティスキャン

## 5. パフォーマンス要件

### 5.1 レスポンス時間
- **API応答**: < 200ms (95%ile)
- **ページロード**: < 2秒 (初回)
- **3D描画**: 60fps維持
- **データ更新**: < 5秒 (リアルタイム)

### 5.2 スループット
- **同時ユーザー**: 1,000人
- **API呼び出し**: 10,000 req/min
- **データ処理**: 全レース分析 < 30分

### 5.3 可用性
- **稼働率**: 99.9%
- **RTO**: < 4時間
- **RPO**: < 1時間

## 6. 拡張性設計

### 6.1 水平スケーリング
- **API**: ロードバランサー + 複数インスタンス
- **Database**: Read Replica, Sharding
- **Cache**: Redis Cluster
- **Storage**: 分散ファイルシステム

### 6.2 垂直スケーリング
- **CPU**: ML処理の並列化
- **Memory**: 大容量データ処理
- **Storage**: SSD, NVMe対応

## 7. 既存システム統合

### 7.1 Keibabook統合
- **保持**: 既存のsrc/keibabook構造
- **拡張**: 新しい分析機能の追加
- **データ**: 既存JSONファイルの活用
- **ID体系**: race_id形式の維持

### 7.2 JRA-VAN統合
- **新規**: C#/.NET APIの構築
- **データ**: リアルタイムデータ取得
- **同期**: 既存データとの整合性確保

## 8. 運用・保守

### 8.1 監視
- **システム**: CPU, Memory, Disk使用率
- **アプリケーション**: エラー率, レスポンス時間
- **ビジネス**: 予測精度, ユーザー行動

### 8.2 ログ管理
- **構造化ログ**: JSON形式
- **集約**: ELK Stack
- **保持期間**: 90日間

### 8.3 バックアップ
- **データベース**: 日次フルバックアップ
- **ファイル**: 増分バックアップ
- **復旧テスト**: 月次実施

## 9. 開発・デプロイメント

### 9.1 開発環境
- **ローカル**: Docker Compose
- **CI/CD**: GitHub Actions
- **テスト**: 自動テスト + 手動テスト

### 9.2 デプロイメント戦略
- **Blue-Green**: ゼロダウンタイム
- **カナリア**: 段階的リリース
- **ロールバック**: 即座に前バージョンに復旧

## 10. 今後の拡張計画

### 10.1 Phase 1 (MVP)
- 基本的な期待値計算
- 馬キャラクター分析
- シンプルなダッシュボード

### 10.2 Phase 2 (機能拡張)
- 3D可視化
- レース質分析
- リアルタイム更新

### 10.3 Phase 3 (高度化)
- 機械学習モデルの高度化
- モバイルアプリ
- ソーシャル機能 
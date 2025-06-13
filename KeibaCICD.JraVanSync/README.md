# JraVanSync - JRA-VAN Data Lab. to SQL Server Data Synchronization System

[![.NET](https://img.shields.io/badge/.NET-8.0-blue.svg)](https://dotnet.microsoft.com/download/dotnet/8.0)
[![C#](https://img.shields.io/badge/C%23-12.0-blue.svg)](https://docs.microsoft.com/en-us/dotnet/csharp/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

JRA-VAN Data Lab.のデータをSQL Serverデータベースに同期する.NET 8.0 Web API + コンソールアプリケーション

## 概要

**JraVanSync**は、JRA-VAN Data Lab. SDKを使用して競馬関連データを取得し、SQL Serverデータベースに効率的に同期するシステムです。RESTful APIでの制御とコマンドライン実行の両方をサポートしています。

### 主な機能

- 🔄 **自動データ同期**: JV-Link SDKによる競馬データの自動取得・同期
- 🌐 **RESTful API**: Web API経由での同期制御とモニタリング
- 💻 **コンソールアプリ**: コマンドライン実行での直接制御
- 📊 **リアルタイム監視**: 同期進捗のリアルタイム追跡
- 🏗️ **Clean Architecture**: 保守性と拡張性を重視した設計
- 🐳 **Docker対応**: コンテナ化による簡単デプロイ
- 🔍 **ヘルスチェック**: システム状態の監視機能

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                      │
├─────────────────────┬─────────────────────┬─────────────────┤
│    Web API          │   Console App       │   Swagger UI    │
│  (REST Endpoints)   │  (CLI Commands)     │  (API Docs)     │
└─────────────────────┴─────────────────────┴─────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer                         │
├─────────────────────┬─────────────────────┬─────────────────┤
│  Sync Services      │  Job Management     │   DTOs/Models   │
│  (Business Logic)   │  (Background Jobs)  │  (Data Transfer)│
└─────────────────────┴─────────────────────┴─────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                            │
├─────────────────────┬─────────────────────┬─────────────────┤
│    Entities         │   Domain Services   │   Repositories  │
│  (Core Models)      │  (Domain Rules)     │  (Interfaces)   │
└─────────────────────┴─────────────────────┴─────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                        │
├─────────────────────┬─────────────────────┬─────────────────┤
│   JV-Link SDK       │   SQL Server        │   External APIs │
│  (Data Source)      │  (Database)         │  (Monitoring)   │
└─────────────────────┴─────────────────────┴─────────────────┘
```

## 技術スタック

- **Runtime**: .NET 8.0
- **Language**: C# 12.0
- **Framework**: ASP.NET Core 8.0
- **Database**: SQL Server 2019+
- **ORM**: Entity Framework Core 8.0
- **Architecture**: Clean Architecture + DDD
- **Containerization**: Docker
- **Documentation**: Swagger/OpenAPI
- **Logging**: Serilog
- **Testing**: xUnit, FluentAssertions, Moq

## プロジェクト構造

```
KeibaCICD.JraVanSync/
├── src/
│   ├── JraVanSync.Domain/              # ドメインモデル・エンティティ
│   ├── JraVanSync.Application/         # アプリケーションロジック
│   ├── JraVanSync.Infrastructure/      # JV-Link連携・DB実装
│   ├── JraVanSync.WebApi/              # ASP.NET Core Web API
│   ├── JraVanSync.Console/             # コンソールクライアント
│   └── JraVanSync.Shared/              # 共通定義・DTO
├── tests/
│   ├── JraVanSync.Domain.Tests/
│   ├── JraVanSync.Application.Tests/
│   ├── JraVanSync.Infrastructure.Tests/
│   └── JraVanSync.WebApi.Tests/
├── docs/                               # ドキュメント
├── docker-compose.yml                  # Docker Compose設定
├── Dockerfile                          # Dockerイメージ定義
└── README.md
```

## セットアップ

### 前提条件

- .NET 8.0 SDK
- SQL Server 2019+ または SQL Server Express
- JRA-VAN Data Lab. SDK Ver4.9.0.2
- Visual Studio 2022 または VS Code (推奨)

### インストール

1. **リポジトリのクローン**
```bash
git clone https://github.com/your-repo/KeibaCICD.JraVanSync.git
cd KeibaCICD.JraVanSync
```

2. **依存関係の復元**
```bash
dotnet restore
```

3. **設定ファイルの編集**
```bash
# appsettings.jsonの編集
cp src/JraVanSync.WebApi/appsettings.json src/JraVanSync.WebApi/appsettings.Development.json
# 接続文字列とJV-Link設定を環境に合わせて調整
```

4. **データベースの作成・マイグレーション**
```bash
dotnet ef database update --project src/JraVanSync.Infrastructure --startup-project src/JraVanSync.WebApi
```

5. **ビルド・実行**
```bash
# Web APIの起動
dotnet run --project src/JraVanSync.WebApi

# コンソールアプリの実行
dotnet run --project src/JraVanSync.Console -- sync --data-types RA SE
```

## 使用方法

### Web API

Web APIは `http://localhost:5000` で起動します。Swagger UIは `http://localhost:5000/swagger` で確認できます。

#### 主要エンドポイント

```http
# 同期ジョブの開始
POST /api/sync/jobs
Content-Type: application/json
{
  "dataTypes": ["RA", "SE"],
  "dataTypeOptions": {
    "RA": {
      "includeSetupData": true,
      "includeNormalData": true,
      "fromTime": "2024-01-01T00:00:00"
    }
  }
}

# ジョブ状態確認
GET /api/sync/jobs/{jobId}

# 実行中ジョブ一覧
GET /api/sync/jobs

# ヘルスチェック
GET /api/health
```

### コンソールアプリケーション

```bash
# 基本的な同期実行
jravansync sync --data-types RA SE UM

# 特定日付からの同期
jravansync sync --data-types RA --from-date 2024-01-01

# 設定ファイルを指定して実行
jravansync sync --config custom-settings.json

# ジョブ状態確認
jravansync status --job-id 123e4567-e89b-12d3-a456-426614174000

# ヘルプ表示
jravansync --help
```

## Docker を使用した実行

```bash
# Docker Compose での起動
docker-compose up -d

# ログ確認
docker-compose logs -f api

# コンテナ内でのコンソール実行
docker-compose run --rm console jravansync sync --data-types RA SE
```

## 対応データ種別

| コード | 説明 | セットアップ | 通常 | リアルタイム |
|--------|------|:----------:|:----:|:----------:|
| RA | レース詳細 | ✓ | ✓ | - |
| SE | 馬毎レース情報 | ✓ | ✓ | ✓ |
| UM | 馬マスタ | ✓ | ✓ | - |
| KS | 騎手マスタ | ✓ | ✓ | - |
| CH | 調教師マスタ | ✓ | ✓ | - |
| O1-O6 | オッズ情報 | ✓ | ✓ | ✓ |

## 監視・ログ

### ログ出力

- **コンソール**: 構造化ログ (JSON形式)
- **ファイル**: `logs/jravansync-{Date}.json`
- **Seq**: 構造化ログ分析プラットフォーム (オプション)

### ヘルスチェック

- **Database**: SQL Server接続確認
- **JV-Link**: JV-Link SDK接続確認
- **Background Services**: バックグラウンドサービス状態確認

## 開発

### 開発環境のセットアップ

```bash
# 開発用データベースの起動 (Docker)
docker run -e "ACCEPT_EULA=Y" -e "SA_PASSWORD=YourStrong@Passw0rd" \
  -p 1433:1433 --name sqlserver --hostname sqlserver \
  -d mcr.microsoft.com/mssql/server:2019-latest

# テスト実行
dotnet test

# カバレッジレポート生成
dotnet test --collect:"XPlat Code Coverage"
```

### 貢献方法

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add some amazing feature'`)
4. ブランチをプッシュ (`git push origin feature/amazing-feature`)
5. Pull Requestを作成

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

## サポート

- **Issues**: [GitHub Issues](https://github.com/your-repo/KeibaCICD.JraVanSync/issues)
- **Documentation**: [Wiki](https://github.com/your-repo/KeibaCICD.JraVanSync/wiki)
- **Email**: support@example.com

---

© 2025 JraVanSync Team. All rights reserved.
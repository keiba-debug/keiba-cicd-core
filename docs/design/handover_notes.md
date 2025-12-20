# 引継ぎ資料: C# .NET 10 移行プロジェクト

## 📋 ドキュメント情報

| 項目 | 内容 |
|------|------|
| **作成日** | 2025年12月13日 |
| **作成者** | AI Assistant |
| **目的** | 作業引継ぎ・再開時の情報共有 |

---

## 1. プロジェクト概要

### 1.1 目的
Python製の競馬ブックスクレイピングシステム（KeibaCICD.keibabook）を **C# .NET 10** に移行する。

### 1.2 移行理由
- JRA-VANデータ（SQL Server）との統合
- 将来的なUI実装（Next.js または Blazor）への対応
- 機械学習推論（ONNX Runtime）の統合
- 定期実行（Hangfire）の導入
- 長期サポート（LTS: 2028年11月まで）

---

## 2. 現在の進捗状況

### 2.1 進捗サマリー

| Phase | 内容 | 状況 | 進捗 |
|-------|------|------|------|
| Phase 1 | 設計 | ✅ 完了 | 100% |
| Phase 2 | プロジェクト基盤 | ⏳ 未着手 | 0% |
| Phase 3 | Scraper/Parser実装 | ⏳ 未着手 | 0% |
| Phase 4 | サービス層・CLI | ⏳ 未着手 | 0% |
| Phase 5 | テスト・並行運用 | ⏳ 未着手 | 0% |

**全体進捗: 30%**（設計完了）

### 2.2 Phase 1（設計）完了成果物

| ファイル | 内容 | 重要度 |
|---------|------|--------|
| `docs/design/csharp_migration_detailed_design.md` | 詳細設計書（メイン） | ⭐⭐⭐ |
| `docs/design/database_integration_design.md` | DB統合設計書 | ⭐⭐⭐ |
| `docs/design/implementation_roadmap.md` | 実装ロードマップ | ⭐⭐⭐ |
| `docs/design/integration_service_design.md` | IntegrationService詳細設計 | ⭐⭐⭐ |
| `docs/design/markdown_generator_design.md` | MarkdownGenerator詳細設計 | ⭐⭐⭐ |
| `docs/design/parser_output_schemas.md` | 7パーサー出力スキーマ | ⭐⭐⭐ |
| `docs/design/review_notes.md` | レビューノート | ⭐⭐ |
| `docs/design/dotnet10_migration_guide.md` | .NET 10移行ガイド | ⭐⭐⭐ |

---

## 3. 次のアクション（Phase 2開始）

### 3.1 .NET 10 SDK インストール確認

```powershell
# バージョン確認
dotnet --version
# 期待値: 10.0.xxx

# SDKインストール（未インストールの場合）
# https://dotnet.microsoft.com/download/dotnet/10.0 からダウンロード
```

### 3.2 ソリューション作成手順

```powershell
# 作業ディレクトリ移動
cd c:\source\git-h.fukuda1207\_keiba\keiba-cicd-core

# ソリューション作成
dotnet new sln -n KeibaCICD.Scraper

# プロジェクト作成（.NET 10指定）
dotnet new classlib -n KeibaCICD.Scraper.Domain -o src/KeibaCICD.Scraper.Domain -f net10.0
dotnet new classlib -n KeibaCICD.Scraper.Application -o src/KeibaCICD.Scraper.Application -f net10.0
dotnet new classlib -n KeibaCICD.Scraper.Infrastructure -o src/KeibaCICD.Scraper.Infrastructure -f net10.0
dotnet new console -n KeibaCICD.Scraper.CLI -o src/KeibaCICD.Scraper.CLI -f net10.0
dotnet new webapi -n KeibaCICD.Scraper.API -o src/KeibaCICD.Scraper.API -f net10.0
dotnet new classlib -n KeibaCICD.Scraper.Jobs -o src/KeibaCICD.Scraper.Jobs -f net10.0

# テストプロジェクト
dotnet new xunit -n KeibaCICD.Scraper.Domain.Tests -o tests/KeibaCICD.Scraper.Domain.Tests -f net10.0
dotnet new xunit -n KeibaCICD.Scraper.Application.Tests -o tests/KeibaCICD.Scraper.Application.Tests -f net10.0
dotnet new xunit -n KeibaCICD.Scraper.Infrastructure.Tests -o tests/KeibaCICD.Scraper.Infrastructure.Tests -f net10.0

# ソリューションに追加
dotnet sln add src/KeibaCICD.Scraper.Domain
dotnet sln add src/KeibaCICD.Scraper.Application
dotnet sln add src/KeibaCICD.Scraper.Infrastructure
dotnet sln add src/KeibaCICD.Scraper.CLI
dotnet sln add src/KeibaCICD.Scraper.API
dotnet sln add src/KeibaCICD.Scraper.Jobs
dotnet sln add tests/KeibaCICD.Scraper.Domain.Tests
dotnet sln add tests/KeibaCICD.Scraper.Application.Tests
dotnet sln add tests/KeibaCICD.Scraper.Infrastructure.Tests

# 参照追加
dotnet add src/KeibaCICD.Scraper.Application reference src/KeibaCICD.Scraper.Domain
dotnet add src/KeibaCICD.Scraper.Infrastructure reference src/KeibaCICD.Scraper.Domain
dotnet add src/KeibaCICD.Scraper.Infrastructure reference src/KeibaCICD.Scraper.Application
dotnet add src/KeibaCICD.Scraper.CLI reference src/KeibaCICD.Scraper.Application
dotnet add src/KeibaCICD.Scraper.CLI reference src/KeibaCICD.Scraper.Infrastructure
```

### 3.3 NuGetパッケージ追加

```powershell
# Domain層
# （依存なし）

# Application層
dotnet add src/KeibaCICD.Scraper.Application package Microsoft.Extensions.Logging.Abstractions

# Infrastructure層
dotnet add src/KeibaCICD.Scraper.Infrastructure package HtmlAgilityPack --version 1.12.4
dotnet add src/KeibaCICD.Scraper.Infrastructure package Serilog.AspNetCore --version 8.0.0
dotnet add src/KeibaCICD.Scraper.Infrastructure package Microsoft.EntityFrameworkCore.SqlServer --version 10.0.0

# CLI層
dotnet add src/KeibaCICD.Scraper.CLI package System.CommandLine --version 2.0.0
dotnet add src/KeibaCICD.Scraper.CLI package Spectre.Console --version 0.50.0

# API層
dotnet add src/KeibaCICD.Scraper.API package Serilog.AspNetCore --version 8.0.0

# Jobs層（Hangfireは後で追加、まずはIHostedServiceで実装）
```

### 3.4 Domain層の優先実装クラス

1. **RaceId.cs** - レースID値オブジェクト
2. **DataType.cs** - データタイプ列挙型
3. **各パーサー出力モデル** - `parser_output_schemas.md` 参照

---

## 4. 技術スタック

### 4.1 確定事項

| 項目 | 技術 | バージョン | 備考 |
|------|------|-----------|------|
| フレームワーク | **.NET 10 LTS** | 10.0.x | サポート: 2028年11月まで |
| 言語 | **C# 14** | - | .NET 10標準 |
| HTMLパース | HtmlAgilityPack | 1.12.4 | .NET Standard 2.0経由 |
| CLI | System.CommandLine | **2.0.0** | 安定版リリース！ |
| CLI表示 | Spectre.Console | 0.50.0 | - |
| ログ | Serilog | 8.0.0 | - |
| DB | EF Core | **10.0.0** | SQL Server |
| JSON | System.Text.Json | 標準 | - |

### 4.2 保留事項

| 項目 | 選択肢 | 決定時期 | 備考 |
|------|--------|---------|------|
| 定期実行 | Hangfire / Quartz.NET / IHostedService | Phase 4 | Hangfireの.NET 10対応状況次第 |
| フロントエンド | Next.js / Blazor | Phase 5以降 | 未決定 |
| 機械学習 | ONNX Runtime | Phase 5以降 | Python連携も検討 |

---

## 5. 重要な設計決定事項

### 5.1 アーキテクチャ

- **Clean Architecture** 採用
- UI/API層はDomain/Applicationに依存しない
- テスト容易性を重視

### 5.2 Python互換性

- **JSON出力形式はPython版と完全互換**を維持
- 日本語キー（`馬番`, `馬名`等）は `[JsonPropertyName]` で固定
- 馬番の型統一: `ToIntSafe()` でint正規化

### 5.3 Cookie認証

- `HttpClientHandler` + `CookieContainer` を使用
- Python版の `requests.Session` と同等の挙動を実現

### 5.4 ファイルパス

- `DataPathOptions` で一元管理
- 環境変数 `KEIBA_DATA_ROOT` でルート変更可能
- 直書きパスは設計上禁止

---

## 6. 注意事項・リスク

### 6.1 Hangfireの.NET 10対応

- 現時点で正式サポート未発表
- Newtonsoft.Json関連の問題報告あり
- **推奨**: Phase 4まではCLIベースで進め、後から統合

### 6.2 HTML構造変更への対応

- 過去に `nittei_parser.py` で対応した経緯あり
- 正規表現で柔軟にパースする設計が重要
- テストデータとして実際のHTML保存を推奨

### 6.3 並列処理

- Python版: `ThreadPoolExecutor` 最大22ワーカー
- C#版: `Parallel.ForEachAsync` + `SemaphoreSlim` で同等実装

---

## 7. 関連ドキュメント一覧

### 設計ドキュメント
- [詳細設計書](./csharp_migration_detailed_design.md)
- [DB統合設計書](./database_integration_design.md)
- [実装ロードマップ](./implementation_roadmap.md)
- [IntegrationService設計](./integration_service_design.md)
- [MarkdownGenerator設計](./markdown_generator_design.md)
- [パーサー出力スキーマ](./parser_output_schemas.md)
- [レビューノート](./review_notes.md)
- [.NET 10移行ガイド](./dotnet10_migration_guide.md)

### タスク管理
- [タスクマスターインデックス](../../tasks/index.md)
- [C#移行タスク](../../tasks/active/2025-12/task-251213-001-csharp-migration.md)

### 作業ログ
- [作業ログ](../../worklog/20251213-001-csharp-migration-design.md)

### Python版参照
- [運用サポート](../../運用サポート.md)
- [アーキテクチャ](../../KeibaCICD.keibabook/docs/システム概要/アーキテクチャ.md)

---

## 8. 再開時のチェックリスト

### 開発環境確認
- [ ] .NET 10 SDK がインストールされているか
- [ ] Visual Studio 2022 または VS Code が最新か
- [ ] Git リポジトリが最新か

### 設計書確認
- [ ] `csharp_migration_detailed_design.md` を一読
- [ ] `parser_output_schemas.md` でDTO構造を確認
- [ ] `implementation_roadmap.md` でPhase 2タスクを確認

### 実装開始
- [ ] ソリューション作成コマンドを実行
- [ ] NuGetパッケージを追加
- [ ] Domain層のRaceId.csから実装開始

---

## 9. 問い合わせ先

設計に関する質問や不明点があれば、以下のドキュメントを参照するか、AIアシスタントに再度確認してください。

- 設計の背景・理由: `review_notes.md`
- 具体的なコード例: `csharp_migration_detailed_design.md`
- Python版との対応: `parser_output_schemas.md`

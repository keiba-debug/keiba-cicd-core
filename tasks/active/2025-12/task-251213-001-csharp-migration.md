# Task: C# .NET スクレイピングシステム移行

## メタデータ
- **ID**: 251213-001
- **作成日**: 2025-12-13
- **更新日**: 2025-12-14 00:30
- **優先度**: 🟡重要
- **ステータス**: 進行中
- **進捗**: 30%
- **見積工数**: 80h（4週間）
- **実績工数**: 6h
- **担当**: AI Assistant

## 概要

Python製の競馬ブックスクレイピングシステム（KeibaCICD.keibabook）をC# .NETに移行する。
運用サポートで使用している機能を中心に、Clean Architectureベースで再設計・実装。

## 依存関係
- 前提: なし
- ブロック: なし

## フェーズ別作業内容

> NOTE: フェーズ定義は `docs/design/implementation_roadmap.md` と統一する。
> - Phase 1: 設計
> - Phase 2: プロジェクト基盤
> - Phase 3: Scraper/Parser実装
> - Phase 4: サービス層・CLI
> - Phase 5: テスト・並行運用

### Phase 1: 設計（Week 1前半）✅ 完了
- [x] 現状システム分析
- [x] 詳細設計書作成
- [x] DB統合設計書作成
- [x] 実装ロードマップ作成
- [x] 設計書レビュー・修正

### Phase 2: プロジェクト基盤（Week 1後半）
- [ ] ソリューション作成
- [ ] NuGetパッケージ設定
- [ ] ドメイン層実装（エンティティ、値オブジェクト）
- [ ] 共通ユーティリティ実装

### Phase 3: Scraper/Parser実装（Week 2）
- [ ] KeibaBookScraper（HTTPクライアント）
- [ ] NitteiParser（日程パース）
- [ ] SyutubaParser（出馬表パース）
- [ ] CyokyoParser（調教パース）
- [ ] DanwaParser（厩舎談話パース）
- [ ] SeisekiParser（成績パース）
- [ ] SyoinParser（前走インタビュー）
- [ ] PaddokParser（パドック）

### Phase 4: サービス層・CLI（Week 3）
- [ ] ScrapingService
- [ ] IntegrationService
- [ ] MarkdownService
- [ ] JockeyService
- [ ] HorseProfileService
- [ ] CLI Commands実装

### Phase 5: テスト・検証（Week 4）
- [ ] ユニットテスト
- [ ] 統合テスト
- [ ] Python版との出力比較
- [ ] 並行運用テスト

## 進捗ログ

### 2025-12-14 00:30
- **実施**: パーサー出力スキーマ文書化
- **成果物**:
  - `docs/design/parser_output_schemas.md`（約600行）
- **内容**:
  - 7パーサー全ての出力JSONスキーマを文書化
  - C#対応クラス（DTOモデル）を設計
  - 互換基準（Must/May/Fail）を固定
  - テスト基準を定義
- **次のアクション**: Phase 2（プロジェクト基盤）開始

### 2025-12-13 23:50
- **実施**: 追加設計書作成（MarkdownGenerator / IntegrationService）
- **成果物**:
  - `docs/design/integration_service_design.md`（約400行）
  - `docs/design/markdown_generator_design.md`（約500行）
- **内容**:
  - IntegrationService: データマージフロー、馬番照合ロジック、エラーハンドリング
  - MarkdownGenerator: 14セクション分離設計、追記エリア保持、Mermaid対応
- **次のアクション**: パーサー出力スキーマ文書化

### 2025-12-13 23:30
- **実施**: 詳細設計書作成、設計レビュー
- **成果物**:
  - `docs/design/csharp_migration_detailed_design.md`
  - `docs/design/database_integration_design.md`
  - `docs/design/implementation_roadmap.md`
  - `docs/design/review_notes.md`
- **発見事項**: Cookie認証実装、パス設定の修正が必要
- **修正完了**: Cookie認証、パス設定、フェーズ定義統一

## 技術メモ

### アーキテクチャ
- Clean Architecture採用
- 6プロジェクト構成（Domain/Application/Infrastructure/CLI/API/Jobs）

### 主要NuGetパッケージ
- HtmlAgilityPack 1.11.61
- System.CommandLine 2.0.0-beta4
- Serilog.AspNetCore 8.0.0
- Microsoft.EntityFrameworkCore.SqlServer 8.0.0
- Hangfire.Core 1.8.6

### 重要な実装ポイント
1. Cookie認証: `HttpClientHandler` + `CookieContainer` 使用
2. 並列処理: `SemaphoreSlim` でワーカー数制御
3. 日付パース: 3形式対応（YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD）

## 関連ファイル
- `docs/design/csharp_migration_detailed_design.md`
- `docs/design/database_integration_design.md`
- `docs/design/implementation_roadmap.md`
- `docs/design/review_notes.md`
- `docs/design/integration_service_design.md`
- `docs/design/markdown_generator_design.md`
- `docs/design/parser_output_schemas.md`
- `docs/design/handover_notes.md` ← NEW（引継ぎ資料）
- `docs/design/dotnet10_migration_guide.md` ← NEW（.NET 10移行ガイド）
- `docs/csharp_migration_analysis.md`
- `docs/architecture_considerations.md`

## 技術決定事項（2025-12-14更新）
- **フレームワーク**: .NET 10 LTS（.NET 8から変更）
- **サポート期限**: 2028年11月14日
- **C#バージョン**: C# 14
- **EF Core**: 10.0.0
- **System.CommandLine**: 2.0.0（安定版）

## 作業ログ
- [2025-12-13: 設計書作成・.NET 10対応](../../worklog/20251213-001-csharp-migration-design.md)

# C# .NET 移行 実装ロードマップ

## 📋 概要

Python → C# .NET 移行の実装計画とタスク管理ドキュメントです。

---

## 0. フェーズ定義（共通）

本プロジェクトでは、他ドキュメント（`tasks/active/2025-12/task-251213-001-csharp-migration.md` 等）と
フェーズ定義を統一する。

| Phase | 意味 | 主な成果物 |
|------|------|------------|
| Phase 1 | 設計 | 詳細設計書 / DB統合設計書 / ロードマップ / レビューノート |
| Phase 2 | プロジェクト基盤 | ソリューション作成 / NuGet設定 / ドメイン層 |
| Phase 3 | Scraper/Parser実装 | KeibaBookScraper / 各Parser / DataFetcher |
| Phase 4 | サービス層・CLI | Services / DTO / Commands |
| Phase 5 | テスト・並行運用 | 統合テスト / Python版比較 / 本番移行準備 |

---

## 1. 全体スケジュール

```
Week 1: Phase 1 - 設計 / Phase 2 - プロジェクト基盤
├── Day 1: 設計レビュー反映（完了）
├── Day 2: ソリューション・プロジェクト作成
└── Day 3-5: ドメイン層実装

Week 2: Phase 3 - Scraper/Parser実装
├── Day 6-8: Scraper/Parser実装
└── Day 9-10: DataFetcher実装

Week 3: Phase 4 - サービス層・CLI
├── Day 11-12: サービス層実装
├── Day 13-14: CLI実装
└── Day 15: テスト・デバッグ

Week 4: Phase 5 - テスト・並行運用
├── Day 16-17: 統合テスト
├── Day 18-19: Python版との比較検証
└── Day 20: 本番移行準備
```

---

## 2. Phase別タスク詳細

### Phase 1: 設計（Week 1前半）✅ 完了

**成果物:**
- `docs/design/csharp_migration_detailed_design.md`
- `docs/design/database_integration_design.md`
- `docs/design/implementation_roadmap.md`（本ファイル）
- `docs/design/review_notes.md`

---

### Phase 2: プロジェクト基盤（Week 1後半）

#### Day 1-2: ソリューション作成

```powershell
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

**タスク:**
- [ ] ソリューション構造作成
- [ ] NuGetパッケージ追加
- [ ] appsettings.json作成
- [ ] Serilog設定

#### Day 3-5: ドメイン層実装

**タスク:**
- [ ] ValueObjects/RaceId.cs
- [ ] ValueObjects/HorseId.cs
- [ ] ValueObjects/JockeyId.cs
- [ ] ValueObjects/DateRange.cs
- [ ] Entities/Race.cs
- [ ] Entities/Horse.cs
- [ ] Entities/Jockey.cs
- [ ] Entities/Entry.cs
- [ ] Entities/Kaisai.cs
- [ ] Enums/DataType.cs
- [ ] Enums/TrackType.cs
- [ ] Enums/TrackCondition.cs
- [ ] Interfaces/IRaceRepository.cs
- [ ] Interfaces/IHorseRepository.cs
- [ ] Interfaces/IJockeyRepository.cs

---

### Phase 3: Scraper/Parser実装（Week 2）

#### Day 6-8: Scraper/Parser実装

**Scraper タスク:**
- [ ] IKeibaBookScraper.cs
- [ ] KeibaBookScraper.cs
- [ ] ScraperOptions.cs
- [ ] JockeyScraper.cs
- [ ] HorseProfileScraper.cs

**Parser タスク:**
- [ ] IParser.cs
- [ ] BaseParser.cs
- [ ] NitteiParser.cs ★最優先
- [ ] SeisekiParser.cs
- [ ] SyutubaParser.cs
- [ ] CyokyoParser.cs
- [ ] DanwaParser.cs
- [ ] SyoinParser.cs
- [ ] PaddokParser.cs

**テストケース:**
```csharp
[Fact]
public void NitteiParser_Parse_ReturnsCorrectRaceCount()
{
    // 実際のHTMLファイルを使用してテスト
    var html = File.ReadAllText("TestData/nittei_20251214.html");
    var parser = new NitteiParser();
    
    var result = parser.Parse(html, "20251214");
    
    Assert.Equal(3, result.KaisaiCount);
    Assert.Equal(36, result.TotalRaces);
}
```

#### Day 9-10: DataFetcher実装

**タスク:**
- [ ] IDataFetcher.cs
- [ ] OptimizedDataFetcher.cs
- [ ] FetcherOptions.cs
- [ ] ErrorStats.cs
- [ ] PerformanceStats.cs

**並列処理設計:**
```csharp
public async Task<ScrapingResult> FetchAllAsync(
    DateTime startDate,
    DateTime endDate,
    DataType[] dataTypes,
    FetcherOptions options,
    IProgress<ProgressDto>? progress,
    CancellationToken cancellationToken)
{
    var semaphore = new SemaphoreSlim(options.MaxWorkers);
    var tasks = new List<Task<FetchResult>>();
    
    foreach (var raceId in raceIds)
    {
        foreach (var dataType in dataTypes)
        {
            tasks.Add(FetchWithSemaphoreAsync(
                semaphore, raceId, dataType, options, cancellationToken));
        }
    }
    
    var results = await Task.WhenAll(tasks);
    return new ScrapingResult(results);
}
```

---

### Phase 4: サービス層・CLI（Week 3）

#### Day 11-12: サービス層実装

**タスク:**
- [ ] IScrapingService.cs
- [ ] ScrapingService.cs
- [ ] IIntegrationService.cs
- [ ] IntegrationService.cs
- [ ] IMarkdownService.cs
- [ ] MarkdownService.cs
- [ ] IJockeyService.cs
- [ ] JockeyService.cs
- [ ] IHorseProfileService.cs
- [ ] HorseProfileService.cs

**DTO タスク:**
- [ ] RaceDto.cs
- [ ] EntryDto.cs
- [ ] IntegratedRaceDto.cs
- [ ] ScrapingResultDto.cs
- [ ] ProgressDto.cs

#### Day 13-14: CLI実装

**タスク:**
- [ ] Program.cs
- [ ] Commands/ScheduleCommand.cs
- [ ] Commands/DataCommand.cs
- [ ] Commands/FullCommand.cs ★最優先
- [ ] Commands/IntegrateCommand.cs
- [ ] Commands/MarkdownCommand.cs
- [ ] Commands/JockeyCommand.cs
- [ ] Commands/HorseProfileCommand.cs

**CLI使用例:**
```powershell
# Python版と同等のコマンド
keiba-scraper schedule --start 2025/12/14 --end 2025/12/14
keiba-scraper full --start 2025/12/14 --data-types shutsuba,cyokyo,danwa,syoin
keiba-scraper integrate --date 2025/12/14
keiba-scraper markdown --date 2025/12/14 --organized
```

#### Day 15: テスト・デバッグ

**タスク:**
- [ ] ユニットテスト実行
- [ ] 実データでの動作確認
- [ ] エラーハンドリング検証
- [ ] ログ出力確認

---

### Phase 5: テスト・並行運用（Week 4）

#### Day 16-17: 統合テスト

**タスク:**
- [ ] E2Eテスト実装
- [ ] パフォーマンステスト
- [ ] メモリ使用量確認
- [ ] 並列処理の負荷テスト

#### Day 18-19: Python版との比較検証

**検証項目:**
- [ ] 出力JSONの差分比較
- [ ] MD新聞の出力比較
- [ ] 処理時間比較
- [ ] エラー発生率比較

**比較スクリプト:**
```powershell
# Python版実行
python -m src.fast_batch_cli full --start 2025/12/14 --end 2025/12/14

# C#版実行
keiba-scraper full --start 2025/12/14 --end 2025/12/14

# JSON差分比較
# NOTE: 単純な文字列比較は順序や整形で差分が出やすいので、
#       重要フィールド（race_id / entries / data_sources 等）の比較を優先する。
Compare-Object (Get-Content py_output.json) (Get-Content cs_output.json)
```

#### Day 20: 本番移行準備

**タスク:**
- [ ] 運用サポート.md更新
- [ ] PowerShellスクリプト更新
- [ ] ドキュメント最終化
- [ ] バックアップ手順確認

---

## 3. 優先順位マトリクス

| コンポーネント | 重要度 | 緊急度 | 優先順位 |
|--------------|--------|--------|---------|
| NitteiParser | ⭐⭐⭐ | ⭐⭐⭐ | 1 |
| KeibaBookScraper | ⭐⭐⭐ | ⭐⭐⭐ | 1 |
| SyutubaParser | ⭐⭐⭐ | ⭐⭐⭐ | 2 |
| CyokyoParser | ⭐⭐⭐ | ⭐⭐ | 3 |
| DanwaParser | ⭐⭐⭐ | ⭐⭐ | 3 |
| SeisekiParser | ⭐⭐ | ⭐⭐ | 4 |
| SyoinParser | ⭐⭐ | ⭐ | 5 |
| PaddokParser | ⭐⭐ | ⭐ | 5 |
| FullCommand | ⭐⭐⭐ | ⭐⭐⭐ | 1 |
| IntegrationService | ⭐⭐⭐ | ⭐⭐⭐ | 2 |
| MarkdownService | ⭐⭐⭐ | ⭐⭐ | 3 |
| JockeyService | ⭐⭐ | ⭐ | 6 |
| HorseProfileService | ⭐⭐ | ⭐ | 6 |

---

## 4. リスク管理

### 4.1 技術的リスク

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|---------|------|
| HTMLパース差異 | 高 | 中 | Python版との出力比較テスト |
| 並列処理の競合 | 中 | 低 | SemaphoreSlimでの制御 |
| Cookie認証問題 | 高 | 低 | 既存Cookie設定の移植 |
| 文字エンコーディング | 中 | 中 | UTF-8統一、BOM対応 |

### 4.2 スケジュールリスク

| リスク | 影響度 | 発生確率 | 対策 |
|--------|--------|---------|------|
| パーサー実装遅延 | 高 | 中 | 優先度に応じた段階実装 |
| テスト不足 | 高 | 中 | Phase 4での集中検証期間 |
| 想定外のバグ | 中 | 中 | Python版との並行運用期間設定 |

---

## 5. 成功基準

### 5.1 機能要件

- [ ] 運用サポートの全コマンドが実行可能
- [ ] Python版と同等のJSON出力
- [ ] Python版と同等のMD新聞出力
- [ ] エラー発生率 < 1%

### 5.2 非機能要件

- [ ] 処理時間: Python版と同等以上
- [ ] メモリ使用量: 500MB以下
- [ ] CPU使用率: 安定
- [ ] ログ出力: 既存形式互換

### 5.3 移行完了条件

1. 全テストケースがグリーン
2. 1週間の並行運用で問題なし
3. 運用担当者の承認
4. ドキュメント更新完了

---

## 6. 次のアクション

### 今すぐ実行

1. **ソリューション作成開始**
   - 上記コマンドでプロジェクト構造を作成
   
2. **NuGetパッケージ追加**
   - HtmlAgilityPack, System.CommandLine, Serilog等

3. **ドメイン層から実装開始**
   - RaceId, DataType等の基本型から

### 承認待ち

- [ ] 本設計書のレビュー・承認
- [ ] 開発リソースの確保
- [ ] スケジュール確定

---

## 付録: コマンド対応表

| Python | C# | 備考 |
|--------|-----|------|
| `python -m src.fast_batch_cli schedule` | `keiba-scraper schedule` | |
| `python -m src.fast_batch_cli data` | `keiba-scraper data` | |
| `python -m src.fast_batch_cli full` | `keiba-scraper full` | |
| `python -m src.integrator_cli batch` | `keiba-scraper integrate` | |
| `python -m src.markdown_cli batch` | `keiba-scraper markdown` | |
| `python -m src.jockey_cli leading` | `keiba-scraper jockey leading` | |
| `python -m src.jockey_cli update` | `keiba-scraper jockey update` | |
| `python -m src.horse_profile_cli` | `keiba-scraper horse-profile` | |

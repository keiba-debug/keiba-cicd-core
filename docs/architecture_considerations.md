# アーキテクチャ設計検討書

## 📋 概要

将来的なUI実装（Next.js / Blazor）を見据え、REST API形式での呼び出しやアーキテクチャ設計についての検討事項をまとめます。

---

## 1. 推奨アーキテクチャ：Clean Architecture

### 1.1 なぜClean Architectureか

| 利点 | 説明 |
|------|------|
| **フロントエンド非依存** | Next.jsでもBlazorでも同じバックエンドを利用可能 |
| **テスタビリティ** | ビジネスロジックの単体テストが容易 |
| **拡張性** | CLI/API/Blazor Serverなど複数の呼び出し方式に対応可能 |
| **保守性** | 責務が明確に分離され、変更の影響範囲を限定できる |

### 1.2 レイヤー構成

```
KeibaCICD.Scraper/
│
├── KeibaCICD.Scraper.Domain/          # ドメイン層（最内層）
│   ├── Entities/                       # ドメインエンティティ
│   │   ├── Race.cs
│   │   ├── Horse.cs
│   │   └── Kaisai.cs
│   ├── ValueObjects/
│   │   ├── RaceId.cs
│   │   └── DateRange.cs
│   └── Interfaces/                     # リポジトリインターフェース
│       ├── IRaceRepository.cs
│       └── IHorseRepository.cs
│
├── KeibaCICD.Scraper.Application/     # アプリケーション層
│   ├── Interfaces/                     # ユースケースのインターフェース
│   │   ├── IScrapingService.cs
│   │   └── IIntegrationService.cs
│   ├── Services/                       # ビジネスロジック
│   │   ├── ScrapingService.cs
│   │   ├── IntegrationService.cs
│   │   └── MarkdownGenerationService.cs
│   ├── DTOs/                           # データ転送オブジェクト
│   │   ├── RaceDto.cs
│   │   ├── ScrapingResultDto.cs
│   │   └── ProgressDto.cs
│   └── Commands/                       # CQRSコマンド（オプション）
│       ├── StartScrapingCommand.cs
│       └── GenerateMarkdownCommand.cs
│
├── KeibaCICD.Scraper.Infrastructure/  # インフラ層
│   ├── Scrapers/                       # 外部サービスアクセス
│   │   ├── KeibaBookScraper.cs
│   │   └── ScraperOptions.cs
│   ├── Parsers/
│   │   ├── NitteiParser.cs
│   │   ├── SyutubaParser.cs
│   │   └── CyokyoParser.cs
│   ├── Repositories/                   # データアクセス
│   │   ├── FileRaceRepository.cs
│   │   └── JsonHorseRepository.cs
│   └── BackgroundJobs/                 # バックグラウンド処理
│       ├── ScrapingJob.cs
│       └── IJobScheduler.cs
│
├── KeibaCICD.Scraper.API/             # Web API層 ★新規追加
│   ├── Program.cs
│   ├── Controllers/
│   │   ├── ScrapingController.cs
│   │   ├── RaceController.cs
│   │   └── JobController.cs
│   ├── Hubs/                           # SignalR Hub
│   │   └── ProgressHub.cs
│   └── appsettings.json
│
├── KeibaCICD.Scraper.CLI/             # CLI層（既存）
│   ├── Program.cs
│   └── Commands/
│
└── KeibaCICD.Scraper.Tests/
```

---

## 2. API設計の検討

### 2.1 REST API vs gRPC vs SignalR

| 技術 | 適用場面 | Next.js互換 | Blazor互換 |
|------|---------|-------------|------------|
| **REST API** | 通常のCRUD操作、データ取得 | ✅ 最適 | ✅ 対応 |
| **SignalR** | リアルタイム進捗通知、長時間処理 | ⚠️ 要クライアント実装 | ✅ 最適 |
| **gRPC** | 高性能な内部通信（マイクロサービス間） | ⚠️ gRPC-Web必要 | ✅ 対応 |

### 2.2 推奨API設計

```
# スケジュール取得（同期処理：すぐ完了）
GET  /api/races/{date}
GET  /api/races/{date}/{raceId}

# スクレイピング開始（非同期処理：ジョブ開始）
POST /api/jobs/scraping
     Body: { "startDate": "2025/12/14", "endDate": "2025/12/14", "dataTypes": ["shutsuba", "cyokyo"] }
     Response: { "jobId": "abc123", "status": "started" }

# ジョブ状態確認
GET  /api/jobs/{jobId}
     Response: { "jobId": "abc123", "status": "running", "progress": 45, "message": "3/7 レース処理中" }

# ジョブキャンセル
DELETE /api/jobs/{jobId}

# Markdown生成
POST /api/markdown/generate
     Body: { "raceId": "202512140101" }

# 馬プロファイル取得
GET  /api/horses/{horseId}
POST /api/horses/profiles/generate
```

### 2.3 長時間処理の扱い方

スクレイピング処理は数分〜数十分かかる可能性があるため、以下の設計が必要：

```
┌─────────────┐     POST /api/jobs/scraping     ┌─────────────┐
│   Client    │ ─────────────────────────────▶  │   API       │
│  (UI/CLI)   │                                 │   Server    │
└─────────────┘                                 └──────┬──────┘
       │                                               │
       │                                               ▼
       │                                      ┌─────────────────┐
       │                                      │ Background      │
       │                                      │ Job Queue       │
       │                                      │ (Hangfire等)    │
       │                                      └────────┬────────┘
       │                                               │
       │         SignalR / Server-Sent Events          │
       │◀──────────────────────────────────────────────┤
       │         進捗通知: { progress: 45% }           │
       │                                               │
       ▼                                               ▼
  進捗表示・完了通知                            スクレイピング実行
```

---

## 3. フロントエンド選択による影響

### 3.1 Next.js を選択した場合

| 項目 | 設計方針 |
|------|---------|
| **通信方式** | REST API + WebSocket（または Server-Sent Events） |
| **認証** | JWT Bearer Token（Cookie認証も可） |
| **リアルタイム** | Socket.io または native WebSocket |
| **ホスティング** | API: Azure App Service / Docker、Frontend: Vercel / Netlify |
| **CORS設定** | 必須（異なるオリジン間通信） |

```typescript
// Next.js側の呼び出し例
const startScraping = async (params: ScrapingParams) => {
  const res = await fetch('/api/jobs/scraping', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  const { jobId } = await res.json();
  
  // WebSocketで進捗監視
  const ws = new WebSocket(`wss://api.example.com/jobs/${jobId}/progress`);
  ws.onmessage = (e) => setProgress(JSON.parse(e.data));
};
```

### 3.2 Blazor を選択した場合

| 項目 | 設計方針 |
|------|---------|
| **通信方式** | REST API + SignalR（ネイティブ対応） |
| **認証** | Cookie認証 or JWT（ASP.NET Identity統合可） |
| **リアルタイム** | SignalR（最適、追加ライブラリ不要） |
| **ホスティング** | 単一のASP.NET Coreアプリとして統合可能 |
| **CORS設定** | 同一オリジンなら不要 |

```csharp
// Blazor側の呼び出し例
@inject HttpClient Http
@inject IHubConnection HubConnection

private async Task StartScraping()
{
    var result = await Http.PostAsJsonAsync("/api/jobs/scraping", new {
        StartDate = "2025/12/14",
        DataTypes = new[] { "shutsuba", "cyokyo" }
    });
    
    var job = await result.Content.ReadFromJsonAsync<JobInfo>();
    
    // SignalRで進捗監視
    HubConnection.On<ProgressDto>("ProgressUpdate", (progress) => {
        CurrentProgress = progress;
        StateHasChanged();
    });
}
```

### 3.3 どちらにも対応できる設計

**推奨：REST API + SignalR の両方を実装**

```csharp
// ProgressHub.cs - SignalR Hub
public class ProgressHub : Hub
{
    public async Task JoinJobGroup(string jobId)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, jobId);
    }
    
    public async Task LeaveJobGroup(string jobId)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, jobId);
    }
}

// ScrapingJob.cs - バックグラウンドジョブ
public class ScrapingJob
{
    private readonly IHubContext<ProgressHub> _hubContext;
    
    public async Task ExecuteAsync(string jobId, ScrapingParams param)
    {
        for (int i = 0; i < totalRaces; i++)
        {
            // スクレイピング処理...
            
            // 進捗通知（SignalR）
            await _hubContext.Clients.Group(jobId).SendAsync("ProgressUpdate", new {
                Progress = (i + 1) * 100 / totalRaces,
                Message = $"{i + 1}/{totalRaces} レース処理中"
            });
        }
    }
}
```

---

## 4. 推奨：バックグラウンドジョブ基盤

### 4.1 選択肢比較

| ライブラリ | 特徴 | 推奨度 |
|-----------|------|--------|
| **Hangfire** | ダッシュボードUI付き、永続化対応、実績多い | ⭐⭐⭐ 最推奨 |
| **Quartz.NET** | 高機能スケジューラー、複雑なスケジュール対応 | ⭐⭐ |
| **IHostedService** | 標準機能、シンプルだが永続化なし | ⭐ |

### 4.2 Hangfire導入例

```csharp
// Program.cs
builder.Services.AddHangfire(x => x.UseSqlServerStorage(connectionString));
builder.Services.AddHangfireServer();

// ScrapingController.cs
[HttpPost]
public IActionResult StartScraping([FromBody] ScrapingRequest request)
{
    var jobId = BackgroundJob.Enqueue<IScrapingService>(
        x => x.ExecuteAsync(request.StartDate, request.EndDate, request.DataTypes)
    );
    
    return Ok(new { JobId = jobId, Status = "started" });
}
```

---

## 5. データ取得処理（CLI）について

### 5.1 CLI実行で問題ない理由

| 観点 | 評価 |
|------|------|
| **バッチ処理の性質** | ✅ 対話不要、定期実行に適している |
| **リソース使用** | ✅ UIプロセスから分離できる |
| **スケジューリング** | ✅ タスクスケジューラ / cron で管理可能 |
| **エラー通知** | ✅ ログファイル + メール通知で対応可 |

### 5.2 CLI + API 両対応の設計

**同じサービス層を共有することで、CLI/API両方から利用可能：**

```csharp
// Application層のサービス（共通）
public class ScrapingService : IScrapingService
{
    public async Task<ScrapingResult> ExecuteAsync(
        string startDate, 
        string endDate, 
        string[] dataTypes,
        IProgress<ProgressInfo>? progress = null)
    {
        // CLI: progress = null
        // API: progress = SignalR通知用のIProgress実装
        
        foreach (var date in dates)
        {
            // 処理...
            progress?.Report(new ProgressInfo { ... });
        }
    }
}

// CLI側
var service = serviceProvider.GetRequiredService<IScrapingService>();
await service.ExecuteAsync(startDate, endDate, dataTypes);

// API側
await service.ExecuteAsync(startDate, endDate, dataTypes, 
    new SignalRProgress(hubContext, jobId));
```

---

## 6. その他の検討事項

### 6.1 認証・認可

| シナリオ | 推奨 |
|---------|------|
| 社内ツール（限定ユーザー） | Windows認証 or 簡易JWT |
| 外部公開（将来） | Azure AD B2C / Auth0 |

### 6.2 ログ・監視

| 項目 | 推奨 |
|------|------|
| **ログ基盤** | Serilog + Seq / Azure Application Insights |
| **ジョブ監視** | Hangfire Dashboard |
| **ヘルスチェック** | ASP.NET Core Health Checks |

### 6.3 デプロイメント

```yaml
# docker-compose.yml 案
version: '3.8'
services:
  api:
    build: ./KeibaCICD.Scraper.API
    ports:
      - "5000:80"
    environment:
      - KEIBA_DATA_ROOT_DIR=/data
    volumes:
      - keiba-data:/data
  
  # 将来的にフロントエンド追加
  # frontend:
  #   build: ./frontend
  #   ports:
  #     - "3000:80"
  
volumes:
  keiba-data:
```

---

## 7. 結論と推奨事項

### 7.1 今すぐ実装すべきこと

| 優先度 | 項目 | 理由 |
|--------|------|------|
| ⭐⭐⭐ | **Clean Architecture採用** | 将来のAPI化・UI化に対応しやすい |
| ⭐⭐⭐ | **サービス層の抽象化** | CLI/APIで同じロジックを再利用 |
| ⭐⭐ | **IProgress対応** | 進捗通知の仕組みを最初から組み込む |

### 7.2 将来のUI実装時に追加すべきこと

| 項目 | 説明 |
|------|------|
| **REST API Controller** | 既存サービスを呼び出すだけのシンプルな実装 |
| **SignalR Hub** | リアルタイム進捗通知用 |
| **Hangfire** | バックグラウンドジョブ管理 |

### 7.3 修正版プロジェクト構成

```
KeibaCICD.Scraper/
│
├── KeibaCICD.Scraper.Domain/          # ドメイン層
├── KeibaCICD.Scraper.Application/     # アプリケーション層 ★重要
│   └── Services/                       # ← ここにビジネスロジック集約
├── KeibaCICD.Scraper.Infrastructure/  # インフラ層
│
├── KeibaCICD.Scraper.CLI/             # CLI層（Phase 1で実装）
└── KeibaCICD.Scraper.API/             # API層（将来追加、薄いレイヤー）
```

**ポイント：Application層を厚く、CLI/API層は薄くする設計**

これにより、フロントエンドの選択（Next.js / Blazor）が未定でも、バックエンドの設計を進められます。

---

## 8. 定期実行（Hangfire）

### 8.1 Hangfireによる定期実行の設計

**スクレイピングの定期実行スケジュール例：**

| タイミング | 処理内容 | Cron式 |
|-----------|---------|--------|
| 毎朝 6:00 | 当日の開催スケジュール取得 | `0 6 * * *` |
| レース開始2時間前 | 出馬表・調教データ取得 | 動的スケジュール |
| レース終了後 | 成績データ取得 | 動的スケジュール |
| 毎週月曜 2:00 | 週末レース結果の一括統合 | `0 2 * * 1` |

### 8.2 Hangfire実装パターン

```csharp
// Program.cs
builder.Services.AddHangfire(config => config
    .SetDataCompatibilityLevel(CompatibilityLevel.Version_180)
    .UseSimpleAssemblyNameTypeSerializer()
    .UseRecommendedSerializerSettings()
    .UseSqlServerStorage(connectionString, new SqlServerStorageOptions
    {
        CommandBatchMaxTimeout = TimeSpan.FromMinutes(5),
        SlidingInvisibilityTimeout = TimeSpan.FromMinutes(5),
        QueuePollInterval = TimeSpan.Zero,
        UseRecommendedIsolationLevel = true,
        DisableGlobalLocks = true
    }));

builder.Services.AddHangfireServer();

// 定期ジョブ登録
app.UseHangfireDashboard("/hangfire");

// 毎朝6時：当日スケジュール取得
RecurringJob.AddOrUpdate<IScrapingService>(
    "daily-schedule",
    x => x.FetchTodayScheduleAsync(),
    "0 6 * * *",
    new RecurringJobOptions { TimeZone = TimeZoneInfo.FindSystemTimeZoneById("Tokyo Standard Time") }
);

// 毎週月曜2時：週末データ統合
RecurringJob.AddOrUpdate<IIntegrationService>(
    "weekly-integration",
    x => x.IntegrateWeekendDataAsync(),
    "0 2 * * 1",
    new RecurringJobOptions { TimeZone = TimeZoneInfo.FindSystemTimeZoneById("Tokyo Standard Time") }
);
```

### 8.3 動的スケジュール（レース時刻ベース）

```csharp
// レース開始2時間前に自動でジョブをスケジュール
public class RaceScheduleService
{
    private readonly IBackgroundJobClient _jobClient;
    
    public async Task SchedulePreRaceJobsAsync(DateTime raceDate)
    {
        // 当日のレース一覧を取得
        var races = await _raceRepository.GetRacesByDateAsync(raceDate);
        
        foreach (var race in races)
        {
            var startTime = race.StartTime;
            var jobTime = startTime.AddHours(-2); // 2時間前
            
            if (jobTime > DateTime.Now)
            {
                // 出馬表・調教データ取得をスケジュール
                _jobClient.Schedule<IScrapingService>(
                    x => x.FetchRaceDataAsync(race.RaceId),
                    jobTime
                );
            }
        }
    }
}
```

### 8.4 Hangfire Dashboard 設定

```csharp
// 認証付きダッシュボード
app.UseHangfireDashboard("/hangfire", new DashboardOptions
{
    Authorization = new[] { new HangfireAuthorizationFilter() },
    DashboardTitle = "KeibaCICD ジョブ管理"
});

public class HangfireAuthorizationFilter : IDashboardAuthorizationFilter
{
    public bool Authorize(DashboardContext context)
    {
        var httpContext = context.GetHttpContext();
        return httpContext.User.Identity?.IsAuthenticated ?? false;
    }
}
```

---

## 9. データベース統合（JRA-VAN連携）

### 9.1 データソース統合の全体像

```
┌─────────────────────────────────────────────────────────────────┐
│                        SQL Server                                │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐    │
│  │   JRA-VAN     │  │  競馬ブック   │  │    統合ビュー     │    │
│  │   データ      │  │  スクレイピング│  │  (分析・ML用)     │    │
│  │               │  │  データ       │  │                   │    │
│  │ - 公式成績    │  │ - 調教データ   │  │ - 統合レース情報  │    │
│  │ - 血統情報    │  │ - 厩舎コメント │  │ - 特徴量データ    │    │
│  │ - 騎手成績    │  │ - パドック情報 │  │ - 予測結果        │    │
│  └───────────────┘  └───────────────┘  └───────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
         ▲                    ▲                    │
         │                    │                    ▼
    JRA-VAN API          スクレイパー         機械学習モデル
```

### 9.2 データベーススキーマ設計

```sql
-- JRA-VANデータ用スキーマ
CREATE SCHEMA jravan;

-- 競馬ブックデータ用スキーマ
CREATE SCHEMA keibabook;

-- 統合・分析用スキーマ
CREATE SCHEMA analysis;

-- 例: 統合レースビュー
CREATE VIEW analysis.vw_RaceIntegrated AS
SELECT 
    j.RaceId,
    j.RaceName,
    j.Date,
    j.Track,
    j.Distance,
    j.TrackCondition,
    k.TrainingComment,
    k.StableComment,
    k.PaddockInfo
FROM jravan.Races j
LEFT JOIN keibabook.RaceData k ON j.RaceId = k.RaceId;
```

### 9.3 Entity Framework Core 設計

```csharp
// DbContext設計
public class KeibaDbContext : DbContext
{
    // JRA-VANデータ
    public DbSet<JraRace> JraRaces { get; set; }
    public DbSet<JraHorse> JraHorses { get; set; }
    public DbSet<JraJockey> JraJockeys { get; set; }
    
    // 競馬ブックスクレイピングデータ
    public DbSet<KbRaceData> KbRaceData { get; set; }
    public DbSet<KbTrainingData> KbTrainingData { get; set; }
    public DbSet<KbStableComment> KbStableComments { get; set; }
    
    // 統合・分析データ
    public DbSet<IntegratedRace> IntegratedRaces { get; set; }
    public DbSet<FeatureVector> FeatureVectors { get; set; }
    public DbSet<Prediction> Predictions { get; set; }
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema("dbo");
        
        // JRA-VANスキーマ
        modelBuilder.Entity<JraRace>().ToTable("Races", "jravan");
        modelBuilder.Entity<JraHorse>().ToTable("Horses", "jravan");
        
        // 競馬ブックスキーマ
        modelBuilder.Entity<KbRaceData>().ToTable("RaceData", "keibabook");
        
        // 分析スキーマ
        modelBuilder.Entity<IntegratedRace>().ToTable("IntegratedRaces", "analysis");
    }
}
```

### 9.4 リポジトリパターンによる抽象化

```csharp
// Domain層 - インターフェース
public interface IRaceRepository
{
    Task<Race?> GetByIdAsync(string raceId);
    Task<IEnumerable<Race>> GetByDateAsync(DateTime date);
    Task SaveAsync(Race race);
}

// Infrastructure層 - 実装（DB用）
public class SqlRaceRepository : IRaceRepository
{
    private readonly KeibaDbContext _context;
    
    public async Task<Race?> GetByIdAsync(string raceId)
    {
        var jraRace = await _context.JraRaces
            .FirstOrDefaultAsync(r => r.RaceId == raceId);
        var kbData = await _context.KbRaceData
            .FirstOrDefaultAsync(r => r.RaceId == raceId);
        
        return MapToIntegratedRace(jraRace, kbData);
    }
    
    public async Task SaveAsync(Race race)
    {
        var entity = new KbRaceData
        {
            RaceId = race.RaceId,
            TrainingComment = race.TrainingComment,
            StableComment = race.StableComment,
            UpdatedAt = DateTime.UtcNow
        };
        
        _context.KbRaceData.Add(entity);
        await _context.SaveChangesAsync();
    }
}

// Infrastructure層 - 実装（ファイル用：既存互換）
public class FileRaceRepository : IRaceRepository
{
    // 既存のJSONファイルベースの実装を維持
}
```

### 9.5 データ同期戦略

| 戦略 | 説明 | 適用場面 |
|------|------|---------|
| **リアルタイム同期** | スクレイピング直後にDB登録 | 通常運用 |
| **バッチ同期** | 定期的にJSONからDBへ一括登録 | 初期移行、障害復旧 |
| **差分同期** | 変更分のみ更新 | パフォーマンス最適化 |

```csharp
// スクレイピング後の自動DB登録
public class ScrapingService : IScrapingService
{
    private readonly IRaceRepository _raceRepository;
    private readonly IDbSyncService _dbSyncService;
    
    public async Task<ScrapingResult> ExecuteAsync(string date, string[] dataTypes)
    {
        // 1. スクレイピング実行
        var result = await ScrapeDataAsync(date, dataTypes);
        
        // 2. ファイル保存（既存処理）
        await SaveToFileAsync(result);
        
        // 3. DB同期（新規追加）
        if (_dbSyncService.IsEnabled)
        {
            await _dbSyncService.SyncAsync(result);
        }
        
        return result;
    }
}
```

---

## 10. 機械学習統合

### 10.1 ML.NET vs Python の選択

| 観点 | ML.NET | Python (scikit-learn等) |
|------|--------|------------------------|
| **C#統合** | ✅ ネイティブ | ⚠️ 要連携実装 |
| **モデル精度** | ⚠️ 比較的シンプル | ✅ 豊富なアルゴリズム |
| **ライブラリ豊富さ** | ⚠️ 限定的 | ✅ 非常に豊富 |
| **デプロイ容易性** | ✅ 単一バイナリ | ⚠️ Python環境必要 |
| **リアルタイム推論** | ✅ 高速 | ⚠️ オーバーヘッドあり |

### 10.2 推奨アーキテクチャ

**ハイブリッドアプローチ：**
- **学習フェーズ**: Python（豊富なライブラリ活用）
- **推論フェーズ**: ONNX経由でC#から呼び出し

```
┌─────────────────────────────────────────────────────────────┐
│                    学習フェーズ (Python)                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ データ取得   │ → │ 特徴量生成   │ → │ モデル学習   │     │
│  │ (SQL Server)│    │ (pandas)    │    │ (LightGBM)  │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
│                                               │              │
│                                               ▼              │
│                                        ┌─────────────┐      │
│                                        │ ONNX Export │      │
│                                        └──────┬──────┘      │
└───────────────────────────────────────────────┼─────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    推論フェーズ (C#)                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ 特徴量取得   │ → │ ONNX Runtime│ → │ 予測結果     │     │
│  │ (EF Core)   │    │ 推論        │    │ DB登録      │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 10.3 特徴量設計

```csharp
// 機械学習用の特徴量エンティティ
public class FeatureVector
{
    public string RaceId { get; set; }
    public string HorseId { get; set; }
    
    // 馬の基本情報
    public int Age { get; set; }
    public float Weight { get; set; }
    public float WeightDiff { get; set; }
    
    // 過去成績
    public float WinRate { get; set; }
    public float PlaceRate { get; set; }
    public float AvgFinishPosition { get; set; }
    public int ConsecutiveRaces { get; set; }
    
    // コース適性
    public float TrackTypeWinRate { get; set; }  // 芝/ダート別
    public float DistanceWinRate { get; set; }   // 距離別
    public float TrackConditionWinRate { get; set; }  // 馬場状態別
    
    // 調教データ（競馬ブックから）
    public float TrainingScore { get; set; }
    public float TrainingTimeDiff { get; set; }
    
    // 厩舎・騎手
    public float JockeyWinRate { get; set; }
    public float TrainerWinRate { get; set; }
    
    // オッズ情報
    public float Odds { get; set; }
    public int PopularityRank { get; set; }
}
```

### 10.4 ONNX Runtime 統合

```csharp
// NuGet: Microsoft.ML.OnnxRuntime
using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;

public class PredictionService : IPredictionService
{
    private readonly InferenceSession _session;
    
    public PredictionService()
    {
        _session = new InferenceSession("models/race_prediction.onnx");
    }
    
    public async Task<PredictionResult> PredictAsync(FeatureVector features)
    {
        // 特徴量をテンソルに変換
        var inputTensor = new DenseTensor<float>(new float[] {
            features.Age,
            features.Weight,
            features.WinRate,
            features.TrainingScore,
            // ... 他の特徴量
        }, new int[] { 1, 20 }); // バッチサイズ1, 特徴量20個
        
        var inputs = new List<NamedOnnxValue>
        {
            NamedOnnxValue.CreateFromTensor("input", inputTensor)
        };
        
        // 推論実行
        using var results = _session.Run(inputs);
        var output = results.First().AsTensor<float>();
        
        return new PredictionResult
        {
            WinProbability = output[0],
            PlaceProbability = output[1],
            ShowProbability = output[2]
        };
    }
}
```

### 10.5 Python学習スクリプト例

```python
# models/train_model.py
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
import onnxmltools
from skl2onnx import convert_sklearn

# SQL Serverからデータ取得
import pyodbc
conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};...')
df = pd.read_sql("SELECT * FROM analysis.vw_FeatureVectors", conn)

# 特徴量とターゲット
X = df.drop(['RaceId', 'HorseId', 'Target'], axis=1)
y = df['Target']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# LightGBM学習
model = lgb.LGBMClassifier(
    n_estimators=1000,
    learning_rate=0.05,
    num_leaves=31,
    random_state=42
)
model.fit(X_train, y_train)

# ONNXエクスポート
from skl2onnx import to_onnx
onnx_model = to_onnx(model, X_train[:1].values.astype('float32'))
with open("race_prediction.onnx", "wb") as f:
    f.write(onnx_model.SerializeToString())

print("Model exported to ONNX format")
```

### 10.6 ML統合のプロジェクト構成

```
KeibaCICD.Scraper/
│
├── KeibaCICD.Scraper.ML/              # 機械学習層
│   ├── Features/
│   │   ├── IFeatureExtractor.cs
│   │   ├── RaceFeatureExtractor.cs
│   │   └── HorseFeatureExtractor.cs
│   ├── Models/
│   │   ├── FeatureVector.cs
│   │   └── PredictionResult.cs
│   ├── Services/
│   │   ├── IPredictionService.cs
│   │   └── OnnxPredictionService.cs
│   └── models/                         # ONNXモデルファイル
│       └── race_prediction.onnx
│
├── KeibaCICD.ML.Training/             # Python学習スクリプト（別プロジェクト）
│   ├── train_model.py
│   ├── feature_engineering.py
│   └── requirements.txt
```

---

## 11. 統合アーキテクチャ（最終形）

### 11.1 全体構成図

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              UI Layer                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │    Blazor UI    │  │   Next.js UI    │  │      CLI        │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
└───────────┼────────────────────┼────────────────────┼───────────────────┘
            │                    │                    │
            ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API Layer                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    REST API + SignalR                            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Application Layer                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │ ScrapingService│  │IntegrationSvc │  │ PredictionSvc │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Infrastructure  │    │    Database     │    │   ML Runtime    │
│  ┌───────────┐  │    │  ┌───────────┐  │    │  ┌───────────┐  │
│  │ Scrapers  │  │    │  │ SQL Server │  │    │  │ONNX Runtime│  │
│  │ Parsers   │  │    │  │ (JRA-VAN + │  │    │  │           │  │
│  │ Hangfire  │  │    │  │ Keibabook) │  │    │  │           │  │
│  └───────────┘  │    │  └───────────┘  │    │  └───────────┘  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 11.2 NuGetパッケージ構成（最終版）

```xml
<ItemGroup>
  <!-- Web -->
  <PackageReference Include="HtmlAgilityPack" Version="1.11.x" />
  
  <!-- CLI -->
  <PackageReference Include="System.CommandLine" Version="2.0.x" />
  
  <!-- Background Jobs -->
  <PackageReference Include="Hangfire.Core" Version="1.8.x" />
  <PackageReference Include="Hangfire.SqlServer" Version="1.8.x" />
  
  <!-- Database -->
  <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="8.x.x" />
  
  <!-- Logging -->
  <PackageReference Include="Serilog.AspNetCore" Version="8.x.x" />
  <PackageReference Include="Serilog.Sinks.MSSqlServer" Version="6.x.x" />
  
  <!-- Machine Learning -->
  <PackageReference Include="Microsoft.ML.OnnxRuntime" Version="1.16.x" />
  
  <!-- SignalR -->
  <PackageReference Include="Microsoft.AspNetCore.SignalR.Core" Version="1.x.x" />
</ItemGroup>
```

---

## 12. 私の意見まとめ（追加）

### 12.1 定期実行について

- **Hangfireを強く推奨** - ダッシュボードUI、再実行機能、ジョブ永続化が便利
- **動的スケジューリング**を活用 - レース開始時刻に合わせた柔軟なジョブ実行
- **タスクスケジューラとの併用も可** - シンプルなCLI定期実行は既存運用を維持

### 12.2 データベース統合について

- **段階的移行を推奨** - 最初はファイルとDB両方に保存、徐々にDBメインへ
- **スキーマ分離** - JRA-VAN、競馬ブック、分析用で明確に分離
- **リポジトリパターン** - ファイル/DB切り替えを容易に

### 12.3 機械学習について

- **ハイブリッドアプローチ推奨** - 学習はPython、推論はONNX+C#
- **特徴量設計が最重要** - 競馬ブックの調教データは差別化ポイント
- **MLパイプライン自動化** - Hangfireで定期的にモデル更新も可能

---

## 13. 総合意見まとめ

### 基本方針
1. **CLI実行で問題なし** - バッチ処理の性質上、CLIは最適な選択です
2. **Clean Architecture採用を強く推奨** - 将来のAPI化を見据えた設計
3. **サービス層を先に充実させる** - CLI/API共通のビジネスロジック
4. **SignalR準備は後回しでOK** - ただしIProgress対応は最初から組み込む
5. **フロントエンド選択は急がなくてよい** - バックエンドがしっかりしていればどちらでも対応可能

### 追加考慮事項
6. **Hangfireによる定期実行** - ダッシュボード付きで運用監視が容易
7. **DB統合は段階的に** - ファイルとDB両立から始め、徐々にDBメインへ
8. **ML統合はONNX経由** - 学習はPython、推論はC#のハイブリッド構成

---

## 付録A：技術選択チートシート

### 推奨技術スタック（全機能対応版）

```
【バックエンド】
├── .NET 8 LTS
├── ASP.NET Core (Minimal API or Controllers)
├── Entity Framework Core (SQL Server)
├── Hangfire (バックグラウンドジョブ・定期実行)
├── Serilog (ログ)
└── HtmlAgilityPack (スクレイピング)

【データベース】
├── SQL Server
├── JRA-VAN連携スキーマ
├── 競馬ブックデータスキーマ
└── 分析・ML用スキーマ

【機械学習】
├── Python (学習・特徴量エンジニアリング)
├── LightGBM / XGBoost (モデル)
├── ONNX (モデルエクスポート)
└── ONNX Runtime (C#推論)

【通信】
├── REST API (メイン)
├── SignalR (リアルタイム通知)
└── JSON (データ形式)

【将来拡張時】
├── Next.js → WebSocket/SSE クライアント実装
└── Blazor → SignalR ネイティブ対応
```

---

## 付録B：実装ロードマップ案

| Phase | 内容 | 期間 | 成果物 |
|-------|------|------|--------|
| **Phase 1** | Core層（Scraper/Parser）移行 | 2週間 | C#版スクレイパー |
| **Phase 2** | DB統合基盤 | 1週間 | EF Core + リポジトリ |
| **Phase 3** | Hangfire定期実行 | 0.5週間 | 自動スケジュール実行 |
| **Phase 4** | REST API | 1週間 | API Controller |
| **Phase 5** | ML統合 | 2週間 | ONNX推論サービス |
| **Phase 6** | UI実装 | 2-4週間 | Blazor or Next.js |

**合計見積: 8-12週間（2-3ヶ月）**

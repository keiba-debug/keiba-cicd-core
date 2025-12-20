# C# .NET 移行詳細設計書

## 📋 ドキュメント情報

| 項目 | 内容 |
|------|------|
| **作成日** | 2025年12月13日 |
| **バージョン** | 1.0 |
| **対象システム** | KeibaCICD.keibabook → KeibaCICD.Scraper |
| **移行元** | Python 3.11+ |
| **移行先** | **.NET 10 LTS** |
| **C#バージョン** | C# 14 |
| **サポート期限** | 2028年11月14日 |

---

## 1. 現状システム分析

### 1.1 運用サポートで使用している主要機能

運用サポート（競馬予想準備）で実行しているコマンドを分析：

```powershell
# 1. 騎手情報更新
python -m src.jockey_cli leading
python -m src.jockey_cli update --top 200

# 2. スケジュール取得
python -m src.fast_batch_cli schedule --start $from_date --end $to_date

# 3. データ取得（7種類）
python -m src.fast_batch_cli full --start $from_date --end $from_date --data-types shutsuba,cyokyo,danwa,syoin
python -m src.fast_batch_cli full --start $from_date --end $from_date --data-types paddok,seiseki

# 4. データ統合
python -m src.integrator_cli batch --date $from_date

# 5. MD新聞生成
python -m src.markdown_cli batch --date $from_date --organized

# 6. 馬プロファイル生成
python -m src.horse_profile_cli --date $from_date --all --with-history --with-seiseki-table
```

### 1.2 移行対象コンポーネント一覧

| カテゴリ | Python | C# | 優先度 |
|---------|--------|-----|--------|
| **CLI** | fast_batch_cli.py | FastBatchCommand | ⭐⭐⭐ |
| **CLI** | integrator_cli.py | IntegratorCommand | ⭐⭐⭐ |
| **CLI** | markdown_cli.py | MarkdownCommand | ⭐⭐⭐ |
| **CLI** | jockey_cli.py | JockeyCommand | ⭐⭐ |
| **CLI** | horse_profile_cli.py | HorseProfileCommand | ⭐⭐ |
| **Scraper** | requests_scraper.py | KeibaBookScraper | ⭐⭐⭐ |
| **Scraper** | jockey_scraper.py | JockeyScraper | ⭐⭐ |
| **Scraper** | horse_profile_manager.py | HorseProfileScraper | ⭐⭐ |
| **Parser** | nittei_parser.py | NitteiParser | ⭐⭐⭐ |
| **Parser** | seiseki_parser.py | SeisekiParser | ⭐⭐⭐ |
| **Parser** | syutuba_parser.py | SyutubaParser | ⭐⭐⭐ |
| **Parser** | cyokyo_parser.py | CyokyoParser | ⭐⭐⭐ |
| **Parser** | danwa_parser.py | DanwaParser | ⭐⭐⭐ |
| **Parser** | syoin_parser.py | SyoinParser | ⭐⭐ |
| **Parser** | paddok_parser.py | PaddokParser | ⭐⭐ |
| **Service** | race_data_integrator.py | RaceDataIntegrator | ⭐⭐⭐ |
| **Service** | markdown_generator.py | MarkdownGenerator | ⭐⭐⭐ |
| **Service** | optimized_data_fetcher.py | OptimizedDataFetcher | ⭐⭐⭐ |

### 1.3 データタイプ一覧

| タイプ | URL | 内容 | MD新聞での利用 |
|--------|-----|------|--------------|
| `nittei` | /cyuou/nittei/{date} | 開催スケジュール | レースID取得 |
| `seiseki` | /cyuou/seiseki/{race_id} | 成績データ | レース結果 |
| `shutsuba` | /cyuou/syutuba/{race_id} | 出馬表 | 騎手・短評・本誌印 |
| `cyokyo` | /cyuou/cyokyo/0/0/{race_id} | 調教データ | 調教評価 |
| `danwa` | /cyuou/danwa/0/{race_id} | 厩舎談話 | 厩舎コメント |
| `syoin` | /cyuou/syoin/{race_id} | 前走インタビュー | 前走評価 |
| `paddok` | /cyuou/paddok/{race_id} | パドック情報 | パドック評価 |

---

## 2. プロジェクト構成

### 2.1 ソリューション構成

```
KeibaCICD.Scraper.sln
│
├── src/
│   ├── KeibaCICD.Scraper.Domain/           # ドメイン層
│   │   ├── Entities/
│   │   │   ├── Race.cs
│   │   │   ├── Horse.cs
│   │   │   ├── Jockey.cs
│   │   │   ├── Entry.cs
│   │   │   └── Kaisai.cs
│   │   ├── ValueObjects/
│   │   │   ├── RaceId.cs
│   │   │   ├── HorseId.cs
│   │   │   ├── JockeyId.cs
│   │   │   └── DateRange.cs
│   │   ├── Enums/
│   │   │   ├── DataType.cs
│   │   │   ├── TrackType.cs
│   │   │   └── TrackCondition.cs
│   │   └── Interfaces/
│   │       ├── IRaceRepository.cs
│   │       ├── IHorseRepository.cs
│   │       └── IJockeyRepository.cs
│   │
│   ├── KeibaCICD.Scraper.Application/      # アプリケーション層
│   │   ├── Interfaces/
│   │   │   ├── IScrapingService.cs
│   │   │   ├── IIntegrationService.cs
│   │   │   ├── IMarkdownService.cs
│   │   │   ├── IJockeyService.cs
│   │   │   └── IHorseProfileService.cs
│   │   ├── Services/
│   │   │   ├── ScrapingService.cs
│   │   │   ├── IntegrationService.cs
│   │   │   ├── MarkdownService.cs
│   │   │   ├── JockeyService.cs
│   │   │   └── HorseProfileService.cs
│   │   ├── DTOs/
│   │   │   ├── RaceDto.cs
│   │   │   ├── EntryDto.cs
│   │   │   ├── ScrapingResultDto.cs
│   │   │   ├── IntegratedRaceDto.cs
│   │   │   └── ProgressDto.cs
│   │   └── Common/
│   │       ├── DateParser.cs
│   │       └── PathHelper.cs
│   │
│   ├── KeibaCICD.Scraper.Infrastructure/   # インフラ層
│   │   ├── Scrapers/
│   │   │   ├── IKeibaBookScraper.cs
│   │   │   ├── KeibaBookScraper.cs
│   │   │   ├── JockeyScraper.cs
│   │   │   ├── HorseProfileScraper.cs
│   │   │   └── ScraperOptions.cs
│   │   ├── Parsers/
│   │   │   ├── IParser.cs
│   │   │   ├── BaseParser.cs
│   │   │   ├── NitteiParser.cs
│   │   │   ├── SeisekiParser.cs
│   │   │   ├── SyutubaParser.cs
│   │   │   ├── CyokyoParser.cs
│   │   │   ├── DanwaParser.cs
│   │   │   ├── SyoinParser.cs
│   │   │   └── PaddokParser.cs
│   │   ├── Repositories/
│   │   │   ├── FileRaceRepository.cs
│   │   │   ├── FileHorseRepository.cs
│   │   │   ├── SqlRaceRepository.cs
│   │   │   └── SqlHorseRepository.cs
│   │   ├── DataFetcher/
│   │   │   ├── IDataFetcher.cs
│   │   │   ├── OptimizedDataFetcher.cs
│   │   │   └── FetcherOptions.cs
│   │   ├── Generators/
│   │   │   ├── MarkdownGenerator.cs
│   │   │   └── TemplateEngine.cs
│   │   └── Persistence/
│   │       ├── KeibaDbContext.cs
│   │       └── Configurations/
│   │
│   ├── KeibaCICD.Scraper.CLI/              # CLI層
│   │   ├── Program.cs
│   │   ├── Commands/
│   │   │   ├── ScheduleCommand.cs
│   │   │   ├── DataCommand.cs
│   │   │   ├── FullCommand.cs
│   │   │   ├── IntegrateCommand.cs
│   │   │   ├── MarkdownCommand.cs
│   │   │   ├── JockeyCommand.cs
│   │   │   └── HorseProfileCommand.cs
│   │   └── appsettings.json
│   │
│   ├── KeibaCICD.Scraper.API/              # Web API層（将来拡張）
│   │   ├── Program.cs
│   │   ├── Controllers/
│   │   ├── Hubs/
│   │   └── appsettings.json
│   │
│   └── KeibaCICD.Scraper.Jobs/             # バックグラウンドジョブ
│       ├── ScrapingJob.cs
│       ├── IntegrationJob.cs
│       └── ScheduledJobs.cs
│
└── tests/
    ├── KeibaCICD.Scraper.Domain.Tests/
    ├── KeibaCICD.Scraper.Application.Tests/
    ├── KeibaCICD.Scraper.Infrastructure.Tests/
    └── KeibaCICD.Scraper.Integration.Tests/
```

### 2.2 NuGetパッケージ

```xml
<!-- KeibaCICD.Scraper.Infrastructure.csproj -->
<ItemGroup>
  <!-- Web Scraping -->
  <PackageReference Include="HtmlAgilityPack" Version="1.12.4" />
  
  <!-- HTTP Client -->
  <PackageReference Include="Microsoft.Extensions.Http" Version="10.0.0" />
  <PackageReference Include="Polly.Extensions.Http" Version="3.0.0" />
  
  <!-- Database (.NET 10対応) -->
  <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="10.0.0" />
  <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="10.0.0" />
  
  <!-- Logging -->
  <PackageReference Include="Serilog.AspNetCore" Version="8.0.0" />
  <PackageReference Include="Serilog.Sinks.Console" Version="5.0.1" />
  <PackageReference Include="Serilog.Sinks.File" Version="5.0.0" />
</ItemGroup>

<!-- KeibaCICD.Scraper.CLI.csproj -->
<ItemGroup>
  <!-- .NET 10と同時リリースの安定版 -->
  <PackageReference Include="System.CommandLine" Version="2.0.0" />
  <PackageReference Include="Spectre.Console" Version="0.50.0" />
</ItemGroup>

<!-- KeibaCICD.Scraper.Jobs.csproj -->
<!-- 注意: Hangfireは.NET 10正式対応待ち。まずはIHostedServiceで実装 -->
<ItemGroup>
  <PackageReference Include="Hangfire.Core" Version="1.8.22" />
  <PackageReference Include="Hangfire.SqlServer" Version="1.8.22" />
</ItemGroup>
```

---

## 3. クラス設計

### 3.1 ドメイン層

#### RaceId（値オブジェクト）

```csharp
namespace KeibaCICD.Scraper.Domain.ValueObjects;

public record RaceId
{
    public string Value { get; }
    
    // 202505050401 → 2025年 第5回 中山 5日目 04レース 01
    public int Year => int.Parse(Value[..4]);
    public int Kai => int.Parse(Value[4..6]);
    public int JyoCode => int.Parse(Value[6..8]);
    public int Nichime => int.Parse(Value[8..10]);
    public int RaceNumber => int.Parse(Value[10..12]);
    
    public RaceId(string value)
    {
        if (string.IsNullOrEmpty(value) || value.Length != 12)
            throw new ArgumentException("RaceId must be 12 characters", nameof(value));
        
        if (!value.All(char.IsDigit))
            throw new ArgumentException("RaceId must contain only digits", nameof(value));
        
        Value = value;
    }
    
    public static implicit operator string(RaceId id) => id.Value;
    public static explicit operator RaceId(string value) => new(value);
    
    public override string ToString() => Value;
}
```

#### Race（エンティティ）

```csharp
namespace KeibaCICD.Scraper.Domain.Entities;

public class Race
{
    public RaceId Id { get; private set; }
    public DateTime Date { get; private set; }
    public string Venue { get; private set; }
    public int RaceNumber { get; private set; }
    public string RaceName { get; private set; }
    public string Grade { get; private set; }
    public TrackType TrackType { get; private set; }
    public int Distance { get; private set; }
    public TrackCondition TrackCondition { get; private set; }
    public string Weather { get; private set; }
    public TimeSpan? StartTime { get; private set; }
    
    public IReadOnlyList<Entry> Entries => _entries.AsReadOnly();
    private readonly List<Entry> _entries = new();
    
    public RaceResult? Result { get; private set; }
    
    // Factory method
    public static Race Create(RaceId id, DateTime date, string venue, int raceNumber, string raceName)
    {
        return new Race
        {
            Id = id,
            Date = date,
            Venue = venue,
            RaceNumber = raceNumber,
            RaceName = raceName
        };
    }
    
    public void AddEntry(Entry entry)
    {
        _entries.Add(entry);
    }
    
    public void SetResult(RaceResult result)
    {
        Result = result;
    }
}
```

#### DataType（列挙型）

```csharp
namespace KeibaCICD.Scraper.Domain.Enums;

public enum DataType
{
    Nittei,     // 日程
    Seiseki,    // 成績
    Shutsuba,   // 出馬表
    Cyokyo,     // 調教
    Danwa,      // 厩舎談話
    Syoin,      // 前走インタビュー
    Paddok      // パドック
}

public static class DataTypeExtensions
{
    public static string ToUrlPath(this DataType dataType, string raceId) => dataType switch
    {
        DataType.Nittei => $"/cyuou/nittei/{raceId}",
        DataType.Seiseki => $"/cyuou/seiseki/{raceId}",
        DataType.Shutsuba => $"/cyuou/syutuba/{raceId}",
        DataType.Cyokyo => $"/cyuou/cyokyo/0/0/{raceId}",
        DataType.Danwa => $"/cyuou/danwa/0/{raceId}",
        DataType.Syoin => $"/cyuou/syoin/{raceId}",
        DataType.Paddok => $"/cyuou/paddok/{raceId}",
        _ => throw new ArgumentOutOfRangeException(nameof(dataType))
    };
}
```

### 3.2 アプリケーション層

#### IScrapingService

```csharp
namespace KeibaCICD.Scraper.Application.Interfaces;

public interface IScrapingService
{
    /// <summary>
    /// 日程データを取得
    /// </summary>
    Task<NitteiResult> FetchScheduleAsync(
        DateTime date,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// レースデータを取得
    /// </summary>
    Task<ScrapingResult> FetchRaceDataAsync(
        DateTime startDate,
        DateTime endDate,
        DataType[] dataTypes,
        int maxWorkers = 5,
        double delaySeconds = 1.0,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// フル処理（スケジュール取得→データ取得）
    /// </summary>
    Task<ScrapingResult> FetchFullAsync(
        DateTime startDate,
        DateTime endDate,
        DataType[] dataTypes,
        int maxWorkers = 5,
        double delaySeconds = 1.0,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default);
}
```

#### IIntegrationService

```csharp
namespace KeibaCICD.Scraper.Application.Interfaces;

public interface IIntegrationService
{
    /// <summary>
    /// 単一レースの統合データを作成
    /// </summary>
    Task<IntegratedRaceDto?> CreateIntegratedFileAsync(
        string raceId,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// 日付指定での一括統合
    /// </summary>
    Task<IntegrationResult> BatchCreateAsync(
        DateTime date,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// 期間指定での一括統合
    /// </summary>
    Task<IntegrationResult> BatchCreateAsync(
        DateTime startDate,
        DateTime endDate,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default);
}
```

#### ScrapingService実装

```csharp
namespace KeibaCICD.Scraper.Application.Services;

public class ScrapingService : IScrapingService
{
    private readonly IKeibaBookScraper _scraper;
    private readonly IDataFetcher _dataFetcher;
    private readonly IRaceRepository _raceRepository;
    private readonly ILogger<ScrapingService> _logger;
    
    public ScrapingService(
        IKeibaBookScraper scraper,
        IDataFetcher dataFetcher,
        IRaceRepository raceRepository,
        ILogger<ScrapingService> logger)
    {
        _scraper = scraper;
        _dataFetcher = dataFetcher;
        _raceRepository = raceRepository;
        _logger = logger;
    }
    
    public async Task<NitteiResult> FetchScheduleAsync(
        DateTime date,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var dateStr = date.ToString("yyyyMMdd");
        _logger.LogInformation("[FAST] スケジュール取得: {Date}", dateStr);
        
        progress?.Report(new ProgressDto
        {
            Phase = "schedule",
            Message = $"スケジュール取得中: {dateStr}",
            Progress = 0
        });
        
        var html = await _scraper.ScrapeAsync(
            DataType.Nittei.ToUrlPath(dateStr),
            cancellationToken);
        
        var parser = new NitteiParser();
        var result = parser.Parse(html, dateStr);
        
        // ファイル保存
        await _raceRepository.SaveScheduleAsync(dateStr, result);
        
        progress?.Report(new ProgressDto
        {
            Phase = "schedule",
            Message = $"スケジュール取得完了: {result.TotalRaces}レース",
            Progress = 100
        });
        
        _logger.LogInformation("[OK] スケジュール取得完了: {Count}開催, {Races}レース",
            result.KaisaiCount, result.TotalRaces);
        
        return result;
    }
    
    public async Task<ScrapingResult> FetchRaceDataAsync(
        DateTime startDate,
        DateTime endDate,
        DataType[] dataTypes,
        int maxWorkers = 5,
        double delaySeconds = 1.0,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("[START] データ取得: {Start} ~ {End}, Types: {Types}",
            startDate.ToString("yyyy/MM/dd"),
            endDate.ToString("yyyy/MM/dd"),
            string.Join(",", dataTypes));
        
        var result = await _dataFetcher.FetchAllAsync(
            startDate,
            endDate,
            dataTypes,
            new FetcherOptions
            {
                MaxWorkers = maxWorkers,
                DelaySeconds = delaySeconds
            },
            progress,
            cancellationToken);
        
        _logger.LogInformation("[OK] データ取得完了: 成功={Success}, 失敗={Failed}",
            result.SuccessCount, result.FailedCount);
        
        return result;
    }
    
    public async Task<ScrapingResult> FetchFullAsync(
        DateTime startDate,
        DateTime endDate,
        DataType[] dataTypes,
        int maxWorkers = 5,
        double delaySeconds = 1.0,
        IProgress<ProgressDto>? progress = null,
        CancellationToken cancellationToken = default)
    {
        // Phase 1: スケジュール取得
        var currentDate = startDate;
        while (currentDate <= endDate)
        {
            await FetchScheduleAsync(currentDate, progress, cancellationToken);
            currentDate = currentDate.AddDays(1);
        }
        
        // Phase 2: データ取得
        return await FetchRaceDataAsync(
            startDate, endDate, dataTypes,
            maxWorkers, delaySeconds,
            progress, cancellationToken);
    }
}
```

### 3.3 インフラ層

#### KeibaBookScraper

```csharp
namespace KeibaCICD.Scraper.Infrastructure.Scrapers;

public class KeibaBookScraper : IKeibaBookScraper, IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly CookieContainer _cookieContainer;
    private readonly ScraperOptions _options;
    private readonly ILogger<KeibaBookScraper> _logger;
    
    public KeibaBookScraper(
        IOptions<ScraperOptions> options,
        ILogger<KeibaBookScraper> logger)
    {
        _options = options.Value;
        _logger = logger;
        
        // CookieContainer を使用したHttpClient設定
        _cookieContainer = new CookieContainer();
        var handler = new HttpClientHandler
        {
            CookieContainer = _cookieContainer,
            UseCookies = true,
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate
        };
        
        _httpClient = new HttpClient(handler)
        {
            Timeout = TimeSpan.FromSeconds(_options.Timeout)
        };
        
        // デフォルトヘッダー設定
        _httpClient.DefaultRequestHeaders.Add("User-Agent", _options.UserAgent);
        _httpClient.DefaultRequestHeaders.Add("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8");
        _httpClient.DefaultRequestHeaders.Add("Accept-Language", "ja,en-US;q=0.7,en;q=0.3");
        _httpClient.DefaultRequestHeaders.Add("Connection", "keep-alive");
        
        // Cookie設定
        SetupCookies();
    }
    
    private void SetupCookies()
    {
        // Python版と同様にCookieContainerに追加
        foreach (var cookie in _options.Cookies)
        {
            _cookieContainer.Add(new Cookie(
                cookie.Name,
                cookie.Value,
                cookie.Path ?? "/",
                cookie.Domain ?? "p.keibabook.co.jp"
            ));
        }
        _logger.LogInformation("Cookieを設定しました: {Count}個", _options.Cookies.Count);
    }
    
    public async Task<string> ScrapeAsync(string path, CancellationToken cancellationToken = default)
    {
        var url = $"{_options.BaseUrl}{path}";
        _logger.LogInformation("データを取得します: {Url}", url);
        
        var response = await _httpClient.GetAsync(url, cancellationToken);
        response.EnsureSuccessStatusCode();
        
        var content = await response.Content.ReadAsStringAsync(cancellationToken);
        _logger.LogInformation("データ取得完了: {Length}文字", content.Length);
        
        return content;
    }
    
    public async Task<string> ScrapeRaceDataAsync(
        DataType dataType,
        string raceId,
        CancellationToken cancellationToken = default)
    {
        var path = dataType.ToUrlPath(raceId);
        return await ScrapeAsync(path, cancellationToken);
    }
    
    public void Dispose()
    {
        _httpClient?.Dispose();
        _logger.LogInformation("セッションを終了しました");
    }
}
```

#### NitteiParser

```csharp
namespace KeibaCICD.Scraper.Infrastructure.Parsers;

public class NitteiParser : BaseParser<NitteiResult>
{
    private readonly ILogger<NitteiParser> _logger;
    
    public NitteiParser(ILogger<NitteiParser>? logger = null)
    {
        _logger = logger ?? NullLogger<NitteiParser>.Instance;
    }
    
    public override NitteiResult Parse(string htmlContent, string dateStr)
    {
        var doc = new HtmlDocument();
        doc.LoadHtml(htmlContent);
        
        var kaisaiData = new Dictionary<string, List<RaceInfo>>();
        
        // kaisai div を取得
        var kaisaiDiv = doc.DocumentNode.SelectSingleNode("//div[@class='kaisai']");
        if (kaisaiDiv == null)
        {
            _logger.LogWarning("kaisaiクラスのdivが見つかりませんでした");
            return new NitteiResult(dateStr, kaisaiData);
        }
        
        // kaisai テーブルを取得
        var kaisaiTables = kaisaiDiv.SelectNodes(".//table[@class='kaisai']");
        _logger.LogInformation("kaisaiテーブル数: {Count}", kaisaiTables?.Count ?? 0);
        
        if (kaisaiTables == null)
            return new NitteiResult(dateStr, kaisaiData);
        
        foreach (var table in kaisaiTables)
        {
            var rows = table.SelectNodes(".//tr");
            if (rows == null) continue;
            
            string? kaisaiName = null;
            var races = new List<RaceInfo>();
            
            foreach (var row in rows)
            {
                // 開催場所名を取得
                var th = row.SelectSingleNode(".//th[@class='midasi']");
                if (th != null)
                {
                    kaisaiName = th.InnerText.Trim();
                    _logger.LogInformation("開催場所発見: {Kaisai}", kaisaiName);
                    continue;
                }
                
                // レース情報を取得
                var tds = row.SelectNodes(".//td");
                if (tds == null || tds.Count < 2) continue;
                
                // レース番号抽出（"1RMy馬" → "1R"）
                var td0Text = tds[0].InnerText.Trim();
                var raceNoMatch = Regex.Match(td0Text, @"^(\d+R)");
                if (!raceNoMatch.Success) continue;
                
                var raceNo = raceNoMatch.Groups[1].Value;
                
                // リンクからレースIDを抽出
                var link = tds[1].SelectSingleNode(".//a[@href]");
                if (link == null) continue;
                
                var href = link.GetAttributeValue("href", "");
                var raceId = ExtractRaceId(href);
                if (string.IsNullOrEmpty(raceId)) continue;
                
                // レース名とコース情報
                var ps = tds[1].SelectNodes(".//p");
                var raceName = ps?[0]?.InnerText.Trim() ?? "";
                var course = ps?.Count > 1 ? ps[1].InnerText.Trim() : "";
                
                // 発走時刻
                string? startTime = null;
                if (tds.Count >= 3)
                {
                    var timeText = tds[2].InnerText.Trim();
                    var timeMatch = Regex.Match(timeText, @"(\d{1,2}):(\d{2})");
                    if (timeMatch.Success)
                    {
                        startTime = $"{timeMatch.Groups[1].Value.PadLeft(2, '0')}:{timeMatch.Groups[2].Value}";
                    }
                }
                
                races.Add(new RaceInfo
                {
                    RaceNo = raceNo,
                    RaceName = raceName,
                    Course = course,
                    RaceId = raceId,
                    StartTime = startTime
                });
            }
            
            if (!string.IsNullOrEmpty(kaisaiName) && races.Count > 0)
            {
                kaisaiData[kaisaiName] = races;
                _logger.LogInformation("開催場所 {Kaisai}: {Count}レース", kaisaiName, races.Count);
            }
        }
        
        var result = new NitteiResult(dateStr, kaisaiData);
        _logger.LogInformation("レース日程パース完了: {Kaisai}開催, {Races}レース",
            result.KaisaiCount, result.TotalRaces);
        
        return result;
    }
    
    private static string? ExtractRaceId(string href)
    {
        var patterns = new[]
        {
            @"/shutsuba/(\d{12})",
            @"/seiseki/(\d{12})",
            @"/cyokyo/\d+/\d+/(\d{12})",
            @"/danwa/\d+/(\d{12})",
            @"/(\d{12})"
        };
        
        foreach (var pattern in patterns)
        {
            var match = Regex.Match(href, pattern);
            if (match.Success)
                return match.Groups[1].Value;
        }
        
        return null;
    }
}
```

### 3.4 CLI層

#### Program.cs

```csharp
using System.CommandLine;
using KeibaCICD.Scraper.CLI.Commands;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Serilog;

var builder = Host.CreateApplicationBuilder(args);

// Serilog設定
Log.Logger = new LoggerConfiguration()
    .ReadFrom.Configuration(builder.Configuration)
    .Enrich.FromLogContext()
    .WriteTo.Console()
    .WriteTo.File("logs/scraper-.log", rollingInterval: RollingInterval.Day)
    .CreateLogger();

builder.Services.AddSerilog();

// DI設定
builder.Services.AddScraperServices();
builder.Services.AddInfrastructureServices();

var host = builder.Build();

// ルートコマンド
var rootCommand = new RootCommand("KeibaCICD Scraper CLI - 競馬ブックデータ取得ツール");

// サブコマンド追加
rootCommand.AddCommand(new ScheduleCommand(host.Services));
rootCommand.AddCommand(new DataCommand(host.Services));
rootCommand.AddCommand(new FullCommand(host.Services));
rootCommand.AddCommand(new IntegrateCommand(host.Services));
rootCommand.AddCommand(new MarkdownCommand(host.Services));
rootCommand.AddCommand(new JockeyCommand(host.Services));
rootCommand.AddCommand(new HorseProfileCommand(host.Services));

return await rootCommand.InvokeAsync(args);
```

#### FullCommand

```csharp
namespace KeibaCICD.Scraper.CLI.Commands;

public class FullCommand : Command
{
    public FullCommand(IServiceProvider services) : base("full", "スケジュール取得→データ取得を一括実行")
    {
        var startOption = new Option<string>("--start", "開始日 (YYYY/MM/DD)") { IsRequired = true };
        startOption.AddAlias("-s");
        
        var endOption = new Option<string?>("--end", "終了日 (YYYY/MM/DD)");
        endOption.AddAlias("-e");
        
        var dataTypesOption = new Option<string>(
            "--data-types",
            () => "seiseki,shutsuba,cyokyo,danwa,syoin,paddok",
            "取得するデータタイプ（カンマ区切り）");
        
        var delayOption = new Option<double>("--delay", () => 1.0, "リクエスト間の遅延（秒）");
        var maxWorkersOption = new Option<int>("--max-workers", () => 5, "並列ワーカー数");
        
        AddOption(startOption);
        AddOption(endOption);
        AddOption(dataTypesOption);
        AddOption(delayOption);
        AddOption(maxWorkersOption);
        
        this.SetHandler(async (start, end, dataTypes, delay, maxWorkers) =>
        {
            using var scope = services.CreateScope();
            var service = scope.ServiceProvider.GetRequiredService<IScrapingService>();
            var logger = scope.ServiceProvider.GetRequiredService<ILogger<FullCommand>>();
            
            var startDate = DateParser.Parse(start);
            var endDate = end != null ? DateParser.Parse(end) : startDate;
            var types = ParseDataTypes(dataTypes);
            
            logger.LogInformation("[START] フル処理: {Start} ~ {End}", 
                startDate.ToString("yyyy/MM/dd"),
                endDate.ToString("yyyy/MM/dd"));
            logger.LogInformation("[DATA] データタイプ: {Types}", string.Join(",", types));
            logger.LogInformation("[SETTING] delay={Delay}s, workers={Workers}", delay, maxWorkers);
            
            // 進捗表示用
            var progress = new Progress<ProgressDto>(p =>
            {
                AnsiConsole.MarkupLine($"[blue]{p.Phase}[/]: {p.Message} ({p.Progress}%)");
            });
            
            var result = await service.FetchFullAsync(
                startDate, endDate, types,
                maxWorkers, delay, progress);
            
            // 結果表示
            AnsiConsole.MarkupLine($"[green]✓[/] 成功: {result.SuccessCount}");
            AnsiConsole.MarkupLine($"[red]✗[/] 失敗: {result.FailedCount}");
            AnsiConsole.MarkupLine($"[blue]⏱[/] 処理時間: {result.ProcessingTime.TotalSeconds:F2}秒");
            
            logger.LogInformation("[OK] フル処理完了");
            
        }, startOption, endOption, dataTypesOption, delayOption, maxWorkersOption);
    }
    
    private static DataType[] ParseDataTypes(string dataTypes)
    {
        return dataTypes.Split(',')
            .Select(t => Enum.Parse<DataType>(t.Trim(), ignoreCase: true))
            .ToArray();
    }
}
```

---

## 4. データモデル設計

### 4.1 DTO定義

```csharp
// IntegratedRaceDto.cs - 統合レースデータ
public record IntegratedRaceDto
{
    public RaceInfoDto RaceInfo { get; init; } = null!;
    public List<EntryDto> Entries { get; init; } = new();
    public MetaDto Meta { get; init; } = null!;
    public AnalysisDto? Analysis { get; init; }
}

public record RaceInfoDto
{
    public string RaceId { get; init; } = "";
    public string Date { get; init; } = "";
    public string Venue { get; init; } = "";
    public int RaceNumber { get; init; }
    public string RaceName { get; init; } = "";
    public string Track { get; init; } = "";
    public int Distance { get; init; }
    public string TrackCondition { get; init; } = "";
    public string Weather { get; init; } = "";
    public string? StartTime { get; init; }
}

public record EntryDto
{
    public int HorseNumber { get; init; }
    public string HorseName { get; init; } = "";
    public string? HorseProfileId { get; init; }
    public EntryDataDto? EntryData { get; init; }
    public TrainingDataDto? TrainingData { get; init; }
    public string? StableComment { get; init; }
    public string? SyoinComment { get; init; }
    public PaddokDataDto? PaddokData { get; init; }
    public ResultDto? Result { get; init; }
}

public record EntryDataDto
{
    public string SexAge { get; init; } = "";
    public string Jockey { get; init; } = "";
    public string Trainer { get; init; } = "";
    public string Weight { get; init; } = "";
    public string? Odds { get; init; }
    public int? Popularity { get; init; }
    public string? HonshiMark { get; init; }
    public string? Comment { get; init; }
}
```

### 4.2 JSON出力形式（Python互換）

```json
{
  "race_info": {
    "race_id": "202505050401",
    "date": "20251214",
    "venue": "中山",
    "race_number": 1,
    "race_name": "2歳未勝利",
    "track": "ダ",
    "distance": 1200,
    "track_condition": "良",
    "weather": "晴",
    "start_time": "09:45"
  },
  "entries": [
    {
      "horse_number": 1,
      "horse_name": "サンプルホース",
      "horse_profile_id": "0936453",
      "entry_data": {
        "sex_age": "牡2",
        "jockey": "ルメール",
        "trainer": "藤沢和雄",
        "weight": "54.0",
        "odds": "2.5",
        "popularity": 1,
        "honshi_mark": "◎",
        "comment": "前走は好位から抜け出し..."
      },
      "training_data": {
        "evaluation": "A",
        "time": "52.3",
        "comment": "動き軽快"
      },
      "stable_comment": "状態は万全",
      "paddok_data": {
        "evaluation": "A",
        "comment": "落ち着いて周回"
      }
    }
  ],
  "meta": {
    "race_id": "202505050401",
    "data_version": "2.0",
    "created_at": "2025-12-14T10:00:00+09:00",
    "data_sources": {
      "seiseki": "取得済",
      "shutsuba": "取得済",
      "cyokyo": "取得済",
      "danwa": "取得済"
    }
  }
}
```

---

## 5. 設定ファイル

### 5.1 appsettings.json

```json
{
  "Serilog": {
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft": "Warning",
        "System": "Warning"
      }
    }
  },
  "Scraper": {
    "BaseUrl": "https://p.keibabook.co.jp",
    "UserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Timeout": 10,
    "MaxRetries": 3,
    "RetryDelay": 5.0,
    "DefaultSleepTime": 2.0,
    "Cookies": [
      {
        "Name": "example_cookie",
        "Value": "YOUR_COOKIE_VALUE",
        "Domain": "p.keibabook.co.jp",
        "Path": "/"
      }
    ]
  },
  "DataPaths": {
    "RootDir": "",
    "RaceIdsDir": "race_ids",
    "TempDir": "temp",
    "IntegratedDir": "integrated",
    "MarkdownDir": "organized",
    "LogsDir": "logs"
  },
  "Hangfire": {
    "ConnectionString": "Server=.;Database=KeibaCICD;Trusted_Connection=True;",
    "DashboardPath": "/hangfire"
  },
  "ConnectionStrings": {
    "DefaultConnection": "Server=.;Database=KeibaCICD;Trusted_Connection=True;TrustServerCertificate=True;"
  }
}
```

---

## 6. 移行手順

### 6.1 Phase別計画

| Phase | 内容 | 期間 | 成果物 |
|-------|------|------|--------|
| **Phase 1** | 設計 | 1日 | 詳細設計書 / DB統合設計書 / ロードマップ / レビューノート |
| **Phase 2** | プロジェクト基盤 | 4日 | ソリューション / NuGet設定 / ドメイン層 |
| **Phase 3** | Scraper/Parser実装 | 5日 | 7種類のパーサー、スクレイパー、DataFetcher |
| **Phase 4** | サービス層・CLI | 5日 | Services / DTO / CLI Commands |
| **Phase 5** | テスト・並行運用 | 5日 | 統合テスト / Python比較 / 本番移行準備 |

**合計: 約20日（4週間）**

> NOTE: フェーズ定義は `docs/design/implementation_roadmap.md` および
> `tasks/active/2025-12/task-251213-001-csharp-migration.md` と統一しています。

### 6.2 移行チェックリスト

- [ ] ソリューション作成
- [ ] ドメイン層実装
  - [ ] エンティティ定義
  - [ ] 値オブジェクト定義
  - [ ] 列挙型定義
- [ ] インフラ層実装
  - [ ] KeibaBookScraper
  - [ ] NitteiParser
  - [ ] SeisekiParser
  - [ ] SyutubaParser
  - [ ] CyokyoParser
  - [ ] DanwaParser
  - [ ] SyoinParser
  - [ ] PaddokParser
  - [ ] OptimizedDataFetcher
  - [ ] MarkdownGenerator
- [ ] アプリケーション層実装
  - [ ] ScrapingService
  - [ ] IntegrationService
  - [ ] MarkdownService
  - [ ] JockeyService
  - [ ] HorseProfileService
- [ ] CLI実装
  - [ ] ScheduleCommand
  - [ ] DataCommand
  - [ ] FullCommand
  - [ ] IntegrateCommand
  - [ ] MarkdownCommand
  - [ ] JockeyCommand
  - [ ] HorseProfileCommand
- [ ] テスト実装
- [ ] 並行運用テスト
- [ ] ドキュメント更新

---

## 7. 次のステップ

本設計書に基づき、以下の順序で実装を進める：

1. **まずソリューション・プロジェクト作成**
2. **ドメイン層から順に実装**
3. **Pythonと同等の機能をテストで検証**
4. **並行運用でデータ差分なしを確認**

設計書の承認後、実装作業を開始します。

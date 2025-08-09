# CursorAI向けプロンプト: JraVanSync - JRA-VAN Data Lab. → SQL Server データ同期システム実装

## 概要
JRA-VAN Data Lab.のデータをSQL Serverデータベースに同期する.NET C# Web API + コンソールアプリケーション「**JraVanSync**」を実装してください。RESTful APIで制御可能な同期エンジンと、コマンドラインから実行可能なクライアントを構築します。

## プロジェクト情報
- **アプリケーション名**: JraVanSync
- **プロジェクト名**: KeibaCICD.JraVanSync
- **フレームワーク**: .NET 8.0
- **言語**: C# 12
- **API**: ASP.NET Core Web API
- **データベース**: SQL Server 2019以降
- **アーキテクチャ**: Clean Architecture + DDD

## 実装要件

### 1. プロジェクト構造
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
└── docs/
```

### 2. Web API設計

#### 2.1 API エンドポイント一覧
```csharp
// Controllers/SyncController.cs
[ApiController]
[Route("api/[controller]")]
public class SyncController : ControllerBase
{
    // 同期ジョブの開始
    [HttpPost("jobs")]
    public async Task<ActionResult<SyncJobResponse>> StartSyncJob(
        [FromBody] SyncJobRequest request);
    
    // 同期ジョブの状態確認
    [HttpGet("jobs/{jobId}")]
    public async Task<ActionResult<SyncJobStatus>> GetJobStatus(Guid jobId);
    
    // 同期ジョブのキャンセル
    [HttpDelete("jobs/{jobId}")]
    public async Task<ActionResult> CancelJob(Guid jobId);
    
    // 実行中のジョブ一覧
    [HttpGet("jobs")]
    public async Task<ActionResult<List<SyncJobSummary>>> GetActiveJobs();
    
    // 同期履歴の取得
    [HttpGet("history")]
    public async Task<ActionResult<PagedResult<SyncHistory>>> GetSyncHistory(
        [FromQuery] SyncHistoryQuery query);
}

// Controllers/ConfigurationController.cs
[ApiController]
[Route("api/[controller]")]
public class ConfigurationController : ControllerBase
{
    // データ種別設定の取得
    [HttpGet("data-types")]
    public async Task<ActionResult<List<DataTypeConfiguration>>> GetDataTypes();
    
    // データ種別設定の更新
    [HttpPut("data-types/{dataType}")]
    public async Task<ActionResult> UpdateDataType(
        string dataType, 
        [FromBody] DataTypeConfiguration config);
    
    // データベース接続設定の取得
    [HttpGet("database")]
    public async Task<ActionResult<DatabaseConfiguration>> GetDatabaseConfig();
    
    // データベース接続設定の更新
    [HttpPut("database")]
    public async Task<ActionResult> UpdateDatabaseConfig(
        [FromBody] DatabaseConfiguration config);
    
    // 設定のエクスポート
    [HttpGet("export")]
    public async Task<ActionResult<CompleteConfiguration>> ExportConfiguration();
    
    // 設定のインポート
    [HttpPost("import")]
    public async Task<ActionResult> ImportConfiguration(
        [FromBody] CompleteConfiguration config);
}

// Controllers/HealthController.cs
[ApiController]
[Route("api/[controller]")]
public class HealthController : ControllerBase
{
    [HttpGet]
    public async Task<ActionResult<HealthCheckResult>> CheckHealth();
    
    [HttpGet("database")]
    public async Task<ActionResult<DatabaseHealthResult>> CheckDatabase();
    
    [HttpGet("jvlink")]
    public async Task<ActionResult<JVLinkHealthResult>> CheckJVLink();
}
```

#### 2.2 DTOモデル
```csharp
// DTOs/SyncJobRequest.cs
public class SyncJobRequest
{
    public List<string> DataTypes { get; set; } // ["RA", "SE", "UM", etc.]
    public Dictionary<string, DataTypeOptions> DataTypeOptions { get; set; }
    public bool ForceFullSync { get; set; } = false;
    public string JobName { get; set; }
}

public class DataTypeOptions
{
    public bool IncludeSetupData { get; set; }
    public bool IncludeNormalData { get; set; }
    public bool IncludeRealtimeData { get; set; }
    public DateTime? FromTime { get; set; }
}

// DTOs/SyncJobResponse.cs
public class SyncJobResponse
{
    public Guid JobId { get; set; }
    public string Status { get; set; }
    public DateTime StartedAt { get; set; }
    public string Message { get; set; }
    public Dictionary<string, string> Links { get; set; } // HATEOAS
}

// DTOs/DataTypeConfiguration.cs
public class DataTypeConfiguration
{
    public string DataType { get; set; }
    public string Description { get; set; }
    public bool IsEnabled { get; set; }
    public DataKindSettings DataKinds { get; set; }
    public DateTime DefaultFromTime { get; set; }
    public int Priority { get; set; }
}

public class DataKindSettings
{
    public bool SetupData { get; set; }
    public bool NormalData { get; set; }
    public bool RealtimeData { get; set; }
    public bool QuickData { get; set; }
}
```

### 3. コンソールアプリケーション

#### 3.1 コマンド設計
```csharp
// Program.cs
using System.CommandLine;

var rootCommand = new RootCommand("JRA-VAN データ同期ツール");

// syncコマンド
var syncCommand = new Command("sync", "データ同期を実行");
var dataTypesOption = new Option<string[]>(
    new[] { "--data-types", "-d" },
    "同期するデータ種別 (RA, SE, UM等)");
var fromDateOption = new Option<DateTime?>(
    new[] { "--from-date", "-f" },
    "取得開始日時");
var configFileOption = new Option<string>(
    new[] { "--config", "-c" },
    () => "appsettings.json",
    "設定ファイルパス");

syncCommand.AddOption(dataTypesOption);
syncCommand.AddOption(fromDateOption);
syncCommand.AddOption(configFileOption);

syncCommand.SetHandler(async (string[] dataTypes, DateTime? fromDate, string configFile) =>
{
    var app = BuildApplication(configFile);
    await app.ExecuteSyncAsync(dataTypes, fromDate);
}, dataTypesOption, fromDateOption, configFileOption);

// configコマンド
var configCommand = new Command("config", "設定管理");

var configListCommand = new Command("list", "設定一覧表示");
configCommand.AddCommand(configListCommand);

var configSetCommand = new Command("set", "設定値の変更");
var keyOption = new Option<string>("--key", "設定キー");
var valueOption = new Option<string>("--value", "設定値");
configSetCommand.AddOption(keyOption);
configSetCommand.AddOption(valueOption);
configCommand.AddCommand(configSetCommand);

// statusコマンド
var statusCommand = new Command("status", "実行状態確認");
var jobIdOption = new Option<Guid?>("--job-id", "ジョブID");
statusCommand.AddOption(jobIdOption);

rootCommand.AddCommand(syncCommand);
rootCommand.AddCommand(configCommand);
rootCommand.AddCommand(statusCommand);

return await rootCommand.InvokeAsync(args);
```

#### 3.2 コンソールアプリケーションサービス
```csharp
public class ConsoleApplication
{
    private readonly IApiClient _apiClient;
    private readonly IConsoleLogger _logger;
    private readonly IConfiguration _configuration;
    
    public async Task ExecuteSyncAsync(string[] dataTypes, DateTime? fromDate)
    {
        _logger.Info("同期処理を開始します...");
        
        // API経由で同期ジョブを開始
        var request = new SyncJobRequest
        {
            DataTypes = dataTypes?.ToList() ?? GetDefaultDataTypes(),
            DataTypeOptions = BuildDataTypeOptions(dataTypes, fromDate),
            JobName = $"Console Sync - {DateTime.Now:yyyy-MM-dd HH:mm:ss}"
        };
        
        var response = await _apiClient.StartSyncJobAsync(request);
        _logger.Info($"ジョブID: {response.JobId}");
        
        // 進捗監視
        await MonitorJobProgressAsync(response.JobId);
    }
    
    private async Task MonitorJobProgressAsync(Guid jobId)
    {
        var spinnerAnimation = new[] { "|", "/", "-", "\\" };
        var spinnerIndex = 0;
        
        while (true)
        {
            var status = await _apiClient.GetJobStatusAsync(jobId);
            
            Console.SetCursorPosition(0, Console.CursorTop);
            Console.Write($"\r[{spinnerAnimation[spinnerIndex++ % 4]}] {status.CurrentDataType}: {status.ProcessedCount}/{status.TotalCount} ({status.ProgressPercentage:F1}%)");
            
            if (status.IsCompleted)
            {
                Console.WriteLine();
                _logger.Info($"同期完了: 成功 {status.SuccessCount}, エラー {status.ErrorCount}");
                break;
            }
            
            if (status.IsFailed)
            {
                Console.WriteLine();
                _logger.Error($"同期失敗: {status.ErrorMessage}");
                break;
            }
            
            await Task.Delay(500);
        }
    }
}
```

### 4. 同期エンジン実装

#### 4.1 バックグラウンドサービス
```csharp
// Services/SyncJobService.cs
public class SyncJobService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly IJobQueue _jobQueue;
    private readonly ILogger<SyncJobService> _logger;
    
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var job = await _jobQueue.DequeueAsync(stoppingToken);
            
            if (job != null)
            {
                using var scope = _serviceProvider.CreateScope();
                var executor = scope.ServiceProvider.GetRequiredService<ISyncJobExecutor>();
                
                _ = Task.Run(async () =>
                {
                    try
                    {
                        await executor.ExecuteAsync(job, stoppingToken);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "ジョブ実行エラー: {JobId}", job.Id);
                    }
                }, stoppingToken);
            }
            
            await Task.Delay(1000, stoppingToken);
        }
    }
}

// Services/SyncJobExecutor.cs
public class SyncJobExecutor : ISyncJobExecutor
{
    private readonly IJVLinkService _jvLink;
    private readonly IDataImportService _importService;
    private readonly ISyncJobRepository _jobRepository;
    private readonly ILogger<SyncJobExecutor> _logger;
    
    public async Task ExecuteAsync(SyncJob job, CancellationToken cancellationToken)
    {
        await _jobRepository.UpdateStatusAsync(job.Id, SyncJobStatus.Running);
        
        try
        {
            foreach (var dataType in job.DataTypes)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    await _jobRepository.UpdateStatusAsync(job.Id, SyncJobStatus.Cancelled);
                    return;
                }
                
                await ProcessDataTypeAsync(job, dataType, cancellationToken);
            }
            
            await _jobRepository.UpdateStatusAsync(job.Id, SyncJobStatus.Completed);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "同期ジョブ失敗: {JobId}", job.Id);
            await _jobRepository.UpdateStatusAsync(job.Id, SyncJobStatus.Failed, ex.Message);
            throw;
        }
    }
    
    private async Task ProcessDataTypeAsync(
        SyncJob job, 
        string dataType, 
        CancellationToken cancellationToken)
    {
        var config = job.GetDataTypeOptions(dataType);
        var dataSpec = BuildDataSpec(dataType, config);
        var fromTime = config.FromTime?.ToString("yyyyMMddHHmmss") ?? "00000000000000";
        
        // JV-Linkでデータ取得開始
        var openResult = await _jvLink.OpenDataAsync(dataSpec, fromTime, DataOption.Normal);
        
        await _jobRepository.UpdateProgressAsync(job.Id, new ProgressInfo
        {
            CurrentDataType = dataType,
            TotalCount = openResult.DataCount,
            ProcessedCount = 0
        });
        
        var buffer = new List<JVData>();
        var processedCount = 0;
        
        // データ読み込みループ
        while (!cancellationToken.IsCancellationRequested)
        {
            var readResult = await _jvLink.ReadDataAsync();
            
            if (readResult.IsEof) break;
            
            buffer.Add(ParseJVData(dataType, readResult.Data));
            
            // バッファがいっぱいになったらバルクインサート
            if (buffer.Count >= 1000)
            {
                await _importService.BulkImportAsync(dataType, buffer);
                processedCount += buffer.Count;
                buffer.Clear();
                
                await _jobRepository.UpdateProgressAsync(job.Id, new ProgressInfo
                {
                    CurrentDataType = dataType,
                    TotalCount = openResult.DataCount,
                    ProcessedCount = processedCount
                });
            }
        }
        
        // 残りのデータを処理
        if (buffer.Any())
        {
            await _importService.BulkImportAsync(dataType, buffer);
        }
    }
}
```

### 5. データインポートサービス

#### 5.1 データ変換とインポート
```csharp
public interface IDataImportService
{
    Task BulkImportAsync(string dataType, IEnumerable<JVData> data);
}

public class DataImportService : IDataImportService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<DataImportService> _logger;
    
    public async Task BulkImportAsync(string dataType, IEnumerable<JVData> data)
    {
        var importerType = GetImporterType(dataType);
        var importer = _serviceProvider.GetRequiredService(importerType) as IDataImporter;
        
        if (importer == null)
        {
            throw new NotSupportedException($"データ種別 {dataType} はサポートされていません");
        }
        
        await importer.ImportAsync(data);
    }
    
    private Type GetImporterType(string dataType)
    {
        return dataType switch
        {
            "RA" => typeof(IRaceImporter),
            "SE" => typeof(IRaceHorseImporter),
            "UM" => typeof(IHorseMasterImporter),
            "KS" => typeof(IJockeyMasterImporter),
            "CH" => typeof(ITrainerMasterImporter),
            _ => throw new NotSupportedException($"Unknown data type: {dataType}")
        };
    }
}

// Importers/RaceImporter.cs
public class RaceImporter : IRaceImporter
{
    private readonly ISqlConnectionFactory _connectionFactory;
    private readonly ILogger<RaceImporter> _logger;
    
    public async Task ImportAsync(IEnumerable<JVData> data)
    {
        using var connection = await _connectionFactory.CreateConnectionAsync();
        using var transaction = connection.BeginTransaction();
        
        try
        {
            // DataTableを作成
            var dataTable = CreateRaceDataTable();
            
            foreach (var item in data.Cast<JV_RA_RACE>())
            {
                var row = dataTable.NewRow();
                MapRaceData(item, row);
                dataTable.Rows.Add(row);
            }
            
            // バルクインサート
            using var bulkCopy = new SqlBulkCopy(connection, SqlBulkCopyOptions.Default, transaction)
            {
                DestinationTableName = "Races",
                BatchSize = 1000
            };
            
            await bulkCopy.WriteToServerAsync(dataTable);
            await transaction.CommitAsync();
            
            _logger.LogInformation("レースデータ {Count} 件をインポートしました", data.Count());
        }
        catch (Exception ex)
        {
            await transaction.RollbackAsync();
            _logger.LogError(ex, "レースデータのインポートに失敗しました");
            throw;
        }
    }
    
    private DataTable CreateRaceDataTable()
    {
        var table = new DataTable();
        table.Columns.Add("RaceKey", typeof(string));
        table.Columns.Add("RaceDate", typeof(DateTime));
        table.Columns.Add("JyoCD", typeof(string));
        table.Columns.Add("RaceName", typeof(string));
        // ... 他のカラム
        return table;
    }
}
```

### 6. 設定管理

#### 6.1 設定ファイル構造
```json
// appsettings.json
{
  "ConnectionStrings": {
    "DefaultConnection": "Server=localhost;Database=JraVanSync;Trusted_Connection=true;TrustServerCertificate=true"
  },
  "JVLink": {
    "ServiceId": "YOUR_SERVICE_ID",
    "JVLinkPath": "C:\\JRA-VAN\\JV-Link\\JV-Link.exe",
    "DataPath": "C:\\JRA-VAN\\Data"
  },
  "Sync": {
    "BatchSize": 1000,
    "MaxConcurrentJobs": 3,
    "DefaultDataTypes": ["RA", "SE", "UM", "KS", "O1", "O2", "O3"]
  },
  "Api": {
    "BaseUrl": "http://localhost:5000",
    "ApiKey": "your-api-key"
  },
  "DataTypes": {
    "RA": {
      "Description": "レース詳細",
      "Priority": 1,
      "DefaultFromTime": "20240101000000",
      "DataKinds": {
        "Setup": true,
        "Normal": true,
        "Realtime": false
      }
    },
    "SE": {
      "Description": "馬毎レース情報",
      "Priority": 2,
      "DefaultFromTime": "20240101000000",
      "DataKinds": {
        "Setup": true,
        "Normal": true,
        "Realtime": true
      }
    }
    // ... 他のデータ種別
  }
}
```

#### 6.2 環境別設定
```json
// appsettings.Production.json
{
  "ConnectionStrings": {
    "DefaultConnection": "Server=prod-server;Database=JraVanSync;User Id=sa;Password=***;TrustServerCertificate=true"
  },
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft": "Warning"
    }
  }
}
```

### 7. 実行例

#### 7.1 コンソールからの実行
```bash
# 基本的な同期実行
jravansync sync --data-types RA SE UM

# 特定日付からの同期
jravansync sync --data-types RA --from-date 2024-01-01

# 設定ファイルを指定して実行
jravansync sync --config custom-settings.json

# ジョブ状態確認
jravansync status --job-id 123e4567-e89b-12d3-a456-426614174000

# 設定確認
jravansync config list

# 設定変更
jravansync config set --key "DataTypes:RA:Priority" --value "1"
```

#### 7.2 API経由での実行
```bash
# 同期ジョブ開始
curl -X POST http://localhost:5000/api/sync/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "dataTypes": ["RA", "SE"],
    "dataTypeOptions": {
      "RA": {
        "includeSetupData": true,
        "includeNormalData": true,
        "fromTime": "2024-01-01T00:00:00"
      }
    }
  }'

# ジョブ状態確認
curl http://localhost:5000/api/sync/jobs/123e4567-e89b-12d3-a456-426614174000

# 実行中ジョブ一覧
curl http://localhost:5000/api/sync/jobs

# ヘルスチェック
curl http://localhost:5000/api/health
```

### 8. Docker対応

#### 8.1 Dockerfile
```dockerfile
# Dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy project files
COPY ["src/JraVanSync.WebApi/JraVanSync.WebApi.csproj", "src/JraVanSync.WebApi/"]
COPY ["src/JraVanSync.Application/JraVanSync.Application.csproj", "src/JraVanSync.Application/"]
# ... 他のプロジェクト

RUN dotnet restore "src/JraVanSync.WebApi/JraVanSync.WebApi.csproj"

# Copy source code
COPY . .
WORKDIR "/src/src/JraVanSync.WebApi"
RUN dotnet build -c Release -o /app/build

FROM build AS publish
RUN dotnet publish -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=publish /app/publish .

# JV-Linkファイルをコピー（必要に応じて）
COPY ["JV-Link/", "/app/JV-Link/"]

EXPOSE 80
ENTRYPOINT ["dotnet", "JraVanSync.WebApi.dll"]
```

#### 8.2 docker-compose.yml
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "5000:80"
    environment:
      - ASPNETCORE_ENVIRONMENT=Production
      - ConnectionStrings__DefaultConnection=Server=db;Database=JraVanSync;User Id=sa;Password=YourStrong@Passw0rd;TrustServerCertificate=true
    depends_on:
      - db
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

  db:
    image: mcr.microsoft.com/mssql/server:2019-latest
    environment:
      - ACCEPT_EULA=Y
      - SA_PASSWORD=YourStrong@Passw0rd
    ports:
      - "1433:1433"
    volumes:
      - sqldata:/var/opt/mssql

  console:
    build:
      context: .
      dockerfile: Dockerfile.console
    environment:
      - Api__BaseUrl=http://api
    depends_on:
      - api
    volumes:
      - ./config:/app/config

volumes:
  sqldata:
```

### 9. ログとモニタリング

#### 9.1 構造化ログ（Serilog）
```csharp
// Program.cs
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Debug()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Information)
    .Enrich.FromLogContext()
    .Enrich.WithMachineName()
    .Enrich.WithProcessId()
    .WriteTo.Console(new RenderedCompactJsonFormatter())
    .WriteTo.File(
        new CompactJsonFormatter(),
        "logs/jravansync-.json",
        rollingInterval: RollingInterval.Day,
        retainedFileCountLimit: 30)
    .WriteTo.Seq("http://localhost:5341")
    .CreateLogger();

builder.Host.UseSerilog();
```

### 10. テストとCI/CD

#### 10.1 GitHub Actions
```yaml
# .github/workflows/build-and-test.yml
name: Build and Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup .NET
      uses: actions/setup-dotnet@v3
      with:
        dotnet-version: 8.0.x
    
    - name: Restore dependencies
      run: dotnet restore
    
    - name: Build
      run: dotnet build --no-restore -c Release
    
    - name: Test
      run: dotnet test --no-build -c Release --verbosity normal
    
    - name: Publish
      run: dotnet publish src/JraVanSync.WebApi/JraVanSync.WebApi.csproj -c Release -o ./publish
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: jravansync-api
        path: ./publish
```

このシステムは自動化とAPI経由での制御を前提とし、CI/CDパイプラインやスケジューラーとの統合が容易な設計となっています。
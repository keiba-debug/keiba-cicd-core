# データベース統合設計書

## 📋 概要

競馬ブックスクレイピングデータをSQL Serverに格納し、JRA-VANデータと統合するためのデータベース設計です。

---

## 1. スキーマ設計

### 1.1 スキーマ構成

```sql
-- 競馬ブックデータ用スキーマ
CREATE SCHEMA keibabook;

-- JRA-VANデータ用スキーマ（既存想定）
CREATE SCHEMA jravan;

-- 統合・分析用スキーマ
CREATE SCHEMA analysis;
```

### 1.2 テーブル構成

```
keibabook.                      # 競馬ブックスクレイピングデータ
├── Races                       # レース基本情報
├── Entries                     # 出走馬情報
├── TrainingData                # 調教データ
├── StableComments              # 厩舎コメント
├── PaddokData                  # パドック情報
├── Results                     # レース結果
├── Jockeys                     # 騎手情報
├── JockeyStats                 # 騎手成績
└── Horses                      # 馬プロファイル

analysis.                       # 統合・分析データ
├── IntegratedRaces             # 統合レースデータ
├── FeatureVectors              # 機械学習用特徴量
└── Predictions                 # 予測結果
```

---

## 1.3 設計方針（重複防止・更新）

- **データの粒度**: 競馬ブックのスクレイピング結果は「レース単位のスナップショット」として扱う
  - 例: `TrainingData` / `StableComments` / `PaddokData` は基本的に **(RaceId, HorseNumber) で1件** を想定
  - 将来的に履歴を保持したい場合は、日時や採取回次をキーに含める（要別途設計）
- **重複防止**: 取り込みの冪等性を担保するため、可能なテーブルは UNIQUE 制約を付与する
- **UpdatedAt**: DEFAULT だけでは更新時に値が変わらないため、以下いずれかに統一する
  - A) アプリケーション側（EF Core）の SaveChanges で `UpdatedAt = UtcNow` を必ずセット（推奨）
  - B) DBトリガーで更新（DB側に寄せる方針の場合）

---

## 2. テーブル定義

### 2.1 keibabook.Races

```sql
CREATE TABLE keibabook.Races (
    RaceId          CHAR(12)        PRIMARY KEY,
    Date            DATE            NOT NULL,
    Venue           NVARCHAR(10)    NOT NULL,
    RaceNumber      INT             NOT NULL,
    RaceName        NVARCHAR(100)   NOT NULL,
    Grade           NVARCHAR(10)    NULL,
    TrackType       NVARCHAR(10)    NOT NULL,   -- 芝/ダート/障害
    Distance        INT             NOT NULL,
    TrackCondition  NVARCHAR(10)    NULL,       -- 良/稍/重/不
    Weather         NVARCHAR(10)    NULL,
    StartTime       TIME            NULL,
    HeadCount       INT             NULL,
    RaceComment     NVARCHAR(MAX)   NULL,       -- 本誌の見解
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    UpdatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    
    INDEX IX_Races_Date (Date),
    INDEX IX_Races_Venue (Venue)
);
```

### 2.2 keibabook.Entries

```sql
CREATE TABLE keibabook.Entries (
    Id              INT             IDENTITY(1,1) PRIMARY KEY,
    RaceId          CHAR(12)        NOT NULL,
    HorseNumber     INT             NOT NULL,
    GateNumber      INT             NULL,
    HorseName       NVARCHAR(50)    NOT NULL,
    HorseId         CHAR(7)         NULL,       -- 馬ID
    SexAge          NVARCHAR(10)    NULL,
    Weight          DECIMAL(4,1)    NULL,       -- 斤量
    Jockey          NVARCHAR(30)    NULL,
    JockeyId        CHAR(5)         NULL,
    Trainer         NVARCHAR(30)    NULL,
    Owner           NVARCHAR(50)    NULL,
    Father          NVARCHAR(30)    NULL,
    Mother          NVARCHAR(30)    NULL,
    Odds            DECIMAL(10,1)   NULL,
    Popularity      INT             NULL,
    HonshiMark      NVARCHAR(2)     NULL,       -- ◎○▲△
    ShortComment    NVARCHAR(200)   NULL,       -- 短評
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    UpdatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Entries_Race FOREIGN KEY (RaceId) REFERENCES keibabook.Races(RaceId),
    CONSTRAINT UQ_Entries_Race_Horse UNIQUE (RaceId, HorseNumber),
    INDEX IX_Entries_HorseId (HorseId),
    INDEX IX_Entries_JockeyId (JockeyId)
);
```

### 2.3 keibabook.TrainingData

```sql
CREATE TABLE keibabook.TrainingData (
    Id              INT             IDENTITY(1,1) PRIMARY KEY,
    RaceId          CHAR(12)        NOT NULL,
    HorseNumber     INT             NOT NULL,
    Evaluation      NVARCHAR(5)     NULL,       -- A/B/C
    TrainingTime    NVARCHAR(20)    NULL,
    TrainingComment NVARCHAR(500)   NULL,
    TrainingPlace   NVARCHAR(20)    NULL,       -- 栗東/美浦
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    UpdatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Training_Race FOREIGN KEY (RaceId) REFERENCES keibabook.Races(RaceId),
    CONSTRAINT UQ_Training_Race_Horse UNIQUE (RaceId, HorseNumber),
    INDEX IX_Training_Race (RaceId)
);
```

### 2.4 keibabook.StableComments

```sql
CREATE TABLE keibabook.StableComments (
    Id              INT             IDENTITY(1,1) PRIMARY KEY,
    RaceId          CHAR(12)        NOT NULL,
    HorseNumber     INT             NOT NULL,
    Comment         NVARCHAR(1000)  NULL,
    Speaker         NVARCHAR(50)    NULL,       -- 調教師名等
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    UpdatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Stable_Race FOREIGN KEY (RaceId) REFERENCES keibabook.Races(RaceId),
    CONSTRAINT UQ_Stable_Race_Horse UNIQUE (RaceId, HorseNumber),
    INDEX IX_Stable_Race (RaceId)
);
```

### 2.5 keibabook.PaddokData

```sql
CREATE TABLE keibabook.PaddokData (
    Id              INT             IDENTITY(1,1) PRIMARY KEY,
    RaceId          CHAR(12)        NOT NULL,
    HorseNumber     INT             NOT NULL,
    Evaluation      NVARCHAR(5)     NULL,       -- A/B/C
    Comment         NVARCHAR(500)   NULL,
    HorseWeight     INT             NULL,       -- 馬体重
    WeightDiff      INT             NULL,       -- 増減
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    UpdatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Paddok_Race FOREIGN KEY (RaceId) REFERENCES keibabook.Races(RaceId),
    CONSTRAINT UQ_Paddok_Race_Horse UNIQUE (RaceId, HorseNumber),
    INDEX IX_Paddok_Race (RaceId)
);
```

### 2.6 keibabook.Results

```sql
CREATE TABLE keibabook.Results (
    Id              INT             IDENTITY(1,1) PRIMARY KEY,
    RaceId          CHAR(12)        NOT NULL,
    HorseNumber     INT             NOT NULL,
    FinishOrder     INT             NULL,
    FinishTime      NVARCHAR(20)    NULL,
    TimeDiff        NVARCHAR(20)    NULL,       -- 着差
    CornerPosition  NVARCHAR(20)    NULL,       -- 通過順
    LastFurlong     DECIMAL(4,1)    NULL,       -- 上がり3F
    JockeyComment   NVARCHAR(500)   NULL,       -- 騎手コメント
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    UpdatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_Results_Race FOREIGN KEY (RaceId) REFERENCES keibabook.Races(RaceId),
    CONSTRAINT UQ_Results_Race_Horse UNIQUE (RaceId, HorseNumber),
    INDEX IX_Results_Race (RaceId)
);
```

### 2.7 keibabook.Jockeys

```sql
CREATE TABLE keibabook.Jockeys (
    JockeyId        CHAR(5)         PRIMARY KEY,
    Name            NVARCHAR(30)    NOT NULL,
    NameKana        NVARCHAR(50)    NULL,
    Affiliation     NVARCHAR(20)    NULL,       -- 所属
    BirthDate       DATE            NULL,
    FirstRide       DATE            NULL,       -- 初騎乗日
    TotalWins       INT             NULL,
    TotalRides      INT             NULL,
    WinRate         DECIMAL(5,2)    NULL,
    PlaceRate       DECIMAL(5,2)    NULL,
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    UpdatedAt       DATETIME2       DEFAULT GETUTCDATE()
);
```

### 2.8 keibabook.JockeyStats

```sql
CREATE TABLE keibabook.JockeyStats (
    Id              INT             IDENTITY(1,1) PRIMARY KEY,
    JockeyId        CHAR(5)         NOT NULL,
    Year            INT             NOT NULL,
    Month           INT             NULL,       -- NULLの場合は年間
    Wins            INT             NOT NULL DEFAULT 0,
    Seconds         INT             NOT NULL DEFAULT 0,
    Thirds          INT             NOT NULL DEFAULT 0,
    Rides           INT             NOT NULL DEFAULT 0,
    WinRate         DECIMAL(5,2)    NULL,
    PlaceRate       DECIMAL(5,2)    NULL,
    LeadingRank     INT             NULL,       -- リーディング順位
    CreatedAt       DATETIME2       DEFAULT GETUTCDATE(),
    
    CONSTRAINT FK_JockeyStats_Jockey FOREIGN KEY (JockeyId) REFERENCES keibabook.Jockeys(JockeyId),
    INDEX IX_JockeyStats_Year (Year, Month)
);
```

---

## 3. Entity Framework Core設定

### 3.1 DbContext

```csharp
namespace KeibaCICD.Scraper.Infrastructure.Persistence;

public class KeibaDbContext : DbContext
{
    public KeibaDbContext(DbContextOptions<KeibaDbContext> options) : base(options) { }
    
    // 競馬ブックデータ
    public DbSet<Race> Races { get; set; }
    public DbSet<Entry> Entries { get; set; }
    public DbSet<TrainingData> TrainingData { get; set; }
    public DbSet<StableComment> StableComments { get; set; }
    public DbSet<PaddokData> PaddokData { get; set; }
    public DbSet<Result> Results { get; set; }
    public DbSet<Jockey> Jockeys { get; set; }
    public DbSet<JockeyStat> JockeyStats { get; set; }
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // スキーマ設定
        modelBuilder.HasDefaultSchema("keibabook");
        
        // Race設定
        modelBuilder.Entity<Race>(entity =>
        {
            entity.ToTable("Races");
            entity.HasKey(e => e.RaceId);
            entity.Property(e => e.RaceId).HasMaxLength(12).IsFixedLength();
            entity.Property(e => e.Venue).HasMaxLength(10);
            entity.Property(e => e.RaceName).HasMaxLength(100);
            entity.HasIndex(e => e.Date);
            entity.HasIndex(e => e.Venue);
        });
        
        // Entry設定
        modelBuilder.Entity<Entry>(entity =>
        {
            entity.ToTable("Entries");
            entity.HasKey(e => e.Id);
            entity.HasOne(e => e.Race)
                .WithMany(r => r.Entries)
                .HasForeignKey(e => e.RaceId);
            entity.HasIndex(e => new { e.RaceId, e.HorseNumber }).IsUnique();
        });
        
        // 他のエンティティも同様に設定...
    }
}
```

### 3.2 リポジトリ実装

```csharp
namespace KeibaCICD.Scraper.Infrastructure.Repositories;

public class SqlRaceRepository : IRaceRepository
{
    private readonly KeibaDbContext _context;
    private readonly ILogger<SqlRaceRepository> _logger;
    
    public SqlRaceRepository(KeibaDbContext context, ILogger<SqlRaceRepository> logger)
    {
        _context = context;
        _logger = logger;
    }
    
    public async Task<Race?> GetByIdAsync(string raceId, CancellationToken cancellationToken = default)
    {
        return await _context.Races
            .Include(r => r.Entries)
            .ThenInclude(e => e.TrainingData)
            .Include(r => r.Entries)
            .ThenInclude(e => e.StableComment)
            .Include(r => r.Entries)
            .ThenInclude(e => e.PaddokData)
            .FirstOrDefaultAsync(r => r.RaceId == raceId, cancellationToken);
    }
    
    public async Task<IEnumerable<Race>> GetByDateAsync(DateTime date, CancellationToken cancellationToken = default)
    {
        return await _context.Races
            .Where(r => r.Date == date)
            .Include(r => r.Entries)
            .OrderBy(r => r.Venue)
            .ThenBy(r => r.RaceNumber)
            .ToListAsync(cancellationToken);
    }
    
    public async Task SaveAsync(Race race, CancellationToken cancellationToken = default)
    {
        var existing = await _context.Races.FindAsync(new object[] { race.RaceId }, cancellationToken);
        
        if (existing == null)
        {
            _context.Races.Add(race);
        }
        else
        {
            _context.Entry(existing).CurrentValues.SetValues(race);
        }
        
        await _context.SaveChangesAsync(cancellationToken);
        _logger.LogDebug("レース保存: {RaceId}", race.RaceId);
    }
    
    public async Task SaveEntriesAsync(string raceId, IEnumerable<Entry> entries, CancellationToken cancellationToken = default)
    {
        // 既存エントリを削除して再登録（全更新）
        var existingEntries = await _context.Entries
            .Where(e => e.RaceId == raceId)
            .ToListAsync(cancellationToken);
        
        _context.Entries.RemoveRange(existingEntries);
        _context.Entries.AddRange(entries);
        
        await _context.SaveChangesAsync(cancellationToken);
        _logger.LogDebug("出走馬保存: {RaceId}, {Count}頭", raceId, entries.Count());
    }
}
```

---

## 4. JRA-VAN連携

### 4.1 統合ビュー

```sql
-- 統合レースビュー
CREATE VIEW analysis.vw_IntegratedRaces AS
SELECT 
    j.RaceId,
    j.Date,
    j.Venue,
    j.RaceNumber,
    j.RaceName,
    j.Grade,
    j.Track AS TrackType,
    j.Distance,
    j.TrackCondition,
    j.Weather,
    j.StartTime,
    -- 競馬ブック拡張データ
    k.RaceComment AS KbRaceComment
FROM jravan.Races j
LEFT JOIN keibabook.Races k ON j.RaceId = k.RaceId;

-- 統合出走馬ビュー
CREATE VIEW analysis.vw_IntegratedEntries AS
SELECT 
    je.RaceId,
    je.HorseNumber,
    je.HorseName,
    je.SexAge,
    je.Weight,
    je.Jockey,
    je.Trainer,
    je.Odds,
    je.Popularity,
    -- JRA-VAN成績
    je.TotalWins,
    je.TotalRuns,
    -- 競馬ブック独自データ
    ke.HonshiMark,
    ke.ShortComment,
    kt.Evaluation AS TrainingEval,
    kt.TrainingComment,
    ks.Comment AS StableComment,
    kp.Evaluation AS PaddokEval,
    kp.Comment AS PaddokComment
FROM jravan.Entries je
LEFT JOIN keibabook.Entries ke ON je.RaceId = ke.RaceId AND je.HorseNumber = ke.HorseNumber
LEFT JOIN keibabook.TrainingData kt ON je.RaceId = kt.RaceId AND je.HorseNumber = kt.HorseNumber
LEFT JOIN keibabook.StableComments ks ON je.RaceId = ks.RaceId AND je.HorseNumber = ks.HorseNumber
LEFT JOIN keibabook.PaddokData kp ON je.RaceId = kp.RaceId AND je.HorseNumber = kp.HorseNumber;
```

### 4.2 データ同期サービス

```csharp
namespace KeibaCICD.Scraper.Application.Services;

public class DbSyncService : IDbSyncService
{
    private readonly IRaceRepository _raceRepository;
    private readonly ILogger<DbSyncService> _logger;
    
    public async Task SyncScrapedDataAsync(
        IntegratedRaceDto raceData,
        CancellationToken cancellationToken = default)
    {
        var race = MapToEntity(raceData);
        await _raceRepository.SaveAsync(race, cancellationToken);
        
        var entries = raceData.Entries.Select(e => MapToEntry(raceData.RaceInfo.RaceId, e));
        await _raceRepository.SaveEntriesAsync(raceData.RaceInfo.RaceId, entries, cancellationToken);
        
        // 調教データ
        foreach (var entry in raceData.Entries.Where(e => e.TrainingData != null))
        {
            var training = MapToTrainingData(raceData.RaceInfo.RaceId, entry);
            await _raceRepository.SaveTrainingDataAsync(training, cancellationToken);
        }
        
        // 厩舎コメント
        foreach (var entry in raceData.Entries.Where(e => e.StableComment != null))
        {
            var comment = MapToStableComment(raceData.RaceInfo.RaceId, entry);
            await _raceRepository.SaveStableCommentAsync(comment, cancellationToken);
        }
        
        _logger.LogInformation("DB同期完了: {RaceId}", raceData.RaceInfo.RaceId);
    }
}
```

---

## 5. マイグレーション

### 5.1 初期マイグレーション

```bash
# マイグレーション作成
dotnet ef migrations add InitialCreate -p KeibaCICD.Scraper.Infrastructure -s KeibaCICD.Scraper.CLI

# マイグレーション適用
dotnet ef database update -p KeibaCICD.Scraper.Infrastructure -s KeibaCICD.Scraper.CLI
```

### 5.2 既存JSONからの移行スクリプト

```csharp
public class JsonToDbMigrator
{
    public async Task MigrateAsync(string jsonDir, CancellationToken cancellationToken = default)
    {
        var files = Directory.GetFiles(jsonDir, "integrated_*.json", SearchOption.AllDirectories);
        
        foreach (var file in files)
        {
            var json = await File.ReadAllTextAsync(file, cancellationToken);
            var raceData = JsonSerializer.Deserialize<IntegratedRaceDto>(json);
            
            if (raceData != null)
            {
                await _dbSyncService.SyncScrapedDataAsync(raceData, cancellationToken);
            }
        }
    }
}
```

---

## 6. 運用設定

### 6.1 接続文字列

```json
{
  "ConnectionStrings": {
    "KeibaDb": "Server=.;Database=KeibaCICD;Trusted_Connection=True;TrustServerCertificate=True;"
  }
}
```

### 6.2 DI設定

```csharp
public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddDatabaseServices(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddDbContext<KeibaDbContext>(options =>
            options.UseSqlServer(configuration.GetConnectionString("KeibaDb")));
        
        services.AddScoped<IRaceRepository, SqlRaceRepository>();
        services.AddScoped<IJockeyRepository, SqlJockeyRepository>();
        services.AddScoped<IDbSyncService, DbSyncService>();
        
        return services;
    }
}
```

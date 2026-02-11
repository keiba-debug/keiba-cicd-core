# IntegrationService 詳細設計書

## 📋 概要

`RaceDataIntegrator`（Python版）をC#に移植するための詳細設計。
7種類のデータソース（shutsuba, cyokyo, danwa, seiseki, syoin, paddok, nittei）を統合し、
1レース = 1 JSONファイルとして出力する。

---

## 1. クラス設計

### 1.1 IntegrationService

```csharp
namespace KeibaCICD.Scraper.Application.Services;

public class IntegrationService : IIntegrationService
{
    private readonly ILogger<IntegrationService> _logger;
    private readonly DataPathOptions _pathOptions;
    private readonly IFileService _fileService;
    
    // race_idと実際の開催日のマッピング
    private readonly Dictionary<string, string> _actualDateMap = new();
    private readonly Dictionary<string, string> _venueNameMap = new();
    private readonly Dictionary<string, string> _raceIdToDateMap = new();
    
    public IntegrationService(
        ILogger<IntegrationService> logger,
        IOptions<DataPathOptions> pathOptions,
        IFileService fileService)
    {
        _logger = logger;
        _pathOptions = pathOptions.Value;
        _fileService = fileService;
        
        LoadActualDates();
    }
    
    // メインエントリ
    public async Task<IntegratedRaceData?> CreateIntegratedFileAsync(
        string raceId, 
        bool save = true,
        RaceIdsData? raceIdsData = null,
        CancellationToken cancellationToken = default);
    
    // バッチ処理
    public async Task<IntegrationSummary> BatchCreateIntegratedFilesAsync(
        string dateStr,
        CancellationToken cancellationToken = default);
    
    // 結果更新
    public async Task<bool> UpdateWithResultsAsync(
        string raceId,
        CancellationToken cancellationToken = default);
}
```

### 1.2 インターフェース定義

```csharp
public interface IIntegrationService
{
    Task<IntegratedRaceData?> CreateIntegratedFileAsync(
        string raceId, 
        bool save = true,
        RaceIdsData? raceIdsData = null,
        CancellationToken cancellationToken = default);
    
    Task<IntegrationSummary> BatchCreateIntegratedFilesAsync(
        string dateStr,
        CancellationToken cancellationToken = default);
    
    Task<bool> UpdateWithResultsAsync(
        string raceId,
        CancellationToken cancellationToken = default);
}
```

---

## 2. データモデル

### 2.1 統合レースデータ

```csharp
namespace KeibaCICD.Scraper.Domain.Models;

public class IntegratedRaceData
{
    public RaceMetadata Meta { get; set; } = new();
    public RaceInfo RaceInfo { get; set; } = new();
    public List<IntegratedEntry> Entries { get; set; } = new();
    public RaceAnalysis? Analysis { get; set; }
    public TenkaiData? TenkaiData { get; set; }
    public string? RaceComment { get; set; }
    public List<PayoutInfo>? Payouts { get; set; }
    public LapsData? Laps { get; set; }
}

public class RaceMetadata
{
    public string RaceId { get; set; } = string.Empty;
    public string DataVersion { get; set; } = "2.0";
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    public DataSourceStatus DataSources { get; set; } = new();
}

public class DataSourceStatus
{
    public string Seiseki { get; set; } = string.Empty;
    public string Syutuba { get; set; } = string.Empty;
    public string Cyokyo { get; set; } = string.Empty;
    public string Danwa { get; set; } = string.Empty;
    public string Nittei { get; set; } = string.Empty;
    public string Syoin { get; set; } = string.Empty;
    public string Paddok { get; set; } = string.Empty;
}
```

### 2.2 統合エントリ（馬データ）

```csharp
public class IntegratedEntry
{
    public int HorseNumber { get; set; }
    public string HorseName { get; set; } = string.Empty;
    public string? HorseId { get; set; }
    
    public EntryData EntryData { get; set; } = new();
    public TrainingData? TrainingData { get; set; }
    public StableComment? StableComment { get; set; }
    public RaceResult? Result { get; set; }
    public PreviousRaceInterview? PreviousRaceInterview { get; set; }
    public PaddockInfo? PaddockInfo { get; set; }
    public PastPerformances? PastPerformances { get; set; }
    public HistoryFeatures? HistoryFeatures { get; set; }
}

public class EntryData
{
    public string? Weight { get; set; }
    public string? WeightDiff { get; set; }
    public string? Jockey { get; set; }
    public string? JockeyId { get; set; }
    public string? Trainer { get; set; }
    public string? Owner { get; set; }
    public string? ShortComment { get; set; }
    public string? Odds { get; set; }
    public int? OddsRank { get; set; }
    public string? AiIndex { get; set; }
    public string? AiRank { get; set; }
    public string? PopularityIndex { get; set; }
    public string? Age { get; set; }
    public string? Sex { get; set; }
    public string? Waku { get; set; }
    public string? Rating { get; set; }
    public string? HorseWeight { get; set; }
    public string? Father { get; set; }
    public string? Mother { get; set; }
    public string? MotherFather { get; set; }
    public string? HonshiMark { get; set; }
    public int MarkPoint { get; set; }
    public Dictionary<string, string>? MarksByPerson { get; set; }
    public int AggregateMarkPoint { get; set; }
}

public class TrainingData
{
    public string? LastTraining { get; set; }
    public List<string>? TrainingTimes { get; set; }
    public string? TrainingCourse { get; set; }
    public string? Evaluation { get; set; }
    public string? TrainerComment { get; set; }
    public string? AttackExplanation { get; set; }
    public string? ShortReview { get; set; }
    public string? TrainingLoad { get; set; }
    public string? TrainingRank { get; set; }
    public string? TrainingArrow { get; set; }
}

public class StableComment
{
    public string? Date { get; set; }
    public string? Comment { get; set; }
    public string? Condition { get; set; }
    public string? TargetRace { get; set; }
    public string? Trainer { get; set; }
}

public class RaceResult
{
    public string? FinishPosition { get; set; }
    public string? Time { get; set; }
    public string? Margin { get; set; }
    public string? Last3F { get; set; }
    public string? CornerPositions { get; set; }
    public decimal? PrizeMoney { get; set; }
    public string? HorseWeight { get; set; }
    public string? HorseWeightDiff { get; set; }
    public Dictionary<string, object>? RawData { get; set; }
}

public class PreviousRaceInterview
{
    public string? Jockey { get; set; }
    public string? Comment { get; set; }
    public string? Interview { get; set; }
    public string? NextRaceMemo { get; set; }
    public string? FinishPosition { get; set; }
    public string? PreviousRaceMention { get; set; }
}

public class PaddockInfo
{
    public string? Mark { get; set; }
    public int? MarkScore { get; set; }
    public string? Comment { get; set; }
    public string? Condition { get; set; }
    public string? Temperament { get; set; }
    public string? Gait { get; set; }
    public string? HorseWeight { get; set; }
    public string? WeightChange { get; set; }
    public string? Evaluator { get; set; }
}
```

---

## 3. 統合ロジック

### 3.1 データマージフロー

```
┌─────────────┐
│  race_id    │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│                    データ読み込み                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ shutsuba│ │ cyokyo  │ │  danwa  │ │ seiseki │        │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘        │
│       │          │          │          │                 │
│  ┌─────────┐ ┌─────────┐                                 │
│  │  syoin  │ │ paddok  │                                 │
│  └────┬────┘ └────┬────┘                                 │
└───────┼──────────┼──────────┼──────────┼─────────────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
┌──────────────────────────────────────────────────────────┐
│              馬番（horse_number）で照合                   │
│                                                          │
│  foreach (entry in shutsuba.Entries)                     │
│  {                                                       │
│      // 馬番でマッチング                                  │
│      training = FindByHorseNumber(cyokyo, entry.Number); │
│      comment = FindByHorseNumber(danwa, entry.Number);   │
│      result = FindByHorseNumber(seiseki, entry.Number);  │
│      interview = FindByHorseNumber(syoin, entry.Number); │
│      paddock = FindByHorseNumber(paddok, entry.Number);  │
│                                                          │
│      mergedEntry = Merge(entry, training, comment, ...); │
│  }                                                       │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│              統合データ（IntegratedRaceData）             │
└──────────────────────────────────────────────────────────┘
```

### 3.2 馬番照合ロジック

```csharp
private IntegratedEntry MergeHorseData(
    int horseNumber,
    SyutubaEntry syutubaEntry,
    CyokyoData? cyokyoData,
    DanwaData? danwaData,
    SeisekiData? seisekiData,
    SyoinData? syoinData,
    PaddokData? paddokData)
{
    var entry = new IntegratedEntry
    {
        HorseNumber = horseNumber,
        HorseName = ExtractHorseName(syutubaEntry),
        HorseId = syutubaEntry.HorseId,
        EntryData = MapEntryData(syutubaEntry)
    };
    
    // 調教データの照合（馬番でマッチング）
    if (cyokyoData != null)
    {
        entry.TrainingData = FindTrainingByHorseNumber(cyokyoData, horseNumber);
    }
    
    // 厩舎談話の照合
    if (danwaData != null)
    {
        entry.StableComment = FindCommentByHorseNumber(danwaData, horseNumber);
    }
    
    // 成績データの照合
    if (seisekiData != null)
    {
        entry.Result = FindResultByHorseNumber(seisekiData, horseNumber);
    }
    
    // 前走インタビューの照合
    if (syoinData != null)
    {
        entry.PreviousRaceInterview = FindInterviewByHorseNumber(syoinData, horseNumber);
    }
    
    // パドック情報の照合
    if (paddokData != null)
    {
        entry.PaddockInfo = FindPaddockByHorseNumber(paddokData, horseNumber);
    }
    
    return entry;
}
```

### 3.3 馬番の安全な数値変換

> **重要**: パーサーごとに馬番の型が異なる（string/int混在）。
> 詳細は [`parser_output_schemas.md` - 0.1 馬番の型統一ルール](./parser_output_schemas.md) を参照。
> IntegrationServiceでは **常に int horseNumber に正規化** する。

```csharp
/// <summary>
/// 全角数字を含む文字列を安全にintに変換
/// Python版の _to_int_safe に対応
/// 入力は string / int どちらでも受け付け、int?に正規化
/// </summary>
private static int? ToIntSafe(object? value)
{
    if (value == null) return null;
    
    var str = value.ToString() ?? "";
    
    // 全角→半角変換
    var halfWidth = ConvertToHalfWidth(str);
    
    // 数字のみ抽出
    var digitsOnly = new string(halfWidth.Where(char.IsDigit).ToArray());
    
    if (int.TryParse(digitsOnly, out var result))
    {
        return result;
    }
    
    return null;
}

private static string ConvertToHalfWidth(string input)
{
    var fullWidth = "０１２３４５６７８９";
    var halfWidth = "0123456789";
    
    var result = new StringBuilder(input.Length);
    foreach (var c in input)
    {
        var index = fullWidth.IndexOf(c);
        result.Append(index >= 0 ? halfWidth[index] : c);
    }
    return result.ToString();
}
```

---

## 4. ファイルパス管理

### 4.1 パス生成ロジック

```csharp
private string GetIntegratedFilePath(string raceId)
{
    var filename = $"integrated_{raceId}.json";
    
    // 実際の開催日を取得
    var actualDate = _raceIdToDateMap.GetValueOrDefault(raceId) 
                  ?? _actualDateMap.GetValueOrDefault(raceId)
                  ?? (raceId.Length >= 8 ? raceId[..8] : "00000000");
    
    var year = actualDate[..4];
    var month = actualDate[4..6];
    var day = actualDate[6..8];
    
    // 出力先: integrated/YYYY/MM/DD/temp
    // NOTE: ディレクトリ名は appsettings.json の DataPaths に従う（直書きしない）
    var outputDir = Path.Combine(
        _pathOptions.RootDir,
        _pathOptions.IntegratedDir,
        year, month, day,
        _pathOptions.TempDir);
    
    return Path.Combine(outputDir, filename);
}
```

### 4.2 日付マッピングの読み込み

```csharp
private void LoadActualDates()
{
    var raceIdsDir = Path.Combine(_pathOptions.RootDir, _pathOptions.RaceIdsDir);
    if (!Directory.Exists(raceIdsDir)) return;
    
    foreach (var file in Directory.GetFiles(raceIdsDir, "*_info.json"))
    {
        var fileName = Path.GetFileNameWithoutExtension(file);
        var dateStr = fileName.Replace("_info", "");
        
        try
        {
            var json = File.ReadAllText(file);
            var data = JsonSerializer.Deserialize<RaceIdsData>(json);
            
            foreach (var (kaisaiName, races) in data?.KaisaiData ?? new())
            {
                // 開催名から競馬場名を抽出
                var venueName = ExtractVenueName(kaisaiName);
                
                foreach (var race in races)
                {
                    if (!string.IsNullOrEmpty(race.RaceId))
                    {
                        _actualDateMap[race.RaceId] = dateStr;
                        if (!string.IsNullOrEmpty(venueName))
                        {
                            _venueNameMap[race.RaceId] = venueName;
                        }
                    }
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to load {File}", file);
        }
    }
}

private static string? ExtractVenueName(string kaisaiName)
{
    var venues = new[] { "札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉" };
    return venues.FirstOrDefault(v => kaisaiName.Contains(v));
}
```

---

## 5. バッチ処理

### 5.1 日付指定バッチ

```csharp
public async Task<IntegrationSummary> BatchCreateIntegratedFilesAsync(
    string dateStr,
    CancellationToken cancellationToken = default)
{
    _logger.LogInformation("統合処理開始: {Date}", dateStr);
    
    // race_ids ファイル読み込み
    var raceIdsFile = GetRaceIdsFilePath(dateStr);
    if (!File.Exists(raceIdsFile))
    {
        _logger.LogError("レースIDファイルが見つかりません: {Date}", dateStr);
        return new IntegrationSummary { Success = false, Error = "No race IDs file" };
    }
    
    var raceIdsData = await _fileService.ReadJsonAsync<RaceIdsData>(raceIdsFile, cancellationToken);
    
    // race_idリストを収集
    var raceIds = new List<string>();
    _raceIdToDateMap.Clear();
    
    foreach (var (venue, races) in raceIdsData?.KaisaiData ?? new())
    {
        foreach (var race in races)
        {
            if (!string.IsNullOrEmpty(race.RaceId))
            {
                raceIds.Add(race.RaceId);
                _raceIdToDateMap[race.RaceId] = dateStr;
            }
        }
    }
    
    // 統合処理実行
    var successCount = 0;
    var failedCount = 0;
    
    foreach (var raceId in raceIds)
    {
        try
        {
            var result = await CreateIntegratedFileAsync(raceId, true, raceIdsData, cancellationToken);
            if (result != null)
            {
                successCount++;
                _logger.LogInformation("[OK] 統合完了: {RaceId}", raceId);
            }
            else
            {
                failedCount++;
                _logger.LogError("[ERROR] 統合失敗: {RaceId}", raceId);
            }
        }
        catch (Exception ex)
        {
            failedCount++;
            _logger.LogError(ex, "[ERROR] 統合失敗: {RaceId}", raceId);
        }
    }
    
    return new IntegrationSummary
    {
        Success = true,
        Date = dateStr,
        TotalRaces = raceIds.Count,
        SuccessCount = successCount,
        FailedCount = failedCount,
        SuccessRate = raceIds.Count > 0 ? (successCount * 100.0 / raceIds.Count) : 0
    };
}
```

---

## 6. エラーハンドリング

### 6.1 データ欠損時の処理

| データソース | 必須 | 欠損時の処理 |
|-------------|------|-------------|
| shutsuba | ✅ 必須 | **統合失敗（null返却）**。エラーログ出力。統合JSONは作成しない |
| cyokyo | ❌ 任意 | TrainingData = null |
| danwa | ❌ 任意 | StableComment = null |
| seiseki | ❌ 任意 | Result = null |
| syoin | ❌ 任意 | PreviousRaceInterview = null |
| paddok | ❌ 任意 | PaddockInfo = null |

> NOTE: バッチ処理では `CreateIntegratedFileAsync(...) == null` を失敗としてカウントする。
> shutsuba欠損時に「空データで成功扱い」になると検知できないため、必須データは失敗扱いに統一する。

### 6.2 例外処理パターン

```csharp
private async Task<T?> LoadRaceDataSafe<T>(string raceId, DataType dataType) where T : class
{
    try
    {
        var filePath = GetJsonFilePath(dataType, raceId);
        if (!File.Exists(filePath))
        {
            _logger.LogDebug("{DataType}データなし: {RaceId}", dataType, raceId);
            return null;
        }
        
        return await _fileService.ReadJsonAsync<T>(filePath);
    }
    catch (JsonException ex)
    {
        _logger.LogWarning(ex, "{DataType}データのパース失敗: {RaceId}", dataType, raceId);
        return null;
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, "{DataType}データの読み込み失敗: {RaceId}", dataType, raceId);
        return null;
    }
}
```

---

## 7. JSON出力形式

### 7.1 Python版互換のシリアライズ設定

```csharp
private static readonly JsonSerializerOptions JsonOptions = new()
{
    WriteIndented = true,
    Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping, // 日本語エスケープ回避
    PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
};
```

### 7.2 互換の合格基準（固定）

Python版との差分検証を「ブレない」ように、互換の基準を先に固定する。

- **必須一致（Must）**
  - `meta.race_id`
  - `race_info` の主要項目（date/venue/race_number 等、運用で参照するもの）
  - `entries[].horse_number` / `entries[].horse_name`
  - **必須データ（shutsuba）由来の項目**
- **許容差分（May）**
  - `null` と「キー省略」の違い（ただし “同じ意味” と扱う場合に限る）
  - 並び順（配列の順序を horse_number で正規化できる前提）
- **不一致扱い（Fail）**
  - 必須項目の欠損（例: race_id, entries が空、horse_number が不正）
  - 異なる race_id の混入

> NOTE: `DefaultIgnoreCondition = WhenWritingNull` は “キー省略” を選択する設定。
> Python版が `null` を出す場合は差分が出るため、比較用の正規化（null/未設定の同一視）を検証側で実施する。

### 7.3 DataSources ステータス値（固定）

`meta.data_sources` の値は文字列で保持し、以下に限定する（ログ/再実行判断に使う）。

| 値 | 意味 | 設定条件 |
|----|------|----------|
| `取得済` | データが読み込めた | ファイル存在 + JSON読み込み成功 |
| `未取得` | データが存在しない | ファイルが存在しない |
| `パース失敗` | 形式不正 | JSON例外（JsonException） |
| `必須欠損` | 必須データ不足 | shutsuba が存在しない/読めない |

> NOTE: 任意データは `未取得`/`パース失敗` でも統合は継続する。

### 7.4 出力例

```json
{
  "meta": {
    "race_id": "202412150501",
    "data_version": "2.0",
    "created_at": "2024-12-15T10:30:00",
    "updated_at": "2024-12-15T10:30:00",
    "data_sources": {
      "seiseki": "未取得",
      "syutuba": "取得済",
      "cyokyo": "取得済",
      "danwa": "取得済",
      "syoin": "未取得",
      "paddok": "未取得"
    }
  },
  "race_info": {
    "date": "2024/12/15",
    "venue": "東京",
    "race_number": 1,
    "race_name": "2歳未勝利",
    "distance": 1600,
    "track": "芝",
    "post_time": "10:05"
  },
  "entries": [
    {
      "horse_number": 1,
      "horse_name": "サンプルホース",
      "horse_id": "2022100001",
      "entry_data": { ... },
      "training_data": { ... },
      "stable_comment": { ... }
    }
  ],
  "analysis": { ... }
}
```

---

## 8. 依存関係

```
IntegrationService
    ├── IFileService (ファイル読み書き)
    ├── ILogger<IntegrationService>
    └── IOptions<DataPathOptions>
```

---

## 9. 実装優先順位

| 優先度 | メソッド | 理由 |
|-------|---------|------|
| 1 | CreateIntegratedFileAsync | コア機能 |
| 2 | MergeHorseData | データ統合ロジック |
| 3 | BatchCreateIntegratedFilesAsync | 運用で必須 |
| 4 | LoadActualDates | 日付マッピング |
| 5 | UpdateWithResultsAsync | 結果反映 |

---

## 10. テスト観点

1. **馬番照合テスト**: 全角/半角数字の混在
2. **データ欠損テスト**: 任意データがnullの場合
3. **ファイルパステスト**: 実際の開催日マッピング
4. **JSON互換性テスト**: Python版との出力比較
5. **バッチ処理テスト**: 複数レースの統合

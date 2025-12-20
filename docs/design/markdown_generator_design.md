# MarkdownGenerator 詳細設計書

## 📋 概要

`MarkdownGenerator`（Python版 約1400行）をC#に移植するための詳細設計。
統合済みレースデータ（IntegratedRaceData）からMarkdown形式のレースレポートを生成する。

---

## 1. クラス設計

### 1.1 MarkdownService

```csharp
namespace KeibaCICD.Scraper.Application.Services;

public class MarkdownService : IMarkdownService
{
    private readonly ILogger<MarkdownService> _logger;
    private readonly DataPathOptions _pathOptions;
    private readonly IFileService _fileService;
    
    // マッピングキャッシュ
    private readonly Dictionary<string, string> _actualDateMap = new();
    private readonly Dictionary<string, string> _venueNameMap = new();
    private readonly Dictionary<string, string> _startTimeMap = new();
    private readonly Dictionary<string, RaceInfoCache> _raceInfoMap = new();
    
    public MarkdownService(
        ILogger<MarkdownService> logger,
        IOptions<DataPathOptions> pathOptions,
        IFileService fileService)
    {
        _logger = logger;
        _pathOptions = pathOptions.Value;
        _fileService = fileService;
        
        LoadActualDates();
    }
    
    // メインエントリ
    public async Task<string> GenerateRaceMarkdownAsync(
        IntegratedRaceData raceData,
        bool save = true,
        CancellationToken cancellationToken = default);
    
    // バッチ生成
    public async Task<MarkdownGenerationSummary> BatchGenerateAsync(
        string? integratedDir = null,
        CancellationToken cancellationToken = default);
}
```

### 1.2 セクション生成クラス群

```csharp
// セクション生成を分離（単一責任の原則）
public interface IMarkdownSectionGenerator
{
    string Generate(IntegratedRaceData raceData);
}

public class HeaderGenerator : IMarkdownSectionGenerator { }
public class RaceInfoGenerator : IMarkdownSectionGenerator { }
public class RaceCommentGenerator : IMarkdownSectionGenerator { }
public class EntryTableGenerator : IMarkdownSectionGenerator { }
public class TrainingCommentsGenerator : IMarkdownSectionGenerator { }
public class TenkaiSectionGenerator : IMarkdownSectionGenerator { }
public class PaddockSectionGenerator : IMarkdownSectionGenerator { }
public class ResultsTableGenerator : IMarkdownSectionGenerator { }
public class RaceFlowMermaidGenerator : IMarkdownSectionGenerator { }
public class ResultsSummaryGenerator : IMarkdownSectionGenerator { }
public class PayoutsSectionGenerator : IMarkdownSectionGenerator { }
public class LapsSectionGenerator : IMarkdownSectionGenerator { }
public class LinksGenerator : IMarkdownSectionGenerator { }
public class FooterGenerator : IMarkdownSectionGenerator { }
```

---

## 2. セクション構成

### 2.1 生成順序

```
1. Header           # 東京1R (未勝利) サンプルステークス
2. RaceInfo         ## 📋 レース情報
3. RaceComment      ## 📰 本紙の見解
4. EntryTable       ## 🐎 出走表
5. TrainingComments ## 📝 調教・厩舎情報
6. TenkaiSection    ## 🏃 展開予想
7. PaddockSection   ## 🐴 パドック情報
8. [結果データがある場合]
   - ResultsTable   ## 🏁 レース結果
   - RaceFlowMermaid ## 📊 レース展開
   - ResultsSummary ## 🧾 成績サマリー
   - PayoutsSection ## 💴 配当情報
   - LapsSection    ## ⏱ ラップ/ペース
9. LinksSection     ## 🔗 関連リンク
10. Footer          --- データ情報
11. AdditionalSection # 追記
```

---

## 3. 各セクションの詳細設計

### 3.1 Header（ヘッダー）

```csharp
public class HeaderGenerator : IMarkdownSectionGenerator
{
    private readonly Dictionary<string, string> _venueNameMap;
    private readonly Dictionary<string, RaceInfoCache> _raceInfoMap;
    
    public string Generate(IntegratedRaceData raceData)
    {
        var raceInfo = raceData.RaceInfo;
        var raceId = raceData.Meta.RaceId;
        
        // 競馬場名を取得（優先順位: venueNameMap > raceInfo > race_idから推測）
        var venue = GetVenueName(raceId, raceInfo);
        
        // レース番号
        var raceNum = raceInfo.RaceNumber;
        if (raceNum == 0 && raceId.Length >= 12)
        {
            raceNum = int.Parse(raceId[10..12]);
        }
        
        // レース名
        var raceName = GetRaceName(raceId, raceInfo);
        
        // グレード・クラス情報
        var classInfo = GetClassInfo(raceInfo);
        
        // ヘッダー構築
        var parts = new List<string>();
        if (!string.IsNullOrEmpty(venue) && raceNum > 0)
            parts.Add($"{venue}{raceNum}R");
        else if (raceNum > 0)
            parts.Add($"{raceNum}R");
        
        if (!string.IsNullOrEmpty(classInfo))
            parts.Add(classInfo);
        
        if (!string.IsNullOrEmpty(raceName) && raceName != $"{raceNum}R")
            parts.Add(raceName);
        
        return $"# {string.Join(" ", parts)}";
    }
    
    private string GetClassInfo(RaceInfo raceInfo)
    {
        var grade = raceInfo.Grade;
        if (!string.IsNullOrEmpty(grade) && grade != "OP")
            return $"({grade})";
        
        var condition = raceInfo.RaceCondition ?? "";
        return condition switch
        {
            var c when c.Contains("新馬") => "(新馬)",
            var c when c.Contains("未勝利") => "(未勝利)",
            var c when c.Contains("1勝クラス") => "(1勝クラス)",
            var c when c.Contains("2勝クラス") => "(2勝クラス)",
            var c when c.Contains("3勝クラス") => "(3勝クラス)",
            var c when c.Contains("オープン") => "(オープン)",
            _ => ""
        };
    }
}
```

### 3.2 EntryTable（出走表）

```csharp
public class EntryTableGenerator : IMarkdownSectionGenerator
{
    public string Generate(IntegratedRaceData raceData)
    {
        var entries = raceData.Entries;
        if (!entries.Any()) return "";
        
        var lines = new List<string>
        {
            "## 🐎 出走表",
            "",
            "| 枠 | 馬番 | 馬名 | 性齢 | 騎手 | 斤量 | オッズ | AI指数 | レート | 本誌 | 総合P | 短評 | 調教 | 調教短評 | パ評価 | パコメント | 適性/割安 |",
            "|:---:|:---:|------|:---:|------|:---:|------:|:------:|:-----:|:---:|:---:|------|:----:|:------:|:------:|:----------:|:---------:|"
        };
        
        // 馬番順にソート
        var sortedEntries = entries.OrderBy(e => e.HorseNumber).ToList();
        
        foreach (var entry in sortedEntries)
        {
            var ed = entry.EntryData;
            var td = entry.TrainingData;
            var pd = entry.PaddockInfo;
            var hf = entry.HistoryFeatures;
            
            // 馬名リンク生成
            var horseNameDisplay = GenerateHorseLink(entry);
            
            // 騎手リンク生成
            var jockeyDisplay = GenerateJockeyLink(ed);
            
            // 調教評価（矢印優先）
            var trainingEval = GetTrainingEvaluation(td);
            
            // パドック情報
            var (paddockEval, paddockComment) = GetPaddockInfo(pd);
            
            // 適性/割安情報
            var suitabilityValue = GetSuitabilityValue(hf);
            
            // 総合ポイント（マイナス値は0に修正）
            var markPoint = Math.Max(0, ed.AggregateMarkPoint);
            
            // NOTE: Markdownの表は `|` や改行が入ると崩れるためサニタイズ必須
            lines.Add(
                $"| {EscapeMarkdownTableCell(ed.Waku ?? "-")} | {entry.HorseNumber} | {EscapeMarkdownTableCell(horseNameDisplay)} | " +
                $"{EscapeMarkdownTableCell(ed.Age ?? "-")} | {EscapeMarkdownTableCell(jockeyDisplay)} | {EscapeMarkdownTableCell(ed.Weight ?? "-")} | " +
                $"{EscapeMarkdownTableCell(ed.Odds ?? "-")} | {EscapeMarkdownTableCell(ed.AiIndex ?? "-")} | {EscapeMarkdownTableCell(ed.Rating ?? "-")} | " +
                $"{EscapeMarkdownTableCell(ed.HonshiMark ?? "-")} | {markPoint} | {EscapeMarkdownTableCell(ed.ShortComment ?? "")} | " +
                $"{EscapeMarkdownTableCell(trainingEval)} | {EscapeMarkdownTableCell(GetTrainingShort(td))} | " +
                $"{EscapeMarkdownTableCell(paddockEval)} | {EscapeMarkdownTableCell(paddockComment)} | {EscapeMarkdownTableCell(suitabilityValue)} |");
        }
        
        return string.Join("\n", lines);
    }

    private static string EscapeMarkdownTableCell(string value)
    {
        if (string.IsNullOrEmpty(value)) return "";
        // 改行は空白に、表の区切り文字はエスケープ
        return value
            .Replace("\r", " ")
            .Replace("\n", " ")
            .Replace("|", "\\|");
    }
    
    private string GenerateHorseLink(IntegratedEntry entry)
    {
        if (string.IsNullOrEmpty(entry.HorseId))
            return entry.HorseName;
        
        // NOTE: パスは DataPathOptions を優先し、未設定の場合のみ環境変数へフォールバックする
        var dataRoot = !string.IsNullOrEmpty(_pathOptions.RootDir)
            ? _pathOptions.RootDir
            : (Environment.GetEnvironmentVariable("KEIBA_DATA_ROOT_DIR") ?? "Z:/KEIBA-CICD/data");
        var safeName = SanitizeHorseNameForFilename(entry.HorseName);
        var profilePath = $"{dataRoot}/horses/profiles/{entry.HorseId}_{safeName}.md";
        profilePath = profilePath.Replace('\\', '/');
        
        return $"[{entry.HorseName}]({profilePath})";
    }
    
    private static string SanitizeHorseNameForFilename(string name)
    {
        if (string.IsNullOrEmpty(name)) return name;
        
        // 先頭の(地)/(外)を除去
        var cleaned = Regex.Replace(name, @"^[\(（]\s*[地外]\s*[\)）]\s*", "");
        // パスに使えない文字を置換
        cleaned = Regex.Replace(cleaned, @"[\\/:*?""<>|]", "_");
        return cleaned;
    }
}
```

### 3.3 TenkaiSection（展開予想）

```csharp
public class TenkaiSectionGenerator : IMarkdownSectionGenerator
{
    // 〇数字マッピング
    private static readonly Dictionary<int, string> CircledNumbers = new()
    {
        { 0, "⓪" }, { 1, "①" }, { 2, "②" }, { 3, "③" }, { 4, "④" },
        { 5, "⑤" }, { 6, "⑥" }, { 7, "⑦" }, { 8, "⑧" }, { 9, "⑨" },
        { 10, "⑩" }, { 11, "⑪" }, { 12, "⑫" }, { 13, "⑬" }, { 14, "⑭" },
        { 15, "⑮" }, { 16, "⑯" }, { 17, "⑰" }, { 18, "⑱" }
    };
    
    public string Generate(IntegratedRaceData raceData)
    {
        var tenkai = raceData.TenkaiData;
        if (tenkai == null) return "";
        
        var lines = new List<string> { "## 🏃 展開予想", "" };
        
        // ペース予想
        var pace = tenkai.Pace ?? "M";
        var paceEmoji = pace switch
        {
            "H" => "🔥",      // ハイペース
            "M-H" => "⚡",    // ややハイ
            "M" => "⚖️",      // 平均
            "M-S" => "🐢",    // ややスロー
            "S" => "🐌",      // スロー
            _ => "⚖️"
        };
        
        lines.Add($"### {paceEmoji} ペース予想: {pace}");
        lines.Add("");
        
        // 展開ポジション表
        if (tenkai.Positions != null && tenkai.Positions.Any())
        {
            lines.Add("### 📊 予想展開（ポジション横配置）");
            lines.Add("");
            
            var positionOrder = new[] { "逃げ", "好位", "中位", "後方" };
            lines.Add("| " + string.Join(" | ", positionOrder) + " |");
            lines.Add("|" + string.Join("|", positionOrder.Select(_ => ":---:")) + "|");
            
            var rowCells = positionOrder.Select(pos =>
            {
                if (tenkai.Positions.TryGetValue(pos, out var horses) && horses.Any())
                {
                    return string.Join(" ", horses.Select(ToCircled));
                }
                return "-";
            });
            
            lines.Add("| " + string.Join(" | ", rowCells) + " |");
            lines.Add("");
        }
        
        // 展開解説
        if (!string.IsNullOrEmpty(tenkai.Description))
        {
            lines.Add("### 💭 展開解説");
            lines.Add("");
            lines.Add($"> {tenkai.Description}");
            lines.Add("");
        }
        
        return string.Join("\n", lines);
    }
    
    private static string ToCircled(int num)
    {
        return CircledNumbers.TryGetValue(num, out var circled) ? circled : num.ToString();
    }
}
```

### 3.4 ResultsTable（レース結果）

```csharp
public class ResultsTableGenerator : IMarkdownSectionGenerator
{
    public string Generate(IntegratedRaceData raceData)
    {
        var entries = raceData.Entries;
        
        // 結果データがある馬のみ抽出
        var results = entries
            .Where(e => e.Result?.FinishPosition != null)
            .Select(e => new
            {
                Entry = e,
                Position = ParsePosition(e.Result!.FinishPosition)
            })
            .Where(x => x.Position.HasValue)
            .OrderBy(x => x.Position)
            .ToList();
        
        if (!results.Any()) return "";
        
        var lines = new List<string> { "## 🏁 レース結果", "" };
        
        // テーブルヘッダー
        lines.Add("| 着順 | 馬番 | 馬名 | タイム | 着差 | 上り3F | 通過 | 4角 | 騎手 | オッズ |");
        lines.Add("|:---:|:---:|------|--------|------:|------:|------|:---:|------|------:|");
        
        // 上位10頭のみ表示
        foreach (var r in results.Take(10))
        {
            var entry = r.Entry;
            var result = entry.Result!;
            var ed = entry.EntryData;
            
            lines.Add($"| {result.FinishPosition} | {entry.HorseNumber} | {entry.HorseName} | " +
                     $"{result.Time ?? ""} | {result.Margin ?? ""} | {result.Last3F ?? ""} | " +
                     $"{result.CornerPositions ?? ""} | {GetLastCornerPosition(result)} | " +
                     $"{ed.Jockey ?? ""} | {ed.Odds ?? ""} |");
        }
        
        // 騎手コメントがあれば追加
        var commentsWithText = results
            .Where(r => !string.IsNullOrEmpty(r.Entry.Result?.RawData?.GetValueOrDefault("interview")?.ToString()))
            .Take(3)
            .ToList();
        
        if (commentsWithText.Any())
        {
            lines.Add("");
            lines.Add("### 💬 騎手コメント");
            lines.Add("");
            
            foreach (var r in commentsWithText)
            {
                var comment = r.Entry.Result?.RawData?["interview"]?.ToString();
                lines.Add($"**{r.Entry.Result?.FinishPosition}着 {r.Entry.HorseName}**");
                lines.Add($"> {comment}");
                lines.Add("");
            }
        }
        
        return string.Join("\n", lines);
    }
    
    private static int? ParsePosition(string? position)
    {
        if (string.IsNullOrEmpty(position)) return null;
        if (int.TryParse(position, out var pos)) return pos;
        return null;
    }
}
```

### 3.5 RaceFlowMermaid（展開図）

```csharp
public class RaceFlowMermaidGenerator : IMarkdownSectionGenerator
{
    public string Generate(IntegratedRaceData raceData)
    {
        // 上位5頭を取得
        var topHorses = raceData.Entries
            .Where(e => e.Result?.FinishPosition != null)
            .Select(e => new
            {
                e.HorseName,
                Position = int.TryParse(e.Result!.FinishPosition, out var p) ? p : 999
            })
            .Where(x => x.Position <= 5)
            .OrderBy(x => x.Position)
            .ToList();
        
        if (!topHorses.Any()) return "";
        
        var lines = new List<string>
        {
            "## 📊 レース展開",
            "",
            "```mermaid",
            "graph LR",
            "    subgraph ゴール"
        };
        
        for (var i = 0; i < topHorses.Count; i++)
        {
            var horse = topHorses[i];
            var label = (char)('A' + i);
            
            if (i == 0)
            {
                lines.Add($"        {label}[1着: {horse.HorseName}]");
            }
            else
            {
                var prevLabel = (char)('A' + i - 1);
                lines.Add($"        {prevLabel} --> {label}[{horse.Position}着: {horse.HorseName}]");
            }
        }
        
        lines.Add("    end");
        lines.Add("```");
        
        return string.Join("\n", lines);
    }
}
```

---

## 4. 追記エリアの保持

### 4.1 既存コンテンツの抽出

```csharp
private string ExtractAdditionalContent(string filePath)
{
    if (!File.Exists(filePath)) return "";
    
    try
    {
        var content = File.ReadAllText(filePath);
        var lines = content.Split('\n');
        
        var additionalStart = -1;
        for (var i = 0; i < lines.Length; i++)
        {
            var line = lines[i].Trim();
            if (line == "# 追記" || line == "# 追記欄")
            {
                additionalStart = i;
                break;
            }
        }
        
        if (additionalStart >= 0)
        {
            return string.Join("\n", lines.Skip(additionalStart));
        }
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex, "追記エリア抽出エラー: {Path}", filePath);
    }
    
    return "";
}

private static string GenerateAdditionalSection()
{
    return """
        ---
        # 追記

        """;
}
```

---

## 5. 出力パス管理

```csharp
private string GetOutputPath(IntegratedRaceData raceData)
{
    var raceId = raceData.Meta.RaceId;
    
    // 日付を取得
    var dateStr = _actualDateMap.GetValueOrDefault(raceId)
               ?? (raceId.Length >= 8 ? raceId[..8] : "00000000");
    
    var year = dateStr[..4];
    var month = dateStr[4..6];
    var day = dateStr[6..8];
    
    // 競馬場名を取得
    var venueName = _venueNameMap.GetValueOrDefault(raceId) ?? GetVenueFromRaceId(raceId);
    
    // 出力先: {MarkdownDir}/YYYY/MM/DD/競馬場名/
    // NOTE: ディレクトリ名は appsettings.json の DataPaths に従う（直書きしない）
    string outputDir;
    if (!string.IsNullOrEmpty(venueName))
    {
        outputDir = Path.Combine(_pathOptions.RootDir, _pathOptions.MarkdownDir, year, month, day, venueName);
    }
    else
    {
        outputDir = Path.Combine(_pathOptions.RootDir, _pathOptions.MarkdownDir, year, month, day);
    }
    
    Directory.CreateDirectory(outputDir);
    return Path.Combine(outputDir, $"{raceId}.md");
}
```

---

## 6. メイン生成フロー

```csharp
public async Task<string> GenerateRaceMarkdownAsync(
    IntegratedRaceData raceData,
    bool save = true,
    CancellationToken cancellationToken = default)
{
    var sections = new List<string>();
    
    // 各セクション生成
    sections.Add(_headerGenerator.Generate(raceData));
    sections.Add(_raceInfoGenerator.Generate(raceData));
    
    var raceComment = _raceCommentGenerator.Generate(raceData);
    if (!string.IsNullOrEmpty(raceComment))
        sections.Add(raceComment);
    
    sections.Add(_entryTableGenerator.Generate(raceData));
    sections.Add(_trainingCommentsGenerator.Generate(raceData));
    
    var tenkai = _tenkaiSectionGenerator.Generate(raceData);
    if (!string.IsNullOrEmpty(tenkai))
        sections.Add(tenkai);
    
    var paddock = _paddockSectionGenerator.Generate(raceData);
    if (!string.IsNullOrEmpty(paddock))
        sections.Add(paddock);
    
    // 結果データがある場合
    if (HasResults(raceData))
    {
        sections.Add(_resultsTableGenerator.Generate(raceData));
        sections.Add(_raceFlowMermaidGenerator.Generate(raceData));
        sections.Add(_resultsSummaryGenerator.Generate(raceData));
        sections.Add(_payoutsSectionGenerator.Generate(raceData));
        sections.Add(_lapsSectionGenerator.Generate(raceData));
    }
    
    sections.Add(_linksGenerator.Generate(raceData));
    sections.Add(_footerGenerator.Generate(raceData));
    
    // セクション結合
    var markdownText = string.Join("\n\n", sections.Where(s => !string.IsNullOrEmpty(s)));
    
    // 追記エリアの保持または新規追加
    var outputPath = GetOutputPath(raceData);
    var additionalContent = ExtractAdditionalContent(outputPath);
    
    if (!string.IsNullOrEmpty(additionalContent))
    {
        markdownText += "\n\n" + additionalContent;
    }
    else
    {
        markdownText += "\n\n" + GenerateAdditionalSection();
    }
    
    // ファイル保存
    if (save)
    {
        await File.WriteAllTextAsync(outputPath, markdownText, cancellationToken);
        _logger.LogInformation("Markdown生成完了: {Path}", outputPath);
    }
    
    return markdownText;
}

private static bool HasResults(IntegratedRaceData raceData)
{
    return raceData.Entries.Any(e => e.Result?.FinishPosition != null);
}
```

---

## 6.1 互換の合格基準（固定）

Markdown出力は「完全一致」だと差分が出やすいため、合格基準を固定する。

- **必須一致（Must）**
  - ヘッダー（開催場/レース番号/クラス/レース名）
  - 出走表（行数・馬番・馬名・本誌印・短評・調教/パドックの主要列）
  - 追記欄が **上書きされない**（既存があれば保持）
- **許容差分（May）**
  - 空白の差分、絵文字の有無
  - 文字列の正規化（全角/半角・スペース）
  - リンクURL（環境差）※リンクが生成されることを重視

> NOTE: 差分検証では “テーブルが崩れていない” ことを必ず確認する。

---

## 7. 依存関係

```
MarkdownService
    ├── IFileService
    ├── ILogger<MarkdownService>
    ├── IOptions<DataPathOptions>
    └── セクション生成クラス群
        ├── HeaderGenerator
        ├── RaceInfoGenerator
        ├── RaceCommentGenerator
        ├── EntryTableGenerator
        ├── TrainingCommentsGenerator
        ├── TenkaiSectionGenerator
        ├── PaddockSectionGenerator
        ├── ResultsTableGenerator
        ├── RaceFlowMermaidGenerator
        ├── ResultsSummaryGenerator
        ├── PayoutsSectionGenerator
        ├── LapsSectionGenerator
        ├── LinksGenerator
        └── FooterGenerator
```

---

## 8. 実装優先順位

| 優先度 | クラス/メソッド | 行数目安 | 理由 |
|-------|----------------|---------|------|
| 1 | MarkdownService (コア) | 100行 | 統合フロー |
| 2 | HeaderGenerator | 80行 | 必須セクション |
| 3 | EntryTableGenerator | 150行 | 最重要テーブル |
| 4 | RaceInfoGenerator | 60行 | 必須セクション |
| 5 | TrainingCommentsGenerator | 120行 | 運用で重要 |
| 6 | ResultsTableGenerator | 100行 | 結果表示 |
| 7 | TenkaiSectionGenerator | 80行 | 展開予想 |
| 8 | PaddockSectionGenerator | 80行 | パドック情報 |
| 9 | その他 | 各50行程度 | 補助的セクション |

**合計: 約800-1000行**（Python版より簡潔化可能）

---

## 9. テスト観点

1. **セクション生成テスト**: 各セクションが正しく生成されるか
2. **リンク生成テスト**: 馬プロファイル/騎手プロファイルへのリンク
3. **追記保持テスト**: 既存の追記エリアが保持されるか
4. **出力パステスト**: 正しいディレクトリに出力されるか
5. **結果有無判定テスト**: 結果データの有無で出力が変わるか
6. **Python版互換テスト**: 同じ入力で同等の出力が得られるか

---

## 10. Python版との差異

| 項目 | Python版 | C#版 |
|------|---------|------|
| 行数 | 約1400行 | 約800-1000行 |
| 構造 | 1クラスに全メソッド | セクション別クラス分離 |
| 文字列結合 | リスト + join | StringBuilder使用可 |
| ファイル操作 | 同期 | 非同期（async/await） |
| 正規表現 | re モジュール | System.Text.RegularExpressions |




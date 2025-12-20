# .NET 10 移行ガイド

## 📋 ドキュメント情報

| 項目 | 内容 |
|------|------|
| **作成日** | 2025年12月13日 |
| **バージョン** | 1.0 |
| **対象** | C# .NET 移行プロジェクト |

---

## 1. .NET 10 概要

### 1.1 リリース情報

| 項目 | 内容 |
|------|------|
| **リリース日** | 2025年11月11日 |
| **サポート種別** | LTS（Long Term Support） |
| **サポート終了日** | 2028年11月14日 |
| **C#バージョン** | C# 14 |
| **EF Coreバージョン** | 10.0 |

### 1.2 .NET 8 vs .NET 10 比較

| 項目 | .NET 8 | .NET 10 | 選択理由 |
|------|--------|---------|---------|
| サポート終了 | 2026年11月 | 2028年11月 | **2年長い** |
| C#バージョン | C# 12 | C# 14 | 新機能活用 |
| パフォーマンス | 基準 | 改善 | JIT最適化 |
| System.CommandLine | beta4 | **2.0.0 安定版** | 正式リリース |

---

## 2. .NET 10 の新機能（プロジェクトで活用可能）

### 2.1 C# 14 新機能

#### Field-backed properties（フィールド支援プロパティ）

```csharp
// C# 14 以前
private string _name = string.Empty;
public string Name
{
    get => _name;
    set => _name = value ?? throw new ArgumentNullException(nameof(value));
}

// C# 14（field キーワード使用）
public string Name
{
    get => field;
    set => field = value ?? throw new ArgumentNullException(nameof(value));
}
```

**活用場面**: DTOクラスのバリデーション付きプロパティ

#### Null-conditional assignment（null条件付き代入）

```csharp
// C# 14 以前
if (horse != null)
{
    horse.Comment = newComment;
}

// C# 14
horse?.Comment = newComment;
```

**活用場面**: パーサー結果のオプショナル更新

#### Collection expression extensions

```csharp
// C# 14: スプレッド演算子の拡張
List<int> combined = [..list1, ..list2, newItem];

// Dictionary初期化
Dictionary<string, int> marks = [
    ("◎", 8),
    ("○", 6),
    ("▲", 4)
];
```

**活用場面**: 複数パーサー結果のマージ

### 2.2 ランタイム改善

#### Stack allocation for small arrays

```csharp
// JITが自動で小さな配列をスタックに割り当て
// 明示的なstackallocなしでGC負荷軽減
var smallArray = new int[10]; // 自動最適化対象
```

**メリット**: スクレイピング時の一時配列処理が高速化

#### AVX10.2 サポート

- x64プロセッサでの SIMD 演算が高速化
- 文字列処理（全角→半角変換等）のパフォーマンス向上

### 2.3 EF Core 10 改善

#### Named query filters

```csharp
// 複数のフィルターを名前付きで定義可能
modelBuilder.Entity<Race>()
    .HasQueryFilter("active", r => r.IsActive)
    .HasQueryFilter("current_year", r => r.Year == DateTime.Now.Year);

// 特定のフィルターを無効化
context.Races.IgnoreQueryFilters("current_year").ToList();
```

**活用場面**: マルチスキーマ（keibabook/jravan/analysis）対応

#### LINQ enhancements

```csharp
// 新しいLINQメソッド
var result = entries
    .DistinctBy(e => e.HorseNumber)  // EF Core 10で改善
    .OrderBy(e => e.Rank)
    .ToList();
```

### 2.4 System.CommandLine 2.0.0（安定版）

.NET 10と同時にリリースされた正式版！

| 改善点 | 内容 |
|--------|------|
| 起動時間 | **12%高速化** |
| パース速度 | **40%高速化** |
| ライブラリサイズ | **32%削減** |
| NativeAOTサイズ | **20%削減** |

```csharp
// 2.0.0 での簡略化されたAPI
var rootCommand = new RootCommand("競馬ブック CLI");

var dateOption = new Option<DateOnly>(
    name: "--date",
    description: "対象日付");

rootCommand.AddOption(dateOption);
rootCommand.SetHandler((date) => 
{
    Console.WriteLine($"処理日: {date}");
}, dateOption);
```

---

## 3. NuGetパッケージ対応状況

### 3.1 対応確認済み

| パッケージ | バージョン | .NET 10対応 | 備考 |
|-----------|-----------|-------------|------|
| HtmlAgilityPack | 1.12.4 | ✅ 互換 | .NET Standard 2.0経由 |
| System.CommandLine | 2.0.0 | ✅ 正式対応 | .NET 10同時リリース |
| Serilog.AspNetCore | 8.0.0+ | ✅ 対応済み | - |
| Spectre.Console | 0.50.0 | ✅ 対応済み | - |
| EF Core | 10.0.0 | ✅ 正式対応 | .NET 10標準 |
| xUnit | 2.9.x | ✅ 対応済み | - |

### 3.2 要確認・代替案あり

| パッケージ | 状況 | 対応方針 |
|-----------|------|---------|
| Hangfire | ⚠️ 正式未対応 | Phase 4まで見送り、IHostedService使用 |
| Hangfire.AspNetCore | ⚠️ Newtonsoft.Json問題報告 | Quartz.NETを代替検討 |

### 3.3 Hangfire問題の詳細

**報告された問題**:
- `Hangfire.AspNetCore` で `Newtonsoft.Json` を `PrivateAssets="All"` で参照時に問題発生
- .NET 10の依存解決との競合

**推奨対応**:
1. Phase 2〜4: `IHostedService` でバックグラウンド処理実装
2. Phase 5: Hangfire正式対応を待つか、Quartz.NETに移行

---

## 4. プロジェクト設定

### 4.1 csproj設定例

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <LangVersion>14</LangVersion>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    
    <!-- .NET 10 最適化オプション -->
    <PublishAot>false</PublishAot> <!-- 必要に応じてtrue -->
    <EnableUnsafeBinaryFormatterSerialization>false</EnableUnsafeBinaryFormatterSerialization>
  </PropertyGroup>
</Project>
```

### 4.2 global.jsonでSDKバージョン固定

```json
{
  "sdk": {
    "version": "10.0.100",
    "rollForward": "latestFeature"
  }
}
```

### 4.3 Directory.Build.props（共通設定）

```xml
<Project>
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <LangVersion>14</LangVersion>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>
  
  <PropertyGroup>
    <Authors>KeibaCICD Team</Authors>
    <Company>KeibaCICD</Company>
  </PropertyGroup>
</Project>
```

---

## 5. C# 14 活用例（本プロジェクト用）

### 5.1 RaceId値オブジェクト（field キーワード使用）

```csharp
public readonly record struct RaceId
{
    public string Value
    {
        get => field;
        init
        {
            if (string.IsNullOrEmpty(value) || value.Length != 12)
                throw new ArgumentException("RaceIdは12桁である必要があります");
            if (!value.All(char.IsDigit))
                throw new ArgumentException("RaceIdは数字のみである必要があります");
            field = value;
        }
    }

    public RaceId(string value) => Value = value;

    // 分解プロパティ
    public int Year => int.Parse(Value[..4]);
    public int MonthDay => int.Parse(Value[4..8]);
    public int Venue => int.Parse(Value[8..10]);
    public int RaceNumber => int.Parse(Value[10..12]);
}
```

### 5.2 パーサー結果マージ（コレクション式拡張）

```csharp
public IntegratedRaceData Merge(
    SyutubaData shutsuba,
    CyokyoData? cyokyo,
    DanwaData? danwa)
{
    var entries = shutsuba.Horses.Select(h => new IntegratedEntry
    {
        HorseNumber = ToIntSafe(h.HorseNumber) ?? 0,
        HorseName = h.HorseName,
        // 他のデータソースをマージ
        Training = cyokyo?.TrainingData
            .FirstOrDefault(t => t.HorseNumber == ToIntSafe(h.HorseNumber)),
        Danwa = danwa?.DanwaData
            .FirstOrDefault(d => ToIntSafe(d.HorseNumber) == ToIntSafe(h.HorseNumber))
    });

    return new IntegratedRaceData
    {
        Entries = [..entries],  // C# 14 コレクション式
        DataSources = new Dictionary<string, string>
        {
            ["shutsuba"] = "取得済",
            ["cyokyo"] = cyokyo != null ? "取得済" : "未取得",
            ["danwa"] = danwa != null ? "取得済" : "未取得"
        }
    };
}
```

### 5.3 null条件付き代入の活用

```csharp
public void UpdateEntry(IntegratedEntry entry, PaddockEvaluation? paddock)
{
    // C# 14: null条件付き代入
    entry?.PaddockComment = paddock?.Comment;
    entry?.PaddockMark = paddock?.Mark;
}
```

---

## 6. パフォーマンス最適化

### 6.1 文字列処理の最適化

```csharp
// .NET 10 の Span<T> 改善を活用
public static int? ToIntSafe(ReadOnlySpan<char> value)
{
    Span<char> buffer = stackalloc char[value.Length];
    int writeIndex = 0;
    
    foreach (var c in value)
    {
        if (char.IsDigit(c))
        {
            buffer[writeIndex++] = c >= '０' && c <= '９' 
                ? (char)(c - '０' + '0')  // 全角→半角
                : c;
        }
    }
    
    return int.TryParse(buffer[..writeIndex], out var result) ? result : null;
}
```

### 6.2 並列処理の最適化

```csharp
// .NET 10 の Parallel.ForEachAsync 改善
await Parallel.ForEachAsync(
    raceIds,
    new ParallelOptions { MaxDegreeOfParallelism = 22 },
    async (raceId, ct) =>
    {
        await FetchAndParseAsync(raceId, ct);
    });
```

---

## 7. 移行チェックリスト

### 7.1 環境準備

- [ ] .NET 10 SDK インストール
- [ ] Visual Studio 2022 最新版 または VS Code + C# Dev Kit
- [ ] global.json でSDKバージョン固定

### 7.2 プロジェクト作成

- [ ] ソリューション作成（`-f net10.0` 指定）
- [ ] Directory.Build.props 配置
- [ ] NuGetパッケージ追加

### 7.3 コード実装

- [ ] C# 14 新機能の活用（field, ??=, コレクション式）
- [ ] Span<T> / stackalloc の活用
- [ ] async/await パターンの統一

### 7.4 テスト

- [ ] xUnit テストプロジェクト作成
- [ ] Python版との互換性テスト
- [ ] パフォーマンスベンチマーク

---

## 8. トラブルシューティング

### 8.1 SDKが見つからない

```powershell
# インストール済みSDK確認
dotnet --list-sdks

# 特定バージョンのSDKをダウンロード
# https://dotnet.microsoft.com/download/dotnet/10.0
```

### 8.2 NuGetパッケージが見つからない

```powershell
# NuGetソースの確認
dotnet nuget list source

# 公式ソースを追加
dotnet nuget add source https://api.nuget.org/v3/index.json -n nuget.org
```

### 8.3 EF Core 10 マイグレーションエラー

```powershell
# ツールのアップデート
dotnet tool update --global dotnet-ef --version 10.0.0

# マイグレーション再生成
dotnet ef migrations add Initial -p src/KeibaCICD.Scraper.Infrastructure -s src/KeibaCICD.Scraper.API
```

---

## 9. 参考リンク

- [.NET 10 公式ドキュメント](https://learn.microsoft.com/dotnet/core/whats-new/dotnet-10/)
- [C# 14 新機能](https://learn.microsoft.com/dotnet/csharp/whats-new/csharp-14)
- [EF Core 10](https://learn.microsoft.com/ef/core/what-is-new/ef-core-10)
- [System.CommandLine 2.0](https://github.com/dotnet/command-line-api)
- [.NET 10 サポートポリシー](https://dotnet.microsoft.com/platform/support/policy/dotnet-core)

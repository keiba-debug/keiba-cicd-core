# 設計書レビューノート

## 📋 レビュー情報

| 項目 | 内容 |
|------|------|
| レビュー日 | 2025-12-13 |
| レビュー者 | AI Assistant |
| 対象 | C# .NET移行設計書群 |

---

## 1. 🔴 要修正事項（Critical）

### 1.1 RaceIdの桁数 ✅ 確認済

**問題箇所**: `csharp_migration_detailed_design.md` - RaceId値オブジェクト

**検証結果**: Python版でも12桁で正しい

```python
# nittei_parser.py:213-228
patterns = [
    r'/shutsuba/(\d{12})',
    r'/seiseki/(\d{12})',
    r'/cyokyo/\d+/\d+/(\d{12})',
    r'/danwa/\d+/(\d{12})',
    r'/(\d{12})'  # 一般的なパターン
]
```

**結論**: 設計は正しい。修正不要。

### 1.2 Cookie認証の詳細設計不足 ✅ 修正済

**問題箇所**: `KeibaBookScraper` のCookie設定

（修正前）現在の設計（誤り）:
```csharp
foreach (var cookie in _options.Cookies)
{
    _httpClient.DefaultRequestHeaders.Add("Cookie", $"{cookie.Name}={cookie.Value}");
}
```

**Python版の実装**（requests_scraper.py:49-64）:
```python
cookies_data = Config.get_required_cookies()
for cookie in cookies_data:
    self.session.cookies.set(
        name=cookie['name'],
        value=cookie['value'],
        domain=cookie.get('domain', 'p.keibabook.co.jp'),
        path=cookie.get('path', '/')
    )
```

**修正案**:
```csharp
// HttpClientHandler + CookieContainer を使用
public class KeibaBookScraper : IKeibaBookScraper
{
    private readonly HttpClient _httpClient;
    private readonly CookieContainer _cookieContainer;
    
    public KeibaBookScraper(IOptions<ScraperOptions> options, ILogger<KeibaBookScraper> logger)
    {
        _cookieContainer = new CookieContainer();
        var handler = new HttpClientHandler
        {
            CookieContainer = _cookieContainer,
            UseCookies = true
        };
        
        _httpClient = new HttpClient(handler);
        SetupCookies(options.Value.Cookies);
    }
    
    private void SetupCookies(List<CookieConfig> cookies)
    {
        foreach (var cookie in cookies)
        {
            _cookieContainer.Add(new Cookie(
                cookie.Name,
                cookie.Value,
                cookie.Path ?? "/",
                cookie.Domain ?? "p.keibabook.co.jp"
            ));
        }
    }
}
```

**ステータス**: ✅ `csharp_migration_detailed_design.md` に反映済み

### 1.3 フェーズ定義の不整合 ✅ 修正済

`csharp_migration_detailed_design.md` / `implementation_roadmap.md` / タスク管理で
Phaseの意味がずれていたため、フェーズ定義を統一した。

- Phase 1: 設計
- Phase 2: プロジェクト基盤
- Phase 3: Scraper/Parser実装
- Phase 4: サービス層・CLI
- Phase 5: テスト・並行運用

---

## 2. 🟡 要確認事項（Important）

### 2.1 パーサー出力形式の詳細

各パーサーの出力JSON形式がPython版と完全互換か確認が必要。

| パーサー | 確認ステータス | 備考 |
|---------|---------------|------|
| NitteiParser | ✅ 完了 | スキーマ: `docs/design/parser_output_schemas.md` |
| SeisekiParser | ✅ 完了 | スキーマ: `docs/design/parser_output_schemas.md` |
| SyutubaParser | ✅ 完了 | スキーマ: `docs/design/parser_output_schemas.md` |
| CyokyoParser | ✅ 完了 | スキーマ: `docs/design/parser_output_schemas.md` |
| DanwaParser | ✅ 完了 | スキーマ: `docs/design/parser_output_schemas.md` |
| SyoinParser | ✅ 完了 | スキーマ: `docs/design/parser_output_schemas.md` |
| PaddokParser | ✅ 完了 | スキーマ: `docs/design/parser_output_schemas.md` |

**対応案**:
- ✅ `docs/design/parser_output_schemas.md` を作成し、7パーサーの出力スキーマを文書化

### 2.2 ファイルパス構造 🔧 要修正

**確認結果**（config.py:66-78 参照）:

| 項目 | 設計値 | Python版 | 修正後 |
|------|--------|---------|--------|
| RootDir | `Z:/KEIBA-CICD/data2` | 環境変数 `KEIBA_DATA_ROOT_DIR` | 環境変数対応 |
| RacesDir | `races` | `race_ids` | `race_ids` に修正 |
| IntegratedDir | `integrated` | `integrated` | ✅ |
| MarkdownDir | `organized` | `organized` | ✅ |

**Python版の実装**:
```python
@classmethod
def get_data_root_dir(cls) -> Path:
    custom_path = cls.get_env("KEIBA_DATA_ROOT_DIR")
    if custom_path:
        return Path(custom_path)
    return cls.PROJECT_ROOT / "data"
```

**修正案**（appsettings.json）:
```json
{
  "DataPaths": {
    "RootDir": "",  // 空の場合は環境変数KEIBA_DATA_ROOT_DIR使用
    "RaceIdsDir": "race_ids",  // races → race_ids に修正
    "IntegratedDir": "integrated",
    "MarkdownDir": "organized",
    "TempDir": "temp",
    "LogsDir": "logs"
  }
}
```

**ステータス**: ✅ `csharp_migration_detailed_design.md` に反映済み

### 2.3 日付パース形式

Python版は3形式対応：
- `YYYY-MM-DD`
- `YYYY/MM/DD`
- `YYYYMMDD`

C#設計の `DateParser.Parse()` でも同様の対応が必要。

```csharp
// 推奨実装
public static DateTime Parse(string dateStr)
{
    // フォーマットを自動検出
    var formats = new[] { "yyyy-MM-dd", "yyyy/MM/dd", "yyyyMMdd" };
    foreach (var format in formats)
    {
        if (DateTime.TryParseExact(dateStr, format, null, DateTimeStyles.None, out var date))
            return date;
    }
    throw new FormatException($"日付形式が不正: {dateStr}");
}
```

### 2.4 OptimizedDataFetcher の詳細

Python版の機能:
- SemaphoreSlim相当の並列制御
- メモリ監視 (`psutil`)
- リトライ（エクスポネンシャルバックオフ）
- エラー分類（HTTP/タイムアウト/パース/その他）

C#設計で網羅されているか確認必要。

---

## 3. 🟢 確認済み事項（OK）

### 3.1 Clean Architecture採用
- ✅ Domain/Application/Infrastructure/CLI/API 層分離
- ✅ 依存関係の方向が正しい

### 3.2 NuGetパッケージ選定
- ✅ HtmlAgilityPack → BeautifulSoup代替
- ✅ System.CommandLine → argparse代替
- ✅ Serilog → logging代替
- ✅ EF Core → データアクセス

### 3.3 CLIコマンド対応
- ✅ schedule → ScheduleCommand
- ✅ data → DataCommand
- ✅ full → FullCommand
- ✅ integrate → IntegrateCommand
- ✅ markdown → MarkdownCommand
- ✅ jockey → JockeyCommand
- ✅ horse-profile → HorseProfileCommand

### 3.4 DB設計
- ✅ 3スキーマ構成（jravan/keibabook/analysis）
- ✅ 主要テーブル定義
- ✅ EF Core設定例

---

## 4. 📝 追加設計が必要な箇所

### 4.1 MarkdownGenerator の詳細

Python版 `markdown_generator.py` は1300行以上の複雑な処理。
以下のセクション生成ロジックの詳細設計が必要：

- ヘッダー生成
- レース情報セクション
- 本誌の見解セクション
- 出走表テーブル（拡張版）
- 調教・厩舎談話
- 展開予想（Mermaid図）
- パドック情報
- レース結果
- 払い戻し
- 外部リンク

### 4.2 IntegrationService の詳細

`race_data_integrator.py` の統合ロジック：
- 複数JSONファイルのマージ
- 馬番での照合
- データ欠損時の処理

### 4.3 エラーハンドリング戦略

Python版のエラー処理パターンを踏襲：
- HTTP 4xx/5xx の扱い
- タイムアウト時のリトライ
- パースエラー時のログ・継続処理

---

## 5. ⚡ 実装優先順位の再評価

### 推奨順序

1. **ソリューション作成 + ドメイン層**（2日）
   - 値オブジェクト、エンティティ、列挙型

2. **KeibaBookScraper + NitteiParser**（2日）
   - 最も基本的なデータ取得
   - HTML構造確認テスト

3. **他のパーサー**（3日）
   - Python版の出力と比較テスト

4. **OptimizedDataFetcher**（2日）
   - 並列処理、リトライ

5. **IntegrationService**（2日）
   - 統合ロジック

6. **MarkdownService**（3日）
   - 最も複雑な処理

7. **CLI**（1日）
   - 薄いレイヤー

8. **テスト・検証**（3日）
   - Python版との出力比較

---

## 6. 🔍 次のアクション

### 即時対応（レビュー修正）

1. [x] RaceId構造の確認（Python実装を確認）
2. [x] Cookie認証の詳細設計追加
3. [x] appsettings.jsonのパス設定修正
4. [x] フェーズ定義の統一
5. [x] 各パーサーの出力スキーマ文書化 → `parser_output_schemas.md`

### 設計書更新

1. [ ] エラーハンドリング設計の追加
2. [x] MarkdownGenerator詳細設計 → `markdown_generator_design.md`
3. [x] IntegrationService詳細設計 → `integration_service_design.md`
4. [ ] DateParser実装追加

### 承認前確認

1. [ ] 全レビュー項目のクローズ
2. [ ] ステークホルダーレビュー依頼

---

## 5. .NET 10 対応（2025-12-14追記）

### 5.1 決定事項

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| フレームワーク | .NET 8 LTS | **.NET 10 LTS** |
| サポート終了 | 2026年11月 | **2028年11月** |
| C#バージョン | C# 12 | **C# 14** |
| EF Core | 8.0.0 | **10.0.0** |
| System.CommandLine | 2.0.0-beta4 | **2.0.0（安定版）** |

### 5.2 .NET 10 選択理由

1. **LTS版で3年間サポート** - .NET 8より2年長い
2. **C# 14新機能** - field キーワード、null条件付き代入
3. **System.CommandLine 2.0.0安定版** - .NET 10同時リリース
4. **パフォーマンス改善** - JIT最適化、Span<T>改善

### 5.3 注意事項

- **Hangfire**: .NET 10正式サポート未発表、Phase 4まで見送り
- **設計書更新済み**: NuGetパッケージバージョン、プロジェクト作成コマンド

### 5.4 追加ドキュメント

- ✅ `handover_notes.md` - 引継ぎ資料
- ✅ `dotnet10_migration_guide.md` - .NET 10移行ガイド

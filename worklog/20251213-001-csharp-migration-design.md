# 作業ログ: 251213-001 - C# .NET移行詳細設計書作成

## 作業情報
- **タスクID**: 251213-001
- **作業種別**: 設計・ドキュメント作成
- **開始日時**: 2025-12-13 10:00:00
- **完了日時**: 2025-12-13 12:00:00
- **所要時間**: 2時間
- **担当**: AI Assistant

---

## 背景・目的

Python製の競馬ブックスクレイピングシステム（KeibaCICD.keibabook）をC# .NETに移行するための詳細設計書を作成。

運用サポートで使用している以下の機能を中心に移行対象を分析：
- `fast_batch_cli.py` - 高速データ取得
- `integrator_cli.py` - データ統合
- `markdown_cli.py` - MD新聞生成
- `jockey_cli.py` - 騎手情報管理
- `horse_profile_cli.py` - 馬プロファイル生成

---

## 実施内容

### 1. 現状システム分析

#### 調査対象ファイル
| ファイル | 内容 |
|---------|------|
| `運用サポート.md` | 実際の運用コマンド一覧 |
| `KeibaCICD.keibabook/docs/システム概要/アーキテクチャ.md` | システム構成 |
| `KeibaCICD.keibabook/docs/システム概要/機能一覧.md` | 機能詳細 |
| `KeibaCICD.keibabook/docs/使い方/実行コマンド一覧.md` | CLI仕様 |
| `KeibaCICD.keibabook/src/parsers/*.py` | 7種類のパーサー |
| `KeibaCICD.keibabook/src/scrapers/*.py` | スクレイパー実装 |
| `KeibaCICD.keibabook/src/batch/optimized_data_fetcher.py` | 並列処理 |

#### 主要発見事項
- **データタイプ7種類**: nittei, seiseki, shutsuba, cyokyo, danwa, syoin, paddok
- **並列処理**: ThreadPoolExecutor使用、最大22ワーカー
- **出力形式**: JSON + Markdown（MD新聞）
- **認証**: Cookie認証

### 2. 設計書作成

#### 作成ドキュメント

| ファイル | 内容 | 行数 |
|---------|------|------|
| `docs/design/csharp_migration_detailed_design.md` | 詳細設計書（メイン） | 約700行 |
| `docs/design/database_integration_design.md` | DB統合設計書 | 約350行 |
| `docs/design/implementation_roadmap.md` | 実装ロードマップ | 約400行 |

#### 詳細設計書の主要内容

**プロジェクト構成:**
```
KeibaCICD.Scraper.sln
├── src/
│   ├── KeibaCICD.Scraper.Domain/        # ドメイン層
│   ├── KeibaCICD.Scraper.Application/   # アプリケーション層
│   ├── KeibaCICD.Scraper.Infrastructure/# インフラ層
│   ├── KeibaCICD.Scraper.CLI/           # CLI層
│   ├── KeibaCICD.Scraper.API/           # Web API層
│   └── KeibaCICD.Scraper.Jobs/          # バックグラウンドジョブ
└── tests/
```

**NuGetパッケージ:**
- HtmlAgilityPack 1.11.61 - HTMLパース
- System.CommandLine 2.0.0-beta4 - CLI
- Serilog.AspNetCore 8.0.0 - ロギング
- Microsoft.EntityFrameworkCore.SqlServer 8.0.0 - DB
- Hangfire.Core 1.8.6 - ジョブスケジューリング

**クラス設計実装例:**
- RaceId（値オブジェクト）
- NitteiParser（パーサー）
- ScrapingService（サービス）
- FullCommand（CLI）

#### DB統合設計書の主要内容

**スキーマ構成:**
- `keibabook` - 競馬ブックスクレイピングデータ
- `jravan` - JRA-VANデータ（既存想定）
- `analysis` - 統合・分析データ

**テーブル定義:**
- Races, Entries, TrainingData, StableComments
- PaddokData, Results, Jockeys, JockeyStats

#### 実装ロードマップの主要内容

**Phase別計画:**
| Phase | 期間 | 内容 |
|-------|------|------|
| Phase 1 | Week 1 | プロジェクト基盤、ドメイン層 |
| Phase 2 | Week 2 | Scraper/Parser実装 |
| Phase 3 | Week 3 | サービス層、CLI実装 |
| Phase 4 | Week 4 | テスト、並行運用 |

**合計: 約4週間（20営業日）**

---

## 変更ファイル

| ファイルパス | 変更内容 |
|-------------|---------|
| `docs/design/csharp_migration_detailed_design.md` | 新規作成 |
| `docs/design/database_integration_design.md` | 新規作成 |
| `docs/design/implementation_roadmap.md` | 新規作成 |
| `worklog/20251213-001-csharp-migration-design.md` | 新規作成（本ファイル） |

---

## 検証結果

- ✅ 運用サポートの全コマンドを移行対象として網羅
- ✅ Python→C#のライブラリ対応を確認
- ✅ Clean Architectureに基づくプロジェクト構成設計
- ✅ JRA-VANデータ連携を考慮したDB設計
- ✅ 実装可能なスケジュール見積もり

---

## 課題・申し送り事項

### 未決定事項
- [ ] フロントエンド技術選定（Next.js vs Blazor）
- [ ] 本番デプロイ環境（Docker/IIS/Azure）
- [ ] 機械学習モデルの詳細仕様

### 次のステップ
1. **設計書レビュー・承認** - ステークホルダー確認
2. **ソリューション作成** - dotnet new sln実行
3. **ドメイン層実装開始** - RaceId, DataType等

### 技術的検討事項
- HTML構造変更への対応（前回のnittei_parser修正を参考）
- 並列処理のパフォーマンス検証
- Cookie認証の移植方法

---

## 関連リンク

- 既存分析: [../docs/csharp_migration_analysis.md]
- アーキテクチャ考慮: [../docs/architecture_considerations.md]
- 詳細設計: [../docs/design/csharp_migration_detailed_design.md]
- DB設計: [../docs/design/database_integration_design.md]
- ロードマップ: [../docs/design/implementation_roadmap.md]

---

## 追記：設計書レビュー（2025-12-13 14:00）

### レビュー実施者
- AI Assistant

### レビュー対象ドキュメント
1. `docs/design/csharp_migration_detailed_design.md`
2. `docs/design/database_integration_design.md`
3. `docs/design/implementation_roadmap.md`
4. `docs/csharp_migration_analysis.md`（既存）
5. `docs/architecture_considerations.md`（既存）

### レビュー結果サマリ

| カテゴリ | 確認済 | 要確認 | 要修正 |
|---------|--------|--------|--------|
| ドキュメント整合性 | 5 | 2 | 1 |
| Python実装網羅性 | 8 | 3 | 0 |
| 技術仕様詳細度 | 6 | 4 | 2 |
| 設定・認証 | 2 | 2 | 0 |

### 詳細レビュー項目
→ 詳細: [../docs/design/review_notes.md]

---

## レビュー詳細（2025-12-13 14:30更新）

### 🔴 修正完了項目

#### 1. Cookie認証の詳細設計
- **問題**: HttpClient.DefaultRequestHeadersにCookieを追加する方式だった
- **修正**: HttpClientHandler + CookieContainerを使用する正しい方式に修正
- **ファイル**: `csharp_migration_detailed_design.md` - KeibaBookScraper

#### 2. ファイルパス設定
- **問題**: `RacesDir: "races"` / `RootDir: "Z:/KEIBA-CICD/data2"` が不正確
- **修正**: `RaceIdsDir: "race_ids"` / `RootDir: ""` （環境変数対応）
- **ファイル**: `csharp_migration_detailed_design.md` - appsettings.json

### ✅ 確認済み項目

1. **RaceIdの桁数**: 12桁で正しい（Python版と一致）
2. **パーサー構成**: 7種類全て網羅
3. **CLIコマンド**: 全コマンド対応済み
4. **NuGetパッケージ**: 適切な選定

### ⚠️ 追加設計が必要な項目

1. **MarkdownGenerator詳細設計** - 1300行超の複雑な処理
2. **IntegrationService詳細設計** - データマージロジック
3. **DateParser実装** - 3形式対応

### 次のアクション

1. [x] Cookie認証設計の修正
2. [x] パス設定の修正
3. [x] タスク管理ドキュメント作成
4. [x] フェーズ定義の統一（設計/ロードマップ/タスク）
5. [x] DB統合設計の補強（重複防止・更新方針）
6. [ ] MarkdownGenerator詳細設計
7. [ ] IntegrationService詳細設計
8. [ ] 全パーサーの出力スキーマ文書化

---

## 追記：タスク管理ドキュメント作成（2025-12-13 23:30）

### 作成ファイル

| ファイル | 内容 |
|---------|------|
| `tasks/index.md` | マスターインデックス更新 |
| `tasks/active/2025-12/task-251213-001-csharp-migration.md` | C#移行タスク詳細 |

### タスク構成

```
tasks/
├── index.md                                    # 更新
├── active/
│   ├── 2025-06/                               # 既存
│   └── 2025-12/                               # 新規作成
│       └── task-251213-001-csharp-migration.md # 新規作成
└── ...
```

### 今後のタスク管理

- **進捗更新**: 作業ごとにタスクファイルとindex.mdを更新
- **完了時**: completedフォルダへ移動、worklogに最終記録

---

## 追記：追加設計書作成（2025-12-13 23:45）

### 作成ファイル

| ファイル | 内容 | 行数 |
|---------|------|------|
| `docs/design/integration_service_design.md` | IntegrationService詳細設計 | 約400行 |
| `docs/design/markdown_generator_design.md` | MarkdownGenerator詳細設計 | 約500行 |

### IntegrationService詳細設計のポイント

1. **データマージフロー**: 7種類のデータソースを馬番で照合
2. **全角数字対応**: `ToIntSafe()` メソッドでPython版と同等の変換
3. **ファイルパス管理**: 実際の開催日マッピングを使用
4. **エラーハンドリング**: shutsubaのみ必須、他は任意

### MarkdownGenerator詳細設計のポイント

1. **セクション分離**: 14個のセクション生成クラスに分割
2. **追記エリア保持**: 既存の追記を上書きしない
3. **リンク生成**: 馬プロファイル/騎手プロファイルへのリンク
4. **Mermaid対応**: レース展開図の生成

### 担当者共有用（このまま貼れる要約）

**目的**
- Python版（`race_data_integrator.py` / `markdown_generator.py`）の挙動をC#へ移植するにあたり、実装前に「仕様として固定すべき点（互換基準/欠損時挙動/パス/サニタイズ）」を明文化し、手戻りを防ぐ。

**今回の決定・明文化（重要）**
- IntegrationService:
  - 必須データ `shutsuba` 欠損時は **統合失敗（null返却）** とし、統合JSONは出力しない（失敗が検知できるようにする）
  - `meta.data_sources` の値を `"取得済" / "未取得" / "パース失敗" / "必須欠損"` に固定
  - 統合JSONの互換「合格基準（Must/May/Fail）」を定義
  - 統合JSONの出力先は `DataPaths.IntegratedDir` / `DataPaths.TempDir` を参照（直書き禁止）
- MarkdownGenerator:
  - 出走表のセル値は **Markdown表崩れ防止のサニタイズ**（`|` と改行）を必須化
  - 出力先は `DataPaths.MarkdownDir` を参照（直書き禁止）
  - Markdown互換の合格基準（Must/May）を定義（追記欄保持はMust）

**残タスク（優先順）**
1. 7パーサーの出力スキーマ文書化（互換テストの前提）
2. Phase 2（プロジェクト基盤）開始（sln作成〜Domain骨格）

### 次のアクション更新

1. [x] Cookie認証設計の修正
2. [x] パス設定の修正
3. [x] タスク管理ドキュメント作成
4. [x] フェーズ定義の統一（設計/ロードマップ/タスク）
5. [x] DB統合設計の補強（重複防止・更新方針）
6. [x] MarkdownGenerator詳細設計
7. [x] IntegrationService詳細設計
8. [x] 全パーサーの出力スキーマ文書化 ← 完了
9. [ ] Phase 2（プロジェクト基盤）開始

---

## 追記：パーサー出力スキーマ文書化（2025-12-14 00:30）

### 作成ファイル

| ファイル | 内容 | 行数 |
|---------|------|------|
| `docs/design/parser_output_schemas.md` | 7パーサー出力スキーマ設計書 | 約600行 |

### 文書化した7パーサー

| パーサー | 主要出力キー | C#対応クラス |
|---------|-------------|--------------|
| NitteiParser | date, kaisai_data, total_races | NitteiData, RaceSchedule |
| SyutubaParser | race_info, horses, ai_data, tenkai_data | SyutubaData, HorseEntry |
| CyokyoParser | training_data | CyokyoData, TrainingEntry |
| DanwaParser | danwa_data | DanwaData, DanwaEntry |
| SeisekiParser | results, payouts, laps | SeisekiData, RaceResult, PayoutInfo |
| SyoinParser | interviews | SyoinData, InterviewEntry |
| PaddokParser | paddock_evaluations, data_status | PaddokData, PaddockEvaluation |

### 互換基準の固定

- **Must**: トップレベルキー名、配列構造、識別子（馬番/馬名/race_id）
- **May**: null vs キー省略、空文字列 vs null、全角/半角
- **Fail**: 必須キー欠損、配列空、型不一致

### 設計上の決定事項

1. **日本語キー名維持**: `馬番`, `馬名` 等のPython版キー名をC#でも `[JsonPropertyName]` で維持
2. **JSONシリアライズ設定**: SnakeCaseLower + UnsafeRelaxedJsonEscaping
3. **テスト基準**: Python版との正規化比較

### レビュー指摘への対応（2025-12-14 01:00）

1. **馬番の型ゆれ統一ルール追記**
   - `parser_output_schemas.md` に 0.1 セクションを追加
   - パーサーごとの型混在（string/int）を明文化
   - `ToIntSafe()` で統一する方針を固定

2. **"配列が空＝Fail"の適用条件を明確化**
   - 「ファイルが存在し、パース成功したにもかかわらず空」の場合に限定
   - ファイル未取得は別扱い

3. **JSONシリアライズ方針を追記**
   - 日本語キー: `[JsonPropertyName]` で固定
   - 英語キー: `SnakeCaseLower` で自動変換

### 次のアクション

- Phase 1（設計）完了 → **Phase 2（プロジェクト基盤）開始可能**
  - ソリューション作成: `dotnet new sln`
  - Domain層: RaceId, DataType, 各パーサー出力モデル

---

## 追記：.NET 10対応・引継ぎ資料作成（2025-12-14 02:00）

### 決定事項

| 項目 | 内容 |
|------|------|
| フレームワーク | **.NET 8 → .NET 10 LTS** に変更 |
| サポート期限 | 2028年11月14日（3年間） |
| C#バージョン | C# 14 |
| EF Core | 10.0.0 |
| System.CommandLine | **2.0.0 安定版**（.NET 10同時リリース） |

### 作成ファイル

| ファイル | 内容 |
|---------|------|
| `docs/design/handover_notes.md` | 引継ぎ資料（Phase 2開始手順含む） |
| `docs/design/dotnet10_migration_guide.md` | .NET 10移行ガイド（新機能・活用例） |

### 設計書更新

| ファイル | 更新内容 |
|---------|---------|
| `csharp_migration_detailed_design.md` | .NET 10指定、NuGetバージョン更新 |
| `implementation_roadmap.md` | `-f net10.0` オプション追加 |

### .NET 10 新機能の活用計画

1. **C# 14 field キーワード**: RaceId値オブジェクトのバリデーション
2. **C# 14 null条件付き代入**: パーサー結果の安全な更新
3. **C# 14 コレクション式拡張**: データマージ処理
4. **EF Core 10 Named filters**: マルチスキーマ対応
5. **System.CommandLine 2.0.0**: 高速CLI（12%起動高速化）

### Hangfire対応方針

- 正式な.NET 10サポート未発表
- Phase 4まではCLIベース + `IHostedService` で実装
- Phase 5でHangfire統合をテスト、問題あればQuartz.NETを検討

### 引継ぎ時のチェックリスト

1. .NET 10 SDK インストール確認
2. 設計書一読（`handover_notes.md` → 各詳細設計）
3. ソリューション作成コマンド実行
4. Domain層のRaceId.csから実装開始

### 次回作業予定

1. [ ] .NET 10 SDK インストール確認
2. [ ] ソリューション・プロジェクト作成
3. [ ] NuGetパッケージ追加
4. [ ] Domain層実装（RaceId, DataType, パーサー出力モデル）

# KeibaCICD v4.0 アーキテクチャ設計書

> **策定日**: 2026-02-07
> **策定者**: カカシ（AI相談役）
> **対象バージョン**: v4.0（2026年夏リリース予定）

---

## 🎯 ビジョン

**「馬券で勝つために、予想精度を高め、ML導入とMCP連携を可能にするアーキテクチャ」**

### 目指す姿

1. **予想精度の向上**: ドメインロジックの洗練とML導入で勝率アップ
2. **保守性の向上**: 層分離により変更影響を局所化
3. **拡張性の確保**: 新データソース、新予想手法の追加が容易
4. **LLM連携**: MCP経由でClaude等のLLMに予想補助を依頼
5. **ハイブリッド構成**: Python（ドメイン）+ C#（高速処理）の選択肢

---

## 🏗️ レイヤー構成

### 全体像

```
┌─────────────────────────────────────────────────────┐
│             Presentation Layer                      │
│  ┌─────────────────────────────────────────────┐  │
│  │ WebViewer (Next.js)                         │  │
│  │  - レース詳細ページ                         │  │
│  │  - 馬プロファイルページ                     │  │
│  │  - 予想ページ（v4.0新設）                   │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        ↓ API / JSON
┌─────────────────────────────────────────────────────┐
│            Application Layer (新設)                 │
│  ┌─────────────────────────────────────────────┐  │
│  │ Use Cases                                   │  │
│  │  - GenerateTrainingSummaryUseCase           │  │
│  │  - PredictRaceUseCase                       │  │
│  │  - AnalyzeHorsePerformanceUseCase           │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ ML Models                                   │  │
│  │  - TrainingMLModel (LightGBM)               │  │
│  │  - RaceMLModel (XGBoost)                    │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ MCP Integration                             │  │
│  │  - LLMPredictionAssistant                   │  │
│  │  - RaceAnalysisAgent                        │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│              Domain Layer (新設)                    │
│  ┌─────────────────────────────────────────────┐  │
│  │ Entities                                    │  │
│  │  - Training (調教)                          │  │
│  │  - Horse (馬)                               │  │
│  │  - Race (レース)                            │  │
│  │  - Prediction (予想)                        │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ Domain Services                             │  │
│  │  - TrainingEvaluationService                │  │
│  │  - RacePredictionService                    │  │
│  │  - ExpectedValueCalculator                  │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ Business Rules                              │  │
│  │  - 好タイム基準                             │  │
│  │  - SS昇格ルール                             │  │
│  │  - 期待値計算式                             │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│          Infrastructure Layer (既存整理)            │
│  ┌─────────────────────────────────────────────┐  │
│  │ Data Sources                                │  │
│  │  - JRA-VAN (CK_DATA, UM_DATA, etc.)         │  │
│  │  - 競馬ブック (スクレイピング)             │  │
│  │  - netkeiba (将来)                          │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ Parsers                                     │  │
│  │  - CKDataParser (Python/C#)                 │  │
│  │  - UMDataParser                             │  │
│  │  - KeibaBookScraper                         │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ Persistence                                 │  │
│  │  - FileSystemRepository (現在)             │  │
│  │  - PostgreSQLRepository (v4.1+)             │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 📦 各レイヤーの責務

### 1. Infrastructure Layer（インフラ層）

**責務**: データの取得・パース・永続化

**モジュール**:
- `KeibaCICD.keibabook`: 競馬ブックからのスクレイピング
- `KeibaCICD.TARGET`: JRA-VANデータのパース
- `KeibaCICD.Infrastructure.Parser` (C#): 高速パース処理（オプション）

**やること**:
- HTMLのスクレイピング
- JRA-VAN固定長レコードのパース（バイトオフセット処理）
- ファイルシステムへの保存
- データベースへの保存（v4.1+）

**やらないこと**:
- 評価ロジック（S/A/B/C/Dの判定など）
- 予想ロジック
- ビジネスルール

---

### 2. Domain Layer（ドメイン層）⭐NEW

**責務**: ビジネスロジック・ドメイン知識の集約

**モジュール**:
- `KeibaCICD.Domain`: 新設

**やること**:
- エンティティの定義（Training, Horse, Race）
- 評価ロジック（is_good_time, lap_class, upgraded_lap_class）
- ビジネスルール（好タイム基準、SS昇格条件）
- ドメインサービス（調教評価、レース予想）

**やらないこと**:
- データ取得
- ML予測
- UI表示

---

### 3. Application Layer（アプリケーション層）⭐NEW

**責務**: ユースケースの実現・データフロー制御

**モジュール**:
- `KeibaCICD.Application`: 新設

**やること**:
- ユースケースの実装（調教サマリ生成、レース予想）
- MLモデルの適用
- MCP経由でのLLM連携
- データフローの制御

**やらないこと**:
- ビジネスルール（Domain層に委譲）
- データパース（Infrastructure層に委譲）
- UI表示（Presentation層に委譲）

---

### 4. Presentation Layer（プレゼンテーション層）

**責務**: ユーザーへの情報表示・操作受付

**モジュール**:
- `KeibaCICD.WebViewer`: Next.js

**やること**:
- レース詳細ページの表示
- 調教分析の可視化
- 予想結果の表示
- ユーザー操作の受付

**やらないこと**:
- ビジネスロジック
- データ取得
- ML予測

---

## 🛠️ 技術スタック

### 既存技術

| レイヤー | 技術 | 用途 |
|---------|------|------|
| Infrastructure | Python 3.11 | パース処理 |
| Infrastructure | BeautifulSoup | HTMLスクレイピング |
| Infrastructure | Selenium | ブラウザ自動操作 |
| Presentation | Next.js 14 | Webフロントエンド |
| Presentation | TypeScript | 型安全なフロントエンド |
| Presentation | Tailwind CSS | スタイリング |

### 新規導入（v4.0）

| レイヤー | 技術 | 用途 | 優先度 |
|---------|------|------|--------|
| Domain | Python 3.11 | ドメインロジック | 必須 |
| Application | Python 3.11 | ユースケース | 必須 |
| Application | LightGBM | 調教ML予測 | 中 |
| Application | XGBoost | レースML予測 | 中 |
| Application | MCP (Claude) | LLM予想補助 | 低 |
| Infrastructure | C#/.NET 8 | 高速パース | 低（オプション） |
| Infrastructure | PostgreSQL 16 | データ永続化 | 低（v4.1+） |

---

## 🤖 MCP（Model Context Protocol）連携

### 概要

MCPを利用して、Claude等のLLMに予想補助を依頼する仕組みを構築します。

### アーキテクチャ

```
┌────────────────────────────────────────┐
│  Application Layer                     │
│  ┌──────────────────────────────────┐ │
│  │ PredictRaceWithLLMUseCase        │ │
│  │  1. ドメイン層で基本分析         │ │
│  │  2. MCPでLLM補助予想             │ │
│  │  3. 結果統合                     │ │
│  └──────────────────────────────────┘ │
└────────────────────────────────────────┘
                 ↓ MCP Protocol
┌────────────────────────────────────────┐
│  MCP Server (Claude Code)              │
│  - analyze_race ツール                 │
│  - predict_top3 ツール                 │
└────────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────┐
│  Claude (LLM)                          │
│  - 血統知識                            │
│  - 騎手の相性                          │
│  - 過去パターン認識                    │
└────────────────────────────────────────┘
```

### MCP連携のメリット

1. **LLMの知識活用**: 血統、騎手、コース適性などの知識を活用
2. **説明可能性**: LLMが予想根拠を自然言語で説明
3. **柔軟性**: LLMの進化に応じて予想精度が向上
4. **人間との協調**: LLMの提案をユーザーが確認・調整可能

---

## 💻 .NET C#との連携（オプション）

### 目的

パース処理の高速化（Python比で2-3倍の速度向上）

### 実装方針

```csharp
// KeibaCICD.Infrastructure.Parser (C#/.NET 8)
namespace KeibaCICD.Infrastructure.Parser;

public class CKDataParser
{
    public List<RawTrainingRecord> ParseFile(string filePath)
    {
        var records = new List<RawTrainingRecord>();

        // C#の高速ファイルIO
        using var reader = new StreamReader(
            filePath,
            Encoding.GetEncoding("shift_jis")
        );

        string? line;
        while ((line = reader.ReadLine()) != null)
        {
            if (line.Length < 47) continue;

            // Span<T>を使った高速パース
            var record = ParseLine(line.AsSpan());
            records.Add(record);
        }

        return records;
    }

    private RawTrainingRecord ParseLine(ReadOnlySpan<char> line)
    {
        // 高速パース処理
        return new RawTrainingRecord
        {
            Date = line.Slice(1, 8).ToString(),
            Time = line.Slice(9, 4).ToString(),
            HorseId = line.Slice(13, 10).ToString(),
            Time4F = ParseDecimal(line.Slice(23, 4)) / 10.0f,
            Lap4 = ParseDecimal(line.Slice(27, 3)) / 10.0f,
            // ... 他のフィールド
        };
    }
}
```

### Pythonから呼び出し

```python
# Infrastructure層
import clr
clr.AddReference("KeibaCICD.Infrastructure.Parser")
from KeibaCICD.Infrastructure.Parser import CKDataParser

# 高速パーサーを使用
parser = CKDataParser()
raw_records = parser.ParseFile(file_path)

# Domain層に渡す
trainings = [Training.from_raw(r, config) for r in raw_records]
```

---

## 📊 データフロー

### v3.0（現在）

```
JRA-VAN CK_DATA
    ↓
parse_ck_data.py (パース + 評価)
    ↓
generate_training_summary.py (サマリ生成 + JSON出力)
    ↓
training_summary.json
    ↓
WebViewer (表示)
```

**問題**:
- パースと評価が混在
- テストしにくい
- ML導入の余地がない

---

### v4.0（目指す姿）

```
JRA-VAN CK_DATA
    ↓
Infrastructure: CKDataParser (パースのみ)
    ↓ RawTrainingRecord
Domain: Training (評価ロジック)
    ↓ Training Entity
Application: GenerateTrainingSummaryUseCase
    ├─ Domain: TrainingEvaluationService
    ├─ Application: TrainingMLModel (オプション)
    └─ Application: LLMPredictionAssistant (オプション)
    ↓
TrainingSummary (DTO)
    ↓ JSON
Presentation: WebViewer
```

**改善点**:
- 各層が独立してテスト可能
- ML/LLMの追加が容易
- ドメインロジックの再利用性が高い

---

## 🔐 セキュリティとパフォーマンス

### セキュリティ

1. **APIキー管理**: 環境変数で管理（`.env`ファイル）
2. **スクレイピング**: robots.txt準拠、rate limit実装
3. **MCP通信**: HTTPS必須、API制限遵守

### パフォーマンス

| 処理 | 現状 | v4.0目標 | 対策 |
|------|------|---------|------|
| CK_DATAパース | 3秒 | 1秒 | C#パーサー導入 |
| 調教サマリ生成 | 5秒 | 3秒 | 並列処理 |
| レース予想 | - | 2秒 | MLモデル最適化 |
| WebViewer表示 | 1秒 | 0.5秒 | キャッシング |

---

## 🚀 マイクロサービス的構成（将来）

### v5.0以降のビジョン

```
┌─────────────────────────────────────────┐
│  API Gateway (Next.js API Routes)      │
└─────────────────────────────────────────┘
         ↓         ↓         ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Training    │ │ Race        │ │ Prediction  │
│ Service     │ │ Service     │ │ Service     │
│ (Python)    │ │ (Python)    │ │ (Python+MCP)│
└─────────────┘ └─────────────┘ └─────────────┘
         ↓                ↓                ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ CK Parser   │ │ Race DB     │ │ ML Models   │
│ (C#/.NET)   │ │ (PostgreSQL)│ │ (LightGBM)  │
└─────────────┘ └─────────────┘ └─────────────┘
```

**メリット**:
- 各サービスを独立してスケール可能
- 言語の選択肢が広がる（Python/C#/Go/Rust）
- 障害の影響範囲を局所化

---

## 📝 実装ガイドライン

### コーディング規約

1. **型ヒント必須**: Python 3.11のtype hintsを活用
2. **dataclass活用**: エンティティは`@dataclass`で定義
3. **pytest**: 単体テストは必須
4. **docstring**: Google Styleで記述

### ディレクトリ構造（v4.0）

```
keiba-cicd-core/
├── KeibaCICD.Domain/          # 新設
│   ├── training/
│   │   ├── training.py        # Training Entity
│   │   ├── config.py          # TrainingConfig
│   │   └── evaluation.py      # TrainingEvaluationService
│   ├── race/
│   │   ├── race.py            # Race Entity
│   │   └── prediction.py      # RacePredictionService
│   └── common/
│       └── value_objects.py   # 値オブジェクト
├── KeibaCICD.Application/     # 新設
│   ├── use_cases/
│   │   ├── training_summary.py
│   │   └── predict_race.py
│   ├── ml/
│   │   ├── training_model.py
│   │   └── race_model.py
│   └── mcp/
│       └── llm_assistant.py
├── KeibaCICD.TARGET/          # 既存（整理）
│   ├── scripts/
│   │   └── parse_ck_data.py   # パース専念
│   └── common/
│       └── jravan/            # JRA-VANライブラリ
├── KeibaCICD.keibabook/       # 既存
└── KeibaCICD.WebViewer/       # 既存
```

---

## 📅 ロードマップ

| フェーズ | バージョン | 期間 | 主な変更 |
|---------|-----------|------|---------|
| Phase 1 | v3.2 | 2026年3月 | Domain層抽出 |
| Phase 2 | v3.3 | 2026年4月 | Application層整備 |
| Phase 3 | v3.4 | 2026年5月 | Infrastructure整理 |
| Phase 4 | v4.0 | 2026年6月 | ML導入 |
| Phase 5 | v4.1 | 2026年7月 | MCP連携 |
| Phase 6 | v4.2 | 2026年8月 | C#パーサー導入 |

---

## 🎓 参考資料

- [クリーンアーキテクチャ](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [ドメイン駆動設計](https://www.domainlanguage.com/ddd/)
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/)
- [.NET Interop with Python](https://github.com/pythonnet/pythonnet)

---

**更新履歴**:
- 2026-02-07: 初版作成（カカシ）

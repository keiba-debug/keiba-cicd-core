# KeibaCICD 開発ガイドライン

## 1. 開発環境セットアップ

### 1.1 必要なツール

#### 基本ツール
- **Git**: バージョン管理
- **Docker**: コンテナ環境
- **Docker Compose**: 開発環境構築
- **Node.js**: v18.0.0以上
- **Python**: v3.11以上
- **.NET**: v8.0以上

#### 開発ツール
- **IDE**: Visual Studio Code（推奨）
- **拡張機能**: 
  - Python
  - TypeScript
  - C#
  - Docker
  - GitLens
  - Prettier
  - ESLint

### 1.2 環境構築手順

```bash
# 1. リポジトリクローン
git clone https://github.com/your-org/keiba-cicd-core.git
cd keiba-cicd-core

# 2. 環境変数設定
cp .env.example .env
# .envファイルを編集

# 3. Docker環境起動
docker-compose up -d

# 4. 依存関係インストール
# Python
pip install -r requirements.txt

# Node.js
cd frontend
npm install

# .NET
cd ../src/jravan
dotnet restore
```

## 2. コーディング規約

### 2.1 Python（FastAPI）

#### 2.1.1 基本規約
- **PEP 8**: Python標準コーディング規約に準拠
- **型ヒント**: 必須（Python 3.11+の型システム活用）
- **docstring**: Google形式
- **インポート**: isortでソート

#### 2.1.2 命名規則
```python
# ファイル名: snake_case
race_analyzer.py
horse_personality.py

# クラス名: PascalCase
class RacePatternAnalyzer:
    pass

# 関数・変数名: snake_case
def calculate_expected_value():
    race_id = "202501050111"
    
# 定数: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30
```

#### 2.1.3 コード例
```python
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class RaceAnalysisRequest(BaseModel):
    """レース分析リクエスト"""
    race_id: str
    include_visualization: bool = False
    analysis_types: List[str] = ["pattern", "expected_value"]

class RacePatternAnalyzer:
    """レース質分析クラス"""
    
    def __init__(self, db_session: Session) -> None:
        """
        初期化
        
        Args:
            db_session: データベースセッション
        """
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
    
    async def analyze_race_pattern(
        self, 
        race_id: str,
        options: Optional[Dict[str, Any]] = None
    ) -> RacePatternAnalysis:
        """
        レース質を分析する
        
        Args:
            race_id: レースID（YYYYMMDDHHRR形式）
            options: 分析オプション
            
        Returns:
            レース質分析結果
            
        Raises:
            RaceNotFoundError: レースが見つからない場合
            AnalysisError: 分析処理でエラーが発生した場合
        """
        try:
            # 実装
            pass
        except Exception as e:
            self.logger.error(f"Race pattern analysis failed: {race_id}", exc_info=True)
            raise AnalysisError(f"Failed to analyze race pattern: {str(e)}")
```

### 2.2 TypeScript（Next.js）

#### 2.2.1 基本規約
- **ESLint**: Airbnb設定ベース
- **Prettier**: コードフォーマット
- **TypeScript**: strict mode
- **React**: 関数コンポーネント + Hooks

#### 2.2.2 命名規則
```typescript
// ファイル名: kebab-case
race-pattern-visualizer.tsx
horse-character-card.tsx

// コンポーネント名: PascalCase
export function RacePatternVisualizer() {}

// 関数・変数名: camelCase
const calculateExpectedValue = () => {}
const raceId = "202501050111"

// 型名: PascalCase
interface RaceAnalysisData {
  raceId: string
  patterns: RacePattern[]
}

// 定数: UPPER_SNAKE_CASE
const MAX_RETRY_COUNT = 3
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL
```

#### 2.2.3 コード例
```typescript
import { useState, useEffect, useCallback } from 'react'
import { RacePatternAnalysis, ApiResponse } from '@/types/api'
import { useRacePattern } from '@/hooks/useRacePattern'

interface RacePatternVisualizerProps {
  raceId: string
  onAnalysisComplete?: (analysis: RacePatternAnalysis) => void
}

export function RacePatternVisualizer({ 
  raceId, 
  onAnalysisComplete 
}: RacePatternVisualizerProps) {
  const [selectedScenario, setSelectedScenario] = useState<number>(0)
  const { data: pattern, loading, error } = useRacePattern(raceId)

  const handleScenarioChange = useCallback((scenarioId: number) => {
    setSelectedScenario(scenarioId)
  }, [])

  useEffect(() => {
    if (pattern && onAnalysisComplete) {
      onAnalysisComplete(pattern)
    }
  }, [pattern, onAnalysisComplete])

  if (loading) {
    return <div className="animate-pulse">分析中...</div>
  }

  if (error) {
    return <div className="text-red-500">エラー: {error.message}</div>
  }

  return (
    <div className="race-pattern-container">
      {/* 実装 */}
    </div>
  )
}
```

### 2.3 C#（.NET）

#### 2.3.1 基本規約
- **Microsoft C# Coding Conventions**: 準拠
- **StyleCop**: 静的解析
- **nullable reference types**: 有効化

#### 2.3.2 命名規則
```csharp
// ファイル名: PascalCase
RaceDataService.cs
JraVanApiClient.cs

// クラス名: PascalCase
public class RaceDataService
{
    // プロパティ: PascalCase
    public string RaceId { get; set; }
    
    // メソッド: PascalCase
    public async Task<RaceData> GetRaceDataAsync(string raceId)
    {
        // ローカル変数: camelCase
        var apiClient = new JraVanApiClient();
        return await apiClient.FetchRaceDataAsync(raceId);
    }
    
    // 定数: PascalCase
    private const int MaxRetryCount = 3;
}
```

## 3. Git運用ルール

### 3.1 ブランチ戦略

#### 3.1.1 ブランチ構成
```
main
├── develop
├── feature/YYMMDD-XXX-feature-name
├── hotfix/YYMMDD-XXX-hotfix-name
└── release/vX.X.X
```

#### 3.1.2 ブランチ運用
- **main**: 本番環境用（常に安定）
- **develop**: 開発統合用
- **feature**: 機能開発用
- **hotfix**: 緊急修正用
- **release**: リリース準備用

### 3.2 コミットメッセージ

#### 3.2.1 形式
```
<type>(<scope>): <subject>

<body>

<footer>
```

#### 3.2.2 例
```
feat(api): レース質分析エンドポイントを追加

- GET /api/v1/races/{race_id}/pattern-analysis を実装
- レース展開シミュレーション機能を含む
- 3D可視化用データも同時に返却

Task: 250607-002
```

### 3.3 プルリクエスト

#### 3.3.1 作成基準
- 機能単位での作成
- 差分は400行以下を推奨
- 自己レビュー完了後に作成

#### 3.3.2 レビュー基準
- 最低1名のレビュー必須
- CI/CDパス必須
- コードカバレッジ維持

## 4. テスト戦略

### 4.1 テスト種別

#### 4.1.1 単体テスト
```python
# Python (pytest)
import pytest
from unittest.mock import Mock, patch

class TestRacePatternAnalyzer:
    @pytest.fixture
    def analyzer(self):
        mock_db = Mock()
        return RacePatternAnalyzer(mock_db)
    
    @pytest.mark.asyncio
    async def test_analyze_race_pattern_success(self, analyzer):
        # Given
        race_id = "202501050111"
        
        # When
        result = await analyzer.analyze_race_pattern(race_id)
        
        # Then
        assert result.race_id == race_id
        assert result.expected_pace is not None
```

```typescript
// TypeScript (Jest + Testing Library)
import { render, screen, fireEvent } from '@testing-library/react'
import { RacePatternVisualizer } from './RacePatternVisualizer'

describe('RacePatternVisualizer', () => {
  it('should display race pattern analysis', () => {
    // Given
    const raceId = '202501050111'
    
    // When
    render(<RacePatternVisualizer raceId={raceId} />)
    
    // Then
    expect(screen.getByText('レース質分析')).toBeInTheDocument()
  })
})
```

#### 4.1.2 統合テスト
```python
# API統合テスト
import pytest
from fastapi.testclient import TestClient
from src.analysis.api.main import app

client = TestClient(app)

def test_get_race_pattern_analysis():
    # Given
    race_id = "202501050111"
    
    # When
    response = client.get(f"/api/v1/races/{race_id}/pattern-analysis")
    
    # Then
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["race_id"] == race_id
```

### 4.2 テストカバレッジ

#### 4.2.1 目標値
- **単体テスト**: 80%以上
- **統合テスト**: 主要パス100%
- **E2Eテスト**: クリティカルパス100%

#### 4.2.2 測定方法
```bash
# Python
pytest --cov=src --cov-report=html

# TypeScript
npm run test:coverage

# C#
dotnet test --collect:"XPlat Code Coverage"
```

## 5. CI/CD

### 5.1 GitHub Actions

#### 5.1.1 ワークフロー構成
```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest --cov=src
```

### 5.2 デプロイメント

#### 5.2.1 環境構成
- **開発環境**: feature/developブランチ自動デプロイ
- **ステージング環境**: releaseブランチ手動デプロイ
- **本番環境**: mainブランチ承認後デプロイ

## 6. セキュリティ

### 6.1 セキュリティチェック

#### 6.1.1 静的解析
```bash
# Python
bandit -r src/
safety check

# TypeScript
npm audit
eslint --ext .ts,.tsx src/

# C#
dotnet list package --vulnerable
```

#### 6.1.2 依存関係管理
- **Dependabot**: 自動更新
- **定期監査**: 月次実施
- **脆弱性対応**: 発見後24時間以内

### 6.2 機密情報管理

#### 6.2.1 環境変数
```bash
# .env.example
DATABASE_URL=postgresql://user:pass@localhost:5432/keiba
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key
JRA_VAN_API_KEY=your-api-key
```

#### 6.2.2 シークレット管理
- **開発環境**: .envファイル
- **本番環境**: AWS Secrets Manager / Azure Key Vault
- **CI/CD**: GitHub Secrets

## 7. パフォーマンス

### 7.1 パフォーマンス基準

#### 7.1.1 API応答時間
- **GET**: 200ms以下
- **POST**: 500ms以下
- **分析処理**: 30秒以下

#### 7.1.2 フロントエンド
- **初回ロード**: 2秒以下
- **ページ遷移**: 500ms以下
- **3D描画**: 60fps維持

### 7.2 最適化手法

#### 7.2.1 バックエンド
```python
# キャッシュ活用
from functools import lru_cache
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

@lru_cache(maxsize=128)
def get_course_characteristics(venue: str, distance: int) -> CourseCharacteristics:
    # 実装
    pass

async def get_race_analysis(race_id: str) -> RaceAnalysis:
    # Redisキャッシュチェック
    cached = redis_client.get(f"race_analysis:{race_id}")
    if cached:
        return RaceAnalysis.parse_raw(cached)
    
    # 分析実行
    analysis = await analyze_race(race_id)
    
    # キャッシュ保存（TTL: 1時間）
    redis_client.setex(
        f"race_analysis:{race_id}", 
        3600, 
        analysis.json()
    )
    
    return analysis
```

#### 7.2.2 フロントエンド
```typescript
// React.memo + useMemo活用
import { memo, useMemo } from 'react'

export const RacePatternVisualizer = memo(({ raceId, data }) => {
  const processedData = useMemo(() => {
    return processRacePatternData(data)
  }, [data])

  return (
    <div>
      {/* 実装 */}
    </div>
  )
})

// 動的インポート
const HeavyComponent = lazy(() => import('./HeavyComponent'))
```

## 8. 監視・ログ

### 8.1 ログ設定

#### 8.1.1 Python
```python
import logging
import structlog

# 構造化ログ設定
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()

# 使用例
logger.info("Race analysis started", race_id=race_id, user_id=user_id)
```

#### 8.1.2 TypeScript
```typescript
// Winston設定
import winston from 'winston'

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
})

// 使用例
logger.info('Component rendered', { 
  component: 'RacePatternVisualizer', 
  raceId,
  timestamp: new Date().toISOString()
})
```

### 8.2 メトリクス

#### 8.2.1 アプリケーションメトリクス
```python
from prometheus_client import Counter, Histogram, generate_latest

# メトリクス定義
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'API request duration')

# 使用例
@REQUEST_DURATION.time()
async def analyze_race_pattern(race_id: str):
    REQUEST_COUNT.labels(method='GET', endpoint='/races/pattern-analysis').inc()
    # 実装
```

## 9. ドキュメント

### 9.1 ドキュメント種別

#### 9.1.1 API仕様書
- **OpenAPI/Swagger**: 自動生成
- **更新**: コード変更時自動更新
- **公開**: 開発者ポータルで公開

#### 9.1.2 コードドキュメント
```python
def calculate_expected_value(
    win_probability: float, 
    odds: float, 
    bet_amount: int = 100
) -> float:
    """
    期待値を計算する
    
    期待値 = (勝率 × オッズ × 投資額) - 投資額
    
    Args:
        win_probability: 勝率（0.0-1.0）
        odds: オッズ
        bet_amount: 投資額（デフォルト: 100円）
        
    Returns:
        期待値（円）
        
    Examples:
        >>> calculate_expected_value(0.2, 6.0, 100)
        20.0
        
    Note:
        期待値が正の場合、理論上利益が見込める
    """
    return (win_probability * odds * bet_amount) - bet_amount
```

### 9.2 ドキュメント管理

#### 9.2.1 更新ルール
- **コード変更時**: 関連ドキュメント同時更新
- **レビュー**: ドキュメントもコードレビューに含める
- **バージョン管理**: Gitで管理

## 10. トラブルシューティング

### 10.1 よくある問題

#### 10.1.1 開発環境
```bash
# Docker起動失敗
docker-compose down
docker system prune -f
docker-compose up -d

# 依存関係エラー
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall

# Node.js依存関係エラー
rm -rf node_modules package-lock.json
npm install
```

#### 10.1.2 本番環境
```bash
# メモリ不足
# アプリケーションログ確認
docker logs keiba-api

# データベース接続エラー
# 接続プール設定確認
# ネットワーク設定確認
```

### 10.2 デバッグ手法

#### 10.2.1 Python
```python
# デバッガー使用
import pdb; pdb.set_trace()

# ログレベル変更
import logging
logging.basicConfig(level=logging.DEBUG)

# プロファイリング
import cProfile
cProfile.run('your_function()')
```

#### 10.2.2 TypeScript
```typescript
// ブラウザデバッガー
debugger

// React Developer Tools
// Redux DevTools

// パフォーマンス測定
console.time('render')
// 処理
console.timeEnd('render')
``` 
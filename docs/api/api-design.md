# KeibaCICD API設計書

## 1. API概要

### 1.1 アーキテクチャ
KeibaCICDシステムでは、以下の3つのAPIサーバーを構築します：

- **Analysis API (FastAPI)**: 分析・予測機能
- **JRA-VAN API (C#/.NET)**: JRA-VANデータ連携
- **Authentication API**: 認証・認可機能

### 1.2 共通仕様

#### 1.2.1 ベースURL
```
# 開発環境
https://api-dev.keibacicd.com

# 本番環境
https://api.keibacicd.com
```

#### 1.2.2 認証方式
- **JWT Bearer Token**: API認証
- **OAuth 2.0**: 外部認証連携
- **API Key**: 外部システム連携

#### 1.2.3 共通レスポンス形式
```json
{
  "success": true,
  "data": {...},
  "message": "Success",
  "timestamp": "2025-06-07T10:00:00Z",
  "request_id": "uuid-here"
}

// エラー時
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid race_id format",
    "details": {...}
  },
  "timestamp": "2025-06-07T10:00:00Z",
  "request_id": "uuid-here"
}
```

#### 1.2.4 ページネーション
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  }
}
```

## 2. Analysis API (FastAPI)

### 2.1 レース分析エンドポイント

#### 2.1.1 レース基本情報取得
```http
GET /api/v1/races/{race_id}
```

**パラメータ:**
- `race_id` (string): レースID (YYYYMMDDHHRR形式)

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "race_id": "202501050111",
    "race_name": "京都金杯",
    "venue": {
      "code": "05",
      "name": "京都"
    },
    "race_date": "2025-01-05",
    "race_number": 11,
    "grade": "G3",
    "distance": 1600,
    "track_type": "芝",
    "direction": "右",
    "weather": "晴",
    "track_condition": "良",
    "entry_count": 16,
    "prize_money": 74000000
  }
}
```

#### 2.1.2 レース質分析取得
```http
GET /api/v1/races/{race_id}/pattern-analysis
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "race_id": "202501050111",
    "course_characteristics": {
      "venue": "京都",
      "distance": 1600,
      "track_type": "芝",
      "straight_length": 404,
      "has_slope": true,
      "favorable_post": "外枠",
      "favorable_style": "差し"
    },
    "runner_distribution": {
      "total_runners": 16,
      "style_counts": {
        "逃げ": 1,
        "先行": 4,
        "差し": 8,
        "追込": 3
      },
      "pace_makers": [1, 3],
      "strong_closers": [7, 11, 14]
    },
    "expected_pace": {
      "type": "ミドル",
      "score": 0.65,
      "factors": [
        "先行馬が多い",
        "距離が1600mで中距離",
        "外枠有利のコース"
      ]
    },
    "race_flow_scenarios": [
      {
        "scenario_id": 1,
        "name": "逃げ馬主導の展開",
        "probability": 0.45,
        "description": "1番馬が逃げて、中団から差し馬が追い込む展開",
        "favorable_horses": [7, 11, 14],
        "critical_points": [
          {"distance": 600, "description": "勝負どころ"},
          {"distance": 200, "description": "直線入口"}
        ]
      }
    ],
    "visualization_data": {
      "course_path": [...],
      "camera_positions": [...]
    }
  }
}
```

#### 2.1.3 期待値計算結果取得
```http
GET /api/v1/races/{race_id}/expected-values
```

**クエリパラメータ:**
- `min_expected_value` (float): 最小期待値フィルタ
- `sort` (string): ソート順 ("expected_value_desc", "probability_desc")

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "race_id": "202501050111",
    "calculated_at": "2025-06-07T09:30:00Z",
    "model_version": "v2.1",
    "horses": [
      {
        "horse_number": 7,
        "umacd": "2019104567",
        "horse_name": "サンプルホース",
        "win_probability": 0.125,
        "place_probability": 0.350,
        "current_odds": {
          "win": 8.5,
          "place": 2.8
        },
        "expected_value": {
          "win": 1.06,
          "place": 0.98
        },
        "recommendation_level": 3,
        "confidence_score": 0.82,
        "factors": [
          "コース適性が高い",
          "前走好走",
          "騎手との相性良好"
        ]
      }
    ],
    "summary": {
      "total_horses": 16,
      "recommended_horses": 3,
      "avg_expected_value": 1.02
    }
  }
}
```

### 2.2 馬分析エンドポイント

#### 2.2.1 馬の基本情報取得
```http
GET /api/v1/horses/{umacd}
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "umacd": "2019104567",
    "horse_name": "サンプルホース",
    "horse_name_kana": "サンプルホース",
    "birth_date": "2019-04-15",
    "sex": "牡",
    "coat_color": "鹿毛",
    "pedigree": {
      "sire": {
        "umacd": "2010123456",
        "name": "父馬名"
      },
      "dam": {
        "umacd": "2012234567",
        "name": "母馬名"
      }
    },
    "connections": {
      "owner": "オーナー名",
      "trainer": "調教師名",
      "stable": "厩舎名"
    }
  }
}
```

#### 2.2.2 馬の性格分析取得
```http
GET /api/v1/horses/{umacd}/personality
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "umacd": "2019104567",
    "personality_type": "勇敢な先行馬",
    "traits": {
      "courage": 0.85,
      "dexterity": 0.70,
      "concentration": 0.75,
      "stamina": 0.80,
      "speed": 0.90,
      "power": 0.75
    },
    "preferred_conditions": {
      "distance_range": [1400, 2000],
      "track_types": ["芝"],
      "pace_preference": "ミドル",
      "weather_preference": ["晴", "曇"]
    },
    "running_style": "先行",
    "character_description": "積極的に前に行きたがる性格で、ペースが上がっても粘り強く走る。直線では末脚を発揮するタイプ。",
    "confidence_score": 0.82,
    "sample_count": 25,
    "last_analyzed": "2025-06-07T08:00:00Z"
  }
}
```

#### 2.2.3 馬のレース適性分析
```http
GET /api/v1/horses/{umacd}/race-compatibility/{race_id}
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "umacd": "2019104567",
    "race_id": "202501050111",
    "compatibility": {
      "overall_score": 0.78,
      "style_match": 0.85,
      "pace_match": 0.70,
      "course_match": 0.80,
      "distance_match": 0.75
    },
    "recommendation": {
      "level": 4,
      "message": "この馬にとって好条件のレース。積極的な投資を推奨。",
      "key_factors": [
        "得意なコース形態",
        "適性距離内",
        "好ペース想定"
      ]
    },
    "risk_factors": [
      "前走から中1週と間隔が短い"
    ]
  }
}
```

### 2.3 統合分析エンドポイント

#### 2.3.1 レース統合分析
```http
GET /api/v1/races/{race_id}/integrated-analysis
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "race_id": "202501050111",
    "race_pattern": {
      // レース質分析結果
    },
    "horses": [
      {
        "horse_number": 7,
        "basic_info": {
          // 馬基本情報
        },
        "personality": {
          // 性格分析結果
        },
        "compatibility": {
          // レース適性
        },
        "expected_value": {
          // 期待値計算結果
        }
      }
    ],
    "ai_commentary": {
      "race_overview": "ミドルペースが想定される中距離戦。外枠の差し馬に注目。",
      "key_horses": [7, 11, 14],
      "betting_strategy": "7番を軸に、11番、14番との馬連・3連複を推奨。"
    }
  }
}
```

### 2.4 リアルタイム更新エンドポイント

#### 2.4.1 WebSocket接続
```
WSS /api/v1/ws/races/{race_id}/live-updates
```

**送信メッセージ例:**
```json
{
  "type": "odds_update",
  "race_id": "202501050111",
  "timestamp": "2025-06-07T10:30:00Z",
  "data": {
    "horse_number": 7,
    "odds": {
      "win": 8.2,
      "place": 2.7
    },
    "change": {
      "win": -0.3,
      "place": -0.1
    }
  }
}
```

## 3. JRA-VAN API (C#/.NET)

### 3.1 データ取得エンドポイント

#### 3.1.1 リアルタイムレースデータ
```http
GET /api/v1/jravan/races/{race_id}/realtime
```

#### 3.1.2 オッズ情報取得
```http
GET /api/v1/jravan/races/{race_id}/odds
```

#### 3.1.3 出走表データ
```http
GET /api/v1/jravan/races/{race_id}/entries
```

### 3.2 データ同期エンドポイント

#### 3.2.1 データ同期状況確認
```http
GET /api/v1/jravan/sync/status
```

#### 3.2.2 手動同期実行
```http
POST /api/v1/jravan/sync/trigger
```

## 4. Authentication API

### 4.1 認証エンドポイント

#### 4.1.1 ログイン
```http
POST /api/v1/auth/login
```

**リクエスト:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**レスポンス:**
```json
{
  "success": true,
  "data": {
    "access_token": "jwt-token-here",
    "refresh_token": "refresh-token-here",
    "expires_in": 3600,
    "user": {
      "user_id": "uuid-here",
      "email": "user@example.com",
      "display_name": "ユーザー名",
      "role": "premium"
    }
  }
}
```

#### 4.1.2 トークン更新
```http
POST /api/v1/auth/refresh
```

#### 4.1.3 ログアウト
```http
POST /api/v1/auth/logout
```

### 4.2 ユーザー管理エンドポイント

#### 4.2.1 ユーザー情報取得
```http
GET /api/v1/users/me
```

#### 4.2.2 ユーザー設定更新
```http
PUT /api/v1/users/me/preferences
```

## 5. エラーハンドリング

### 5.1 HTTPステータスコード

| コード | 説明 | 用途 |
|--------|------|------|
| 200 | OK | 正常処理 |
| 201 | Created | リソース作成成功 |
| 400 | Bad Request | リクエスト形式エラー |
| 401 | Unauthorized | 認証エラー |
| 403 | Forbidden | 認可エラー |
| 404 | Not Found | リソース未発見 |
| 429 | Too Many Requests | レート制限 |
| 500 | Internal Server Error | サーバーエラー |

### 5.2 エラーコード一覧

```json
{
  "VALIDATION_ERROR": "入力値検証エラー",
  "RACE_NOT_FOUND": "指定されたレースが見つかりません",
  "HORSE_NOT_FOUND": "指定された馬が見つかりません",
  "ANALYSIS_NOT_READY": "分析結果がまだ準備できていません",
  "INSUFFICIENT_DATA": "分析に必要なデータが不足しています",
  "MODEL_ERROR": "予測モデルでエラーが発生しました",
  "RATE_LIMIT_EXCEEDED": "API呼び出し制限を超過しました",
  "MAINTENANCE_MODE": "メンテナンス中です"
}
```

## 6. レート制限

### 6.1 制限値

| エンドポイント | 制限 | 期間 |
|---------------|------|------|
| 一般API | 1000回 | 1時間 |
| 分析API | 100回 | 1時間 |
| WebSocket | 10接続 | 同時 |
| 認証API | 10回 | 1分 |

### 6.2 レスポンスヘッダー

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1625097600
```

## 7. セキュリティ

### 7.1 CORS設定
```
Access-Control-Allow-Origin: https://app.keibacicd.com
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
```

### 7.2 セキュリティヘッダー
```http
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

## 8. API仕様書生成

### 8.1 OpenAPI/Swagger
- **FastAPI**: 自動生成 (`/docs`, `/redoc`)
- **C#/.NET**: Swashbuckle.AspNetCore
- **統合**: Swagger UI での一元管理

### 8.2 ドキュメント更新
- **自動更新**: CI/CDパイプラインで自動生成
- **バージョン管理**: APIバージョンごとの仕様書管理
- **変更通知**: API変更時の自動通知システム 
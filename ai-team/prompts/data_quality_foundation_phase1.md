# データ品質基盤 Phase 1 実装プロンプト

**作成日**: 2026-01-31
**優先度**: ⭐⭐⭐⭐⭐（最優先）
**工数見積**: 1-2日
**目的**: AIエージェントが自動でデータ品質を確認できる基盤を構築

---

## 📋 概要

競馬予想AIシステムにおいて、**データ品質の保証**は最重要課題です。AIが不完全なデータで予想すると、精度が大きく低下します。

Phase 1では、以下の3つのAPIを実装します：

1. **データ取得ステータスAPI** - どのデータが取得済みか可視化
2. **データ検証API** - 異常値・欠損値の検出
3. **ヘルスチェックAPI** - システム全体の健全性監視

---

## 🎯 実装するAPI

### 1. データ取得ステータスAPI

#### エンドポイント
```
GET  /api/data/status?date=20260131
POST /api/data/status
```

#### 目的
指定日のデータ取得状況を確認し、不足データを検出する。

#### GET パラメータ
```typescript
{
  date: string  // YYYYMMDD形式（例: 20260131）
}
```

#### GET レスポンス
```json
{
  "date": "20260131",
  "status": {
    "race_info": {
      "status": "success",           // success | partial | missing | error
      "updated_at": "2026-01-31T08:00:00Z",
      "count": 36,
      "missing_races": []
    },
    "odds": {
      "status": "success",
      "updated_at": "2026-01-31T09:30:00Z",
      "count": 36,
      "missing_races": []
    },
    "training": {
      "status": "partial",
      "updated_at": "2026-01-31T07:00:00Z",
      "count": 150,
      "errors": ["馬ID不明: 3件"],
      "missing_horses": ["2019103487", "2020102345", "2021105678"]
    },
    "baba": {
      "status": "missing",
      "updated_at": null,
      "message": "馬場データ未取得"
    },
    "integrated": {
      "status": "success",
      "updated_at": "2026-01-31T10:00:00Z",
      "count": 36
    }
  },
  "completeness": 85,  // 完全性スコア（%）
  "summary": {
    "total_data_types": 5,
    "success": 3,
    "partial": 1,
    "missing": 1,
    "error": 0
  }
}
```

#### POST リクエスト（ステータス更新）
```json
{
  "date": "20260131",
  "data_type": "odds",  // race_info | odds | training | baba | integrated
  "status": "success",
  "count": 36,
  "errors": []
}
```

#### 実装要件

**データソース確認**:
```javascript
// 確認すべきファイル・ディレクトリ
const dataSources = {
  race_info: `${KEIBA_DATA_ROOT_DIR}/races/${year}/${month}/${day}/race_info.json`,
  odds: `${JV_DATA_ROOT_DIR}/RT_DATA/${date}`, // または JI_2026
  training: `${JV_DATA_ROOT_DIR}/CK/CK_${date}.txt`,
  baba: `${JV_DATA_ROOT_DIR}/_BABA/cushion${year}.csv`,
  integrated: `${KEIBA_DATA_ROOT_DIR}/races/${year}/${month}/${day}/temp/integrated_*.json`
};
```

**完全性スコアの計算**:
```javascript
function calculateCompleteness(status) {
  const weights = {
    race_info: 30,    // 最重要
    odds: 25,
    training: 20,
    baba: 15,
    integrated: 10
  };

  let score = 0;
  for (const [key, weight] of Object.entries(weights)) {
    if (status[key].status === 'success') {
      score += weight;
    } else if (status[key].status === 'partial') {
      score += weight * 0.5;
    }
  }

  return Math.round(score);
}
```

**実装場所**: `keiba-cicd-core/KeibaCICD.WebViewer/src/app/api/data/status/route.ts`

---

### 2. データ検証API

#### エンドポイント
```
GET /api/data/validate?date=20260131&type=race
```

#### 目的
データの異常値・欠損値・整合性を検証する。

#### パラメータ
```typescript
{
  date: string,      // YYYYMMDD形式
  type: string       // race | horse | odds | training | all
}
```

#### レスポンス
```json
{
  "date": "20260131",
  "type": "race",
  "validation": {
    "race_2026013105010101": {
      "valid": false,
      "errors": [
        {
          "field": "horse_count",
          "expected": ">= 5",
          "actual": 0,
          "severity": "critical",
          "message": "出走馬数が0頭"
        },
        {
          "field": "start_time",
          "expected": "past or near future",
          "actual": "2027-01-31T10:05:00Z",
          "severity": "error",
          "message": "発走時刻が1年以上未来"
        }
      ],
      "warnings": [
        {
          "field": "odds",
          "message": "オッズデータが古い（2時間前）",
          "severity": "warning"
        }
      ]
    },
    "race_2026013105010102": {
      "valid": true,
      "errors": [],
      "warnings": []
    }
  },
  "summary": {
    "total": 36,
    "valid": 35,
    "invalid": 1,
    "warnings_count": 1
  }
}
```

#### 検証ルール

**レースデータ検証**:
```javascript
const raceValidationRules = {
  horse_count: {
    min: 5,
    max: 18,
    severity: 'critical'
  },
  start_time: {
    check: (time) => {
      const now = new Date();
      const startTime = new Date(time);
      const diff = startTime - now;
      return diff >= -86400000 && diff <= 86400000 * 7; // 過去1日～未来7日
    },
    severity: 'error'
  },
  distance: {
    min: 1000,
    max: 4000,
    severity: 'error'
  },
  track: {
    allowed: ['芝', 'ダート', '障害'],
    severity: 'error'
  },
  venue: {
    allowed: ['札幌', '函館', '福島', '新潟', '東京', '中山', '中京', '京都', '阪神', '小倉'],
    severity: 'error'
  }
};
```

**馬データ検証**:
```javascript
const horseValidationRules = {
  age: {
    min: 2,
    max: 12,
    severity: 'error'
  },
  weight: {
    min: 400,
    max: 600,
    severity: 'warning'
  },
  jockey: {
    notEmpty: true,
    severity: 'error'
  }
};
```

**オッズデータ検証**:
```javascript
const oddsValidationRules = {
  odds_value: {
    min: 1.0,
    max: 999.9,
    severity: 'error'
  },
  updated_at: {
    check: (time) => {
      const now = new Date();
      const updated = new Date(time);
      return now - updated <= 3600000 * 3; // 3時間以内
    },
    severity: 'warning'
  }
};
```

**実装場所**: `keiba-cicd-core/KeibaCICD.WebViewer/src/app/api/data/validate/route.ts`

---

### 3. ヘルスチェックAPI

#### エンドポイント
```
GET /api/health
```

#### 目的
システム全体の健全性を監視し、異常を早期検出する。

#### レスポンス
```json
{
  "status": "healthy",  // healthy | degraded | unhealthy
  "timestamp": "2026-01-31T10:00:00Z",
  "uptime": 86400,  // 秒
  "components": {
    "api": {
      "status": "up",
      "response_time_ms": 50,
      "last_check": "2026-01-31T10:00:00Z"
    },
    "file_system": {
      "status": "up",
      "free_space_gb": 500,
      "total_space_gb": 1000,
      "usage_percent": 50,
      "paths": {
        "KEIBA_DATA_ROOT_DIR": {
          "exists": true,
          "writable": true,
          "free_gb": 300
        },
        "JV_DATA_ROOT_DIR": {
          "exists": true,
          "writable": true,
          "free_gb": 200
        }
      }
    },
    "python_executor": {
      "status": "up",
      "version": "3.11.5",
      "queue_size": 0,
      "last_execution": "2026-01-31T09:30:00Z"
    },
    "data_freshness": {
      "status": "up",
      "latest_date": "2026-01-31",
      "age_hours": 2,
      "threshold_hours": 24
    }
  },
  "metrics": {
    "api_requests_24h": 1500,
    "errors_24h": 5,
    "avg_response_time_ms": 120,
    "data_fetch_success_rate": 98.5
  },
  "issues": []  // 問題がある場合はここに配列
}
```

#### 異常時のレスポンス
```json
{
  "status": "degraded",
  "timestamp": "2026-01-31T10:00:00Z",
  "components": {
    "file_system": {
      "status": "degraded",
      "free_space_gb": 10,
      "usage_percent": 99,
      "message": "ディスク容量不足"
    },
    "data_freshness": {
      "status": "down",
      "latest_date": "2026-01-29",
      "age_hours": 50,
      "threshold_hours": 24,
      "message": "データが2日前"
    }
  },
  "issues": [
    {
      "component": "file_system",
      "severity": "warning",
      "message": "ディスク容量が10GB以下です",
      "action": "古いデータを削除してください"
    },
    {
      "component": "data_freshness",
      "severity": "error",
      "message": "データが24時間以上古いです",
      "action": "データ取得スクリプトを実行してください"
    }
  ]
}
```

#### 実装要件

**ステータス判定ロジック**:
```javascript
function determineOverallStatus(components) {
  const statuses = Object.values(components).map(c => c.status);

  if (statuses.some(s => s === 'down')) {
    return 'unhealthy';
  }
  if (statuses.some(s => s === 'degraded')) {
    return 'degraded';
  }
  return 'healthy';
}
```

**ファイルシステムチェック**:
```javascript
import { statfs } from 'fs';
import { promisify } from 'util';

async function checkFileSystem(path) {
  try {
    const stats = await promisify(statfs)(path);
    const totalSpace = stats.blocks * stats.bsize;
    const freeSpace = stats.bfree * stats.bsize;
    const usagePercent = ((totalSpace - freeSpace) / totalSpace) * 100;

    return {
      status: usagePercent > 95 ? 'degraded' : 'up',
      free_space_gb: Math.round(freeSpace / 1024 / 1024 / 1024),
      total_space_gb: Math.round(totalSpace / 1024 / 1024 / 1024),
      usage_percent: Math.round(usagePercent)
    };
  } catch (error) {
    return {
      status: 'down',
      error: error.message
    };
  }
}
```

**データ鮮度チェック**:
```javascript
async function checkDataFreshness() {
  const raceDatesFile = path.join(KEIBA_DATA_ROOT_DIR, 'race_dates.json');
  const dates = JSON.parse(await fs.readFile(raceDatesFile, 'utf-8'));

  const latestDate = dates[0]; // 最新日付
  const now = new Date();
  const latest = new Date(latestDate);
  const ageHours = (now - latest) / 1000 / 3600;

  return {
    status: ageHours > 24 ? 'down' : 'up',
    latest_date: latestDate,
    age_hours: Math.round(ageHours),
    threshold_hours: 24
  };
}
```

**実装場所**: `keiba-cicd-core/KeibaCICD.WebViewer/src/app/api/health/route.ts`

---

## 🔧 共通実装ガイドライン

### 環境変数
```typescript
const KEIBA_DATA_ROOT_DIR = process.env.KEIBA_DATA_ROOT_DIR || 'E:\\share\\KEIBA-CICD\\data2';
const JV_DATA_ROOT_DIR = process.env.JV_DATA_ROOT_DIR || 'E:\\TFJV';
```

### エラーハンドリング
```typescript
export async function GET(request: Request) {
  try {
    // API処理
    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error('[API Error]', error);
    return NextResponse.json(
      {
        error: error.message,
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    );
  }
}
```

### ログ出力
```typescript
// 成功ログ
console.log('[Data Status API] Success:', { date, completeness });

// エラーログ
console.error('[Data Status API] Error:', { date, error: error.message });

// 警告ログ
console.warn('[Data Validation] Warning:', { date, warnings });
```

### CORS設定
```typescript
const headers = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type'
};
```

---

## 🧪 テストケース

### 1. データ取得ステータスAPI

**テスト1: 全データ取得済み**
```bash
curl "http://localhost:3000/api/data/status?date=20260131"
# 期待: completeness = 100, すべて "success"
```

**テスト2: 一部データ欠損**
```bash
curl "http://localhost:3000/api/data/status?date=20260201"
# 期待: completeness < 100, 一部 "missing"
```

**テスト3: ステータス更新**
```bash
curl -X POST "http://localhost:3000/api/data/status" \
  -H "Content-Type: application/json" \
  -d '{"date":"20260131","data_type":"odds","status":"success","count":36}'
# 期待: 200 OK
```

---

### 2. データ検証API

**テスト1: レースデータ検証**
```bash
curl "http://localhost:3000/api/data/validate?date=20260131&type=race"
# 期待: 検証結果と異常値の配列
```

**テスト2: 全データ検証**
```bash
curl "http://localhost:3000/api/data/validate?date=20260131&type=all"
# 期待: すべてのデータタイプの検証結果
```

---

### 3. ヘルスチェックAPI

**テスト1: 正常時**
```bash
curl "http://localhost:3000/api/health"
# 期待: status = "healthy"
```

**テスト2: 異常検出**
```bash
# ディスク容量を意図的に減らして確認
curl "http://localhost:3000/api/health"
# 期待: status = "degraded" または "unhealthy"
```

---

## 📊 データフロー図

```
【データ取得】
KIBA（データ追跡） → データ取得スクリプト実行
                   ↓
           ファイルシステムに保存
                   ↓
     POST /api/data/status でステータス更新

【データ検証】
GUARDIAN（リスク管理） → GET /api/data/validate
                        ↓
                    検証ルール適用
                        ↓
                   異常値を検出・報告

【ヘルスチェック】
COMMANDER（全体統括） → GET /api/health
                       ↓
                 全コンポーネント確認
                       ↓
                  異常があればアラート
```

---

## 🎯 AI活用ポイント

### KIBA（データ追跡）
```python
import requests

def check_data_status(date):
    response = requests.get(f"http://localhost:3000/api/data/status?date={date}")
    data = response.json()

    if data["completeness"] < 80:
        print(f"⚠️ データ完全性が低い: {data['completeness']}%")

        # 不足データを特定
        for key, status in data["status"].items():
            if status["status"] in ["missing", "partial"]:
                print(f"  - {key}: {status['status']}")
                # 自動取得を試みる
                auto_fetch_data(date, key)
```

### GUARDIAN（リスク管理）
```python
def validate_before_prediction(date):
    response = requests.get(f"http://localhost:3000/api/data/validate?date={date}&type=all")
    data = response.json()

    critical_errors = [
        error for race in data["validation"].values()
        for error in race.get("errors", [])
        if error["severity"] == "critical"
    ]

    if critical_errors:
        print("🚨 致命的エラー検出 - 予想を中止")
        return False

    return True
```

### COMMANDER（全体統括）
```python
def morning_health_check():
    response = requests.get("http://localhost:3000/api/health")
    health = response.json()

    if health["status"] != "healthy":
        print(f"⚠️ システムステータス: {health['status']}")

        for issue in health.get("issues", []):
            print(f"  - [{issue['severity']}] {issue['message']}")
            print(f"    対策: {issue['action']}")
```

---

## 📚 参照ドキュメント

- [WEBVIEWER_API_SPECIFICATION.md](../../keiba-cicd-core/KeibaCICD.WebViewer/docs/api/WEBVIEWER_API_SPECIFICATION.md) - 既存API仕様
- [DATA_SPECIFICATION.md](../knowledge/DATA_SPECIFICATION.md) - データ仕様統一
- [AI_DATA_ACCESS_GUIDE.md](../knowledge/AI_DATA_ACCESS_GUIDE.md) - AI実装ガイド

---

## ✅ 完了チェックリスト

### API実装
- [ ] データ取得ステータスAPI（GET/POST）
- [ ] データ検証API（GET）
- [ ] ヘルスチェックAPI（GET）

### テスト
- [ ] 各APIの単体テスト実施
- [ ] 異常系テスト実施
- [ ] AI連携テスト（KIBA、GUARDIAN等）

### ドキュメント
- [ ] API仕様書に追記
- [ ] AI_DATA_ACCESS_GUIDEに使用例追記

---

## 🚀 次のステップ（Phase 2）

Phase 1完了後、以下に進む：

1. **データ更新履歴API** - いつ・誰が・何を更新したか記録
2. **エラーログ統合API** - エラーの一元管理
3. **データ取得ダッシュボードUI** - 可視化

---

**作成者**: カカシ（AI相談役）
**承認者**: ふくだ君
**実装者**: Cursor / Claude / 開発チーム

---

それでは実装を開始しましょう！🚀

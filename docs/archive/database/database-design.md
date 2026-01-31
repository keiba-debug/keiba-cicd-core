# KeibaCICD データベース設計書

## 1. データベース概要

### 1.1 データベース構成
KeibaCICDシステムでは、用途に応じて複数のデータベースを使い分けます：

- **PostgreSQL**: 構造化データ（レース結果、馬情報、ユーザーデータ）
- **MongoDB**: 非構造化データ（スクレイピング生データ、分析結果）
- **Redis**: キャッシュ、セッション管理
- **Elasticsearch**: 全文検索、ログ分析

### 1.2 データベース選択理由

| データベース | 用途 | 選択理由 |
|-------------|------|----------|
| PostgreSQL | メインデータ | ACID特性、複雑なクエリ、リレーション管理 |
| MongoDB | ドキュメント | 柔軟なスキーマ、JSON形式データ、水平スケーリング |
| Redis | キャッシュ | 高速アクセス、TTL機能、Pub/Sub |
| Elasticsearch | 検索・分析 | 全文検索、集計機能、ログ分析 |

## 2. PostgreSQL設計

### 2.1 基本設計方針
- **正規化**: 第3正規形まで正規化
- **命名規則**: snake_case、複数形テーブル名
- **主キー**: 自動採番ID + ビジネスキー
- **外部キー**: 参照整合性の確保
- **インデックス**: パフォーマンス重視の設計

### 2.2 テーブル設計

#### 2.2.1 競馬場・コース関連

```sql
-- 競馬場マスタ
CREATE TABLE venues (
    id SERIAL PRIMARY KEY,
    venue_code VARCHAR(2) NOT NULL UNIQUE,
    venue_name VARCHAR(20) NOT NULL,
    location VARCHAR(50),
    established_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- コース特性マスタ
CREATE TABLE course_characteristics (
    id SERIAL PRIMARY KEY,
    venue_code VARCHAR(2) NOT NULL,
    distance INTEGER NOT NULL,
    track_type VARCHAR(10) NOT NULL, -- '芝', 'ダート', '障害'
    direction VARCHAR(10) NOT NULL,  -- '右', '左', '直線'
    straight_length INTEGER,
    has_slope BOOLEAN DEFAULT FALSE,
    corner_count INTEGER,
    corner_type VARCHAR(20),
    surface_condition VARCHAR(20),
    base_pattern JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(venue_code, distance, track_type, direction),
    FOREIGN KEY (venue_code) REFERENCES venues(venue_code)
);
```

#### 2.2.2 レース関連

```sql
-- レース基本情報
CREATE TABLE races (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(12) NOT NULL UNIQUE, -- YYYYMMDDHHRR形式
    venue_code VARCHAR(2) NOT NULL,
    race_date DATE NOT NULL,
    race_number INTEGER NOT NULL,
    race_name VARCHAR(100),
    grade VARCHAR(10), -- 'G1', 'G2', 'G3', 'OP', 'L', '3勝', '2勝', '1勝', '新馬', '未勝利'
    distance INTEGER NOT NULL,
    track_type VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    weather VARCHAR(20),
    track_condition VARCHAR(20),
    prize_money BIGINT,
    entry_count INTEGER,
    race_time TIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venue_code) REFERENCES venues(venue_code)
);

-- レース質分析結果
CREATE TABLE race_patterns (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(12) NOT NULL,
    expected_pace VARCHAR(20), -- 'スロー', 'ミドル', 'ハイ'
    pace_score DECIMAL(3,2),
    favorable_style VARCHAR(20), -- '逃げ', '先行', '差し', '追込'
    favorable_post VARCHAR(20), -- '内枠', '外枠', '中枠'
    runner_distribution JSONB,
    pace_makers JSONB,
    strong_closers JSONB,
    critical_points JSONB,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);
```

#### 2.2.3 馬関連

```sql
-- 馬基本情報
CREATE TABLE horses (
    id SERIAL PRIMARY KEY,
    umacd VARCHAR(10) NOT NULL UNIQUE, -- JRA-VAN馬コード
    horse_name VARCHAR(50) NOT NULL,
    horse_name_kana VARCHAR(100),
    birth_date DATE,
    sex VARCHAR(10), -- '牡', '牝', 'セ'
    coat_color VARCHAR(20),
    sire_umacd VARCHAR(10),
    dam_umacd VARCHAR(10),
    breeder VARCHAR(100),
    owner VARCHAR(100),
    trainer VARCHAR(50),
    stable VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sire_umacd) REFERENCES horses(umacd),
    FOREIGN KEY (dam_umacd) REFERENCES horses(umacd)
);

-- 馬の性格・特性分析
CREATE TABLE horse_personalities (
    id SERIAL PRIMARY KEY,
    umacd VARCHAR(10) NOT NULL,
    personality_type VARCHAR(50),
    traits JSONB, -- 勇敢さ、器用さ、集中力、スタミナ等
    preferred_distance_min INTEGER,
    preferred_distance_max INTEGER,
    preferred_track_type VARCHAR(10),
    preferred_pace VARCHAR(20),
    running_style VARCHAR(20),
    character_description TEXT,
    confidence_score DECIMAL(3,2),
    sample_count INTEGER,
    last_analyzed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (umacd) REFERENCES horses(umacd)
);

-- 馬のコース適性
CREATE TABLE horse_course_compatibility (
    id SERIAL PRIMARY KEY,
    umacd VARCHAR(10) NOT NULL,
    venue_code VARCHAR(2) NOT NULL,
    distance INTEGER NOT NULL,
    track_type VARCHAR(10) NOT NULL,
    compatibility_score DECIMAL(3,2),
    win_rate DECIMAL(4,3),
    place_rate DECIMAL(4,3),
    sample_count INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(umacd, venue_code, distance, track_type),
    FOREIGN KEY (umacd) REFERENCES horses(umacd),
    FOREIGN KEY (venue_code) REFERENCES venues(venue_code)
);
```

#### 2.2.4 出走・結果関連

```sql
-- 出走情報
CREATE TABLE race_entries (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(12) NOT NULL,
    umacd VARCHAR(10) NOT NULL,
    horse_number INTEGER NOT NULL,
    post_position INTEGER,
    jockey_name VARCHAR(50),
    jockey_weight DECIMAL(3,1),
    horse_weight INTEGER,
    horse_weight_change INTEGER,
    odds_win DECIMAL(6,2),
    odds_place DECIMAL(6,2),
    popularity INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, horse_number),
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    FOREIGN KEY (umacd) REFERENCES horses(umacd)
);

-- レース結果
CREATE TABLE race_results (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(12) NOT NULL,
    umacd VARCHAR(10) NOT NULL,
    horse_number INTEGER NOT NULL,
    finish_position INTEGER,
    finish_time TIME,
    margin VARCHAR(20),
    passing_order VARCHAR(50),
    last_3f_time DECIMAL(3,1),
    corner_positions JSONB,
    jockey_comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    FOREIGN KEY (umacd) REFERENCES horses(umacd)
);
```

#### 2.2.5 予測・分析関連

```sql
-- 期待値計算結果
CREATE TABLE expected_values (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(12) NOT NULL,
    umacd VARCHAR(10) NOT NULL,
    win_probability DECIMAL(4,3),
    place_probability DECIMAL(4,3),
    expected_value_win DECIMAL(4,2),
    expected_value_place DECIMAL(4,2),
    recommendation_level INTEGER, -- 1-5段階
    confidence_score DECIMAL(3,2),
    model_version VARCHAR(20),
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    FOREIGN KEY (umacd) REFERENCES horses(umacd)
);

-- 予測モデル管理
CREATE TABLE prediction_models (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    model_type VARCHAR(30), -- 'random_forest', 'neural_network', 'ensemble'
    parameters JSONB,
    training_data_period DATERANGE,
    accuracy_metrics JSONB,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, model_version)
);
```

#### 2.2.6 ユーザー関連

```sql
-- ユーザー基本情報
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id UUID DEFAULT gen_random_uuid() UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE,
    password_hash VARCHAR(255),
    display_name VARCHAR(100),
    avatar_url VARCHAR(500),
    role VARCHAR(20) DEFAULT 'user', -- 'admin', 'premium', 'user'
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ユーザー設定
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    notification_settings JSONB,
    display_settings JSONB,
    analysis_preferences JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 投資記録
CREATE TABLE betting_records (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    race_id VARCHAR(12) NOT NULL,
    bet_type VARCHAR(20), -- '単勝', '複勝', '馬連', '馬単', '3連複', '3連単'
    bet_amount INTEGER,
    bet_target JSONB, -- 購入した馬番組み合わせ
    odds DECIMAL(6,2),
    result_amount INTEGER,
    profit_loss INTEGER,
    bet_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);
```

### 2.3 インデックス設計

```sql
-- パフォーマンス重視のインデックス
CREATE INDEX idx_races_date_venue ON races(race_date, venue_code);
CREATE INDEX idx_races_grade_distance ON races(grade, distance);
CREATE INDEX idx_race_entries_race_id ON race_entries(race_id);
CREATE INDEX idx_race_results_umacd ON race_results(umacd);
CREATE INDEX idx_horse_personalities_umacd ON horse_personalities(umacd);
CREATE INDEX idx_expected_values_race_recommendation ON expected_values(race_id, recommendation_level DESC);
CREATE INDEX idx_betting_records_user_date ON betting_records(user_id, bet_date DESC);

-- 複合インデックス
CREATE INDEX idx_course_characteristics_lookup ON course_characteristics(venue_code, distance, track_type);
CREATE INDEX idx_horse_course_compatibility_lookup ON horse_course_compatibility(umacd, venue_code, distance);
```

## 3. MongoDB設計

### 3.1 コレクション設計

#### 3.1.1 スクレイピング生データ

```javascript
// races_raw コレクション
{
  "_id": ObjectId(),
  "race_id": "202501050111",
  "source": "keibabook",
  "scraped_at": ISODate(),
  "raw_data": {
    // 競馬ブックから取得した生データ
    "race_info": {...},
    "entries": [...],
    "odds": {...}
  },
  "processed": false,
  "processing_errors": []
}

// horses_raw コレクション
{
  "_id": ObjectId(),
  "umacd": "2019104567",
  "source": "keibabook",
  "scraped_at": ISODate(),
  "raw_data": {
    "profile": {...},
    "race_history": [...],
    "pedigree": {...}
  },
  "processed": false
}
```

#### 3.1.2 分析結果データ

```javascript
// race_analysis コレクション
{
  "_id": ObjectId(),
  "race_id": "202501050111",
  "analysis_type": "race_pattern",
  "analysis_version": "v2.1",
  "results": {
    "pace_analysis": {
      "expected_pace": "ミドル",
      "pace_score": 0.65,
      "factors": [...]
    },
    "flow_scenarios": [
      {
        "scenario_id": 1,
        "name": "逃げ馬主導の展開",
        "probability": 0.45,
        "positions": [...],
        "critical_points": [...]
      }
    ],
    "visualization_data": {
      "course_path": [...],
      "camera_positions": [...]
    }
  },
  "analyzed_at": ISODate(),
  "confidence_score": 0.82
}

// horse_analysis コレクション
{
  "_id": ObjectId(),
  "umacd": "2019104567",
  "analysis_type": "personality",
  "analysis_version": "v1.3",
  "results": {
    "personality_traits": {
      "courage": 0.75,
      "dexterity": 0.60,
      "concentration": 0.85,
      "stamina": 0.70
    },
    "character_type": "勇敢な先行馬",
    "preferred_conditions": {
      "distance_range": [1400, 2000],
      "track_types": ["芝"],
      "pace_preference": "ミドル"
    },
    "race_compatibility": {
      "202501050111": {
        "overall_score": 0.78,
        "style_match": 0.85,
        "pace_match": 0.70,
        "course_match": 0.80
      }
    }
  },
  "analyzed_at": ISODate(),
  "sample_races": 25
}
```

### 3.2 インデックス設計

```javascript
// パフォーマンス用インデックス
db.races_raw.createIndex({"race_id": 1, "source": 1});
db.races_raw.createIndex({"scraped_at": -1});
db.races_raw.createIndex({"processed": 1});

db.race_analysis.createIndex({"race_id": 1, "analysis_type": 1});
db.race_analysis.createIndex({"analyzed_at": -1});

db.horse_analysis.createIndex({"umacd": 1, "analysis_type": 1});
db.horse_analysis.createIndex({"analysis_version": 1});
```

## 4. Redis設計

### 4.1 キー設計規則

```
# 命名規則: {service}:{type}:{identifier}:{sub_key}
keiba:cache:race:{race_id}
keiba:cache:horse:{umacd}
keiba:session:{user_id}
keiba:odds:{race_id}:{horse_number}
keiba:analysis:{race_id}:{analysis_type}
```

### 4.2 データ構造

```redis
# レースキャッシュ (Hash)
HSET keiba:cache:race:202501050111 
  "basic_info" "{\"race_name\":\"...\", \"distance\":1600}"
  "entries" "[{\"horse_number\":1, \"umacd\":\"...\"}]"
  "analysis" "{\"expected_pace\":\"ミドル\"}"
  "updated_at" "2025-06-07T10:00:00Z"

# オッズ情報 (Sorted Set)
ZADD keiba:odds:202501050111:win 3.2 1 5.8 2 12.5 3

# セッション (Hash + TTL)
HSET keiba:session:user123
  "user_id" "uuid-here"
  "role" "premium"
  "last_activity" "2025-06-07T10:00:00Z"
EXPIRE keiba:session:user123 3600

# リアルタイム通知 (Pub/Sub)
PUBLISH keiba:notifications:odds_update "{\"race_id\":\"202501050111\", \"changes\":[...]}"
```

## 5. Elasticsearch設計

### 5.1 インデックス設計

```json
// horses インデックス
{
  "mappings": {
    "properties": {
      "umacd": {"type": "keyword"},
      "horse_name": {
        "type": "text",
        "analyzer": "kuromoji",
        "fields": {
          "keyword": {"type": "keyword"}
        }
      },
      "horse_name_kana": {
        "type": "text",
        "analyzer": "kuromoji_reading"
      },
      "traits": {
        "type": "nested",
        "properties": {
          "trait_name": {"type": "keyword"},
          "score": {"type": "float"}
        }
      },
      "race_history": {
        "type": "nested",
        "properties": {
          "race_id": {"type": "keyword"},
          "finish_position": {"type": "integer"},
          "race_date": {"type": "date"}
        }
      }
    }
  }
}

// races インデックス
{
  "mappings": {
    "properties": {
      "race_id": {"type": "keyword"},
      "race_name": {
        "type": "text",
        "analyzer": "kuromoji"
      },
      "venue_name": {"type": "keyword"},
      "distance": {"type": "integer"},
      "grade": {"type": "keyword"},
      "race_date": {"type": "date"},
      "entries": {
        "type": "nested",
        "properties": {
          "umacd": {"type": "keyword"},
          "horse_name": {"type": "text"},
          "expected_value": {"type": "float"}
        }
      }
    }
  }
}
```

## 6. データ移行・ETL設計

### 6.1 既存データ移行

```python
# 既存JSONファイルからPostgreSQLへの移行
def migrate_keibabook_data():
    """
    src/data/keibabook/*.json → PostgreSQL
    """
    json_files = glob.glob("src/data/keibabook/*.json")
    
    for file_path in json_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # レース基本情報の挿入
        race_data = extract_race_info(data)
        insert_race(race_data)
        
        # 出走馬情報の挿入
        for entry in data.get('entries', []):
            horse_data = extract_horse_info(entry)
            upsert_horse(horse_data)
            
            entry_data = extract_entry_info(entry, race_data['race_id'])
            insert_race_entry(entry_data)
```

### 6.2 リアルタイムETL

```python
# JRA-VANデータの継続的取り込み
class JRAVANETLPipeline:
    def process_realtime_data(self, jravan_data):
        # 1. 生データをMongoDBに保存
        raw_doc = {
            "source": "jravan",
            "data_type": jravan_data.get("type"),
            "raw_data": jravan_data,
            "received_at": datetime.utcnow()
        }
        mongo_db.raw_data.insert_one(raw_doc)
        
        # 2. 構造化データをPostgreSQLに保存
        if jravan_data["type"] == "race_result":
            structured_data = transform_race_result(jravan_data)
            upsert_race_result(structured_data)
            
        # 3. キャッシュを更新
        update_redis_cache(jravan_data)
        
        # 4. リアルタイム通知
        publish_update_notification(jravan_data)
```

## 7. バックアップ・復旧戦略

### 7.1 PostgreSQL
- **フルバックアップ**: 日次 (pg_dump)
- **WALアーカイブ**: 継続的
- **PITR**: 任意の時点への復旧可能
- **レプリケーション**: Streaming Replication

### 7.2 MongoDB
- **レプリカセット**: 3ノード構成
- **バックアップ**: mongodump (日次)
- **Oplog**: 継続的バックアップ
- **シャーディング**: 将来的な水平分散

### 7.3 Redis
- **RDB**: 定期スナップショット
- **AOF**: 全操作ログ
- **レプリケーション**: Master-Slave構成
- **クラスタ**: 高可用性構成

## 8. パフォーマンス最適化

### 8.1 クエリ最適化
- **インデックス**: 適切なインデックス設計
- **パーティショニング**: 日付ベースのパーティション
- **マテリアライズドビュー**: 集計データの事前計算
- **コネクションプール**: 接続数の最適化

### 8.2 キャッシュ戦略
- **L1キャッシュ**: アプリケーションレベル
- **L2キャッシュ**: Redis
- **CDN**: 静的コンテンツ
- **TTL**: 適切な有効期限設定

## 9. 監視・メトリクス

### 9.1 データベースメトリクス
- **接続数**: アクティブ/アイドル接続
- **クエリ性能**: 実行時間、スロークエリ
- **リソース使用率**: CPU、メモリ、ディスク
- **レプリケーション遅延**: マスター・スレーブ間の遅延

### 9.2 アラート設定
- **接続数上限**: 80%で警告
- **クエリ実行時間**: 1秒超で警告
- **ディスク使用率**: 85%で警告
- **レプリケーション遅延**: 10秒超で警告 
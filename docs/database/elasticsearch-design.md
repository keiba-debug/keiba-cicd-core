# Elasticsearch実装詳細設計書

## 1. Elasticsearch導入の目的と用途

KeibaCICDプロジェクトにおけるElasticsearchの役割：

1. **コメント全文検索**: 騎手インタビュー、調教師コメント、レース回顧の検索
2. **馬名・レース名のあいまい検索**: カタカナ/ひらがな、部分一致対応
3. **時系列分析**: レース結果の時系列集計・可視化
4. **ログ分析**: アプリケーションログ、スクレイピングログの分析

## 2. インデックス設計

### 2.1 horses_comments インデックス

```json
PUT /horses_comments
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "ja_text_analyzer": {
          "type": "custom",
          "tokenizer": "kuromoji_tokenizer",
          "filter": ["lowercase", "kuromoji_stop", "kuromoji_stemmer"]
        },
        "ja_reading_analyzer": {
          "type": "custom",
          "tokenizer": "kuromoji_tokenizer",
          "filter": ["kuromoji_readingform", "lowercase"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "race_id": { "type": "keyword" },
      "horse_name": {
        "type": "text",
        "analyzer": "ja_text_analyzer",
        "fields": {
          "keyword": { "type": "keyword" },
          "reading": {
            "type": "text",
            "analyzer": "ja_reading_analyzer"
          }
        }
      },
      "comments": {
        "type": "nested",
        "properties": {
          "type": { "type": "keyword" },
          "text": {
            "type": "text",
            "analyzer": "ja_text_analyzer"
          },
          "speaker": { "type": "keyword" },
          "date": { "type": "date" },
          "sentiment_score": { "type": "float" }
        }
      },
      "keywords": { "type": "keyword" },
      "created_at": { "type": "date" }
    }
  }
}
```

### 2.2 races インデックス

```json
PUT /races
{
  "mappings": {
    "properties": {
      "race_id": { "type": "keyword" },
      "race_name": {
        "type": "text",
        "analyzer": "ja_text_analyzer",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "race_date": { "type": "date" },
      "venue": { "type": "keyword" },
      "grade": { "type": "keyword" },
      "distance": { "type": "integer" },
      "track_type": { "type": "keyword" },
      "weather": { "type": "keyword" },
      "entries": {
        "type": "nested",
        "properties": {
          "horse_name": { "type": "text", "analyzer": "ja_text_analyzer" },
          "finish_position": { "type": "integer" },
          "odds": { "type": "float" },
          "expected_value": { "type": "float" }
        }
      }
    }
  }
}
```

## 3. 検索クエリ実装例

### 3.1 コメント検索

```python
# src/analysis/core/elasticsearch/comment_searcher.py
from elasticsearch import Elasticsearch
from typing import List, Dict

class CommentSearcher:
    def __init__(self):
        self.es = Elasticsearch(['localhost:9200'])
    
    def search_comments(self, query: str, filters: Dict = None) -> List[Dict]:
        """
        コメントを全文検索
        
        Args:
            query: 検索キーワード
            filters: フィルター条件（race_id, date_range等）
        """
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "nested": {
                                "path": "comments",
                                "query": {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["comments.text^2", "horse_name"],
                                        "type": "best_fields",
                                        "analyzer": "ja_text_analyzer"
                                    }
                                }
                            }
                        }
                    ]
                }
            },
            "highlight": {
                "fields": {
                    "comments.text": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"]
                    }
                }
            },
            "size": 20
        }
        
        # フィルター追加
        if filters:
            if 'race_id' in filters:
                search_body["query"]["bool"]["filter"] = [
                    {"term": {"race_id": filters["race_id"]}}
                ]
        
        return self.es.search(index="horses_comments", body=search_body)
    
    def search_by_sentiment(self, min_score: float = 0.7) -> List[Dict]:
        """ポジティブなコメントを検索"""
        return self.es.search(
            index="horses_comments",
            body={
                "query": {
                    "nested": {
                        "path": "comments",
                        "query": {
                            "range": {
                                "comments.sentiment_score": {
                                    "gte": min_score
                                }
                            }
                        }
                    }
                }
            }
        )
```

### 3.2 レース検索と集計

```python
def search_races_by_condition(self, venue: str, distance: int, 
                             track_type: str, limit: int = 100):
    """同条件の過去レースを検索"""
    return self.es.search(
        index="races",
        body={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"venue": venue}},
                        {"term": {"distance": distance}},
                        {"term": {"track_type": track_type}}
                    ]
                }
            },
            "aggs": {
                "pace_distribution": {
                    "terms": {
                        "field": "pace_type",
                        "size": 10
                    }
                },
                "favorable_style": {
                    "terms": {
                        "field": "winning_style",
                        "size": 10
                    }
                }
            },
            "sort": [{"race_date": {"order": "desc"}}],
            "size": limit
        }
    )
```

## 4. データ同期戦略

### 4.1 ETLパイプライン

```python
# scripts/etl/elasticsearch_sync.py
class ElasticsearchSyncService:
    def sync_from_mongodb(self):
        """MongoDBからElasticsearchへのデータ同期"""
        # 1. MongoDBから最新データ取得
        # 2. データ変換
        # 3. Bulk APIでElasticsearchに投入
        
    def sync_from_postgresql(self):
        """PostgreSQLからElasticsearchへのデータ同期"""
        # 1. 更新されたレースデータ取得
        # 2. 関連データのJOIN
        # 3. Elasticsearchドキュメント形式に変換
```

## 5. パフォーマンス最適化

### 5.1 インデックス最適化
- シャード数の適切な設定（データ量に応じて調整）
- レプリカ数の設定（可用性とのバランス）
- refresh_intervalの調整（リアルタイム性 vs パフォーマンス）

### 5.2 検索最適化
- Query DSLの最適化（match vs term）
- フィールドブースティング
- キャッシュ戦略

## 6. 運用・監視

### 6.1 インデックス管理

```bash
# インデックスのローテーション設定
PUT _ilm/policy/comments_policy
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50GB",
            "max_age": "30d"
          }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

### 6.2 監視項目
- クラスタヘルス
- インデックスサイズ
- 検索レイテンシ
- メモリ使用率

## 7. セキュリティ設定
- 認証・認可（X-Pack Security）
- 通信の暗号化（TLS）
- 監査ログの設定

## 8. 実装スケジュール
1. Phase 1: 基本的な全文検索機能
2. Phase 2: 高度な検索・集計機能
3. Phase 3: リアルタイム同期・可視化
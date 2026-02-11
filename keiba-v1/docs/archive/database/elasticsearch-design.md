# KeibaCICD Elasticsearch実装詳細設計書

## 1. Elasticsearch導入の目的と用途

### 1.1 KeibaCICDプロジェクトにおけるElasticsearchの役割

1. **コメント全文検索**: 騎手インタビュー、調教師コメント、レース回顧の検索
2. **馬名・レース名のあいまい検索**: カタカナ/ひらがな、部分一致対応
3. **時系列分析**: レース結果の時系列集計・可視化
4. **ログ分析**: アプリケーションログ、スクレイピングログの分析
5. **リアルタイム検索**: レース中のコメント・分析結果の即座検索
6. **集計・分析**: 複雑な条件での統計情報生成

### 1.2 技術的要件

- **日本語解析**: kuromoji tokenizer使用
- **リアルタイム性**: 1秒以内のインデックス更新
- **スケーラビリティ**: 100万件以上のドキュメント対応
- **可用性**: 99.9%稼働率
- **検索性能**: 100ms以内のレスポンス

## 2. インデックス設計

### 2.1 horses_comments インデックス

```json
PUT /horses_comments
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "refresh_interval": "1s",
    "analysis": {
      "analyzer": {
        "ja_text_analyzer": {
          "type": "custom",
          "tokenizer": "kuromoji_tokenizer",
          "filter": [
            "lowercase",
            "kuromoji_stop",
            "kuromoji_stemmer",
            "ja_synonym_filter"
          ]
        },
        "ja_reading_analyzer": {
          "type": "custom",
          "tokenizer": "kuromoji_tokenizer",
          "filter": [
            "kuromoji_readingform",
            "lowercase"
          ]
        },
        "ngram_analyzer": {
          "type": "custom",
          "tokenizer": "ngram_tokenizer",
          "filter": ["lowercase"]
        }
      },
      "tokenizer": {
        "ngram_tokenizer": {
          "type": "ngram",
          "min_gram": 2,
          "max_gram": 3,
          "token_chars": ["letter", "digit"]
        }
      },
      "filter": {
        "ja_synonym_filter": {
          "type": "synonym",
          "synonyms": [
            "逃げ,先行",
            "差し,追込",
            "重馬場,不良馬場",
            "芝,ターフ",
            "ダート,砂"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "race_id": { 
        "type": "keyword",
        "index": true
      },
      "horse_name": {
        "type": "text",
        "analyzer": "ja_text_analyzer",
        "fields": {
          "keyword": { 
            "type": "keyword" 
          },
          "reading": {
            "type": "text",
            "analyzer": "ja_reading_analyzer"
          },
          "ngram": {
            "type": "text",
            "analyzer": "ngram_analyzer"
          }
        }
      },
      "horse_number": {
        "type": "integer"
      },
      "comments": {
        "type": "nested",
        "properties": {
          "type": { 
            "type": "keyword",
            "index": true
          },
          "text": {
            "type": "text",
            "analyzer": "ja_text_analyzer",
            "fields": {
              "raw": {
                "type": "keyword"
              }
            }
          },
          "speaker": { 
            "type": "keyword" 
          },
          "date": { 
            "type": "date",
            "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
          },
          "sentiment_score": { 
            "type": "float",
            "index": true
          },
          "confidence": {
            "type": "float"
          },
          "source": {
            "type": "keyword"
          }
        }
      },
      "keywords": { 
        "type": "keyword" 
      },
      "race_date": {
        "type": "date",
        "format": "yyyy-MM-dd"
      },
      "venue": {
        "type": "keyword"
      },
      "created_at": { 
        "type": "date" 
      },
      "updated_at": {
        "type": "date"
      }
    }
  }
}
```

### 2.2 races インデックス

```json
PUT /races
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "ja_text_analyzer": {
          "type": "custom",
          "tokenizer": "kuromoji_tokenizer",
          "filter": ["lowercase", "kuromoji_stop", "kuromoji_stemmer"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "race_id": { 
        "type": "keyword" 
      },
      "race_name": {
        "type": "text",
        "analyzer": "ja_text_analyzer",
        "fields": {
          "keyword": { 
            "type": "keyword" 
          },
          "ngram": {
            "type": "text",
            "analyzer": "ngram_analyzer"
          }
        }
      },
      "race_date": { 
        "type": "date",
        "format": "yyyy-MM-dd"
      },
      "venue": { 
        "type": "keyword" 
      },
      "venue_name": {
        "type": "text",
        "analyzer": "ja_text_analyzer"
      },
      "grade": { 
        "type": "keyword" 
      },
      "distance": { 
        "type": "integer" 
      },
      "track_type": { 
        "type": "keyword" 
      },
      "direction": {
        "type": "keyword"
      },
      "weather": { 
        "type": "keyword" 
      },
      "track_condition": {
        "type": "keyword"
      },
      "race_number": {
        "type": "integer"
      },
      "prize_money": {
        "type": "long"
      },
      "entries": {
        "type": "nested",
        "properties": {
          "horse_name": { 
            "type": "text", 
            "analyzer": "ja_text_analyzer" 
          },
          "horse_number": {
            "type": "integer"
          },
          "finish_position": { 
            "type": "integer" 
          },
          "odds": { 
            "type": "float" 
          },
          "expected_value": { 
            "type": "float" 
          },
          "jockey_name": {
            "type": "text",
            "analyzer": "ja_text_analyzer"
          },
          "trainer_name": {
            "type": "text",
            "analyzer": "ja_text_analyzer"
          },
          "weight": {
            "type": "integer"
          },
          "age": {
            "type": "integer"
          }
        }
      },
      "pace_type": {
        "type": "keyword"
      },
      "winning_style": {
        "type": "keyword"
      },
      "created_at": {
        "type": "date"
      }
    }
  }
}
```

## 3. 検索クエリ実装例

### 3.1 コメント検索サービス

```python
# src/analysis/core/elasticsearch/comment_searcher.py
from elasticsearch import Elasticsearch
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class CommentSearcher:
    def __init__(self, es_host: str = "localhost:9200"):
        self.es = Elasticsearch([es_host])
        self.index_name = "horses_comments"
    
    def search_comments(self, 
                       query: str, 
                       filters: Optional[Dict] = None,
                       page: int = 1,
                       per_page: int = 20) -> Dict:
        """
        コメントを全文検索
        
        Args:
            query: 検索キーワード
            filters: フィルター条件（race_id, date_range等）
            page: ページ番号
            per_page: 1ページあたりの件数
        
        Returns:
            検索結果とメタデータ
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
                                        "fields": [
                                            "comments.text^3",
                                            "horse_name^2",
                                            "keywords"
                                        ],
                                        "type": "best_fields",
                                        "analyzer": "ja_text_analyzer",
                                        "fuzziness": "AUTO"
                                    }
                                },
                                "inner_hits": {
                                    "highlight": {
                                        "fields": {
                                            "comments.text": {
                                                "pre_tags": ["<mark>"],
                                                "post_tags": ["</mark>"],
                                                "fragment_size": 150,
                                                "number_of_fragments": 3
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    ],
                    "filter": []
                }
            },
            "highlight": {
                "fields": {
                    "horse_name": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"]
                    }
                }
            },
            "sort": [
                {"race_date": {"order": "desc"}},
                {"_score": {"order": "desc"}}
            ],
            "from": (page - 1) * per_page,
            "size": per_page
        }
        
        # フィルター追加処理...
        
        try:
            response = self.es.search(index=self.index_name, body=search_body)
            return self._format_search_response(response, page, per_page)
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise
```

## 4. データ同期戦略

### 4.1 ETLパイプライン

```python
# scripts/etl/elasticsearch_sync.py
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import json
import logging
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

logger = logging.getLogger(__name__)

class ElasticsearchSyncService:
    def __init__(self, es_host: str, mongo_uri: str, postgres_uri: str):
        self.es = Elasticsearch([es_host])
        # MongoDB, PostgreSQL接続設定...
        
    async def sync_from_mongodb(self, collection_name: str, 
                               last_sync: datetime = None):
        """MongoDBからElasticsearchへのデータ同期"""
        # 実装詳細...
        
    async def sync_from_postgresql(self, table_name: str, 
                                  last_sync: datetime = None):
        """PostgreSQLからElasticsearchへのデータ同期"""
        # 実装詳細...
```

## 5. パフォーマンス最適化

### 5.1 インデックス最適化

- **シャード数の適切な設定**: データ量に応じて調整
- **レプリカ数の設定**: 可用性とのバランス
- **refresh_intervalの調整**: リアルタイム性 vs パフォーマンス

### 5.2 検索最適化

- **Query DSLの最適化**: match vs term
- **フィールドブースティング**: 重要フィールドの重み付け
- **キャッシュ戦略**: 頻繁な検索結果のキャッシュ

## 6. 運用・監視

### 6.1 インデックス管理

```bash
# インデックスライフサイクル管理
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

- **クラスタヘルス**: ノード状態、シャード状態
- **インデックスサイズ**: ディスク使用量
- **検索レイテンシ**: 応答時間
- **メモリ使用率**: JVMヒープ使用量

## 7. セキュリティ設定

- **認証・認可**: X-Pack Security
- **通信の暗号化**: TLS設定
- **監査ログ**: アクセスログの記録

## 8. 実装スケジュール

### Phase 1: 基本的な全文検索機能 (4週間)
- Week 1: インデックス設計・作成
- Week 2: 基本検索機能実装
- Week 3: データ同期機能実装
- Week 4: テスト・デバッグ

### Phase 2: 高度な検索・集計機能 (6週間)
- Week 1-2: 複雑な検索クエリ実装
- Week 3-4: 集計・分析機能実装
- Week 5: パフォーマンス最適化
- Week 6: 統合テスト

### Phase 3: リアルタイム同期・可視化 (4週間)
- Week 1-2: リアルタイム同期実装
- Week 3: 監視・アラート機能
- Week 4: 本番環境デプロイ・運用開始

# 外部コメント統合システム仕様書

## 1. 概要
福田さんの個人分析や外部システムからのコメントをMDファイルに統合するシステム

## 2. コメントソース

### 2.1 対応形式
1. **JSONファイル**: 構造化されたコメント
2. **テキストファイル**: 自由記述
3. **CSVファイル**: 表形式のデータ
4. **API連携**: 外部システムからの取得（将来）

## 3. データ構造

### 3.1 外部コメントJSON
```json
{
  "date": "2025-08-16",
  "track": "札幌",
  "race": "11R",
  "comments": {
    "fukuda": {
      "timestamp": "2025-08-16T09:30:00",
      "general": "札幌記念は例年波乱含み。人気薄に注意",
      "horses": {
        "1": {
          "name": "サンプル馬A",
          "comment": "前走は展開不利。巻き返し期待",
          "rating": "A",
          "confidence": 4
        },
        "2": {
          "name": "サンプル馬B", 
          "comment": "距離短縮プラス。調教動き良好",
          "rating": "B",
          "confidence": 3
        }
      },
      "strategy": {
        "main": "1-2-5のBOX",
        "hedge": "1軸の流し",
        "budget": 5000
      }
    },
    "ai_analysis": {
      "timestamp": "2025-08-16T10:00:00",
      "pace_prediction": "ミドルペース",
      "key_factors": [
        "逃げ馬不在でペース落ち着く",
        "直線の瞬発力勝負"
      ]
    },
    "external_system": {
      "source": "予想システムA",
      "timestamp": "2025-08-16T08:00:00",
      "predictions": {
        "win": [1, 5, 8],
        "place": [1, 2, 5, 8, 12]
      }
    }
  }
}
```

### 3.2 簡易テキスト形式
```text
# 2025-08-16 札幌11R メモ

## 注目馬
1番: ◎ 前走は不利を受けた。今回は好走必至
2番: ○ 調教の動きが良い
5番: ▲ 穴馬。一発ある

## 買い目
三連複: 1-2-5
馬連: 1-2, 1-5
```

## 4. 統合ルール

### 4.1 優先順位
1. 福田さんの手動コメント（最優先）
2. 外部システムからの自動分析
3. AIアシスタントの分析

### 4.2 競合時の処理
- 同じ馬に複数コメントがある場合は全て表示
- タイムスタンプで新しい順に並べる

## 5. ファイル配置

```
Z:/KEIBA-CICD/data/
├── external_comments/
│   ├── fukuda/
│   │   ├── 2025/
│   │   │   └── 08/
│   │   │       └── 16/
│   │   │           ├── 札幌11R.json
│   │   │           └── 札幌11R.txt
│   ├── ai_analysis/
│   │   └── 2025/08/16/
│   └── external_systems/
│       └── system_a/
```

## 6. 読み込み処理

### 6.1 コメント読み込み関数
```python
def load_external_comments(date, track, race_no):
    """外部コメントを全て読み込み"""
    comments = {}
    
    # 福田コメント（JSON）
    fukuda_json = f"external_comments/fukuda/{date[:4]}/{date[4:6]}/{date[6:8]}/{track}{race_no}.json"
    if os.path.exists(fukuda_json):
        with open(fukuda_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
            comments['fukuda'] = data.get('comments', {}).get('fukuda', {})
    
    # 福田コメント（テキスト）
    fukuda_txt = f"external_comments/fukuda/{date[:4]}/{date[4:6]}/{date[6:8]}/{track}{race_no}.txt"
    if os.path.exists(fukuda_txt):
        with open(fukuda_txt, 'r', encoding='utf-8') as f:
            comments['fukuda_text'] = f.read()
    
    # AI分析
    ai_json = f"external_comments/ai_analysis/{date[:4]}/{date[4:6]}/{date[6:8]}/{track}{race_no}.json"
    if os.path.exists(ai_json):
        with open(ai_json, 'r', encoding='utf-8') as f:
            comments['ai'] = json.load(f)
    
    return comments
```

### 6.2 MD生成時の統合
```python
def generate_external_comments_section(comments):
    """外部コメントセクションを生成"""
    md_content = "## 📝 外部コメント\n\n"
    
    # 福田メモ
    if 'fukuda' in comments:
        md_content += "### 福田メモ\n"
        if 'general' in comments['fukuda']:
            md_content += f"**総評**: {comments['fukuda']['general']}\n\n"
        
        if 'horses' in comments['fukuda']:
            for num, horse_info in comments['fukuda']['horses'].items():
                md_content += f"- **{num}番 {horse_info['name']}**: "
                md_content += f"{horse_info['comment']} "
                md_content += f"(評価: {horse_info['rating']})\n"
    
    # テキストメモ
    if 'fukuda_text' in comments:
        md_content += "\n### メモ（テキスト）\n"
        md_content += "```\n"
        md_content += comments['fukuda_text']
        md_content += "\n```\n"
    
    return md_content
```

## 7. 入力支援ツール

### 7.1 簡易入力スクリプト
```python
# コメント入力CLI
python add_comment.py --date 2025-08-16 --track 札幌 --race 11R \
  --horse 1 --comment "前走不利。今回期待" --rating A

# 一括入力
python import_comments.py --file my_analysis.csv --date 2025-08-16
```

### 7.2 テンプレート生成
```python
# 空のコメントテンプレート生成
python generate_comment_template.py --date 2025-08-16 --track 札幌 --race 11R

# 出力: external_comments/fukuda/2025/08/16/札幌11R_template.json
```

## 8. 実装優先度

1. **Phase 1（今日）**: JSONファイル読み込み機能
2. **Phase 2（明日）**: テキストファイル対応
3. **Phase 3（来週）**: CSV入力、簡易入力ツール
4. **Phase 4（将来）**: Web UI、API連携
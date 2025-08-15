# 馬場情報・レース傾向記録システム仕様書

## 1. 概要
その日の馬場状態やレース傾向を記録し、レース分析に活用するシステム

## 2. データ構造

### 2.1 馬場情報ファイル
```json
{
  "date": "2025-08-16",
  "tracks": {
    "札幌": {
      "weather": "晴",
      "temperature": 24,
      "humidity": 65,
      "wind": {
        "direction": "北西",
        "speed": 2
      },
      "turf": {
        "condition": "良",
        "moisture": 12,
        "notes": "内回り有利、直線の伸びが良い",
        "time_index": -0.5
      },
      "dirt": {
        "condition": "良",
        "moisture": 8,
        "notes": "外枠有利傾向",
        "time_index": 0.0
      },
      "bias": {
        "turf_inside": 1.2,
        "turf_outside": 0.8,
        "dirt_inside": 0.9,
        "dirt_outside": 1.1
      }
    }
  }
}
```

### 2.2 レース傾向ファイル
```json
{
  "date": "2025-08-16",
  "tracks": {
    "札幌": {
      "races": {
        "11R": {
          "name": "札幌記念",
          "historical_trends": {
            "pace_tendency": "ミドルペース",
            "favorable_position": "先行",
            "winning_rate_by_position": {
              "逃げ": 10,
              "先行": 45,
              "差し": 30,
              "追込": 15
            }
          },
          "bloodline_trends": {
            "top_sires": ["ディープインパクト", "オルフェーヴル"],
            "success_rate": {
              "ディープインパクト": 35,
              "オルフェーヴル": 25
            }
          },
          "jockey_trends": {
            "top_jockeys": ["ルメール", "川田"],
            "recent_winners": [
              {"year": 2024, "jockey": "ルメール"},
              {"year": 2023, "jockey": "川田"}
            ]
          }
        }
      }
    }
  }
}
```

## 3. 入力インターフェース

### 3.1 Webフォーム（将来実装）
```html
<!-- 馬場情報入力フォーム -->
<form id="track-condition-form">
  <h3>馬場情報入力</h3>
  <select name="track">
    <option>札幌</option>
    <option>新潟</option>
    <option>中京</option>
  </select>
  
  <label>天候:</label>
  <select name="weather">
    <option>晴</option>
    <option>曇</option>
    <option>雨</option>
  </select>
  
  <label>芝状態:</label>
  <select name="turf_condition">
    <option>良</option>
    <option>稍重</option>
    <option>重</option>
    <option>不良</option>
  </select>
  
  <label>特記事項:</label>
  <textarea name="notes"></textarea>
</form>
```

### 3.2 CLIコマンド（当面の実装）
```python
# 馬場情報入力
python track_manager.py --date 2025-08-16 --track 札幌 \
  --weather 晴 --turf 良 --dirt 良 \
  --note "内回り有利"

# レース傾向入力  
python trend_manager.py --date 2025-08-16 --track 札幌 --race 11R \
  --pace ミドル --position 先行 \
  --note "ディープ産駒好走"
```

## 4. データ保存先
```
Z:/KEIBA-CICD/data/
├── track_conditions/
│   └── 2025/
│       └── 08/
│           └── track_condition_20250816.json
└── race_trends/
    └── 2025/
        └── 08/
            └── race_trend_20250816.json
```

## 5. 活用方法

### 5.1 MD生成時の自動読み込み
```python
def load_track_info(date, track):
    """馬場情報を読み込み"""
    file_path = f"track_conditions/{date[:4]}/{date[4:6]}/track_condition_{date}.json"
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['tracks'].get(track, {})
    return {}
```

### 5.2 分析での活用
```python
def adjust_expected_value(base_value, track_info):
    """馬場状態による期待値調整"""
    if track_info.get('turf', {}).get('condition') == '重':
        # パワー型の馬の期待値を上方修正
        base_value *= 1.1
    return base_value
```

## 6. 更新タイミング

### 朝一（8:00）
- 天候確認
- 馬場状態初期入力

### レース前（各レース30分前）
- 馬場状態更新
- 風向き・風速確認

### レース後
- 実際のレース傾向記録
- タイム指数更新

## 7. 実装優先度

1. **最優先**: JSONファイルの手動作成・読み込み機能
2. **次優先**: CLI入力インターフェース
3. **将来**: Webフォーム、自動取得機能
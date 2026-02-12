# ML統合計画（v3.2〜v4.0）

> **目的**: 機械学習を活用した競馬予想の精度向上と、好走パターンの発見

---

## 📌 基本方針

### ML活用の目的

1. **評価指数のチューニング**
   - 既存の手動ルールベース評価を改善
   - 過去データから最適な重み付けを学習

2. **好走パターンの発見**
   - 馬場状態 × メンバー構成 × ラップ傾向
   - 調教師別の好走調教パターン
   - 複雑な相関関係の発見

3. **前日予想データの生成**
   - 事前に計算した予想をJSON保存
   - WebViewerで出走表に表示

### 重要な設計決定

✅ **ML予測はバッチ処理**（リアルタイム不要）
- 金曜夜に週末レース分を一括予測
- 結果をJSONファイルに保存
- WebViewerは読み込むだけ（高速）

✅ **Backend API分離は不要**
- 現在のアーキテクチャ（バッチ → JSON → Next.js）で十分
- ネットワークレイテンシーなし

---

## 🎯 段階的実装計画

### Phase 1: データ収集・蓄積（v3.2）

**期間**: 2026年3月

#### データベース設計

**training_history.db**（SQLite）:

```sql
-- レーステーブル
CREATE TABLE races (
    race_id TEXT PRIMARY KEY,
    race_date TEXT NOT NULL,
    track_code TEXT NOT NULL,
    race_number INTEGER NOT NULL,
    distance INTEGER,
    track_condition TEXT,  -- 良/稍重/重/不良
    race_class TEXT,       -- G1/G2/G3/オープン/1600万/1000万/500万/未勝利
    INDEX idx_race_date (race_date)
);

-- 出走馬テーブル
CREATE TABLE race_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    horse_name TEXT NOT NULL,
    finish_position INTEGER,  -- 着順
    odds REAL,                 -- オッズ
    trainer_id TEXT,
    trainer_name TEXT,
    jockey_id TEXT,
    jockey_name TEXT,
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    INDEX idx_horse_id (horse_id),
    INDEX idx_trainer_id (trainer_id)
);

-- 調教履歴テーブル
CREATE TABLE training_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    training_date TEXT NOT NULL,
    center TEXT,           -- 美浦/栗東
    location TEXT,         -- 坂路/コース/ウッド等
    time_4f REAL,          -- 4Fタイム
    lap_1 REAL,            -- ラップ1
    speed_class TEXT,      -- S/A/B/C/D
    lap_class TEXT,        -- S+/A-/B=等
    upgraded_lap_class TEXT,  -- SS/S+/A-等
    is_good_time INTEGER,  -- 好タイム（0/1）
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    INDEX idx_horse_training (horse_id, training_date)
);

-- パターンテーブル（v3.3で使用）
CREATE TABLE winning_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,  -- trainer_training/track_condition等
    pattern_name TEXT NOT NULL,
    conditions TEXT NOT NULL,    -- JSON形式の条件
    win_count INTEGER DEFAULT 0,
    total_count INTEGER DEFAULT 0,
    win_rate REAL,
    confidence REAL,
    last_updated TEXT
);
```

#### データ収集スクリプト

**scripts/collect_training_data.py**:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
過去データ収集スクリプト（v3.2）
JRA-VAN CK_DATA + SE_DATA（成績データ）を統合してDBに格納
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from parse_ck_data import parse_ck_file
# from parse_se_data import parse_se_file  # 成績データパーサー（要実装）

DATA_DIR = Path(os.environ["KEIBA_DATA_ROOT_DIR"])
JV_DIR = Path(os.environ["JV_DATA_ROOT_DIR"])
DB_PATH = DATA_DIR / "training_history.db"

def init_database():
    """データベース初期化"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # テーブル作成（上記SQL）
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS races (...);
        CREATE TABLE IF NOT EXISTS race_entries (...);
        CREATE TABLE IF NOT EXISTS training_records (...);
        CREATE TABLE IF NOT EXISTS winning_patterns (...);
    """)

    conn.commit()
    conn.close()

def collect_past_data(start_date: str, end_date: str):
    """
    指定期間のデータを収集
    start_date, end_date: "YYYY-MM-DD"
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current_date <= end:
        date_str = current_date.strftime("%Y%m%d")
        print(f"📅 {date_str} のデータを収集中...")

        # 1. CK_DATAから調教データ取得
        ck_files = list((JV_DIR / "CK_DATA" / current_date.strftime("%Y/%Y%m")).glob(f"*{date_str}.DAT"))
        for ck_file in ck_files:
            training_records = parse_ck_file(ck_file)
            for record in training_records:
                cursor.execute("""
                    INSERT INTO training_records
                    (race_id, horse_id, training_date, center, location,
                     time_4f, lap_1, speed_class, lap_class, upgraded_lap_class, is_good_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.race_id, record.horse_id, record.date,
                    record.center, record.location, record.time_4f,
                    record.lap_1, record.speed_class, record.lap_class,
                    record.upgraded_lap_class, 1 if record.is_good_time else 0
                ))

        # 2. SE_DATAからレース結果取得（要実装）
        # ...

        conn.commit()
        current_date += timedelta(days=1)

    conn.close()
    print("✅ データ収集完了")

if __name__ == "__main__":
    init_database()

    # 過去3年分のデータ収集
    collect_past_data("2023-01-01", "2026-01-31")
```

**成果物**:
- `training_history.db`（約10-20GB）
- データ収集ログ

---

### Phase 2: パターン分析（v3.3）

**期間**: 2026年4月

#### 好走パターンの発見

**scripts/find_winning_patterns.py**:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
好走パターン発見スクリプト（v3.3）
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(os.environ["KEIBA_DATA_ROOT_DIR"]) / "training_history.db"
PATTERNS_FILE = Path(os.environ["KEIBA_DATA_ROOT_DIR"]) / "patterns.json"

def find_trainer_training_patterns(min_sample_size=20):
    """調教師 × 調教評価パターンを発見"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
        SELECT
            t.trainer_name,
            tr.center,
            tr.location,
            tr.upgraded_lap_class,
            COUNT(*) as total,
            SUM(CASE WHEN e.finish_position = 1 THEN 1 ELSE 0 END) as wins
        FROM training_records tr
        JOIN race_entries e ON tr.race_id = e.race_id AND tr.horse_id = e.horse_id
        JOIN races r ON tr.race_id = r.race_id
        WHERE tr.upgraded_lap_class IN ('SS', 'S+', 'S=', 'A+')
          AND e.finish_position IS NOT NULL
        GROUP BY t.trainer_name, tr.center, tr.location, tr.upgraded_lap_class
        HAVING COUNT(*) >= ?
        ORDER BY wins * 1.0 / total DESC
    """

    cursor.execute(query, (min_sample_size,))
    patterns = []

    for row in cursor.fetchall():
        trainer, center, location, lap_class, total, wins = row
        win_rate = wins / total

        if win_rate >= 0.20:  # 勝率20%以上のみ
            pattern = {
                "type": "trainer_training_pattern",
                "name": f"{trainer}_{center}{location}_{lap_class}評価",
                "description": f"{trainer}厩舎で{center}{location}{lap_class}評価",
                "conditions": {
                    "trainer": trainer,
                    "center": center,
                    "location": location,
                    "lap_class": lap_class
                },
                "win_count": wins,
                "total_count": total,
                "win_rate": round(win_rate, 3),
                "confidence": calculate_confidence(wins, total)
            }
            patterns.append(pattern)

    conn.close()
    return patterns

def find_track_condition_patterns(min_sample_size=50):
    """馬場 × ラップ傾向パターンを発見"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 実装省略（同様のロジック）
    # ...

    conn.close()
    return patterns

def calculate_confidence(wins, total):
    """信頼度計算（簡易版）"""
    # ベイズ推定等で信頼区間を計算
    # サンプルサイズが大きいほど信頼度が高い
    if total < 20:
        return 0.5
    elif total < 50:
        return 0.7
    else:
        return 0.85

def save_patterns():
    """パターンをJSONファイルに保存"""
    patterns = {
        "trainer_training_patterns": find_trainer_training_patterns(),
        "track_condition_patterns": find_track_condition_patterns(),
        # 他のパターンタイプも追加
    }

    with open(PATTERNS_FILE, 'w', encoding='utf-8') as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)

    print(f"✅ パターン保存完了: {PATTERNS_FILE}")

if __name__ == "__main__":
    save_patterns()
```

**パターン出力例（patterns.json）**:

```json
{
  "trainer_training_patterns": [
    {
      "type": "trainer_training_pattern",
      "name": "藤沢和雄_栗東坂路_S+評価",
      "description": "藤沢和雄厩舎で栗東坂路S+評価",
      "conditions": {
        "trainer": "藤沢和雄",
        "center": "栗東",
        "location": "坂路",
        "lap_class": "S+"
      },
      "win_count": 12,
      "total_count": 45,
      "win_rate": 0.267,
      "confidence": 0.82
    },
    {
      "type": "trainer_training_pattern",
      "name": "矢作芳人_栗東坂路_SS評価",
      "description": "矢作芳人厩舎で栗東坂路SS評価",
      "conditions": {
        "trainer": "矢作芳人",
        "center": "栗東",
        "location": "坂路",
        "lap_class": "SS"
      },
      "win_count": 8,
      "total_count": 22,
      "win_rate": 0.364,
      "confidence": 0.75
    }
  ],
  "track_condition_patterns": [
    {
      "type": "track_condition_pattern",
      "name": "京都ダ1800m_良馬場_ハイペース_差し",
      "description": "京都ダ1800m・良馬場・ハイペース想定 → 差し脚質有利",
      "conditions": {
        "track": "京都",
        "distance": 1800,
        "surface": "ダート",
        "condition": "良",
        "pace": "ハイペース",
        "running_style": "差し"
      },
      "win_count": 42,
      "total_count": 120,
      "win_rate": 0.35,
      "confidence": 0.88
    }
  ]
}
```

---

### Phase 3: ML予想モデル（v4.0）

**期間**: 2026年5-6月

#### 特徴量設計

**features.py**:

```python
def extract_features(horse_id: str, race_id: str) -> dict:
    """特徴量抽出"""
    features = {}

    # 1. 調教データ
    features['training_time_4f'] = get_latest_training(horse_id)['time_4f']
    features['training_lap_class_encoded'] = encode_lap_class(...)
    features['training_is_good_time'] = 1 or 0

    # 2. 過去成績
    features['recent_win_rate'] = calculate_recent_win_rate(horse_id, last_n=5)
    features['track_win_rate'] = calculate_track_win_rate(horse_id, track_code)

    # 3. 調教師パターンマッチ
    features['trainer_pattern_match'] = check_trainer_pattern(...)

    # 4. 馬場・ペース
    features['track_condition_encoded'] = encode_track_condition(...)
    features['expected_pace_encoded'] = encode_pace(...)

    # 5. メンバー構成
    features['member_strength'] = calculate_member_strength(race_id)

    return features
```

#### MLモデル実装

**ml/prediction_model.py**:

```python
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

class RacePredictionModel:
    def __init__(self):
        self.model = None

    def train(self, X, y):
        """モデル訓練"""
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        params = {
            'objective': 'binary',  # 勝ち/負けの二値分類
            'metric': 'auc',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': 0
        }

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
            valid_sets=[val_data],
            early_stopping_rounds=50
        )

    def predict(self, X):
        """予測（勝率）"""
        return self.model.predict(X, num_iteration=self.model.best_iteration)

    def save(self, path):
        self.model.save_model(path)

    def load(self, path):
        self.model = lgb.Booster(model_file=path)
```

#### 週次予想生成

**scripts/generate_weekly_predictions.py**:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
週次予想生成スクリプト（v4.0）
金曜夜に実行し、週末レースの予想を生成
"""

import os
import json
from pathlib import Path
from datetime import datetime
from ml.prediction_model import RacePredictionModel
from features import extract_features

DATA_DIR = Path(os.environ["KEIBA_DATA_ROOT_DIR"])
PREDICTIONS_DIR = DATA_DIR / "predictions"

def generate_race_prediction(race_id: str, entries: list) -> dict:
    """レース予想生成"""
    model = RacePredictionModel()
    model.load(DATA_DIR / "models" / "race_predictor_v1.0.txt")

    predictions = []

    for entry in entries:
        # 特徴量抽出
        features = extract_features(entry['horse_id'], race_id)
        X = pd.DataFrame([features])

        # 予測
        win_prob = model.predict(X)[0]

        # パターンマッチング
        patterns = find_matching_patterns(entry, race_id)

        # スコア計算（予測勝率 × パターン信頼度）
        score = calculate_score(win_prob, patterns)

        predictions.append({
            "horse_id": entry['horse_id'],
            "horse_name": entry['horse_name'],
            "prediction": {
                "score": round(score, 1),
                "winning_probability": round(win_prob, 3),
                "rank": 0,  # 後で設定
                "recommendation": "",  # 後で設定
                "confidence": round(calculate_confidence(win_prob, patterns), 2)
            },
            "patterns": patterns
        })

    # ランキング設定
    predictions.sort(key=lambda x: x['prediction']['score'], reverse=True)
    for i, pred in enumerate(predictions, 1):
        pred['prediction']['rank'] = i
        if i == 1:
            pred['prediction']['recommendation'] = "◎"
        elif i == 2:
            pred['prediction']['recommendation'] = "○"
        elif i == 3:
            pred['prediction']['recommendation'] = "▲"
        elif i <= 5:
            pred['prediction']['recommendation'] = "△"

    return {
        "race_id": race_id,
        "meta": {
            "predicted_at": datetime.now().isoformat(),
            "model_version": "v1.0",
            "confidence": round(np.mean([p['prediction']['confidence'] for p in predictions]), 2)
        },
        "horses": predictions
    }

def generate_weekend_predictions(target_date: str):
    """週末レース分の予想を一括生成"""
    # レース一覧取得（省略）
    races = get_weekend_races(target_date)

    for race in races:
        prediction = generate_race_prediction(race['race_id'], race['entries'])

        # JSON保存
        output_dir = PREDICTIONS_DIR / target_date[:4] / target_date[4:6] / target_date[6:8]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{race['race_id']}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(prediction, f, ensure_ascii=False, indent=2)

        print(f"✅ {race['race_name']}: {output_file}")

if __name__ == "__main__":
    # 金曜夜に実行
    generate_weekend_predictions("20260208")
```

**予想データ出力例**:

```json
{
  "race_id": "2026020806010208",
  "meta": {
    "predicted_at": "2026-02-07T22:00:00",
    "model_version": "v1.0",
    "confidence": 0.78
  },
  "horses": [
    {
      "horse_id": "2023103073",
      "horse_name": "カゼノハゴロモ",
      "prediction": {
        "score": 85.3,
        "winning_probability": 0.23,
        "rank": 1,
        "recommendation": "◎",
        "confidence": 0.82
      },
      "patterns": [
        {
          "type": "trainer_training_pattern",
          "name": "藤沢和雄_栗東坂路_S+評価",
          "win_rate": 0.267,
          "confidence": 0.82
        }
      ]
    }
  ]
}
```

---

## 🖥️ WebViewer統合

### 予想セクション追加

**src/components/race-v2/PredictionSection.tsx**:

```tsx
import { useMemo } from 'react';

interface PredictionData {
  race_id: string;
  horses: Array<{
    horse_name: string;
    prediction: {
      score: number;
      winning_probability: number;
      rank: number;
      recommendation: string;
      confidence: number;
    };
    patterns: Array<{
      type: string;
      name: string;
      win_rate: number;
    }>;
  }>;
}

export function PredictionSection({ raceId }: { raceId: string }) {
  const { data, error } = useSWR(`/api/predictions/${raceId}`, fetcher);

  if (!data) return <div>予想データ読み込み中...</div>;

  return (
    <section className="mb-6">
      <h3 className="text-lg font-bold mb-3">🔮 AI予想分析</h3>

      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-100 dark:bg-gray-800">
            <th>枠</th>
            <th>番</th>
            <th>馬名</th>
            <th>予想</th>
            <th>スコア</th>
            <th>勝率</th>
            <th>パターン</th>
          </tr>
        </thead>
        <tbody>
          {data.horses.map((horse) => (
            <tr key={horse.horse_name}>
              <td>{/* 枠番 */}</td>
              <td>{/* 馬番 */}</td>
              <td>{horse.horse_name}</td>
              <td>
                <span className={getRecommendationColor(horse.prediction.recommendation)}>
                  {horse.prediction.recommendation}
                </span>
              </td>
              <td className="font-bold">{horse.prediction.score}</td>
              <td>{(horse.prediction.winning_probability * 100).toFixed(1)}%</td>
              <td>
                <button onClick={() => showPatterns(horse.patterns)}>
                  {horse.patterns.length}件
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
```

---

## 📊 評価とモニタリング

### モデル精度評価

**scripts/evaluate_model.py**:

```python
def evaluate_predictions(start_date: str, end_date: str):
    """予想精度の評価"""
    results = {
        "top1_accuracy": 0,  # 本命的中率
        "top3_accuracy": 0,  # 3着以内的中率
        "auc": 0,            # AUCスコア
        "calibration": 0     # 勝率予測のキャリブレーション
    }

    # 実装省略

    return results
```

### 週次レポート

毎週月曜日に自動生成：

```
=== 週次予想レポート（2026年2月第2週）===

予想レース数: 48
本命的中: 15 / 48 (31.3%)
3着以内的中: 38 / 48 (79.2%)

パターンマッチ的中率:
- 藤沢和雄_栗東坂路_S+評価: 3 / 8 (37.5%)
- 京都ダ1800m_良馬場_差し: 5 / 12 (41.7%)

改善ポイント:
- 不良馬場での予測精度が低い（20%）
- メンバー構成の重み調整が必要
```

---

**最終更新**: 2026-02-07（カカシ）
**承認**: ふくだ君（保留中）

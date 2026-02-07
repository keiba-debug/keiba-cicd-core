# オッズ管理ガイド

**リアルタイムオッズの取得と活用**

期待値計算には「最新のオッズ」が不可欠です。このドキュメントでは、JRA-VANからオッズを取得し、効果的に活用する方法を説明します。

---

## 🎯 オッズの重要性

### なぜ最新オッズが必要か

```
シナリオ: 予測勝率30%の馬

前日夜のオッズ: 5.0倍
  期待値 = 0.30 × 5.0 = 150% → 買い！

締切直前のオッズ: 2.5倍
  期待値 = 0.30 × 2.5 = 75% → 見送り
```

**古いオッズで判断すると大損します。**

---

## 📊 JRA-VANのオッズデータ

### 取得可能なオッズ種別

| データ種別 | 内容 | ファイル例 |
|-----------|------|-----------|
| **O1** | 単勝・複勝オッズ | `O1_20260201_1530.txt` |
| **O2** | 馬連オッズ | `O2_20260201_1530.txt` |
| **O3** | ワイドオッズ | `O3_20260201_1530.txt` |
| **O4** | 馬単オッズ | `O4_20260201_1530.txt` |
| **O5** | 三連複オッズ | `O5_20260201_1530.txt` |
| **O6** | 三連単オッズ | `O6_20260201_1530.txt` |

### オッズ取得タイミング

| タイミング | 時刻 | 用途 |
|-----------|------|------|
| 前日夜オッズ | 金曜 20:00 | 初期候補選定 |
| 朝オッズ | 土曜 10:00 | 購入候補絞り込み |
| 昼オッズ | 土曜 12:00 | 中間確認 |
| **締切前オッズ** | **レース30分前** | **最終判断** |

---

## 🔧 実装方式の選択

### ファイルベース vs DB

| 項目 | ファイルベース | DB |
|------|---------------|-----|
| **実装の容易さ** | ✅ 簡単 | ❌ 複雑 |
| **TARGETとの統一** | ✅ 同じ仕組み | ❌ 別管理 |
| **クエリ速度** | △ やや遅い | ✅ 高速 |
| **時系列分析** | △ やや面倒 | ✅ 容易 |
| **保守性** | ✅ シンプル | △ スキーマ管理必要 |

### 推奨：段階的移行

```
Phase 1 (今すぐ)
  └─ ファイルベース
      ├─ JRA-VANから直接ファイル取得
      ├─ TARGETと同じディレクトリ構成
      └─ シンプルで実装が早い

Phase 2 (必要になったら)
  └─ DB化を検討
      ├─ オッズ変動分析が必要になった時
      ├─ 大量レース並行処理が必要な時
      └─ クエリ性能が問題になった時
```

---

## 📁 ファイルベースの実装

### ディレクトリ構成

```
E:\share\KEIBA-DATA\jv-data\ODDS\
  ├─ O1_20260201_1000.txt  # 朝オッズ（単勝・複勝）
  ├─ O1_20260201_1200.txt  # 昼オッズ
  ├─ O1_20260201_1400.txt  # 午後オッズ
  ├─ O1_20260201_1530.txt  # 締切前オッズ ★最重要
  ├─ O2_20260201_1530.txt  # 馬連オッズ
  └─ ...
```

### オッズ取得スクリプト

**PowerShell**: `scripts/fetch_odds.ps1`

```powershell
# オッズ取得スクリプト
# 使用例: .\fetch_odds.ps1 -Date "20260201" -Time "1530"

param(
    [string]$Date = (Get-Date -Format "yyyyMMdd"),
    [string]$Time = (Get-Date -Format "HHmm")
)

$JVDataRoot = "E:\share\KEIBA-DATA\jv-data"
$OddsDir = "$JVDataRoot\ODDS"

# ディレクトリ作成
if (-not (Test-Path $OddsDir)) {
    New-Item -ItemType Directory -Path $OddsDir
}

# JVLinkでオッズ取得
Write-Host "オッズ取得中: $Date $Time"

# DIFF配信でリアルタイムオッズ取得
JVLink.exe -dataspec "DIFF O1 O2" -fromdate $Date -todate $Date

# 取得したファイルをタイムスタンプ付きでリネーム
$SourceO1 = "$JVDataRoot\O1.txt"
$SourceO2 = "$JVDataRoot\O2.txt"

if (Test-Path $SourceO1) {
    $DestO1 = "$OddsDir\O1_${Date}_${Time}.txt"
    Move-Item -Path $SourceO1 -Destination $DestO1 -Force
    Write-Host "✓ 単勝・複勝オッズ保存: $DestO1"
}

if (Test-Path $SourceO2) {
    $DestO2 = "$OddsDir\O2_${Date}_${Time}.txt"
    Move-Item -Path $SourceO2 -Destination $DestO2 -Force
    Write-Host "✓ 馬連オッズ保存: $DestO2"
}

Write-Host "オッズ取得完了"
```

### 定期実行（タスクスケジューラ）

**土曜日の自動取得**:

```
10:00 - 朝オッズ
12:00 - 昼オッズ
14:00 - 午後オッズ
15:25 - 締切前オッズ (1R直前)
15:55 - 締切前オッズ (2R直前)
...
```

**Windows タスクスケジューラ設定**:

```powershell
# タスク作成例（土曜10:00に実行）
$Action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-File E:\share\KEIBA-CICD\_keiba\scripts\fetch_odds.ps1 -Time 1000"

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 10:00AM

Register-ScheduledTask -TaskName "FetchOdds_Saturday_1000" `
    -Action $Action -Trigger $Trigger -Description "土曜朝オッズ取得"
```

---

## 🐍 Pythonでのオッズ利用

### 基本的な使い方

```python
from ml.betting.odds_manager import OddsManager

# オッズマネージャー初期化
manager = OddsManager()

# 最新オッズを取得
race_id = "2026020105010211"
race_date = "20260201"

odds = manager.get_race_odds(race_id, race_date, snapshot_time="latest")

# 特定の馬のオッズ
horse_odds = manager.get_horse_odds(race_id, race_date, umaban="01", snapshot_time="closing")

print(f"1番の単勝オッズ: {horse_odds['win_odds']:.1f}倍")
```

### 期待値計算との統合

```python
from ml.betting.odds_manager import OddsManager
from ml.betting.evaluator import ExpectedValueCalculator

# オッズ取得
manager = OddsManager()
odds = manager.get_race_odds(race_id, race_date, snapshot_time="closing")

# 期待値計算
calculator = ExpectedValueCalculator()

for umaban, odds_data in odds.items():
    # 予測確率（MLモデルから取得）
    prob = predictions[umaban]['prob']

    # 期待値計算
    ev = calculator.calculate_win(prob, odds_data['win_odds'])

    print(f"{umaban}番: 期待値 {ev:.1%}")
```

---

## 📈 2段階判断システム

現実的なオッズ取得タイミングを考慮した購入判断フロー。

### フロー図

```
金曜夜 (20:00)
  ├─ 予想モデル実行 → 勝率予測
  ├─ 前日夜オッズ取得（初回発表）
  └─ 期待値計算 → 「候補馬リスト」作成
      ↓
土曜朝 (10:00)
  ├─ 朝オッズ取得
  ├─ 期待値再計算
  └─ 候補馬を絞り込み → 「購入候補リスト」
      ↓
レース30分前 (例: 15:05)
  ├─ 締切前オッズ取得 ★最重要
  ├─ 最終期待値計算
  ├─ ケリー基準で賭け金計算
  └─ 「購入確定」 or 「見送り」
      ↓
人間が承認 → 購入実行
```

### Python実装

```python
from datetime import datetime
from ml.betting.odds_manager import OddsManager
from ml.betting.decision_engine import BettingDecisionEngine

def two_stage_decision(race_id: str, race_date: str, predictions: dict):
    """
    2段階判断システム

    Args:
        race_id: レースID
        race_date: レース日付（YYYYMMDD）
        predictions: {umaban: {'prob': float}}

    Returns:
        購入推奨リスト
    """
    manager = OddsManager()
    engine = BettingDecisionEngine()

    # === Stage 1: 候補選定（前日夜） ===
    print("=== Stage 1: 候補選定（前日夜オッズ） ===")

    # 前日夜オッズ取得（仮に金曜20:00のオッズ）
    # 実際には前日夜に取得したものを使用
    night_odds = manager.get_race_odds(race_id, race_date, snapshot_time="2000")

    candidates = []
    for umaban, pred in predictions.items():
        odds_data = night_odds.get(umaban)
        if not odds_data:
            continue

        # 期待値計算
        ev_rate = pred['prob'] * odds_data['win_odds']

        # 期待値120%以上を候補に
        if ev_rate >= 1.20:
            candidates.append({
                'umaban': umaban,
                'prob': pred['prob'],
                'night_odds': odds_data['win_odds'],
                'night_ev': ev_rate
            })

    print(f"候補馬: {len(candidates)}頭")

    # === Stage 2: 最終判断（締切前） ===
    print("\n=== Stage 2: 最終判断（締切前オッズ） ===")

    # 締切前オッズ取得（レース30分前）
    closing_odds = manager.get_race_odds(race_id, race_date, snapshot_time="closing")

    final_recommendations = []
    for candidate in candidates:
        umaban = candidate['umaban']
        prob = candidate['prob']

        closing_odds_data = closing_odds.get(umaban)
        if not closing_odds_data:
            continue

        closing_odds_value = closing_odds_data['win_odds']

        # 最終期待値計算
        rec = engine.evaluate_bet(
            horse_name=f"{umaban}番",
            prob=prob,
            odds=closing_odds_value
        )

        if rec.should_bet:
            final_recommendations.append({
                'umaban': umaban,
                'prob': prob,
                'night_odds': candidate['night_odds'],
                'closing_odds': closing_odds_value,
                'odds_change': closing_odds_value - candidate['night_odds'],
                'final_ev': rec.expected_value_rate,
                'bet_amount': rec.bet_amount,
                'reason': rec.reason
            })

    print(f"購入推奨: {len(final_recommendations)}頭")

    return final_recommendations


# 使用例
race_id = "2026020105010211"
race_date = "20260201"

predictions = {
    "01": {"prob": 0.25},
    "03": {"prob": 0.18},
    "05": {"prob": 0.30},
}

recommendations = two_stage_decision(race_id, race_date, predictions)

for rec in recommendations:
    print(f"\n{rec['umaban']}番:")
    print(f"  予測勝率: {rec['prob']:.1%}")
    print(f"  前日オッズ: {rec['night_odds']:.1f}倍")
    print(f"  締切前オッズ: {rec['closing_odds']:.1f}倍")
    print(f"  オッズ変動: {rec['odds_change']:+.1f}倍")
    print(f"  最終期待値: {rec['final_ev']:.1%}")
    print(f"  推奨賭け金: {rec['bet_amount']}円")
```

---

## 📊 DB化する場合の設計

将来的に必要になった場合の参考。

### テーブル設計

```sql
-- オッズスナップショット
CREATE TABLE odds_snapshots (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(16) NOT NULL,
    umaban CHAR(2) NOT NULL,
    snapshot_time TIMESTAMP NOT NULL,
    win_odds DECIMAL(6,2),
    place_odds_min DECIMAL(6,2),
    place_odds_max DECIMAL(6,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_race_snapshot ON odds_snapshots(race_id, snapshot_time);
CREATE INDEX idx_race_umaban ON odds_snapshots(race_id, umaban);

-- オッズ変動統計
CREATE TABLE odds_volatility (
    race_id VARCHAR(16) PRIMARY KEY,
    umaban CHAR(2),
    first_odds DECIMAL(6,2),      -- 初回発表
    morning_odds DECIMAL(6,2),     -- 朝オッズ
    closing_odds DECIMAL(6,2),     -- 締切前
    max_odds DECIMAL(6,2),         -- 最高値
    min_odds DECIMAL(6,2),         -- 最低値
    volatility DECIMAL(6,2)        -- 変動率
);
```

### SQLiteで軽量DB

PostgreSQLやMySQLは大げさなので、SQLiteで十分。

```python
import sqlite3
from pathlib import Path

class OddsDatabase:
    """SQLiteベースのオッズDB"""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("ml/data/odds.db")
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()

    def _create_tables(self):
        """テーブル作成"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id TEXT NOT NULL,
                umaban TEXT NOT NULL,
                snapshot_time TEXT NOT NULL,
                win_odds REAL,
                place_odds_min REAL,
                place_odds_max REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_race_snapshot
            ON odds_snapshots(race_id, snapshot_time)
        """)

    def insert_snapshot(self, race_id: str, umaban: str, snapshot_time: str, odds: dict):
        """スナップショット挿入"""
        self.conn.execute("""
            INSERT INTO odds_snapshots (race_id, umaban, snapshot_time, win_odds, place_odds_min, place_odds_max)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (race_id, umaban, snapshot_time, odds['win_odds'], odds['place_odds_min'], odds['place_odds_max']))

        self.conn.commit()

    def get_latest_odds(self, race_id: str):
        """最新オッズ取得"""
        cursor = self.conn.execute("""
            SELECT umaban, win_odds, place_odds_min, place_odds_max
            FROM odds_snapshots
            WHERE race_id = ?
            ORDER BY snapshot_time DESC
            LIMIT 18
        """, (race_id,))

        return {row[0]: {'win_odds': row[1], 'place_odds_min': row[2], 'place_odds_max': row[3]} for row in cursor}
```

---

## 🎯 推奨事項

### 今すぐやること

1. **ファイルベースで開始**
   - `E:\share\KEIBA-DATA\jv-data\ODDS\` ディレクトリ作成
   - オッズ取得スクリプト作成
   - タスクスケジューラ設定

2. **OddsManagerの活用**
   - `ml/betting/odds_manager.py` をインポート
   - 最新オッズ取得テスト
   - 期待値計算と統合

3. **2段階判断の実装**
   - 前日夜に候補選定
   - 締切前に最終判断
   - 人間承認フロー

### 将来的に検討

1. **オッズ変動分析**
   - 人気馬のオッズ下落パターン
   - 穴馬のオッズ上昇パターン
   - 最適な購入タイミング判定

2. **DB化**
   - 時系列分析が重要になったら
   - SQLiteで軽量実装

3. **リアルタイムAPI**
   - JRA公式APIが利用可能になったら
   - WebSocket経由でリアルタイム取得

---

## 📚 関連ドキュメント

- [BETTING_STRATEGY_FRAMEWORK.md](./BETTING_STRATEGY_FRAMEWORK.md) - 購入戦略詳細
- [EXPERT_SYSTEM_ARCHITECTURE.md](../../ai-team/knowledge/EXPERT_SYSTEM_ARCHITECTURE.md) - エージェント構成

---

*作成日: 2026-01-30*
*バージョン: 1.0*

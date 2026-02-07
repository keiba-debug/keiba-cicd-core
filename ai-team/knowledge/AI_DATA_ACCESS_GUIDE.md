# AI競馬予想チーム データアクセスガイド

**バージョン**: 1.0
**最終更新**: 2026-01-31
**作成者**: カカシ（AI相談役）
**対象**: 全AIエージェント（ANALYST、ARTETA、シノ、シカマル、サイ、KIBA等）

---

## 📍 このガイドの目的

このガイドは、**AIエージェントが自動でデータを取得・分析するための実践的な手引き**です。

### 3つの柱
1. **WebViewer API仕様** - 詳細は[WEBVIEWER_API_SPECIFICATION.md](../../keiba-cicd-core/KeibaCICD.WebViewer/docs/api/WEBVIEWER_API_SPECIFICATION.md)
2. **UI画面機能** - 詳細は[UI_FEATURES.md](../../keiba-cicd-core/KeibaCICD.WebViewer/docs/UI_FEATURES.md)
3. **AIエージェント別推奨API** - このドキュメント

---

## 🎯 エージェント別推奨API一覧

### ANALYST（ひなた）- 分析統括

**役割**: レース分析、馬分析、収支分析

**使用すべきAPI**:

1. **分析データ取得**:
   ```bash
   # 馬券種別回収率分析
   GET /api/bankroll/stats?period=3months

   # レースオッズ + 分析パターン
   GET /api/odds/race?raceId=2026013105010101

   # オッズ変動トレンド
   GET /api/odds/timeseries?raceId=2026013105010101

   # 調教評価
   GET /api/training/summary?date=20260131&format=json
   ```

2. **結果確認**:
   ```bash
   # 予想確認
   GET /api/predictions/20260131/2026013105010101

   # 日別成績
   GET /api/bankroll/daily/20260131
   ```

**実装例**:
```python
import requests

def analyze_race(race_id):
    # オッズデータ取得
    odds_response = requests.get(f"http://localhost:3000/api/odds/race?raceId={race_id}")
    odds_data = odds_response.json()

    # 分析パターン確認
    pattern = odds_data.get("analysis", {}).get("pattern")

    if pattern == "favorite_down":
        print("本命馬の人気が下落中。穴馬に注目")

    # 時系列オッズ取得
    timeseries_response = requests.get(f"http://localhost:3000/api/odds/timeseries?raceId={race_id}")
    timeseries_data = timeseries_response.json()

    # 変動分析
    for change in timeseries_data["changes"]:
        if change["trend"] == "up" and change["changePercent"] > 20:
            print(f"馬番{change['umaban']}: 人気上昇（+{change['changePercent']}%）")

    return {
        "pattern": pattern,
        "changes": timeseries_data["changes"]
    }
```

**🎯 分析のポイント**:
- オッズパターン（favorite_down, favorite_up等）で戦略変更
- 時系列変動で「締切直前の人気変動」を検出
- 馬券種別統計で「今月の得意券種」を把握

---

### ARTETA（アルテタ）- ML予想エージェント

**役割**: 機械学習モデルによる予想

**使用すべきAPI**:

1. **学習データ取得**:
   ```bash
   # 馬の基本情報検索
   GET /api/horses/search?q=ドウデュース

   # 調教データ（ML入力）
   GET /api/debug/training?date=20260131

   # 調教サマリー
   GET /api/training/summary?date=20260131

   # レース詳細情報
   GET /api/race-lookup?date=2026/01/31&track=東京&raceNumber=1
   ```

2. **予想保存**:
   ```bash
   # ML予想結果保存
   POST /api/predictions/20260131/2026013105010101
   Content-Type: application/json

   {
     "marks": {"1": "◎", "2": "○", "3": "▲"},
     "scores": {"1": 95, "2": 85, "3": 75},
     "confidence": "高",
     "status": "confirmed"
   }
   ```

**実装例**:
```python
import requests
import json

def ml_predict_race(race_id, date):
    # レース情報取得
    race_info = requests.get(f"http://localhost:3000/api/race-lookup?date={date}&track=東京&raceNumber=1").json()

    # 調教データ取得
    training_data = requests.get(f"http://localhost:3000/api/training/summary?date={date}&format=json").json()

    # MLモデルで予測（仮）
    predictions = ml_model.predict(race_info, training_data)

    # 予想保存
    prediction_payload = {
        "marks": {
            "1": "◎",
            "2": "○",
            "3": "▲"
        },
        "scores": {
            "1": predictions[0]["score"],
            "2": predictions[1]["score"],
            "3": predictions[2]["score"]
        },
        "confidence": "高",
        "status": "confirmed"
    }

    response = requests.post(
        f"http://localhost:3000/api/predictions/{date}/{race_id}",
        json=prediction_payload
    )

    return response.json()
```

**🎯 ML学習のポイント**:
- 調教データ（lapClass, timeClass）を数値化して入力
- レース特性（RPCI）を特徴量に追加
- 馬場状態（良/稍重/重/不良）をカテゴリ変数化

---

### シノ（期待値計算エージェント）

**役割**: オッズ×勝率で期待値計算、購入判定

**使用すべきAPI**:

1. **期待値計算**:
   ```bash
   # オッズ取得
   GET /api/odds/race?raceId=2026013105010101

   # 時系列オッズ（変動予測用）
   GET /api/odds/ji-timeseries?raceId=2026013105010101
   ```

2. **購入判定**:
   ```bash
   # 購入可能判定
   POST /api/bankroll/check
   Content-Type: application/json

   {
     "betType": "win",
     "amount": 3000
   }
   ```

3. **期待値結果保存**:
   ```bash
   # 購入記録保存
   POST /api/purchases/20260131
   Content-Type: application/json

   {
     "race_id": "2026013105010101",
     "bet_type": "win",
     "selection": "1",
     "amount": 3000,
     "odds": 5.0,
     "expected_value": 750
   }
   ```

**実装例**:
```python
import requests

def calculate_expected_value(race_id, date):
    # オッズ取得
    odds_response = requests.get(f"http://localhost:3000/api/odds/race?raceId={race_id}")
    odds_data = odds_response.json()

    # 予想取得（ANALYSTまたはARTETAが作成済み）
    prediction_response = requests.get(f"http://localhost:3000/api/predictions/{date}/{race_id}")
    prediction_data = prediction_response.json()

    # 期待値計算
    expected_values = []
    for horse in odds_data["horses"]:
        umaban = horse["umaban"]
        odds = horse["odds"]

        # スコアから勝率を推定（仮）
        score = prediction_data["scores"].get(umaban, 0)
        win_probability = score / 100  # 0-1の範囲

        expected_value = (odds * win_probability) - 1

        if expected_value > 0.2:  # 期待値20%以上
            expected_values.append({
                "umaban": umaban,
                "odds": odds,
                "win_probability": win_probability,
                "expected_value": expected_value
            })

    # 購入判定
    for ev in expected_values:
        check_response = requests.post(
            "http://localhost:3000/api/bankroll/check",
            json={"betType": "win", "amount": 3000}
        )
        check_data = check_response.json()

        if check_data["canBet"]:
            # 購入記録
            purchase_payload = {
                "race_id": race_id,
                "bet_type": "win",
                "selection": ev["umaban"],
                "amount": 3000,
                "odds": ev["odds"],
                "expected_value": round(ev["expected_value"] * 3000)
            }

            requests.post(
                f"http://localhost:3000/api/purchases/{date}",
                json=purchase_payload
            )

    return expected_values
```

**🎯 期待値計算のポイント**:
- 期待値 = (オッズ × 勝率) - 1
- 期待値 > 0.2（20%以上）で購入推奨
- bankroll/checkで予算チェック必須

---

### シカマル（購入戦略エージェント）

**役割**: 予算管理、馬券種別配分、購入計画

**使用すべきAPI**:

1. **戦略立案**:
   ```bash
   # 予算設定
   GET /api/bankroll/config

   # 馬券種別配分
   GET /api/bankroll/allocation?year=2026&month=1

   # 購入予定管理
   GET /api/bankroll/plans?date=20260131
   ```

2. **実行監視**:
   ```bash
   # バッチ実行監視
   POST /api/admin/execute
   Content-Type: application/json

   {
     "action": "training_summary",
     "date": "2026-01-31"
   }
   ```

**実装例**:
```python
import requests

def create_purchase_strategy(date):
    # 予算設定取得
    config_response = requests.get("http://localhost:3000/api/bankroll/config")
    config = config_response.json()

    daily_limit = config["total_bankroll"] * (config["daily_limit_percent"] / 100)
    race_limit = config["total_bankroll"] * (config["race_limit_percent"] / 100)

    # 馬券種別配分取得
    allocation_response = requests.get("http://localhost:3000/api/bankroll/allocation?year=2026&month=1")
    allocation = allocation_response.json()

    # 購入予定作成
    plans = []
    for alloc in allocation["allocation"]:
        if alloc["recoveryRate"] > 100:  # 回収率100%以上の券種のみ
            plan = {
                "betType": alloc["betType"],
                "amount": int(daily_limit * (alloc["percentage"] / 100)),
                "confidence": "高" if alloc["recoveryRate"] > 120 else "中"
            }
            plans.append(plan)

    return {
        "daily_limit": daily_limit,
        "race_limit": race_limit,
        "plans": plans
    }
```

**🎯 戦略立案のポイント**:
- 回収率100%以上の券種に重点配分
- 日別上限・レース上限を遵守
- 連敗時は購入額を減額

---

### サイ（実行記録エージェント）

**役割**: 購入実績記録、成績管理

**使用すべきAPI**:

1. **購入記録**:
   ```bash
   # 購入実績記録
   POST /api/purchases/20260131
   PUT /api/purchases/20260131  # ステータス更新
   ```

2. **成績確認**:
   ```bash
   # 日別成績確認
   GET /api/bankroll/daily/20260131

   # 資金出入管理
   GET /api/bankroll/fund
   POST /api/bankroll/fund
   ```

**実装例**:
```python
import requests

def record_purchase_result(date, purchase_id, result, payout=0):
    # ステータス更新
    status = "result_win" if result == "的中" else "result_lose"

    update_payload = {
        "id": purchase_id,
        "status": status,
        "payout": payout
    }

    response = requests.put(
        f"http://localhost:3000/api/purchases/{date}",
        json=update_payload
    )

    # 資金履歴更新（競馬収支同期）
    if result == "的中":
        fund_payload = {
            "action": "sync_betting",
            "year": 2026,
            "month": 1
        }
        requests.post("http://localhost:3000/api/bankroll/fund", json=fund_payload)

    return response.json()

def get_daily_summary(date):
    # 日別成績取得
    response = requests.get(f"http://localhost:3000/api/bankroll/daily/{date}")
    summary = response.json()

    print(f"日付: {summary['date']}")
    print(f"総投資: {summary['summary']['total_bet']}円")
    print(f"総払戻: {summary['summary']['total_payout']}円")
    print(f"収支: {summary['summary']['profit']}円")
    print(f"回収率: {summary['summary']['recovery_rate']}%")

    return summary
```

**🎯 記録管理のポイント**:
- 購入時に `status: "planned"` で記録
- 結果確定後に `status: "result_win"` or `"result_lose"` に更新
- 資金履歴は月次で同期

---

### GUARDIAN（リスク管理エージェント）

**役割**: 予算アラート、リスク監視

**使用すべきAPI**:

1. **リスク監視**:
   ```bash
   # 予算アラート取得
   GET /api/bankroll/alerts

   # 購入前リスクチェック
   POST /api/bankroll/check
   ```

**実装例**:
```python
import requests

def monitor_risks():
    # アラート取得
    response = requests.get("http://localhost:3000/api/bankroll/alerts")
    alerts = response.json()

    for alert in alerts["alerts"]:
        if alert["severity"] == "high":
            print(f"⚠️ 警告: {alert['message']}")
        elif alert["severity"] == "medium":
            print(f"⚡ 注意: {alert['message']}")

    return alerts
```

**🎯 リスク管理のポイント**:
- 残り予算20%未満で警告
- 5連敗で警告、10連敗で購入停止推奨
- 当日使用率80%以上で警告

---

### LEARNER（ナルト - 継続学習エージェント）

**役割**: 過去データ学習、パターン分析

**使用すべきAPI**:

1. **学習データ**:
   ```bash
   # レースメモ（振り返り）
   GET /api/memos/2026013105010101?date=2026-01-31

   # スタート状況
   GET /api/start-memo?raceId=2026013105010101

   # 的中馬券コレクション
   GET /api/bankroll/collection
   ```

2. **パターン分析**:
   ```bash
   # 馬券種別傾向分析
   GET /api/bankroll/stats?period=6months
   ```

**実装例**:
```python
import requests

def analyze_success_patterns():
    # 的中馬券コレクション取得
    response = requests.get("http://localhost:3000/api/bankroll/collection")
    collection = response.json()

    # 高配当パターン分析
    high_payout_tickets = [t for t in collection["tickets"] if t["payout"] > 10000]

    patterns = {}
    for ticket in high_payout_tickets:
        bet_type = ticket["bet_type"]
        patterns[bet_type] = patterns.get(bet_type, 0) + 1

    print("高配当パターン:")
    for bet_type, count in patterns.items():
        print(f"  {bet_type}: {count}回")

    return patterns
```

**🎯 学習のポイント**:
- 的中馬券の共通パターンを抽出
- スタートメモと結果の相関分析
- 失敗レースの振り返り（postメモ）

---

### KIBA（データ追跡エージェント）

**役割**: データ取得確認、インデックス管理

**使用すべきAPI**:

1. **データ取得確認**:
   ```bash
   # 開催日一覧
   GET /api/race-dates

   # オッズあるレース一覧
   GET /api/odds/list?date=20260131
   ```

2. **インデックス管理**:
   ```bash
   # インデックス再構築
   POST /api/admin/rebuild-index
   ```

**実装例**:
```python
import requests

def check_data_availability(date):
    # オッズデータ確認
    response = requests.get(f"http://localhost:3000/api/odds/list?date={date}")
    odds_data = response.json()

    if odds_data["count"] == 0:
        print(f"⚠️ {date}: オッズデータ未取得")
        return False

    print(f"✓ {date}: {odds_data['count']}レースのオッズあり")
    return True
```

**🎯 データ追跡のポイント**:
- 毎朝の開催日チェック
- オッズ取得漏れの検出
- インデックス破損時の再構築

---

### COMMANDER（ベンゲル - 全体統括エージェント）

**役割**: バッチ実行、設定管理

**使用すべきAPI**:

1. **バッチ実行**:
   ```bash
   # 定期バッチ実行（調教サマリー、基準値計算等）
   POST /api/admin/execute
   ```

2. **設定管理**:
   ```bash
   # レイティング基準確認
   GET /api/admin/rating-standards

   # RPCI基準確認
   GET /api/admin/rpci-standards
   ```

**実装例**:
```python
import requests
import json

def execute_daily_batch(date):
    # SSE接続でリアルタイムログ受信
    url = "http://localhost:3000/api/admin/execute"
    payload = {
        "action": "training_summary",
        "date": date
    }

    response = requests.post(url, json=payload, stream=True)

    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8'))
            print(f"[{data['type']}] {data.get('data', {})}")
```

**🎯 バッチ管理のポイント**:
- 毎朝の調教サマリー生成
- 月初のRPCI/レイティング基準再計算
- エラー時の自動リトライ

---

## 🔗 データフロー図

```
【データ取得】
KIBA → /api/race-dates → 開催日確認
     → /api/odds/list → オッズ確認

【分析】
ANALYST → /api/odds/race → オッズパターン分析
        → /api/training/summary → 調教評価

ARTETA → /api/training/summary → ML学習
       → /api/predictions/[date]/[raceId] → 予想保存

【期待値計算】
シノ → /api/odds/race → オッズ取得
    → /api/predictions/[date]/[raceId] → 予想取得
    → 期待値計算
    → /api/bankroll/check → 購入可能判定
    → /api/purchases/[date] → 購入記録

【戦略立案】
シカマル → /api/bankroll/config → 予算確認
         → /api/bankroll/allocation → 配分決定
         → /api/bankroll/plans → 購入計画

【実行・記録】
サイ → /api/purchases/[date] → 購入記録
    → /api/bankroll/fund → 資金管理

【学習】
LEARNER → /api/bankroll/collection → 的中パターン
        → /api/memos/[raceId] → 振り返り
```

---

## 📝 実装時の注意事項

### 1. 環境変数の設定
```bash
# 必須環境変数
export KEIBA_DATA_ROOT_DIR="E:\share\KEIBA-CICD\data2"
export JV_DATA_ROOT_DIR="E:\TFJV"
export PYTHON_PATH="C:\path\to\python.exe"
```

### 2. APIエンドポイント
```python
# 開発環境
BASE_URL = "http://localhost:3000"

# 本番環境（将来）
# BASE_URL = "https://keiba-cicd.example.com"
```

### 3. エラーハンドリング
```python
import requests

def safe_api_call(url, method="GET", **kwargs):
    try:
        if method == "GET":
            response = requests.get(url, **kwargs)
        elif method == "POST":
            response = requests.post(url, **kwargs)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return None
```

### 4. レート制限
- 同時接続数: 最大10接続
- SSEストリーム: 1接続まで
- タイムアウト: 30秒

---

## 🚀 クイックスタート

### Step 1: データ確認（KIBA）
```python
import requests

# 本日のレース確認
response = requests.get("http://localhost:3000/api/race-dates")
dates = response.json()["dates"]
print(f"最新開催日: {dates[0]}")
```

### Step 2: 分析実行（ANALYST）
```python
# オッズ分析
race_id = "2026013105010101"
odds = requests.get(f"http://localhost:3000/api/odds/race?raceId={race_id}").json()
print(f"パターン: {odds['analysis']['pattern']}")
```

### Step 3: 予想保存（ARTETA）
```python
# ML予想保存
prediction = {
    "marks": {"1": "◎", "2": "○"},
    "scores": {"1": 95, "2": 85},
    "confidence": "高"
}
requests.post(f"http://localhost:3000/api/predictions/20260131/{race_id}", json=prediction)
```

### Step 4: 期待値計算（シノ）
```python
# 期待値計算 → 購入判定
expected_value = (5.0 * 0.25) - 1  # オッズ5.0、勝率25%
if expected_value > 0.2:
    requests.post("http://localhost:3000/api/purchases/20260131", json={
        "race_id": race_id,
        "bet_type": "win",
        "selection": "1",
        "amount": 3000,
        "odds": 5.0,
        "expected_value": 750
    })
```

### Step 5: 結果記録（サイ）
```python
# 結果更新
requests.put("http://localhost:3000/api/purchases/20260131", json={
    "id": "20260131_16707200xx",
    "status": "result_win",
    "payout": 15000
})
```

---

## 📚 関連ドキュメント

### 詳細仕様
- [WebViewer API仕様書](../../keiba-cicd-core/KeibaCICD.WebViewer/docs/api/WEBVIEWER_API_SPECIFICATION.md) - 全34API詳細
- [UI画面機能一覧](../../keiba-cicd-core/KeibaCICD.WebViewer/docs/UI_FEATURES.md) - 全16画面詳細

### データ仕様
- [DATA_SPECIFICATION.md](./DATA_SPECIFICATION.md) - データ構造統一仕様
- [JRA-VAN使用ガイド](../../keiba-cicd-core/KeibaCICD.TARGET/docs/jravan/USAGE_GUIDE.md)

### チームガイドライン
- [CLAUDE.md](./CLAUDE.md) - AIチームガイドライン v1.0
- [HANDOVER.md](./HANDOVER_20260131.md) - 日次引き継ぎ記録

---

## 🎯 まとめ

このガイドにより、各AIエージェントは：
1. **自動でデータを取得**（WebViewer API経由）
2. **分析・予想を実行**（オッズ、調教、レース特性等）
3. **期待値計算・購入判定**（リスク管理含む）
4. **結果記録・学習**（継続的改善）

を実現できます。

**次のステップ**:
- 各エージェントの実装コードを`keiba-ai/agents/`に配置
- 定期実行スケジュール（cron）の設定
- エラー通知システムの構築

---

**文書作成日**: 2026-01-31
**作成者**: カカシ（AI相談役）
**承認者**: ふくだ君

---

AIエージェントが実際に競馬予想システムを自動運用できるよう、詳細な実装例を含めて記載しました。

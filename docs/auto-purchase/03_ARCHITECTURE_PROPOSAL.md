# 03. TO-BE アーキテクチャ提案

## 1. 設計原則

1. **L4/L5分離**: 買い目・金額（Themis）と 実行（Executor）は別モジュール
2. **既存資産最大再利用**: `bet_engine`, `target-pd-writer`, `bankroll/check`, `confirmed_bets`
3. **半自動デフォルト**: 完全無人は Phase 4 まで禁止（kill switch 常備）
4. **イベント駆動**: vb_refresh・人間操作・締切タイマーで状態遷移
5. **単一の真実**: `purchase_ledger/{date}.json` が購入パイプラインの SoT

## 2. 論理アーキテクチャ

```mermaid
flowchart TB
  subgraph L1_L3 [既存: データ・推論]
    JV[JRA-VAN / keibabook]
    ML[predict / vb_refresh]
    D3[(data3 predictions bets)]
  end

  subgraph L4 [Themis - 購入決定]
    BE[bet_engine.py / bet-engine.ts]
    BR[bankroll config + check]
  end

  subgraph NEW [新規: Orchestrator]
    SCH[Schedule Service]
    ORC[Purchase Orchestrator]
    LED[(purchase_ledger)]
  end

  subgraph L5 [購入実行]
    FF[target-pd-writer / auto-bet API]
    TGT[TARGET IPAT連動]
    IPAT[JRA IPAT]
  end

  subgraph L6 [記録・監視]
    PUR[userdata/purchases]
    DASH[/auto-purchase UI]
    ALT[Alert Service]
  end

  JV --> ML --> D3
  D3 --> BE --> ORC
  BR --> ORC
  SCH --> ORC
  ML -->|vb_refresh event| ORC
  ORC --> LED
  ORC --> FF --> TGT --> IPAT
  ORC --> PUR
  LED --> DASH
  ORC --> ALT
```

## 3. 新規コンポーネント

### 3.1 Purchase Orchestrator（Python 推奨）

**配置案**: `keiba-v2/ml/purchase_orchestrator.py` または `keiba-v2/services/purchase_orchestrator/`

**責務**

| 責務 | 説明 |
|------|------|
| スケジュール | 当日レース一覧と T-10, T-7 トリガ生成 |
| 再評価 | vb_refresh 後の bets 差分検知 |
| ガード | bankroll DD、日上限、horse exposure（将来） |
| FFキュー | 承認済みレースのみ `auto-bet` 相当を呼ぶ |
| 状態更新 | ledger の遷移 |

**呼び出し元**

- Windows タスク: `purchase_orchestrator_tick.bat`（1分間隔、開催日のみ）
- Web API: `POST /api/auto-purchase/approve`, `emergency-stop`
- vb_refresh 完了フック（オプション）

### 3.2 Purchase Ledger（JSON）

`data3/userdata/purchase_ledger/YYYY-MM-DD.json` — スキーマは [07_DATA_SCHEMA_AND_EVENTS.md](./07_DATA_SCHEMA_AND_EVENTS.md)

### 3.3 Auto-Purchase API（Next.js）

| メソッド | パス | 用途 |
|----------|------|------|
| GET | `/api/auto-purchase/status?date=` | 当日全レース状態 |
| POST | `/api/auto-purchase/mode` | manual / semi / stopped |
| POST | `/api/auto-purchase/races/{raceId}/approve` | 半自動承認 |
| POST | `/api/auto-purchase/races/{raceId}/confirm-ipat` | IPAT投票完了申告 |
| POST | `/api/auto-purchase/emergency-stop` | 全停止 |
| GET | `/api/auto-purchase/events?tail=50` | イベントログ |

### 3.4 Dashboard UI

`web/src/app/auto-purchase/page.tsx` — [04_UI_UX_DESIGN.md](./04_UI_UX_DESIGN.md)

## 4. 既存コンポーネントとの接続

| 既存 | 接続方法 |
|------|----------|
| `ml.vb_refresh` | 終了時に `--emit-orchestrator-event` または ledger の `last_refresh_at` 更新 |
| `POST /api/target-marks/auto-bet` | Orchestrator から内部 fetch（同一ロジックを Python に移植も可） |
| `bankroll/check` | Orchestrator が FF 出力前にバッチ呼び出し |
| `confirmed_bets` | 承認時にスナップショット複製 → ledger `snapshot_id` |
| `settle_purchases` | ledger `SETTLED` と purchases 精算を同期 |

## 5. モード定義

| モード | FF自動 | TARGET | IPAT最終投票 | 用途 |
|--------|--------|--------|--------------|------|
| `manual` | 手動のみ | 手動 | 手動 | 現状相当 |
| `semi` | 締切前自動（要承認可） | 手動取込 | 人手 | **推奨デフォルト** |
| `auto_ff` | 自動 | 手動 | 人手 | 承認スキップ版（上級者） |
| `stopped` | 禁止 | — | — | 緊急停止 |

## 6. Themis 拡張（購入決定側・変更最小）

既存 `bet_engine` を変えず、Orchestrator が以下のみ追加判定:

```python
def should_offer_race(race, bets, bankroll_state, mode_config) -> Decision:
    if bankroll_state.emergency_stop:
        return SKIP("emergency")
    if race.state == "EV_COLLAPSED":  # JIT: 全推奨が EV < 1
        return SKIP("ev_collapsed")
    if race.minutes_to_post < mode_config.min_minutes_before_post:
        return SKIP("too_late")
    return ELIGIBLE
```

## 7. デプロイ・実行環境

| 項目 | 案 |
|------|-----|
| ホスト | 既存 KeibaCICD Windows マシン（vb_refresh と同じ） |
| プロセス | タスクスケジューラ + Next.js IIS |
| ログ | `data3/logs/purchase_orchestrator/` |
| 設定 | `data3/userdata/auto_purchase_config.json` |

## 8. テスト戦略

| 層 | 内容 |
|----|------|
| 単体 | 状態遷移、冪等キー、締切計算 |
| 結合 | モック FF 出力、ledger 読み書き |
| E2E | 非開催日ドライラン、過去日付リプレイ |
| 本番前 | 100円×1レース・手動確認 |

## 9. 非機能要件

| 要件 | 目標 |
|------|------|
| 可用性 | vb_refresh 停止時は自動購入オフ |
| レイテンシ | 承認→FF出力 < 5秒 |
| 復旧 | ledger が壊れても purchases から再構築可能 |
| セキュリティ | IPAT認証情報は Orchestrator に持たない（Aルート時） |

## 10. 松風8モジュールとの対応表

| 松風 | KeibaCICD TO-BE |
|------|-----------------|
| Zeus | builders, mykeibadb, data3 |
| Poseidon | ml/train, features |
| 推論 | predict, vb_refresh |
| **Themis** | bet_engine + bankroll |
| **購入実行** | Orchestrator + FF + TARGET/IPAT |
| 記録・監視 | purchase_ledger + purchases + dashboard |
| スケジューリング | orchestrator tick + race schedule |
| レポーティング | bankroll PerformanceTab + 将来レポートAPI |

# ベッティングシステム設計書

> v5.36 (2026-02-28) — VB Floor Gate導入

## 1. 概要

2層フィルターアーキテクチャにより、Value Bet候補から購入プランを選出する。

```
全出走馬 → [Layer 1: VB Floor] → VB候補 → [Layer 2: プリセット] → 購入プラン
```

**不変条件**: `購入プラン ⊆ VB候補`（全プリセット・全オッズ状況で）

## 2. VB判定基準 (is_value_bet)

### 条件A: EV + ARd（メインルート）
```
win_ev >= 1.0  AND  ar_deviation >= 50.0
```
- `win_ev` = calibrated_pred_proba_wv × 単勝オッズ（IsotonicRegression校正済み確率）
- `ar_deviation` = AR偏差値（レース内相対評価、mean=50 std=10）

### 条件B: ARd VBルート（能力 vs 市場乖離）
```
ar_deviation >= 65.0  AND  odds >= 10.0
```
- EV/Gap条件をバイパスする独立ルート
- 高能力（ARd>=65）なのに市場が見逃している（odds>=10）馬を捕捉
- BT実績: 80件, 勝率11.2%, WinROI 179.9% (Session 60)

### 判定式
```python
is_value_bet = (条件A) OR (条件B)
```

### 定数管理

| 定数 | 値 | Python (`bet_engine.py`) | TypeScript (`bet-engine.ts`) |
|------|-----|--------------------------|------------------------------|
| EV下限 | 1.0 | `VB_FLOOR_MIN_WIN_EV` | `VB_FLOOR.minWinEv` |
| ARd下限 | 50.0 | `VB_FLOOR_MIN_ARD` | `VB_FLOOR.minArd` |
| ARd VB ARd | 65.0 | `VB_FLOOR_ARD_VB_MIN_ARD` | `VB_FLOOR.ardVbMinArd` |
| ARd VB Odds | 10.0 | `VB_FLOOR_ARD_VB_MIN_ODDS` | `VB_FLOOR.ardVbMinOdds` |

**同期ルール**: Python側をマスターとし、TS側は手動同期。変更時はPython定数のコメントに同期先を記載。

## 3. 購入プラン選出フロー

```
for each horse in race:
  ┌─ Layer 1: VB Floor Gate ─────────────────┐
  │  win_ev >= 1.0 AND ARd >= 50?            │
  │  OR ARd >= 65.0 AND odds >= 10?          │
  │  → NO: skip (not a VB candidate)         │
  └──────────────────────────────────────────┘
         ↓ (VB候補のみ通過)
  ┌─ Layer 2: プリセットフィルター ──────────┐
  │  2a. V%比率 >= 0.75 (pre-filter)         │
  │      ※バイパス: gap>=7 & EV>=3.0         │
  │  2b. ARd段階gap                          │
  │      ARd>=65 → gap>=3                    │
  │      ARd>=55 → gap>=4                    │
  │      ARd>=45 → gap>=5                    │
  │      ARd<45  → 不合格                    │
  │  2c. EV閾値 (プリセット別)               │
  │      standard=1.5 / wide=0.0 / aggr=1.8 │
  │  2d. ARd VBルート (2a-2c独立)            │
  │      ARd>=65 & odds>=10 → 直接通過       │
  │  2e. 1R最大2単勝 (gap上位2頭)            │
  └──────────────────────────────────────────┘
         ↓
  購入プラン output
```

### ライブオッズの反映

TS `bet-engine.ts` はライブオッズで以下を再計算:
- `odds_rank` → `gap` (market rank - model rank)
- `win_ev` = `pred_proba_wv_cal × liveOdds` (calibrated確率 × ライブオッズ)
- VB Floor Gateもライブ値でチェック

→ 予測時 `is_value_bet=True` でもライブオッズ低下でEV<1.0になれば購入プランから外れる。

## 4. プリセット比較

| パラメータ | standard | wide | aggressive |
|-----------|----------|------|------------|
| EV閾値 | >= 1.5 | なし (0.0) | >= 1.8 |
| V%比率 | >= 0.75 | >= 0.75 | >= 0.75 |
| ARd段階gap | [(65,3),(55,4),(45,5)] | 同左 | 同左 |
| ARd VBルート | ARd>=65,odds>=10 | 同左 | 同左 |
| 危険馬boost | 0 | 0 | 0 |
| 最大単勝/R | 2 | 2 | 2 |
| 配分 | WinOnly | WinOnly | WinOnly |

### BT実績 (2025-2026テスト期間, 3%均等)

| プリセット | ROI | MaxDD | Calmar | ベット数 |
|-----------|-----|-------|--------|---------|
| **aggressive** | **182%** | 43% | **7.01** | 178 |
| standard | 135% | 43% | 2.25 | 206 |
| wide | TBD (VB Floor導入後に要再検証) | - | - | - |

**推奨**: aggressive + 3% + 均等

## 5. データフロー

```
predict.py
  ├─ ML models → pred_proba_wv_cal (calibrated)
  ├─ win_ev = pred_proba_wv_cal × odds
  ├─ ar_deviation (regression model → 偏差値化)
  └─ is_value_bet = (EV>=1.0 & ARd>=50) OR (ARd>=65 & odds>=10)
       ↓
predictions_live.json / predictions.json (archive)
       ↓
Web UI
  ├─ VB候補テーブル: is_value_bet==true でフィルタ
  ├─ 購入プラン:
  │    ├─ /api/odds/db-latest → ライブオッズ (30秒更新)
  │    ├─ bet-engine.ts: VB Floor Gate (ライブEV/ARdでゲート)
  │    ├─ bet-engine.ts: プリセットフィルター
  │    └─ bet-engine.ts: 予算配分
  └─ 馬単・ワイド推奨: simulate_multi_leg.py → multi_leg_recommendations
```

## 6. 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| v5.36 | 2026-02-28 | VB Floor Gate導入、is_value_bet拡張(ARd VBルート)、pred_proba_wv_cal追加 |
| v5.35 | 2026-02 | WinOnly最適化、予算率UI、プリセット比較 |
| v5.34 | 2026-02 | ARd VBルート追加、TS bet-engine LIVE化 |
| v5.32 | 2026-02 | max_win_per_race=2 |

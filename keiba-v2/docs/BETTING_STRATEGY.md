# ベッティング戦略フレームワーク (keiba-v2)

> 期待値計算、資金管理、バックテストの設計指針。
> v1のフレームワークをv2 Value Bet戦略に適合。

---

## 期待値 (Expected Value) 計算

### 基本式

```python
# 単勝 EV
ev_win = prob_win * odds_win - (1 - prob_win)
# ev > 0 なら期待値プラス

# 複勝 EV
ev_place = prob_top3 * odds_place - (1 - prob_top3)

# EVレート (1.0以上で期待値プラス)
ev_rate = prob * odds
# ev_rate >= 1.10 をベット閾値とする
```

### 馬連・ワイド (参考)
```python
# 独立仮定
prob_quinella = prob_a_top2 * prob_b_top2
ev_quinella = prob_quinella * odds_quinella - (1 - prob_quinella)
```

---

## Value Bet 戦略 (v2実績ベース)

### 概要
Model A (全特徴量) と Model B (市場独立特徴量) の順位乖離を利用。
市場（オッズ）が織り込んでいない実力差を検出する。

```python
rank_gap = model_a_rank - model_b_rank

# rank_gap > 0: 市場が過小評価している馬
# 市場系特徴量を含むModel Aでは低順位だが、
# 実力ベースのModel Bでは高順位 → オッズに対して割安
```

### 実績データ (v2)

| 条件 | 賭け数 | 複勝的中率 | 複勝ROI |
|------|--------|----------|---------|
| gap >= 2 | 6,036 | 37.7% | 94.5% |
| gap >= 3 | 3,543 | 35.2% | **104.7%** |
| gap >= 4 | 2,065 | 33.5% | **112.1%** |
| gap >= 5 | 1,179 | 30.4% | 99.9% |

### 推奨設定
- **複勝**: gap >= 3 で賭け → ROI 104.7%
- **高配当狙い**: gap >= 4 に絞る → ROI 112.1%
- gap >= 5 は的中率低下でROI低下 → 非推奨

---

## Kelly Criterion (資金管理)

### Full Kelly
```python
f_star = (b * p - q) / b

# f_star: 最適賭け比率 (bankrollに対する%)
# b: 純利益倍率 (odds - 1)
# p: 勝率
# q: 敗率 (1 - p)

# 例: prob=0.30, odds=5.0
# f* = (4.0 * 0.30 - 0.70) / 4.0 = 0.125 (12.5%)
```

### Fractional Kelly (推奨)
```python
# Full Kellyは変動が大きすぎる → 1/2〜1/4 Kelly推奨
bet_fraction = f_star * kelly_fraction  # kelly_fraction = 0.25〜0.5

# 例: f*=12.5%, 1/2 Kelly → 6.25% of bankroll
```

---

## リスク管理

### 損失制限
```python
max_daily_loss = bankroll * 0.05    # 1日最大5%損失
max_race_loss = bankroll * 0.02     # 1レース最大2%損失
consecutive_loss_halt = 3            # 連敗3で当日停止
```

### ベッティング判定フロー
```
1. Value Bet検出: rank_gap >= 3?
2. EV確認: ev_rate >= 1.10?
3. リスク確認: bet_amount <= max_race_loss?
4. 連敗確認: consecutive_losses < 3?
5. Kelly計算: bet = bankroll * kelly_fraction * f_star
6. 実行
```

---

## バックテスト設計

### 記録項目
```python
@dataclass
class BetRecord:
    race_id: str          # 16桁
    race_date: str
    horse_name: str
    ketto_num: str
    bet_type: str         # "win" / "place"
    bet_amount: int
    odds: float
    rank_gap: int
    model_a_rank: int
    model_b_rank: int
    is_hit: bool
    profit: int           # 配当 - 賭け金
    bankroll_after: int
```

### 評価指標
```python
# 基本指標
total_bets: int            # 総賭け数
total_invested: int        # 総投資額
total_return: int          # 総回収額
hit_rate: float            # 的中率
recovery_rate: float       # 回収率 (return / invested * 100)
roi: float                 # ROI (profit / invested * 100)

# リスク指標
max_drawdown: float        # 最大ドローダウン
max_consecutive_losses: int
sharpe_ratio: float        # (平均利益 / 利益の標準偏差)
```

---

## 凡走予測（逆アプローチ）

### 人気馬消し条件 (仮説)
高配当を狙うため、人気馬が凡走するパターンを検出。

```python
# 消耗戦後の短間隔出走
is_exhausted = (prev_rpci <= 46) and (days_since_last <= 14)

# 僅差負け後の消耗
is_depleted = (prev_popularity == 1) and (prev_finish in [2, 3]) and (prev_margin <= 0.2)

# 急坂コース初挑戦
is_slope_naive = (prev_venues_all_flat) and (current_venue_has_slope)

# 斤量増
is_weight_up = (futan - prev_futan >= 2.0)
```

### 活用方法
```python
# 人気馬に凡走フラグが立っている場合:
# 1. その馬の複勝・単勝を避ける
# 2. 相手候補（Value Bet馬）の期待値が上がる
# 3. 馬連・ワイドの穴狙いに活用
```

---

## 実験管理

### 実験ログ
```python
experiment = {
    "name": "v3_kelly_0.5_gap3",
    "date": "2026-02-XX",
    "params": {
        "kelly_fraction": 0.5,
        "min_ev_threshold": 1.10,
        "min_rank_gap": 3,
        "bet_type": "place",
        "model_version": "v3"
    },
    "results": {
        "auc_a": 0.7944,
        "auc_b": 0.7635,
        "roi_gap3": 104.7,
        "roi_gap4": 112.1,
        "hit_rate": 35.2,
        "total_bets": 3543,
        "max_drawdown": -15.2
    }
}
```

### 実験比較ポイント
- AUC (Model A / Model B)
- Value Bet ROI (gap>=3, gap>=4)
- 複勝的中率
- 最大ドローダウン
- 特徴量重要度の変化

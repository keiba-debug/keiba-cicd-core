# 馬券購入戦略フレームワーク

**予想精度よりも購入戦略が重要**

このドキュメントでは、期待値ベースの馬券購入判断システムを設計します。

---

## 🎯 基本方針

### 人間の役割 vs システムの役割

```
人間の役割:
  ├─ データ収集の確認
  ├─ モデル性能のモニタリング
  ├─ 戦略ルールの設定（閾値、リスク許容度）
  └─ 最終的な購入実行の承認

システムの役割:
  ├─ 予測確率の計算
  ├─ 期待値の計算
  ├─ 最適賭け金の計算
  ├─ リスク評価
  └─ 購入推奨リストの生成
```

**重要**: 人間は判断せず、情報整理と承認のみ。購入判断は機械的にルールベースで行う。

---

## 📐 期待値計算の基礎

### 1. 期待値（Expected Value）とは

```
期待値 = (勝率 × 的中時の払戻) - (負け率 × 賭け金)

期待値 > 0 → 長期的に利益が出る
期待値 < 0 → 長期的に損失が出る
```

### 2. 単勝馬券の期待値計算

```python
def calculate_expected_value_win(prob: float, odds: float, bet_amount: int = 100) -> float:
    """
    単勝馬券の期待値を計算

    Args:
        prob: 勝率予測（0.0~1.0）
        odds: 単勝オッズ
        bet_amount: 賭け金

    Returns:
        期待値（円）
    """
    # 的中時の払戻
    return_if_win = odds * bet_amount

    # 期待値計算
    expected_value = (prob * return_if_win) - ((1 - prob) * bet_amount)

    return expected_value

# 例
prob = 0.30  # 30%の勝率予測
odds = 5.0   # 5倍のオッズ

ev = calculate_expected_value_win(prob, odds, bet_amount=100)
print(f"期待値: {ev}円")  # => 期待値: 80円

# 期待値率
ev_rate = (ev / 100) * 100
print(f"期待値率: {ev_rate}%")  # => 80%
```

### 3. 複勝馬券の期待値計算

```python
def calculate_expected_value_place(
    prob_top3: float,
    odds_place: float,
    bet_amount: int = 100
) -> float:
    """
    複勝馬券の期待値を計算

    Args:
        prob_top3: 3着以内に入る確率
        odds_place: 複勝オッズ
        bet_amount: 賭け金

    Returns:
        期待値（円）
    """
    return_if_win = odds_place * bet_amount
    expected_value = (prob_top3 * return_if_win) - ((1 - prob_top3) * bet_amount)

    return expected_value
```

### 4. 馬連の期待値計算

```python
def calculate_expected_value_quinella(
    prob_horse1_top2: float,
    prob_horse2_top2: float,
    odds_quinella: float,
    bet_amount: int = 100
) -> float:
    """
    馬連の期待値を計算（簡易版）

    Args:
        prob_horse1_top2: 馬1が2着以内に入る確率
        prob_horse2_top2: 馬2が2着以内に入る確率
        odds_quinella: 馬連オッズ
        bet_amount: 賭け金

    Returns:
        期待値（円）
    """
    # 両方が2着以内に入る確率（独立性を仮定）
    prob_both_top2 = prob_horse1_top2 * prob_horse2_top2

    return_if_win = odds_quinella * bet_amount
    expected_value = (prob_both_top2 * return_if_win) - ((1 - prob_both_top2) * bet_amount)

    return expected_value
```

---

## 💰 資金管理：ケリー基準

### ケリー基準（Kelly Criterion）とは

最適な賭け金を数学的に算出する方法。

```
f* = (bp - q) / b

f*: 資金に対する最適賭け割合
b: 的中時の純利益率（オッズ - 1）
p: 勝率予測
q: 負け率（1 - p）
```

### Python実装

```python
def kelly_criterion(prob: float, odds: float) -> float:
    """
    ケリー基準で最適賭け割合を計算

    Args:
        prob: 勝率予測（0.0~1.0）
        odds: オッズ

    Returns:
        最適賭け割合（0.0~1.0）
    """
    b = odds - 1  # 純利益率
    p = prob
    q = 1 - p

    f_star = (b * p - q) / b

    # 負の値の場合は賭けない
    return max(0, f_star)

# 例
prob = 0.30
odds = 5.0

kelly_fraction = kelly_criterion(prob, odds)
print(f"最適賭け割合: {kelly_fraction:.1%}")  # => 12.5%

# 資金10万円の場合
bankroll = 100000
optimal_bet = bankroll * kelly_fraction
print(f"最適賭け金: {optimal_bet:.0f}円")  # => 12,500円
```

### フラクショナル・ケリー（推奨）

ケリー基準は攻めすぎる傾向があるため、実際には1/2や1/4に抑える。

```python
def fractional_kelly(prob: float, odds: float, fraction: float = 0.5) -> float:
    """
    フラクショナル・ケリーで賭け割合を計算

    Args:
        prob: 勝率予測
        odds: オッズ
        fraction: ケリー割合（0.25~0.5が一般的）

    Returns:
        賭け割合
    """
    kelly_full = kelly_criterion(prob, odds)
    return kelly_full * fraction

# 例: Half Kelly
kelly_fraction = fractional_kelly(prob, odds, fraction=0.5)
print(f"Half Kelly賭け割合: {kelly_fraction:.1%}")  # => 6.25%
```

---

## 🛡️ リスク管理ルール

### 1. 最大損失制限

```python
class RiskManager:
    def __init__(self, bankroll: int):
        self.bankroll = bankroll
        self.max_loss_per_day = bankroll * 0.05  # 1日最大5%まで
        self.max_loss_per_race = bankroll * 0.02  # 1レース最大2%まで
        self.daily_loss = 0
        self.consecutive_losses = 0

    def can_bet(self, bet_amount: int) -> tuple[bool, str]:
        """
        賭けが許可されるかチェック

        Returns:
            (許可, 理由)
        """
        # 1日の損失上限チェック
        if self.daily_loss >= self.max_loss_per_day:
            return False, "1日の損失上限に達しました"

        # 1レースの賭け金上限チェック
        if bet_amount > self.max_loss_per_race:
            return False, f"1レース最大賭け金({self.max_loss_per_race}円)を超えています"

        # 連敗上限チェック（3連敗で一時停止）
        if self.consecutive_losses >= 3:
            return False, "3連敗のため一時停止中"

        return True, "OK"

    def record_result(self, profit: int):
        """結果を記録"""
        self.daily_loss += max(0, -profit)

        if profit < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
```

### 2. 期待値閾値

```python
def should_bet(expected_value: float, min_ev_threshold: float = 1.1) -> bool:
    """
    期待値が閾値以上かチェック

    Args:
        expected_value: 期待値率（1.0 = 100%）
        min_ev_threshold: 最小期待値閾値（1.1 = 110%推奨）

    Returns:
        購入すべきか
    """
    return expected_value >= min_ev_threshold

# 例
ev_rate = 1.15  # 期待値115%
if should_bet(ev_rate, min_ev_threshold=1.1):
    print("購入推奨")
else:
    print("見送り")
```

---

## 🎯 統合購入判断システム

すべてを組み合わせた購入判断フロー。

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class BettingRecommendation:
    """購入推奨結果"""
    horse_name: str
    bet_type: str  # "win", "place", "quinella"
    should_bet: bool
    bet_amount: int
    expected_value: float
    expected_value_rate: float
    kelly_fraction: float
    reason: str


class BettingDecisionEngine:
    """購入判断エンジン"""

    def __init__(
        self,
        bankroll: int = 100000,
        min_ev_threshold: float = 1.10,
        kelly_fraction: float = 0.5
    ):
        self.bankroll = bankroll
        self.min_ev_threshold = min_ev_threshold
        self.kelly_fraction = kelly_fraction
        self.risk_manager = RiskManager(bankroll)

    def evaluate_bet(
        self,
        horse_name: str,
        prob: float,
        odds: float,
        bet_type: str = "win",
        bet_base_amount: int = 100
    ) -> BettingRecommendation:
        """
        馬券を評価して購入推奨を生成

        Args:
            horse_name: 馬名
            prob: 勝率予測
            odds: オッズ
            bet_type: 馬券種別
            bet_base_amount: 基準賭け金

        Returns:
            購入推奨結果
        """
        # 期待値計算
        ev = calculate_expected_value_win(prob, odds, bet_base_amount)
        ev_rate = 1 + (ev / bet_base_amount)

        # ケリー基準で賭け金計算
        kelly_frac = fractional_kelly(prob, odds, fraction=self.kelly_fraction)
        optimal_bet = int(self.bankroll * kelly_frac)

        # 購入判断
        should_bet = False
        reason = ""

        # 1. 期待値チェック
        if ev_rate < self.min_ev_threshold:
            reason = f"期待値不足 ({ev_rate:.1%} < {self.min_ev_threshold:.1%})"
        # 2. リスク管理チェック
        elif not self.risk_manager.can_bet(optimal_bet)[0]:
            reason = self.risk_manager.can_bet(optimal_bet)[1]
        # 3. 賭け金がゼロ（ケリー基準で賭けるべきでない）
        elif optimal_bet <= 0:
            reason = "ケリー基準により賭け金ゼロ"
        else:
            should_bet = True
            reason = f"期待値{ev_rate:.1%}、最適賭け金{optimal_bet}円"

        return BettingRecommendation(
            horse_name=horse_name,
            bet_type=bet_type,
            should_bet=should_bet,
            bet_amount=optimal_bet if should_bet else 0,
            expected_value=ev,
            expected_value_rate=ev_rate,
            kelly_fraction=kelly_frac,
            reason=reason
        )


# 使用例
engine = BettingDecisionEngine(
    bankroll=100000,
    min_ev_threshold=1.10,  # 期待値110%以上
    kelly_fraction=0.5       # Half Kelly
)

# レース予測結果
predictions = [
    {"horse": "馬A", "prob": 0.25, "odds": 6.0},
    {"horse": "馬B", "prob": 0.15, "odds": 8.0},
    {"horse": "馬C", "prob": 0.35, "odds": 3.5},
]

print("=== 購入推奨 ===\n")
for pred in predictions:
    rec = engine.evaluate_bet(
        horse_name=pred["horse"],
        prob=pred["prob"],
        odds=pred["odds"]
    )

    print(f"{rec.horse_name}:")
    print(f"  購入推奨: {'✓ YES' if rec.should_bet else '× NO'}")
    print(f"  賭け金: {rec.bet_amount}円")
    print(f"  期待値率: {rec.expected_value_rate:.1%}")
    print(f"  理由: {rec.reason}")
    print()
```

---

## 📊 バックテストでの検証

購入戦略の有効性を検証する。

```python
class BettingBacktest:
    """購入戦略のバックテスト"""

    def __init__(self, initial_bankroll: int = 100000):
        self.initial_bankroll = initial_bankroll
        self.bankroll = initial_bankroll
        self.bet_history = []

    def run(self, races_df: pd.DataFrame, engine: BettingDecisionEngine):
        """
        バックテスト実行

        Args:
            races_df: レース結果DataFrame（pred_prob, odds, 着順を含む）
            engine: 購入判断エンジン
        """
        for idx, row in races_df.iterrows():
            # 購入判断
            rec = engine.evaluate_bet(
                horse_name=row['horse_name'],
                prob=row['pred_prob'],
                odds=row['odds']
            )

            if rec.should_bet:
                # 結果判定
                is_hit = (row['着順'] == 1)  # 単勝の場合
                profit = (rec.bet_amount * row['odds'] - rec.bet_amount) if is_hit else -rec.bet_amount

                # 資金更新
                self.bankroll += profit

                # 記録
                self.bet_history.append({
                    'race_date': row['race_date'],
                    'horse_name': row['horse_name'],
                    'bet_amount': rec.bet_amount,
                    'odds': row['odds'],
                    'is_hit': is_hit,
                    'profit': profit,
                    'bankroll': self.bankroll
                })

    def report(self):
        """結果レポート"""
        if len(self.bet_history) == 0:
            print("購入実績なし")
            return

        df = pd.DataFrame(self.bet_history)

        total_bets = len(df)
        total_invested = df['bet_amount'].sum()
        total_return = df[df['is_hit']]['bet_amount'] * df[df['is_hit']]['odds']
        total_return = total_return.sum() if len(total_return) > 0 else 0
        total_profit = df['profit'].sum()

        hit_rate = (df['is_hit'].sum() / total_bets) * 100
        recovery_rate = (total_return / total_invested) * 100 if total_invested > 0 else 0
        roi = ((self.bankroll - self.initial_bankroll) / self.initial_bankroll) * 100

        print("=== バックテスト結果 ===")
        print(f"購入回数: {total_bets}回")
        print(f"投資額: {total_invested:,}円")
        print(f"払戻額: {total_return:,}円")
        print(f"的中率: {hit_rate:.1f}%")
        print(f"回収率: {recovery_rate:.1f}%")
        print(f"総収支: {total_profit:+,}円")
        print(f"ROI: {roi:+.1f}%")
        print(f"最終資金: {self.bankroll:,}円")
```

---

## 🔄 トライアンドエラーのサイクル

### 実験管理フレームワーク

```python
import json
from datetime import datetime

class ExperimentTracker:
    """実験管理"""

    def __init__(self, experiment_dir: Path):
        self.experiment_dir = experiment_dir
        self.experiment_dir.mkdir(parents=True, exist_ok=True)

    def log_experiment(
        self,
        name: str,
        params: dict,
        results: dict,
        notes: str = ""
    ):
        """
        実験を記録

        Args:
            name: 実験名
            params: パラメータ（閾値、ケリー係数など）
            results: 結果（回収率、ROIなど）
            notes: メモ
        """
        experiment = {
            'name': name,
            'timestamp': datetime.now().isoformat(),
            'params': params,
            'results': results,
            'notes': notes
        }

        # JSON保存
        filename = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.json"
        filepath = self.experiment_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(experiment, f, ensure_ascii=False, indent=2)

        print(f"✓ 実験記録保存: {filepath}")

# 使用例
tracker = ExperimentTracker(Path("ml/experiments"))

tracker.log_experiment(
    name="kelly_0.5_ev_1.10",
    params={
        'kelly_fraction': 0.5,
        'min_ev_threshold': 1.10,
        'min_prob_threshold': 0.20
    },
    results={
        'roi': 15.5,
        'recovery_rate': 105.2,
        'hit_rate': 32.1,
        'total_bets': 150
    },
    notes="Half Kelly、期待値110%以上で好成績"
)
```

---

## 📈 推奨実験プラン

### Week 1: 基準値の確立

```python
experiments = [
    {'kelly_fraction': 1.0, 'min_ev': 1.05},
    {'kelly_fraction': 0.5, 'min_ev': 1.05},
    {'kelly_fraction': 0.25, 'min_ev': 1.05},
]
```

### Week 2: 期待値閾値の最適化

```python
experiments = [
    {'kelly_fraction': 0.5, 'min_ev': 1.00},
    {'kelly_fraction': 0.5, 'min_ev': 1.05},
    {'kelly_fraction': 0.5, 'min_ev': 1.10},
    {'kelly_fraction': 0.5, 'min_ev': 1.15},
]
```

### Week 3: 複合戦略

```python
experiments = [
    {'strategy': 'conservative', 'kelly': 0.25, 'min_ev': 1.15},
    {'strategy': 'moderate', 'kelly': 0.5, 'min_ev': 1.10},
    {'strategy': 'aggressive', 'kelly': 0.75, 'min_ev': 1.05},
]
```

---

## 🎯 次のステップ

1. **このフレームワークをPythonスクリプト化**
   - `ml/betting/decision_engine.py`
   - `ml/betting/risk_manager.py`
   - `ml/betting/backtest.py`

2. **実験管理システムの構築**
   - `ml/experiments/` ディレクトリ
   - 実験記録の自動化

3. **AIチームメンバーとの協議**
   - ANALYST: 戦略分析
   - COMMANDER: 実行管理
   - LEARNER: 改善学習

---

*作成日: 2026-01-30*
*バージョン: 1.0*

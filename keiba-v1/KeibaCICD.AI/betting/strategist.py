"""
STRATEGIST (シカマル) - 購入戦略エンジン

天才戦略家シカマルが、ケリー基準とリスク管理で最適な賭け金を計算する。

「めんどくせぇな...でも戦略的にはこうだ」
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime


@dataclass
class BettingRecommendation:
    """購入推奨結果"""
    race_id: str
    horse_name: str
    bet_type: str  # "win", "place", "quinella", "exacta"
    should_bet: bool
    bet_amount: int
    expected_value: float
    expected_value_rate: float
    kelly_fraction: float
    risk_level: str  # "low", "medium", "high"
    reason: str
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class KellyCriterion:
    """
    ケリー基準計算エンジン

    「最適な賭け金を数学的に算出する。めんどくせぇけど、これが最強だ」
    """

    @staticmethod
    def calculate(prob: float, odds: float) -> float:
        """
        ケリー基準で最適賭け割合を計算

        Args:
            prob: 勝率予測（0.0~1.0）
            odds: オッズ

        Returns:
            最適賭け割合（0.0~1.0）
        """
        if prob <= 0 or odds <= 1.0:
            return 0.0

        b = odds - 1.0  # 純利益率
        p = prob
        q = 1.0 - p

        # f* = (bp - q) / b
        f_star = (b * p - q) / b

        # 負の値の場合は賭けない
        return max(0.0, f_star)

    @staticmethod
    def fractional_kelly(
        prob: float,
        odds: float,
        fraction: float = 0.5
    ) -> float:
        """
        フラクショナル・ケリー計算

        Args:
            prob: 勝率予測
            odds: オッズ
            fraction: ケリー係数（0.25~0.5が一般的）

        Returns:
            賭け割合

        「Full Kellyは攻めすぎる。Half Kellyで行くぞ」
        """
        kelly_full = KellyCriterion.calculate(prob, odds)
        return kelly_full * fraction


class RiskManager:
    """
    リスク管理システム

    「リスクを見誤ると全てが終わる。慎重に行くぞ」
    """

    def __init__(
        self,
        bankroll: int,
        max_loss_per_day_rate: float = 0.05,
        max_loss_per_race_rate: float = 0.02,
        max_consecutive_losses: int = 3
    ):
        """
        Args:
            bankroll: 総資金
            max_loss_per_day_rate: 1日最大損失率（デフォルト5%）
            max_loss_per_race_rate: 1レース最大損失率（デフォルト2%）
            max_consecutive_losses: 連敗上限（デフォルト3）
        """
        self.bankroll = bankroll
        self.max_loss_per_day = int(bankroll * max_loss_per_day_rate)
        self.max_loss_per_race = int(bankroll * max_loss_per_race_rate)
        self.max_consecutive_losses = max_consecutive_losses

        self.daily_loss = 0
        self.consecutive_losses = 0
        self.total_bets = 0
        self.total_wins = 0

    def can_bet(self, bet_amount: int) -> Tuple[bool, str]:
        """
        賭けが許可されるかチェック

        Returns:
            (許可, 理由)

        「めんどくせぇけど、全部チェックする」
        """
        # 1日の損失上限チェック
        if self.daily_loss >= self.max_loss_per_day:
            return False, f"1日の損失上限({self.max_loss_per_day:,}円)に達しました"

        # 1レースの賭け金上限チェック
        if bet_amount > self.max_loss_per_race:
            return False, f"1レース最大賭け金({self.max_loss_per_race:,}円)を超えています"

        # 連敗上限チェック
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"{self.max_consecutive_losses}連敗のため一時停止中"

        # 資金不足チェック
        if bet_amount > self.bankroll:
            return False, "資金不足"

        return True, "OK"

    def record_result(self, profit: int):
        """
        結果を記録

        Args:
            profit: 収支（正=利益、負=損失）

        「結果を記録して次に活かす。これが戦略家だ」
        """
        self.total_bets += 1

        if profit < 0:
            # 損失
            self.daily_loss += abs(profit)
            self.consecutive_losses += 1
        else:
            # 利益
            self.consecutive_losses = 0
            self.total_wins += 1

        # 資金更新
        self.bankroll += profit

    def get_risk_level(self, bet_amount: int) -> str:
        """
        リスクレベルを判定

        Returns:
            "low" / "medium" / "high"
        """
        bet_rate = bet_amount / self.bankroll if self.bankroll > 0 else 0

        if bet_rate < 0.01:  # 1%未満
            return "low"
        elif bet_rate < 0.03:  # 3%未満
            return "medium"
        else:
            return "high"

    def reset_daily(self):
        """
        1日の損失カウンターをリセット

        「新しい日、新しい戦略だ」
        """
        self.daily_loss = 0

    def get_status(self) -> Dict:
        """
        現在の状態を取得

        Returns:
            状態辞書
        """
        win_rate = (self.total_wins / self.total_bets * 100) if self.total_bets > 0 else 0

        return {
            'bankroll': self.bankroll,
            'daily_loss': self.daily_loss,
            'consecutive_losses': self.consecutive_losses,
            'total_bets': self.total_bets,
            'total_wins': self.total_wins,
            'win_rate': win_rate,
            'remaining_daily_budget': self.max_loss_per_day - self.daily_loss
        }


class BettingStrategist:
    """
    購入戦略エンジン - シカマル

    期待値計算結果をもとに、ケリー基準とリスク管理で最適な購入戦略を立案。

    「めんどくせぇな...でも戦略的にはこうだ」
    """

    def __init__(
        self,
        bankroll: int = 100000,
        min_ev_threshold: float = 1.10,
        kelly_fraction: float = 0.5,
        max_loss_per_day_rate: float = 0.05,
        max_loss_per_race_rate: float = 0.02,
        max_consecutive_losses: int = 3
    ):
        """
        Args:
            bankroll: 総資金
            min_ev_threshold: 最小期待値閾値（1.10 = 110%推奨）
            kelly_fraction: ケリー係数（0.5 = Half Kelly推奨）
            max_loss_per_day_rate: 1日最大損失率
            max_loss_per_race_rate: 1レース最大損失率
            max_consecutive_losses: 連敗上限
        """
        self.bankroll = bankroll
        self.min_ev_threshold = min_ev_threshold
        self.kelly_fraction = kelly_fraction

        self.risk_manager = RiskManager(
            bankroll=bankroll,
            max_loss_per_day_rate=max_loss_per_day_rate,
            max_loss_per_race_rate=max_loss_per_race_rate,
            max_consecutive_losses=max_consecutive_losses
        )

        self.kelly_calculator = KellyCriterion()

    def evaluate_bet(
        self,
        race_id: str,
        horse_name: str,
        prob: float,
        odds: float,
        expected_value: float,
        expected_value_rate: float,
        bet_type: str = "win"
    ) -> BettingRecommendation:
        """
        馬券を評価して購入推奨を生成

        Args:
            race_id: レースID
            horse_name: 馬名
            prob: 勝率予測（0.0~1.0）
            odds: オッズ
            expected_value: 期待値（円）
            expected_value_rate: 期待値率（1.0 = 100%）
            bet_type: 馬券種別

        Returns:
            購入推奨結果

        「めんどくせぇけど、全部計算するぞ」
        """
        should_bet = False
        bet_amount = 0
        reason = ""
        kelly_frac = 0.0

        # 1. 期待値チェック
        if expected_value_rate < self.min_ev_threshold:
            reason = f"期待値不足 ({expected_value_rate:.1%} < {self.min_ev_threshold:.1%})"
        else:
            # 2. ケリー基準で賭け金計算
            kelly_frac = self.kelly_calculator.fractional_kelly(
                prob=prob,
                odds=odds,
                fraction=self.kelly_fraction
            )
            bet_amount = int(self.risk_manager.bankroll * kelly_frac)

            # 最低賭け金（100円単位）
            bet_amount = max(100, (bet_amount // 100) * 100)

            # 3. リスク管理チェック
            can_bet, risk_reason = self.risk_manager.can_bet(bet_amount)

            if not can_bet:
                reason = risk_reason
            elif bet_amount <= 0:
                reason = "ケリー基準により賭け金ゼロ"
            else:
                should_bet = True
                risk_level = self.risk_manager.get_risk_level(bet_amount)
                reason = f"期待値{expected_value_rate:.1%}、Kelly {kelly_frac:.2%}、リスク{risk_level}"

        # リスクレベル判定
        risk_level = self.risk_manager.get_risk_level(bet_amount) if bet_amount > 0 else "low"

        return BettingRecommendation(
            race_id=race_id,
            horse_name=horse_name,
            bet_type=bet_type,
            should_bet=should_bet,
            bet_amount=bet_amount if should_bet else 0,
            expected_value=expected_value,
            expected_value_rate=expected_value_rate,
            kelly_fraction=kelly_frac,
            risk_level=risk_level,
            reason=reason
        )

    def generate_purchase_list(
        self,
        race_evaluations: List[Dict]
    ) -> List[BettingRecommendation]:
        """
        複数レースの評価結果から購入推奨リストを生成

        Args:
            race_evaluations: レース評価結果リスト
                [
                    {
                        'race_id': 'RACE001',
                        'horse_name': '馬A',
                        'prob': 0.25,
                        'odds': 5.0,
                        'expected_value': 25.0,
                        'expected_value_rate': 1.25,
                        'bet_type': 'win'
                    },
                    ...
                ]

        Returns:
            購入推奨リスト（期待値率の高い順）

        「戦略的に優先順位をつけるぞ」
        """
        recommendations = []

        for ev_result in race_evaluations:
            rec = self.evaluate_bet(
                race_id=ev_result['race_id'],
                horse_name=ev_result['horse_name'],
                prob=ev_result['prob'],
                odds=ev_result['odds'],
                expected_value=ev_result['expected_value'],
                expected_value_rate=ev_result['expected_value_rate'],
                bet_type=ev_result.get('bet_type', 'win')
            )
            recommendations.append(rec)

        # 期待値率の高い順にソート
        recommendations.sort(key=lambda x: x.expected_value_rate, reverse=True)

        return recommendations

    def record_result(self, profit: int):
        """
        結果を記録

        Args:
            profit: 収支（正=利益、負=損失）
        """
        self.risk_manager.record_result(profit)

    def reset_daily(self):
        """1日の損失カウンターをリセット"""
        self.risk_manager.reset_daily()

    def get_status(self) -> Dict:
        """現在の状態を取得"""
        return self.risk_manager.get_status()


# ========================================
# テストコード
# ========================================

def test_strategist():
    """
    シカマル（STRATEGIST）のテスト

    「めんどくせぇけど、テストは必要だ」
    """
    print("=" * 60)
    print("シカマル（STRATEGIST）テスト")
    print("=" * 60)
    print()

    # シカマル初期化
    strategist = BettingStrategist(
        bankroll=100000,
        min_ev_threshold=1.10,  # 期待値110%以上
        kelly_fraction=0.5       # Half Kelly
    )

    print(f"総資金: {strategist.bankroll:,}円")
    print(f"期待値閾値: {strategist.min_ev_threshold:.0%}")
    print(f"Kelly係数: {strategist.kelly_fraction:.0%}")
    print()

    # エバちゃんからの期待値計算結果（ダミー）
    race_evaluations = [
        {
            'race_id': '2026020101010101',
            'horse_name': 'ドウデュース',
            'prob': 0.30,
            'odds': 5.0,
            'expected_value': 50.0,
            'expected_value_rate': 1.50,
            'bet_type': 'win'
        },
        {
            'race_id': '2026020101010102',
            'horse_name': 'イクイノックス',
            'prob': 0.25,
            'odds': 6.0,
            'expected_value': 50.0,
            'expected_value_rate': 1.50,
            'bet_type': 'win'
        },
        {
            'race_id': '2026020101010103',
            'horse_name': 'リバティアイランド',
            'prob': 0.20,
            'odds': 4.5,
            'expected_value': -10.0,
            'expected_value_rate': 0.90,  # 期待値不足
            'bet_type': 'win'
        },
        {
            'race_id': '2026020101010104',
            'horse_name': 'ソングライン',
            'prob': 0.35,
            'odds': 4.0,
            'expected_value': 40.0,
            'expected_value_rate': 1.40,
            'bet_type': 'win'
        }
    ]

    # 購入推奨リスト生成
    print("=" * 60)
    print("購入推奨リスト（期待値率順）")
    print("=" * 60)
    print()

    recommendations = strategist.generate_purchase_list(race_evaluations)

    for i, rec in enumerate(recommendations, 1):
        print(f"[{i}] {rec.horse_name}")
        print(f"    推奨: {'YES' if rec.should_bet else 'NO'}")
        print(f"    賭け金: {rec.bet_amount:,}円")
        print(f"    期待値率: {rec.expected_value_rate:.1%}")
        print(f"    Kelly: {rec.kelly_fraction:.2%}")
        print(f"    リスク: {rec.risk_level}")
        print(f"    理由: {rec.reason}")
        print()

    # 推奨リストのみ抽出
    buy_list = [rec for rec in recommendations if rec.should_bet]

    print("=" * 60)
    print(f"購入推奨: {len(buy_list)}件")
    print("=" * 60)
    print()

    total_bet = sum(rec.bet_amount for rec in buy_list)
    print(f"合計賭け金: {total_bet:,}円")
    print()

    # 状態確認
    status = strategist.get_status()
    print("=" * 60)
    print("シカマルの状態")
    print("=" * 60)
    print(f"総資金: {status['bankroll']:,}円")
    print(f"今日の損失: {status['daily_loss']:,}円")
    print(f"連敗数: {status['consecutive_losses']}回")
    print(f"購入回数: {status['total_bets']}回")
    print(f"的中回数: {status['total_wins']}回")
    print()

    print("シカマル: 「めんどくせぇけど、戦略的にはこうだ。期待値の高い順に3件推奨する」")


if __name__ == '__main__':
    test_strategist()

# -*- coding: utf-8 -*-
"""
EVALUATOR - 期待値計算エンジン

予測確率とオッズから期待値を計算し、購入判断を行います。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum


class BetType(Enum):
    """馬券種別"""
    WIN = "win"              # 単勝
    PLACE = "place"          # 複勝
    QUINELLA = "quinella"    # 馬連
    EXACTA = "exacta"        # 馬単
    WIDE = "wide"            # ワイド
    TRIO = "trio"            # 三連複
    TRIFECTA = "trifecta"    # 三連単


@dataclass
class ExpectedValueResult:
    """期待値計算結果"""
    bet_type: str
    expected_value: float        # 期待値（円）
    expected_value_rate: float   # 期待値率（1.0 = 100%）
    is_positive: bool            # 期待値がプラスか
    recommended: bool            # 購入推奨か


class ExpectedValueCalculator:
    """
    期待値計算エンジン

    各種馬券の期待値を計算します。
    """

    def __init__(self, min_ev_threshold: float = 1.05):
        """
        初期化

        Args:
            min_ev_threshold: 最小期待値閾値（1.05 = 105%）
        """
        self.min_ev_threshold = min_ev_threshold

    def calculate_win(
        self,
        prob: float,
        odds: float,
        bet_amount: int = 100
    ) -> ExpectedValueResult:
        """
        単勝の期待値を計算

        Args:
            prob: 1着になる確率（0.0~1.0）
            odds: 単勝オッズ
            bet_amount: 賭け金（円）

        Returns:
            期待値計算結果
        """
        # 的中時の払戻
        return_if_win = odds * bet_amount

        # 期待値計算
        ev = (prob * return_if_win) - ((1 - prob) * bet_amount)

        # 期待値率
        ev_rate = 1 + (ev / bet_amount)

        return ExpectedValueResult(
            bet_type=BetType.WIN.value,
            expected_value=ev,
            expected_value_rate=ev_rate,
            is_positive=(ev > 0),
            recommended=(ev_rate >= self.min_ev_threshold)
        )

    def calculate_place(
        self,
        prob_top3: float,
        odds_place: float,
        bet_amount: int = 100
    ) -> ExpectedValueResult:
        """
        複勝の期待値を計算

        Args:
            prob_top3: 3着以内に入る確率（0.0~1.0）
            odds_place: 複勝オッズ（平均オッズを使用）
            bet_amount: 賭け金（円）

        Returns:
            期待値計算結果
        """
        # 的中時の払戻
        return_if_win = odds_place * bet_amount

        # 期待値計算
        ev = (prob_top3 * return_if_win) - ((1 - prob_top3) * bet_amount)

        # 期待値率
        ev_rate = 1 + (ev / bet_amount)

        return ExpectedValueResult(
            bet_type=BetType.PLACE.value,
            expected_value=ev,
            expected_value_rate=ev_rate,
            is_positive=(ev > 0),
            recommended=(ev_rate >= self.min_ev_threshold)
        )

    def calculate_quinella(
        self,
        prob_horse1_top2: float,
        prob_horse2_top2: float,
        odds_quinella: float,
        bet_amount: int = 100,
        independence_assumption: bool = True
    ) -> ExpectedValueResult:
        """
        馬連の期待値を計算

        Args:
            prob_horse1_top2: 馬1が2着以内に入る確率
            prob_horse2_top2: 馬2が2着以内に入る確率
            odds_quinella: 馬連オッズ
            bet_amount: 賭け金（円）
            independence_assumption: 独立性を仮定するか

        Returns:
            期待値計算結果
        """
        if independence_assumption:
            # 簡易版: 独立性を仮定
            # 実際には相関があるため過小評価の可能性
            prob_both_top2 = prob_horse1_top2 * prob_horse2_top2
        else:
            # より正確な計算（実装は複雑）
            # TODO: 相関を考慮した確率計算
            prob_both_top2 = prob_horse1_top2 * prob_horse2_top2 * 1.2  # 補正係数

        # 的中時の払戻
        return_if_win = odds_quinella * bet_amount

        # 期待値計算
        ev = (prob_both_top2 * return_if_win) - ((1 - prob_both_top2) * bet_amount)

        # 期待値率
        ev_rate = 1 + (ev / bet_amount)

        return ExpectedValueResult(
            bet_type=BetType.QUINELLA.value,
            expected_value=ev,
            expected_value_rate=ev_rate,
            is_positive=(ev > 0),
            recommended=(ev_rate >= self.min_ev_threshold)
        )

    def calculate_exacta(
        self,
        prob_horse1_win: float,
        prob_horse2_place_given_horse1_win: float,
        odds_exacta: float,
        bet_amount: int = 100
    ) -> ExpectedValueResult:
        """
        馬単の期待値を計算

        Args:
            prob_horse1_win: 馬1が1着になる確率
            prob_horse2_place_given_horse1_win: 馬1が1着の条件下で馬2が2着になる確率
            odds_exacta: 馬単オッズ
            bet_amount: 賭け金（円）

        Returns:
            期待値計算結果
        """
        # 条件付き確率
        prob_exacta = prob_horse1_win * prob_horse2_place_given_horse1_win

        # 的中時の払戻
        return_if_win = odds_exacta * bet_amount

        # 期待値計算
        ev = (prob_exacta * return_if_win) - ((1 - prob_exacta) * bet_amount)

        # 期待値率
        ev_rate = 1 + (ev / bet_amount)

        return ExpectedValueResult(
            bet_type=BetType.EXACTA.value,
            expected_value=ev,
            expected_value_rate=ev_rate,
            is_positive=(ev > 0),
            recommended=(ev_rate >= self.min_ev_threshold)
        )

    def evaluate_race(
        self,
        predictions: Dict[str, Dict],
        odds: Dict[str, Dict],
        bet_types: List[str] = None
    ) -> List[Dict]:
        """
        レース全体の期待値を評価

        Args:
            predictions: {umaban: {'prob_win': float, 'prob_top3': float}}
            odds: {umaban: {'win_odds': float, 'place_odds_min': float, ...}}
            bet_types: 評価する馬券種別のリスト（デフォルト: ["win", "place"]）

        Returns:
            期待値評価結果のリスト
        """
        if bet_types is None:
            bet_types = ["win", "place"]

        results = []

        for umaban, pred in predictions.items():
            odds_data = odds.get(umaban)
            if not odds_data:
                continue

            # 単勝の評価
            if "win" in bet_types and "win_odds" in odds_data:
                ev_win = self.calculate_win(
                    prob=pred.get("prob_win", 0),
                    odds=odds_data["win_odds"]
                )

                results.append({
                    "umaban": umaban,
                    "bet_type": "win",
                    "prob": pred.get("prob_win", 0),
                    "odds": odds_data["win_odds"],
                    "expected_value": ev_win.expected_value,
                    "expected_value_rate": ev_win.expected_value_rate,
                    "recommended": ev_win.recommended
                })

            # 複勝の評価
            if "place" in bet_types and "place_odds_min" in odds_data:
                # 複勝オッズの平均を使用
                place_odds_avg = (
                    odds_data["place_odds_min"] + odds_data.get("place_odds_max", odds_data["place_odds_min"])
                ) / 2

                ev_place = self.calculate_place(
                    prob_top3=pred.get("prob_top3", 0),
                    odds_place=place_odds_avg
                )

                results.append({
                    "umaban": umaban,
                    "bet_type": "place",
                    "prob": pred.get("prob_top3", 0),
                    "odds": place_odds_avg,
                    "expected_value": ev_place.expected_value,
                    "expected_value_rate": ev_place.expected_value_rate,
                    "recommended": ev_place.recommended
                })

        return results

    def get_best_bets(
        self,
        results: List[Dict],
        max_bets: int = 5,
        sort_by: str = "expected_value_rate"
    ) -> List[Dict]:
        """
        最良の購入候補を取得

        Args:
            results: evaluate_race()の結果
            max_bets: 最大購入数
            sort_by: ソート基準（"expected_value_rate" or "expected_value"）

        Returns:
            購入推奨のリスト（期待値が高い順）
        """
        # 推奨フラグが立っているもののみ
        recommended = [r for r in results if r["recommended"]]

        # ソート
        sorted_results = sorted(
            recommended,
            key=lambda x: x[sort_by],
            reverse=True
        )

        return sorted_results[:max_bets]


class RaceEvaluator:
    """
    レース評価統合クラス

    予測とオッズを受け取り、購入推奨リストを生成します。
    """

    def __init__(self, min_ev_threshold: float = 1.05):
        """
        初期化

        Args:
            min_ev_threshold: 最小期待値閾値
        """
        self.calculator = ExpectedValueCalculator(min_ev_threshold)

    def evaluate_and_recommend(
        self,
        race_id: str,
        predictions: Dict[str, Dict],
        odds: Dict[str, Dict],
        max_bets: int = 5
    ) -> Dict:
        """
        レースを評価して購入推奨を生成

        Args:
            race_id: レースID
            predictions: 予測結果
            odds: オッズデータ
            max_bets: 最大購入数

        Returns:
            {
                'race_id': str,
                'all_evaluations': List[Dict],
                'recommendations': List[Dict],
                'summary': Dict
            }
        """
        # 期待値計算
        all_evaluations = self.calculator.evaluate_race(predictions, odds)

        # 購入推奨を取得
        recommendations = self.calculator.get_best_bets(all_evaluations, max_bets)

        # サマリー
        summary = {
            'total_horses': len(predictions),
            'total_evaluations': len(all_evaluations),
            'positive_ev_count': len([e for e in all_evaluations if e['expected_value'] > 0]),
            'recommended_count': len(recommendations),
            'avg_ev_rate': sum(e['expected_value_rate'] for e in all_evaluations) / len(all_evaluations) if all_evaluations else 0
        }

        return {
            'race_id': race_id,
            'all_evaluations': all_evaluations,
            'recommendations': recommendations,
            'summary': summary
        }


# ===== ユニットテスト（ダミーデータ） =====

def test_evaluator():
    """EVALUATORの動作テスト"""
    print("=== EVALUATOR テスト ===\n")

    # ダミーデータ
    predictions = {
        "01": {"prob_win": 0.25, "prob_top3": 0.55},
        "03": {"prob_win": 0.18, "prob_top3": 0.45},
        "05": {"prob_win": 0.30, "prob_top3": 0.60},
        "07": {"prob_win": 0.12, "prob_top3": 0.35},
    }

    dummy_odds = {
        "01": {"win_odds": 5.0, "place_odds_min": 1.8, "place_odds_max": 2.2},
        "03": {"win_odds": 7.5, "place_odds_min": 2.1, "place_odds_max": 2.8},
        "05": {"win_odds": 3.5, "place_odds_min": 1.5, "place_odds_max": 1.9},
        "07": {"win_odds": 12.0, "place_odds_min": 3.2, "place_odds_max": 4.5},
    }

    # 評価実行
    evaluator = RaceEvaluator(min_ev_threshold=1.05)
    result = evaluator.evaluate_and_recommend(
        race_id="TEST_RACE_001",
        predictions=predictions,
        odds=dummy_odds,
        max_bets=3
    )

    # 結果表示
    print(f"レースID: {result['race_id']}")
    print(f"評価対象: {result['summary']['total_evaluations']}件")
    print(f"期待値プラス: {result['summary']['positive_ev_count']}件")
    print(f"購入推奨: {result['summary']['recommended_count']}件\n")

    print("=== 全評価結果 ===")
    for ev in result['all_evaluations']:
        print(f"{ev['umaban']}番 ({ev['bet_type']}): "
              f"期待値率 {ev['expected_value_rate']:.1%}, "
              f"推奨: {'YES' if ev['recommended'] else 'NO'}")

    print("\n=== 購入推奨リスト ===")
    for i, rec in enumerate(result['recommendations'], 1):
        print(f"{i}. {rec['umaban']}番 {rec['bet_type']}")
        print(f"   予測確率: {rec['prob']:.1%}")
        print(f"   オッズ: {rec['odds']:.1f}倍")
        print(f"   期待値率: {rec['expected_value_rate']:.1%}")
        print()


if __name__ == "__main__":
    test_evaluator()

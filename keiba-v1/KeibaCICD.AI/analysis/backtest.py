"""
ANALYST (ひなた) - バックテスト・結果分析システム

分析の達人ひなたが、過去データでシミュレーションし、戦略の有効性を検証。

「あの...データを見ると、このパターンが見えます」
"""

import json
import csv
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum


@dataclass
class BacktestResult:
    """バックテスト結果"""
    race_id: str
    race_date: str
    horse_name: str
    bet_type: str
    bet_amount: int
    odds: float
    expected_value_rate: float
    kelly_fraction: float
    result_rank: int
    is_hit: bool
    payout: int
    profit: int
    bankroll_after: int


@dataclass
class PerformanceMetrics:
    """パフォーマンス指標"""
    total_races: int
    total_bets: int
    total_invested: int
    total_payout: int
    total_profit: int

    hit_count: int
    hit_rate: float
    recovery_rate: float
    roi: float

    win_streak: int
    loss_streak: int
    max_drawdown: int
    max_drawdown_rate: float

    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None


@dataclass
class StrategyReport:
    """戦略レポート"""
    strategy_name: str
    date_range: str
    initial_bankroll: int
    final_bankroll: int
    metrics: PerformanceMetrics
    monthly_breakdown: List[Dict]
    recommendations: List[str]
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class BacktestEngine:
    """
    バックテストエンジン

    過去データでシミュレーションを実行
    """

    def __init__(
        self,
        initial_bankroll: int = 100000,
        min_ev_threshold: float = 1.10,
        kelly_fraction: float = 0.5
    ):
        """
        Args:
            initial_bankroll: 初期資金
            min_ev_threshold: 最小期待値閾値
            kelly_fraction: ケリー係数
        """
        self.initial_bankroll = initial_bankroll
        self.min_ev_threshold = min_ev_threshold
        self.kelly_fraction = kelly_fraction

        self.bankroll = initial_bankroll
        self.results: List[BacktestResult] = []

    def calculate_kelly(self, prob: float, odds: float) -> float:
        """
        ケリー基準で賭け割合を計算

        Args:
            prob: 勝率予測
            odds: オッズ

        Returns:
            賭け割合
        """
        if prob <= 0 or odds <= 1.0:
            return 0.0

        b = odds - 1.0
        p = prob
        q = 1.0 - p

        f_star = (b * p - q) / b
        return max(0.0, f_star * self.kelly_fraction)

    def run_race(
        self,
        race_id: str,
        race_date: str,
        horse_name: str,
        prob: float,
        odds: float,
        result_rank: int,
        bet_type: str = "win"
    ) -> Optional[BacktestResult]:
        """
        1レースのシミュレーション

        Args:
            race_id: レースID
            race_date: レース日付
            horse_name: 馬名
            prob: 勝率予測
            odds: オッズ
            result_rank: 実際の着順
            bet_type: 馬券種別

        Returns:
            バックテスト結果
        """
        # 期待値計算
        return_if_win = odds * 100
        ev = (prob * return_if_win) - ((1 - prob) * 100)
        ev_rate = 1 + (ev / 100)

        # 期待値閾値チェック
        if ev_rate < self.min_ev_threshold:
            return None

        # ケリー基準で賭け金計算
        kelly_frac = self.calculate_kelly(prob, odds)
        bet_amount = int(self.bankroll * kelly_frac)

        # 最低賭け金
        bet_amount = max(100, (bet_amount // 100) * 100)

        # 資金不足チェック
        if bet_amount > self.bankroll:
            return None

        # 結果判定
        is_hit = (result_rank == 1) if bet_type == "win" else (result_rank <= 3)
        payout = int(odds * bet_amount) if is_hit else 0
        profit = payout - bet_amount

        # 資金更新
        self.bankroll += profit

        result = BacktestResult(
            race_id=race_id,
            race_date=race_date,
            horse_name=horse_name,
            bet_type=bet_type,
            bet_amount=bet_amount,
            odds=odds,
            expected_value_rate=ev_rate,
            kelly_fraction=kelly_frac,
            result_rank=result_rank,
            is_hit=is_hit,
            payout=payout,
            profit=profit,
            bankroll_after=self.bankroll
        )

        self.results.append(result)
        return result

    def get_results(self) -> List[BacktestResult]:
        """バックテスト結果を取得"""
        return self.results

    def reset(self):
        """バックテストをリセット"""
        self.bankroll = self.initial_bankroll
        self.results = []


class PerformanceAnalyzer:
    """
    パフォーマンス分析 - ひなた

    「あの...データを見ると、パターンが見えます」
    """

    @staticmethod
    def analyze(
        results: List[BacktestResult],
        initial_bankroll: int
    ) -> PerformanceMetrics:
        """
        パフォーマンスを分析

        Args:
            results: バックテスト結果
            initial_bankroll: 初期資金

        Returns:
            パフォーマンス指標

        「分析を開始します...」
        """
        if not results:
            return PerformanceMetrics(
                total_races=0,
                total_bets=0,
                total_invested=0,
                total_payout=0,
                total_profit=0,
                hit_count=0,
                hit_rate=0.0,
                recovery_rate=0.0,
                roi=0.0,
                win_streak=0,
                loss_streak=0,
                max_drawdown=0,
                max_drawdown_rate=0.0
            )

        total_bets = len(results)
        total_invested = sum(r.bet_amount for r in results)
        total_payout = sum(r.payout for r in results)
        total_profit = total_payout - total_invested

        hit_count = sum(1 for r in results if r.is_hit)
        hit_rate = (hit_count / total_bets * 100) if total_bets > 0 else 0.0
        recovery_rate = (total_payout / total_invested * 100) if total_invested > 0 else 0.0

        final_bankroll = results[-1].bankroll_after
        roi = ((final_bankroll - initial_bankroll) / initial_bankroll * 100) if initial_bankroll > 0 else 0.0

        # 連勝・連敗の計算
        current_streak = 0
        max_win_streak = 0
        max_loss_streak = 0

        for result in results:
            if result.is_hit:
                if current_streak >= 0:
                    current_streak += 1
                else:
                    current_streak = 1
                max_win_streak = max(max_win_streak, current_streak)
            else:
                if current_streak <= 0:
                    current_streak -= 1
                else:
                    current_streak = -1
                max_loss_streak = max(max_loss_streak, abs(current_streak))

        # 最大ドローダウン計算
        peak_bankroll = initial_bankroll
        max_drawdown = 0
        max_drawdown_rate = 0.0

        for result in results:
            peak_bankroll = max(peak_bankroll, result.bankroll_after)
            drawdown = peak_bankroll - result.bankroll_after
            drawdown_rate = (drawdown / peak_bankroll * 100) if peak_bankroll > 0 else 0.0

            max_drawdown = max(max_drawdown, drawdown)
            max_drawdown_rate = max(max_drawdown_rate, drawdown_rate)

        # Profit Factor（総利益 / 総損失）
        total_wins = sum(r.profit for r in results if r.profit > 0)
        total_losses = abs(sum(r.profit for r in results if r.profit < 0))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else None

        return PerformanceMetrics(
            total_races=total_bets,
            total_bets=total_bets,
            total_invested=total_invested,
            total_payout=total_payout,
            total_profit=total_profit,
            hit_count=hit_count,
            hit_rate=hit_rate,
            recovery_rate=recovery_rate,
            roi=roi,
            win_streak=max_win_streak,
            loss_streak=max_loss_streak,
            max_drawdown=max_drawdown,
            max_drawdown_rate=max_drawdown_rate,
            profit_factor=profit_factor
        )

    @staticmethod
    def generate_recommendations(metrics: PerformanceMetrics) -> List[str]:
        """
        改善提案を生成

        Args:
            metrics: パフォーマンス指標

        Returns:
            提案リスト

        「あの...改善点を見つけました」
        """
        recommendations = []

        # 回収率チェック
        if metrics.recovery_rate < 100:
            recommendations.append("回収率が100%未満です。期待値閾値を上げることを検討してください")
        elif metrics.recovery_rate < 110:
            recommendations.append("回収率が110%未満です。より高い期待値の馬券に絞ることを推奨します")

        # 的中率チェック
        if metrics.hit_rate < 20:
            recommendations.append("的中率が低すぎます。予測モデルの見直しが必要です")
        elif metrics.hit_rate > 50:
            recommendations.append("的中率が高いです。オッズが低い可能性があります。期待値を確認してください")

        # ドローダウンチェック
        if metrics.max_drawdown_rate > 30:
            recommendations.append(f"最大ドローダウン{metrics.max_drawdown_rate:.1f}%と大きいです。Kelly係数を下げることを推奨します")
        elif metrics.max_drawdown_rate > 20:
            recommendations.append(f"ドローダウン{metrics.max_drawdown_rate:.1f}%です。リスク管理の強化を検討してください")

        # 連敗チェック
        if metrics.loss_streak > 5:
            recommendations.append(f"最大{metrics.loss_streak}連敗しています。連敗時の一時停止ルールを検討してください")

        # Profit Factorチェック
        if metrics.profit_factor and metrics.profit_factor < 1.5:
            recommendations.append(f"Profit Factor {metrics.profit_factor:.2f}と低いです。損失を減らす工夫が必要です")

        # ROIチェック
        if metrics.roi < 0:
            recommendations.append("ROIがマイナスです。戦略全体の見直しが必要です")
        elif metrics.roi > 50:
            recommendations.append("ROIが非常に良好です。この戦略を継続してください")

        if not recommendations:
            recommendations.append("パフォーマンスは良好です。現在の戦略を継続してください")

        return recommendations

    @staticmethod
    def create_report(
        strategy_name: str,
        date_range: str,
        initial_bankroll: int,
        results: List[BacktestResult]
    ) -> StrategyReport:
        """
        戦略レポートを作成

        Args:
            strategy_name: 戦略名
            date_range: 期間
            initial_bankroll: 初期資金
            results: バックテスト結果

        Returns:
            戦略レポート

        「レポートを作成します...」
        """
        metrics = PerformanceAnalyzer.analyze(results, initial_bankroll)
        recommendations = PerformanceAnalyzer.generate_recommendations(metrics)

        # 月次集計（簡易版）
        monthly_breakdown = []

        final_bankroll = results[-1].bankroll_after if results else initial_bankroll

        return StrategyReport(
            strategy_name=strategy_name,
            date_range=date_range,
            initial_bankroll=initial_bankroll,
            final_bankroll=final_bankroll,
            metrics=metrics,
            monthly_breakdown=monthly_breakdown,
            recommendations=recommendations
        )

    @staticmethod
    def save_report(report: StrategyReport, output_file: Path):
        """
        レポートを保存

        Args:
            report: 戦略レポート
            output_file: 出力ファイルパス
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            # StrategyReport を辞書に変換
            report_dict = asdict(report)
            # PerformanceMetrics も辞書として含まれる
            json.dump(report_dict, f, ensure_ascii=False, indent=2)


# ========================================
# テストコード
# ========================================

def test_backtest():
    """
    ひなた（ANALYST）のバックテストテスト

    「あの...テストを実行します」
    """
    print("=" * 60)
    print("ひなた（ANALYST）バックテストテスト")
    print("=" * 60)
    print()

    # バックテストエンジン初期化
    engine = BacktestEngine(
        initial_bankroll=100000,
        min_ev_threshold=1.10,
        kelly_fraction=0.25  # Quarter Kelly
    )

    print(f"初期資金: {engine.initial_bankroll:,}円")
    print(f"期待値閾値: {engine.min_ev_threshold:.0%}")
    print(f"Kelly係数: {engine.kelly_fraction:.0%}")
    print()

    # ダミーデータでシミュレーション
    print("=" * 60)
    print("シミュレーション実行")
    print("=" * 60)
    print()

    races = [
        # (race_id, date, horse, prob, odds, result_rank)
        ("R001", "20260101", "馬A", 0.30, 5.0, 1),   # 的中
        ("R002", "20260101", "馬B", 0.25, 6.0, 3),   # 不的中
        ("R003", "20260101", "馬C", 0.35, 4.0, 2),   # 不的中
        ("R004", "20260108", "馬D", 0.28, 5.5, 1),   # 的中
        ("R005", "20260108", "馬E", 0.22, 7.0, 5),   # 不的中
        ("R006", "20260115", "馬F", 0.32, 4.5, 1),   # 的中
        ("R007", "20260115", "馬G", 0.20, 8.0, 2),   # 不的中
        ("R008", "20260122", "馬H", 0.40, 3.5, 1),   # 的中
        ("R009", "20260122", "馬I", 0.15, 10.0, 4),  # 不的中
        ("R010", "20260129", "馬J", 0.33, 4.2, 1),   # 的中
    ]

    bet_count = 0
    for race in races:
        result = engine.run_race(*race)
        if result:
            bet_count += 1
            status = "的中" if result.is_hit else "不的中"
            print(f"{result.horse_name}: {status} - 収支{result.profit:+,}円 (資金残{result.bankroll_after:,}円)")

    print()
    print(f"購入件数: {bet_count}件")
    print()

    # パフォーマンス分析
    print("=" * 60)
    print("パフォーマンス分析（ひなた）")
    print("=" * 60)
    print()

    print("ひなた: 「あの...分析を開始します」")
    print()

    results = engine.get_results()
    metrics = PerformanceAnalyzer.analyze(results, engine.initial_bankroll)

    print(f"総レース数: {metrics.total_races}回")
    print(f"投資額: {metrics.total_invested:,}円")
    print(f"払戻額: {metrics.total_payout:,}円")
    print(f"収支: {metrics.total_profit:+,}円")
    print(f"的中率: {metrics.hit_rate:.1f}%")
    print(f"回収率: {metrics.recovery_rate:.1f}%")
    print(f"ROI: {metrics.roi:+.1f}%")
    print(f"最大連勝: {metrics.win_streak}回")
    print(f"最大連敗: {metrics.loss_streak}回")
    print(f"最大ドローダウン: {metrics.max_drawdown:,}円 ({metrics.max_drawdown_rate:.1f}%)")
    if metrics.profit_factor:
        print(f"Profit Factor: {metrics.profit_factor:.2f}")
    print()

    # 改善提案
    print("=" * 60)
    print("改善提案（ひなた）")
    print("=" * 60)
    print()

    recommendations = PerformanceAnalyzer.generate_recommendations(metrics)

    print("ひなた: 「あの...改善点を見つけました」")
    print()

    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")
    print()

    # レポート作成
    report = PerformanceAnalyzer.create_report(
        strategy_name="Quarter Kelly (EV >= 110%)",
        date_range="2026-01-01 ~ 2026-01-29",
        initial_bankroll=engine.initial_bankroll,
        results=results
    )

    # レポート保存
    output_file = Path("logs/backtest/report_test.json")
    PerformanceAnalyzer.save_report(report, output_file)

    print("ひなた: 「レポートを保存しました」")
    print(f"保存先: {output_file}")
    print()

    print("ひなた: 「分析が完了しました。このパターンが見えます」")


if __name__ == '__main__':
    test_backtest()

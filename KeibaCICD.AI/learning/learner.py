"""
LEARNER (ナルト) - 継続的改善システム

成長し続けるナルトが、失敗から学び、システムを改善し続ける。

「だってばよ！次は絶対勝つ！」
"""

import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum


class ImprovementType(Enum):
    """改善タイプ"""
    PARAMETER = "parameter"          # パラメータ調整
    STRATEGY = "strategy"            # 戦略変更
    MODEL = "model"                  # モデル改善
    DATA = "data"                    # データ拡充
    RISK = "risk"                    # リスク管理


@dataclass
class ImprovementProposal:
    """改善提案"""
    proposal_id: str
    improvement_type: str  # ImprovementType
    title: str
    description: str
    current_value: Optional[str] = None
    proposed_value: Optional[str] = None
    expected_impact: str = ""
    priority: str = "medium"  # "low" / "medium" / "high"
    status: str = "pending"   # "pending" / "approved" / "rejected" / "implemented"
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class LearningReport:
    """学習レポート"""
    report_id: str
    date_range: str
    total_improvements: int
    high_priority: int
    medium_priority: int
    low_priority: int
    proposals: List[ImprovementProposal]
    summary: str
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class PerformanceMonitor:
    """
    パフォーマンス監視

    「今の状態を確認するってばよ！」
    """

    @staticmethod
    def detect_issues(metrics: Dict) -> List[str]:
        """
        パフォーマンス問題を検出

        Args:
            metrics: パフォーマンス指標

        Returns:
            問題リスト

        「問題を見つけたってばよ！」
        """
        issues = []

        # 回収率チェック
        recovery_rate = metrics.get('recovery_rate', 0)
        if recovery_rate < 100:
            issues.append("回収率が100%未満（赤字状態）")
        elif recovery_rate < 110:
            issues.append("回収率が110%未満（目標未達成）")

        # 的中率チェック
        hit_rate = metrics.get('hit_rate', 0)
        if hit_rate < 10:
            issues.append("的中率が極端に低い（10%未満）")
        elif hit_rate > 70:
            issues.append("的中率が高すぎる（オッズが低い可能性）")

        # ROIチェック
        roi = metrics.get('roi', 0)
        if roi < -10:
            issues.append("ROIが大幅マイナス（-10%以下）")

        # ドローダウンチェック
        max_drawdown_rate = metrics.get('max_drawdown_rate', 0)
        if max_drawdown_rate > 30:
            issues.append("最大ドローダウンが30%超（リスク過大）")

        # 連敗チェック
        loss_streak = metrics.get('loss_streak', 0)
        if loss_streak > 5:
            issues.append(f"{loss_streak}連敗中（戦略見直し必要）")

        # Profit Factorチェック
        profit_factor = metrics.get('profit_factor')
        if profit_factor and profit_factor < 1.0:
            issues.append("Profit Factorが1.0未満（損失＞利益）")

        return issues

    @staticmethod
    def identify_strengths(metrics: Dict) -> List[str]:
        """
        強みを特定

        Args:
            metrics: パフォーマンス指標

        Returns:
            強みリスト

        「強みも見つけるってばよ！」
        """
        strengths = []

        # 回収率
        recovery_rate = metrics.get('recovery_rate', 0)
        if recovery_rate >= 120:
            strengths.append(f"回収率が優秀（{recovery_rate:.1f}%）")

        # ROI
        roi = metrics.get('roi', 0)
        if roi >= 30:
            strengths.append(f"ROIが優秀（{roi:+.1f}%）")

        # Profit Factor
        profit_factor = metrics.get('profit_factor')
        if profit_factor and profit_factor >= 2.0:
            strengths.append(f"Profit Factorが優秀（{profit_factor:.2f}）")

        # ドローダウン
        max_drawdown_rate = metrics.get('max_drawdown_rate', 100)
        if max_drawdown_rate < 10:
            strengths.append(f"ドローダウンが小さい（{max_drawdown_rate:.1f}%）")

        return strengths


class ParameterOptimizer:
    """
    パラメータ最適化提案

    「パラメータを調整して強くなるってばよ！」
    """

    @staticmethod
    def suggest_kelly_adjustment(metrics: Dict) -> Optional[ImprovementProposal]:
        """
        Kelly係数の調整提案

        Args:
            metrics: パフォーマンス指標

        Returns:
            改善提案
        """
        max_drawdown_rate = metrics.get('max_drawdown_rate', 0)
        current_kelly = metrics.get('current_kelly_fraction', 0.5)

        if max_drawdown_rate > 20:
            # ドローダウンが大きい → Kelly係数を下げる
            proposed_kelly = max(0.25, current_kelly - 0.25)
            return ImprovementProposal(
                proposal_id=f"param_kelly_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                improvement_type=ImprovementType.PARAMETER.value,
                title="Kelly係数の引き下げ",
                description=f"最大ドローダウン{max_drawdown_rate:.1f}%と大きいため、Kelly係数を引き下げてリスクを抑える",
                current_value=f"Kelly係数: {current_kelly:.2f}",
                proposed_value=f"Kelly係数: {proposed_kelly:.2f}",
                expected_impact="ドローダウン縮小、リスク低減",
                priority="high"
            )
        elif max_drawdown_rate < 5 and metrics.get('roi', 0) > 20:
            # ドローダウンが小さく、ROIも良好 → Kelly係数を上げてもOK
            proposed_kelly = min(1.0, current_kelly + 0.25)
            return ImprovementProposal(
                proposal_id=f"param_kelly_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                improvement_type=ImprovementType.PARAMETER.value,
                title="Kelly係数の引き上げ",
                description=f"ドローダウン{max_drawdown_rate:.1f}%と小さく、ROIも良好なため、Kelly係数を上げて利益最大化",
                current_value=f"Kelly係数: {current_kelly:.2f}",
                proposed_value=f"Kelly係数: {proposed_kelly:.2f}",
                expected_impact="利益拡大、リターン向上",
                priority="medium"
            )

        return None

    @staticmethod
    def suggest_ev_threshold_adjustment(metrics: Dict) -> Optional[ImprovementProposal]:
        """
        期待値閾値の調整提案

        Args:
            metrics: パフォーマンス指標

        Returns:
            改善提案
        """
        hit_rate = metrics.get('hit_rate', 0)
        recovery_rate = metrics.get('recovery_rate', 0)
        current_threshold = metrics.get('current_ev_threshold', 1.10)

        if recovery_rate < 100:
            # 回収率が100%未満 → 閾値を上げる
            proposed_threshold = min(1.30, current_threshold + 0.05)
            return ImprovementProposal(
                proposal_id=f"param_ev_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                improvement_type=ImprovementType.PARAMETER.value,
                title="期待値閾値の引き上げ",
                description=f"回収率{recovery_rate:.1f}%と低いため、より高い期待値の馬券に絞る",
                current_value=f"期待値閾値: {current_threshold:.0%}",
                proposed_value=f"期待値閾値: {proposed_threshold:.0%}",
                expected_impact="回収率向上、購入件数減少",
                priority="high"
            )
        elif recovery_rate > 130 and hit_rate < 30:
            # 回収率が高く、的中率が低い → 閾値を下げてもOK
            proposed_threshold = max(1.05, current_threshold - 0.05)
            return ImprovementProposal(
                proposal_id=f"param_ev_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                improvement_type=ImprovementType.PARAMETER.value,
                title="期待値閾値の引き下げ",
                description=f"回収率{recovery_rate:.1f}%と高く余裕があるため、購入機会を増やす",
                current_value=f"期待値閾値: {current_threshold:.0%}",
                proposed_value=f"期待値閾値: {proposed_threshold:.0%}",
                expected_impact="購入機会増加、リスク分散",
                priority="low"
            )

        return None


class ImprovementEngine:
    """
    改善エンジン - ナルト

    ひなたの分析結果から改善提案を生成

    「失敗から学んで、もっと強くなるってばよ！」
    """

    def __init__(self, output_dir: Path = None):
        """
        Args:
            output_dir: 出力ディレクトリ
        """
        if output_dir is None:
            output_dir = Path("logs/improvements")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_proposals(
        self,
        metrics: Dict,
        context: Dict = None
    ) -> List[ImprovementProposal]:
        """
        改善提案を生成

        Args:
            metrics: パフォーマンス指標
            context: 追加コンテキスト

        Returns:
            改善提案リスト

        「改善案を考えるってばよ！」
        """
        if context is None:
            context = {}

        proposals = []

        # 1. 問題検出
        issues = PerformanceMonitor.detect_issues(metrics)

        # 2. Kelly係数の調整提案
        kelly_proposal = ParameterOptimizer.suggest_kelly_adjustment(metrics)
        if kelly_proposal:
            proposals.append(kelly_proposal)

        # 3. 期待値閾値の調整提案
        ev_proposal = ParameterOptimizer.suggest_ev_threshold_adjustment(metrics)
        if ev_proposal:
            proposals.append(ev_proposal)

        # 4. 一般的な改善提案
        if "回収率が100%未満" in issues:
            proposals.append(ImprovementProposal(
                proposal_id=f"strategy_general_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                improvement_type=ImprovementType.STRATEGY.value,
                title="戦略全体の見直し",
                description="回収率が100%未満のため、予測モデル、期待値計算、リスク管理を含めた戦略全体の見直しが必要",
                expected_impact="回収率の改善",
                priority="high"
            ))

        if "的中率が極端に低い" in issues:
            proposals.append(ImprovementProposal(
                proposal_id=f"model_improve_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                improvement_type=ImprovementType.MODEL.value,
                title="予測モデルの改善",
                description="的中率が極端に低いため、予測モデルの精度向上が必要。特徴量追加、ハイパーパラメータ調整、再学習を検討",
                expected_impact="的中率向上、予測精度改善",
                priority="high"
            ))

        if "連敗中" in str(issues):
            proposals.append(ImprovementProposal(
                proposal_id=f"risk_stop_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                improvement_type=ImprovementType.RISK.value,
                title="連敗時の一時停止ルール強化",
                description="連敗が続いているため、一時停止ルールを見直し、損失拡大を防ぐ",
                expected_impact="損失抑制、リスク管理強化",
                priority="high"
            ))

        return proposals

    def create_report(
        self,
        proposals: List[ImprovementProposal],
        date_range: str,
        summary: str = ""
    ) -> LearningReport:
        """
        学習レポートを作成

        Args:
            proposals: 改善提案リスト
            date_range: 対象期間
            summary: サマリー

        Returns:
            学習レポート

        「レポートを作るってばよ！」
        """
        # 優先度別集計
        high_priority = sum(1 for p in proposals if p.priority == "high")
        medium_priority = sum(1 for p in proposals if p.priority == "medium")
        low_priority = sum(1 for p in proposals if p.priority == "low")

        report_id = f"learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return LearningReport(
            report_id=report_id,
            date_range=date_range,
            total_improvements=len(proposals),
            high_priority=high_priority,
            medium_priority=medium_priority,
            low_priority=low_priority,
            proposals=proposals,
            summary=summary
        )

    def save_report(self, report: LearningReport):
        """
        レポートを保存

        Args:
            report: 学習レポート
        """
        output_file = self.output_dir / f"{report.report_id}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            # LearningReport を辞書に変換
            report_dict = asdict(report)
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        print(f"ナルト: 「レポート保存したってばよ！ → {output_file}」")


# ========================================
# テストコード
# ========================================

def test_learner():
    """
    ナルト（LEARNER）のテスト

    「テストするってばよ！」
    """
    print("=" * 60)
    print("ナルト（LEARNER）テスト")
    print("=" * 60)
    print()

    # ナルト初期化
    learner = ImprovementEngine(output_dir=Path("logs/improvements_test"))

    print("ナルト: 「俺が改善提案するってばよ！」")
    print()

    # ひなたからのパフォーマンス指標（ダミー）
    metrics = {
        'total_races': 10,
        'total_bets': 10,
        'total_invested': 32500,
        'total_payout': 83470,
        'total_profit': 50970,
        'hit_count': 5,
        'hit_rate': 50.0,
        'recovery_rate': 256.8,
        'roi': 51.0,
        'win_streak': 1,
        'loss_streak': 2,
        'max_drawdown': 6400,
        'max_drawdown_rate': 5.7,
        'profit_factor': 4.75,
        'current_kelly_fraction': 0.25,
        'current_ev_threshold': 1.10
    }

    # 問題検出
    print("=" * 60)
    print("パフォーマンス分析")
    print("=" * 60)
    print()

    issues = PerformanceMonitor.detect_issues(metrics)
    strengths = PerformanceMonitor.identify_strengths(metrics)

    print("【問題点】")
    if issues:
        for issue in issues:
            print(f"  ⚠️ {issue}")
    else:
        print("  特になし")
    print()

    print("【強み】")
    if strengths:
        for strength in strengths:
            print(f"  + {strength}")
    else:
        print("  特になし")
    print()

    # 改善提案生成
    print("=" * 60)
    print("改善提案（ナルト）")
    print("=" * 60)
    print()

    print("ナルト: 「改善案を考えるってばよ！」")
    print()

    proposals = learner.generate_proposals(metrics)

    for i, proposal in enumerate(proposals, 1):
        print(f"[提案 {i}] {proposal.title} (優先度: {proposal.priority.upper()})")
        print(f"  タイプ: {proposal.improvement_type}")
        print(f"  説明: {proposal.description}")
        if proposal.current_value:
            print(f"  現在: {proposal.current_value}")
        if proposal.proposed_value:
            print(f"  提案: {proposal.proposed_value}")
        print(f"  期待効果: {proposal.expected_impact}")
        print()

    # レポート作成
    print("=" * 60)
    print("学習レポート作成")
    print("=" * 60)
    print()

    summary = "ROI +51.0%、回収率 256.8%と非常に良好。Profit Factor 4.75で利益効率も優秀。"
    report = learner.create_report(
        proposals=proposals,
        date_range="2026-01-01 ~ 2026-01-29",
        summary=summary
    )

    print(f"レポートID: {report.report_id}")
    print(f"対象期間: {report.date_range}")
    print(f"改善提案: {report.total_improvements}件")
    print(f"  - 高優先度: {report.high_priority}件")
    print(f"  - 中優先度: {report.medium_priority}件")
    print(f"  - 低優先度: {report.low_priority}件")
    print()
    print(f"サマリー: {report.summary}")
    print()

    # レポート保存
    learner.save_report(report)
    print()

    print("ナルト: 「これで次はもっと強くなれるってばよ！」")


if __name__ == '__main__':
    test_learner()

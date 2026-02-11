#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
レース選定支援ツール (Race Selector)

データの完全性や予想しやすさを評価し、予想すべきレースを推奨する。

データ形式: integrated_*.json (統合レースデータ)

使用例:
    python race_selector.py --date 20260125
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

# プロジェクトルートを追加
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class RaceScore:
    """レーススコア"""
    race_id: str
    race_name: str
    venue: str
    race_number: int
    distance: int
    track: str
    horse_count: int
    data_completeness: float  # データ完全性 (0.0-1.0)
    predictability: float     # 予想しやすさ (0.0-1.0)
    confidence: float         # 信頼度 (0.0-1.0)
    total_score: float        # 総合スコア (0.0-100.0)
    recommendation: str       # 推奨度 (高/中/低/不可)
    reasons: List[str]        # 理由


class DataCompletenessChecker:
    """データ完全性チェッカー（integrated_形式対応）"""

    @staticmethod
    def check_entry_data(entry: Dict) -> Tuple[float, List[str]]:
        """
        出走馬データの完全性をチェック

        Returns:
            (スコア 0.0-1.0, 不足項目リスト)
        """
        entry_data = entry.get("entry_data", {})

        required_fields = [
            ("horse_name", entry),
            ("horse_number", entry),
            ("jockey", entry_data),
            ("trainer", entry_data),
            ("odds", entry_data),
        ]

        optional_fields = [
            ("short_comment", entry_data),
            ("honshi_mark", entry_data),
            ("ai_index", entry_data),
            ("rating", entry_data),
        ]

        training_fields = [
            ("short_review", entry.get("training_data", {})),
            ("training_arrow", entry.get("training_data", {})),
        ]

        score = 0.0
        missing = []

        # 必須項目チェック (50%の重み)
        for field, data in required_fields:
            if data.get(field):
                score += 0.5 / len(required_fields)
            else:
                missing.append(field)

        # オプション項目チェック (30%の重み)
        for field, data in optional_fields:
            if data.get(field):
                score += 0.3 / len(optional_fields)

        # 調教データチェック (20%の重み)
        for field, data in training_fields:
            if data.get(field):
                score += 0.2 / len(training_fields)

        return score, missing

    @staticmethod
    def check_race_data(race_data: Dict) -> Tuple[float, List[str]]:
        """
        レースデータの完全性をチェック

        Returns:
            (スコア 0.0-1.0, 不足項目リスト)
        """
        entries = race_data.get("entries", [])
        if not entries:
            return 0.0, ["出走馬データなし"]

        # 全馬のデータ完全性を計算
        total_score = 0.0
        all_missing = []

        for entry in entries:
            entry_score, missing = DataCompletenessChecker.check_entry_data(entry)
            total_score += entry_score
            all_missing.extend(missing)

        avg_score = total_score / len(entries)

        # ユニークな不足項目
        unique_missing = list(set(all_missing))

        return avg_score, unique_missing


class PredictabilityEvaluator:
    """予想しやすさ評価器"""

    @staticmethod
    def evaluate(race_data: Dict) -> Tuple[float, List[str]]:
        """
        予想しやすさを評価

        Returns:
            (スコア 0.0-1.0, 理由リスト)
        """
        score = 0.5  # ベーススコア
        reasons = []

        entries = race_data.get("entries", [])
        if not entries:
            return 0.0, ["出走馬なし"]

        horse_count = len(entries)

        # 1. 出走頭数による評価
        if 8 <= horse_count <= 16:
            score += 0.15
            reasons.append(f"適正頭数 ({horse_count}頭)")
        elif horse_count < 8:
            score += 0.1
            reasons.append(f"少頭数 ({horse_count}頭)")
        else:
            score -= 0.1
            reasons.append(f"多頭数 ({horse_count}頭)")

        # 2. オッズ分布による評価
        odds_list = []
        for entry in entries:
            odds_str = entry.get("entry_data", {}).get("odds", "0")
            try:
                odds = float(odds_str)
                if odds > 0:
                    odds_list.append(odds)
            except (ValueError, TypeError):
                pass

        if odds_list:
            min_odds = min(odds_list)
            max_odds = max(odds_list)

            # 1番人気が極端に低いオッズ → 堅い (予想しやすい)
            if min_odds < 2.0:
                score += 0.15
                reasons.append(f"堅いレース (1人気 {min_odds:.1f}倍)")
            elif min_odds < 3.0:
                score += 0.1
                reasons.append(f"やや堅い (1人気 {min_odds:.1f}倍)")
            elif min_odds > 5.0:
                score -= 0.1
                reasons.append(f"混戦 (1人気 {min_odds:.1f}倍)")

            # オッズ格差が大きい → 予想しやすい
            if max_odds / min_odds > 20:
                score += 0.1
                reasons.append("オッズ格差大")

        # 3. 本誌印の有無
        has_marks = any(entry.get("entry_data", {}).get("honshi_mark") for entry in entries)
        if has_marks:
            score += 0.05
            reasons.append("本誌印あり")

        # 4. 調教データの有無
        has_training = any(entry.get("training_data", {}).get("short_review") for entry in entries)
        if has_training:
            score += 0.1
            reasons.append("調教データあり")

        # 5. AI指数の有無
        has_ai_index = any(entry.get("entry_data", {}).get("ai_index") for entry in entries)
        if has_ai_index:
            score += 0.05
            reasons.append("AI指数あり")

        # スコアを0-1の範囲に収める
        score = max(0.0, min(1.0, score))

        return score, reasons


class RaceSelector:
    """レース選定エンジン"""

    def __init__(self, data_root: Path):
        self.data_root = data_root

    def load_races(self, target_date: str) -> List[Dict]:
        """指定日のレースを読み込む（integrated_形式）"""
        year = target_date[:4]
        month = target_date[4:6]
        day = target_date[6:8]

        race_dir = self.data_root / "races" / year / month / day / "temp"

        if not race_dir.exists():
            return []

        races = []
        for race_file in race_dir.glob("integrated_*.json"):
            try:
                with open(race_file, "r", encoding="utf-8") as f:
                    race_data = json.load(f)
                    races.append(race_data)
            except Exception as e:
                print(f"レースデータ読み込みエラー: {race_file} - {e}")

        return races

    def evaluate_race(self, race_data: Dict) -> RaceScore:
        """レースを評価"""
        meta = race_data.get("meta", {})
        race_info = race_data.get("race_info", {})

        race_id = meta.get("race_id", "")
        race_name = race_info.get("race_condition", "") or race_info.get("race_name", "")
        venue = race_info.get("venue", "")
        race_number = race_info.get("race_number", 0)
        distance = race_info.get("distance", 0)
        track = race_info.get("track", "")
        horse_count = len(race_data.get("entries", []))

        # データ完全性チェック
        completeness, missing = DataCompletenessChecker.check_race_data(race_data)

        # 予想しやすさ評価
        predictability, pred_reasons = PredictabilityEvaluator.evaluate(race_data)

        # 信頼度計算 (データ完全性と予想しやすさの重み付け平均)
        confidence = (completeness * 0.6 + predictability * 0.4)

        # 総合スコア (0-100)
        total_score = confidence * 100

        # 推奨度判定
        if total_score >= 70:
            recommendation = "高"
        elif total_score >= 55:
            recommendation = "中"
        elif total_score >= 40:
            recommendation = "低"
        else:
            recommendation = "不可"

        # 理由をまとめる
        reasons = []
        reasons.append(f"データ完全性: {completeness*100:.0f}%")
        reasons.append(f"予想しやすさ: {predictability*100:.0f}%")
        reasons.extend(pred_reasons)

        if missing:
            reasons.append(f"不足: {', '.join(missing[:3])}")

        return RaceScore(
            race_id=race_id,
            race_name=race_name,
            venue=venue,
            race_number=race_number,
            distance=distance,
            track=track,
            horse_count=horse_count,
            data_completeness=completeness,
            predictability=predictability,
            confidence=confidence,
            total_score=total_score,
            recommendation=recommendation,
            reasons=reasons
        )

    def select_races(self, target_date: str, min_score: float = 50.0) -> List[RaceScore]:
        """
        推奨レースを選定

        Args:
            target_date: 日付 (YYYYMMDD)
            min_score: 最小スコア閾値

        Returns:
            推奨レースのリスト (スコア降順)
        """
        races = self.load_races(target_date)

        if not races:
            print(f"\n{target_date} のintegrated_データが見つかりません。")
            print("WebViewerでデータ作成を実行してください: http://localhost:3000/admin")
            return []

        scores = []
        for race_data in races:
            score = self.evaluate_race(race_data)
            scores.append(score)

        # スコア降順でソート
        scores.sort(key=lambda x: x.total_score, reverse=True)

        # 閾値以上のレースをフィルタ
        filtered = [s for s in scores if s.total_score >= min_score]

        return filtered

    def print_scores(self, scores: List[RaceScore], show_all: bool = False):
        """スコアを表示"""
        if not scores:
            print("\n推奨レースがありません（閾値以上のレースなし）")
            return

        print("\n" + "="*110)
        print("レース選定結果")
        print("="*110)

        print(f"{'No':<4} {'レースID':<14} {'会場':<6} {'R':<4} {'レース名':<20} "
              f"{'コース':<10} {'頭数':<6} {'スコア':<8} {'推奨':<6}")
        print("-"*110)

        for i, score in enumerate(scores, 1):
            track_info = f"{score.track}{score.distance}m"

            print(f"{i:<4} {score.race_id:<14} {score.venue:<6} {score.race_number:<4} "
                  f"{score.race_name:<20} {track_info:<10} {score.horse_count:<6} "
                  f"{score.total_score:<8.1f} {score.recommendation:<6}")

            if show_all:
                for reason in score.reasons:
                    print(f"{'':50} - {reason}")

        print("-"*110)
        print(f"合計: {len(scores)}レース")
        print("="*110)

        # 推奨度別カウント
        high = sum(1 for s in scores if s.recommendation == "高")
        mid = sum(1 for s in scores if s.recommendation == "中")
        low = sum(1 for s in scores if s.recommendation == "低")
        print(f"\n推奨度別: 高={high}件, 中={mid}件, 低={low}件")

    def save_scores(self, scores: List[RaceScore], output_dir: Path = None):
        """スコアを保存"""
        if not scores:
            return

        if output_dir is None:
            output_dir = self.data_root.parent / "_keiba" / "logs" / "race_selection"

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"race_scores_{timestamp}.json"

        data = [
            {
                "race_id": s.race_id,
                "race_name": s.race_name,
                "venue": s.venue,
                "race_number": s.race_number,
                "track": s.track,
                "distance": s.distance,
                "horse_count": s.horse_count,
                "data_completeness": s.data_completeness,
                "predictability": s.predictability,
                "confidence": s.confidence,
                "total_score": s.total_score,
                "recommendation": s.recommendation,
                "reasons": s.reasons
            }
            for s in scores
        ]

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\nレース選定結果を保存しました: {output_file}")


def main():
    """メイン処理"""
    import argparse

    parser = argparse.ArgumentParser(description="レース選定支援ツール")
    parser.add_argument("--data-root", type=str, default=r"E:\share\KEIBA-CICD\data2",
                       help="データルートディレクトリ")
    parser.add_argument("--date", type=str, required=True,
                       help="日付 (YYYYMMDD形式)")
    parser.add_argument("--min-score", type=float, default=50.0,
                       help="最小スコア閾値 (デフォルト: 50.0)")
    parser.add_argument("--show-all", action="store_true",
                       help="全ての理由を表示")
    parser.add_argument("--save", action="store_true",
                       help="結果を保存")

    args = parser.parse_args()

    selector = RaceSelector(data_root=Path(args.data_root))

    print(f"\n{args.date} のレースを評価中...")

    scores = selector.select_races(args.date, min_score=args.min_score)

    selector.print_scores(scores, show_all=args.show_all)

    if args.save:
        selector.save_scores(scores)


if __name__ == "__main__":
    main()

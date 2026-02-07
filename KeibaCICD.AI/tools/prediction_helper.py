#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
予想ヘルパーツール (Prediction Helper)

ふくださんが手動で予想する際の支援ツール。
期待値計算、賭け金推奨、レース選定支援を提供。

データ形式: integrated_*.json (統合レースデータ)

使用例:
    python prediction_helper.py --date 20260131 --interactive
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# プロジェクトルートを追加
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


# ============================================================
# 期待値計算（シノの機能を内蔵）
# ============================================================

class ExpectedValueCalculator:
    """期待値計算クラス"""

    @staticmethod
    def calculate(prob: float, odds: float, bet_amount: int = 100, bet_type: str = "win") -> Dict:
        """
        期待値を計算

        Args:
            prob: 勝率 (0.0-1.0)
            odds: オッズ
            bet_amount: 賭け金（デフォルト100円）
            bet_type: 券種

        Returns:
            期待値情報の辞書
        """
        if prob <= 0 or odds <= 0:
            return {
                "expected_value": 0,
                "expected_value_rate": 0,
                "potential_return": 0
            }

        potential_return = bet_amount * odds
        expected_value = (prob * potential_return) - bet_amount
        expected_value_rate = (prob * odds) * 100  # パーセント表記

        return {
            "expected_value": expected_value,
            "expected_value_rate": expected_value_rate,
            "potential_return": potential_return
        }


class RecommendationEngine:
    """推奨判定エンジン"""

    def __init__(self, ev_threshold: float = 110.0):
        self.ev_threshold = ev_threshold  # 期待値閾値（110% = プラス期待値）

    def recommend(self, ev_rate: float, prob: float, odds: float) -> Tuple[bool, str]:
        """
        購入推奨判定

        Returns:
            (推奨するか, 理由)
        """
        if ev_rate >= self.ev_threshold:
            return True, f"期待値{ev_rate:.1f}%（閾値{self.ev_threshold}%以上）"
        else:
            return False, f"期待値{ev_rate:.1f}%（閾値{self.ev_threshold}%未満）"


# ============================================================
# Kelly基準（シカマルの機能を内蔵）
# ============================================================

class KellyCriterion:
    """Kelly基準による賭け金計算"""

    @staticmethod
    def calculate(prob: float, odds: float) -> float:
        """フルKelly係数を計算"""
        if prob <= 0 or odds <= 1.0:
            return 0.0
        b = odds - 1.0
        p = prob
        q = 1.0 - p
        f_star = (b * p - q) / b
        return max(0.0, f_star)

    @staticmethod
    def fractional_kelly(prob: float, odds: float, fraction: float = 0.25) -> float:
        """Fractional Kelly（保守的な賭け金）"""
        full_kelly = KellyCriterion.calculate(prob, odds)
        return full_kelly * fraction


class BettingStrategist:
    """賭け戦略クラス（簡易版）"""

    def __init__(self, bankroll: int = 100000, kelly_fraction: float = 0.25,
                 ev_threshold: float = 110.0):
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.ev_threshold = ev_threshold

    def evaluate_bet(self, race_id: str, horse_name: str, prob: float, odds: float,
                    expected_value: float, expected_value_rate: float,
                    bet_type: str = "win") -> Dict:
        """賭けを評価"""
        # 期待値チェック
        if expected_value_rate < self.ev_threshold:
            return {
                "race_id": race_id,
                "horse_name": horse_name,
                "bet_amount": 0,
                "can_bet": False,
                "risk_reason": f"期待値{expected_value_rate:.1f}%が閾値{self.ev_threshold}%未満"
            }

        # Kelly係数計算
        kelly_frac = KellyCriterion.fractional_kelly(prob, odds, self.kelly_fraction)
        bet_amount = int(self.bankroll * kelly_frac)

        # 最小賭け金チェック
        if bet_amount < 100:
            bet_amount = 0
            can_bet = False
            risk_reason = "賭け金が100円未満"
        else:
            # 100円単位に丸める
            bet_amount = (bet_amount // 100) * 100
            can_bet = True
            risk_reason = ""

        return {
            "race_id": race_id,
            "horse_name": horse_name,
            "bet_amount": bet_amount,
            "can_bet": can_bet,
            "risk_reason": risk_reason
        }


# ============================================================
# データローダー
# ============================================================

class RaceDataLoader:
    """レースデータ読み込み（integrated_形式対応）"""

    def __init__(self, data_root: Path):
        self.data_root = data_root

    def load_race(self, race_id: str, target_date: str = None) -> Optional[Dict]:
        """レースデータを読み込む"""
        if target_date:
            year = target_date[:4]
            month = target_date[4:6]
            day = target_date[6:8]
            race_dir = self.data_root / "races" / year / month / day / "temp"
        else:
            race_dir = self._find_race_directory(race_id)
            if not race_dir:
                print(f"レースディレクトリが見つかりません: {race_id}")
                return None

        race_file = race_dir / f"integrated_{race_id}.json"

        if not race_file.exists():
            print(f"レースデータが見つかりません: {race_file}")
            return None

        with open(race_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _find_race_directory(self, race_id: str) -> Optional[Path]:
        """race_idからディレクトリを探す"""
        for year in ["2026", "2025", "2024", "2023"]:
            races_dir = self.data_root / "races" / year
            if not races_dir.exists():
                continue
            for month_dir in races_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue
                    temp_dir = day_dir / "temp"
                    if temp_dir.exists():
                        race_file = temp_dir / f"integrated_{race_id}.json"
                        if race_file.exists():
                            return temp_dir
        return None

    def get_available_races(self, target_date: str) -> List[Dict]:
        """利用可能なレースを取得"""
        year = target_date[:4]
        month = target_date[4:6]
        day = target_date[6:8]

        race_dir = self.data_root / "races" / year / month / day / "temp"

        if not race_dir.exists():
            return []

        # race_info.jsonから正しい会場名を取得
        venue_map = self._build_venue_map(target_date)

        races = []
        for race_file in race_dir.glob("integrated_*.json"):
            try:
                with open(race_file, "r", encoding="utf-8") as f:
                    race_data = json.load(f)
                    race_info = race_data.get("race_info", {})
                    race_id = race_data.get("meta", {}).get("race_id", "")

                    # race_info.jsonから正しい会場名を取得
                    venue = venue_map.get(race_id, {}).get("venue", race_info.get("venue", ""))

                    races.append({
                        "race_id": race_id,
                        "race_name": race_info.get("race_condition", "") or race_info.get("race_name", ""),
                        "venue": venue,
                        "race_number": race_info.get("race_number", 0),
                        "distance": race_info.get("distance", 0),
                        "track": race_info.get("track", ""),
                        "horse_count": len(race_data.get("entries", []))
                    })
            except Exception as e:
                print(f"読み込みエラー: {race_file} - {e}")

        races.sort(key=lambda x: (x["venue"], x["race_number"]))
        return races

    def _build_venue_map(self, target_date: str) -> Dict[str, Dict]:
        """race_info.jsonからrace_id→会場のマッピングを作成"""
        year = target_date[:4]
        month = target_date[4:6]
        day = target_date[6:8]

        race_info_file = self.data_root / "races" / year / month / day / "race_info.json"

        if not race_info_file.exists():
            return {}

        venue_map = {}
        try:
            with open(race_info_file, "r", encoding="utf-8") as f:
                race_info = json.load(f)

            for kaisai_name, race_list in race_info.get("kaisai_data", {}).items():
                # "1回東京1日目" から "東京" を抽出
                venue = ""
                for v in ["東京", "中山", "京都", "阪神", "中京", "小倉", "新潟", "福島", "札幌", "函館"]:
                    if v in kaisai_name:
                        venue = v
                        break

                for race in race_list:
                    race_id = race.get("race_id", "")
                    venue_map[race_id] = {
                        "venue": venue,
                        "kaisai": kaisai_name,
                        "race_name": race.get("race_name", ""),
                        "course": race.get("course", "")
                    }
        except Exception as e:
            print(f"race_info.json読み込みエラー: {e}")

        return venue_map

    def get_race_info_from_json(self, target_date: str) -> List[Dict]:
        """race_info.jsonからレース一覧を取得"""
        year = target_date[:4]
        month = target_date[4:6]
        day = target_date[6:8]

        race_info_file = self.data_root / "races" / year / month / day / "race_info.json"

        if not race_info_file.exists():
            return []

        with open(race_info_file, "r", encoding="utf-8") as f:
            race_info = json.load(f)

        races = []
        for kaisai_name, race_list in race_info.get("kaisai_data", {}).items():
            for race in race_list:
                races.append({
                    "race_id": race.get("race_id", ""),
                    "race_name": race.get("race_name", ""),
                    "venue": kaisai_name,
                    "race_number": race.get("race_no", ""),
                    "course": race.get("course", ""),
                    "start_time": race.get("start_time", "")
                })
        return races


# ============================================================
# 予想ヘルパー
# ============================================================

class PredictionHelper:
    """予想支援システム"""

    def __init__(self, data_root: Path, bankroll: int = 100000, kelly_fraction: float = 0.25):
        self.data_root = data_root
        self.data_loader = RaceDataLoader(data_root)
        self.ev_calculator = ExpectedValueCalculator()
        self.recommendation_engine = RecommendationEngine()
        self.strategist = BettingStrategist(bankroll=bankroll, kelly_fraction=kelly_fraction)

    def analyze_prediction(self, race_id: str, horse_name: str,
                          win_prob: float, target_date: str = None,
                          bet_type: str = "win") -> Optional[Dict]:
        """予想を分析して期待値と推奨度を計算"""
        race_data = self.data_loader.load_race(race_id, target_date)
        if not race_data:
            return None

        race_info = race_data.get("race_info", {})
        entries = race_data.get("entries", [])

        # 馬を検索
        horse = None
        for h in entries:
            if h.get("horse_name") == horse_name:
                horse = h
                break

        if not horse:
            print(f"馬が見つかりません: {horse_name}")
            print("出走馬一覧:")
            for h in entries:
                print(f"  {h.get('horse_number')}. {h.get('horse_name')}")
            return None

        # オッズ取得
        entry_data = horse.get("entry_data", {})
        odds_str = entry_data.get("odds", "0")
        try:
            odds = float(odds_str)
        except (ValueError, TypeError):
            print(f"オッズ情報が不正です: {odds_str}")
            return None

        if odds == 0.0:
            print(f"オッズ情報がありません: {horse_name}")
            return None

        # 期待値計算
        ev = self.ev_calculator.calculate(win_prob, odds, bet_type=bet_type)

        # 推奨度判定
        recommended, reason = self.recommendation_engine.recommend(
            ev["expected_value_rate"], win_prob, odds
        )

        # 賭け金計算
        bet_evaluation = self.strategist.evaluate_bet(
            race_id=race_id,
            horse_name=horse_name,
            prob=win_prob,
            odds=odds,
            expected_value=ev["expected_value"],
            expected_value_rate=ev["expected_value_rate"],
            bet_type=bet_type
        )

        return {
            "race_id": race_id,
            "race_name": f"{race_info.get('venue', '')} {race_info.get('race_number', '')}R {race_info.get('race_condition', '')}",
            "horse_name": horse_name,
            "horse_number": horse.get("horse_number", 0),
            "jockey": entry_data.get("jockey", ""),
            "trainer": entry_data.get("trainer", ""),
            "win_prob": win_prob,
            "odds": odds,
            "bet_type": bet_type,
            "expected_value": ev["expected_value"],
            "expected_value_rate": ev["expected_value_rate"],
            "recommended": recommended,
            "reason": reason,
            "bet_amount": bet_evaluation["bet_amount"],
            "can_bet": bet_evaluation["can_bet"],
            "risk_reason": bet_evaluation["risk_reason"]
        }

    def analyze_with_manual_odds(self, race_id: str, horse_name: str,
                                 win_prob: float, manual_odds: float,
                                 bet_type: str = "win") -> Dict:
        """手動入力のオッズで期待値計算"""
        ev = self.ev_calculator.calculate(win_prob, manual_odds, bet_type=bet_type)
        recommended, reason = self.recommendation_engine.recommend(
            ev["expected_value_rate"], win_prob, manual_odds
        )
        bet_evaluation = self.strategist.evaluate_bet(
            race_id=race_id,
            horse_name=horse_name,
            prob=win_prob,
            odds=manual_odds,
            expected_value=ev["expected_value"],
            expected_value_rate=ev["expected_value_rate"],
            bet_type=bet_type
        )

        return {
            "race_id": race_id,
            "race_name": "",
            "horse_name": horse_name,
            "horse_number": 0,
            "jockey": "",
            "trainer": "",
            "win_prob": win_prob,
            "odds": manual_odds,
            "bet_type": bet_type,
            "expected_value": ev["expected_value"],
            "expected_value_rate": ev["expected_value_rate"],
            "recommended": recommended,
            "reason": reason,
            "bet_amount": bet_evaluation["bet_amount"],
            "can_bet": bet_evaluation["can_bet"],
            "risk_reason": bet_evaluation["risk_reason"]
        }

    def show_race_list(self, target_date: str):
        """利用可能なレース一覧を表示"""
        races = self.data_loader.get_available_races(target_date)

        if races:
            print("\n" + "="*90)
            print(f"{target_date[:4]}/{target_date[4:6]}/{target_date[6:8]} レース一覧")
            print("="*90)
            print(f"{'No':<4} {'レースID':<14} {'会場':<6} {'R':<4} {'レース名':<20} {'コース':<10} {'頭数'}")
            print("-"*90)
            for i, race in enumerate(races, 1):
                track_info = f"{race['track']}{race['distance']}m"
                print(f"{i:<4} {race['race_id']:<14} {race['venue']:<6} {race['race_number']:<4} "
                      f"{race['race_name']:<20} {track_info:<10} {race['horse_count']}頭")
            print("="*90)
        else:
            races = self.data_loader.get_race_info_from_json(target_date)
            if races:
                print("\n" + "="*90)
                print(f"{target_date[:4]}/{target_date[4:6]}/{target_date[6:8]} レース一覧 (基本情報のみ)")
                print("="*90)
                for race in races:
                    print(f"{race['race_id']} {race['venue']} {race['race_number']} {race['race_name']}")
                print("="*90)
            else:
                print(f"\n{target_date} のレースデータが見つかりません。")

    def show_horses(self, race_id: str, target_date: str = None):
        """レースの出走馬一覧を表示"""
        race_data = self.data_loader.load_race(race_id, target_date)
        if not race_data:
            return

        race_info = race_data.get("race_info", {})
        entries = race_data.get("entries", [])

        print("\n" + "="*100)
        print(f"レース: {race_info.get('venue', '')} {race_info.get('race_number', '')}R "
              f"{race_info.get('race_condition', '')}")
        print(f"コース: {race_info.get('track', '')}{race_info.get('distance', '')}m")
        print(f"ID: {race_id}")
        print("="*100)
        print(f"{'馬番':<4} {'馬名':<18} {'騎手':<10} {'オッズ':<8} {'人気':<6} {'印':<4} {'短評'}")
        print("-"*100)

        for entry in entries:
            horse_num = entry.get("horse_number", 0)
            horse_name = entry.get("horse_name", "")
            entry_data = entry.get("entry_data", {})
            jockey = entry_data.get("jockey", "")
            win_odds = entry_data.get("odds", "")
            odds_rank = entry_data.get("odds_rank", "")
            honshi_mark = entry_data.get("honshi_mark", "")
            short_comment = entry_data.get("short_comment", "")[:15] if entry_data.get("short_comment") else ""

            print(f"{horse_num:<4} {horse_name:<18} {jockey:<10} {win_odds:<8} "
                  f"{odds_rank:<6} {honshi_mark:<4} {short_comment}")

        print("="*100)

    def interactive_mode(self, target_date: str = None):
        """対話モード"""
        print("\n" + "="*70)
        print("予想ヘルパーツール - 対話モード")
        print("="*70)
        print("コマンド:")
        print("  list [YYYYMMDD]  - レース一覧を表示")
        print("  show <race_id>   - 出走馬一覧を表示")
        print("  predict          - 予想を入力（データから）")
        print("  manual           - 予想を入力（手動オッズ）")
        print("  quit             - 終了")
        print("="*70)

        if target_date:
            print(f"\nデフォルト日付: {target_date}")

        predictions = []
        current_date = target_date

        while True:
            try:
                cmd = input("\nコマンド> ").strip()

                if cmd.lower() == "quit":
                    break

                elif cmd.lower().startswith("list"):
                    parts = cmd.split()
                    date = parts[1] if len(parts) > 1 else current_date
                    if date:
                        self.show_race_list(date)
                        current_date = date
                    else:
                        print("日付を指定してください: list YYYYMMDD")

                elif cmd.lower().startswith("show"):
                    parts = cmd.split()
                    if len(parts) < 2:
                        print("使い方: show <race_id>")
                        continue
                    race_id = parts[1]
                    self.show_horses(race_id, current_date)

                elif cmd.lower() == "predict":
                    print("\n--- 予想入力（データから） ---")
                    race_id = input("レースID: ").strip()
                    horse_name = input("馬名: ").strip()
                    win_prob_str = input("予想勝率 (例: 15 for 15%): ").strip()
                    bet_type = input("券種 (win/place) [win]: ").strip() or "win"

                    try:
                        win_prob = float(win_prob_str) / 100.0
                    except ValueError:
                        print("勝率は数値で入力してください。")
                        continue

                    result = self.analyze_prediction(race_id, horse_name, win_prob,
                                                    current_date, bet_type)
                    if result:
                        predictions.append(result)
                        self.print_result(result)
                        self._ask_continue(predictions)

                elif cmd.lower() == "manual":
                    print("\n--- 予想入力（手動オッズ） ---")
                    race_id = input("レースID（任意）: ").strip() or "manual"
                    horse_name = input("馬名: ").strip()
                    win_prob_str = input("予想勝率 (例: 15 for 15%): ").strip()
                    odds_str = input("オッズ: ").strip()
                    bet_type = input("券種 (win/place) [win]: ").strip() or "win"

                    try:
                        win_prob = float(win_prob_str) / 100.0
                        manual_odds = float(odds_str)
                    except ValueError:
                        print("数値を正しく入力してください。")
                        continue

                    result = self.analyze_with_manual_odds(race_id, horse_name,
                                                         win_prob, manual_odds, bet_type)
                    predictions.append(result)
                    self.print_result(result)
                    self._ask_continue(predictions)

                else:
                    print("不明なコマンドです。help でコマンド一覧を確認してください。")

            except KeyboardInterrupt:
                print("\n\n終了します。")
                break
            except Exception as e:
                print(f"エラー: {e}")

    def _ask_continue(self, predictions: List[Dict]):
        """続けるか確認"""
        more = input("\n他にも予想を追加しますか？ (y/n): ").strip().lower()
        if more != "y":
            self.print_summary(predictions)
            save = input("\n結果を保存しますか？ (y/n): ").strip().lower()
            if save == "y":
                self.save_predictions(predictions)
            predictions.clear()

    def print_result(self, result: Dict):
        """分析結果を表示"""
        print("\n" + "="*70)
        print("分析結果")
        print("="*70)
        if result['race_name']:
            print(f"レース: {result['race_name']}")
        print(f"馬名: {result['horse_name']} ({result['horse_number']}番)")
        if result['jockey']:
            print(f"騎手: {result['jockey']} / 調教師: {result['trainer']}")
        print("-"*70)
        print(f"予想勝率: {result['win_prob']*100:.1f}%")
        print(f"オッズ: {result['odds']:.1f}倍")
        print(f"期待値: {result['expected_value']:.0f}円 ({result['expected_value_rate']:.1f}%)")
        print("-"*70)
        print(f"推奨: {'YES' if result['recommended'] else 'NO'}")
        print(f"理由: {result['reason']}")
        print("-"*70)
        print(f"推奨賭け金: {result['bet_amount']:,}円")
        print(f"購入可否: {'可' if result['can_bet'] else '不可'}")
        if result['risk_reason']:
            print(f"リスク理由: {result['risk_reason']}")
        print("="*70)

    def print_summary(self, results: List[Dict]):
        """複数の予想結果をサマリー表示"""
        if not results:
            return

        print("\n" + "="*80)
        print("予想サマリー")
        print("="*80)

        total_bet = 0
        recommended_count = 0

        print(f"{'No':<4} {'馬名':<18} {'勝率%':<8} {'オッズ':<8} {'期待値%':<10} {'推奨':<6} {'賭け金'}")
        print("-"*80)

        for i, result in enumerate(results, 1):
            total_bet += result['bet_amount']
            if result['recommended']:
                recommended_count += 1

            print(f"{i:<4} {result['horse_name']:<18} "
                  f"{result['win_prob']*100:<8.1f} {result['odds']:<8.1f} "
                  f"{result['expected_value_rate']:<10.1f} "
                  f"{'YES' if result['recommended'] else 'NO':<6} "
                  f"{result['bet_amount']:,}円")

        print("-"*80)
        print(f"合計: {len(results)}件 (推奨: {recommended_count}件)")
        print(f"合計賭け金: {total_bet:,}円")
        print("="*80)

    def save_predictions(self, results: List[Dict], output_dir: Path = None):
        """予想結果を保存"""
        if not results:
            return

        if output_dir is None:
            output_dir = self.data_root.parent / "_keiba" / "logs" / "user_predictions"

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"predictions_{timestamp}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n予想結果を保存しました: {output_file}")


def main():
    """メイン処理"""
    import argparse

    parser = argparse.ArgumentParser(description="予想ヘルパーツール")
    parser.add_argument("--data-root", type=str, default=r"E:\share\KEIBA-CICD\data2",
                       help="データルートディレクトリ")
    parser.add_argument("--bankroll", type=int, default=100000,
                       help="資金 (デフォルト: 100,000円)")
    parser.add_argument("--kelly-fraction", type=float, default=0.25,
                       help="Kelly係数 (デフォルト: 0.25)")
    parser.add_argument("--interactive", action="store_true",
                       help="対話モードで起動")
    parser.add_argument("--race-id", type=str,
                       help="レースID")
    parser.add_argument("--list", action="store_true",
                       help="レース一覧を表示")
    parser.add_argument("--date", type=str,
                       help="日付 (YYYYMMDD形式)")

    args = parser.parse_args()

    helper = PredictionHelper(
        data_root=Path(args.data_root),
        bankroll=args.bankroll,
        kelly_fraction=args.kelly_fraction
    )

    if args.interactive:
        helper.interactive_mode(args.date)
    elif args.list:
        if not args.date:
            print("--date オプションで日付を指定してください")
            return
        helper.show_race_list(args.date)
    elif args.race_id:
        helper.show_horses(args.race_id, args.date)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

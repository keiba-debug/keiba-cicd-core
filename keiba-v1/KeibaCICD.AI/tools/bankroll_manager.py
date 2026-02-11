#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
収支管理ツール (Bankroll Manager)

資金管理、収支記録、リスク管理を行う。
シカマルの役割を担当。

使用例:
    python bankroll_manager.py --init 100000        # 総資金10万円で初期化
    python bankroll_manager.py --status             # 現在の状況を表示
    python bankroll_manager.py --today              # 本日の予算を表示
    python bankroll_manager.py --bet                # 購入を記録（対話モード）
    python bankroll_manager.py --result             # 結果を記録（対話モード）
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# データディレクトリ
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "bankroll"


@dataclass
class BetRecord:
    """馬券購入記録"""
    id: str
    date: str
    time: str
    race_id: str
    race_name: str
    venue: str
    bet_type: str  # 単勝, 馬連, 三連複, etc.
    selection: str  # "1", "1-2", "1-2-3", etc.
    amount: int
    odds: Optional[float] = None
    result: Optional[str] = None  # "win", "lose", "pending"
    payout: int = 0
    profit: int = 0
    confidence: str = "中"  # 高/中/低
    memo: str = ""


class BankrollManager:
    """収支管理マネージャー（シカマル）"""

    def __init__(self):
        self.config_file = DATA_DIR / "config.json"
        self.summary_file = DATA_DIR / "summary.json"
        self.transactions_dir = DATA_DIR / "transactions"
        self.transactions_dir.mkdir(parents=True, exist_ok=True)

        self.config = self._load_json(self.config_file)
        self.summary = self._load_json(self.summary_file)

    def _load_json(self, file_path: Path) -> Dict:
        """JSONファイルを読み込む"""
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_json(self, file_path: Path, data: Dict):
        """JSONファイルを保存"""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def initialize(self, total_bankroll: int):
        """資金を初期化"""
        self.config["settings"]["total_bankroll"] = total_bankroll
        self.config["updated_at"] = datetime.now().strftime("%Y-%m-%d")

        self.summary["total_bankroll"] = total_bankroll
        self.summary["current_balance"] = total_bankroll
        self.summary["last_updated"] = datetime.now().strftime("%Y-%m-%d")

        self._save_json(self.config_file, self.config)
        self._save_json(self.summary_file, self.summary)

        print(f"\n{'='*50}")
        print("資金設定完了")
        print(f"{'='*50}")
        print(f"総資金: {total_bankroll:,}円")
        print(f"1日上限: {self.get_daily_limit():,}円 ({self.config['settings']['daily_limit_percent']}%)")
        print(f"1レース上限: {self.get_race_limit():,}円 ({self.config['settings']['race_limit_percent']}%)")
        print(f"{'='*50}")

    def get_daily_limit(self) -> int:
        """1日の上限額を取得"""
        bankroll = self.summary.get("current_balance") or self.summary.get("total_bankroll") or 0
        percent = self.config["settings"]["daily_limit_percent"]
        return int(bankroll * percent / 100)

    def get_race_limit(self) -> int:
        """1レースの上限額を取得"""
        bankroll = self.summary.get("current_balance") or self.summary.get("total_bankroll") or 0
        percent = self.config["settings"]["race_limit_percent"]
        return int(bankroll * percent / 100)

    def get_today_transactions(self) -> List[Dict]:
        """本日の取引を取得"""
        today = datetime.now().strftime("%Y%m%d")
        file_path = self.transactions_dir / f"{today}.json"
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def get_today_spent(self) -> int:
        """本日の使用額を取得"""
        transactions = self.get_today_transactions()
        return sum(t.get("amount", 0) for t in transactions)

    def get_today_remaining(self) -> int:
        """本日の残り予算を取得"""
        return max(0, self.get_daily_limit() - self.get_today_spent())

    def can_bet(self, amount: int) -> tuple[bool, str]:
        """
        賭けられるかチェック

        Returns:
            (可否, 理由)
        """
        # 資金未設定チェック
        if not self.summary.get("total_bankroll"):
            return False, "総資金が設定されていません。--init で初期化してください"

        # 1レース上限チェック
        race_limit = self.get_race_limit()
        if amount > race_limit:
            return False, f"1レース上限({race_limit:,}円)を超えています"

        # 1日上限チェック
        remaining = self.get_today_remaining()
        if amount > remaining:
            return False, f"本日の残り予算({remaining:,}円)を超えています"

        # 連敗チェック
        consecutive_limit = self.config["settings"]["consecutive_loss_limit"]
        if self.summary.get("consecutive_losses", 0) >= consecutive_limit:
            return False, f"{consecutive_limit}連敗中です。一旦休止を推奨します"

        return True, "OK"

    def record_bet(self, bet: BetRecord):
        """馬券購入を記録"""
        today = datetime.now().strftime("%Y%m%d")
        file_path = self.transactions_dir / f"{today}.json"

        transactions = self.get_today_transactions()
        transactions.append(asdict(bet))

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(transactions, f, ensure_ascii=False, indent=2)

        # サマリー更新
        self.summary["total_invested"] += bet.amount
        self._save_json(self.summary_file, self.summary)

        print(f"\n購入記録完了: {bet.race_name} {bet.bet_type} {bet.selection} {bet.amount:,}円")

    def record_result(self, bet_id: str, result: str, payout: int = 0):
        """結果を記録"""
        today = datetime.now().strftime("%Y%m%d")
        file_path = self.transactions_dir / f"{today}.json"

        transactions = self.get_today_transactions()

        for t in transactions:
            if t["id"] == bet_id:
                t["result"] = result
                t["payout"] = payout
                t["profit"] = payout - t["amount"]

                # サマリー更新
                self.summary["total_return"] += payout
                self.summary["total_profit"] = self.summary["total_return"] - self.summary["total_invested"]

                if result == "win":
                    self.summary["win_count"] += 1
                    self.summary["consecutive_losses"] = 0
                    self.summary["current_balance"] += t["profit"]
                else:
                    self.summary["loss_count"] += 1
                    self.summary["consecutive_losses"] += 1
                    self.summary["current_balance"] -= t["amount"]

                total_bets = self.summary["win_count"] + self.summary["loss_count"]
                if total_bets > 0:
                    self.summary["win_rate"] = self.summary["win_count"] / total_bets * 100

                if self.summary["total_invested"] > 0:
                    self.summary["roi"] = self.summary["total_profit"] / self.summary["total_invested"] * 100

                break

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(transactions, f, ensure_ascii=False, indent=2)

        self._save_json(self.summary_file, self.summary)

    def show_status(self):
        """現在の状況を表示"""
        print("\n" + "="*60)
        print("収支状況 (シカマルレポート)")
        print("="*60)

        if not self.summary.get("total_bankroll"):
            print("\n[!] 資金が設定されていません")
            print("    python bankroll_manager.py --init <金額> で初期化してください")
            return

        print(f"\n【資金状況】")
        print(f"  総資金:     {self.summary['total_bankroll']:>10,}円")
        print(f"  現在残高:   {self.summary['current_balance']:>10,}円")
        print(f"  累計損益:   {self.summary['total_profit']:>+10,}円")

        print(f"\n【本日の状況】")
        print(f"  1日上限:    {self.get_daily_limit():>10,}円")
        print(f"  使用済み:   {self.get_today_spent():>10,}円")
        print(f"  残り予算:   {self.get_today_remaining():>10,}円")

        print(f"\n【成績】")
        print(f"  的中:       {self.summary['win_count']:>10}回")
        print(f"  不的中:     {self.summary['loss_count']:>10}回")
        print(f"  的中率:     {self.summary['win_rate']:>10.1f}%")
        print(f"  ROI:        {self.summary['roi']:>10.1f}%")

        print(f"\n【リスク状態】")
        consecutive = self.summary.get('consecutive_losses', 0)
        limit = self.config['settings']['consecutive_loss_limit']
        if consecutive >= limit:
            print(f"  [!] {consecutive}連敗中 - 休止推奨")
        elif consecutive > 0:
            print(f"  現在{consecutive}連敗中 (上限{limit}連敗)")
        else:
            print(f"  良好")

        print("="*60)

    def show_today(self):
        """本日の予算を表示"""
        print("\n" + "="*50)
        print(f"本日({datetime.now().strftime('%Y-%m-%d')})の予算")
        print("="*50)

        if not self.summary.get("total_bankroll"):
            print("\n[!] 資金が設定されていません")
            return

        daily_limit = self.get_daily_limit()
        spent = self.get_today_spent()
        remaining = self.get_today_remaining()
        race_limit = self.get_race_limit()

        print(f"\n1日上限:      {daily_limit:>10,}円")
        print(f"使用済み:     {spent:>10,}円")
        print(f"残り予算:     {remaining:>10,}円")
        print(f"1レース上限:  {race_limit:>10,}円")

        # 本日の取引
        transactions = self.get_today_transactions()
        if transactions:
            print(f"\n【本日の購入履歴】")
            for t in transactions:
                status = "[O]" if t.get("result") == "win" else "[X]" if t.get("result") == "lose" else "[?]"
                print(f"  {status} {t['race_name'][:15]:<15} {t['bet_type']:<6} {t['amount']:>6,}円")

        print("="*50)

    def interactive_bet(self):
        """対話モードで購入を記録"""
        print("\n" + "="*50)
        print("馬券購入記録")
        print("="*50)

        if not self.summary.get("total_bankroll"):
            print("\n[!] 資金が設定されていません")
            return

        print(f"\n残り予算: {self.get_today_remaining():,}円")
        print(f"1レース上限: {self.get_race_limit():,}円")

        # 入力
        race_id = input("\nレースID (例: 202601040111): ").strip()
        race_name = input("レース名 (例: 白富士S): ").strip()
        venue = input("会場 (例: 東京): ").strip()
        bet_type = input("馬券種 (単勝/複勝/馬連/馬単/三連複/三連単): ").strip()
        selection = input("買い目 (例: 1 または 1-2 または 1-2-3): ").strip()

        try:
            amount = int(input("金額 (円): ").strip())
        except ValueError:
            print("金額は数字で入力してください")
            return

        odds_str = input("オッズ (不明なら空欄): ").strip()
        odds = float(odds_str) if odds_str else None

        confidence = input("自信度 (高/中/低): ").strip() or "中"
        memo = input("メモ (任意): ").strip()

        # チェック
        can, reason = self.can_bet(amount)
        if not can:
            print(f"\n[!] 購入不可: {reason}")
            return

        # 記録
        bet = BetRecord(
            id=f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{race_id}",
            date=datetime.now().strftime("%Y-%m-%d"),
            time=datetime.now().strftime("%H:%M:%S"),
            race_id=race_id,
            race_name=race_name,
            venue=venue,
            bet_type=bet_type,
            selection=selection,
            amount=amount,
            odds=odds,
            result="pending",
            confidence=confidence,
            memo=memo
        )

        self.record_bet(bet)
        print(f"\n残り予算: {self.get_today_remaining():,}円")

    def interactive_result(self):
        """対話モードで結果を記録"""
        print("\n" + "="*50)
        print("結果記録")
        print("="*50)

        transactions = self.get_today_transactions()
        pending = [t for t in transactions if t.get("result") == "pending"]

        if not pending:
            print("\n未確定の馬券がありません")
            return

        print("\n【未確定の馬券】")
        for i, t in enumerate(pending, 1):
            print(f"  {i}. {t['race_name']} {t['bet_type']} {t['selection']} {t['amount']:,}円")

        try:
            choice = int(input("\n番号を選択: ").strip())
            if choice < 1 or choice > len(pending):
                print("無効な番号です")
                return
        except ValueError:
            print("番号を入力してください")
            return

        selected = pending[choice - 1]
        result = input("結果 (win/lose): ").strip().lower()

        if result not in ["win", "lose"]:
            print("win または lose を入力してください")
            return

        payout = 0
        if result == "win":
            try:
                payout = int(input("払戻金額 (円): ").strip())
            except ValueError:
                print("金額は数字で入力してください")
                return

        self.record_result(selected["id"], result, payout)

        profit = payout - selected["amount"]
        if result == "win":
            print(f"\n[O] 的中! +{profit:,}円")
        else:
            print(f"\n[X] 不的中 -{selected['amount']:,}円")

        self.show_status()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="収支管理ツール (シカマル)")
    parser.add_argument("--init", type=int, help="総資金を設定して初期化")
    parser.add_argument("--status", action="store_true", help="現在の状況を表示")
    parser.add_argument("--today", action="store_true", help="本日の予算を表示")
    parser.add_argument("--bet", action="store_true", help="購入を記録（対話モード）")
    parser.add_argument("--result", action="store_true", help="結果を記録（対話モード）")

    args = parser.parse_args()

    manager = BankrollManager()

    if args.init:
        manager.initialize(args.init)
    elif args.status:
        manager.show_status()
    elif args.today:
        manager.show_today()
    elif args.bet:
        manager.interactive_bet()
    elif args.result:
        manager.interactive_result()
    else:
        # デフォルトはステータス表示
        manager.show_status()


if __name__ == "__main__":
    main()

"""
EXECUTOR (サイ) - 実行記録システム

几帳面な記録者サイが、購入推奨リストを整理し、実行記録と結果を追跡する。

「記録しました」「データを確認します」
"""

import json
import csv
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from enum import Enum


class BetStatus(Enum):
    """馬券の状態"""
    PENDING = "pending"      # 未実行
    EXECUTED = "executed"    # 実行済み
    HIT = "hit"              # 的中
    MISS = "miss"            # 不的中


@dataclass
class BettingRecord:
    """購入記録"""
    record_id: str
    race_id: str
    race_date: str
    race_name: str
    horse_name: str
    bet_type: str
    bet_amount: int
    odds: float
    expected_value_rate: float
    status: str  # BetStatus
    result_rank: Optional[int] = None
    payout: Optional[int] = None
    profit: Optional[int] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class DailySummary:
    """日次サマリー"""
    date: str
    total_bets: int
    total_invested: int
    total_payout: int
    total_profit: int
    hit_count: int
    hit_rate: float
    recovery_rate: float
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class PurchaseLogger:
    """
    購入記録システム

    「記録しました」
    """

    def __init__(self, log_dir: Path = None):
        """
        Args:
            log_dir: ログ保存ディレクトリ
        """
        if log_dir is None:
            log_dir = Path("logs/betting")

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_purchase(self, record: BettingRecord) -> bool:
        """
        購入を記録

        Args:
            record: 購入記録

        Returns:
            成功したか

        「購入記録を保存します」
        """
        try:
            # CSVファイルに追記
            csv_file = self.log_dir / f"purchases_{record.race_date}.csv"

            file_exists = csv_file.exists()

            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'record_id', 'race_id', 'race_date', 'race_name', 'horse_name',
                    'bet_type', 'bet_amount', 'odds', 'expected_value_rate',
                    'status', 'result_rank', 'payout', 'profit', 'timestamp'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                if not file_exists:
                    writer.writeheader()

                writer.writerow(asdict(record))

            return True

        except Exception as e:
            print(f"エラー: 購入記録の保存に失敗しました - {e}")
            return False

    def get_purchases(self, date: str) -> List[BettingRecord]:
        """
        指定日の購入記録を取得

        Args:
            date: 日付（YYYYMMDD）

        Returns:
            購入記録リスト

        「データを確認します」
        """
        csv_file = self.log_dir / f"purchases_{date}.csv"

        if not csv_file.exists():
            return []

        records = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 数値変換
                row['bet_amount'] = int(row['bet_amount'])
                row['odds'] = float(row['odds'])
                row['expected_value_rate'] = float(row['expected_value_rate'])

                if row['result_rank']:
                    row['result_rank'] = int(row['result_rank'])
                else:
                    row['result_rank'] = None

                if row['payout']:
                    row['payout'] = int(row['payout'])
                else:
                    row['payout'] = None

                if row['profit']:
                    row['profit'] = int(row['profit'])
                else:
                    row['profit'] = None

                records.append(BettingRecord(**row))

        return records


class ResultTracker:
    """
    結果追跡システム

    「結果を記録します」
    """

    def __init__(self, log_dir: Path = None):
        """
        Args:
            log_dir: ログ保存ディレクトリ
        """
        if log_dir is None:
            log_dir = Path("logs/betting")

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = PurchaseLogger(log_dir)

    def update_result(
        self,
        record_id: str,
        race_date: str,
        result_rank: int,
        payout: int = 0
    ) -> bool:
        """
        結果を更新

        Args:
            record_id: 記録ID
            race_date: レース日付
            result_rank: 着順
            payout: 払戻金

        Returns:
            成功したか

        「結果を更新しました」
        """
        # 既存記録を読み込み
        records = self.logger.get_purchases(race_date)

        updated = False
        for record in records:
            if record.record_id == record_id:
                # 結果更新
                record.result_rank = result_rank
                record.payout = payout
                record.profit = payout - record.bet_amount

                # ステータス更新
                if payout > 0:
                    record.status = BetStatus.HIT.value
                else:
                    record.status = BetStatus.MISS.value

                updated = True
                break

        if not updated:
            print(f"エラー: record_id={record_id} が見つかりません")
            return False

        # CSVファイルを再書き込み
        csv_file = self.log_dir / f"purchases_{race_date}.csv"

        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'record_id', 'race_id', 'race_date', 'race_name', 'horse_name',
                    'bet_type', 'bet_amount', 'odds', 'expected_value_rate',
                    'status', 'result_rank', 'payout', 'profit', 'timestamp'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for record in records:
                    writer.writerow(asdict(record))

            return True

        except Exception as e:
            print(f"エラー: 結果更新に失敗しました - {e}")
            return False

    def calculate_daily_summary(self, date: str) -> Optional[DailySummary]:
        """
        日次サマリーを計算

        Args:
            date: 日付（YYYYMMDD）

        Returns:
            日次サマリー

        「サマリーを計算します」
        """
        records = self.logger.get_purchases(date)

        if not records:
            return None

        total_bets = len(records)
        total_invested = sum(r.bet_amount for r in records)
        total_payout = sum(r.payout or 0 for r in records)
        total_profit = total_payout - total_invested

        hit_count = sum(1 for r in records if r.status == BetStatus.HIT.value)
        hit_rate = (hit_count / total_bets * 100) if total_bets > 0 else 0
        recovery_rate = (total_payout / total_invested * 100) if total_invested > 0 else 0

        return DailySummary(
            date=date,
            total_bets=total_bets,
            total_invested=total_invested,
            total_payout=total_payout,
            total_profit=total_profit,
            hit_count=hit_count,
            hit_rate=hit_rate,
            recovery_rate=recovery_rate
        )

    def save_daily_summary(self, summary: DailySummary) -> bool:
        """
        日次サマリーを保存

        Args:
            summary: 日次サマリー

        Returns:
            成功したか
        """
        try:
            json_file = self.log_dir / f"summary_{summary.date}.json"

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(summary), f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"エラー: サマリー保存に失敗しました - {e}")
            return False


class BettingExecutor:
    """
    購入実行記録システム - サイ

    シカマルの購入推奨リストを受け取り、実行記録と結果を追跡。

    「記録しました」「データを確認します」
    """

    def __init__(self, log_dir: Path = None):
        """
        Args:
            log_dir: ログ保存ディレクトリ
        """
        if log_dir is None:
            log_dir = Path("logs/betting")

        self.log_dir = Path(log_dir)
        self.logger = PurchaseLogger(log_dir)
        self.tracker = ResultTracker(log_dir)

    def create_purchase_instructions(
        self,
        recommendations: List[Dict],
        race_date: str
    ) -> List[BettingRecord]:
        """
        購入指示書を作成

        Args:
            recommendations: シカマルからの購入推奨リスト
            race_date: レース日付

        Returns:
            購入記録リスト

        「購入指示書を作成します」
        """
        records = []

        for i, rec in enumerate(recommendations):
            if not rec.get('should_bet', False):
                continue

            record_id = f"{race_date}_{i+1:03d}"

            record = BettingRecord(
                record_id=record_id,
                race_id=rec['race_id'],
                race_date=race_date,
                race_name=rec.get('race_name', ''),
                horse_name=rec['horse_name'],
                bet_type=rec['bet_type'],
                bet_amount=rec['bet_amount'],
                odds=rec.get('odds', 0.0),
                expected_value_rate=rec['expected_value_rate'],
                status=BetStatus.PENDING.value
            )

            records.append(record)

        return records

    def execute_purchases(self, records: List[BettingRecord]) -> bool:
        """
        購入を実行（記録）

        Args:
            records: 購入記録リスト

        Returns:
            成功したか

        「購入を記録しました」
        """
        for record in records:
            record.status = BetStatus.EXECUTED.value
            success = self.logger.log_purchase(record)

            if not success:
                return False

        return True

    def generate_purchase_sheet(
        self,
        records: List[BettingRecord],
        output_file: Path = None
    ) -> bool:
        """
        購入指示書（人間向け）を生成

        Args:
            records: 購入記録リスト
            output_file: 出力ファイルパス

        Returns:
            成功したか

        「購入指示書を出力します」
        """
        if output_file is None:
            output_file = self.log_dir / f"purchase_sheet_{records[0].race_date}.txt"

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("購入指示書\n")
                f.write("=" * 60 + "\n")
                f.write(f"日付: {records[0].race_date}\n")
                f.write(f"作成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n")

                total_bet = sum(r.bet_amount for r in records)
                f.write(f"合計賭け金: {total_bet:,}円\n")
                f.write(f"購入件数: {len(records)}件\n")
                f.write("\n")
                f.write("-" * 60 + "\n")

                for i, record in enumerate(records, 1):
                    f.write(f"\n[{i}] {record.horse_name}\n")
                    f.write(f"    レースID: {record.race_id}\n")
                    f.write(f"    馬券種別: {record.bet_type.upper()}\n")
                    f.write(f"    賭け金: {record.bet_amount:,}円\n")
                    f.write(f"    オッズ: {record.odds:.1f}倍\n")
                    f.write(f"    期待値率: {record.expected_value_rate:.1%}\n")
                    f.write("\n")

                f.write("-" * 60 + "\n")
                f.write("\nサイ: 「購入指示書を作成しました」\n")

            return True

        except Exception as e:
            print(f"エラー: 購入指示書の生成に失敗しました - {e}")
            return False

    def get_status_report(self, date: str) -> Dict:
        """
        実行状況レポートを取得

        Args:
            date: 日付

        Returns:
            レポート辞書

        「状況を確認します」
        """
        records = self.logger.get_purchases(date)

        if not records:
            return {
                'date': date,
                'total_records': 0,
                'pending': 0,
                'executed': 0,
                'hit': 0,
                'miss': 0
            }

        status_counts = {
            BetStatus.PENDING.value: 0,
            BetStatus.EXECUTED.value: 0,
            BetStatus.HIT.value: 0,
            BetStatus.MISS.value: 0
        }

        for record in records:
            status_counts[record.status] = status_counts.get(record.status, 0) + 1

        return {
            'date': date,
            'total_records': len(records),
            'pending': status_counts[BetStatus.PENDING.value],
            'executed': status_counts[BetStatus.EXECUTED.value],
            'hit': status_counts[BetStatus.HIT.value],
            'miss': status_counts[BetStatus.MISS.value]
        }


# ========================================
# テストコード
# ========================================

def test_executor():
    """
    サイ（EXECUTOR）のテスト

    「テストを実行します」
    """
    print("=" * 60)
    print("サイ（EXECUTOR）テスト")
    print("=" * 60)
    print()

    # サイ初期化
    executor = BettingExecutor(log_dir=Path("logs/betting_test"))

    print("サイ: 「記録システムを起動しました」")
    print()

    # シカマルからの購入推奨リスト（ダミー）
    recommendations = [
        {
            'race_id': '2026020101010101',
            'race_name': '東京1R',
            'horse_name': 'ドウデュース',
            'bet_type': 'win',
            'should_bet': True,
            'bet_amount': 3100,
            'odds': 5.0,
            'expected_value_rate': 1.50
        },
        {
            'race_id': '2026020101010102',
            'race_name': '東京2R',
            'horse_name': 'イクイノックス',
            'bet_type': 'win',
            'should_bet': True,
            'bet_amount': 2500,
            'odds': 6.0,
            'expected_value_rate': 1.50
        },
        {
            'race_id': '2026020101010103',
            'race_name': '東京3R',
            'horse_name': 'ソングライン',
            'bet_type': 'win',
            'should_bet': True,
            'bet_amount': 3300,
            'odds': 4.0,
            'expected_value_rate': 1.40
        }
    ]

    race_date = "20260201"

    # 購入指示書作成
    print("=" * 60)
    print("購入指示書作成")
    print("=" * 60)
    print()

    records = executor.create_purchase_instructions(recommendations, race_date)

    print(f"購入件数: {len(records)}件")
    for record in records:
        print(f"  - {record.horse_name}: {record.bet_type.upper()} {record.bet_amount:,}円")
    print()

    # 購入実行（記録）
    success = executor.execute_purchases(records)
    if success:
        print("サイ: 「購入を記録しました」")
    else:
        print("サイ: 「エラーが発生しました」")
    print()

    # 購入指示書生成
    executor.generate_purchase_sheet(records)
    print("サイ: 「購入指示書を出力しました」")
    print()

    # 結果更新（ダミー）
    print("=" * 60)
    print("結果更新")
    print("=" * 60)
    print()

    # ドウデュース: 1着（的中）
    executor.tracker.update_result(
        record_id=records[0].record_id,
        race_date=race_date,
        result_rank=1,
        payout=15500  # 5.0倍 × 3100円
    )
    print(f"サイ: 「{records[0].horse_name} - 的中を記録しました」")

    # イクイノックス: 3着（不的中）
    executor.tracker.update_result(
        record_id=records[1].record_id,
        race_date=race_date,
        result_rank=3,
        payout=0
    )
    print(f"サイ: 「{records[1].horse_name} - 不的中を記録しました」")

    # ソングライン: 2着（不的中、単勝なので）
    executor.tracker.update_result(
        record_id=records[2].record_id,
        race_date=race_date,
        result_rank=2,
        payout=0
    )
    print(f"サイ: 「{records[2].horse_name} - 不的中を記録しました」")
    print()

    # 日次サマリー計算
    print("=" * 60)
    print("日次サマリー")
    print("=" * 60)
    print()

    summary = executor.tracker.calculate_daily_summary(race_date)
    if summary:
        print(f"日付: {summary.date}")
        print(f"購入回数: {summary.total_bets}回")
        print(f"投資額: {summary.total_invested:,}円")
        print(f"払戻額: {summary.total_payout:,}円")
        print(f"収支: {summary.total_profit:+,}円")
        print(f"的中率: {summary.hit_rate:.1f}%")
        print(f"回収率: {summary.recovery_rate:.1f}%")
        print()

        # サマリー保存
        executor.tracker.save_daily_summary(summary)
        print("サイ: 「サマリーを保存しました」")
    print()

    # 状況レポート
    status = executor.get_status_report(race_date)
    print("=" * 60)
    print("実行状況")
    print("=" * 60)
    print(f"総件数: {status['total_records']}件")
    print(f"  - 未実行: {status['pending']}件")
    print(f"  - 実行済み: {status['executed']}件")
    print(f"  - 的中: {status['hit']}件")
    print(f"  - 不的中: {status['miss']}件")
    print()

    print("サイ: 「記録を完了しました」")


if __name__ == '__main__':
    test_executor()

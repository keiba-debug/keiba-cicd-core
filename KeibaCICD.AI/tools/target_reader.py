#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TARGET買い目データ読み込みモジュール

TARGET frontier JVの買い目データCSV（PDyyyymm.CSV）を読み込み、
収支管理に必要な情報を抽出する。

CSVフォーマット仕様:
- 1行 = 1レース分の買い目情報
- フィールド0: レースID（16桁 YYYYMMDDVVKKNNRR）
- フィールド17: 的中払戻金額（円単位）
- フィールド118以降: 買い目詳細レコード（10フィールド単位）
  - [0] 買い目残り件数（初回のみ）
  - [1] 的中フラグ（0=外れ, 1=的中）
  - [2] 馬券種別コード
  - [3] 馬番1
  - [4] 馬番2
  - [5] 馬番3
  - [6] 金額（100円単位）
  - [7] オッズ
  - [8] 空
  - [9] 空
"""

import os
import sys
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# hr_parser は同じディレクトリにある前提
try:
    from hr_parser import get_payout_for_race, check_bet_hit, PayoutInfo
    HR_PARSER_AVAILABLE = True
except ImportError:
    HR_PARSER_AVAILABLE = False


@dataclass
class BetRecord:
    """馬券購入記録"""
    race_id: str  # JRA-VAN 16桁レースID
    bet_type: int  # 券種コード (0=単勝, 1=複勝, etc.)
    bet_type_name: str  # 券種名
    selection: str  # 買い目 (例: "1", "1-2", "1-2-3")
    amount: int  # 購入金額（円）
    odds: float  # オッズ
    is_hit: bool  # 的中フラグ
    payout: int  # 払戻金額（円）


@dataclass
class RaceSummary:
    """レース単位のサマリー"""
    race_id: str
    date: str  # YYYYMMDD
    venue: str  # 競馬場名
    race_number: int  # レース番号
    total_bet: int  # 購入合計（円）
    total_payout: int  # 払戻合計（円）
    profit: int  # 収支（円）
    recovery_rate: float  # 回収率 (%)
    bets: List[BetRecord]
    hits: List[str]  # 的中した券種名リスト
    confirmed: bool = True  # 結果確定済みかどうか（JV-VAN払戻データあり=True）


# 券種コードマッピング
BET_TYPE_MAP = {
    0: "単勝",
    1: "複勝",
    2: "枠連",
    3: "馬連",
    4: "ワイド",
    5: "馬単",
    6: "三連複",
    7: "三連単",
}

# 場コードマッピング
VENUE_MAP = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}


class TargetDataReader:
    """TARGET買い目データ読み込みクラス"""

    def __init__(self, data_root: Optional[str] = None):
        """
        初期化
        
        Args:
            data_root: TARGETデータルートディレクトリ
                      デフォルトは環境変数 JV_DATA_ROOT_DIR または E:\\TFJV
        """
        self.data_root = Path(
            data_root or os.environ.get('JV_DATA_ROOT_DIR', 'E:\\TFJV')
        )
        self.my_data_dir = self.data_root / 'MY_DATA'

    def _read_csv_file(self, file_path: Path) -> List[List[str]]:
        """
        CSVファイルを読み込む（Shift-JIS）
        """
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        rows = []
        try:
            with open(file_path, 'r', encoding='cp932', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    rows.append(row)
        except PermissionError:
            raise PermissionError(
                f"ファイルがロックされています。TARGETを閉じてから再試行してください: {file_path}"
            )
        except Exception as e:
            raise Exception(f"CSV読み込みエラー: {e}")

        return rows

    def _parse_race_id(self, race_id: str) -> Tuple[str, str, int]:
        """
        レースIDをパース
        
        Args:
            race_id: 16桁レースID（YYYYMMDDVVKKNNRR）
            
        Returns:
            (日付, 競馬場名, レース番号)
        """
        if len(race_id) != 16:
            return ("", "", 0)
        
        date = race_id[:8]  # YYYYMMDD
        venue_code = race_id[8:10]  # VV
        race_number = int(race_id[14:16])  # RR
        venue_name = VENUE_MAP.get(venue_code, f"場{venue_code}")
        
        return (date, venue_name, race_number)

    def _parse_bet_records(self, row: List[str], race_id: str) -> List[BetRecord]:
        """
        買い目詳細レコードをパース
        
        構造:
        - フィールド118 = 買い目件数
        - フィールド119以降 = 買い目詳細（10フィールド単位）
          - [0] 的中フラグ（0=外れ, 1=的中）
          - [1] 券種コード
          - [2] 馬番1
          - [3] 馬番2
          - [4] 馬番3
          - [5] 金額（100円単位）
          - [6] オッズ
          - [7-9] 空
        """
        bets = []
        
        if len(row) <= 119:
            return bets
        
        # フィールド118 = 買い目件数
        bet_count_str = row[118].strip() if row[118] else "0"
        bet_count = int(bet_count_str) if bet_count_str.isdigit() else 0
        
        if bet_count == 0:
            return bets
        
        # フィールド119以降を取得
        bet_fields = row[119:]
        
        for bet_idx in range(bet_count):
            offset = bet_idx * 10
            
            if offset + 6 >= len(bet_fields):
                break
            
            # [0] 的中フラグ
            hit_flag_str = bet_fields[offset].strip() if bet_fields[offset] else "0"
            is_hit = hit_flag_str == "1"
            
            # [1] 券種コード
            bet_type_str = bet_fields[offset + 1].strip() if bet_fields[offset + 1] else ""
            if not bet_type_str.isdigit():
                continue
            bet_type = int(bet_type_str)
            if bet_type < 0 or bet_type > 7:
                continue
            
            # [2-4] 馬番
            horse1 = int(bet_fields[offset + 2]) if len(bet_fields) > offset + 2 and bet_fields[offset + 2].strip().isdigit() else 0
            horse2 = int(bet_fields[offset + 3]) if len(bet_fields) > offset + 3 and bet_fields[offset + 3].strip().isdigit() else 0
            horse3 = int(bet_fields[offset + 4]) if len(bet_fields) > offset + 4 and bet_fields[offset + 4].strip().isdigit() else 0
            
            # [5] 金額（100円単位）
            amount_unit = int(bet_fields[offset + 5]) if len(bet_fields) > offset + 5 and bet_fields[offset + 5].strip().isdigit() else 0
            amount = amount_unit * 100
            
            # [6] オッズ
            odds_str = bet_fields[offset + 6].strip() if len(bet_fields) > offset + 6 else ""
            try:
                odds = float(odds_str) if odds_str else 0.0
            except ValueError:
                odds = 0.0
            
            if amount > 0:
                # 買い目文字列を作成
                selection_parts = [str(horse1)]
                if horse2 > 0:
                    selection_parts.append(str(horse2))
                if horse3 > 0:
                    selection_parts.append(str(horse3))
                selection = "-".join(selection_parts)
                
                # 払戻金額を計算（的中時のみ）
                payout = int(amount * odds) if is_hit else 0
                
                bets.append(BetRecord(
                    race_id=race_id,
                    bet_type=bet_type,
                    bet_type_name=BET_TYPE_MAP.get(bet_type, f"不明({bet_type})"),
                    selection=selection,
                    amount=amount,
                    odds=odds,
                    is_hit=is_hit,
                    payout=payout,
                ))
        
        return bets

    def _convert_race_id_for_jvvan(self, race_id: str) -> List[str]:
        """
        TARGETのレースIDをJV-VAN形式に変換（複数候補を返す）
        
        TARGETとJV-VANでレースIDの「日目」が異なる場合があるため、
        複数の候補を生成して検索する
        
        Args:
            race_id: TARGET形式のレースID（16桁）
            
        Returns:
            JV-VAN形式のレースID候補リスト
        """
        if len(race_id) != 16:
            return [race_id]
        
        # YYYYMMDD(8) + VV(2) + KK(2) + NN(2) + RR(2) = 16桁
        base = race_id[:12]  # YYYYMMDDVVKK
        day = race_id[12:14]  # NN (日目)
        race_num = race_id[14:16]  # RR (レース番号)
        
        # 日目の候補を生成（01-08の範囲）
        candidates = []
        try:
            day_int = int(day)
            # 元のID
            candidates.append(race_id)
            # 日目を-1した候補
            if day_int > 1:
                candidates.append(f"{base}{day_int-1:02d}{race_num}")
            # 日目を+1した候補
            if day_int < 8:
                candidates.append(f"{base}{day_int+1:02d}{race_num}")
        except ValueError:
            candidates.append(race_id)
        
        return candidates

    def _verify_bets_with_jvvan(self, bets: List[BetRecord], race_id: str) -> Tuple[List[BetRecord], int, bool]:
        """
        JV-VAN HRレコードと照合して的中判定と払戻金額を修正
        
        Args:
            bets: TARGET CSVからパースした買い目リスト
            race_id: レースID
            
        Returns:
            (修正後の買い目リスト, 合計払戻金額, 結果確定フラグ)
        """
        if not HR_PARSER_AVAILABLE:
            # hr_parser が使えない場合は元のまま返す（未確定扱い）
            return bets, sum(bet.payout for bet in bets if bet.is_hit), False
        
        # JV-VAN形式のレースID候補を生成
        race_id_candidates = self._convert_race_id_for_jvvan(race_id)
        
        payouts = None
        for candidate_id in race_id_candidates:
            payouts = get_payout_for_race(candidate_id)
            if payouts and any(payouts.values()):
                break
        
        if not payouts:
            # 払戻情報が見つからない場合は未確定として返す
            # 予想払戻はそのまま表示するが、confirmedはFalse
            return bets, sum(bet.payout for bet in bets if bet.is_hit), False
        
        # 各買い目をJV-VAN払戻情報と照合
        verified_bets = []
        total_payout = 0
        
        for bet in bets:
            hit_info = check_bet_hit(bet.bet_type, bet.selection, payouts)
            
            if hit_info:
                # 的中！
                # 払戻金額 = JV-VAN払戻金額(100円あたり) × 購入枚数
                tickets = bet.amount // 100
                payout = hit_info.payout * tickets
                total_payout += payout
                
                verified_bet = BetRecord(
                    race_id=bet.race_id,
                    bet_type=bet.bet_type,
                    bet_type_name=bet.bet_type_name,
                    selection=bet.selection,
                    amount=bet.amount,
                    odds=hit_info.payout / 100,  # JV-VAN払戻からオッズを計算
                    is_hit=True,
                    payout=payout,
                )
            else:
                # 外れ
                verified_bet = BetRecord(
                    race_id=bet.race_id,
                    bet_type=bet.bet_type,
                    bet_type_name=bet.bet_type_name,
                    selection=bet.selection,
                    amount=bet.amount,
                    odds=bet.odds,
                    is_hit=False,
                    payout=0,
                )
            
            verified_bets.append(verified_bet)
        
        return verified_bets, total_payout, True  # confirmed=True

    def read_monthly_data(self, year: int, month: int, verify_with_jvvan: bool = True) -> List[RaceSummary]:
        """
        月間の買い目データを読み込む
        
        Args:
            year: 年
            month: 月
            verify_with_jvvan: JV-VAN HRレコードと照合して的中判定を行うか
        """
        filename = f"PD{year}{month:02d}.CSV"
        file_path = self.my_data_dir / filename

        if not file_path.exists():
            return []

        rows = self._read_csv_file(file_path)
        summaries = []

        for row in rows:
            if len(row) < 20:
                continue

            race_id = row[0].strip()
            if not race_id or len(race_id) != 16:
                continue

            date, venue, race_number = self._parse_race_id(race_id)
            
            # 買い目詳細をパース
            bets = self._parse_bet_records(row, race_id)
            
            confirmed = False  # 結果確定フラグ
            if verify_with_jvvan and HR_PARSER_AVAILABLE:
                # JV-VAN HRレコードと照合
                bets, total_payout, confirmed = self._verify_bets_with_jvvan(bets, race_id)
            else:
                # CSVのフィールド17: 的中払戻金額（円単位）
                total_payout = int(float(row[17])) if len(row) > 17 and row[17].strip() else 0
                confirmed = False  # JV-VAN未照合 = 未確定
            
            # 購入合計を計算
            total_bet = sum(bet.amount for bet in bets)
            
            # 的中した券種リストを作成（確定レースのみ）
            hits = list(set(bet.bet_type_name for bet in bets if bet.is_hit)) if confirmed else []
            
            # 収支を計算（未確定の場合は払戻0として扱う）
            if confirmed:
                profit = total_payout - total_bet
                recovery_rate = (total_payout / total_bet * 100) if total_bet > 0 else 0.0
            else:
                # 未確定: 払戻は予想値として保持するが、収支計算には含めない
                profit = -total_bet  # 未確定は購入額のみマイナス
                recovery_rate = 0.0
                total_payout = 0  # 確定していないので払戻は0

            summary = RaceSummary(
                race_id=race_id,
                date=date,
                venue=venue,
                race_number=race_number,
                total_bet=total_bet,
                total_payout=total_payout,
                profit=profit,
                recovery_rate=recovery_rate,
                bets=bets,
                hits=hits,
                confirmed=confirmed,
            )
            summaries.append(summary)

        return summaries

    def get_daily_summary(self, date: str) -> Dict:
        """
        日別サマリーを取得（買い目詳細を含む）
        """
        year = int(date[:4])
        month = int(date[4:6])
        
        filename = f"PD{year}{month:02d}.CSV"
        file_path = self.my_data_dir / filename
        file_exists = file_path.exists()

        summaries = self.read_monthly_data(year, month)
        daily_summaries = [s for s in summaries if s.date == date]

        # 確定レースのみで収支計算
        confirmed_summaries = [s for s in daily_summaries if s.confirmed]
        total_bet = sum(s.total_bet for s in confirmed_summaries)
        total_payout = sum(s.total_payout for s in confirmed_summaries)
        profit = total_payout - total_bet
        recovery_rate = (total_payout / total_bet * 100) if total_bet > 0 else 0.0
        win_count = sum(1 for s in confirmed_summaries if s.total_payout > 0)
        
        # 未確定レースの購入合計（参考情報）
        unconfirmed_summaries = [s for s in daily_summaries if not s.confirmed]
        unconfirmed_bet = sum(s.total_bet for s in unconfirmed_summaries)

        # レース情報を整形（買い目詳細を含む）
        races = []
        for s in daily_summaries:
            # 買い目詳細を変換
            bets = []
            for bet in s.bets:
                bets.append({
                    'bet_type': bet.bet_type_name,
                    'selection': bet.selection,
                    'amount': bet.amount,
                    'odds': bet.odds,
                    'is_hit': bet.is_hit,
                    'payout': bet.payout,
                })
            
            races.append({
                'race_id': s.race_id,  # レースID（16桁）
                'venue': s.venue,
                'race_number': s.race_number,
                'race_name': '',  # APIでintegrated_*.jsonから取得
                'post_time': '',  # APIでintegrated_*.jsonから取得
                'distance': '',   # APIでintegrated_*.jsonから取得
                'track_condition': '',
                'entries': 0,
                'total_bet': s.total_bet,
                'total_payout': s.total_payout if s.confirmed else 0,  # 未確定は0
                'profit': s.profit,
                'recovery_rate': s.recovery_rate,
                'hits': s.hits,
                'bets': bets,  # 買い目詳細を追加
                'confirmed': s.confirmed,  # 確定フラグを追加
            })

        return {
            'date': date,
            'total_bet': total_bet,
            'total_payout': total_payout,
            'profit': profit,
            'recovery_rate': recovery_rate,
            'race_count': len(confirmed_summaries),  # 確定レースのみカウント
            'win_count': win_count,
            'races': races,
            'file_exists': file_exists,
            'has_data': len(daily_summaries) > 0,
            # 未確定レース情報
            'unconfirmed_count': len(unconfirmed_summaries),
            'unconfirmed_bet': unconfirmed_bet,
        }

    def get_monthly_summary(self, year: int, month: int) -> Dict:
        """
        月間サマリーを取得
        """
        filename = f"PD{year}{month:02d}.CSV"
        file_path = self.my_data_dir / filename
        file_exists = file_path.exists()
        
        summaries = self.read_monthly_data(year, month)

        total_bet = sum(s.total_bet for s in summaries)
        total_payout = sum(s.total_payout for s in summaries)
        profit = total_payout - total_bet
        recovery_rate = (total_payout / total_bet * 100) if total_bet > 0 else 0.0

        return {
            'year': year,
            'month': month,
            'total_bet': total_bet,
            'total_payout': total_payout,
            'profit': profit,
            'recovery_rate': recovery_rate,
            'race_count': len(summaries),
            'file_exists': file_exists,
            'has_data': len(summaries) > 0,
        }

    def get_bet_type_stats(self, year: int, month: int) -> Dict[str, Dict]:
        """
        馬券種別の統計を取得
        """
        filename = f"PD{year}{month:02d}.CSV"
        file_path = self.my_data_dir / filename
        file_exists = file_path.exists()
        
        if not file_exists:
            return {
                '_meta': {
                    'file_exists': False,
                    'has_data': False,
                    'race_count': 0,
                }
            }
        
        summaries = self.read_monthly_data(year, month)
        
        # 馬券種別ごとに集計
        stats: Dict[str, Dict] = {}
        
        for summary in summaries:
            for bet in summary.bets:
                bet_type_name = bet.bet_type_name
                
                if bet_type_name not in stats:
                    stats[bet_type_name] = {
                        'bet_type': bet_type_name,
                        'total_bet': 0,
                        'total_payout': 0,
                        'profit': 0,
                        'count': 0,
                        'win_count': 0,
                        'recovery_rate': 0.0,
                        'win_rate': 0.0,
                    }
                
                stats[bet_type_name]['total_bet'] += bet.amount
                stats[bet_type_name]['count'] += 1
                
                if bet.is_hit:
                    stats[bet_type_name]['total_payout'] += bet.payout
                    stats[bet_type_name]['win_count'] += 1
        
        # 回収率・的中率を計算
        for stat in stats.values():
            stat['profit'] = stat['total_payout'] - stat['total_bet']
            stat['recovery_rate'] = (stat['total_payout'] / stat['total_bet'] * 100) if stat['total_bet'] > 0 else 0.0
            stat['win_rate'] = (stat['win_count'] / stat['count'] * 100) if stat['count'] > 0 else 0.0
        
        return {
            '_meta': {
                'file_exists': file_exists,
                'has_data': len(summaries) > 0,
                'race_count': len(summaries),
            },
            **stats
        }


def main():
    """メイン関数"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='TARGET買い目データ読み込み')
    parser.add_argument('--year', type=int, help='年')
    parser.add_argument('--month', type=int, help='月')
    parser.add_argument('--date', type=str, help='日付 (YYYYMMDD)')
    parser.add_argument('--stats', action='store_true', help='馬券種別統計を表示')

    args = parser.parse_args()

    reader = TargetDataReader()

    if args.date:
        summary = reader.get_daily_summary(args.date)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    elif args.stats and args.year and args.month:
        stats = reader.get_bet_type_stats(args.year, args.month)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif args.year and args.month:
        summary = reader.get_monthly_summary(args.year, args.month)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("使用方法:")
        print("  --year YYYY --month MM          月間サマリー")
        print("  --year YYYY --month MM --stats  馬券種別統計")
        print("  --date YYYYMMDD                 日別サマリー")


if __name__ == '__main__':
    main()

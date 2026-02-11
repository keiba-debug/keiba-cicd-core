#!/usr/bin/env python3
"""
Accumulator CLI - 馬の履歴データ蓄積モジュール
Phase1: organized配下のseiseki_*.jsonから直近3走の特徴量を生成・蓄積
"""

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import glob
from collections import defaultdict

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HorseHistoryAccumulator:
    """馬の履歴データ蓄積クラス"""
    
    def __init__(self, base_path: str = "Z:/KEIBA-CICD"):
        self.base_path = Path(base_path)
        self.organized_path = self.base_path / "data" / "organized"
        self.accumulated_path = self.base_path / "data" / "accumulated" / "horses"
        self.accumulated_path.mkdir(parents=True, exist_ok=True)
    
    def backfill(self, date_str: str, runs: int = 3, source: str = "organized") -> None:
        """
        指定日の出走馬に対して直近N走の履歴データをバックフィル
        
        Args:
            date_str: 対象日（YYYY/MM/DD形式）
            runs: 収集する直近走数（デフォルト3）
            source: データソース（Phase1は"organized"固定）
        """
        logger.info(f"Starting backfill for {date_str}, runs={runs}, source={source}")
        
        # 日付パース
        target_date = datetime.strptime(date_str, "%Y/%m/%d")
        
        # Step 1: 対象日の出走馬IDを収集
        horse_ids = self._collect_target_horses(target_date)
        logger.info(f"Found {len(horse_ids)} horses for {date_str}")
        
        # Step 2: 各馬について直近N走を収集
        for horse_id in horse_ids:
            try:
                history = self._collect_horse_history(horse_id, target_date, runs)
                if history:
                    features = self._calculate_features(history)
                    self._save_horse_data(horse_id, history, features)
                    logger.debug(f"Processed horse {horse_id}: {len(history)} races found")
            except Exception as e:
                logger.error(f"Error processing horse {horse_id}: {e}")
    
    def _collect_target_horses(self, target_date: datetime) -> List[str]:
        """対象日の出走馬IDを収集"""
        horse_ids = set()
        
        # integrated_*.jsonから馬IDを収集
        date_path = target_date.strftime("%Y/%m/%d").replace("/", "\\")
        pattern = str(self.organized_path / date_path / "*" / "integrated_*.json")
        
        for json_file in glob.glob(pattern):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # entriesから馬IDを抽出
                for entry in data.get('entries', []):
                    horse_id = entry.get('horse_id')
                    if horse_id:
                        horse_ids.add(str(horse_id))
            except Exception as e:
                logger.error(f"Error reading {json_file}: {e}")
        
        return list(horse_ids)
    
    def _collect_horse_history(self, horse_id: str, target_date: datetime, runs: int) -> List[Dict]:
        """馬の直近N走の履歴を収集"""
        history = []
        
        # 過去180日間のデータを走査（十分な期間）
        for days_back in range(1, 180):
            check_date = target_date - timedelta(days=days_back)
            date_path = check_date.strftime("%Y/%m/%d").replace("/", "\\")
            
            # seiseki_*.jsonファイルを探索
            pattern = str(self.organized_path / date_path / "*" / "seiseki_*.json")
            
            for json_file in glob.glob(pattern):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 該当馬のレコードを探す
                    for record in data:
                        if self._match_horse(record, horse_id):
                            race_info = self._extract_race_info(record, check_date)
                            if race_info:
                                history.append(race_info)
                                
                                # 必要数に達したら終了
                                if len(history) >= runs:
                                    return history
                except Exception as e:
                    logger.error(f"Error reading {json_file}: {e}")
        
        return history
    
    def _match_horse(self, record: Dict, horse_id: str) -> bool:
        """レコードが対象馬かどうか判定"""
        # 馬IDが一致するか確認（複数の形式に対応）
        record_horse_id = record.get('horse_id') or record.get('馬ID') or record.get('id')
        if record_horse_id:
            return str(record_horse_id) == horse_id
        
        # TODO: 馬名での照合も実装可能
        return False
    
    def _extract_race_info(self, record: Dict, race_date: datetime) -> Optional[Dict]:
        """レコードからレース情報を抽出"""
        try:
            return {
                'date': race_date.strftime("%Y-%m-%d"),
                'finish_position': record.get('着順') or record.get('finish_position'),
                'last_3f': record.get('上り3F') or record.get('last_3f'),
                'passing_orders': record.get('通過順位') or record.get('passing_orders', []),
                'course': record.get('コース') or record.get('course'),
                'distance': record.get('距離') or record.get('distance'),
                'odds': record.get('オッズ') or record.get('odds'),
                'popularity': record.get('人気') or record.get('popularity'),
                'time': record.get('タイム') or record.get('time')
            }
        except Exception as e:
            logger.error(f"Error extracting race info: {e}")
            return None
    
    def _calculate_features(self, history: List[Dict]) -> Dict[str, Any]:
        """履歴から特徴量を算出"""
        features = {}
        
        # last3f_mean_3: 直近3走の上り3F平均
        last_3fs = []
        for race in history[:3]:
            if race.get('last_3f'):
                try:
                    # 時間形式を秒数に変換（例: "35.1" → 35.1）
                    last_3f = float(str(race['last_3f']).replace(':', '.'))
                    last_3fs.append(last_3f)
                except:
                    pass
        
        if last_3fs:
            features['last3f_mean_3'] = round(sum(last_3fs) / len(last_3fs), 2)
        
        # passing_style: 通過順位から脚質タイプを推定
        passing_positions = []
        for race in history[:3]:
            orders = race.get('passing_orders', [])
            if orders:
                passing_positions.append(orders)
        
        if passing_positions:
            features['passing_style'] = self._estimate_passing_style(passing_positions)
        
        # course_distance_perf: 同コース×距離の成績
        features['course_distance_perf'] = self._calculate_course_distance_perf(history)
        
        # recency_days: 最終出走からの日数
        if history:
            last_race_date = datetime.strptime(history[0]['date'], "%Y-%m-%d")
            features['recency_days'] = (datetime.now() - last_race_date).days
        
        # value_flag: 簡易割安判定
        features['value_flag'] = self._calculate_value_flag(history)
        
        return features
    
    def _estimate_passing_style(self, passing_positions: List[List]) -> str:
        """通過順位から脚質タイプを推定"""
        # 簡易版：前半と後半の平均順位で判定
        early_positions = []
        late_positions = []
        
        for positions in passing_positions:
            if len(positions) >= 2:
                early_positions.append(positions[0])
                late_positions.append(positions[-1])
        
        if not early_positions:
            return "不明"
        
        avg_early = sum(early_positions) / len(early_positions)
        avg_late = sum(late_positions) / len(late_positions)
        
        if avg_early <= 3:
            return "逃げ" if avg_early <= 1.5 else "先行"
        elif avg_late < avg_early - 2:
            return "差し"
        elif avg_late < avg_early:
            return "差し"
        else:
            return "追込" if avg_early > 8 else "中団"
    
    def _calculate_course_distance_perf(self, history: List[Dict]) -> Dict:
        """同コース×距離の成績を集計"""
        perf = {'runs': 0, 'win': 0, 'in3': 0}
        
        # 簡易版：全レースを集計（本来は同コース×距離でフィルタリング）
        for race in history:
            position = race.get('finish_position')
            if position:
                try:
                    pos = int(position)
                    perf['runs'] += 1
                    if pos == 1:
                        perf['win'] += 1
                    if pos <= 3:
                        perf['in3'] += 1
                except:
                    pass
        
        return perf
    
    def _calculate_value_flag(self, history: List[Dict]) -> str:
        """簡易割安判定"""
        # 簡易版：近走の着順と人気の乖離で判定
        recent_performances = []
        
        for race in history[:3]:
            position = race.get('finish_position')
            popularity = race.get('popularity')
            
            if position and popularity:
                try:
                    pos = int(position)
                    pop = int(popularity)
                    # 人気より着順が良ければプラス評価
                    recent_performances.append(pop - pos)
                except:
                    pass
        
        if recent_performances:
            avg_perf = sum(recent_performances) / len(recent_performances)
            if avg_perf > 2:
                return "割安"
            elif avg_perf > 0:
                return "やや割安"
            elif avg_perf < -2:
                return "割高"
            else:
                return "妥当"
        
        return "不明"
    
    def _save_horse_data(self, horse_id: str, history: List[Dict], features: Dict) -> None:
        """馬のデータを保存"""
        output_file = self.accumulated_path / f"{horse_id}.json"
        
        data = {
            'horse_id': horse_id,
            'updated_at': datetime.now().isoformat(),
            'history': history,
            'history_features': features
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Saved horse data to {output_file}")


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='Accumulator CLI - 馬の履歴データ蓄積')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # horse-history コマンド
    horse_parser = subparsers.add_parser('horse-history', help='Horse history accumulation')
    horse_subparsers = horse_parser.add_subparsers(dest='subcommand', help='Subcommands')
    
    # backfill サブコマンド
    backfill_parser = horse_subparsers.add_parser('backfill', help='Backfill horse history')
    backfill_parser.add_argument('--date', required=True, help='Target date (YYYY/MM/DD)')
    backfill_parser.add_argument('--runs', type=int, default=3, help='Number of recent runs to collect')
    backfill_parser.add_argument('--source', default='organized', help='Data source')
    
    args = parser.parse_args()
    
    if args.command == 'horse-history' and args.subcommand == 'backfill':
        accumulator = HorseHistoryAccumulator()
        accumulator.backfill(args.date, args.runs, args.source)
        logger.info("Backfill completed")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
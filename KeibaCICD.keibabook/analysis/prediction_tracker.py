#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
予想記録・収支管理システム
KeibaCICD競馬予想チーム - LEARNER エージェント用
予想と結果を記録し、継続的な改善に活用する
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime, date
import sqlite3
import logging
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

@dataclass
class Prediction:
    """予想記録クラス"""
    prediction_id: str          # 予想ID
    race_id: str               # レースID
    race_name: str             # レース名
    race_date: str             # レース日
    horse_number: int          # 馬番
    horse_name: str            # 馬名
    bet_type: str              # 券種（単勝、複勝、馬連など）
    bet_amount: float          # 投資額
    odds: float                # オッズ
    expected_value: float      # 期待値
    confidence: float          # 確信度（0-1）
    created_at: str            # 作成日時
    
@dataclass
class Result:
    """結果記録クラス"""
    result_id: str             # 結果ID
    prediction_id: str         # 予想ID
    race_id: str               # レースID
    finishing_position: int    # 着順
    is_hit: bool              # 的中フラグ
    payout: float             # 払戻金額
    actual_odds: float        # 実際のオッズ
    profit_loss: float        # 損益
    updated_at: str           # 更新日時

@dataclass
class Performance:
    """パフォーマンス統計クラス"""
    period: str               # 期間
    total_races: int          # 総レース数
    total_bets: int           # 総投資数
    total_investment: float   # 総投資額
    total_return: float       # 総払戻額
    profit_loss: float        # 総損益
    roi: float               # ROI（%）
    hit_rate: float          # 的中率（%）
    avg_odds: float          # 平均オッズ
    max_profit: float        # 最大利益
    max_loss: float          # 最大損失

class PredictionTracker:
    """予想記録・収支管理クラス"""
    
    def __init__(self, db_path: str = None):
        """
        初期化
        Args:
            db_path: データベースファイルパス
        """
        if db_path is None:
            db_dir = Path("C:/source/git-h.fukuda1207/_keiba/keiba-cicd-core/KeibaCICD.keibabook/analysis/db")
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "predictions.db"
            
        self.db_path = str(db_path)
        self._init_database()
        
    def _init_database(self):
        """データベースを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 予想テーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                race_id TEXT NOT NULL,
                race_name TEXT,
                race_date TEXT,
                horse_number INTEGER,
                horse_name TEXT,
                bet_type TEXT,
                bet_amount REAL,
                odds REAL,
                expected_value REAL,
                confidence REAL,
                created_at TEXT
            )
        ''')
        
        # 結果テーブル
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                result_id TEXT PRIMARY KEY,
                prediction_id TEXT,
                race_id TEXT NOT NULL,
                finishing_position INTEGER,
                is_hit INTEGER,
                payout REAL,
                actual_odds REAL,
                profit_loss REAL,
                updated_at TEXT,
                FOREIGN KEY (prediction_id) REFERENCES predictions (prediction_id)
            )
        ''')
        
        # インデックス作成
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_race_id ON predictions (race_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_race_date ON predictions (race_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prediction_id ON results (prediction_id)')
        
        conn.commit()
        conn.close()
        
    def add_prediction(self, prediction: Prediction) -> str:
        """
        予想を記録
        Args:
            prediction: 予想データ
        Returns:
            予想ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO predictions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                prediction.prediction_id,
                prediction.race_id,
                prediction.race_name,
                prediction.race_date,
                prediction.horse_number,
                prediction.horse_name,
                prediction.bet_type,
                prediction.bet_amount,
                prediction.odds,
                prediction.expected_value,
                prediction.confidence,
                prediction.created_at
            ))
            conn.commit()
            logger.info(f"予想を記録しました: {prediction.prediction_id}")
            return prediction.prediction_id
            
        except sqlite3.IntegrityError:
            logger.warning(f"予想は既に存在します: {prediction.prediction_id}")
            return prediction.prediction_id
            
        finally:
            conn.close()
            
    def add_result(self, result: Result) -> str:
        """
        結果を記録
        Args:
            result: 結果データ
        Returns:
            結果ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.result_id,
                result.prediction_id,
                result.race_id,
                result.finishing_position,
                int(result.is_hit),
                result.payout,
                result.actual_odds,
                result.profit_loss,
                result.updated_at
            ))
            conn.commit()
            logger.info(f"結果を記録しました: {result.result_id}")
            return result.result_id
            
        except sqlite3.IntegrityError:
            logger.warning(f"結果は既に存在します: {result.result_id}")
            return result.result_id
            
        finally:
            conn.close()
            
    def get_performance(self, start_date: str = None, end_date: str = None) -> Performance:
        """
        パフォーマンス統計を取得
        Args:
            start_date: 開始日（YYYY-MM-DD）
            end_date: 終了日（YYYY-MM-DD）
        Returns:
            パフォーマンス統計
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 期間指定のSQL条件
        date_condition = ""
        params = []
        if start_date and end_date:
            date_condition = "WHERE p.race_date BETWEEN ? AND ?"
            params = [start_date, end_date]
        elif start_date:
            date_condition = "WHERE p.race_date >= ?"
            params = [start_date]
        elif end_date:
            date_condition = "WHERE p.race_date <= ?"
            params = [end_date]
            
        # 統計情報を取得
        query = f'''
            SELECT 
                COUNT(DISTINCT p.race_id) as total_races,
                COUNT(p.prediction_id) as total_bets,
                SUM(p.bet_amount) as total_investment,
                COALESCE(SUM(r.payout), 0) as total_return,
                COALESCE(SUM(r.profit_loss), 0) as profit_loss,
                AVG(CASE WHEN r.is_hit = 1 THEN 100.0 ELSE 0 END) as hit_rate,
                AVG(p.odds) as avg_odds,
                MAX(COALESCE(r.profit_loss, -p.bet_amount)) as max_profit,
                MIN(COALESCE(r.profit_loss, -p.bet_amount)) as max_loss
            FROM predictions p
            LEFT JOIN results r ON p.prediction_id = r.prediction_id
            {date_condition}
        '''
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        
        if row and row[2]:  # total_investmentが存在する場合
            roi = ((row[3] / row[2]) - 1) * 100 if row[2] > 0 else 0
            
            period = f"{start_date or '開始'} ~ {end_date or '現在'}"
            
            return Performance(
                period=period,
                total_races=row[0] or 0,
                total_bets=row[1] or 0,
                total_investment=row[2] or 0,
                total_return=row[3] or 0,
                profit_loss=row[4] or 0,
                roi=roi,
                hit_rate=row[5] or 0,
                avg_odds=row[6] or 0,
                max_profit=row[7] or 0,
                max_loss=row[8] or 0
            )
        else:
            return Performance(
                period=f"{start_date or '開始'} ~ {end_date or '現在'}",
                total_races=0,
                total_bets=0,
                total_investment=0,
                total_return=0,
                profit_loss=0,
                roi=0,
                hit_rate=0,
                avg_odds=0,
                max_profit=0,
                max_loss=0
            )
            
    def get_recent_predictions(self, limit: int = 10) -> List[Dict]:
        """
        最近の予想を取得
        Args:
            limit: 取得件数
        Returns:
            予想リスト
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, r.is_hit, r.payout, r.profit_loss
            FROM predictions p
            LEFT JOIN results r ON p.prediction_id = r.prediction_id
            ORDER BY p.created_at DESC
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
        
    def generate_report(self, period_days: int = 30) -> str:
        """
        収支レポートを生成
        Args:
            period_days: レポート期間（日数）
        Returns:
            レポート文字列
        """
        # 期間計算
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - datetime.timedelta(days=period_days)).strftime('%Y-%m-%d')
        
        # パフォーマンス取得
        perf = self.get_performance(start_date, end_date)
        
        # レポート生成
        report = []
        report.append("=" * 60)
        report.append(f"KeibaCICD 収支レポート ({perf.period})")
        report.append("=" * 60)
        report.append("")
        
        report.append("【総合成績】")
        report.append(f"・対象レース数: {perf.total_races}レース")
        report.append(f"・総投資回数: {perf.total_bets}回")
        report.append(f"・総投資額: {perf.total_investment:,.0f}円")
        report.append(f"・総払戻額: {perf.total_return:,.0f}円")
        report.append("")
        
        report.append("【収支】")
        if perf.profit_loss >= 0:
            report.append(f"・総損益: +{perf.profit_loss:,.0f}円 ✨")
        else:
            report.append(f"・総損益: {perf.profit_loss:,.0f}円")
        report.append(f"・ROI: {perf.roi:+.1f}%")
        report.append("")
        
        report.append("【的中率・オッズ】")
        report.append(f"・的中率: {perf.hit_rate:.1f}%")
        report.append(f"・平均オッズ: {perf.avg_odds:.1f}倍")
        report.append("")
        
        report.append("【最大値】")
        report.append(f"・最大利益: +{perf.max_profit:,.0f}円")
        report.append(f"・最大損失: {perf.max_loss:,.0f}円")
        report.append("")
        
        # 最近の予想
        recent = self.get_recent_predictions(5)
        if recent:
            report.append("【最近の予想結果】")
            for pred in recent:
                hit_mark = "○" if pred.get('is_hit') else "×" if pred.get('is_hit') is not None else "－"
                report.append(
                    f"{hit_mark} {pred['race_date']} {pred['race_name'][:10]} "
                    f"{pred['horse_number']}番 {pred['bet_type']} "
                    f"{pred['bet_amount']:.0f}円"
                )
            
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)

def main():
    """メイン処理（テスト用）"""
    tracker = PredictionTracker()
    
    # サンプル予想を追加
    prediction = Prediction(
        prediction_id=f"PRED_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        race_id="202504050111",
        race_name="紫苑ステークス(G3)",
        race_date="2025-09-06",
        horse_number=3,
        horse_name="サンプルホース",
        bet_type="単勝",
        bet_amount=1000,
        odds=5.5,
        expected_value=1.32,
        confidence=0.75,
        created_at=datetime.now().isoformat()
    )
    
    pred_id = tracker.add_prediction(prediction)
    
    # レポート生成
    report = tracker.generate_report(30)
    print(report)
    
    logger.info("予想記録システムの初期化が完了しました")

if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
期待値計算システム
KeibaCICD競馬予想チーム - INVESTOR エージェント用
期待値（オッズ×勝率）に基づく合理的な投資判断を行う
"""

import json
import os
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

@dataclass
class Horse:
    """馬情報クラス"""
    number: int          # 馬番
    name: str           # 馬名
    odds: float         # オッズ
    probability: float  # 勝率（推定）
    expected_value: float  # 期待値
    jockey: str         # 騎手名
    weight: float       # 斤量
    popularity: int     # 人気順位

@dataclass
class RaceAnalysis:
    """レース分析結果クラス"""
    race_id: str
    race_name: str
    race_date: str
    horses: List[Horse]
    recommended_bets: List[Dict]
    total_investment: float
    expected_return: float

class ExpectedValueCalculator:
    """期待値計算クラス"""
    
    def __init__(self, kelly_ratio: float = 0.25):
        """
        初期化
        Args:
            kelly_ratio: Kelly基準の適用率（0.25 = 1/4 Kelly）
        """
        self.kelly_ratio = kelly_ratio
        self.min_expected_value = 1.2  # 最小期待値（120%以上）
        self.max_bet_ratio = 0.05      # 1レースあたりの最大投資率
        
    def calculate_win_probability(self, horse_data: Dict) -> float:
        """
        馬の勝率を推定する
        簡易版：人気とオッズから逆算
        
        Args:
            horse_data: 馬のデータ
        Returns:
            推定勝率（0-1）
        """
        # オッズから市場の期待勝率を逆算
        odds = horse_data.get('odds', 100.0)
        if odds <= 0:
            return 0.0
            
        # 控除率を考慮した市場確率
        market_probability = 0.8 / odds  # JRA控除率約20%
        
        # 人気による補正
        popularity = horse_data.get('popularity', 10)
        if popularity <= 3:
            # 上位人気は市場確率をやや上方修正
            adjusted_probability = market_probability * 1.1
        elif popularity >= 8:
            # 下位人気は市場確率をやや下方修正
            adjusted_probability = market_probability * 0.9
        else:
            adjusted_probability = market_probability
            
        # 0-1の範囲に収める
        return min(max(adjusted_probability, 0.0), 1.0)
        
    def calculate_expected_value(self, odds: float, probability: float) -> float:
        """
        期待値を計算する
        
        Args:
            odds: オッズ
            probability: 勝率
        Returns:
            期待値
        """
        return odds * probability
        
    def calculate_kelly_bet(self, 
                          bankroll: float,
                          odds: float,
                          probability: float) -> float:
        """
        Kelly基準による最適投資額を計算
        
        Args:
            bankroll: 総資金
            odds: オッズ
            probability: 勝率
        Returns:
            推奨投資額
        """
        # Kelly公式: f = (p * b - q) / b
        # f: 資金の投資割合
        # p: 勝率
        # b: オッズ - 1
        # q: 負ける確率 (1 - p)
        
        if odds <= 1 or probability <= 0:
            return 0
            
        b = odds - 1
        q = 1 - probability
        
        kelly_fraction = (probability * b - q) / b
        
        # Kelly比率を適用（リスク軽減）
        adjusted_fraction = kelly_fraction * self.kelly_ratio
        
        # 最大投資率を超えないように制限
        final_fraction = min(adjusted_fraction, self.max_bet_ratio)
        
        # 負の値の場合は投資しない
        if final_fraction <= 0:
            return 0
            
        return bankroll * final_fraction
        
    def analyze_race(self, race_data: Dict, bankroll: float = 10000) -> RaceAnalysis:
        """
        レースを分析して投資推奨を作成
        
        Args:
            race_data: レースデータ
            bankroll: 総資金
        Returns:
            レース分析結果
        """
        horses = []
        
        # 各馬の期待値を計算
        for horse_data in race_data.get('horses', []):
            odds = horse_data.get('odds', 0)
            if odds <= 0:
                continue
                
            probability = self.calculate_win_probability(horse_data)
            expected_value = self.calculate_expected_value(odds, probability)
            
            horse = Horse(
                number=horse_data.get('number', 0),
                name=horse_data.get('name', ''),
                odds=odds,
                probability=probability,
                expected_value=expected_value,
                jockey=horse_data.get('jockey', ''),
                weight=horse_data.get('weight', 0),
                popularity=horse_data.get('popularity', 0)
            )
            horses.append(horse)
            
        # 期待値順にソート
        horses.sort(key=lambda x: x.expected_value, reverse=True)
        
        # 投資推奨を作成
        recommended_bets = []
        total_investment = 0
        expected_return = 0
        
        for horse in horses:
            if horse.expected_value < self.min_expected_value:
                continue
                
            bet_amount = self.calculate_kelly_bet(
                bankroll - total_investment,
                horse.odds,
                horse.probability
            )
            
            if bet_amount >= 100:  # 最小投資額100円
                # 100円単位に丸める
                bet_amount = round(bet_amount / 100) * 100
                
                recommended_bets.append({
                    'horse_number': horse.number,
                    'horse_name': horse.name,
                    'bet_type': '単勝',
                    'amount': bet_amount,
                    'odds': horse.odds,
                    'expected_value': horse.expected_value,
                    'expected_return': bet_amount * horse.odds * horse.probability
                })
                
                total_investment += bet_amount
                expected_return += bet_amount * horse.odds * horse.probability
                
        return RaceAnalysis(
            race_id=race_data.get('race_id', ''),
            race_name=race_data.get('race_name', ''),
            race_date=race_data.get('date', ''),
            horses=horses,
            recommended_bets=recommended_bets,
            total_investment=total_investment,
            expected_return=expected_return
        )
        
    def generate_report(self, analysis: RaceAnalysis) -> str:
        """
        分析レポートを生成
        
        Args:
            analysis: レース分析結果
        Returns:
            レポート文字列
        """
        report = []
        report.append(f"=== {analysis.race_name} 期待値分析レポート ===")
        report.append(f"レースID: {analysis.race_id}")
        report.append(f"開催日: {analysis.race_date}")
        report.append("")
        
        report.append("【期待値上位馬】")
        for i, horse in enumerate(analysis.horses[:5], 1):
            report.append(
                f"{i}. {horse.number:2d}番 {horse.name:15s} "
                f"オッズ:{horse.odds:5.1f} "
                f"推定勝率:{horse.probability:.1%} "
                f"期待値:{horse.expected_value:.2f}"
            )
        report.append("")
        
        if analysis.recommended_bets:
            report.append("【推奨投資】")
            for bet in analysis.recommended_bets:
                report.append(
                    f"・{bet['horse_number']:2d}番 {bet['horse_name']:15s} "
                    f"{bet['bet_type']} {bet['amount']:,}円 "
                    f"(期待値:{bet['expected_value']:.2f})"
                )
            report.append("")
            report.append(f"総投資額: {analysis.total_investment:,.0f}円")
            report.append(f"期待収益: {analysis.expected_return:,.0f}円")
            report.append(f"期待ROI: {(analysis.expected_return/analysis.total_investment - 1)*100:.1f}%")
        else:
            report.append("【推奨投資】")
            report.append("期待値基準を満たす馬がいません")
            
        return "\n".join(report)

def main():
    """メイン処理"""
    # サンプルデータ（実際はスクレイピングデータを使用）
    sample_race = {
        'race_id': '202504050111',
        'race_name': '紫苑ステークス(G3)',
        'date': '2025-09-06',
        'horses': [
            {'number': 1, 'name': 'サンプルホースA', 'odds': 3.5, 'popularity': 1, 'jockey': '武豊'},
            {'number': 2, 'name': 'サンプルホースB', 'odds': 5.2, 'popularity': 2, 'jockey': 'ルメール'},
            {'number': 3, 'name': 'サンプルホースC', 'odds': 8.7, 'popularity': 3, 'jockey': '川田'},
            {'number': 4, 'name': 'サンプルホースD', 'odds': 15.3, 'popularity': 5, 'jockey': '池添'},
            {'number': 5, 'name': 'サンプルホースE', 'odds': 25.6, 'popularity': 7, 'jockey': '横山武'},
        ]
    }
    
    # 期待値計算
    calculator = ExpectedValueCalculator()
    analysis = calculator.analyze_race(sample_race, bankroll=10000)
    
    # レポート生成
    report = calculator.generate_report(analysis)
    print(report)
    
    # 結果をJSONファイルに保存
    output_dir = "C:\\source\\git-h.fukuda1207\\_keiba\\keiba-cicd-core\\KeibaCICD.keibabook\\analysis\\results"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(
        output_dir,
        f"analysis_{analysis.race_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'race_id': analysis.race_id,
            'race_name': analysis.race_name,
            'race_date': analysis.race_date,
            'horses': [
                {
                    'number': h.number,
                    'name': h.name,
                    'odds': h.odds,
                    'probability': h.probability,
                    'expected_value': h.expected_value
                } for h in analysis.horses
            ],
            'recommended_bets': analysis.recommended_bets,
            'total_investment': analysis.total_investment,
            'expected_return': analysis.expected_return
        }, f, ensure_ascii=False, indent=2)
        
    logger.info(f"分析結果を保存しました: {output_file}")

if __name__ == "__main__":
    main()
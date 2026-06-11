"""較正モジュール (Session 150)

OddsConditionedCalibrator: P複勝モデルの生スコアを単勝オッズ条件で較正する後処理層。
"""
from ml.calibration.odds_conditioned import OddsConditionedCalibrator

__all__ = ["OddsConditionedCalibrator"]

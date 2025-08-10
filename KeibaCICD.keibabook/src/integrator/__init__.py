"""
レースデータ統合モジュール

出走表、調教、厩舎談話、成績データを統合して
分析しやすい形式で提供します。
"""

from .race_data_integrator import RaceDataIntegrator

__all__ = ['RaceDataIntegrator']
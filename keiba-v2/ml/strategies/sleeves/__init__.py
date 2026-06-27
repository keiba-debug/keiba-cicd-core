# -*- coding: utf-8 -*-
"""買い目スリーブ (sleeve) パッケージ — スリーブ・オーケストレーション (Session 176)。

各スリーブ = 独立したエッジ・サイザー・隔離口座を持つ「純粋な買い目生成器」。
投票/タイミング/lock 等の安全機構は持たず、Orchestrator が1箇所に集約する。
正本設計 = docs/sleeve_orchestration_design.md。
"""
from ml.strategies.sleeves.base import Sleeve, SleeveDisplay  # noqa: F401
from ml.strategies.sleeves.registry import SLEEVES, enabled_sleeves, get_sleeve  # noqa: F401

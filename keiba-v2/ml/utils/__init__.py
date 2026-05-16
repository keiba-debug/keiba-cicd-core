"""ML共通ユーティリティ群

Phase 0 (Session 122) でリファクタ。 ml/ 配下に散在していた
ROI計算/セグメント分割/障害フィルタ/backtest_cacheローダー/race_*.json走査
を集約。

Modules:
    filters         — 障害除外/最小サンプル/win_only/selective フィルタ
    segments        — bin_odds/bin_runners/bin_gap/bin_ev/bin_distance/bin_month
    roi             — calc_roi/bootstrap_ci/sharpe/sortino/max_drawdown/brier/ece
    backtest_cache  — load_backtest_cache/flatten_to_df/cache_to_predictions
    race_io         — iter_date_dirs/iter_predictions/load_race_results
"""

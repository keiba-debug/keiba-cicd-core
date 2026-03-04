#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
バンクロールシミュレーター

backtest_cache.json から戦略別×フィルタ別のバンクロールシミュレーションを実行。
モンテカルロ法（ブートストラップ）で信頼区間・破産確率を算出。

Usage:
    python -m ml.bankroll_simulator [--initial 50000] [--mc 1000]
"""

import json
import sys
import random
import math
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Literal

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from core.config import data_root

DATA3 = Path(data_root())
CACHE_PATH = DATA3 / "ml" / "backtest_cache.json"
REPORT_PATH = DATA3 / "ml" / "bankroll_sim_report.md"


# ============================================================
# データ構造
# ============================================================

@dataclass
class Bet:
    """抽出済みベット（1行=1馬）"""
    date: str
    race_id: str
    umaban: int
    horse_name: str
    odds: float
    place_odds_min: float
    is_win: int
    is_top3: int
    win_ev: float
    ar_deviation: float
    predicted_margin: float
    rank_w: int
    win_vb_gap: int


@dataclass
class SimConfig:
    """シミュレーション設定"""
    name: str
    initial_balance: int
    sizing: Literal['fixed', 'proportional', 'kelly', 'tiered_ev']
    # Fixed
    unit_amount: int = 500
    # Proportional
    bet_pct: float = 2.0
    # Kelly
    kelly_fraction: float = 0.25
    kelly_cap: float = 0.10
    # Tiered EV
    ev_tiers: list = field(default_factory=lambda: [(2.0, 3), (1.5, 2), (1.3, 1)])
    base_unit: int = 500
    # Common
    min_bet: int = 100


@dataclass
class SimResult:
    """1回のシミュレーション結果"""
    final_balance: int
    growth_pct: float
    max_dd_pct: float
    min_balance: int
    total_wagered: int
    total_returned: int
    roi: float
    num_bets: int
    num_wins: int
    history: list  # balance推移


@dataclass
class MCResult:
    """モンテカルロ結果"""
    config_name: str
    filter_name: str
    num_bets: int
    num_trials: int
    # Deterministic (original order)
    det_result: SimResult
    # Monte Carlo percentiles
    final_p5: int
    final_p50: int
    final_p95: int
    growth_p50: float
    max_dd_p50: float
    max_dd_p95: float
    bust_rate: float  # % of trials where min_balance < initial * 0.5
    sharpe: float
    # Monthly P&L (deterministic)
    monthly_pnl: dict


# ============================================================
# フィルタ定義
# ============================================================

FILTERS = {
    "intersection": {
        "label": "Intersection (推奨)",
        "fn": lambda e: (
            e.get('rank_w') == 1
            and e.get('win_vb_gap', 0) >= 4
            and e.get('win_ev', 0) >= 1.3
            and e.get('predicted_margin', 999) <= 60
        ),
    },
    "simple": {
        "label": "Simple (gap>=4)",
        "fn": lambda e: (
            e.get('rank_w') == 1
            and e.get('win_vb_gap', 0) >= 4
        ),
    },
    "ev_strict": {
        "label": "EV Strict (EV>=1.3 rank<=2)",
        "fn": lambda e: (
            e.get('win_ev', 0) >= 1.3
            and e.get('ar_deviation', 0) >= 50
            and e.get('rank_w', 99) <= 2
        ),
    },
    "aggressive": {
        "label": "Aggressive (EV>=1.5 gap>=5)",
        "fn": lambda e: (
            e.get('rank_w') == 1
            and e.get('win_vb_gap', 0) >= 5
            and e.get('win_ev', 0) >= 1.5
        ),
    },
}


# ============================================================
# ベット抽出
# ============================================================

def load_cache() -> list:
    """backtest_cache.jsonを読み込み"""
    print(f"Loading {CACHE_PATH}...")
    with open(CACHE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"  {len(data)} races loaded")
    return data


def extract_bets(cache: list, filter_name: str) -> list[Bet]:
    """フィルタ条件に合うベットを抽出（日付順）"""
    fn = FILTERS[filter_name]["fn"]
    bets = []

    for race in cache:
        race_id = str(race['race_id'])
        date_str = f"{race_id[:4]}/{race_id[4:6]}/{race_id[6:8]}"

        for e in race['entries']:
            if fn(e):
                place_odds = e.get('place_odds_min') or (e.get('odds', 1) / 3.5)
                bets.append(Bet(
                    date=date_str,
                    race_id=race_id,
                    umaban=e['umaban'],
                    horse_name=e.get('horse_name', ''),
                    odds=e['odds'],
                    place_odds_min=place_odds,
                    is_win=e['is_win'],
                    is_top3=e['is_top3'],
                    win_ev=e.get('win_ev', 0),
                    ar_deviation=e.get('ar_deviation', 50),
                    predicted_margin=e.get('predicted_margin', 50),
                    rank_w=e.get('rank_w', 99),
                    win_vb_gap=e.get('win_vb_gap', 0),
                ))

    # 日付順ソート
    bets.sort(key=lambda b: (b.date, b.race_id, b.umaban))
    return bets


# ============================================================
# ベットサイズ計算
# ============================================================

def calc_bet_size(config: SimConfig, balance: int, bet: Bet) -> int:
    """戦略に応じたベットサイズを計算（100円単位）"""
    if config.sizing == 'fixed':
        raw = config.unit_amount

    elif config.sizing == 'proportional':
        raw = balance * config.bet_pct / 100

    elif config.sizing == 'kelly':
        # Kelly criterion: f = (p*b - q) / b where b=odds-1, p=implied_prob from EV
        # Simplified: f = (EV - 1) / (odds - 1)
        ev = bet.win_ev
        odds = bet.odds
        if odds > 1 and ev > 1:
            f = (ev - 1) / (odds - 1)
            f = min(f, config.kelly_cap)  # cap
            f *= config.kelly_fraction  # fractional Kelly
            raw = balance * f
        else:
            raw = config.min_bet

    elif config.sizing == 'tiered_ev':
        multiplier = 1
        for ev_threshold, mult in sorted(config.ev_tiers, key=lambda x: -x[0]):
            if bet.win_ev >= ev_threshold:
                multiplier = mult
                break
        raw = config.base_unit * multiplier

    else:
        raw = config.min_bet

    # 100円単位に丸め、最低bet保証
    amount = max(config.min_bet, int(raw / 100) * 100)
    # バンクロール超過防止（最大残高の20%）
    amount = min(amount, int(balance * 0.2 / 100) * 100)
    return max(config.min_bet, amount)


# ============================================================
# シミュレーション実行
# ============================================================

def simulate_once(bets: list[Bet], config: SimConfig) -> SimResult:
    """1回のシミュレーション"""
    balance = config.initial_balance
    peak = balance
    min_balance = balance
    max_dd_pct = 0.0
    total_wagered = 0
    total_returned = 0
    num_wins = 0
    history = [balance]

    for bet in bets:
        if balance < config.min_bet:
            # 破産
            history.append(balance)
            break

        bet_amount = calc_bet_size(config, balance, bet)
        total_wagered += bet_amount

        # リターン計算（単勝のみ）
        returned = 0
        if bet.is_win:
            returned = int(bet.odds * bet_amount)
            num_wins += 1
        total_returned += returned

        balance = balance - bet_amount + returned
        history.append(balance)

        peak = max(peak, balance)
        min_balance = min(min_balance, balance)
        if peak > 0:
            dd = (peak - balance) / peak * 100
            max_dd_pct = max(max_dd_pct, dd)

    roi = (total_returned / total_wagered * 100) if total_wagered > 0 else 0

    return SimResult(
        final_balance=balance,
        growth_pct=(balance / config.initial_balance - 1) * 100,
        max_dd_pct=max_dd_pct,
        min_balance=min_balance,
        total_wagered=total_wagered,
        total_returned=total_returned,
        roi=roi,
        num_bets=len(bets),
        num_wins=num_wins,
        history=history,
    )


def calc_monthly_pnl(bets: list[Bet], config: SimConfig) -> dict:
    """月別収支を計算"""
    monthly = defaultdict(lambda: {"wagered": 0, "returned": 0, "bets": 0, "wins": 0})
    balance = config.initial_balance

    for bet in bets:
        if balance < config.min_bet:
            break

        month = bet.date[:7]  # "YYYY/MM"
        bet_amount = calc_bet_size(config, balance, bet)

        returned = 0
        if bet.is_win:
            returned = int(bet.odds * bet_amount)
            monthly[month]["wins"] += 1

        monthly[month]["wagered"] += bet_amount
        monthly[month]["returned"] += returned
        monthly[month]["bets"] += 1
        balance = balance - bet_amount + returned

    return dict(monthly)


# ============================================================
# モンテカルロ
# ============================================================

def monte_carlo(bets: list[Bet], config: SimConfig, n_trials: int = 1000) -> MCResult:
    """ブートストラップ・モンテカルロ"""
    if len(bets) == 0:
        empty = SimResult(config.initial_balance, 0, 0, config.initial_balance, 0, 0, 0, 0, 0, [])
        return MCResult(
            config_name=config.name, filter_name="", num_bets=0, num_trials=0,
            det_result=empty, final_p5=0, final_p50=0, final_p95=0,
            growth_p50=0, max_dd_p50=0, max_dd_p95=0, bust_rate=0, sharpe=0,
            monthly_pnl={},
        )

    # 決定論的（実際の順序）
    det_result = simulate_once(bets, config)
    monthly_pnl = calc_monthly_pnl(bets, config)

    # MC試行
    finals = []
    growths = []
    max_dds = []
    busts = 0

    for _ in range(n_trials):
        # ブートストラップ: 復元抽出（同じ件数をランダムに）
        shuffled = random.choices(bets, k=len(bets))
        result = simulate_once(shuffled, config)
        finals.append(result.final_balance)
        growths.append(result.growth_pct)
        max_dds.append(result.max_dd_pct)
        if result.min_balance < config.initial_balance * 0.5:
            busts += 1

    finals.sort()
    growths.sort()
    max_dds.sort()

    p5 = lambda arr: arr[int(len(arr) * 0.05)]
    p50 = lambda arr: arr[int(len(arr) * 0.50)]
    p95 = lambda arr: arr[int(len(arr) * 0.95)]

    # Sharpe比: 平均月次リターン / 月次リターンの標準偏差 × sqrt(12)
    monthly_returns = []
    for m_data in monthly_pnl.values():
        if m_data["wagered"] > 0:
            monthly_returns.append((m_data["returned"] - m_data["wagered"]) / config.initial_balance)

    if len(monthly_returns) >= 2:
        avg_r = sum(monthly_returns) / len(monthly_returns)
        std_r = (sum((r - avg_r) ** 2 for r in monthly_returns) / (len(monthly_returns) - 1)) ** 0.5
        sharpe = (avg_r / std_r * math.sqrt(12)) if std_r > 0 else 0
    else:
        sharpe = 0

    return MCResult(
        config_name=config.name,
        filter_name="",
        num_bets=len(bets),
        num_trials=n_trials,
        det_result=det_result,
        final_p5=p5(finals),
        final_p50=p50(finals),
        final_p95=p95(finals),
        growth_p50=p50(growths),
        max_dd_p50=p50(max_dds),
        max_dd_p95=p95(max_dds),
        bust_rate=busts / n_trials * 100,
        sharpe=sharpe,
        monthly_pnl=monthly_pnl,
    )


# ============================================================
# レポート生成
# ============================================================

def generate_report(
    all_results: dict[str, dict[str, MCResult]],
    initial_balance: int,
    n_trials: int,
) -> str:
    """Markdownレポート生成"""
    lines = []
    lines.append("# バンクロールシミュレーション結果")
    lines.append("")
    lines.append(f"**生成日**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**初期資金**: ¥{initial_balance:,}")
    lines.append(f"**MC試行回数**: {n_trials:,}")
    lines.append(f"**期間**: 2025-03 ~ 2026-02（12ヶ月）")
    lines.append("")

    # === 戦略比較サマリー ===
    lines.append("---")
    lines.append("")
    lines.append("## 戦略比較サマリー")
    lines.append("")
    lines.append("| 戦略 | フィルタ | ベット数 | 的中 | 的中率 | ROI | 最終残高(P50) | 成長率 | MaxDD(P95) | 破産率 | Sharpe |")
    lines.append("|------|----------|---------|------|--------|-----|--------------|--------|-----------|--------|--------|")

    for filter_name, filter_results in all_results.items():
        filter_label = FILTERS[filter_name]["label"]
        for config_name, mc in filter_results.items():
            det = mc.det_result
            hit_rate = (det.num_wins / det.num_bets * 100) if det.num_bets > 0 else 0
            lines.append(
                f"| {config_name} | {filter_label} | {det.num_bets} | {det.num_wins} | "
                f"{hit_rate:.1f}% | {det.roi:.1f}% | "
                f"¥{mc.final_p50:,} | {mc.growth_p50:+.1f}% | "
                f"{mc.max_dd_p95:.1f}% | {mc.bust_rate:.1f}% | {mc.sharpe:.2f} |"
            )

    # === フィルタ別詳細 ===
    for filter_name, filter_results in all_results.items():
        filter_label = FILTERS[filter_name]["label"]
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"## {filter_label}")
        lines.append("")

        # サンプルのベット数を取得
        sample_mc = list(filter_results.values())[0] if filter_results else None
        if sample_mc:
            lines.append(f"**ベット数**: {sample_mc.num_bets}件/年")
            lines.append(f"**的中率**: {sample_mc.det_result.num_wins}/{sample_mc.det_result.num_bets} "
                         f"({sample_mc.det_result.num_wins / max(1, sample_mc.det_result.num_bets) * 100:.1f}%)")
            lines.append("")

        # 詳細テーブル
        lines.append("| 戦略 | 最終残高 | P5(悲観) | P50(中央) | P95(楽観) | MaxDD(中央) | MaxDD(P95) | 破産率 |")
        lines.append("|------|---------|---------|----------|----------|-----------|-----------|--------|")

        for config_name, mc in filter_results.items():
            det = mc.det_result
            lines.append(
                f"| {config_name} | ¥{det.final_balance:,} | "
                f"¥{mc.final_p5:,} | ¥{mc.final_p50:,} | ¥{mc.final_p95:,} | "
                f"{mc.max_dd_p50:.1f}% | {mc.max_dd_p95:.1f}% | {mc.bust_rate:.1f}% |"
            )

        # 月別推移（最初の戦略のみ表示）
        if filter_results:
            first_key = list(filter_results.keys())[0]
            mc = filter_results[first_key]
            if mc.monthly_pnl:
                lines.append("")
                lines.append(f"### 月別推移（{first_key}）")
                lines.append("")
                lines.append("| 月 | ベット数 | 的中 | 投資額 | 回収額 | 収支 | 月ROI |")
                lines.append("|------|---------|------|--------|--------|------|-------|")

                cumulative_pnl = 0
                for month in sorted(mc.monthly_pnl.keys()):
                    m = mc.monthly_pnl[month]
                    pnl = m["returned"] - m["wagered"]
                    cumulative_pnl += pnl
                    mroi = (m["returned"] / m["wagered"] * 100) if m["wagered"] > 0 else 0
                    lines.append(
                        f"| {month} | {m['bets']} | {m['wins']} | "
                        f"¥{m['wagered']:,} | ¥{m['returned']:,} | "
                        f"¥{pnl:+,} | {mroi:.0f}% |"
                    )
                lines.append(f"| **累計** | | | | | **¥{cumulative_pnl:+,}** | |")

    # === 推奨 ===
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 推奨戦略")
    lines.append("")

    # intersection filterの結果から推奨を選ぶ
    if "intersection" in all_results:
        int_results = all_results["intersection"]
        # Sharpe最高
        best_sharpe = max(int_results.items(), key=lambda x: x[1].sharpe)
        # 最低MaxDD
        safest = min(int_results.items(), key=lambda x: x[1].max_dd_p95)
        # 最高成長
        highest_growth = max(int_results.items(), key=lambda x: x[1].growth_p50)

        lines.append(f"- **保守的**: {safest[0]}（MaxDD P95={safest[1].max_dd_p95:.1f}%, 破産率={safest[1].bust_rate:.1f}%）")
        lines.append(f"- **バランス型**: {best_sharpe[0]}（Sharpe={best_sharpe[1].sharpe:.2f}, 成長率P50={best_sharpe[1].growth_p50:+.1f}%）")
        lines.append(f"- **積極的**: {highest_growth[0]}（成長率P50={highest_growth[1].growth_p50:+.1f}%, MaxDD P95={highest_growth[1].max_dd_p95:.1f}%）")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 注意事項")
    lines.append("- シミュレーションはバックテスト（2025-03〜2026-02）のデータに基づく")
    lines.append("- 過去の実績は将来のリターンを保証しない")
    lines.append("- MaxDD P95 = 1000回試行の95パーセンタイル（ほぼ最悪ケース）")
    lines.append("- 破産率 = 初期資金の50%以下に到達した試行の割合")
    lines.append("- Sharpe比 = 月次リターン平均 / 月次リターン標準偏差 × √12（年率換算）")

    return "\n".join(lines)


# ============================================================
# メイン
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Bankroll Simulator")
    parser.add_argument("--initial", type=int, default=50000, help="Initial balance (default: 50000)")
    parser.add_argument("--mc", type=int, default=1000, help="Monte Carlo trials (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    initial = args.initial
    n_trials = args.mc
    random.seed(args.seed)

    print("=" * 60)
    print("Bankroll Simulator")
    print(f"  Initial: ¥{initial:,}")
    print(f"  MC trials: {n_trials:,}")
    print("=" * 60)

    # キャッシュ読み込み
    cache = load_cache()

    # 戦略定義
    configs = [
        SimConfig(name="Fixed ¥500", initial_balance=initial, sizing='fixed', unit_amount=500),
        SimConfig(name="Proportional 1%", initial_balance=initial, sizing='proportional', bet_pct=1.0),
        SimConfig(name="Proportional 2%", initial_balance=initial, sizing='proportional', bet_pct=2.0),
        SimConfig(name="Proportional 3%", initial_balance=initial, sizing='proportional', bet_pct=3.0),
        SimConfig(name="Kelly 1/4", initial_balance=initial, sizing='kelly', kelly_fraction=0.25, kelly_cap=0.10),
        SimConfig(name="Tiered EV", initial_balance=initial, sizing='tiered_ev', base_unit=500,
                  ev_tiers=[(2.0, 3), (1.5, 2), (1.3, 1)]),
    ]

    # 全フィルタ × 全戦略
    all_results: dict[str, dict[str, MCResult]] = {}

    for filter_name, filter_def in FILTERS.items():
        print(f"\n--- Filter: {filter_def['label']} ---")
        bets = extract_bets(cache, filter_name)
        print(f"  Bets: {len(bets)}")

        if len(bets) == 0:
            print("  [SKIP] No bets")
            continue

        # 的中率
        wins = sum(1 for b in bets if b.is_win)
        print(f"  Wins: {wins} ({wins / len(bets) * 100:.1f}%)")

        filter_results = {}
        for config in configs:
            print(f"  Simulating: {config.name}...", end="", flush=True)
            mc = monte_carlo(bets, config, n_trials)
            mc.filter_name = filter_name
            filter_results[config.name] = mc
            det = mc.det_result
            print(f" ROI={det.roi:.1f}%, Final=¥{det.final_balance:,}, "
                  f"MaxDD(P95)={mc.max_dd_p95:.1f}%, Sharpe={mc.sharpe:.2f}")

        all_results[filter_name] = filter_results

    # レポート生成
    print("\n" + "=" * 60)
    print("Generating report...")
    report = generate_report(all_results, initial, n_trials)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"Report saved: {REPORT_PATH}")
    print(f"Report size: {len(report):,} chars")

    # サマリー出力
    print("\n" + "=" * 60)
    print("SUMMARY (Intersection Filter)")
    print("=" * 60)
    if "intersection" in all_results:
        for name, mc in all_results["intersection"].items():
            det = mc.det_result
            print(f"  {name:20s}  ROI={det.roi:6.1f}%  Final=¥{det.final_balance:>8,}  "
                  f"DD(P95)={mc.max_dd_p95:5.1f}%  Bust={mc.bust_rate:4.1f}%  Sharpe={mc.sharpe:5.2f}")


if __name__ == "__main__":
    main()

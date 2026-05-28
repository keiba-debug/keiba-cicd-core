#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Freebudget 戦略 (Session 134 / 1万円フリー予算 OOS 用)

設計:
  bet_engine.generate_recommendations() の standard プリセット (Composite Score>=5.5
  + EV>=1.0 hard floor) を経由して VB Floor 通過の単勝候補を抽出。
  各馬を 1/4 Kelly fraction で案分し、 1馬上限 = bankroll * per_bet_cap_pct (default 10%)
  でキャップ。 100円単位丸め後、 合計が bankroll を超えていれば EV 降順で切り捨て。

入出力:
  入力  : predictions.json (vb_refresh 後の最新 win_ev)
  出力  : freebudget_bets.json (selective_bets と同形式 v2.0,
                                source="freebudget_kelly_1q", amount フィールド付き)

CLI:
    python -m ml.strategies.freebudget --date 2026-05-30
    python -m ml.strategies.freebudget --date 2026-05-31 --bankroll 12500
    python -m ml.strategies.freebudget --date 2026-05-30 --dry-run

設計判断 (Session 134):
  - source は selective_loader.ALLOWED_SOURCES の拡張が必要 ("freebudget_kelly_1q" 追加)
  - amount は selective_loader._validate_bet に追加検証 (100..1000)
  - 当日中はバンクロール固定 (シズネ 「動的調整なし」 原則)
  - 日跨ぎ更新は --bankroll 引数で明示的に上書き (例: 5/31 朝 = 5/30 終了残高)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.bet_engine import (  # noqa: E402
    PRESETS,
    calc_kelly_fraction,
    generate_recommendations,
)
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402


DEFAULT_BANKROLL = 10000          # 1万円フリー予算 (OOS 5/30 初日)
DEFAULT_KELLY_FRACTION = 0.25     # 1/4 Kelly (bankroll/config.json と整合)
DEFAULT_PER_BET_CAP_PCT = 0.10    # 1馬上限 10% (= 1000円 @ bankroll=10000)
DEFAULT_PRESET = "standard"       # bet_engine.PRESETS から
BET_UNIT_YEN = 100                # 100円単位丸め
MIN_BET_YEN = 100                 # 100円未満は不採用


@dataclass
class FreebudgetBet:
    """1馬の購入指示 (selective_bets.json の bets[] 互換 + amount)"""
    race_id: str
    race_number: Optional[int]
    venue_name: Optional[str]
    grade: str
    track_type: Optional[str]
    distance: Optional[int]
    num_runners: Optional[int]
    umaban: int
    horse_name: str
    odds: float
    rank_p: Optional[int]
    rank_w: Optional[int]
    odds_rank: Optional[int]
    vb_gap: Optional[int]
    win_ev: Optional[float]
    confidence: Optional[float]
    source: str = "freebudget_kelly_1q"
    # --- freebudget 固有 ---
    amount: int = 0                   # 購入額 (100円単位)
    kelly_p: float = 0.0              # 推定勝率 (= win_ev / odds)
    kelly_raw: float = 0.0            # 生 Kelly fraction
    kelly_sized: float = 0.0          # 1/4 Kelly cap適用後 fraction
    vb_score: float = 0.0             # bet_engine の composite score


@dataclass
class FreebudgetResult:
    bets: list[FreebudgetBet]
    bankroll: int
    kelly_fraction: float
    per_bet_cap_pct: float
    preset: str
    total_yen: int = 0
    n_eligible: int = 0               # VB Floor 通過した馬数
    n_funded: int = 0                 # 実際に amount >= 100 になった馬数
    n_truncated: int = 0              # 合計超過で切り捨てた馬数
    warnings: list[str] = field(default_factory=list)


def _bet_from_rec(rec, race_meta: dict, *, amount: int,
                   p: float, kelly_raw: float, kelly_sized: float) -> FreebudgetBet:
    """bet_engine.BetRecommendation + race meta → FreebudgetBet"""
    return FreebudgetBet(
        race_id=str(rec.race_id),
        race_number=race_meta.get("race_number"),
        venue_name=race_meta.get("venue_name"),
        grade=str(race_meta.get("grade") or ""),
        track_type=race_meta.get("track_type"),
        distance=race_meta.get("distance"),
        num_runners=race_meta.get("num_runners"),
        umaban=int(rec.umaban),
        horse_name=str(rec.horse_name or ""),
        odds=float(rec.odds or 0),
        rank_p=None,
        rank_w=None,
        odds_rank=None,
        vb_gap=int(rec.gap) if rec.gap is not None else None,
        win_ev=float(rec.win_ev) if rec.win_ev is not None else None,
        confidence=race_meta.get("race_confidence"),
        amount=int(amount),
        kelly_p=round(p, 4),
        kelly_raw=round(kelly_raw, 4),
        kelly_sized=round(kelly_sized, 4),
        vb_score=float(rec.vb_score or 0),
    )


def extract_freebudget_bets(
    predictions: dict,
    *,
    bankroll: int = DEFAULT_BANKROLL,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    per_bet_cap_pct: float = DEFAULT_PER_BET_CAP_PCT,
    preset: str = DEFAULT_PRESET,
) -> FreebudgetResult:
    """predictions.json から 1/4 Kelly 案分の freebudget 候補を抽出

    Steps:
      1. bet_engine.generate_recommendations で VB Floor 通過候補を取得
      2. 単勝系 (bet_type ∈ {'単勝', '単複'}) かつ win_amount > 0 のものに絞り込み
      3. 各馬について p = win_ev / odds → Kelly fraction (1/4 cap = per_bet_cap_pct)
      4. amount = floor(bankroll * kelly_sized / 100) * 100, < 100 は除外
      5. 合計 > bankroll なら EV 降順で切り捨て
    """
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset!r} (allowed: {sorted(PRESETS)})")
    params = PRESETS[preset]

    races = predictions.get("races", [])
    if not races:
        return FreebudgetResult(
            bets=[], bankroll=bankroll, kelly_fraction=kelly_fraction,
            per_bet_cap_pct=per_bet_cap_pct, preset=preset,
            warnings=["predictions has no races"],
        )

    # シズネ Session 134 🔴-4: bet_engine.apply_budget の按分縮小を経由させない。
    # budget=10**9 (= 巨大値) で按分縮小条件 (total > budget) を実質無効化、
    # bet_engine が返す win_amount は本来の Kelly 結果 (rec.kelly_capped) ベース。
    # freebudget は rec.win_amount > 0 のフラグ用途のみで実金額は自前 Kelly で再計算。
    # Themis 原則: bankroll は「金額決定の入力」 であり「件数フィルタの入力」 ではない。
    recs = generate_recommendations(races, params, budget=10**9)

    race_meta_by_id = {str(r.get("race_id")): r for r in races}

    per_bet_cap_yen = int(bankroll * per_bet_cap_pct)
    per_bet_cap_yen = (per_bet_cap_yen // BET_UNIT_YEN) * BET_UNIT_YEN

    candidates: list[tuple[FreebudgetBet, float]] = []  # (bet, ev_for_sort)

    for rec in recs:
        if rec.bet_type not in {"単勝", "単複"}:
            continue
        if (rec.win_amount or 0) <= 0:
            continue
        odds = float(rec.odds or 0)
        win_ev = float(rec.win_ev or 0)
        if odds <= 1.0 or win_ev < 1.0:
            continue
        p = win_ev / odds
        if p <= 0 or p >= 1:
            continue
        kelly_raw = calc_kelly_fraction(p, odds)
        if kelly_raw <= 0:
            continue
        kelly_sized = min(kelly_raw * kelly_fraction, per_bet_cap_pct)
        raw_yen = int(bankroll * kelly_sized)
        amount_yen = (raw_yen // BET_UNIT_YEN) * BET_UNIT_YEN
        amount_yen = min(amount_yen, per_bet_cap_yen)
        if amount_yen < MIN_BET_YEN:
            continue
        race_meta = race_meta_by_id.get(str(rec.race_id), {})
        bet = _bet_from_rec(rec, race_meta,
                            amount=amount_yen, p=p,
                            kelly_raw=kelly_raw, kelly_sized=kelly_sized)
        candidates.append((bet, win_ev))

    n_eligible = len(candidates)

    candidates.sort(key=lambda x: x[1], reverse=True)
    bets: list[FreebudgetBet] = []
    total = 0
    n_truncated = 0
    for bet, _ev in candidates:
        if total + bet.amount > bankroll:
            n_truncated += 1
            continue
        bets.append(bet)
        total += bet.amount

    bets.sort(key=lambda b: (b.race_id, b.umaban))

    return FreebudgetResult(
        bets=bets,
        bankroll=bankroll,
        kelly_fraction=kelly_fraction,
        per_bet_cap_pct=per_bet_cap_pct,
        preset=preset,
        total_yen=total,
        n_eligible=n_eligible,
        n_funded=len(bets),
        n_truncated=n_truncated,
    )


def write_freebudget_bets(date_dir: Path, result: FreebudgetResult) -> Path:
    """freebudget_bets.json を date_dir に書き出し (selective_loader 互換 schema)"""
    out_path = date_dir / "freebudget_bets.json"
    payload = {
        "strategy": "selective",       # selective_loader 互換のため固定
        "version": "2.0",
        "description": (
            f"freebudget Kelly 1/4 cap {result.per_bet_cap_pct:.0%} "
            f"(preset={result.preset}, bankroll={result.bankroll}円)"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_bets": len(result.bets),
        "bankroll": result.bankroll,
        "kelly_fraction": result.kelly_fraction,
        "per_bet_cap_pct": result.per_bet_cap_pct,
        "preset": result.preset,
        "total_yen": result.total_yen,
        "n_eligible": result.n_eligible,
        "n_funded": result.n_funded,
        "n_truncated": result.n_truncated,
        "bets": [asdict(b) for b in result.bets],
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def process_date(
    date_str: str, *,
    bankroll: int = DEFAULT_BANKROLL,
    kelly_fraction: float = DEFAULT_KELLY_FRACTION,
    per_bet_cap_pct: float = DEFAULT_PER_BET_CAP_PCT,
    preset: str = DEFAULT_PRESET,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    day_dir = date_dir_for(date_str)
    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print(f"  [{date_str}] predictions.json なし → スキップ")
        return {"date": date_str, "n_bets": 0, "skipped": True}

    result = extract_freebudget_bets(
        predictions,
        bankroll=bankroll,
        kelly_fraction=kelly_fraction,
        per_bet_cap_pct=per_bet_cap_pct,
        preset=preset,
    )

    if verbose:
        print(f"  [{date_str}] preset={preset} bankroll={bankroll}円 "
              f"kelly={kelly_fraction} cap={per_bet_cap_pct:.0%}")
        print(f"    eligible={result.n_eligible} funded={result.n_funded} "
              f"truncated={result.n_truncated} total={result.total_yen}円")
        for b in result.bets:
            ev_str = f"EV={b.win_ev:.2f}" if b.win_ev else ""
            print(f"    💴 {b.race_id} {b.venue_name or '?'} "
                  f"{b.race_number or '?'}R {b.grade} / "
                  f"{b.umaban}番 {b.horse_name} odds={b.odds:.1f} "
                  f"{ev_str}  amount={b.amount}円 "
                  f"(f={b.kelly_sized:.3f})")

    if not dry_run and result.bets:
        out_path = write_freebudget_bets(day_dir, result)
        if verbose:
            print(f"    → {out_path}")

    return {
        "date": date_str,
        "n_bets": len(result.bets),
        "total_yen": result.total_yen,
        "n_eligible": result.n_eligible,
        "n_truncated": result.n_truncated,
        "skipped": False,
    }


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--date", required=True, help="単日処理 (YYYY-MM-DD)")
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL,
                   help=f"バンクロール (円, default {DEFAULT_BANKROLL})")
    p.add_argument("--kelly-fraction", type=float, default=DEFAULT_KELLY_FRACTION,
                   help=f"Kelly 縮小率 (default {DEFAULT_KELLY_FRACTION})")
    p.add_argument("--per-bet-cap-pct", type=float, default=DEFAULT_PER_BET_CAP_PCT,
                   help=f"1馬上限 (バンクロール比, default {DEFAULT_PER_BET_CAP_PCT})")
    p.add_argument("--preset", default=DEFAULT_PRESET,
                   help=f"bet_engine プリセット (default {DEFAULT_PRESET})")
    p.add_argument("--dry-run", action="store_true",
                   help="ファイル書かず stdout のみ")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    # Windows console で UTF-8 出力を許可 (絵文字対応)
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    result = process_date(
        args.date,
        bankroll=args.bankroll,
        kelly_fraction=args.kelly_fraction,
        per_bet_cap_pct=args.per_bet_cap_pct,
        preset=args.preset,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )
    if not args.quiet:
        print(f"\n[Done] {result.get('n_bets', 0)} bets / "
              f"{result.get('total_yen', 0)}円")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""単◎ 戦略 (Step 1)

ふくだ手動 My印が打たれたレース集合に対し、 ◎ 馬の単勝 1 点を生成する。
F戦法 Step 1 (docs/auto-purchase/06_PHASED_ROADMAP.md §6.5.1) の最初の杭。

入力:
    - predictions.json (rank_p / odds など)
    - TARGET MY_DATA/*.DAT (◎ の馬番)
    - data3/my_marks_v2/{race_id}.json (明示消で ◎ を打ち消す可能性は無いが、
      消の馬が ◎ 候補の場合は除外される — DAT と矛盾するレースの安全弁)

出力:
    - data3/races/YYYY/MM/DD/tansho_bets.json

Usage:
    python -m ml.strategies.tansho --date 2026-05-17
    python -m ml.strategies.tansho --date 2026-05-17 --dry-run
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.features.my_marks import (
    load_my_marks, find_horse_by_mark, parse_race_id, get_mark_file_path,
)
from ml.strategies.base import (
    KIND_TANSHO,
    Bet,
    BettingStrategy,
    RaceContext,
)
from ml.utils.race_io import date_dir_for, load_predictions


# Step 1 では固定 100 円。 bankroll 統合は base.py の stake_hint を上位で上書きする
DEFAULT_STAKE_YEN = 100

# 障害戦は Step 1 では除外 (TARGET DAT は障害でも書けるが、ML パイプラインの整合性を保つ)
EXCLUDED_TRACK_TYPES = {"obstacle"}


class TanshoMarkerStrategy(BettingStrategy):
    """My印 ◎ → 単勝 1 点

    対象外:
      - ◎ が打たれていない
      - 障害戦
      - ◎ 馬が明示消されている (これは矛盾。 安全側で除外し warning)
    """

    name = "tansho_marker"
    kind = KIND_TANSHO

    def __init__(self, stake_yen: int = DEFAULT_STAKE_YEN) -> None:
        self.stake_yen = stake_yen

    def generate(self, ctx: RaceContext) -> List[Bet]:
        if ctx.track_type in EXCLUDED_TRACK_TYPES:
            return []
        if (ctx.grade or "").strip() and "障" in (ctx.grade or ""):
            return []

        marker = find_horse_by_mark(ctx.my_marks, "◎")
        if marker is None:
            return []

        # 安全弁: 同一馬が ◎ かつ消 はあり得ないが、 my_marks ロジックで消が勝つため、
        # marker が None になる経路はカバー済み。 ここは明示確認のみ。
        if marker.is_erased:
            return []

        entry = ctx.find_entry(marker.umaban)
        odds = float(entry.get("odds") or 0) if entry else 0.0
        ev = float(entry.get("win_ev") or 0) if entry else None
        pattern = _classify_mark_pattern(ctx)

        bet = Bet(
            race_id=ctx.race_id,
            kind=KIND_TANSHO,
            horses=[marker.umaban],
            stake_hint=self.stake_yen,
            reason=f"My印◎ (馬番={marker.umaban})",
            mark_pattern=pattern,
            odds=odds if odds > 0 else None,
            expected_value=ev,
            strategy_name=self.name,
            formation_type="single",
            raw_legs={"win": [marker.umaban]},
        )
        return [bet]


def _classify_mark_pattern(ctx: RaceContext) -> str:
    """印パターンの簡易ラベル (事後分析用)。 09 §1.3 の暫定実装"""
    symbols = {m.mark_symbol for m in ctx.my_marks.values() if m.is_marked}
    if not symbols:
        return "no_mark"
    if symbols == {"◎"}:
        return "1strong"
    if symbols == {"◎", "○"}:
        return "2strong"
    if symbols == {"◎", "○", "▲"}:
        return "3strong"
    if "◎" in symbols and len(symbols & {"△", "Ⅲ"}) >= 2 and "○" not in symbols:
        return "1strong_widefan"  # 1強総流し型
    if "穴" in symbols:
        return "ana_focus"
    return "other"


# ===========================================================================
# レースバッチ処理
# ===========================================================================

def build_context(race: dict, mark_set: int = 1) -> Optional[RaceContext]:
    """predictions.json の 1 レース dict から RaceContext を組み立てる"""
    rid = str(race.get("race_id") or "").strip()
    if len(rid) != 16 or not rid.isdigit():
        return None
    try:
        marks = load_my_marks(rid, mark_set=mark_set)
    except ValueError:
        marks = {}
    return RaceContext(
        race_id=rid,
        date=str(race.get("date") or ""),
        venue_name=race.get("venue_name"),
        race_number=race.get("race_number"),
        grade=race.get("grade"),
        track_type=race.get("track_type"),
        distance=race.get("distance"),
        num_runners=race.get("num_runners"),
        race_confidence=race.get("race_confidence"),
        entries=race.get("entries", []),
        my_marks=marks,
    )


def generate_bets_for_date(date_str: str, *, mark_set: int = 1,
                           stake_yen: int = DEFAULT_STAKE_YEN) -> tuple[list[Bet], int]:
    """1 日分の単◎買い目を生成。 returns (bets, n_races_scanned)"""
    day_dir = date_dir_for(date_str)
    predictions = load_predictions(day_dir)
    if predictions is None:
        return [], 0

    strategy = TanshoMarkerStrategy(stake_yen=stake_yen)
    bets: list[Bet] = []
    races = predictions.get("races", [])
    for race in races:
        ctx = build_context(race, mark_set=mark_set)
        if ctx is None:
            continue
        bets.extend(strategy.generate(ctx))
    return bets, len(races)


def _self_verify_race_id_parse(bets: list[Bet], mark_set: int) -> Optional[str]:
    """M1 セルフ verify: bets の先頭 1 件で parse_race_id → DAT exists を確認。
    通れば 'OK <iso>' を返す。 失敗時は None (payload には verified_at は入らない)
    シズネ a5635d4226c49c8d0: 「verify が古いまま放置されると M1 保証が形骸化」への根本対応"""
    for b in bets:
        try:
            coord = parse_race_id(b.race_id)
            path = get_mark_file_path(coord, mark_set=mark_set)
            if path.exists():
                return f"{datetime.now().isoformat(timespec='seconds')} (sample={b.race_id} dat={path.name})"
        except ValueError:
            continue
    return None


def _build_sources_snapshot(bets: list[Bet], day_dir: Path, mark_set: int) -> dict:
    """N2: ledger / 監査向けに「どのファイルから読んだか」をスナップショット"""
    import os
    dat_paths: set[str] = set()
    for b in bets:
        try:
            coord = parse_race_id(b.race_id)
            dat_paths.add(str(get_mark_file_path(coord, mark_set=mark_set)))
        except ValueError:
            continue
    return {
        "predictions_path": str(day_dir / "predictions.json"),
        "dat_paths": sorted(dat_paths),
        "my_marks_v2_dir": str(Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")) / "my_marks_v2"),
    }


def _pattern_distribution(bets: list[Bet]) -> dict:
    """N3: pattern_label の集計 (Step2 で pattern × ROI を見るときに便利)"""
    out: dict[str, int] = {}
    for b in bets:
        key = b.mark_pattern or "no_mark"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def write_bets(date_str: str, bets: list[Bet], *, mark_set: int) -> Path:
    """tansho_bets.json を date_dir に書き出し"""
    day_dir = date_dir_for(date_str)
    out_path = day_dir / "tansho_bets.json"
    now_iso = datetime.now().isoformat(timespec="seconds")
    payload = {
        "strategy": "tansho_marker",
        "version": "1.0",
        "description": "F戦法 Step1: My印◎ → 単勝1点 (固定100円, bankroll統合前)",
        "mark_set": mark_set,
        "generated_at": now_iso,
        # M1: 毎回 self-verify (bets 先頭で parse_race_id → DAT exists). 失敗時は null
        "race_id_parse_verified_at": _self_verify_race_id_parse(bets, mark_set),
        "n_bets": len(bets),
        "total_stake_hint": sum(b.stake_hint for b in bets),
        "pattern_distribution": _pattern_distribution(bets),
        "sources": _build_sources_snapshot(bets, day_dir, mark_set),
        "bets": [asdict(b) for b in bets],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return out_path


# ===========================================================================
# CLI
# ===========================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--date", required=True, help="単日処理 (YYYY-MM-DD)")
    p.add_argument("--mark-set", type=int, default=1,
                   help="TARGET 印セット (1-8, default=1)")
    p.add_argument("--stake", type=int, default=DEFAULT_STAKE_YEN,
                   help=f"1点あたり stake_hint (default={DEFAULT_STAKE_YEN})")
    p.add_argument("--dry-run", action="store_true", help="ファイル書かず stdout のみ")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    verbose = not args.quiet

    bets, n_races = generate_bets_for_date(
        args.date, mark_set=args.mark_set, stake_yen=args.stake
    )

    if verbose:
        if bets:
            print(f"[{args.date}] {len(bets)} bets / {n_races} races")
            for b in bets:
                odds_str = f"odds={b.odds:.1f}" if b.odds else "odds=?"
                ev_str = f"EV={b.expected_value:.2f}" if b.expected_value else ""
                print(f"  ◎ {b.race_id} 馬番{b.horses[0]} {odds_str} {ev_str} "
                      f"stake={b.stake_hint} pattern={b.mark_pattern}")
        else:
            print(f"[{args.date}] My印◎ 該当なし ({n_races} races)")

    if not args.dry_run and bets:
        out_path = write_bets(args.date, bets, mark_set=args.mark_set)
        if verbose:
            print(f"→ {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

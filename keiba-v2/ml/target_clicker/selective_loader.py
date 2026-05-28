#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""selective_bets.json ローダ + schema 検証 (Session 129 / シズネ指摘 J)

設計: docs/auto-purchase/shizune_review_session129.md 観点 J

背景:
  runner.py は selective_bets.json を schema 検証ゼロで読み込んでいた。
  Session 128 で +8,300 円勝った経路 (emerging_w_not_top2 source) を保護するためにも、
  ここを固めるのは「儲かった経路を守る」こと自体に等しい。

検証項目 (シズネ ふくだ確定: 違反は abort):
  - strategy == "selective"
  - version は ALLOWED_VERSIONS のいずれか
  - generated_at は ISO8601 (鮮度 24h 超は warning, 7d 超は SchemaError)
  - bets[] は list で len>=1
  - 各 bet:
      race_id     : 16桁数字
      umaban      : 1..30
      source      : ALLOWED_SOURCES のいずれか
      odds        : > 0 の float (未確定オッズ防止)
      horse_name  : 非空
      amount は loader 段階では渡されない (runner で --amount で上書き)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


ALLOWED_VERSIONS = {"2.0"}
ALLOWED_SOURCES = {"grade_top_p", "emerging_w_not_top2", "freebudget_kelly_1q"}
RACE_ID_RE = re.compile(r"^\d{16}$")

# bet.amount 検証範囲 (freebudget 用、 100..1000 円 = 1万円フリー予算 1馬上限10%)
# Session 134: freebudget_kelly_1q source で amount フィールドが入る場合のみ検証。
# 他 source は amount=None 許可 (runner --amount で上書き)。
AMOUNT_MIN_YEN = 100
AMOUNT_MAX_YEN = 1000

FRESHNESS_WARN_HOURS = 24      # 24h 超 → warning
FRESHNESS_ABORT_HOURS = 24 * 7  # 7d 超 → abort


class SchemaError(ValueError):
    """selective_bets.json schema 違反 (投票 abort 用)"""


@dataclass
class SelectiveBetEntry:
    """schema 検証済 bet 1 件 (runner で FfBet に変換される)"""
    race_id: str
    umaban: int
    horse_name: str
    odds: float
    source: str
    grade: Optional[str] = None
    venue_name: Optional[str] = None
    race_number: Optional[int] = None
    rank_p: Optional[int] = None
    rank_w: Optional[int] = None
    odds_rank: Optional[int] = None
    vb_gap: Optional[int] = None
    win_ev: Optional[float] = None
    # Session 134: freebudget_kelly_1q source で bet ごとに金額指定
    # None なら runner --amount で上書き (selective v2.0 既存互換)
    amount: Optional[int] = None


@dataclass
class LoadResult:
    bets: list[SelectiveBetEntry]
    warnings: list[str]
    version: str
    generated_at: str
    n_grade_top_p: int
    n_emerging_w_not_top2: int
    n_freebudget_kelly_1q: int = 0


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _validate_bet(idx: int, raw: dict) -> SelectiveBetEntry:
    if not isinstance(raw, dict):
        raise SchemaError(f"bets[{idx}] is not a dict: {type(raw).__name__}")

    rid = raw.get("race_id")
    if not isinstance(rid, str) or not RACE_ID_RE.match(rid):
        raise SchemaError(f"bets[{idx}].race_id 不正 (16桁数字必須): {rid!r}")

    umaban = raw.get("umaban")
    if not isinstance(umaban, int) or not (1 <= umaban <= 30):
        raise SchemaError(f"bets[{idx}].umaban 不正 (1..30): {umaban!r}")

    horse_name = raw.get("horse_name")
    if not isinstance(horse_name, str) or not horse_name.strip():
        raise SchemaError(f"bets[{idx}].horse_name 非空文字列必須: {horse_name!r}")

    odds = raw.get("odds")
    try:
        odds_f = float(odds)
    except (TypeError, ValueError):
        raise SchemaError(f"bets[{idx}].odds 数値必須: {odds!r}")
    if odds_f <= 0:
        # 未確定オッズ (0.0) は投票してはいけない
        raise SchemaError(
            f"bets[{idx}].odds <= 0 = 未確定オッズの可能性: race_id={rid}, odds={odds_f}"
        )

    source = raw.get("source", "")
    if source not in ALLOWED_SOURCES:
        raise SchemaError(
            f"bets[{idx}].source 不正 ({source!r}, 許可: {sorted(ALLOWED_SOURCES)})"
        )

    # Session 134: amount は freebudget 系 source では必須 + 範囲検証
    amount_raw = raw.get("amount")
    amount_val: Optional[int] = None
    if source == "freebudget_kelly_1q":
        if not isinstance(amount_raw, int) or isinstance(amount_raw, bool):
            raise SchemaError(
                f"bets[{idx}].amount は int 必須 (source={source}): {amount_raw!r}"
            )
        if not (AMOUNT_MIN_YEN <= amount_raw <= AMOUNT_MAX_YEN):
            raise SchemaError(
                f"bets[{idx}].amount 範囲外 "
                f"({AMOUNT_MIN_YEN}..{AMOUNT_MAX_YEN}): {amount_raw}"
            )
        if amount_raw % 100 != 0:
            raise SchemaError(
                f"bets[{idx}].amount は 100 円単位必須: {amount_raw}"
            )
        amount_val = int(amount_raw)
    elif amount_raw is not None:
        # 他 source で amount があっても許可しない (誤って混入していた場合 abort)
        raise SchemaError(
            f"bets[{idx}].amount は source={source!r} では指定不可 "
            f"(amount は freebudget 系のみ)"
        )

    return SelectiveBetEntry(
        race_id=rid,
        umaban=int(umaban),
        horse_name=horse_name.strip(),
        odds=odds_f,
        source=source,
        grade=raw.get("grade"),
        venue_name=raw.get("venue_name"),
        race_number=raw.get("race_number"),
        rank_p=raw.get("rank_p"),
        rank_w=raw.get("rank_w"),
        odds_rank=raw.get("odds_rank"),
        vb_gap=raw.get("vb_gap"),
        win_ev=raw.get("win_ev"),
        amount=amount_val,
    )


def load_selective_bets(path: Path, *, now: Optional[datetime] = None) -> LoadResult:
    """selective_bets.json を読み込み + schema 検証。 違反は SchemaError raise。"""
    if now is None:
        now = datetime.now()

    if not path.exists():
        raise SchemaError(f"selective_bets.json not found: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SchemaError(f"JSON parse error: {path}: {e}")

    warnings: list[str] = []

    # strategy
    if data.get("strategy") != "selective":
        raise SchemaError(
            f"strategy != 'selective' (got: {data.get('strategy')!r}): {path}"
        )

    # version
    version = data.get("version")
    if version not in ALLOWED_VERSIONS:
        raise SchemaError(
            f"version {version!r} not in allowed {sorted(ALLOWED_VERSIONS)}: {path}"
        )

    # generated_at + 鮮度
    gen_at = data.get("generated_at", "")
    gen_dt = _parse_iso(gen_at) if isinstance(gen_at, str) else None
    if gen_dt is None:
        raise SchemaError(f"generated_at 不正 (ISO8601 必須): {gen_at!r}")
    age = now - gen_dt
    if age > timedelta(hours=FRESHNESS_ABORT_HOURS):
        raise SchemaError(
            f"selective_bets.json が古すぎる "
            f"(age={age}, 上限 {FRESHNESS_ABORT_HOURS}h): generated_at={gen_at}"
        )
    if age > timedelta(hours=FRESHNESS_WARN_HOURS):
        warnings.append(
            f"selective_bets.json が {age} 経過 "
            f"(警告閾値 {FRESHNESS_WARN_HOURS}h): generated_at={gen_at}"
        )

    # bets[]
    bets_raw = data.get("bets")
    if not isinstance(bets_raw, list) or not bets_raw:
        raise SchemaError(f"bets[] が空または非list: {type(bets_raw).__name__}")

    bets: list[SelectiveBetEntry] = []
    for i, b in enumerate(bets_raw):
        bets.append(_validate_bet(i, b))

    # 重複検査 (同一 race_id + umaban が複数)
    seen: set[tuple[str, int]] = set()
    for b in bets:
        key = (b.race_id, b.umaban)
        if key in seen:
            warnings.append(f"重複 bet: race_id={b.race_id} umaban={b.umaban}")
        seen.add(key)

    n_grade = sum(1 for b in bets if b.source == "grade_top_p")
    n_emerging = sum(1 for b in bets if b.source == "emerging_w_not_top2")
    n_freebudget = sum(1 for b in bets if b.source == "freebudget_kelly_1q")

    return LoadResult(
        bets=bets,
        warnings=warnings,
        version=version,
        generated_at=gen_at,
        n_grade_top_p=n_grade,
        n_emerging_w_not_top2=n_emerging,
        n_freebudget_kelly_1q=n_freebudget,
    )

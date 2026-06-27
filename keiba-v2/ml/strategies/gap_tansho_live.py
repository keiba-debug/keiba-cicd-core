#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gap5単勝エッジ 本投票化 — サイジング + bankroll 追跡 + config (Session 176)

S173-175 の市場較正監査で確定したエッジ「gap≥5単勝 × (未勝利/条件/重賞)」を本番自動投票の
★最初の収益源★ にする (ふくだ決定 S175/S176)。器 (TARGET/IPAT 実行) は freebudget/bettype
を流用し、選定は `gap_tansho_shadow.select_gap_tansho` が canonical (shadow と同一ロジック=
broad/全オッズ)。combo (sanrentan_formation) は止める。

このモジュールの責務 (純関数 + config/ledger I/O。 DB/subprocess なし):
  - config (web 設定可・bankroll/config.json settings): gap_enabled / 初期bankroll(30万) /
    1点比率(%) / 日次cap(%)。
  - bankroll 実残高 = 初期bankroll + 過去 gap-live 実現PnL (日次更新・当日開始時で凍結)。
  - 1点額 = 残高 × 比率 (100円単位・最低100円)。★比例=破産ガード内包★ (Themis 原則・残高連動で
    勝てば自動で厚く・負ければジワ減りで破産しない。 監査MC: 比例1%=破産0%)。
  - select_gap_tansho → RaceSizing (tansho legs) を生成。

★サイズ根拠 (docs/market_calibration_edge_map.md §8)★: committed エッジ = broad ROI 130% /
  CI[81-187] / P(null≥130%)=0.026 (実在だが薄い・高分散)。連敗 p95=106 を耐える必要があるため
  比例フラクショナルが本体。比率はふくだ判断 1% (web で変更可)。

正本: docs/selection_engine_design.md §7 / docs/market_calibration_edge_map.md §8。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.kelly import BET_UNIT_YEN, MIN_BET_YEN  # noqa: E402
from ml.strategies.bettype_sizing import RaceSizing, SizedLeg, fit_legs_to_cap  # noqa: E402
from ml.strategies.gap_tansho_shadow import select_gap_tansho, DEFAULT_PARAMS  # noqa: E402

# bankroll config (freebudget_scheduler.BANKROLL_CONFIG_PATH と同一ファイル = web 設定の正本)。
BANKROLL_CONFIG_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "bankroll" / "config.json"

# gap-live 専用台帳 (実現PnL の蓄積 = 残高計算の素・本番 purchase_ledger とは別の口座簿)。
GAP_LIVE_DIR = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "gap_tansho_live"

# 既定値 (config 未設定時)。enabled は ★安全側で False★ (web で明示 ON してから稼働)。
DEFAULT_GAP_INITIAL_BANKROLL = 300_000   # 初期 bankroll = 30万 (隔離口座・ふくだ S175 確定)
DEFAULT_GAP_BET_PCT = 1.0                 # 1点 = 残高 × 1% (ふくだ S176 確定・web 変更可)
DEFAULT_GAP_DAY_PCT = 5.0                 # 日次 cap = 残高 × 5% (≈ 5点ぶん・暴走ガード)


@dataclass
class GapConfig:
    """bankroll/config.json settings から読む gap-live 設定 (web 設定可)。"""
    enabled: bool
    initial_bankroll_yen: int
    bet_pct: float          # 1点 = 残高 × bet_pct%
    day_pct: float          # 日次cap = 残高 × day_pct%
    source: str = ""        # 由来 (ログ/監査用)


def read_gap_config(path: Optional[Path] = None) -> GapConfig:
    """config.json settings から gap-live 設定を読む。

    キー (settings 直下): gap_enabled(bool) / gap_initial_bankroll_yen(int) /
    gap_bet_pct(float) / gap_day_pct(float)。欠損は安全側の既定 (enabled=False) にフォールバック。
    """
    p = path or BANKROLL_CONFIG_PATH
    try:
        if not p.exists():
            return GapConfig(False, DEFAULT_GAP_INITIAL_BANKROLL, DEFAULT_GAP_BET_PCT,
                             DEFAULT_GAP_DAY_PCT, source="config なし → 既定 (enabled=False)")
        cfg = json.loads(p.read_text(encoding="utf-8"))
        s = cfg.get("settings", {}) or {}
        enabled = bool(s.get("gap_enabled", False))
        initial = int(s.get("gap_initial_bankroll_yen", DEFAULT_GAP_INITIAL_BANKROLL)
                      or DEFAULT_GAP_INITIAL_BANKROLL)
        bet_pct = float(s.get("gap_bet_pct", DEFAULT_GAP_BET_PCT) or DEFAULT_GAP_BET_PCT)
        day_pct = float(s.get("gap_day_pct", DEFAULT_GAP_DAY_PCT) or DEFAULT_GAP_DAY_PCT)
        # サニティ: 比率は (0, 100]、初期残高は正。 不正値は既定へ。
        if not (0 < bet_pct <= 100):
            bet_pct = DEFAULT_GAP_BET_PCT
        if not (0 < day_pct <= 100):
            day_pct = DEFAULT_GAP_DAY_PCT
        if initial <= 0:
            initial = DEFAULT_GAP_INITIAL_BANKROLL
        return GapConfig(enabled, initial, bet_pct, day_pct,
                         source=f"config.json (enabled={enabled} 初期{initial:,} "
                                f"1点{bet_pct}% 日次{day_pct}%)")
    except (OSError, ValueError, TypeError) as e:
        return GapConfig(False, DEFAULT_GAP_INITIAL_BANKROLL, DEFAULT_GAP_BET_PCT,
                         DEFAULT_GAP_DAY_PCT, source=f"config 読込失敗 → 既定 (安全側): {e}")


# ---------------------------------------------------------------------------
# gap-live 台帳 (実現 PnL の蓄積 → bankroll 残高)
# ---------------------------------------------------------------------------

def _ledger_path() -> Path:
    GAP_LIVE_DIR.mkdir(parents=True, exist_ok=True)
    return GAP_LIVE_DIR / "ledger.json"


def load_gap_ledger(path: Optional[Path] = None) -> dict:
    """gap-live 台帳を読む (無ければ空)。 days = {date: {cost,payout,pnl,n,hit,settled_at}}。"""
    p = path or _ledger_path()
    if not p.exists():
        return {"days": {}}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc.setdefault("days", {})
        return doc
    except (OSError, ValueError):
        return {"days": {}}


def realized_pnl(ledger: dict) -> int:
    """台帳の確定済 days の実現 PnL 合計 (= payout - cost の総和)。"""
    return int(sum(int(d.get("pnl", 0) or 0) for d in (ledger.get("days") or {}).values()))


def account_balance(config: Optional[GapConfig] = None,
                    ledger: Optional[dict] = None) -> int:
    """gap 口座の現残高 = 初期bankroll + 確定済 実現PnL の総和。

    ★日次更新で可 (memory)★: 当日開始時に1回だけ呼んで scheduler state に凍結する。
    初期bankroll は ★config から live 取得★ (web で増資/減資したら即反映)。実現PnL は台帳から。
    残高が 0 以下になっても最低 BET_UNIT は返さず、 呼び出し側 (scheduler) が enabled/残高で
    投票可否を判断する (ここでは素の残高を返す)。
    """
    cfg = config or read_gap_config()
    led = ledger if ledger is not None else load_gap_ledger()
    return int(cfg.initial_bankroll_yen + realized_pnl(led))


# ---------------------------------------------------------------------------
# サイジング: 1点 = 残高 × 比率 (比例フラクショナル)
# ---------------------------------------------------------------------------

def stake_for(balance: int, bet_pct: float, *, unit: int = BET_UNIT_YEN,
              min_bet: int = MIN_BET_YEN) -> int:
    """1点額 = 残高 × bet_pct% を ★unit(100円)単位に切り捨て・最低 min_bet★。

    残高×比率が min_bet 未満 (= 残高が極小) のときは 0 を返す (= 投票しない・破産しかけ)。
    比例なので残高が増えれば自動で1点が厚くなる (「1点を厚く」は勝つにつれ自動で叶う)。
    """
    if balance <= 0 or bet_pct <= 0:
        return 0
    raw = balance * bet_pct / 100.0
    amt = int(raw // unit) * unit
    if amt < min_bet:
        # 残高×比率が 100円未満なら 0 (張らない)。 端数切り捨てで min_bet を割る極小残高ガード。
        return 0
    return amt


def size_gap_race(pred_race: dict, *, balance: int, bet_pct: float,
                  per_race_cap: int = 0, params: Optional[dict] = None) -> Optional[RaceSizing]:
    """1レースの gap5単勝候補を残高×比率でサイジングして RaceSizing を返す (買い目なしは None)。

    - 選定 = select_gap_tansho (canonical broad)。該当馬は全頭 (top_k=None)。
    - 各点 = stake_for(balance, bet_pct) の ★同額★ (比例フラクショナルは口座残高に連動・点ごとに
      差をつけない=エッジは券種選択でなく口座管理が本体)。
    - per_race_cap>0 なら fit_legs_to_cap で per_race 以内に按分 (複数点が同一レースに出た時の保険)。
    """
    pp = params or dict(DEFAULT_PARAMS)
    picks = select_gap_tansho(pred_race, **pp)
    if not picks:
        return None
    rid = str(pred_race.get("race_id"))
    stake = stake_for(balance, bet_pct)
    if stake < MIN_BET_YEN:
        return None  # 残高が極小 → 張らない (破産ガード)
    legs = []
    for pk in picks:
        legs.append(SizedLeg(
            race_id=rid, bet_type="tansho", horses=[pk["umaban"]], amount=stake,
            plan_label=f"gap単勝 {pk['cls']} (gap{pk['gap']} odds{pk['odds']})",
            leg_odds=pk.get("odds"), ev=pk.get("win_ev"), hit_prob=None,
            note=f"gap-live 残高{balance:,}×{bet_pct}%={stake} rank_w{pk['rank_w']}"))
    n_dropped = 0
    if per_race_cap > 0 and sum(l.amount for l in legs) > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
    if not legs:
        return None
    total = sum(l.amount for l in legs)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=total,
                      combo_yen=0, per_race_cap=per_race_cap, n_dropped=n_dropped,
                      warnings=[f"gap単勝: {len(legs)}点 各{stake}円 (残高{balance:,}×{bet_pct}%)"])


# ---------------------------------------------------------------------------
# settle: gap-live state の実投票を haraimodoshi で精算 → 台帳に蓄積
# ---------------------------------------------------------------------------

def settle_gap_day(date_str: str, state_votes: dict, *,
                   ledger_path: Optional[Path] = None) -> dict:
    """当日の gap-live 実投票 (state["votes"]) を実払戻で精算し台帳 days[date] に記録 (冪等)。

    cost = exit_code==0 の vote の amount 合計。 payout = day_recovery.compute_recovery で実払戻。
    pnl = payout - cost。 着順未確定なら payout 過小 (安全側) なので ★確定後に再実行★ して上書き。
    戻り: その日の {cost, payout, pnl, n, hit}。
    """
    from ml.strategies.day_recovery import compute_recovery
    cost = 0
    n = 0
    for v in (state_votes or {}).values():
        if isinstance(v, dict) and v.get("exit_code") == 0:
            cost += int(v.get("amount", 0) or 0)
            n += 1
    rec = compute_recovery(date_str, state_votes)
    payout = int(rec.get("recovered_yen", 0) or 0)
    # hit 数 = recovery detail で payout>0 のレース数 (近似・単勝は1点/レースが基本)
    hit = sum(1 for d in (rec.get("detail") or {}).values()
              if isinstance(d, dict) and int(d.get("payout", 0) or 0) > 0)
    day = {"cost": cost, "payout": payout, "pnl": payout - cost, "n": n, "hit": hit,
           "settled_races": rec.get("settled_races", 0),
           "pending_races": rec.get("pending_races", 0),
           "settled_at": datetime.now().isoformat(timespec="seconds")}
    p = ledger_path or _ledger_path()
    led = load_gap_ledger(p)
    led["days"][date_str] = day
    led["updated_at"] = day["settled_at"]
    p.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    return day


def report(config: Optional[GapConfig] = None, ledger: Optional[dict] = None) -> dict:
    """gap-live 口座の累積サマリ (残高・実現PnL・的中)。"""
    cfg = config or read_gap_config()
    led = ledger if ledger is not None else load_gap_ledger()
    days = led.get("days") or {}
    tot_cost = sum(int(d.get("cost", 0) or 0) for d in days.values())
    tot_pay = sum(int(d.get("payout", 0) or 0) for d in days.values())
    tot_n = sum(int(d.get("n", 0) or 0) for d in days.values())
    tot_hit = sum(int(d.get("hit", 0) or 0) for d in days.values())
    pnl = tot_pay - tot_cost
    return {
        "enabled": cfg.enabled,
        "initial_bankroll_yen": cfg.initial_bankroll_yen,
        "bet_pct": cfg.bet_pct, "day_pct": cfg.day_pct,
        "balance": cfg.initial_bankroll_yen + pnl,
        "settled_days": len(days), "n_bet": tot_n,
        "cost": tot_cost, "payout": tot_pay, "pnl": pnl,
        "roi": (tot_pay / tot_cost * 100 if tot_cost else 0.0),
        "hit": (tot_hit / tot_n * 100 if tot_n else 0.0),
        "days": dict(sorted(days.items())),
    }

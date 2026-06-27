#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""本命EV単 本投票化 — サイジング + bankroll 追跡 + config (Session 177)

推奨馬券画面の主力プリセット `tansho_ippon`(bet_engine) を自動投票の ★2本目スリーブ★ にする
(ふくだ決定 S177)。逆張り単(gap)が「人気薄×AI上位の単勝」なのに対し、本命EV単は
「AI本命(rank_w=1)を、市場が過小評価していて(win_vb_gap≥3)、期待値が高く(win_ev≥1.3)、
接戦で勝ち切れる(predicted_margin≤60)ときだけ単勝1点」= 本命側の妙味狙い。

選定条件 = bet_engine の PRESETS['tansho_ippon'] と同一 (他フィルタは全て無効化されており、
実効条件はこの4つ。test で bet_engine と parity を担保)。器(TARGET/IPAT 実行) と安全機構は
sleeve_orchestrator が集約 (gap と共有)。口座(config/残高/台帳)は ★完全隔離★ (gap とは別建て)。

このモジュールの責務 (純関数 + config/ledger I/O。 DB/subprocess なし):
  - config (web 設定可・bankroll/config.json settings): tansho_ev_enabled / 初期bankroll(30万) /
    1点比率(%) / 日次cap(%)。
  - bankroll 実残高 = 初期bankroll + 過去 本命EV単 実現PnL (日次更新・当日開始時で凍結)。
  - 1点額 = 残高 × 比率 (100円単位・最低100円)。★比例=破産ガード内包★ (gap と同型)。
  - select_honmei_ev → RaceSizing (tansho legs) を生成。

正本: docs/sleeve_orchestration_design.md / docs/selection_engine_design.md。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.kelly import BET_UNIT_YEN, MIN_BET_YEN  # noqa: E402
from ml.strategies.bettype_sizing import RaceSizing, SizedLeg, fit_legs_to_cap  # noqa: E402
from ml.strategies.gap_tansho_live import stake_for  # noqa: E402  (汎用サイザー=残高×比率を流用)

# bankroll config (gap と同一ファイル = web 設定の正本)。
BANKROLL_CONFIG_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "bankroll" / "config.json"

# 本命EV単 専用台帳 (実現PnL の蓄積 = 残高計算の素・本番 purchase_ledger とは別の口座簿)。
HONMEI_EV_DIR = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "honmei_ev_live"

# 既定値 (config 未設定時)。enabled は ★安全側で False★ (web で明示 ON してから稼働)。
DEFAULT_INITIAL_BANKROLL = 300_000   # 初期 bankroll = 30万 (隔離口座・ふくだ S177 確定=gap と別建て同額)
DEFAULT_BET_PCT = 2.0                 # 1点 = 残高 × 2% (web 変更可)
DEFAULT_DAY_PCT = 10.0                # 日次 cap = 残高 × 10% (暴走ガード・web 変更可)

# 選定パラメータ = bet_engine PRESETS['tansho_ippon'] の実効4条件 (他は無効化済)。
DEFAULT_PARAMS = {
    "rank_w_max": 1,          # win_max_rank_w=1 (AI本命のみ)
    "win_gap_min": 3,         # win_min_win_gap=3 (win_vb_gap≥3 = 市場の過小評価)
    "win_ev_floor": 1.3,      # win_min_ev=1.3 (単勝EV≥1.3)
    "margin_max": 60,         # win_max_predicted_margin=60 (接戦)
    "top_k": 1,               # max_win_per_race=1 (1レース1点)
}


@dataclass
class HonmeiEvConfig:
    """bankroll/config.json settings から読む 本命EV単 設定 (web 設定可)。"""
    enabled: bool
    initial_bankroll_yen: int
    bet_pct: float          # 1点 = 残高 × bet_pct%
    day_pct: float          # 日次cap = 残高 × day_pct%
    source: str = ""        # 由来 (ログ/監査用)


def read_honmei_ev_config(path: Optional[Path] = None) -> HonmeiEvConfig:
    """config.json settings から 本命EV単 設定を読む。

    キー (settings 直下): tansho_ev_enabled(bool) / tansho_ev_initial_bankroll_yen(int) /
    tansho_ev_bet_pct(float) / tansho_ev_day_pct(float)。欠損は安全側の既定 (enabled=False)。
    """
    p = path or BANKROLL_CONFIG_PATH
    try:
        if not p.exists():
            return HonmeiEvConfig(False, DEFAULT_INITIAL_BANKROLL, DEFAULT_BET_PCT,
                                  DEFAULT_DAY_PCT, source="config なし → 既定 (enabled=False)")
        cfg = json.loads(p.read_text(encoding="utf-8"))
        s = cfg.get("settings", {}) or {}
        enabled = bool(s.get("tansho_ev_enabled", False))
        initial = int(s.get("tansho_ev_initial_bankroll_yen", DEFAULT_INITIAL_BANKROLL)
                      or DEFAULT_INITIAL_BANKROLL)
        bet_pct = float(s.get("tansho_ev_bet_pct", DEFAULT_BET_PCT) or DEFAULT_BET_PCT)
        day_pct = float(s.get("tansho_ev_day_pct", DEFAULT_DAY_PCT) or DEFAULT_DAY_PCT)
        # サニティ: 比率は (0, 100]、初期残高は正。 不正値は既定へ。
        if not (0 < bet_pct <= 100):
            bet_pct = DEFAULT_BET_PCT
        if not (0 < day_pct <= 100):
            day_pct = DEFAULT_DAY_PCT
        if initial <= 0:
            initial = DEFAULT_INITIAL_BANKROLL
        return HonmeiEvConfig(enabled, initial, bet_pct, day_pct,
                              source=f"config.json (enabled={enabled} 初期{initial:,} "
                                     f"1点{bet_pct}% 日次{day_pct}%)")
    except (OSError, ValueError, TypeError) as e:
        return HonmeiEvConfig(False, DEFAULT_INITIAL_BANKROLL, DEFAULT_BET_PCT,
                              DEFAULT_DAY_PCT, source=f"config 読込失敗 → 既定 (安全側): {e}")


# ---------------------------------------------------------------------------
# 選定: 本命EV単 (= bet_engine tansho_ippon の実効条件と同一・test で parity 担保)
# ---------------------------------------------------------------------------

def select_honmei_ev(pred_race: dict, *, rank_w_max=1, win_gap_min=3, win_ev_floor=1.3,
                     margin_max=60, top_k=1) -> list:
    """1レースの 本命EV単候補を返す (canonical 選定)。

    条件 = rank_w≤rank_w_max(=1) かつ win_vb_gap≥win_gap_min(=3) かつ win_ev≥win_ev_floor(=1.3)
    かつ predicted_margin≤margin_max(=60)。bet_engine PRESETS['tansho_ippon'] の実効4条件と同一。
    """
    cands = []
    for e in (pred_race.get("entries") or []):
        umaban = e.get("umaban")
        rank_w = e.get("rank_w")
        win_gap = e.get("win_vb_gap")
        win_ev = e.get("win_ev")
        margin = e.get("predicted_margin")
        if (not umaban or rank_w is None or win_gap is None
                or win_ev is None or margin is None):
            continue
        if (rank_w <= rank_w_max and win_gap >= win_gap_min
                and win_ev >= win_ev_floor and margin <= margin_max):
            cands.append({
                "umaban": umaban,
                "horse_name": e.get("horse_name", ""),
                "rank_w": rank_w,
                "win_gap": win_gap,
                "odds": e.get("odds"),
                "win_ev": round(float(win_ev), 2),
                "predicted_margin": round(float(margin), 1),
            })
    cands.sort(key=lambda c: -c["win_ev"])  # 期待値降順
    if top_k is not None:
        cands = cands[:top_k]
    return cands


# ---------------------------------------------------------------------------
# 本命EV単 台帳 (実現 PnL の蓄積 → bankroll 残高)
# ---------------------------------------------------------------------------

def _ledger_path() -> Path:
    HONMEI_EV_DIR.mkdir(parents=True, exist_ok=True)
    return HONMEI_EV_DIR / "ledger.json"


def load_ledger(path: Optional[Path] = None) -> dict:
    """本命EV単 台帳を読む (無ければ空)。 days = {date: {cost,payout,pnl,n,hit,settled_at}}。"""
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


def account_balance(config: Optional[HonmeiEvConfig] = None,
                    ledger: Optional[dict] = None) -> int:
    """本命EV単 口座の現残高 = 初期bankroll + 確定済 実現PnL の総和 (gap と同型)。"""
    cfg = config or read_honmei_ev_config()
    led = ledger if ledger is not None else load_ledger()
    return int(cfg.initial_bankroll_yen + realized_pnl(led))


# ---------------------------------------------------------------------------
# サイジング: 1点 = 残高 × 比率 (比例フラクショナル・gap の stake_for を流用)
# ---------------------------------------------------------------------------

def size_honmei_ev_race(pred_race: dict, *, balance: int, bet_pct: float,
                        per_race_cap: int = 0, params: Optional[dict] = None
                        ) -> Optional[RaceSizing]:
    """1レースの 本命EV単候補を残高×比率でサイジングして RaceSizing を返す (買い目なしは None)。"""
    pp = params or dict(DEFAULT_PARAMS)
    picks = select_honmei_ev(pred_race, **pp)
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
            plan_label=f"本命EV単 (gap{pk['win_gap']} ev{pk['win_ev']} margin{pk['predicted_margin']})",
            leg_odds=pk.get("odds"), ev=pk.get("win_ev"), hit_prob=None,
            note=f"honmei-ev 残高{balance:,}×{bet_pct}%={stake} rank_w{pk['rank_w']}"))
    n_dropped = 0
    if per_race_cap > 0 and sum(l.amount for l in legs) > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
    if not legs:
        return None
    total = sum(l.amount for l in legs)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=total,
                      combo_yen=0, per_race_cap=per_race_cap, n_dropped=n_dropped,
                      warnings=[f"本命EV単: {len(legs)}点 各{stake}円 (残高{balance:,}×{bet_pct}%)"])


# ---------------------------------------------------------------------------
# settle: 本命EV単 state の実投票を haraimodoshi で精算 → 台帳に蓄積 (gap と同型)
# ---------------------------------------------------------------------------

def settle_honmei_ev_day(date_str: str, state_votes: dict, *,
                         ledger_path: Optional[Path] = None) -> dict:
    """当日の 本命EV単 実投票 (votes・★当該スリーブ分にフィルタ済★) を実払戻で精算し
    台帳 days[date] に記録 (冪等)。 cost/payout/pnl/n/hit を返す。"""
    from ml.strategies.day_recovery import compute_recovery
    cost = 0
    n = 0
    for v in (state_votes or {}).values():
        if isinstance(v, dict) and v.get("exit_code") == 0:
            cost += int(v.get("amount", 0) or 0)
            n += 1
    rec = compute_recovery(date_str, state_votes)
    payout = int(rec.get("recovered_yen", 0) or 0)
    hit = sum(1 for d in (rec.get("detail") or {}).values()
              if isinstance(d, dict) and int(d.get("payout", 0) or 0) > 0)
    day = {"cost": cost, "payout": payout, "pnl": payout - cost, "n": n, "hit": hit,
           "settled_races": rec.get("settled_races", 0),
           "pending_races": rec.get("pending_races", 0),
           "settled_at": datetime.now().isoformat(timespec="seconds")}
    p = ledger_path or _ledger_path()
    led = load_ledger(p)
    led["days"][date_str] = day
    led["updated_at"] = day["settled_at"]
    p.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    return day


def report(config: Optional[HonmeiEvConfig] = None, ledger: Optional[dict] = None) -> dict:
    """本命EV単 口座の累積サマリ (残高・実現PnL・的中)。"""
    cfg = config or read_honmei_ev_config()
    led = ledger if ledger is not None else load_ledger()
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深読み三点（ふかよみさんてん・コメＡ3点セット）本投票化 — 選定 + サイジング + bankroll 追跡 + config (Session 189)

コメントLLM (qwen2.5:14b) のＡ印 (confidence=高) を器に、単勝1u + 複勝2u + ワイド(×ML本命)1u
の3点セットで買う第三スリーブ。エッジ実証 = docs/ml-experiments/202607_comment_picks_payout_backtest.md
(★実装形 2:1:1+R4増額の2026年実測: ROI167.6% / 尻尾除き139.3 / CI[124.6,215.4] / p=0.001。
再現 = `python -m ml.analyze.comment_sleeve_dataset build` → `... portfolio`。
複勝Ａ的中率エッジは人気マッチ+20pt が2025/2026 の2年で再現)。
設計正本 = docs/comment_a_sleeve_design.md。

このモジュールの責務 (gap_tansho_live / honmei_ev_live と同型・DB/subprocess なし):
  - config (web 設定可): comment_a_enabled / 初期bankroll(30万) / 1単位比率(0.5%) /
    日次cap(10%) / R4ブースト(on)。
  - bankroll 実残高 = 初期bankroll + 過去 comment-a 実現PnL (隔離口座)。
  - 選定 = picks_YYYY-MM-DD.json のＡ印 (朝固定・オッズゲートなし) + predictions の
    rank_w 最上位をワイド相手に。
  - 配分 = 複2u(R4通過で3u)/単1u/ワイド1u (u = 残高×比率・比例フラクショナル)。

★R4 EVゲート★ = (pred_proba_p_raw + R4_UPLIFT) × place_odds_min ≥ 1.0。
コメＡの実測上乗せ (+19.6pt・2025推定/2026実測+19.8ptで一致) をモデル複勝確率に足した
EV 判定。通過時は複勝を1単位増額 (二値絞りは総利益を削るため不採用)。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.kelly import BET_UNIT_YEN, MIN_BET_YEN  # noqa: E402
from ml.strategies.bettype_sizing import RaceSizing, SizedLeg, fit_legs_to_cap  # noqa: E402
from ml.strategies.gap_tansho_live import stake_for  # noqa: E402

# bankroll config (gap/honmei と同一ファイル = web 設定の正本)。
BANKROLL_CONFIG_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "bankroll" / "config.json"

# comment-a 専用台帳 (実現PnL の蓄積 = 残高計算の素・gap/honmei と完全隔離)。
COMMENT_A_DIR = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "comment_a_live"

# コメAI picks (comment_llm live)。当日朝の prep で生成・日中固定。
PICKS_DIR = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "comment_llm" / "live"

# 既定値 (config 未設定時)。enabled は ★安全側で False★ (web で明示 ON してから稼働)。
DEFAULT_COMMENT_A_INITIAL_BANKROLL = 300_000  # 初期 bankroll = 30万 (隔離口座)
DEFAULT_COMMENT_A_BET_PCT = 0.5               # 1単位 = 残高 × 0.5% (1 pick = 4-5単位)
DEFAULT_COMMENT_A_DAY_PCT = 10.0              # 日次 cap = 残高 × 10% (≈ 4-5 picks ぶん)
DEFAULT_COMMENT_A_R4_BOOST = True             # R4 EVゲート通過時に複勝 2u→3u

# 配分 (単位数)。docs/comment_a_sleeve_design.md §3。
WEIGHT_FUKUSHO = 2
WEIGHT_FUKUSHO_R4 = 3
WEIGHT_TANSHO = 1
WEIGHT_WIDE = 1

# R4 EVゲートの上乗せ幅 (2025年実測のコメＡ複勝率上乗せ +19.6pt。2026実測+19.8ptと独立に一致)。
R4_UPLIFT = 0.196

# ★ハードDDストップ (ふくだ確定 S189)★: 口座残高が初期 bankroll の 50% を割ったら
# スリーブを自動停止 (is_enabled=False)。「事前に決めない停止線は停止線ではない」(シズネ 🟡-2)
# の code-enforced 版。
DD_STOP_FLOOR_PCT = 50.0


@dataclass
class CommentAConfig:
    """bankroll/config.json settings から読む comment-a 設定 (web 設定可)。"""
    enabled: bool
    initial_bankroll_yen: int
    bet_pct: float          # 1単位 = 残高 × bet_pct%
    day_pct: float          # 日次cap = 残高 × day_pct%
    r4_boost: bool = DEFAULT_COMMENT_A_R4_BOOST
    source: str = ""        # 由来 (ログ/監査用)


def read_comment_a_config(path: Optional[Path] = None) -> CommentAConfig:
    """config.json settings から comment-a 設定を読む。

    キー (settings 直下): comment_a_enabled(bool) / comment_a_initial_bankroll_yen(int) /
    comment_a_bet_pct(float) / comment_a_day_pct(float) / comment_a_r4_boost(bool)。
    欠損は安全側の既定 (enabled=False) にフォールバック。
    """
    p = path or BANKROLL_CONFIG_PATH
    try:
        if not p.exists():
            return CommentAConfig(False, DEFAULT_COMMENT_A_INITIAL_BANKROLL,
                                  DEFAULT_COMMENT_A_BET_PCT, DEFAULT_COMMENT_A_DAY_PCT,
                                  source="config なし → 既定 (enabled=False)")
        cfg = json.loads(p.read_text(encoding="utf-8"))
        s = cfg.get("settings", {}) or {}
        enabled = bool(s.get("comment_a_enabled", False))
        initial = int(s.get("comment_a_initial_bankroll_yen",
                            DEFAULT_COMMENT_A_INITIAL_BANKROLL)
                      or DEFAULT_COMMENT_A_INITIAL_BANKROLL)
        bet_pct = float(s.get("comment_a_bet_pct", DEFAULT_COMMENT_A_BET_PCT)
                        or DEFAULT_COMMENT_A_BET_PCT)
        day_pct = float(s.get("comment_a_day_pct", DEFAULT_COMMENT_A_DAY_PCT)
                        or DEFAULT_COMMENT_A_DAY_PCT)
        r4_boost = bool(s.get("comment_a_r4_boost", DEFAULT_COMMENT_A_R4_BOOST))
        # サニティ: 比率は (0, 100]、初期残高は正。 不正値は既定へ (gap と同基準)。
        if not (0 < bet_pct <= 100):
            bet_pct = DEFAULT_COMMENT_A_BET_PCT
        if not (0 < day_pct <= 100):
            day_pct = DEFAULT_COMMENT_A_DAY_PCT
        if initial <= 0:
            initial = DEFAULT_COMMENT_A_INITIAL_BANKROLL
        return CommentAConfig(enabled, initial, bet_pct, day_pct, r4_boost,
                              source=f"config.json (enabled={enabled} 初期{initial:,} "
                                     f"1単位{bet_pct}% 日次{day_pct}% r4={r4_boost})")
    except (OSError, ValueError, TypeError) as e:
        return CommentAConfig(False, DEFAULT_COMMENT_A_INITIAL_BANKROLL,
                              DEFAULT_COMMENT_A_BET_PCT, DEFAULT_COMMENT_A_DAY_PCT,
                              source=f"config 読込失敗 → 既定 (安全側): {e}")


# ---------------------------------------------------------------------------
# picks: コメAI Ａ印 (日次キャッシュ・朝固定なので当日中は不変)
# ---------------------------------------------------------------------------

_picks_cache: Dict[str, Dict[str, list]] = {}


def _picks_by_race(date_str: str, picks_dir: Optional[Path] = None) -> Dict[str, list]:
    """picks_YYYY-MM-DD.json → {race_id: [Ａ印 pick, ...]}。ファイル欠損/壊れは空 (安全側)。

    当日中はファイル不変 (朝 prep で生成・日中再生成しない運用) なのでモジュール内キャッシュ。
    """
    key = f"{picks_dir or PICKS_DIR}|{date_str}"
    if key in _picks_cache:
        return _picks_cache[key]
    p = (picks_dir or PICKS_DIR) / f"picks_{date_str}.json"
    out: Dict[str, list] = {}
    try:
        if not p.exists():
            # ★Ａ印ゼロの日との区別 (シズネ 🟡-1)★: ファイル自体の不存在は生成系
            # (Ollama/朝prep) の障害シグナル。ここで stderr に1回警告 (キャッシュで抑制。
            # scheduler はパス毎に別プロセス = ログに定期的に残る)。検知の正本は朝の --check。
            print(f"[comment_a] ⚠ {p.name} 不存在 — コメAI picks 未生成 "
                  f"(Ollama/朝prep を確認。当日 comment_a は no-op)", file=sys.stderr)
        if p.exists():
            for race in json.loads(p.read_text(encoding="utf-8")) or []:
                rid = str(race.get("race_id") or "")
                a = [pk for pk in (race.get("picks") or [])
                     if pk.get("confidence") == "高" and pk.get("umaban") is not None]
                if rid and a:
                    out[rid] = a
    except (OSError, ValueError, TypeError) as e:
        print(f"[comment_a] picks 読込失敗 ({p.name}) → 空 (安全側): {e}", file=sys.stderr)
        out = {}
    _picks_cache[key] = out
    return out


def _date_of_race(race_id: str) -> str:
    """race_id (YYYYMMDDJJKKNNRR) → YYYY-MM-DD。不正形式は '' (→ picks 空 = no-op)。"""
    s = str(race_id)
    if len(s) >= 8 and s[:8].isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return ""


# ---------------------------------------------------------------------------
# 選定: Ａ印 + ワイド相手 (ML本命) + R4 EVゲート
# ---------------------------------------------------------------------------

def _valid_odds(e: dict) -> bool:
    o = e.get("odds")
    return isinstance(o, (int, float)) and o > 0


def select_comment_a(pred_race: dict, *, picks_dir: Optional[Path] = None) -> list:
    """1レースのコメＡ候補を返す (canonical 選定)。

    各候補 = {umaban, horse_name, odds, wide_partner(None可), r4_pass(bool),
              sellable_fukusho_wide(bool), reason}。
    - Ａ印 = picks JSON の confidence=="高" (朝固定・オッズゲートなし)。
    - ★取消・除外ガード (シズネ 🔴-1)★: pick の馬番が pred_race entries に有効オッズ付きで
      存在しない (取消/除外/データ欠損) 場合はその pick を買わない。picks は朝固定のため
      日中取消は必ず起きうる。ガード無しだと runner 失敗 → 連続失敗 halt が
      ★他スリーブを巻き込む★ (マージ投票は1本)。
    - wide_partner = 有効オッズを持つ rank_w 最上位 (pick 自身を除く)。不在なら None。
    - r4_pass = (pred_proba_p_raw + R4_UPLIFT) × place_odds_min ≥ 1.0。欠損は False (安全側)。
    - sellable_fukusho_wide = 有効オッズの頭数 ≥ 5 (4頭以下は複勝発売なし・少頭数は
      ワイドも同様 → 単勝のみに縮退。シズネ 🟢-4)。
    """
    rid = str(pred_race.get("race_id") or "")
    date_str = _date_of_race(rid)
    if not date_str:
        return []
    a_picks = _picks_by_race(date_str, picks_dir).get(rid)
    if not a_picks:
        return []

    entries = pred_race.get("entries") or []
    by_uma = {}
    ranked = []
    for e in entries:
        u = e.get("umaban")
        if u is None:
            continue
        by_uma[int(u)] = e
        if e.get("rank_w") is not None and _valid_odds(e):
            ranked.append((e["rank_w"], int(u)))
    ranked.sort()
    n_active = sum(1 for e in by_uma.values() if _valid_odds(e))
    sellable = n_active >= 5

    out = []
    for pk in a_picks:
        try:
            uma = int(pk["umaban"])
        except (TypeError, ValueError):
            continue
        e = by_uma.get(uma)
        if e is None or not _valid_odds(e):
            print(f"[comment_a] {rid} #{uma} 取消/除外/オッズ欠損 → この pick は見送り "
                  f"(entries={'不在' if e is None else 'オッズ無効'})", file=sys.stderr)
            continue
        partner = next((u for _, u in ranked if u != uma), None)
        proba_p = e.get("pred_proba_p_raw")
        po_min = e.get("place_odds_min")
        r4 = (isinstance(proba_p, (int, float)) and isinstance(po_min, (int, float))
              and po_min > 0 and (proba_p + R4_UPLIFT) * po_min >= 1.0)
        out.append({
            "umaban": uma,
            "horse_name": e.get("horse_name") or pk.get("name") or "",
            "odds": e.get("odds"),
            "wide_partner": partner,
            "r4_pass": bool(r4),
            "sellable_fukusho_wide": sellable,
            "reason": (pk.get("reason") or "")[:40],
        })
    return out


# ---------------------------------------------------------------------------
# comment-a 台帳 (実現 PnL の蓄積 → bankroll 残高) — gap/honmei と同型
# ---------------------------------------------------------------------------

def _ledger_path() -> Path:
    COMMENT_A_DIR.mkdir(parents=True, exist_ok=True)
    return COMMENT_A_DIR / "ledger.json"


def load_ledger(path: Optional[Path] = None) -> dict:
    """comment-a 台帳を読む (無ければ空)。 days = {date: {cost,payout,pnl,n,hit,settled_at}}。"""
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


def account_balance(config: Optional[CommentAConfig] = None,
                    ledger: Optional[dict] = None) -> int:
    """comment-a 口座の現残高 = 初期bankroll + 確定済 実現PnL の総和 (gap と同型)。"""
    cfg = config or read_comment_a_config()
    led = ledger if ledger is not None else load_ledger()
    return int(cfg.initial_bankroll_yen + realized_pnl(led))


def dd_stopped(config: Optional[CommentAConfig] = None,
               ledger: Optional[dict] = None) -> bool:
    """ハードDDストップ発動中か (残高 < 初期 × DD_STOP_FLOOR_PCT%)。

    True の間 CommentASleeve.is_enabled() は False (投票しない)。停止中は残高が動かないため
    実質ラッチ — 再開 = ふくだが原因究明のうえ増資 or 初期残高/config を明示変更。
    """
    cfg = config or read_comment_a_config()
    bal = account_balance(cfg, ledger)
    return bal < cfg.initial_bankroll_yen * DD_STOP_FLOOR_PCT / 100.0


# ---------------------------------------------------------------------------
# サイジング: 複2u(R4で3u)/単1u/ワイド1u (u = 残高×比率・比例フラクショナル)
# ---------------------------------------------------------------------------

def size_comment_a_race(pred_race: dict, *, balance: int, bet_pct: float,
                        per_race_cap: int = 0, r4_boost: bool = True,
                        picks_dir: Optional[Path] = None) -> Optional[RaceSizing]:
    """1レースのコメＡ候補を3点セットでサイジングして RaceSizing を返す (買い目なしは None)。

    - 1単位 u = stake_for(balance, bet_pct) (gap と同式・100円単位・破産ガード内包)。
    - 各 pick: 複勝 WEIGHT_FUKUSHO×u (R4通過かつ r4_boost なら WEIGHT_FUKUSHO_R4×u) +
      単勝 WEIGHT_TANSHO×u + ワイド(pick×ML本命) WEIGHT_WIDE×u (相手不在ならワイドのみ略)。
    - per_race_cap>0 なら fit_legs_to_cap で按分 (アンカー=単複が保護され wide から落ちる)。
    """
    picks = select_comment_a(pred_race, picks_dir=picks_dir)
    if not picks:
        return None
    rid = str(pred_race.get("race_id"))
    unit = stake_for(balance, bet_pct)
    if unit < MIN_BET_YEN:
        return None  # 残高が極小 → 張らない (破産ガード)
    legs: List[SizedLeg] = []
    warns: List[str] = []
    for pk in picks:
        uma = pk["umaban"]
        boosted = bool(r4_boost and pk["r4_pass"])
        w_fuku = WEIGHT_FUKUSHO_R4 if boosted else WEIGHT_FUKUSHO
        tag = " R4" if boosted else ""
        base_note = f"comment-a 残高{balance:,}×{bet_pct}%=u{unit}{tag}"
        # 少頭数 (有効オッズ<5頭) は複勝発売なし → 単勝のみに縮退 (シズネ 🟢-4)
        if pk.get("sellable_fukusho_wide", True):
            legs.append(SizedLeg(
                race_id=rid, bet_type="fukusho", horses=[uma], amount=unit * w_fuku,
                plan_label=f"コメＡ複勝{tag} ({pk['horse_name']})",
                leg_odds=None, ev=None, hit_prob=None, note=base_note))
        else:
            warns.append(f"#{uma} 少頭数(<5) → 複勝/ワイド発売なし・単勝のみ")
        legs.append(SizedLeg(
            race_id=rid, bet_type="tansho", horses=[uma], amount=unit * WEIGHT_TANSHO,
            plan_label=f"コメＡ単勝 ({pk['horse_name']} odds{pk['odds']})",
            leg_odds=pk.get("odds"), ev=None, hit_prob=None, note=base_note))
        if pk.get("wide_partner") is not None and pk.get("sellable_fukusho_wide", True):
            legs.append(SizedLeg(
                race_id=rid, bet_type="wide", horses=[uma, pk["wide_partner"]],
                amount=unit * WEIGHT_WIDE,
                plan_label=f"コメＡワイド ({uma}×ML本命{pk['wide_partner']})",
                leg_odds=None, ev=None, hit_prob=None, note=base_note))
    n_dropped = 0
    if per_race_cap > 0 and sum(l.amount for l in legs) > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
    if not legs:
        return None
    total = sum(l.amount for l in legs)
    n_picks = len(picks)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=total,
                      combo_yen=0, per_race_cap=per_race_cap, n_dropped=n_dropped,
                      warnings=[f"コメＡ3点セット: {n_picks}頭 {len(legs)}脚 {total}円 "
                                f"(u{unit}=残高{balance:,}×{bet_pct}%)"] + warns)


# ---------------------------------------------------------------------------
# settle: comment-a state の実投票を実払戻で精算 → 台帳に蓄積 (gap/honmei と同型)
# ---------------------------------------------------------------------------

def settle_comment_a_day(date_str: str, state_votes: dict, *,
                         ledger_path: Optional[Path] = None) -> dict:
    """当日の comment-a 実投票 (votes・★当該スリーブ分にフィルタ済★) を実払戻で精算し
    台帳 days[date] に記録 (冪等)。 cost/payout/pnl/n/hit を返す。

    複勝は day_recovery (settle_ledger.compute_payout) の odds_low 下限精算 = payout 過小の
    保守バイアス (設計 §4)。安全側 (残高が小さく見える) として容認。
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


def report(config: Optional[CommentAConfig] = None, ledger: Optional[dict] = None) -> dict:
    """comment-a 口座の累積サマリ (残高・実現PnL・的中)。"""
    cfg = config or read_comment_a_config()
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
        "bet_pct": cfg.bet_pct, "day_pct": cfg.day_pct, "r4_boost": cfg.r4_boost,
        "balance": cfg.initial_bankroll_yen + pnl,
        "settled_days": len(days), "n_bet": tot_n,
        "cost": tot_cost, "payout": tot_pay, "pnl": pnl,
        "roi": (tot_pay / tot_cost * 100 if tot_cost else 0.0),
        "hit": (tot_hit / tot_n * 100 if tot_n else 0.0),
        "days": dict(sorted(days.items())),
    }


# ---------------------------------------------------------------------------
# CLI: 朝の稼働前チェック (--check) / 口座レポート (--report)
# ---------------------------------------------------------------------------

def _check(date_str: str) -> int:
    """picks 有無・Ａ印数・買い目予定を dry 表示 (朝 prep の確認用・投票しない)。"""
    cfg = read_comment_a_config()
    bal = account_balance(cfg)
    unit = stake_for(bal, cfg.bet_pct)
    picks_map = _picks_by_race(date_str)
    n_a = sum(len(v) for v in picks_map.values())
    print(f"[comment_a] {date_str} config: {cfg.source}")
    print(f"[comment_a] 残高={bal:,}円 1単位={unit}円 "
          f"1pick={unit * (WEIGHT_FUKUSHO + WEIGHT_TANSHO + WEIGHT_WIDE)}"
          f"〜{unit * (WEIGHT_FUKUSHO_R4 + WEIGHT_TANSHO + WEIGHT_WIDE)}円")
    if not picks_map:
        print(f"[comment_a] ⚠ picks_{date_str}.json なし/Ａ印ゼロ → 当日は no-op "
              f"(朝 prep で live_picks 生成済みか確認)")
        return 1
    print(f"[comment_a] Ａ印 {n_a}頭 / {len(picks_map)}レース:")
    y, m, d = date_str.split("-")
    pred_path = (Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))
                 / "races" / y / m / d / "predictions.json")
    preds = {}
    if pred_path.exists():
        try:
            pj = json.loads(pred_path.read_text(encoding="utf-8"))
            preds = {str(r.get("race_id")): r for r in pj.get("races") or []}
        except (OSError, ValueError):
            pass
    else:
        print(f"[comment_a] ⚠ predictions.json なし → ワイド相手/R4 判定不可 (単複のみ想定)")
    n_sel = n_r4 = n_wide = 0
    ranks = []
    for rid in sorted(picks_map):
        pr = preds.get(rid) or {"race_id": rid, "entries": []}
        sel = select_comment_a(pr)
        for pk in sel:
            n_sel += 1
            n_r4 += 1 if pk["r4_pass"] else 0
            n_wide += 1 if pk["wide_partner"] is not None else 0
            print(f"  {rid[-4:]} #{pk['umaban']:>2} {pk['horse_name']:<12} "
                  f"wide相手={pk['wide_partner']} R4={'○' if pk['r4_pass'] else '-'} "
                  f"({pk['reason']})")
        if not sel and picks_map.get(rid):
            print(f"  {rid[-4:]} (取消/predictions不在などで選定0: Ａ印{len(picks_map[rid])}頭)")
        for p_ in picks_map.get(rid) or []:
            if p_.get("rank"):
                ranks.append(p_["rank"])
    # ★カナリア3指標 (シズネ 🟢-2)★: backtest 基準 = 約4頭/日・平均人気5.7・R4通過57%。
    #   選定母集団の変質は損失より先にここに現れる。
    avg_rank = f"{sum(ranks) / len(ranks):.1f}" if ranks else "-"
    print(f"[comment_a] カナリア: Ａ印{n_a}頭 (基準≈4/日) 平均人気{avg_rank} (基準5.7) "
          f"R4通過{n_r4}/{n_sel} (基準57%) wide解決{n_wide}/{n_sel}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="コメＡ3点セット スリーブ (check/report)")
    ap.add_argument("--check", action="store_true", help="稼働前チェック (picks/買い目 dry 表示)")
    ap.add_argument("--report", action="store_true", help="口座サマリ表示")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = ap.parse_args()
    if args.check:
        return _check(args.date)
    if args.report:
        print(json.dumps(report(), ensure_ascii=False, indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

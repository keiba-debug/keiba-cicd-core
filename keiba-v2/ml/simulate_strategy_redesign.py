#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
戦略プリセット再設計シミュレーション

backtest_cache.json + haraimodoshi(MySQL) を使って
新プリセット（馬券種×狙い方）をバックテスト＋バンクロールSim。

新プリセット:
  [単勝系] tansho_A ~ tansho_E: rank_w=1ベースの単勝バリエーション
  [馬連系] umaren_A ~ umaren_D: モデルTop1軸の馬連
  [複勝系] fukusho_A ~ fukusho_C: rank_p=1の複勝、試行回数型

Usage:
    python -m ml.simulate_strategy_redesign
    python -m ml.simulate_strategy_redesign --sizing kelly --initial 100000
"""

import json
import sys
import math
import random
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from itertools import combinations
from typing import Callable, Dict, List, Literal, Optional, Tuple

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import config
from core.db import get_connection
from ml.utils.backtest_cache import load_backtest_cache as _load_bt


# ============================================================
# Data Loading
# ============================================================

def load_cache(cache_path: Optional[str] = None) -> list:
    return _load_bt(path=Path(cache_path) if cache_path else None)


def load_haraimodoshi(race_codes: List[str]) -> Dict[str, dict]:
    """haraimodoshiテーブルから馬連/ワイド/馬単の払戻データを一括取得"""
    cols = ["RACE_CODE"]
    for bt in ("UMAREN", "WIDE", "UMATAN"):
        cols.append(f"FUSEIRITSU_FLAG_{bt}")
    for i in range(1, 4):
        cols.extend([f"UMAREN{i}_KUMIBAN1", f"UMAREN{i}_KUMIBAN2",
                     f"UMAREN{i}_HARAIMODOSHIKIN"])
    for i in range(1, 8):
        cols.extend([f"WIDE{i}_KUMIBAN1", f"WIDE{i}_KUMIBAN2",
                     f"WIDE{i}_HARAIMODOSHIKIN"])
    for i in range(1, 7):
        cols.extend([f"UMATAN{i}_KUMIBAN1", f"UMATAN{i}_KUMIBAN2",
                     f"UMATAN{i}_HARAIMODOSHIKIN"])

    col_str = ", ".join(cols)
    result = {}
    batch_size = 500

    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        for start in range(0, len(race_codes), batch_size):
            batch = race_codes[start:start + batch_size]
            placeholders = ",".join(["%s"] * len(batch))
            sql = f"SELECT {col_str} FROM haraimodoshi WHERE RACE_CODE IN ({placeholders})"
            cur.execute(sql, batch)
            for row in cur.fetchall():
                rc = row["RACE_CODE"].strip()
                result[rc] = _parse_hm_row(row)
        cur.close()

    return result


def _pi(s) -> int:
    if not s or not str(s).strip():
        return 0
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def _parse_hm_row(row: dict) -> dict:
    payouts = {
        "umaren": [], "wide": [], "umatan": [],
        "flags": {},
    }
    for bt in ("UMAREN", "WIDE", "UMATAN"):
        payouts["flags"][bt] = (row.get(f"FUSEIRITSU_FLAG_{bt}", "0") == "1")

    for i in range(1, 4):
        k1 = _pi(row.get(f"UMAREN{i}_KUMIBAN1", ""))
        k2 = _pi(row.get(f"UMAREN{i}_KUMIBAN2", ""))
        pay = _pi(row.get(f"UMAREN{i}_HARAIMODOSHIKIN", ""))
        if k1 and k2 and pay:
            payouts["umaren"].append((frozenset({k1, k2}), pay))

    for i in range(1, 8):
        k1 = _pi(row.get(f"WIDE{i}_KUMIBAN1", ""))
        k2 = _pi(row.get(f"WIDE{i}_KUMIBAN2", ""))
        pay = _pi(row.get(f"WIDE{i}_HARAIMODOSHIKIN", ""))
        if k1 and k2 and pay:
            payouts["wide"].append((frozenset({k1, k2}), pay))

    for i in range(1, 7):
        k1 = _pi(row.get(f"UMATAN{i}_KUMIBAN1", ""))
        k2 = _pi(row.get(f"UMATAN{i}_KUMIBAN2", ""))
        pay = _pi(row.get(f"UMATAN{i}_HARAIMODOSHIKIN", ""))
        if k1 and k2 and pay:
            payouts["umatan"].append(((k1, k2), pay))

    return payouts


def _match_umaren(payouts: dict, pair: frozenset) -> int:
    for p, yen in payouts.get("umaren", []):
        if p == pair:
            return yen
    return 0


def _match_wide(payouts: dict, pair: frozenset) -> int:
    for p, yen in payouts.get("wide", []):
        if p == pair:
            return yen
    return 0


# ============================================================
# Helpers
# ============================================================

def _get_sorted(entries, key, n, desc=True):
    """entriesをkey降順でソートしてtop n返す（odds>0のみ）"""
    valid = [e for e in entries if (e.get("odds") or 0) > 0]
    return sorted(valid, key=lambda e: -(e.get(key) or 0) if desc else (e.get(key) or 0))[:n]


def _rank_w_top(entries, n=1):
    valid = [e for e in entries if (e.get("odds") or 0) > 0 and (e.get("rank_w") or 99) <= n]
    return sorted(valid, key=lambda e: (e.get("rank_w") or 99))


def _rank_p_top(entries, n=1):
    valid = [e for e in entries if (e.get("odds") or 0) > 0 and (e.get("rank_p") or 99) <= n]
    return sorted(valid, key=lambda e: (e.get("rank_p") or 99))


# ============================================================
# Bet Result
# ============================================================

@dataclass
class Bet:
    date: str
    race_id: str
    umaban: int  # 0 for multi-leg
    horse_name: str
    odds: float
    is_hit: bool
    payout_per_100: int  # 100円あたりの払い戻し
    bet_type: str  # '単勝' / '複勝' / '馬連' / 'ワイド'
    # extras
    win_ev: float = 0
    rank_w: int = 99
    win_vb_gap: int = 0
    predicted_margin: float = 99
    ar_deviation: float = 0


# ============================================================
# 単勝系プリセット
# ============================================================

TANSHO_PRESETS = {}

def _tansho_filter(entry, race, **kwargs) -> bool:
    """単勝フィルタのベース"""
    max_rw = kwargs.get('max_rank_w', 1)
    min_gap = kwargs.get('min_gap', 0)
    min_ev = kwargs.get('min_ev', 0)
    max_margin = kwargs.get('max_margin', 999)
    min_ard = kwargs.get('min_ard', 0)

    rw = entry.get('rank_w') or 99
    gap = entry.get('win_vb_gap') or 0
    ev = entry.get('win_ev') or 0
    margin = entry.get('predicted_margin') or 999
    ard = entry.get('ar_deviation') or 0

    if rw > max_rw:
        return False
    if gap < min_gap:
        return False
    if ev < min_ev:
        return False
    if margin > max_margin:
        return False
    if ard < min_ard:
        return False
    return True


# tansho_A: intersection再現 (rank_w=1, gap>=4, EV>=1.3, margin<=60)
TANSHO_PRESETS['tansho_A'] = {
    'label': '単勝A: intersection (rw1+gap4+EV1.3+m60)',
    'params': dict(max_rank_w=1, min_gap=4, min_ev=1.3, max_margin=60),
}

# tansho_B: intersection緩和 (gap>=3, EV>=1.2, margin<=60)
TANSHO_PRESETS['tansho_B'] = {
    'label': '単勝B: 緩和intersection (rw1+gap3+EV1.2+m60)',
    'params': dict(max_rank_w=1, min_gap=3, min_ev=1.2, max_margin=60),
}

# tansho_C: simple hybrid (gap>=3, EVなし, marginなし)
TANSHO_PRESETS['tansho_C'] = {
    'label': '単勝C: simple gap3 (rw1+gap3)',
    'params': dict(max_rank_w=1, min_gap=3),
}

# tansho_D: EV重視 (EV>=1.5, gapなし)
TANSHO_PRESETS['tansho_D'] = {
    'label': '単勝D: EV重視 (rw1+EV1.5)',
    'params': dict(max_rank_w=1, min_ev=1.5),
}

# tansho_E: 高ARd限定 (ARd>=60, gap>=2, EV>=1.2, margin<=60)
TANSHO_PRESETS['tansho_E'] = {
    'label': '単勝E: 高能力 (rw1+ARd60+gap2+EV1.2+m60)',
    'params': dict(max_rank_w=1, min_gap=2, min_ev=1.2, min_ard=60, max_margin=60),
}

# tansho_F: rw<=2拡大 (rank_w=1~2, gap>=4, EV>=1.3, margin<=60)
TANSHO_PRESETS['tansho_F'] = {
    'label': '単勝F: rw1-2拡大 (rw2+gap4+EV1.3+m60)',
    'params': dict(max_rank_w=2, min_gap=4, min_ev=1.3, max_margin=60),
}

# tansho_G: margin無制限 (intersectionからmarginだけ外す)
TANSHO_PRESETS['tansho_G'] = {
    'label': '単勝G: margin無制限 (rw1+gap4+EV1.3)',
    'params': dict(max_rank_w=1, min_gap=4, min_ev=1.3),
}

# tansho_H: gap>=3 + EV>=1.3 + margin<=60 (BとGの中間)
TANSHO_PRESETS['tansho_H'] = {
    'label': '単勝H: 中間型 (rw1+gap3+EV1.3+m60)',
    'params': dict(max_rank_w=1, min_gap=3, min_ev=1.3, max_margin=60),
}


def extract_tansho_bets(cache: list, preset_key: str) -> List[Bet]:
    params = TANSHO_PRESETS[preset_key]['params']
    bets = []
    for race in cache:
        rid = str(race['race_id'])
        date_str = f"{rid[:4]}/{rid[4:6]}/{rid[6:8]}"
        for e in race['entries']:
            if _tansho_filter(e, race, **params):
                odds = e.get('odds') or 0
                is_win = bool(e.get('is_win'))
                payout = int(odds * 100) if is_win else 0
                bets.append(Bet(
                    date=date_str, race_id=rid,
                    umaban=e.get('umaban', 0),
                    horse_name=e.get('horse_name', ''),
                    odds=odds, is_hit=is_win,
                    payout_per_100=payout,
                    bet_type='単勝',
                    win_ev=e.get('win_ev') or 0,
                    rank_w=e.get('rank_w') or 99,
                    win_vb_gap=e.get('win_vb_gap') or 0,
                    predicted_margin=e.get('predicted_margin') or 99,
                    ar_deviation=e.get('ar_deviation') or 0,
                ))
    bets.sort(key=lambda b: (b.date, b.race_id))
    return bets


# ============================================================
# 馬連系プリセット
# ============================================================

UMAREN_PRESETS = {}

# umaren_A: rank_w=1軸 → ARd Top2-3 (1-3点)
UMAREN_PRESETS['umaren_A'] = {
    'label': '馬連A: rw1軸→ARd Top3 (1-3点)',
    'desc': 'rank_w=1の馬を軸に、ARd上位2-3頭への馬連流し',
}

# umaren_B: rank_w=1軸 → rank_p Top2-3 (モデル合意型)
UMAREN_PRESETS['umaren_B'] = {
    'label': '馬連B: rw1軸→rp Top3 (モデル合意)',
    'desc': 'rank_w=1の馬を軸に、rank_p上位2-3頭(自分以外)への馬連',
}

# umaren_C: rw1+rp1合意(同一馬)の時だけ → ARd Top2-3
UMAREN_PRESETS['umaren_C'] = {
    'label': '馬連C: rw1=rp1合意 → ARd Top3 (厳選)',
    'desc': 'rank_w=1とrank_p=1が同一馬の場合のみ発動。最強の本命軸',
}

# umaren_D: rw1軸 → 危険馬除外ARd Top2 (2点)
UMAREN_PRESETS['umaren_D'] = {
    'label': '馬連D: rw1軸→危険除外ARd Top2 (2点)',
    'desc': 'rank_w=1軸、危険馬(odds<=8&ARd<53&V%<15%)を除いたARd Top2',
}

# --- VB条件付き馬連（軸がVB条件を満たすレースのみ発動） ---

# umaren_E: VB軸(gap3+EV1.3+m60) → ARd Top2 (2点)
UMAREN_PRESETS['umaren_E'] = {
    'label': '馬連E: VB軸(gap3+EV1.3)→ARd2 (厳選2点)',
    'desc': '軸がtansho_H条件(rw1+gap3+EV1.3+m60)の時だけ馬連',
    'axis_filter': dict(max_rank_w=1, min_gap=3, min_ev=1.3, max_margin=60),
    'n_partners': 2,
    'partner_method': 'ard',
}

# umaren_F: VB軸(gap3+EV1.3+m60) → ARd Top3 (3点)
UMAREN_PRESETS['umaren_F'] = {
    'label': '馬連F: VB軸(gap3+EV1.3)→ARd3 (厳選3点)',
    'desc': '軸がtansho_H条件の時、ARd上位3頭',
    'axis_filter': dict(max_rank_w=1, min_gap=3, min_ev=1.3, max_margin=60),
    'n_partners': 3,
    'partner_method': 'ard',
}

# umaren_G: VB軸(gap4+EV1.3+m60) → ARd Top2 (intersection級厳選)
UMAREN_PRESETS['umaren_G'] = {
    'label': '馬連G: VB軸(gap4+EV1.3)→ARd2 (超厳選)',
    'desc': '軸がintersection条件の時だけ馬連',
    'axis_filter': dict(max_rank_w=1, min_gap=4, min_ev=1.3, max_margin=60),
    'n_partners': 2,
    'partner_method': 'ard',
}

# umaren_H: VB+合意軸 (rw1=rp1, gap3+EV1.2) → ARd Top2
UMAREN_PRESETS['umaren_H'] = {
    'label': '馬連H: 合意+VB(gap3)→ARd2',
    'desc': 'rw1=rp1合意+gap3+EV1.2の時だけ馬連',
    'axis_filter': dict(max_rank_w=1, min_gap=3, min_ev=1.2, max_margin=60),
    'require_consensus': True,
    'n_partners': 2,
    'partner_method': 'ard',
}

# umaren_I: VB軸 → rp Top2 (Placeモデル相手)
UMAREN_PRESETS['umaren_I'] = {
    'label': '馬連I: VB軸(gap3+EV1.3)→rp2',
    'desc': '軸はWモデル、相手はPモデル上位',
    'axis_filter': dict(max_rank_w=1, min_gap=3, min_ev=1.3, max_margin=60),
    'n_partners': 2,
    'partner_method': 'rp',
}


def extract_umaren_bets(cache: list, hm_data: dict, preset_key: str) -> List[Bet]:
    bets = []
    for race in cache:
        rid = str(race['race_id'])
        date_str = f"{rid[:4]}/{rid[4:6]}/{rid[6:8]}"

        # haraimodoshi lookup: RACE_CODEは16桁フルrace_id
        payouts = hm_data.get(rid)
        if not payouts or payouts["flags"].get("UMAREN"):
            continue

        entries = race['entries']
        valid = [e for e in entries if (e.get("odds") or 0) > 0]
        if len(valid) < 2:
            continue

        pairs = _get_umaren_pairs(valid, preset_key, UMAREN_PRESETS[preset_key])
        for pair in pairs:
            pay = _match_umaren(payouts, pair)
            # ソートして表示名
            sorted_pair = tuple(sorted(pair))
            bets.append(Bet(
                date=date_str, race_id=rid,
                umaban=0,
                horse_name=f"{sorted_pair[0]}-{sorted_pair[1]}",
                odds=pay / 100 if pay else 0,
                is_hit=pay > 0,
                payout_per_100=pay,
                bet_type='馬連',
            ))

    bets.sort(key=lambda b: (b.date, b.race_id))
    return bets


def _get_umaren_pairs(entries: list, preset_key: str, preset_cfg: dict = None) -> List[frozenset]:
    """プリセットに応じた馬連ペアを返す"""
    if preset_key == 'umaren_A':
        return _umaren_rw1_ard_top(entries, n_partners=3)
    elif preset_key == 'umaren_B':
        return _umaren_rw1_rp_top(entries, n_partners=3)
    elif preset_key == 'umaren_C':
        return _umaren_consensus_ard(entries, n_partners=3)
    elif preset_key == 'umaren_D':
        return _umaren_rw1_nodanger_ard(entries, n_partners=2)
    elif preset_cfg and preset_cfg.get('axis_filter'):
        return _umaren_vb_axis(entries, preset_cfg)
    return []


def _umaren_rw1_ard_top(entries, n_partners=3):
    """rank_w=1軸 → ARd上位(軸除く) n点"""
    axis_list = [e for e in entries if (e.get('rank_w') or 99) == 1]
    if not axis_list:
        return []
    axis = axis_list[0]
    ard_sorted = sorted(
        [e for e in entries if e['umaban'] != axis['umaban']],
        key=lambda e: -(e.get('ar_deviation') or 0)
    )[:n_partners]
    return [frozenset({axis['umaban'], t['umaban']}) for t in ard_sorted]


def _umaren_rw1_rp_top(entries, n_partners=3):
    """rank_w=1軸 → rank_p上位(軸除く) n点"""
    axis_list = [e for e in entries if (e.get('rank_w') or 99) == 1]
    if not axis_list:
        return []
    axis = axis_list[0]
    rp_sorted = sorted(
        [e for e in entries if e['umaban'] != axis['umaban']],
        key=lambda e: (e.get('rank_p') or 99)
    )[:n_partners]
    return [frozenset({axis['umaban'], t['umaban']}) for t in rp_sorted]


def _umaren_consensus_ard(entries, n_partners=3):
    """rank_w=1 & rank_p=1 が同一馬の場合のみ → ARd Top n"""
    rw1 = [e for e in entries if (e.get('rank_w') or 99) == 1]
    rp1 = [e for e in entries if (e.get('rank_p') or 99) == 1]
    if not rw1 or not rp1:
        return []
    if rw1[0]['umaban'] != rp1[0]['umaban']:
        return []  # 合意なし → 見送り
    axis = rw1[0]
    ard_sorted = sorted(
        [e for e in entries if e['umaban'] != axis['umaban']],
        key=lambda e: -(e.get('ar_deviation') or 0)
    )[:n_partners]
    return [frozenset({axis['umaban'], t['umaban']}) for t in ard_sorted]


def _umaren_vb_axis(entries, preset_cfg):
    """VB条件付き馬連: 軸がフィルタ条件を満たす場合のみ発動"""
    af = preset_cfg['axis_filter']
    n_partners = preset_cfg.get('n_partners', 2)
    partner_method = preset_cfg.get('partner_method', 'ard')
    require_consensus = preset_cfg.get('require_consensus', False)

    # 軸候補
    axis_list = []
    for e in entries:
        if _tansho_filter(e, None, **af):
            axis_list.append(e)
    if not axis_list:
        return []

    axis = axis_list[0]

    # 合意チェック (rw1 = rp1)
    if require_consensus:
        rp1 = [e for e in entries if (e.get('rank_p') or 99) == 1]
        if not rp1 or rp1[0]['umaban'] != axis['umaban']:
            return []

    # 相手選出
    others = [e for e in entries if e['umaban'] != axis['umaban'] and (e.get('odds') or 0) > 0]
    if partner_method == 'rp':
        partners = sorted(others, key=lambda e: (e.get('rank_p') or 99))[:n_partners]
    else:  # ard
        partners = sorted(others, key=lambda e: -(e.get('ar_deviation') or 0))[:n_partners]

    return [frozenset({axis['umaban'], p['umaban']}) for p in partners]


def _umaren_rw1_nodanger_ard(entries, n_partners=2):
    """rank_w=1軸 → 危険馬除外してARd Top n"""
    axis_list = [e for e in entries if (e.get('rank_w') or 99) == 1]
    if not axis_list:
        return []
    axis = axis_list[0]
    danger = set()
    for e in entries:
        odds = e.get("odds") or 999
        ard = e.get("ar_deviation") or 99
        v_pct = e.get("pred_proba_p_raw") or 1.0
        if 0 < odds <= 8 and ard < 53 and v_pct < 0.15:
            danger.add(e["umaban"])
    candidates = [e for e in entries
                  if e['umaban'] != axis['umaban'] and e['umaban'] not in danger]
    ard_sorted = sorted(candidates, key=lambda e: -(e.get('ar_deviation') or 0))[:n_partners]
    return [frozenset({axis['umaban'], t['umaban']}) for t in ard_sorted]


# ============================================================
# 複勝系プリセット
# ============================================================

FUKUSHO_PRESETS = {}

# fukusho_A: rank_p=1 全買い
FUKUSHO_PRESETS['fukusho_A'] = {
    'label': '複勝A: rp1全買い',
    'params': dict(max_rank_p=1),
}

# fukusho_B: rank_p=1 + place_ev>=1.2
FUKUSHO_PRESETS['fukusho_B'] = {
    'label': '複勝B: rp1+PEV1.2',
    'params': dict(max_rank_p=1, min_place_ev=1.2),
}

# fukusho_C: rank_p=1 + ARd>=55 (能力担保)
FUKUSHO_PRESETS['fukusho_C'] = {
    'label': '複勝C: rp1+ARd55',
    'params': dict(max_rank_p=1, min_ard=55),
}

# fukusho_D: rank_p=1 + rw<=3 (Winモデルもそこそこ推し)
FUKUSHO_PRESETS['fukusho_D'] = {
    'label': '複勝D: rp1+rw3以内',
    'params': dict(max_rank_p=1, max_rank_w=3),
}

# fukusho_E: rw1 + place_ev>=1.3 (Winモデル1位の複勝)
FUKUSHO_PRESETS['fukusho_E'] = {
    'label': '複勝E: rw1+PEV1.3',
    'params': dict(max_rank_p=99, max_rank_w=1, min_place_ev=1.3),
}

# fukusho_F: rp1 + PEV>=1.5 + ARd>=55 (高EV+能力担保)
FUKUSHO_PRESETS['fukusho_F'] = {
    'label': '複勝F: rp1+PEV1.5+ARd55',
    'params': dict(max_rank_p=1, min_place_ev=1.5, min_ard=55),
}

# fukusho_G: rp1 + rw<=2 + PEV>=1.3 (両モデル推し+EV)
FUKUSHO_PRESETS['fukusho_G'] = {
    'label': '複勝G: rp1+rw2+PEV1.3',
    'params': dict(max_rank_p=1, max_rank_w=2, min_place_ev=1.3),
}

# fukusho_H: VB条件(rw1+gap3) の複勝 (単勝VBの保険)
FUKUSHO_PRESETS['fukusho_H'] = {
    'label': '複勝H: VB単勝の複勝保険(rw1+gap3)',
    'params': dict(max_rank_p=99, max_rank_w=1, min_gap=3),
}


def extract_fukusho_bets(cache: list, preset_key: str) -> List[Bet]:
    params = FUKUSHO_PRESETS[preset_key]['params']
    max_rp = params.get('max_rank_p', 99)
    max_rw = params.get('max_rank_w', 99)
    min_pev = params.get('min_place_ev', 0)
    min_ard = params.get('min_ard', 0)
    min_gap = params.get('min_gap', 0)

    bets = []
    for race in cache:
        rid = str(race['race_id'])
        date_str = f"{rid[:4]}/{rid[4:6]}/{rid[6:8]}"
        n_entries = len([e for e in race['entries'] if (e.get('odds') or 0) > 0])
        for e in race['entries']:
            rp = e.get('rank_p') or 99
            rw = e.get('rank_w') or 99
            ard = e.get('ar_deviation') or 0
            odds = e.get('odds') or 0
            gap = e.get('win_vb_gap') or 0

            if odds <= 0:
                continue

            # place_ev推定: 実値があればそれを使い、なければ近似
            pev = e.get('place_ev')
            if pev is None or pev == 0:
                place_odds = e.get('place_odds_min') or (odds / 3.5)
                p_raw = e.get('pred_proba_p_raw') or 0
                pev = place_odds * p_raw * 3 if p_raw > 0 else 0

            if rp > max_rp:
                continue
            if rw > max_rw:
                continue
            if pev < min_pev:
                continue
            if ard < min_ard:
                continue
            if gap < min_gap:
                continue

            is_top3 = bool(e.get('is_top3'))
            place_odds = e.get('place_odds_min') or (odds / 3.5)
            payout = int(place_odds * 100) if is_top3 else 0

            bets.append(Bet(
                date=date_str, race_id=rid,
                umaban=e.get('umaban', 0),
                horse_name=e.get('horse_name', ''),
                odds=place_odds,
                is_hit=is_top3,
                payout_per_100=payout,
                bet_type='複勝',
                ar_deviation=ard,
                rank_w=rw,
            ))

    bets.sort(key=lambda b: (b.date, b.race_id))
    return bets


# ============================================================
# Bankroll Simulation
# ============================================================

@dataclass
class SimConfig:
    name: str
    initial_balance: int = 100000
    sizing: str = 'fixed'       # 'fixed' / 'proportional' / 'kelly'
    unit_amount: int = 500
    bet_pct: float = 3.0
    kelly_fraction: float = 0.25
    kelly_cap: float = 0.10
    min_bet: int = 100


def calc_bet_size(cfg: SimConfig, balance: int, bet: Bet) -> int:
    if cfg.sizing == 'fixed':
        raw = cfg.unit_amount
    elif cfg.sizing == 'proportional':
        raw = balance * cfg.bet_pct / 100
    elif cfg.sizing == 'kelly':
        if bet.bet_type == '単勝' and bet.win_ev > 1:
            # 単勝: Kelly criterion f = (p*b - q) / b ≈ (EV-1) / (odds-1)
            ev = bet.win_ev
            odds = bet.odds
            if odds > 1:
                f = (ev - 1) / (odds - 1)
                f = min(f, cfg.kelly_cap)
                f *= cfg.kelly_fraction
                raw = balance * f
            else:
                raw = cfg.min_bet
        else:
            # 馬連等: EVが事前に不明なので固定比率(2%)を使用
            raw = balance * 0.02
    else:
        raw = cfg.min_bet

    amount = max(cfg.min_bet, int(raw / 100) * 100)
    amount = min(amount, int(balance * 0.15 / 100) * 100)
    return max(cfg.min_bet, amount)


@dataclass
class SimResult:
    label: str
    mode: str               # preset key for Web UI
    bet_type: str
    budget_label: str
    num_bets: int
    num_hits: int
    hit_rate: float
    flat_roi: float         # 定額100円ベースROI
    flat_pnl: int           # 定額P&L
    sim_final: int          # バンクロールSim最終残高
    roi_pct: float          # バンクロール成長率 %
    sim_max_dd: float       # 最大ドローダウン %
    calmar: float           # Calmar比率
    sharpe: float           # 月次Sharpe
    # 日次集計
    bet_days: int = 0
    win_days: int = 0
    lose_days: int = 0
    max_win_streak: int = 0
    max_loss_streak: int = 0
    # 券種別内訳
    win_bets: int = 0
    place_bets: int = 0
    umaren_bets: int = 0
    win_hit_rate: float = 0
    place_hit_rate: float = 0
    umaren_hit_rate: float = 0
    # チャート用 history
    history: list = field(default_factory=list)  # [{date, bankroll}]


def run_simulation(bets: List[Bet], label: str, mode: str, bet_type: str,
                   cfg: SimConfig, budget_label: str = '3%') -> SimResult:
    """バンクロールシミュレーション実行（history付き）"""
    if not bets:
        return SimResult(
            label=label, mode=mode, bet_type=bet_type, budget_label=budget_label,
            num_bets=0, num_hits=0, hit_rate=0, flat_roi=0, flat_pnl=0,
            sim_final=cfg.initial_balance, roi_pct=0, sim_max_dd=0,
            calmar=0, sharpe=0,
            history=[{'date': None, 'bankroll': cfg.initial_balance}],
        )

    # 1) Flat ROI (100円均一)
    total_wagered = len(bets) * 100
    total_returned = sum(b.payout_per_100 for b in bets)
    num_hits = sum(1 for b in bets if b.is_hit)
    flat_roi = (total_returned / total_wagered * 100) if total_wagered > 0 else 0
    flat_pnl = total_returned - total_wagered

    # 2) Bankroll sim with daily aggregation
    balance = cfg.initial_balance
    peak = balance
    max_dd_pct = 0.0
    monthly_pnl = defaultdict(int)
    daily_pnl = defaultdict(int)
    history = [{'date': None, 'bankroll': cfg.initial_balance}]

    for bet in bets:
        if balance < cfg.min_bet:
            break
        bet_amount = calc_bet_size(cfg, balance, bet)
        returned = int(bet.odds * bet_amount) if bet.is_hit else 0
        pnl = returned - bet_amount
        balance += pnl

        # date key: YYYYMMDD
        date_key = bet.date.replace('/', '')
        daily_pnl[date_key] += pnl
        month_key = bet.date[:7]
        monthly_pnl[month_key] += pnl

        peak = max(peak, balance)
        if peak > 0:
            dd = (peak - balance) / peak * 100
            max_dd_pct = max(max_dd_pct, dd)

    # Build history from daily balance changes
    running = cfg.initial_balance
    for date_key in sorted(daily_pnl.keys()):
        running += daily_pnl[date_key]
        history.append({'date': date_key, 'bankroll': running})

    roi_pct = round((balance / cfg.initial_balance - 1) * 100, 1)
    calmar = roi_pct / max_dd_pct if max_dd_pct > 0 else (99.0 if roi_pct > 0 else 0)

    # Daily win/loss stats
    sorted_dates = sorted(daily_pnl.keys())
    bet_days = len(sorted_dates)
    win_days = sum(1 for d in sorted_dates if daily_pnl[d] > 0)
    lose_days = sum(1 for d in sorted_dates if daily_pnl[d] <= 0)

    # Streaks
    max_win_streak = max_loss_streak = 0
    cur_win = cur_loss = 0
    for d in sorted_dates:
        if daily_pnl[d] > 0:
            cur_win += 1
            cur_loss = 0
            max_win_streak = max(max_win_streak, cur_win)
        else:
            cur_loss += 1
            cur_win = 0
            max_loss_streak = max(max_loss_streak, cur_loss)

    # Monthly Sharpe
    monthly_vals = list(monthly_pnl.values())
    if len(monthly_vals) >= 2:
        mean_m = sum(monthly_vals) / len(monthly_vals)
        std_m = (sum((v - mean_m) ** 2 for v in monthly_vals) / (len(monthly_vals) - 1)) ** 0.5
        sharpe = mean_m / std_m if std_m > 0 else 0
    else:
        sharpe = 0

    # 券種別内訳
    win_bets_n = sum(1 for b in bets if b.bet_type == '単勝')
    place_bets_n = sum(1 for b in bets if b.bet_type == '複勝')
    umaren_bets_n = sum(1 for b in bets if b.bet_type == '馬連')
    win_hits = sum(1 for b in bets if b.bet_type == '単勝' and b.is_hit)
    place_hits = sum(1 for b in bets if b.bet_type == '複勝' and b.is_hit)
    umaren_hits = sum(1 for b in bets if b.bet_type == '馬連' and b.is_hit)

    return SimResult(
        label=label, mode=mode, bet_type=bet_type, budget_label=budget_label,
        num_bets=len(bets), num_hits=num_hits,
        hit_rate=round(num_hits / len(bets) * 100, 1) if bets else 0,
        flat_roi=round(flat_roi, 1), flat_pnl=flat_pnl,
        sim_final=balance, roi_pct=roi_pct,
        sim_max_dd=round(max_dd_pct, 1),
        calmar=round(calmar, 2), sharpe=round(sharpe, 3),
        bet_days=bet_days, win_days=win_days, lose_days=lose_days,
        max_win_streak=max_win_streak, max_loss_streak=max_loss_streak,
        win_bets=win_bets_n, place_bets=place_bets_n, umaren_bets=umaren_bets_n,
        win_hit_rate=round(win_hits / win_bets_n * 100, 1) if win_bets_n else 0,
        place_hit_rate=round(place_hits / place_bets_n * 100, 1) if place_bets_n else 0,
        umaren_hit_rate=round(umaren_hits / umaren_bets_n * 100, 1) if umaren_bets_n else 0,
        history=history,
    )


# ============================================================
# Output
# ============================================================

def print_results_table(results: List[SimResult], title: str):
    print(f"\n{'='*110}")
    print(f"  {title}")
    print(f"{'='*110}")
    header = (f"{'Preset':<22} {'Budget':<7} {'Type':<5} {'Bets':>5} {'Hits':>5} {'Hit%':>6} "
              f"{'FlatROI':>8} {'PnL':>8} {'Final':>8} {'Growth':>8} {'MaxDD':>7} "
              f"{'Calmar':>7} {'Sharpe':>7} {'W/L':>7}")
    print(header)
    print("-" * 110)

    for r in results:
        line = (
            f"{r.label:<22} {r.budget_label:<7} {r.bet_type:<5} "
            f"{r.num_bets:>5} {r.num_hits:>5} {r.hit_rate:>5.1f}% "
            f"{r.flat_roi:>7.1f}% {r.flat_pnl:>+7,} "
            f"{r.sim_final:>8,} {r.roi_pct:>+7.1f}% "
            f"{r.sim_max_dd:>6.1f}% {r.calmar:>7.2f} {r.sharpe:>7.3f} "
            f"{r.win_days:>3}/{r.lose_days:<3}"
        )
        print(line)
    print()


def print_monthly_detail(bets: List[Bet], label: str):
    """月次ブレイクダウン"""
    monthly = defaultdict(lambda: {'bets': 0, 'hits': 0, 'wagered': 0, 'returned': 0})
    for b in bets:
        m = b.date[:7]
        monthly[m]['bets'] += 1
        monthly[m]['hits'] += 1 if b.is_hit else 0
        monthly[m]['wagered'] += 100
        monthly[m]['returned'] += b.payout_per_100

    print(f"\n  [{label}] 月次ブレイクダウン")
    print(f"  {'Month':<8} {'Bets':>5} {'Hits':>5} {'ROI':>8} {'PnL':>8}")
    for m in sorted(monthly.keys()):
        d = monthly[m]
        roi = d['returned'] / d['wagered'] * 100 if d['wagered'] else 0
        pnl = d['returned'] - d['wagered']
        print(f"  {m:<8} {d['bets']:>5} {d['hits']:>5} {roi:>7.1f}% {pnl:>+7,}")


# ============================================================
# JSON Export (Web UI互換フォーマット)
# ============================================================

def result_to_dict(r: SimResult) -> dict:
    """SimResult → bankroll_simulation.json 互換dict"""
    return {
        'preset': r.mode,
        'budget_label': r.budget_label,
        'mode': r.mode,
        'label': r.label,
        'final_bankroll': r.sim_final,
        'roi_pct': r.roi_pct,
        'flat_roi': r.flat_roi,
        'max_dd': r.sim_max_dd,
        'sharpe': r.sharpe,
        'calmar': r.calmar,
        'bet_days': r.bet_days,
        'total_bets': r.num_bets,
        'win_days': r.win_days,
        'lose_days': r.lose_days,
        'max_loss_streak': r.max_loss_streak,
        'max_win_streak': r.max_win_streak,
        'history': r.history,
        'win_bets': r.win_bets,
        'place_bets': r.place_bets,
        'umaren_bets': r.umaren_bets,
        'win_hit_rate': r.win_hit_rate,
        'place_hit_rate': r.place_hit_rate,
        'umaren_hit_rate': r.umaren_hit_rate,
    }


def export_json(all_results: List[SimResult], initial: int, output_path: Path,
                label: Optional[str] = None):
    """bankroll_simulation.json 互換フォーマットで出力"""
    # ユニークなmode/budget_label
    modes = list(dict.fromkeys(r.mode for r in all_results))
    budget_labels = list(dict.fromkeys(r.budget_label for r in all_results))

    budget_pct_map = {
        '1%': 0.01, '2%': 0.02, '3%': 0.03, '5%': 0.05,
        'flat500': 0, 'K1/4': 0,
    }

    data = {
        'model_version': label or 'polaris-2.0 (strategy-redesign)',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'initial_bankroll': initial,
        'budget_configs': [
            {'label': bl, 'pct': budget_pct_map.get(bl, 0)}
            for bl in budget_labels
        ],
        'strategies': [
            {'mode': m, 'label': next((r.label for r in all_results if r.mode == m), m)}
            for m in modes
        ],
        'presets': modes,
        'results': [result_to_dict(r) for r in all_results],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n[Export] {output_path} ({len(all_results)} results)")


# ============================================================
# 新プリセット定義（Web UI用 3+コンボ）
# ============================================================

# 新プリセットの名前とベット抽出を定義
NEW_PRESETS = {
    'tansho_ippon': {
        'label': '単勝一本',
        'desc': 'rw1+gap≥3+EV≥1.3+margin≤60',
        'tansho_key': 'tansho_H',
    },
    'honmei_umaren': {
        'label': '本命馬連',
        'desc': '単勝一本と同じ軸 + rp相手2点',
        'tansho_key': 'tansho_H',
        'umaren_key': 'umaren_I',
    },
    'umaren_hirome': {
        'label': '馬連広め',
        'desc': '単勝一本と同じ軸 + ARd相手3点',
        'tansho_key': 'tansho_H',
        'umaren_key': 'umaren_F',
    },
}


def extract_combo_bets(cache, hm_data, preset_cfg) -> List[Bet]:
    """新プリセット用: 単勝+馬連を組み合わせたベットリスト"""
    bets = extract_tansho_bets(cache, preset_cfg['tansho_key'])
    if preset_cfg.get('umaren_key'):
        umaren = extract_umaren_bets(cache, hm_data, preset_cfg['umaren_key'])
        bets.extend(umaren)
    bets.sort(key=lambda b: (b.date, b.race_id))
    return bets


# ============================================================
# Main
# ============================================================

BUDGET_CONFIGS = [
    ('1%', SimConfig(name='1%', sizing='proportional', bet_pct=1.0)),
    ('2%', SimConfig(name='2%', sizing='proportional', bet_pct=2.0)),
    ('3%', SimConfig(name='3%', sizing='proportional', bet_pct=3.0)),
    ('5%', SimConfig(name='5%', sizing='proportional', bet_pct=5.0)),
    ('flat500', SimConfig(name='flat500', sizing='fixed', unit_amount=500)),
    ('K1/4', SimConfig(name='K1/4', sizing='kelly', kelly_fraction=0.25)),
]


def main():
    parser = argparse.ArgumentParser(description='戦略プリセット再設計シミュレーション')
    parser.add_argument('--initial', type=int, default=100000)
    parser.add_argument('--export', action='store_true', help='bankroll_simulation.json出力')
    parser.add_argument('--scan', action='store_true', help='全プリセットスキャン（探索モード）')
    parser.add_argument('--monthly', action='store_true', help='月次詳細出力')
    parser.add_argument('--cache', type=str, default=None,
                        help='backtest_cacheファイルパス (例: data3/ml/backtest_cache_v7.9.json)')
    parser.add_argument('--label', type=str, default=None,
                        help='モデルバージョンラベル (例: v7.9)')
    args = parser.parse_args()

    initial = args.initial

    print(f"\n{'#'*70}")
    print(f"  戦略プリセット再設計シミュレーション")
    print(f"  Initial: ¥{initial:,}")
    print(f"{'#'*70}")

    # === Load Data ===
    cache = load_cache(args.cache)
    race_codes = [str(r['race_id']) for r in cache]
    print(f"\n[Load] haraimodoshi for {len(race_codes):,} races...")
    hm_data = load_haraimodoshi(race_codes)
    print(f"  {len(hm_data):,} races with payouts")

    if args.scan:
        # === 探索モード: 全プリセットを3%で比較 ===
        cfg = SimConfig(name='3%', initial_balance=initial, sizing='proportional', bet_pct=3.0)

        tansho_results = []
        for key in sorted(TANSHO_PRESETS.keys()):
            bets = extract_tansho_bets(cache, key)
            label = TANSHO_PRESETS[key]['label']
            res = run_simulation(bets, label, key, '単勝', cfg, '3%')
            tansho_results.append(res)
            if args.monthly and bets:
                print_monthly_detail(bets, label)
        print_results_table(tansho_results, "単勝系プリセット比較")

        umaren_results = []
        for key in sorted(UMAREN_PRESETS.keys()):
            bets = extract_umaren_bets(cache, hm_data, key)
            label = UMAREN_PRESETS[key]['label']
            res = run_simulation(bets, label, key, '馬連', cfg, '3%')
            umaren_results.append(res)
            if args.monthly and bets:
                print_monthly_detail(bets, label)
        print_results_table(umaren_results, "馬連系プリセット比較")

        fukusho_results = []
        for key in sorted(FUKUSHO_PRESETS.keys()):
            bets = extract_fukusho_bets(cache, key)
            label = FUKUSHO_PRESETS[key]['label']
            res = run_simulation(bets, label, key, '複勝', cfg, '3%')
            fukusho_results.append(res)
        print_results_table(fukusho_results, "複勝系プリセット比較")

        all_results = tansho_results + umaren_results + fukusho_results
        by_roi = sorted(all_results, key=lambda r: -r.flat_roi)
        print("\n  [Flat ROI Top 5]")
        for i, r in enumerate(by_roi[:5], 1):
            print(f"  {i}. {r.label} — ROI {r.flat_roi:.1f}%, PnL {r.flat_pnl:+,}, "
                  f"{r.num_bets} bets")
        return

    # === メインモード: 新3プリセット × 複数budget ===
    print(f"\n[Main] 新プリセット × {len(BUDGET_CONFIGS)} budgets")

    all_results: List[SimResult] = []

    for preset_key, preset_cfg in NEW_PRESETS.items():
        bets = extract_combo_bets(cache, hm_data, preset_cfg)
        print(f"  {preset_key} ({preset_cfg['label']}): {len(bets)} bets")

        for budget_label, budget_cfg in BUDGET_CONFIGS:
            budget_cfg.initial_balance = initial
            res = run_simulation(
                bets, preset_cfg['label'], preset_key,
                'combo' if preset_cfg.get('umaren_key') else '単勝',
                budget_cfg, budget_label,
            )
            all_results.append(res)

    # Print comparison for default budget
    default_results = [r for r in all_results if r.budget_label == '3%']
    print_results_table(default_results, "新プリセット比較 (3%)")

    # Print all budgets for each preset
    for preset_key in NEW_PRESETS:
        preset_results = [r for r in all_results if r.mode == preset_key]
        print_results_table(preset_results, f"{NEW_PRESETS[preset_key]['label']} — Budget比較")

    # === Export ===
    if args.export:
        out_path = Path(config.data_root()) / 'ml' / 'bankroll_simulation.json'
        export_json(all_results, initial, out_path, label=args.label)

    print()


if __name__ == "__main__":
    main()

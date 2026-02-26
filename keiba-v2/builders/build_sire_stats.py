#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
種牡馬(sire)・母馬(dam)・母父(bms)統計インデックス構築

race JSONsとpedigree_index.jsonから、sire/dam/bms別の集計統計を構築。
ベースライン(勝率/複勝率) + 条件別統計を算出。

対応仮説:
  H0: ベースライン (sire/bms基本勝率・複勝率)
  H3: 休み明け上昇型 (days >= 56)
  H4: 間隔詰め疲労型 (days <= 21)
  H5: 瞬発vs持続適性 (RPCI >= 55 vs <= 45)
  H6: 成長曲線 (age <= 3 vs age >= 4)

Usage:
    python -m builders.build_sire_stats             # ビルドのみ
    python -m builders.build_sire_stats --analyze    # ビルド + 全仮説分析
"""

import json
import sys
import time
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.jravan import um_parser


# ============================================================
# ベイズ平滑化パラメータ (past_features.pyと同じ)
# ============================================================
PRIOR_WIN_ALPHA = 1.0
PRIOR_WIN_BETA = 12.0      # prior mean ≈ 0.077

PRIOR_TOP3_ALPHA = 2.5
PRIOR_TOP3_BETA = 7.5      # prior mean = 0.25


def bayesian_rate(successes: int, total: int, alpha: float, beta: float) -> float:
    """ベイズ平滑化レート (Beta-Binomial posterior mean)"""
    return round((successes + alpha) / (total + alpha + beta), 4)


# ============================================================
# 条件閾値
# ============================================================
FRESH_DAYS = 56     # 8週以上 = 休み明け
TIGHT_DAYS = 21     # 3週以内 = 間隔詰め
MIN_RUNS_CONDITIONAL = 10  # 条件付きrateの最小サンプル数

# H5: 瞬発vs持続 (実データ: mean=51, SD=2.1, range=45-58)
# RPCI = last_3f / (first_3f + last_3f) * 100
# 高RPCI = 後半遅い = 前傾（ハイペース）= 持続/消耗レース
# 低RPCI = 後半速い = 後傾（スロー）= 瞬発レース
RPCI_SPRINT_THRESHOLD = 49     # RPCI <= 49 = 後傾（瞬発レース）
RPCI_SUSTAINED_THRESHOLD = 53  # RPCI >= 53 = 前傾（持続レース）

# H5b: レースタイプ3カテゴリ（race_trend_v2ベース）
RACE_TYPE_SPRINT = {'sprint', 'sprint_mild'}            # 瞬発系
RACE_TYPE_BALANCE = {'even', 'long_sprint'}             # バランス
RACE_TYPE_SUSTAINED = {'sustained_hp', 'sustained_strong', 'sustained_doroashi'}  # 持続系

# H6: 成長曲線
YOUNG_AGE_MAX = 3   # 若駒: 2-3歳
MATURE_AGE_MIN = 4  # 本格期: 4歳以上


def load_sire_names() -> Dict[str, str]:
    """UM_DATAから繁殖登録番号→種牡馬/母馬/母父名マッピングを構築

    UM_DATA Ketto3Info (各46B = HansyokuNum 10B + Bamei 36B):
      @204: 父 (sire)
      @250: 母 (dam)
      @388: 母父 (BMS)
    """
    UM_LEN = 1609
    names: Dict[str, str] = {}
    files = um_parser.get_um_files(0)  # 全ファイル
    print(f"  Scanning {len(files)} UM files for sire/dam/BMS names...")

    for um_file in files:
        try:
            data = um_file.read_bytes()
        except Exception:
            continue

        num = len(data) // UM_LEN
        for i in range(num):
            off = i * UM_LEN
            # 簡易レコードタイプチェック
            if data[off:off + 2] != b'UM':
                continue

            # 父: HansyokuNum @204(10B), Bamei @214(36B)
            sire_num = _extract_hansyoku(data, off + 204)
            if sire_num and sire_num not in names:
                sire_name = _extract_sjis(data, off + 214, 36)
                if sire_name:
                    names[sire_num] = sire_name

            # 母: HansyokuNum @250(10B), Bamei @260(36B)
            dam_num = _extract_hansyoku(data, off + 250)
            if dam_num and dam_num not in names:
                dam_name = _extract_sjis(data, off + 260, 36)
                if dam_name:
                    names[dam_num] = dam_name

            # 母父: HansyokuNum @388(10B), Bamei @398(36B)
            bms_num = _extract_hansyoku(data, off + 388)
            if bms_num and bms_num not in names:
                bms_name = _extract_sjis(data, off + 398, 36)
                if bms_name:
                    names[bms_num] = bms_name

    print(f"  Found {len(names):,} sire/dam/BMS names")
    return names


def _extract_hansyoku(data: bytes, offset: int) -> str:
    """10バイトのHansyokuNum抽出"""
    raw = data[offset:offset + 10]
    s = ''.join(chr(b) for b in raw if 0x30 <= b <= 0x39)
    return s if len(s) >= 8 else ''


def _extract_sjis(data: bytes, offset: int, length: int) -> str:
    """Shift-JIS名前抽出"""
    try:
        decoded = data[offset:offset + length].decode('shift_jis', errors='replace').strip()
        # サロゲート文字・置換文字を除去
        decoded = ''.join(c for c in decoded if not (0xD800 <= ord(c) <= 0xDFFF) and c != '\ufffd')
        return decoded.replace('\u3000', '').replace('@', '').strip()
    except Exception:
        return ''


def load_race_jsons() -> List[dict]:
    """全レースJSONを日付順にロード"""
    races_dir = config.races_dir()
    files = sorted(races_dir.glob("**/race_[0-9]*.json"))
    print(f"  Found {len(files):,} race files")

    races = []
    for f in files:
        try:
            with open(f, encoding='utf-8') as fp:
                race = json.load(fp)
            races.append(race)
        except Exception:
            continue

    # 日付順ソート
    races.sort(key=lambda r: r.get('date', ''))
    return races


def load_pedigree_index() -> Dict[str, dict]:
    """pedigree_index.jsonをロード"""
    path = config.indexes_dir() / "pedigree_index.json"
    if not path.exists():
        print(f"  [ERROR] pedigree_index.json not found: {path}")
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def build_sire_stats(races: List[dict], pedigree_index: Dict[str, dict]) -> dict:
    """sire/dam/bms別統計を構築

    各馬の前走日を追跡してdays_since_last_raceを計算し、
    sire/dam/bms別にベースライン+条件別の成績を集計。
    """

    # 馬ごとの最終出走日を追跡
    horse_last_date: Dict[str, str] = {}  # ketto_num → date string

    # sire/dam/bms別集計
    def _new_accum():
        return {
            'total_runs': 0, 'wins': 0, 'top3': 0,
            # H3/H4: 休み明け・間隔詰め
            'fresh_runs': 0, 'fresh_wins': 0, 'fresh_top3': 0,
            'tight_runs': 0, 'tight_wins': 0, 'tight_top3': 0,
            'normal_runs': 0, 'normal_wins': 0, 'normal_top3': 0,
            # H5: 瞬発vs持続 (RPCIベース)
            'sprint_runs': 0, 'sprint_wins': 0, 'sprint_top3': 0,
            'sustained_runs': 0, 'sustained_wins': 0, 'sustained_top3': 0,
            # H5b: レースタイプ3カテゴリ (race_trend_v2ベース)
            'cat_sprint_runs': 0, 'cat_sprint_wins': 0, 'cat_sprint_top3': 0,
            'cat_balance_runs': 0, 'cat_balance_wins': 0, 'cat_balance_top3': 0,
            'cat_sustained_runs': 0, 'cat_sustained_wins': 0, 'cat_sustained_top3': 0,
            # H6: 成長曲線
            'young_runs': 0, 'young_wins': 0, 'young_top3': 0,
            'mature_runs': 0, 'mature_wins': 0, 'mature_top3': 0,
        }

    sire_stats = defaultdict(_new_accum)
    dam_stats = defaultdict(_new_accum)
    bms_stats = defaultdict(_new_accum)

    total_entries = 0
    matched_entries = 0
    no_prev_race = 0

    for race in races:
        race_date = race.get('date', '')
        if not race_date:
            continue

        # H5: レース単位のRPCI取得
        pace = race.get('pace') or {}
        rpci = pace.get('rpci')
        # H5b: レースタイプ3カテゴリ
        race_type_cat = _classify_race_type(pace.get('race_trend_v2'))

        entries = race.get('entries', [])
        for entry in entries:
            ketto_num = entry.get('ketto_num', '')
            if not ketto_num:
                continue

            finish = entry.get('finish_position')
            if finish is None or finish == 0:
                continue  # 出走取消・競走中止

            total_entries += 1

            # 血統ルックアップ
            ped = pedigree_index.get(ketto_num)
            if not ped:
                continue

            sire_id = ped.get('sire')
            dam_id = ped.get('dam')
            bms_id = ped.get('bms')
            if not sire_id and not dam_id and not bms_id:
                continue

            matched_entries += 1

            is_win = (finish == 1)
            is_top3 = (finish <= 3)

            # days_since_last_race 計算
            prev_date = horse_last_date.get(ketto_num)
            days = None
            if prev_date:
                try:
                    d1 = datetime.strptime(prev_date, '%Y-%m-%d')
                    d2 = datetime.strptime(race_date, '%Y-%m-%d')
                    days = (d2 - d1).days
                except ValueError:
                    pass
            else:
                no_prev_race += 1

            # 馬の最終出走日を更新
            horse_last_date[ketto_num] = race_date

            # 条件分類
            rest_cond = _classify_rest(days)
            pace_cond = _classify_pace(rpci)
            age_cond = _classify_age(entry.get('age'))

            # sire集計
            if sire_id:
                _accumulate(sire_stats[sire_id], is_win, is_top3,
                            rest_cond, pace_cond, age_cond, race_type_cat)

            # dam集計
            if dam_id:
                _accumulate(dam_stats[dam_id], is_win, is_top3,
                            rest_cond, pace_cond, age_cond, race_type_cat)

            # bms集計
            if bms_id:
                _accumulate(bms_stats[bms_id], is_win, is_top3,
                            rest_cond, pace_cond, age_cond, race_type_cat)

    print(f"  Total entries: {total_entries:,}")
    print(f"  Matched (pedigree): {matched_entries:,} ({matched_entries/max(total_entries,1)*100:.1f}%)")
    print(f"  No prev race (debut): {no_prev_race:,}")
    print(f"  Unique sires: {len(sire_stats):,}")
    print(f"  Unique dams: {len(dam_stats):,}")
    print(f"  Unique BMS: {len(bms_stats):,}")

    # 統計量を計算
    sire_result = _finalize_stats(sire_stats)
    dam_result = _finalize_stats(dam_stats)
    bms_result = _finalize_stats(bms_stats)

    return {
        'sire': sire_result,
        'dam': dam_result,
        'bms': bms_result,
        'meta': {
            'total_races': len(races),
            'total_entries': total_entries,
            'matched_entries': matched_entries,
            'unique_sires': len(sire_stats),
            'unique_dams': len(dam_stats),
            'unique_bms': len(bms_stats),
            'fresh_days_threshold': FRESH_DAYS,
            'tight_days_threshold': TIGHT_DAYS,
            'rpci_sprint_threshold': RPCI_SPRINT_THRESHOLD,
            'rpci_sustained_threshold': RPCI_SUSTAINED_THRESHOLD,
            'young_age_max': YOUNG_AGE_MAX,
            'mature_age_min': MATURE_AGE_MIN,
            'min_runs_conditional': MIN_RUNS_CONDITIONAL,
            'built_at': datetime.now().isoformat(timespec='seconds'),
        }
    }


def _classify_rest(days: Optional[int]) -> str:
    """休養日数を分類"""
    if days is None:
        return 'debut'  # 初出走
    if days >= FRESH_DAYS:
        return 'fresh'
    if days <= TIGHT_DAYS:
        return 'tight'
    return 'normal'


def _classify_pace(rpci: Optional[float]) -> Optional[str]:
    """H5: RPCI→瞬発/持続分類
    低RPCI = 後半速い = 瞬発レース, 高RPCI = 後半遅い = 持続レース
    """
    if rpci is None:
        return None
    if rpci <= RPCI_SPRINT_THRESHOLD:
        return 'sprint'
    if rpci >= RPCI_SUSTAINED_THRESHOLD:
        return 'sustained'
    return None  # 中間ペースは集計しない


def _classify_race_type(trend_v2: Optional[str]) -> Optional[str]:
    """H5b: race_trend_v2 → 3カテゴリ分類"""
    if not trend_v2:
        return None
    if trend_v2 in RACE_TYPE_SPRINT:
        return 'cat_sprint'
    if trend_v2 in RACE_TYPE_BALANCE:
        return 'cat_balance'
    if trend_v2 in RACE_TYPE_SUSTAINED:
        return 'cat_sustained'
    return None


def _classify_age(age) -> Optional[str]:
    """H6: 年齢→若駒/本格期分類"""
    if age is None or age == 0:
        return None
    if age <= YOUNG_AGE_MAX:
        return 'young'
    if age >= MATURE_AGE_MIN:
        return 'mature'
    return None


def _accumulate(stats: dict, is_win: bool, is_top3: bool,
                rest_cond: str, pace_cond: Optional[str],
                age_cond: Optional[str], race_type_cat: Optional[str] = None):
    """成績を加算"""
    stats['total_runs'] += 1
    if is_win:
        stats['wins'] += 1
    if is_top3:
        stats['top3'] += 1

    # H3/H4: 休み明け・間隔詰め
    if rest_cond != 'debut':
        stats[f'{rest_cond}_runs'] += 1
        if is_win:
            stats[f'{rest_cond}_wins'] += 1
        if is_top3:
            stats[f'{rest_cond}_top3'] += 1

    # H5: 瞬発vs持続 (RPCIベース)
    if pace_cond:
        stats[f'{pace_cond}_runs'] += 1
        if is_win:
            stats[f'{pace_cond}_wins'] += 1
        if is_top3:
            stats[f'{pace_cond}_top3'] += 1

    # H5b: レースタイプ3カテゴリ (race_trend_v2ベース)
    if race_type_cat:
        stats[f'{race_type_cat}_runs'] += 1
        if is_win:
            stats[f'{race_type_cat}_wins'] += 1
        if is_top3:
            stats[f'{race_type_cat}_top3'] += 1

    # H6: 成長曲線
    if age_cond:
        stats[f'{age_cond}_runs'] += 1
        if is_win:
            stats[f'{age_cond}_wins'] += 1
        if is_top3:
            stats[f'{age_cond}_top3'] += 1


def _finalize_stats(raw_stats: dict) -> dict:
    """生カウントからレート・差分を計算"""
    result = {}

    for sid, s in raw_stats.items():
        total = s['total_runs']
        if total == 0:
            continue

        entry = {
            'total_runs': total,
            'wins': s['wins'],
            'top3': s['top3'],
            'win_rate': bayesian_rate(s['wins'], total, PRIOR_WIN_ALPHA, PRIOR_WIN_BETA),
            'top3_rate': bayesian_rate(s['top3'], total, PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA),
        }

        # 条件別レート（runs >= MIN_RUNS_CONDITIONAL で有効）
        normal_top3_rate = None
        if s['normal_runs'] >= MIN_RUNS_CONDITIONAL:
            normal_top3_rate = bayesian_rate(
                s['normal_top3'], s['normal_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['normal_runs'] = s['normal_runs']
            entry['normal_top3_rate'] = normal_top3_rate

        if s['fresh_runs'] >= MIN_RUNS_CONDITIONAL:
            fresh_rate = bayesian_rate(
                s['fresh_top3'], s['fresh_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['fresh_runs'] = s['fresh_runs']
            entry['fresh_top3_rate'] = fresh_rate
            if normal_top3_rate is not None:
                entry['fresh_advantage'] = round(fresh_rate - normal_top3_rate, 4)

        if s['tight_runs'] >= MIN_RUNS_CONDITIONAL:
            tight_rate = bayesian_rate(
                s['tight_top3'], s['tight_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['tight_runs'] = s['tight_runs']
            entry['tight_top3_rate'] = tight_rate
            if normal_top3_rate is not None:
                entry['tight_penalty'] = round(tight_rate - normal_top3_rate, 4)

        # H5: 瞬発vs持続
        sprint_rate = None
        sustained_rate = None

        if s['sprint_runs'] >= MIN_RUNS_CONDITIONAL:
            sprint_rate = bayesian_rate(
                s['sprint_top3'], s['sprint_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['sprint_runs'] = s['sprint_runs']
            entry['sprint_top3_rate'] = sprint_rate

        if s['sustained_runs'] >= MIN_RUNS_CONDITIONAL:
            sustained_rate = bayesian_rate(
                s['sustained_top3'], s['sustained_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['sustained_runs'] = s['sustained_runs']
            entry['sustained_top3_rate'] = sustained_rate

        if sprint_rate is not None and sustained_rate is not None:
            entry['finish_type_pref'] = round(sprint_rate - sustained_rate, 4)

        # H5b: レースタイプ3カテゴリ
        for cat_key in ('cat_sprint', 'cat_balance', 'cat_sustained'):
            runs_key = f'{cat_key}_runs'
            top3_key = f'{cat_key}_top3'
            if s[runs_key] >= MIN_RUNS_CONDITIONAL:
                rate = bayesian_rate(
                    s[top3_key], s[runs_key],
                    PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
                entry[f'{cat_key}_runs'] = s[runs_key]
                entry[f'{cat_key}_top3_rate'] = rate

        # H6: 成長曲線
        young_rate = None
        mature_rate = None

        if s['young_runs'] >= MIN_RUNS_CONDITIONAL:
            young_rate = bayesian_rate(
                s['young_top3'], s['young_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['young_runs'] = s['young_runs']
            entry['young_top3_rate'] = young_rate

        if s['mature_runs'] >= MIN_RUNS_CONDITIONAL:
            mature_rate = bayesian_rate(
                s['mature_top3'], s['mature_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['mature_runs'] = s['mature_runs']
            entry['mature_top3_rate'] = mature_rate

        if young_rate is not None and mature_rate is not None:
            entry['maturity_index'] = round(mature_rate - young_rate, 4)

        result[sid] = entry

    return result


# ============================================================
# 分析モード
# ============================================================

def analyze_all_hypotheses(stats: dict):
    """全仮説(H3/H4/H5/H6)の統計的検証"""

    print(f"\n{'='*60}")
    print(f"  全血統仮説検証 (H3/H4/H5/H6)")
    print(f"{'='*60}")

    for label, data in [('Sire (父)', stats['sire']), ('Dam (母)', stats.get('dam', {})), ('BMS (母父)', stats['bms'])]:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        print(f"  Total entries: {len(data):,}")

        # H3/H4
        _analyze_hypothesis(data, 'fresh_advantage', 'H3 休み明け', '得意', '苦手')
        _analyze_hypothesis(data, 'tight_penalty', 'H4 間隔詰め', '得意', '苦手')

        # H5: 瞬発vs持続
        has_pref = [(sid, s) for sid, s in data.items() if 'finish_type_pref' in s]
        print(f"\n  Has finish_type_pref (sprint>=10 & sustained>=10): {len(has_pref):,}")

        if has_pref:
            prefs = [s['finish_type_pref'] for _, s in has_pref]
            _print_distribution("H5 finish_type_pref (正=瞬発型, 負=持続型)", prefs)

            # 瞬発得意Top 10
            top10 = sorted(has_pref, key=lambda x: x[1]['finish_type_pref'], reverse=True)[:10]
            print(f"\n  Top 10 瞬発得意 (sprint > sustained):")
            for sid, s in top10:
                print(f"    {sid}: pref={s['finish_type_pref']:+.4f} "
                      f"(sprint={s['sprint_runs']}走 rate={s['sprint_top3_rate']:.3f}, "
                      f"sustained={s['sustained_runs']}走 rate={s['sustained_top3_rate']:.3f})")

            # 持続得意Top 10
            bot10 = sorted(has_pref, key=lambda x: x[1]['finish_type_pref'])[:10]
            print(f"\n  Top 10 持続得意 (sustained > sprint):")
            for sid, s in bot10:
                print(f"    {sid}: pref={s['finish_type_pref']:+.4f} "
                      f"(sprint={s['sprint_runs']}走 rate={s['sprint_top3_rate']:.3f}, "
                      f"sustained={s['sustained_runs']}走 rate={s['sustained_top3_rate']:.3f})")

        # H6: 成長曲線
        has_maturity = [(sid, s) for sid, s in data.items() if 'maturity_index' in s]
        print(f"\n  Has maturity_index (young>=10 & mature>=10): {len(has_maturity):,}")

        if has_maturity:
            indices = [s['maturity_index'] for _, s in has_maturity]
            _print_distribution("H6 maturity_index (正=晩成型, 負=早熟型)", indices)

            # 晩成型Top 10
            top10 = sorted(has_maturity, key=lambda x: x[1]['maturity_index'], reverse=True)[:10]
            print(f"\n  Top 10 晩成型 (mature > young):")
            for sid, s in top10:
                print(f"    {sid}: index={s['maturity_index']:+.4f} "
                      f"(young={s['young_runs']}走 rate={s['young_top3_rate']:.3f}, "
                      f"mature={s['mature_runs']}走 rate={s['mature_top3_rate']:.3f})")

            # 早熟型Top 10
            bot10 = sorted(has_maturity, key=lambda x: x[1]['maturity_index'])[:10]
            print(f"\n  Top 10 早熟型 (young > mature):")
            for sid, s in bot10:
                print(f"    {sid}: index={s['maturity_index']:+.4f} "
                      f"(young={s['young_runs']}走 rate={s['young_top3_rate']:.3f}, "
                      f"mature={s['mature_runs']}走 rate={s['mature_top3_rate']:.3f})")

    # ベースライン統計
    print(f"\n--- ベースライン統計 ---")
    for label, data in [('Sire', stats['sire']), ('Dam', stats.get('dam', {})), ('BMS', stats['bms'])]:
        if not data:
            print(f"  {label}: no data")
            continue
        total_runs_list = [s['total_runs'] for s in data.values()]
        top3_rates = [s['top3_rate'] for s in data.values()]
        has_30_plus = sum(1 for r in total_runs_list if r >= 30)
        has_100_plus = sum(1 for r in total_runs_list if r >= 100)
        print(f"  {label}: {len(data):,} entries, "
              f">=30runs={has_30_plus:,}, >=100runs={has_100_plus:,}, "
              f"top3_rate median={statistics.median(top3_rates):.4f}")


def _analyze_hypothesis(data: dict, field: str, name: str,
                        high_label: str, low_label: str):
    """個別仮説の分析ヘルパー"""
    has_field = [(sid, s) for sid, s in data.items() if field in s]
    print(f"\n  Has {field}: {len(has_field):,}")

    if has_field:
        values = [s[field] for _, s in has_field]
        _print_distribution(f"{name} {field}", values)

        top10 = sorted(has_field, key=lambda x: x[1][field], reverse=True)[:10]
        print(f"\n  Top 10 {name}{high_label}:")
        for sid, s in top10:
            print(f"    {sid}: {field}={s[field]:+.4f}")

        bot10 = sorted(has_field, key=lambda x: x[1][field])[:10]
        print(f"\n  Top 10 {name}{low_label}:")
        for sid, s in bot10:
            print(f"    {sid}: {field}={s[field]:+.4f}")


def _print_distribution(name: str, values: List[float]):
    """分布の要約統計量を表示"""
    if not values:
        print(f"  {name}: no data")
        return

    mean = statistics.mean(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    pct_positive = sum(1 for v in values if v > 0) / len(values) * 100
    pct_strong = sum(1 for v in values if abs(v) > 0.05) / len(values) * 100

    print(f"\n  {name} 分布 (n={len(values):,}):")
    print(f"    Mean:     {mean:+.4f}")
    print(f"    Median:   {median:+.4f}")
    print(f"    Stdev:    {stdev:.4f}")
    print(f"    Min/Max:  {min(values):+.4f} / {max(values):+.4f}")
    print(f"    正の割合: {pct_positive:.1f}%")
    print(f"    |val|>0.05: {pct_strong:.1f}% (信号強度)")


# ============================================================
# メイン
# ============================================================

def main():
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Sire/Dam/BMS Stats Builder")
    print(f"{'='*60}\n")

    t0 = time.time()
    do_analyze = '--analyze' in sys.argv

    # データロード
    print("[1/3] Loading pedigree index...")
    pedigree_index = load_pedigree_index()
    if not pedigree_index:
        print("  Cannot proceed without pedigree_index.json")
        return

    print(f"  Loaded {len(pedigree_index):,} horses")

    print("\n[2/3] Loading race JSONs...")
    races = load_race_jsons()

    print("\n[3/3] Building sire/dam/bms stats...")
    stats = build_sire_stats(races, pedigree_index)

    print("\n[4/4] Loading sire/dam/BMS names from UM_DATA...")
    sire_names = load_sire_names()
    named = 0
    for category in ('sire', 'dam', 'bms'):
        for sid, entry in stats[category].items():
            if sid in sire_names:
                entry['name'] = sire_names[sid]
                named += 1
    print(f"  Named {named:,} / {sum(len(stats[c]) for c in ('sire','dam','bms')):,} entries")

    # 保存
    out_path = config.indexes_dir() / "sire_stats_index.json"
    config.ensure_dir(config.indexes_dir())

    print(f"\n[Save] Writing {out_path}...")
    out_path.write_text(
        json.dumps(stats, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )

    file_size = out_path.stat().st_size / 1024 / 1024
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Sires:     {len(stats['sire']):,}")
    print(f"  Dams:      {len(stats['dam']):,}")
    print(f"  BMS:       {len(stats['bms']):,}")
    print(f"  File size: {file_size:.1f} MB")
    print(f"  Output:    {out_path}")
    print(f"  Elapsed:   {elapsed:.1f}s")
    print(f"{'='*60}")

    # 分析モード
    if do_analyze:
        analyze_all_hypotheses(stats)

    print()


if __name__ == '__main__':
    main()

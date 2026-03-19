#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
障害レース専用特徴量 v2.5

v2.0: 基本障害特徴量（経験、難易度、騎手/調教師成績）
v2.1: 予想理論ベース（コース属性、平地IDM、レベル差）
v2.2: 障害走限定過去走統計、NaN修正、ベイズ平滑化
v2.3: per-courseテーブル修正 + ハイレベル経験 + 平地プロフィール
v2.3b: 3軸分類 + 障害数 + 直線路面 + 同系統コース成績
v2.5: 経験曲線特徴量（重み付き過去走、成長速度、初障害割引）

主要特徴量:
- obstacle_experience/exp_tier: 障害戦出走回数・経験ビン
- obstacle_level: コース難易度 (10-53)
- jockey/trainer障害成績: PIT-safe、ベイズ平滑化
- has_sash_course: 襷コースの有無 (v2.3: per-course修正)
- course_avg_l3f: コース別平均上がり3F (v2.3)
- is_high_level/high_to_low_transfer: ハイレベル経験・降格転戦 (v2.3)
- flat_turf_ratio/flat_avg_distance: 平地プロフィール (v2.3, 西谷J理論)
- obs_*: 障害走限定過去走統計 (v2.2)
- venue_skill_type: 3軸分類 (v2.3b, 0=器用さ, 1=平地力, 2=飛越力, 3=総合力)
- obstacle_count: コース別障害数 (v2.3b)
- straight_surface: 直線路面 (v2.3b, 0=芝, 1=ダ)
- obs_same_group_top3_rate: 同系統コースでの障害好走率 (v2.3b)
- obs_weighted_finish_last3: 指数減衰重み付き障害着順 (v2.5, 半減期2走)
- obs_improvement_rate: 初障害→2戦目の成長速度 (v2.5)
- obs_debut_discount: 初障害を除外した場合の着順改善度 (v2.5)
"""

from collections import defaultdict
from typing import Dict, List, Tuple

# ── コース難易度テーブル (web UI obstacle analysis page由来) ──
# Key: (venue_name, distance, surface) → difficulty level (10-53)
OBSTACLE_LEVEL_TABLE: Dict[Tuple[str, int, str], int] = {
    # 京都 (最高難度)
    ('京都', 3930, '芝'): 53, ('京都', 3170, '芝'): 44,
    ('京都', 3170, 'ダ'): 43, ('京都', 2910, 'ダ'): 36,
    # 阪神
    ('阪神', 3900, '芝'): 40, ('阪神', 3140, '芝'): 34,
    ('阪神', 3110, 'ダ'): 34, ('阪神', 2970, 'ダ'): 33,
    # 中山
    ('中山', 4250, '芝'): 37, ('中山', 4100, '芝'): 35,
    ('中山', 3570, '芝'): 34, ('中山', 3560, '芝'): 33,
    ('中山', 3200, 'ダ'): 31, ('中山', 3210, '芝'): 31,
    ('中山', 2880, 'ダ'): 21,
    # 東京
    ('東京', 3110, '芝'): 29, ('東京', 3000, 'ダ'): 28,
    ('東京', 3100, 'ダ'): 28,
    # 小倉
    ('小倉', 3390, '芝'): 27, ('小倉', 2860, '芝'): 24,
    # 中京
    ('中京', 3300, '芝'): 25, ('中京', 3330, '芝'): 25,
    ('中京', 3000, '芝'): 23,
    # 新潟
    ('新潟', 3250, '芝'): 22, ('新潟', 3290, '芝'): 22,
    ('新潟', 2850, '芝'): 18, ('新潟', 2890, '芝'): 18,
    # 福島
    ('福島', 3350, '芝'): 19, ('福島', 3380, '芝'): 19,
    ('福島', 2750, '芝'): 15, ('福島', 2770, '芝'): 15,
}

# 会場別のデフォルト難易度（テーブルにないコース用）
_VENUE_DEFAULT_LEVEL = {
    '京都': 44, '阪神': 35, '中山': 33, '東京': 28,
    '小倉': 25, '中京': 24, '新潟': 20, '福島': 17,
}


def compute_obstacle_level(
    venue_name: str,
    distance: int,
    track_type_raw: str,
) -> int:
    """コース難易度レベルを返す (10-53)

    Args:
        venue_name: 会場名（京都, 中山, etc.）
        distance: 距離(m)
        track_type_raw: 'turf'/'dirt'/'obstacle' — 障害は芝ベースだが
                        一部ダートコースあり。surfaceは距離+会場で判定。
    """
    # 障害レースのsurface判定: テーブルを芝/ダ両方で探す
    for surface in ('芝', 'ダ'):
        key = (venue_name, distance, surface)
        if key in OBSTACLE_LEVEL_TABLE:
            return OBSTACLE_LEVEL_TABLE[key]

    # テーブルにない → 会場デフォルト or 全体中央値
    return _VENUE_DEFAULT_LEVEL.get(venue_name, 25)


def compute_obstacle_experience(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> dict:
    """馬の障害戦経験回数を算出

    Returns:
        {'obstacle_experience': int}
    """
    records = history_cache.get(ketto_num, [])
    count = 0
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') == 'obstacle':
            count += 1
    return {'obstacle_experience': count}


def compute_obstacle_exp_tier(obstacle_experience: int) -> int:
    """障害経験をビン化: 0=初障害, 1=1-3戦, 2=4-10戦, 3=11+"""
    if obstacle_experience == 0:
        return 0
    if obstacle_experience <= 3:
        return 1
    if obstacle_experience <= 10:
        return 2
    return 3


def compute_prev_was_obstacle(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> int:
    """前走が障害レースだったか (1=障害, 0=平地/初出走)"""
    records = history_cache.get(ketto_num, [])
    for rec in reversed(records):
        rd = rec.get('race_date', '')
        if rd < race_date:
            return 1 if rec.get('track_type') == 'obstacle' else 0
    return 0


def compute_difficulty_exp_match(
    ketto_num: str,
    race_date: str,
    current_level: int,
    history_cache: dict,
    level_tolerance: int = 10,
) -> float:
    """当該難易度帯での経験度 (0.0-1.0)

    過去の障害レースのうち、当該コース難易度±toleranceに出走した割合。
    """
    records = history_cache.get(ketto_num, [])
    total_obs = 0
    match_count = 0
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') != 'obstacle':
            continue
        total_obs += 1
        # 過去レースの難易度を計算
        past_venue = rec.get('venue_name', '')
        past_dist = rec.get('distance', 0)
        past_level = compute_obstacle_level(past_venue, past_dist, 'obstacle')
        if abs(past_level - current_level) <= level_tolerance:
            match_count += 1

    if total_obs == 0:
        return 0.0
    return match_count / total_obs


# ── PIT-safe 騎手/調教師 障害タイムライン ──

def build_obstacle_personnel_timelines(
    history_cache: dict,
) -> Tuple[Dict[str, list], Dict[str, list]]:
    """history_cacheから障害レースの騎手/調教師タイムラインを構築

    Returns:
        (jockey_timeline, trainer_timeline)
        jockey_timeline: {jockey_code: [(race_date, is_win, is_top3), ...]}  sorted by date
        trainer_timeline: {trainer_code: [(race_date, is_top3), ...]}  sorted by date
    """
    jockey_tl: Dict[str, list] = defaultdict(list)
    trainer_tl: Dict[str, list] = defaultdict(list)

    for ketto_num, records in history_cache.items():
        if isinstance(records, dict):
            continue
        for rec in records:
            if rec.get('track_type') != 'obstacle':
                continue
            rd = rec.get('race_date', '')
            if not rd:
                continue
            fp = rec.get('finish_position')
            if fp is None or fp == 0:
                continue
            num_runners = rec.get('num_runners', 18)
            place_cutoff = 3 if num_runners >= 8 else (2 if num_runners >= 5 else 1)
            is_win = 1 if fp == 1 else 0
            is_top3 = 1 if fp <= place_cutoff else 0

            jc = rec.get('jockey_code', '')
            tc = rec.get('trainer_code', '')
            if jc:
                jockey_tl[jc].append((rd, is_win, is_top3))
            if tc:
                trainer_tl[tc].append((rd, is_top3))

    # ソート
    for jc in jockey_tl:
        jockey_tl[jc].sort(key=lambda x: x[0])
    for tc in trainer_tl:
        trainer_tl[tc].sort(key=lambda x: x[0])

    return dict(jockey_tl), dict(trainer_tl)


def compute_jockey_obstacle_stats(
    jockey_code: str,
    race_date: str,
    jockey_obstacle_tl: dict,
    global_win_rate: float = 0.07,
    prior_n: int = 20,
) -> dict:
    """PIT-safe: 当該日以前の騎手の障害成績（ベイズ平滑化付き）

    ベイズ平滑化: (wins + global_win_rate * prior_n) / (total + prior_n)
    → 少ないサンプル数の騎手は全体平均に引き寄せられる

    Returns:
        {'jockey_obstacle_races': int, 'jockey_obstacle_win_rate': float}
    """
    records = jockey_obstacle_tl.get(jockey_code, [])
    if not records:
        return {'jockey_obstacle_races': 0, 'jockey_obstacle_win_rate': global_win_rate}

    # bisectで当該日以前のレコード数を取得
    from bisect import bisect_left
    dates = [r[0] for r in records]
    idx = bisect_left(dates, race_date)

    if idx == 0:
        return {'jockey_obstacle_races': 0, 'jockey_obstacle_win_rate': global_win_rate}

    total = idx
    wins = sum(1 for r in records[:idx] if r[1] == 1)
    # ベイズ平滑化
    smoothed = (wins + global_win_rate * prior_n) / (total + prior_n)
    return {
        'jockey_obstacle_races': total,
        'jockey_obstacle_win_rate': round(smoothed, 4),
    }


def compute_trainer_obstacle_stats(
    trainer_code: str,
    race_date: str,
    trainer_obstacle_tl: dict,
    global_top3_rate: float = 0.25,
    prior_n: int = 20,
) -> dict:
    """PIT-safe: 当該日以前の調教師の障害好走率（ベイズ平滑化付き）

    Returns:
        {'trainer_obstacle_top3_rate': float}
    """
    records = trainer_obstacle_tl.get(trainer_code, [])
    if not records:
        return {'trainer_obstacle_top3_rate': global_top3_rate}

    from bisect import bisect_left
    dates = [r[0] for r in records]
    idx = bisect_left(dates, race_date)

    if idx == 0:
        return {'trainer_obstacle_top3_rate': global_top3_rate}

    total = idx
    top3s = sum(1 for r in records[:idx] if r[1] == 1)
    smoothed = (top3s + global_top3_rate * prior_n) / (total + prior_n)
    return {
        'trainer_obstacle_top3_rate': round(smoothed, 4),
    }


def compute_weight_gain_trend(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> dict:
    """近走の馬体重増加トレンドを計算

    仮説: 障害馬は鍛えて筋肉をつけて体重増加 → 成長のシグナル

    Returns:
        {
            'weight_gain_last3': float  - 直近3走の体重差(最新-3走前), kg。データ不足は0
            'weight_gain_per_race': float - 直近5走の1走あたり体重変化(回帰傾斜), kg/race。データ不足は0
        }
    """
    records = history_cache.get(ketto_num, [])
    # PIT-safe: 当該レース日より前の走のみ、日付降順で取得
    past_weights = []
    for rec in reversed(records):
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        hw = rec.get('horse_weight', 0)
        if hw and hw > 0:
            past_weights.append(hw)
        if len(past_weights) >= 5:
            break

    result = {'weight_gain_last3': 0.0, 'weight_gain_per_race': 0.0}

    # weight_gain_last3: 最新走 - 3走前 (past_weights[0]が最新)
    if len(past_weights) >= 3:
        result['weight_gain_last3'] = float(past_weights[0] - past_weights[2])

    # weight_gain_per_race: 直近N走(最大5)の線形回帰傾斜
    n = len(past_weights)
    if n >= 2:
        # past_weights[0]=最新, past_weights[-1]=最古
        # x: 0=最古, ..., n-1=最新  →  y: weights reversed
        weights = list(reversed(past_weights))  # 古い順
        # 単純線形回帰 slope = Σ(x-x̄)(y-ȳ) / Σ(x-x̄)²
        x_mean = (n - 1) / 2.0
        y_mean = sum(weights) / n
        num = sum((i - x_mean) * (w - y_mean) for i, w in enumerate(weights))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den > 0:
            result['weight_gain_per_race'] = round(num / den, 2)

    return result


# ── コース属性テーブル v2.3（予想理論データ由来、per-courseルックアップ） ──
# 旧venue-level _SASH_COURSE_VENUES は誤りだった（東京/京都=襷なし, 小倉/福島=全襷）
# v2.3: (venue, distance, surface) 単位の正確なテーブルに置き換え

_PLACED_OBSTACLE_VENUES = {'新潟', '福島', '中京'}

# Key: (venue_name, distance, surface) → {has_sash, avg_l3f}
# avg_l3f: コース別平均上がり3F（予想理論データ, 秒）
OBSTACLE_COURSE_ATTRS: Dict[Tuple[str, int, str], dict] = {
    # 京都 (全コース: 襷×)
    ('京都', 3930, '芝'): {'has_sash': 0, 'avg_l3f': 38.2},
    ('京都', 3170, '芝'): {'has_sash': 0, 'avg_l3f': 38.3},
    ('京都', 3170, 'ダ'): {'has_sash': 0, 'avg_l3f': 38.5},
    ('京都', 2910, 'ダ'): {'has_sash': 0, 'avg_l3f': 38.8},
    # 阪神 (全コース: 襷○)
    ('阪神', 3900, '芝'): {'has_sash': 1, 'avg_l3f': 38.2},
    ('阪神', 3140, '芝'): {'has_sash': 1, 'avg_l3f': 37.7},
    ('阪神', 3110, 'ダ'): {'has_sash': 1, 'avg_l3f': 39.3},
    ('阪神', 2970, 'ダ'): {'has_sash': 1, 'avg_l3f': 38.3},
    # 中山 (4250/4100のみ襷○, 他は×)
    ('中山', 4250, '芝'): {'has_sash': 1, 'avg_l3f': 39.0},
    ('中山', 4100, '芝'): {'has_sash': 1, 'avg_l3f': 37.7},
    ('中山', 3570, '芝'): {'has_sash': 0, 'avg_l3f': 37.8},
    ('中山', 3560, '芝'): {'has_sash': 0, 'avg_l3f': 38.0},
    ('中山', 3200, 'ダ'): {'has_sash': 0, 'avg_l3f': 38.4},
    ('中山', 3210, '芝'): {'has_sash': 0, 'avg_l3f': 38.4},
    ('中山', 2880, 'ダ'): {'has_sash': 0, 'avg_l3f': 38.4},
    # 東京 (全コース: 襷×)
    ('東京', 3110, '芝'): {'has_sash': 0, 'avg_l3f': 39.5},
    ('東京', 3000, 'ダ'): {'has_sash': 0, 'avg_l3f': 39.5},
    ('東京', 3100, 'ダ'): {'has_sash': 0, 'avg_l3f': 39.5},
    # 小倉 (全コース: 襷○)
    ('小倉', 3390, '芝'): {'has_sash': 1, 'avg_l3f': 39.3},
    ('小倉', 2860, '芝'): {'has_sash': 1, 'avg_l3f': 39.9},
    # 中京 (全コース: 襷×)
    ('中京', 3300, '芝'): {'has_sash': 0, 'avg_l3f': 39.2},
    ('中京', 3330, '芝'): {'has_sash': 0, 'avg_l3f': 39.2},
    ('中京', 3000, '芝'): {'has_sash': 0, 'avg_l3f': 39.1},
    # 新潟 (全コース: 襷×)
    ('新潟', 3250, '芝'): {'has_sash': 0, 'avg_l3f': 39.3},
    ('新潟', 3290, '芝'): {'has_sash': 0, 'avg_l3f': 39.3},
    ('新潟', 2850, '芝'): {'has_sash': 0, 'avg_l3f': 39.3},
    ('新潟', 2890, '芝'): {'has_sash': 0, 'avg_l3f': 39.3},
    # 福島 (全コース: 襷○)
    ('福島', 3350, '芝'): {'has_sash': 1, 'avg_l3f': 38.7},
    ('福島', 3380, '芝'): {'has_sash': 1, 'avg_l3f': 38.7},
    ('福島', 2750, '芝'): {'has_sash': 1, 'avg_l3f': 38.9},
    ('福島', 2770, '芝'): {'has_sash': 1, 'avg_l3f': 38.9},
}

# 会場別の襷デフォルト（テーブルにないコース用）
_VENUE_SASH_DEFAULT = {
    '阪神': 1, '小倉': 1, '福島': 1,
    '京都': 0, '東京': 0, '新潟': 0, '中京': 0, '中山': 0,
}

# ハイレベルコース閾値（予想理論: レベル33以上 = ハイレベル）
HIGH_LEVEL_THRESHOLD = 33

# ── v2.3b: 3軸分類テーブル (obstacle_race_knowledge.md 由来) ──

# 3軸分類: 0=器用さ, 1=平地力, 2=飛越力, 3=総合力
VENUE_SKILL_TYPE = {
    '福島': 0, '中山': 0, '小倉': 0,  # 器用さ（襷/坂路、コーナー多い）
    '新潟': 1, '中京': 1,              # 平地力（単純周回、置き障害メイン）
    '東京': 2, '京都': 2,              # 飛越力（障害難度高い）
    '阪神': 3,                          # 総合力（全スキル必要）
}

# コース別障害数（未勝利基準、ドキュメントの表より）
VENUE_OBSTACLE_COUNT = {
    '福島': 7, '中山': 8, '小倉': 9, '新潟': 9,
    '阪神': 11, '東京': 12, '京都': 12, '中京': 12,
}

# 直線路面（中央4場=ダ=1, ローカル4場=芝=0, "中央4場の未勝利は直線ダート"）
VENUE_STRAIGHT_SURFACE = {
    '東京': 1, '中山': 1, '京都': 1, '阪神': 1,
    '中京': 0, '新潟': 0, '福島': 0, '小倉': 0,
}

# 同系統コースグループ（コースリンク用）
# 福島↔中山↔小倉 (器用さ), 新潟↔中京 (平地力), 東京↔京都 (飛越力)
# 阪神=総合力 + 小倉≈阪神 (ドキュメント: "ほぼ阪神と似た特徴")
SKILL_GROUP_VENUES = {
    0: {'福島', '中山', '小倉'},    # 器用さ
    1: {'新潟', '中京'},             # 平地力
    2: {'東京', '京都'},             # 飛越力
    3: {'阪神', '小倉'},             # 総合力（小倉≈阪神）
}


def compute_venue_skill_features(venue_name: str) -> dict:
    """コースの3軸分類 + 障害数 + 直線路面（v2.3b）

    Returns:
        {
            'venue_skill_type': int,   # 0=器用さ, 1=平地力, 2=飛越力, 3=総合力
            'obstacle_count': int,     # 障害数 (7-12)
            'straight_surface': int,   # 0=芝, 1=ダート
        }
    """
    return {
        'venue_skill_type': VENUE_SKILL_TYPE.get(venue_name, 1),  # 不明→平地力(中間)
        'obstacle_count': VENUE_OBSTACLE_COUNT.get(venue_name, 10),
        'straight_surface': VENUE_STRAIGHT_SURFACE.get(venue_name, 0),
    }


def compute_same_group_stats(
    ketto_num: str,
    race_date: str,
    current_venue: str,
    history_cache: dict,
) -> dict:
    """同系統コースでの障害好走率（v2.3b, コースリンク）

    福島↔中山↔小倉, 新潟↔中京, 東京↔京都 の同系統コースでの過去成績。
    コース適性の転用: "福島で好走した馬は中山でも走れる" etc.

    Returns:
        {'obs_same_group_top3_rate': float}
    """
    skill_type = VENUE_SKILL_TYPE.get(current_venue, -1)
    if skill_type < 0:
        return {'obs_same_group_top3_rate': float('nan')}

    same_group = SKILL_GROUP_VENUES.get(skill_type, set())

    records = history_cache.get(ketto_num, [])
    if not records or isinstance(records, dict):
        return {'obs_same_group_top3_rate': float('nan')}

    total = 0
    top3 = 0
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') != 'obstacle':
            continue
        v = rec.get('venue_name', '')
        if v not in same_group:
            continue
        total += 1
        fp = rec.get('finish_position', 99)
        nr = rec.get('num_runners', 18)
        cutoff = 3 if nr >= 8 else (2 if nr >= 5 else 1)
        if fp <= cutoff:
            top3 += 1

    if total == 0:
        return {'obs_same_group_top3_rate': float('nan')}

    return {'obs_same_group_top3_rate': round(top3 / total, 4)}


def compute_course_attributes(venue_name: str, distance: int = 0) -> dict:
    """コース属性（置き障害/襷/平均上がり3F）を計算（v2.3: per-courseテーブル）

    Returns:
        {
            'is_placed_obstacle': 0/1,
            'has_sash_course': 0/1,
            'course_avg_l3f': float,
        }
    """
    is_placed = 1 if venue_name in _PLACED_OBSTACLE_VENUES else 0

    # per-courseテーブルから襷/avg_l3fを取得
    for surface in ('芝', 'ダ'):
        key = (venue_name, distance, surface)
        if key in OBSTACLE_COURSE_ATTRS:
            attrs = OBSTACLE_COURSE_ATTRS[key]
            return {
                'is_placed_obstacle': is_placed,
                'has_sash_course': attrs['has_sash'],
                'course_avg_l3f': attrs['avg_l3f'],
            }

    # テーブルにない → 会場デフォルト
    return {
        'is_placed_obstacle': is_placed,
        'has_sash_course': _VENUE_SASH_DEFAULT.get(venue_name, 0),
        'course_avg_l3f': float('nan'),
    }


def compute_prev_obstacle_level_diff(
    ketto_num: str,
    race_date: str,
    current_level: int,
    history_cache: dict,
) -> int:
    """前走の障害レベル - 今走の障害レベル

    正値 = レベルダウン転戦（有利説）
    負値 = レベルアップ転戦
    0 = 前走障害なし or 同レベル
    """
    records = history_cache.get(ketto_num, [])
    for rec in reversed(records):
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') != 'obstacle':
            continue
        prev_venue = rec.get('venue_name', '')
        prev_dist = rec.get('distance', 0)
        prev_level = compute_obstacle_level(prev_venue, prev_dist, 'obstacle')
        return prev_level - current_level
    return 0


def compute_flat_idm_avg3(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
    jrdb_sed_index: dict,
) -> float:
    """障害転向前の平地IDM 3走平均

    障害初出走日より前の平地走から直近3走のIDMを取得。
    2走以上のIDMがあれば平均、なければ-1.0。
    すでに障害経験がある場合も、初障害以前の平地IDMを使う（一度計算したら不変）。
    """
    records = history_cache.get(ketto_num, [])
    if not records or isinstance(records, dict):
        return -1.0

    # 初障害日を特定
    first_obs_date = None
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') == 'obstacle':
            if first_obs_date is None or rd < first_obs_date:
                first_obs_date = rd

    if first_obs_date is None:
        # まだ障害未出走 = 今回が初障害。転向前の平地全走を対象
        first_obs_date = race_date

    # 初障害より前の平地走を日付降順で収集
    flat_recs = []
    for rec in reversed(records):
        rd = rec.get('race_date', '')
        if rd >= first_obs_date:
            continue
        if rec.get('track_type') == 'obstacle':
            continue
        flat_recs.append(rec)
        if len(flat_recs) >= 3:
            break

    if not flat_recs:
        return float('nan')

    # SED index からIDMを取得
    idms = []
    for rec in flat_recs:
        rd = rec.get('race_date', '')
        sed_key = f"{ketto_num}_{rd}"
        sed_data = jrdb_sed_index.get(sed_key, {})
        idm = sed_data.get('idm', 0)
        if idm and idm > 0:
            idms.append(idm)

    if len(idms) < 2:
        return float('nan')

    return round(sum(idms) / len(idms), 1)


def compute_jockey_selection(
    entries: List[dict],
    history_cache: dict,
    race_date: str,
) -> Dict[int, dict]:
    """レース内の騎手選択シグナルを計算

    前走で同じ騎手が乗っていた馬が複数出走する場合、
    その騎手が今回も継続騎乗する馬 = 「選ばれた馬」(+1)
    その騎手が乗り替わりになった馬 = 「選ばれなかった馬」(-1)

    Returns:
        {umaban: {'jockey_selected': int, 'jockey_selected_count': int}}
    """
    prev_jockey_map = {}
    curr_jockey_map = {}

    for entry in entries:
        umaban = entry.get('umaban', 0)
        ketto_num = entry.get('ketto_num', '')
        curr_jockey = entry.get('jockey_code', '')

        if not ketto_num or not curr_jockey:
            continue

        curr_jockey_map[umaban] = curr_jockey

        records = history_cache.get(ketto_num, [])
        prev_jockey = ''
        for rec in reversed(records):
            rd = rec.get('race_date', '')
            if rd < race_date:
                prev_jockey = rec.get('jockey_code', '')
                break

        if prev_jockey:
            prev_jockey_map[umaban] = prev_jockey

    jockey_to_umabans = defaultdict(list)
    for umaban, pj in prev_jockey_map.items():
        jockey_to_umabans[pj].append(umaban)

    result = {}
    all_umabans = {e.get('umaban', 0) for e in entries if e.get('umaban', 0) > 0}

    for umaban in all_umabans:
        result[umaban] = {'jockey_selected': 0, 'jockey_selected_count': 0}

    for prev_jockey, umabans in jockey_to_umabans.items():
        if len(umabans) < 2:
            continue

        for uma in umabans:
            curr_j = curr_jockey_map.get(uma, '')
            group_size = len(umabans)
            if curr_j == prev_jockey:
                result[uma] = {
                    'jockey_selected': 1,
                    'jockey_selected_count': group_size,
                }
            else:
                result[uma] = {
                    'jockey_selected': -1,
                    'jockey_selected_count': group_size,
                }

    return result


# ── 障害走限定の過去走統計 (v2.2) ──

def compute_obstacle_only_past_stats(
    ketto_num: str,
    race_date: str,
    current_distance: int,
    history_cache: dict,
) -> dict:
    """障害レースのみの過去走統計（平地走を除外）

    既存の win_rate_all, top3_rate_all 等は平地走が混ざるため、
    障害走限定版を別特徴量として追加。

    Returns:
        {
            'obs_win_rate': float,         # 障害のみ勝率
            'obs_top3_rate': float,        # 障害のみ好走率
            'obs_avg_finish_last3': float,  # 障害直近3走の平均着順
            'obs_last3f_avg_last3': float,  # 障害直近3走の上がり3F平均
            'obs_best_finish_last5': float, # 障害直近5走のベスト着順
            'obs_days_since_last': float,   # 前走障害からの日数
            'obs_distance_fitness': float,  # 障害走での距離適性
        }
    """
    import math
    from datetime import datetime as _dt

    _NAN_RESULT = {
        'obs_win_rate': float('nan'),
        'obs_top3_rate': float('nan'),
        'obs_avg_finish_last3': float('nan'),
        'obs_last3f_avg_last3': float('nan'),
        'obs_best_finish_last5': float('nan'),
        'obs_days_since_last': float('nan'),
        'obs_distance_fitness': float('nan'),
    }

    records = history_cache.get(ketto_num, [])
    if not records or isinstance(records, dict):
        return _NAN_RESULT.copy()

    # 障害走のみ抽出（PIT-safe: 当該日より前）
    obs_recs = []
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') == 'obstacle':
            obs_recs.append(rec)

    total = len(obs_recs)
    if total == 0:
        return _NAN_RESULT.copy()

    # 勝率・好走率
    wins = sum(1 for r in obs_recs if r.get('finish_position') == 1)
    top3s = 0
    for r in obs_recs:
        fp = r.get('finish_position', 99)
        nr = r.get('num_runners', 18)
        cutoff = 3 if nr >= 8 else (2 if nr >= 5 else 1)
        if fp <= cutoff:
            top3s += 1

    obs_win_rate = wins / total
    obs_top3_rate = top3s / total

    # 日付降順でソート（最新→最古）
    obs_desc = sorted(obs_recs, key=lambda r: r.get('race_date', ''), reverse=True)

    # 直近3走平均着順
    last3_fp = [r.get('finish_position', 0) for r in obs_desc[:3]
                if r.get('finish_position') and r.get('finish_position') > 0]
    obs_avg_finish = sum(last3_fp) / len(last3_fp) if last3_fp else float('nan')

    # 直近3走上がり3F平均
    last3_l3f = [r.get('last_3f', 0) for r in obs_desc[:3]
                 if r.get('last_3f') and r.get('last_3f') > 0]
    obs_l3f_avg = sum(last3_l3f) / len(last3_l3f) if last3_l3f else float('nan')

    # 直近5走ベスト着順
    last5_fp = [r.get('finish_position', 99) for r in obs_desc[:5]
                if r.get('finish_position') and r.get('finish_position') > 0]
    obs_best_finish = float(min(last5_fp)) if last5_fp else float('nan')

    # 前走障害からの日数
    last_obs_date = obs_desc[0].get('race_date', '')
    if last_obs_date:
        try:
            d1 = _dt.strptime(race_date, '%Y-%m-%d')
            d2 = _dt.strptime(last_obs_date, '%Y-%m-%d')
            obs_days = float((d1 - d2).days)
        except (ValueError, TypeError):
            obs_days = float('nan')
    else:
        obs_days = float('nan')

    # 障害走での距離適性（±200m以内の好走率）
    dist_recs = [r for r in obs_recs
                 if abs(r.get('distance', 0) - current_distance) <= 200]
    if dist_recs:
        dist_top3 = 0
        for r in dist_recs:
            fp = r.get('finish_position', 99)
            nr = r.get('num_runners', 18)
            cutoff = 3 if nr >= 8 else (2 if nr >= 5 else 1)
            if fp <= cutoff:
                dist_top3 += 1
        obs_dist_fitness = dist_top3 / len(dist_recs)
    else:
        obs_dist_fitness = float('nan')

    def _safe_round(v, digits):
        return round(v, digits) if not math.isnan(v) else float('nan')

    return {
        'obs_win_rate': round(obs_win_rate, 4),
        'obs_top3_rate': round(obs_top3_rate, 4),
        'obs_avg_finish_last3': _safe_round(obs_avg_finish, 2),
        'obs_last3f_avg_last3': _safe_round(obs_l3f_avg, 1),
        'obs_best_finish_last5': obs_best_finish,
        'obs_days_since_last': obs_days,
        'obs_distance_fitness': _safe_round(obs_dist_fitness, 4),
    }


# ── ハイレベルコース経験 (v2.3) ──

def compute_high_level_experience(
    ketto_num: str,
    race_date: str,
    current_level: int,
    history_cache: dict,
) -> dict:
    """ハイレベルコース(≥33)での過去走実績

    予想理論: ハイレベルコースで負けた馬がローレベルに来ると複勝回収105%
    メメニシコリの例: ハイレベル 0-2-9-9 vs それ以外 0-1-0-17

    Returns:
        {
            'is_high_level': int,              # 今走がハイレベルコースか (0/1)
            'obs_high_level_runs': int,        # ハイレベルコース出走数
            'obs_high_level_top3_rate': float,  # ハイレベルコースでの好走率
            'prev_was_high_level': int,        # 前走がハイレベルコースだったか (0/1)
            'high_to_low_transfer': int,       # ハイ→ロー転戦 (1/0)
        }
    """
    is_high = 1 if current_level >= HIGH_LEVEL_THRESHOLD else 0

    records = history_cache.get(ketto_num, [])
    if not records or isinstance(records, dict):
        return {
            'is_high_level': is_high,
            'obs_high_level_runs': 0,
            'obs_high_level_top3_rate': float('nan'),
            'prev_was_high_level': 0,
            'high_to_low_transfer': 0,
        }

    # 過去の障害走を収集（PIT-safe）
    obs_recs = []
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') == 'obstacle':
            obs_recs.append(rec)

    if not obs_recs:
        return {
            'is_high_level': is_high,
            'obs_high_level_runs': 0,
            'obs_high_level_top3_rate': float('nan'),
            'prev_was_high_level': 0,
            'high_to_low_transfer': 0,
        }

    # ハイレベルコースでの成績
    high_runs = 0
    high_top3 = 0
    for rec in obs_recs:
        v = rec.get('venue_name', '')
        d = rec.get('distance', 0)
        lv = compute_obstacle_level(v, d, 'obstacle')
        if lv >= HIGH_LEVEL_THRESHOLD:
            high_runs += 1
            fp = rec.get('finish_position', 99)
            nr = rec.get('num_runners', 18)
            cutoff = 3 if nr >= 8 else (2 if nr >= 5 else 1)
            if fp <= cutoff:
                high_top3 += 1

    high_top3_rate = high_top3 / high_runs if high_runs > 0 else float('nan')

    # 前走がハイレベルだったか
    obs_desc = sorted(obs_recs, key=lambda r: r.get('race_date', ''), reverse=True)
    prev_rec = obs_desc[0]
    prev_lv = compute_obstacle_level(
        prev_rec.get('venue_name', ''),
        prev_rec.get('distance', 0),
        'obstacle',
    )
    prev_high = 1 if prev_lv >= HIGH_LEVEL_THRESHOLD else 0

    # ハイ→ロー転戦（降格ローテ的）
    high_to_low = 1 if prev_high == 1 and is_high == 0 else 0

    return {
        'is_high_level': is_high,
        'obs_high_level_runs': high_runs,
        'obs_high_level_top3_rate': round(high_top3_rate, 4) if high_runs > 0 else float('nan'),
        'prev_was_high_level': prev_high,
        'high_to_low_transfer': high_to_low,
    }


# ── 平地レースプロフィール (v2.3) ──

def compute_flat_racing_profile(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> dict:
    """障害転向前の平地レースプロフィール

    西谷J理論: 「芝のマイルで切れる馬 or ダート1800で走っている馬」が障害向き
    → 平地での主戦場（芝/ダ、距離帯）を特徴量化

    Returns:
        {
            'flat_turf_ratio': float,       # 平地走のうち芝の割合 (0-1)
            'flat_avg_distance': float,     # 平地走の平均距離 (m)
        }
    """
    records = history_cache.get(ketto_num, [])
    if not records or isinstance(records, dict):
        return {
            'flat_turf_ratio': float('nan'),
            'flat_avg_distance': float('nan'),
        }

    # 障害初出走日を特定（PIT-safe）
    first_obs_date = None
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') == 'obstacle':
            if first_obs_date is None or rd < first_obs_date:
                first_obs_date = rd

    if first_obs_date is None:
        first_obs_date = race_date

    # 障害転向前の平地走を収集（直近10走まで）
    flat_recs = []
    for rec in reversed(records):
        rd = rec.get('race_date', '')
        if rd >= first_obs_date:
            continue
        if rec.get('track_type') == 'obstacle':
            continue
        flat_recs.append(rec)
        if len(flat_recs) >= 10:
            break

    if not flat_recs:
        return {
            'flat_turf_ratio': float('nan'),
            'flat_avg_distance': float('nan'),
        }

    # 芝率
    turf_count = sum(1 for r in flat_recs if r.get('track_type') == 'turf')
    turf_ratio = turf_count / len(flat_recs)

    # 平均距離
    distances = [r.get('distance', 0) for r in flat_recs if r.get('distance', 0) > 0]
    avg_dist = sum(distances) / len(distances) if distances else float('nan')

    return {
        'flat_turf_ratio': round(turf_ratio, 3),
        'flat_avg_distance': round(avg_dist, 0) if distances else float('nan'),
    }


# ── 経験曲線特徴量 (v2.5) ──
#
# 分析結果:
# - 初障害→2戦目で60.5%の馬が改善、中央値+8.3pt
# - 初障害 vs 3戦目 相関0.268（弱い）→ 初障害の情報価値は急速に低下
# - 指数減衰重み（半減期2走）が全予測器中MSE最小(0.0736)
# - tier1(1-3戦)ではdecay重みが最良、tier2以降はequalと同等


def compute_experience_curve_features(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> dict:
    """障害経験曲線特徴量: 重み付き過去走、成長速度、初障害割引 (v2.5)

    仮説: 障害経験が少ないほど1戦ごとの経験値が重要で上昇幅が大きい。
    初障害の大敗はほぼ無視してよく、直近走の重みを大きくすべき。

    Returns:
        {
            'obs_weighted_finish_last3': float,  # 指数減衰重み付き障害着順比率
                                                  # (半減期2走: 直近=1, 1走前=0.707, 2走前=0.5)
            'obs_improvement_rate': float,        # 初障害→2戦目の着順比率改善幅
                                                  # 正値=改善、障害2戦以上で有効
            'obs_debut_discount': float,          # 初障害除外時の着順改善度
                                                  # = avg_without_debut - avg_with_debut
                                                  # 負値=初障害が足を引っ張っている
        }
    """
    import math

    _NAN = {
        'obs_weighted_finish_last3': float('nan'),
        'obs_improvement_rate': float('nan'),
        'obs_debut_discount': float('nan'),
    }

    records = history_cache.get(ketto_num, [])
    if not records or isinstance(records, dict):
        return _NAN.copy()

    # 障害走のみ抽出（PIT-safe）、日付昇順
    obs_recs = []
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') != 'obstacle':
            continue
        fp = rec.get('finish_position')
        nr = rec.get('num_runners')
        if fp and fp > 0 and nr and nr > 0:
            obs_recs.append({
                'date': rd,
                'fp': fp,
                'nr': nr,
                'fp_ratio': fp / nr,
            })

    if not obs_recs:
        return _NAN.copy()

    obs_recs.sort(key=lambda x: x['date'])
    n_obs = len(obs_recs)

    # --- obs_weighted_finish_last3: 指数減衰重み付き (半減期=2走) ---
    # 直近3走を取得（最新が末尾）
    last3 = obs_recs[-3:] if n_obs >= 3 else obs_recs
    # 重み: 半減期2走 → weight = 2^(-i/2) where i=距離(走前)
    # last3[-1]=直近(i=0, w=1.0), last3[-2]=1走前(i=1, w=0.707), last3[-3]=2走前(i=2, w=0.5)
    weights = []
    ratios = []
    for j, rec in enumerate(last3):
        dist_from_latest = len(last3) - 1 - j  # 0=最古, len-1=最新 → reverse
        w = 2.0 ** (-dist_from_latest / 2.0)
        weights.append(w)
        ratios.append(rec['fp_ratio'])

    w_sum = sum(weights)
    obs_weighted = sum(r * w for r, w in zip(ratios, weights)) / w_sum if w_sum > 0 else float('nan')

    # --- obs_improvement_rate: 初障害→2戦目の着順比率改善幅 ---
    if n_obs >= 2:
        debut_ratio = obs_recs[0]['fp_ratio']
        second_ratio = obs_recs[1]['fp_ratio']
        improvement = debut_ratio - second_ratio  # 正値=改善
    else:
        improvement = float('nan')

    # --- obs_debut_discount: 初障害を除外した場合の着順改善度 ---
    if n_obs >= 3:
        # 直近3走の均等平均（初障害含む可能性）
        last3_ratios = [r['fp_ratio'] for r in obs_recs[-3:]]
        avg_with_all = sum(last3_ratios) / len(last3_ratios)

        # 初障害を除外した直近3走の均等平均
        no_debut = obs_recs[1:]  # 初障害以外
        last3_no_debut = [r['fp_ratio'] for r in no_debut[-3:]]
        avg_no_debut = sum(last3_no_debut) / len(last3_no_debut)

        # 負値=初障害が足を引っ張っている（除外したら平均が良くなる）
        debut_discount = avg_no_debut - avg_with_all
    else:
        debut_discount = float('nan')

    def _sr(v, d):
        return round(v, d) if not math.isnan(v) else float('nan')

    return {
        'obs_weighted_finish_last3': _sr(obs_weighted, 4),
        'obs_improvement_rate': _sr(improvement, 4),
        'obs_debut_discount': _sr(debut_discount, 4),
    }

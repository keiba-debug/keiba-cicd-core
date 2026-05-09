"""新潟千直 Phase 1 検証共通ユーティリティ"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from scipy.stats import beta


REPORT_PATH = Path(
    "C:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2/docs/ml-experiments/"
    "v8.x_vega_niigata1000_phase1_verification.md"
)
CSV_DIR = REPORT_PATH.parent / "v8.x_vega_niigata1000_phase1_data"


def beta_ci(success: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    """Beta credible interval (Jeffreys-ish prior)"""
    if total == 0:
        return (0.0, 0.0)
    a = success + 1
    b = total - success + 1
    return (float(beta.ppf(alpha / 2, a, b)), float(beta.ppf(1 - alpha / 2, a, b)))


def add_running_style(df: pd.DataFrame) -> pd.DataFrame:
    """脚質指標カラムを追加（verify_02と同じロジック）

    pre_2f_dev: 前半2F偏差（負=テン速い）
    last_3f_dev: 上がり3F偏差（負=末脚速い）
    running_style: 4象限カテゴリ
    is_strong_horse: 結果脚質①強馬（テン速&末脚速）かつ 3着内
    """
    df = df.copy()
    df["last_3f_valid"] = df["last_3f"].where(df["last_3f"].notna() & (df["last_3f"] > 0))
    df["pre_2f"] = df["time_sec"] - df["last_3f_valid"]
    df["pre_2f_race_mean"] = df.groupby("race_id")["pre_2f"].transform("mean")
    df["last_3f_race_mean"] = df.groupby("race_id")["last_3f_valid"].transform("mean")
    df["pre_2f_dev"] = df["pre_2f"] - df["pre_2f_race_mean"]
    df["last_3f_dev"] = df["last_3f_valid"] - df["last_3f_race_mean"]

    def classify(row):
        p, l = row["pre_2f_dev"], row["last_3f_dev"]
        if pd.isna(p) or pd.isna(l):
            return "不明"
        if p < 0 and l < 0:
            return "①強馬"
        if p < 0 and l >= 0:
            return "②先行・逃げ"
        if p >= 0 and l < 0:
            return "③差し・追込"
        return "④凡走"

    df["running_style"] = df.apply(classify, axis=1)
    df["is_strong_horse"] = (df["running_style"] == "①強馬") & df["is_top3"]
    return df


def aggregate_with_strong(df: pd.DataFrame, group_col, label: str = None) -> pd.DataFrame:
    """グループ別の集計（is_win, is_top3, is_strong_horse, ROI + CI）"""
    grouped = df.groupby(group_col, dropna=False).agg(
        n=("is_win", "size"),
        wins=("is_win", "sum"),
        top3=("is_top3", "sum"),
        strong=("is_strong_horse", "sum"),
        win_payoff=("win_payoff", "sum"),
    ).reset_index()
    grouped["win_rate"] = grouped["wins"] / grouped["n"]
    grouped["top3_rate"] = grouped["top3"] / grouped["n"]
    grouped["strong_rate"] = grouped["strong"] / grouped["n"]
    grouped["win_roi"] = grouped["win_payoff"] / (grouped["n"] * 100.0)

    win_ci = grouped.apply(lambda r: beta_ci(int(r["wins"]), int(r["n"])), axis=1)
    grouped["win_rate_lo"] = [c[0] for c in win_ci]
    grouped["win_rate_hi"] = [c[1] for c in win_ci]
    top3_ci = grouped.apply(lambda r: beta_ci(int(r["top3"]), int(r["n"])), axis=1)
    grouped["top3_rate_lo"] = [c[0] for c in top3_ci]
    grouped["top3_rate_hi"] = [c[1] for c in top3_ci]
    strong_ci = grouped.apply(lambda r: beta_ci(int(r["strong"]), int(r["n"])), axis=1)
    grouped["strong_rate_lo"] = [c[0] for c in strong_ci]
    grouped["strong_rate_hi"] = [c[1] for c in strong_ci]

    return grouped


def fmt_table_with_strong(g: pd.DataFrame, group_label: str) -> str:
    """強馬率カラム付きMarkdown表"""
    lines = [
        f"| {group_label} | 出走 | 勝 | 3着内 | 強馬 | 勝率 | 3着内率 | 強馬率 | 単勝ROI |",
        f"|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in g.iterrows():
        key = r.iloc[0]
        lines.append(
            f"| {key} | {int(r['n'])} | {int(r['wins'])} | {int(r['top3'])} | {int(r['strong'])} | "
            f"{r['win_rate']*100:.1f}% | "
            f"{r['top3_rate']*100:.1f}% | "
            f"{r['strong_rate']*100:.1f}% | "
            f"{r['win_roi']*100:.1f}% |"
        )
    return "\n".join(lines)


_HISTORY_CACHE: dict | None = None
_PEDIGREE_INDEX: dict | None = None
_SIRE_STATS: dict | None = None


def load_pedigree_index() -> dict:
    """pedigree_index.json をロード"""
    global _PEDIGREE_INDEX
    if _PEDIGREE_INDEX is None:
        import json
        path = Path("C:/KEIBA-CICD/data3/indexes/pedigree_index.json")
        with path.open("r", encoding="utf-8") as f:
            _PEDIGREE_INDEX = json.load(f)
    return _PEDIGREE_INDEX


def load_sire_stats() -> dict:
    """sire_stats_index.json をロード"""
    global _SIRE_STATS
    if _SIRE_STATS is None:
        import json
        path = Path("C:/KEIBA-CICD/data3/indexes/sire_stats_index.json")
        with path.open("r", encoding="utf-8") as f:
            _SIRE_STATS = json.load(f)
    return _SIRE_STATS


def attach_pedigree(df: pd.DataFrame) -> pd.DataFrame:
    """各馬に父系・母父系名を付与

    付与カラム:
      sire_id, sire_name, bms_id, bms_name, dam_id,
      sire_line（簡易サンデー系/その他系判定）
    """
    pedigree = load_pedigree_index()
    stats = load_sire_stats()
    sire_db = stats.get("sire", {})
    bms_db = stats.get("bms", {})

    rows = []
    for _, r in df.iterrows():
        ketto = r["ketto_num"]
        ped = pedigree.get(ketto, {})
        sire_id = ped.get("sire", "")
        bms_id = ped.get("bms", "")
        dam_id = ped.get("dam", "")
        sire_name = sire_db.get(sire_id, {}).get("name", "?") if sire_id else "?"
        bms_name = bms_db.get(bms_id, {}).get("name", "?") if bms_id else "?"

        rows.append({
            "sire_id": sire_id,
            "sire_name": sire_name,
            "bms_id": bms_id,
            "bms_name": bms_name,
            "dam_id": dam_id,
            "sire_line": classify_sire_line(sire_name),
            "bms_line": classify_sire_line(bms_name),
        })

    info_df = pd.DataFrame(rows, index=df.index)
    return pd.concat([df, info_df], axis=1)


# 簡易系統判定（部分文字列マッチ）
SUNDAY_PATTERNS = [
    "ディープ", "ステイ", "ハーツ", "キズナ", "オルフェ", "ゴールドシップ",
    "フジキセキ", "アグネス", "ダイワメジャー", "マンハッタン", "スペシャル",
    "デュランダル", "ゼンノロブロイ", "ネオユニヴァース", "ハットトリック",
    "カネヒキリ", "ヴィクトワールピサ", "サトノダイヤモンド", "リアルインパクト",
    "ハーピア", "ハービンジャー",  # ※ハービンジャーはダンジグ系だが念のため除外名で記載
    "サンデー",
]
KING_KAMEHAMEHA_PATTERNS = [
    "キングカメハメハ", "ロードカナロア", "ルーラーシップ", "リオンディーズ",
    "ホッコータルマエ", "ドゥラメンテ", "アドミラブル",
]
STORM_CAT_PATTERNS = [
    "ヘニーヒューズ", "ヘニー", "ハービンジャー",
]
NORTHERN_DANCER_PATTERNS = [
    "ハービンジャー", "ダンチヒ", "ストームキャット", "ハーランズホリデー",
]


def classify_sire_line(sire_name: str) -> str:
    """父系統の簡易分類（重複時は最初にマッチするもの）"""
    if not sire_name or sire_name == "?":
        return "不明"
    # ハービンジャーは Dansili (Danzig系) なので NORTHERN_DANCER系
    if "ハービンジャー" in sire_name:
        return "ノーザンダンサー系"
    for p in SUNDAY_PATTERNS:
        if p in sire_name:
            return "サンデー系"
    for p in KING_KAMEHAMEHA_PATTERNS:
        if p in sire_name:
            return "キングカメハメハ系"
    for p in STORM_CAT_PATTERNS:
        if p in sire_name:
            return "ストームキャット系"
    for p in NORTHERN_DANCER_PATTERNS:
        if p in sire_name:
            return "ノーザンダンサー系"
    return "その他"


def load_history_cache() -> dict:
    """horse_history_cache.json をロード（プロセス内キャッシュ）"""
    global _HISTORY_CACHE
    if _HISTORY_CACHE is None:
        import json
        cache_path = Path("C:/KEIBA-CICD/data3/ml/horse_history_cache.json")
        with cache_path.open("r", encoding="utf-8") as f:
            _HISTORY_CACHE = json.load(f)
    return _HISTORY_CACHE


def attach_past_running_style(df: pd.DataFrame, history_cache: dict | None = None) -> pd.DataFrame:
    """各出走に過去走の脚質傾向を付与（Phase 2 用）

    付与カラム:
      past_corner_first_avg_5: 過去5走の前半通過順位平均（先行傾向の代理）
      past_corner_first_min_5: 過去5走のベスト前半通過順位（最先行時）
      past_last_3f_avg_5: 過去5走の上がり3F平均
      past_last_3f_min_5: 過去5走のベスト上がり3F（最速時）
      past_short_avg_l3f: 過去走（1000-1200m短距離のみ）の上がり3F平均
      past_short_count: 過去走の短距離経験回数
      past_choku_corner_first_avg: 過去千直での前半通過順位平均（千直経験馬のみ）
      past_choku_last_3f_avg: 過去千直での上がり3F平均（千直経験馬のみ）
      past_choku_finish_avg: 過去千直での着順平均
      total_career_races_p2: 過去走数（再計算）
    """
    if history_cache is None:
        history_cache = load_history_cache()

    rows: list[dict] = []
    for _, r in df.iterrows():
        ketto = r["ketto_num"]
        race_date = r["date"]
        runs = history_cache.get(ketto, [])
        past = [run for run in runs if run.get("race_date", "") < race_date]

        info: dict = {
            "past_corner_first_avg_5": None,
            "past_corner_first_min_5": None,
            "past_last_3f_avg_5": None,
            "past_last_3f_min_5": None,
            "past_short_avg_l3f": None,
            "past_short_count": 0,
            "past_choku_corner_first_avg": None,
            "past_choku_last_3f_avg": None,
            "past_choku_finish_avg": None,
            "total_career_races_p2": len(past),
        }

        if not past:
            rows.append(info)
            continue

        last5 = past[-5:]

        # 過去5走の前半通過順位
        cf5 = [run.get("corners", [None])[0] for run in last5
               if run.get("corners") and run["corners"][0] not in (None, 0)]
        if cf5:
            info["past_corner_first_avg_5"] = sum(cf5) / len(cf5)
            info["past_corner_first_min_5"] = min(cf5)

        # 過去5走の上がり3F
        l3f5 = [run.get("last_3f") for run in last5
                if run.get("last_3f") is not None and run.get("last_3f") > 0]
        if l3f5:
            info["past_last_3f_avg_5"] = sum(l3f5) / len(l3f5)
            info["past_last_3f_min_5"] = min(l3f5)

        # 過去走の短距離（1000-1200m）成績
        short = [run for run in past
                 if run.get("distance") in (1000, 1100, 1200)
                 and run.get("track_type") == "turf"]
        info["past_short_count"] = len(short)
        l3f_short = [run.get("last_3f") for run in short
                     if run.get("last_3f") is not None and run.get("last_3f") > 0]
        if l3f_short:
            info["past_short_avg_l3f"] = sum(l3f_short) / len(l3f_short)

        # 過去千直経験
        choku = [run for run in past
                 if run.get("venue_code") == "04"
                 and run.get("distance") == 1000
                 and run.get("track_type") == "turf"]
        if choku:
            cf = [run.get("corners", [None])[0] for run in choku
                  if run.get("corners") and run["corners"][0] not in (None, 0)]
            if cf:
                info["past_choku_corner_first_avg"] = sum(cf) / len(cf)
            l3f = [run.get("last_3f") for run in choku
                   if run.get("last_3f") is not None and run.get("last_3f") > 0]
            if l3f:
                info["past_choku_last_3f_avg"] = sum(l3f) / len(l3f)
            fp = [run.get("finish_position") for run in choku
                  if run.get("finish_position") is not None and run.get("finish_position") > 0]
            if fp:
                info["past_choku_finish_avg"] = sum(fp) / len(fp)

        rows.append(info)

    info_df = pd.DataFrame(rows, index=df.index)
    return pd.concat([df, info_df], axis=1)


def attach_past_info(df: pd.DataFrame, history_cache: dict | None = None) -> pd.DataFrame:
    """各出走に過去走情報をマージ

    付与カラム:
      has_prev, prev_distance, prev_track_type, prev_finish, prev_last_3f,
      days_since_prev, total_career_races,
      niigata_1000m_count, niigata_1000m_top3_count, is_first_choku,
      niigata_1000m_top3_rate
    """
    from datetime import date as _date

    if history_cache is None:
        history_cache = load_history_cache()

    def parse_date(s):
        try:
            y, m, d = s.split("-")
            return _date(int(y), int(m), int(d))
        except Exception:
            return None

    rows: list[dict] = []
    for _, r in df.iterrows():
        ketto = r["ketto_num"]
        race_date = r["date"]
        runs = history_cache.get(ketto, [])
        past = [run for run in runs if run.get("race_date", "") < race_date]

        info: dict = {
            "has_prev": False,
            "prev_distance": None,
            "prev_track_type": None,
            "prev_finish": None,
            "prev_last_3f": None,
            "days_since_prev": None,
            "total_career_races": len(past),
            "niigata_1000m_count": 0,
            "niigata_1000m_top3_count": 0,
            "is_first_choku": True,
            "niigata_1000m_top3_rate": None,
        }

        if past:
            last = past[-1]
            info["has_prev"] = True
            info["prev_distance"] = last.get("distance")
            info["prev_track_type"] = last.get("track_type")
            info["prev_finish"] = last.get("finish_position")
            info["prev_last_3f"] = last.get("last_3f")
            d_now = parse_date(race_date)
            d_prev = parse_date(last.get("race_date", ""))
            if d_now and d_prev:
                info["days_since_prev"] = (d_now - d_prev).days

        # 新潟芝1000m リピーター
        choku = [
            run for run in past
            if run.get("venue_code") == "04"
            and run.get("distance") == 1000
            and run.get("track_type") == "turf"
        ]
        info["niigata_1000m_count"] = len(choku)
        info["is_first_choku"] = len(choku) == 0
        if choku:
            top3 = sum(1 for run in choku if (run.get("finish_position") or 99) <= 3)
            info["niigata_1000m_top3_count"] = top3
            info["niigata_1000m_top3_rate"] = top3 / len(choku)

        rows.append(info)

    info_df = pd.DataFrame(rows, index=df.index)
    return pd.concat([df, info_df], axis=1)


def upsert_section(section_marker: str, section_body: str, next_markers: list[str]) -> None:
    """レポートにセクションを挿入/更新"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else ""
    if section_marker in existing:
        start = existing.index(section_marker)
        end = len(existing)
        for nm in next_markers:
            idx = existing.find(nm, start + 1)
            if idx != -1 and idx < end:
                end = idx
        new_content = existing[:start] + section_body + existing[end:]
        REPORT_PATH.write_text(new_content, encoding="utf-8")
    else:
        REPORT_PATH.write_text(existing + section_body, encoding="utf-8")

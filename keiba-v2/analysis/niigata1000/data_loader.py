"""新潟芝1000M直線（千直）データ抽出基盤

新潟芝1000mの全レース（venue_code='04', distance=1000, track_type='turf'）を
data3/races/ から抽出し、出走馬単位の DataFrame を構築する。

Phase 1 仮説検証スクリプトから共通利用される基盤モジュール。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pandas as pd

DATA_RACES_DIR = Path("C:/KEIBA-CICD/data3/races")

NIIGATA_VENUE_CODE = "04"
TARGET_DISTANCE = 1000
TARGET_TRACK_TYPE = "turf"


def iter_race_files(start_year: int = 2020, end_year: int = 2026) -> Iterator[Path]:
    """data3/races 配下の race_*.json を年範囲でイテレート"""
    for year in range(start_year, end_year + 1):
        year_dir = DATA_RACES_DIR / f"{year:04d}"
        if not year_dir.exists():
            continue
        for path in sorted(year_dir.rglob("race_[0-9]*.json")):
            yield path


def is_niigata_1000m(race: dict) -> bool:
    """新潟芝1000mレース判定"""
    return (
        race.get("venue_code") == NIIGATA_VENUE_CODE
        and race.get("distance") == TARGET_DISTANCE
        and race.get("track_type") == TARGET_TRACK_TYPE
    )


def load_races(start_year: int = 2020, end_year: int = 2026) -> list[dict]:
    """新潟芝1000mのレースdictリストを取得"""
    races = []
    for path in iter_race_files(start_year, end_year):
        try:
            race = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if is_niigata_1000m(race):
            races.append(race)
    return races


def _parse_finish_time(time_str: str | None) -> float | None:
    """'M:SS.s' or 'SS.s' 形式の時計を秒に変換"""
    if not time_str or time_str in ("", "-"):
        return None
    s = str(time_str).strip()
    try:
        if ":" in s:
            m, rest = s.split(":", 1)
            return int(m) * 60 + float(rest)
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_corners(corners) -> tuple[int | None, int | None]:
    """corners 配列から first / last コーナー位置を返す（千直は基本なし）"""
    if not corners or not isinstance(corners, list):
        return None, None
    valid = [c for c in corners if isinstance(c, (int, float)) and c > 0]
    if not valid:
        return None, None
    return int(valid[0]), int(valid[-1])


def to_horse_dataframe(races: list[dict]) -> pd.DataFrame:
    """レース dict リスト → 出走馬単位の DataFrame

    出力カラム（主要）:
    - race_id, date, year, month, kai, nichi, race_no, race_name, grade
    - num_runners, track_condition, weather, is_handicap, is_female_only
    - pace_l3, pace_l4, pace_lap_times (json), race_trend
    - umaban, wakuban, ketto_num, horse_name, sex_cd, age
    - jockey_name, jockey_code, trainer_name, trainer_code
    - futan, horse_weight, horse_weight_diff
    - finish_position, time_sec, last_3f, odds, popularity, margin
    - is_win, is_top3, win_payoff, place_payoff
    - jrdb_pre_idm, jrdb_sogo_idx, jrdb_training_idx, jrdb_stable_idx,
      jrdb_gekisou_idx, jrdb_idm
    """
    rows: list[dict] = []
    for race in races:
        race_id = race.get("race_id", "")
        date = race.get("date", "")
        year = int(date[:4]) if len(date) >= 4 else None
        month = int(date[5:7]) if len(date) >= 7 else None

        pace = race.get("pace") or {}
        race_common = {
            "race_id": race_id,
            "date": date,
            "year": year,
            "month": month,
            "kai": race.get("kai"),
            "nichi": race.get("nichi"),
            "race_no": race.get("race_number"),
            "race_name": race.get("race_name", ""),
            "grade": race.get("grade", ""),
            "num_runners": race.get("num_runners"),
            "track_condition": race.get("track_condition", ""),
            "weather": race.get("weather", ""),
            "is_handicap": bool(race.get("is_handicap", False)),
            "is_female_only": bool(race.get("is_female_only", False)),
            "pace_l3": pace.get("l3"),
            "pace_l4": pace.get("l4"),
            "pace_rpci": pace.get("rpci"),
            "pace_race_trend": pace.get("race_trend"),
            "pace_lap_times": pace.get("lap_times"),
            "pace_lap33": pace.get("lap33"),
            "pace_trend_v2": pace.get("race_trend_v2"),
        }

        for entry in race.get("entries", []):
            finish = entry.get("finish_position")
            try:
                finish_int = int(finish) if finish is not None else None
            except (ValueError, TypeError):
                finish_int = None

            odds = entry.get("odds")
            try:
                odds_f = float(odds) if odds is not None else None
            except (ValueError, TypeError):
                odds_f = None

            is_win = finish_int == 1
            is_top3 = finish_int is not None and 1 <= finish_int <= 3
            win_payoff = (odds_f * 100.0) if (is_win and odds_f) else 0.0

            corner_first, corner_last = _parse_corners(entry.get("corners"))

            row = {
                **race_common,
                "umaban": entry.get("umaban"),
                "wakuban": entry.get("wakuban"),
                "ketto_num": entry.get("ketto_num"),
                "horse_name": entry.get("horse_name"),
                "sex_cd": entry.get("sex_cd"),
                "age": entry.get("age"),
                "jockey_name": entry.get("jockey_name"),
                "jockey_code": entry.get("jockey_code"),
                "trainer_name": entry.get("trainer_name"),
                "trainer_code": entry.get("trainer_code"),
                "futan": entry.get("futan"),
                "horse_weight": entry.get("horse_weight"),
                "horse_weight_diff": entry.get("horse_weight_diff"),
                "finish_position": finish_int,
                "time_sec": _parse_finish_time(entry.get("time")),
                "last_3f": entry.get("last_3f"),
                "last_4f": entry.get("last_4f"),
                "odds": odds_f,
                "popularity": entry.get("popularity"),
                "margin": entry.get("margin", ""),
                "corner_first": corner_first,
                "corner_last": corner_last,
                "is_win": is_win,
                "is_top3": is_top3,
                "win_payoff": win_payoff,
                "jrdb_pre_idm": entry.get("jrdb_pre_idm"),
                "jrdb_sogo_idx": entry.get("jrdb_sogo_idx"),
                "jrdb_training_idx": entry.get("jrdb_training_idx"),
                "jrdb_stable_idx": entry.get("jrdb_stable_idx"),
                "jrdb_gekisou_idx": entry.get("jrdb_gekisou_idx"),
                "jrdb_idm": entry.get("jrdb_idm"),
            }
            rows.append(row)

    df = pd.DataFrame(rows)
    # 並び順
    if not df.empty:
        df = df.sort_values(["date", "race_no", "umaban"]).reset_index(drop=True)
    return df


@dataclass
class NiigataDataset:
    """新潟千直データセット（レース dict + 出走馬 DataFrame）"""
    races: list[dict]
    horses: pd.DataFrame

    @property
    def n_races(self) -> int:
        return len(self.races)

    @property
    def n_horses(self) -> int:
        return len(self.horses)

    def summary(self) -> str:
        if self.horses.empty:
            return "Empty dataset"
        df = self.horses
        years = df["year"].value_counts().sort_index()
        baba = df.groupby("race_id")["track_condition"].first().value_counts()
        return (
            f"Races: {self.n_races}, Horses: {self.n_horses}\n"
            f"Year breakdown: {dict(years)}\n"
            f"Track conditions: {dict(baba)}"
        )


def load_dataset(start_year: int = 2020, end_year: int = 2026) -> NiigataDataset:
    """主要エントリ：新潟千直データセットをロード"""
    races = load_races(start_year, end_year)
    horses = to_horse_dataframe(races)
    return NiigataDataset(races=races, horses=horses)


if __name__ == "__main__":
    ds = load_dataset()
    print(ds.summary())
    print("\nColumns:", list(ds.horses.columns))
    print("\nSample (first 3 rows):")
    print(ds.horses.head(3).to_string())

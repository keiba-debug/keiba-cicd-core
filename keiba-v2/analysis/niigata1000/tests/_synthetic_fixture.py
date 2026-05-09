"""snapshot_builder/relations 用の合成 history_cache fixture

5レース×多頭、関係者(jockey/trainer)+ 強馬判定が手計算で予測できる小規模データ。

レース構成:
  Race A: 2022-08-21 (4頭)
  Race B: 2024-05-04 (4頭)
  Race C: 2024-08-04 (4頭, snapshot_2024-07 後)
  Race D: 2022-08-10 (2頭, expired テスト用)
  Race E: 2024-08-25 (2頭, cutoff='2024-08-15' より後)

期待値:
  snapshot_ym='2024-07' (window_start ~2022-08-02 ~ 2024-07-31):
    A + B + D を含む (E除外:未来 / C除外:未来)
  snapshot_ym='2024-08' (window_start ~2022-09-01 ~ 2024-08-31):
    B + C + E を含む (A除外:窓外 / D除外:窓外)

  cutoff='2024-08-15' (cutoff_2y=2024-08-16):
    base(2024-07): A + B + D
    delta(2024-08-01~14): C
    expired(window_start~2022-08-15): D (2022-08-10)
    →最終: A + B + C
"""
from __future__ import annotations


def _run(*, race_id, race_date, umaban, jockey, trainer, finish, time, last_3f):
    return {
        "race_id": race_id,
        "race_date": race_date,
        "venue_code": "04",
        "venue_name": "新潟",
        "umaban": umaban,
        "finish_position": finish,
        "time": time,
        "last_3f": last_3f,
        "jockey_code": jockey,
        "trainer_code": trainer,
        "corners": [],
        "num_runners": 8,
        "distance": 1000,
        "track_type": "turf",
        "track_condition": "良",
        "grade": "OP",
    }


# Race A: 2022-08-21 (4 horses)
# strong horse 計算 (race-mean):
#   pre_2f = time - last_3f
#   H_A1: pre_2f=22.0, l3f=32.5
#   H_A2: pre_2f=21.5, l3f=33.5
#   H_A3: pre_2f=23.5, l3f=32.0
#   H_A4: pre_2f=22.0, l3f=34.0
#   mean(pre_2f)=22.25, mean(l3f)=33.0
#   H_A1: dev_pre=-0.25(<0), dev_l3f=-0.5(<0), finish=1 → STRONG ✓
#   H_A2: dev_pre=-0.75, dev_l3f=+0.5 → not strong, top3
#   H_A3: dev_pre=+1.25, dev_l3f=-1.0 → not strong, top3
#   H_A4: dev_pre=-0.25, dev_l3f=+1.0 → not strong, NOT top3
RACE_A_RUNS = [
    _run(race_id="R_A", race_date="2022-08-21", umaban=1, jockey="J_A", trainer="T_A",
         finish=1, time="54.5", last_3f=32.5),
    _run(race_id="R_A", race_date="2022-08-21", umaban=2, jockey="J_B", trainer="T_B",
         finish=2, time="55.0", last_3f=33.5),
    _run(race_id="R_A", race_date="2022-08-21", umaban=3, jockey="J_A", trainer="T_B",
         finish=3, time="55.5", last_3f=32.0),
    _run(race_id="R_A", race_date="2022-08-21", umaban=4, jockey="J_B", trainer="T_A",
         finish=4, time="56.0", last_3f=34.0),
]

# Race B: 2024-05-04 (4 horses, no strong)
#   mean(pre_2f)=21.875, mean(l3f)=33.375
#   H_B1: pre_2f=22.0, dev_pre=+0.125 → not strong, top3
#   H_B2: pre_2f=22.0, dev_pre=+0.125 → not strong, top3
#   H_B3: pre_2f=23.0, dev_pre=+1.125 → not strong, top3
#   H_B4: pre_2f=20.5, dev_pre=-1.375, dev_l3f=+0.625 → not strong, NOT top3
RACE_B_RUNS = [
    _run(race_id="R_B", race_date="2024-05-04", umaban=1, jockey="J_A", trainer="T_A",
         finish=1, time="55.0", last_3f=33.0),
    _run(race_id="R_B", race_date="2024-05-04", umaban=2, jockey="J_C", trainer="T_C",
         finish=2, time="55.5", last_3f=33.5),
    _run(race_id="R_B", race_date="2024-05-04", umaban=3, jockey="J_C", trainer="T_A",
         finish=3, time="56.0", last_3f=33.0),
    _run(race_id="R_B", race_date="2024-05-04", umaban=4, jockey="J_A", trainer="T_C",
         finish=4, time="54.5", last_3f=34.0),
]

# Race C: 2024-08-04 (4 horses, no strong - delta テスト用)
#   mean(pre_2f)=21.75, mean(l3f)=33.5
#   H_C1: dev_pre=+0.25, dev_l3f=-0.5 → not strong, top3
#   H_C2: dev_pre=+0.25, dev_l3f=0 → not strong, NOT top3 (finish=4)
#   H_C3: dev_pre=+0.25, dev_l3f=+0.5 → not strong, top3 (finish=1)
#   H_C4: dev_pre=-0.75, dev_l3f=0 → not strong, top3 (finish=3)
RACE_C_RUNS = [
    _run(race_id="R_C", race_date="2024-08-04", umaban=1, jockey="J_A", trainer="T_A",
         finish=2, time="55.0", last_3f=33.0),
    _run(race_id="R_C", race_date="2024-08-04", umaban=2, jockey="J_B", trainer="T_B",
         finish=4, time="55.5", last_3f=33.5),
    _run(race_id="R_C", race_date="2024-08-04", umaban=3, jockey="J_C", trainer="T_A",
         finish=1, time="56.0", last_3f=34.0),
    _run(race_id="R_C", race_date="2024-08-04", umaban=4, jockey="J_A", trainer="T_C",
         finish=3, time="54.5", last_3f=33.5),
]

# Race D: 2022-08-10 (2 horses, expired テスト用)
#   mean(pre_2f)=22.0, mean(l3f)=33.25
#   H_D1: dev_pre=0, dev_l3f=-0.25 → not strong (pre_dev not <0), top3
#   H_D2: dev_pre=0, dev_l3f=+0.25 → not strong, top3
RACE_D_RUNS = [
    _run(race_id="R_D", race_date="2022-08-10", umaban=1, jockey="J_A", trainer="T_A",
         finish=1, time="55.0", last_3f=33.0),
    _run(race_id="R_D", race_date="2022-08-10", umaban=2, jockey="J_B", trainer="T_B",
         finish=2, time="55.5", last_3f=33.5),
]

# Race E: 2024-08-25 (2 horses, future テスト用)
RACE_E_RUNS = [
    _run(race_id="R_E", race_date="2024-08-25", umaban=1, jockey="J_A", trainer="T_A",
         finish=1, time="55.0", last_3f=33.0),
    _run(race_id="R_E", race_date="2024-08-25", umaban=2, jockey="J_C", trainer="T_C",
         finish=2, time="55.5", last_3f=33.5),
]


def build_synthetic_history() -> dict:
    """合成 history_cache (ketto -> [runs])

    各馬 (8頭+追加) は1〜2レース出走。同一 ketto は使い回さない。
    """
    runs = (
        RACE_A_RUNS + RACE_B_RUNS + RACE_C_RUNS + RACE_D_RUNS + RACE_E_RUNS
    )
    cache: dict = {}
    for i, r in enumerate(runs):
        ketto = f"K{i:04d}"
        cache[ketto] = [r]
    return cache

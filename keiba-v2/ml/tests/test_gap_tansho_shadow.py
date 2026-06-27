# -*- coding: utf-8 -*-
"""gap_tansho_shadow.py の選定ロジック単体テスト (Session 175)

検証:
  - _bucket: grade → エッジクラス正規化
  - select_gap_tansho: gap/rank/win_ev ゲート・新馬/OP除外・top_k 並び
  - S175 broad: DEFAULT_PARAMS が全オッズ (odds帯フィルタを落とした=過学習棄却) を捕る
"""
from ml.strategies import gap_tansho_shadow as gs


def _race(grade, entries):
    return {"grade": grade, "entries": entries, "venue_name": "T", "race_number": 1}


def _e(umaban, rank_w, odds_rank, odds, win_ev=2.0, name=None):
    return {"umaban": umaban, "rank_w": rank_w, "odds_rank": odds_rank,
            "odds": odds, "win_ev": win_ev, "horse_name": name or f"h{umaban}"}


# --- _bucket ---

def test_bucket():
    assert gs._bucket("未勝利") == "miSHOURI"
    assert gs._bucket("3歳1勝クラス") == "jouken"
    assert gs._bucket("G1") == "juushou"
    assert gs._bucket("新馬") == "shinba"
    assert gs._bucket("OP") == "OP/L"


# --- クラス除外 ---

def test_shinba_and_op_excluded():
    assert gs.select_gap_tansho(_race("新馬", [_e(1, 2, 7, 20)])) == []
    assert gs.select_gap_tansho(_race("OP", [_e(1, 2, 7, 20)])) == []


# --- gap / rank ゲート ---

def test_gap_and_rank_gates():
    r = _race("未勝利", [
        _e(1, 2, 7, 20),    # gap=5 rank=2 -> in
        _e(2, 2, 6, 20),    # gap=4       -> out
        _e(3, 4, 10, 20),   # rank=4      -> out
    ])
    assert {p["umaban"] for p in gs.select_gap_tansho(r)} == {1}


# --- grade 空 → race_name フォールバック (S176+: レース当日朝の盲目バグ回帰防止) ---

def test_grade_empty_falls_back_to_race_name():
    """keibabook ビルダーは grade='' でクラスを race_name に入れる。当日朝の predictions は
    grade 空なので、race_name を見ないと全レース対象外で偽の0になる (実バグ 2026-06-27)。"""
    # grade 空 + race_name にクラス → 拾える
    r = {"grade": "", "race_name": "3歳未勝利", "venue_name": "T", "race_number": 1,
         "entries": [_e(1, 2, 7, 20)]}  # gap=5 rank=2 -> in
    assert {p["umaban"] for p in gs.select_gap_tansho(r)} == {1}
    # grade 優先: grade が有れば race_name は見ない (履歴=grade あり時の挙動不変)
    r2 = {"grade": "未勝利", "race_name": "新馬", "venue_name": "T", "race_number": 1,
          "entries": [_e(1, 2, 7, 20)]}
    assert {p["umaban"] for p in gs.select_gap_tansho(r2)} == {1}
    # 両方空 → 対象外
    r3 = {"grade": "", "race_name": "", "venue_name": "T", "race_number": 1,
          "entries": [_e(1, 2, 7, 20)]}
    assert gs.select_gap_tansho(r3) == []


# --- win_ev フロア ---

def test_winev_floor():
    r = _race("未勝利", [_e(1, 2, 7, 20, win_ev=0.5)])
    assert gs.select_gap_tansho(r, win_ev_floor=1.0) == []
    assert len(gs.select_gap_tansho(r, win_ev_floor=0.0)) == 1


# --- S175: broad = 全オッズ (odds帯フィルタは過学習で棄却済み) ---

def test_broad_default_params_all_odds():
    assert gs.DEFAULT_PARAMS["odds_lo"] == 0.0
    assert gs.DEFAULT_PARAMS["odds_hi"] >= 9999.0
    r = _race("3歳3勝クラス", [
        _e(1, 2, 7, 8.0),     # 低オッズ gap5 -> broad で in (旧core[15,30)なら out)
        _e(2, 3, 9, 60.0),    # 高オッズ gap6 -> in
    ])
    assert {p["umaban"] for p in gs.select_gap_tansho(r)} == {1, 2}


def test_gap_computed_and_recorded():
    r = _race("未勝利", [_e(1, 1, 8, 25.0)])
    picks = gs.select_gap_tansho(r)
    assert len(picks) == 1
    assert picks[0]["gap"] == 7          # odds_rank - rank_w = 8 - 1
    assert picks[0]["cls"] == "miSHOURI"


# --- top_k は win_ev 降順 ---

def test_top_k_sorts_by_winev():
    r = _race("未勝利", [
        _e(1, 2, 7, 20, win_ev=1.5),
        _e(2, 3, 9, 20, win_ev=3.0),
    ])
    picks = gs.select_gap_tansho(r, top_k=1)
    assert len(picks) == 1 and picks[0]["umaban"] == 2


def test_log_picks_noop_on_non_race_day(monkeypatch):
    """非開催日 (predictions.json 無し) は scheduler 用に静かに no-op (S175 堅牢化)。"""
    def _raise(_):
        raise FileNotFoundError("predictions.json なし")
    monkeypatch.setattr(gs, "_predictions", _raise)
    res = gs.log_picks("2099-12-31")
    assert res["added"] == 0 and "no predictions" in res.get("skip", "")

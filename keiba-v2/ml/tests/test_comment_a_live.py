# -*- coding: utf-8 -*-
"""コメＡ3点セット (comment_a_live) の単体テスト (Session 189)。

カバレッジ:
  - read_comment_a_config: 既定(無効)/欠損/サニティクランプ/有効化/他スリーブ独立
  - select_comment_a: Ａ印のみ / ワイド相手=rank_w最上位(自身除く) / R4ゲート / picks欠損=空
  - size_comment_a_race: 配分 複2u(R4で3u)/単1u/ワイド1u・相手不在=ワイド略・極小残高=None・cap fit
  - settle_comment_a_day: 台帳記録・冪等 (compute_recovery は monkeypatch)
  - registry: comment_a 登録済み・優先順は最後尾
"""
from __future__ import annotations

import json

from ml.strategies import comment_a_live as cl


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

RID = "2026062805030611"  # → date 2026-06-28


def _entry(umaban, rank_w=None, proba_p=None, po_min=None, odds=8.0, name="h"):
    e = {"umaban": umaban, "horse_name": name, "odds": odds}
    if rank_w is not None:
        e["rank_w"] = rank_w
    if proba_p is not None:
        e["pred_proba_p_raw"] = proba_p
    if po_min is not None:
        e["place_odds_min"] = po_min
    return e


def _fillers(*umabans, odds=30.0):
    """頭数合わせ用のモブ馬 (rank_w/ML フィールドなし・有効オッズのみ)。"""
    return [_entry(u, odds=odds, name=f"mob{u}") for u in umabans]


def _race(rid=RID, entries=None):
    return {"race_id": rid, "venue_name": "函館", "race_number": 11,
            "entries": entries if entries is not None else [
                _entry(1, rank_w=1, proba_p=0.40, po_min=1.5, odds=2.0, name="ml-hon"),
                _entry(5, rank_w=2, proba_p=0.30, po_min=2.0, odds=6.0, name="second"),
                _entry(7, rank_w=6, proba_p=0.20, po_min=3.0, odds=15.0, name="pick-a"),
            ] + _fillers(2, 3, 4)}


def _picks_dir(tmp_path, date="2026-06-28", races=None):
    d = tmp_path / "live"
    d.mkdir(parents=True, exist_ok=True)
    if races is None:
        races = [{"race_id": RID, "picks": [
            {"umaban": 7, "name": "pick-a", "odds": 15.0, "confidence": "高",
             "reason": "気配良"},
            {"umaban": 5, "name": "second", "odds": 6.0, "confidence": "中",
             "reason": "Ｂ印は買わない"},
        ]}]
    (d / f"picks_{date}.json").write_text(
        json.dumps(races, ensure_ascii=False), encoding="utf-8")
    return d


def _cfg(path, **settings):
    path.write_text(json.dumps({"settings": settings}, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# read_comment_a_config
# ---------------------------------------------------------------------------

def test_config_missing_defaults_disabled(tmp_path):
    c = cl.read_comment_a_config(tmp_path / "nope.json")
    assert c.enabled is False
    assert c.initial_bankroll_yen == cl.DEFAULT_COMMENT_A_INITIAL_BANKROLL == 300_000
    assert c.bet_pct == cl.DEFAULT_COMMENT_A_BET_PCT == 0.5
    assert c.day_pct == cl.DEFAULT_COMMENT_A_DAY_PCT == 10.0
    assert c.r4_boost is True


def test_config_reads_enabled_values(tmp_path):
    p = _cfg(tmp_path / "c.json", comment_a_enabled=True,
             comment_a_initial_bankroll_yen=500000, comment_a_bet_pct=1.0,
             comment_a_day_pct=15.0, comment_a_r4_boost=False)
    c = cl.read_comment_a_config(p)
    assert c.enabled is True and c.initial_bankroll_yen == 500000
    assert c.bet_pct == 1.0 and c.day_pct == 15.0 and c.r4_boost is False


def test_config_sanity_clamps_bad_values(tmp_path):
    p = _cfg(tmp_path / "c.json", comment_a_enabled=True, comment_a_bet_pct=0,
             comment_a_day_pct=200, comment_a_initial_bankroll_yen=-1)
    c = cl.read_comment_a_config(p)
    assert c.bet_pct == cl.DEFAULT_COMMENT_A_BET_PCT
    assert c.day_pct == cl.DEFAULT_COMMENT_A_DAY_PCT
    assert c.initial_bankroll_yen == cl.DEFAULT_COMMENT_A_INITIAL_BANKROLL


def test_config_independent_of_other_sleeves(tmp_path):
    # gap/honmei が ON でも comment_a は独立キー (comment_a_enabled) が無ければ無効
    p = _cfg(tmp_path / "c.json", gap_enabled=True, tansho_ev_enabled=True)
    assert cl.read_comment_a_config(p).enabled is False


# ---------------------------------------------------------------------------
# select_comment_a
# ---------------------------------------------------------------------------

def test_select_a_only_with_partner_and_r4(tmp_path):
    pd = _picks_dir(tmp_path)
    sel = cl.select_comment_a(_race(), picks_dir=pd)
    assert len(sel) == 1  # Ｂ印(5番)は選ばれない
    pk = sel[0]
    assert pk["umaban"] == 7
    assert pk["wide_partner"] == 1          # rank_w=1 (pick自身でない)
    # R4: (0.20+0.196)*3.0 = 1.188 >= 1.0 → 通過
    assert pk["r4_pass"] is True


def test_select_partner_excludes_pick_itself(tmp_path):
    # pick 自身が rank_w=1 なら相手は rank_w 2位
    races = [{"race_id": RID, "picks": [
        {"umaban": 1, "confidence": "高", "name": "ml-hon"}]}]
    pd = _picks_dir(tmp_path, races=races)
    sel = cl.select_comment_a(_race(), picks_dir=pd)
    assert sel[0]["umaban"] == 1 and sel[0]["wide_partner"] == 5


def test_select_r4_fails_when_ev_low_or_missing(tmp_path):
    pd = _picks_dir(tmp_path)
    # (0.20+0.196)*2.0 = 0.79 < 1.0 → 不通過
    r = _race(entries=[_entry(1, rank_w=1), _entry(7, rank_w=6, proba_p=0.20, po_min=2.0)]
              + _fillers(2, 3, 4))
    assert cl.select_comment_a(r, picks_dir=pd)[0]["r4_pass"] is False
    # フィールド欠損 → False (安全側)
    r2 = _race(entries=[_entry(1, rank_w=1), _entry(7, rank_w=6)] + _fillers(2, 3, 4))
    assert cl.select_comment_a(r2, picks_dir=pd)[0]["r4_pass"] is False


def test_select_no_picks_file_returns_empty(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cl.select_comment_a(_race(), picks_dir=empty) == []


def test_select_no_rank_w_partner_none(tmp_path):
    pd = _picks_dir(tmp_path)
    r = _race(entries=[_entry(1), _entry(7, proba_p=0.2, po_min=3.0)]
              + _fillers(2, 3, 4))  # rank_w なし
    sel = cl.select_comment_a(r, picks_dir=pd)
    assert sel[0]["wide_partner"] is None


def test_select_bad_race_id_returns_empty(tmp_path):
    pd = _picks_dir(tmp_path)
    assert cl.select_comment_a({"race_id": "xxx", "entries": []}, picks_dir=pd) == []


# --- 取消・除外ガード (シズネ 🔴-1) ---

def test_select_scratched_pick_skipped(tmp_path):
    pd = _picks_dir(tmp_path)
    # pick(7番) が entries に不在 (取消で vb_refresh から消えた) → 買わない
    r = _race(entries=[_entry(1, rank_w=1), _entry(5, rank_w=2)] + _fillers(2, 3, 4))
    assert cl.select_comment_a(r, picks_dir=pd) == []


def test_select_pick_without_valid_odds_skipped(tmp_path):
    pd = _picks_dir(tmp_path)
    # pick(7番) は居るがオッズ None (取消/データ欠損) → 買わない
    ent = [_entry(1, rank_w=1), _entry(7, rank_w=6)] + _fillers(2, 3, 4)
    ent[1]["odds"] = None
    assert cl.select_comment_a(_race(entries=ent), picks_dir=pd) == []


def test_select_partner_skips_invalid_odds(tmp_path):
    pd = _picks_dir(tmp_path)
    # rank_w1 (1番) が取消 (オッズ0) → 相手は rank_w2 (5番) に繰り下がる
    ent = [_entry(1, rank_w=1, odds=0), _entry(5, rank_w=2),
           _entry(7, rank_w=6, proba_p=0.2, po_min=3.0)] + _fillers(2, 3, 4)
    sel = cl.select_comment_a(_race(entries=ent), picks_dir=pd)
    assert sel[0]["wide_partner"] == 5


# --- 少頭数縮退 (シズネ 🟢-4) ---

def test_select_few_runners_flags_unsellable(tmp_path):
    pd = _picks_dir(tmp_path)
    # 有効オッズ4頭 → 複勝/ワイド発売なしフラグ
    r = _race(entries=[_entry(1, rank_w=1), _entry(5, rank_w=2),
                       _entry(7, rank_w=6)] + _fillers(2))
    sel = cl.select_comment_a(r, picks_dir=pd)
    assert sel[0]["sellable_fukusho_wide"] is False


def test_size_few_runners_tansho_only(tmp_path):
    pd = _picks_dir(tmp_path)
    r = _race(entries=[_entry(1, rank_w=1), _entry(5, rank_w=2),
                       _entry(7, rank_w=6)] + _fillers(2))
    rs = cl.size_comment_a_race(r, balance=300000, bet_pct=0.5, picks_dir=pd)
    assert {l.bet_type for l in rs.legs} == {"tansho"}
    assert rs.total_yen == 1500


# ---------------------------------------------------------------------------
# size_comment_a_race
# ---------------------------------------------------------------------------

def test_size_three_legs_with_weights(tmp_path):
    pd = _picks_dir(tmp_path)
    # 残高300,000×0.5% = u1500。R4通過 → 複勝3u=4500 / 単勝1u=1500 / ワイド1u=1500
    rs = cl.size_comment_a_race(_race(), balance=300000, bet_pct=0.5,
                                picks_dir=pd, r4_boost=True)
    assert rs is not None
    by_type = {l.bet_type: l for l in rs.legs}
    assert set(by_type) == {"fukusho", "tansho", "wide"}
    assert by_type["fukusho"].amount == 4500 and by_type["fukusho"].horses == [7]
    assert by_type["tansho"].amount == 1500 and by_type["tansho"].horses == [7]
    assert by_type["wide"].amount == 1500 and by_type["wide"].horses == [7, 1]
    assert rs.total_yen == 7500


def test_size_r4_boost_off_uses_base_weight(tmp_path):
    pd = _picks_dir(tmp_path)
    rs = cl.size_comment_a_race(_race(), balance=300000, bet_pct=0.5,
                                picks_dir=pd, r4_boost=False)
    fuku = next(l for l in rs.legs if l.bet_type == "fukusho")
    assert fuku.amount == 3000  # 2u
    assert rs.total_yen == 6000


def test_size_no_partner_skips_wide(tmp_path):
    pd = _picks_dir(tmp_path)
    r = _race(entries=[_entry(7, proba_p=0.2, po_min=2.0)] + _fillers(1, 2, 3, 4))  # rank_w 不在
    rs = cl.size_comment_a_race(r, balance=300000, bet_pct=0.5, picks_dir=pd)
    assert {l.bet_type for l in rs.legs} == {"fukusho", "tansho"}


def test_size_no_picks_returns_none(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cl.size_comment_a_race(_race(), balance=300000, bet_pct=0.5,
                                  picks_dir=empty) is None


def test_size_tiny_balance_returns_none(tmp_path):
    pd = _picks_dir(tmp_path)
    assert cl.size_comment_a_race(_race(), balance=10000, bet_pct=0.5,
                                  picks_dir=pd) is None  # 50円 < 100円


def test_size_cap_fits_and_protects_anchor(tmp_path):
    pd = _picks_dir(tmp_path)
    rs = cl.size_comment_a_race(_race(), balance=300000, bet_pct=0.5,
                                picks_dir=pd, per_race_cap=3000)
    assert rs is not None and rs.total_yen <= 3000
    # 単複 (アンカー) は fit 後も必ず残る (wide から落ちる)
    kept = {l.bet_type for l in rs.legs}
    assert "fukusho" in kept and "tansho" in kept


# ---------------------------------------------------------------------------
# realized_pnl / account_balance
# ---------------------------------------------------------------------------

def test_realized_pnl_and_balance():
    led = {"days": {"2026-07-04": {"pnl": -3000}, "2026-07-05": {"pnl": 9000}}}
    assert cl.realized_pnl(led) == 6000
    cfg = cl.CommentAConfig(True, 300000, 0.5, 10.0)
    assert cl.account_balance(cfg, led) == 306000


# --- ハードDDストップ (ふくだ確定 S189: 初期の50%割れで自動停止) ---

def test_dd_stop_triggers_below_half():
    cfg = cl.CommentAConfig(True, 300000, 0.5, 10.0)
    assert cl.dd_stopped(cfg, {"days": {"d": {"pnl": -150001}}}) is True   # 149,999 < 150,000
    assert cl.dd_stopped(cfg, {"days": {"d": {"pnl": -150000}}}) is False  # ちょうど 150,000 は稼働
    assert cl.dd_stopped(cfg, {"days": {}}) is False


def test_sleeve_disabled_by_dd_stop(monkeypatch, tmp_path):
    from ml.strategies.sleeves import get_sleeve
    p = _cfg(tmp_path / "c.json", comment_a_enabled=True)
    monkeypatch.setattr(cl, "BANKROLL_CONFIG_PATH", p)
    monkeypatch.setattr(cl, "load_ledger",
                        lambda *a, **k: {"days": {"d": {"pnl": -160000}}})
    assert get_sleeve("comment_a").is_enabled() is False  # 残高14万 < 15万 → 自動停止
    monkeypatch.setattr(cl, "load_ledger", lambda *a, **k: {"days": {}})
    assert get_sleeve("comment_a").is_enabled() is True


# ---------------------------------------------------------------------------
# settle_comment_a_day (compute_recovery を monkeypatch)
# ---------------------------------------------------------------------------

def test_settle_writes_ledger(tmp_path, monkeypatch):
    ledpath = tmp_path / "ledger.json"
    monkeypatch.setattr(cl, "_ledger_path", lambda: ledpath)
    monkeypatch.setattr("ml.strategies.day_recovery.compute_recovery",
                        lambda d, v: {"recovered_yen": 9000, "settled_races": 1,
                                      "pending_races": 0, "detail": {"r1": {"payout": 9000}}})
    votes = {"r1": {"exit_code": 0, "amount": 7500,
                    "legs": [{"bet_type": "fukusho", "horses": [7], "amount": 4500},
                             {"bet_type": "tansho", "horses": [7], "amount": 1500},
                             {"bet_type": "wide", "horses": [7, 1], "amount": 1500}]}}
    day = cl.settle_comment_a_day("2026-07-04", votes)
    assert day["cost"] == 7500 and day["payout"] == 9000 and day["pnl"] == 1500
    saved = json.loads(ledpath.read_text(encoding="utf-8"))
    assert saved["days"]["2026-07-04"]["pnl"] == 1500


def test_settle_idempotent_overwrite(tmp_path, monkeypatch):
    ledpath = tmp_path / "ledger.json"
    monkeypatch.setattr(cl, "_ledger_path", lambda: ledpath)
    seq = iter([{"recovered_yen": 0, "detail": {}},
                {"recovered_yen": 9000, "detail": {"r1": {"payout": 9000}}}])
    monkeypatch.setattr("ml.strategies.day_recovery.compute_recovery",
                        lambda d, v: next(seq))
    votes = {"r1": {"exit_code": 0, "amount": 7500,
                    "legs": [{"bet_type": "fukusho", "horses": [7], "amount": 7500}]}}
    cl.settle_comment_a_day("2026-07-04", votes)
    day2 = cl.settle_comment_a_day("2026-07-04", votes)
    assert day2["payout"] == 9000
    saved = json.loads(ledpath.read_text(encoding="utf-8"))
    assert len(saved["days"]) == 1 and saved["days"]["2026-07-04"]["pnl"] == 1500


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

def test_registry_has_comment_a_last(tmp_path, monkeypatch):
    from ml.strategies.sleeves import SLEEVES, get_sleeve
    assert list(SLEEVES) == ["honmei_ev", "gap_tansho", "comment_a"]
    s = get_sleeve("comment_a")
    assert s.display.bet_type.startswith("複勝")
    # config を tmp に向けると既定は無効 (安全側)
    monkeypatch.setattr(cl, "BANKROLL_CONFIG_PATH", tmp_path / "nope.json")
    assert s.is_enabled() is False


def test_sleeve_freeze_and_size(tmp_path, monkeypatch):
    from ml.strategies.sleeves import get_sleeve
    p = _cfg(tmp_path / "c.json", comment_a_enabled=True, comment_a_bet_pct=0.5,
             comment_a_day_pct=10.0, comment_a_initial_bankroll_yen=300000)
    monkeypatch.setattr(cl, "BANKROLL_CONFIG_PATH", p)
    monkeypatch.setattr(cl, "PICKS_DIR", _picks_dir(tmp_path))
    s = get_sleeve("comment_a")
    assert s.is_enabled() is True
    snap = s.freeze(per_race_cap=12000)
    assert snap["bankroll"] == 300000 and snap["day_cap"] == 30000
    rs = s.size_race(_race(), snap)
    assert rs is not None and all(l.sleeve == "comment_a" for l in rs.legs)
    assert rs.total_yen == 7500  # R4通過: 複4500+単1500+ワイド1500

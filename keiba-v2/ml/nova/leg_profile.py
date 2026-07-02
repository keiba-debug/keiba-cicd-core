#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regulus craft: 脚質・能力プロファイル (上がり3軸=JRDB指数ベース・印/解説用)  Session 178

Regulus B(文脈で過去走を掃除して能力トレンドをde-confound)は NO-GO で確定
(JRDB IDM が既に文脈掃除済み R²=0.9999, レポート§7)。だが「経験豊富な王者級の馬の
脚質・能力タイプを言語化して印/解説に出す」のは payout エッジでなく**説明力**として別価値
([[feedback_specialist_for_its_own_sake]])。本モジュールはその craft 成果物。

安井『上がりXハロン』の3軸(スピード/スタミナ/パワー)を、lap_times の再構成でなく
**JRDB SED が既に持つ正規化済み指数**で軽量に表現する:
  軸1 テン力   = ten_idx   (前半スピード・先行力)          高い=速い=良い
  軸2 末脚力   = agari_idx (上がり・瞬発)                  高い=切れる=良い
  軸3 持続力   = -(rear_3f - front_3f) を距離標準化         後半が垂れない=スタミナ
  脚質タイプ   = corners(道中位置/頭数) → 逃げ/先行/差し/追込
  上昇度      = joushou_code (JRDB)

全て**対象レース日より前の走のみ**(リークフリー)。最近 N=5 走を集計。
グレード(S/A/B/C/D)は OP+ 母集団パーセンタイルでカット。

Usage:
  python -m ml.nova.leg_profile --race <race_id>          # その1レースの脚質表(test splitから)
  python -m ml.nova.leg_profile --date 2026-05-31 --n 1   # その日のOP+レースを n本デモ
出力: 標準出力(人間可読の脚質・能力プロファイル表)
"""
from __future__ import annotations
import sys, json, bisect, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd
from core import config

HIST = config.ml_dir() / "horse_history_cache.json"
SPLITS = config.ml_dir() / "nova" / "turf_op" / "splits"
RECENT_N = 5

_SED = None
_HIST = None
_HDATES = None
_BASE = None   # grading baselines (percentiles)


def _load():
    global _SED, _HIST, _HDATES, _BASE
    if _SED is not None:
        return
    _SED = json.load(open(config.indexes_dir() / "jrdb_sed_index.json", encoding="utf-8"))
    _HIST = json.load(open(HIST, encoding="utf-8"))
    _HDATES = {k: sorted({r.get("race_date") for r in rs if r.get("race_date")})
               for k, rs in _HIST.items()}
    # grading baselines: 全SED母集団の分位(グレード) + 平均/標準偏差(偏差値=指数化)
    ten = np.array([v["ten_idx"] for v in _SED.values()
                    if isinstance(v, dict) and v.get("ten_idx") is not None], dtype=float)
    ag = np.array([v["agari_idx"] for v in _SED.values()
                   if isinstance(v, dict) and v.get("agari_idx") is not None], dtype=float)
    sus = np.array([float(v["front_3f"]) - float(v["rear_3f"]) for v in _SED.values()
                    if isinstance(v, dict) and v.get("front_3f") and v.get("rear_3f")], dtype=float)
    # 外れ値(±99.9等の欠測コード)を分位/モーメントから除外
    def _clip(a, lo=1, hi=99):
        q = np.percentile(a, [lo, hi]); return a[(a >= q[0]) & (a <= q[1])]
    tenc, agc, susc = _clip(ten), _clip(ag), _clip(sus)
    _BASE = {
        "ten": np.percentile(tenc, [10, 30, 70, 90]),
        "agari": np.percentile(agc, [10, 30, 70, 90]),
        "sustain": np.percentile(susc, [10, 30, 70, 90]),
        "ten_ms": (float(tenc.mean()), float(tenc.std()) or 1.0),
        "agari_ms": (float(agc.mean()), float(agc.std()) or 1.0),
        "sustain_ms": (float(susc.mean()), float(susc.std()) or 1.0),
    }


def _hensachi(x, ms):
    """偏差値(平均50・SD10)。高いほど良い。[20,80]にクリップ。"""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    mean, std = ms
    return int(round(min(80, max(20, 50 + 10 * (x - mean) / (std or 1.0)))))


def _grade(x, cuts):
    """cuts=[p10,p30,p70,p90] に対し D/C/B/A/S。高いほど良い。"""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    if x >= cuts[3]:
        return "S"
    if x >= cuts[2]:
        return "A"
    if x >= cuts[1]:
        return "B"
    if x >= cuts[0]:
        return "C"
    return "D"


def _kyakushitsu(corners_list, num_runners_list):
    """道中位置/頭数 の平均から脚質。corners[-2]=道中(3角相当)。"""
    pos = []
    for c, n in zip(corners_list, num_runners_list):
        if not c or not n:
            continue
        p = c[-2] if len(c) >= 2 else c[0]
        if p and n:
            pos.append(p / n)
    if not pos:
        return "—", None
    r = float(np.mean(pos))
    if r < 0.18:
        return "逃げ", r
    if r < 0.40:
        return "先行", r
    if r < 0.65:
        return "差し", r
    return "追込", r


def profile(ketto, date):
    """対象(ketto,date)直前の最近走から脚質・能力プロファイル(リークフリー)。"""
    _load()
    ketto = str(ketto); date = str(date)
    ds = _HDATES.get(ketto)
    if not ds:
        return None
    i = bisect.bisect_left(ds, date)
    past_dates = ds[:i][-RECENT_N:]
    if not past_dates:
        return None
    ten, ag, sus, joushou = [], [], [], []
    corners_l, nrun_l = [], []
    races_by_date = {r.get("race_date"): r for r in _HIST[ketto]}
    for pd_ in past_dates:
        s = _SED.get(f"{ketto}_{pd_}")
        if s:
            if s.get("ten_idx") is not None:
                ten.append(float(s["ten_idx"]))
            if s.get("agari_idx") is not None:
                ag.append(float(s["agari_idx"]))
            if s.get("front_3f") and s.get("rear_3f"):
                sus.append(float(s["front_3f"]) - float(s["rear_3f"]))
            if s.get("joushou_code"):
                joushou.append(float(s["joushou_code"]))
        r = races_by_date.get(pd_)
        if r:
            corners_l.append(r.get("corners"))
            nrun_l.append(r.get("num_runners"))
    ten_m = float(np.mean(ten)) if ten else None
    ag_m = float(np.mean(ag)) if ag else None
    sus_m = float(np.mean(sus)) if sus else None
    ks, ks_ratio = _kyakushitsu(corners_l, nrun_l)
    return {
        "n_runs": len(past_dates),
        "ten_idx": ten_m, "ten_t": _hensachi(ten_m, _BASE["ten_ms"]), "ten_grade": _grade(ten_m, _BASE["ten"]),
        "agari_idx": ag_m, "agari_t": _hensachi(ag_m, _BASE["agari_ms"]), "agari_grade": _grade(ag_m, _BASE["agari"]),
        "sustain": sus_m, "sustain_t": _hensachi(sus_m, _BASE["sustain_ms"]), "sustain_grade": _grade(sus_m, _BASE["sustain"]),
        "kyakushitsu": ks, "ks_ratio": ks_ratio,
        "joushou": float(np.mean(joushou)) if joushou else None,
    }


def tags(p):
    """プロファイル dict → 脚質・能力の言語化タグ list。"""
    if not p:
        return []
    out = []
    if p["agari_grade"] in ("S", "A") and p["ten_grade"] in ("C", "D"):
        out.append("末脚一閃型(展開待ち)")
    if p["ten_grade"] in ("S", "A") and p["sustain_grade"] in ("S", "A"):
        out.append("先行押し切り型")
    if p["sustain_grade"] in ("S", "A") and p["agari_grade"] in ("C", "D"):
        out.append("バテない持続型(消耗戦◎)")
    if p["agari_grade"] == "S" and p["ten_grade"] == "S":
        out.append("オールラウンダー")
    if p.get("joushou") and p["joushou"] <= 2.0:
        out.append("上昇気配")
    return out


def narrative(p):
    """プロファイル dict → 人間可読の1行印解説。"""
    if not p:
        return "(過去走データなし)"
    def _ax(nm, t, g):
        return f"{nm}{t if t is not None else '--'}({g})"
    axes = [_ax("テン", p["ten_t"], p["ten_grade"]),
            _ax("上がり", p["agari_t"], p["agari_grade"]),
            _ax("持続", p["sustain_t"], p["sustain_grade"])]
    tg = tags(p)
    return f"{p['kyakushitsu']:　<4} / {' '.join(axes)}" + (f"  ◀ {'・'.join(tg)}" if tg else "")


def _demo(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    te = pd.read_pickle(SPLITS / "test.pkl")
    if args.race:
        sel = te[te["race_id"].astype(str) == str(args.race)]
        races = [str(args.race)] if len(sel) else []
    else:
        # 既定は Regulus の土俵 = 3歳上芝OP+ に絞ってデモ
        from ml.nova.train_turf_op import filter_turf_op
        pool = filter_turf_op(te, "demo")
        if "age" in pool.columns:
            pool = pool[pool["age"] >= 3]
        if args.date:
            pool = pool[pool["date"].astype(str) == str(args.date)]
        # 直近日から見せる(test後半=新しい)
        pool = pool.sort_values("date", ascending=False)
        races = list(dict.fromkeys(pool["race_id"].astype(str)))[: args.n]
    if not races:
        print("該当レースなし(test split内)。--date か --race を確認。"); return 1
    for rid in races:
        rows = te[te["race_id"].astype(str) == rid].copy()
        if "umaban" in rows.columns:
            rows = rows.sort_values("umaban")
        d0 = str(rows["date"].iloc[0])
        grd = rows["grade"].iloc[0] if "grade" in rows.columns else "?"
        print(f"\n{'='*78}\nrace {rid}  {d0}  grade={grd}  ({len(rows)}頭)  ★脚質・能力プロファイル(Regulus craft)")
        print(f"{'馬番':>3} {'ketto':>10} {'脚質/3軸(テン/上がり/持続)・印解説':<46}")
        print("-" * 78)
        for _, r in rows.iterrows():
            p = profile(r["ketto_num"], r["date"])
            uma = int(r["umaban"]) if "umaban" in rows.columns and not pd.isna(r["umaban"]) else 0
            print(f"{uma:>3} {str(r['ketto_num']):>10} {narrative(p)}")
    return 0


def _kyi_tenkai(k):
    """KYI index エントリ → JRDB展開予想オーバーレイ(jrdbキー・Session 186)。
    道中/残り3F/ゴールの3コマ = アニメーション補間用キーフレーム。
    diff=先頭からの累積差(半馬身)・inout=1(最内)〜5(大外)。
    注意: pred系指数は負値中心(mean≈-13)。>0 を有効値扱いすると94%消える。"""
    def frame(pfx):
        o = k.get(f"pred_{pfx}_order")
        if o is None or o <= 0:
            return None
        return {"order": o, "diff": k.get(f"pred_{pfx}_diff"),
                "inout": k.get(f"pred_{pfx}_uchi_soto")}
    frames = {name: frame(src) for name, src in
              (("dochu", "dochu"), ("f3", "3f"), ("goal", "goal"))}
    frames = {name: v for name, v in frames.items() if v}
    if not frames and k.get("pred_ten_idx") is None:
        return None
    out = {"pace": k.get("pred_pace") or None,
           "ten_idx": k.get("pred_ten_idx"),
           "agari_idx": k.get("pred_agari_idx"),
           "position_idx": k.get("pred_position_idx")}
    out.update(frames)
    return out


def emit_date(date):
    """その日の全 race_*.json を読み、各馬の脚質プロファイル+JRDB展開予想を
    races/YYYY/MM/DD/leg_profiles.json に出力(web予想カードのオーバーレイ源)。
    返り値: 書いたレース数。"""
    import glob
    _load()
    kyi_path = config.indexes_dir() / "jrdb_kyi_index.json"
    kyi = json.load(open(kyi_path, encoding="utf-8")) if kyi_path.exists() else {}
    y, m, d = date.split("-")
    day_dir = config.races_dir() / y / m / d
    files = sorted(glob.glob(str(day_dir / "race_*.json")))
    out = {}
    for f in files:
        try:
            race = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        rid = str(race.get("race_id") or "")
        rdate = str(race.get("date") or date)
        if not rid:
            continue
        per = {}
        for e in race.get("entries", []):
            ket = e.get("ketto_num")
            uma = e.get("umaban")
            if not ket or not uma:
                continue
            p = profile(ket, rdate)
            jr = _kyi_tenkai(kyi[f"{ket}_{rdate}"]) if f"{ket}_{rdate}" in kyi else None
            if not p and not jr:
                continue
            # p 無し(過去走なし=新馬等)でも JRDB 展開予想があれば隊列図用に emit する。
            # その場合 n=0 — web 側の脚質テーブル/出馬表セルは n>0 でガード。
            rec = {
                "kyakushitsu": p["kyakushitsu"] if p else "—",
                "ten": p["ten_t"] if p else None,
                "agari": p["agari_t"] if p else None,
                "sustain": p["sustain_t"] if p else None,
                "ten_grade": p["ten_grade"] if p else "—",
                "agari_grade": p["agari_grade"] if p else "—",
                "sustain_grade": p["sustain_grade"] if p else "—",
                "tags": tags(p), "n": p["n_runs"] if p else 0,
            }
            if jr:
                rec["jrdb"] = jr
            per[str(int(uma))] = rec
        if per:
            out[rid] = per
    out_path = day_dir / "leg_profiles.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[emit] {out_path}  races={len(out)} (of {len(files)} files)")
    return len(out)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--race", help="race_id (test split内・デモ表示)")
    ap.add_argument("--date", help="YYYY-MM-DD (デモ表示の絞り)")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--emit-date", help="YYYY-MM-DD: その日の leg_profiles.json を生成")
    args = ap.parse_args()
    if args.emit_date:
        emit_date(args.emit_date)
        return 0
    return _demo(args)


if __name__ == "__main__":
    sys.exit(main())

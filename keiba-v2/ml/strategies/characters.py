#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""買い方キャラ (ペルソナ) 定義 (Session 149 / T12)

各キャラ = 「買い方テンプレ (bet_templates) + 2層バンクロールの day_fraction +
1点の太さ unit_fraction + 隔離設定」 の組。 simulate_bankroll_character が各キャラを
独立 bankroll で複利運用し、 資金軌道・リスク特性 (maxDD/破産確率/Sharpe) を比較する。

DB/IO 非依存の純データ層 (bet_templates.py と同階層)。

設計原則:
  - 配分は評価ベース (テンプレの weight) のみ。 Kelly/EV/オッズで歪めない (ふくだ §5)。
  - 比例ベット: 1点の基準 stake = 総資金 W × unit_fraction。 W が増えれば 1点も太る
    (複利)。 bet-template-lab の「flat 100円/点」を W 比例に置換したもの。
  - ringfenced (三連単ロマン等 -EV 遊び枠) は初期資金を総資金 × ringfence_cap_pct に
    隔離し、 補充なし (溶けたら停止)。 シズネ・ガードレール。
  - odds_dependent (オッズで買うレースを絞るキャラ) は確定オッズ精算だと後知恵。
    現状の全レース版は絞らないので後知恵なしだが、 単勝は分散が大きい旨を warnings で明記。

※ day_fraction / unit_fraction は初期の当たり値。 実際に軌道を見て (発火レース数・
   maxDD) 調整する前提。 CLI で全体上書きも可能。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Character:
    key: str
    name: str
    templates: Tuple[str, ...]       # bet_templates のテンプレ名 (1つ以上)
    day_fraction: float              # 総資金に対する日次スタート額の割合 (2層bankroll)
    unit_fraction: float = 0.0005    # 1点の基準 stake = 総資金 × この割合 (比例ベット)
    mark_mode: str = "composite"     # "composite" (常にtop5) | "ai" (崖カット実印)
    ringfenced: bool = False         # -EV 隔離枠 (補充なし)
    ringfence_cap_pct: float = 0.0   # 隔離初期資金 = 総資金 × この割合 (ringfenced 時のみ)
    odds_dependent: bool = False     # オッズ依存 (後知恵注意のマーカー)
    note: str = ""
    warnings: Tuple[str, ...] = ()


# 全キャラ初版は composite モード (常に◎○▲△Ⅲ top5 = テンプレ設計通りに発火)。
#   「画面の実 AI印 (ai モード = 崖カット) で買う実態」との差分は bet-lab を参照。
CHARACTERS: List[Character] = [
    Character(
        key="honmei", name="本命党",
        templates=("honmei_formation",), day_fraction=0.05,
        note="◎中心。三連複1頭軸保険 + 三連単◎○▲BOXボーナス。本命決着で両取り。"),
    Character(
        key="wide_kenjitsu", name="ワイド堅実党",
        templates=("wide_anchor",), day_fraction=0.05,
        note="ワイド◎流し保険 + 三連複本線。bet-lab で唯一 月中央値トントンの本線候補。"),
    Character(
        key="fukusho_kenjitsu", name="複勝堅実党",
        templates=("fukusho_korogashi",), day_fraction=0.05,
        note="複◎で土台 + ワイド◎-○ボーナス。ローリスク。"),
    Character(
        key="sanrentan_roman", name="三連単ロマン党",
        templates=("sanrentan_roman",), day_fraction=0.20, unit_fraction=0.02,
        ringfenced=True, ringfence_cap_pct=0.03,
        note="単◎保険 + 三連単アタマ固定フォメ。-EV 承知の隔離遊び枠 (補充なし)。",
        warnings=("-EV の隔離枠。初期資金は総資金の3%・補充なし。溶けたら停止 "
                  "(シズネ・ガードレール)。",)),
    Character(
        key="myomi", name="妙味党",
        templates=("tansho_ai2",), day_fraction=0.05,
        odds_dependent=True,
        note="AI上位2頭の単勝二刀流。全レース版 (オッズ条件で絞らない)。",
        warnings=("本来の妙味狙い (1人気弱×合成G ゲート) は確定オッズ判定=後知恵のため保留 "
                  "(S148: cache125%→predictions68%に消滅)。これは全レースで AI上位2頭の単勝を"
                  "買う版で、単勝のため配当分散が大きい。",)),
]

CHAR_BY_KEY: Dict[str, Character] = {c.key: c for c in CHARACTERS}


def list_characters() -> List[str]:
    return [c.key for c in CHARACTERS]


def get_character(key: str) -> Character:
    if key not in CHAR_BY_KEY:
        raise ValueError(f"unknown character: {key!r} (allowed: {list(CHAR_BY_KEY)})")
    return CHAR_BY_KEY[key]

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""買い方テンプレ・ライブラリ (Phase1 / Session 146)

『馬券力の正体』の券種併用・フォーメーション体系を **データ駆動** で表現し、
AI印 (◎○▲△Ⅲ穴☆) を入力に買い目リスト (Ticket) を生成する純関数層。
DB/IO/オッズ非依存 → backtest(Phase2)・複利sim(Phase3) が同じエンジンを呼ぶ。

設計思想 (本の体系):
  - 買い目 = 「券種 × 各列(ポジション)に入る印の集合」のフォーメーション。
    1列目=軸◎, 2列目=対抗○▲☆, 3列目=ヒモ△... を列で表現。
  - 併用 = 1テンプレに複数 BetComponent (保険/ボーナス/本線の役割付き)。
  - 「印の数は関係ない、すべては買い方次第」→ 印→列割当を変えれば点数が激変。
  - 「買い方から逆算して印をつける」→ テンプレ(列定義)を固定し markset を当てはめる。

入力 markset: {印名: [馬番,...]}。エンジンは印名に依存しない (テンプレが使う印が
  markset にあればよい)。△ など複数馬を持つ印に対応。
出力 Ticket: (bet_type, horses, role, template)。順序系(馬単/三連単)は horses が着順、
  順不同系(馬連/ワイド/三連複)は昇順ソート済 (重複は frozenset で排除)。
  金額は付けない (sizing は Phase3 / backtest 側の責務)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Dict, List, Optional, Tuple

# 券種 -> (列数, 順序あり?)
BET_SPEC: Dict[str, Tuple[int, bool]] = {
    "tansho": (1, False),
    "fukusho": (1, False),
    "umaren": (2, False),
    "wide": (2, False),
    "umatan": (2, True),
    "sanrenpuku": (3, False),
    "sanrentan": (3, True),
}

# 役割ラベル (表示・分析用。保険/ボーナス/本線)
ROLE_INSURANCE = "保険"
ROLE_BONUS = "ボーナス"
ROLE_MAIN = "本線"


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ticket:
    """1点の買い目 (金額なし)。順不同系は horses 昇順、順序系は着順。"""
    bet_type: str
    horses: Tuple[int, ...]
    role: str = ROLE_MAIN
    template: str = ""


@dataclass
class BetComponent:
    """テンプレ内の 1 券種の買い目定義 (列ごとに印名リストを置く)。"""
    bet_type: str
    columns: List[List[str]]      # 各列に入る印名 (例 [["◎"], ["○","▲"], ["○","▲","△"]])
    role: str = ROLE_MAIN
    weight: float = 1.0           # 配分の重み (Phase3 sizing 用ヒント)


@dataclass
class Template:
    """買い方テンプレ (併用 = 複数 component)。"""
    name: str
    label: str
    system: str                   # "当てる" (単/馬連/ワイド) | "当たる" (三連系)
    components: List[BetComponent]
    note: str = ""
    ringfenced: bool = False      # -EV遊び枠 (隔離bankroll上限ハードコード対象)


# ---------------------------------------------------------------------------
# 展開エンジン (純関数)
# ---------------------------------------------------------------------------

def _resolve(col: List[str], marks: Dict[str, List[int]]) -> List[int]:
    """列の印名リスト -> 馬番リスト (順序保持・重複除去)。"""
    out: List[int] = []
    for m in col:
        for u in marks.get(m, []) or []:
            iu = int(u)
            if iu not in out:
                out.append(iu)
    return out


def expand_component(c: BetComponent, marks: Dict[str, List[int]]) -> List[Ticket]:
    """1 component を買い目 (Ticket) のリストに展開。

    列の直積から、同一馬を含む組を除外。順不同系は frozenset、順序系は tuple で
    重複排除。markset に印が無く解決ゼロの列があれば空 (買えない)。
    """
    spec = BET_SPEC.get(c.bet_type)
    if spec is None:
        raise ValueError(f"unknown bet_type: {c.bet_type!r}")
    ncol, ordered = spec
    cols = c.columns[:ncol]
    if len(cols) < ncol:
        # 列定義が足りなければ最後の列を補完 (1頭軸流し等で省略を許す)
        cols = cols + [cols[-1]] * (ncol - len(cols)) if cols else []
    if len(cols) < ncol:
        return []
    horse_cols = [_resolve(col, marks) for col in cols]
    if any(len(h) == 0 for h in horse_cols):
        return []
    seen = set()
    tickets: List[Ticket] = []
    for combo in product(*horse_cols):
        if len(set(combo)) != len(combo):
            continue  # 同一馬を含む組は無効
        if ordered:
            key: object = tuple(combo)
            horses = tuple(combo)
        else:
            key = frozenset(combo)
            horses = tuple(sorted(combo))
        if key in seen:
            continue
        seen.add(key)
        tickets.append(Ticket(c.bet_type, horses, c.role, ""))
    return tickets


def apply_template(t: Template, marks: Dict[str, List[int]]) -> List[Ticket]:
    """テンプレを markset に適用して全買い目を生成 (template 名を付与)。"""
    out: List[Ticket] = []
    for c in t.components:
        for tk in expand_component(c, marks):
            out.append(Ticket(tk.bet_type, tk.horses, tk.role, t.name))
    return out


def count_points(t: Template, marks: Dict[str, List[int]]) -> int:
    return len(apply_template(t, marks))


# ---------------------------------------------------------------------------
# composite 序列 -> AI印 markset ヘルパ (Phase2 連携用・DB非依存)
# ---------------------------------------------------------------------------

DEFAULT_MARK_ORDER = ("◎", "○", "▲", "☆")  # 上位4頭に割当、残りは △ にまとめる


def marks_from_ranking(umaban_ranking: List[int], *,
                       singles: Tuple[str, ...] = DEFAULT_MARK_ORDER,
                       rest_mark: str = "△",
                       max_rest: Optional[int] = None) -> Dict[str, List[int]]:
    """composite 降順の馬番リスト -> {印: [馬番]}。

    上位から ◎○▲☆ を 1 頭ずつ、残りを △ (複数馬) に。max_rest で △ 頭数を制限。
    印体系はテンプレが使う名前に合わせて singles を差し替え可能。
    """
    marks: Dict[str, List[int]] = {}
    n_singles = len(singles)
    for i, u in enumerate(umaban_ranking):
        if i < n_singles:
            marks[singles[i]] = [int(u)]
        else:
            marks.setdefault(rest_mark, []).append(int(u))
    if max_rest is not None and rest_mark in marks:
        marks[rest_mark] = marks[rest_mark][:max_rest]
    return marks


# ---------------------------------------------------------------------------
# テンプレ定義 (本の代表パターン・データ駆動)
# ---------------------------------------------------------------------------

def _c(bet_type, columns, role=ROLE_MAIN, weight=1.0) -> BetComponent:
    return BetComponent(bet_type, columns, role, weight)


TEMPLATES: Dict[str, Template] = {
    # --- 当てる系 (単・馬連・ワイド = 少点数で仕留める) ---
    "honmei_hoken": Template(
        name="honmei_hoken", label="本命党 (単◎保険 + 馬連◎-○▲)", system="当てる",
        components=[
            _c("tansho", [["◎"]], ROLE_INSURANCE, 1.0),
            _c("umaren", [["◎"], ["○", "▲"]], ROLE_MAIN, 1.0),
        ],
        note="単◎を保険に、馬連◎-相手で本線。死に馬券を防ぎつつ的中率重視。"),

    "wide_anchor": Template(
        name="wide_anchor", label="ワイド堅実党 (ワイド◎流し保険 + 三連複本線)",
        system="当てる",
        components=[
            _c("wide", [["◎"], ["○", "▲", "☆"]], ROLE_INSURANCE, 1.0),
            _c("sanrenpuku", [["◎"], ["○", "▲"], ["○", "▲", "☆", "△"]], ROLE_MAIN, 1.0),
        ],
        note="ワイド流しで的中率担保 → 三連複を強気に絞る (本の黄金パターン)。"),

    "bonus_umatan": Template(
        name="bonus_umatan", label="ボーナス党 (単◎保険 + 馬単◎→○▲ボーナス)",
        system="当てる",
        components=[
            _c("tansho", [["◎"]], ROLE_INSURANCE, 1.0),
            _c("umatan", [["◎"], ["○", "▲"]], ROLE_BONUS, 1.0),
        ],
        note="単◎で的中担保、馬単アタマ固定で順番まで当たれば上乗せ。"),

    "fukusho_korogashi": Template(
        name="fukusho_korogashi", label="複勝堅実党 (複◎ + ワイド◎-○ボーナス)",
        system="当てる",
        components=[
            _c("fukusho", [["◎"]], ROLE_INSURANCE, 1.0),
            _c("wide", [["◎"], ["○"]], ROLE_BONUS, 1.0),
        ],
        note="複勝で土台、ワイドがボーナス。ローリスク・転がしの素地。"),

    # --- 当たる系 (三連系 = 広く運で拾う高配当・隔離) ---
    "sanrentan_roman": Template(
        name="sanrentan_roman",
        label="三連単ロマン党 (単◎保険 + 三連単◎→○▲☆→○▲☆△△)",
        system="当たる",
        components=[
            _c("tansho", [["◎"]], ROLE_INSURANCE, 0.2),
            _c("sanrentan", [["◎"], ["○", "▲", "☆"], ["○", "▲", "☆", "△"]],
               ROLE_BONUS, 0.8),
        ],
        note="単◎を保険に、3連単アタマ固定フォメで高配当を夢を買う。-EV承知の遊び枠。",
        ringfenced=True),

    "sanrenpuku_1jiku": Template(
        name="sanrenpuku_1jiku", label="三連複1頭軸流し (◎-相手総流し)",
        system="当たる",
        components=[
            _c("sanrenpuku", [["◎"], ["○", "▲", "☆", "△"], ["○", "▲", "☆", "△"]],
               ROLE_MAIN, 1.0),
        ],
        note="◎軸固定、2-3列目を相手総流し。荒れ読みレースの多点買い。"),
}


def list_templates() -> List[str]:
    return list(TEMPLATES.keys())


def get_template(name: str) -> Template:
    if name not in TEMPLATES:
        raise ValueError(f"unknown template: {name!r} (allowed: {list(TEMPLATES)})")
    return TEMPLATES[name]


# ---------------------------------------------------------------------------
# 動作確認 CLI (ダミー markset で全テンプレ展開)
# ---------------------------------------------------------------------------

def _demo():
    import sys
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    marks = {"◎": [1], "○": [2], "▲": [3], "☆": [4], "△": [5, 6, 7, 8]}
    print("markset:", marks)
    for name, t in TEMPLATES.items():
        tickets = apply_template(t, marks)
        by_type: Dict[str, int] = {}
        for tk in tickets:
            by_type[tk.bet_type] = by_type.get(tk.bet_type, 0) + 1
        breakdown = " ".join(f"{k}:{v}" for k, v in by_type.items())
        print(f"\n[{name}] {t.label}  系統={t.system}"
              + ("  (隔離)" if t.ringfenced else ""))
        print(f"  合計 {len(tickets)}点  ({breakdown})")
        for tk in tickets[:6]:
            arrow = "→" if BET_SPEC[tk.bet_type][1] else "-"
            print(f"    {tk.bet_type:<10} {arrow.join(str(h) for h in tk.horses):<12} [{tk.role}]")
        if len(tickets) > 6:
            print(f"    ... 他 {len(tickets) - 6}点")


if __name__ == "__main__":
    _demo()

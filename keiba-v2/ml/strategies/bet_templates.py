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
from typing import Collection, Dict, List, Optional, Tuple

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
    """1点の買い目。順不同系は horses 昇順、順序系は着順。

    weight = 配分の重み (sizing ヒント・component から伝播)。 精算側 (ラボ) が
    stake = 100 * weight として効かせる。 既定 1.0 (均等)。
    """
    bet_type: str
    horses: Tuple[int, ...]
    role: str = ROLE_MAIN
    template: str = ""
    weight: float = 1.0


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


def expand_component(c: BetComponent, marks: Dict[str, List[int]],
                     *, no_head: Collection[int] = ()) -> List[Ticket]:
    """1 component を買い目 (Ticket) のリストに展開。

    列の直積から、同一馬を含む組を除外。順不同系は frozenset、順序系は tuple で
    重複排除。markset に印が無く解決ゼロの列があれば空 (買えない)。

    no_head: 「1着に来ない」と判定した馬番集合 (役割分化 / Session 148 捨て馬券)。
      順序系券種 (馬単/三連単) の 1 列目からのみ除外する (2-3着要員に降格)。
      順不同系 (馬連/ワイド/三連複) と単複には影響しない。
      除外で 1 列目が空になれば component 不成立 (買えない)。
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
    if ordered and no_head:
        drop = set(int(u) for u in no_head)
        horse_cols[0] = [u for u in horse_cols[0] if u not in drop]
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
        tickets.append(Ticket(c.bet_type, horses, c.role, "", c.weight))
    return tickets


def apply_template(t: Template, marks: Dict[str, List[int]],
                   *, no_head: Collection[int] = ()) -> List[Ticket]:
    """テンプレを markset に適用して全買い目を生成 (template 名を付与)。

    no_head: 役割分化 (expand_component 参照)。順序系の 1 列目から除外する馬番。
    """
    out: List[Ticket] = []
    for c in t.components:
        for tk in expand_component(c, marks, no_head=no_head):
            out.append(Ticket(tk.bet_type, tk.horses, tk.role, t.name, tk.weight))
    return out


def count_points(t: Template, marks: Dict[str, List[int]],
                 *, no_head: Collection[int] = ()) -> int:
    return len(apply_template(t, marks, no_head=no_head))


# ---------------------------------------------------------------------------
# composite 序列 -> AI印 markset ヘルパ (Phase2 連携用・DB非依存)
# ---------------------------------------------------------------------------

# AI印 (markSet=2) と同語彙。 上位5頭に序列印を1頭ずつ (☆/ヒモ複数は廃止)。
#   ねじれ解消 (Session 147): テンプレ語彙を実 AI印 (◎○▲△Ⅲ) に統一し、
#   「印の付いた馬しか買わない」= 画面の印で買う実態に一致させる。
DEFAULT_MARK_ORDER = ("◎", "○", "▲", "△", "Ⅲ")


def marks_from_ranking(umaban_ranking: List[int], *,
                       singles: Tuple[str, ...] = DEFAULT_MARK_ORDER
                       ) -> Dict[str, List[int]]:
    """composite 降順の馬番リスト -> {印: [馬番]}。

    上位から ◎○▲△Ⅲ を 1 頭ずつ (各単独印)。 6位以降は無印。
    AI印 (markSet=2 = 複勝率の崖) と同じ語彙・同じ頭数なので、実 AI印が
    そのままテンプレに入る (印の無い馬を買わない)。
    """
    marks: Dict[str, List[int]] = {}
    for i, u in enumerate(umaban_ranking[:len(singles)]):
        marks[singles[i]] = [int(u)]
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

    "honmei_formation": Template(
        name="honmei_formation",
        label="本命党フォーメーション (三連複1頭軸保険 + 三連単◎○▲BOXボーナス)",
        system="当てる",
        components=[
            # 保険: 三連複 ◎-相手総流し (◎3着内6割を着順不問で広く拾う)
            _c("sanrenpuku", [["◎"], ["○", "▲", "△", "Ⅲ"], ["○", "▲", "△", "Ⅲ"]],
               ROLE_INSURANCE, 1.0),
            # ボーナス: 三連単 ◎○▲ BOX (本命決着の三連複の薄さを着順で約5倍補完)
            #   weight=0.25: 全体ROIをほぼ維持 (100.8→98.7%) しつつ本命決着時ROIを
            #   197→365%に倍化するフロンティアの推奨点。 ★今後の調整候補
            #   (「当たった時にでかく勝つ」鉄則で状況により厚くする余地あり / ふくだ S147)。
            _c("sanrentan", [["◎", "○", "▲"], ["◎", "○", "▲"], ["◎", "○", "▲"]],
               ROLE_BONUS, 0.25),
        ],
        note="◎○▲本命決着なのに三連複だと安い問題を、◎○▲三連単BOXで補完。"
             "本命決着で三連複+三連単が両取り (ふくだ Session 147)。三連単 weight=0.25。"),

    "wide_anchor": Template(
        name="wide_anchor", label="ワイド堅実党 (ワイド◎流し保険 + 三連複本線)",
        system="当てる",
        components=[
            _c("wide", [["◎"], ["○", "▲", "△"]], ROLE_INSURANCE, 1.0),
            _c("sanrenpuku", [["◎"], ["○", "▲"], ["○", "▲", "△", "Ⅲ"]], ROLE_MAIN, 1.0),
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
        label="三連単ロマン党 (単◎保険 + 三連単◎→○▲△→○▲△Ⅲ)",
        system="当たる",
        components=[
            _c("tansho", [["◎"]], ROLE_INSURANCE, 0.2),
            _c("sanrentan", [["◎"], ["○", "▲", "△"], ["○", "▲", "△", "Ⅲ"]],
               ROLE_BONUS, 0.8),
        ],
        note="単◎を保険に、3連単アタマ固定フォメで高配当を夢を買う。-EV承知の遊び枠。",
        ringfenced=True),

    "sanrenpuku_1jiku": Template(
        name="sanrenpuku_1jiku", label="三連複1頭軸流し (◎-相手総流し)",
        system="当たる",
        components=[
            _c("sanrenpuku", [["◎"], ["○", "▲", "△", "Ⅲ"], ["○", "▲", "△", "Ⅲ"]],
               ROLE_MAIN, 1.0),
        ],
        note="◎軸固定、2-3列目を相手(○▲△Ⅲ)で流す。印の付いた上位5頭内で完結。"),

    # --- Session 148 買い方チューニング検証から追加 ---
    "tansho_ai2": Template(
        name="tansho_ai2", label="単勝二刀流 (AI上位2頭)", system="当てる",
        components=[
            _c("tansho", [["◎", "○"]], ROLE_MAIN, 1.0),
        ],
        note="AI上位2頭の単勝2点。「1人気弱(AI△以下)×合成G>=2.5」ゲート併用が"
             "S148検証の最有望 (ROI124.8%/月中央値129.6%/9勝11ヶ月・train≒valid)。"),

    "honmei_formation_stable": Template(
        name="honmei_formation_stable",
        label="本命フォーメーション安定版 (三連単weight 0.1)",
        system="当てる",
        components=[
            _c("sanrenpuku", [["◎"], ["○", "▲", "△", "Ⅲ"], ["○", "▲", "△", "Ⅲ"]],
               ROLE_INSURANCE, 1.0),
            # 0.25→0.1: 月中央値 95.2→100.8% / 本命決着ROI 365→273% (S148 sweep)
            _c("sanrentan", [["◎", "○", "▲"], ["◎", "○", "▲"], ["◎", "○", "▲"]],
               ROLE_BONUS, 0.1),
        ],
        note="honmei_formation の安定寄せ (三連単 weight 0.25→0.1)。"
             "中央値100.8%を守りつつ本命決着273%。「でかく勝つ」⇄安定のフロンティア対照用。"),

    "honmei_plus_tansho": Template(
        name="honmei_plus_tansho",
        label="本命+単勝二刀 (三連複保険+単勝◎半分)",
        system="当てる",
        components=[
            _c("sanrenpuku", [["◎"], ["○", "▲", "△", "Ⅲ"], ["○", "▲", "△", "Ⅲ"]],
               ROLE_INSURANCE, 1.0),
            _c("tansho", [["◎"]], ROLE_BONUS, 0.5),
        ],
        note="三連単の代わりに単勝◎で体験の質を買う形。中央値103.3%/的中率45% "
             "(S148 sweep。三連単0.25版より中央値も的中体験も上、爆発力は劣る)。"),
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
    marks = {"◎": [1], "○": [2], "▲": [3], "△": [4], "Ⅲ": [5]}
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

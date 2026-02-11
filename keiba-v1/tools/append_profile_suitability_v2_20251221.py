import glob
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


DATE = "20251221"
RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"


RIGHT_TURN_TRACKS = {"中山", "阪神", "京都", "小倉", "札幌", "函館", "福島"}
LEFT_TURN_TRACKS = {"中京", "東京", "新潟"}


def _safe_float(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s or s == "☆":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_horse_name(name: str) -> str:
    name = (name or "").strip()
    name = name.replace("（", "(").replace("）", ")")
    name = re.sub(r"\s+", "", name)
    return name


def _extract_int(s: str) -> Optional[int]:
    s = (s or "").strip()
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None


def _turn_direction(track: str) -> Optional[str]:
    track = (track or "").strip()
    if track in RIGHT_TURN_TRACKS:
        return "右"
    if track in LEFT_TURN_TRACKS:
        return "左"
    return None


def _circled_to_int(token: str) -> Optional[int]:
    token = (token or "").strip()
    if not token:
        return None
    # Some files use circled numbers like ①..⑳ or ⑴..⑳
    # We'll just take the first character and map unicode blocks.
    ch = token[0]
    o = ord(ch)
    # ①(2460) .. ⑳(2473)
    if 0x2460 <= o <= 0x2473:
        return o - 0x245F
    # ⑴(2474) .. ⒇(2487) (parenthesized)
    if 0x2474 <= o <= 0x2487:
        return o - 0x2473
    # Fullwidth digits etc fallback
    return _extract_int(token)


@dataclass
class Runner:
    frame: str
    number: str
    name: str
    odds: Optional[float]
    ai: Optional[float]
    paper_mark: str
    total_p: Optional[float]
    profile_path: Optional[str]


@dataclass
class Race:
    track: str  # 中京/阪神/中山
    r_no: int
    race_id: str
    surface: str  # 芝/ダ/障
    distance: int
    path: str
    runners: List[Runner]
    pos_group_by_no: Dict[str, str]  # 馬番 -> 逃げ/好位/中位/後方


@dataclass
class PastRun:
    date: str
    track: str
    race_name: str
    dist_surface: str
    going: str
    finish: Optional[int]
    memo: str

    @property
    def surface(self) -> Optional[str]:
        if self.dist_surface.startswith("ダ"):
            return "ダ"
        if self.dist_surface.startswith("芝"):
            return "芝"
        return None

    @property
    def distance(self) -> Optional[int]:
        m = re.search(r"(\d{3,4})", self.dist_surface)
        return int(m.group(1)) if m else None

    @property
    def turn(self) -> Optional[str]:
        return _turn_direction(self.track)


TRAIT_PATTERNS: List[Tuple[str, str]] = [
    (r"出遅れ|ゲート", "スタート課題"),
    (r"砂を被|砂被", "砂被りが鍵"),
    (r"ワンペース|一本調子", "ワンペース型"),
    (r"ズブ|反応.*鈍|追われて案外", "ズブい（加速遅い）"),
    (r"折り合い|力み", "折り合いが鍵"),
    (r"先行|好位|ハナ", "先行力"),
    (r"差し|追い上げ|外から", "差し脚"),
    (r"右回り", "右回り向き/注意"),
    (r"左回り", "左回り向き/注意"),
    (r"距離短縮", "距離短縮向き/注意"),
    (r"距離延ば|距離延長|距離いい方に", "距離延長向き/注意"),
    (r"ダート.*歓迎|ダート.*合|ダート.*適性", "ダート適性示唆"),
    (r"芝.*歓迎|芝.*合|芝.*適性", "芝適性示唆"),
]


def parse_race_md(path: str) -> Race:
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m_title = re.search(r"^#\s*(中京|阪神|中山)(\d+)R", text, re.M)
    if not m_title:
        raise ValueError(f"Race title not found: {path}")
    track = m_title.group(1)
    r_no = int(m_title.group(2))

    m_course = re.search(r"\*\*競馬場\*\*:\s*(中京|阪神|中山)\s+((?:芝(?:内|外)?|ダ|障害))・(\d+)m", text)
    if not m_course:
        raise ValueError(f"Course line not found: {path}")
    surface_raw = m_course.group(2)
    if surface_raw.startswith("芝"):
        surface = "芝"
    elif surface_raw.startswith("ダ"):
        surface = "ダ"
    else:
        surface = "障"
    distance = int(m_course.group(3))

    race_id = os.path.splitext(os.path.basename(path))[0]

    # 1) 出走表 runners
    runners: List[Runner] = []
    lines = text.splitlines()
    in_table = False
    for ln in lines:
        if ln.startswith("| 枠 | 馬番 | 馬名 |"):
            in_table = True
            continue
        if in_table:
            if not ln.startswith("|"):
                break
            if ln.startswith("|:---"):
                continue
            cols = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cols) < 11:
                continue
            frame = cols[0]
            number = cols[1]
            name_cell = cols[2]
            m_link = re.search(r"\[([^\]]+)\]\(([^)]+)\)", name_cell)
            name = m_link.group(1) if m_link else name_cell
            link = m_link.group(2) if m_link else ""
            name = _normalize_horse_name(name)
            profile_path = None
            m_profile = re.search(r"(?:Z:\/KEIBA-CICD\/data2\/horses\/profiles\/[^)]+\.md)", link)
            if m_profile:
                profile_path = m_profile.group(0).replace("Z:/", "Z:\\").replace("/", "\\")

            odds = _safe_float(cols[6])
            ai = _safe_float(cols[7])
            paper = cols[9] if cols[9] else ""
            total_p = _safe_float(cols[10])
            runners.append(
                Runner(
                    frame=frame,
                    number=number,
                    name=name,
                    odds=odds,
                    ai=ai,
                    paper_mark=paper,
                    total_p=total_p,
                    profile_path=profile_path,
                )
            )

    # 2) 展開予想の馬番配置（B用）
    pos_group_by_no: Dict[str, str] = {}
    m_pos_table = re.search(r"\|\s*逃げ\s*\|\s*好位\s*\|\s*中位\s*\|\s*後方\s*\|\s*\n\|.*\n\|([^\n]+)\n", text)
    if m_pos_table:
        row = m_pos_table.group(1)
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        groups = ["逃げ", "好位", "中位", "後方"]
        for gi, cell in enumerate(cells[:4]):
            if cell == "-" or not cell:
                continue
            for tok in cell.split():
                n = _circled_to_int(tok)
                if n is None:
                    continue
                pos_group_by_no[str(n)] = groups[gi]

    return Race(
        track=track,
        r_no=r_no,
        race_id=race_id,
        surface=surface,
        distance=distance,
        path=path,
        runners=runners,
        pos_group_by_no=pos_group_by_no,
    )


def parse_profile_recent_runs(profile_text: str) -> List[PastRun]:
    # Parse "最近10走（統合）" markdown table
    if "## 最近10走（統合）" not in profile_text:
        return []
    block = profile_text.split("## 最近10走（統合）", 1)[1]
    m_next = re.search(r"\n##\s+", block)
    if m_next:
        block = block[: m_next.start()]
    lines = [ln for ln in block.splitlines() if ln.startswith("|")]
    if len(lines) < 3:
        return []

    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]

    def idx(col: str) -> Optional[int]:
        try:
            return header.index(col)
        except ValueError:
            return None

    i_date = idx("日付")
    i_track = idx("競馬場")
    i_race = idx("レース")
    i_dist = idx("距離")
    i_going = idx("馬場")
    i_memo = idx("結果メモ")
    i_finishpop = idx("着順/人気")

    if i_date is None or i_track is None or i_race is None or i_dist is None:
        return []

    out: List[PastRun] = []
    for ln in lines[2:]:
        if ln.startswith("|:---"):
            continue
        cols = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cols) < len(header):
            continue
        finish = None
        if i_finishpop is not None:
            finish = _extract_int(cols[i_finishpop])
        out.append(
            PastRun(
                date=cols[i_date],
                track=cols[i_track],
                race_name=cols[i_race],
                dist_surface=cols[i_dist],
                going=cols[i_going] if i_going is not None else "",
                finish=finish,
                memo=cols[i_memo] if i_memo is not None else "",
            )
        )
    return out


def extract_traits(profile_text: str) -> List[str]:
    traits: List[str] = []
    for pat, label in TRAIT_PATTERNS:
        if re.search(pat, profile_text):
            traits.append(label)
    # stable order, but unique
    uniq: List[str] = []
    for t in traits:
        if t not in uniq:
            uniq.append(t)
    return uniq[:4]


def _c_score_and_reasons(race: Race, r: Runner, runs: List[PastRun], traits: List[str], profile_text: str) -> Tuple[float, List[str]]:
    """
    C: sand/turn/gate/position-like penalties & bonuses
    """
    s = 0.0
    reasons: List[str] = []

    # Turn direction (only when we have finishes)
    race_turn = "左" if race.track == "中京" else "右"
    right_fin: List[int] = []
    left_fin: List[int] = []
    for pr in runs[:10]:
        if pr.finish is None:
            continue
        t = pr.turn
        if t == "右":
            right_fin.append(pr.finish)
        elif t == "左":
            left_fin.append(pr.finish)
    if race_turn == "右" and right_fin:
        avg = sum(right_fin) / len(right_fin)
        if avg <= 6:
            s += 0.6
            reasons.append("右回りで崩れにくい")
        elif avg >= 10:
            s -= 0.4
            reasons.append("右回りで成績が安定しない")
    if race_turn == "左" and left_fin:
        avg = sum(left_fin) / len(left_fin)
        if avg <= 6:
            s += 0.6
            reasons.append("左回りで崩れにくい")
        elif avg >= 10:
            s -= 0.4
            reasons.append("左回りで成績が安定しない")

    # Sand / kickback
    if race.surface == "ダ":
        if "砂被りが鍵" in traits:
            # If expected position is back/mid -> higher risk
            pos = race.pos_group_by_no.get(r.number)
            if pos in ("中位", "後方"):
                s -= 0.6
                reasons.append("砂被り課題×後ろ想定はリスク")
            else:
                s -= 0.2
                reasons.append("砂被り課題は注意")

    # Gate issues
    if "スタート課題" in traits:
        pos = race.pos_group_by_no.get(r.number)
        if pos in ("逃げ", "好位"):
            s -= 0.4
            reasons.append("スタート課題×前付け想定は不安")
        else:
            s -= 0.2
            reasons.append("スタート課題に注意")

    # Quick extra: explicit right/left mention in text
    if race_turn == "右" and re.search(r"右回り.*改めて|右回り.*プラス", profile_text):
        s += 0.3
        reasons.append("右回りが材料")
    if race_turn == "左" and re.search(r"左回り.*改めて|左回り.*プラス", profile_text):
        s += 0.3
        reasons.append("左回りが材料")

    return s, reasons


def _b_score_and_reasons(race: Race, r: Runner, traits: List[str]) -> Tuple[float, List[str]]:
    """
    B: running style × expected position.
    """
    s = 0.0
    reasons: List[str] = []
    pos = race.pos_group_by_no.get(r.number)
    if not pos:
        return 0.0, []

    has_front = "先行力" in traits
    has_close = "差し脚" in traits
    one_pace = "ワンペース型" in traits

    if has_front and pos in ("逃げ", "好位"):
        s += 0.5
        reasons.append("先行力×前目想定")
    if has_close and pos in ("中位", "後方"):
        s += 0.4
        reasons.append("差し脚×中後ろ想定")

    # mismatch penalties (small)
    if has_front and pos == "後方":
        s -= 0.2
    if has_close and pos == "逃げ":
        s -= 0.2

    # one-pace tends to want position (avoid too far back)
    if one_pace and pos in ("逃げ", "好位"):
        s += 0.2
        reasons.append("ワンペース×前目が理想")
    if one_pace and pos == "後方":
        s -= 0.2

    return s, reasons


def _a_score_and_reasons(race: Race, runs: List[PastRun], profile_text: str) -> Tuple[float, List[str]]:
    """
    A: distance fit (weaker priority per request)
    """
    s = 0.0
    reasons: List[str] = []
    same = 0
    close = 0
    for pr in runs[:10]:
        if pr.surface != race.surface:
            continue
        d = pr.distance
        if d is None:
            continue
        if d == race.distance:
            same += 1
        elif abs(d - race.distance) <= 200:
            close += 1
    if same:
        s += 0.6
        reasons.append(f"同条件（{race.surface}{race.distance}）経験")
    elif close:
        s += 0.3
        reasons.append(f"近い条件（±200）経験")

    # Hints about distance change (very small)
    if re.search(r"距離短縮.*プラス|距離短縮魅力", profile_text):
        reasons.append("距離短縮が材料")
    if re.search(r"距離延長.*プラス|距離いい方に", profile_text):
        reasons.append("距離延長が材料")
    return s, reasons[:2]


def _base_score(r: Runner) -> float:
    ai = r.ai or 0.0
    tp = r.total_p or 0.0
    paper = {"◎": 3.0, "○": 2.0, "▲": 1.0, "△": 0.5}.get((r.paper_mark or "").strip(), 0.0)
    return ai / 65.0 + tp / 14.0 + paper


def build_append_block(race: Race, scored: List[Tuple[Runner, float, List[str], List[str]]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top = scored[:5]
    marks = ["◎", "○", "▲", "△", "△"]

    lines: List[str] = []
    lines.append("")
    lines.append("## GPT-5 追記（適性強化：C→B→A）")
    lines.append(f"- 更新: {now}")
    lines.append("")
    lines.append("### 印（適性を加味した再ランク）")
    for i, (r, s, traits, reasons) in enumerate(top):
        m = marks[i] if i < len(marks) else ""
        odds = f"{r.odds:.1f}" if r.odds is not None else "?"
        reason_txt = " / ".join(reasons) if reasons else "適性根拠薄め（データ不足）"
        trait_txt = "・".join(traits) if traits else "-"
        lines.append(f"- {m} {r.number} {r.name}（オッズ:{odds} / 適性v2:{s:.1f}）: {reason_txt} | 特徴: {trait_txt}")

    lines.append("")
    lines.append("### メモ（優先度）")
    lines.append("- C: 砂被り/右左/ゲート等 → B: 脚質×展開 → A: 距離")
    lines.append("")
    lines.append("----")
    lines.append("")
    return "\n".join(lines)


def append_block(path: str, block: str) -> bool:
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    if "## GPT-5 追記（適性強化：C→B→A）" in text:
        return False
    if "# 追記" not in text:
        raise ValueError(f"追記セクションが見つかりません: {path}")
    if not text.endswith("\n"):
        text += "\n"
    text += block
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def main() -> None:
    tracks = ["中京", "阪神", "中山"]
    race_paths: List[str] = []
    for tr in tracks:
        race_paths.extend(glob.glob(os.path.join(RACES_ROOT, tr, "*.md")))
    races = [parse_race_md(p) for p in race_paths]

    track_order = {"中京": 0, "阪神": 1, "中山": 2}
    races.sort(key=lambda r: (r.r_no, track_order.get(r.track, 9)))

    updated = 0
    skipped = 0
    for race in races:
        scored: List[Tuple[Runner, float, List[str], List[str]]] = []
        for runner in race.runners:
            profile_text = ""
            runs: List[PastRun] = []
            traits: List[str] = []
            if runner.profile_path and os.path.exists(runner.profile_path):
                profile_text = open(runner.profile_path, "r", encoding="utf-8", errors="replace").read()
                runs = parse_profile_recent_runs(profile_text)
                traits = extract_traits(profile_text)

            c_s, c_r = _c_score_and_reasons(race, runner, runs, traits, profile_text)
            b_s, b_r = _b_score_and_reasons(race, runner, traits)
            a_s, a_r = _a_score_and_reasons(race, runs, profile_text)

            score = _base_score(runner) + c_s + b_s + a_s
            reasons = (c_r + b_r + a_r)[:3]
            scored.append((runner, score, traits[:3], reasons))

        scored.sort(key=lambda x: x[1], reverse=True)
        block = build_append_block(race, scored)
        did = append_block(race.path, block)
        if did:
            updated += 1
        else:
            skipped += 1

    print(f"done. updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()



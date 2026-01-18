import glob
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


DATE = "20251221"
RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"


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


@dataclass
class PastRun:
    date: str
    track: str
    race_name: str
    dist_surface: str  # 例: ダ1800 / 芝1400 / 芝内・1800m 等
    going: str
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


TRAIT_PATTERNS: List[Tuple[str, str]] = [
    (r"出遅れ|ゲート", "スタート課題"),
    (r"砂を被|砂被", "砂被りが鍵"),
    (r"ワンペース|一本調子", "ワンペース型"),
    (r"ズブ|反応.*鈍|追われて", "ズブい（加速遅い）"),
    (r"折り合い|力み", "折り合いが鍵"),
    (r"先行|好位|ハナ", "先行力"),
    (r"差し|追い上げ|外から", "差し脚"),
    (r"右回り", "右回り向き/注意"),
    (r"左回り", "左回り向き/注意"),
    (r"距離短縮", "距離短縮向き/注意"),
    (r"距離延ば|距離延長|距離いい方に", "距離延長向き/注意"),
    (r"ダート.*歓迎|ダート.*合", "ダート適性示唆"),
    (r"芝.*歓迎|芝.*合", "芝適性示唆"),
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
                # Convert Z:/ to Z:\ for file access
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
    return Race(track=track, r_no=r_no, race_id=race_id, surface=surface, distance=distance, path=path, runners=runners)


def parse_profile_recent_runs(profile_text: str) -> List[PastRun]:
    # Parse "最近10走（統合）" markdown table (best structured for our purpose)
    if "## 最近10走（統合）" not in profile_text:
        return []

    block = profile_text.split("## 最近10走（統合）", 1)[1]
    # stop at next heading
    m_next = re.search(r"\n##\s+", block)
    if m_next:
        block = block[: m_next.start()]

    lines = [ln for ln in block.splitlines() if ln.startswith("|")]
    if len(lines) < 3:
        return []

    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    # find indices
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

    # if essential cols missing, skip
    if i_date is None or i_track is None or i_race is None or i_dist is None:
        return []

    out: List[PastRun] = []
    for ln in lines[2:]:
        if ln.startswith("|:---"):
            continue
        cols = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cols) < len(header):
            continue
        out.append(
            PastRun(
                date=cols[i_date],
                track=cols[i_track],
                race_name=cols[i_race],
                dist_surface=cols[i_dist],
                going=cols[i_going] if i_going is not None else "",
                memo=cols[i_memo] if i_memo is not None else "",
            )
        )
    return out


def extract_traits(profile_text: str) -> List[str]:
    traits = []
    for pat, label in TRAIT_PATTERNS:
        if re.search(pat, profile_text):
            traits.append(label)
    # keep only a few
    return traits[:3]


def suitability_score(race: Race, runs: List[PastRun], profile_text: str) -> Tuple[float, List[str]]:
    """
    Returns: (score, reasons)
    - score is a small adjustment (roughly -2..+3)
    """
    s = 0.0
    reasons: List[str] = []

    # Surface/distance match in recent runs
    same_exact = 0
    same_close = 0
    for pr in runs[:10]:
        if pr.surface != race.surface:
            continue
        d = pr.distance
        if d is None:
            continue
        if d == race.distance:
            same_exact += 1
        elif abs(d - race.distance) <= 200:
            same_close += 1
    if same_exact > 0:
        s += 2.0
        reasons.append(f"同条件（{race.surface}{race.distance}）の出走経験あり")
    elif same_close > 0:
        s += 1.0
        reasons.append(f"近い条件（{race.surface}{race.distance}±200）経験あり")
    else:
        # first-time surface hint
        if race.surface == "ダ" and re.search(r"初ダ|ダート.*歓迎|ダート.*合", profile_text):
            s += 0.5
            reasons.append("ダート適性示唆コメントあり")
        if race.surface == "芝" and re.search(r"初芝|芝.*歓迎|芝.*合", profile_text):
            s += 0.5
            reasons.append("芝適性示唆コメントあり")

    # Distance change hints
    if re.search(r"距離短縮.*プラス|距離短縮.*魅力", profile_text):
        reasons.append("距離短縮が材料")
    if re.search(r"距離延長.*プラス|距離いい方に", profile_text):
        reasons.append("距離延長が材料")

    # Start / trouble penalties
    if re.search(r"出遅れ", profile_text):
        s -= 0.3
        reasons.append("出遅れ癖に注意")
    if race.surface == "ダ" and re.search(r"砂を被.*嫌|砂を被.*課題", profile_text):
        s -= 0.3
        reasons.append("砂被りが課題の可能性")

    # Keep reasons short
    return s, reasons[:3]


def base_score(r: Runner) -> float:
    ai = r.ai or 0.0
    tp = r.total_p or 0.0
    paper = {"◎": 3.0, "○": 2.0, "▲": 1.0, "△": 0.5}.get((r.paper_mark or "").strip(), 0.0)
    return ai / 60.0 + tp / 12.0 + paper


def build_append_block(
    race: Race,
    scored: List[Tuple[Runner, float, List[str], List[str]]],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top = scored[:5]
    marks = ["◎", "○", "▲", "△", "△"]

    lines: List[str] = []
    lines.append("")
    lines.append("## GPT-5 追記（適性重視：過去走コメント）")
    lines.append(f"- 更新: {now}")
    lines.append("")
    lines.append("### 印（適性を加味した再ランク）")
    for i, (r, s, traits, reasons) in enumerate(top):
        m = marks[i] if i < len(marks) else ""
        odds = f"{r.odds:.1f}" if r.odds is not None else "?"
        reason_txt = " / ".join(reasons) if reasons else "適性根拠薄め（データ不足）"
        trait_txt = "・".join(traits) if traits else "-"
        lines.append(f"- {m} {r.number} {r.name}（オッズ:{odds} / 適性スコア:{s:.1f}）: {reason_txt} | 特徴: {trait_txt}")

    lines.append("")
    lines.append("### メモ（使い方）")
    lines.append("- ここは『調教ブロック』とは別に、過去走コメント由来の適性を上乗せして並べ替えています")
    lines.append("- レース当日の馬場/枠/出走取消で前提が崩れる場合は、上の順序より見送り判断を優先してください")
    lines.append("")
    lines.append("----")
    lines.append("")
    return "\n".join(lines)


def append_block(path: str, block: str) -> bool:
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    if "## GPT-5 追記（適性重視：過去走コメント）" in text:
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
        for r in race.runners:
            profile_text = ""
            runs: List[PastRun] = []
            traits: List[str] = []
            if r.profile_path and os.path.exists(r.profile_path):
                profile_text = open(r.profile_path, "r", encoding="utf-8", errors="replace").read()
                runs = parse_profile_recent_runs(profile_text)
                traits = extract_traits(profile_text)
            suit, reasons = suitability_score(race, runs, profile_text)
            score = base_score(r) + suit
            scored.append((r, score, traits, reasons))
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



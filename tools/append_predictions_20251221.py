import csv
import glob
import os
import re
import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


DATE = "20251221"
RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"
PROFILES_ROOT = r"Z:\KEIBA-CICD\data2\horses\profiles"


def _safe_float(s: str) -> Optional[float]:
    s = (s or "").strip()
    if not s:
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


def _lap_type_from_last2(lap2: Optional[float], lap1: Optional[float]) -> Optional[str]:
    if lap1 is None or lap2 is None:
        return None
    # 画像の定義に合わせる（A3/B3の扱いを修正）
    if lap1 < lap2:  # 加速
        if 11.0 <= lap1 < 12.0:
            return "A3"
        if 12.0 <= lap1 < 13.0:
            if 12.0 <= lap2 < 13.0:
                return "A2"
            return "A1"
        return None
    if lap1 > lap2:  # 減速
        if 11.0 <= lap2 < 12.0:
            return "B3"
        if 12.0 <= lap2 < 13.0:
            if 12.0 <= lap1 < 13.0:
                return "B2"
            return "B1"
        return None
    return None


def _format_laps(laps: List[Optional[float]]) -> str:
    parts = []
    for v in laps:
        if v is None:
            parts.append("-")
        else:
            parts.append(f"{v:.1f}")
    return "-".join(parts)


@dataclass
class HillWork:
    date: str
    place: str  # 栗東/美浦など
    trainer: str
    time4f: Optional[float]  # Time1
    lap4: Optional[float]
    lap3: Optional[float]
    lap2: Optional[float]
    lap1: Optional[float]

    @property
    def lap_type(self) -> Optional[str]:
        return _lap_type_from_last2(self.lap2, self.lap1)


@dataclass
class CourseWork:
    date: str
    place: str
    direction: str  # 左/右
    trainer: str
    f5: Optional[float]
    f4: Optional[float]
    f3: Optional[float]
    f2: Optional[float]
    f1: Optional[float]
    lap2: Optional[float]
    lap1: Optional[float]
    related: str

    @property
    def lap_type(self) -> Optional[str]:
        return _lap_type_from_last2(self.lap2, self.lap1)


@dataclass
class Runner:
    frame: str
    number: str
    name: str
    odds: Optional[float]
    ai: Optional[float]
    paper_mark: str
    total_p: Optional[float]


@dataclass
class Race:
    track: str  # 中京/阪神/中山
    r_no: int
    race_id: str
    surface: str  # 芝/ダ
    distance: int
    path: str
    runners: List[Runner]


def load_hill_works(csv_path: str) -> Dict[str, List[HillWork]]:
    by_horse: Dict[str, List[HillWork]] = {}
    with open(csv_path, "r", encoding="cp932", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            horse = _normalize_horse_name(row.get("馬名", ""))
            if not horse:
                continue
            w = HillWork(
                date=row.get("年月日", "").strip(),
                place=row.get("場所", "").strip(),
                trainer=row.get("調教師", "").strip(),
                time4f=_safe_float(row.get("Time1", "")),
                lap4=_safe_float(row.get("Lap4", "")),
                lap3=_safe_float(row.get("Lap3", "")),
                lap2=_safe_float(row.get("Lap2", "")),
                lap1=_safe_float(row.get("Lap1", "")),
            )
            by_horse.setdefault(horse, []).append(w)
    for k in list(by_horse.keys()):
        by_horse[k].sort(key=lambda x: x.date)
    return by_horse


def load_course_works(csv_path: str) -> Dict[str, List[CourseWork]]:
    by_horse: Dict[str, List[CourseWork]] = {}
    with open(csv_path, "r", encoding="cp932", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            horse = _normalize_horse_name(row.get("馬名", ""))
            if not horse:
                continue
            w = CourseWork(
                date=row.get("年月日", "").strip(),
                place=row.get("場所", "").strip(),
                direction=row.get("回り", "").strip(),
                trainer=row.get("調教師", "").strip(),
                f5=_safe_float(row.get("5F", "")),
                f4=_safe_float(row.get("4F", "")),
                f3=_safe_float(row.get("3F", "")),
                f2=_safe_float(row.get("2F", "")),
                f1=_safe_float(row.get("1F", "")),
                lap2=_safe_float(row.get("Lap2", "")),
                lap1=_safe_float(row.get("Lap1", "")),
                related=(row.get("関連データ", "") or "").strip(),
            )
            by_horse.setdefault(horse, []).append(w)
    for k in list(by_horse.keys()):
        by_horse[k].sort(key=lambda x: x.date)
    return by_horse


def parse_race_md(path: str) -> Race:
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m_title = re.search(r"^#\s*(中京|阪神|中山)(\d+)R", text, re.M)
    if not m_title:
        raise ValueError(f"Race title not found: {path}")
    track = m_title.group(1)
    r_no = int(m_title.group(2))

    # Examples:
    # - **競馬場**: 阪神 ダ・1800m
    # - **競馬場**: 中山 芝外・1600m
    # - **競馬場**: 中山 芝内・1800m
    # - **競馬場**: 中山 ダ・2880m (障害戦でも表記はダのことがある)
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

    m_race_id = re.search(r"race/(\\d+)/(\\d+)$", text, re.M)
    race_id = os.path.splitext(os.path.basename(path))[0]
    if m_race_id:
        race_id = m_race_id.group(2)

    # Parse 出走表 rows (the first table)
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
            m_link = re.search(r"\[([^\]]+)\]\(", name_cell)
            name = m_link.group(1) if m_link else name_cell
            name = _normalize_horse_name(name)
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
                )
            )
    return Race(
        track=track,
        r_no=r_no,
        race_id=race_id,
        surface=surface,
        distance=distance,
        path=path,
        runners=runners,
    )


def _paper_bonus(mark: str) -> float:
    mark = (mark or "").strip()
    return {"◎": 4.0, "○": 3.0, "▲": 2.0, "△": 1.0}.get(mark, 0.0)


def _training_score(hill: Optional[HillWork], course: Optional[CourseWork]) -> float:
    s = 0.0
    if hill and hill.time4f is not None:
        if hill.time4f <= 52.0:
            s += 3.0
        elif hill.time4f <= 54.0:
            s += 2.0
        elif hill.time4f <= 56.0:
            s += 1.0
        if hill.lap_type in ("A2", "A3"):
            s += 1.0
        if hill.lap_type in ("B2", "B3"):
            s -= 0.5
    if course:
        if course.f5 is not None:
            if course.f5 <= 67.9:
                s += 2.0
            elif course.f5 <= 69.9:
                s += 1.0
        if course.f4 is not None and course.f4 <= 54.0:
            s += 1.0
        if course.lap_type in ("A2", "A3"):
            s += 0.5
        if course.lap_type in ("B2", "B3"):
            s -= 0.5
    return s


def _base_score(r: Runner) -> float:
    ai = r.ai or 0.0
    tp = r.total_p or 0.0
    return ai / 50.0 + tp / 10.0 + _paper_bonus(r.paper_mark)


def pick_marks(
    race: Race,
    hill_by_horse: Dict[str, List[HillWork]],
    course_by_horse: Dict[str, List[CourseWork]],
) -> Tuple[List[Tuple[Runner, float, Optional[HillWork], Optional[CourseWork]]], Dict[str, float]]:
    scored = []
    score_map: Dict[str, float] = {}
    for r in race.runners:
        hill = (hill_by_horse.get(r.name) or [])[-1] if hill_by_horse.get(r.name) else None
        course = (course_by_horse.get(r.name) or [])[-1] if course_by_horse.get(r.name) else None
        s = _base_score(r) + _training_score(hill, course)
        scored.append((r, s, hill, course))
        score_map[r.name] = s
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored, score_map


def build_append_block(
    race: Race,
    scored: List[Tuple[Runner, float, Optional[HillWork], Optional[CourseWork]]],
    block_header: str,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top = scored[:5]
    marks = ["◎", "○", "▲", "△", "△"]
    picks = []
    for i, (r, s, hill, course) in enumerate(top):
        m = marks[i] if i < len(marks) else ""
        picks.append((m, r, s, hill, course))

    # Determine confidence (margin)
    margin = top[0][1] - top[1][1] if len(top) >= 2 else 0.0
    buy_style = "見送り" if margin < 0.8 else "点数絞り"

    # Betting suggestion (very compact)
    bets = []
    if buy_style == "点数絞り" and len(picks) >= 3:
        bets.append(f"- 馬単1点: {picks[0][1].number}→{picks[1][1].number}")
        bets.append(f"- 3連単（最大5点）: {picks[0][1].number}→{picks[1][1].number},{picks[2][1].number}→{picks[1][1].number},{picks[2][1].number}")
    else:
        if len(picks) >= 2:
            bets.append(f"- ワイド1点: {picks[0][1].number}-{picks[1][1].number}")
        bets.append("- 条件が揃わなければ見送り優先")

    # Training notes for top 3
    tnotes = []
    for m, r, s, hill, course in picks[:3]:
        parts = []
        if hill and hill.time4f is not None:
            laps = _format_laps([hill.lap4, hill.lap3, hill.lap2, hill.lap1])
            parts.append(f"坂路4F {hill.time4f:.1f}（{hill.lap_type or '-'} / {laps}）")
        if course and (course.f5 or course.f4 or course.f1):
            f5 = f"{course.f5:.1f}" if course.f5 is not None else "-"
            f4 = f"{course.f4:.1f}" if course.f4 is not None else "-"
            f1 = f"{course.f1:.1f}" if course.f1 is not None else "-"
            parts.append(f"コース {course.direction} 5F {f5} / 4F {f4} / 1F {f1}（{course.lap_type or '-'}）")
        if not parts:
            parts.append("調教データ薄め（直前気配/馬場/オッズで補正）")
        tnotes.append(f"- {m}{r.number} {r.name}: " + " / ".join(parts))

    lines = []
    lines.append("")
    lines.append(block_header)
    lines.append(f"- 更新: {now}")
    lines.append("")
    lines.append("### 印（結論）")
    for m, r, s, _, _ in picks:
        odds = f"{r.odds:.1f}" if r.odds is not None else "?"
        lines.append(f"- {m} {r.number} {r.name}（オッズ:{odds} / スコア:{s:.1f}）")
    lines.append("")
    lines.append("### 調教評価（上位3頭の根拠）")
    lines.extend(tnotes)
    lines.append("")
    lines.append("### 馬券案（点数を絞る）")
    lines.extend(bets)
    lines.append("")
    lines.append("### 見送り条件")
    lines.append("- 直前で馬場/オッズが想定とズレて期待値が崩れる場合")
    lines.append("- 調教データが薄い馬が人気先行になりすぎる場合")
    lines.append("")
    lines.append("----")
    lines.append("")
    return "\n".join(lines)


def append_to_race_file(path: str, block: str, block_header: str) -> bool:
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    if block_header in text:
        return False
    if "# 追記" not in text:
        raise ValueError(f"追記セクションが見つかりません: {path}")
    # append at end (追記以降)
    if not text.endswith("\n"):
        text += "\n"
    text += block
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revised", action="store_true", help="訂正版ブロック（A1-B3を画像ルールで再判定）を追記する")
    args = ap.parse_args()

    block_header = "## GPT-5 追記（調教重視：訂正版）" if args.revised else "## GPT-5 追記（調教重視）"

    # Discover chokyo csv paths (avoid JP filename typing)
    csv_paths = glob.glob(os.path.join(RACES_ROOT, "chokyo_251221_*.csv"))
    if len(csv_paths) < 2:
        raise RuntimeError("chokyo_251221_*.csv が見つかりません")

    hill_csv = None
    course_csv = None
    for p in csv_paths:
        with open(p, "r", encoding="cp932", errors="replace", newline="") as f:
            header = next(csv.reader(f))
        if "Time1" in header and "Lap4" in header:
            hill_csv = p
        if "10F" in header and "Lap9" in header:
            course_csv = p
    if not hill_csv or not course_csv:
        raise RuntimeError("坂路CSV/コースCSVの判別に失敗しました")

    hill_by_horse = load_hill_works(hill_csv)
    course_by_horse = load_course_works(course_csv)

    # Race md paths
    tracks = ["中京", "阪神", "中山"]
    race_paths: List[str] = []
    for tr in tracks:
        race_paths.extend(glob.glob(os.path.join(RACES_ROOT, tr, "*.md")))

    races = [parse_race_md(p) for p in race_paths]

    # Sort in requested order: 中京1, 阪神1, 中山1, 中京2, 阪神2, 中山2, ...
    track_order = {"中京": 0, "阪神": 1, "中山": 2}
    races.sort(key=lambda r: (r.r_no, track_order.get(r.track, 9)))

    updated = 0
    skipped = 0
    for race in races:
        scored, _ = pick_marks(race, hill_by_horse, course_by_horse)
        block = build_append_block(race, scored, block_header=block_header)
        did = append_to_race_file(race.path, block, block_header=block_header)
        if did:
            updated += 1
            print(f"UPDATED {race.track}{race.r_no}R {race.race_id} -> {race.path}")
        else:
            skipped += 1
            print(f"SKIP (already appended) {race.track}{race.r_no}R {race.race_id}")
    print(f"done. updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()



import csv
import glob
import os
import re
import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"
RACE_DATE = "20251221"
KEIBA_CICD_ROOT = r"Z:\KEIBA-CICD"
RULEBOOK_FILENAME = "調教データ.md"

# ターミナル環境で日本語パスのファイルが0バイト扱いになるケースがあるため、
# その場合に備えてクイックリファレンス（調教師→最重要パターン）を内蔵しておく。
FALLBACK_QUICK_REFERENCE: Dict[str, str] = {
    "矢作芳人": "A2ラップ（2F各12秒台加速）",
    "友道康夫": "A1ラップ（終い1Fのみ12秒台）",
    "木村哲也": "前週坂路55秒以下+当週ウッド+ルメール",
    "堀宣行": "ウッド4F 53秒切り",
    "上村洋行": "前週土日坂路+当週ウッド終い11秒台",
    "高野友和": "坂路55秒以上+A1（地味な加速）",
    "鹿戸雄一": "前週土日坂路55秒以下+当週追い切り",
    "藤原英昭": "坂路11秒台ラップ（A3/B3）+前日追いなし",
    "寺島良": "前週土日坂路A1→当週ウッド+ダート戦",
    "吉村圭司": "栗東坂路A2ラップ（2F各12秒台加速）",
    "久保田貴士": "前日美浦坂路追いあり+田辺騎手",
    "森秀行": "A3ラップ（2F各11秒台加速）",
    "大竹正博": "前週土日坂路57秒以下+当週ウッド+芝戦",
    "辻野泰之": "加速ラップ+芝レース",
    "松下武士": "A2/A3ラップ（矢作パターン）+全体54秒以上",
    "牧浦充徳": "A2ラップ+B2ラップ（高回収率）",
    "菊沢隆徳": "美浦坂路加速ラップ（改修後）",
    "石橋守": "栗東坂路A2/A3ラップ（11秒台加速）",
    "竹内正洋": "美浦ウッド5F67秒以下+終い11秒台",
    "加藤士津八": "美浦坂路追い切り（改修後）",
    "野中賢二": "ダート戦+坂路加速ラップ",
    "嘉藤貴行": "前週土日坂路60秒以上→当週ウッド",
    "新谷功一": "坂路51秒以下+減速ラップ（B2/B3）",
    "福永祐一": "栗東坂路加速ラップ（A1/A2中心）",
}


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


@dataclass
class HillWork:
    date: str
    place: str
    trainer: str
    time4f: Optional[float]
    lap2: Optional[float]
    lap1: Optional[float]

    @property
    def lap_type(self) -> Optional[str]:
        return _lap_type_from_last2(self.lap2, self.lap1)


@dataclass
class CourseWork:
    date: str
    place: str
    trainer: str
    f5: Optional[float]
    f4: Optional[float]
    f1: Optional[float]
    lap2: Optional[float]
    lap1: Optional[float]

    @property
    def lap_type(self) -> Optional[str]:
        return _lap_type_from_last2(self.lap2, self.lap1)


@dataclass
class Runner:
    number: str
    name: str


@dataclass
class Race:
    track: str
    r_no: int
    surface: str
    distance: int
    path: str
    runners: List[Runner]


def parse_rulebook_quick_reference(md_text: str) -> Dict[str, str]:
    """
    Returns {trainer_full_name: pattern_text}
    from the '調教師別 最重要パターン一覧' table.
    """
    if "### 調教師別 最重要パターン一覧" not in md_text:
        return {}
    block = md_text.split("### 調教師別 最重要パターン一覧", 1)[1]
    # until next heading
    m_next = re.search(r"\n###\s+", block)
    if m_next:
        block = block[: m_next.start()]

    lines = [ln for ln in block.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        return {}

    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    def idx(col: str) -> Optional[int]:
        try:
            return header.index(col)
        except ValueError:
            return None

    i_tr = idx("調教師")
    i_pat = idx("最重要パターン")
    if i_tr is None or i_pat is None:
        return {}

    out: Dict[str, str] = {}
    for ln in lines[2:]:
        if ln.startswith("|:---"):
            continue
        cols = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cols) < max(i_tr, i_pat) + 1:
            continue
        tr = re.sub(r"\*\*", "", cols[i_tr]).strip()
        pat = re.sub(r"\*\*", "", cols[i_pat]).strip()
        if tr and pat:
            out[tr] = pat
    return out


def _read_text_utf8(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def discover_rulebook_path() -> Optional[str]:
    """
    Windows環境で日本語パスが直接開けないケースがあるため、
    ルートから実ファイルを探索して確実に取得する。
    """
    # First try the canonical location (fast path)
    canonical = os.path.join(KEIBA_CICD_ROOT, "調教データ", RULEBOOK_FILENAME)
    try:
        txt = _read_text_utf8(canonical)
        if "### 調教師別 最重要パターン一覧" in txt:
            return canonical
    except OSError:
        pass

    # Fallback: walk the repository and find the file by name + expected content
    for root, _, files in os.walk(KEIBA_CICD_ROOT):
        if RULEBOOK_FILENAME not in files:
            continue
        p = os.path.join(root, RULEBOOK_FILENAME)
        try:
            txt = _read_text_utf8(p)
        except OSError:
            continue
        if "### 調教師別 最重要パターン一覧" in txt:
            return p
    return None


def discover_chokyo_csvs() -> Tuple[str, str]:
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
    return hill_csv, course_csv


def load_hill_by_horse(csv_path: str) -> Dict[str, List[HillWork]]:
    by_horse: Dict[str, List[HillWork]] = {}
    with open(csv_path, "r", encoding="cp932", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            horse = _normalize_horse_name(row.get("馬名", ""))
            if not horse:
                continue
            w = HillWork(
                date=(row.get("年月日", "") or "").strip(),
                place=(row.get("場所", "") or "").strip(),
                trainer=(row.get("調教師", "") or "").strip(),
                time4f=_safe_float(row.get("Time1", "")),
                lap2=_safe_float(row.get("Lap2", "")),
                lap1=_safe_float(row.get("Lap1", "")),
            )
            by_horse.setdefault(horse, []).append(w)
    for k in list(by_horse.keys()):
        by_horse[k].sort(key=lambda x: x.date)
    return by_horse


def load_course_by_horse(csv_path: str) -> Dict[str, List[CourseWork]]:
    by_horse: Dict[str, List[CourseWork]] = {}
    with open(csv_path, "r", encoding="cp932", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            horse = _normalize_horse_name(row.get("馬名", ""))
            if not horse:
                continue
            w = CourseWork(
                date=(row.get("年月日", "") or "").strip(),
                place=(row.get("場所", "") or "").strip(),
                trainer=(row.get("調教師", "") or "").strip(),
                f5=_safe_float(row.get("5F", "")),
                f4=_safe_float(row.get("4F", "")),
                f1=_safe_float(row.get("1F", "")),
                lap2=_safe_float(row.get("Lap2", "")),
                lap1=_safe_float(row.get("Lap1", "")),
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

    # Parse runners
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
            if len(cols) < 3:
                continue
            no = cols[1]
            name_cell = cols[2]
            m_link = re.search(r"\[([^\]]+)\]\(", name_cell)
            name = m_link.group(1) if m_link else name_cell
            runners.append(Runner(number=no, name=_normalize_horse_name(name)))
    return Race(track=track, r_no=r_no, surface=surface, distance=distance, path=path, runners=runners)


def _has_prev_weekend(dates: List[str]) -> bool:
    # for 2025-12-21, prev weekend is 20251213/20251214
    return any(d in ("20251213", "20251214") for d in dates)


def _norm_date(d: str) -> str:
    return re.sub(r"\D", "", (d or "").strip())


def _prev_weekend_hill(hill_list: List[HillWork]) -> Optional[HillWork]:
    """
    Return the best (fastest time4f) hill work on prev weekend if exists.
    """
    cand = []
    for w in hill_list:
        dd = _norm_date(w.date)
        if dd in ("20251213", "20251214"):
            cand.append(w)
    if not cand:
        return None
    # Prefer smallest time4f when available, else latest
    cand.sort(key=lambda x: (x.time4f is None, x.time4f if x.time4f is not None else 999.0))
    return cand[0]


def evaluate_pattern_hit(
    pattern: str,
    race: Race,
    horse: str,
    hill_list: List[HillWork],
    course_list: List[CourseWork],
) -> Optional[str]:
    """
    Returns a short reason string if it matches, else None.
    Heuristic matching based on keywords in pattern.
    """
    hill = hill_list[-1] if hill_list else None
    course = course_list[-1] if course_list else None

    tokens = set(re.findall(r"(A1|A2|A3|B2|B3)", pattern))
    need_dirt = "ダート" in pattern
    need_turf = "芝" in pattern and "芝レース" in pattern

    if need_dirt and race.surface != "ダ":
        return None
    if need_turf and race.surface != "芝":
        return None

    # Check lap type match (either hill or course)
    if tokens:
        ok = False
        which = []
        if hill and hill.lap_type in tokens:
            ok = True
            which.append(f"坂路{hill.lap_type}")
        if course and course.lap_type in tokens:
            ok = True
            which.append(f"コース{course.lap_type}")
        if not ok:
            return None
    else:
        which = []

    # Time thresholds
    if "51秒台以下" in pattern:
        if not hill or hill.time4f is None or hill.time4f > 51.9:
            return None
        which.append(f"坂路4F{hill.time4f:.1f}")

    if "55秒以下" in pattern and "坂路" in pattern:
        # If pattern mentions "前週", check prev-weekend hill. Otherwise, check latest hill.
        if "前週" in pattern:
            pw = _prev_weekend_hill(hill_list)
            if not pw or pw.time4f is None or pw.time4f > 55.9:
                return None
            which.append(f"前週坂路4F{pw.time4f:.1f}")
        else:
            if not hill or hill.time4f is None or hill.time4f > 55.9:
                return None
            which.append(f"坂路4F{hill.time4f:.1f}")

    if "55秒以上" in pattern and "坂路" in pattern:
        if not hill or hill.time4f is None or hill.time4f < 55.0:
            return None
        which.append(f"坂路4F{hill.time4f:.1f}")

    if "57秒以下" in pattern and "坂路" in pattern:
        pw = _prev_weekend_hill(hill_list) if "前週" in pattern else (hill_list[-1] if hill_list else None)
        if not pw or pw.time4f is None or pw.time4f > 57.9:
            return None
        which.append(("前週" if "前週" in pattern else "") + f"坂路4F{pw.time4f:.1f}")

    if "60秒以上" in pattern and "坂路" in pattern:
        pw = _prev_weekend_hill(hill_list) if "前週" in pattern else (hill_list[-1] if hill_list else None)
        if not pw or pw.time4f is None or pw.time4f < 60.0:
            return None
        which.append(("前週" if "前週" in pattern else "") + f"坂路4F{pw.time4f:.1f}")

    if "ウッド4F 53秒切り" in pattern or "ウッド4F" in pattern and "53" in pattern:
        if not course or course.f4 is None or course.f4 > 53.9:
            return None
        which.append(f"ウッド4F{course.f4:.1f}")

    if "ウッド5F67秒以下" in pattern or "67秒以下" in pattern:
        if not course or course.f5 is None or course.f5 > 67.9:
            return None
        which.append(f"ウッド5F{course.f5:.1f}")

    if "当週ウッド" in pattern:
        if not course:
            return None
        which.append("当週ウッドあり")

    if "全体54秒以上" in pattern:
        if not hill or hill.time4f is None or hill.time4f < 54.0:
            return None
        which.append(f"坂路4F{hill.time4f:.1f}")

    if "終い11秒台" in pattern:
        ok = False
        if course and course.f1 is not None and course.f1 < 12.0:
            ok = True
            which.append(f"終い1F{course.f1:.1f}")
        if hill and hill.lap1 is not None and hill.lap1 < 12.0:
            ok = True
            which.append(f"終いLap1{hill.lap1:.1f}")
        if not ok:
            return None

    # Prev weekend / previous day checks (existence)
    dates = [w.date for w in (hill_list + course_list) if w.date]
    if "前週土日" in pattern:
        if not _has_prev_weekend(dates):
            return None
        which.append("前週土日あり")

    if "前日" in pattern:
        # For 12/21, previous day is 20251220
        if "20251220" not in dates:
            return None
        which.append("前日追いあり")

    # If nothing is checked but trainer is in rulebook, don't spam
    if not which:
        return None

    return " / ".join(which)


def build_block(
    race: Race,
    hits: List[Tuple[str, str, str, str]],
    block_header: str,
) -> str:
    """
    hits: [(horse_no, horse_name, trainer_full, reason)]
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []
    lines.append("")
    lines.append(block_header)
    lines.append(f"- 更新: {now}")
    lines.append("")
    lines.append("`調教データ.md` の「調教師別 最重要パターン」に該当した馬だけを抜粋します。")
    lines.append("")
    if not hits:
        lines.append("- 該当なし（このレースの出走馬は、登録済み“勝負パターン”調教師に該当しないか、条件不一致）")
    else:
        for no, name, tr, reason in hits:
            lines.append(f"- {no} {name}（調教師:{tr}）: パターン該当 → {reason}")
    lines.append("")
    lines.append("----")
    lines.append("")
    return "\n".join(lines)


def append_block(path: str, block: str, block_header: str) -> bool:
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    if block_header in text:
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--revised", action="store_true", help="訂正版ブロック（A1-B3を画像ルールで再判定）を追記する")
    ap.add_argument("--rev2", action="store_true", help="訂正版v2（ルールブック探索改善）を追記する")
    ap.add_argument("--rev3", action="store_true", help="訂正版v3（クイックリファレンス内蔵＋条件判定強化）を追記する")
    args = ap.parse_args()

    if args.rev3:
        block_header = "## GPT-5 追記（調教師ポイント該当：訂正版v3）"
    elif args.rev2:
        block_header = "## GPT-5 追記（調教師ポイント該当：訂正版v2）"
    else:
        block_header = "## GPT-5 追記（調教師ポイント該当：訂正版）" if args.revised else "## GPT-5 追記（調教師ポイント該当）"

    rulebook_path = discover_rulebook_path()
    if not rulebook_path:
        trainer_patterns = dict(FALLBACK_QUICK_REFERENCE)
        rulebook_note = "fallback_quick_reference"
    else:
        md_text = _read_text_utf8(rulebook_path)
        trainer_patterns = parse_rulebook_quick_reference(md_text)
        if not trainer_patterns:
            trainer_patterns = dict(FALLBACK_QUICK_REFERENCE)
            rulebook_note = "fallback_quick_reference"
        else:
            rulebook_note = "rulebook_file"

    print(f"rulebook_source={rulebook_note} rulebook_path={rulebook_path} patterns={len(trainer_patterns)}")

    hill_csv, course_csv = discover_chokyo_csvs()
    hill_by_horse = load_hill_by_horse(hill_csv)
    course_by_horse = load_course_by_horse(course_csv)

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
        hits: List[Tuple[str, str, str, str]] = []
        for runner in race.runners:
            hill_list = hill_by_horse.get(runner.name, [])
            course_list = course_by_horse.get(runner.name, [])
            # trainer in csv is short name, but rulebook uses full name
            trainer_short = ""
            if hill_list:
                trainer_short = hill_list[-1].trainer
            if course_list and not trainer_short:
                trainer_short = course_list[-1].trainer
            if not trainer_short:
                continue

            # Try exact match first, then "contains" match.
            matched_trainer = None
            for full in trainer_patterns.keys():
                if full == trainer_short:
                    matched_trainer = full
                    break
            if not matched_trainer:
                for full in trainer_patterns.keys():
                    if trainer_short and trainer_short in full:
                        matched_trainer = full
                        break
            if not matched_trainer:
                continue

            pat = trainer_patterns[matched_trainer]
            reason = evaluate_pattern_hit(pat, race, runner.name, hill_list, course_list)
            if reason:
                hits.append((runner.number, runner.name, matched_trainer, reason))

        block = build_block(race, hits, block_header=block_header)
        did = append_block(race.path, block, block_header=block_header)
        if did:
            updated += 1
        else:
            skipped += 1

    print(f"done. updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()



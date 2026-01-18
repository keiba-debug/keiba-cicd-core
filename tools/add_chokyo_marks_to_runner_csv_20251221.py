import csv
import glob
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"


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
    name = "".join(name.split())
    return name


def _lap_type_from_last2(lap2: Optional[float], lap1: Optional[float]) -> Optional[str]:
    if lap1 is None or lap2 is None:
        return None
    # 画像の定義に合わせる:
    # A1: 終い1Fのみ12秒台の加速（例: ...-13.1-12.5）
    # A2: 終い2F各12秒台の加速（例: ...-12.5-12.1）
    # A3: 終い1Fが11秒台の加速（※2Fが11秒台も含む / 例: ...-12.5-11.9）
    # B1: 2Fのみ12秒台の減速（例: ...-12.8-13.1）
    # B2: 終い2F各12秒台の減速（例: ...-12.2-12.6）
    # B3: 2Fが11秒台の減速（※1Fが11秒台も含む / 例: ...-11.8-12.7）
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
    lap2: Optional[float]
    lap1: Optional[float]

    @property
    def mark(self) -> Optional[str]:
        return _lap_type_from_last2(self.lap2, self.lap1)


@dataclass
class CourseWork:
    date: str
    lap2: Optional[float]
    lap1: Optional[float]

    @property
    def mark(self) -> Optional[str]:
        return _lap_type_from_last2(self.lap2, self.lap1)


def discover_inputs() -> Tuple[str, str, str]:
    """
    Returns (runner_csv, hill_csv, course_csv)
    """
    csvs = glob.glob(os.path.join(RACES_ROOT, "*.csv"))
    if not csvs:
        raise RuntimeError("RACES_ROOT 配下にCSVが見つかりません")

    runner = [p for p in csvs if "chokyo_251221_" not in os.path.basename(p)]
    if not runner:
        raise RuntimeError("出走馬_調教印.csv 相当のCSVが見つかりません")
    runner_csv = runner[0]

    hill_csv = None
    course_csv = None
    for p in csvs:
        base = os.path.basename(p)
        if "chokyo_251221_" not in base:
            continue
        with open(p, "r", encoding="cp932", errors="replace", newline="") as f:
            header = next(csv.reader(f))
        if "Time1" in header and "Lap4" in header:
            hill_csv = p
        if "10F" in header and "Lap9" in header:
            course_csv = p

    if not hill_csv or not course_csv:
        raise RuntimeError("坂路/コースのchokyo CSVを特定できませんでした")

    return runner_csv, hill_csv, course_csv


def load_hill_marks(path: str) -> Dict[str, HillWork]:
    by_horse: Dict[str, HillWork] = {}
    with open(path, "r", encoding="cp932", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            horse = _normalize_horse_name(row.get("馬名", ""))
            if not horse:
                continue
            date = (row.get("年月日", "") or "").strip()
            w = HillWork(
                date=date,
                lap2=_safe_float(row.get("Lap2", "")),
                lap1=_safe_float(row.get("Lap1", "")),
            )
            prev = by_horse.get(horse)
            if prev is None or (date and date >= prev.date):
                by_horse[horse] = w
    return by_horse


def load_course_marks(path: str) -> Dict[str, CourseWork]:
    by_horse: Dict[str, CourseWork] = {}
    with open(path, "r", encoding="cp932", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            horse = _normalize_horse_name(row.get("馬名", ""))
            if not horse:
                continue
            date = (row.get("年月日", "") or "").strip()
            w = CourseWork(
                date=date,
                lap2=_safe_float(row.get("Lap2", "")),
                lap1=_safe_float(row.get("Lap1", "")),
            )
            prev = by_horse.get(horse)
            if prev is None or (date and date >= prev.date):
                by_horse[horse] = w
    return by_horse


def read_runner_names(path: str) -> List[str]:
    """
    This file is currently a 1-column "name per line" list (no commas).
    """
    with open(path, "r", encoding="cp932", errors="replace") as f:
        lines = [ln.strip() for ln in f.read().splitlines()]
    return [ln for ln in lines if ln]


def read_runner_rows(path: str) -> List[str]:
    """
    Support both formats:
    - old: one horse name per line (no commas)
    - new: csv with header '馬名,...'
    Returns a list of horse names.
    """
    # Prefer stable source list if backup exists (the backup is created from the original 1-col list).
    bak = path + ".bak"
    if os.path.exists(bak):
        with open(bak, "r", encoding="cp932", errors="replace") as f:
            lines = [ln.strip() for ln in f.read().splitlines()]
        return [ln for ln in lines if ln]

    with open(path, "r", encoding="cp932", errors="replace") as f:
        head = f.readline()
        rest = f.read()
    # If header contains comma, treat as CSV
    if "," in head:
        # parse full content as csv
        content = head + rest
        rows = []
        for row in csv.DictReader(content.splitlines()):
            name = (row.get("馬名") or "").strip()
            if name:
                # Guard against previously malformed rows where the "name" itself contains commas
                if "," in name:
                    continue
                rows.append(name)
        return rows
    # otherwise, old format
    lines = [head.strip()] + [ln.strip() for ln in rest.splitlines()]
    return [ln for ln in lines if ln]


def write_augmented_runner_csv(path: str, rows: List[Tuple[str, str, str, str]]) -> None:
    # backup
    bak = path + ".bak"
    if not os.path.exists(bak):
        os.replace(path, bak)
    else:
        # overwrite original (keep existing bak)
        os.remove(path)

    with open(path, "w", encoding="cp932", newline="") as f:
        w = csv.writer(f)
        w.writerow(["馬名", "坂路_印", "コース_印", "最終追い切り_印"])
        for r in rows:
            w.writerow(list(r))


def main() -> None:
    runner_csv, hill_csv, course_csv = discover_inputs()
    hill = load_hill_marks(hill_csv)
    course = load_course_marks(course_csv)

    names = read_runner_rows(runner_csv)
    out_rows: List[Tuple[str, str, str, str]] = []
    for name in names:
        key = _normalize_horse_name(name)
        h = hill.get(key)
        c = course.get(key)
        h_mark = h.mark if h and h.mark else ""
        c_mark = c.mark if c and c.mark else ""
        final = h_mark or c_mark or ""
        out_rows.append((name, h_mark, c_mark, final))

    write_augmented_runner_csv(runner_csv, out_rows)
    print(f"done. updated {runner_csv} (backup: {runner_csv}.bak)")


if __name__ == "__main__":
    main()



import glob
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"
OUT_PATH = r"Z:\KEIBA-CICD\data2\races\2025\12\21\temp\trainer_pattern_hits_v3_summary_20251221.md"
TARGET_BLOCK = "## GPT-5 追記（調教師ポイント該当：訂正版v3）"


@dataclass
class RaceKey:
    track: str
    r_no: int
    race_id: str
    path: str


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _parse_race_key(text: str, path: str) -> RaceKey:
    m = re.search(r"^#\s*(中京|阪神|中山)(\d+)R", text, re.M)
    if not m:
        raise ValueError(f"Race title not found: {path}")
    track = m.group(1)
    r_no = int(m.group(2))
    race_id = os.path.splitext(os.path.basename(path))[0]
    return RaceKey(track=track, r_no=r_no, race_id=race_id, path=path)


def _extract_v3_hits(text: str) -> List[str]:
    """
    Returns lines like:
      "9 ララマセラシオン（調教師:大竹正博）: パターン該当 → ..."
    """
    if TARGET_BLOCK not in text:
        return []
    after = text.split(TARGET_BLOCK, 1)[1]
    # stop at next GPT block header
    m_stop = re.search(r"\n## GPT-5 追記（", after)
    if m_stop:
        after = after[: m_stop.start()]
    hits: List[str] = []
    for ln in after.splitlines():
        ln = ln.strip()
        if not ln.startswith("- "):
            continue
        if ln.startswith("- 更新:"):
            continue
        if "パターン該当" not in ln:
            continue
        hits.append(ln[2:].strip())
    return hits


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def main() -> None:
    md_paths = []
    for tr in ("中京", "阪神", "中山"):
        md_paths.extend(glob.glob(os.path.join(RACES_ROOT, tr, "*.md")))

    races: List[Tuple[RaceKey, List[str]]] = []
    for p in md_paths:
        text = _read_text(p)
        key = _parse_race_key(text, p)
        hits = _extract_v3_hits(text)
        if hits:
            races.append((key, hits))

    track_order = {"中京": 0, "阪神": 1, "中山": 2}
    races.sort(key=lambda x: (x[0].r_no, track_order.get(x[0].track, 9)))

    lines: List[str] = []
    lines.append("# 12/21（3場36R）調教師ポイント該当（訂正版v3）集約")
    lines.append("")
    lines.append(f"- 対象: `{RACES_ROOT}` の各レースMD")
    lines.append(f"- 抽出ブロック: `{TARGET_BLOCK}`")
    lines.append(f"- 該当レース数: **{len(races)}**")
    lines.append("")
    lines.append("----")
    lines.append("")

    for key, hits in races:
        lines.append(f"## {key.track}{key.r_no}R（{key.race_id}）")
        lines.append(f"- ファイル: `{key.path}`")
        lines.append("")
        lines.append("### 該当馬")
        for h in hits:
            lines.append(f"- {h}")
        lines.append("")
        lines.append("----")
        lines.append("")

    _ensure_parent_dir(OUT_PATH)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print(f"done. wrote {OUT_PATH} races={len(races)}")


if __name__ == "__main__":
    main()



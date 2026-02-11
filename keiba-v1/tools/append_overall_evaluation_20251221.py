import glob
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"


@dataclass
class Pick:
    no: str
    name: str
    score: Optional[float]


@dataclass
class RaceMeta:
    track: str
    r_no: int
    path: str


def _parse_race_meta(text: str, path: str) -> RaceMeta:
    m = re.search(r"^#\s*(中京|阪神|中山)(\d+)R", text, re.M)
    if not m:
        raise ValueError(f"Race title not found: {path}")
    return RaceMeta(track=m.group(1), r_no=int(m.group(2)), path=path)


def _parse_picks(block_text: str, label: str) -> List[Pick]:
    """
    label:
      - "スコア" for training block
      - "適性v2" for suitability v2 block
    """
    picks: List[Pick] = []
    for ln in block_text.splitlines():
        ln = ln.strip()
        if not ln.startswith("- "):
            continue
        if ln.startswith("- 更新:"):
            continue
        # Example:
        # - ◎ 4 ブラックコーラル（オッズ:1.8 / スコア:17.2）
        # - ◎ 4 ブラックコーラル（オッズ:1.8 / 適性v2:11.8）: ...
        m = re.search(r"-\s*[◎○▲△]?\s*(\d+)\s+([^\s（]+).*?"+re.escape(label)+r":\s*([0-9]+(?:\.[0-9]+)?)", ln)
        if not m:
            # allow missing score (rare)
            m2 = re.search(r"-\s*[◎○▲△]?\s*(\d+)\s+([^\s（]+)", ln)
            if m2:
                picks.append(Pick(no=m2.group(1), name=m2.group(2), score=None))
            continue
        picks.append(Pick(no=m.group(1), name=m.group(2), score=float(m.group(3))))
    return picks[:5]


def _extract_mark_list(text: str, block_header: str, section_header: str) -> str:
    """
    Return the markdown list text under a specific section inside a block.
    Example:
      block_header="## GPT-5 追記（調教重視）"
      section_header="### 印（結論）"
    """
    if block_header not in text:
        return ""
    after = text.split(block_header, 1)[1]
    m_stop = re.search(r"\n## GPT-5 追記（", after)
    if m_stop:
        after = after[: m_stop.start()]
    if section_header not in after:
        return ""
    sec = after.split(section_header, 1)[1]
    m_next = re.search(r"\n###\s+", sec)
    if m_next:
        sec = sec[: m_next.start()]
    lines = []
    for ln in sec.splitlines():
        ln = ln.strip()
        if ln.startswith("- ") and not ln.startswith("- 更新:"):
            lines.append(ln)
    return "\n".join(lines)


def _extract_section(text: str, header: str) -> str:
    if header not in text:
        return ""
    after = text.split(header, 1)[1]
    # stop at next "## GPT-5 追記（" or EOF
    m_stop = re.search(r"\n## GPT-5 追記（", after)
    if m_stop:
        after = after[: m_stop.start()]
    return after.strip()


def _trainer_hits(text: str) -> Tuple[bool, List[str]]:
    """
    Returns (has_any, lines)
    """
    sec = _extract_section(text, "## GPT-5 追記（調教師ポイント該当）")
    if not sec:
        return False, []
    lines = []
    for ln in sec.splitlines():
        ln = ln.strip()
        if not ln.startswith("- "):
            continue
        if ln.startswith("- 更新:"):
            continue
        if "該当なし" in ln:
            continue
        if ln.startswith("- `"):
            continue
        lines.append(ln[2:])
    return len(lines) > 0, lines[:3]


def _agreement(p1: List[Pick], p2: List[Pick]) -> Tuple[int, bool]:
    """
    Returns: (intersection count among top3, top1 same?)
    """
    top1_same = False
    if p1 and p2 and p1[0].no == p2[0].no:
        top1_same = True
    set1 = {p.no for p in p1[:3]}
    set2 = {p.no for p in p2[:3]}
    return len(set1 & set2), top1_same


def _margin(picks: List[Pick]) -> Optional[float]:
    if len(picks) < 2:
        return None
    if picks[0].score is None or picks[1].score is None:
        return None
    return picks[0].score - picks[1].score


def _recommendation(training: List[Pick], suit_v2: List[Pick], trainer_hit_any: bool) -> Tuple[str, str, List[str]]:
    """
    Returns (grade, decision, reasons)
    grade: S/A/B/C/見送り
    decision: 買う/見送り
    """
    reasons: List[str] = []

    inter, top1_same = _agreement(training, suit_v2)
    m_tr = _margin(training)
    m_su = _margin(suit_v2)

    if top1_same:
        reasons.append("調教重視と適性v2で本命一致")
    if inter >= 2:
        reasons.append("上位3頭の重なりが大きい")
    if m_tr is not None:
        reasons.append(f"調教スコア差（1-2位）={m_tr:.1f}")
    if m_su is not None:
        reasons.append(f"適性v2差（1-2位）={m_su:.1f}")
    if trainer_hit_any:
        reasons.append("調教師パターン該当馬あり（加点材料）")

    # Grade logic (simple + conservative)
    if top1_same and inter >= 2 and (m_tr is None or m_tr >= 1.0):
        grade = "S" if trainer_hit_any else "A"
        decision = "買う"
    elif inter >= 2 and (m_tr is None or m_tr >= 0.6):
        grade = "A"
        decision = "買う"
    elif inter >= 1:
        grade = "B"
        decision = "買う（点数は絞る）"
    else:
        grade = "C"
        decision = "見送り寄り"

    # Hard skip condition if both margins tiny and no agreement
    if not top1_same and inter == 0 and (m_tr is not None and m_tr < 0.5):
        grade = "見送り"
        decision = "見送り"
        reasons.insert(0, "上位評価が割れており決め手不足")

    return grade, decision, reasons[:4]


def _format_picks(title: str, picks: List[Pick]) -> List[str]:
    lines = [f"**{title}**:"]
    if not picks:
        return [f"**{title}**: -"]
    parts = []
    for p in picks[:3]:
        if p.score is None:
            parts.append(f"{p.no} {p.name}")
        else:
            parts.append(f"{p.no} {p.name}（{p.score:.1f}）")
    lines.append("- " + " / ".join(parts))
    return lines


def build_block(meta: RaceMeta, text: str, is_v2: bool) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tr_mark_list = _extract_mark_list(text, "## GPT-5 追記（調教重視）", "### 印（結論）")
    su_mark_list = _extract_mark_list(text, "## GPT-5 追記（適性強化：C→B→A）", "### 印（適性を加味した再ランク）")

    training = _parse_picks(tr_mark_list, "スコア") if tr_mark_list else []
    suit_v2 = _parse_picks(su_mark_list, "適性v2") if su_mark_list else []
    trainer_any, trainer_lines = _trainer_hits(text)

    grade, decision, reasons = _recommendation(training, suit_v2, trainer_any)

    lines: List[str] = []
    lines.append("")
    lines.append("## GPT-5 追記（総合評価：修正版）" if is_v2 else "## GPT-5 追記（総合評価）")
    lines.append(f"- 更新: {now}")
    lines.append("")
    lines.append(f"- **推奨度**: {grade}")
    lines.append(f"- **結論**: {decision}")
    lines.append("")
    lines.extend(_format_picks("調教重視（上位）", training))
    lines.extend(_format_picks("適性v2（上位）", suit_v2))
    if trainer_any:
        lines.append("")
        lines.append("**調教師ポイント**:")
        for t in trainer_lines:
            lines.append(f"- {t}")
    lines.append("")
    lines.append("**総合根拠（短く）**:")
    if reasons:
        for r in reasons:
            lines.append(f"- {r}")
    else:
        lines.append("- 根拠抽出が不足（追記ブロック形式差異の可能性）。既存追記を優先してください。")
    lines.append("")
    lines.append("----")
    lines.append("")
    return "\n".join(lines)


def append_block(path: str) -> bool:
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    # v1 is already added in this workspace; add v2 without editing v1.
    if "## GPT-5 追記（総合評価：修正版）" in text:
        return False
    if "# 追記" not in text:
        raise ValueError(f"追記セクションが見つかりません: {path}")
    meta = _parse_race_meta(text, path)
    block = build_block(meta, text, is_v2=True)
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

    # sort: 中京1→阪神1→中山1→... (same as before)
    def sort_key(p: str) -> Tuple[int, int]:
        text = open(p, "r", encoding="utf-8", errors="replace").read()
        meta = _parse_race_meta(text, p)
        order = {"中京": 0, "阪神": 1, "中山": 2}.get(meta.track, 9)
        return meta.r_no, order

    race_paths.sort(key=sort_key)

    updated = 0
    skipped = 0
    for p in race_paths:
        if append_block(p):
            updated += 1
        else:
            skipped += 1
    print(f"done. updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()



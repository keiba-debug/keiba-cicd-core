import glob
import os
import re
import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple


RACES_ROOT = r"Z:\KEIBA-CICD\data2\races\2025\12\21"


@dataclass
class RaceMeta:
    track: str
    r_no: int
    surface: str  # 芝/ダ/障
    distance: int
    path: str


def _parse_race_meta(text: str, path: str) -> RaceMeta:
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
    return RaceMeta(track=track, r_no=r_no, surface=surface, distance=distance, path=path)


def _extract_training_top3(text: str, prefer_revised: bool) -> List[str]:
    """
    Pull the 3 lines under:
      ### 調教評価（上位3頭の根拠）
    within the existing "GPT-5 追記（調教重視）" block.
    """
    headers = ["## GPT-5 追記（調教重視：訂正版）", "## GPT-5 追記（調教重視）"] if prefer_revised else ["## GPT-5 追記（調教重視）"]
    chosen = None
    for h in headers:
        if h in text:
            chosen = h
            break
    if not chosen:
        return []
    # take from first training block to the first separator after it
    after = text.split(chosen, 1)[1]
    # Stop at the next "----" or next GPT section header (best effort)
    m_stop = re.search(r"\n----\n|\n## GPT-5 追記（適性", after)
    if m_stop:
        after = after[: m_stop.start()]

    m = re.search(r"### 調教評価（上位3頭の根拠）\n((?:- .*\n){1,6})", after)
    if not m:
        return []
    lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip().startswith("- ")]
    return lines[:3]


def _axes_text(meta: RaceMeta) -> List[str]:
    """
    Build easy-to-understand axes depending on surface/distance.
    This is intentionally simple and consistent across races.
    """
    s = meta.surface
    d = meta.distance

    # Distance buckets (rough)
    if s == "ダ":
        if d >= 2100:
            return [
                "- **全体（5F/4F）**: 長丁場は「終いだけ」より **中盤から負荷を掛けた全体時計** を重視（持続力の裏付け）",
                "- **終い（1F）**: 12秒前半までで我慢できる馬は止まりにくい。終いだけ派手でも全体が緩いと評価を上げにくい",
                "- **直前週の時計**: 最終週に出せている＝仕上げが間に合っている可能性が高い",
            ]
        if d >= 1700:
            return [
                "- **坂路4F（またはコース5F）**: 中距離は“土台の時計”を優先（止まりにくさ）",
                "- **ラップの質（A系）**: 余力を残して加速できる形（A2/A3寄り）はプラス",
                "- **減速が強い（B系）**: 追ってから失速が目立つ内容は割引",
            ]
        # sprint dirt
        return [
            "- **坂路4F**: 短距離は“スピードの絶対値”が出やすいのでまずここを見る",
            "- **終い（Lap1）**: 追われて伸びる/止まらないか（加速 or 減速の度合い）",
            "- **データ薄い馬**: 直前の馬場・オッズで過信しない（見送り条件を厳しめに）",
        ]

    if s == "芝":
        if d >= 2000:
            return [
                "- **全体（5F/4F）**: 中長距離は“持続力”が効くので全体時計の良さを重視",
                "- **終い（1F）**: 11秒台〜12秒前半なら最後にもう一段踏める",
                "- **ラップの形**: 直線で加速できる形（A系）をプラス評価",
            ]
        if d >= 1600:
            return [
                "- **坂路/コースのバランス**: マイルは“全体＋終い”の両立が理想",
                "- **終い（1F）**: 11秒台が出ていれば仕上がりの目安になりやすい",
                "- **減速が強い場合**: 直線の坂や最後の伸びに不安が出やすいので注意",
            ]
        # sprint turf
        return [
            "- **坂路4F**: スプリントは坂路のスピードが結果に直結しやすい",
            "- **終い（Lap1）**: 追っても止まらない（加速 or 減速が小さい）内容が良い",
            "- **人気先行注意**: 調教が平凡で人気なら消しの材料にしやすい",
        ]

    return [
        "- **障害は個別性が強い**ため、調教“だけ”で断定せず、近走内容と合わせて評価",
    ]


def _build_block(meta: RaceMeta, top3_lines: List[str], block_header: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: List[str] = []
    lines.append("")
    lines.append(block_header)
    lines.append(f"- 更新: {now}")
    lines.append("")
    lines.append("この追記は、上の「調教重視」結論が **なぜ買いに繋がるのか** を、判断軸→当てはめで短く整理したものです。")
    lines.append("")
    lines.append(f"### 判断軸（{meta.track}{meta.r_no}R / {meta.surface}{meta.distance}）")
    lines.extend(_axes_text(meta))
    lines.append("")
    lines.append("### 推奨馬ごとの噛み合い（上位3頭）")
    if not top3_lines:
        lines.append("- 調教根拠の抽出に失敗（形式差異）。上の調教ブロックの内容を優先してください。")
    else:
        # Convert "- ◎11 ..." lines into short bullets
        for ln in top3_lines:
            # keep original line but prepend a rationale phrase
            lines.append(f"- {ln[2:]} → 全体と終いのバランスを評価（軸に近い）")
    lines.append("")
    lines.append("### 見送りの考え方（共通）")
    lines.append("- 人気先行で調教が平凡（または減速が強い）なら、点数を絞る代わりに見送りを優先")
    lines.append("- 馬場が想定とズレた場合は、スピード型/持続型の評価が入れ替わるので直前で再判断")
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
    ap.add_argument("--revised", action="store_true", help="訂正版（調教重視：訂正版）に紐づく推奨理由を追記する")
    args = ap.parse_args()

    block_header = "## GPT-5 追記（調教分析：推奨理由の補足：訂正版）" if args.revised else "## GPT-5 追記（調教分析：推奨理由の補足）"

    tracks = ["中京", "阪神", "中山"]
    race_paths: List[str] = []
    for tr in tracks:
        race_paths.extend(glob.glob(os.path.join(RACES_ROOT, tr, "*.md")))

    races: List[Tuple[RaceMeta, str]] = []
    for p in race_paths:
        text = open(p, "r", encoding="utf-8", errors="replace").read()
        meta = _parse_race_meta(text, p)
        races.append((meta, text))

    track_order = {"中京": 0, "阪神": 1, "中山": 2}
    races.sort(key=lambda x: (x[0].r_no, track_order.get(x[0].track, 9)))

    updated = 0
    skipped = 0
    for meta, text in races:
        top3 = _extract_training_top3(text, prefer_revised=args.revised)
        block = _build_block(meta, top3, block_header=block_header)
        did = append_block(meta.path, block, block_header=block_header)
        if did:
            updated += 1
        else:
            skipped += 1

    print(f"done. updated={updated} skipped={skipped}")


if __name__ == "__main__":
    main()



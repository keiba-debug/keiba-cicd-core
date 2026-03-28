# ソラ — v3 手の修正プロンプト

> 「...え？」版が表情・服装・小道具すべて正解。
> 手が3本になっている問題だけを修正する。

---

## 方法1: 全体再生成（同じ構図を狙う）

```
manga-influenced anime, sketchy pen linework, flat color, low saturation, muted tones, white background, upper body close-up shot, slightly from above angle

1girl, solo, age 26, slim build
black messy chin-length bob hair, unkempt, some strands sticking up
wearing a wrinkled dusty blue-gray button-up shirt (open, untucked, sleeves rolled up unevenly) over a plain white t-shirt
old scratched compact binoculars hanging from a worn fabric strap around her neck
faded jeans

HANDS — EXACTLY TWO HANDS, ANATOMICALLY CORRECT:
- RIGHT hand: holding a folded racing form (newspaper-style sheet covered in red circles, blue arrows, green underlines — messy, impulsive pen marks). the hand grips the paper loosely, fingers visible
- LEFT hand: raised to her chin/mouth area, fingers curled near her lips in a worried gesture — she is touching her own face out of nervousness
- IMPORTANT: only TWO hands total in the image. no extra fingers, no extra hands

EXPRESSION — THE MOST IMPORTANT ELEMENT:
- eyes wide, looking at the racing form with genuine surprise and disbelief
- mouth slightly open — a small "o" shape — the face of someone who just realized her circled horse actually won
- a single manga-style sweat drop near her temple (optional)
- eyebrows raised, not furrowed — this is surprise, not worry
- she looks like she doesn't trust what she's seeing
- the Japanese text "…え？" floating near her head (optional — can be added in post)

THE RACING FORM:
- folded newspaper-style with visible grid structure
- covered in colorful pen marks: red X marks, red circles, blue crossing lines, green underlines
- the marks are chaotic, overlapping, impulsive
- these colored marks are the most vivid elements in the image

ART STYLE:
- sketchy imperfect pen linework with visible line weight variation
- flat coloring, almost no shading, watercolor-wash texture in some areas
- very low saturation everywhere EXCEPT the pen marks on the racing form
- manga-influenced proportions — head slightly oversized, simplified features
- minimal facial detail — emotion from eyebrow angle and mouth shape
- plain white background, no environment
- looks like a character sketch from a manga artist's notebook

DO NOT:
- draw more than 2 hands
- draw extra fingers
- make her look confident or cool
- make the shirt look neat or new
- use bright saturated colors except on the racing form pen marks
```

---

## 方法2: インペイント用（手の周辺だけ修正する場合）

> ツールがインペイント対応の場合、胸元〜手の領域をマスクして以下で再生成

```
INPAINT REGION: chest and hands area

anatomically correct two hands:
- left hand raised to mouth/chin, fingers curled near lips in nervous gesture, gripping the binoculars strap
- right hand holding a folded newspaper racing form at chest level
- exactly 5 fingers on each hand
- the binoculars hang naturally from the neck strap between the two hands
- dusty blue-gray wrinkled shirt visible, white t-shirt underneath

maintain the same sketchy pen linework style, flat color, low saturation
```

---

## 方法3: ネガティブプロンプト追加（再生成時）

> 現在のプロンプトにネガティブプロンプトを追加

```
Negative prompt: extra hands, extra fingers, three hands, mutated hands, deformed hands, bad anatomy, extra limbs, fused fingers, too many fingers, malformed hands
```

---

## 備考

この画像で確定している要素（再生成しても絶対維持すべきもの）：

1. **表情**：「...え？」の驚きと信じられなさ。目が大きく開いて口が小さく開いている
2. **シャツ**：くすんだ青灰。よれている。MCの水色シャツと同系統だが「くたびれた版」
3. **双眼鏡**：古い、使い込んだ質感。首から下げている
4. **出馬表**：色ペン（赤・青・緑）のぐちゃぐちゃな印。これが画面で一番色がある
5. **髪**：黒の無造作ボブ。手入れされていない
6. **全体のトーン**：低彩度、スケッチ線、白背景

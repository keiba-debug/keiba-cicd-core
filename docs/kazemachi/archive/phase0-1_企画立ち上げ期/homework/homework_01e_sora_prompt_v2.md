# ソラ（直感派）— 追加プロンプト v2

> 前回の成功画像（双眼鏡+スマホ+汚れたジャケット）をベースに、
> 「出馬表」案と表情修正案を統合。

---

## A. メインプロンプト（出馬表版・ベース画像）

```
manga-influenced anime, sketchy pen linework, flat color, low saturation, muted tones, white background, upper body shot

1girl, solo, age 26, slim build, relaxed but alert posture
dark brown (almost black) messy shoulder-length hair, slightly wavy ends, one side tucked behind ear
ONE small colorful holographic hair clip on the right side — this and the colored pen marks on the paper are the ONLY vivid colors in the image

FACE — CRITICAL:
- expression is "quiet confidence with a crack of vulnerability underneath"
- mouth: closed, or barely parted — one corner of the lips VERY slightly raised (not a full smile — a private "hmm, I knew it" expression)
- eyes: slightly narrowed, focused but not aggressive — she is reading something (the race card) but her mind is somewhere else. there is a subtle softness in the eyes that suggests she's not 100% sure, just 90% sure
- cheek blush: 2-3 short sketch lines on ONE cheek only (asymmetric, minimal)
- overall: NOT the face of someone who's certain. the face of someone who FEELS certain but knows that feeling has betrayed her before

CLOTHING:
- oversized vintage track jacket — muted navy and off-white, faded and worn. visible dirt marks near the hem and one elbow. sleeves slightly too long, cuffs pushed up to reveal wrists. the jacket looks like it's been to dozens of racetracks
- plain white t-shirt underneath
- faded jeans (casual, not stylish — functional)
- compact binoculars hanging from a strap around her neck (for watching horses at the paddock)

POSE:
- standing, weight shifted to one leg, slight lean
- RIGHT hand holds a folded racing form (出馬表 / horse racing program) — the paper is covered in COLORFUL pen marks: red circles, blue arrows, green underlines, some crossed out, some circled twice. the marks look impulsive and messy, NOT organized — this is intuition externalized on paper
- LEFT hand in jacket pocket, or loosely at her side
- her gaze is directed at the racing form BUT her eyes seem to be looking THROUGH it — as if she's seeing something beyond the paper

THE RACING FORM IS KEY:
- it should be a folded newspaper-style sheet, clearly marked up
- the pen colors (red, blue, green) should be the most vivid elements in the entire image
- the marks should look fast, instinctive — circles that aren't quite round, arrows that overshoot, underlines that are crooked
- some marks overlap or contradict each other (circled AND crossed out)
- this visual chaos contrasts with Narumi's clean spreadsheet

ART STYLE — MATCH MC REFERENCE:
- linework: sketchy, hand-drawn pen strokes with visible imperfections. line weight varies. NOT clean digital lines
- proportions: manga-influenced — head slightly oversized, features simplified (NOT realistic proportions)
- coloring: flat fill, almost no shading. very low saturation EXCEPT the hair clip and the pen marks on the racing form
- facial detail: minimal — emotion conveyed through few lines, not detailed rendering
- background: plain white or very light warm gray, no environment
- overall impression: "a character page from a slice-of-life manga tankoubon"

DO NOT:
- make her look directly at the camera
- open her mouth wide
- use large/sparkly shounen-manga eyes
- make the jacket look new or clean
- make the pen marks on the racing form look neat or organized
- add dramatic lighting or action poses
```

---

## B. バリエーション：見上げ版（パドック帰り）

```
（Aのプロンプトに以下を差し替え）

POSE:
- standing, weight shifted to one leg
- RIGHT hand holds a folded racing form at her side — she's done marking it
- LEFT hand adjusting binoculars around her neck, or pushing hair behind her ear
- her gaze is directed UPWARD and slightly to the side — she's looking at something in the distance (a horse? the sky? a memory?)
- expression: the "vulnerability" is more visible in this version. she looks like she's waiting for confirmation of something she already feels

（この版は「パドックから戻ってきたソラ」。出馬表はもう書き終わっている。
あとは結果を待つだけ。その待っている瞬間の不安と期待が混ざった顔。）
```

---

## C. バリエーション：ナルミとの対比用

```
（Aのプロンプトに以下を差し替え）

POSE:
- sitting in a simple chair, leaning back, one leg crossed over the other
- the racing form is spread open on her lap — visible colorful marks
- one hand rests on the racing form, a colored pen (red) loosely held between fingers
- the other hand is near her chin, touching her lower lip — a thinking gesture
- she is looking at the racing form with focus
- binoculars on the table beside her

（ナルミがPCの前に座っている構図と対になる。
同じ「データを見ている」でも、ナルミはスプレッドシート、ソラは色ペンだらけの出馬表。
並べた時に「同じ問いに全く違うアプローチで向き合っている」が一目でわかる。）
```

---

## 設計メモ

### なぜ出馬表か

| 比較 | スマホ | 出馬表 |
|---|---|---|
| 情報の隠し方 | 画面を見せない（物理的に隠す） | 見せているが意味がわからない（意味を隠す） |
| 視覚的インパクト | 低（スマホは記号として弱い） | 高（色ペンの混沌が目を引く） |
| 直感の可視化 | 間接的（撮った写真＝記録） | 直接的（殴り書き＝思考の痕跡） |
| 他キャラとの差別化 | △（誰でもスマホは持つ） | ◎（色ペンで出馬表を塗りたくる人は独特） |
| 仕掛けの余地 | ◎（画面を隠す構図自体が伏線） | ◎（どの馬に何色がついているか＝読める伏線） |

### 色ペンの設計ルール（レイ向け）

- 赤＝ソラの第一直感（最初に「この馬」と感じたもの）
- 青＝比較対象（「こっちもありえる」）
- 緑＝意味不明（ソラ自身にも説明できない印）
- このルールは読者には明かさない。考察班が自分で見つけるもの
- たまにルールが破綻する（赤と緑が同じ馬についている等）→ソラの迷い

### スマホは完全に消すべきか？

消さなくていい。ポケットに入っている、またはテーブルの上に置いてある——程度の存在。
メインの記号は「双眼鏡＋色ペンの出馬表」に移行。
スマホが前面に出るのは「パドックで馬の写真を撮って見せる」特別回のみ（カイのレアポーズ設計と一致）。

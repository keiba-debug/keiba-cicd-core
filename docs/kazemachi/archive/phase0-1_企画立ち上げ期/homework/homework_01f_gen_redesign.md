# ゲンさん（経験派）— 完全リデザインプロンプト

---

## 不評ポイント総まとめ

### プロデューサー
- やさしすぎる。「近所の好々爺」
- テイストが一番AI感が強い。線がツルッとしてて他キャラと合わない
- ノートが英語になった

### ユキ（感情設計）
- 目まで優しい → レース中に絶叫する本性が想像できない
- **核心：「笑っている口元と、笑っていない目」が必要**
- 口角は上がっているが、目は何かを思い出している。遠くにピントが合っている
- 手がゴツくない → 現場にいた人間の身体が見えない
- ノートは日本語の殴り書き。達筆ではなく癖のある字

### カイ（構成・テンポ）
- 「おじいちゃんの味方」にしか見えない → どちらにも乗れる余白が顔に必要
- **核心：ベース画像は「話が始まる0.5秒前」の顔にすべき**
- 「この型、昔も見たんだけど——」と言いかけた瞬間。思い出しかけている
- 穏やかに完結した顔（今の画像）は「話が終わった後」の顔。それは違う
- 5人並べた時にゲンさんだけ絵柄が違う → テイスト統一が必須
- 値踏みしている目 = 下まぶたを少し上げる

### レイ（仕掛け）
- **核心：手書きノートの中身にこそ仕掛けの本命がある**
- ノートに書くべきもの：日本語殴り書き、コース図（手描き楕円）、数字、赤ペンで丸した固有名詞
- 赤丸の固有名詞 = 画像の中で唯一の赤。読者の視線が自然に行く。でも読めない
- ゲンさんがノートに印をつけるのは自然な行動。伏線のためにキャラを動かしていない

---

## ゲンさんとは何者か（ソラの教訓を踏まえて）

ソラで学んだこと：**キャラの核心を「1つの感情」で定義してからプロンプトを書く。**

- MC = 「またこの人たちか」（疲れた諦め）
- ナルミ = 「数字は嘘をつかない」（冷たい確信）
- ソラ = 「合ってるかな…」（脆い直感）
- テツ = 「あのレースを思い出している」（遠い過去）

**ゲンさん = 「この展開、前にも見た」（静かな既視感）**

40年分のレースを見てきた男。穏やかだが、目だけは別の時間を見ている。
口元は今の会話に参加している。でも目は20年前のレースと今のレースを重ねている。
その「重ね合わせ」が完了した瞬間——ゲンさんは黙っていられなくなる。

---

## A. メインプロンプト（ベース画像）

```
manga-influenced anime, sketchy pen linework, flat color, low saturation, muted tones, white background, upper body shot

1boy, solo, early 60s, medium-large build — NOT frail, NOT thin. this man has spent 40 years on his feet at racetracks. broad shoulders, thick neck, slightly rounded belly. he takes up space

HAIR: short gray hair, slightly messy — not styled, not military-short. just a man who gets it cut every few weeks and doesn't think about it between. some white mixed in at the temples. light stubble on chin and jaw (2-3 days unshaved)

FACE — THE MOST IMPORTANT ELEMENT:
- THE MOUTH: relaxed, warm. the corners are slightly turned up — a default half-smile. this is a man who smiles easily, who makes everyone comfortable. the mouth says "don't worry about it"
- THE EYES: completely different from the mouth. the eyes are NOT smiling. they are SHARP. slightly narrowed. the lower eyelids are raised just a fraction — this is the face of someone APPRAISING, EVALUATING, COMPARING what he sees now to something he saw decades ago
- the DISCONNECT between the warm mouth and the calculating eyes IS this character. if the mouth and eyes match (both warm, or both sharp), the image has FAILED
- deep laugh lines around the mouth and crow's feet around the eyes — these are earned wrinkles from decades of squinting at tracks in sunlight and laughing at bar counters
- skin is sun-weathered, slightly rough — this is NOT a desk worker's face

CLOTHING:
- a slightly worn plaid flannel shirt in muted browns and greens — washed many times, soft, comfortable. sleeves rolled up to just below the elbows
- forearms visible: thick, veined, sun-tanned. these are WORKING hands and arms, not delicate
- a plain white undershirt visible at the open collar
- the shirt is buttoned but not neatly — one button is in the wrong hole, or the collar is slightly crooked. he doesn't notice and doesn't care

HANDS — CRITICAL:
- fingers are thick, knuckles prominent — a man who has gripped railings and pens for decades
- one hand holds a pen (cap off, ready to write) loosely between thick fingers
- the other hand rests on or near an open notebook
- the hands should look like they belong to someone who has done physical work, not office work

PROP — THE NOTEBOOK:
- a well-worn spiral notebook, open to a page filled with JAPANESE handwriting
- the writing is messy, fast, cursive — NOT neat, NOT calligraphy. the handwriting of someone who writes for himself, not for others
- visible on the page: a hand-drawn oval shape (a simplified racecourse diagram)
- several numbers scattered around (race times, horse numbers, finishing positions)
- ONE line of text is circled in RED pen — this is the ONLY red in the entire image. the circled text is small, suggesting a name or a date, but unreadable at normal zoom
- the notebook looks like it has been used for years — cover is bent, pages are yellowed and dog-eared

SECONDARY PROP:
- a smartphone lying FACE-DOWN on the table nearby (he doesn't use it, he gave up on learning it)
- reading glasses pushed up on top of his head (he forgets they're there)

POSE:
- sitting in a simple chair, leaning slightly forward — elbows on the table or knees
- his posture suggests he just thought of something. he was relaxed, but now there's a slight tension in his upper body — he's leaning in
- his head is tilted very slightly — the angle of someone who just heard a familiar melody and is trying to place where he knows it from
- overall: "this型、昔も見たんだけど——" THE 0.5 SECONDS BEFORE HE SPEAKS

WHAT THIS IMAGE SHOULD MAKE THE VIEWER FEEL:
- "this man knows something I don't"
- "he looks friendly, but I wouldn't bet against him"
- NOT "what a nice grandpa" NOT "he looks so kind"
- the feeling is: quiet danger disguised as warmth

ART STYLE — MATCH MC AND SORA:
- linework: sketchy, imperfect pen strokes — visible line weight variation, rough edges, lines that don't perfectly connect. NOT smooth, NOT clean, NOT polished
- proportions: manga-influenced — slightly stylized, features simplified but with character
- coloring: flat fill, almost no shading. watercolor-wash texture in some areas is OK. very low saturation
- the ONLY color with saturation is the RED circle in the notebook
- skin tone: warm but muted — sun-tanned but not vivid
- background: plain white, no environment
- this should look like it was drawn by the SAME ARTIST who drew MC and Sora

DO NOT:
- make him look purely gentle or purely kind
- give him soft, warm, grandfatherly eyes
- make his hands look thin or delicate
- use clean, smooth digital linework
- make the notebook text in English or any non-Japanese script
- make the shirt look new or crisp
- add any bright or saturated colors except the red circle in the notebook
- make him look frail or elderly-weak — he is 60, not 80
```

---

## B. バリエーション：レース中（本性が出る瞬間）

```
（Aのプロンプトに以下を差し替え）

POSE:
- sitting but his upper body is LEANING FORWARD sharply — he just saw something
- one hand grips the edge of the table, knuckles white
- the other hand is still holding the pen but it's frozen mid-air
- his mouth is NO LONGER smiling — it's slightly open, lips parted
- his eyes are WIDE and LOCKED onto something — the calculating look from the base image has intensified into full focus
- the notebook is still on the table but he's no longer looking at it
- he looks like a man who just realized his hunch was right and the race is about to prove it

EXPRESSION:
- the warmth is GONE. this is the real Gen-san. the version that his drinking buddies have never seen
- pure concentration. the face of someone watching a pattern complete itself in real time
- this is 40 years of experience converging on a single moment

（この版は「ゲンさんの本性」。普段の穏やかさが剥がれた瞬間。
使用タイミング：レース中の実況回。レアカードではないが頻度は低い。
「穏やかなゲンさんがこの顔をした」= テンポが動くサイン。）
```

---

## C. バリエーション：ナルミ・ソラとの対比用

```
（Aのプロンプトに以下を差し替え）

POSE:
- sitting at a table, leaning back in his chair, arms loosely crossed
- the notebook is closed on the table in front of him
- his reading glasses are pushed up on his forehead
- he is looking at someone across the table (not in frame) with his signature expression: warm mouth, sharp eyes
- the body language says "I'm listening" but the eyes say "I already know where this is going"

（ナルミやソラが自分の予想を説明している時のゲンさん。
聞いているフリをしているが、既に自分の答えを持っている。
並べた時に「この3人の力関係」が画像だけで伝わる構図。）
```

---

## D. バリエーション：ノート書き込み中（仕掛け用）

```
（Aのプロンプトに以下を差し替え）

POSE:
- hunched over the notebook, writing actively — pen touching paper
- his face is in profile or three-quarter view, looking down at the notebook
- the notebook page is clearly visible to the viewer — Japanese handwriting, course diagrams, numbers
- ONE red circle on the page is prominent
- his reading glasses are ON his nose (this is the only time he uses them)
- expression: concentrated, mouth slightly pursed — the warm smile is temporarily off

THE NOTEBOOK IS THE STAR OF THIS IMAGE:
- the page should be large enough to see some detail
- the hand-drawn course diagram should be clearly an oval (racecourse shape)
- scattered numbers around the margins
- the red-circled text should be visible but just barely too small to read — it INVITES the viewer to zoom in
- some pages have been folded at the corner (dog-eared)

（この版はレイの仕掛け用。ノートの中身が主役。
ゲンさんの顔は横顔でもいい。ノートのページが読者に見えることが優先。
考察班がこの画像を拡大して赤丸の中を読もうとする——それが狙い。）
```

---

## 設計メモ

### ゲンさん vs 他キャラの小道具比較

| キャラ | 小道具 | 時間軸 | 情報の種類 |
|---|---|---|---|
| ナルミ | PC＋スプレッドシート | 今のデータ | デジタル・構造化 |
| ソラ | 双眼鏡＋色ペンの出馬表 | 今の感覚 | アナログ・混沌 |
| MC | クリップボード＋書類 | 今の管理 | 組織的 |
| テツ | 古い馬券 | 過去の1点 | 感傷的 |
| **ゲンさん** | **手書きノート＋赤丸** | **過去と今の接続点** | **アナログ・蓄積型** |

ゲンさんのノートはテツの馬券と似ているようで違う。テツの馬券は「1つの過去」。ゲンさんのノートは「40年分の過去の集合体」。テツは過去に囚われているが、ゲンさんは過去を道具として使っている。

### 「口と目の温度差」のAI指示テクニック

ソラで学んだこと：AIは「表情の矛盾」を苦手とする。「笑っているけど悲しい」と書くと、中間の曖昧な顔になるか、どちらか一方に倒れる。

対策：**口と目を別々に指示し、「この不一致がキャラの核」と明示する。** さらにDO NOTで「口と目が同じ温度になること」を禁止。

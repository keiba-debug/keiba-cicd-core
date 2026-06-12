# 【カイ】宿題①c — キャラ画像プロンプト

> 優先順位：① データ派 × 直感派（2人セット） → ② 進行役のツッコミ差分 → ③ ゲンさん → ④ ロマン派
> カイの方針：**並べた時に対立が見える**ことが最優先。1人ずつ作ると「いい絵」が出る。2人セットで作ると「番組が見える」。

---

## 優先①：ナルミ × ソラ（2人セット）

<!-- 構成メモ：この2人の絵が並んだ瞬間に「あ、意見が割れてる番組なんだ」と分かるのが理想。1枚で番組のコンセプトが伝わる。 -->

### なぜ2人セットか

Xのタイムラインで流れてきたとき、1キャラだと「誰？」で終わる。2キャラだと「何が起きてる？」になる。対立が画面に入っていれば、キャプションを読む前にコンセプトが伝わる。

### プロンプト（ナルミ）

```
1boy, late 20s, sitting at a desk covered in printed data sheets
wearing a dark cardigan over a simple crew-neck shirt, sleeves slightly too long
one hand on laptop keyboard, the other hand holding a pen that hasn't moved in 10 seconds
short black hair, plain features, glasses
expression: flat, unreadable — staring at screen with zero emotion on the surface
BUT: a crumpled betting slip is visible in the desk trash can beside him (he threw it away but didn't empty the trash)
color palette: cool grays and navy, low saturation
slice-of-life anime, sketchy linework matching the MC reference image
upper body, 3/4 angle from the left
```

**構成意図：** ソラと左右に配置する前提。ナルミは画面左、やや閉じた構図。「データの世界に閉じている」印象。ゴミ箱の馬券は本性の痕跡。

### プロンプト（ソラ）

```
1girl, mid 20s, standing with weight on one leg, slightly leaning to the side
holding smartphone at arm's length showing a blurry paddock photo
wearing a baggy vintage racing windbreaker (oversized, bright accent color on zipper only) over a casual t-shirt
medium-length hair with a single colorful clip, slightly windblown
expression: mouth open, mid-word, eyes alive — clearly interrupting someone
one finger pointing at the phone screen as if to say "LOOK at this"
color palette: same low saturation base as Narumi but with ONE warm pop on the hair clip
slice-of-life anime, same linework
upper body, 3/4 angle from the right (mirroring Narumi's angle)
```

**構成意図：** 画面右に配置。ナルミとミラー構図。ナルミが閉じているのに対して、ソラは外に開いている。「この2人、明らかに考え方が違う」が左右の絵を見比べるだけでわかる。

### 2人を並べた時のチェックリスト

```
          ナルミ（左）    ソラ（右）
姿勢      座り・静        立ち・動
色        寒色ベース      暖色アクセント
小道具    PC・データシート  スマホ・ブレた写真
表情      無表情          口が開いている
目線      画面（内側）    こちら（外側）
体の向き  3/4 左向き      3/4 右向き（対面構図）
```

**タイムラインで流れてきたとき：** 「PCを見てる人」と「スマホを突きつけてくる人」。この2人が何か言い合ってる。→ 気になってキャプション読む。これが構成上の勝ち筋。

---

## 優先②：進行役（マキ）のツッコミ差分

<!-- 構成メモ：マキの差分は「使用頻度で設計する」のが正解。毎回使うものは表現がライトに、レアなものは重くする。 -->

### 差分設計の構成ルール

| 差分 | 使用頻度 | 表情の変化量 | 構成上の役割 |
|---|---|---|---|
| A：デフォルト | 毎回 | 変化量ゼロ。基準点 | 他キャラの感情を際立たせる「無」 |
| B：呆れ顔 | 毎回 | 小（目が半閉じ） | ゲンさんの長話・ソラの帽色間違いへの定番リアクション |
| C：斬り顔 | 週1 | 中（目がまっすぐ鋭く） | ツッコミの瞬間。「で、結局どの馬？」の顔 |
| D：微笑み | 月1 | 極小（口角0.5mm） | 曖昧に笑っている——ように見える。レア演出 |
| E：間の顔 | 年数回 | 中〜大（目線が外れる） | 予想しない理由を訊かれた時。最もレアで最も重い |

### プロンプト（A：デフォルト）

```
same character as MC reference (black bob, blue shirt, badge, clipboard)
expression: completely neutral. not happy, not sad, not bored. just present
eyes looking straight ahead, mouth in a flat line
posture: standing straight but not stiff, clipboard held at waist level
the face of someone who is observing everything and reacting to nothing
```

### プロンプト（B：呆れ顔）

```
same character
expression: eyelids lowered to half-closed, slight exhale through nose
head tilted very slightly to one side
one hand raised to temple as if nursing a headache
the universal face of "I work with these people"
```

### プロンプト（C：斬り顔）

```
same character
expression: eyes fully open and focused, looking directly at viewer (or at another character)
mouth slightly open, about to deliver one sentence that will end someone's argument
posture shifts forward by a few degrees — subtle but intentional
this is the face that makes the other characters go quiet
```

### プロンプト（D：微笑み）

```
same character
expression: ALMOST identical to default. the difference is in the mouth corners only — lifted by less than a millimeter
eyes unchanged from default
this should be ambiguous enough that viewers argue about whether she's actually smiling
```

### プロンプト（E：間の顔）

```
same character
expression: eyes slightly wider, looking 10 degrees to the right (breaking her usual straight gaze)
jaw set slightly tighter, hands gripping clipboard harder
NOT shock. NOT sadness. the face of someone who just heard something that she needs 0.8 seconds to process before she can move on
this face appears 3-4 times per season maximum
```

---

## 優先③：ゲンさん（経験派）

### プロンプト

```
1boy, solo, early 60s, warm and stocky build
sitting in a simple chair, leaning forward with elbows on knees
a small handwritten notebook in one hand, a pen in the other (pen cap in mouth)
wearing a comfortable plaid flannel shirt, slightly faded
short gray hair, kind eyes with deep laugh lines, reading glasses perched on top of head
expression: mid-chuckle, about to say something — the face right before "let me tell you about a race from 2009..."
a smartphone lies face-down on the table next to him (he gave up on it)
warm indoor lighting, nostalgic tone
same slice-of-life linework
upper body, frontal, open pose
```

**構成意図：** ナルミとソラが「対立」を見せるキャラなら、ゲンさんは「間」を見せるキャラ。前のめりで話しかけてくる構図は、聞き手（読者）との距離を近くする。スマホが裏返っている→ アナログ人間の記号。ペンの蓋を口に咥えている→ 「次に何を書くか」考え中の動きが、話が長くなるフラグとして機能する。

---

## 優先④：ロマン派（テツ）

### プロンプト

```
1boy, solo, mid to late 50s, tall and lean silhouette
standing with one hand in coat pocket, the other holding nothing
wearing a long dark overcoat, collar slightly turned up, a white scarf loosely draped
angular face, silver-streaked hair pushed back, deep-set calm eyes
expression: looking into the distance with a faint, knowing smile — not at the viewer, not at anything specific
background: intentionally sparse — a blurred railing and open sky. could be a racecourse, could be anywhere
ONE detail: a very old, yellowed betting slip barely visible sticking out of his breast pocket
slightly higher contrast than the other characters — he looks like he belongs to a different show
same linework style but with more negative space around him
full body, standing, solitary composition
```

**構成意図：** テツの構図は他のキャラと差をつける。ナルミ・ソラ・ゲンさん・マキは全員「室内」「人と一緒」「何かを持っている」。テツだけ「屋外」「1人」「ほぼ手ぶら」。テンポの異質さをビジュアルでも反映する。G1回で初登場するとき、タイムラインに突然この空気感が入ると「誰この人？」のフックになる。

---

## カイの構成チェック：5人を横並びにした時の視覚テンポ

```
[ナルミ]  [ソラ]   [ゲンさん] [マキ]    [テツ]
 座り     立ち      座り      立ち      立ち
 閉じ     開き      開き      ニュートラル 閉じ
 寒色     暖色点    暖色      淡色      暗色
 左向き   右向き    正面      正面      横向き
 PC       スマホ    ノート    ボード    手ぶら
```

テンポ的に言うと：静→動→暖→無→異。この並びなら飽きない。テツが最後に来ることで「何か違う」が余韻になる。

ただし、Xでは全員同時に出さない。並びの効果が活きるのは番組のキービジュアルや、シーズン終盤の全員集合回。Phase 1では2人ずつ出す。

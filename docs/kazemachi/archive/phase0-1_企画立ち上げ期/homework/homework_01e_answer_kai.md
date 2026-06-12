# 【カイ】宿題①e — ソラのビジュアル方向性

---

## 1. 全画像を見た結論

**全部ダメだが、ダメの質が違う。そこにヒントがある。**

### 茶髪スマホ指差し系（tone-0, 1, 1(1), 2, _フォルダの全部）

少年漫画のヒロイン。「見て見て！」と叫んでいる女の子。ソラではない。

問題の本質は**ポーズ**。スマホをカメラに突き出す＋前のめり＋口全開——このポーズは「相手に何かを見せる」ポーズ。つまり**コミュニケーションのポーズ**。ソラの直感は対外的なものじゃない。自分の中で完結している。ポーズが内向きであるべきなのに外向きになっている。

ただし、**tone-2.jpg**は例外。目だけが違う。口は開いているけど、目が「見てほしい」ではなく「わかってるでしょ」と言っている。この目は使える。

### 黒髪ショートボブ腕組み系（tone-0(1), 1(3), 2(1), 3）

「かっこいい」になったが、**テンポ感が死んだ**。

全部同じポーズ（腕組み＋微笑み＋見上げ）で、バリエーションがない。4枚並べても同じ人の同じ瞬間に見える。つまり**差分が作れない**。表情差分で「自信」「動揺」「ムッとする」を回せるベース画像として機能しない。

もう一つ：MCと並べたときの問題。MCが「ゆるスケッチ＋デフォルメ」なのに、黒髪版のソラは「整った線＋リアル等身」。**同じタイムラインに流したら「コラ画像」に見える**。これが最大の問題。

---

## 2. ナルミと並べた時に対立が映えるビジュアル

### 対立構造を画像で作るには「温度差」が必要

ナルミ：紺カーディガン、PC、EV+マグカップ、目の下のクマ、静止、寒色。
→ **冷たくて閉じている**

ソラをナルミの対極にするなら：
→ **暖かくて開いている**

ただし「暖かくて開いている」を少年漫画的にやると今のソラになる（元気！笑顔！叫ぶ！）。そうじゃない。

**「暖かいけど静か」なソラ。**

カイの提案する対立構図：

```
ナルミ                     ソラ
PCを見ている（前を向いていない）  ← → 遠くを見ている（前を向いていない）
データが見えている              ← → 何かが見えている（言語化できない）
座っている                    ← → 立っている（でも動いていない）
マグカップ（静物）             ← → スマホを手に持っている（でも見ていない）
紺（寒色）                   ← → ダークブラウン+白（暖色寄りの中間色）
```

2人とも**前を向いていない**。でも見ている方向が違う。ナルミは目の前のデータ、ソラは遠くの何か。これが並んだとき「同じ問いに違う角度から向き合っている2人」に見える。

### Xのタイムラインで止まる絵

スマホを突き出す絵はタイムラインで止まらない。「元気なアニメキャラがスマホ見せてる」はノイズ。

止まるのは**「何を見ているかわからない顔」**。

MCの画像がなぜ止まるか——半目で何を考えているかわからないから。テツの画像がなぜ止まるか——何を思い出しているかわからないから。

ソラも「わからない」が入ればタイムラインで止まる。**スマホの画面を自分だけ見ていて、少しだけ口角が上がっている**——「この子は何を見つけたんだろう」と思わせる構図。

---

## 3. 具体的な修正案＋プロンプト

### カイの修正案：ポーズを根本的に変える

やめること：
- スマホをカメラに突き出す
- 前のめり
- 口を大きく開ける
- 腕組み（差分が作れない）

やること：
- **スマホを自分の方に向けて見ている**（画面は読者から見えない）
- 立っているが、片足を少し引いている
- 口は閉じているか、少しだけ開いている
- 片手はジャケットのポケットに入っている

### プロンプト案

```
1girl, solo, age 26, natural relaxed stance
dark brown messy shoulder-length hair, one colorful hair clip (the ONLY vivid color in the image)
wearing an oversized navy-and-white track jacket (vintage/worn look — small stains, slightly faded), plain white tee, dark shorts
POSE: standing with weight shifted to one leg, one hand in jacket pocket
the OTHER hand holds a smartphone — FACING TOWARD HER, screen NOT visible to viewer
she is looking at the phone screen with a slight smirk — not a full smile, just one corner of the mouth raised
her eyes are focused, sharp, evaluating — she sees something on the screen that confirms what she already felt
the overall mood is: "she just found what she was looking for, and she's quietly satisfied"

CRITICAL ART STYLE MATCHING (reference: MC image with clipboard):
- line quality: sketchy, hand-drawn pen feel — NOT clean/smooth digital lines
- proportions: slightly stylized/deformed — head slightly oversized, features simplified
- coloring: flat, minimal shading, very low saturation
- facial rendering: MINIMAL lines — emotion from FEW strokes, not detailed rendering
- cheek blush: sparse sketch lines (2-3 lines), NOT solid pink areas
- background: plain white, no environment
- the image must look like it was drawn by the SAME artist who drew the MC

DO NOT:
- make her look at the camera
- make her mouth wide open
- make her eyes large/sparkly/shounen-manga style
- use high saturation anywhere except the hair clip
- add dramatic pose or dynamic angle
```

### カイの設計意図

**「ソラのベース画像」は「見つけた瞬間」にすべき。**

各キャラのベース画像はそのキャラの「一番らしい瞬間」を切り取るもの：
- MC → 書類を抱えて半目で立っている（「またこの人たちか」の瞬間）
- ナルミ → PCの前でマグカップを持っている（「分析中」の瞬間）
- ゲンさん → ノートを見ながら何かを思い出しかけている（「あれ、これ前にも…」の瞬間）
- テツ → 柵にもたれて曇り空を見ている（「あのレースを思い出している」の瞬間）

**ソラ → スマホの中の馬の写真を見て「やっぱりこの子だ」と確信しかけている瞬間。**

動いていない。叫んでいない。ただ、目だけが「見つけた」と言っている。

このベース画像があれば、差分は回せる：
- 自信差分：口角がもう少し上がる → 「今日は来ますよ」
- 動揺差分：目が泳ぐ、口が「への字」 → 「……あれ？」
- 興奮差分：スマホを突き出す → **例外的にこのポーズが出る = テンションが上がった証拠**

最後の点が重要。スマホ突き出しポーズを「通常」にすると特別感がない。「普段は見せないソラが、今日だけ見せてきた」——**レアなポーズが物語を動かす**。

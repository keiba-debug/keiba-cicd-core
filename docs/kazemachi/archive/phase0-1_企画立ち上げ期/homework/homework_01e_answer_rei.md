# 【レイ】宿題①e — ソラのビジュアル方向性

---

## 1. 今までの試行で「一番近い」もの

**構造的に分類してから答える。**

### 試行の分類

| 系統 | 画像 | テイスト統一 | キャラ表現 | 仕掛けの余地 |
|---|---|---|---|---|
| A: 茶髪スマホ突き出し | tone-0, 1, 1(1), 2, _フォルダ全部 | × 少年漫画寄り | × 元気すぎ | × スマホが前面＝画面が見える＝情報がオープン |
| B: 黒髪ショートボブ腕組み | 0(1), 1(3), 2(1), 3 | × 線が整いすぎ | △ かっこいいが一面的 | △ 手が隠れている＝何を持っているかわからない |
| C: tone-2単体 | tone-2 | △ まだ少年漫画だがマシ | ○ 目に意志がある | × スマホが前面 |

**レイの回答：一番近いのは「B系統の考え方」＋「Cの目」。**

B系統が正しいのは「手元の情報を見せない構図」を生んだこと。ソラのスマホの中身が常に読者に見えている状態は、仕掛けの観点から最悪。**「ソラだけが見ているもの」があることが重要**。

しかしB系統のテイストはMCと合わない。だから、B系統の「情報を隠す構図設計」をA系統のテイスト（スケッチ線、デフォルメ）の中でやり直す必要がある。

---

## 2. 仕掛けの観点からのビジュアル設計

### ソラの画像に仕込むべき「層」

**[表層] 直感派の予想屋** — パドックに行く子。馬を自分の目で見る子。スマホには自分で撮った馬の写真が入っている。

**[裏層] ソラが「見えている」ものは何か？** — ソラの直感は「なんとなく」ではない。パドックで馬の気配を読む身体能力。これはデータにできない。つまりナルミのスプレッドシートには載らない情報を持っている。**ソラのスマホの中にはナルミが持っていないデータがある。**

この裏層を画像で機能させるには：

1. **スマホの画面を読者に見せない構図がデフォルト**
2. **たまに画面が見えるとき、そこに「普通の馬写真」以上の情報がある**（例：パドック写真の端にゲンさんの後ろ姿が映っている → ゲンさんも同じ馬を見ていた？）
3. **考察班が「ソラのスマホに映っていた馬は何号だったか」をレースごとに追跡しはじめる**

### ジャケットの仕掛け

ソラのジャケットには小道具としての仕掛けの余地がある。

**ワッペン/パッチの設計：**
- レーシングジャケットにはパッチがつきもの
- ソラのジャケットに**1つだけ「読めそうで読めないワッペン」**を入れる
- これはソラが過去に行った競馬場、あるいは牧場のロゴ
- Phase 1では見えない。画像のどこかにあるが、判読できない
- Phase 2のどこかで、同じロゴが別の場所に出る

ただし、この仕掛けは**ジャケットの汚れや古さと矛盾しない形で入れる**。使い込んだジャケットにパッチが付いているのは自然。新品のジャケットにロゴが入っているのは広告に見える。

### ヘアクリップの仕掛け

レインボー/ホログラフィックのヘアクリップがソラの唯一の彩度ポイントとして設計されている。

**このクリップを「固定の記号」として扱うか「変わるもの」として扱うか？**

レイの提案：**基本は同じクリップだが、たまに位置が変わる。** 右側にある日と左側にある日がある。考察班が気づく：「ソラのクリップが左のときは予想が当たっている」——ただしこれは偶然の一致であるべき。パターンを見出そうとする読者の行為自体が「直感派vs分析派」のテーマを反映する。

---

## 3. プロンプト案（仕掛けの仕込み込み）

```
1girl, solo, age 26, natural stance
dark brown messy shoulder-length hair, ONE colorful holographic hair clip on the right side
wearing an oversized vintage navy/white track jacket — the jacket shows visible wear: faded sections, a small dirt mark near the hem, sleeves slightly too long with cuffs pushed up
IMPORTANT: the jacket has ONE small embroidered patch on the upper left chest area — the patch design should be simple, small, and slightly worn/unclear (like a faded logo that's been through many washes)
plain white t-shirt underneath, dark shorts

POSE: standing, weight on left leg, right leg slightly back
right hand holds a smartphone — the phone screen faces TOWARD HER, angled away from the viewer (the viewer can see the back of the phone but NOT the screen)
left hand loosely at her side or touching the edge of her jacket
she is glancing at the phone screen — her eyes are focused downward at the phone with quiet intensity
expression: mouth closed or barely parted. a very subtle asymmetric expression — not quite a smile, more like "hmm, I thought so"

KEY EXPRESSION NOTE: her face should convey "I see something others can't see, and I'm used to that being lonely" — confidence layered over vulnerability. the confidence is on the surface, the vulnerability is in the slight tension of her shoulders

ART STYLE — ABSOLUTE PRIORITY:
this image MUST match the MC reference (clipboard woman) in:
- linework: sketchy, imperfect pen strokes — visible line weight variation, occasional rough edges
- proportions: manga-influenced deformation — head slightly oversized, simplified features
- coloring: flat fill, almost NO gradient shading, extremely low saturation
- the ONLY saturated color in the entire image is the holographic hair clip
- facial detail: MINIMAL — 2-3 short lines for blush on one cheek only, simple dot or short-line nose, eyes with personality but NOT large/detailed
- background: plain off-white, no environment detail
- overall impression: "one page of a manga storyboard" NOT "anime key visual"
```

### レイの追加指示（仕掛け対応）

このプロンプトで生成した画像に対して、**以下は後工程で手動追加を検討する：**

1. **スマホの背面に小さなステッカー**を1つ描き足す。競馬場の入場記念ステッカーのようなもの。何の競馬場かは今は不明。後から特定できるようにデザインだけ決めておく
2. **ジャケットのパッチ**がこのプロンプトで十分に出ない場合、生成後に描き足す。デザインは「馬のシルエット＋2文字のアルファベット」程度のシンプルなもの
3. **ヘアクリップの位置**をベース画像では右側に固定。差分で左側版も生成しておく

---

## 補足：ソラの画像に「いつか爆発するもの」を埋めておく

ソラの現在の画像群には「物語の種」がない。全部「今のソラ」しか描いていない。

ゲンさんのノートには赤丸があった。テツの馬券は過去のレースだった。MCのクリップボードには書類が挟まっていた。全員「見えるけど読めない情報」を持っている。

**ソラが持つ「見えるけど読めない情報」は、スマホの画面。**

だからスマホの画面を読者に見せない構図がデフォルトであることが正しい。ソラのスマホの画面が見える日——それは物語が動く日。

画面を隠す＝物語を隠す。ソラの構図そのものが伏線になる。

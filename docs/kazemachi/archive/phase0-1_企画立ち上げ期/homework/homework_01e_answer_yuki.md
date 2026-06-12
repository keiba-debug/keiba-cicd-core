# 【ユキ】宿題①e — ソラのビジュアル方向性

---

## 1. 今までの試行で「一番近い」もの

**tone-2.jpg（茶髪ミディアム・スマホ指差し・目が鋭い版）が一番近い。**

理由：この1枚だけ、目に「意志」がある。口は開いているけど、目が笑っていない。スマホを指差す動作は「見て！」ではなく「これでしょ」と言い切っている目をしている。ソラの直感が「ビジョン」であることが、この目からだけ伝わる。

ただし、まだ足りない。「脆さ」が見えない。この目は「自信100%」の目。ソラの目は「自信90%、不安10%」であるべき。

**黒髪ショートボブ+腕組み版（tone-0(1)、1(3)、2(1)、3）は方向性として面白いが、別の問題を起こしている。** 顔の描き方がMCと完全に別タッチ。MCが「散らかったスケッチ線＋デフォルメ強め」なのに対して、黒髪版のソラは「整った線＋等身が高い」。同じ番組のキャラに見えない。

---

## 2. 「ここをこう変えればハマる」

### 問題の根本：ソラは「2つの顔を同時に持っている子」

今のすべての画像は「元気なソラ」か「かっこいいソラ」のどちらか一方しか出ていない。ユキが思うソラは**両方が同時にいる子**。

具体的に：
- 口は少し開いている（言いかけている）が、叫んでいない
- 目は鋭いが、片方だけ少し細い——見定めている
- 姿勢は前のめりだが、片足に重心が乗っている（すぐ引ける）
- ジャケットは着ているが、片方の袖が少しずり落ちている

**「自信と不安の共存」を1枚で表現する。** これがソラの画像の核。

### 「この子好きだな」と思わせる一要素

**汚れたジャケット。**

黒髪版で出ている「泥がついたジャケット」は正解に近い。ソラはパドックに行く子。厩舎に行く子。服が汚れる場所にいる人間。ナルミがPCの前にいる人間で、ゲンさんが机の前にいる人間であるのに対し、ソラは**馬のそばにいる人間**。

服の汚れは「この子はちゃんと現場に行ってる」の証拠。これが一番の好感ポイント。きれいなジャケットにしてはいけない。

### MCとのテイスト統一の具体策

MCの画像を改めて見た。ユキが見るMCのテイストの特徴：

1. **線が「きれい」じゃない**。ペンで描いたスケッチ。はみ出しがある。完璧じゃない
2. **デフォルメが強い**。頭が大きめ。目の位置が低め。リアル寄りではない
3. **色が少ない**。水色のシャツ以外はほぼモノクロ。肌色も抑えめ
4. **表情がミニマル**。半目と薄い口元だけで感情を伝えている

ソラの画像で合わなかったのは：
- 茶髪版：目がデカすぎ、口が開きすぎ、頬の赤みが強すぎ → MCと「表情の情報量」が違いすぎる
- 黒髪版：線が整いすぎ、等身がリアルすぎ → MCの「ゆるいデフォルメ」と合わない

**解決：MCの「情報量の少なさ」に合わせる。**

ソラの表情もミニマルにする。大きな口ではなく、少し開いた口。大きな目ではなく、片方を少し細めた目。頬の赤みは線3本程度。MCと同じ「少ない線で人格を伝える」ルールの中にソラを入れる。

---

## 3. プロンプト案

```
1girl, solo, age 26, medium height, slim but not fragile
HAIR: dark brown (NOT bright brown — closer to coffee brown), messy shoulder-length, one side tucked behind ear, the other side falling forward. a SINGLE colorful hair clip (rainbow/holographic — this is her ONE bright accent, like MC's light-blue shirt is her one color)
FACE: mouth slightly open — NOT wide open, just parted lips as if about to say something. ONE eye slightly narrower than the other — she's assessing, evaluating, reading something that others can't see. minimal blush (just 2-3 sketch lines on one cheek, NOT both — asymmetry is key). expression is CONFIDENT but NOT aggressive — she knows something, and she's deciding whether to tell you
CLOTHING: oversized navy/white racing jacket — sleeves slightly too long, pushed up on one arm. the jacket has visible wear: a small stain near the hem, a scuffed patch on one elbow. plain white t-shirt underneath. the jacket is OPEN, not zipped
POSE: standing, weight on one leg, slight lean forward. one hand in jacket pocket, the other holding a smartphone at her side (NOT thrusting it toward camera — the phone is for HER, not for the audience). casual but alert
PROP: smartphone screen shows a blurry horse photo (visible but not the focus of the image)
BODY LANGUAGE: she looks like she just noticed something interesting and hasn't decided what to do about it yet

ART STYLE — THIS IS THE MOST CRITICAL SECTION:
MATCH the MC reference image EXACTLY in these ways:
- sketchy pen linework with visible imperfections (NOT clean digital lines)
- flat color with minimal shading
- low saturation, muted tones — the ONLY saturated element is the hair clip
- slightly exaggerated proportions (head slightly large relative to body — manga-influenced, NOT realistic)
- minimal facial detail — emotion conveyed through FEW lines, not many
- background: plain white or very light gray, NO environment
- the overall feeling should be "a page from a slice-of-life manga" not "an anime screenshot"
```

### ユキのプロンプト設計意図

| 変更点 | 理由 |
|---|---|
| 口を「少し開いている」に変更 | 叫んでいるソラは少年漫画。言いかけているソラがこの番組のソラ |
| 目の左右非対称 | 「見定めている」表情。直感派が何かを感じている瞬間 |
| 頬の赤みを片側だけ・線3本 | MCと同じミニマル表情ルール。両頬ベタ塗り赤は情報過多 |
| スマホを突き出すのをやめる | ソラのスマホは自分のため。見せびらかすものではない。キャラの距離感が変わる |
| 髪色をダークブラウンに | 明るい茶髪は彩度が高くMCと合わない。コーヒーブラウンなら低彩度に馴染む |
| ヘアクリップだけが彩度ポイント | MCの水色シャツと同じ設計。「1キャラ1色」ルール |
| ジャケットの汚れを明示 | 「現場に行く子」の証拠。好感の種 |
| 「まだ決めていない」ボディランゲージ | 確信ではなく、確信に近づいている瞬間。ソラの直感の「途中」 |

### 補足：ソラの「記号」は何か

ナルミ＝PC、ゲンさん＝手書きノート、MC＝クリップボード、テツ＝古い馬券。

**ソラの記号はスマホ——ではなく、スマホの中の「自分だけが撮った馬の写真」。**

スマホは道具。写真が本体。ソラが自分の目で見て、自分の判断で撮った写真。それはデータでもなく、経験でもなく、「あの瞬間に自分が感じたこと」の記録。

だからスマホを突き出す構図ではなく、手元に持っている構図が正しい。ソラにとって写真は「見せるもの」ではなく「確かめるもの」。——たまに興奮して見せてしまうだけ。

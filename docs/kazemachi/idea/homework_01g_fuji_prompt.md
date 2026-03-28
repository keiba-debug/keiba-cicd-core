# 宿題①g — フジさん（記録係・中年女性版）プロンプト募集

> 各作家のシステムプロンプトの後ろに貼って投げる。
> MC・ソラの確定画像を参考として添付。

---

```
━━━━━━━━━━━━━━━━━━━━━
■ フジさんのビジュアルを作りたい
━━━━━━━━━━━━━━━━━━━━━

記録係を中年女性にする案。全員賛成済み。

【フジさんの設計（確定事項）】
- 48歳女性。事務処理の達人。成績表・データ管理担当
- 建前：淡々と仕事をする。感情を出さない。年齢を重ねた結果の静けさ
- 本性：全員の予想と成績を最も長く見てきた人間。
  「◯◯さん、去年もこのコースで同じこと言って外してましたよ」と言える立場。
  でも言わない。——たまに言う。そのときが一番怖い
- ギャップ：帰りの電車で競馬新聞を読んでいる。しかもかなり書き込んでいる。誰にも見せない
- マキ（MC）が唯一「先輩」と呼ぶ存在
- 5人並べた時のテンポ：「圧」

【5人のテンポ確認】
[ナルミ♂30] [ソラ♀26] [ゲンさん♂60] [MC♀34] [フジさん♀48]
  冷          脆          渋           無        圧

【仕掛けの観点（レイ向け）】
- 「すべてのデータにアクセスできるポジション」を維持
- ベテランが管理 → 考察班が「この人の数字は正確」と信頼する前提が生まれる
- タブレットで成績管理＋投稿する役割

━━━━━━━━━━━━━━━━━━━━━
■ 制約：プロンプトは短くしてほしい
━━━━━━━━━━━━━━━━━━━━━

画像生成AIの文字数制限がある。
1回のプロンプトにすべてを詰め込めない。

だから以下の形式で出してほしい：

【形式】
- 「コアプロンプト」（200語以内）：画風・体型・髪・服・ポーズの最低限
- 「表情プロンプト」（100語以内）：表情だけを差し替える追加文
- 「小道具プロンプト」（100語以内）：手元・持ち物の追加文
- 必要なら「ネガティブプロンプト」も

何回かに分けて生成して、良いパーツを組み合わせる方式で進める。

━━━━━━━━━━━━━━━━━━━━━
■ 聞きたいこと
━━━━━━━━━━━━━━━━━━━━━

1. フジさんの「記号」（小道具）は何か？
   ナルミ=PC、ソラ=双眼鏡+出馬表、ゲンさん=ノート+赤丸、MC=クリップボード
   フジさんは？

2. フジさんの「1色」は何か？
   MC=水色、ソラ=出馬表の色ペン、ゲンさん=ノートの赤丸
   フジさんの画面上の差し色は？

3. 48歳女性をAIに描かせる時の注意点
   若すぎず老けすぎず。「おばさん」でも「お姉さん」でもない。
   「仕事できる中年女性」をどう指示する？

4. MCとの関係性が見た目で伝わる工夫
   マキ（34歳）がフジさんを「先輩」と呼ぶ関係。
   並べた時に「この2人は同じ組織で働いている」と分かる要素は？

あなたの専門視点で：
- カイ：5人のビジュアルバランスで「圧」を出すには？ シルエットの差別化は？
- ユキ：「淡々としているのに怖い」を表情でどう表現する？ 好感を持たせる一要素は？
- レイ：フジさんの画像に仕掛けを仕込む余地は？ タブレット画面の中身？ 手元のメモ？

短いプロンプトで核心を突くアイデアがほしい。
```

---

# 回答・プロンプト一式（統合）

## 1. フジさんの「記号」（小道具）

**主記号：タブレット＋スタイラス（成績・データの「正」）**

- ナルミのPC＝**分析の現場**、フジのタブレット＝**集計・公式記録の現場**。同じ「画面」でも役割が違う。
- **副記号（任意）：** クリップ留めの印刷物・「成績」らしい表の束、細いメモ用紙（手書き1行だけ）。「全部見ている」感を紙でも補強。
- **ギャップ用（別生成）：** 電車内・**競馬新聞に鉛筆で殴り書き**（表紙は見せず、紙の端と手元だけ）。普段のフジとは別カード扱いでよい。

---

## 2. フジさんの「1色」

| 候補 | 意味 |
|---|---|
| **ティール／スレート青（画面の1本の線 or 1セル）** | 「管理画面」の冷たさ。ゲンさんの**アナログ赤**と被らない。 |
| **琥珀／オレンジ1点（警告マーカー1つだけ）** | 「ここだけ異常」——レイの仕掛け向き。ただし派手になりやすいので低彩度で。 |

**推奨：** 低彩度のまま **タブレット上のティール系1点**（グラフの1本、またはハイライト1セル）。MCの水色（服）と「青系」でつながりつつ、**デジタル＝冷たい光**として差別化。

---

## 3. 48歳をAIに描かせるときの注意

- **年齢を数字で固定：** `age 48` / `mid-40s office worker` を必ず入れる。
- **若作り防止：** `subtle crow's feet`, `fine lines under eyes`, `gray hair at temples` のどれか1〜2個。全部入れると老けすぎ。
- **「おばさん／お姉さん」回避：** `not glamorous`, `not cute`, `professional administrative worker`, `plain office clothing` — キャラ属性は**職業**で縛る。
- **髪：** ロング艶髪は避ける。`short bob` / `low ponytail` / `practical haircut`。
- **ネガ：** `teenage`, `idol`, `heavy makeup`, `baby face`, `school uniform` を必ず入れる。

---

## 4. MC（マキ）と並べたとき「同じ組織」に見える工夫

- **名札・ストラップ：** 同じ**ストラップ色**（例：紺）＋**名札の形は同じ・中の数字や記号だけ違う**（仕掛けにもなる）。
- **服装の系統：** マキ＝水色シャツ、フジ＝**チャコール／紺のカーディガン or ジャケット**（同じ「オフィスカジュアル」だがフジは一段暗い＝先輩・管理）。
- **小物の共通項：** どちらも**クリップボード or 書類の角**がフレームに入る。マキは散らかり、フジは**綴じられた束**——同じ「紙仕事」、整理度が違う。

---

## 【カイ】「圧」とシルエット

- **圧の正体は「低い位置＋正面性」。** カメラをやや**やや上から**（フジが下を見る／画面を見る），マキより**視線が画面側**。無言で「記録はこっち」と言っている構図。
- **シルエット：** マキ・ソラは立ち気味・細い。フジは**座り＋肩のラインが横に広い**（ジャケット）か、**縦長のタブレット**が画面を縦断して「縦の棒」が入る。5人並べで**唯一「横に重い」ブロック**になると「圧」が出る。

---

## 【ユキ】淡々としているのに怖い／好感の一要素

- **怖さ：** 目は**細く開いたまま**、相手を見ていない（画面か数字）。**口は動かない**。感情がゼロに見える瞬間が一番怖い。
- **好感：** **手元だけ丁寧**（スタイラスの持ち方、紙の角を揃える）。人に優しくないが、**仕事には誠実**——「嫌な人だけど信頼はできる」温度。

---

## 【レイ】仕掛け

- **タブレット：** グリッドに**全員のイニシャル or 略号**が並ぶが小さくて読めない／1セルだけ色が違う。
- **手元メモ：** 1行だけ**「去年」**「**同**」など単語が切れて見える（意味は取らせない）。
- **名札：** `0017` 系でマキと**連番 or 近い番号**（前後関係の示唆）。

---

## 短いプロンプト（英語・文字数目安）

※「語」は英語ワード数の目安。コピペ用。

### コアプロンプト（〜200 words）

```
manga-influenced anime, sketchy pen linework, flat color, low saturation, muted tones, white background, upper body

1woman, solo, age 48, Japanese office administrator, mature face, subtle crow's feet, fine under-eye lines, short neat dark brown hair with slight gray at temples, practical bob or low ponytail, average build, not glamorous, not cute

wearing charcoal gray cardigan or blazer over cream blouse, simple office slacks or skirt, conservative work clothes slightly worn from real use

seated at a plain desk, upright calm posture, shoulders level, looking slightly down at hands or screen, hands in lower frame

same rough sketch style as slice-of-life manga reference, imperfect lines, NOT smooth digital rendering, NOT idol anime
```

### 表情プロンプト（〜100 words）

```
neutral calm face, eyes half-lidded but attentive, mouth closed, no smile, no anger, emotionless professional mask, tiny tired shadows under eyes, eyebrows relaxed, gaze directed at tablet or papers — not at viewer, silent judgment without expression
```

### 小道具プロンプト（〜100 words）

```
slim tablet with stylus in hand, screen shows faint grid UI with one teal highlight line or one highlighted cell, stack of clipped printouts on desk, optional navy lanyard ID badge, smartphone face-down, papers neat not messy
```

### ネガティブプロンプト

```
teenage, young face, idol, kawaii, glam makeup, sparkling eyes, heavy blush, long flowing hair, cleavage, fantasy costume, smooth glossy skin, deformed hands, extra fingers, English text on screen, bright saturated colors
```

### 差分用（短く）

**電車＋競馬新聞ギャップ：** `evening train interior blurred, holding folded newspaper, pencil in hand, newspaper edge with handwritten marks, same woman age 48, same hair, tired eyes focused on paper, no tablet`

---

## 使い方メモ

1. まず **コア＋表情＋小道具** を1回に分けず、**コアのみ** → 良ければ **表情** 足す → **小道具** 足す、の順でも可。  
2. タブレットの文字は英語になりやすい → **画面はぼかす／アイコンとグリッドだけ** にすると事故が減る。  
3. 「圧」が弱いときは **カメラを少し上から**＋**目線を画面固定** を試す。

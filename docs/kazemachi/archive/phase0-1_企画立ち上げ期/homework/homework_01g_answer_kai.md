# 宿題①g — フジさん（記録係）プロンプト回答

> 【カイ】中心。ユキ・レイの観点は短く併記。  
> 依頼: `homework_01g_fuji_prompt.md`

---

## 質問への回答（短く）

### 1. フジさんの「記号」（小道具）は何か？

**タブレット＋「成績表グリッド」＋1行だけのハイライト。**

理由はシンプルで、フジさんの仕事は「予想」じゃなく **記録と照合** だから。  
ナルミのPCが「今を計算する」なら、フジさんの画面は **「過去が並んでいる」**。

補助記号としてはこれが強い。

- 薄いバインダー or 二つ折りの **印刷したランキング表**（角が折れてる）
- **色付きインデックス**（付箋ではなく、事務の「区切り」の付箋）
- 胸ポケットの **細いボールペン**（安物でいい。プロっぽい）

競馬新聞は **ベース画像では出さない**。ギャップ用の別カット専用。

---

### 2. フジさんの「1色」は何か？

おすすめは **画面の1行ハイライト＝アンバー／琥珀色（くすんだ金）**。

- MCの水色＝組織・現場の空気  
- ゲンの赤＝人間の手で丸した「注目」  
- フジさんのアンバー＝ **システム上の「要確認」**（冷たいが正しい）

別案として **ティールグレー**（UIの行背景だけ）もアリ。  
どっちかに統一して、**画面の中でその1色だけが目に入る**ようにする。

---

### 3. 48歳女性をAIに描かせる時の注意点

**「年齢数字」だけ足すと失敗しやすい。** セットで入れるのがコツ。

- **役職語**: `veteran office coordinator`, `admin lead`, `not glamorous`, `not a model`
- **肌**: `subtle crow's feet`, `natural skin texture`（やりすぎ禁止）
- **髪**: `practical short haircut`, `dark brown`, `no trendy idol bangs`
- **服**: `muted navy cardigan`, `simple blouse`, `no jewelry except watch or thin ring`
- **禁止**: `cute`, `schoolgirl`, `beauty influencer`, `heavy makeup`, `grandma stereotype`, `deep wrinkles`

「おばさん／お姉さん」という言葉より、**仕事の型**で中年を作る。

---

### 4. MCとの関係性が見た目で伝わる工夫

**同じ「番組スタッフの制服ルール」＋「色の序列」。**

- **同型の名札・ランヤード**（色はフジさんだけワンランク濃い／またはストラップ色だけ違う）
- **シャツの系統は近い**（水色＝マキ、フジは **紺灰＋白ブラウス** で一段落ち着く）
- **フジさんだけクリップボードがない／タブレットが主** → マキは進行、フジは記録
- 並べた時、**フジさんの方が肩のラインが安定**（マキはやや細く見える）

「先輩」は顔じゃなく、**装備の貫禄**で出すのが安全。

---

## 専門視点（短く）

### カイ（構成・テンポ）

「圧」は **デカさ** じゃなく **静止** で出る。  
5人並べた時、フジさんだけ **一番動いてない** と勝つ。

シルエットは **縦長のブロック**（肩が安定、裾が広がらない）。  
ソラの前のめり、ナルミの細い前傾、マキの書類だらけと並べると、フジさんだけ **重い柱** に見える。

---

### ユキ（感情）

「淡々」と「怖い」の同居は、**目だけ止まってる**のが一番ラク。  
口は直線、目は **相手の数字を見てる目**。

好感の一要素は **冷たい人間味** じゃなく、**手元の丁寧さ**（画面の行を指でなぞる、ペンキャップをちゃんと閉める）。

---

### レイ（仕掛け）

- タブレットに **小さすぎて読めないが列は分かる表**＋ **1行だけ色**
- 手元メモに **日付だけ**（レース日が後から照合できる）
- バインダーの背表紙に **番組略称**（読めなくていい。存在が効く）

ARGにしない。**キャラの仕事の結果として自然に写る情報**に留める。

---

## 画像生成プロンプト（英語・語数制限付き）

### コアプロンプト（200語以内）

```text
manga-influenced anime, sketchy pen linework, flat color, low saturation, muted tones, plain white background, waist-up portrait, same art style as a slice-of-life TV staff reference

one woman, 48 years old, Japanese, veteran office coordinator, calm professional presence, not glamorous, not cute, not a model, medium build, upright quiet posture, practical short dark-brown hair, subtle crow's feet, minimal makeup, natural middle-aged face

outfit: muted navy or charcoal cardigan over light gray blouse, simple lanyard ID badge, small wristwatch, no flashy jewelry, sleeves neat, office veteran look

pose: standing or sitting at a plain desk edge, shoulders stable, hands calm — she looks like someone who manages records all day, body language heavy and still, reads as "pressure" in a lineup

silhouette: vertical block, stable shoulders, not frilly, not youthful

match MC/Sora line quality: rough imperfect lines, not glossy, not smooth digital airbrush
```

**語数**: 約 150 語（目安）。

---

### 表情プロンプト（100語以内）

```text
expression: neutral office calm, mouth nearly flat, not smiling warmly, not angry, not shocked. eyes steady, quietly observant, direct gaze as if auditing numbers. micro-detail: slightly raised inner eyebrow, subtle "I remember your past mistake" tension. no big emotion, no anime sparkle eyes. unsettling calm authority without shouting.
```

**語数**: 約 70 語。

---

### 小道具プロンプト（100語以内）

```text
props: slim tablet held or resting on desk, screen shows a simple spreadsheet-like grid of tiny numbers, ONE row highlighted in muted amber/gold as the only warm accent. optional thin binder with printed ranking sheets, neat paper edges, index tabs. slim ballpoint pen clipped to cardigan pocket. no racing newspaper in this base image.
```

**語数**: 約 65 語。

---

### ネガティブプロンプト（任意）

```text
young girl, moe, idol face, big sparkly eyes, heavy makeup, glamorous, low neckline, school uniform, extreme wrinkles, walking cane, grandmother stereotype, shonen action lines, bright saturated colors, glossy skin, western CEO suit only, messy anime hair drills, cleavage, selfie pose
```

---

## 生成の回し方（運用メモ）

1. **コア** だけで体型・服・画風を固定  
2. **表情** を2〜3パターン（無表情／ほんの少し目線だけ／指が画面に触れる瞬間）  
3. **小道具** で画面の琥珀1行を固定  
4. ギャップ用は別生成：**電車内・競馬新聞に書き込み**（ベースと混ぜない）

---

## この一言（カイ）

フジさんの絵は「強そう」より **「動かない」** が正解。  
**止まってる人が一番怖い。** それが「圧」。

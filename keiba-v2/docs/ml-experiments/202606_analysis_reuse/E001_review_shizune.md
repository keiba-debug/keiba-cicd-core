# E-001 品質メタ標準化 仕様書レビュー（シズネ / Session 152 / 2026-06-12 改訂2版）

> 対象: `E001_quality_meta_spec.md`（Session 152 草案）
> レビュアー: シズネ（運用・リスク視点の独立レビュー）
> 裏取り: 実物JSON 7本 + 算出スクリプト 7本 + web/ML読み手 2本を確認済み。引用はすべて `file:line`。
> 改訂2版での変更: 同日再点検で **B-4（prior デフォルト、旧S-1から昇格）/ S-12（精度≠妥当性原則）を追加**、S-2（連続量スケール）/ S-7（horse_stats スコープ・サイズ）/ 出口妥当性（正規化指標）を増強。

## 結論（冒頭3行）

**方向性に賛成、ただし仕様確定前に直すべき blocker が4件**。①quality が「どの指標のCIか」を持たない、②「率×n で hits 復元」は血統条件別では数学的に誤り（ベイズ事後平均のため）、③IDM の algo=bayesian は適用不能（連続量）、④prior Beta(1,12) の一律デフォルトは「踏襲」ですらなく、Phase 1 対象指標で系統バイアスを生む。
4判断は (a)条件付き採用 / (b)却下→指標別 prior に再設計 / (c)却下→CIベース判定へ置換提案 / (d)条件付き採用（3条件付き）。
件数: **🔴 4 / 🟡 11 / 🟢 7**。

## 良い点（先に言っておきます）

- `quality` 入れ子で既存キーと衝突回避（§2）— 後方互換の基本姿勢として正しい
- `algo` 明示で「率のCI」と「平均のCI」の取り違え防止（§2）— これは良い設計です
- 純関数ヘルパ + pytest（§4）、実装を E-010 に分離（§7）— Goal-driven の作法に適合
- `year_rates` 無しを `insufficient` とし「安定と誤読させない」（§3）— 私が言いたいことを先回りしている
- 後方互換の実地確認: ML 側 `ml/features/pedigree_features.py:171-177` は明示フィールドリストで `s.get(key)` する設計、web 側 TS interface は構造的型付けで余剰キーを無視。**`quality` キー追加自体で壊れる読み手は確認した範囲では無し**（strict parse/Zod 不使用）

---

## 🔴 blocker（仕様確定前に直すべき）

### B-1. quality が「どの指標の CI か」を特定できない — E-002 誤用に直結

§2 スキーマは1エントリ1 `quality` だが、**実物のエントリは複数の率を持つ**:

| 分析 | 1エントリ内の率 | 実物根拠 |
|---|---|---|
| 調教師 | `win_rate` + `top3_rate`（lift は top3 基準） | `trainer_patterns.json` best_patterns / `analysis/trainer_patterns.py:375-382` |
| 出遅れ | `slow_start_rate` + `top3_rate_when_slow` + `top3_rate_normal`（分母が全部違う） | `builders/build_slow_start_analysis.py:254-268` |
| 騎手接戦 | `close_win_rate` + `win_rate` + `top3_rate` | `jockey_close_finish.json` ranking |
| 調教分析 | `win_rate` + `top3_rate` + `top5_rate` | `analysis/training_analysis.py:195-202` |

このまま実装すると、E-002 が「出遅れ率の CI」を「出遅れ時複勝率の判定」に使う類の誤用を**スキーマが防げない**。さらに出遅れの `top3_rate_when_slow` は分母が `len(fps_slow)`（完走のみ、`build_slow_start_analysis.py:263-264`）で `slow_starts` と一致せず、n の取り違えも起きる。

**修正案（§2）**: quality に `"metric": "top3_rate"` を必須フィールド追加し、Phase 1 は「分析ごとに主要指標1つ」を §5 の表に列として明記（調教師=top3_rate、出遅れ=slow_start_rate、血統=top3_rate、接戦=close_win_rate）。複数指標が必要になったら `"quality": {"top3_rate": {...}}` の指標名キー形式に拡張。

### B-2. 「率×n で hits 復元」は設計として破綻している — builder 改修に置換すべき

§5 の 3a/3b「率×nで復元」は2つの理由で危険:

1. **生カウントは builder の手元に既にある。捨てているだけ**。`analysis/trainer_patterns.py:362-364` は `p_wins`/`p_top3`/`p_n` を算出済みで、出力時に率へ丸めて捨てている（`:375-382`）。`analysis/training_analysis.py:189-191` も同様（`wins`/`top3`/`top5` を持ちながら `:195-202` で率のみ出力）。復元などせず**出力に1行足すのが正道**です。4桁丸めの逆算は trainer の n≤4,000 なら概ね正確（誤差 < n×5e-5 + 0.5）だが、丸め桁数や n の増加で**静かに壊れる**設計を選ぶ理由がありません。
2. **血統の条件別は復元式そのものが違う**。`sire_stats_index.json` 実物で検算済み: `top3_rate=0.1867 = (207+2.5)/(1112+10)`（ベイズ事後平均、`builders/build_sire_stats.py:439-440`）。条件別（`fresh_top3_rate` 等）は**ベイズ済み rate のみ出力で生 hits が無い**（`build_sire_stats.py:446-459`）。`hits = rate×n` ではなく `hits = rate×(n+α+β) − α` でないと復元できず、4桁丸めで誤差も乗る。仕様はこの事実に未言及で、実装者が `rate×n` で書くと**静かに間違った CI** が量産されます。

**修正案（§5・§6）**: 「率×n復元」を全廃。Phase 1 の前提タスクとして「builder 改修（生 hits/n の出力追加）」を明記 — trainer_patterns.py / training_analysis.py / build_sire_stats.py（条件別 `fresh_top3` 等の生カウント）。いずれも数行の改修で、6/5 に全 builder の再実行実績があり（JSON mtime 確認済み）再生成コストは低い。

### B-3. IDM の CI algo「bayesian」は適用不能 — 率が存在しない

§5 #2 は IDM の hits/n を「winner/horse」、algo を「bayesian」とするが、`winner_count/horse_count` は「IDM保有勝ち馬数/IDM保有全馬数 ≈ 1/頭数」＝**レース構造で決まるほぼ定数**であって、信頼区間を出したい量ではない。IDM 分析の中身は `winner.mean/stdev`・`all.mean/stdev` の**連続量**です（`analysis/idm_standards.py:229-254`、`idm_standards.json` 実物確認: G1_古馬 winner.mean=75.87, stdev=2.87, winner_count=46）。Beta-Binomial を当てる二項試行がそもそも無い。

**修正案（§5 #2・§6 Phase 3）**: IDM の algo を `mean_se`（対象: `winner.mean` を主、n=winner_count）に変更。「IDM を bayesian + entry-level granularity」（Phase 3）の bayesian も削除し、RPCI と同じ「基準値の推定誤差」系に統一。

### B-4. 事前 Beta(1,12) の一律デフォルトは「踏襲」ではない — Phase 1 対象指標で系統バイアス（旧S-1から昇格）

- 踏襲元 `builders/build_sire_stats.py:39-43` は**既に2種を使い分けている**: win 用 Beta(1,12)（mean≈0.077）と **top3 用 Beta(2.5,7.5)（mean=0.25）**。「既存からの踏襲」と言うなら踏襲すべきは「**prior mean ≒ 指標の全体ベース率、prior strength ≒ 10〜13走分**」という設計哲学の方です。§3 の表と §4 シグネチャの `prior=(1.0,12.0)` は、仕様の定数そのものが誤りという意味で B-3 と同格。
- Phase 1 の対象指標はほぼ **top3系・接戦勝率・出遅れ率**で、(1,12) を当てた場合の実害（実物で検算）:
  - 接戦勝率: ベース率 **0.5**（`jockey_close_finish.json` summary `overall_close_win_rate: 0.5` — 接戦=2頭の競り合いでどちらかが勝つ構造上 0.5 が基準）。rank1 田山旺佑 10/13=0.769 が事後 mean (10+1)/(13+13)=**0.423** に潰れ、ベース以下に**反転**。
  - 出遅れ率: ベース率 0.216（33,749/156,038、`slow_start_analysis.json` coverage）。(1,12) は 0.077 へ強制的に引き下げ。
  - 小標本ほど 7.7% へ誤収縮＝**低信頼データほど系統的に過小評価**で、E-002 の減点と同方向に二重で歪む。
- さらに prior 定数は `ml/features/pedigree_features.py:19-26` に**複製**が存在（"same as build_sire_stats.py" コメント付き）。E-001 で prior を整備するなら `quality_meta.py` に一元化し両者が import する構成にしないと、将来の変更で乖離します。

**修正案（§3・§4）**: ヘルパの `prior` デフォルト値を**廃止（必須引数化）**し、§3 に指標別 prior 規定表を追加（win: (1,12) / top3: (2.5,7.5) / close_win: ベース0.5×strength10 ≒ (5,5) / slow_start: ベース率×strength から算出）。汎用則は「α=base_rate×S, β=(1−base_rate)×S, S≈10〜13」。prior 定数は quality_meta.py に一元化。

---

## 🟡 should-fix

### S-2. stability 閾値（絶対0.10/相対20%）は base rate にもスケールにも非対応 — CI ベース判定へ置換（判断 c 関連）

- **率側**: OR 条件のため win 系（ベース≈7%）では相対20%が支配し、**1.4pt の変動で drift 発火**。n=200 でも SE≈1.8% なので 0.8SE のただのノイズで drift 連発。逆に絶対0.10は win 系でほぼ発火せず、どちらに転んでも較正されていない。
- **連続量側（改訂2版で追加）**: algo=mean_se（RPCI、Phase 2-3 で「年別集計要」と stability 適用予定）にこの閾値をそのまま当てると、絶対 0.10 は RPCI スケール（〜51、年平均の揺れは普通に 0.1 超）で**ほぼ常時 drift 発火**、相対 20%（=10ポイント超）は**永久に不発火**。§3 の閾値は率スケール専用で、連続量の判定規則が未定義。
- §4 シグネチャは `year_rates`（率のみ）で**各年の n を受け取れない** → 最小n判定が実装不能。実物では年n が小さい例が普通にある（`slow_start_analysis.json` 武士沢友 2022年 total=4、`jockey_close_finish.py:65-68` は年 close_total<5 で `close_win_rate: None` を格納 — null 年のスキップ規則も未定義）。
- 「最新年」は部分年（2026年は1〜6月＝冬春開催に偏る）。さらに S-3 の鮮度問題と交絡（凍結ファイルでは最新年=1〜3月のみ）。

**修正案（§3・§4)**: E-001 はせっかく CI を作るのだから **「最新年率が全期間率の CI95 外、かつ最新年 n ≥ 20」で drift** と定義（恣意定数2つ→最小n 1つに削減、率/連続量とも同一ロジックで動く）。シグネチャは `year_data={year: {hits, n}}` 形式に変更し、None 年スキップを pytest 境界に追加。部分年の注意（季節偏り）を §3 に1行明記。

### S-3. jockey_close_finish.json が 2026-03-17 で凍結 — 「凍結データに stable フラグ」事故の芽

実物 mtime 確認: 他5本は 6/5 更新、**jockey_close_finish.json のみ 3/17**（`analysis-reuse-project` メモリで既知の課題、[[ml-cache-staleness-incident]] と同根）。このまま Phase 1 で品質メタを付けると「3月で止まったデータに stable / ci95 付き」という、信頼を装った不良データが生まれます。これは私が一番止めたい形です。

**修正案（§6 Phase 1 前提条件 + 新§）**: ①Phase 1 着手前に jockey_close_finish 再生成、②全分析 metadata に `coverage: {from_date, to_date}` を必須化（slow_start には既にある。`build_slow_start_analysis.py:313-319`）、③**6分析の再生成を `keiba-data-prep` スキル等の運用に配線する規定**を仕様に1節追加。品質メタは「生成時点の信頼性」しか語れない — 鮮度の担保が無い品質メタは半分しか仕事をしません。

### S-4. 多重比較・勝者の呪いへの対処が無い（依頼観点の通り、実物で裏付け）

- 調教師: 74調教師 × 12パターン（`trainer_patterns.py:177-227`）→ `top3_rate≥0.25 AND lift≥0.05` フィルタ（`:370`）→ score 順 top5（`:385-386`）。**約900比較から上振れだけを選抜**した後の率に CI95 を額面で付けると、CI ごと上にバイアスします（選抜で条件付けた分布の CI ではない）。「n=81・CI付き」が逆に誤った安心感を与える構図。
- 騎手接戦: ranking が**生率降順ソート**（`jockey_close_finish.py:34`）で、rank1 が n=13 の小標本（Wilson CI ≈ [0.50, 0.92]、下限はベース0.5と同値）。上位＝小標本上振れの典型。

**修正案（§2・新§）**: ①quality に `"selected": true`（多数候補からの選抜エントリ）を任意フィールド追加（調教師 best_patterns、接戦 ranking 上位に付与）、②E-002 への申し送りとして「**選抜系エントリは点推定でなく ci95.lower を入力に使う**」を仕様に明記（lower 基準なら勝者の呪いを部分的に相殺できる）、③選抜系は wilson でなく **bayesian（指標別prior）の shrinkage を標準**にして一次緩和、④根治（split-sample / FDR）は Phase 外と明記して expectations を管理。

### S-5. ベイズ済み rate に Wilson CI を混ぜる系列不整合（判断 d の血統に直結）

§5 #5 は血統 baseline を「wilson」とするが、JSON の `win_rate`/`top3_rate` は**ベイズ事後平均**（B-2 で検算済み。win_rate 0.0524 = (58+1)/(1112+13)、raw は 0.0522）。点推定＝ベイズ、CI＝Wilson(raw) だと、小標本で **点推定が CI の外に出る**ケースが構造的に発生します（prior が強く効く側に点が引かれるため）。

**修正案（§3 に整合規則を1行）**: 「**rate がベイズ平滑化済みのエントリは ci95 も同じ事後分布（algo=bayesian_beta_binomial、同一prior）で出す**。点推定と CI の生成系列を混ぜない」。§5 #5 の baseline は wilson→bayesian に変更。あわせて「effective_n は常に raw 観測数 n（n+α+β ではない）」を §3 に明記 — E-002 が「ベイズで縮小済みの値」に「小nだから減点」を重ねる**二重ペナルティ**（CI幅まで使えば三重）の防止注意も §3 に書いてください。

### S-6. IDM fallback 時、quality が自己完結しない

`idm_standards.py:292-297` の fallback は `fallback_from`/`original_sample_count` を**エントリ直下**に置く（実物5件確認: G1_3歳 original 25 / G1_2歳 9 / G2_2歳 9 / G3_2歳 24 / Listed_2歳 6 → いずれもプール統計のコピー）。仕様の effective_n=「代用元n」(=80) だけだと、quality しか読まない E-002 は「G1_2歳 固有の n=80」と誤信し、**実n=9 の借用値が減点を素通り**します。さらに G1_2歳 / G1_3歳 が**同一プール統計のコピー**である事実も quality からは見えない（独立条件と誤解して合算すると二重カウント）。

**修正案（§2）**: quality に `"source": "direct" | "fallback:G1"` を追加し、fallback 時は original n も `"original_n": 9` で保持。

### S-7. §4 の単純 Dict/Array ループでは実物のネスト構造を回れない + 付与スコープ未定義（サイズ影響あり）

- 調教師: `trainers.{code}.best_patterns[]`（Dict→内部Array）
- 調教分析: `overall.by_lapRank.{}` / `by_popularity_bucket.{人気帯}.by_lapRank.{}` / `trainers.{code}.all_patterns.by_final_lap.{}` の3層（`training_analysis.py:418-463, 504-530`）
- 接戦: ranking 内に `close_by_track.{}` / `close_by_distance.{}` のネスト条件別 — 実物に **n=1, rate=1.0** のエントリが存在（田山 intermediate 1/1）。ここに quality を付けるのか付けないのか未規定。
- **（改訂2版で追加）出遅れの「Array(190)」は jockey_ranking のみ**。実ファイルにはほかに **horse_stats 15,208件**（`total_with_hassou=1, slow_start_rate=1.0` のような n=1 が大量）と recent_incidents 33,749件があり、合計 **12.7MB**。全付与なら +数MB＆web パース時間増のうえ、horse_stats はほぼ全件 insufficient になります。RPCI も「Dict(8)」は by_distance_group のみで、実物は `courses`(92) / `by_baba`(169) / `by_distance_group_baba`(16) を持つ4階層。

**修正案（§4・§5）**: 「Dict/Array 両対応」の2分類を捨て、**§5 に分析ごとの「quality 付与対象パス」列を追加**（例: 調教師=`trainers.*.best_patterns[*]`、接戦=`ranking[*]` のみ、出遅れ=`jockey_ranking[*]` のみ（horse_stats/recent_incidents は対象外と明記）、RPCI=4階層のどこまでか明示。ネスト条件別は Phase 2 等）。ヘルパは純関数のまま、walk は各 builder の責務と明記。E-010 完了条件にファイルサイズ増の実測を追加（N-3/N-4 と接続）。

### S-8. 最小 n の既存値が分析ごとにバラバラで、一律 MIN_RUNS_CONDITIONAL=10 と不整合

実物の生成時足切り: 調教師パターン **8**（`trainer_patterns.py:358`）/ 調教分析 **5**（`training_analysis.py:510`）/ 接戦 **10**（`jockey_close_finish.py:22`）/ IDM **10と30**（`idm_standards.py:44,226`）/ RPCI **10**（`race_type_standards.py:172`）/ 血統 **10**（`build_sire_stats.py:56`）。一律10だと「n=5〜9 のエントリが JSON に存在するのに全部 insufficient」（調教分析）や「n=8〜9 の best_patterns が新基準で即 insufficient」（調教師）が起き、web 表示が insufficient だらけになる分析が出ます。意図的ならそれで構いませんが、**仕様に対応表が無いと実装時に混乱**します。

**修正案（§3・§4）**: ヘルパに `min_n` 引数を追加し、§5 の表に分析別 min_n 列を追加（既存足切りと揃えるか、引き上げるなら「既存エントリの何%が insufficient になるか」を E-010 で計測して判断）。

### S-9. 既存の `confidence` フィールド（high/medium/low）との関係が未規定

`training_analysis.py:205-211` の `compute_confidence`（n≥50 & lift≥0.05 → high 等）が既に存在し、web の型にも入っています（`web/src/lib/data/trainer-patterns-reader.ts:25` `confidence: string`）。quality 導入後、「confidence=high なのに ci95 が広い」という**矛盾表示**が出る経路があります。

**修正案（新§ or §2 注記）**: 「既存 confidence は quality 導入後 deprecated（E-006 の信頼度ヘッダで置換、表示は quality 由来に統一）」の方針を1行。削除はせず読み手の移行を E-006 で。

### S-10. RPCI: ci95 をどの平均に付けるか不明 + 対象セクションのスコープ曖昧（判断 a 関連）

- `analysis/race_type_standards.py` `calculate_course_stats` は `mean` と **`weighted_mean`（直近2年×2重み）** を併出力し、運用閾値 `thresholds` は **weighted_mean ± 0.5σ** 基準（sustained/instantaneous の式を実コードで確認）。§3 の `mean ± z·stdev/√n` は単純 mean 基準なので、**CI と運用値の基準がズレる**。weighted に付けるなら SE=√(Σw²σ²)/(Σw)、effective_n=(Σw)²/Σw² の規定が必要。
- IDM「Dict(20)」= by_grade のみ? **`by_race_name`（重賞別、count=2〜4 の極小サンプル）こそ品質メタが要る場所**です（`idm_standards.py:308-354`、実物で count=2〜4 を確認）。
- なお thresholds は mean±0.5σ 由来なので、mean の CI だけでは **threshold 自体の不確実性は表せない**点も §3 に注記を。

**修正案（§3・§5）**: ①RPCI の ci95 は weighted_mean 基準と明記し weighted SE 式を §3 に追加（または「CI は mean 基準・thresholds とは別物」と明示的に割り切る）、②§5 の形式列を「対象セクション」列に差し替え（S-7 と同件）。

### S-11. schema_version が Phase 4 では遅い

quality の有無・形式が Phase 1〜3 で段階的に変わるのに、識別子が Phase 4 まで無い。読み手（E-002 実装）が「この JSON は quality 付きか」を判別する術が mtime しかなくなります。なお `sire_stats_index.json` のトップは `meta`（`metadata` でない）— 命名ぶれの吸収方針も同時に。

**修正案（§6）**: `metadata.schema_version`（例 "quality_meta/1"）を **Phase 1 の出力から**付与。コストはほぼゼロです。

### S-12. quality は「精度」のメタであり「妥当性（bias）」を保証しない — 原則の明文化（改訂2版で追加）

実例: `builders/build_slow_start_analysis.py:117-119` は hassou コメントが無いレースを**スキップ**するため、slow_start_rate は**カバレッジ条件付き率**（jockey_ranking 上位で 0.45 と高率なのはこのため）。ここに ci95 を付けても**分母の選択バイアスは1ミリも直らない**のに、E-006 で「CI付き＝信頼できる数字」と誤読される経路ができます。S-4（選抜バイアス）・S-3（鮮度）と合わせ、「quality があれば安心」という**人間側の形骸化**こそ私が警戒する点です。

**修正案（§1 or §2 に原則1行）**: 「**quality は精度（precision）のメタであり、妥当性（bias・分母定義・選抜・鮮度）は保証しない。分母定義は各分析の責任**」。E-006 のヘッダ文言設計時の事故防止にもなります。

---

## 🟢 nice-to-have

- **N-1**: mean_se の z=1.96 は n<30 で過信（n=10 なら t=2.26、CI が13%狭く出る）。`min_n` 近傍は t 分布 or 注記。
- **N-2**: RPCI は同日同コースのレースが馬場状態で相関し独立性仮定が崩れ、SE がやや過小。注記で十分。
- **N-3**: E-010 完了条件に受け入れ基準を追加 — 「対象エントリの quality 付与率 100% / ci95 null 率 ◯% 以下/ファイルサイズ増分を実測レポート」。Goal-driven の verify loop に乗せる。
- **N-4**: sire_stats_index.json は 4.3MB で sire/dam/bms 合計が万単位。全エントリ +quality(~100B) でサイズ数MB増。**dam/bms も Phase 1 対象か**の明示と概算を §5 に。
- **N-5**: 出遅れの `top3_rate_when_slow` 分母（完走出遅れ数）を builder で `n_slow_finished` として明示出力（B-1 の n 曖昧性の根治）。
- **N-6**: 接戦 ranking の `rank` 自体が生率ソートのまま残る。E-006 で「wilson lower 基準の並べ替え表示」を提案（rank1 n=13 の見栄え問題の出口）。
- **N-7**: bayesian の 2.5/97.5%ile は scipy.stats.beta.ppf 依存。スリム venv に scipy が入っているか確認（sklearn 依存で入っているはずだが、E-010 の実装ノートに1行）。

---

## 4設計判断への回答

| 判断 | 結論 | 理由（要点） |
|---|---|---|
| **(a) RPCI を mean_se** | **条件付き採用** | 連続量に正規近似 SE は標準的で、n≥10 足切り済み・分布単峰（実物: Dirt_1200m- n=2789, mean51.89, σ1.06）なので成立。条件: ①「基準値（平均）の推定誤差」であり「レース毎のばらつき(σ)」ではないと §3 と E-006 表示語彙で明文化（n=2789 だと CI 幅 ±0.04 と極狭になり「このコースは安定」と誤読される）②weighted_mean との基準統一（S-10）③n<30 は t 分布（N-1）。なお RPCI baseline の CI はほぼ常に極狭で E-002 的な情報量は小さい → Phase 3 後回しの現配置は妥当 |
| **(b) Beta(1,12) 踏襲** | **却下 → 指標別 prior に再設計** | (1,12) は win 率専用。既存実装自体が top3 に (2.5,7.5) を使い分けており（build_sire_stats.py:39-43）、「踏襲」するなら**設計哲学（prior mean=ベース率, strength≈10-13）の方を踏襲**すべき。接戦（ベース0.5）に当てると 0.769→0.423 の破壊的バイアス（実物検算済み）。デフォルト引数廃止+指標別規定表+定数の一元化が条件（B-4） |
| **(c) 閾値 絶対0.10/相対20%** | **却下 → CI ベース判定へ置換** | base rate 依存で win 系は相対20%が0.8SE程度のノイズで発火（誤検知過多）、絶対0.10は発火不能。連続量(RPCI)では逆に絶対0.10が常時発火・相対20%が永久不発火で、**どのスケールでも較正されていない**。カカシ先生自身「やや恣意的」と認めている通りで、E-001 で CI を作る以上「最新年率が全期間 CI95 外 ∧ 最新年 n≥20」にすれば恣意定数が消え、率/連続量でロジックも一本化されます（S-2）。シグネチャの year_rates に n が無い穴も併修 |
| **(d) Phase 1 = 4分析** | **条件付き採用** | 絞り自体は正しい（出遅れ・接戦は生カウント+year_stats 完備で即可）。条件3つ: ①**jockey_close_finish の再生成を前提条件に**（3/17凍結のまま品質メタを付けない、S-3）②調教師は「率×n復元」でなく builder 改修（生カウントは手元にある、B-2）③血統 baseline は wilson でなく bayesian（rate と CI の系列整合、S-5）。加えて選抜系（best_patterns/ranking）は shrinkage 標準を推奨（S-4） |

## 出口妥当性（E-002 から見て足りるか）

- **足りるもの**: ci95（幅・下限）、effective_n、algo。減点の主材料は揃う。
- **欠けるもの**: ①どの指標の CI か（B-1・最重要）②選抜エントリの識別（S-4）③fallback の自己完結情報（S-6）④**algo 横断の正規化**: ci95 の意味が algo 依存（率の幅0.2 と RPCI 平均の幅0.2 は別物）なので、このままだと E-002 が分析ごとの if 分岐だらけになる。横断で使う正規化値（例: `rel_width = (upper−lower)/指標スケール`、または `tier: high|mid|low` の導出規則表）を仕様に置くと、E-006 のヘッダ表示もそのまま使える。
- **過剰/未接続**: stability_flag は E-002 の減点でどう使うか未定義（drift をどう点数化する？）。実態は E-006 信頼度ヘッダ向けの情報です。仕様に「**E-002 は ci95 + effective_n + metric だけで動ける。stability は E-006 向け**」と依存関係を1行書くと、Phase 1 の出口が軽くなります。
- **推奨**: E-002 の想定演算を仕様に1行例示（例: 「補正率 = ci95.lower を採用」or「減点係数 = f(CI幅)」）。これが無いと E-001 の completeness を検証できません（success criteria 不在）。あわせて「**平滑化済み点推定の分析では effective_n による追加減点をしない**」（S-5 の二重〜三重補正防止）をこの節に集約。

## 仕様の修正箇所サマリ（カカシ先生の取り込み用）

| セクション | 修正 | 対応指摘 |
|---|---|---|
| §1 or §2 | 原則1行「quality は精度のメタ、妥当性(bias)は保証しない」 | S-12 |
| §2 | `metric` 必須追加 / `selected` 任意追加 / `source`+`original_n`（fallback）追加 | B-1, S-4, S-6 |
| §3 | IDM=mean_se に変更 / prior 指標別規定表 / 「ベイズ済み rate は CI もベイズで」整合規則 / effective_n=raw n 明記+二重減点注意 / stability を CI ベース判定に書換（率/連続量共通） / weighted SE 式 / 部分年・null年注意 | B-3, B-4, S-5, S-2, S-10 |
| §4 | prior デフォルト廃止（必須引数化） / `min_n` 引数 / `year_data={year:{hits,n}}` / Dict/Array 2分類→パスwalk は builder 責務 | B-4, S-8, S-2, S-7 |
| §5 | 「率×n復元」全廃→builder改修列に / 血統 baseline=bayesian / IDM=mean_se / 「対象パス」「主要metric」「min_n」列追加 / 出遅れ=jockey_ranking のみ（horse_stats対象外）明記 / RPCI 4階層・by_race_name・dam/bms の対象可否明示 | B-2, S-5, B-3, B-1, S-7, S-8, S-10, N-4 |
| §6 | Phase 1 前提に「jockey_close_finish 再生成」「builder 生カウント改修」/ schema_version を Phase 1 へ前倒し / 運用配線（data-prep）規定の新設 | S-3, B-2, S-11 |
| §7 | 完了条件に「E-002 想定演算の1行例示」「E-010 受け入れ基準（付与率/null率/サイズ増）」 | 出口妥当性, N-3 |
| 新設 | 「E-002 連携」節: 正規化指標（rel_width or tier 導出表）/ stability は E-006 向けの線引き / 平滑化済み分析への effective_n 追加減点禁止 / selected・proxy の扱い | 出口妥当性, S-4, S-5, S-6 |

## ふくだ君に確認したい論点

1. **Phase 1 の主要 metric をどれにするか**（B-1 の帰結）: 調教師=top3_rate、出遅れ=slow_start_rate、血統=top3_rate、接戦=close_win_rate で仮置きしましたが、E-002 の減点が見る指標と一致させる必要があります。買い目判断で効かせたいのはどの率ですか。
2. **jockey_close_finish の再生成と運用配線**: 元データの更新を含め、6分析の再生成を keiba-data-prep（週次）に入れますか。入れないなら「品質メタ付きだが鮮度不明」が常態化します — 私はそれを良しとしません。
3. **E-002 の減点は何を主役にしますか**: CI幅・effective_n・stability を全部掛けると、血統のように（事後平滑化＋CI幅＋小n減点の）三重補正で小標本が沈み過ぎ、**妙味（過小評価馬）を自分で消す**方向に働きます。私は「ci95.lower（または tier）一本＋proxy/selected フラグで個別係数」を推します。

---

*レビュー方針メモ: 本レビューの指摘はすべて実物（JSON 7本・スクリプト 7本・読み手 2本）で裏取りした事項のみ。未確認の憶測は含めていません（[[feedback_no_fabricated_tool_results]] 準拠）。改訂2版は同日の独立再点検（2nd pass）との統合版で、両パスで一致した指摘はそのまま、新規発見4点を追加しています。*

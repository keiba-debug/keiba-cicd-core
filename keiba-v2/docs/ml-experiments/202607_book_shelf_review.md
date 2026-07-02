# 競馬書籍まとめ 棚卸し + 立川ラベル検証 v0（Session 185）

作成日: 2026-07-02
目的: `E:\share\FBiz\projects\local-llm\vlm-test\notes\shots` の書籍digest（競馬12冊）を再点検し、
①どこまでシステムに消化済みか ②未消化でバージョンアップに繋がる発見は何か を確定する。
後半は、その場で実施した **立川レース質マトリックス理論の収益検証 v0** の結果（本レビューの主要な実測成果）。

関連正本: `docs/regulus/sources/00-05`（5冊のML特徴量spec） / `docs/market_calibration_edge_map.md` /
`docs/ml_profit_roadmap_202607.md` / `docs/ml-experiments/202607_training_eval_book_review.md`（調教本・同日作成）

---

## 1. 消化状況マップ（結論: 主要5冊は読了・spec化・大半は検証済み）

主要5冊（レース質マトリックス 正/実践・上がりXハロン・双馬式展開読み・みねた前走位置取り）は
S177 で `docs/regulus/sources/` に spec 化済みで、Regulus プロジェクトの源流資料だった。

| 書籍の知見 | 消化状況 |
|---|---|
| クッション値・含水率・初角距離・直線長（レース質§馬場/コース） | ✅ 実装済み（`baba_features.py`・experiment 投入済み） |
| front_ratio・逃げハサミ（みねた§1,3） | ✅ S177 実装（`ml/nova/context_features.py`）→ **OP+ で生足し効果なし** |
| 能力3軸 テン力/上がり/持続（上がりX§1 + 双馬） | ✅ JRDB 指数（ten_idx/agari_idx/front_3f）で `leg_profile.py` 本番化。lap 再構成は「JRDB IDM が既により正確に実施済み」と結論（v9.x phase0 §6） |
| IDM 軌跡の文脈掃除・反レース質（実践§8） | ❌ B/B' 計3回 NO-GO（IDM 既掃除 R²0.9999・S179/S183） |
| 調教タイムの読み方 | ✅ レビュー済（202607_training_eval_book_review.md・新規性=CHA テンFのみ） |
| 妙味度名鑑 2026 | 別プラン進行中（memory: myomido-meikan） |
| 単勝という哲学 / 競馬を読む力 | 哲学・心理系。tansho-central 方針と整合、特徴量なし |
| 血統ビーム vol4 / スマート出馬表（亀谷） | 人気ランク・血統国別。血統集計は既存、亀谷「人気ランクD妙味」は市場較正の実測と矛盾しない範囲で消化済み扱い |

## 2. 未消化の発見（バージョンアップ候補・優先度順）

### A. ★検証場所の間違い疑惑 — 書籍特徴量群を C-3（未勝利/条件 specialist）の材料に
書籍由来特徴量の NO-GO は**全て 3歳上芝OP+**（市場最シャープ・IDM 情報天井）での結果。
エッジ実在地の**未勝利/条件**（市場緩い×過去走1-3本で IDM 薄い＝craft の限界価値最大）では未検証。
`docs/regulus/sources/` の特徴量カタログはそのまま C-3 の材料表として再利用する。
検証規律は [[feedback_train_scope_not_match_eval]]（幅広学習×適用絞り・同一 test 対照）。

### B. ★予想ペース指数（レースレベル展開）= Eclipse v3 + 共有部品化
- `features.md` に「予想ペース指数｜優先度高｜未」として明文化済みの宿題。
- 材料の JRDB KYI `pred_ten_idx`/`pred_pace_idx`（事前予想指数）は build_jrdb_index で index 化済み・未使用。
- **Eclipse の現ペース指標（senkou_ratio/pace_pressure）は過去走通過順由来** = 双馬式が批判した当のやり方。
  ten_idx 系（テン持ちタイム相当）で置換/補強 → Eclipse v3。
- その過程で pace_scenario（想定隊列・ペース圧力）を共通部品に切り出し、
  A-4 荒れ度 → D-3 レース選定層（降りる判断）・Web 展開図（残対応「SED通過順位活用」）へ配る。
- §4 の立川検証の帰結（style軸=Eclipse が上位互換）とも合流 → **次の本命タスク**。

### C. 風バイアス — 唯一の完全新データ源
直線方位×当日風向（気象API）。JRDB/mykeibadb に無い情報なので、
A-1 受け入れ試験ベンチ（`--market-offset` で BestIter>1 か20分審判）の最初の被験者に適する。

### D. 枠バイアスの非定常対応（frame_bias_3yr）
実践編§4 の最重要警告「枠バイアスは経年で符号反転（東京芝 2018-20内→2021-外）」。
コース辞典 CSV が固定長期集計なら近3年ローリング版に分割する。小粒・確実。

### E. 小粒バックログ
- 新馬戦 上がり2F≤22.5「名馬の証」フラグ（roadmap C-4 新馬非市場情報の具体案）
- 延長血統×ローテ交互作用（ext_pedigree_score）
- JRDB CHA テンF 特徴量化（調教本レビューの結論・同日 doc 参照）

---

## 3. 立川ラベル検証 v0 — 設計

**問い**: レース質（枠/脚質の有利属性）と pick 属性の一致は、gap単勝/EV単の成績を説明するか。

- データ: `df_test_danger.pkl`（test 3653R・2025.05-2026.05 OOS・S173 と同一）
- v0 ラベラ（全て事前計算可能・リーク無し）:
  - `rq_pace`: メンバー先行率 front_ratio（JRDB脚質1/2 or 前走初角前方）… みねた閾値 <30%=slow / >40%=high
  - `rq_style`: pace ± クッション値（芝: ≥11超高速→差し寄り・≥10×短直線→先行）± 含水率（ダート: ≥10→先行・≤6乾燥→差し）
  - `rq_frame`: 初角距離 ≤350m=内 / ≥500m=外
  - 馬側: JRDB脚質→先行/差し、枠=双馬式（1-3内/6-8外）
  - `rq_match` = style一致±1 + frame一致±1
- picks: gap≥5単勝（n=775）/ gap≥3（n=2120）/ EV本命単 rank_w=1×EV≥1（n=1769）
- 検定: match−mismatch の ROI 差を picks 間並べ替え 2000 回で null 化
- スクリプト: `C:/tmp/{tachikawa_v0,tachikawa_v0_acc}.py`（使い捨て）

## 4. 立川ラベル検証 v0 — 結果

### 4.1 収益価値: 検出されず（方向はむしろ逆・非有意）
| picks | match | neutral | mismatch | ROI差検定 |
|---|---|---|---|---|
| gap≥5単勝 n=775 | 99.0% | 77.6% | **123.5%** | P(null≥obs)=0.69 |
| gap≥3単勝 n=2120 | 79.4% | 68.7% | 104.6% | P=0.89 |
| EV本命単 n=1769 | 90.4% | 74.8% | 83.9% | P=0.32 |

- 「レース質一致で買う」は不成立。レース質は公開情報の組み合わせ＝市場が織り込む。
  非有意ながら mismatch 側が良い傾向は「市場に嫌われた不一致にこそ乖離が残る」という
  市場効率のいつもの構図と整合（ただし主張しない・ノイズの範囲）。
- 全馬レベルでも一致度別の top3 率リフト無し（match 20.5% vs mismatch 22.6%）。

### 4.2 予報精度: v0 ラベラは style 軸で答え合わせに負けている（逆相関気味）
事後の実測バイアス（3着内馬の先行率リフト = style_bias / 内枠率リフト = frame_bias）と突合:

| 予報 | 実測 style_bias | 先行決着率 |
|---|---|---|
| front 予報 n=1378 | +0.075 | 50.4% |
| closer 予報 n=1778 | **+0.100** | **63.3%** ← 逆 |

- 主因: **みねた式 front_ratio→決着の関係が素朴な形では実測不成立**
  （>40%帯の実測 style_bias +0.098 vs <30%帯 +0.067 = 理論と逆方向）。
- frame 軸（初角距離→内外）は方向正しいが微弱（in +0.002 / out −0.030）。
  かつ first_corner_dist・wakuban は既にモデル入力済み＝GBDT が学習済み。
- 全体基調: style_bias 平均 +0.094（競馬は常態で先行有利）/ frame_bias ≈ 0。

### 4.3 結論と「独自に成熟」の道筋
1. **本の閾値をそのまま移植したルールエンジンは、予報としても収益文脈としても不成立**（v0 実測）。
   ルール表を磨く方向は筋が悪い。
2. **レース質の「独自成熟」の正体 = race-level 学習モデル群**:
   - style 軸は **Eclipse（closing_race_proba）が既に上位互換**として存在（立川4軸の1軸は成熟済みだった）
   - frame 軸（内外決着予測）は不在 → 今回作った実測 frame_bias を目的変数に Eclipse の兄弟モデルとして新設可能
   - §2-B の ten_idx 系ペース入力強化（Eclipse v3）と同一ロードマップに合流
3. **答え合わせ指標（実測 style_bias / frame_bias）が本レビューの再利用可能な成果物**。
   「レース質予報 → 回顧で採点」のループの採点関数がこれ。出馬表表示（推理エンタメ・表示専用）はこの上に乗せる。

---

## 5. Eclipse v3a ablation — 実施済み・NO-GO（同日 S185 実施）

§2-B の第一手として、KYI 事前予想指数のレース集約 11 特徴量
（eten_top1/gap12/top3_mean/mean/std・n_eten_contenders・lead_side_ten・
eagari_top3_mean・eten_agari_balance・kyi_front_ratio/nige_count — 全て当日朝公表・リーク無し）を
Eclipse v2.1 と同一 splits・同一 5seed・同一パラメータで ablation（`C:/tmp/eclipse_v3_ablation.py`・本番保存なし）。

| | test AUC | PR-AUC | val AUC |
|---|---|---|---|
| baseline (47f) | 0.6948 | 0.1717 | 0.6907 |
| +ten v3a (58f) | 0.6946 | 0.1737 | 0.6996 |

- **ΔAUC = -0.0002 = フラット → Eclipse の AUC 改善手段としては NO-GO**（v2.1 続投）。
- ただし新特徴量は重用されている（eagari_top3_mean 全58中2位・eten_mean 5位・eten_agari_balance 11位）
  = **既存の通過順ベース集約と情報等価**で GBDT が情報源を差し替えただけ。val +0.009 は test に汎化せず。
- **含意**: 「Eclipse は KYI を見たことがない」のに AUC が動かない = 通過順集約が展開情報を既に拾い切っていた。
  書籍法（双馬式テン→隊列）の情報自体は JRDB pred 指数として綺麗に在庫があるので、
  通過順では作りにくい出口へ回す: ①Web 展開図（残対応「タイム推定→実データ」に pred_ten_idx）
  ②A-4 荒れ度モデル（目的変数が別・未検証） ③frame 軸モデルの入力（lead_side_ten）。
- 教訓（実装バグ）: KYI pred 系指数は**負値中心**（pred_ten_idx mean≈-13・range -50〜+37）。
  `>0` を有効値と仮定すると 94% を捨てる（初回 run はこれでカバー率 2% になり無効・破棄）。

## 6. 次の一手
1. ~~Eclipse v3 ablation~~ → **✅実施・NO-GO（§5）**。Eclipse の伸びは入力側でなく別目的変数へ。
2. **A-4 荒れ度モデル試作** — 同じレース集約特徴量で目的変数を「波乱（人気薄激走）」に。§5 の含意の本線。
3. frame 軸モデル（内外決着予測）の試作 — 目的変数は §4.2 の frame_bias（符号 or 連続）。
4. Web 展開図に pred_ten_idx 配線（表示系・残対応リスト消化）。
5. C-3 着手時に `docs/regulus/sources/` の特徴量カタログを材料表として持ち込む。風バイアスは A-1 ベンチ被験者キューへ。

## 7. 変更履歴

| Session | 内容 |
|---|---|
| 185 | 初版。書籍12冊の消化状況マップ+未消化候補A-E。立川ラベル v0 検証（収益✗・予報✗・成熟の道筋=race-levelモデル化）。 |
| 185 | §5 追加: Eclipse v3a ablation = NO-GO（ΔAUC-0.0002・KYI事前指数は通過順集約と情報等価）。次はA-4荒れ度/展開図/frame軸へ。 |

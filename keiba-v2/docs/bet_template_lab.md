# 買い方ラボ (Bet Template Lab) — 設計と運用

> Session 146 で『馬券力の正体』の買い方体系をデータ駆動テンプレ化 (Python)。
> Session 147 で **web 化** (`/analysis/bet-lab`)。今後の馬券戦略検証の **核** とする。

## 目的

AI印 (◎○▲☆△) を入力に、『馬券力の正体』の券種併用 (保険/ボーナス)・ワイド併用・
強弱/均等・フォーメーション・当てる/当たる体系を **データ駆動テンプレ** で表現し、
「テンプレ × 勝負レース条件」で **何を・どの条件で買うべきか** を haraimodoshi 実配当で
検証する。最終目標は「死なない本線 + 長期期待値の望み (ロマン枠)」の2層を確定し、
自動購入 (キャラ別) と KAZEMACHI 配信に繋ぐこと。

## アーキテクチャ (SoT → web は読むだけ)

ledger-reader / niigata で確立した「Python artifact JSON → web 表示」パターンを踏襲。
web 側は一切計算しない。

```
ml/strategies/bet_templates.py        テンプレDSL + 買い目生成 (純関数・DB非依存)
ml/analyze/backtest_selector.py       勝負レース条件 CONDITIONS の SoT
ml/analyze/backtest_bet_templates.py  haraimodoshi 実配当ローダー / ticket_payout
        │
        ▼  (再利用)
ml/export_bet_template_lab.py         ★SoT exporter (Session 147 新規)
        │   テンプレ×条件 の全メトリクスを集計
        ▼
data3/ml/bet_template_lab.json        ★成果物 (+ versions/v{ver}/ にアーカイブ)
        │
        ▼
web/src/lib/data/bet-template-lab-reader.ts   読み込み (version 対応)
web/src/app/api/bet-template-lab/route.ts      API (?version=)
web/src/app/api/bet-template-lab/versions/route.ts
        │
        ▼
web/src/app/analysis/bet-lab/page.tsx          ★表示ページ
```

### 再生成コマンド

```bash
python -m ml.export_bet_template_lab                       # 既定 (split=2026-01-01, max_rest=4)
python -m ml.export_bet_template_lab --split-date 2026-01-01 --max-rest 4
```

backtest_cache (2,934R / 2025-05〜2026-03) + haraimodoshi 実配当。数値は既存ラボ
(backtest_selector / backtest_walkforward) と一致する (同じ cache・同じ精算)。

## 印モード (C案 / Session 147) — 実AI印 ⇄ composite理論

ふくだの鋭い指摘「画面のAI評価で買い目に入るのか?」から、2つの印モードを並走。

| モード | 印の決め方 | 意味 |
|---|---|---|
| **ai (実AI印)** | `assign_ai_marks(step=2)` = composite序列 + **複勝率(P)の崖で頭数カット** (markSet=2、出走表に出る印) | **画面のAI印で買ったらどうなるか** |
| **composite (理論)** | composite序列から ◎○▲☆△ を**常に上位5頭**へ機械割当 | **印を最適配置したら届く上限** |

- 両モードとも ◎ は同じ (composite最高)。違いは相手印の頭数・構成。

### 印語彙の統一 (ねじれ解消 / Session 147)

当初テンプレは ◎○▲**☆**△ (☆=4位、△=ヒモ複数)、AI印は ◎○▲△**Ⅲ** で**ねじれ**ていた。
ふくだ指摘「印種類のねじれ」を受け、**テンプレ語彙を AI印 (markSet=2) と同じ ◎○▲△Ⅲ
(上位5頭の単独序列印) に統一**。`marks_from_ranking` は上位5頭に1頭ずつ印、6位以降は無印。

- マッピングが恒等になり、実 AI印がそのままテンプレに入る (穴のみ Ⅲ に合流)。
- **相手総流しが上位5頭 (○▲△Ⅲ=最大4頭) に収まる** → 印の無い6頭目以降を買う矛盾が消える
  (ふくだの違和感「このAI評価で買い目に入るのか」の根本解消)。
- 三連複1頭軸流しは 21点→6点 に減 (上位5頭内で完結)。composite理論モードの相手も5頭に揃う。
- 印頭数のチューニングは今後 AI印側 (CLIFF_RATIO) かテンプレの列構成で行う (旧 max_rest は廃止)。

### ★C案の核心発見 (ALL条件・語彙統一後)

| テンプレ | 実AI印 ROI/中央値 | composite理論 ROI/中央値 |
|---|---|---|
| 三連複1頭軸流し | 87% / 87% | **101% / 105%★** |
| ワイド堅実党 | 88% / 89% | 98% / 98% |
| 複勝堅実党 | 92% / 89% | 96% / 95% |
| 三連単ロマン | 80% / 76% | 88% / 92% |

→ **実AI印は composite理論より一律ROIが低い** = 印ロジック(markSet=2の崖)に改善余地。
両モードの差 = 伸びしろ。三連複1頭軸は理論で中央値105%★に届くのに実印では87%。

### ★ねじれ解消の副次効果 (語彙統一で「印無し馬」を切った)

相手を上位5頭 (○▲△Ⅲ) に絞った結果、composite理論の **三連複1頭軸流しが 91%→中央値105%★** に
改善 (21点→6点・的中率49%→28%)。**印の無い6頭目以降を買うのは無駄打ちだった**ことを実証
(ふくだの違和感が正しかった)。maxDD も激減 (三連複654k→118k / ワイド224k→145k / 三連単678k→413k)
= 印を絞る = 堅実化。

## データ構造 (bet_template_lab.json)

- top: `period_*`, `total_races`, `split_date`, `max_rest`, `mark_modes[]`, `months[]`,
  `conditions[]` (key/label/desc), `templates[]` (key/label/system/ringfenced/note)
- `cells[]` = **印モード × 条件 × テンプレ (2×7×6 = 84セル)**。各セルに `mark_mode`。フィールド:
  - 全期間: `fire` / `hits` / `hit_rate` / `roi`
  - OOS: `roi_train` (date<split) / `roi_valid` (date>=split)
  - **安定性 (主軸)**: `median_roi` (月別ROIの中央値) / `avg_roi` / `plus_months` ("6/11") /
    `roi_first_half` / `roi_second_half`
  - 出現数: `per_day` / `month_inv` / `interval` (何R買って1的中)
  - リスク: `max_dd` (累積pnl最大DD・円) / `max_streak` (最大連敗)
  - 系列: `monthly[]` (月別 fire/inv/ret/hits/roi/pnl)
  - 明細: `hit_details[]` (高配当 top30 / race_id, bet_type, horses, payout)

## メトリクス体系 (★中央値が主軸)

| 指標 | 意味 | 判定 |
|---|---|---|
| **中央値ROI** | 月別ROIの中央値 | **≥100% = ★安定**。万馬券1本で跳ねる平均より信頼 |
| +月 | ROI≥100% の月数/有効月数 | 高いほどコンスタント |
| ROI(全) | 全期間ROI | 平均的・上振れに注意 |
| OOS(valid) | split_date 以降の実質OOS | 後知恵バイアスの正直チェック |
| 月投資 / 的中間隔 | 月あたり投資・何R買って1的中 | ふくだ重視 (予算・楽しさ・配信頻度) |
| maxDD / 連敗 | リスク | 隔離枠の上限設計に直結 |

## ★結論 (2層構造)

- **全レース機械買いで控除率を10-22pt埋める = AI印のエッジは本物** (単勝99/ワイド98.3/複勝95.8%)。
- **中央値で安定して勝てるのは ALL×ワイド堅実党 (中央値100%・トントン) のみ**。
- 条件絞り (軸強/荒れ) の高ROIは「平均は高いが中央値は低い」= 1-2ヶ月の万馬券依存。確実な金脈ではない。

| 層 | 中身 | 位置づけ |
|---|---|---|
| ① 本線 | 全レース×ワイド堅実党 (中央値100%) / 複勝堅実党 (maxDD最小・連敗短) | 死なない・楽しい土台 |
| ② ロマン枠 | 軸強/荒れ × 高配当系 (平均>100%・中央値負け) | 少額・隔離で長期期待値の望み「⚡勝負レース」 |

## Session 148: 買い方チューニング徹底検証 (2026-06-11)

3レイヤー整理 (**L1 買い目構成 / L2 配分=評価ベース固定・哲学§5 / L3 ゲート=合成オッズは絶対水準のみ・§4**) で
5系統を一括検証。精算 haraimodoshi 実配当 / 判定は月別中央値 / 2934R (2025-05〜2026-03) composite理論モード。
注意: backtest_cache は 4/26 生成の旧モデル予測 (P分布が本番6月モデルよりフラット・崖2.5がほぼ出ない)。

### ★最有望: 単勝多点ゲート (`ml/analyze/backtest_tansho_multi.py`)
「1番人気が飛びそうなら勝ちそうな馬を複数買う、合成オッズが乗るなら」(ふくだ構想) の機械版が機能:
- ゲート: 1番人気の AI 評価低 (composite rank>=4、発火10.1%) × **AI上位2頭の単勝2点**
- 素のゲート: 月中央値 122.0% だが train 121.8% → valid 99.1% で失速
- **合成オッズフロア G>=2.5 重ね: ROI 124.8% / 月中央値 129.6% / 9/11ヶ月+ / train 124.7% ≒ valid 125.4%** (212R = 月19R・月投資 ~3,800円)
- G フロアは 2.0→2.5→3.0 で単調改善 = 閾値チューニングでなく構造的 (両頭とも市場が推してない歪みレースに絞る効果)。単勝なので万馬券上振れ汚染も小さい
- ◎1点 (tansho_ai1) は valid 67% で不成立 → **「多点 (2点) + G フロア」の組が本体**
- 三連単頭複数化 (srt_2head [AI1,2]→[1-3]→[1-4]) は中央値 67% で不成立 — 単勝の歪みは三連単に転写されない。現段階は単勝で取るのが正解

### weight sweep: 「でかく勝つ」の対価表 (`ml/analyze/backtest_weight_sweep.py`)
コンポーネント別 flat 精算1回 → 線形再構成で 189 構成 sweep (puku=三連複1頭軸 / tan3=三連単◎○▲BOX / 単勝◎ / 馬単◎→○▲):
- **三連複1頭軸単体が王者: 月中央値 105.4% / hitP90 7.08倍**。何を足しても中央値は下がる (足す価値は別目的の対価)
- tan3 の価値は hitP90 でなく**本命決着クラスタの塊回収**: weight 0→0.1→0.25 で本命決着ROI **197→273→365%**、対価は中央値 105.4→100.8→95.2%。**0.4 以上は中央値95%割れ=却下圏**。現行 0.25 はフロンティア上で妥当 (「でかく勝つ」最重視なら維持、安定寄せなら 0.1)
- **puku+単勝◎0.5: 中央値 103.3%・的中率 45%** — 現行構成より中央値も的中体験も上 (hitP90 は 4.89 に低下)。「単勝を足す」は楽しさ↑の有効回路
- コンポーネント相関 (松風知見9の実証): **単勝×馬単 0.51 (同じ賭けを2回)** / 三連複×三連単BOX 0.20 (併用合理性)。馬単買い足しは優先度低

### W/P乖離 = 捨て馬券の土台: 成立 (`ml/analyze/analyze_wp_split.py`)
ふくだの「○の頭はない」読み (例: 三連複合成2.0が安い→三連単◎▲→◎○▲→◎○▲だけ買う) の機械再現:
- win_share = pred_w/pred_p の P(1着|3着内): 印対象 (top5) で Q1 22.3% → Q5 45.2% **単調** = 「来ても勝ち切れない馬」は事前に分かる
- ○P型 (share < 印3頭中央値×0.6、336R=11%) 発火レース内: 三連単BOX 128.2% vs **○頭捨て4点 172.8%** (コスト2/3で払戻維持)
- 三連単という土俵自体は中央値75%で弱いので全面適用は+2pt止まり → **honmei_formation の三連単部分に「○P型なら1列目から外す」役割分化を組み込む**のが次の一手

### 崖セレクタ: 不成立で確定 (検証して棄却)
- 本物の崖 (P比2.5) は崖1≈1%で希少すぎ (このキャッシュ)。ソフト崖1.5 も walkforward 中央値 97% 止まり (selector valid 単区間の 106% は再現せず = Session 146 教訓の再演)
- ソフト団子 × sanrenpuku_1jiku 中央値 104% で ALL (105%) と差なし → **買う/降りる条件として無効。崖は印の頭数決定 (本来の用途) に留める**

### パドック点数 (データ制約確定・感触あり)
- **mark 蓄積は 2026 年〜のみ / 7R 以降のみ / S は全期間 57 頭** (A 1,170・B 1,542 の 1/20 — ふくだの「S は別格」をデータ確認。S≠A 厳守、mark_score は S=A=5 に潰れているので mark 生値で層別すること)
- cache 重なり 337R: **◎×パドックS (n=16) 勝率 43.8% / 3着内 75% / 単勝ROI 106% / 複勝 102.5%**。S 単独 (n=37) 複勝ROI 108.6%
- A は勝率 17.7% に対し単勝ROI 76.3% = **高評価が市場に織り込まれ割引かれる** (妙味は S だけに残る構造)
- n 極小につき感触止まり。前向き蓄積を継続し 2026 後半に再検証 (S=勝負レース昇格オーバーレイ候補)

### Session 148 新規ツール
- `ml/strategies/synthetic_odds.py` (+`ml/tests/test_synthetic_odds.py` 12件): 合成オッズ G / 実配分 hit_return / トリガミ検出 / `prune_to_floor` (floor 未達は**ロールバック=降りる**、中途半端に痩せたプランを買わせない)
- `ml/strategies/role_split.py` (+`ml/tests/test_role_split.py` 9件): `win_share` / `detect_no_head` (P型検出)。`bet_templates.apply_template(no_head=)` で順序系券種の1列目から除外
- `ml/analyze/backtest_weight_sweep.py` / `backtest_tansho_multi.py` / `analyze_wp_split.py` / `analyze_paddock_signal.py`
- `backtest_selector.py` に崖条件 (cliff/cliff15/cliff18)、`backtest_walkforward.py` に `--conditions/--templates`

### ラボ反映 (lab_version 1.2 / 同日後半)
`export_bet_template_lab.py` を v1.2 化して `/analysis/bet-lab` に反映 (web はデータ駆動で自動追従):
- 新テンプレ: `tansho_ai2` / `honmei_formation_stable` (tan3 0.1) / `honmei_plus_tansho` (puku+単勝0.5) / `honmei_formation_rs` (役割分化・仮想テンプレ)
- 新条件: 「1人気弱 (AI△以下)」「1人気弱 & 単勝G>=2.5」。棄却済みの崖条件はラボに持ち込まない (LAB_CONDITIONS 厳選)
- **クロスチェック通過**: composite × tansho_ai2 × 1人気弱&G>=2.5 = ROI 124.8% / 中央値 129.6% / 9勝 / train 124.7% / valid 125.4% — `backtest_tansho_multi` と独立実装で完全一致
- **発見: ゲートの汎用性** — 同ゲート上で `honmei_formation_rs` ROI 168.2% / 中央値 161.9% / valid 114.8%、`sanrenpuku_1jiku` 146.3% / valid 104.5%。「1人気弱×G」は単勝専用でなく**歪みレースの検出器**として汎用に効く。ただし三連単系は train 180.6%→valid 114.8% の落差 (分散大) — **valid で最も頑健なのは単勝二刀流 (125.4%)**
- ALL 条件でも新顔が即★: `honmei_plus_tansho` 中央値 103%★ / `honmei_formation_stable` 101%★ / rs 版は素の honmei_formation 95%→98% (+3pt)

### ⚠ 役割分化の正直な現在地 (formation 実環境で再現せず → 同日 spot check で棄却確定)
formation 画面 (predictions.json = **当時の本番モデルの実予測**・2025-03〜2026-06・3,970R) に
AI_BOX3 / AI_BOX3_RS / AI_HONMEI_FIX を追加して再生成した結果:
- AI_BOX3 69.4% vs **AI_BOX3_RS 67.8% — 役割分化が逆に下回った** (2026年以降に絞っても 72.9% vs 68.6%)
- 効果の段階的消失: composite理論×均質cache **+10.6pt** → 実AI印×均質cache **+1pt** → 実AI印×実predictions **-1.6pt**
- 解釈: 役割分化 (win_share の P型検出) は **印と W/P キャリブレーションの質に強く依存する脆い効果**。
  理論上限では効くが、実運用条件 (崖カット後の印・時期で質が違う当時モデルの W/P) に近づくほど消える
- **最終判定 = 棄却**: model_meta 確認で現行本番モデルは 2.3 のまま (cache=現行モデルの test 期間予測 = in-sample リークなし)。
  「最新モデルなら効く」仮説は消滅し、現行モデル稼働期 (2026-04〜06) の predictions 529R でも 72.8% vs 68.8% で効かず。
  副産物: **AI_HONMEI_FIX (◎頭固定) が同期間 95.1% で最良** = 「頭を絞る」は W/P 動的判定より ◎固定の静的絞りが頑健

### 🚨 spot check (predictions 直接検証) — 単勝二刀流の棄却と「オッズゲート後知恵」の発見
`backtest_tansho_multi --source predictions` (4,244R・直前オッズでゲート判定・実払戻精算 = 本番運用と同条件):
- **単勝二刀流 (1人気弱×G>=2.5): cache ROI 124.8%/valid 125.4% → predictions ROI 68.3%/valid 53.8% に消滅。本番組み込みは棄却**
- 発火率も 10.1% → 5.1% と別物 = 同じレース集合を事前には選べていなかった
- 原因の切り分け:
  - cache は in-sample リークではない (model_meta split: train ~2025-03 / cache 期間 = test 2025-05~2026-03)
  - オッズ非依存の ◎単勝は現行モデル期 predictions ≈ cache (~85%) で一致 = **モデル質はcacheの数字どおり**
  - 消えたのは**オッズ条件ゲート**: cache は確定オッズで「1人気弱・G>=2.5」を判定 = 市場が最後まで評価しなかったレースの**事後識別**。
    本番は直前オッズ判定 → スマートマネー (松風知見7) で締切までに形が変わる。**ふくだの「5分前オッズ注意」が最初から答えだった**
- **検証規律に追加** (`feedback_odds_gate_hindsight` メモリ): オッズ依存条件 (1人気・EV・合成G・人気乖離) を含む戦略は
  cache で見つけても **predictions ソースで再検証するまで信用しない**。cache で信用できるのはオッズを条件に使わない検証
  (ALL 機械買い・印/composite 序列・W/P 比)。bet-lab の該当条件 desc とdata_source に ⚠ 明記済み (教材として残置)

## 今後の拡張 (この画面を核に)

1. **単勝多点ゲートの実装・前向き検証** — Session 148 ★。1人気弱×AI上位2頭×G>=2.5 を bettype 選定に組み込み、本番モデル predictions でスポット確認 → 自動投票へ。
2. **役割分化テンプレ** — honmei_formation の三連単 1 列目から○P型 (win_share 低) を外す。weight sweep (本命決着365%) と合成。
3. **テンプレ/印頭数チューニング** — `max_rest` を毎週 walk-forward で最適化。「ALL×ワイド中央値100%」をベンチに探索。
4. **キャラ別バンクロール軌道** — `/analysis/simulation` に `simulate_bankroll_bettype` 連携。本命党/妙味党/三連単ロマン党/複勝転がし党の複利軌道・破産確率。
5. **パドックブースト前向き検証** — 競馬ブックパドック S → 勝負レース化。2026 年蓄積継続 (7R以降限定・S≠A)。
6. **対象レース出現数の標準化** — fire/月投資/的中間隔を全画面のメトリクスに統一。
7. **KAZEMACHI 配信連携** — 確定したキャラの買い目を配信・自動購入 (隔離bankroll・シズネガードレール)。

## 関連

- メモリ: `bet-template-lab`, `character-betting-personas`, `feedback_combo_backtest_settlement`,
  `feedback_betting_philosophy`, `bet-adjustment-items`, `notify-layer-roadmap`
- コード: `ml/export_bet_template_lab.py`, `ml/strategies/bet_templates.py`,
  `ml/analyze/backtest_{selector,bet_templates,walkforward}.py`

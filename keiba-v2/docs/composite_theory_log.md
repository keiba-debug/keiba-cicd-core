# composite理論ログ — 印ロジックの定義と改訂履歴

> 買い方ラボ ([[bet_template_lab]]) の **composite理論** = 「印を最適配置したら届く上限」。
> これを北極星に、実 AI印 (markSet=2) を近づけていくのが本筋。
> **改訂のたびに後知恵 (全期間) ではなく OOS (valid) と walk-forward 中央値で効果を記録する** —
> でないとデータスヌーピングで自分を騙す (Session 146 W9 / 後知恵105%→OOS86% の教訓)。

## composite理論の定義

- **composite** = レース内 robust-z(W, P, AR) の重み付き合成 (`bettype_efficiency.process_race`)。
  - W = pred_proba_w_cal (校正済勝率)、P = pred_proba_p (複勝率)、AR = ar_deviation (着差偏差)。
  - 重み既定 (1, 1, 1)。ADR 欠損/分散ゼロ時は (W,P) 2軸に縮退。
- **序列** = composite 降順。同点は win_prob → 馬番で決定的に。
- **印語彙** = `◎○▲△Ⅲ` (上位5頭の単独序列印)。6位以降は無印。
- **2モード**:
  - **composite理論** = 常に上位5頭へ ◎○▲△Ⅲ を機械割当 (理論上限)。
  - **実 AI印** = `assign_ai_marks(step2)` = composite序列 + **複勝率(P)の崖**で頭数カット (markSet=2、画面に出る印)。
- **精算** = haraimodoshi 実配当、flat 100円/点 (配分=sizing は別レイヤー)。
- **再生成** = `python -m ml.export_bet_template_lab` → `data3/ml/bet_template_lab.json` (`lab_version`)。

## 改訂履歴 (changelog)

各エントリは「変更内容 → ALL条件・代表テンプレの 全期間ROI / valid(OOS) / walk-forward中央値 / maxDD」。
**valid と中央値を必ず併記** (全期間ROIだけで判断しない)。

### v1.0 (2026-06-10 / Session 147) — 語彙統一・2モード化

- 買い方ラボを web 化 (`/analysis/bet-lab`)、SoT exporter 新規。
- **C案**: 実 AI印 ⇄ composite理論 の2モード並走。
- **ねじれ解消**: テンプレ語彙を ☆△混在 → AI印と同じ `◎○▲△Ⅲ` に統一。
  相手を上位5頭に絞り、印の無い6頭目以降を買わない設計に。

| テンプレ (composite理論) | 全期間ROI | valid(OOS) | 中央値 | maxDD |
|---|---|---|---|---|
| 三連複1頭軸流し | 101% | **86%** | 105%★ | 118k |
| ワイド堅実党 | 98% | 83% | 98% | 145k |
| 複勝堅実党 | 96% | 86% | 95% | 30k |
| 本命党 | 88% | 90% | 87% | 122k |

- 所見: ねじれ解消で三連複1頭軸が中央値85%→105%★に改善 (印無し馬を切った効果)。
  **ただし OOS(valid)では101%→86%** = 後知恵と OOS のギャップは健在。過信しない。
- 実 AI印は全テンプレで composite理論を下回る = markSet=2 崖ロジックの伸びしろ。

### v1.1 (2026-06-10 / Session 147) — 本命フォーメーション (三連単補完) + 配分(sizing)層

- **新テンプレ `honmei_formation`**: 三連複1頭軸(保険) + ◎○▲三連単BOX(ボーナス)。
  「◎○▲ズバリ本命決着なのに三連複だと安い」を三連単補完で解決 = ①(本命決着)で儲かる仕組み。
- **配分(sizing)層**: `BetComponent.weight` を精算で有効化 (stake = 100×weight)。
  オッズ/EVベースでなく**評価ベース**配分 ([[feedback_betting_philosophy]] §5)。
- **三連単 weight = 0.25** に設定 (★今後の調整候補・「当たった時にでかく勝つ」鉄則で厚くする余地)。

データ根拠 (◎の信頼度・全2934R):
- ◎(composite1位) 勝率29.4% / 複勝率63.8% / 本命決着(◎○▲3着独占)頻度8.7%・うち◎1着44%
  → ◎1着固定はダメ、**◎○▲三連単BOX**で全着順カバー。
- 本命決着時の配当: 三連複◎○▲ 中央値760円 vs 三連単(実着順) 中央値3700円 = **約5倍**。

三連単 weight フロンティア (全体ROI / 本命決着時ROI):

| 三連単weight | 全体ROI | 本命決着時ROI |
|---|---|---|
| 0 (三連複のみ) | 100.8% | 197% |
| **0.25 (採用)** | **98.7%** | **365%** |
| 0.5 | 97.3% | 477% |
| 1.0 (均等) | 95.5% | 617% |

- honmei_formation (composite理論・weight別 ALL): flat 96%/中央値81%/maxDD382k → 0.5 で 97%/88%/235k。
  0.25 はさらに改善 (薄い三連単で本命決着の上乗せだけ取り、全体悪化を抑える)。
- 所見: 「全体ROIを微妙に削って、本命決着の配当を厚くする」トレードオフを weight で連続調整できる。
  weight は評価ベースの調整ノブ (オッズで決めない)。**OOSでの本命決着時ROIは要継続観察** (本命決着 8.7%=少数)。
- 副次: `sanrentan_roman` の component weight (tansho0.2/sanrentan0.8) も有効化され maxDD が縮小。

### v1.2 (2026-06-11 / Session 148) — 買い方チューニング: 単勝二刀流・weight変種・役割分化

検証詳細は `bet_template_lab.md` Session 148 セクション。3レイヤー整理
(L1構成 / L2配分=評価ベース / L3ゲート=合成オッズ絶対水準) で5系統を一括検証した成果を反映。

- **新テンプレ**: `tansho_ai2` (単勝AI上位2点) / `honmei_formation_stable` (三連単weight 0.1) /
  `honmei_plus_tansho` (三連複保険+単勝◎0.5)。
- **新条件 (ゲート)**: 「1人気弱 (AI△以下)」(fav_rank>=4) / 「1人気弱 & 単勝G>=2.5」。
  ★最有望: 1人気弱×G>=2.5 × tansho_ai2 = **ROI124.8% / 月中央値129.6% / 9勝11ヶ月 /
  train124.7%≒valid125.4%** (212R)。Gフロアは 2.0→2.5→3.0 で単調改善 = 構造的。
- **役割分化 (仮想テンプレ `honmei_formation_rs`)**: W/P乖離 (win_share = pred_w/pred_p) で
  「1着に来ない (P型)」頭候補を三連単1列目から外す (`role_split.detect_no_head` +
  `apply_template(no_head=)`)。発火1377R/2934Rで三連単部分 BOX 96.9%→**107.5%** (コスト2/3)。
  ◎P型 (93R) では1列目が○▲ = maru-2着付けの機械版が副産物で動く。
- **崖セレクタは棄却**: ソフト崖(P比1.5)も walkforward 中央値97%止まり。崖は印の頭数決定に留める。
- **★同日 spot check (predictions 直接検証) で大どんでん返し**:
  - 単勝二刀流 cache 124.8%/valid 125.4% → **predictions (直前オッズ判定) 68.3%/valid 53.8% に消滅 → 棄却**。
    cache は in-sample でない (split: cache期間=test) が、**確定オッズでのゲート判定が後知恵**だった
    (市場が最後まで評価しなかったレースの事後識別。本番=直前オッズでは同じレースを事前に選べない)。
  - 役割分化も現行モデル(2.3)稼働期 529R で AI_BOX3 72.8% vs RS 68.8% → **棄却** (理論モード専用の現象)。
    副産物: AI_HONMEI_FIX (◎頭固定) 95.1% = 頭の絞りは静的 (◎固定) が頑健。
  - **検証規律**: オッズ依存条件の戦略は predictions ソース再検証必須 (`feedback_odds_gate_hindsight`)。
    cache で信用できるのは ALL 機械買い・印序列・W/P 比などオッズ非依存の検証のみ。
  - 生き残った v1.2 の成果: ALL 条件の新テンプレ (`honmei_plus_tansho` 103%★ / `honmei_formation_stable` 101%★)
    と weight sweep の対価表 (これらはオッズ条件を使わない)。

### 次版候補 — 相手の広さ可変 / 抜け人気2着付け

- 相手の広さを可変に (合成オッズフロア `synthetic_odds.prune_to_floor` で点削減・降りる判断)。
- 「抜けた1番人気◎を2着付けにして伏兵▲を1着に」= [[maru-second-place-formation]]。
  ▲(頭possibilityの伏兵)選定に激走軸(sirius)が要る → 激走モデル待ち。
  (◎P型検出が同方向の機械版として v1.2 で部分稼働済み — sirius は▲の質を上げる役)

## 関連

- メモリ: `bet-template-lab`, `feedback_betting_philosophy` (§4 券種選択), `feedback_combo_backtest_settlement`
- doc: `bet_template_lab.md` (アーキテクチャ全体), `ml_experiment_log.md` (モデル側)
- コード: `ml/export_bet_template_lab.py` (LAB_VERSION), `ml/strategies/bet_templates.py`

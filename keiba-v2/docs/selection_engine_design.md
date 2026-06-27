# 買い目選定エンジン — 設計書 (Session 172・型を捨てて全組み合わせから選ぶ)

> **対象**: 自動投票の買い目選定を、役割固定の「型」(◎2-3着流し等) から
> **「考えられる組み合わせ全体から、回収率と当たりやすさで選定する」**方式へ作り替える構想。
> **正本ステータス**: この doc が買い目選定エンジンの設計正本。初版 = Session 172 (2026-06-21)。
> **発端**: ふくだ「今のルールの組み方だと繰り返し。やらなくちゃいけないのは考えられる組み合わせ
> すべてから買い目を選定すること。今は毎回がちがちにルール決めて見もしてない」(S172)。
> **関連**: `[[sanrentan_formation_design]]` (置き換え対象の現行型) / `[[tansho-central-strategy]]`
> `[[payout-ceiling-strategy]]` / `[[feedback_odds_gate_hindsight]]` / `[[favorite-betrayal-project]]`
> `[[maru-second-place-formation]]` / `[[feedback_betting_philosophy]]` §4

---

## 0. なぜ作り替えるか (S172 の発端)

S163 以降ずっと「`shobu_rate` → `wide_anaba` → `sanrentan_formation`」と **役割固定の"型"を作っては
パラメータを sweep で詰める**、を繰り返してきた。だが ふくだの指摘の通り、これは
**「考えられる組み合わせを見て、その中からベストを選ぶ」をやっていない**。

### 0.1 決定的な実例 — 東京9R (2026-06-21・race 2026062105030609)
- 結果 **15→9→11 で三連単 59,410円 (594倍)**。印は当てていた (〇15→▲9→△11)。
- **現行フォメは1点も買えなかった** (頭候補なし → 見送り)。理由 = 全買い目が「◎が2-3着に必ず
  入る」型なので、**◎8 が飛んだ瞬間に構造的に全外れ**。〇15 は win_ev 2.43 だが頭ゲート
  `pred_w≥0.15` に届かず (0.089) 弾かれた。
- ◎8 = AI 的に断然 (pred_w 0.37・gap 2.03・cliff=1) **だが過剰人気 (win_ev 0.85・2.3倍)** で飛んだ。
  → 「印で6万を当てて100円も買えない」= 型の構造的限界。

### 0.2 ビジョン (ふくだ S172)
1. **役割固定 (◎2-3着等) を廃止**。
2. **候補 = 全組み合わせ** (まず三連単 C(N,3)×6、理想は全券種)。◎抜きも 15-9-11 もフラットに候補。
3. **足切り = 回収率500%以上 (オッズ5倍以上)** + 幽霊点除外。「思い切って切る分は削る」。
4. **レース選定** = 1日36Rを「買いたい順」にランキング → 上位N(例5R)に予算集中。「最初に決めておく」。
5. **直前は最終調整** (直前オッズで買い目確定)。「狙い1位が単勝5倍に全額もあり」(券種フリー)。

> ★核心 (ふくだ S172 締め)★ — **決め打ちで動くのは無理がある。あくまで状況に応じて、あらゆる
> 購入パターンの中から「より最適だと思われる買い目」を作る**。= 型(決め打ち)を sweep で詰める
> 開発スタイルを卒業し、毎レース「レース状況 → 候補全体 → 選定」を動的に回す。次セッション主題。

---

## 1. S172 実証で分かった壁 (正直に・最重要)

ビジョンを素朴に実装すると **較正バイアス** に当たる。東京9R で機械順位づけを試した結果:

| 順位づけ | 上位に来るもの | 15-9-11 の順位 |
|---|---|---|
| **ハーヴィルEV (p×o) 降順** | 幽霊点 `5-16-3` (p=0.00006・o=528,983倍) ばかり | **2574位 / 2730** |
| **妙味 distortion 降順** | 同上 (幽霊点) | 2574位 |
| **上位K頭∩オッズ5倍 × 確率順** | `8-15-x` (◎8が1着の点) が独占 | **61位 (K=6)** |
| 単勝 オッズ5倍∩回収率見込み順 | #5 (289倍・pred_w0.035) =幽霊 | 〇15 は7位 |

- **EV順 → 幽霊点の罠** (ハーヴィル確率が人気薄を過大評価。S169 で実証済みの較正バイアス)。
- **確率順 → ◎(過剰人気の断然馬)の罠** (モデルが◎8を断然と見る → 8始動の点が確率上位を独占。
  でもその◎8が過剰人気で飛ぶ)。
- ＝ **買い目の組み方 (型/EV/確率/回収率) をどう変えても、確率の較正が壊れていると、ふくだの直感
  (◎8消し・混戦で〇▲△の高配当) を機械で再現できない**。S165「勝ちはモデルのエッジ次第」/
  S169「妙味は単勝に宿る・combo に較正エッジ無し」の再確認。
- **本丸 = 確率の較正** (混戦・人気薄・三連単の精度)。選定エンジンはその器であって、エッジの源泉
  ではない。これを忘れると「器をいじって黒字化する」幻想 ([[feedback_odds_gate_hindsight]] 系) に陥る。

### 1.1 S172 の副産物 = ◎過剰人気 見送りゲート (中間成果・検証済)
探索 `explore_axis_confidence` で「◎の win_ev で成績が3層に割れる」と判明:

| ◎win_ev 層 | 発動R | ROI | PnL | 天井 |
|---|---|---|---|---|
| Q1 過剰人気 <0.78 | 50 | 49% | **−44,740** (大負けの主犯) | 43,760 |
| Q2 適正 0.78-1.14 | 52 | 127% | +23,870 | 43,150 |
| Q3 妙味 >1.14 | 50 | 88% | −10,610 | **81,390** |

→ `min_axis_win_ev` ゲートを `sanrentan_formation` に実装。sweep で **ev_gate=0.6 が全指標で現行超え**
(発動135R・ROI 88→100%・月中央 90→**98%**・PnL −31k→**+920**・天井81,390維持・maxDD改善)。
**これは現行フォメの低リスク改善** = 選定エンジン完成までの「つなぎ」本番化候補 (§4 で判断)。
ただし東京9R の◎8 は win_ev 0.85 で gate0.6 を逃れる = 「降りる」だけでは6万は救えない。
**→ S172 で本番化済** (`DEFAULT_MIN_AXIS_WIN_EV=0.6`・`bettype_scheduler` は bankroll/per_race_cap のみ
渡すので非依存で次レースから有効・test 17 green)。月別裏取りで「4-5月は全config全ハズレ=月中央は
脆い指標・判断は全期間ROI/PnL/天井で」と確認。「悪くしない小改善」として確定 (本丸は較正)。

### 1.2 ①「動的点数 (頭の数)」は死蔵と確定
当初の §5.0 (sanrentan_formation_design) の①「n_head を動かす」は、本番ゲート下では妙味頭が
**中央値1頭しかいない** (n_myomi≈1) ため、n_head=1〜5 で買い目・PnL が1円も動かず **空振り**と実証。
頭を増やすには頭ゲート緩和が要るが、それは選定エンジン (型廃止) で吸収する。

---

## 2. 設計 — 2層の意思決定

```
【事前 (朝)】 レース選定層
  1日36R を「買いたい度」でランキング → 上位N (例5R) に予算を割り当て
        │  (買いたい度の指標は §3.1。 レース単位は粗いぶん較正ノイズに頑健な可能性)
        ▼
【直前】 買い目選定層 (選んだレースのみ)
  候補 = 全組み合わせ (三連単/単勝/…)
    ├─ 足切りA: 市場オッズ ≥ 5倍 (回収率500%以上・天井狙い・固い点を捨てる)
    ├─ 足切りB: 幽霊点除外 (構成馬をモデル上位 or 印馬に限定 / 確率下限)
    ├─ 狙い順ランキング (指標は §3.2・要検証)
    └─ 予算内で上位を買う (券種フリー。 単勝1点全額もあり)
```

### 2.1 既存資産の再利用
- `ml/strategies/harville.py` — 全組み合わせのハーヴィル確率・合成オッズ。
- `ml/strategies/bettype_efficiency.py` — RaceEfficiency (composite/pred_w/win_ev/印序列)・Plan。
- `core/odds_db.get_all_combo_odds` — 全券種の確定オッズ (バッチ取得は S172 `_load_all_trifecta_odds`)。
- `ana_tansho` (穴単勝 shadow) — 「妙味は単勝に宿る」の既存実装。単勝候補はここと統合。
- `min_axis_win_ev` ゲート (S172 実装) — 過剰人気◎ の扱いに流用可。

---

## 3. 未決の核心論点 (次セッション以降で詰める)

### 3.1 レース選定の「買いたい度」指標
候補: ◎の格 (gap)・cliff (分布)・最良買い目の狙い度・妙味馬の有無・◎win_ev。
**レース単位は3着まで当てるより粗い → 較正ノイズに頑健か** を実データで確認する価値。

### 3.2 買い目の「狙い順」指標 (最難関 = 較正の壁)
- EV順=幽霊点、確率順=過剰人気◎ の両罠を避ける指標が要る。
- 候補: (a) 印ベース (◎○▲△ の組み合わせ格)、(b) モデル上位K頭限定 + 確率順、(c) 過剰人気◎を
  軸から外したうえでの確率順、(d) 三連単確率の較正やり直し (本丸)。
- ★ここが「モデルのエッジ」に直結。器の工夫だけでは黒字化しない前提で設計する★。

### 3.3 検証方法 (採用条件)
- 実払戻 (haraimodoshi・leak-free) で **現行 `sanrentan_formation` を上回るか**。
- 指標 = 月中央ROI (壁72.5%超)・天井 (≥1000R・最高配当)・maxDD・PnL。
- レース選定の予算集中効果と、買い目選定の妙味捕捉を分けて測る。
- **上回れば本番化 / ダメなら「較正が本丸」と確定** (どちらでも前進)。

---

## 4. 当面の進め方 (S172 終了時点の宿題)
1. **✅ 本番化済 (S172)** `min_axis_win_ev=0.6` をモジュール既定化 (scheduler 非依存・bat編集不要・
   test 17 green)。月別裏取りで「1-3月改善・4-5月は現行同様0」= 悪くしない小改善と確認。
2. レース選定層の「買いたい度」を試作 → 上位N集中が実払戻で効くか単独検証。
3. 買い目選定層の「狙い順」指標を §3.2 の候補で比較 (東京9R 等の的中レースで「拾えるか」可視化 →
   実払戻 sweep)。
4. 本丸 = 三連単/人気薄の確率較正 (モデルのエッジ強化)。買い方探索が頭打ちと出たらここへ。

---

## 5. S172 で作ったコード資産
| ファイル | 役割 |
|---|---|
| `ml/analyze/explore_axis_confidence.py` | ◎信号×n_head 探索 (①死蔵・win_ev層別発見)・三連単OD バッチ取得 |
| `ml/analyze/sweep_axis_winev_gate.py` | ◎win_ev 見送りゲート sweep (ev_gate=0.6 が現行超え) |
| `ml/strategies/sanrentan_formation.py` | `min_axis_win_ev` ゲート追加 (DEFAULT=0.0=無効) |
| `ml/strategies/bettype_sizing.py` | `size_race_sanrentan_formation` に `min_axis_win_ev` 引数 |
| `C:/tmp/rank_tokyo9*.py` | 東京9R 全組み合わせランキングの可視化 (使い捨て調査) |

---

## 7. S175 決定: gap単勝エッジを「最初の収益源」として本投票化 (★次セッションで実装)

S173-175 の市場較正監査で「エッジは gap≥5単勝×(未勝利/条件/重賞) にだけ実在 (a-priori p=0.026)・comboは控除率の壁で勝ち筋なし」と確定 (詳細 `market_calibration_edge_map.md §8`)。
本番自動投票の実払戻実績 (purchase_ledger v2・8開催) も **ROI 72.9% / PnL -70,433 / 838点** = combo は控除率ぶん丸負けと裏付け。
→ ふくだ決定: **器 (TARGET/IPAT実行インフラ) は残し、サイザーを gap単勝に差し替える**。

### 7.1 確定パラメータ (次セッション実装の前提)
- **買い方**: gap単勝 broad = `pred_rank_w≤3 ∧ gap≥5 ∧ cls∈{未勝利,条件,重賞} ∧ win_ev≥1` (全オッズ・odds帯フィルタは過学習で棄却済)。`select_gap_tansho` が canonical。
- **サイジング**: 1点 = **bankroll 実残高 × 1% (比例・100円単位・最低100円)**。固定額でなく残高連動 (Themis原則=入力に残高/破産ガード)。
  - 監査MC (実払戻13ヶ月・5000回): 比例1%は **破産確率0% / 中央 30万→86万 / 上振れ5%500万 / 最悪5%最終18万**。固定額3000円は破産2.7%。比例が全面的に優位。
  - 「1点を厚く」は勝つにつれ自動で叶う (残高増→1点増)。エッジ下振れ時もジワ減りで破産しない。
- **初期bankroll**: **30万 (隔離口座・本番bettype_autoの per_day 檻と分離)**。
- **combo (sanrentan_formation)**: 止める。
- **追加の買い方** (高ARD妙味穴の天井供給 等): 別途検討 (本件スコープ外)。

### 7.2 実装チェックリスト (次セッション)
1. **bankroll 実残高の追跡層** — 初期30万 + 累計実PnL。`settle_ledger` (portfolio_pnl) / `day_recovery` から現残高を取り「1点=残高×1%」を算出。更新は日次 (当日開始時残高) で可。
2. **gap単勝サイザーの配線** — `bettype_scheduler` は bankroll を引数で受ける設計。`select_gap_tansho`(broad) → 比例残高で1点額 → 投票。`size_race_*` 相当を新設 or gap専用 sizer。
3. **`bettype_auto.bat --sizing` を combo→gap単勝へ切替** (SJIS+CRLFバイト編集)。
4. **口座/檻の分離** — 30万専用。`manual-auto-bet-coexistence` の檻リスク回避。
5. テスト (sizer・残高連動・100円単位丸め) + dry → 次開催ライブ。
- **留意**: フォワード実績ゼロ・CI下限81%。比例1%が破産ガードを内包するので様子見0.5%は不要だが、エッジが下振れする可能性は残る。shadow (gap_tansho_shadow) と並走で乖離監視。

### 7.3 S176 実装 (本投票化を実装・★稼働は web の master switch 待ち★)
**方針決定 (ふくだ S176)**: 「実弾化する。比率は 1% でよいが ★画面で設定できるように★ しよう」。
→ `market_calibration_edge_map.md §8.4` の慎重論 (「今は実弾化せず shadow を溜める / deep フラクショナル
≤0.5%」) に対し、ふくだは **30万隔離口座での実弾化を選択・比率1%・web 設定可** とした。隔離口座 + 比例
(破産ガード内包) + master switch + shadow 並走監視で、リスクを限定しつつリアルな試行データを取る判断。
docs (SSoT) はこの実装内容を正本として記録する。

**実装 (S176・全て新規追加。combo の bettype_scheduler/sizing は無改変=即ロールバック可)**:
1. **`ml/strategies/gap_tansho_live.py`** (新) — config 読取 (`read_gap_config`: gap_enabled / gap_initial_bankroll_yen /
   gap_bet_pct / gap_day_pct を `bankroll/config.json settings` から)、bankroll 残高 (`account_balance` = 初期 +
   実現PnL)、サイズ (`stake_for` = 残高×比率・100円丸め・最低100)、`size_gap_race` (select_gap_tansho broad →
   RaceSizing)、`settle_gap_day` (実払戻で台帳に実現PnL を蓄積)。残高 = 初期30万 + 過去実現PnL の専用台帳
   `userdata/gap_tansho_live/ledger.json` (combo の purchase_ledger とは別の口座簿)。
2. **`ml/strategies/gap_tansho_scheduler.py`** (新・専用スケジューラ) — freebudget の安全機構 (timing/lock/state/
   halt/鮮度/連続失敗) + bettype の投票経路 (runner --bet) を ★import 流用★。state/lock/cage/bankroll は ★完全隔離★
   (`gap_tansho_scheduler_state.json` 等)。当日開始時に bankroll/日次cap を凍結。日次cap = 残高×day_pct% を
   純損失(回収差引)ベースで。per_race 上限は `read_per_race_cap` (=runner番人と同値) で複数点を fit。
   `--settle`/`--report`/`--halt`/`--resume`/`--confirm --i-understand-live`。
   **★master switch★**: `gap_enabled=False` (既定) なら静かに no-op = bat 切替後も web で有効化するまで1円も賭けない。
3. **web 資金管理画面** — `BudgetForm.tsx` に「gap単勝 自動投票（隔離口座）」セクション (有効/無効トグル・初期残高・
   1点比率%・日次cap%・1点額プレビュー)。`api/bankroll/config/route.ts` の `ConfigPatchBody`+`applyPatch` と
   `lib/bankroll/limit-resolver.ts` の型に gap_* を追加 (whitelist 方式なので両方必須)。
4. **`scripts/bettype_auto.bat`** — combo (`bettype_scheduler --sizing sanrentan_formation`) → `gap_tansho_scheduler`
   に切替 (SJIS+CRLF バイト保存・ロールバック用 REM + `.bak_s176`)。`scripts/settle_auto.bat` に夜間 gap settle 配線。
5. **テスト** `ml/tests/test_gap_tansho_live.py` (23 green: config/サイズ/残高/台帳/scheduler master switch・凍結・
   日次cap・冪等)。dry-run 実機で 6/21 を再現 (東京11R uma11 を 30万×1%=3000円で WOULD VOTE = shadow と一致)。

**運用 (次の手順)**: ① web 資金管理で gap を「有効」+ 初期残高30万 + 1点1% を保存 → ② 次開催 (6/28) から
Task Scheduler の bettype_auto.bat (gap live) が稼働 → ③ 夜 settle_auto が gap 台帳を更新し残高に反映。
**未配線/留意**: ①gap settle の late-payout catch-up は当日のみ (tansho は同日確定が基本)。②runner の purchase_ledger
記録は gap 専用 strategy タグ無し (税SoT には残るが gap 集計は別台帳)。③combo は停止 (bat 切替で no-op 化)。

---

## 8. 変更履歴
| Session | 変更 |
|---|---|
| 172 | 初版。ふくだ「型を捨てて全組み合わせから選定」ビジョンを設計化。東京9R(6万取り逃し)で型の限界を実証。①動的点数(頭数)は死蔵と確定。副産物=◎過剰人気 win_ev 見送りゲート(ev_gate=0.6 が現行超え)。較正バイアス(EV順=幽霊点/確率順=過剰人気◎)が本丸と再確認。 |
| 175 | gap単勝エッジを最初の収益源として本投票化を決定 (§7)。combo実払戻実績ROI72.9%/-70,433 で勝ち筋なしを裏付け。器は残しサイザーをgap単勝(broad)に差し替え・1点=残高×1%比例(破産0%)・初期30万隔離。次セッションで実装。 |
| 176 | 本投票化を実装 (§7.3)。ふくだ判断=実弾化する/比率1%/★画面で設定可★ (§8.4 慎重論に対し30万隔離+比例+master switchでリスク限定の上で実弾化を選択)。新規=gap_tansho_live.py (config/残高/サイズ/台帳)・gap_tansho_scheduler.py (専用・安全機構import流用・隔離state/cage)・web資金管理にgap項目・bettype_auto.bat切替 (combo停止・ロールバック可)・夜settle配線・テスト23green。★稼働は web で gap_enabled=true にするまで no-op★ (master switch)。次開催6/28から。 |

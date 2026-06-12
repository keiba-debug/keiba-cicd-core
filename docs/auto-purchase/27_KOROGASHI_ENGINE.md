# 27. 複勝転がしエンジン設計書（イクコ / 複勝転がし党）

> **作成日**: 2026-06-12（Session 154）
> **状態**: 設計案 v0.1 — 実装前。シズネレビュー未済
> **目的**: KAZEMACHI §11「複勝のみ・当たったら3回転がす」（イクコ）を自動投票で実現するための設計
> **関連**: characters.py の `fukusho_kenjitsu`、bet_templates の `fukusho_korogashi`、
> 21_MULTIBETTYPE_AUTO_OPS、17_NOTIFICATION_LAYER、[[character-betting-personas]]

---

## 0. TL;DR

転がしは既存の自動投票と**根本的に違う点が1つ**ある — **レースをまたぐ状態を持つ**こと。

```
既存: レースごとに独立判断（predictions → 選定 → 投票。前のレースの結果は見ない）
転がし: レースNの結果（的中+払戻額）を知ってから、レースN+1の投票額が決まる
```

これを既存の **単発パス方式スケジューラ**（freebudget/bettype_scheduler のパターン）に
**状態機械 + 状態ファイル** を足すことで実現する。新規ファイル4本、既存改修ほぼゼロ。

最大のリスクは技術でなく**データレイテンシ**：「前のレースの確定払戻が、次のレースの
締切までに mykeibadb に入っているか」。これが Phase 0（前提検証）の唯一の検証項目。

---

## 1. 要件

### 1.1 機能要件（イクコ仕様）

| 項目 | 内容 | 出典 |
|------|------|------|
| 券種 | 複勝のみ・◎1点 | 聖典§11.3「複勝のみ・当たったら3回転がす」 |
| 転がし | 的中したら払戻全額を次レースの複勝に再投資 | 同上 |
| セット完了 | 3連勝で利確（払戻を財布へ）。口癖「もう一回だけね」 | character_stock |
| セット失敗 | 1回でも外れたらセット終了（追いかけ禁止） | シズネ・ガードレール |
| 参戦レース | 全レースではない。「自分の好きなレース・条件」だけ | 聖典§11.1 |

### 1.2 ガードレール要件（シズネ Session 146 — 必須）

> 「複勝転がしは特に危険＝連勝で雪だるま＝§3動的調整なし違反そのもの。
> 転がすなら **1セットの元本上限＋利確/損切り回数を固定**」

| # | ガードレール | 設計での実現 |
|---|------------|------------|
| G1 | 1セット元本固定 | `set_stake`（例: 1,000円）。連勝中も元本は増やさない |
| G2 | 転がし回数固定 | `rolls = 3`。3連勝で**強制利確**（4回目はない） |
| G3 | 転がし額の絶対上限 | `roll_cap_yen`（例: 10,000円）。払戻がcapを超えたら超過分は財布へ戻し cap 額のみ転がす（部分転がし） |
| G4 | 隔離 bankroll・補充なし | イクコ専用財布（ringfence）。溶けたら当月終了。日次の自動補充をしない |
| G5 | 1日のセット数上限 | `max_sets_per_day`（例: 2）。負けたから追加、をさせない |
| G6 | per_race/per_day 檻との整合 | 既存 bankroll config.json の檻は**そのまま通す**（転がし額も per_race_max_yen を超えない） |
| G7 | 監査 | runner 経由で投票するため ledger v2 に自動記録。`set_id` で転がし系列を追跡可能に |

### 1.3 検証要件（過去の教訓から）

- **後知恵バイアス禁止**（[[feedback_odds_gate_hindsight]]）: レース選定に確定オッズを使わない。
  予測時点情報（◎の `pred_proba_p` 等）のみで選定。直前オッズを使う場合は predictions ソースで backtest。
- **着順ベース精算検証**（[[feedback_combo_backtest_settlement]]）: sim の的中判定は着順から再計算して検証。

---

## 2. 既存アーキテクチャとの対応（調査結果）

| レイヤ | 既存 | 転がしでの扱い |
|--------|------|--------------|
| テンプレ（純関数） | `strategies/bet_templates.py` の `fukusho_korogashi`（複◎+ワイド◎-○） | **そのまま使わない**。転がしは「複◎のみ」が本体（§5.4 未決-5 参照）。テンプレは「どの馬を買うか」までで、転がしは金額の時系列制御＝別レイヤ |
| キャラ | `strategies/characters.py` `fukusho_kenjitsu` | `korogashi` 設定フィールドを追加（rolls/set_stake/cap 等） |
| sim | `analyze/bankroll_core.py`（2層bankroll・日次粒度） | **日次粒度では転がしの順序依存を表現できない** → simulate_day_fn をレース時系列処理に拡張（§7） |
| 当日スケジューラ | `strategies/freebudget_scheduler.py` / `bettype_scheduler.py`（単発パス・1-2分毎・state JSON冪等・halt・檻） | **安全機構を import 流用**（bettype_scheduler が確立した流用パターンを踏襲）。差し替えは候補生成と状態機械のみ |
| 投票実行 | `target_clicker/runner.py`（`--bet race_id:fukusho:5:800` 形式） | そのまま利用。改修不要 |
| 結果取得 | `settle_purchases.get_db_finish_positions`（SE.KAKUTEI_CHAKUJUN）/ `settle_ledger` の haraimodoshi 払戻関数群 | **当日中にライブ照会**する関数として流用（§4.3）。レイテンシ検証が Phase 0 |
| 精算・税務 | `settle_ledger.py`（夜バッチ・ledger v2） | 変更不要。転がし投票も通常 ticket として精算される |
| 通知 | `target_clicker/notify.py`（TTS） | セット進行イベントを追加（「2連勝、転がします」）→ KAZEMACHI VOICEVOX 接続点 |

**結論: 既存改修はほぼゼロ。新規4ファイル + characters.py への設定追加だけで成立する。**

---

## 3. 状態機械（設計の核心）

### 3.1 セットの状態遷移

```
                    ┌─────────────────────────────────────────┐
                    │                セット (set_id)            │
                    └─────────────────────────────────────────┘

  IDLE ──開始条件OK──▶ LEG_PLACED(n=1) ──結果待ち──▶ 判定
                            ▲                          │
                            │                ┌─────────┼──────────┐
                            │               HIT       MISS     STALE/取消系
                            │                │          │          │
                            │          n<rolls?    SET_LOST   SET_ABORTED
                            │           │    │    (セット終了)  (§4.4 縁ケース)
                            │          yes   no
                            │           │    └──▶ SET_COMPLETE (3連勝・利確)
                            └─次leg投票─┘
```

### 3.2 状態の永続化

単発パス方式（プロセスは毎回死ぬ）なので、状態はファイルに永続化する。
freebudget の `state.json` パターンを踏襲し、**転がし専用 state** を別ファイルに持つ。

```
<day_dir>/korogashi_state.json        # live
<day_dir>/korogashi_state_dryrun.json # dry-run
<day_dir>/korogashi_scheduler.lock    # 排他ロック（stale 600s 上書き、freebudget流用）
```

### 3.3 state スキーマ（案）

```jsonc
{
  "date": "2026-06-14",
  "mode": "live",                    // live | dry-run
  "halted": false,
  "halt_reason": null,
  "wallet": {                        // G4: 隔離財布（当日スナップショット）
    "month_capital": 10000,          // 当月元本（補充なし）
    "available": 8000                // 残額 = 元本 - 進行中/喪失分 + 利確分
  },
  "sets_today": 1,                   // G5 カウンタ
  "active_set": {                    // null = IDLE
    "set_id": "20260614-IKUKO-01",
    "leg": 2,                        // 現在 leg（1..rolls）
    "stake": 1800,                   // 現在 leg の投票額
    "status": "waiting_result",      // planned | placed | waiting_result
    "race_id": "2026061405010205",
    "umaban": 7,
    "placed_at": "2026-06-14T11:32:08",
    "history": [
      {"leg": 1, "race_id": "...0103", "umaban": 3, "stake": 1000,
       "result": "hit", "payout": 1800, "finish_pos": 2,
       "payout_source": "haraimodoshi", "settled_at": "..."}
    ]
  },
  "completed_sets": [ /* SET_COMPLETE / SET_LOST / SET_ABORTED の履歴 */ ],
  "votes": { /* race_id → 投票記録（冪等性。freebudget と同形式） */ }
}
```

---

## 4. 当日スケジューラ（korogashi_scheduler）

### 4.1 パスごとの処理フロー（1-2分毎に Task Scheduler から起動）

```
1. lock 取得（stale 600s 上書き）・state 読込・halted チェック   ← freebudget 流用
2. predictions 鮮度チェック（vb_refreshed_at > 10分で skip）     ← freebudget 流用
3. 状態機械を1ステップ進める:
   [A] active_set が waiting_result の場合:
       → DB 照会: 着順（SE.KAKUTEI_CHAKUJUN）+ 複勝払戻（haraimodoshi）
       → 未確定: 何もしない（次パスで再照会）。ただし「次候補の締切」が迫っていたら
                 そのまま待つ（次候補を1本飛ばす）。当日最終レースを過ぎたら SET_ABORTED ではなく
                 leg結果確定まで待ち続け、確定後に SET_COMPLETE/LOST 処理（翌日 catch-up でも可）
       → MISS: SET_LOST。wallet 更新。セット終了
       → HIT : payout 計算 → leg == rolls なら SET_COMPLETE（利確、wallet へ）
               leg < rolls なら次 leg を planned に（stake = min(payout, roll_cap_yen) を100円丸め、
               超過分は wallet へ = G3 部分転がし）
   [B] active_set が planned の場合:
       → plan から次の候補レースを選定（条件: 投票ウィンドウまでに余裕 / §4.2）
       → 投票ウィンドウ内 [発走-6分, 発走-2分] なら runner --bet で投票
         （per_race/per_day 檻チェックは runner 側でも効く = G6 二重防御）
       → exit code 5/7/8 → halt（freebudget 流用）
       → 成功: status=waiting_result、state.votes 記録（冪等）
   [C] active_set が null（IDLE）の場合:
       → sets_today < max_sets_per_day かつ wallet.available >= set_stake
         かつ plan に未使用候補が残っている → 新セットを planned で開始
4. state 保存・lock 解放
```

### 4.2 レース選定（korogashi_plan — 朝バッチ）

転がしは「次に乗るレース」を動的に選ぶ必要がある（結果確定を待つ間に候補が締め切られるため）。
**朝に候補列を作り、当日はその中から「今乗れる次の1本」を選ぶ**2段構え。

```
korogashi_plan.json（朝、generate_bets 後に生成）:
  - 当日全レースから「イクコが参戦してよいレース」を発走時刻順に列挙
  - 選定条件（オッズ非依存・predictions 時点情報のみ = 後知恵禁止）:
      ・◎（AI印1位）の pred_proba_p >= p_floor（例 0.55）   ← イクコの「堅実」
      ・頭数 >= 5（複勝3着まで成立）
      ・障害戦除外（任意）
  - 各候補に post_time を持たせる（freebudget_race.load_post_times 流用）
```

当日の「次の1本」選定条件:
```
candidate.post_time - 6分 > now + result_margin_min
  （result_margin_min: 結果確定〜投票準備の余裕。初期値 2分）
かつ plan 順で最初の未消費候補
```

#### ⚠ 次レース最小間隔の制約（ふくだ指摘 2026-06-12 — 転がし固有の最重要運用制約）

前レース発走 T0 から次レース T1 に乗るには、確定→DB反映→投票ウィンドウの連鎖が必要:

```
T1 ≥ T0 + 約7分（走破+写真判定+確定）+ L（DB反映レイテンシ）
        + 2分（パス間隔）+ 6分（投票ウィンドウ頭 = 発走-6分）
  = T0 + 15 + L 分
```

| L（Phase 0 実測対象） | 必要間隔 | 帰結 |
|---|---|---|
| 5分 | 約20分 | 他場の中間レースも一部候補になる |
| 10分 | 約25分 | **実質「同場の次レース」専用**（同場間隔≈30分でギリギリ） |
| 15分 | 約30分 | 同場リレーすら危うい → 日またぎ（案C）へフォールバック |

- 3場開催の発走刻みは10分前後 → **直後の2〜3レースは構造的に全部スキップ**。
  36レースあってもリレー可能経路は限られる（plan の候補密度 ≠ 乗れる本数）
- 副作用: 1セット完走に約1時間（3 leg × 間隔30分弱）→ 午後遅い開始セットは
  完走前に当日レースが尽きる（→ §10 未決-7「セット開始デッドライン」）
- scheduler 実装では「`post_time(次候補) ≥ 結果確定見込み + margin`」を
  plan 消費時に毎回チェックし、満たさない候補は消費せず温存（前倒しスキップしない —
  結果が早く出れば近い候補に乗れることもあるため、判定は now ベースで動的に行う）

**将来拡張（備忘 2026-06-12）**: p_floor を満たす候補が複数ある時の順位付けに
**ペルソナ・バイアス層**を挿す構想（応援騎手・馬体重増好き・前走不利の挽回好き等の
「人間らしさ」= 選定の歪みこそ人格）。バイアスは選定順位にのみ作用し、
金額・檻には作用させない。詳細: `docs/kazemachi/idea/persona_bias_layer.md`

### 4.3 結果のライブ照会（最大の技術リスク）

| データ | ソース | 既存関数 | 確定タイミング（要検証） |
|--------|--------|---------|------------------------|
| 着順 | `umagoto_race_joho.KAKUTEI_CHAKUJUN` | `settle_purchases.get_db_finish_positions` | レース確定後、JV速報→DB同期次第 |
| 複勝払戻 | `haraimodoshi.FUKUSHO*` | `settle_ledger` 内払戻関数群 | 同上 |
| （補助）確定複勝オッズ | `odds1_fukusho` | `odds_db.get_final_place_odds` | 同上 |

**払戻の正は haraimodoshi**（settle_ledger と同じ。シズネ🔴-2「不正確な暫定値を書かない」と同思想）。
haraimodoshi が未着で着順だけ確定している場合も**転がさない**（払戻額が分からないのに次の stake を
決めるのは G1-G3 の意味を壊す）。次パスで再照会。

**Phase 0 検証**: 開催日に「レース確定時刻 → KAKUTEI_CHAKUJUN がDBに現れた時刻 →
haraimodoshi が現れた時刻」を1日分ログして、レイテンシ分布を実測する（観測スクリプト1本）。
→ p95 が15分以内なら同場リレー転がしは成立。それ以上なら §8 代替案へ。

### 4.4 縁ケース

| ケース | 扱い |
|--------|------|
| ◎が投票前に取消 | その候補をスキップして次の候補へ（賭けていないので状態は planned のまま） |
| 投票後に取消・返還 | 複勝100円元返し相当。**転がし中断（SET_ABORTED）**とし返還額は wallet へ。判定の自動化が難しければ「haraimodoshi に該当馬番がなく着順も無い」を検出して halt+手動確認が安全側 |
| 同着で複勝4頭 | haraimodoshi に従う（既存 settle と同じ） |
| 当日最終レースまでに結果未確定 | セットは waiting_result のまま持ち越し。翌朝 catch-up パスで精算のみ実施（転がしはしない） |
| scheduler クラッシュ | lock stale 上書き + state 冪等で次パスが継続（freebudget 実績パターン） |
| 「次レースが無い」（最終R で HIT） | その時点で利確（rolls 未満でも SET_COMPLETE 扱い、reason="no_more_races"） |

---

## 5. モジュール構成（新規4本 + 設定追加）

```
ml/strategies/korogashi.py            # ① 純ロジック層（DB/IO非依存・最重要）
    - KorogashiConfig (rolls, set_stake, roll_cap_yen, max_sets_per_day,
                       p_floor, result_margin_min, ...)
    - SetState / LegResult dataclass 群（state JSON ⇄ オブジェクト）
    - transition(state, event) -> (new_state, actions)   # 状態機械の遷移純関数
    - next_stake(payout, cfg) -> (stake, overflow)        # G3 部分転がし計算
    → bet_templates.py と同じ「純関数層」思想。pytest でフル網羅（遷移表テスト）

ml/strategies/korogashi_plan.py       # ② 朝の候補列生成
    - build_plan(predictions, cfg) -> plan dict
    - CLI: python -m ml.strategies.korogashi_plan --date today
    → 出力: <day_dir>/korogashi_plan.json

ml/strategies/korogashi_scheduler.py  # ③ 当日スケジューラ
    - freebudget_scheduler から lock/state/halt/檻/鮮度 を import 流用
      （bettype_scheduler が確立した流用パターン）
    - §4.1 のパス処理。投票は runner を --bet 単発起動
    - CLI: --date today [--confirm --i-understand-live] [--now HH:MM] [--halt]
    - dry-run では「投票したつもり」で state を進める（結果照会は実DBを使う
      = 投票以外フルリハーサル可能。KAZEMACHI 第0回はこのモードで動かせる）

ml/analyze/simulate_korogashi.py      # ④ backtest / sim
    - §7 参照。bankroll_core.run_trajectory に注入する simulate_day_fn を
      「日内レース時系列で状態機械を回す」実装にする
    - korogashi.py の遷移関数を**そのまま**使う（sim と live でロジック共有 =
      sim 乖離を構造的に防ぐ）

ml/strategies/characters.py           # 設定追加（既存改修はこれだけ）
    - Character に korogashi: Optional[KorogashiConfig] = None を追加
    - fukusho_kenjitsu（イクコ）に設定を付与
```

**置かないもの**: bet_engine.py への組み込み（転がしは bets.json の事前生成と相性が悪い
— 金額が当日の結果依存で事前に決まらない。candidates は plan、金額は scheduler が持つ）。

---

## 6. 金額計算の仕様（G1-G3 の具体化）

```
leg1 stake = set_stake                               （例: 1,000円・固定）
leg(n+1) stake = floor_100( min(leg_n_payout, roll_cap_yen) )
overflow = leg_n_payout - leg(n+1) stake → wallet へ（部分転がし）
SET_COMPLETE: leg_rolls の payout 全額 → wallet
SET_LOST: 何も戻らない（leg_n stake は leg_(n-1) payout 由来なので、
          セットの実損 = set_stake のみ。これが「転がしの実態は元本1,000円の宝くじ」
          という構造的安全性。イクコの「3着でいいのよ」の数理的正体）
```

数値例（複勝1.8倍 × 3連勝、cap 10,000円）:
```
leg1: 1,000円 → 払戻1,800
leg2: 1,800円 → 払戻3,240 → 3,200(丸め) ※40円はwalletへ
leg3: 3,200円 → 払戻5,760 → 利確
セット収支: +4,800円 / リスクは常に元本1,000円
```

---

## 7. sim / backtest 設計（Phase 2）

現行 character-sim は**日次合算**（simulate_day_fn が日の cost/payout を返す）。
転がしは日内の**順序**に意味があるため、day_fn の中身をレース時系列処理にする:

```
simulate_day_fn(ctxs, *, day_start, w_total, **kw):
    ctxs を post_time 順にソート
    state = IDLE
    for race in ctxs:
        korogashi.transition() を発走時刻順に適用
        （結果確定レイテンシ L 分を仮定し、post_time + L 以降に
          結果が「見える」制約をシミュレート。L は Phase 0 の実測値）
    return (day_cost, day_payout)
```

- 的中判定は**着順から再計算**し payout は確定複勝オッズ×stake（[[feedback_combo_backtest_settlement]] 準拠の検証スクリプト併設）
- 出力指標: セット成功率（3連勝率）、セット期待値、月次軌道、maxDD、
  「レイテンシ L 感度」（L=5/10/15分でセット成立数がどう変わるか）、
  **リレー可能本数**（§4.2 間隔制約で当日何セット組めたか — 候補密度ではなく
  実際に乗れた経路数。max_sets_per_day の檻が効く前に物理制約で頭打ちになる可能性を確認）
- 理論値: 複勝的中率を p とすると 3連勝率 = p³（p=0.65 → 27%、p=0.75 → 42%）。
  p_floor の設定がセット成功率を直接決める。backtest で p_floor スイープする
- **KAZEMACHI 接続**: この backtest 軌道が「イクコの第0世代の記憶」（レイの
  「プロトタイプの墓場」案）。セット履歴はそのままセリフ生成の感情パラメータになる
  （2連勝中=「もう一回だけね」、SET_LOST=「3着でいいって言ったのにねえ」）

---

## 8. 代替案の検討（採らなかった/保留の案）

| 案 | 内容 | 判断 |
|----|------|------|
| A. 疑似転がし（事前決め打ち） | 朝の時点でレース3本と金額を固定（1000→1800→3240 を仮定額で） | ❌ 払戻額が事前に分からない以上「転がし」にならない。的中時の再投資額がズレて G3 を破る |
| B. IPAT 残高ベース | 払戻は IPAT 残高に入るので残高照会で判定 | ⏸ 残高スクレイピングは未実装・壊れやすい。haraimodoshi で足りる見込み。Phase 0 で DB レイテンシが致命的だった場合の代替候補 |
| C. 日またぎ転がし | leg を日単位にする（土曜的中→日曜に転がす） | ⏸ レイテンシ問題が消える堅実案だが「その日のうちにもう一回」というイクコらしさが消える。**Phase 0 の結果が悪かった場合のフォールバック**として温存 |
| D. websocket/速報API直結 | JV-Link 速報イベント駆動 | ❌ 単発パス方式の安全実績を捨ててまで要らない。パス間隔1-2分で十分 |

---

## 9. 安全機構まとめ（シズネレビュー観点の先回り）

1. **デフォルト dry-run**。実弾は `--confirm --i-understand-live` 二重フラグ（freebudget 踏襲）
2. **状態ファイル冪等**: votes 記録で同レース二重投票なし。lock で多重パス防止
3. **halt 連鎖**: runner exit 5/7/8 → 当日 halt（freebudget 踏襲）+ 転がし固有 halt
   （結果照会の矛盾検出 = 着順あるのに払戻無し等）
4. **檻の三重構造**: イクコ財布（月次元本・補充なし）⊂ per_day_max_yen ⊂ per_race_max_yen
   （既存檻はバイパスしない。G6）
5. **手動投票との共存リスク**（[[manual-auto-bet-coexistence]]）: per_day 檻が自動分しか
   縛らない構造はここでも同じ。イクコ財布の絶対額を小さく保つ（月1万円等）ことで吸収
6. **「ズルズル補充」の構造的禁止**: wallet.month_capital は config に手書きする月次定数。
   scheduler は減らすことしかできない（増やすコードパスを作らない）
7. **通知**: セット開始/転がし/利確/喪失 を TTS+Toast（17_NOTIFICATION_LAYER 拡張）。
   失敗系は三重通知（音声+Toast+監査ログ）

---

## 10. 未決事項（ふくだ判断待ち）

| # | 論点 | カカシ推奨 |
|---|------|-----------|
| 1 | 転がしは同日内のみか | **同日内のみ**（イクコらしさ。日またぎは案Cとして温存） |
| 2 | set_stake / roll_cap / max_sets / 月次元本の初期値 | 1,000円 / 10,000円 / 2セット / 10,000円（= 最悪でも月1万円の娯楽費） |
| 3 | レース選定の p_floor | backtest でスイープしてから決める（0.55-0.75）。「イクコは堅い◎しか買わない」が人格と整合 |
| 4 | 投票後取消・返還の扱い | SET_ABORTED + 返還額 wallet 戻し。検出が曖昧なら halt+手動（安全側） |
| 5 | fukusho_korogashi テンプレのワイド成分 | 転がしには**含めない**（複勝のみ）。ワイド◎-○ボーナスは転がし外の通常ベットとして残す（テンプレ側で weight 調整 or 転がし専用テンプレ `fukusho_pure` 新設） |
| 6 | KAZEMACHI 第0回との関係 | Phase 2 (backtest) と Phase 3 (dry-run) がそのまま第0回素材。実弾は不要 |
| 7 | セット開始デッドライン（§4.2 間隔制約の副作用） | 1セット完走≈1時間。残り候補が3本未満の時間帯に新セットを **(a)開始しない** か **(b)開始して途中利確(no_more_races)許容** か。カカシ推奨は **(b)**（イクコは「時間が無いから買わない」人ではない + 途中利確は損ではない）。backtest で (a)(b) 比較可能 |

---

## 11. 実装ロードマップ

| Phase | 内容 | 規模感 | 依存 |
|-------|------|--------|------|
| **0** | **レイテンシ実測**: 開催日に SE 着順 / haraimodoshi のDB出現時刻を1日ポーリングしてログ（観測スクリプト1本） | 小 | 次の開催日 |
| 1 | `korogashi.py` 純ロジック + 遷移表テスト | 中 | なし（今すぐ可能） |
| 2 | `simulate_korogashi.py` backtest（p_floor/L 感度、月次軌道）→ 未決2/3 を数値で決める | 中 | Phase 1 |
| 3 | `korogashi_plan.py` + `korogashi_scheduler.py` **dry-run 運用**（投票なし・実DBで状態遷移だけライブ）= KAZEMACHI 第0回エンジン | 中 | Phase 0,1 |
| 4 | シズネレビュー → 実弾（--confirm --i-understand-live） | 小 | Phase 3 + 口座分離検討 |

**Phase 1 と Phase 0 は並行可能**。純ロジック層はレイテンシ問題と独立。

---

## 12. 参照ソース（本設計の根拠にした既存実装）

| ファイル | 参照した点 |
|---------|-----------|
| `ml/strategies/freebudget_scheduler.py` | 単発パス・lock/state/halt/檻/鮮度・投票ウィンドウ [発走-6, 発走-2] |
| `ml/strategies/bettype_scheduler.py` | 安全機構 import 流用パターン・state別ファイル衝突回避 |
| `ml/strategies/bet_templates.py` | 純関数層の思想・fukusho_korogashi テンプレ |
| `ml/strategies/characters.py` | fukusho_kenjitsu・ringfence 設計・比例ベット |
| `ml/analyze/bankroll_core.py` | simulate_day_fn 契約・2層bankroll |
| `ml/target_clicker/runner.py` | --bet 単発投票 IF・exit code・bankroll 檻 |
| `ml/settle_ledger.py` / `ml/settle_purchases.py` | haraimodoshi 払戻関数・SE 着順照会・「不正確な暫定値を書かない」原則 |
| `core/odds_db.py` | get_final_place_odds（確定複勝オッズ） |

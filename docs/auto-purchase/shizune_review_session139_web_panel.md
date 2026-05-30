# シズネレビュー — Session 139 / web 自動投票コントロールパネル (Stream B)

> 対象: ブラウザから freebudget 自動投票スケジューラを 開始/dry-run/停止 + 当日の投票状況を監視するコントロールパネル。
> **ブラウザから実弾投票が飛びうる新経路**のため、リスク管理視点で 2 巡 adversarial レビュー。

## 結論（2巡目 最終判定）

**条件付き GO**
- **dry-run / 監視用途 = 今日から無条件 GO**（投票経路に到達しない。status は fs 読みのみ。halt は安全側）。
- **web LIVE 実弾 = 将来「軽微🔴 1 点を直してから GO」**（下記 §残課題）。
- 今日 2026-05-31 (OOS 2 日目) の実弾は **既存 `freebudget_vote.bat` 経由**。web は観測窓として使う（ふくだ判断）。

## レビュー対象ファイル
- `keiba-v2/web/src/components/bankroll/AutoVoteControl.tsx`（本体UI）
- `keiba-v2/web/src/app/api/freebudget/{start,halt,status}/route.ts`
- `keiba-v2/web/src/lib/data/freebudget-scheduler-reader.ts`
- `keiba-v2/ml/strategies/freebudget_scheduler.py`（`halt_day` / `--halt` / `vote_one_race`）
- `keiba-v2/ml/target_clicker/runner.py`（per_race ハードチェック `_check_per_race_limits`）
- `data3/userdata/bankroll/config.json`（`limit_mode=absolute / per_race_max_yen=3000 / per_day_max_yen=10000`）

---

## 1巡目 指摘と対応（🔴2 / 🟡5）

| # | 指摘 | 対応 |
|---|---|---|
| 🔴-1 | 確認額 (artifact total) と実投票額 (scheduler が毎パス最新オッズで再計算) が乖離しうる。UI 脚注「サーバ側で買い目合計を再照合(不一致なら拒否)」は**虚偽記述**（scheduler は artifact を照合しない） | **ふくだ判断: 「直前の最新オッズで買えたものが正、最後の判断が正」= 再計算が正で乖離は『仕様』**。→ 脚注を正直に書き換え（「上の金額は朝の計画額。実投票は最新オッズで再計算され変動しうる/日次・レース上限の範囲内」）。**真の安全弁は承認額でなく config の per_race/per_day ハードキャップ**（§認識合わせ参照） |
| 🔴-2 | 日付ピッカーに制約がなく過去日/未来日に LIVE を撃てる | LIVE を当日限定: API `date !== resolveDate('today')` → 400 / UI `liveEnabled = isToday && ...` + ボタン title 理由。dry-run は任意日 OK |
| 🟡-1 | start API に halted チェック無し（curl 直叩きでバイパス可） | `getSchedulerStatus(date).halted` → 409。scheduler 側 state.halted + UI `!halted` と三重 |
| 🟡-2 | `confirmed_total_yen === fundedTotal` 厳密等価が浮動小数で割れうる | `Math.round()` 両辺 + `Number.isFinite` ガード |
| 🟡-3 | lock 600s 鮮度 / 15s ポーリング / 複数端末運用の running 表示 | 本ドキュメントに運用前提を明記（JST・単一マシン前提） |
| 🟡-4 | SSE クライアント中断でも Python child は kill されない（タブ閉じても投票継続） | UI LIVE ダイアログに「タブを閉じても投票は継続、止めるには[停止]」を明記（mid-vote kill はかえって危険なので kill しない設計） |
| 🟡-5 | `sanitizeReason` が日本語を消す | 現状 reason は固定文字列 `manual_stop_via_web` で無害。将来ユーザー入力化する時は enum 化（将来課題） |

## 2巡目 確認結果（実コード file:line）

- **🔴-1 を「仕様+honest text+ハードキャップ」で閉じてよい**: runner `_check_per_race_limits`（config 3000 を直接読む）が `--max-yen` と独立に効き、超過で **exit 5 → `HALT_EXIT_CODES` → 当日 halt**。scheduler 日次は `voted_yen+sub.total_yen>per_day_max_yen(10000)` で skip。**「最新オッズ判断が正」でも 1 レース 3000 / 1 日 10000 の檻は誰も外せない** = ふくだ哲学とリスク管理の両立構造。
- 🔴-2 / 🟡-1 / 🟡-2 の修正は十分（多層で効く）。
- dry-run / 監視は今日から無条件 GO（投票経路に到達しない。status は fs 読みのみ。halt は安全側）。
- SSE arbitrary input（date 正規表現 / reason sanitize / confirmed 型チェック）、status reader 例外（try/catch で null・500 は最外 try）、日付境界（不一致は拒否側に倒れる）、halt sticky（進行中 1 レースは止まらない=設計通り、UI 開示済）— いずれも問題なし。

---

## ★認識合わせ（記録上 譲れない点）★

**web LIVE の「承認額」は実投票額の上限を保証しない。** 朝の計画 (`freebudget_bets.json` total) を確認・承認しても、各レースのウィンドウ到達時に最新オッズで再計算されるため、実際に飛ぶ金額・買い目は変わりうる（ふくだ哲学＝それが正）。

**本当の上限 = config の `per_race_max_yen=3000` / `per_day_max_yen=10000`**（runner + scheduler の二段ハードキャップ、コードで実効確認済）。承認額照合は「朝の計画と画面の一致確認」のみ。

→ 「承認したのと違う額が飛んだ」となっても、それは仕様（最新オッズ判断が正）であり、檻は 3000/10000。この理解をふくだと共有済みとして記録する。

---

## 残課題（将来 web LIVE 本稼働前）

1. **`vote_one_race` の `--max-yen=amount`**（`freebudget_scheduler.py:170-178`）は per_race 3000 キャップになっていない（再計算後の total ちょうど = leftover/idempotency の二次確認）。救い: runner の config チェックが独立に効く。本稼働前に `--max-yen min(amount, per_race_max_yen)` にするか現状維持（コメントは Session 139 で正直に修正済）。**今日の dry-run/監視・bat 実弾には無関係。**
2. **per_race=3000 vs 1 馬 cap=1000 の整合**: freebudget Kelly が 1 レースに 4 頭 funded すると 4×1000=4000 > per_race 3000 → runner exit 5 → 当日 halt。「想定内の停止」か、per_race を上げる / 1 馬 cap を絞るか、ふくだ確認待ち。
3. 運用前提: **JST・単一マシン前提**（UI todayStr とサーバ resolveDate('today') が一致する前提）。複数端末運用時は running 表示の意味に注意。

## テスト
`ml/tests/test_freebudget_scheduler.py` に `halt_day` 系 6 件追加（冪等 / votes 保全 / 破損理由保持 / dir 未作成でも mkdir / live・dry 両 halt）→ 13 passed。web tsc / eslint クリーン。Python 414 passed（既存 7 fail = test_bet_engine 無関係）。

# 21. multi-bettype 自動投票 運用 Runbook (Session 140)

> 全7券種（単/複/馬連/ワイド/馬単/三連複/三連単）を各レース締切前に最新オッズで自動投票する
> `bettype_scheduler` の運用手順。 freebudget（単勝のみ）の安全機構を流用した別系統。
> 関連: `19_OOS_RUNBOOK.md`, `10_BANKROLL_CONTROL.md`, `14_LEDGER_SCHEMA.md`,
> `shizune_review_session140_multibettype.md`, メモリ `bet-adjustment-items`。

## TL;DR（よく使う）
```bash
# 緊急停止（投票だけ止める・当日 halt。 タスクは残る）
python -m ml.strategies.bettype_scheduler --halt

# 完全停止（Task Scheduler タスク削除＝再発火しない）
schtasks /delete /tn KeibaBettypeAuto /f

# dry 確認（投票しない・各レースの選定+サイジング+--bet 一覧）
python -m ml.strategies.bettype_race --date today --strategy concentrate
```

## 構成
- `ml/strategies/bettype_scheduler.py` — 当日スケジューラ（単発パス。 Task Scheduler が1分毎に叩く）
- `ml/strategies/bettype_sizing.py` — サイジング（アンカー◎単/複=Kelly + 複合=per_race 残予算 EV 比例配分）
- `ml/strategies/bettype_race.py` — per-race dry ビュー（投票しない検証用）
- `scripts/bettype_auto.bat` — Task Scheduler 用ラッパー（`dry`/`live`、ログ `data3/logs/bettype/<date>.log`）
- 投票実体 = `ml/target_clicker/runner.py` を `--bet "race:券種:馬/馬:額"` 群で起動 → TARGET → IPAT
- 状態: `data3/races/<Y>/<M>/<D>/bettype_scheduler_state[_dryrun].json`（freebudget とは別ファイル）

## 前提（LIVE で実際に click されるための条件）
1. **TARGET アプリ起動 ＋ IPAT ログイン済 ＋ 口座入金**（無いと click 失敗→halt＝安全側で停止）
2. **vb_refresh が稼働**（オッズ鮮度 >10分 で LIVE は投票 skip。 `predictions.vb_refreshed_at` を確認）
3. **predictions.json 生成済**（当日の予測・買い目）
4. **IPAT 排他**: freebudget の live を**同時に起動しない**（IPAT は1セッション。 bettype はアンカー単=freebudget 相当を含むので bettype 単独で足りる）

## 開始（arm）
Task Scheduler に登録（1分毎・当日 11:00-18:00・ログオン中＝対話セッションで GUI click）:
```bash
schtasks /create /tn "KeibaBettypeAuto" /tr "C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\bettype_auto.bat live" /sc minute /mo 1 /st 11:00 /et 18:00 /f
```
- バッチが毎分 `bettype_scheduler --date today --confirm --i-understand-live --strategy concentrate --per-day-max-yen 30000` を実行。
- 窓内レースが無いパスは何もしない（空振り）。 各レース [発走-6分, 発走-2分] でのみ投票。
- **段階ロールアウト推奨**: 初日や設定変更後は最初の1レースを画面で見守り、 正常なら継続。

## 停止
| 目的 | コマンド | 効果 |
|---|---|---|
| **緊急停止**（投票を止める） | `python -m ml.strategies.bettype_scheduler --halt` | 当日 state を halted=True。 以降のパスが全 skip（進行中の1レースは止まらない）。 タスクは残るので翌日また動く |
| **完全停止**（タスク撤去） | `schtasks /delete /tn KeibaBettypeAuto /f` | Task Scheduler から削除。 再発火しない |
| 当日の再開（halt 解除） | state JSON の `halted` を false に（手動）or 翌日へ | halt は当日限り。 翌日は fresh state |

★`--halt` は live/dry 両 state を halt（安全側操作なので二重フラグ不要）。

## 監視
- **見送り音声通知**（Session140 ふくだ要望）: 窓内で評価したが投票しないレース（買い目なし/日次予算上限）を**1回だけ**音声で「○○R 見送り」と通知（live のみ・`notified_skips` で重複抑止）。「動いてない」のか「評価して見送った」のか区別がつく。抑止は `--no-skip-notify`。
- ログ: `data3/logs/bettype/<date>.log`（各パスの now/候補/投票/skip/halted）
- 状態: `bettype_scheduler_state.json` の `votes[race_id]`（amount/exit_code/bet_specs/legs/anchor_yen/combo_yen）
- 台帳: `data3/userdata/purchase_ledger/<date>.json`（券種・馬番・金額・IPAT receipt）
- exit code: 0=成功 / 5,7,8=halt（セッション切れ等）→当日停止 / 1,4=失敗（連続2回で halt）

## 檻（資金上限）
- `per_race_max_yen=3000` / `per_day_max_yen=30000`（`data3/userdata/bankroll/config.json`、 scheduler と統一）
- 多層: ① scheduler が per_day 残予算超のレースを skip ② `--max-yen=min(total, per_race, per_day残)` を runner に渡す ③ runner `_check_per_race_limits`（config 直読み・per_race 正本）④ 連続失敗・セッション切れで halt
- ★per_day を変えたら config と scheduler の `--per-day-max-yen` を**必ず揃える**（不一致は檻の最終段が無効化＝シズネ Session140 🔴-1）

## サイジング（既定 anchor_kelly_combo_ev）
- アンカー◎単 = freebudget Kelly（p=pred_proba_w_cal, odds=単オッズ）。 ◎複 = Kelly（place_odds_min 最低値）。 EV≤1 は 0（買わない）。
- 複合 = per_race 残予算を EV 比例で各券種に配分 → plan 内は逆オッズ。 排反/相関のため naive per-leg Kelly はしない（oversize 回避）。
- 同一券種の入れ子幅（◎-相手2/3/4）は**券種ごと最良EV1つに dedup**（重複買い防止）。
- `--strategy`（concentrate/ev_floor/spread_if_worth/hole_seeker）/ `--sizing` で差し替え可。

## 後始末（レース終了後）
1. **タスク削除**: `schtasks /delete /tn KeibaBettypeAuto /f`（毎日11-18時に再発火するため必須）
2. **収支照合**: `python -m ml.settle_ledger --date <date>`（確定配当→ledger payout）+ ledger ビュー
3. **config 戻す判断**: per_day を 30000 のまま継続 or 10000 へ（`bankroll/config.json`、 notes に記録）

## 既知の調整候補（→ メモリ `bet-adjustment-items`）
- 複勝アンカーの低オッズは薄利・非対称 → 除外/最低オッズ floor/最低利益閾値（v2 サイジング）
- ledger の portfolio_strategy が "manual_cli" 記録（runner --bet ラベル）→ 自動分 ROI 分離のため strategy タグ化（v2）

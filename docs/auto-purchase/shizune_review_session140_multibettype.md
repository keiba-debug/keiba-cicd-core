# シズネレビュー — Session 140 multi-bettype 自動投票スケジューラ

> レビュー対象: 今日午後から無人 LIVE 運用する金経路の新システム
> レビュアー: シズネ（リスク管理・ブレーキ役）
> 日付: 2026-05-31
> 対象コミット前提: `bettype_sizing.py` / `bettype_scheduler.py` / `bettype_race.py` / `bettype_auto.bat` 新規

---

## 結論（先に3行）

**条件付き GO。実装の品質は高く、サイジングの健全性・dedup 修正・安全機構の継承はいずれも合格。ただし LIVE arm 前に潰すべき 🔴 が 1 件ある。**

- 🔴-1（必須）: `config.json per_day_max_yen=10000` と scheduler `--per-day-max-yen 30000` が**食い違っており、runner 側の per_day ハードキャップが累積を止めない**。檻の二重化が破れている。
- これさえ整合させれば（config 側を 30000 に上げる or scheduler を config と揃える）、**今日午後の「1 レースだけ実弾 arm（ロールアウト Step5）」に進んでよい**。
- 本格 live（複数レース連続）は、1 レース実弾で ledger / IPAT 受付 / state(exit 0) / 二重投票なし を確認してから。

---

## 🔴 LIVE 前に必須

### 🔴-1: per_day の檻が二重化されていない（config=10000 vs scheduler=30000）

**最も金が消えうる経路。これが本レビューの本丸。**

- `config.json` は `per_day_max_yen: 10000`（`C:/KEIBA-CICD/data3/userdata/bankroll/config.json`）。
- 一方 `bettype_scheduler.py:57` `DEFAULT_BETTYPE_PER_DAY_MAX_YEN = 30000`、`bettype_auto.bat:23,25` も `--per-day-max-yen 30000`。
- runner の per_day 検証（`runner.py:395`）は **その subprocess に渡された `--bet` 合計しか見ない**。各レースは per_race=3000 以下なので、1 レース subprocess は必ず `3000 <= 10000` で通る。
- 実証（このレビューで確認）:
  ```
  runner が読む config: enabled=True per_day=10000 per_race=3000
  1レース 3000円 <= per_day(10000)? True (runner は通す)
  => scheduler が30000まで7レース回しても runner は毎回 3000<=10000 で通す
     = config per_day=10000 は累積を止めない。
  ```
- **意味**: per_day=30000 の累積上限を守る正本は **scheduler の state 累積（`bettype_scheduler.py:266` `voted_yen + rs.total_yen > per_day_max_yen`）だけ**になる。runner config（10000）は「1 subprocess あたり 10000」としてしか効かず、累積30000 のガードに**一切寄与しない**。
- これは Session 139 の学び「真の安全弁は承認額でなく config の per_race=3000/per_day=10000 ハードキャップ（runner exit5→halt）」と**直接矛盾**する。今の状態では「真の安全弁（config per_day）」が無効化されている。
- 危険シナリオ: scheduler の state ファイルが（破損でなく）何らかの理由で voted の累計を取りこぼす／別 state ファイルに分離されて累計が分断される／--per-day-max-yen を手で大きく渡す——のいずれでも、runner 側に最後の砦が無いため 30000 を超えて投票が通りうる。

**修正案（どちらか一方。LIVE arm 前に必須）**:
- (a) 推奨: 今日の運用上限を本当に 30000 にするなら、**config.json の `per_day_max_yen` を 30000 に上げる**（per_race=3000 は据え置き）。これで runner も「1 subprocess ≤ 30000」を見る——が、これでも累積二重化にはならない点に注意（下記 b と併用が理想）。
- (b) より堅い: scheduler が runner に **その日の残予算（`per_day - voted_yen`）を `--max-yen` の上限として渡す**。現状 `vote_one_race_multi:154` は `max_yen = min(amount, per_race_cap)` で per_race しか効かせていない。ここを `min(amount, per_race_cap, per_day_remaining)` にすれば、runner の `--max-yen` が累積の砦になる（ダイアログ層 + bankroll 層の両方で効く）。
- (c) 最小対応: config と scheduler を**同じ値に揃える**だけでも「食い違いによる事故」は消える。ふくだが「今日は 30000 で回す」なら config を 30000 にする。「いや 10000 が真の上限」なら scheduler を 10000 に下げる（初日カバー方針と要相談）。

**ふくだ判断が要る点**: 「今日の per_day の真の上限は 10000 か 30000 か」。30000 なら config を上げる、10000 なら scheduler を下げる。**どちらかに統一しないまま LIVE は NO-GO**。

---

## 🟡 推奨（LIVE 中 or 直後に対応）

### 🟡-1: 複勝アンカーの元本効率が極端に悪い（低オッズ複勝の罠）

- dry 実測で複勝が低オッズで fund されている: 東京3R `fukusho 6 ¥400 odds=1.4`、京都1R `fukusho 6 ¥600 odds=1.8`、東京4R `fukusho 5 ¥400 odds=1.3`。
- 数値検証（このレビューで確認、bankroll=10000 / kelly 0.25 / cap 0.10）:
  ```
  place p=0.85 odds=1.1 EV=0.94 -> 0円      (EV<1 なので張らない=健全)
  place p=0.80 odds=1.3 EV=1.04 -> 300円 (払戻390, 利益90)
  place p=0.70 odds=1.4 EV=0.98 -> 0円
  place p=0.65 odds=1.8 EV=1.17 -> 500円 (払戻900, 利益400)
  ```
- **評価**: calc_kelly_fraction は EV≤1 で 0 を返すので「複勝1.1倍に1000円暴走」は**起きない**（当初の私の懸念は外れ。設計は健全）。よって🔴ではない。
- ただし EV>1 でも複勝1.3倍に300円賭けて利益90円は、的中率は高いが「ほぼ確実に当たるが利益が薄く、外したとき(～20-30%)に元本が消える」非対称。これは数学的には正しいが、**ふくだの心理（「当たったのに増えない」「外したとき痛い」）と相性が悪い**。
- place_odds_min（最低値=保守）使用は妥当（過大評価を防ぐ）。むしろ保守側なので問題なし。
- **推奨**: 複勝アンカーに **最低オッズ floor**（例 odds < 1.5 の複勝はアンカーから外す or EV floor を複勝だけ 1.1 に上げる）を検討。今日の LIVE は現状のままでも資金消失リスクは低い（cap 1000 + EV>1 ゲート）ので、🟡（運用後チューニング）に留める。

### 🟡-2: IPAT 排他が運用前提のみで、コードによる相互排他がない

- lock は別系統（`bettype_scheduler.lock` vs `freebudget_scheduler.lock`、`bettype_scheduler.py:65`）。設計通り state を汚さないのは正しいが、**両方を Task Scheduler に live で入れると、ロックが別なので両方とも走りうる**。
- bettype はアンカー単=freebudget 相当を含むので、両方 live = **同一レースに二重投票 + IPAT セッション競合**のリスク。
- 現状の歯止めは「今日は bettype のみ Task Scheduler に入れる」という**運用前提のみ**（プランの「IPAT 排他＝今日は bettype 単独 live」）。
- **推奨**: 共通の「live 排他ロック」（例 `ipat_live.lock` を両 scheduler が live 時のみ取得）を入れると、設定ミスで両方 arm しても片方が降りる。今日は運用で担保（freebudget の Task Scheduler を無効化したことをふくだが目視確認）すれば LIVE 可。コードでの相互排他は次セッションの宿題。

### 🟡-3: runner の per_day=10000 に各レースが「個別には」通る前提が、per_race=3000×4頭で崩れうる

- Session 139 宿題②に既出の論点: `per_race=3000` だが、1 馬 cap=1000（per_bet_cap_pct 0.10 × bankroll 10000）。アンカー単+複+複合が積み上がると 1 レースで 3000 に達する（dry で東京2R/7R/京都1R/2R が 2800〜3000）。
- これ自体は `fit_legs_to_cap` で 3000 に truncate されるので per_race は破れない（dry で全レース ≤3000 を確認）。問題なし。
- ただし **runner の per_race 検証は config per_race_max_yen=3000 で groupby 合計を見る正本**（`runner.py:248-279`）なので、scheduler が 3000 ちょうどを送ると境界。`fit_legs_to_cap` は `<= cap` に収めるので 3000 は通る（`> max_yen` で違反、`runner.py:272`）。境界は安全側。確認済み、問題なし。

---

## 🟢 任意（確認済み・良好）

### 🟢-1: dedup 修正は完全（全券種で入れ子重複なし）

- 入れ子幅の生成元: `bettype_efficiency.build_plans` が馬連◎-相手2/3/4、ワイド◎-相手2/3、馬単◎-相手2/3 を**別 Plan**として出す（`bettype_efficiency.py:386-419`）。相手2 ⊂ 相手3 ⊂ 相手4 の入れ子。
- selection は全プランをループするので selected_plans に同一券種の複数幅が入りうる（`bettype_selection.py:251-270`）。
- サイジングの dedup は二段:
  1. `eff_by_key = {(bet_type, legs_key): plan}`（`bettype_sizing.py:193`）で plan を (bet_type, legs) 完全一致で引く。
  2. `best_by_type[bet_type]`（`bettype_sizing.py:236-239`）で**券種ごとに最良EV1つ**（同点は点数多い=広い方）に絞る。
- 実証（5/31 4R dry）: `umaren 5/12, 5/7` と `umatan 5/12, 5/7, 5/14` が各券種 1 セットのみ。同一脚の二重買いなし。京都1R の馬連/馬単/三連複/三連単も各券種で独立した脚集合、重複なし。
- アンカー（tansho/fukusho）は build_plans で各1プランのみ（`bettype_efficiency.py:372-383`）+ `next(...)` で最初の1つ（`bettype_sizing.py:197-198`）なので重複の余地なし。
- 回帰テスト `test_combo_dedup_nested_widths_same_bettype` で「馬単◎-相手2 と ◎-相手3 を両方含んでも最良EV(相手3)1セットに dedup」を担保。**合格**。

### 🟢-2: サイジングの健全性（per_race を超えない・排反保守）

- アンカー◎単 Kelly は freebudget と同一式（`bettype_sizing.py:74-90` が `freebudget.py:182-190` をミラー、`calc_kelly_fraction` 共有 `bet_engine.py:685`）。`test_kelly_amount_matches_freebudget_formula` で同額（p=0.3/odds=5.0→300円）を担保。
- 複合は per_race 残予算（`residual = per_race_cap - anchor_yen`、`bettype_sizing.py:227`）を EV 比例 → plan 内逆オッズ（`_alloc_inverse_odds`、`bettype_sizing.py:139`）。**naive per-leg Kelly を使わず固定予算配分**なので排反/相関で oversize しない。`test_combo_ev_proportional_and_residual_bound` で `combo_yen <= residual` を担保。
- 最終 `fit_legs_to_cap`（`bettype_sizing.py:97`）で per_race 以内に truncate（比例縮小→最低100→低EV drop、**アンカー保護**で複合を先に落とす）。`test_per_race_truncate_protects_anchor` で「per_race=500 でもアンカー単は残る」を担保。
- 実データ全7レースで合計 ≤ per_race_cap(3000) を確認（dry: 3000/400/2900/3000/2700/2800/3000）。**per_race の檻は健全**。
- 複勝 place_odds_min（最低値=保守）使用は過大評価を防ぐ正しい方向。

### 🟢-3: 安全機構の継承（freebudget と同等）

- lock/state/halt/鮮度/per_day累計/HALT_EXIT_CODES{5,7,8}/連続失敗(2) を `freebudget_scheduler` から import 流用（`bettype_scheduler.py:34-45`）。骨格 `_run_pass_inner`(`bettype_scheduler.py:189`) は freebudget(`freebudget_scheduler.py:271`) と同構造。
- state/lock は別ファイル（`bettype_scheduler*`）で freebudget state を汚さない。`test_state_lock_paths_are_bettype` / `test_halt_day_writes_bettype_state_only` で担保。
- 冪等（`votes[race_id].exit_code==0` で skip、`bettype_scheduler.py:239`）/ 窓判定（`[vote_at, deadline]`、:249-258）/ 締切超過 missed 記録（:251-258）/ halt_day（:74、dir 未作成でも mkdir して必ず効く緊急ブレーキ）を確認。
- オッズ鮮度ガード（live のみ、ODDS_STALE_MIN=10、:225-236）= vb_refresh 停止時に古いオッズで投票しない。dry-run は鮮度に関わらず予定表示（freebudget と同一挙動）。
- HALT_EXIT_CODES / 連続失敗 halt は freebudget と同経路（:291-306）。`test_inner_*` 5件で窓/冪等/per_day/fund0 を担保。23 passed 確認。
- 二重フラグ（`--confirm` + `--i-understand-live`、:360-363）= 実弾の人ゲート。dry は subprocess 不発（`test_vote_dry_no_subprocess`）。
- **継承は崩れていない。合格**。

### 🟢-4: --bet 経路の正確性

- `build_bet_specs`（`bettype_scheduler.py:129`）→ `parse_bet_spec`（`ff_writer.py:139`）往復で馬単/三連単の順序保持。`test_build_bet_specs_roundtrip_preserves_order` で担保。
- FF CSV は 7券種すべて bet_type コード 0/1/3/4/5/6/7・umaban/2/3・順序正しく出力（プラン記載の検証済事実 + `ff_writer._build_row` で確認）。
- ledger 記録 `record_portfolio_votes`（`runner.py:784-799`）は (race_id, strategy) group + 各 ticket の実 bet_type + 全馬番（`horses = [umaban] + [umaban2, umaban3]`、:795）で multi-bettype を正確に残す。Session 137 の過少記録(3/11)バグは本治療済み。
- runner の per_race 検証は race_id groupby 合計（`runner.py:257-259`）なので --bet 群でも正しく効く。**合格**。

### 🟢-5: dry-run の安全性

- `size_one_race` は窓内のみ重い評価（`bettype_scheduler.py:260-262` でウィンドウ内に入って初めて DB query）= DB query 抑制 OK。
- dry は subprocess 不発（`vote_one_race_multi:150-151` で live=False は WOULD VOTE のみ）。
- `--now` 擬似時刻で発火検証可（5/31 13:05 で東京7R WOULD VOTE、締切超過 skip、窓前待機を確認）。

---

## 段階ロールアウトの評価

プランの Step1-6 は妥当。現状:
- Step1（静的 dry）✅ 完了（bettype_race で全レース ≤3000・100円単位確認）
- Step2（scheduler dry 窓発火）✅ 完了（--now で WOULD VOTE / 冪等 / per_day 確認）
- Step3（runner 単発 dry / click なし）— FF CSV 検証済（プラン記載）
- Step4（シズネ review）= 本書 → **🔴-1 を条件に**
- Step5（live arm 1 レース）= 🔴-1 解消後に GO
- Step6（本格 live）= 1 レース実弾の ledger/IPAT/state 確認後

per_day=30000 の露出は per_race=3000 + halt + ふくだ監視 で抑制されているが、**🔴-1（config 食い違い）で「最後の砦=runner config」が無効**なので、そこだけ必ず塞ぐこと。

---

## ふくだ君に確認したい論点（3つ）

1. **【最重要 / 🔴-1】今日の per_day の「真の上限」は 10000 か 30000 か？**
   30000 で回すなら config.json の per_day_max_yen を 30000 に上げてほしい（runner の最後の砦を整合させる）。10000 が真の上限なら scheduler を 10000 に下げる。どちらかに統一しないまま LIVE は NO-GO。可能なら 🔴-1(b)（scheduler が runner に「日次残予算」を --max-yen で渡す）も入れたいが、今日は config 統一だけでも arm 可。

2. **【🟡-2】今日 freebudget の Task Scheduler は確実に無効化したか？**
   bettype と freebudget の live ロックは別系統なので、両方 Task Scheduler に入っていると二重投票する。今日は bettype 単独 live が前提。freebudget_auto の live タスクを止めたことを目視確認してほしい。

3. **【🟡-1】複勝アンカーの低オッズ（1.3〜1.8倍）はそのまま買ってよいか？**
   資金消失リスクは低い（EV>1 ゲート + cap 1000）が、「当たっても利益薄・外すと痛い」非対称で、ふくだの心理と相性が悪いかもしれない。今日は現状維持で OK だが、運用後に複勝の最低オッズ floor を入れるか相談したい。

---

## まとめ

| 観点 | 判定 |
|------|------|
| サイジングの健全性（per_race 不超過・排反保守） | 🟢 合格 |
| dedup 修正の完全性（全券種・入れ子） | 🟢 合格 |
| 安全機構の継承（lock/state/halt/鮮度/連続失敗） | 🟢 合格 |
| --bet 経路・ledger 記録の正確性 | 🟢 合格 |
| per_day=30000 の檻の二重化 | 🔴 **要修正（config 食い違い）** |
| IPAT 排他 | 🟡 運用前提のみ（今日は目視で担保可） |
| 複勝アンカーの元本効率 | 🟡 運用後チューニング |

**🔴-1（config per_day を scheduler と統一）を解消すれば、今日午後の 1 レース実弾 arm（Step5）に GO。** 実装の質は高い。ブレーキ役として一点だけ、最後の砦が無効化されている点を必ず塞いでから arm してください。

---

## Session 140 カカシ対応（🔴-1 + ふくだ判断）

シズネ 🔴-1（per_day の檻が config10000 vs scheduler30000 で不一致・最終段が無効）を以下で解消:
1. **per_day 残予算を runner --max-yen に織り込み**（理想案）: `vote_one_race_multi(..., per_day_remaining)` を追加し `--max-yen = min(amount, per_race_cap, per_day_remaining)`。`_run_pass_inner` が `per_day_max_yen - voted_yen` を渡す。境界レースがダイアログ層でも日次上限を超えない（累積上限の per-call 番人）。test 追加。
2. **config と scheduler を 30000 で統一**（ふくだ判断「30000 に統一・config も上げる」）: `data3/userdata/bankroll/config.json` per_day_max_yen 10000→30000。documented な真の檻=30000 で coherent。per_race=3000 据え置き。※config は永続変更（夜間に戻すか継続か要判断、notes に記録）。

🟡-2（IPAT 排他）: Task Scheduler に freebudget/bettype の自動タスクは現状**未登録＝競合なし**（実機 schtasks 確認済）。bettype arm 時は単独。
🟡-1（複勝低オッズ）: calc_kelly_fraction が EV≤1 で 0 を返すため低オッズ単独では買われない（EV>1=高 place 確率時のみ）。最低オッズ floor は運用後に相談（後回し）。

検証: 48 passed（sizing12+scheduler12+freebudget_scheduler24）。config per_day=30000 反映確認。

→ **🔴-1 クローズ。段階ロールアウト Step5（1レースだけ実弾 arm、ふくだ監視）に進める。**
※運用前提: vb_refresh が動いていること（live はオッズ鮮度>10分で投票 skip。Task Scheduler 要確認）。

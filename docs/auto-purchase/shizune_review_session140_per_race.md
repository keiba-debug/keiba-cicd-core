# シズネレビュー — Session 140 / per_race ハードキャップの scheduler 二層化 (残課題①②)

> 対象: `freebudget_scheduler.py` の per_race キャップ対応。
> ① `vote_one_race` の `--max-yen` を per_race で min キャップ（ダイアログ層の二次防御）
> ② `_run_pass_inner` で over-cap レースを **day-halt でなく当レース skip** に変更
> **自動投票スケジューラの金経路の挙動変更**のため、リスク管理視点で精査。

## 結論

**条件付き GO（dry-run/監視/bat 実弾は今日も無条件 GO。web LIVE 無人本稼働は #1 のふくだ再確認が前提）**

- コードの整合性・安全性は十分。🔴（資金が消える/暴走する経路）はゼロ。
- ただし **#1 の挙動変更（halt → skip）は「ふくだ確認待ち（現状維持）」だった残課題②をカカシが skip で実装した**もの。判断自体は妥当だが、リスク選好に関わる方針変更なので**ふくだの明示承認を取ってから web LIVE 無人運用に乗せる**こと。これを記録上の宿題として残す。
- 二段ハードキャップ（runner 正本 + scheduler 事前 skip + ダイアログ min キャップ）の構造は崩れていない。正本は依然 runner の `_check_per_race_limits`。

---

## 検証した事実（実コード file:line + 実値）

### per_race / per_bet の数値関係（残課題②の前提が正しいことを確認）
- config 実値（`data3/userdata/bankroll/config.json`）: `limit_mode=absolute` / `per_race_max_yen=3000` / `per_day_max_yen=10000` / `race_overrides={}`。
- freebudget の 1 馬上限 = `bankroll(10000) × per_bet_cap_pct(0.10)` = **1000 円**（`freebudget.py:51,165-166`）。
- → **1 レース 4 頭 funded = 4×1000 = 4000 > per_race 3000** で over-cap が成立しうる（残課題②の前提は正しい）。
  - 3 頭 funded = 3000 = per_race ちょうど → `>` 判定なので **skip されない**（許容）。妥当。
- 実測（カカシ報告）: 5/30 は fund 2 レース・各 1 頭（200/100 円）、over-cap 0/2 件。over-cap は少額サイジングでは稀な理論ケース、で合致。

### runner 正本との整合（per_race の番人が崩れていないか）
- runner `_read_bankroll_limits`（`runner.py:223-245`）と scheduler `read_per_race_cap`（`freebudget_scheduler.py:82-98`）は**同じ config・同じ `limit_mode=absolute` ガード・同じキー**を読む。値は一致する。
- runner `_check_per_race_limits`（`runner.py:248-281`）は `total > max_yen` で違反 → main で **return 5**（`runner.py:411`）。
- scheduler `HALT_EXIT_CODES = {5,7,8}`（`:67`）に 5 が含まれる → 従来は per_race 違反 exit 5 → 当日 halt。**今回はその前に scheduler が skip する**ので、通常運用で per_race 由来の exit 5 には到達しなくなる。
- **正本は依然 runner**。scheduler はキャップを「破る」のでなく「先に避ける（skip）」＋「ダイアログでも独立に効かせる（min）」だけ。番人は崩れていない。✅

### 境界の一致（off-by-one がないか）
- scheduler skip: `sub.total_yen > per_race_cap`（`:332`、`>`）。
- runner 違反: `total > max_yen`（`runner.py:272`、`>`）。
- → **両者とも「ちょうど 3000 は許容、3001 から弾く」で一致**。境界の食い違いなし。✅（検算で確認: 3000→投票、3001→skip/違反）

### min キャップのロジック（誤 reject を生まないか）
- `max_yen = min(amount, per_race_cap) if per_race_cap > 0 else amount`（`:201`）。
- 検算: `amount<=cap` のとき `min=amount`（挙動不変）。`amount>cap` のとき `min=cap`。`cap=0` のとき `amount`（旧挙動）。
- 通常（scheduler が over-cap を先に skip）は `amount<=cap` なので `min=amount` で**挙動不変**。誤 reject は生じない。✅

### exit 5 のセマンティクス分離（重要）
- runner の exit 5 は **3 箇所共用**: per_day 超過（`:400`）/ per_race 違反（`:411`）/ postvote セッション切れ（`:721`）。
- scheduler は per_day を自前で先に skip（`:322`）、per_race も今回先に skip（`:332`）するため、**通常運用で scheduler に返る exit 5 は「postvote セッション切れ」= 真に halt すべき異常**に収れんする。
- → むしろ今回の変更で **exit 5 のシグナル純度が上がる**（cap 系の「正常な見送り」を halt 経路から外し、残る exit 5 は本物の異常だけ）。これは安全側の改善。✅

---

## 指摘（🔴/🟡/🟢）

### 🔴-1 [方針] halt → skip の挙動変更は「ふくだ確認待ち」だった #2 をコード化したもの → ふくだ再確認が要る
- 該当: `_run_pass_inner` の over-cap skip（`freebudget_scheduler.py:326-335`）。
- Session 139 doc 残課題 #2（`shizune_review_session139_web_panel.md:57`）は明確に「**『想定内の停止』か、per_race を上げる/1 馬 cap を絞るか、ふくだ確認待ち**」と書かれていた。今回カカシが「over-cap は異常でなくサイジング → 1 レース skip が妥当」と判断して実装した。
- **判断そのものは妥当**（理由は下記）。だが**リスク選好に関わる方針決定**であり、レビュアーとして「コードが正しいか」とは別に「ふくだがこの方針を選んだか」を確認する責務がある。
  - skip 寄りの根拠（妥当）: ① over-cap = 「強い馬が 4 頭以上」というサイジング起因で、IPAT 障害・セッション切れのような**システム異常ではない** ② per_day(10000) は依然効く ③ 1 レースの見送りが当日他レースの正当な投票を巻き込まないのは、per_day skip と対称で一貫している。
  - halt 寄りの懸念（残る）: ① halt は「異常時は全部止める」保守側。skip にすると「毎回 4 頭以上 funded されてサイレントに見送られ続ける」状態に**人が気づきにくい**（観察者不在対策が一段薄くなる）。② もし over-cap が想定外のサイジングバグ（例: per_bet_cap が効かず全額計上）に起因していた場合、skip は症状を隠す。
- **修正案（コードでなく運用/記録）**:
  - (a) **ふくだに「over-cap は halt せず当レース skip でよいか」を明示確認**し、承認を本 doc に追記してから web LIVE 無人本稼働へ。bat 実弾・dry-run・監視は今日も無条件 GO（この経路に影響しない / 影響しても安全側）。
  - (b) skip が**沈黙しない**ように観測性を一段足すことを推奨（次セッション任意）: over-cap skip 時に ledger event か state に「per_race_over_cap_skipped」を 1 行残す（現状は `skipped` リストに入り pass 終了時 print されるだけで、state には残らない＝後から「あの日何回見送ったか」を監査できない）。「借金記録の鬼」としては、**見送りも記録に残したい**。

### 🟡-1 [観測性] over-cap skip を state に記録しないと事後監査できない
- 該当: `:332-335`。コメント通り「オッズで再サイジングされ得るため state に記録せず毎パス再判定」。冪等性の観点では正しい（per_day skip と同流儀）。
- ただし**「当日 over-cap で見送ったレースがあった事実」が state に残らない**。pass 終了時の print（`:375-376`）は Task Scheduler 実行ではログに流れて消えやすい。
- 提案: 冪等な再判定は維持しつつ、`state` に `over_cap_skips: {race_id: {total, cap, last_seen_at}}`（投票成立の `votes` とは別キー）を**上書き記録**する案。投票判定には使わない（毎パス上書きなので冪等性は保たれる）。web 監視パネルで「今日 N レースが per_race 超過で見送り」を可視化できる。次セッション任意。

### 🟡-2 [フォールバック] config 読めない時 cap=0（キャップ無効化）の安全性
- 該当: `read_per_race_cap`（`:82-98`）— ファイル欠落 / 破損 / `limit_mode≠absolute` / 例外 → すべて **0（キャップ無し）**。
- このとき scheduler 側の over-cap skip も `--max-yen` min も**無効化**され、**旧挙動（runner 任せ）に戻る**。
- 評価: **二重には守られる**。config が読めなくても runner 側 `_read_bankroll_limits` が同じファイルを独立に読み、読めれば per_race exit 5 で弾く。runner も読めなければ両者 cap 無効だが、それは**今までと同じ状態**（今回の変更で悪化していない）。
- ただし「scheduler は cap=0（無効）と判断したのに runner は読めて有効」または**その逆**という**非対称**が起こり得る（例: ファイルが書き換え途中で scheduler が読んだ瞬間だけ壊れていた）。この場合:
  - scheduler 無効 / runner 有効 → scheduler は skip しないが runner が exit 5 → halt（保守側に倒れる。安全）。✅
  - scheduler 有効 / runner 無効 → 起こりにくい（runner は例外時に「制限なしで続行」: `runner.py:243-245`）が、起きても scheduler が先に skip するので over-cap は飛ばない。✅
- → **どちらの非対称でも安全側に倒れる**ので実害なし。🟡 据え置き（記録のみ）。気になるなら read_per_race_cap の「無効化した理由」を verbose 出力すると運用で気づける（任意）。

### 🟡-3 [一貫性] per_day は scheduler が「累計で skip」、per_race は「単発で skip」— 設計意図の明文化
- per_day skip（`:322`）は `voted_yen + sub.total_yen > per_day_max_yen`（既投票累計を見る）。
- per_race skip（`:332`）は `sub.total_yen > per_race_cap`（そのレース単体）。
- これは正しい（per_day は累積上限、per_race は単発上限なので非対称で当然）。ただ「per_day と対称」というコメント（`:327`）は**「halt しない」という応答の対称**であって**判定式は非対称**。誤読を避けるためコメントを「応答が対称（どちらも当該分のみ見送り）」と一言補強すると親切。🟢 寄りの 🟡。

### 🟢-1 dry-run / 監視への影響
- `read_per_race_cap` は live/dry 両方で呼ばれるが、dry-run は `vote_one_race(live=False)` で即 return（`:186-188`、subprocess 起動なし）。over-cap skip は dry-run でも作動するので、**dry-run で「このレースは per_race 超過で見送る予定」が事前に見える**＝むしろ良い（本番前に over-cap レースを把握できる）。✅

### 🟢-2 状態ファイル冪等性 / 回帰
- over-cap skip は `continue` で `state["votes"]` に書かない → 投票済み判定（`:296`）に影響しない。冪等性維持。✅
- min キャップは `--max-yen` の値を変えるだけ。`--max-bets`（件数）は不変なので件数ガードはそのまま効く。✅
- 既存テストとの整合: `test_vote_one_race_live_passes_exact_max`（per_race_cap デフォルト 0）は `min` 分岐に入らず `amount` のまま → 既存挙動不変。回帰なし。✅

---

## テスト評価（`test_freebudget_scheduler.py` 新規 8 件）

- カバレッジは**過不足なく的を射ている**:
  - min キャップ 3 ケース（over→丸め `3000` / under→不変 `600` / cap=0→旧 `4000`）。✅ 境界 amount==cap が無いが、`>` 判定は over-cap skip 側でテスト済みなので可。
  - `read_per_race_cap` 3 ケース（absolute→3000 / 非absolute→0 / ファイル欠落→0）。✅ **破損 JSON ケースが無い**（`except` 節 OSError/ValueError/TypeError は JSONDecodeError を ValueError 経由で拾うが、明示テストが欲しい。🟡 補強推奨）。
  - over-cap skip 2 ケース（over→halt せず skip・vote 未到達 / under→投票到達）。✅ **これが #1 の核心の回帰ガード。良い。**
- 補強推奨（任意）:
  - `read_per_race_cap` で**破損 config → 0** のテスト（`config.json = "{ broken"` → 0 を確認）。フォールバック安全性（🟡-2）の回帰ガード。
  - `per_race_cap=0` のとき over-cap でも skip されず投票到達するテスト（旧挙動＝キャップ無効化の確認。フォールバック経路の回帰ガード）。
- 注記: 環境の `C:\Python311` に pytest 未導入のため**本レビューでは実行確認できていない**（カカシ報告は 21 passed）。ロジックは手計算で全分岐を検算済み（境界・min・skip すべて期待通り）。コミット前に正規の venv で 21 passed を再確認のこと。

---

## ふくだ君に確認したい論点

1. **【最重要・方針】over-cap（1 レース 4 頭以上 funded で >3000）の応答を「当日全停止(halt)」から「当レースのみ見送り(skip)」に変えていい?** 元々「ふくだ確認待ち（現状維持）」だった点です。skip 派の理由は「over-cap は異常でなく強い馬が多いだけ＝サイジング起因、per_day 1 万の檻は残る」。halt 派の懸念は「毎回サイレントに見送られても気づきにくい」。**この方針で承認なら本 doc に「ふくだ承認済」と追記して web LIVE 無人本稼働へ。**
2. **【観測性】見送り(skip)を記録に残しますか?** 現状 over-cap skip は state に残らず print のみ（Task Scheduler だと消える）。「今日 N レース見送った」を後から監査できるよう state か ledger に 1 行残すか（🟡-1）。残すなら次セッションで対応。
3. **【サイジング側の根本解決の要否】**そもそも per_race=3000 vs 1 馬 1000 で「4 頭 funded なら必ず over」になる構造を、サイジング側で解く（例: 1 レース内の合計が per_race を超えたら頭数を絞る/按分する）案は要りますか? skip は「見送り」、按分は「上限内で買う」。ふくだ哲学（自分にできない買い方）的にどちらが好みか。

---

## 補足: 二段ハードキャップの最終構造（記録）

```
[scheduler 事前 skip]   sub.total_yen > per_race(3000) → 当レース skip（halt せず）   ← 今回追加
        ↓ すり抜け（config 非対称等）
[runner 正本チェック]   _check_per_race_limits → exit 5 → HALT_EXIT_CODES → 当日 halt  ← 不変（番人）
        ↓ 同時に
[ダイアログ min キャップ] --max-yen = min(amount, 3000) → ダイアログ total が超なら投票しない ← 今回追加
        ↓ 別軸
[per_day 累計]          voted_yen + sub > per_day(10000) → skip                        ← 不変
```

- 正本は runner。scheduler は「先に避ける」＋「ダイアログでも効かせる」二次防御。**檻（3000/10000）は誰も外せない**構造は維持。
- 「最新オッズ判断が正」（ふくだ哲学・Session 139 §認識合わせ）と、ハードキャップ（リスク管理）の両立は崩れていない。

---

## Session 140 ふくだ判断 + カカシ最終実装（halt→skip→★按分★）

シズネ 🔴-1（halt→skip はリスク選好決定なのでふくだ承認要）を受けてふくだに3択提示 → **ふくだは「按分（上限内に収めて買う）」を選択**（skip でも halt でもない）。

### 実装（`freebudget_scheduler.py`）
- `fit_result_to_cap(sub, cap)` 新規: over-cap の 1 レースを per_race 以内に **比例縮小（按分）**。
  - factor=cap/total で各 bet を縮小、100円単位に floor、最低100円。例: 4頭×1000=4000 → 700×4=2800（≤3000）。
  - 最低100円制約で縮小しきれない多点ケースのみ **低 win_ev 順に drop** して収める。
  - 縮小のみ（amount は元値以下）なので per_bet_cap は決して超えない。
- `_run_pass_inner`: per_day チェックの**前**に per_race 按分を適用。日次累計には縮小後の額を使う。
- 按分した事実は投票結果 dict に `per_race_adjusted={before,after,dropped}` で記録（state に残る＝**シズネ🟡-1 監査要求を充足**）。
- `vote_one_race` の `--max-yen min(amount, per_race)` は二次防御として維持（按分後は amount≤cap で min=amount）。

### シズネ指摘の対応状況
- 🔴-1（方針承認）: **ふくだが按分を明示選択 → 承認済**。halt の「サイレント見送り」懸念は、按分なら「見送らず上限内で買う」ので解消。さらに per_race_adjusted を記録し監査可能に。
- 🟡-1（skip の監査記録）: 按分の `per_race_adjusted` を state に記録して充足。
- 検算: scheduler skip境界/runner違反境界の `>` 一致、正本=runner不変、config フォールバック安全 は按分でも維持（按分は per_race を**超えない**方向の調整なので runner の番人と矛盾しない）。

### テスト（正規 venv で実行確認）
`test_freebudget_scheduler.py` 24 passed（按分の比例縮小/低EV drop/over-cap投票到達/under-cap不変/read_per_race_cap/--max-yen min）。関連 63 passed。

→ **残課題①②ともクローズ。over-cap = 按分で上限内に収めて投票（day-halt も skip もしない）。**

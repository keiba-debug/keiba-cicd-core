# AI印 ⇔ 自動投票 軸連動 設計メモ (シズネレビュー用ドラフト)

ステータス: 論点整理 / シズネレビュー待ち / 関連: [[auto-purchase-project]], 22_AI_MARKS_DESIGN.md, [[feedback_betting_philosophy]], [[bettype-selection-roadmap]]
発端: Session 141 — ふくだ「AI印は◎⑬なのに自動投票は⑤から買ってて違和感。買う馬が無印はおかしい」

---

## 0. 問題 (なぜこれを直すか)

AI印 Step2 を 5/31 実機 apply 後、ふくだが気づいた不整合:

- **AI印◎(実力軸) と 自動投票の軸(妙味軸) が 8R中7Rで不一致**。
- 自動投票 `hole_seeker` は win_ev 軸で馬を選ぶ → 東京11Rは ⑤バステール(33倍・勝率18%・単EV6.0)を軸に12点投票。
- 一方 AI印は composite(W/P/ADR)最強の ⑬パントルナイーフ(勝率27%)を◎単独に。
- 結果: **「実際に買っている軸馬が markSet=6 で無印」** という状態。「買う馬には印が付くべき」(ふくだ) に反する。

### 5/31 実データ (voted 8R の AI印◎ vs 自動投票軸)

| レース | AI印◎ | 自動投票軸 | 一致 | 戦略 |
|---|---|---|---|---|
| 東京4R | ◎5 | 5 | ○ | concentrate |
| 京都6R | ◎9 | 6 | × | hole_seeker |
| 東京7R | ◎5 | 1 | × | hole_seeker |
| 東京8R | ◎11 | 13 | × | hole_seeker |
| 京都8R | ◎8 | 6 | × | hole_seeker |
| 京都9R | ◎10 | 5 | × | hole_seeker |
| 京都10R | ◎1 | 3 | × | hole_seeker |
| 東京11R | ◎13 | 5 | × | hole_seeker |

一致率 1/8。hole_seeker(妙味軸) と AI印(実力軸=Themis準拠) が別レイヤーを見ているので構造的に食い違う。

### なぜ「難しい」か (ふくだの直感は正しい)

- ⑤を **◎** にする → Themis原則(確率で序列)違反。⑬(27%)より弱い⑤(18%)を◎にするのは「強さの嘘」。
- ⑤を **無印** のまま → 買ってるのに印なし(現状の不整合)。
- ⑤を **穴** にする → 現状の穴ロジックは win_ev 最大の④(259倍)を拾い ⑤を拾わない。穴ロジックと投票軸ロジックがまた別物で食い違う。

→ 根本原因: **AI印・穴・自動投票の軸が、それぞれ別ロジックで「印/軸」を決めている**。

---

## 1. ふくだの方針 (この設計の制約)

1. **「買う馬には印が付くべき」** — 自動投票した軸馬が無印なのは不可。
2. **「購入後に印を変えてもいい」** — 予想時の印を投票後に上書き/追加してよい。順序を `投票 → 印` に逆転できる。
3. **「⑤に穴とかでもいい」** — 軸馬の印は ◎ でなくてよい(穴等の別印で「買った」を表せれば可)。
4. **「印の種類を増やしてもいい」** — My印体系(◎○▲△Ⅲ穴消)に無い新印/新markSetを足すのも可。
5. 賭け哲学 [[feedback_betting_philosophy]]: 「自分にできない買い方を見つける」。妙味軸(hole_seeker)は人が見落とす値を拾う = ふくだの拡張。実力軸(AI印)とは別の正しさ。**両方残す価値**がある。

---

## 2. 方式候補 (シズネに評価してほしい)

| 案 | 中身 | 長所 | 短所/リスク |
|---|---|---|---|
| **A: 軸を◎上書き** | 投票後、軸馬を markSet=6 の◎に上書き(実力◎を捨てる) | 無印が確実に消える。シンプル | 実力評価(◎=最強)が消え、AI印が「予想」でなく「買い記録」に変質。Themis的な実力序列が見えなくなる |
| **B: 軸に穴を付与(実力◎残す)** | AI印◎(実力)はそのまま、軸馬に「穴」を追加付与 | 実力◎と買い軸の両方が画面で見える。印体系内で完結 | 穴の意味が「妙味馬」と「買い軸」で二重化。穴ロジック(突出判定)と投票軸が違う馬を指すと穴が2頭になり混乱 |
| **C: 新印/新markSet** | 「買った軸」専用の印(例 ¥ / ◉)か別 markSet(例 markSet=8) を新設 | 意味が完全分離(実力◎・妙味穴・買い軸¥)。誤読しない | 印体系拡張のコスト。TARGET/web 両方に decode 追加。ふくだの画面が記号で混雑 |
| **D: AI印を投票軸に一本化** | hole_seeker の軸を AI印◎にする(予想と投票の軸を投票側に統一) | 印=買い目の軸で完全一致 | 実力軸が消える。AI印が hole_seeker 依存になり戦略変更で印が動く |

補足: ふくだは案B(⑤に穴)を例示しつつ「やり方はいくつかある」「印増やしてもいい」と幅を許容 → A〜Dすべて俎上。

---

## 3. データソースと実装上の事実 (レビューの前提)

- **軸馬を確実に取れるのは `bettype_scheduler_state.json` の `votes[rid].legs[].plan_label='◎...'` の `horses[0]`** のみ。
- **ledger v2 (`userdata/purchase_ledger/{date}.json`) には軸フィールドが無い**。raw_legs(馬番集合)はあるが「どれが軸か」は持たない。`pattern_label="その他"`, `strategy_name="manual_cli"`(scheduler では hole_seeker。**自動分ROI分離問題** = メモリ既知)。
- markSet=6 書込みは `ml/ai_marks/dat_writer.py`(clear→該当馬、markSet=1 施錠ガード、VALID_AI_MARKS)。穴のバイトは定義済(`b"\x8c\x8a"`)。
- 印書き換えは `data3/ai_marks/audit/{date}.jsonl` に証跡を残せる(Step1 で実装済の枠組み)。

---

## 4. シズネに見てほしい論点 (リスク管理視点)

1. **監査証跡**: 印を「予想時」と「投票後」で書き換える運用は、AI印の元の予想(実力◎)を消す。後から「AIは当時何を強いと見ていたか」が辿れなくなる懸念。audit JSONL に予想時/投票後の両方を残す設計で足りるか。
2. **データソースの信頼性**: 軸を scheduler_state からしか取れない(ledger に無い)。scheduler_state は state ファイルで、再実行/halt で上書きされうる。投票後に印を打つタイミング(投票直後 hook? 日次バッチ?)と、その時 state が正かを担保できるか。
3. **「予想」と「買い記録」の混同リスク**: 印を買い記録にすると(案A/D)、印を ML特徴量化(`ai_honmei`)する将来構想で「実力予想」でなく「投票結果」を学習してしまう汚染。実力軸の印は別に保持すべきでは(案B/C寄り)。
4. **二重投票/手動共存**: 手動IPATと自動が共存(per_day檻問題 [[manual-auto-bet-coexistence]])。印書き換えが手動印(markSet=1)を侵さないこと(施錠ガードで担保済だが運用で再確認)。
5. **賭け哲学整合**: 妙味軸の存在価値([[feedback_betting_philosophy]])を消さない案が望ましい(実力◎を残す B/C)。ただし画面の記号過多はふくだの可読性を下げる。
6. **未投票/見送りレースの印**: 投票しなかったレースの AI印は予想(実力◎)のまま残すのか、撃ちなしにするのか。投票有無で印の意味が混ざらないか。

---

## 5. カカシの暫定推奨 (レビューのたたき台、確定でない)

- **案B(実力◎残す + 軸に穴) か 案C(新markSet) を軸に検討**。理由: 将来の ML特徴量化・賭け哲学(妙味軸を残す)の両面で「実力予想の印」を消したくない。
- 案Bの穴二重化リスクは「穴ロジック(妙味突出)と買い軸が一致しないレースでは買い軸を優先 or 別記号」で回避できるか要検討 → そこが案Cに寄る分岐点。
- 軸データは scheduler_state を真とし、投票成立(exit_code=0, note=voted)レースのみ印連動。audit に予想時◎と投票後印の両方を記録。
- まず 5/31 の voted 8R で各案を dry-run 出力し、ふくだが画面イメージで選べるようにする。

---

## 6. 次アクション
1. シズネレビュー(本メモ §2 方式選定 + §4 論点)。
2. ふくだが画面イメージで案を選ぶ(voted 8R の dry-run 比較表示)。
3. 確定案を実装(投票後 印連動ツール + audit + web表示)。

---

## 7. 実装記録 (2026-06-06 / VU-1 — 案C採用)

**確定**: 案C = markSet=8「買い軸」専用スロット新設。評価(◎)・妙味(穴)・買い軸(◆◇)を意味分離。

### 記号
- **◆ = 買い軸 (axis)** / **◇ = 相手 (partner)**。中立記号(評価ラダー◎○▲△Ⅲ穴と非衝突)。
- CP932 byte: ◆=`0x819f` / ◇=`0x819e`。評価印の byte と衝突しないことをテストで保証。
- TS (`target-mark-reader.ts`) と Python (`dat_writer.py`) で decode/encode 対称(条件⑤)。

### 軸抽出 (ledger 起点 = 税務SoT、条件②)
- **軸 = 1 portfolio 内 全 ticket の `raw_legs.horses` の積集合**。アンカー型(◎単+◎-相手)は全 leg が軸を含むので積集合={軸}。単票(tansho/fukusho 1点)は積集合={その馬}=軸。
- **相手 = 登場全馬(和集合) − 軸**。積集合が空(box/formation で共通馬なし)のときは軸なし=全馬を相手(honest fallback)。
- `superseded_by_repair` portfolio は除外(Session 137 修復の旧 portfolio、settle と同様)。
- **5/31 実 ledger で検証**: 自動投票軸(§0.5/31表)と完全一致(東4R◆5・京6R◆6・東11R◆5・京12R◆16 …)。scheduler_state なしで ledger だけから軸が取れることを実証(シズネ発見の裏取り)。

### 実装ファイル (すべて live vote パス外 = 開催日中も安全)
- `ml/ai_marks/dat_writer.py`: `write_buy_marks_to_dat`(markSet=8) 追加 + 共通コア化。**施錠**: 買い writer は markSet=1/6 を拒否(=**markSet=6 凍結ガード 条件①**)、AI writer は markSet=8 を拒否(相互施錠 条件⑤)。`read_marks_from_dat` で round-trip 検証。
- `ml/ai_marks/buy_marks.py`(新): ledger → 軸+相手 純関数。
- `ml/ai_marks/write_buy_marks.py`(新): CLI `--date --apply`。dry-run 既定。
- `ml/ai_marks/audit_log.py`: `subdir` 引数追加(`buy_audit/{date}.jsonl`)。**全 audit に「買い軸印は表示用 — 購入の正本は purchase_ledger」明記(条件⑥)**。
- web: `target-mark-reader.ts`(◆◇ decode/encode)、`races-v2/[date]/[track]/[id]/page.tsx`(markSet=8 読込)、`HorseEntryTable.tsx`(「買」列を AI 列の隣に追加、◆琥珀濃/◇琥珀淡)。
- テスト: `ml/tests/test_buy_marks.py`(18件)。pytest 525 passed(既存 test_bet_engine 7fail は無関係)。web `tsc --noEmit` clean / `npm run build` exit0(80/80) / lint 増分ゼロ(257既存問題 不変)。

### ⚠️ live 反映を保留した条件 (開催日中 KeibaBettypeAuto が毎分 live 稼働のため)
本セッションは **2026-06-06 開催日**で `KeibaBettypeAuto`(10:12–18:00 毎分 `bettype_auto.bat live`)が**稼働中**だったため、live vote パスが import するファイル(`runner.py` / `bettype_scheduler.py` / `purchase_ledger/writer.py`)は**一切触っていない**。以下2点は**非開催日にシズネ+ふくだ承認のうえ反映**:

1. **条件② 後半 `axis_umaban` 明示保存**(ledger writer): 現状は積集合で軸を導出でき、アンカー型では完全に機能するため**買い軸印機能には不要**。box/formation(積集合=空)を将来導入する時に `record_portfolio_votes` へ `axis_umaban` フィールドを追加する。**未着手・defer**。
2. **条件④ `strategy_name=manual_cli` 汚染修正**(runner+scheduler): scheduler が runner を `--bet` 群で起動するため auto 投票が ledger 上 `manual_cli` と記録される([[manual-auto-bet-coexistence]])。**買い軸印は strategy_name に依存せず raw_legs から軸を取るので、汚染があっても印は正しい**。修正案 = runner に `--portfolio-strategy`(additive/既定 manual_cli)を足し scheduler が実戦略名を渡す。**strategy_name は idempotency key の構成要素**のため開催日中に変えると二重記録リスク → **必ずレース外で**。**未着手・defer**。

> 結論: 買い軸印(markSet=8)の機能本体は完成・live安全。①③⑤⑥ 充足。② は「ledger起点」充足・axis_umaban保存のみ defer。④ は defer(機能は非依存)。markSet=6 は不変(凍結)。**live への apply(`write_buy_marks --apply`)と上記 defer 2点の反映可否はシズネ+ふくだ**。

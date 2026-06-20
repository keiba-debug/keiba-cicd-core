# キャラ別エンタメ枠 自動購入 — 設計書 (Session 165 / 2026-06-20)

> **ステータス**: 設計フェーズ (実装前)。レビュー = シズネ (リスク管理) 必須。
> **正本**: 検証基盤 = `bet_template_lab.md` / サイジング本線 = `auto_purchase_sizing_design.md`。
> 本書は「検証済テンプレを **キャラ別・隔離bankroll** で自動購入する」実戦化レイヤーの設計。
> メモリ: [[character-betting-personas]] [[bet-template-lab]] [[lab-wiring-project]] [[feedback_betting_philosophy]]

---

## 0. 位置づけ — 「勝つ本線」とは別トラックの「楽しむ枠」

★Session 165 の検証で前提が確定した★:
- 最新cache (3653R・13ヶ月・2026-06-13) の walk-forward で、**どのテンプレ×どの条件も月別ROI中央値は
  100%未満** (最良 = 複勝堅実党 87% / ワイド堅実党 86%・ALL条件)。条件で絞ると一部の月だけ100%超に
  跳ねるが分散が激増し中央値はむしろ下がる (= 万馬券1本の上振れ・信用しない)。
- メモリ [[character-betting-personas]] の旧数値「ワイド堅実党 中央値100%・複勝堅実党トントン」は
  ★古いcache/短い窓の数字で、最新検証では再現しなかった★ (stale修復 + 期間延長で均された)。

→ **結論**: キャラ別テンプレは「黒字化の手段」ではない。**本線 (`fixed_grade_v2` = 全レース買う・
  最も損が小さい ROI 79-83%) は維持**し、キャラは『多様な買い方を楽しむ・KAZEMACHI 配信のエンタメ』
  として **隔離bankroll で独立** に回す。黒字化は別トラック (モデル改良 = danger-model/sirius) が担う。
  これは W9 結論「配分は破産制御・勝ちはモデル由来」([[bet-adjustment-items]] W9) と整合。

---

## 1. 初期キャラ = 2タイプ (ふくだ判定 Session 165)

| キャラ | テンプレ | 性質 (検証値・ALL) | ringfenced | 役割 |
|---|---|---|---|---|
| **堅実党** | `fukusho_korogashi` or `wide_anchor` | 中央値86-87%・全月76-96%に収束・上振れ依存なし | False | 損が小さく読める・「手堅く楽しむ」 |
| **ロマン党** | `sanrentan_roman` (or `sanrenpuku_1jiku`) | 中央値73-85%・月別15-268%の高分散・maxDD大 | **True** | 外れても痛くない・当たれば跳ねる「⚡夢枠」 |

- 堅実党は ringfenced=False でも **キャラ用の独立 bankroll** を持つ (本線とは別財布)。
- ロマン党は ringfenced=True = **絶対上限 + 補充なし** (溶けたら終了)。シズネ🔴必須要件。

---

## 2. アーキテクチャ — 既存資産の上に組む (新規実装を最小化)

★既に存在するもの (再利用)★:
- **買い目生成 bridge**: `bet_templates.marks_from_ranking`(composite序列→AI印◎○▲△Ⅲ) →
  `apply_template`(テンプレ→`List[Ticket]`)。印の付いた馬しか買わない (Session 147 で実AI印に統一)。
- **Template.ringfenced** フラグ (隔離bankroll上限の対象識別。データ構造に組込済)。
- **template_flat サイザー経路**: `bettype_scheduler.resolve_sizer` が `--sizing template_flat:NAME` を
  パース (Session 162 実装・本線では不採用だが ★キャラ実戦化の足場として有効★)。
- **bankroll/day_budget 管理**: `bettype_fund.read_day_budget` + 朝凍結 (Session 145)。
- **自動投票チェーン**: `target_clicker/{runner,menu_runner,auto_vote}` + scheduler。
- **ledger v2 + settle**: `purchase_ledger/{date}.json` + `settle_ledger`。

★新規に必要なもの (キャラ層)★:
1. **キャラ定義 + 独立 bankroll 台帳** (§3 = `characters.py` 拡張)。
2. **隔離bankroll の絶対上限・補充なしの実効化** (ringfenced → ★runner abort★・§4 + §9-2)。
   ★現状コードに入金ハードキャップは無い★ (安全弁は「入金=人間の行為」一本) = 実装の核心。
3. **キャラ別 ledger** (税務・二重投票照合のため ★物理分離せず単一ログ + persona_key フィールド★・
   シズネ§9-4)。
4. **口座分離の前提クリア** ([[manual-auto-bet-coexistence]] 未解決 = キャラ実投票の前提条件) (§6)。
   ★現行 runner/scheduler/config は IPAT口座1個・1日1値を全経路で前提★ (シズネ§9-3)。

---

## 3. キャラ定義 — ★SoT = 既存 `ml/strategies/characters.py` (新JSON廃案・シズネ§9-1)★

★Session 165 修正★: 当初は新規 `character_personas.json` を提案したが、シズネレビューで
**既に `characters.py` (Session 149) にキャラ5体が定義済み**と判明 (二重実装の罠)。
→ **SoT は `characters.py` を正とし、新JSONは廃案**。実投票レイヤーはこの dataclass を読む。

既存 `CHARACTERS` (5体・`characters.py:47-75`):

| key | name | templates | day_fraction | ringfenced | cap_pct | 初期2キャラ |
|---|---|---|---|---|---|---|
| `honmei` | 本命党 | honmei_formation | 0.05 | F | — | |
| `wide_kenjitsu` | ワイド堅実党 | wide_anchor | 0.05 | F | — | ★堅実党 候補 |
| `fukusho_kenjitsu` | 複勝堅実党 | fukusho_korogashi | 0.05 | F | — | ★堅実党 候補 |
| `sanrentan_roman` | 三連単ロマン党 | sanrentan_roman | 0.20 | **T** | **0.03** | ★ロマン党 (確定) |
| `myomi` | 妙味党 | tansho_ai2 | 0.05 | F | — | odds_dependent (後知恵注意) |

- **初期2キャラ = `fukusho_kenjitsu` or `wide_kenjitsu` (堅実党) + `sanrentan_roman` (ロマン党)**。
- ★隔離パラメータは `ringfence_cap_pct` (総資金×割合) に一本化★ (絶対額 `bankroll_total_yen` は廃止・
  二系統矛盾を回避・シズネ§9-1)。ロマン党 = 総資金 × 3% を隔離・補充なし。
- 実投票に必要だが `characters.py` に ★無い★ フィールド (実戦化で追加要件):
  - `per_day_max_yen` (キャラ別日次上限・実投票の runner abort 用)。
  - `enabled` (bankroll<=0 で自動降格する実データ起点フラグ)。
  → これらは characters.py に追記 (sim 専用フィールドと実戦フィールドを同 dataclass に共存)。

- 各キャラ = **独立 bankroll + 独立テンプレ + 独立 per_day**。互いに干渉しない。本線とも別財布。
- bankroll は **手動入金のみで増える**。ただし ★入金ハードキャップは現状コードに無い★ (シズネ§9-2) →
  §4-1 + §9-2 の runner abort 実装が実投票の前提条件。

---

## 4. シズネ・ガードレール (🔴 必須・[[character-betting-personas]] レビュー由来)

実装の ★中心★ はリスク制御。以下を設計に組み込む:

1. **ringfenced = 絶対上限 + 補充なし (★コードで縛る・シズネ§9-2★)**:
   - (a) キャラ別 bankroll の ★累計入金額を ledger から集計★し、`総資金 × ringfence_cap_pct` 超過を
     ★runner が abort する★ チェックを runner の per_day_max チェックと同階層に新設。
   - (b) bankroll<=0 → `enabled=false` 自動降格を ★実データ (ledger 残高) 起点★ で判定
     (sim の break ではなく実台帳)。
   - ★この2つが無い限り ringfenced は名前だけ★ = 溶けた後の追い入金で歯止めが消える経路が残る。
2. **複勝転がしは特に危険 = §3「動的調整なし」違反**: 転がし系を入れる場合は **1セットの元本上限 +
   利確/損切り回数を固定**。連勝で増額しない (Kelly的雪だるま禁止)。→ 初期2キャラには転がしを ★入れない★
   (堅実党=複勝堅実党 fukusho_korogashi は「複◎+ワイド◎-○」で転がしロジックなし・固定額)。
3. **口座分離が前提** (§6): per_day檻がキャラ数倍に膨らむリスク → 口座分離未解決ならキャラは
   ★ペーパー (shadow) 運用に留める★。実投票は口座分離後。
4. **配信は過去sim可視化まで**: KAZEMACHI で実口座リアルタイム自動投票画面を見せるのは JRA/IPAT規約・
   法務リスク → 「過去データ sim 結果の可視化」までに留め、実投票配信は法務確認まで保留。
5. **ラベリング**: ロマン党は「-EV娯楽枠」と明示タグ。§1「ROIの高い気づき発見」とは別物。

---

## 5. キャラ別 ledger / settle / web (★単一ログ + persona_key・シズネ§9-4★)

★Session 165 修正★: 当初は `purchase_ledger/personas/{key}/{date}.json` への物理分離を提案したが、
シズネ§9-4 で「現行は全投票が単一の月次イベントログ (`events_{YYYY-MM}.jsonl`) に集約され、settle/
idempotency/二重投票照合/IPAT限度額が `LEDGER_DIR` モジュール定数に全依存。物理分離は『引数1つで
不変』にならず監査ログを分断する」と判明。

→ **物理分離せず ★単一 ledger に `persona_key` フィールドを足す★** (監査ログ1本=税務・改ざん防止維持・
  二重投票照合も1本のまま)。本線投票は `persona_key=null` (or "main")、キャラ投票は各 key。
- settle: 単一 ledger のまま回る (コアロジック不変・persona 分離による settle 改修不要)。
- web: `/bankroll/personas` (新) で persona_key で filter し各キャラの bankroll 軌道・的中・
  破産までの距離を表示。`simulate_bankroll_character.py` を各キャラの ROI/破産確率の評価道具に。

---

## 6. ★前提条件★: 口座分離 ([[manual-auto-bet-coexistence]] 未解決)

- 現状 per_day 上限は ★自動投票分しか縛らない★ (手動IPAT投票と同一口座だと檻が効かない)。
- キャラを増やす = 同一口座に複数の自動投票主体 → per_day檻リスクがキャラ数倍。
- **解 = 口座分離** (キャラ専用 IPAT 口座 or 区分管理)。これが ★キャラ実投票の前提条件★。
- 口座分離が済むまでは ★shadow (ペーパー) 運用★ = 買い目生成 + sim 精算のみ・実投票しない。

---

## 7. 実装フェーズ (案・★シズネ Phase別判定 §9 反映★)

| Phase | 内容 | 実投票 | シズネ判定 |
|---|---|---|---|
| P1 | `characters.py` 拡張 + bridge 配線 (marks→template→Ticket→sizing) + ★shadow 精算★ | ✗ | **GO** (先に SoT 一本化) |
| P2 | 単一ledger に persona_key + settle 確認 + web 軌道表示 | ✗ | **CONDITIONAL_GO** (物理分離せず) |
| P3 | 口座分離クリア後に堅実党1体を実投票 (最小・少額) | ◯ | **NO_GO** (前提3つ未達) |
| P4 | ロマン党を ringfenced で実投票 + KAZEMACHI 過去sim可視化 | ◯ | **NO_GO** (P3全条件+配信法務) |

★shadow と live の物理隔離 (シズネ§9-3)★: shadow は ★実投票コード経路から物理隔離★ する
  (別エントリポイント or `--shadow` で auto_vote を no-op 固定)。同一 runner/config を共有して
  「設定1ミスで live に化ける」事故を防ぐ。

★P3 (堅実党 実投票) の前提条件 (全て満たすまで NO_GO)★:
  1. 口座分離 (キャラ専用 IPAT 区分・§6)。
  2. 入金ハードキャップの runner abort 実装 (§4-1・§9-2)。
  3. shadow→live 昇格ゲート (期間だけでなく合格条件を明文化・§8)。

★P1 から開始★ (実投票なし = リスクゼロで骨組みを作り、shadow で挙動確認してから実戦)。

---

## 8. 未決事項 (要ふくだ/シズネ判断)

★設計判断 (実装着手前に決める)★:
1. **SoT 一本化**: `characters.py` を正・新JSON廃案 (シズネ推奨) でよいか。
2. **入金ハードキャップを本当にコードで縛るか** (§4-1 の runner abort 実装。運用は重くなるが
   シズネは「作るべき」)。作らないなら ringfenced は名前だけ = ロマン党実投票は永久 NO_GO。
3. **ledger は単一ログ + persona_key で行くか** (物理分離しない・税務/二重投票照合を1本に維持)。

★運用判断 (P3 ブロッカー)★:
4. 堅実党のテンプレは `fukusho_kenjitsu`(複勝) と `wide_kenjitsu`(ワイド) のどちらか / 両方か。
5. 各キャラの初期 bankroll / per_day の具体額。
6. 口座分離の具体手段 (専用口座 / 区分台帳)。
7. shadow→live 昇格ゲート (期間だけでなく ★合格条件★: 何開催・どの指標がどの水準なら上げるか)。

★シズネ追加論点 (§9-5)★:
8. 本線とキャラの ★同一レース重複露出ルール★ (本線で◎単+キャラで複◎ が重なる扱い)。
9. enabled=false 降格後の ★復活手順の SOP 化★ (溶けたキャラをどう再開するか・無秩序な復活防止)。
10. odds_dependent キャラ (妙味党 tansho_ai2) の ★後知恵罠★ ([[feedback_odds_gate_hindsight]]・初期2キャラ
    には入れない)。
11. KAZEMACHI 配信法務の ★判断主体と保留解除条件★ (実投票配信は本書スコープ外・別途法務レビュー必須)。

---

## 9. ★シズネ・リスクレビュー (Session 165 / 2026-06-20) — CONDITIONAL_GO★

> **結論: P1-P2 (shadow) は GO / P3-P4 (実投票) は NO_GO のまま据え置き。**
> 設計の方向 (本線維持・キャラは隔離エンタメ) は正しい。だが本書は ★「既存資産の上に組む」と
> 言いながら既存資産の実体を取り違えている★ 箇所が複数あり、そのまま実装すると
> 「楽しむ枠」が「ズルズル補充」「単一檻の崩壊」「監査ログ分断」に化ける経路が残っている。
> 以下を満たすまで実投票 (P3 以降) には進まないこと。

### 9-1. 🔴 致命: 設計書と既存実装が食い違っている (二重実装の罠)

- **既に `ml/strategies/characters.py` (Session 149) にキャラ定義が存在する** (本命/ワイド堅実/
  複勝堅実/三連単ロマン/妙味の5体・`CHARACTERS`)。本書 §3 は新規 `character_personas.json` を
  ゼロから作る前提で、既存 `characters.py` との関係・統廃合に ★一言も触れていない★。
  → SoT が 2 つ (JSON と py) になり、ringfenced の値・テンプレ割当が食い違う事故が起きる。
  **要決定**: SoT は `characters.py` を正とし JSON は廃案にするか、JSON に一本化して
  `characters.py` を読み替えるか。曖昧なまま実装着手は禁止。

- **ringfence の隔離パラメータが 2 系統で矛盾**:
  - 既存 `characters.py:39` = `ringfence_cap_pct` (総資金 × 割合で隔離・sim 用)。
  - 本書 §3 JSON = `bankroll_total_yen` (絶対額直指定)。
  → 「総資金の3%」と「絶対1万円」は別概念。どちらが実投票の上限かを 1 つに固定すること。

### 9-2. 🔴 致命: 「入金ハードキャップ」の実体がコードに存在しない (§4-1 は絵に描いた餅)

- §4-1 は「`bankroll_total_yen` を超える入金もブロック (ハードキャップ)」と書くが、
  現行の安全弁は ★「入金という人間の行為そのもの」★ 一本 (`freebudget_scheduler.read_day_budget`
  L103-127 / Session 145: 入金額 = 日次上限 = 最大損失)。**プログラムが入金を制止する仕組みは無い。**
- `characters.py` の ringfence は ★sim 内で `eff_w0 = w0 × cap_pct`・`w<=0 で break` するだけ★
  (`simulate_bankroll_character.py:251`)。これは過去シミュレーションの停止条件であって、
  実 IPAT 口座への追加入金を防ぐ機構ではない。
- → **「楽しむ → ズルズル補充」が残る最大の経路はここ**。ロマン党が溶けた後、ふくだが
  IPAT に追加入金して per_day_max を上げれば、ringfenced=True は ★何の歯止めにもならない★。
  **要件 (実投票前)**: (a) キャラ別 bankroll の累計入金額を ledger から集計し、
  `bankroll_total_yen` 超過を ★runner が abort する★ チェックを runner.py の per_day_max チェックと
  同階層に新設する。(b) bankroll<=0 → `enabled=false` 自動降格を ★実データ (ledger 残高) 起点★で
  判定する (sim の break ではなく)。この 2 つが無い限り ringfenced は名前だけ。

### 9-3. 🔴 致命: 単一 per_day 檻はキャラ複数で必ず崩れる (§6 の前提は実装で守られない)

- 現行コードは ★IPAT 口座 1 個・1 日 1 値★ を全経路で前提にしている:
  - `runner.py:40,389-403` = `per_day_max_yen` 単一値で total 超過を abort。
  - `bettype_scheduler.py:279-286` = `read_day_budget()` 単一値を朝に凍結。
  - `read_day_budget` が読むのは config.json の `daily_start_balance_yen` ★1 個★。
- → キャラを N 体走らせると「日次最大損失 = 入金額 1 個」の保証が壊れ、実効上限が N 倍に膨らむ。
  §6 はこれを正しく指摘しているが、本書 §7 (Phase 表) では P3 で「口座分離クリア後」と書くだけで、
  ★P1/P2 の shadow 中に "誤って実投票チェーンに繋がらない" ことを保証する仕組みが無い★。
  shadow と live が同じ runner/scheduler/config を共有するなら、設定 1 つのミスで live に化ける。
  **要件**: shadow は ★実投票コード経路から物理的に隔離★ (別エントリポイント・IPAT ログイン不可・
  `--shadow` で auto_vote を no-op 固定) する。「フラグで分岐」では不十分 (フラグ忘れ = 実投票事故)。

### 9-4. 🟡 注意: `fukusho_korogashi` の裏取り結果 = 「転がしロジックは無いが、名前と note が地雷」

- 裏取り (`bet_templates.py:242-249`): `fukusho_korogashi` の実体は
  ★複◎ 1 点 + ワイド◎-○ 1 点の固定 2 点・weight=1.0★。**連勝で増額する転がしロジックは無い** →
  §4-2「転がしロジックなし・固定額」の主張は ★正しい★。初期キャラに転がしを入れない判断も妥当。
- ただし **危険な含み 2 点**:
  - テンプレ名が `fukusho_korogashi` (= 転がし) で `note` に「★転がしの素地★」と明記 (L249)。
    将来「素地があるなら転がしを足そう」となった瞬間、動的調整なし違反 ([[feedback_betting_philosophy]])
    に直結する。→ **「このテンプレに転がしを後付けしない」を設計書に禁止事項として固定すべき。**
  - sim 側 `characters.py` は `unit_fraction` 比例ベット (総資金 W が増えれば 1 点も太る = 複利)。
    これは「連勝で増額しない固定額」とは ★別物★。実投票で比例ベットを採れば、勝って bankroll が
    増えるほど 1 点が膨らむ = 緩い転がしと同じ挙動になる。**実投票は固定額 (per_day 内定額) に
    倒すこと。比例ベットは sim 専用と明記。**

### 9-5. 🟡 注意: 税務・監査ログの一貫性が §5 で壊れる

- 現行は ★全投票が単一の月次イベントログ★ に集約される (`runner.py:303-310` =
  `{KEIBA_DATA_ROOT}/userdata/purchase_ledger/events_{YYYY-MM}.jsonl`)。settle_ledger も
  `writer.LEDGER_DIR` 定数に直結 (`settle_ledger.py:61`)。**雑所得の年間損益・改ざん検知の観点では
  "1 本の追記専用ログに全部入る" のが望ましい状態。**
- §5「ledger を `personas/{key}/{date}.json` に物理分離」「settle に `--ledger-root` 追加 (コアロジック
  不変)」は、この単一ログ前提を ★破壊する★。しかも `LEDGER_DIR` は writer.py のモジュール定数で、
  「引数 1 つ追加で不変」とはいかない (writer/idempotency/二重投票照合が全部この定数に依存)。
  **代替案**: 物理分離せず、★既存の単一 ledger に `persona_key` フィールドを 1 つ足す★。
  集計・web は persona_key で filter。これなら (a) 監査ログは 1 本 = 税務・改ざん防止が保たれ、
  (b) 二重投票照合 ([[target-clicker-timing-fix]] のゾンビ runner 対策) も 1 本のままで効く。
  本線とキャラを別 ledger に割ると、★同一口座の総購入額が 2 つのログに割れて IPAT 限度額照合が
  できなくなる★ (二重投票・限度額超過の真の照合は audit JSONL + IPAT 限度額・メモリ既知)。

### 9-6. 🟡 §8 に抜けている重大論点

1. **本線とキャラの「同一レース重複投票」**: 本線 (fixed_grade_v2) が◎単を買う同じレースで、
   堅実党も複◎・ロマン党も◎単を買う → 同一馬への露出が想定外に集中。隔離 bankroll でも
   「実際の口座から同一レースに重ね張り」する。重複可否のルールが §8 に無い。
2. **shadow → live 昇格ゲート (合格条件) が定義されていない**: §8-4 は「何開催見るか」だけ。
   ★何を満たしたら昇格か★ (例: shadow N 開催で破産 sim ruin% < x%・実 AI 印 mode で再現・
   ledger 整合 100%) を G ゲート化すべき。期間だけでは形骸化する。
3. **キャラ enabled=false 自動降格の "復活" 手順**: 溶けて降格した後、誰がどの記録を残して
   再開を承認するか。「補充なし=終了」を骨抜きにしないため、再開は ★手動・記録必須・
   理由明記★ を SOP 化する (借金記録の鬼として必須)。
4. **odds_dependent キャラの後知恵罠**: 妙味党 (`tansho_ai2`) は `odds_dependent=True` で
   ★確定オッズ判定 = 後知恵★の地雷 ([[feedback_odds_gate_hindsight]])。初期2キャラに入れない
   判断は正しいが、§8 に「odds_dependent キャラは predictions 直前オッズで再検証するまで
   実投票禁止」を明記すべき。
5. **配信法務の判断主体と保留解除条件**: §4-4 は「法務確認まで保留」とあるが、誰が確認し
   何をもって解除かが無い。実口座リアルタイム配信は JRA/IPAT 規約・賭博幇助・景表法の
   検討が要る重い論点。「過去 sim 可視化まで」を ★ハード境界★ とし、実投票配信は本書の
   スコープ外 (別途法務レビュー必須) と明記すべき。§4-4 の方向は妥当。

### 9-7. レビュー結論

| Phase | 判定 | 条件 |
|---|---|---|
| P1 (キャラ定義 + bridge + shadow 精算) | **GO** | 9-1 (SoT 一本化) を先に決める。shadow は実投票経路と物理隔離 (9-3) |
| P2 (ledger/settle/web 軌道) | **CONDITIONAL_GO** | ledger は物理分離せず単一ログ + persona_key フィールド (9-5) |
| P3 (堅実党 実投票) | **NO_GO (現時点)** | 口座分離 (9-3) + 入金ハードキャップの runner abort 実装 (9-2) + 昇格ゲート定義 (9-6.2) が前提 |
| P4 (ロマン党 + 配信) | **NO_GO (現時点)** | P3 全条件 + 配信法務レビュー (9-6.5)。実投票配信は本書スコープ外 |

> **総括**: 方向性 (本線維持・隔離エンタメ・ロマン党 ringfenced) は ★賛成★。だが現状の §4 ガードレールは
> 「sim の停止条件」を「実投票の安全弁」と取り違えており、★実投票に対する歯止めが 1 つも実装されていない★。
> 「楽しむ」が「破産・追い入金」に化ける経路 (9-2) が最大リスク。shadow で骨組みを作るのは歓迎、
> ただし実投票は 9-2/9-3 の実装と 9-6 の SOP が揃うまで凍結する。 — シズネ

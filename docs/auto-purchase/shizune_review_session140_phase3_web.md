# シズネレビュー — Session 140 / 券種選択 web 配線 (Phase 3 表示層)

> 対象: Python (`bettype_selection.py`) が書いた `betting_selection.json` artifact を読んで
> odds-race ページの「🎫 券種選択」タブに表示する **display-only** 機能。
> 金経路には触れない (投票・金額決定はしない)。選択ロジック本体と Phase2 効率ビューは
> Session 138/139 でレビュー済 → 今回は **「表示が選択ロジックを忠実に表しているか」
> 「誤誘導防止フレーミングが web 描画で崩れていないか」** に集中。

## 結論

**条件付き GO**

- display-only であり金経路に到達しないため、**マージは 🔴 1 点を直せば可**。
- 🔴-1（強 -EV アンカーが「単勝◎に集中」とだけ大きく出て、-EV 警告が `select_reason` の
  小さい灰色文字に埋もれる）は **このプロジェクトの本丸（誤誘導防止）に直接触れる**ので、
  マージ前に必須修正とする。実データに該当レースが現存する（後述）。
- 残りは 🟡4 / 🟢2。忠実性そのものは概ね良好（artifact の主要フィールドは落ちていない）。

検証データ: 実 API `2026053005021102`（5/30 東京2R・concentrate・軸◎4インタノン・5選択/6降り）+
artifact 全 24 レース走査 + 市場オッズ欠落レース `2026053008031103`（強 -EV アンカーのみ selected）。

---

## 🔴 マージ前に必須

### 🔴-1 「単勝◎に集中」表示が強 -EV を隠す（誤誘導の本丸）

実 artifact `2026053008031103`（合成用の市場オッズが DB に無い → 複合は全 skip、基準券種のみ残る）の中身:

- selected: `単勝 EV=0.53` / `複勝 EV=0.68`（どちらも**強い期待値マイナス**）
- `decision_reason` = 「複合券種に fund 対象なし (EV<floor=1.0 等) → 単勝◎に集中」
- `select_reason` = 「軸◎の単勝 (基準券種・アンカー) ※EV=0.53<1.0 (本命だが期待値マイナス寄り)」

UI 上の描画（`BetTypeSelectionTab.tsx`）:

- 「判断」ボックスに `decision_reason` がそのまま出る → **「単勝◎に集中」という前向きな指示文だけが目立つ**（`BetTypeSelectionTab.tsx:217-220`）。
- 「✅ 買う券種」見出し横に「複合券種なし → 軸◎に集中」が出る（`:247-249`）→ さらに集中を後押し。
- 肝心の **-EV 警告は `select_reason` の `text-[10px] text-gray-500`（10px の灰色）**（`:280-282`）に埋もれる。EV 列（0.53）も「未満=灰」色（`evColor`, `:71`）で**目立たない**。
- 結果: 「複合がダメなら本命の単複に集中すればいい」と読め、**EV0.53（控除込みで実質半分が溶ける買い目）を踏む**方向へ視線が流れる。ふくだ君の本能（『本命なら堅い』）と合わさると危険。

これは should_fund の契約「◎単/複はアンカー常時 fund（EV<1.0 でも候補）」自体は正しい（-EV 保護は下流 Kelly が担う、候補段階は amount 無し）。だが**表示が「候補として残しているだけ」でなく「集中せよ」という推奨に読める**のが問題。`bettype_selection.py:138` のコメント通り「-EV は _base_reason で正直に注記する」が、その注記が UI で小さすぎて誤誘導防止になっていない。

**修正案（いずれか / 併用可）**:
1. selected 行で `expected_return < 1.0` のとき、券種ラベルか EV 列に **amber の「期待値マイナス」ピル**を立てる（灰色に沈めない）。アンカー（単/複）が -EV のときは特に。
2. `decision_reason` が「単勝◎に集中」を含み、かつ selected の基準券種が全部 -EV のケースは、判断ボックスを **amber 系の警告色**にする（slate の中立色だと「OK の指示」に見える）。
3. 「✅ 買う券種」見出しの「軸◎に集中」注記を、アンカーが -EV のときは「軸◎に集中（ただし単勝 EV<1.0＝期待値マイナス）」に書き換える。

最小実装は案1（EV<1.0 の selected 行に amber バッジ）。これだけで「集中＝得」の誤読を断てる。

---

## 🟡 推奨（マージ後早期に）

### 🟡-1 ヘッダーの「戦略」がフォールバック後の実効戦略を取り違える

ヘッダーは `strategyLabel(data.selection_strategy)`（= file レベルの要求戦略）を出している（`BetTypeSelectionTab.tsx:194`）。一方で **`skip_all` への自動フォールバックは `sel.strategy`（= selection レベルの実効戦略）に入る**（reader 型定義 `betting-selection-reader.ts:54` のコメント「実効戦略 ('skip_all' を含む)」、Python `bettype_selection.py:362-366`）。

- 現状の全 24 レースには skip_all フォールバックが無い（実害は未顕在）が、**「fund 対象 0 件 → 全見送り」になったレースでも、ヘッダーには要求戦略（例: concentrate）が出続ける** = 「全見送り」という最重要の結論がヘッダーに反映されない。
- `isSkipAll` の判定は正しく `sel.strategy === 'skip_all'` を見ている（`:177`）が、ヘッダーのバッジは `data.selection_strategy`（file 値）を見ている。**判定と表示でソースがずれている**。
- 加えて `STRATEGY_LABEL` に `skip_all: '全見送り'` は定義済（`:48`）なのに、ヘッダーでは到達しない。

**修正案**: ヘッダーの戦略バッジを `sel.strategy`（実効）優先にし、要求と異なる場合は「concentrate → 全見送り」のように両方出す（CLI `_print_selection` の `eff` 表現 `bettype_selection.py:559` と揃える）。`requested_strategy` フィールドは reader 型にあるのに UI で一切使われていない（`betting-selection-reader.ts:55`）→ ここで使う。

### 🟡-2 「EV プラスだが降りた」券種が灰色 skip 行に埋もれ、忠実だが不親切

実データ `2026053005021102` の skipped に **馬連 ◎-相手4 / EV=1.04（期待値プラス！）/ vs単=lt / 「EV>=floor だが合成<=単 (広げる相対妙味薄) → 単に集中」** がある。

- これは選択ロジックの核心（concentrate は `funded AND merit` の AND 条件、`bettype_selection.py:252`）を正しく反映した skip で、**忠実性は OK**。
- だが UI 上は skip テーブルの行で `opacity-70` の灰色（`:335`）、EV=1.04 も `evColor` では緑（`:69`）だが skip 文脈に置かれるため、**「EV プラスなのになぜ降りた？」が一瞬で読み取りづらい**。skip_reason は出ているので情報としては落ちていないが、Phase2（効率ビュー）を見ていないユーザーには「EV プラスを見送る」判断の根拠（合成<=単＝広げる相対妙味なし）が伝わりにくい。
- 逆方向の誤読（「降りたのは全部 -EV だろう」と思い込む）も起きうる。

**修正案（軽め）**: skipped 行のうち `expected_return >= ev_floor` のものに「EVは足りるが集中」等の小バッジを立てるか、skip_reason の該当文を少し強調。忠実性問題ではないので 🟡。

### 🟡-3 selected テーブルの vs単「単より高(sky)」が「買い得」と誤読される残存リスク

誤誘導防止バナー（`:223-229`）と中立色設計（sky=中立、`VsTanshoBadge` のコメント `:74`）は Phase2 と整合しており良い。ただし **selected（=買う）テーブルの中**に「単より高」バッジが並ぶと、「選ばれた＋単より高＝買い得だから選ばれた」と短絡される余地が残る。

- Phase2（効率ビュー）は全プランを並べる判断支援なので「単より高」が中立でも誤読は限定的。
- Phase3（選択ビュー）は **「選ばれた券種」という文脈が付く**ので、同じ中立バッジでも「選定理由＝単より高」と読まれやすい。実際の選定理由は EV 絶対水準（`select_reason` に明記）であって vs単ではない。
- バナーは「fund 判断は EV 絶対水準のみで vs単は参考」と書いているので**文言レベルでは防御済**。ただバナーは上部、バッジは下部のテーブルにあり、視線が離れている。

**修正案（任意寄りだが推奨）**: selected テーブルの vs単 列ヘッダーに `(参考)` を付ける、または列をデフォルト控えめ表示にする。「選定の根拠は EV 列、vs単は参考」を列レベルで明示。

### 🟡-4 「✅ 買う」という語が「推奨＝この通り買え」と読まれる（candidate 性の希薄化）

観点4（判断支援 vs 推奨）への指摘。

- 見出しが **「✅ 買う券種」**（`:245`）と断定的。candidate 注記（`:232-236`）は「これは候補、投票は最新オッズで再計算」と正しく書いてあり、Session 139 の「最後の判断＝最新オッズが正」「真の檻は config per_race/per_day」とも整合している（良い）。
- ただし candidate 注記は `text-[11px] text-gray-500` の小さい灰文字で、見出しの「✅ 買う券種（緑・太字）」の方が圧倒的に目立つ。**「買う」と緑チェックの組み合わせは『確定した推奨リスト』に見える**。
- このタブ単体で「この5点を買えばいい」と受け取られると、Phase3 が「判断支援」でなく「自動推奨」に化ける。プロジェクト原則「人間が形骸化するリスク（半自動の罠）」に触れる。

**修正案**: 見出しを「✅ 買う候補（N件）」または「✅ fund 候補」にして candidate 性を見出しに織り込む。candidate 注記をバナー並みの視認性（枠付き）に格上げするのも可。

---

## 🟢 任意

### 🟢-1 freshness の stale 閾値 180分は妥当だが「生成時オッズ」の含意を強調したい

`freshnessLabel`（`:104-114`）は 180分で stale 警告。Phase2 と揃っている（`BetTypeEfficiencyTab.tsx:81`）。

- 文言は「N分前のオッズで選択」で Phase2 の「N分前のオッズ」より一歩踏み込んでいて良い（選択がオッズ依存だと示せている）。
- ただし**選択結果（どの券種を買うか）はオッズが動けば変わりうる**点（EV が floor をまたぐと selected ⇄ skipped が入れ替わる）が、鮮度ラベルだけだと伝わりにくい。candidate 注記と合わせれば足りるので 🟢。
- 閾値 180分自体は「朝生成 → 昼レース」程度の運用なら妥当。レース直前用途なら短くしたいが、それは将来の vb_refresh 統合（artifact 鮮度自動化）の領域。

### 🟢-2 reader / API の堅牢性は良好（軽微な確認のみ）

- reader: `getBettingSelectionByDate` / `ByRace` とも try/catch → null（`betting-selection-reader.ts:96-105`）。例外握り潰しは display-only として妥当。`dateFromRaceId` の 16桁 + 数字チェック済（`:89-92`）。
- API: 16桁 + 数字の 400 ガード（`route.ts:16-18`）、artifact 無し / レース無しの 404 + 再生成 hint（`:22-30`）、`force-dynamic`（`:12`）→ 静的キャッシュ 404 罠（web-route-force-dynamic-404 の教訓）を踏まない。良い。
- UI: AbortController で abort 後の setState を全箇所ガード（`:137,145,148`）、空 selected（skip_all / fund対象なし）の分岐（`:252-255`）、skipped 0件は非表示（`:312`）、null フィールドは `fmtOdds`/`fmtEv` が `—` 化（`:56-61`）。崩れない。
- 1点だけ: API レスポンスは `result`（`{selection, selection_strategy, ev_floor, taste, generated_at}`）を**そのまま返す**ので、`data.selection` 前提（`:174`）と一致。型 OK。

---

## 忠実性チェック（artifact フィールド → 表示）

| フィールド | 表示 | 判定 |
|---|---|---|
| `axis_umaban` / `axis_name` / `axis_odds` | ヘッダーバッジ（`:189-192`） | ✅ 空名は `馬{n}` フォールバック（`:176`） |
| `selected_plans[].{bet_type,label,legs,hit_prob,synthetic_odds,expected_return,vs_tansho,select_reason}` | selected テーブル全列 | ✅ 全フィールド表示 |
| `skipped_plans[].{bet_type,label,expected_return,vs_tansho,skip_reason}` | skipped テーブル全列 | ✅ **skip_reason 出る**（降りた理由を隠さない） |
| `decision_reason` | 判断ボックス（`:219`） | ⚠ 🔴-1（強 -EV 時に誤誘導） |
| `warnings` | 下部 + ⚠（`:374-376`） | ✅ 市場オッズ欠落 warning 表示確認 |
| `strategy`（実効・skip_all 含む） | `isSkipAll` 判定のみ | ⚠ 🟡-1（ヘッダーは file 値で実効を取り違える） |
| `requested_strategy` | **未使用** | ⚠ 🟡-1（フォールバック表現に使うべき） |
| `selection_strategy`（file） | ヘッダー + 下部注記 | △ 実効と混同（🟡-1） |
| `ev_floor` | ヘッダー（`:196`） | ✅ |
| `taste` | バッジ（`:197-201`）+ TASTE_LABEL | ✅ 網羅（`popularity_gap_max`/`ev_min`） |
| `specialist` | バッジ（`:202-206`） | ✅（実データに該当無し、コードは正しい） |
| should_fund「◎単/複は EV<1.0 でも候補」 | selected に出る + `select_reason` に -EV 注記 | ⚠ 🔴-1（注記が小さすぎて -EV が伝わらない） |

落ちているフィールドは無い。歪みは 🔴-1（強 -EV の見せ方）と 🟡-1（実効戦略の取り違え）の2点。

---

## ふくだ君に確認したい論点

1. **🔴-1 の扱い**: 市場オッズが取れず複合が全 skip → 強 -EV のアンカー（単 EV0.53 等）だけが「単勝◎に集中」と出るケース、UI で「期待値マイナス」を amber で立てて良いか？ それとも「合成オッズが無い＝そもそも選択タブの判断材料が無い」として、このタブ自体を控えめ表示（warning 前面）にしたいか。ロジックは正しいので**見せ方だけの判断**。
2. **🟡-4「買う」という語**: 見出しを「買う候補」に弱めるのは哲学的に OK か？ ふくだ君は「最後の判断＝最新オッズが正」「自分で判断する」立場なので candidate 性を強調する方が整合すると見るが、「候補」と書くと逆に頼りなく感じるか確認したい。
3. **このタブの位置づけ**: Phase2（効率ビュー）と Phase3（選択ビュー）が並ぶことで「効率→選択」の流れは良い。ただ Phase3 を見て「この通り買おう」と手で IPAT に入れる運用が想定にあるか？ あるなら 🟡-4 の candidate 強調と、将来「選択結果→投票」を配線する時の per_race/per_day ハードキャップ（Session 139 の真の檻）への接続を今から意識しておきたい。

---

## Session 140 カカシ対応（ふくだ判断反映 / 2巡目へ）

ふくだ君の判断を反映し、🔴-1 + 非論争な 🟡 を `BetTypeSelectionTab.tsx` で修正済。

| # | 指摘 | ふくだ判断 / 対応 |
|---|---|---|
| 🔴-1 | 「単集中」が強 -EV を隠す | **「バッジ+EV色+バナー」採用**（最強案）。① EV<floor の selected 行に amber「期待値−」バッジ ② その行の EV 値を灰→amber（`negEv ? amber : evColor`）③ **単集中×全アンカー -EV のレースはカード冒頭に警告バナー**（`concentratedNegative`: combo=0 かつ positiveEV=0）「複合が全部降り、残るのは期待値マイナスの◎単／複だけ。集中≠安全。見送りも有力」。実データ `2026053008031103`（単0.53/複0.68）でバナー+バッジ発火を確認 |
| 🟡-4 | 「買う」が「推奨＝この通り買え」に読める | **「買う候補」/「降りた候補」に弱化**（ふくだ哲学「最後の判断＝最新オッズが正」と整合、candidate 性を見出しでも明示） |
| 🟡-1 | ヘッダー戦略バッジが file 値で skip_all フォールバックを取り違える | **`sel.strategy`（実効）表示に修正**。`sel.strategy !== sel.requested_strategy` のとき「（要求 ◯◯）」併記。`requested_strategy` を実使用に |
| 🟡-3 | selected の「単より高(sky)」が選定理由に読まれる | **vs単 列ヘッダーに「※参考」明示**（選定根拠は EV 絶対水準である旨を視覚補強） |
| 🟡-2 | EV>=floor だが合成<=単で降りた馬連が灰 skip 行に埋もれる | 忠実表示なので**保留**（skip_reason に「EV>=floor だが合成<=単 → 単に集中」と出る）。将来 skipped 側でも EV>=floor を弱く立てる余地あり |
| Q3 | Phase3→手 IPAT 運用想定 | ふくだ未回答。**将来「選択結果→投票」を配線する際は per_race/per_day ハードキャップ（Session 139 の真の檻）への接続を必須**として記録 |

検証: 新規/修正ファイル tsc エラー0・eslint clean（`set-state-in-effect` 回避済）。odds-race ページ HTTP 200（combo / -EV単集中 両レース）。API 400/404 ガード健在。

→ **2巡目レビュー（🔴-1 クローズ確認）をシズネに依頼中。**

---

## 2巡目（カカシ修正の検証 / シズネ）

### 結論: 🔴-1 クローズ = **YES**。残 🔴 ゼロ → **無条件 GO**（display-only）。

独立検証（実 API + artifact 直読み + JS ロジック再現 + Python 選択ロジック精読）で、1巡目の 🔴-1 と 🟡4 点が全て意図通り潰れたことを確認。新たな誤誘導・表示崩れは無し。1 点だけ将来の 🟢（実害ゼロの理論境界）を置き土産として残す。

### 🔴-1（本丸）クローズ根拠

検証は全て「artifact の実値 → JS の判定ロジックを Python で再現 → コードと一致」で裏取り。

1. **EV<floor の selected 行に amber「期待値−」バッジ** — `BetTypeSelectionTab.tsx:192` `isNegEv = ev !== null && ev < evFloor`、`:301`→`:311-314` で発火。実 API `2026053008031103`（単 EV=0.528 / 複 EV=0.683）で両行 `negEv=True` を確認。
2. **EV 値色 灰→amber** — `:329-332` `negEv ? 'text-amber-700 ... font-semibold' : evColor(...)`。`negEv` 行は amber、それ以外は従来 `evColor`。意図通り。
3. **単集中×全アンカー -EV バナー** — `:189-190` `concentratedNegative = selected.length>0 && comboSelected.length===0 && !hasPositiveSelected`、`:272-278` で「複合が全部降り、残るのは期待値マイナスの◎単／複だけ。集中≠安全。見送りも有力」を amber バナーで前面化。`2026053008031103` で `concentratedNegative=True` を確認。
4. **二重後押しの除去** — 旧「複合券種なし → 軸◎に集中」注記（集中をさらに後押ししていた）に `&& !concentratedNegative` ガード（`:266`）が付き、バナーが出るレースでは消える。前向き注記と警告バナーが同時に出る矛盾を回避。良い修正。

### `concentratedNegative` の境界を厳しく検証（5/30 全 24 レース走査）

| 境界ケース | 期待挙動 | 実測 | 判定 |
|---|---|---|---|
| 単集中×全-EV（combo 0・positiveEV 0） | バナー発火 | **10/24 レースで True**（誤発火なし） | ✅ |
| combo>0（複合 fund あり） | バナー不発火 | 全て False（`2026053005021102` 等） | ✅ |
| 単集中だが EV>=floor（プラス） | バナー不発火・行バッジなし | `…105`(単1.047/複1.052)/`…109`(単1.242) で `CN=False` | ✅ |
| **単集中・単はプラス／複だけ -EV** | バナー出ない・複行のみバッジ | **`2026053008031109`（単1.242 / 複0.939）で `CN=False` かつ複行 `negEv=True`**。banner と badge の役割分担が実データで効いている | ✅ |
| selected 空（skip_all / fund対象0） | バナー不発火（`selected.length>0` ガード） | 該当 0 件だがコード上 False 確定 | ✅ |

- **「combo>0 だが全部 -EV」でバナーも行バッジも漏れる見落とし** — concentrate は `funded AND merit`（`bettype_selection.py:252`）の AND 条件なので combo 選択行は構造的に EV>=floor のみ。5/30 でも該当 0 件。よって concentrate ではこの穴は起き得ない（行バッジも当然不要）。
  - ただし **`spread_if_worth` 戦略**（`bettype_selection.py:279-296`）は `should_fund` を通らなくても `vs_tansho=='gt'` なら EV<floor の combo を selected に残す。この戦略では combo>0 でも -EV 行が混ざりうる → そのとき `concentratedNegative=False`（combo>0 のため）でバナーは出ないが、**行バッジ（`isNegEv`）は EV<floor を拾うので各 combo 行に「期待値−」が立つ**。バナーは「全アンカーが -EV のとき集中を戒める」用途、行バッジは「個別 -EV を埋もれさせない」用途で役割が分離しており、`spread_if_worth` でも行バッジが誤誘導を防ぐ。穴なし。

### 🟡 クローズ確認

- **🟡-1**: ヘッダー戦略バッジが `sel.strategy`（実効）に修正（`:208`）、`sel.strategy !== sel.requested_strategy` で「（要求 ◯◯）」併記（`:209-213`）。`requested_strategy` を実使用（reader 型 `betting-selection-reader.ts:55` が UI に到達）。`STRATEGY_LABEL` に `skip_all:'全見送り'`（`:48`）があるので skip_all フォールバック時は「戦略: 全見送り（要求 集中（保守））」と正しく出る。判定（`isSkipAll`, `:177`）と表示のソースずれ解消。✅
- **🟡-3**: vs単 列ヘッダーに「※参考」（`:295`、`text-gray-400`）。選定根拠は EV 絶対水準である旨を列レベルで補強。✅
- **🟡-4**: 見出し「✅ 買う候補」（`:264`）/「✖ 降りた候補」（`:358`）に弱化。candidate 性が見出しに織り込まれた。✅
- 🟡-2 は忠実表示として保留（合意済）。回帰なし。

### 回帰チェック（新たな誤誘導・表示崩れ）

- **バナー多重表示なし**: 誤誘導防止バナー（vs単 説明・`:242-248`）はヘッダーカード、`concentratedNegative` バナー（`:272-278`）は selected カード冒頭で別カード。同一レースで両方出ても文脈が分離しており「うるさすぎる」二重警告にはならない。むしろ前者=一般原則、後者=このレース固有の警告で補完関係。
- **「複合券種なし→軸◎に集中」と警告バナーの矛盾**: `:266` の `!concentratedNegative` ガードで排他。前向き注記が出るのは「単集中だが残りがプラス」のレース（`…105`/`…109`）のみで、これは集中して問題ないケース。整合。
- **バッジ過剰**: `negEv` バッジは EV<floor の行のみ。combo がプラスのレース（`…102` 等）では 0 個。控除率下の常態（-EV 多発）でも、selected に残るのはアンカー（常に fund）と EV>=floor の combo なので、バッジが付くのはアンカー -EV と spread_if_worth の残置 combo に限られ、洪水にはならない。
- **forced amber の読みやすさ**: EV 列が amber + 行頭バッジ amber + （該当時）バナー amber と amber が重なるが、これは「-EV を埋もれさせない」という 🔴-1 の趣旨に沿った意図的強調であり、過剰評価不要（display-only）。

### 🟢 置き土産（実害ゼロ・将来の堅牢化メモ、GO を妨げない）

- **🟢 null-EV アンカー × バナー文言の断定**: anchor（単/複）は `should_fund` で常に fund=True（`bettype_selection.py:145`）、かつ EV が null でも selected に入る。単勝オッズ完全欠落（`axis_odds=None`、`bettype_efficiency.py:374`）のレースで単集中になると、`hasPositiveSelected=false`（null は `>= floor` を満たさず除外、`:183-184`）＋ combo 0 → `concentratedNegative=true` でバナーが出る。だがバナー文言は「**期待値マイナス**の◎単／複だけ」と断定する一方、`isNegEv = ev !== null && ev < floor`（`:192`）は null 行にバッジを立てない。つまり「EV 不明（マイナスと確定していない）」を「マイナス」と断言する**逆方向の軽い誤誘導**になりうる。
  - **実害**: 現存 artifact 全 24 レースで null-EV anchor は **0 件**。`2026053008031103` も単勝オッズだけは取れて EV=0.53 が出ている。完全欠落（単勝すら取れない）は朝早い時間・取消・地方等で理論上起きうるが頻度は極小。
  - **将来対応案（任意）**: バナー / バッジ判定を「EV<floor かつ非null」と「EV=null（不明）」で文言分岐するか、null-EV anchor のみのレースは `concentratedNegative` から外して「市場オッズ未取得＝選択材料不足」の warning（既に `warnings` 表示機構あり・`:416-418`）に寄せる。display-only かつ実害 0 のため 🟢。

### 検証に使った根拠

- 実 API: `2026053008031103`（単集中×全-EV、`CN=True`・両行バッジ）/ `2026053005021102`（combo 3 fund、`CN=False`・バッジ 0）を curl→python json で確認。
- artifact 直読み（`C:\KEIBA-CICD\data3\races\2026\05\30\betting_selection.json`）で 24 レース全走査 → `concentratedNegative=10`、combo 全-EV=0、skip_all=0、null-EV anchor=0。混合ケース `2026053008031109`（単+/複−）を実確認。
- 全 artifact 横断（現状 5/30 のみ）で null-EV anchor 0 件。
- Python 選択ロジック精読（`should_fund` `:132-149`、`_select_concentrate` `:242-262`、`_select_spread_if_worth` `:279-296`、`build_plans` `:374-381`）で combo に -EV が混ざる戦略を特定し、行バッジが拾うことを確認。

### ふくだ君に確認したい論点（2巡目）

1. **🟢 null-EV アンカーのバナー文言**: 実害 0 だが、将来「単勝オッズ完全欠落」レースが単集中になると「期待値マイナスと断言するが実は不明」になる。今は据え置き（GO）で良いか、それとも将来 vb_refresh 統合（artifact 鮮度自動化）のタイミングで「不明」表示を入れるか。記録だけ残したい。
2. **`spread_if_worth` の行バッジ運用**: この戦略は EV<floor の combo を「相対妙味あり」で selected に残す = 行に「期待値−」バッジが並ぶ。これは正しい挙動だが、ふくだ君の運用で `spread_if_worth` を使う想定があるなら、「-EV だが広げる」の意図が select_reason（`:317-319`）で十分伝わるか、実レースで一度目視確認しておきたい。

→ **2巡目クローズ。display-only として無条件 GO（マージ可）。**

### 🟢 (null-EV アンカー文言) も先回り対応

シズネ 2巡目の置き土産（アンカー EV が全 null のとき banner が「マイナス」と断言＝不明を負と誤誘導）を、0 件でも誤誘導防止の本丸として先回り修正。
- `concentratedNegative` を「base-only かつ正の妙味なし **かつ アンカーに EV 算出済が1件以上**」に厳格化（`anchorEvKnown`）。
- 全アンカー EV=null は別フラグ `concentratedUnknownEv` で**灰色の「判断材料なし（オッズ未取得）。オッズ確定後に再生成を」**バナーに分離（マイナスと断言しない）。
- 全 artifact (5/30 の 24 レース) で `concentratedUnknownEv` は 0 件 = 既存挙動は不変、将来オッズ確定前生成の経路だけ塞いだ。tsc/eslint clean・両レース HTTP 200 維持。

→ **残 🔴 ゼロ・残 🟡 ゼロ・🟢 も対応済。Phase3 web 配線 完了。**

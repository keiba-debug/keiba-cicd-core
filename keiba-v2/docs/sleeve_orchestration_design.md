# スリーブ・オーケストレーション — 設計書 (Session 176・買い目スリーブを並行運用する)

> **対象**: 自動投票を「単一方式を丸ごと置き換える」運用から、**独立した買い目スリーブ（sleeve）を
> 複数本 並行で走らせる**運用へ拡張する構想。各スリーブは自分のエッジ・サイザー・隔離口座を持ち、
> 1つのオーケストレーターが集約して **1本の IPAT 実行口** から投票する。
> **正本ステータス**: この doc がスリーブ並行運用の設計正本。初版 = Session 176 (2026-06-25)。
> **発端**: ふくだ「今後こういった自動投票のロジックを丸ごと置き換えるのではなく、新たなスリーブを
> 追加したり、何本か並行で買い目を作るみたいなことも検討可能だろうか」(S176)。
> **関連**: `[[selection_engine_design]]` / `[[market_calibration_edge_map]]` / `[[gap-tansho-live-project]]`
> `[[character-betting-personas]]` / `[[manual-auto-bet-coexistence]]` / `[[shizune-agent]]`
> `[[tansho-central-strategy]]` / `[[feedback_betting_philosophy]]`

---

## 0. なぜ作るか (S176 の発端)

S163 以降、自動投票は **1つのサイザーを sweep で詰めては丸ごと差し替える**（`shobu_rate` →
`wide_anaba` → `sanrentan_formation` → `gap_tansho`）を繰り返してきた。だが S173-176 の市場較正監査で
**「エッジは1つの方式に集約されるのではなく、複数の狭い tail に分散して存在する」** と分かった
(`market_calibration_edge_map.md`)：
- **① gap単勝（逆張り単）** = AI評価＞人気の過小評価馬の単勝（実装済・本投票化）。
- **② 高ARD妙味穴** = 20–100倍の妙味穴単勝（`ana_tansho_shadow` で shadow 運用中）。
- さらに ふくだの **キャラ別買い方**（本命党/妙味党/三連単ロマン党/複勝転がし党 ＝
  `[[character-betting-personas]]`）も「独立口座で並行運用するエンタメ枠」として構想済み。

→ **1方式 = 1スリーブ**として独立に育て、**複数本を並行**で走らせれば、丸ごと置換の破壊的変更を
やめ、エッジを足し算で増やせる。ふくだの賭け哲学（型に縛らない・自分にできない買い方を見つける
＝`[[feedback_betting_philosophy]]`）とも整合する。

### 0.1 既に半分できている
今の `gap_tansho_scheduler`（S176）は **「安全機構は共有・選定/サイズ/口座(state/lock/cage/bankroll)は
隔離」** という作りで、`freebudget → bettype → gap` と積み上げた「スケジューラを足す」パターンの最新形。
**これを一般化すれば「スリーブ・レジストリ＋オーケストレーター」になる**。本 doc はその一般化を設計する。

---

## 1. 設計の肝 — IPAT/TARGET は物理的に1本 (最重要制約)

`bettype_auto.bat` ヘッダ「freebudget_auto と同時 live 起動しない（IPAT 排他）」が示す通り、
**投票の実行口（TARGET ウィンドウ操作 ＋ IPAT ログインセッション ＋ 暗証番号入力）は1つしかない**。
複数スケジューラが同時に `runner` subprocess を起動すると、画面自動操作（SetForegroundWindow /
クリック）が衝突し、二重投票・誤投票・セッション切れの温床になる。

→ ★結論★: **「買い目を並行で作る」のは各スリーブが純関数として行ってよいが、「投票（runner 実行）」は
1つのオーケストレーターが直列に1本化する**。これが本設計の背骨。

```
  並行OK ──────────────────┐         ┌────── 直列・1本化 (IPAT排他)
  逆張り単(gap) → RaceSizing │         │
  妙味穴単(ana) → RaceSizing │ → 集約 → │ → runner 1回/レース → IPAT
  本命党/ロマン党… → RaceSizing│  (merge)│   (全スリーブの該当レースの脚を1呼び出しに束ねる)
  └────────────────────┘         └──────
```

---

## 2. アーキテクチャ — スリーブ・レジストリ ＋ オーケストレーター

### 2.1 Sleeve インターフェース (純粋な「買い目生成器」)
各スリーブは **DB/IO/subprocess/投票を持たない純関数の束**として定義する。`gap_tansho_live` が雛形：

```
Sleeve = {
  key:            str            # "gap_tansho" / "ana_tansho" / ...
  display:        {label, thesis, betType, resultsLink}   # ActiveMethodCard 用 (S176 で確立)
  is_enabled():   bool           # master switch (config から。 gap_enabled 同様)
  bankroll():     int            # 隔離口座残高 = 初期 + 専用台帳の実現PnL (gap_tansho_live と同型)
  day_cap():      int            # スリーブ別日次cap = 残高×day_pct%
  size_race(pred_race, bankroll) -> RaceSizing | None    # 選定+サイズ (select + stake)
  settle_day(date, votes) -> ledger_day                  # 実払戻で専用台帳に実現PnL蓄積
}
```

- gap は既に `gap_tansho_live.{read_gap_config, account_balance, size_gap_race, settle_gap_day}` で
  この形を満たす ⇒ **GapSleeve は薄いアダプタで載る**。
- ana（妙味穴単）は `ana_tansho_shadow.{select_ana_tansho, settle}` があるので、サイザーと
  隔離台帳を足せばスリーブ化できる。

### 2.2 Orchestrator (安全機構を1箇所に集約)
オーケストレーターは現行スケジューラの **timing / lock / state / halt / オッズ鮮度 / 連続失敗 /
recovery / runner投票** を **1つだけ**持ち、レースごとに全 enabled スリーブを回す：

```
run_pass(date, now, live):
  for race in 窓内レース:
    legs = []
    for sleeve in registry.enabled():
      rs = sleeve.size_race(race, sleeve.bankroll())     # 並行に買い目生成
      if rs: legs += tag(rs.legs, sleeve.key)             # 脚にスリーブ名タグ
    merged = merge_and_dedup(legs)                        # §4 重複方針
    if 全体日次cap / per_race番人 を満たす:
      vote_once(race, merged)                             # ★runner 1回 = IPAT排他を構造回避★
      record(state, per_sleeve_attribution)              # スリーブ別に投票額/結果を帰属
```

- **state/lock は1ファイル**（`sleeve_orch_*`）。スリーブ別の口座台帳は各スリーブが持つ（隔離維持）。
- 既存 `gap_tansho_scheduler` / `bettype_scheduler` は **オーケストレーターに吸収**（または当面は
  別 bat として残置しロールバック可）。`freebudget_scheduler` の安全機構 import 流用は継続。

### 2.3 レジストリ
`sleeve_registry.py`：`{key: Sleeve}` の dict。enable は各スリーブの config（`<key>_enabled`）。
新スリーブ追加 = レジストリに1行 + Sleeve実装 + config キー + display。**オーケストレーターは無改変**。

---

## 3. 表示 (ActiveMethodCard の一般化)

S176 で作った `/api/bankroll/active-method` ＋ `ActiveMethodCard` を **「稼働中スリーブ一覧」**に拡張：
- API は bat（オーケストレーター起動）＋レジストリ＋各 config を読み、**enabled スリーブの配列**を返す。
- カードは各スリーブを1枚ずつ（label / thesis / 稼働中・停止中 / 口座残高 / 検証リンク）並べる。
- 「今日この口座は何を狙って・いくら張っていて・累計いくらか」を一望できる（運用の透明性）。

---

## 4. 重複・マージ方針 (要決定・シズネ論点)

同一レースで複数スリーブが**同じ馬の同じ券種**（例：単勝 馬11）を推した場合の扱い：

| 案 | 内容 | 長所 | 短所 |
|---|---|---|---|
| **A 合算1枚** | stake を合算して1枚購入、払戻はスリーブ別に按分計上 | IPAT 枚数最小・控除率影響なし | 帰属計算が要る・どちらの予算から出すか規則化必要 |
| **B 別建て** | スリーブごとに別ポートフォリオ/別チケットで購入 | 帰属が自明・台帳が綺麗 | 同一馬に2枚＝IPAT/TARGET 操作が増える・点数番人に当たりやすい |
| C 優先1本 | 優先度高いスリーブだけ買い、他はスキップ | 単純 | 機会損失・「並行」の意味が薄れる |

★S176 確定 = **B（別建て）**★（ふくだ採用＝シズネ推奨・§11-2/§11-6）：スリーブごとに別チケットで購入。
既存 settle/ledger を無改修でスリーブ別に呼べて税SoT・破産ガード・監査が最もきれい。gap/ana は狙う帯が
違い同一馬衝突がレアなので IPAT 枚数増も許容範囲。**A（合算1枚＋按分）は不採用**（① settle 二重計上
§11-1d ② per_race縮小時の按分書き戻し未実装で破産ガードが崩れる §11-1c が未解決）。A は衝突が頻発・
枚数が問題化し、かつ按分3点（書き戻し/二段settle/監査根拠）がテスト付きで揃ってから後付け最適化。
（異なる券種・異なる馬は単純に別脚として束ねるだけ＝衝突しない。）

---

## 5. 予算管理 — 二段キャップ ＋ 破産ガード (シズネ正本領域)

- **スリーブ別**: 各スリーブの `bankroll()`（隔離残高）× 比率で1点、`day_cap()` で日次上限（gap と同型）。
- **全体（オーケストレーター）**: **全スリーブ合計の日次純投資 ≤ 全体日次cap**。1日の IPAT 入金額を
  全スリーブ合計が超えないことを保証（`[[manual-auto-bet-coexistence]]` の檻リスクの一般化）。
  - ★S176 確定（§11-6）★: 全体cap の出どころ = **専用キー（明示のハード上限）**。入金額（`daily_start_balance_yen`）
    流用は「誤って増える」リスクがあるため不採用（シズネ §11-1a）。
  - ★口座は分離しない（同一口座運用）★: 手動投票はその日しない運用ルールで「最大損失 ≤ 入金額」を担保。
    口座分離が無いぶん全体cap は自動分しか縛らない（運用規律でカバー＝ふくだ承知のリスク受容）。
  - 純損失ベース（回収差引）で判定＝既存 `day_recovery.compute_recovery` を全スリーブ合算で再利用。
    ただし B 別建て前提なので、cage 判定は **votes をスリーブ key でフィルタ**してスリーブ別＋全体の二段で。
- **per_race番人**: runner の `per_race_max_yen` は1レース合計（全スリーブの脚の和）に効く。
  合算がこれを超える場合の縮小/優先規則が要る（§4A の按分と整合）。
- **破産ガード**: 各スリーブは比例サイジング（残高×%）で破産確率0%を内包（gap 監査済）。全体でも
  入金額上限で最大損失を固定。**スリーブを増やしても「最大損失 ≤ 入金額」は不変**にする。

---

## 6. 税 SoT / 帰属 (purchase_ledger 拡張)

- `purchase_ledger.record_portfolio_votes` は既に `portfolio_strategy` / `strategy_name` タグを持つ
  ⇒ **各脚にスリーブ名を入れる**だけで税SoT上のスリーブ別集計が可能（現 gap は未タグ＝ここで付与）。
- §4A 合算1枚にする場合、ledger 上は1チケットだが `notes`/イベントにスリーブ別按分を残す。
- スリーブ別損益は各スリーブの隔離台帳（`userdata/<key>_live/ledger.json`）が SoT。purchase_ledger は
  税・監査の SoT（全投票）。二系統の役割分担は gap で確立済（`gap_tansho_live`）。

---

## 7. スリーブ候補 (ロードマップ)

| 優先 | スリーブ | エッジ/狙い | 状態 |
|---|---|---|---|
| 1 | **本命EV単（honmei_ev）** | AI本命(rank_w=1)×市場過小評価(gap≥3)×EV≥1.3×接戦の単勝 | ✅ 実装済（S177・★2本目として実装★・有効化待ち） |
| 2 | **逆張り単（gap_tansho）** | AI評価＞人気の過小評価馬の単勝・中〜高配 | ✅ 実装済（S176・本投票化・稼働中） |
| - | 妙味穴単（ana_tansho） | 高ARD×20–100倍の妙味穴単勝 | shadow 運用中 → 将来スリーブ化 |
| - | 本命党 | 堅軸の単/複（高的中・死なない） | 構想（`[[character-betting-personas]]`） |
| - | 三連単ロマン党 | フォメで天井狙い（`sanrentan_formation` 流用） | 既存サイザーあり |

→ ★S177: 2本目はふくだ指定で **本命EV単**（推奨画面 tansho_ippon と同条件）を採用（ana でなく）。
  優先度 = **本命EV単 > 逆張り単**（registry 登録順）。これで「並行」を実証する。

---

## 8. 移行計画 (段階・挙動不変で積む)

1. ✅ **完了 (S176)** — **オーケストレーター骨格** + **GapSleeve**（gap ロジックをスリーブ化）で **gap単独**。
   実装: `ml/strategies/sleeves/{base,gap_sleeve,registry}.py` + `ml/strategies/sleeve_orchestrator.py`
   （freebudget 安全機構 + bettype 投票経路を import 流用・state/lock=`sleeve_orchestrator_*`）。
   ★挙動完全一致を証明★: `ml/analyze/verify_sleeve_parity.py` が 6/21 で **差分0**（orchestrator(gap単独) ≡
   `gap_tansho_scheduler`・東京3R/11R とも同一 bet_spec/amount）。test 9 green（計161 green・回帰なし）。
   `SizedLeg.sleeve` タグ追加（B別建ての帰属）。**bat 差し替え済**（`bettype_auto.bat`/`settle_auto.bat` の
   `gap_tansho_scheduler`→`sleeve_orchestrator`・cp932+CRLF・exit0・live no-op 確認・`.bak_s176_orch`）。
   active-method API も orchestrator を gap として検出（カード継続動作）。**稼働は gap_enabled 有効化待ちのまま**。
2. **AnaSleeve（妙味穴単）** を追加 → 「2本並行」を dry → shadow 並走 → 実弾化（master switch）。
3. §4 マージ/§5 全体cap/§6 タグ を実装（2本目で初めて衝突が現実化するため、ここで本実装）。
4. 表示（ActiveMethodCard 一覧化）。
5. 以降はレジストリにスリーブを足すだけ（本命党/ロマン党…）。

★各段階で「最大損失 ≤ 入金額」「IPAT は1本」「冪等（二重投票なし）」を回帰テストで担保★。

---

## 9. 未決論点 (シズネレビュー対象)

1. **§4 重複マージ**: A（合算按分）でよいか／按分規則の正確性／どの予算から出すか。
2. **§5 全体cap**: 全体日次capのソース（入金額流用 or 専用キー）／per_race番人と合算の整合。
3. **スリーブ別 vs 全体の優先順位**: 全体capに当たったとき、どのスリーブを優先して残すか。
4. **失敗・halt の粒度**: 1スリーブの連続失敗で全体を止めるか、そのスリーブだけ止めるか。
5. **手動投票との共存**: 全体capは自動分のみ縛る（`[[manual-auto-bet-coexistence]]` 未解決の口座分離）。
6. **税SoT 按分の監査可能性**: 合算1枚のスリーブ別按分が後から検証できる形か。
7. **【シズネ追加】合算1枚 settle の二重計上**: §4A 合算後、各スリーブ台帳が `settle_gap_day` 型の素朴合算で cost を積むと1枚を複数スリーブが二重計上する。按分 settle 経路が未実装（§11-1d）。
8. **【シズネ追加】境界レース・最終レースでの全体cap執行漏れ**: per-pass で逐次投票する構造上、最後に評価したスリーブだけが cap で弾かれ「先に評価された順」で予算を食う先着順問題（§11-1b）。
9. **【シズネ追加】halt 粒度とドメインの非対称性**: IPAT/runner 由来の失敗（セッション切れ・二重投票疑い）は全体halt、選定/データ起因の失敗は当該スリーブのみ skip、という二軸の切り分け（§11-1e）。
10. **【シズネ追加】手動 + 複数スリーブ合算での「最大損失 ≤ 入金額」の崩れ**: 同一口座だと全体cap は自動合算しか縛らず、手動分が乗ると入金額を超過しうる（§11-1a）。口座分離をスリーブ2本目の前提条件にすべきか。

---

## 11. シズネ・リスクレビュー (Session 176)

> **結論（先に）**: 設計の背骨「並行で作る／投票は1本化」は ★賛成★。だが **このまま2本目（ana）の
> 実弾化に進むのは NO_GO**。理由は (i) §4A 合算1枚の按分 settle が未実装で台帳が二重計上しうる、
> (ii) per_race_cap の縮小規則（`fit_legs_to_cap`）がスリーブ優先度を見ず低EV順に削る＝意図しない
> スリーブが消える、(iii) 全体cap執行が per-pass 逐次のため先着順で予算を食う、(iv) 手動併用下では
> 「最大損失 ≤ 入金額」が口座分離なしには保証されない。**gap単独のスリーブ化（§8-1・挙動不変）まで
> は GO**。2本目は下記ガードを実装してから。

### 11-1. 盲点・抜け穴（並行で初めて顕在化）

**a) 「最大損失 ≤ 入金額」は合算＋手動で崩れる（最優先）**
- 全体cap のソース＝`daily_start_balance_yen`（入金額）流用案（§5）は **自動スリーブ合算しか縛らない**。
  手動 IPAT 投票は purchase_ledger を通らず全体cap の分母に入らない（`[[manual-auto-bet-coexistence]]`）。
  同一口座だと「自動合計≤入金額」を守っても、人が別に打てば口座実残高ベースの最大損失は入金額を超える。
- スリーブ別 bankroll は隔離台帳（`gap_tansho_live`）で破産0%を内包するが、**それは各口座内の話**。
  全体の最大損失＝Σ（各スリーブ day_cap）＋手動分。**スリーブを N 本に増やすと自動分の1日最大損失も
  N 倍に積み上がる**（各 day_pct×bankroll の和）。設計書§5「スリーブを増やしても最大損失≤入金額は不変」は
  ★全体capが Σ day_cap を実際に上から抑える実装になっていて初めて真★。今は全体cap実装が未着手。
- ★処方★: (1) 全体日次cap＝ハード上限を **専用キー**で持ち（入金額流用でなく明示・誤って増えない）、
  Σ自動スリーブ純投資 ≤ 全体cap を runner 直前にアサート、超過分は §11-3 の優先順位で縮小/skip。
  (2) **実弾スリーブ2本目の前提条件＝自動専用 IPAT 口座への分離**（`[[manual-auto-bet-coexistence]]` の解）。
  分離前は「2本目も shadow に留める」を既定にする。

**b) 全体cap の per-pass 先着順問題（執行漏れ）**
- §2.2 の擬似コードは「レースごとに enabled スリーブを回し、全体日次cap を満たせば vote」。だが
  pass はレース順に進むため、**早い時間帯のレースで先に評価されたスリーブが cap を食い切ると、後半の
  高EVレースに全体capが残っていない**＝「先に来た者勝ち」。境界レース（capちょうど跨ぎ）でも、合算の
  どの脚を残すか規則がないと毎回挙動が変わる（再現性なし＝監査で説明できない）。
- ★処方★: 全体cap は **1日の純投資の積み上げ**として逐次減算で運用しつつ、capに当たったレースでは
  §11-3 の優先順位で「残すスリーブ／削る脚」を決定的（deterministic）に選ぶ。乱数・dict 順序依存は禁止。

**c) 合算1枚の按分が破産ガードを崩す経路**
- §4A 合算1枚は「stake合算→1枚購入→払戻を按分」。だが各スリーブの1点額は `stake_for(balance,bet_pct)`＝
  **自スリーブ残高×%** で破産0%を保証している。合算後に per_race_cap（`fit_legs_to_cap`）で縮小されると、
  **どのスリーブの実投下額が幾ら減ったか**を按分台帳に正しく戻さないと、台帳上の bankroll と実投下が乖離し、
  次回の `stake_for` が誤った残高で1点額を出す＝比例フラクショナルの破産ガード前提が崩れる。
- `fit_legs_to_cap`（`ml/strategies/bettype_sizing.py:177-212`）は縮小・drop を **EVキー＋ANCHOR保護**で
  行い、**スリーブ帰属を一切見ない**。合算脚を縮めたとき「gap の脚を 1,500→900、ana を 2,000→1,800」の
  ような按分結果をスリーブ台帳に書き戻す処理が現状ゼロ。
- ★処方★: 合算1枚にする場合、`fit_legs_to_cap` 適用後の **各脚最終 amount をスリーブkeyで集計し直して
  各台帳の当日 cost に記録**する（settle 時の cost は「実際にそのスリーブに帰属した投下額」で積む）。
  これが無いなら §4A でなく §4B 別建てにせよ（下記 11-2）。

**d) 合算 settle の二重計上（実装ギャップ・実害）**
- 現 `settle_gap_day`（`ml/strategies/gap_tansho_live.py:200-229`）は `state["votes"]` の `exit_code==0`
  vote の amount を **丸ごと cost に積む**。合算1枚にすると1チケットに複数スリーブの stake が乗るため、
  各スリーブ台帳がこの素朴 settle を呼ぶと **同じ払戻を複数スリーブが二重計上 / cost を二重計上**する。
- `compute_recovery`（`ml/strategies/day_recovery.py:64-141`）も `votes` 全体を口座区別なく合算するので、
  スリーブ別 cage 判定には votes を **スリーブkeyでフィルタして渡す**改修が必須（今は無区別）。
- ★処方★: settle は (i) 全体purchase_ledger＝税SoT（合算1枚＝1ticket）、(ii) スリーブ台帳＝按分後の
  スリーブ別 cost/payout、の **二段で別ロジック**にする。スリーブ台帳の settle は「合算前の自スリーブ脚」
  だけを対象にする（vote 記録にスリーブkey＋按分前後 amount を残すのが前提）。

**e) halt の波及範囲（ドメイン非対称）**
- §9-4「1スリーブの失敗で全体止めるか」。失敗には2種ある：
  **(1) 投票実行口の失敗**（IPATセッション切れ・SetForegroundWindow衝突・二重投票疑い＝
  `target-clicker-timing-fix` のゾンビrunner遅延成功）→ これは **共有資源の事故＝全体 halt** が正しい
  （1本しかない投票口が壊れているのに他スリーブが投げ続けるのは危険）。
  (2) 選定/データ起因の失敗（あるスリーブの predictions 欠損・select 例外）→ **当該スリーブだけ skip**、
  他は継続。
- ★処方★: halt を「グローバルhalt（投票口由来）」と「スリーブhalt（選定由来）」の2軸に分け、
  既存 `freebudget_scheduler` の halt 機構はグローバル側に割り当てる。スリーブhalt は当該 Sleeve の
  `is_enabled()` を当日 false に倒す soft-disable で十分。

### 11-2. §4 マージA（合算按分）の是非 — シズネ推奨

| 観点 | A 合算1枚＋按分 | B 別建て |
|---|---|---|
| IPAT枚数/操作 | ◎ 最小 | △ 同一馬で枚数増 |
| 控除率二重取り | ◎ 回避 | ✕ 同一馬2枚で控除二重 |
| 税SoT帰属 | △ **按分の記録設計が要る** | ◎ 自明（1脚=1スリーブ） |
| 破産ガード整合 | ✕ **縮小時の按分戻しが必須**（11-1c） | ◎ 各台帳が自分の脚だけ見る |
| 監査可能性 | △ 按分根拠を notes に残せば可 | ◎ 完全分離 |
| 実装コスト | 高（按分 settle 新規） | 低（既存 settle 流用） |

- ★シズネ推奨★: **当面は B（別建て）を既定にし、A は「同一馬・同一券種が現実に頻発し IPAT 枚数が
  問題化したら」最適化として後付け**する。理由：
  1. gap/ana はどちらも単勝・狭い tail。**同一レースで同一馬を両スリーブが推す頻度は低い**（gap＝
     AI評価＞人気の過小評価、ana＝20–100倍の高ARD穴で狙う帯が違う）。衝突がレアなら A の実装コストと
     破産ガード崩れリスクは割に合わない。
  2. B なら `settle_gap_day` / `compute_recovery` / `record_portfolio_votes` を **無改修でスリーブ別に
     呼べる**（各スリーブが自分の脚だけ）。税SoT は ticket 単位 `strategy_name` で既に分離可能
     （`writer.py:252,301`）。**監査が一番きれいなのが B**。
  3. ★A が安全に成立する条件★＝(i) `fit_legs_to_cap` 後の按分 amount をスリーブ別に書き戻す経路、
     (ii) スリーブ台帳 settle が按分後 cost を使う、(iii) purchase_ledger に按分根拠（各スリーブの
     按分前後 amount）を notes/event で残す、の3点が **テスト付きで実装済**であること。これが揃うまで A は不可。
- 別建て B で IPAT 枚数が増える件は、**「同一馬同一券種が衝突した時だけ amount を足して1枚」**という
  限定マージ（券種・馬が完全一致のときのみ）に留めれば、按分の複雑さを最小化できる（部分集合だけ A）。

### 11-3. 執行順序・優先度（全体capに当たった時に残すスリーブ）

★規則案（決定的・監査可能）★:
1. **第1キー＝スリーブ優先度（ふくだ指定の固定順）**。エッジの確度が高い順に手動で順序を固定
   （初期＝ gap > ana > 本命党 > … ）。「高EV優先」を動的に使うと **オッズ直前判定の後知恵リスク**
   （`feedback_odds_gate_hindsight`）＋再現性低下があるため、第1キーは固定順を推奨。
2. **第2キー（同一スリーブ内で削る脚）＝低EV順**。既存 `fit_legs_to_cap` の挙動を踏襲（ANCHOR保護）。
3. **隔離残高比例は使わない**（残高が大きいスリーブが全体capを独占し、新規スリーブが永久に張れない
   飢餓を生む）。
4. ★フェイルセーフ★: 優先度が引き分け・判定不能なら **そのレースは全スリーブ見送り**（張らない側に倒す）。
- これにより「全体capに当たった日、どのスリーブが残ったか」が **固定順＋低EV順で一意に説明可能**になる
  （税務質問・事故調査で「なぜこの日 ana だけ買っていないのか」に答えられる）。

### 11-4. フェイルセーフ既定（不確実時は賭けない／少なく）

★`compute_recovery` の「回収0に倒す」思想（`day_recovery.py:17-25,89,118,133`）をオーケストレーター
全体の既定にする★。明文化する不確実時の挙動：

| 不確実事象 | 既定の倒し方 |
|---|---|
| 全体cap残額が計算不能（recovery DBエラー等） | recovery=0扱い＝**グロスで早めに止まる**（緩めない） |
| スリーブ bankroll の当日凍結値が取れない | そのスリーブは当日 **size_race=None（張らない）** |
| オッズ鮮度 NG / vb_refresh 停止 | 全スリーブ **当該レース見送り**（鮮度ゲートは共有・既存踏襲） |
| 合算按分の帰属が一意に決まらない | **別建て B にフォールバック**（足さない＝二重計上もゼロ） |
| 投票口の状態不明（receipt未取得・dialog timeout） | **グローバルhalt**＝以降のレース投票停止＋手動照合フラグ |
| config 読込失敗 | gap と同じく `enabled=False` の安全側（`gap_tansho_live.py:75,95`） |

- 原則：**「賭けすぎる方向の誤りは絶対に作らない／賭けなさすぎる方向の誤りは許容する」**。回収・残額・
  帰属の3つは常に保守側（回収=0、残額=最小、帰属=分けない）に丸める。

### 11-5. 段階移行（§8）のゲート条件（リスク観点で具体化）

各段階を本番（実弾）に進める前の **必須回帰テスト／検証**：

| 段階 | 必須ゲート（これが green でなければ進めない） |
|---|---|
| **§8-1 gap単独スリーブ化** | (a) 現 `gap_tansho_scheduler` と **同一入力で買い目・amount・state が完全一致**を dry で差分0証明（リグレッション）。(b) 二重投票なし＝同一レース2回pass で idempotency により ledger 増分0。(c) settle 冪等＝同日2回 settle で台帳 pnl 不変。 |
| **§8-2 ana 追加（dry→shadow）** | (a) ana は **auto_vote no-op の shadow** で最低 4週末 並走し、shadow台帳の cost/payout が手計算と一致。(b) gap と ana が **同一レース同一馬を推した実例**を1件は人手で追い、§4方針（B別建て or A按分）どおりに記録されるか確認。(c) per_race_cap 縮小が起きるケースを合成データで作り、縮小後 amount のスリーブ別合計＝台帳 cost を **テストで固定**。 |
| **§8-3 全体cap/マージ/タグ本実装** | (a) 「Σ自動スリーブ純投資 ≤ 全体cap」を **境界値テスト**（capちょうど・cap-100・cap+100）。(b) 全体capに当たった時の残存スリーブが §11-3 の固定順で**決定的**（同入力で同結果）。(c) 合算1枚採用なら 11-1c/d の按分書き戻し＋二重計上なしを **専用テスト**（payout を2スリーブに按分した和＝実払戻、を assert）。(d) 手動投票を1件混ぜた日で「最大損失 ≤ 入金額」が口座分離前提で保たれるかを **手計算照合**。 |
| **§8-4 表示一覧化** | (a) ActiveMethodCard が enabled/disabled・各口座残高を **台帳と一致**して表示（表示と実体の乖離は事故源）。 |
| **共通（全段階）** | ★「最大損失 ≤ 入金額」「IPAT は1本（runner 1回/レース）」「冪等（二重投票なし）」の3不変条件を回帰テストで毎回担保（§8 末尾の既存方針を**テストIDで固定**）。実弾化は shadow 黒字でなく **ガード green が条件**（エッジが薄い＝CI下限81%なので、勝ってからでなく安全が揃ってから実弾化）。 |

### 11-6. ふくだ判断（S176 確定）
1. **口座分離 = しない。同一口座＋全体日次cap で運用**（ふくだ選択）。シズネ推奨（自動専用 IPAT 口座
   分離を ana 実弾化の必須前提）は **不採用**。代わりに **「手動投票をその日はしない」運用ルール**で
   「最大損失 ≤ 入金額」を担保する。
   - ★承知のリスク受容★: 口座分離が無いと **全体cap は自動合算しか縛らない**ため、運用ルールを破って
     手動投票が乗ると入金額を超過しうる（§11-1a の警告は残存）。これは ふくだが運用規律で引き受ける前提。
   - ★実装要件★: それでも全体cap（Σ自動スリーブ純投資 ≤ ハード上限）は **必須実装**（§5・§11-1b）。
     口座分離が無いぶん、全体cap の執行漏れ（先着順・境界レース）は §11-3 の決定的順序で厳密に塞ぐ。
2. **§4 = B（別建て）で確定**（ふくだ採用＝シズネ推奨）。A 合算は衝突頻発・IPAT枚数が問題化し、かつ
   §11-2 の按分3点（書き戻し/二段settle/監査根拠）がテスト付きで揃ってから後付け最適化。
3. **スリーブ優先度の固定順 = 2本目（ana）を載せる段階で確定**（ふくだ「あとで決める」）。それまでは
   §8-1（gap 単独）に集中＝優先順は不要。確定するまで全体cap執行の第1キーは保留。

### 11-8. シズネ・リスクレビュー（S177 本命EV単実装 — 条件付き NO_GO）
> **総評 = 条件付き NO_GO（実弾化は1点修正してから）**。口座隔離・settle分離・master switch・
> 全体cap境界・決定的執行は GO。ただし下記 per_race_cap×マルチスリーブの実害バグを直すまで
> 「2本同時 enabled での実弾化」は止める。**本命EV単は現状デフォルト無効＝gap単独は安全**（単一
> スリーブでは merge 溢れが起きない）。

★🔴 実害バグ（実弾化前 必須修正・§8-3 ゲート未充足）★:
- 各スリーブは自分の脚だけを per_race_cap に fit（`honmei_ev_live.py:204-205`/`gap_tansho_live.py:186-187`）
  するが、**orchestrator の merge（`sleeve_orchestrator.py:273-280`）が merged 合計に fit をかけない**。
- 2スリーブが同一レースに別馬で乗ると merged = 5200+3000 = **8200 > per_race_cap 5200**。dry はスルー
  （テスト緑）だが **LIVE は runner が abort exit 5 → exit∈HALT_EXIT_CODES → 当日全 halt**、halt理由は
  「セッション切れ」と誤表示（誤った事故対応 SOP を誘発）。単勝主力2本の同一レース被りは稀でない。
- ★シズネ推奨修正（最小・§11-3整合）★: merge 前に全体cap と同じ固定順ループで
  `running_race_total + rs.total_yen ≤ per_race_cap` を満たすスリーブだけ kept（低優先=逆張り単を
  レース単位で丸ごと落とす）。残りがなお cap 超なら最優先1本だけ `fit_legs_to_cap`。低EV順 drop は
  §11-3 の固定順と衝突するので使わない。
- ★テスト穴★: `test_orch_merges_both_sleeves_b_betsuda` は per_race_cap=20000 で干渉回避＝**本番値
  5200 での溢れが未テスト**（§11-5 §8-2c「per_race縮小後 amount のスリーブ別合計＝台帳cost」未充足）。
  修正時に「merged ≤ per_race_cap を固定順で満たす」回帰＋「vote_one_race_multi に渡る bet_specs 合計
  ≤ per_race_cap」を追加必須。

★ふくだ確認待ち（3点）★:
1. 被り時の方針: ①固定順で逆張り単をレース見送り（5200維持・シズネ推奨）か ②それぞれ満額で買う
   （per_race_max_yen 上げ or スリーブ別per_race＝§11-7-5 の据え置きと矛盾するので要再考）。
2. per_race_cap=5200 据え置きの再確認（①なら本命EV単5200・逆張り単は残りに入れば、の挙動）。
3. 全体cap 専用キー `sleeve_total_day_cap_yen` を web 有効化時に明示設定する運用にするか（0=Σ自動だと
   3本目追加で静かに上限が膨らむ・シズネ明示推奨）。

その他のシズネ指摘（GO だが運用メモ）:
- 観点6: 全体cap は自動分のみ縛る（§11-1a 据え置き・ふくだ承知）。専用キーは明示推奨。
- 観点7: select_honmei_ev は `win_vb_gap`/`win_ev`/`predicted_margin` を直読み（`honmei_ev_live.py:122`）。
  実 predictions に欠損があると静かに全除外＝「動くのに買わない」になる→実データで存在を1件確認のこと。

★11-8 追補（シズネ 2巡目・runner番人の制約）★:
- runner `_check_per_race_limits` は **レース合算 total** を per_race_max_yen(5200) と比較し超過で **exit 5**
  （`runner.py:248-281,405-411`）。**スリーブ概念なし**＝IPATが1レース1本投票である以上、物理的にレース合算でしか縛れない。
- 現状コードの安全範囲: 各スリーブの size_race が per_race_cap=5200 で自脚を fit するため **本命EV単 単独**
  なら 6000→5200 で runner OK（halt しない）。**バグは2スリーブ被り時の merged 溢れ**（5200+α>5200→exit5→halt）。
- ★ふくだの「各スリーブ自分の2%で買う」は per_race_max_yen=5200 据え置きとは両立しない★:
  - **案A（ふくだ希望を叶える）**: スリーブ別上限（各6000）＋レース合算上限（新キー、**runner per_race_max_yen と一致必須**・
    起動時アサート）。合算 fit は §11-3 固定順で**スリーブ丸ごと落とし**（按分しない＝§11-1c 破産ガード維持）。
    → per_race_max_yen を 6000（単独満額）or 12000（2本満額）へ**引き上げる判断が要る**（§11-7-5 の据え置き見直し）。
  - **案B（5200据え置き・最保守）**: merge を固定順 fit で 5200 に収める。本命EV単も 5200(1.73%) のまま＝ふくだ希望は叶わない。
  - 案C（runner をスリーブ単位化）= IPAT 合算1本ゆえ番人の唯一性が崩れる→却下。
- ★判定★: **本命EV単 実弾化の前に 案A か 案B を必ず1つ実装**（merge 溢れ放置＝2スリーブ被りで day-halt）。
  「後回し可」の唯一の条件 = 本命EV単を gap と同時 enable しない運用。**現状 master switch 既定 False ＝有効化しなければ安全**。
- ふくだ確認(更新): ①案A か案B か（=ふくだの「各自2%」を叶えるか／5200維持か） ②案Aなら per_race_max_yen の新値
  ③合算で削る時はスリーブ丸ごと見送り（按分しない）で確定して良いか（シズネ=丸ごと推奨）。

### 11-7. ふくだ判断（S177 確定 — 2本目スリーブ）
1. **2本目スリーブ = 本命EV単（honmei_ev）**（ana でなく）。推奨馬券画面の主力プリセット
   `tansho_ippon`（rank_w=1×win_vb_gap≥3×win_ev≥1.3×predicted_margin≤60）を同条件でスリーブ化。
   選定は bet_engine PRESETS['tansho_ippon'] と parity（test で条件ドリフト検知）。
2. **優先度の固定順 = 本命EV単 > 逆張り単**（registry 登録順・全体cap執行の第1キー）。§11-6-3 の保留を確定。
3. **口座 = 30万 別建て（gap と隔離）・即実弾**（shadow 先行はしない）。master switch（`tansho_ev_enabled`・
   既定 False）は残し、web 資金管理で有効化するまで no-op＝gap と同じ安全弁。
4. **全体日次cap = 専用キー `sleeve_total_day_cap_yen`**（web 設定可・0=自動=Σ sleeve day_cap）。§5/§11-1a の必須実装。
5. ★per_race_cap 判断★: ~~`per_race_max_yen=5200` は据え置き~~ → **【S177 追加判断で撤回・案A確定】**。
   下記7参照。当初「5200据え置き・2%は5200にtrim」としたが、シズネ2巡目(§11-8)で「ふくだの『各スリーブ
   自分の2%で買う』は per_race_max_yen=5200 と両立しない(runner番人がレース合算で判定)」と判明し、
   ふくだは **案A（それぞれ満額・per_race を上げる）** を選択。
6. （旧6）ガード状態は §8-3 既実装。実弾化は §11-5 ゲート green が条件。
7. ★per_race 二段化 = 案A 確定（ふくだ S177・§11-8）→ ★S178 実装完了★★: **スリーブ別上限（各スリーブ
   自分の比率）＋レース合算上限（新キー `sleeve_per_race_cap_yen`・runner `per_race_max_yen` と一致必須・
   ★各パス先頭でアサート★）** の二段。同一レース被りで合算上限超過時は **固定順（本命EV単優先）で低優先
   スリーブをレース単位で丸ごと見送り（按分しない＝§11-1c 破産ガード維持）**。
   - ★S178 ふくだ最終確認 = 合算上限 **12000**★（両スリーブ満額＋余裕。 本命EV単 2%=6000 ＋ 逆張り単
     1.5%=4500 = 10500 ≤ 12000。 比率を ~2%/2% に上げても耐える）。`per_race_max_yen` は web で 12000 に
     引き上げる（BudgetForm「レース合算上限」入力が `per_race_max_yen` と `sleeve_per_race_cap_yen` を
     **同値で連動保存**＝食い違いを構造的に防ぐ）。
   - ★実装★: `sleeve_orchestrator.resolve_per_race_cap()` が `(combined_cap, ok, source)` を返す。
     `read_per_race_max_yen()` は runner `_read_bankroll_limits` と **同条件**（limit_mode==absolute のみ）で
     per_race_max_yen を読む（shobu 換算 `read_per_race_cap` は combo 用なので不使用＝合算cap=runner一致を保証）。
     専用キーが per_race_max_yen と食い違うと `ok=False` → **そのパスは1円も投票しない fail-safe**
     （size 上限と runner の番人が食い違うと merge 溢れ→exit5→day-halt するため）。 merge は kept ループで
     全体日次cap＋レース合算cap を固定順に満たすスリーブだけ残し、 最終層に二重ガード（合算超過なら末尾
     スリーブを丸ごと落とす）。 各スリーブは自分の脚を per_race_cap で fit 済（スリーブ別上限）。
   - テスト（`ml/tests/test_sleeve_orchestrator.py`・本番値）: 12000で両満額(10500)・旧5200で逆張り単を
     固定順 drop し溢れなし・境界(10500/10400)・bet_specs合計≤cap・runner一致アサート/不一致 fail-safe。計24 green。
   - ★稼働の最後の一手★: ふくだが web 資金管理で **「レース合算上限」= 12000 を保存**するまでは
     `per_race_max_yen=5200` のまま＝衝突レースでは逆張り単が見送られる（**安全・halt なし**だが両満額は出ない）。
6. ★ガード状態★: §8-3 の全体cap/決定的優先(固定順)/B別建て/スリーブ別settle は §8-1 で既に実装済
   （orchestrator）。S177 で 2本目を実装し **マルチスリーブ回帰テスト**（B別建てmerge・全体cap境界・
   決定的執行）を追加し全 green。**実弾化はシズネ §11-5 共通ゲート green が条件**（shadow 黒字でなく安全が揃ってから）。

---

## 10. 変更履歴
| Session | 変更 |
|---|---|
| 176 | 初版。ふくだ「丸ごと置換でなく並行スリーブ追加」構想を設計化。IPAT排他＝投票1本化が背骨。スリーブ・レジストリ＋オーケストレーター（各スリーブ=純粋な買い目生成器、安全機構は集約）。予算二段cap・重複マージ(A合算按分推奨)・税SoTタグ・表示一覧化・移行計画(gap単独で挙動不変→ana追加で並行実証)。未決論点はシズネレビューへ。 |
| 176 | §11 シズネ・リスクレビュー追記。総評＝gap単独スリーブ化(§8-1挙動不変)はGO／ana実弾化はNO_GO(按分settle未実装の二重計上・fit_legs_to_capがスリーブ優先度を見ず低EV順drop・全体cap執行のper-pass先着順・手動併用下の最大損失保証)。**§4は当面B別建て推奨**(衝突レア・税SoT/破産ガード最もきれい、Aは按分書き戻し＋二重計上テストが揃うまで不可)。執行優先度=固定順第1キー＋低EV第2キー(動的高EVは後知恵回避で却下)。フェイルセーフ＝回収0/残額最小/帰属分けない の保守3丸め。段階ゲートをテストID固定で具体化。§9に4項目追加。 |
| 176 | **ふくだ判断確定(§11-6)**: ①口座分離=しない・同一口座＋専用キーの全体日次cap で運用(手動はその日しない運用ルールで最大損失≤入金額を担保・シズネ警告は承知のリスク受容)。②**§4=B別建てで確定**。③スリーブ優先度は2本目(ana)を載せる段階で確定(あとで)。→ 次の着手は §8-1 gap単独スリーブ化(挙動不変・3判断と無関係に安全)。 |
| 178 | **per_race 二段化 = 案A 実装完了(§11-7-7・§11-8 実害バグ修正)**。ふくだ最終確認=合算上限 **12000**(両スリーブ満額+余裕)。`sleeve_orchestrator.resolve_per_race_cap()` 新設(専用キー `sleeve_per_race_cap_yen`・runner `per_race_max_yen` と一致必須・不一致は **投票しない fail-safe**・shobu換算 read_per_race_cap は不使用で合算cap=runner一致を保証)。merge を kept ループで全体日次cap+レース合算cap を固定順に満たすスリーブだけ残す二段化(超過は低優先をレース単位で丸ごと見送り・按分しない=§11-1c)+最終層二重ガード。web: limit-resolver/config route に `sleeve_per_race_cap_yen` 追加、BudgetForm「レース合算上限」入力が `per_race_max_yen` と同値で連動保存(食い違い構造防止)+本命EV単のtrim文言を案A挙動に修正。本番値テスト計24 green/ML全体935 green(既存 bet_engine 7赤は S151 既知負債)/tsc src エラー0。**③ 推奨画面に逆張り単表示**: `web/src/app/predictions/lib/gap-tansho.ts`(select_gap_tansho の TS 忠実移植・表示専用)+race-card に「🔵逆張り単 N頭」ヘッダバッジ+該当馬行バッジ。★ふくだ enable は完了済(tansho_ev_enabled=true)・稼働の最後の一手 = web で「レース合算上限」12000 を保存★(それまで 5200 で衝突時は逆張り単見送り=安全・halt なし)。**④ 税SoT スリーブ帰属(§6 実装)**: 実投票が purchase_ledger に `strategy_name='manual_cli'` で記録されスリーブ不明だった問題を、runner `--leg-strategy`(--bet と同順・FfBet.strategy・bet_specs 文字列は無改変で parity 不変)+`vote_one_race_multi` が脚の sleeve を渡す経路で解消。自動投票履歴の「レース別購入」戦略列＋戦略別ROI表が本命EV単/逆張り単で自動分離(`AutoPurchaseHistory.StrategyCell` で色付きバッジ)。ふくだ S178 要望(どのエンジンか一目で)。テスト計27 green(orch24+leg-strategy3)。 |
| 177 | **2本目スリーブ = 本命EV単(honmei_ev) 実装(§11-7)**。ふくだ確定: 2本目はana でなく本命EV単(推奨画面 tansho_ippon と同条件)/優先度=本命EV単>逆張り単/30万別建て・即実弾(master switch は残す)/全体cap=専用キー(0=Σ)/per_race_cap=5200据え置き(2%は5200にtrim・承知)。実装: `honmei_ev_live.py`+`sleeves/honmei_ev_sleeve.py`+registry先頭登録+web(config route/limit-resolver/BudgetForm/active-method配列化/ActiveMethodCard複数描画)。テスト: honmei単体19+bet_engine parity+マルチスリーブ回帰(B別建てmerge/全体cap境界/決定的執行)=計64 green・tsc src エラー0。**稼働は web で tansho_ev_enabled=true 保存まで no-op**。残: ③推奨画面に逆張り単表示・シズネ実弾化ゲート点検。 |

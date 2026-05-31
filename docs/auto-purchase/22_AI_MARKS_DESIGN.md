# AI印 (markSet=6) 変換 + auto-danger スロット退避 設計書

ステータス: Step1(◎)実装+5/31実機apply済 / Step2(○▲△Ⅲ段差ベース+穴別系統)実装済(§7) / backtest 未了
対象セッション: Step1=Session140-141, Step2=Session141 / 関連: [[auto-purchase-project]] §AI印打ち構想2, [[bettype-selection-roadmap]], docs/auto-purchase/09_MY_MARKS_AND_STRATEGY.md §7/§9

---

## 0. 結論サマリ(採用する変換アプローチ・スロット・danger退避)

| 項目 | 決定 |
|---|---|
| 採用アプローチ | **rank-based(順位ベース)を主**、gap-based は「1強型なら◎のみで止める」抑制発想を `p_top1_gap` で**1ルールだけ後付け**(従) |
| なぜ rank-based | シズネ推奨。composite_score 降順→固定rank割当で**動的閾値補正ゼロ**、外部パラメータは重みベクトル `(wW,wP,wA)` 1本のみ。Session140 backtest と直結し、監査記録(§7再現性)に「composite最高だから◎」の一行で残せる |
| なぜ gap-based を主にしない | 即死バグ確定: 擬似コードの `race_confidence <= 0.3 / > 0.7` 閾値が**実データ 0-100スケール(median 80.55)と不一致**→全レースで confidence 分岐が死に、撃ちなし安全弁が永遠に効かない。gap閾値 1.0/0.5/0.4 も z-score空間の未検証仮値 |
| **Step1 スコープ** | **◎(本命)1頭のみ**を markSet=6 に書く。○▲△Ⅲは**書かない**(Step2以降)。**穴は書かない**(Themis逸脱回避、§4-E参照) |
| 既定重み | **等重み (1,1,1)**。P寄せ (0.5,2,0.5) は `--weights` で渡せる**実験パラメータ**に留め、本番既定にしない(full-selection ROI walk-forward 未了のため。Session140宿題⑤) |
| 物理スロット | **markSet=6 (UmaMark6/)**。手動印 markSet=1(MY_DATA直下)と物理分離。`load_my_marks(race_id, mark_set=6)` で既に読める |
| SoT | **Python(ml側)が純関数で印を決定→JSONL監査ログ→DAT書込み**。web API は「Python を起動する/結果を読む」だけ(predictions-reader / ledger-reader と同じ流儀) |
| **auto-danger 修正** | MARK_SET を **1→7** に退避(危は「確率補正係数」として分離スロットへ)。markSet=1 を**ふくだ手動専用に施錠**。残存危は**厳密バイト置換**でクリーンアップ(全クリア禁止) |

実データ確認済み(本設計の前提): predictions.json 24R / entry に `pred_proba_w_cal, pred_proba_p, pred_proba_p_raw, ar_deviation, rank_w, rank_p, odds, popularity` 実在。`race_confidence`=0-100, `p_top1_gap`=0-0.161, `p_top3_concentration`=0-0.643。4R京都(`2026053108031204`)は ar_deviation が10頭全null。

---

## 1. 変換ロジック仕様

### 1.1 純関数の入出力契約

```
ml/ai_marks/assign.py

def assign_ai_marks(
    entries: list[dict],
    weights: tuple[float, float, float] = (1.0, 1.0, 1.0),
    step: int = 1,
) -> AiMarkResult
```

入力 `entries`: predictions.json の `races[].entries[]`。各 dict から使うキー:
`umaban`(int), `pred_proba_w_cal`(float), `pred_proba_p`(校正済複勝率, float), `ar_deviation`(float or None)。
※ P成分は **校正済の `pred_proba_p` を使う**(`pred_proba_p_raw` ではない)。理由: W成分が校正済 `pred_proba_w_cal` なので、同じ校正済空間で z 化するのが整合的。raw は校正前で分布が違う。

出力 `AiMarkResult`(dataclass):
```
@dataclass
class AiMarkResult:
    marks: dict[int, str]          # {umaban: '◎'}  Step1 は ◎ 0〜1頭のみ
    skipped: bool                  # True=撃ちなし(印を1つも立てない)
    skip_reason: str | None        # 'too_few_runners' / 'flat_distribution' / 'adr_dropped_and_flat' 等
    adr_used: bool                 # ADR成分を composite に入れたか(全欠/分散ゼロで落としたら False)
    composite: dict[int, float]    # {umaban: composite_score}  監査用
    weights: tuple[float,float,float]
    notes: list[str]               # 'ADR成分を欠損のため除外' 等(監査ログにそのまま載せる)
```

純関数(I/Oなし・乱数なし・DB非依存)。同一入力→同一出力を保証(§7再現性)。

### 1.2 アルゴリズム(rank-based 主)

**Step 0: 早期撃ちなし**
- `len(entries) < 3` → `skipped=True, skip_reason='too_few_runners'`、`marks={}`。
- (race_confidence は **使わない**。0-100スケールの閾値換算が backtest 未了で恣意的になるため、Step1 では信頼度ゲートを撃ちなし判定に入れない。撃ちなし判定は「分布が平坦か」=composite の分散で行う=データ駆動で再現可能)

**Step 1: race内 z-score(外れ値ロバスト)**
- `z_w = robust_z(pred_proba_w_cal)`、`z_p = robust_z(pred_proba_p)`、`z_a = robust_z(ar_deviation)`。
- `robust_z` は median / MAD ベース(MAD=0 のとき std にフォールバック、std も 0 なら全頭 0 を返す)。理由: ADR の50±10帯域の外れ値(<30 / >70)や圧倒的人気で w_cal が突出するレースで平均/標準偏差が歪むのを抑える。

**Step 2: ADR欠損/分散ゼロの明示処理(silent degradation 禁止)**
- `ar_deviation` が **全頭 None or 全頭同値(分散ゼロ)** の場合:
  - `z_a` を全頭 0 にし、**ADR成分を composite から除外**(`adr_used=False`)。重みは `(wW, wP)` で再正規化。
  - `notes.append('ADR全欠損/分散ゼロのため2軸(W,P)判定に縮退')`。これを**監査ログに必ず残す**。
  - さらに W も P も分散ゼロ(全頭同スコア) → `skipped=True, skip_reason='flat_distribution'`(無作為◎を避ける)。
- 一部の馬だけ None(例: 348中10欠)→ その馬の該当成分のみ median 補完し `notes` に記録。全欠でなければ ADR成分は活かす。

**Step 3: composite 合成(重み正規化)**
```
denom = wW + wP + (wA if adr_used else 0)
composite[i] = (wW*z_w[i] + wP*z_p[i] + (wA*z_a[i] if adr_used else 0)) / denom
```

**Step 4: 平坦分布ガード**
- composite を降順ソート。`gap_top = composite[0] - composite[1]`。
- 全体が平坦(`max(隣接gap) < FLAT_EPS`、FLAT_EPS=0.10 を定数定義)→ `skipped=True, skip_reason='flat_distribution'`。
- これは z-score空間の値だが「**分散ゼロに近い=◎を立てる意味がない**」という**データ駆動の撃ちなし**であり、gap-based の経験的多段閾値(1.0/0.5/0.4)とは別物。閾値は1個(FLAT_EPS)に限定し A/B 可能にする。

**Step 5: ◎割当(Step1 のスコープ)**
- `marks = {composite[0].umaban: '◎'}`。tiebreak: composite 同点は `rank_w` 昇順(校正済勝率1位を優先)。
- ○▲△Ⅲ穴は **Step1 では一切書かない**。

### 1.3 gap-based からの「1ルールだけ」採用(従)

将来 Step2 で ○ 以下を書く際の**事前フック**として、`p_top1_gap` を「1強指標」に使う設計余地だけ残す(Step1 では未使用、コメントで明記):
- `p_top1_gap >= 0.10`(実データ max 0.161、median 0.064) → 1強型。Step2 で「◎のみ厳選、○以下を抑制」する分岐に使う候補。
- これは rank-based の**後付け抑制ルール**であり、◎決定ロジックには介入しない(◎は常に composite 最高)。

### 1.4 重み方針(規律)

- 既定 `(1,1,1)`。Session140 backtest「的中は等重みで十分」に準拠。
- P寄せ `(0.5,2,0.5)` は `--weights` で渡せるが **本番既定にしない**。Themis逸脱の正当化(ROIで重みを動かす)は full-selection ROI の walk-forward 裏取り後のみ(Session140宿題⑤)。それまでは「実験中フラグ」扱い、監査ログに `weights` を必ず記録。
- 同一日内で複数の重み方針を混在させない(市場判定がブレる/規律違反)。日次バッチは1つの weights で全レース処理。

### 1.5 edge case 一覧

| ケース | 挙動 |
|---|---|
| 出走 < 3頭 | 撃ちなし(`too_few_runners`) |
| ADR全頭null(例: 4R京都) | ADR成分除外+notes記録、W/P 2軸で◎決定。W/Pも平坦なら撃ちなし |
| ADR一部null | 該当成分のみ median 補完+notes、ADRは活用 |
| 全頭同composite(分散ゼロ) | 撃ちなし(`flat_distribution`)。無作為◎を出さない |
| 圧倒的人気(w_cal突出) | robust_z(MAD)で外れ値圧縮。composite最高がそのまま◎で問題なし |
| composite同点 | rank_w 昇順 tiebreak |
| 穴候補(高オッズ) | **Step1 では印を立てない**(§4-E)。将来は独立印でなくEV配分の重み係数 |
| race_confidence | Step1 では撃ちなし判定に使わない(0-100スケール、閾値 backtest 未了) |

---

## 2. 配置(新規 + 既存流用)

### 2.1 新規ファイル

| パス | 役割 |
|---|---|
| `ml/ai_marks/__init__.py` | パッケージ |
| `ml/ai_marks/assign.py` | **純関数 `assign_ai_marks()`**(§1)。I/O・DB非依存 |
| `ml/ai_marks/write_ai_marks.py` | CLI: `python -m ml.ai_marks.write_ai_marks --date YYYY-MM-DD [--weights 1,1,1] [--dry-run]`。predictions.json 読込→各race `assign_ai_marks`→**JSONL監査ログ追記**→`batchWriteHorseMarks` 相当の DAT 書込み(下記 writer 経由)。`--dry-run` は決定結果を表示し DAT を書かない |
| `ml/ai_marks/dat_writer.py` | **Python側 DAT writer**(markSet=6 専用)。`target-mark-reader.ts` の `batchWriteHorseMarks` とバイト互換(record_index=(day-1)*12+(race-1)、offset=record*44+6+(uma-1)*2、◎=0x819d)。**全18頭クリアはしない**=該当◎馬だけ書込み(auto-ard/vb と同流儀の「クリア→該当馬」だが Step1 は◎1頭なので、当該レコードの18頭分を 0x2020 でクリアしてから◎を書く=AI印スロットは AI 専用なので安全) |
| `ml/ai_marks/audit_log.py` | JSONL 追記ヘルパ(`data3/ai_marks/audit/{date}.jsonl`)。1行=`{ts, race_id, weights, marks, skipped, skip_reason, adr_used, composite_top3, notes}` |
| `ml/tests/test_ai_marks_assign.py` | 純関数ユニットテスト(§5 success criteria の固定入力) |
| `ml/tests/test_ai_marks_dat_writer.py` | DAT round-trip(書込み→`load_my_marks(rid, mark_set=6)`で◎が読める) |
| `web/src/app/api/target-marks/ai-marks/route.ts` | POST: `--date` を受け `python -m ml.ai_marks.write_ai_marks` を起動(child_process)。auto-danger と同じ admin 導線に並べる |
| `scripts/ai_marks_write.bat` | 手動/タスク実行用(create-windows-batch スキルで SJIS+CRLF 生成) |

### 2.2 既存流用(改変あり/なし)

| ファイル | 流用/改変 |
|---|---|
| `ml/features/my_marks.py` `load_my_marks(rid, mark_set=6)` | **改変なしで読める**(mark_set引数対応済)。ただし**危対応とは無関係**(AI印は◎○▲△Ⅲ穴=既に decode 可) |
| `web/.../target-mark-reader.ts` `batchWriteHorseMarks` / `VALID_MARKS` | TS 側からも書ける既存関数。ただし **SoT は Python**。TS 直叩きは使わず Python writer に寄せる(二重実装回避) |
| predictions-reader / admin/page.tsx | AI印 API を admin の自動印ボタン群に1行追加(§3.4 と同じ導線) |
| auto-danger `route.ts` | §3 で MARK_SET 1→7 改変 |

設計判断: **DAT 書込みを Python に一本化**。理由 — ①SoT を Python に揃える(本メモリの ledger/predictions と同じ)、②監査ログ・バリデーション・robust_z を1箇所に集約、③web は起動するだけで責務が薄い。TS の `batchWriteHorseMarks` は手動印 admin 経路で現役なので残すが、AI印では使わない。

---

## 3. auto-danger バグ修正(slot1→7退避 + 残存危クリーンアップ)

### 3.1 route.ts の変更(最小)

```ts
// auto-danger/route.ts
const MARK_SET = 7;          // ← 1 から 7 へ(危を分離スロットへ退避)
const DANGER_MARK = '危';    // 不変
```
- L83-94 の「全18頭クリア→危書込み」ロジックは markSet=7(危専用スロット)では安全=**そのまま流用可**(他markSetと干渉しない)。
- API レスポンス `summary.note='危印→markSet=7(UmaMark7)に書込み'` 追記、`console.error('[auto-danger API (markSet=7)] ...')`。

### 3.2 危 decode 対応(read 不能バグ修正 — シズネ赤旗)

**TS 側** `target-mark-reader.ts` `MARK_BYTES_TO_SYMBOL`(L16-24)に追加:
```ts
'8aeb': '危',
```
**Python 側** `ml/features/my_marks.py` `_MARK_BYTES_TO_SYMBOL`(L24-32)にも追加:
```py
b"\x8a\xeb": "危",
```
- これで markSet=7 に退避した危が web/Python 双方で読み戻せる(round-trip 成立)。
- 注意: 危は手動印の優先度体系に混ぜない。`MARK_PRIORITY` に危は**入れない**(危は信頼度補正係数であって序列印ではない)。`load_my_marks(rid, mark_set=7)` で読むと `mark_priority=0`(未定義)で返る—危専用に別 reader 関数 `load_danger_marks(rid)` を `my_marks.py` に足し、`is_danger=True` フラグで返すのが筋(序列印 API と混線させない)。

### 3.3 残存危クリーンアップ(厳密バイト置換 — 全クリア禁止)

実スキャン確定: MY_DATA直下4ファイルに危残存(`UM261小`=9, `UM261阪`=2, `UM262中`=5, `UM263京`=1、計17バイト)。**いずれもふくだ手動印と同一レコード内に同居**。

専用スクリプト `ml/ai_marks/cleanup_danger_slot1.py`:
1. 対象を**自動探索**(MY_DATA直下 `UM*.DAT` を走査し `0x8a 0xeb` を含むファイルを列挙)。会場名はバイトで判定(ファイル名の漢字が cp932 端末で化けるため、`glob`+バイナリ read で判定)。
2. 各対象を `{name}_bk_{timestamp}` にバックアップコピー。
3. **`0x8a 0xeb` を見つけた箇所だけ `0x20 0x20` に置換**。他バイトは**一切触らない**(record境界・改行・他印を保持)。
4. 差分検証: 置換前後で「危バイトの位置以外が完全一致」かつ「危バイトが0個になった」を assert。◎○▲△Ⅲ穴のバイト数が置換前後で不変であることも検証(手動印を巻き込んでいないことの証明)。
5. `--dry-run` 既定、`--apply` で実行。実行ログを JSONL に残す。

**絶対禁止**: `batchWriteHorseMarks(..., ops=全18頭クリア, markSet=1)` でのクリーンアップ。これは当該レコードの手動印も 0x2020 で消す(シズネ赤旗の核心)。

### 3.4 admin UI ラベル更新

`admin/page.tsx` L963 付近:
```
旧: '馬印2:VB / 馬印3:ARd / 馬印4:IDM / 馬印5:パドック印（7R以降）'
新: '馬印1:ふくだ手動 / 馬印2:VB / 馬印3:ARd / 馬印4:IDM / 馬印5:パドック / 馬印6:AI印(◎) / 馬印7:危印'
```
危印ボタンの label を「危→馬印7」に更新。AI印ボタン「AI印◎→馬印6」を新規追加。

### 3.5 markSet=1 施錠(auto系が手動スロットに書けないガード)

`target-mark-reader.ts` の `batchWriteHorseMarks` 冒頭に**実行時ガード**:
```ts
// auto系(危/vb/ard/idm/paddock/ai)が誤って手動スロットに書くのを防ぐ。
// 手動印 admin 経路は別フラグ allowManualSlot=true で明示的に解錠。
if (markSet === 1 && !allowManualSlot) {
  throw new Error('markSet=1 はふくだ手動印専用。auto系は markSet>=2 を使うこと');
}
```
- 第6引数 `allowManualSlot=false` を追加。手動印 `/api/target-marks`(VALID_MARKS バリデーション経路)だけ `true` を渡す。
- Python `dat_writer.py` にも同等 assert(`if mark_set == 1: raise`)。AI印は6固定、危は7固定。

---

## 4. シズネ赤旗の解消方針

| # | 赤旗 | 本設計での解消 |
|---|---|---|
| **R1** | danger-relocate: markSet=1 に危残骸が手動印と同居(全クリア厳禁) | §3.3 **厳密バイト置換スクリプト**(危バイトのみ→0x2020、_bk バックアップ、置換前後で手動印バイト数不変を assert)。`batchWriteHorseMarks` 全クリアは**禁止**と明記。markSet=7切替の**前提タスク**として先に実行 |
| **R2** | gap-based 即死: race_confidence 閾値が 0-100 と不一致 | **gap-based を主採用しない**(§0)。rank-based に確定。race_confidence は Step1 の撃ちなし判定に**使わない**。撃ちなしは composite分散(FLAT_EPS)=スケール非依存のデータ駆動判定に置換(§1.2 Step4) |
| **R3** | rank-based 擬似コードバグ(sort符号反転で◎最弱馬/dict比較常時True/threshold未定義) | 擬似コードは**破棄**。§1.2 の確定仕様で再実装。**符号バグ防止のため**: ユニットテストで「既知入力→◎=W/P/ADR最強馬」を固定(§5 SC-2)。dict比較・未定義閾値は仕様から排除(○以下を Step1 で書かないため該当コード自体が無い) |
| **R4** | ADR全欠レースで z 分母0→NaN汚染で◎不定(silent degradation) | §1.2 Step2 **明示処理**: ADR全欠/分散ゼロ→ADR成分除外+`adr_used=False`+`notes`に記録+**監査ログ出力**。W/Pも平坦なら撃ちなし。黙って続行しない(§9教訓準拠)。robust_z は MAD=0→std→0 のフォールバックで0除算も防止 |
| **R5** | 穴印が Themis逸脱(odds>6/popularity<3 で印を立てる) | §4-E。**Step1 では穴印を書かない**。穴は将来「印の格上げでなくEV配分の重み係数」。pros欄の自己矛盾(Themis準拠と穴ロジック)は穴を切ることで解消 |
| **R6** | 危 decode 非対称(write可/read不可) | §3.2 TS `MARK_BYTES_TO_SYMBOL` と Python `_MARK_BYTES_TO_SYMBOL` に `8aeb→危` 追加。round-trip テスト(§5 SC-6)で書けて読めることを担保 |

### 4.E 穴印の扱い(Themis原則)

- §7#4 / シズネ themis_check(A): 「穴は確率を持ち上げて◎扱いするな、信頼度の補正係数として扱え」。
- **Step1**: 穴印を**一切書かない**。markSet=6 には ◎ のみ。
- **将来Step**: 穴は「◎/○候補のうち高オッズで妙味のある馬に**信頼度係数**を付ける」=EV配分の重みであり、印スキーマでの独立印昇格ではない。odds/popularity を**印判定の直接材料にしない**(composite=確率+ADR で序列を決め、EV は配分側で扱う)。
- §9教訓: 無印は「単に無印」。AI印で「消」の概念は持ち込まない(`explicit_erase` は手動印 my_marks_v2 専用)。

### 4.Y イエローフラグ対応(Step1で潰すもの)

- **監査ログ必須**(§9.5): `data3/ai_marks/audit/{date}.jsonl` に「いつ・どのレースに・何を・どの weights で書いたか/撃ちなし理由」。危クリーンアップも別ログ。→「AI印がふくだ印を上書きしていないか」を後追い可能に(AI印は markSet=6 物理分離なので上書きは構造上起きないが、証跡は残す)。
- **書込み前バリデーション**: Python writer で `mark ∈ {'◎'}`(Step1)を assert。将来 ◎○▲△Ⅲ穴 に拡張時も VALID_MARKS 相当をチェック。typo 無検証書込みを防ぐ。
- **TARGET 表示確認**: UmaMark6 はサブフォルダ。ふくだの TARGET 画面で markSet=6 のDATが読まれ◎が見えるかを**実機で1回確認**(書けても表示されなければ無意味)。これは success criteria に含める(SC-7)。

---

## 5. 実装ステップ(順序付き・success criteria)

> 原則: danger クリーンアップ(過去汚染の根治)を**最初**に。AI印は純関数→writer→CLI→web の順でボトムアップ。各ステップは前ステップ完了が前提。

**SC-0(前提タスク・最優先): 危残骸クリーンアップ**
- `ml/ai_marks/cleanup_danger_slot1.py` 実装。`--dry-run` で対象4ファイル17バイトを検出表示。
- 完了条件: `--apply` 後、MY_DATA直下に `0x8a 0xeb` が0個 / 4ファイルの ◎○▲△Ⅲ穴 バイト数が置換前後で完全一致(手動印無傷) / `_bk` バックアップ存在 / 実行ログJSONL出力。

**SC-1: 危 decode 対応(TS+Python)**
- `8aeb→危` を両 reader に追加。
- 完了条件: テスト用 DAT に危を書き(既存 encode)、TS `getRaceMarks` と Python `load_danger_marks` 双方で「危」が返る(round-trip)。

**SC-2: 純関数 `assign_ai_marks` + ユニットテスト**
- §1.2 仕様で実装。
- 完了条件(test_ai_marks_assign.py):
  - 固定入力(W/P/ADR最強が一致する馬)→ `marks == {その馬: '◎'}`(**◎が最強馬=符号バグ無し**)。
  - 出走2頭 → `skipped=True, skip_reason='too_few_runners'`。
  - ADR全null(4R京都の実データ抜粋)→ `adr_used=False`, `notes` に縮退記録, W/Pで◎決定。
  - 全頭同スコア → `skipped=True, skip_reason='flat_distribution'`。
  - weights=(0.5,2,0.5) と (1,1,1) で composite が変わる(重み反映確認)。
  - 全 pass。

**SC-3: Python DAT writer + round-trip**
- `dat_writer.py`(markSet=6専用, mark_set=1 書込みは assert で拒否)。
- 完了条件(test_ai_marks_dat_writer.py): 一時 MY_DATA に◎を書込み→`load_my_marks(rid, mark_set=6)` で◎が返る / byte offset が TS `batchWriteHorseMarks` と一致(record_index・offset 計算の等価性) / mark_set=1 渡すと例外。

**SC-4: CLI `write_ai_marks` + 監査ログ**
- `python -m ml.ai_marks.write_ai_marks --date 2026-05-31 --dry-run`。
- 完了条件: 24R 全件の◎(or 撃ちなし理由)を表示 / `--dry-run` は DAT 不変 / 本実行で `data3/ai_marks/audit/2026-05-31.jsonl` に24行(weights/marks/skip_reason/adr_used/notes 含む)。4R京都が `adr_used=false` で記録される。

**SC-5: markSet=1 施錠ガード**
- TS `batchWriteHorseMarks` に `markSet===1 && !allowManualSlot → throw`、Python writer に同等 assert。手動印経路は `allowManualSlot=true`。
- 完了条件: auto系API(危/AI)が markSet=1 を渡すと失敗 / 手動印 admin は従来通り書ける(回帰なし)。

**SC-6: auto-danger スロット退避**
- route.ts MARK_SET 1→7、note・ラベル更新。
- 完了条件: auto-danger 実行→ markSet=7(UmaMark7/)に危が書かれ markSet=1 は不変 / `load_danger_marks(rid)` で危が読める / admin ラベルに「馬印6:AI印 / 馬印7:危印」表示。

**SC-7: web API + admin 導線 + TARGET実機確認**
- `/api/target-marks/ai-marks` 新設(Python起動)、admin にボタン追加。
- 完了条件: admin から AI印ボタン→ markSet=6 に◎書込み成功(HTTP200, summary 件数) / **ふくだの TARGET 画面で UmaMark6 の◎が表示される**ことを実機確認 / 危ボタンが markSet=7 に書く。

**SC-8(任意・後追い): ML特徴量化の素振り**
- `load_my_marks(rid, mark_set=6)` で◎をフラグ化できることを確認(将来 polaris 特徴量に `ai_honmei` 追加の足場)。Step1 では確認のみ。

---

## 6. ふくだに最終確認すべき点

1. **P成分は校正済 `pred_proba_p` を使う**(raw でなく)で良いか。W が `pred_proba_w_cal`(校正済)なので同空間の校正済Pで揃える設計にした。「複勝率は raw のほうが分離が良い」等の意図があれば変更する。
2. **Step1 は◎1頭のみ書く**で確定で良いか(○▲△Ⅲは Step2、穴は Themis 上 EV配分側へ)。
3. **撃ちなし基準**: 「出走<3頭」「W/P/ADR が全頭平坦」を撃ちなしにする。race_confidence(0-100)は backtest 未了のため Step1 の撃ちなし判定に**使わない**。これで良いか(信頼度ゲートを早期に入れたいなら、0-100スケールで閾値を決めて backtest してから追加)。
4. **危クリーンアップの実行タイミング**: 対象4ファイル(`UM261小/阪`, `UM262中`, `UM263京`)はバックアップを取って危バイトのみ除去する。これらに**いま付いている危印は不要(消して良い)**という理解で正しいか。過去の自分の危印を参照に残したい場合は、退避でなく markSet=7 に**移し替え**る別案にする。
5. **既定 weights は (1,1,1)** 固定で本番運用、P寄せ (0.5,2,0.5) は `--weights` 実験扱い(ROI walk-forward 裏取りまで本番にしない)。この規律で良いか。

---

---

## 7. Step2 実装 (○▲△Ⅲ 段差ベース + 穴 別系統) — Session 141 実装済

Step1(◎のみ)を踏襲し、`assign_ai_marks(..., step=2, enable_ana=False)` で拡張。設計は最小、判断はコードコメントに集約。

### 7.1 ○▲△Ⅲ = 段差ベース割当 (rank-based の自然な延長)
- composite 降順に `MARK_LADDER=("◎","○","▲","△","Ⅲ")` を順に割当。◎は composite 最高で常に付く。
- **打ち切り**: 2頭目以降は「前の馬との composite 段差 < `BREAK_GAP`(=1.0, z空間)」の間だけ続ける。段差が `BREAK_GAP` 以上開いた=ここで力が一段落ちる、と判断しそこで打ち切る。
- 思想: 僅差で続けば押さえ(○▲△Ⅲ)が増え、段差で切れれば◎単独に絞られる = ふくだの「迷ったら押さえ多い / 自信あれば絞る」を**段差が自動表現**。閾値は `BREAK_GAP` 1本(A/B可)。
- 上限は `MARK_LADDER` 長 = 5頭(◎○▲△Ⅲ)。打ち切り理由は notes に記録(監査)。
- 5/31 実データ素振り: 24R で ◎単独〜フル5頭、平均2.1印/R。1強型は◎単独、混戦はフル、自然に分かれた。

### 7.2 穴 = 別系統・突出判定 (Themis §4-E 整合)
- 序列印(◎○▲△Ⅲ)とは**完全に別系統**。`enable_ana=True`(CLI `--ana`)で明示有効化、既定 OFF=実験扱い。
- **乱発防止が肝**: `win_ev=勝率×odds` の構造特性で「win_ev>1 の高オッズ馬」はほぼ全レースに出る(5/31 検証で絶対閾値だと 22/24R)。絶対水準でなく**レース内で win_ev が突出しているか**で判定:
  - 序列印外 & `odds >= ANA_MIN_ODDS`(=6.0, 低人気=妙味の前提) の馬を穴候補とし win_ev 降順。
  - 候補1頭→そのまま穴 / 2頭以上→トップが2位より `ANA_BREAK`(=1.5, win_ev空間)以上高い時だけ穴。団子(僅差で複数)なら穴なし。
  - 最大 `ANA_MAX_COUNT`(=1)頭。「今日の穴はこのレース」を表現。
- **Themis整合**: odds/popularity を序列の直接材料にしない。穴は win_ev(確率起点)の突出フラグであり「確率を持ち上げて◎扱い」しない。odds下限は人気馬を穴と呼ばない最低条件として残す。
- 5/31 素振り: 突出判定で 22/24R → 12/24R に絞られた。

### 7.3 変更ファイル (Step1 から)
- `ml/ai_marks/assign.py`: `step`/`enable_ana` 引数、段差ベース割当、`_assign_ana()` 追加。`MARK_LADDER`/`BREAK_GAP`/`ANA_MIN_ODDS`/`ANA_BREAK`/`ANA_MAX_COUNT` 定数。
- `ml/ai_marks/dat_writer.py`: `VALID_AI_MARKS=("◎","○","▲","△","Ⅲ","穴")` に拡張(「消」は持ち込まない)。
- `ml/ai_marks/write_ai_marks.py`: `--step{1,2}`/`--ana` フラグ、複数印の序列順1行表示、印総数集計、audit に `step` 追記。
- `ml/tests/test_ai_marks_assign.py`: Step2 ケース 8件追加(段差割当/打ち切り/穴突出/団子で穴なし/人気馬除外/二重付与なし)。
- `ml/tests/test_ai_marks_dat_writer.py`: ◎○▲△Ⅲ穴 round-trip + 未知印拒否。
- テスト計 24件 全 pass。

### 7.4 Step2 残課題 (将来)
- **backtest 未了**: `BREAK_GAP`/`ANA_BREAK` の値は 5/31 1日の素振りで妥当に見えるだけ。複数開催で印数分布・的中率を walk-forward 検証して定数を確定する(Session140宿題⑤ と合流可)。
- **穴の前向き検証**: 突出判定の穴が実際に妙味だったか(回収率)を後追い。`is_value_bet`/`win_vb_gap` との相関も見る。
- web/admin 導線・TARGET実機表示は SC-7(Step1) の枠組みをそのまま流用。

---

関連ファイル(絶対パス):
- 実データ: `C:\KEIBA-CICD\data3\races\2026\05\31\predictions.json`(race_confidence 0-100, 4R京都 ADR全null 確認済)
- 既存読み: `C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\ml\features\my_marks.py`(`load_my_marks(rid, mark_set=6)` 流用 / `_MARK_BYTES_TO_SYMBOL` に危追加対象 L24-32)
- 既存書き: `C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\web\src\lib\data\target-mark-reader.ts`(`batchWriteHorseMarks` L306 / `MARK_BYTES_TO_SYMBOL` L16-24 に危追加 / `VALID_MARKS` L365)
- 修正対象: `C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\web\src\app\api\target-marks\auto-danger\route.ts`(MARK_SET 1→7 L15)
- 危残骸(クリーンアップ対象): `C:\TFJV\MY_DATA\` 直下4ファイル(危バイト計17箇所、手動印と同居)
- 新規パッケージ: `C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\ml\ai_marks\`(assign/dat_writer/write_ai_marks/audit_log/cleanup_danger_slot1)
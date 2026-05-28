# シズネレビュー: target_clicker (Session 127-128) — Session 129 着手前監査

> 作成日: 2026-05-24
> レビュアー: シズネ
> 対象: `keiba-v2/ml/target_clicker/{auto_vote,menu_runner,runner,ff_writer,__main__}.py` + `docs/auto-purchase/16_TARGET_AUTOCLICK.md`
> 背景: Session 127-128 で 4 件ライブ投票成功 (受付 0029/0030/0045/0046)、 うち新潟8R +8,300円 初的中。 Session 129 で TTS/ledger v2/起動自動化 に進む前に、 既存実装の安全性を棚卸し。
> Themis 原則: 確率×オッズ×bankroll でのみ意思決定。 馬名で動かない。

---

## TL;DR (結論)

**留保付き GO**。 4 件のライブ投票で実機検証済、 安全弁の方向性も悪くない。 ただし **「先に直せ」 が 3 件、 並行で直せが 5 件**。 Session 129 の TTS レイヤを乗せる前にこれだけ片付けてほしい。

最大のリスクは **per_race_max_yen が runner で見られていない** (シズネ自身が Session 126 で導入したのに使われてない) と **selective_bets.json の schema 検証ゼロ** (今日の的中は emerging_w_not_top2 で「市場と乖離する v2.0 戦略」 だが、 ファイルが腐ったら勝手に投票する経路が開いている) の 2 つ。

---

## 各観点の評価サマリ (🟢 8 / 🟡 7 / 🔴 3)

| # | 観点 | 評価 | 「先に直せ」? |
|---|---|---|---|
| A | デフォルト dry-run + --confirm 強制 | 🟢 | — |
| B | ダイアログタイトル/ボタンラベル完全一致 | 🟢 | — |
| C | 合計金額 / ベット数 / IPAT 残高 3 軸検証 | 🟢 | — |
| D | 受付番号抽出 + JSONL 監査 | 🟢 | — |
| E | menu_runner の 5 段 fallback の方向性 | 🟢 | — |
| F | ff_writer の validate() (race_id 16桁・amount % 100) | 🟢 | — |
| G | bankroll per_day_max_yen チェック (runner) | 🟢 | — |
| H | inspect-batch + save-coords による検証 SOP | 🟢 | — |
| I | **per_race_max_yen を runner が無視** | 🔴 | **先に直せ** |
| J | **selective_bets.json schema 検証ゼロ** | 🔴 | **先に直せ** |
| K | **JSONL 監査ログのアトミック性 (共通化されてない)** | 🔴 | **先に直せ** |
| L | bankroll 日次累計の考慮なし (per_day_max_yen は単発比較) | 🟡 | Session 129 後 |
| M | finalize_save_to_target 失敗時の TARGET 状態不整合 | 🟡 | Session 129 並行 |
| N | menu_runner 全戦略失敗時の沈黙 return False | 🟡 | Session 129 並行 (TTS と直結) |
| O | dialog_handle を JSONL に残す意味 (個人情報判定) | 🟡 | 並行 |
| P | raw_text 全文記録 (将来 PII リスク) | 🟡 | 並行 |
| Q | 連続投票 race condition (1 ダイアログ 1 click) | 🟡 | 後回し可 |
| R | TARGET セッション切れ時の振る舞い未検証 | 🟡 | 後回し可 |

---

## 「先に直せ」 詳細 (Session 129 TTS 着手前)

### 🔴 I. per_race_max_yen が runner で見られていない

**箇所**: `runner.py:152-164` `_read_bankroll_per_day_limit()` は `per_day_max_yen` だけ読む。 `194-203` のチェックも `per_day_max_yen` だけ。

**問題**: Session 126 で私 (シズネ) が導入した `per_race_max_yen=3000` (config.json:12) と `race_overrides` (PUT /api/bankroll/race-override/[raceId] で reason 必須にしたやつ) を runner が一切参照していない。 selective_bets.json から複数レースを一括投票するときに、 1 レースに偏った場合の防御がない。

実例: 今日 (0046) は ワイド1-3 + 1-10 + 単勝1 を 1 レースに 1,000円 で済んでいるが、 将来 `--amount 1000` で 3 ベット同一レース = 3,000円ピッタリ、 1 件でも overrides 設定があると `per_race_max_yen` を超えて投票してしまう。

**修正方針**:

1. `runner.py:115-138` `load_bets_from_args()` 後に `bets[].race_id` で groupby → レースごと合計を計算
2. `_read_bankroll_per_day_limit()` を拡張して `(per_day_max_yen, per_race_max_yen, race_overrides)` の 3 つを返す `_read_bankroll_limits()` に
3. レースごと合計 > `race_overrides[race_id]` or `per_race_max_yen` なら abort
4. `--no-bankroll-check` の警告メッセージに「per_race_max_yen も skip される」 と明示

**所要**: 30-40 分。 Session 129 で `bankroll/limit-resolver.ts` の Python ポート (`ml/utils/bankroll_limit.py`) を作って共通化するのが筋。 TS 側と SoT 不一致が始まる前に。

---

### 🔴 J. selective_bets.json schema 検証ゼロ

**箇所**: `runner.py:127-138`

```python
for jp in json_paths:
    with open(jp, encoding="utf-8") as f:
        data = json.load(f)
    for b in data.get("bets", []):
        bets.append(FfBet(
            race_id=str(b["race_id"]),
            bet_type=BET_TYPE_CODE["tansho"],
            umaban=int(b["umaban"]),
            amount=args.amount,
        ))
```

**問題**:
- version チェックなし (selective.py 側は `"version": "2.0"` を書いているが runner は読まない)
- generated_at の鮮度チェックなし (3 日前の selective_bets.json を間違えて --from-date 2026-05-21 で叩いたら投票されちゃう)
- strategy チェックなし (将来 `strategy: "experimental"` 等が混入したときに弾けない)
- source チェックなし (`emerging_w_not_top2` `top_p` 以外の知らない source が来ても投票)
- 全 bets が **無条件 tansho 扱い** (BET_TYPE_CODE["tansho"] 固定)。 将来 selective が複勝/ワイドを返したら全部単勝として誤投票

「市場と乖離するシグナルこそ収益源」 (Session 122) の OOS サンプルがやっと採れ始めたいま、 schema 不整合で勝手に投票して的中分を吐き出すのは最悪のシナリオ。

**修正方針**:

1. `ml/target_clicker/selective_loader.py` を新設 (40-60 行):
   - `version in {"2.0"}` 強制
   - `generated_at` を parse して `now - generated_at > 24h` なら警告 (--allow-stale でのみ通す)
   - `source in {"top_p", "emerging_w_not_top2"}` whitelist
   - bet ごと `race_id` 16桁 isdigit、 `umaban` 1-18、 `odds > 1.0` を assert
   - 返り値は明示 `list[SelectiveBetTyped]`
2. `runner.py:127-138` をこのローダー呼出に置換
3. selective_bets.json が壊れていたら **abort** (warn ではなく)
4. `--allow-experimental-source` で whitelist 解除可能に (検証用)

**所要**: 40 分。 受付 0045 で +8,300円勝てたファイルが selective v2.0 emerging_w_not_top2 だから、 ここの schema を固めることは「儲かった経路を保護する」 ことそのもの。

---

### 🔴 K. JSONL 監査ログのアトミック性 (共通化されてない)

**箇所**: `auto_vote.py:410-439` `_audit()` — `with open(log_path, "a", ...) f.write(...)` の単純 append、 fsync なし、 ロックなし

**問題**:

Session 125-126 で TS 側は `lib/io/atomic-write.ts` を共通化済 (my_marks_v2 + bankroll が SoT 共有)。 私 (シズネ) が「同じ穴を 2 回開けない」 原則を Session 126 で明示したのに、 Session 127-128 で Python 側に **3 つ目の穴** が開いた:

1. **OS クラッシュ時の行欠損リスク**: Python `f.write()` は OS バッファに乗るだけ。 IPAT 投票終了直後にブルスクで 受付番号 行が消える = 税務 7 年保存要件違反 (14_LEDGER_SCHEMA.md)
2. **部分行混入**: 改行を最後に書く設計 (`+ "\n"`) なので途中で落ちると改行なしの不完全 JSON 行が残る。 次回 jsonl パーサーが死ぬ
3. **並列実行未保護**: 現状は 1 ユーザー手動なので問題出ていないが、 Session 129 で TTS 通知から「Toast click → 投票照会更新」 系を入れたら同時 append の可能性

**ただし注意**: append-only の JSONL を「writeAtomic (tmp → rename)」 すると **既存ログが全消えになる**。 tmp に全部書き直してから rename だと、 既存 N 行 + 新 1 行 = N+1 行を毎回フル書き出しになる。 これは現実的でない (10MB の audit ファイルに毎回フル書き)。

**修正方針 (JSONL 用の別パターン)**:

`ml/utils/jsonl_append.py` (新設、 50 行):

```python
def append_jsonl_atomic(path: Path, entry: dict, *, lock_timeout_ms=5000):
    """JSONL 1 行追記。 ファイルロック + fsync + 全行改行終端保証。"""
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    data = line.encode("utf-8")
    with _file_lock(path, timeout_ms=lock_timeout_ms):
        # 既存末尾が \n で終わってなければ \n を先に挿入 (前回欠損対策)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
```

ロック実装は TS 側 `withFileLock` の mkdir-based パターンを Python 移植 (`{path}.lock` ディレクトリ作成)。

これを `auto_vote._audit()` (line 434-435) と将来の ledger v2 writer で共用。

**所要**: 60 分。 Session 129 ledger v2 配線でも同じ穴を絶対開けないために、 今やる価値が極めて高い。

---

## 並行 / Session 129 と一緒に直す系

### 🟡 L. bankroll 日次累計の考慮なし

**箇所**: `runner.py:194-203`

per_day_max_yen=10,000 のところ、 1 回の runner 実行で 1,000円 投票 → 5 回繰り返したら計 5,000円 だが、 各回が独立に「1,000 ≤ 10,000」 で通る。 累計が見えない。

**修正**: `data3/userdata/bankroll/history/YYYYMMDD.jsonl` から当日合計を読んで `total_today + planned_total > per_day_max_yen` で abort。 Session 129 で ledger v2 配線するときに同時実装が筋 (ledger 側でも累計が必要)。

### 🟡 M. finalize_save_to_target 失敗時の TARGET 状態不整合

**箇所**: `runner.py:258-265`

投票成功 → `finalize_save_to_target()` 失敗 = IPAT には投票済だが TARGET の買い目データには未保存。 翌日「投票したつもりの買い目」 を TARGET で振り返れない。 audit JSONL には載るが、 ふくだ視点では認知不一致。

**修正**: 失敗時に audit JSONL に `finalize_failed: true` フラグを追記 + Session 129 の TTS でこの失敗を **音声警告** (「保存に失敗しました、TARGET で手動で F10 押してください」)。

### 🟡 N. menu_runner 全戦略失敗時の沈黙 return False

**箇所**: `menu_runner.py:852-853` `step3_start_ipat` 全 5 戦略失敗で `_vp(verbose, "IPAT 投票起動: 全戦略失敗")` の後 `return False`、 runner 側は exit code 4 で死ぬだけ。

シズネ視点: IPAT 起動失敗は **物理 GUI 操作の致命的な失敗** = 「投票したつもりが起動すらしてない」 のと「起動はしたが click 失敗」 が区別できない。 これは TTS で「IPAT 起動に失敗しました、 ふくだ介入が必要です」 と **音声警告 + デスクトップ通知** が必須。

**修正**: Session 129 TTS 実装と一緒に。 `runner.py:225-229` で `step3_start_ipat False` 時に notify レイヤ呼び出し。

### 🟡 O. dialog_handle を JSONL に残す意味 (個人情報か)

**箇所**: `auto_vote.py:331, 422`

handle は OS の HWND (整数)。 監査価値ゼロ (再起動で値変わる)。 個人情報ではないが「無価値情報を記録する」 は監査ログの S/N 比を下げる。

**修正**: スキーマ v1.1 (Session 129 で audit 形式に version 入れるタイミングで一緒に) で削除。 もしくは debug=True のときだけ記録。

### 🟡 P. raw_text 全文記録 (将来 PII リスク)

**箇所**: `auto_vote.py:426, 431`

現状 raw_text に「投票ベット数: N | 合計金額 | ...」 等しか出てないので OK。 但し将来 TARGET バージョンで「IPAT ユーザーID」 や「セッション ID」 がダイアログに表示されると、 そのまま JSONL に流れ込む。 7 年保存だから不可逆。

**修正**: `_audit()` 前に正規表現でセンシティブパターン (英数字10桁以上、 セッション系キーワード) を `[REDACTED]` 化する filter を入れる。 Session 130 以降で十分。

---

## 後回しでも可

### 🟡 Q. 連続投票 race condition

`auto_vote.click_vote_button()` は 1 ダイアログ 1 click。 selective 7 件を 7 レース連続投票するとき、 ふくだが TARGET 側で「次のレース IPAT 起動」 を手動で 7 回やる必要。 runner 自動化前提が崩れる。 **Session 130 で「連続投票モード」 実装、 各レースごとに menu_runner.step1-3 + click を回す。** 今はOK。

### 🟡 R. TARGET セッション切れ時の振る舞い未検証

IPAT 認証が切れたら TARGET が再ログインダイアログを出す。 これは title 完全一致 (`投票内容確認`) と違うので auto_vote は timeout で死ぬ = 安全側。 だが「なぜ timeout したか」 が分からない。 **TTS 実装時に「投票ダイアログ未検出」 を音声化** すれば判明する。 Session 129 でカバー可。

---

## 良かったところ (🟢 詳細)

### A. デフォルト dry-run (`__main__.py:26-27`, `runner.py:84-85`)

`--confirm` 必須は完璧。 `--dry-run` を no-op として明示受付しているのも丁寧。 シズネ原則「人間の明示意思」 を担保。

### B. ダイアログタイトル / ボタンラベル完全一致 (`auto_vote.py:46-52`)

`投票内容確認` `投票` `投票終了` `OK` の 4 つだけ反応。 「キャンセル」 を誤押下する経路がない。 **将来 TARGET バージョン更新でタイトル変わったら 即 timeout = 安全側に倒れる**。 これは sopha (smart fail-safe) と呼べる設計。

### C. 3 軸検証 (`auto_vote.py:341-364`)

- 合計金額 0 → reject (抽出失敗時の安全側)
- 合計金額 > max_yen → reject
- ベット数 > max_bets → reject
- 合計 > IPAT 残高 → reject (二重防御)

順序も正しい。 0 円バグを最初に弾く。

### D. 受付番号抽出 + JSONL 監査 (`auto_vote.py:225-263`)

`受付番号 : 0045` の半角/全角コロン両対応 (`_RECEIPT_NO_RE`)。 受付番号は JRA 公式 ID なので税務上の証跡として最強。 14_LEDGER_SCHEMA.md v1.1 と整合させやすい。

### E. menu_runner 5 段 fallback (`menu_runner.py:826-853`)

戦略順 `["menu", "uia", "win32", "shortcut", "coords"]` の優先順位は Session 128 実測 (受付 0045) で確定済。 menu 戦略 (WM_COMMAND id=1601 動的解決) が最速・最安全。 coords は最終手段で window size 検証付き (`menu_runner.py:759-763`)、 これも筋がいい。

### F. ff_writer.validate() (`ff_writer.py:70-86`)

`race_id` 16桁 isdigit、 `bet_type` 列挙、 `umaban` 1-18、 `amount >= 100 && %100 == 0` の 4 検証。 これだけで「不正な FF CSV を TARGET に投入する事故」 はほぼ無い。

### G. bankroll per_day_max_yen チェック (`runner.py:152-203`)

`limit_mode == "absolute"` のときだけ反応する exclusive な設計。 `--no-bankroll-check` での skip も明示警告付き (`"本当に妥当か確認のこと"`)。 シズネ Session 126 設計と整合。 ただし → I & L が残課題。

### H. inspect-batch + save-coords による検証 SOP (`menu_runner.py:112-316`)

Win32+UIA dual dump + メニュー dump + スクショ + IPAT 候補抽出 + JSON 保存 + コンソール出力 (簡潔)。 これは 「次の不具合時に1発で攻略情報を集める」 ためのインフラとして極めて優秀。 設計書 16_TARGET_AUTOCLICK.md §10.3 の SOP も再現可能性が高い。 Session 129 以降で TTS の不具合検証にも応用可。

---

## Session 127 残 must-fix 4 件の再確認

| # | 指摘 | 現状 | コメント |
|---|---|---|---|
| ① writeAtomic Windows非アトミック+fsync無し | Session 126 で `lib/io/atomic-write.ts` 共通化済 (TS 側) | 🟢 TS 側解決済。 但し Python 側 (auto_vote._audit) には適用されてない → 観点 K で再指摘 |
| ② ファイルロック無し | TS 側 withFileLock 適用済 | 🟢 TS 側解決済。 Python は K で共通化提案 |
| ③ ★→Ⅲ 残骸 | Session 125 内で 18 ファイル一括置換済 | 🟢 解決済 (本レビューでは grep 不要、 target_clicker は印を扱わない) |
| ④ DAT 書込み成功+v2 失敗の rollback 無し | Session 125 で TargetMarkInputModal に rollback 実装済 | 🟢 解決済 |

→ TS 側は片付いた。 **Python 側 (target_clicker) で 1 件 (観点 K) が残課題**。

---

## Session 129 着手順序の提案

シズネ視点で順序を組むと:

```
[ Session 129 開始 ]
   ↓
1. (40分) 観点 J: selective_loader.py 新設 + runner.py 配線
   - 一番ふくだの「儲かる経路」 を守る。 schema 不整合での誤投票防止。
   ↓
2. (30-40分) 観点 I: runner に per_race_max_yen チェック追加
   - レースごと groupby + race_overrides 参照
   ↓
3. (60分) 観点 K: ml/utils/jsonl_append.py 新設 + auto_vote._audit 置換
   - ここで JSONL の安全性確立 → ledger v2 が乗っかる土台が完成
   ↓
4. (90-120分) TTS 通知レイヤ実装 ★Session 129 のメインタスク
   - 観点 M (finalize失敗時) + 観点 N (IPAT起動失敗) も同時にカバー
   ↓
5. (60分) ledger v2 配線
   - jsonl_append.py を使うので K がここで効く
   ↓
6. (Session 130) TARGET 起動自動化 + 観点 Q (連続投票)
```

**所要見積**: Session 129 中に 1-5 まで全部入る (合計 4-5 時間)。 もし時間がなければ TTS 前に **1+2+3 を最低限** やってほしい (約 2 時間)。 これだけで 「お金が消える経路」 と「監査ログ欠損」 の両方が塞がる。

---

## ふくだ君に確認したい論点

1. **schema 検証で abort vs warn**: selective_bets.json が壊れていたら **abort** で良いか? warn だけにして「いま動いてる経路を止めない」 派もあり得る (シズネは abort 推奨)
2. **bankroll 累計考慮の起点**: 日次累計は (a) `audit_2026-05.jsonl` 自体から計算するか、 (b) `bankroll/history/YYYYMMDD.jsonl` を別途持つか。 ledger v2 配線と直結
3. **TTS 警告の優先順位**: 観点 N (IPAT 起動失敗) と 観点 M (finalize 失敗) の音声テンプレート文言は、 「ふくだの介入が必要です」 「TARGET で F10 を押してください」 等を Session 129 でカカシ・ふくだで決めてほしい。 シズネは「事務的・短文・繰り返さない」 派

---

> 「お金が消える経路を最初に探す」 が私の仕事。 4 件のライブ投票で 1 件 9.3 倍が刺さったタイミングは、 浮かれずに **守りを固めるべき瞬間** です。 観点 I/J/K の 3 つを Session 129 着手前に必ず。 — シズネ

# シズネレビュー: Session 132 Phase 4-C-full

> **対象**: 18_TARGET_FULL_AUTOMATION.md §1.3 Phase 4-C-full (TARGET 再起動なしの IPAT セッション復旧)
> **実装**: launcher.py / auto_vote.py / runner.py / notify.py / writer.py / test_launcher_recovery.py
> **レビュー日**: 2026-05-24 (Session 132)
> **観点**: A. お金経路の安全性 / B. ふくだのギャンブル本能ブレーキ / C. 検知精度 / D. 冪等性 / E. 見落とし / F. success criteria 網羅性 (Karpathy)
> **総合判定**: **条件付き GO (来週末 OOS 検証実施可)**。 🔴 1 件 (CLI 二重投票誘発) を OOS 前に対応推奨、 🟡 8 件は OOS 後 / Session 133+ で対応可。

---

## 0. 結論 (3 行)

1. お金経路の構造設計は妥当 — 「自動リトライしない / 投票 click 後の検知は manual_review に倒す / 復旧は CLI で人手 1 アクション」 の 3 点で「便利すぎる流れ」 を意図的に作らなかった判断は **強く支持**。
2. 「先に直せ」 級は **1 件**: `recover-session` CLI が `auto_vote` ループ無し単独実行のため、 ふくだが「あれ、 復旧コマンド打ったらまた投票も走る?」 と思って `runner.py --confirm` に走ると **同じ bets を二重投票するリスク** が残る。 文書 + CLI ガード両面で潰したい (詳細 §1 🔴-1)。
3. success criteria 5 項目は **網羅的だが Karpathy 観点で 1 つ追加推奨** — 「**verify loop**: 検出から ledger event 着地までの end-to-end が実機 OOS で 1 件以上観測されること」 を 6 項目目として追加。

---

## 1. 「先に直せ」 級 (🔴) — OOS 検証前に対応推奨

### 🔴-1 `recover-session` CLI 単独実行 → 二重投票誘発リスク

**問題**:
- `launcher.py:1289-1356` の `recover-session` CLI は復旧成功で exit 0 を返すだけ。
- 復旧成功後の運用は**設計書 §1.3 範囲外 「自動リトライしない」** の前提に従って `runner.py --auto-launch` を **再実行しない** ことになっているが、 ふくだ視点で「復旧成功 → よし続きの投票へ」 と感じて `selective_vote.bat 2026-05-31 100 --confirm` を**再実行する誘惑**が残る。
- 同じ `selective_bets.json` を再投与すると、 該当 race の bets[] が再展開される。 idempotency_key (`writer.py:240-245`) は同一 portfolio/ticket を重複検出して `action="duplicate"` で skip するが、 これは **ledger 記録の話**。 IPAT 側の投票自体は `auto_vote.click_vote_button` が新規 click を行う。 受付不明の race (vote_already_clicked=True 経路) に対して TARGET の「投票内容確認」 が二度立ち上がれば、 二度目を承認すれば二重投票になる。
- 特に `result_dialog_timeout` 経路 (= 投票 click 済だが「投票終了」 が出なかった、 受付不明) で復旧した場合、 IPAT 側に投票が成立していたかどうかが分からないまま **同じ買い目を再投与する** ことは構造的に防がれていない。

**現在の防御層**:
- `runner.py:539-551` で `result.session_expired=True` のとき exit 5 で abort する (= **同じ runner.py 実行内**は再投票しない) ✅
- ledger event `IPAT_SESSION_EXPIRED_POSTVOTE` payload に `manual_review_required=True` 記録 (`writer.py:497`) ✅
- runner.py が `vprint("→ 復旧する場合は: python -m ml.target_clicker.launcher recover-session")` を案内 (`runner.py:548`) ✅
- 投票内容確認ダイアログでの max_yen / max_bets 検証 (`auto_vote.py:377-394`) ✅

**抜けている層**:
- **`runner.py --auto-launch` 再実行時に「直近の IPAT_SESSION_EXPIRED_POSTVOTE event があれば確認プロンプト」** 機構がない
- **`recover-session` 成功後の「次の一手」 を文書 + 音声で明示** していない (今は `notify_ipat_session_recovery_succeeded` が「投票を継続します」 と言うが、 ここで言う「継続」 は何の継続なのか不明確 = ふくだは「あ、 selective_vote.bat 続き走らせていいんだ」 と解釈する可能性大)

**修正案 (OOS 前に対応推奨)**:

修正 A. **音声文面の明確化** (即対応・5 分): `notify.py:486-506` の `notify_ipat_session_recovery_succeeded` を以下に変更:

```python
# 旧
text = "IPAT セッションの再認証に成功しました。 投票を継続します。"

# 新
text = (
    "IPAT セッションの再認証に成功しました。 "
    "ただし、 前回検知した未投票分の自動再送はしません。 "
    "再投票が必要なレースは ledger を確認した上で、 必要なら手動で投票してください。"
)
```

修正 B. **`runner.py --auto-launch` の起動時チェック追加** (中規模・30 分): 直近 1 時間以内の `IPAT_SESSION_EXPIRED_POSTVOTE` event (= `vote_already_clicked=True` 含む) が events_jsonl にあれば、 起動時に音声 + stderr で警告し、 `--ignore-recent-session-expired` 明示が無ければ exit する。 これでふくだが何も考えずに `selective_vote.bat` を再叩きしても止まる。

修正 C. **設計書 §1.3 「範囲外」 セクションに明示追加** (即対応・3 分):
```
- 復旧成功後の自動継続: recover-session で復旧しても、 検知時点で投票
  キューに残っていた bets[] の自動再送は **しない**。 ふくだは ledger event
  (IPAT_SESSION_EXPIRED_POSTVOTE) と IPAT 履歴を照合した上で、 必要分を
  手動で `--bet ...` を組んで再投票する。
```

**判定**: A + C は OOS 検証前 (来週末まで) に対応推奨。 B は OOS で発生頻度を見てから判断 (空振りすると毎回煩い)。

---

## 2. 「将来 OK」 級 (🟡) — OOS 後 / Session 133+ で対応

### 🟡-2 `vote_already_clicked` 判定が phase 名固定値で fragile

`auto_vote.py:529` で:
```python
vote_already_clicked=(result.session_expired_phase == "result_dialog_timeout"),
```

これは文字列リテラル比較。 タイポすれば常に False になり、 manual_review_required も False に流れる。

**対応案**: `auto_vote.py` 冒頭に enum or 定数化:
```python
SESSION_EXPIRED_PHASE_VOTE_DIALOG_TIMEOUT = "vote_dialog_timeout"
SESSION_EXPIRED_PHASE_RESULT_DIALOG_TIMEOUT = "result_dialog_timeout"  # vote click 済
SESSION_EXPIRED_PHASE_EXPLICIT_ERROR_DIALOG = "explicit_error_dialog"
VOTE_ALREADY_CLICKED_PHASES = {SESSION_EXPIRED_PHASE_RESULT_DIALOG_TIMEOUT}
```

そして `auto_vote.py:529` を `result.session_expired_phase in VOTE_ALREADY_CLICKED_PHASES` に変更。 testable + 拡張性も上がる。

**判定**: Session 133 で対応 (Karpathy 観点でも「数日後の自分がタイポして気づけない」 構造リスク = 早めに潰すべき)。

### 🟡-3 `explicit_error_dialog` phase が auto_vote 経路から呼び出されない

設計書 §1.3 検知パターン表で `explicit_error_dialog` は「dialog title regex で検知」 と書かれているが、 実装上 `auto_vote.py` で `_attach_session_expired_info` を呼ぶのは:
1. `find_vote_dialog` timeout 時 → phase=`vote_dialog_timeout`
2. `close_result_dialog` の closed=False or receipt=None 時 → phase=`result_dialog_timeout`

の 2 経路だけ。 投票ダイアログ表示中に脇からセッション切れ dialog が湧くケース (= explicit_error_dialog) は **どこからも検知しない**。 `runner.py` レベルでも poll してない。

**実害**: 検知パターン①②でセッション切れの大半は拾える (`detect_session_expired_dialog` を呼ぶので)。 ただし「投票内容確認ダイアログ表示中に突然セッション切れ警告が割り込んだ」 ケースは見逃す (確率低そうだが OOS で確認したい)。

**対応案**: Session 133+ で `auto_vote.click_vote_button` 内に「click 前にも一度 `detect_session_expired_dialog` を呼ぶ」 を追加。 もしくは、 Phase 4-D で「runner.py の各 step 前後に poll」 を考えてもよい。

**判定**: 来週末 OOS で発生頻度を見てから判断。

### 🟡-4 `_audit` の TTS と ledger 記録の順序が「TTS 先 → ledger 後」 で誤読リスク

`auto_vote.py:498-535` の `_audit` 内処理順序:
1. TTS (`notify_ipat_session_recovery_attempted` 等) を **先に** 発話
2. ledger event を **後で** 記録
3. audit JSONL を **最後に** 追記

これは設計判断としては「音声を最速で出す = ふくだに早く気づかせる」 という思想で妥当。 ただし、 ledger 書込みで Exception が出た場合、 TTS は「復旧試みます」 と言ったのに ledger には何も残らない、 という乖離が起こりうる。

**対応案**:
- (案 i) TTS 文面に「ledger に記録しました」 を入れるのを **やめる** (現状そうなっていないので OK)
- (案 ii) ledger 失敗時に追加の音声 (「ledger 記録失敗、 手動メモを残してください」) を出す
- (案 iii) 現状維持: TTS は best-effort、 ledger 失敗は stderr に出すのみ (Session 129 の `notify` hook 失敗時の方針と同じ)

→ (案 iii) でよい。 ただし `writer.py:587` の print(stderr) で済ませている部分について「ledger 失敗時にも音声」 にするかは Session 133+ で検討。

**判定**: 現状のままで OK だが、 OOS で ledger 失敗が出たら案 ii を検討。

### 🟡-5 `session_expired_patterns.json` v2 スキーマで `verified_by` / `target_version` 必須化が CI レベルで強制されていない

設計書 §1.3 では「verified_by/target_version 必須」 と書かれているが、 `load_session_expired_patterns` (`launcher.py:971-996`) では **dict 形式なら patterns[] さえあれば受け入れる**。 verified_by が無くてもエラーにならない。

これは whitelist v2 (`load_dialog_whitelist_v2`) も同じ問題 (verified_by 必須でない) があるので、 一貫して「**verified_by 必須化** + 無いなら起動時 warning」 を Session 133 で入れる。

**対応案**:
```python
if isinstance(data, dict):
    patterns = data.get("patterns", [])
    if not data.get("verified_by"):
        print(f"[launcher] WARNING: session_expired_patterns.json に verified_by 必須 "
              f"(JSON 内容の責任所在を明示してください)", file=sys.stderr)
    ...
```

**判定**: Session 133 で whitelist v2 と同時に対応。

### 🟡-6 `_read_dialog_body` の `max_descendants=50` が IPAT エラー dialog の body 全部読めない可能性

`launcher.py:999-1014`:
```python
def _read_dialog_body(window, max_descendants: int = 50) -> str:
```

IPAT の Web View 内 (TWebBrowser 子コントロール) を dump すると 50 を簡単に超える可能性。 セッション切れ dialog の本文が body_keywords にマッチしない原因になる。

**対応案**:
- 上限を 200 に上げる (実害なし)
- そもそも body keywords でなく title + button 構造で判定する pattern を JSON に追加可能にする

**判定**: 来週末 OOS で `inspect-launch` の dump を見てから判断。 仮に 50 件で取りこぼしているなら OOS 当日にパラメータ調整。

### 🟡-7 ledger event 6 種が 14_LEDGER_SCHEMA.md に未反映

シズネ Session 130/131 🟡 F (積み残し) と同じ事象が **6 種に増えた** 状態。 14_LEDGER_SCHEMA.md を grep しても以下が未記載:
- `IPAT_SESSION_EXPIRED` (Session 131 / pre-flight)
- `IPAT_SESSION_EXPIRED_POSTVOTE` (Session 132 NEW)
- `IPAT_SESSION_RECOVERED` (Session 132 NEW)
- `IPAT_SESSION_RECOVERY_FAILED` (Session 132 NEW)
- `IPAT_START_FAILED` (Session 130)
- `TARGET_SAVE_FAILED` (Session 130)
- `TARGET_DIALOG_UNKNOWN` (Session 131)
- `VOTE_FAILED` (Session 129)

実装側だけ進んでスキーマ文書が追いついていない = 後から「この event 何だっけ」 が増える。

**対応案**: Session 133 冒頭で 14 を一括更新。 event 表に 8 種追加 + 各 payload の必須 field をスキーマ化。

**判定**: Session 133 必須対応。

### 🟡-8 `recover_ipat_session` の Step 2 (open_ipat_menu) でセッション切れ dialog が **閉じる前に** menu 起動を試みる順序の不安

`launcher.py:1163-1184` の Step 1 → Step 2 順序:
- Step 1: `_close_session_expired_dialog(info)` が `info.handle` で connect して click
- Step 2: `open_ipat_menu` が TARGET window の focus を奪って menu 起動

Step 1 で dialog 閉じた直後、 IPAT の error dialog の **後ろに** さらにモーダル dialog が積まれている可能性 (たとえば「ログアウトしました」 + 後ろに「ログイン画面に戻ります」 の 2 段)。 1 つ閉じただけで安全と言えるか?

**対応案**: Step 1 を「`_close_session_expired_dialog` を最大 3 回試行 (= 多段モーダル対応)」 に拡張。 もしくは `auto_dismiss_dialogs` を再利用してもよい。

**判定**: 来週末 OOS で「セッション切れ時の dialog 構造」 を inspect-launch で確認。 1 段なら現状で OK、 2 段以上なら修正。

### 🟡-9 復旧中に新規 `IPAT_SESSION_EXPIRED_POSTVOTE` を二度検知して event 重複

質問の D 「冪等性」 の論点と同じ。 `recover_ipat_session` 内で何らかの理由で Step 5 (precheck) が失敗 → `runner.py` 側で再度同じ event が走る可能性。

ただし、 実装上は `recover_ipat_session` の各 step は ledger event を **記録しない** (POSTVOTE event は `auto_vote._audit` の経路でのみ記録、 RECOVERED/FAILED は呼び出し側 = runner.py が記録する想定だが、 **現在 runner.py に配線がない** — これは見落とし、 🟡-10 参照)。

**判定**: 重複の心配は薄い。 ただし 🟡-10 と合わせて整備。

### 🟡-10 `record_ipat_session_recovered` / `record_ipat_session_recovery_failed` が **どこからも呼ばれていない**

writer.py に関数定義はある (`writer.py:504-552`) が、 `runner.py` / `launcher.py` / `auto_vote.py` から検索しても呼び出し箇所がゼロ。 つまり Session 132 の実装で `recover_ipat_session()` を **CLI 単独実行した場合、 復旧結果 event が ledger に残らない**。

CLI 実行時のロジック (`launcher.py:1344-1356`):
```python
elif args.cmd == "recover-session":
    info = detect_session_expired_dialog()
    r = recover_ipat_session(...)
    print(...)
    sys.exit(0 if r.success else 1)
```

→ exit するだけで `record_ipat_session_recovered` を呼ばない。

**対応案**: `launcher.py` の CLI ハンドラに ledger 記録を追加:
```python
elif args.cmd == "recover-session":
    info = detect_session_expired_dialog()
    r = recover_ipat_session(...)
    try:
        from ml.purchase_ledger.writer import (
            record_ipat_session_recovered, record_ipat_session_recovery_failed,
        )
        race_id = ""  # CLI なので不明、 空で events_jsonl のみ
        if r.success:
            record_ipat_session_recovered(
                race_id=race_id, elapsed_sec=r.elapsed_sec or 0.0,
                steps_completed=r.steps_completed,
            )
        else:
            record_ipat_session_recovery_failed(
                race_id=race_id, failure_action=r.action, reason=r.reason,
                elapsed_sec=r.elapsed_sec, steps_completed=r.steps_completed,
            )
    except Exception as e:
        print(f"[ledger] 記録失敗: {e}", file=sys.stderr)
    sys.exit(0 if r.success else 1)
```

**判定**: 「先に直せ」 級か悩んだが、 「audit 記録の欠落」 は事後追跡不能だけで二重投票には繋がらないので 🟡 にとどめた。 ただし Session 133 で必ず対応 (= 「ledger は監査の根拠」 原則 / [[shizune-agent]])。

---

## 3. 「これは良い」 級 (🟢) — このまま OOS 検証 OK

### 🟢-A 「自動リトライ無し」 を runner.py の return 5 + 文書範囲外宣言の二重で実装

`runner.py:539-551` + 設計書 §1.3 範囲外 + CLI 案内 (`recover-session` を打つよう促す) の 3 重で「自動継続を構造的に潰した」 のは [[feedback_betting_philosophy]] と整合し、 シズネ原則「お金経路の最終認証は人」 を貫いている。 特に `result_dialog_timeout` で `vote_already_clicked=True` フラグを ledger に焼き込む処理 (`writer.py:497`) は「rollback 不能を人に正しく戻す」 原則の良い実装例。

### 🟢-B 暗証番号自動化禁止が Phase 4-C-full にも継承されている

`recover_ipat_session` の Step 4 で「ふくだ手動 + `notify_ipat_login_required`」 を呼ぶだけ、 暗証番号入力を **絶対にしない** 構造 (`launcher.py:1202-1210`)。 既存 `test_launcher_no_password.py` の AST 検査が新規追加コードにも効いている (recovery 関数は keyring/getpass/pyperclip 未使用)。 二重認証ゲートも復旧経路で再発火する設計判断は妥当 (= ふくだは復旧時にも一度暗証番号入力 = 「これで本当に再開していいか」 の意思確認になる)。

### 🟢-C `session_expired_patterns.json` を JSON override 可能 + default フォールバック

実機検証前は default で動作、 OOS で確定後は JSON 上書きで漸進更新可能 (`launcher.py:971-996`)。 同じパターンが whitelist v2 で確立済 = 学習コストゼロ。 ただし 🟡-5 (verified_by 必須化) は対応推奨。

### 🟢-D テスト 23 件 + 既存 14 件で 37 件 PASS

`test_launcher_recovery.py` 23 件で:
- `load_session_expired_patterns`: 5 件 (file 不在 / list / dict / 破損 / default 健全性)
- `detect_session_expired_dialog`: 8 件 (Desktop().windows() mock 化済、 TARGET メイン除外 / title + body 両方マッチ / body 不一致 / title 不一致 / カスタム pattern title only / pattern_source / 不可視 window skip)
- `recover_ipat_session`: 8 件 (全 step 成功 / expired_info なしで dialog_close skip / 各 step 失敗パターン)
- dataclass defaults: 2 件

特に「失敗パターン網羅」 が綺麗 (= verify loop で各分岐の挙動が確定済)。 既存 `test_launcher_no_password.py` 14 件と regression なし = Session 131 までの CI 強制が継続している。

### 🟢-E `_attach_session_expired_info` が launcher を遅延 import

`auto_vote.py:459` で `from ml.target_clicker.launcher import detect_session_expired_dialog` を関数内 import。 launcher を起動しないテスト環境 / launcher が壊れた状態でも auto_vote 単独動作維持。 循環参照回避も同時に達成。 [[feedback_proactive_proposals]] の「失敗に強い設計」 として優秀。

### 🟢-F audit JSONL に session_expired_* 5 field を焼き込み

`auto_vote.py:563-567` で audit ログに session_expired / phase / title / keyword / pattern_source を保存。 「false positive で誤判定 → 後で audit を見れば追跡可能」 (質問 C) の安全弁が成立している。 ledger event の重複 (質問 D) も audit JSONL と突合すれば検出可能 = 監査経路は二重化されている。

### 🟢-G 設計書 §1.3 範囲外セクションが明示的

「暗証番号自動入力 / 自動リトライループ / 投票成立自動判定」 の 3 つを範囲外と明文化。 「やらないこと」 を文書化するのは Karpathy ガイドの 「success criteria の裏返し = 何ができれば終わりか」 を守るうえで重要。 ただし 🔴-1 で指摘した「復旧後の自動継続もしない」 を明示追加すれば完璧。

---

## 4. ふくだに確認したい論点 (3 件)

1. **🔴-1 修正 B (起動時の最近の SESSION_EXPIRED チェック) を Session 133 で入れるか?** — 空振りすると煩いが、 二重投票防止の最終層。 月初 OFF 練習日 (§1.5) と相性が良い (OFF 日は手動投票 = 自動で起動時チェックが発火しても無害)。

2. **`recover-session` CLI に `--confirm` 必須化するか?** — 現状は誰でも (= shell 履歴の上矢印で) 走らせられる。 復旧フローは「Step 4 で必ずふくだ暗証番号入力が必要」 なので暴走はしないが、 「CLI を打つ意図が確認されたか」 をもう一段挟むかどうか。

3. **`record_ipat_session_recovered` / `record_ipat_session_recovery_failed` を CLI 単独実行時にも記録する** (🟡-10) のを Session 132 内 (OOS 前) に入れるか、 Session 133 にするか? — 30 行程度の追加で済むが、 OOS 検証時に「初の復旧経路を ledger に残せる」 のは大きい。

---

## 5. Karpathy 「success criteria + verify loop」 観点の評価

### 5.1 設計書の success criteria 5 項目評価

| # | 内容 | 評価 | コメント |
|---|------|------|---------|
| 1 | 3 パターン (timeout / close_result 失敗 / 専用エラー) で検知 | 🟢 | 実装網羅 (ただし 🟡-3 で explicit_error_dialog 経路の呼出が薄い) |
| 2 | 検知時に音声 + IPAT_SESSION_EXPIRED_POSTVOTE 記録 | 🟢 | auto_vote._audit で配線済、 audit JSONL にも焼き込み |
| 3 | TARGET 再起動なしで復旧フローを試行 | 🟢 | recover_ipat_session 5-step 構造 OK |
| 4 | 復旧成功時 IPAT_SESSION_RECOVERED event + 音声 | 🟡 | event 関数定義済だが CLI 単独実行時に呼ばれない (🟡-10) |
| 5 | 復旧失敗時 IPAT_SESSION_RECOVERY_FAILED event + 音声 + 残り abort | 🟡 | 同上、 CLI 単独実行時に呼ばれない |

### 5.2 追加推奨 success criterion (6 項目目)

> **6. verify loop**: 来週末 OOS 検証で、 検知 → 音声 → ledger event 着地 → audit JSONL 記録 → recover-session 起動 → ledger RECOVERED event 着地、 までの end-to-end が **1 件以上実機観測される** (シナリオ: 暗証番号入力後 60 秒放置 → 自然タイムアウト → 投票試行 → session_expired 検知)

これを 18_TARGET_FULL_AUTOMATION.md §1.3 「Session 132 完成度」 の最後の `[ ]` 項目に追加することで、 「実装完了 = 設計書チェック完了」 ではなく「実機 OOS 検知が完了 = 設計書チェック完了」 という Karpathy 流の verify loop が回る。

---

## 6. 質問への直接回答

### A. お金経路の安全性
- **「自動リトライ無し」 を return 5 で実装** → 構造的に十分。 ただし `recover-session` CLI 単独実行後の「ふくだの再投票誘惑」 を 🔴-1 で対応するとさらに堅い。
- **`vote_already_clicked=True` の 3 経路通知** → ledger payload + audit JSONL + 音声で漏れなく伝わる設計。 ただし 🟡-2 の文字列比較 fragility を Session 133 で潰すべき。
- **`recover-session` CLI 二重投票リスク** → **🔴-1 として残る**。 修正 A (音声文面明確化) + 修正 C (設計書範囲外明示) は OOS 前に対応推奨。

### B. シズネ「ふくだのギャンブル本能ブレーキ」
- **「便利な流れを作らない」 設計判断** → 完全に支持。 ふくだに「1 度 CLI を打つ」 思考の隙間を強制するのは、 [[feedback_betting_philosophy]] の「動的調整なし」 哲学と整合する。
- **Step 4 永続手動** → 復旧時にも維持されており、 二重認証ゲートが復旧経路で再発火 = 「これで本当に再開していいか」 の意思確認になる。 [[shizune-agent]] 原則 1 (「人間が形骸化するリスク」) への抵抗策として優秀。
- **「諦める選択肢を残す」** → recover-session を打たない選択肢は構造的に保たれている (= TARGET ウィンドウ閉じれば終わり)。 ただし 🔴-1 修正 A の音声文面明確化で「今日はここでやめる」 を促す表現を入れるとなお良い。

### C. detect_session_expired_dialog の精度
- **2 段判定 (title_re + body_keywords) で false positive 抑制** → 妥当な選択。 ただし `_read_dialog_body` の max_descendants=50 が IPAT Web View で不足する可能性 (🟡-6) は OOS で確認。
- **JSON override + verified_by/target_version 必須** → 🟡-5 で CI 強制が未実装。 Session 133 で対応。
- **false positive で正常投票を session_expired 誤判定 → return 5** → audit JSONL に session_expired_* field が焼き込まれているので **追跡可能** = 完全に失うわけではない (🟢-F)。 ただし、 IPAT 側で既に投票成立した状態で誤判定が起こると、 ふくだは「あれ、 投票したつもりだったのに session_expired になった」 と混乱する。 ここは OOS で要観察。

### D. ledger event の冪等性
- **race_id 単位で記録、 重複 OK** → **同意**。 監査記録としては「どのフェーズで何回検知したか」 が大事で、 idempotency_key で潰すと「同一 race で何度も検知した = 復旧が安定しなかった」 という情報が失われる。 現状の「重複しても記録」 が正しい。
- ただし 🟡-9 / 🟡-10 で書いたように、 RECOVERED/RECOVERY_FAILED event が記録されないままだと「検知だけ大量 / 解決記録なし」 になり監査時に追えなくなる。 🟡-10 を Session 133 で必ず対応。

### E. その他見落とし
- **並行性 (複数 runner 同時起動)** → 想定外で OK だが、 設計書 18 のどこかに「`selective_vote.bat` は同時 1 プロセスのみ運用」 を明記すべき。 これは Session 133 で 18 §11 として追記。
- **セッション切れ後の TARGET ウィンドウ状態クリーンアップ責任** → 現在は誰も持っていない。 `recover_ipat_session` の Step 1 で `_close_session_expired_dialog` が 1 段だけ閉じるが、 もし 2 段 dialog が残っていたら? 🟡-8 で書いた通り、 OOS で実機構造を見てから判断。
- **来週末 OOS で確認すべき項目**:
  1. `launch_dialogs.json` の実機 dialog 確定 (Session 131 から積み残し)
  2. `session_expired_patterns.json` の実機 dialog 確定 (Session 132 NEW)
  3. セッション切れ時の dialog 多重構造 (1 段 / 2 段)
  4. `_read_dialog_body` の max_descendants=50 で IPAT Web View 本文を取りきれるか
  5. `result_dialog_timeout` 経路の発生条件 (= 投票 click 後に「投票終了」 が出ないシナリオを再現できるか — IPAT は投票成立してるはず)

### F. success criteria の網羅性
- 設計書 §1.3 success criteria 5 項目は **網羅的**。 ただし `verify loop` の観点で 6 項目目「実機 OOS で end-to-end 1 件以上観測」 を追加推奨 (§5.2)。
- 範囲外 3 項目 (暗証番号自動 / 自動リトライ / 投票成立自動判定) も明示済で良い (🟢-G)。 🔴-1 修正 C で「復旧後の自動継続もしない」 を追加すれば完璧。

---

## 7. OOS 検証前 To Do (推奨優先順)

| 優先度 | 項目 | 工数 | 担当 |
|--------|------|------|------|
| 🔴 必須 | 🔴-1 修正 A: `notify_ipat_session_recovery_succeeded` 文面明確化 | 5 分 | カカシ |
| 🔴 必須 | 🔴-1 修正 C: 設計書 §1.3 範囲外に「復旧後の自動継続もしない」 追記 | 3 分 | カカシ |
| 🟡 推奨 | 🟡-10: `recover-session` CLI で RECOVERED/RECOVERY_FAILED event 記録 | 30 分 | カカシ |
| 🟡 推奨 | success criteria 6 項目目 (verify loop) 追加 | 5 分 | カカシ |
| 🟢 OOS 後 | 🔴-1 修正 B / 🟡-2 / 🟡-3 / 🟡-5 / 🟡-6 / 🟡-7 / 🟡-8 / 🟡-9 | 各 30-90 分 | Session 133+ |

---

> 「セッション切れに自動でつなぐ便利さよりも、 そこで一度ふくだに『あれ?』 と思わせる方が、 結局は本能ブレーキとして強い。 今回の設計はそれを構造的に保っている。 残るのは『便利すぎる流れに見える CLI 案内』 だけ — そこを文面と設計書で明確化すれば、 来週末 OOS は GO。」 — シズネ (Session 132)

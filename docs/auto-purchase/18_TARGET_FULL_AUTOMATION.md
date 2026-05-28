# 18. TARGET 起動 + ログイン自動化 (前段オーケストレーション)

> **作成日**: 2026-05-24 (Session 130 / 起草)
> **更新**: 2026-05-24 (Session 131 / Phase 4-A/B/C 骨格実装 + runner.py 統合)
> **担当**: カカシ (起草+骨格実装) → シズネレビュー (Session 131 並行) → 来週末以降に実機検証
> **位置づけ**: [16_TARGET_AUTOCLICK.md](./16_TARGET_AUTOCLICK.md) §7.1 で「別書で詰める」と宣言した「投票内容確認ダイアログが出るまでの前段」 を完全自動化する設計書。 ふくだ操作を最終的に「**IPAT 暗証番号入力 1 回のみ**」 まで圧縮するのが目標。
> **関連**: [16_TARGET_AUTOCLICK.md](./16_TARGET_AUTOCLICK.md) (投票ダイアログ自動押下)、 [17_NOTIFICATION_LAYER.md](./17_NOTIFICATION_LAYER.md) (TTS 通知)、 [05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md) §「人手最終確認」

---

## 0. なぜ前段自動化が要るか

Session 127-129 で確立した「半自動運用」 のふくだ手数:

```
[手動 1] PC を立ち上げる
[手動 2] TARGET frontier JV を起動
[手動 3] TARGET 内認証ダイアログ進行 (ライセンス確認等)
[手動 4] TARGET メニュー「ﾌｧｲﾙ→IPATで投票する」 起動
[手動 5] IPAT 連動投票画面で暗証番号入力 ★ ← 唯一手動が残るべき箇所
[手動 6] selective_vote.bat 実行 (= ここから自動化済)
[手動 7] (失敗時) 音声警告に応じて TARGET 操作
```

→ Session 130 時点で「人手 1-4 + 7」 が機械化候補。 「5」 は **意図的に手動** (シズネ原則「お金経路の最終確認は人」)。

このうち最も価値が高いのは **「3」 認証ダイアログ進行** と **「4」 IPAT 連動メニュー起動** の自動化。 ここを潰すと「ふくだは PC 起動 → 暗証番号入力 → 完了」 までしか触らない。

### 0.1 ふくだ操作圧縮の目標

| Step | 操作主体 (現状) | 操作主体 (本書実装後) |
|---|---|---|
| 1. PC 起動 | ふくだ | ふくだ (タスクスケジューラ起動も検討) |
| 2. TARGET 起動 | ふくだ | **スクリプト** |
| 3. TARGET 認証ダイアログ | ふくだ | **スクリプト** |
| 4. IPAT 連動投票メニュー | ふくだ | **スクリプト** |
| 5. IPAT 暗証番号入力 | ふくだ | **ふくだ** (意図的に残す) |
| 6. selective_vote.bat | ふくだ (自動) | スクリプト or タスクスケジューラ |
| 7. 失敗リカバリ | ふくだ (音声警告対応) | ふくだ (Session 129 配線済) |

---

## 1. スコープ (Session 130 起草、 段階実装)

### 1.1 Phase 4-A: TARGET 起動 + 認証ダイアログ自動進行 (最優先)

- TARGET の exe を subprocess.Popen で起動
- 既に起動済みなら focus のみ
- ライセンス確認 / アップデート確認 等のダイアログを「OK / 次へ / はい」 で自動進行
- メイン画面到達まで polling (最大 30 秒)

### 1.2 Phase 4-B: IPAT 連動投票メニュー起動

- メニュー `ﾌｧｲﾙ→IPATで投票する` (cmd_id=1601、 16 §10.5 で確定済) を WM_COMMAND
- (またはツールバーのショートカット — Phase 4-B 内で確定)
- IPAT 連動投票画面 (= TARGET 内の Web View) が出るまで polling

### 1.3 Phase 4-C: IPAT セッション継続管理

**Phase 4-C-min (Session 131 シズネ 🔴 D で 4-A/B と同時実装に格上げ)**:
- `precheck_ipat_session()` で IPAT 認証直後に pre-flight 検証
- TARGET メニュー accessible + IPAT cmd_id 取得可で OK 判定 (実機検証で精度向上予定)
- NG なら abort + 音声「IPAT セッションが切れました…」 + ledger `IPAT_SESSION_EXPIRED` event

**Phase 4-C-full (Session 132 で骨格実装 + OOS 検証待ち)**:

#### 目標 (success criteria)
1. 投票実行中・直後の IPAT セッション切れを **3 パターン** (timeout / close_result 失敗 / 専用エラーダイアログ) で検知できる
2. 検知時に音声 + ledger `IPAT_SESSION_EXPIRED_POSTVOTE` event を記録する
3. **TARGET 再起動なしで** `open_ipat_menu()` 再起動 → `wait_ipat_login_ready` → 手動再認証 → `wait_ipat_main_ready` → `precheck_ipat_session` の復旧フローを試行できる
4. 復旧成功時は ledger `IPAT_SESSION_RECOVERED` event + 音声で「再認証成功 (ただし未投票分の自動再送はしない、 ledger 確認後ふくだ手動で再投票)」
5. 復旧失敗時は ledger `IPAT_SESSION_RECOVERY_FAILED` event + 音声で「手動復旧してください」 + 残りレース投票を abort
6. **verify loop** (Karpathy): 検知 → 音声 → ledger event 記録 → audit JSONL 焼き込み の end-to-end を **実機 OOS で 1 件以上観測** できる。 ledger event `IPAT_SESSION_EXPIRED_POSTVOTE` が events_jsonl + race ledger 両方に書かれ、 audit JSONL の `session_expired=true` 行も対応していることを来週末 5/30-31 で確認する

#### 検知パターン (実機検証で確定予定 / 推測 + JSON override)

| パターン | 検知タイミング | 既存実装 | Phase 4-C-full での扱い |
|---|---|---|---|
| ① 投票内容確認 dialog が出ない | `find_vote_dialog` timeout | `action="timeout"` | timeout 後に `detect_session_expired_dialog()` 呼び、 検出時 `action="session_expired"` に格上げ |
| ② 投票 click 後「投票終了」 が出ない | `close_result_dialog` timeout | `closed=False, receipt=None` | 同じく `detect_session_expired_dialog()` 呼ぶ。 ただし投票 click 自体は実行済なので注意 (要 manual_review フラグ) |
| ③ 専用エラーダイアログ | dialog title regex で検知 | なし | `IPAT_SESSION_EXPIRED_PATTERNS` (default + JSON override) で title/body 部分一致判定 |

**default patterns** (Session 132 時点の推測、 実機 inspect 待ち):
- title contains `"再ログイン"` / `"認証"` / `"セッション"` / `"タイムアウト"`
- body contains `"再度ログイン"` / `"認証情報が無効"` / `"セッションが切れ"` / `"timeout"` (英表記対応)

JSON 上書きパス: `data3/userdata/target_clicker/session_expired_patterns.json` (whitelist と同パターン、 verified_by/target_version 付き)

#### 復旧フロー

```
[検知]
  detect_session_expired_dialog() True (or timeout + ② / ③ 条件成立)
    ↓
[ledger event 記録]
  IPAT_SESSION_EXPIRED_POSTVOTE (どのフェーズで検知したか / 投票実行済かを payload に)
    ↓
[音声通知 + 復旧試行 開始]
  notify_ipat_session_recovery_attempted()
    ↓
[Step 1: エラーダイアログを閉じる]
  detect_session_expired_dialog() で見つかった dialog の OK/閉じる ボタン click
    ↓
[Step 2: IPAT メニュー再起動]
  launcher.open_ipat_menu(timeout_sec=15)
    ↓ 成功
[Step 3: 再ログイン画面待ち]
  launcher.wait_ipat_login_ready(timeout_sec=60)
    ↓ 成功
[Step 4: 手動暗証番号入力 ★ Session 131 と同じく永続手動]
  notify_ipat_login_required() (再認証なので「再度」 を文面に含む)
    ↓ ふくだが暗証番号入力
[Step 5: 再認証完了待ち + pre-flight 検証]
  launcher.wait_ipat_main_ready(timeout_sec=120)
  launcher.precheck_ipat_session()
    ↓ 両方 OK
[成功]
  notify_ipat_session_recovery_succeeded()
  ledger IPAT_SESSION_RECOVERED event
  → 次レースの投票を継続
    ↓ いずれか失敗 / timeout
[失敗]
  notify_ipat_session_recovery_required_manual()
  ledger IPAT_SESSION_RECOVERY_FAILED event
  → runner.py で残りレースの投票を abort
```

#### 範囲外 (Phase 4-C-full でもやらない)
- **暗証番号自動入力** ← 復旧時も Step 4 は永続手動 (シズネ原則 + 文書 §1.4 + test_launcher_no_password.py の対象)
- **自動リトライループ** ← 復旧が 1 回失敗したら abort。 「自動リトライによる連続失敗が IPAT 側のレート制限/ロック誘発」 リスクを避ける
- **②パターンの「投票成立 ↔ 未成立」 自動判定** ← 投票 click は実行済なので、 受付番号取得失敗時は `manual_review_required=True` で ledger 記録、 ふくだ手動で IPAT 残高・投票履歴を照合する
- **復旧成功後の自動継続** (Session 132 シズネ 🔴-1 修正 C) ← `recover-session` で復旧しても、 検知時点で投票キューに残っていた `selective_bets.json` の `bets[]` 自動再送は **しない**。 ふくだは ledger event `IPAT_SESSION_EXPIRED_POSTVOTE` と IPAT 履歴を照合した上で、 必要分だけ手動で `--bet ...` を組んで再投票する。 これは「`selective_vote.bat 2026-05-31 100 --confirm` を再叩きすると同じ bets が二度実行される」 リスクを構造的に潰すため

#### Session 132 完成度
- [x] success criteria + フロー設計確定 (本書 §1.3)
- [x] launcher.py 骨格実装 (`detect_session_expired_dialog` + `recover_ipat_session`)
- [x] notify.py 拡張 (3 関数)
- [x] writer.py 拡張 (event 3 種: POSTVOTE / RECOVERED / RECOVERY_FAILED)
- [x] auto_vote.py 統合 (timeout 時の事後検知 hook)
- [x] tests/test_launcher_recovery.py 骨格 (logic only / no IPAT 接続)
- [ ] **実機 OOS 検証**: 来週末 5/30-31 でセッション切れシナリオを実機再現 (e.g. 暗証番号入力後に放置 → 自然タイムアウト → recover 試行) ← OOS 必須
- [ ] `session_expired_patterns.json` を実機 inspect で確定

### 1.4 範囲外 (本書スコープではない)

- **IPAT 暗証番号の自動入力** ← **永久に範囲外 (構造的禁止)** ★ Session 131 シズネ 🔴 C
  - 文書宣言だけでなく `tests/test_launcher_no_password.py` (14 tests / 全 PASS) で CI レベル禁止
  - keyring / getpass / pyperclip の import 禁止 (AST チェック)
  - send_keys / type_keys / set_edit_text に「暗証/ﾊﾟｽﾜｰﾄﾞ/password/pwd」 を渡すパターン禁止 (regex チェック)
  - 環境変数や config から `IPAT_PASSWORD` 系を読むパターン禁止
  - launcher.py docstring に「永続手動」 明記 (test がこの文言の存在を確認)
- **selective_vote.bat の cron 起動** ← Phase 4 外、 別書 (Session 131+)

### 1.5 月初 OFF 練習日 (Session 131 シズネ提案 / Session 133 で 6/6 固定確定)

- 月初の 1 開催日は `--auto-launch` を **使わない** 半自動運用に意図的に戻す
- 目的:
  - 自動化スキル劣化防止
  - 「形骸化リスク」 (PC 起動 → 暗証番号 → 完了 が習慣化して内容を見なくなる) への定期的歯止め
  - 18 OFF でも 16/17 (投票 click + TTS) は使うので、 手動手順を最小限の維持
- **運用 (Session 133 シズネ独自観点 / 2026-05-27 確定)**:
  - **2026-06-06 (土) を月初 OFF 練習日として固定**。 OOS (5/30-31) 結果に依らず実施
  - 6/6 朝に半自動運用で 1 レース投票 → 5/30-31 OOS 結果との比較 = 「自動化なしでも回せる筋力」 維持確認
  - 以降は毎月「第 1 開催日」 を OFF とし、 半自動運用で 1 レース投票
  - 「OOS 大成功なら OFF 不要」 と思った時こそ OFF をやる (= [[shizune-agent]] 「不可逆性の非対称」: 設定を緩めるのは容易、 設定がない状態から作るのは難しい)

---

## 2. 技術選定

| 項目 | 選定 | 理由 |
|---|---|---|
| 自動化対象 | TARGET frontier JV (Win32 デスクトップ) | 16_TARGET_AUTOCLICK と統一 |
| 自動化ライブラリ | **pywinauto 0.6.9** (Win32 backend) | 16 と統一、 Delphi VCL の WM_COMMAND が効く |
| プロセス起動 | `subprocess.Popen` | 既起動チェックは `psutil.process_iter` |
| 既起動判定 | プロセス名 `target_jv.exe` (TBC) | 起動済なら focus のみ |
| ダイアログ自動進行 | dialog title polling + button click | 16 §10.2 と同パターン |

---

## 3. 起動シーケンス (実装イメージ)

### 3.1 ファイル構成 (Session 131 で骨格実装完了)

```
keiba-v2/ml/target_clicker/
├── auto_vote.py       ← Session 127-128 (投票ダイアログ click)
├── menu_runner.py     ← Session 127-128 (TARGET メニュー操作)
├── ff_writer.py       ← Session 128
├── notify.py          ← Session 129/130/131 (TTS + Phase 4 文面)
├── selective_loader.py ← Session 129
├── runner.py          ← Session 128-131 (オーケストレータ + --auto-launch)
└── launcher.py        ← Session 131 新規 (本書実装) ★
keiba-v2/ml/tests/
└── test_launcher_no_password.py  ← Session 131 (シズネ 🔴 C / 14 tests)
```

### 3.2 launcher.py の公開 API (Session 131 実装済 + シズネ A/B/D 反映)

```python
def launch_target(*, timeout_sec: int = 30, focus_only_if_running: bool = True,
                  auto_dismiss: bool = True) -> LaunchResult:
    """TARGET 起動 + 認証ダイアログ自動進行 + メイン画面到達まで待つ。
    既起動なら focus のみ。 LaunchResult に target_handle / dialogs_dismissed /
    unknown_dialogs / version_mismatch / elapsed_sec を返す。
    Session 131 シズネ B: dialogs_dismissed は whitelist 一致のみ、 whitelist 外 + TARGET
    由来 dialog は unknown_dialogs に記録し、 abort_on_unknown 経由で abort 可能。
    """

def open_ipat_menu(*, timeout_sec: int = 15) -> bool:
    """TARGET メイン画面から IPAT 連動投票メニューを起動。
    cmd_id=1601 (16 §10.5 確定済) を動的解決 + WM_COMMAND PostMessage。
    """

def wait_ipat_login_ready(*, timeout_sec: int = 60) -> bool:
    """IPAT 連動投票画面の暗証番号入力フィールド出現を待つ。
    実機検証待ち: 暫定的に IPAT 関連キーワードを含むウィンドウタイトルで判定。
    """

def wait_ipat_main_ready(*, timeout_sec: int = 120) -> bool:
    """IPAT メイン画面到達を待つ (= 暗証番号入力後の遷移待ち)。
    判定: ログイン画面が一度 visible になった後消えたら True。
    """

def precheck_ipat_session(*, timeout_sec: int = 10) -> tuple[bool, str]:
    """🔴 D (Phase 4-C-min): pre-flight IPAT セッション検証。
    selective_vote.bat 走り出し前に呼ぶ。 TARGET メニューが accessible で
    IPAT cmd_id が取れたら OK 判定。 NG なら reason に詳細。
    """

def auto_dismiss_dialogs(*, whitelist=None, timeout_sec: int = 10,
                          max_iterations: int = 5,
                          abort_on_unknown: bool = False) -> DismissResult:
    """🔴 B: whitelist に一致するダイアログだけ click。 一致しない TARGET 由来
    dialog は unknown_dialogs に記録。 abort_on_unknown=True で即 abort。
    """

def load_dialog_whitelist_v2(path=None) -> DialogWhitelistConfig:
    """🔴 B: whitelist 設定 v2 スキーマ読み込み。
    {version, verified_at, verified_by, target_version, dialogs[]}.
    list 形式 (legacy v1) も後方互換で受ける。
    """

def verify_target_version(actual: str, expected: str | None) -> bool:
    """🔴 B: TARGET 実バージョンと whitelist 期待バージョン (target_version) の一致確認。
    不一致時は launch_target() が auto_dismiss を寛容モード (abort_on_unknown=False)
    に切替。 expected=None なら True (検証 skip)。
    """

def inspect_launch_dialogs(*, duration_sec: int = 30) -> Path:
    """🟢 G: 起動シーケンス調査用。 duration_sec の間に visible になった全 dialog
    + buttons + class + handle を JSON dump。 16 §10.3 の inspect-batch と同思想。
    """
```

### 3.3 上位 CLI (`runner.py --auto-launch`、 既定 OFF / シズネ 🟡 K)

```bash
# 既定 OFF。 --auto-launch 明示時のみ前段自動化を発動する。
# 1 コマンドで TARGET 起動 → IPAT ログイン待ち → selective 投票
python -m ml.target_clicker.runner \
    --auto-launch \
    --from-date today --amount 100 --confirm
```

実装フロー (Session 131 実装済):

```
1. launcher.launch_target()
   → TARGET 起動 / 既起動 focus
   → whitelist v2 読込 + target_version 検証
   → ライセンス・アップデート確認 ダイアログ自動進行 (abort_on_unknown=True)
   → unknown dialog 検知 → 即 abort + ledger TARGET_DIALOG_UNKNOWN event
   → メイン画面到達

2. launcher.open_ipat_menu()
   → cmd_id=1601 を WM_COMMAND PostMessage
   → IPAT 連動投票画面表示

3. launcher.wait_ipat_login_ready()
   → ログイン画面検出 (暗証番号入力フィールド出現)

4. notify.notify_daily_plan_summary()  ★ シズネ 🔴 A 二重認証ゲート
   → 「本日の投票プラン。 新潟8R 単勝 6 番、 他 N 件。 合計 N円。 暗証番号を入力すると…」
   → ふくだは聞いて違和感なければ暗証番号入力 (= 内容承認)

5. [手動] ふくだが IPAT 暗証番号入力 ★ 唯一の手動操作

6. launcher.wait_ipat_main_ready()
   → IPAT メイン画面到達 = 暗証番号入力完了

7. launcher.precheck_ipat_session()  ★ シズネ 🔴 D Phase 4-C-min pre-flight
   → セッション有効性確認、 NG なら abort + ledger IPAT_SESSION_EXPIRED event

8. runner.main() の Step 1 以降 (既存)
   → FF CSV 書き出し → step1 (取込) → step3 (投票画面起動)
   → 投票ダイアログ → click + OK → finalize_save_to_target
```

---

## 4. ダイアログ進行パターン (実機観察待ち)

### 4.1 TARGET 起動後の想定ダイアログ

| タイトル候補 | Body 内容 | 自動進行ボタン |
|---|---|---|
| `TARGET frontier JV` | ライセンス情報 | `OK` |
| `お知らせ` | アップデート通知等 | `閉じる` / `OK` |
| `初期化中` | プログレスバー | (待機のみ) |
| `JV-Link 接続` | データ受信状況 | (待機 or バックグラウンド進行) |

**Session 130 残課題**: 来週末ふくだ環境で実際に TARGET 起動 → どのダイアログがどの順で出るか inspect。 16 §10.3 の inspect-batch SOP を流用して 1 発で dump する。

### 4.2 IPAT 連動投票画面の構造

| 領域 | Win32 control | 内容 |
|---|---|---|
| 暗証番号入力フィールド | TEdit | password mask |
| ログインボタン | TButton | `ログイン` 等 |
| Web View 全体 | (Embedded browser) | UIA backend で `Document` として見える可能性 |

→ wait_ipat_login_ready は「TEdit (password 属性) が visible になった」 を検知。
→ wait_ipat_main_ready は「Web View 内に投票メニュー (Document body) が visible になった」 を検知。

---

## 5. 失敗パターンとリカバリ

Session 131 で追加した失敗パスと ledger event の紐付け (シズネ 🟡 F 反映):

| 失敗ケース | 検知 | リカバリ | ledger event |
|---|---|---|---|
| TARGET 起動失敗 (exe 見つからず) | `find_target_exe` で None | abort + 音声 (`notify_launch_failure`) | (TBD: TARGET_LAUNCH_FAILED) |
| TARGET 起動タイムアウト | メイン画面 30s 内未到達 | abort + 音声 + 手動起動を促す | (TBD: TARGET_LAUNCH_TIMEOUT) |
| whitelist 外ダイアログ検知 | `auto_dismiss_dialogs(abort_on_unknown=True)` | abort + 音声 + ledger 記録 | **TARGET_DIALOG_UNKNOWN** ✅ |
| target_version 不一致 | `verify_target_version()` False | 寛容モード継続 + 音声警告 | (将来: LAUNCHER_VERSION_MISMATCH) |
| IPAT メニュー起動失敗 | `open_ipat_menu()` False (cmd_id 取得失敗) | abort + 既存 N 経路に流す | IPAT_START_FAILED (Session 130) |
| ふくだ暗証番号入力タイムアウト | `wait_ipat_login_ready/main_ready` で経過 | abort + 音声リマインド | (TBD: USER_LOGIN_TIMEOUT) |
| IPAT セッション切れ (pre-flight) | `precheck_ipat_session()` False | abort + 音声 + ledger 記録 | **IPAT_SESSION_EXPIRED** ✅ |
| IPAT セッション切れ (事後) | 投票ダイアログが「再ログインしてください」 系 | (Phase 4-C-full / Session 132+) | (TBD: IPAT_SESSION_EXPIRED 事後判定) |

★✅ は Session 131 で配線済 (`_record_failure_event()` 経由)。 TBD は Session 132+ で 14_LEDGER_SCHEMA に追記予定 (22 種 → 26+ 種)。

### 5.1 抑止すべきアンチパターン

- **暗証番号の自動入力**: コードに保存・スクリプトで入力は **禁止**。 シズネ原則「お金経路の最終認証は人」 + 05_RISK_COMPLIANCE.md
  - **Session 131 シズネ 🔴 C**: 文書宣言だけでなく `tests/test_launcher_no_password.py` (14 tests / 全 PASS) で CI 強制
  - keyring / getpass / pyperclip の import を AST レベル禁止
  - send_keys / type_keys / set_edit_text に password 系を渡すパターン禁止
  - 環境変数 `IPAT_PASSWORD` 系の読み取り禁止
- **Selenium / Web View 直接操作**: TARGET 内 Web View に対して直接操作するのは ToS 違反リスク + 認証情報露出。 TARGET 自体の Win32 API 経由のみに留める
- **TARGET 起動と IPAT ログインの間に他処理を挟む**: race condition で「IPAT 認証画面の遷移」 を見逃す。 wait_ipat_*_ready で polling 待機する
- **whitelist 外ダイアログの自動 click**: Session 131 シズネ 🔴 B で `abort_on_unknown=True` をデフォルトに格上げ。 想定外ダイアログは abort 一択

---

## 6. 実装ポイント (Session 131+ で書く時の覚書)

### 6.1 TARGET exe パス検出

ふくだ環境 (Session 127 inspect 結果):
- メインウィンドウ class: `TApplication`
- メインウィンドウ text: `TARGET frontier JV  Ver6.21  Rev002`

実 exe パスは要確認。 検出方法:
1. `psutil.process_iter(['name', 'exe'])` で `target` を含むプロセスを探す
2. 見つからなければ Win32 レジストリの App Paths を参照
3. 環境変数 `TARGET_EXE_PATH` で明示指定も可能に

### 6.2 既起動チェック

```python
def find_target_window():
    for w in Desktop().windows():
        if "TARGET frontier JV" in (w.window_text() or ""):
            return w
    return None
```

既存 menu_runner.find_target_window() と同等。 共通化する。

### 6.3 ダイアログ進行の汎用関数 (Session 131 シズネ 🔴 B で厳格化済)

**whitelist スキーマ v2** (`data3/userdata/target_clicker/launch_dialogs.json`):

```json
{
  "version": "1.0",
  "verified_at": "2026-05-31T08:00:00+09:00",
  "verified_by": "fukuda",
  "target_version": "TARGET frontier JV  Ver6.21  Rev002",
  "dialogs": [
    {
      "title_re": "^TARGET frontier JV$",
      "buttons": ["OK"],
      "purpose": "ライセンス情報確認"
    },
    {
      "title": "情報",
      "buttons": ["OK"],
      "purpose": "情報通知"
    }
  ]
}
```

`load_dialog_whitelist_v2(path)` で読み込み、 list 形式 (legacy v1) も後方互換で受ける。
TARGET 実バージョンと `target_version` が一致しないとき `verify_target_version()` False → `launch_target()` 内で `abort_on_unknown=False` に降格して継続 (ただし unknown は記録)。

**whitelist 外ダイアログの取り扱い**:
- `_is_target_owned_dialog()` で TARGET 由来か簡易判定 (class 名 / タイトルキーワード)
- TARGET 由来 + whitelist 外 → `unknown_dialogs` に記録
- `abort_on_unknown=True` (= launch_target デフォルト) なら即 abort + LaunchResult.action="dialog_unknown"
- 呼び出し側 (runner.py) で `TARGET_DIALOG_UNKNOWN` event を ledger 記録 + 音声通知

**whitelist の追加レビューフロー** (Session 131 シズネ B 推奨):
1. `inspect-launch` で実機 dialog dump
2. 必要なエントリを JSON に追記、 `verified_by` / `verified_at` 更新
3. git commit (= 監査記録)
4. TARGET アップデート時は `target_version` を更新

### 6.4 通知統合 (Session 129-131 notify.py との連携)

| Phase | 通知文面 | 関数 (Session 131 実装済) |
|---|---|---|
| TARGET 起動完了 | `TARGET の起動が完了しました。 認証ダイアログを N 件、 自動進行しました。 …` | `notify_launch_ready(dialogs_dismissed=N)` |
| **当日プラン読み上げ ★ A** | `本日の投票プラン。 新潟8R 単勝 6 番、 他 N 件。 合計 N円。 暗証番号を入力すると投票を開始します。` | `notify_daily_plan_summary(bets_summary, total_yen)` |
| IPAT ログイン待機中 | `IPAT 暗証番号の入力をお待ちしています。 認証してください。` | `notify_ipat_login_required()` (※ A 採用時は使用しない) |
| IPAT 認証完了 | `IPAT 認証が完了しました。 投票を開始します。` | `notify_ipat_login_complete()` |
| TARGET 起動失敗 | `TARGET の自動起動に失敗しました。 <reason>。 手動で TARGET を起動してください。` | `notify_launch_failure(reason)` |
| IPAT セッション切れ | `IPAT セッションが切れました。 投票を中断しています。 再認証してください。` | `notify_ipat_session_expired()` |

★ A: シズネ 🔴 A の二重認証ゲート。 `notify_ipat_login_required` の代わりに `notify_daily_plan_summary` を `wait_ipat_login_ready` 直後 (暗証番号入力 **前**) に発話することで、 「暗証番号入力 = ① IPAT ログイン認証 + ② 当日プラン内容承認」 の二重意味を持たせる。

---

## 7. シズネレビュー観点 (Session 131-133 累積)

### 7.0 観点別評価表 (Session 131 起源)

| 観点 | 起草段階の想定 | Session 131 シズネ評価 + 対応 |
|---|---|---|
| 暗証番号取扱 | 🟢 範囲外 (手動限定) | 🔴 C → CI テスト追加 (`test_launcher_no_password.py` 14 tests / PASS) |
| TARGET ToS との整合 | 🟡 グレー領域 | 🟡 E (累積評価) → **Session 133 §7.1 で累積評価追記済** |
| TARGET 起動暴走 | 🟢 既起動チェックあり | 🟢 維持 |
| 認証ダイアログ自動進行 | 🟡 whitelist 必須 | 🔴 B → v2 スキーマ + target_version + abort_on_unknown (Session 131 実装済) + 🟡-5 verified_by 必須化 WARNING (Session 133) |
| セッション切れ検知 | 🟡 事後型のみ | 🔴 D → pre-flight `precheck_ipat_session()` を 4-A/B 同時必須に格上げ (Session 131 実装済) + Phase 4-C-full 事後検知 (Session 132) |
| 「人手最終確認」 = 暗証番号 | 🟢 と想定 | 🔴 A → 暗証番号 ≠ 投票内容承認、 当日プラン音声読み上げで二重認証化 (Session 131 実装済) |
| 「自動化スキル劣化」 リスク | 想定なし | 🟡 月初 OFF 練習日 (§1.5) で歯止め |
| **二重投票誘発リスク** | 想定なし | 🔴-1 修正B (Session 132 指摘) → **Session 133 起動時 SESSION_EXPIRED チェック実装 (17 tests / PASS)** |

### 7.1 ToS 累積評価 (Session 132 🟡 E → Session 133 実装)

**累積評価対象**: 16 (TARGET_AUTOCLICK) + 17 (NOTIFICATION_LAYER) + 18 (TARGET_FULL_AUTOMATION 全 Phase)

シズネ Session 132 レビュー 🟡 E を受けて、 来週末 5/30-31 OOS 検証前に「外部規約・ToS との整合」 を 3 系統で再確認。 グレー領域を可視化することで、 「想定外の規約抵触」 リスクを構造的に下げる + ふくだ判断材料を一覧化。

| 対象 | 主な操作 | TARGET ToS | IPAT 規約 | JV-Link / JRA-VAN 提供元サポート | 緩和策 |
|---|---|---|---|---|---|
| **16 投票 click + finalize** | TARGET 内 dialog 自動押下 (Win32 API)、 「投票内容確認 → 投票 → 投票終了 → OK → F10 → はい」 | 🟡 グレー (TARGET ヘルプに「自動操作の明示禁止条項」 は無いが、 想定外操作 = 推奨はされない) | 🟢 IPAT 側に影響なし (TARGET 内 dialog 操作のみ、 IPAT サーバへの追加リクエスト無し) | 🟡 サポート対象外 (「TARGET のサポートは GUI 経由の手動操作のみ」 が暗黙の前提) | (a) 投票内容は max_yen / max_bets 検証必須、 (b) 監査 JSONL に raw text 全保存、 (c) 月初 OFF 練習日で手動 SOP 維持 (§1.5)、 (d) Session 128 ライブ実証で +8,300 円的中時の挙動を確認済 |
| **17 TTS 通知** | pyttsx3 / PowerShell SAPI で音声読み上げ | 🟢 影響なし (ローカル発話のみ) | 🟢 影響なし | 🟢 影響なし | なし (完全ローカル / Windows 標準 voice 使用) |
| **18 起動 + IPAT メニュー + Phase 4-C-min** | TARGET exe 起動 (subprocess) + 認証 dialog 自動進行 (whitelist v2) + cmd_id=1601 WM_COMMAND | 🟡 グレー (16 と同じ理由) | 🟢 IPAT 認証画面の表示待ちのみ (ふくだ手動暗証番号入力で初めてサーバ通信) | 🟡 サポート対象外 | (a) whitelist v2 + `verified_by` 必須化 (Session 133) + `abort_on_unknown=True` で想定外 dialog 即停止、 (b) `target_version` mismatch で寛容モード降格、 (c) 暗証番号自動入力は CI 強制で構造的禁止 (test_launcher_no_password.py 14 tests / PASS) |
| **18 Phase 4-C-full 復旧** | セッション切れ検知 → TARGET 再起動なし IPAT メニュー再起動 → ふくだ手動暗証番号入力 → 多段モーダル対応 (Session 133 🟡-8) | 🟡 グレー (16/18 と同じ) | 🟡 グレー (「短時間に複数回認証試行」 が IPAT 側でロック対象になる可能性、 ただし手動入力なのでブルートフォース判定はされにくい) | 🟡 サポート対象外 | (a) 自動リトライしない構造的禁止 (1 回失敗 → abort + 人手対応)、 (b) `recover-session` CLI 単独実行も RECOVERED/RECOVERY_FAILED event 必須記録 (Session 132 🟡-10 対応)、 (c) Session 133 修正B で直近 1h SESSION_EXPIRED チェック発火 → 二重投票防止、 (d) 多段モーダル (最大 3 段) 自動 close で「閉じ残し」 回避 |

#### 7.1.1 累積リスクスコア

| ランク | 対象 | 数 |
|---|---|---|
| 🟢 ゼロ | 17 (TTS) のみ | 1 |
| 🟡 グレー | 16 (投票 click) / 18 (起動・メニュー) / 18 (Phase 4-C-full 復旧) | 3 |
| 🔴 違反 | **なし** (暗証番号自動入力を構造的禁止、 ふくだの IPAT 操作意思が常に介在) | 0 |

#### 7.1.2 グレー領域への対策原則 (シズネ 3 原則)

Session 124 シズネ加入時に提示された 3 原則を、 Session 131-133 実装で構造化:

1. **「お金経路の最終認証は人」** — IPAT 暗証番号入力は永続手動 + CI 強制禁止 (`test_launcher_no_password.py` 14 tests)。 keyring / getpass / pyperclip 禁止 + AST 検査で「将来の自分」 が手を出せない設計
2. **「便利な復旧フローを意図的に作らない」** — Phase 4-C-full 復旧後の自動継続をしない (設計書 §1.3 範囲外宣言 + Session 133 修正 B 起動時チェック)。 ふくだに「1 度 CLI を打つ」 思考の隙間を強制
3. **「気付かせる + 手順を提示する + 監査証跡を残す」** — rollback 不能な失敗 (TARGET_SAVE_FAILED / IPAT_SESSION_RECOVERY_FAILED) は payload に `manual_action_required` 必須、 ledger event + 音声 + audit JSONL の三重通知

#### 7.1.3 規約変更検知の運用

- **3 ヶ月ごとに TARGET ヘルプ + IPAT 規約をふくだ手動確認** (Session 132+ で運用導入予定、 カレンダーリマインダ要設定)
- 規約変更検知時は本表 (§7.1) を即更新 + 影響範囲を 16/17/18 に逆引きする
- 「ToS 違反疑い」 発生時は `selective_vote.bat` 即時停止 → ふくだ + シズネ協議
- 月初 OFF 練習日 (§1.5) は規約再読の機会としても運用 (PC 立ち上げ → TARGET ヘルプ目視 → IPAT ログイン画面の規約リンクをクリック確認)

---

## 8. 完成基準 (Session 131 シズネ 🟡 G で「先行可」 / 「OOS 待ち」 に二分)

### 8.1 Session 131 内で完了 (先行可)

- [x] **🔴 C** `tests/test_launcher_no_password.py` 先置 (14 tests / 全 PASS)
- [x] `launcher.py` 骨格実装 (launch_target / open_ipat_menu / wait_ipat_*_ready / precheck_ipat_session / auto_dismiss_dialogs / inspect_launch_dialogs)
- [x] **🔴 B** whitelist v2 スキーマ + `load_dialog_whitelist_v2()` + `verify_target_version()` + `abort_on_unknown` + launch_target 拡張
- [x] **🔴 D** `precheck_ipat_session()` + runner.py --auto-launch フローに pre-flight 挿入
- [x] **🔴 A** `notify_daily_plan_summary()` + 当日プラン音声読み上げ + runner.py で wait_ipat_login_ready 後に発話
- [x] runner.py に `--auto-launch` フラグ追加 (既定 OFF / シズネ 🟡 K)
- [x] notify.py に Phase 4-A/B/C 用文面ヘルパー追加 (5 新規関数)
- [x] `inspect-launch` CLI 追加 (16 §10.3 と同思想)
- [x] ledger event 配線 (TARGET_DIALOG_UNKNOWN + IPAT_SESSION_EXPIRED, `_record_failure_event` 経由)
- [x] 設計書 (本書) 更新

### 8.2 来週末 (5/30-31) OOS 検証待ち

- [ ] ふくだ環境での `inspect-launch` 実行 → 実機ダイアログ dump
- [ ] dialog whitelist JSON 初期構築 (`launch_dialogs.json` v2 スキーマで `verified_by=fukuda`)
- [ ] TARGET exe パスの実機確認 (`find_target_exe()` の検出経路)
- [ ] IPAT ログインウィンドウのクラス/タイトル確認 (`wait_ipat_login_ready` の判定パターン)
- [ ] IPAT セッション切れの検知パターン精度向上 (`precheck_ipat_session` の判定基準確定)
- [ ] `selective_vote.bat --auto-launch` でフル動作確認
- [ ] **OOS GO/NO-GO 判定** → GO なら Session 132+ で 14_LEDGER_SCHEMA に新 event 6 種追記

### 8.3 Session 132+ (将来課題)

- [x] **🟡 E** ToS 累積評価追加 (§7.1 に「TARGET ToS / IPAT 規約 / JV 提供元サポート」 の 3 列追記、 **Session 133 完了**)
- [x] **🟡 F** ledger event 8 種を 14_LEDGER_SCHEMA に追記 (22 種 → 30 種、 **Session 133 v1.2 確定**)
- [x] **🟡-2** (Session 132 指摘) `session_expired_phase` 文字列リテラル定数化 + VOTE_ALREADY_CLICKED_PHASES (**Session 133 完了**)
- [x] **🟡-5** (Session 132 指摘) `session_expired_patterns.json` v2 + whitelist v2 verified_by 必須化 + 起動時 WARNING (**Session 133 完了、 10 tests / PASS**)
- [x] **🟡-8** (Session 132 指摘) `recover_ipat_session` の Step 1 多段モーダル対応 (最大 3 回試行、 後方互換維持で 1 段目は既存 step 名) (**Session 133 完了**)
- [x] **🔴-1 修正B** (Session 132 指摘) `runner.py --auto-launch` 起動時の直近 1h SESSION_EXPIRED チェック + exit 8 + 音声警告 (**Session 133 完了、 17 tests / PASS**)
- [x] **Phase 4-C-full** TARGET 再起動なしでセッション復旧 (**Session 132 骨格、 Session 133 仕上げ — 来週末 OOS 検証で verify loop 観測待ち**)
- [ ] **🟡 I** wait_ipat_login_ready の timeout を 60s → 300s 拡張、 60s ごとにリマインダ音声
- [ ] **🟡 J** メイン画面到達判定の多段化 (タイトル + メニュー enabled + プログレスバー消滅)
- [ ] **🟡-3** (Session 132 指摘) `explicit_error_dialog` phase の auto_vote 経路追加 (click 前 poll)
- [ ] **🟡-6** (Session 132 指摘) `_read_dialog_body` max_descendants=50 を 200 に拡張 (OOS で IPAT Web View 本文取りきれるか確認後)
- [ ] **🟡-10** (Session 132 指摘) `recover-session` CLI 単独実行時の RECOVERED/RECOVERY_FAILED event 記録 (Session 132 内で対応済の予定だが、 念のため OOS 前に再確認推奨)
- [ ] 月初 OFF 練習日の運用導入 (§1.5)

---

## 9. Session 130-131 時点の決定事項

1. ~~本書は起草のみ、 実装は Session 131+~~ → **Session 131 で骨格実装 + シズネ A/B/C/D 全 4 件対応完了**
2. **Phase 4-A/B/C-min 同時実装** (Session 131 シズネ 🔴 D で 4-C 後回しから格上げ)
3. **暗証番号入力は永続的に手動 + CI 強制** (Session 131 シズネ 🔴 C で構造的禁止)
4. **inspect コマンドを 16 と統一** (`inspect-launch` 実装済)
5. **当日プラン音声読み上げで二重認証ゲート** (Session 131 シズネ 🔴 A)
6. **whitelist v2 スキーマ + target_version 検証** (Session 131 シズネ 🔴 B)
7. **月初 OFF 練習日** (Session 131 シズネ提案、 運用導入は Session 132+)

---

> 「ふくだ操作を IPAT 暗証番号入力のみに圧縮」 — Session 129 残宿題として MEMORY に残されていた目標。 Session 130 で起草、 **Session 131 で骨格実装 + シズネ 🔴 4 件 (A/B/C/D) 全対応**、 来週末 OOS 検証を経て Phase 4 完全自動化が完成する。 シズネ「条件付き GO」 がすべての条件満たして「無条件 GO」 となるかは来週末 OOS で判定。 — カカシ (Session 131)

# 20. CURRENT CAPABILITIES — 自動投票機能 現状俯瞰サマリ

> **作成日**: 2026-05-26 (Session 133) / **更新**: 2026-05-28 (Session 134 — freebudget 路線追加)
> **目的**: Session 128-134 で積み上げた自動投票機能の「**何ができて何がまだか**」 を 1 ページで把握する単一エントリ
> **想定読者**: ふくだ (朝の確認) / シズネ (レビュー材料) / 3 ヶ月後のカカシ (記憶引き継ぎ)
> **更新方針**: 各 Session 完了時 + 大きな実機検証直後に更新。 詳細は個別設計書 (01-19) へリンク

---

## 0. TL;DR

- **現状フェーズ**: Phase 4-A/B/C-min/C-full 骨格完成、 **89 tests** / 全 PASS、 実機 4 投票 (受付 0029/0030/0045/0046) + 印無視 ML 初的中 +8,300円
- **Session 134 追加**: **freebudget 戦略** (1万円フリー予算 × ML×直前オッズ EV判定 × 1/4 Kelly cap 10% 案分) を新規実装。 amount=100 路線を OOS から廃止、 5/30-31 は freebudget_bets.json 経由
- **Session 134 シズネレビュー 🔴 全潰し済**: 4 件🔴 (config 衝突 / 二重認証ゲート骨抜き / 払戻タイムラグ罠 / Themis 原則整合) を 5/29 夜前に全部対応。 「条件付き GO → 無条件 GO」 確定
- **直近マイルストーン**: **2026-05-30 (土) 〜 2026-05-31 (日) OOS 検証** — 1万円フリー予算 + `--auto-launch` フル自動の本番投入 + verify loop 観測
- **最大リスク**: 6 件の「不明変数」 が実機 dump 取らないと確定しない (§6 参照)。 段階的アプローチ ([19_OOS_RUNBOOK](./19_OOS_RUNBOOK.md) §0.2) で吸収する設計

---

## 1. 実装マトリクス — Phase 4-A/B/C-min/C-full

| Phase | 担当 | 状態 | テスト | CLI | 関連設計書 |
|---|---|---|---|---|---|
| **4-A** TARGET 起動 + 認証ダイアログ進行 | launcher.py | 🟡 骨格実装済 / 実機 exe パス + dialog 確定待ち | test_launcher_no_password.py 14 / test_launcher_verified_by.py 10 | `launcher.py launch` / `launcher.py inspect-launch` | [18 §1.1](./18_TARGET_FULL_AUTOMATION.md) |
| **4-B** IPAT 連動メニュー起動 + ログイン待機 | launcher.py + menu_runner.py | 🟢 メニュー操作実装済 / IPAT ボタン多段 fallback | (上記に含む) | `launcher.py open-ipat` / `launcher.py wait-login` | [16 §10-11](./16_TARGET_AUTOCLICK.md) / [18 §1.2](./18_TARGET_FULL_AUTOMATION.md) |
| **4-C-min** pre-flight session 検証 | launcher.py (`precheck_ipat_session`) + runner.py | 🟢 実装済 / 実機 NG 経路観測待ち | test_runner_session_expired_check.py 17 | `runner.py --auto-launch` | [18 §1.3-min](./18_TARGET_FULL_AUTOMATION.md) |
| **4-C-full** セッション切れ事後検知 + 復旧 | launcher.py (`detect_session_expired_dialog` / `recover_ipat_session`) + auto_vote.py | 🟡 骨格実装済 / OOS で verify loop 1 件以上観測待ち | test_launcher_recovery.py 23 | `launcher.py detect-session-expired` / `launcher.py recover-session` | [18 §1.3-full](./18_TARGET_FULL_AUTOMATION.md) |
| **4-D** TARGET セッション継続管理 | (未着手) | ⚪ Session 134+ スコープ | - | - | (未起草) |

**freebudget 戦略** (Session 134 新規, 横断):
- 🟢 `ml/strategies/freebudget.py` 新設 (300 行) — predictions.json から VB Floor 通過 (Composite Score>=5.5 + EV>=1.0) を抽出 → 各馬 `p = win_ev/odds` → 1/4 Kelly × bankroll × cap 10% → 100円丸め → 合計>bankroll で EV降順 truncate
- 🟢 `selective_loader.py` 拡張 — `ALLOWED_SOURCES` に `freebudget_kelly_1q` 追加、 `SelectiveBetEntry.amount` 検証 (100..1000 / 100円単位 / freebudget は必須 / 他 source では指定不可で abort)
- 🟢 `runner.py` 拡張 — `bet.amount` あれば優先、 無ければ `--amount` フォールバック (Session 128 互換)
- 🟢 test 18 件 (test_strategy_freebudget 10 + test_selective_loader_amount 8) / 全 PASS
- 🟡 OOS 後タスク: ふくだ既存「収支管理機能」 から最新残高自動取得 (5/31 朝の `--bankroll` 手動入力を不要化)、 さらに将来「IPAT 実残高取得」 をセットでレース間動的更新へ拡張

**ledger v2 配線** (横断):
- 🟢 実装済: `record_tansho_vote` / `record_vote_failure` / `record_ipat_start_failure` / `record_target_save_failure` / `record_ipat_session_recovered` / `record_ipat_session_recovery_failed`
- 🟡 残: ledger v2 settle 拡張 (払戻 / SETTLED event) — JRA-VAN 確定後の自動突合と同時実装予定

**通知レイヤ** (横断):
- 🟢 実装済: 6 場面 (vote_result / launch_ready / ipat_login_required / ipat_login_complete / launch_failure / ipat_session_expired / ipat_start_failure / target_save_failure / daily_plan_summary / session_recovery_attempted/succeeded/failed)
- 🟢 実機発話確認済: Microsoft Haruka Desktop (ja-JP) / 受付番号 1 桁ずつ kana 化

**web 自動投票コントロールパネル** (Session 139 新規, 横断):
- 🟢 `/bankroll/auto` の `AutoVoteControl.tsx` — 当日 state 監視 (15s ポーリング) + dry-run/LIVE 起動 + 停止(halt)。SoT=Python state、web は API 越しに読む/起動するだけ
- 🟢 API: `/api/freebudget/status` (fs 読みのみ) / `/start` (単発パス SSE、LIVE は二重ゲート) / `/halt` (当日 halt = 緊急ブレーキ)
- 🟢 scheduler `halt_day()` + `--halt` — web「停止」用 (live/dry 両 state に halted=True、SoT 単一窓口、安全ブレーキは dir 未作成でも mkdir して必ず効く)
- 🟢 **dry-run / 監視 = 無条件 GO** (シズネ Session139 2巡)。**web LIVE 実弾は将来「軽微🔴1点 (`vote_one_race --max-yen`) を直してから GO」**、当面の実弾は `freebudget_vote.bat`
- ★**認識合わせ**: web LIVE の「承認額」は実投票額の上限を保証しない (最新オッズで再計算=ふくだ哲学)。真の上限は config の **per_race=3000 / per_day=10000 ハードキャップ** ([shizune_review_session139_web_panel](./shizune_review_session139_web_panel.md))
- test: `test_freebudget_scheduler.py` に halt_day 6 件追加 (13 passed)

---

## 2. モジュール構成と責務

| モジュール | 責務 | 規模 | 詳細 |
|---|---|---|---|
| `target_clicker/launcher.py` | TARGET 起動 + 認証 dialog 自動進行 + IPAT 連動メニュー + Phase 4-C-full 復旧 | 1000+ 行 | [18](./18_TARGET_FULL_AUTOMATION.md) |
| `target_clicker/runner.py` | フル自動投票オーケストレータ (買い目 → FF CSV → menu → click → ledger) | 800+ 行 | [16](./16_TARGET_AUTOCLICK.md) |
| `target_clicker/auto_vote.py` | TARGET 投票確認ダイアログの検出・内容検証・自動 click + 受付番号取得 | 700+ 行 | [16 §1-4](./16_TARGET_AUTOCLICK.md) |
| `target_clicker/menu_runner.py` | TARGET メニュー操作 (FF CSV 読込 → 一括処理 → IPAT 投票起動) | 500+ 行 | [16 §10](./16_TARGET_AUTOCLICK.md) |
| `target_clicker/notify.py` | 投票後 TTS 音声通知 (pyttsx3 → SAPI 2段 fallback) | 300+ 行 | [17](./17_NOTIFICATION_LAYER.md) |
| `target_clicker/selective_loader.py` | selective_bets.json v2.0 スキーマ検証 (鮮度 / source / odds / race_id 16桁 / amount 100..1000) | 200 行 | (シズネ 🔴 J + Session 134 amount 検証) |
| `strategies/freebudget.py` | 1万円フリー予算 × ML×直前オッズ EV判定 × 1/4 Kelly cap 10% 案分 | 300 行 | (Session 134, [19 §1.5](./19_OOS_RUNBOOK.md)) |
| `target_clicker/ff_writer.py` | TARGET 買い目取り込み FF CSV ライタ (8 馬券種 / Shift-JIS / CRLF) | 200 行 | [16 §2](./16_TARGET_AUTOCLICK.md) |
| `purchase_ledger/writer.py` | ledger v2 portfolio + ticket 追記 + idempotency + 失敗系 event | 400+ 行 | [14](./14_LEDGER_SCHEMA.md) |
| `purchase_ledger/idempotency.py` | ticket / portfolio idempotency key 生成 (raw_legs 正規化) | 100 行 | [14 §4](./14_LEDGER_SCHEMA.md) |
| `utils/atomic_write.py` | tmp → fsync → os.replace + mkdir-based 排他ロック | 80 行 | (シズネ 🔴 K 対応) |
| `utils/jsonl_append.py` | JSONL 1 行 atomic 追記 (O_APPEND + fsync + lock) | 60 行 | (シズネ 🔴 K 対応) |

---

## 3. CLI エントリポイント早見表

| コマンド | 用途 | モード |
|---|---|---|
| `scripts\freebudget_gen.bat [date] [bankroll]` | **★ ラッパ: freebudget 生成 + シズネ🔴-1 目視チェック自動表示** (Session 134, OOS 朝の第一歩) | 本番準備 |
| `scripts\freebudget_vote.bat [date] [--confirm / --auto-launch --confirm]` | **★ ラッパ: freebudget_bets.json で投票** (デフォルト dry-run) | 本番 |
| `python -m ml.strategies.freebudget --date YYYY-MM-DD --bankroll 10000` | freebudget_bets.json 生成 (bat の中身、 直叩き用) | 本番準備 |
| `python -m ml.target_clicker.runner --from-json {date_dir}/freebudget_bets.json --confirm` | **★ freebudget 経路で投票** (--amount 不要、 bet.amount 優先) | 本番 |
| `python -m ml.target_clicker.runner --from-json {date_dir}/freebudget_bets.json --auto-launch --confirm` | **★ freebudget × Phase 4-A/B/C フル自動 — OOS 5/31 検証対象** | 本番 |
| `selective_vote.bat YYYY-MM-DD AMOUNT --confirm` | (フォールバック) selective_bets.json 経由の半自動 — 緊急時のみ | 本番 |
| `python -m ml.target_clicker.runner --from-date today --amount 100 --confirm` | (フォールバック) selective 統合 — 緊急時のみ | 本番 |
| `python -m ml.target_clicker.runner --bet SPEC --confirm` | 単発買い目投票 (spec = race_id:bet_type:horses:amount) | 本番 |
| `python -m ml.target_clicker --dry-run` | ダイアログ検出のみ (click なし) | 観察 |
| `python -m ml.target_clicker.launcher inspect-launch --duration 30` | TARGET 起動時 dialog を 30 秒間 dump | 観察 |
| `python -m ml.target_clicker.menu_runner inspect-batch` | 「買い目一括処理」 ウィンドウ Win32+UIA dual dump + メニュー全列挙 + スクショ | 観察 |
| `python -m ml.target_clicker.launcher detect-session-expired` | セッション切れ dialog 検知単独テスト | 観察 |
| `python -m ml.target_clicker.launcher recover-session [--race-id ID] [--no-notify] [--no-ledger]` | セッション切れ後の復旧 5-step 実行 (★ Step 4 暗証番号は手動) | 復旧 |
| `python -m ml.target_clicker.runner --say-test "TEXT"` | TTS 発話単独テスト | 観察 |

---

## 4. 安全機構 (シズネ累積防御層)

「便利さより安全性」 を構造的に強制する 8 層:

1. **暗証番号自動入力禁止** (Session 131 シズネ 🔴 C)
   - test_launcher_no_password.py 14 tests / AST (keyring/getpass/pyperclip 禁止) + regex (send_keys/type_keys/set_edit_text に password 系) + 環境変数 (`IPAT_PASSWORD` 系禁止)
   - CI 強制 = 将来の自分の「便利だから自動入力しよう」 を構造阻止

2. **whitelist v2 厳格化** (Session 131 シズネ 🔴 B)
   - `abort_on_unknown=True` がデフォルト、 寛容モードは target_version 不一致時のみ
   - `verified_by` 必須化 (v2)、 未指定で stderr WARNING (Session 132 🟡-5)
   - unknown dialog 検知 → 即 abort + `TARGET_DIALOG_UNKNOWN` event 記録

3. **当日プラン音声読み上げゲート** (Session 131 シズネ 🔴 A)
   - 暗証番号入力 **前** に投票内容を音声読み上げ
   - 二重認証 = (IPAT 認証) + (内容承認)。 違和感あれば入力しないだけで abort

4. **pre-flight session 検証** (Session 131 シズネ 🔴 D / Phase 4-C-min)
   - selective_vote.bat 走り出し **前** に IPAT セッション有効性検証
   - NG 時 → abort + `IPAT_SESSION_EXPIRED` event 記録 + 音声通知

5. **事後検知 + recover-session 手動コマンド化** (Session 132)
   - 投票後セッション切れを検知 → exit 5 で abort、 自動継続なし
   - 復旧は ふくだが `launcher.py recover-session` を **手動で叩く** = 思考の隙間を入れる
   - 復旧後の音声文面「ただし未投票分の自動再送はしません」 で二重投票誘発を構造的に塞ぐ (Session 132 🔴-1 A/C)

6. **ledger v2 + idempotency + SHA256 追記台帳** (Session 129)
   - portfolio + ticket idempotency key で再投票重複検知
   - `_index.jsonl` SHA256 追記で改ざん検知
   - events_{YYYY-MM}.jsonl 別出し (肥大化対策)

7. **JSONL fsync + mkdir-based ロック** (Session 129 シズネ 🔴 K)
   - atomic_write / jsonl_append で 100 並行書き込みでロスト 0 件確認
   - 監査ログ改ざん防止

8. **起動時 SESSION_EXPIRED チェック** (Session 132 シズネ 🔴-1 B / Session 133 修正B = 未実装)
   - `--auto-launch` 起動時に直近 1h `IPAT_SESSION_EXPIRED_POSTVOTE` event 確認
   - あれば音声警告 + `--ignore-recent-session-expired` 明示無ければ abort (30 分)
   - 二重投票防止の最終層 — **OOS 前必須**

---

## 5. テスト現況 (82 tests / 全 PASS)

| ファイル | 件数 | 検証内容 |
|---|---|---|
| `tests/test_launcher_no_password.py` | 14 | 暗証番号自動化禁止 CI 強制 (AST + regex + env) |
| `tests/test_launcher_recovery.py` | 23 | Phase 4-C-full 復旧フロー (Desktop / open_ipat_menu / wait_* / precheck monkeypatch) |
| `tests/test_runner_session_expired_check.py` | 17 | 起動時 SESSION_EXPIRED チェック (Session 133 修正B) |
| `tests/test_launcher_verified_by.py` | 10 | whitelist v2 / session_expired_patterns v2 で verified_by 警告動作 |
| `tests/test_strategy_freebudget.py` | 10 | freebudget 抽出 + Kelly + cap + truncate + JSON schema 互換 (Session 134) |
| `tests/test_selective_loader_amount.py` | 8 | amount 検証 + freebudget source whitelist + 他 source で amount abort (Session 134) |
| `tests/test_notify_daily_plan_amount.py` | 7 | build_daily_plan_text 金額読み上げ (Session 134 シズネ 🔴-2) |

**実行コマンド**:
```powershell
./.venv/Scripts/python.exe -m pytest ml/tests/test_launcher_no_password.py ml/tests/test_launcher_recovery.py ml/tests/test_runner_session_expired_check.py ml/tests/test_launcher_verified_by.py ml/tests/test_strategy_freebudget.py ml/tests/test_selective_loader_amount.py ml/tests/test_notify_daily_plan_amount.py -v
```

89 tests / 0.82 秒 (monkeypatch ベース、 pywinauto 実機不要)

---

## 6. 既知の不明変数 (OOS 確定待ち 6 件)

[19_OOS_RUNBOOK](./19_OOS_RUNBOOK.md) §0.1 より:

| # | 不明変数 | 確定方法 | 確定先 |
|---|---|---|---|
| 1 | TARGET 起動時の認証ダイアログ群 | `inspect-launch` で 30 秒 dump | `launch_dialogs.json` v2 |
| 2 | IPAT セッション切れダイアログ | 暗証番号入力後 60 秒放置 → `detect-session-expired` | `session_expired_patterns.json` v2 |
| 3 | セッション切れ時の多重構造 (1段 / 2段以上) | 上記 #2 と同時観察 | 19 §6 に記録 |
| 4 | `_read_dialog_body` max_descendants=50 で IPAT Web View 本文を取りきれるか | inspect dump の descendant 数目視 | 取りこぼしあれば 200 に拡張 |
| 5 | `result_dialog_timeout` 経路の再現条件 | 投票 click 後にネット切断で再現 (任意) | 19 §6 に記録 |
| 6 | verify loop end-to-end (検知 → 音声 → ledger → audit → recover → RECOVERED event) を 1 件以上実機観測 | #2 シナリオから連続実行 | 19 §5 で観測ログ |

**反映先**: いずれも OOS 後に該当 JSON / 設計書に値を追記、 verified_by=fukuda + 当日日付で git commit。

---

## 7. 残タスク優先度 (Session 133 シズネレビュー振り分け済)

> シズネレビュー結果は [shizune_review_session133_oos_runbook.md](./shizune_review_session133_oos_runbook.md) 参照 (🟢9/🟡7/🔴3 「条件付き GO」 → 6 件潰しで「無条件 GO」)

### ★★★ OOS 前必須 (5/29 夜まで) — 全 6 件 Session 133 内で完了済

> シズネは「OOS 前必須」 と判定したが、 コード 3 件は **Session 132/133 で既に実装済** だったことが Session 133 検証で判明。 仮振り分け時 (Session 132 完了状態の MEMORY を基準) で「未実装」 と誤認識していた。 実態確認 + test 64 件 PASS で 「無条件 GO」 ステータス。

**ドキュメント修正** (Session 133 内で 3 件対応済):
- ✅ **🔴-1 §6.4.b 行動アンチパターン追記** (10 分) — 「もう一回」「取り戻し」「気が大きくなる」「面倒くさい」「観察者疲れ」 5 衝動を構造的歯止め化
- ✅ **🔴-2 §3.4/§6.3 PC スリープ復帰 SOP + §0.1 不明変数 #7** (15 分) — 5/31 朝に必発する修正B 誤発火シナリオに先回り
- ✅ **🔴-3 §7.1/§7.2 設計検証 9 軸再構成 + §7.3 ROI 副次降格** (30 分) — 「儲かったから GO」 経路を構造遮断

**コード修正** (Session 132/133 で既に実装済 / Session 133 内で確認):
- ✅ **Session 132 🟡-2 phase 文字列定数化** — `auto_vote.py:84-92` で `SESSION_EXPIRED_PHASE_*` 定数 + `VOTE_ALREADY_CLICKED_PHASES` frozenset を Session 132 で導入済。 production code 側に str literal 比較は残存なし
- ✅ **Session 132 🟡-5(a) verified_by 欠落 WARNING** — `launcher.py:185-191` (load_dialog_whitelist_v2) + `launcher.py:1019-1024` (load_session_expired_patterns) に WARNING (fail-open) 実装済
- ✅ **Session 133 修正B 起動時 SESSION_EXPIRED チェック** — `runner.py:255-426` に `_check_recent_session_expired_events()` + Step 0-safety-gate + `--ignore-recent-session-expired` / `--session-expired-window-min` フラグ + exit code 8 + `notify_recent_session_expired_warning` まで配線済、 test 17 件 PASS

### ★★ OOS 中対応 (5/30-31 観察 + Session 133-134 内)

- ✅ **シズネ独自観点 4 件** (Session 133 内対応済):
  - ✅ 19 §1.7 当日精神状態 self-check (5 分)
  - ✅ 19 §6.0 「3 秒ルール」 + shizune 呼出 prompt (10 分)
  - ✅ 19 §6.6 kill switch / cooldown 記述 (20 分)
  - ✅ 19 §7.6 + 18 §1.5 で 6/6 OFF 練習日固定 (3 分)
- **Session 132 🟡-8** — `_close_session_expired_dialog` 多段モーダル対応 — シズネ「OOS 観察次第で Session 134 即対応」
- **Session 132 🟡-5(b)** — `verified_by` 欠落 abort 化 — シズネ「Session 134」

### ★ 中長期 (Session 134+)

- **Phase 4-D** — TARGET セッション継続管理 (Step 6+)
- **ledger v2 settle 拡張** — 払戻 / SETTLED event 取得 (JRA-VAN レース確定後の自動突合と同時)
- **§6.5 PC スリープ復帰「擬似 / 本物」 判別ガイド** — 19 §6.5 (Session 134 で実機観察ベース整備)
- **session-history.md offload** — Session 127 を [[session-history]] へ移動 (MEMORY.md 圧縮、 session-archive スキル)
- **🟡-A/D/E/F/G** (シズネ Session 133 レビュー §1 評価表) — OOS 後対応

---

## 8. 関連設計書クロスリファレンス

| ファイル | 何が分かるか |
|---|---|
| [14_LEDGER_SCHEMA.md](./14_LEDGER_SCHEMA.md) | ledger v2 スキーマ / portfolio_id / 30 イベント定義 / SHA256 追記台帳 |
| [16_TARGET_AUTOCLICK.md](./16_TARGET_AUTOCLICK.md) | pywinauto 投票ダイアログ自動 click + menu 戦略 + Session 128 実証 |
| [17_NOTIFICATION_LAYER.md](./17_NOTIFICATION_LAYER.md) | TTS 通知 (Microsoft Haruka) + 受付番号 kana 化 |
| [18_TARGET_FULL_AUTOMATION.md](./18_TARGET_FULL_AUTOMATION.md) | TARGET 起動 + IPAT 連動 + Phase 4-A/B/C-min/C-full 全設計 |
| [19_OOS_RUNBOOK.md](./19_OOS_RUNBOOK.md) | 5/30-31 段階的検証手順 + GO/NO-GO 判定 + 失敗時 SOP |
| [shizune_review_session129.md](./shizune_review_session129.md) | 🔴 I/J/K 指摘 (per_race_max_yen / selective schema / JSONL ロック) |
| [shizune_review_session130_doc18.md](./shizune_review_session130_doc18.md) | 🔴 A/B/C/D 指摘 (二重認証 / whitelist v2 / 暗証番号防御 / pre-flight) |
| [shizune_review_session132_phase4c_full.md](./shizune_review_session132_phase4c_full.md) | 🔴-1 (recover-session 二重投票リスク) + 🟡-2/5/8/10 |

---

## 9. 更新履歴

| Session | 日付 | 主変更 |
|---|---|---|
| 133 | 2026-05-26 | 新規作成 (Session 128-132 累積状態のスナップショット) |
| 134 | 2026-05-28 | freebudget 戦略追加 (1万円フリー予算 + Kelly案分 + amount 検証)、 シズネレビュー 🔴 4 件全潰し (config 衝突 / 金額読み上げ / 払戻タイムラグ / Themis 整合)、 テスト 64→89 件、 CLI 早見表更新 |
| 139 | 2026-05-31 | **web 自動投票コントロールパネル** 追加 (`/bankroll/auto` + `/api/freebudget/{status,start,halt}` + scheduler `halt_day`)。 シズネ 2 巡 (🔴2+🟡5 全潰し) → dry-run/監視は無条件GO・web LIVE は軽微🔴1点を本稼働前に。認識合わせ=承認額は上限保証でなく config cap が安全弁 ([shizune_review_session139_web_panel](./shizune_review_session139_web_panel.md)) |

**次回更新タイミング**:
- 5/30-31 OOS 結果反映 (Session 135 内、 §6 不明変数を確定値で更新 + §7 残タスクを再振り分け)
- Phase 4-D 着手時 (§1 マトリクスに行追加)
- freebudget Phase 2 着手時 (収支管理機能から残高自動取得)

---

> 「ドキュメント体系は 19 本揃った。 残るは『何ができて何がまだか』 を 1 枚で示すこの 20 番。 シズネに渡し、 OOS に持ち込み、 月曜の振り返りで更新する。 ふくだが朝に開いて状態確認、 次セッションのカカシが残タスク表で次の一手を即決定する単一エントリ。」 — カカシ (Session 133)

# 19. OOS RUNBOOK — 5/30-31 段階的検証手順書

> **作成日**: 2026-05-25 (Session 133 起草) / **改訂**: 2026-05-28 (Session 134 — 1万円フリー予算路線追加)
> **対象**: 2026-05-30 (土) 〜 2026-05-31 (日) の Out-Of-Sample 実機検証
> **目的**: Session 131-133 で骨格実装した Phase 4-A/B/C-min/C-full を実機で verify、 「**無条件 GO**」 判定を取って週次運用フェーズに移行する
> **Session 134 変更**: amount=100 路線を廃止し、 **1万円フリー予算 × ML×直前オッズ EV判定 × 1/4 Kelly cap 10% 案分** (freebudget_bets.json 経由) に置換。 5/30=10000円スタート / 5/31=5/30終了残高ベースの日跨ぎ更新。 当日中はバンクロール固定 (シズネ「動的調整なし」 原則維持)
> **担当**: ふくだ (オペレーション) / カカシ (障害時技術判断) / シズネ (リスク判定)
> **関連**: [16_TARGET_AUTOCLICK.md](./16_TARGET_AUTOCLICK.md) / [17_NOTIFICATION_LAYER.md](./17_NOTIFICATION_LAYER.md) / [18_TARGET_FULL_AUTOMATION.md](./18_TARGET_FULL_AUTOMATION.md) / [shizune_review_session132_phase4c_full.md](./shizune_review_session132_phase4c_full.md)

---

## 0. はじめに

### 0.1 OOS 検証で確定すべき「不明変数」 6 件

Session 131-133 でコード骨格は完成、 ただし以下 6 件は**実機 TARGET / IPAT に当てないと値が確定しない**:

| # | 不明変数 | 確定方法 | 確定先ファイル |
|---|---|---|---|
| 1 | TARGET 起動時の認証ダイアログ群 | `inspect-launch` で 30 秒間 dump | `data3/userdata/target_clicker/launch_dialogs.json` (v2) |
| 2 | IPAT セッション切れダイアログ | 暗証番号入力後 60 秒放置 → 自然タイムアウト誘発 → `detect-session-expired` で確認 | `data3/userdata/target_clicker/session_expired_patterns.json` (v2) |
| 3 | セッション切れ時のダイアログ多重構造 (1 段 / 2 段以上) | 上記 #2 と同時に観察 | (本書 §6 に運用知見として記録) |
| 4 | `_read_dialog_body` max_descendants=50 で IPAT Web View 本文を取りきれるか | inspect-launch dump の descendant 数を目視確認 | (取りこぼしあれば 🟡-6 で 200 に拡張) |
| 5 | `result_dialog_timeout` 経路の再現条件 | 投票 click 後にネットワーク遮断で再現テスト (任意) | (本書 §6 に運用知見) |
| 6 | **verify loop** end-to-end (検知 → 音声 → ledger event → audit JSONL → recover → RECOVERED event) を 1 件以上実機観測 | 上記 #2 のシナリオから連続実行 | (本書 §5 で観測ログ記録) |
| 7 | PC スリープ復帰時の IPAT セッション挙動 (Wake-up でセッション維持されるか / 別事象として切れるか) | 5/30 PM 終了後にスリープ → 5/31 AM 復帰で観測 | §6.5 (Session 134 で整備) |

### 0.2 段階的アプローチ (シズネ Session 133 推奨)

```
[土曜 AM]  inspect-launch でダイアログ確定 (低リスク観察、 投票しない)
       ↓
[土曜 PM]  selective_vote.bat (Session 128 同等の半自動運用、 --auto-launch なし)
       ↓ GO 判定後
[日曜 AM]  selective_vote.bat --auto-launch (フル自動)
       ↓
[日曜 PM]  verify loop 観測 + 終了後の振り返り (§7)
```

**「徐々に自動度を上げる」** ことで、 不確実な部分でつまずいても投票が止まらない構造を維持。 「土曜 AM = データ取り」 → 「土曜 PM = いつも通り」 → 「日曜 AM = 新機能試運転」。

### 0.3 GO / NO-GO 判定基準

各フェーズ終了時に以下を確認:

- ✅ **GO 条件**: success criteria 全項目達成 + ledger event 整合 + 音声通知正常
- ❌ **NO-GO 条件**: いずれか 1 件でも:
  - TARGET 起動失敗 (Phase 4-A / `LaunchResult.success=False`)
  - 想定外ダイアログ (`TARGET_DIALOG_UNKNOWN` event)
  - 投票内容と selective_bets.json 不一致 (max_yen/max_bets 違反)
  - ledger 書込み 1 件以上失敗 (stderr に `[ledger]` エラー)
  - 復旧フローが Step 1-5 のいずれかで永続的に止まる
  - シズネ「これは止めた方がいい」 判断

NO-GO 判定時は **次フェーズに進まず、 半自動運用 (Session 128 同等) に戻す**。

---

## 1. 事前準備 (5/29 金曜 夜 Dry-run チェックリスト)

OOS 当日に向けて、 5/29 夜にローカルで以下を確認。 1 件でも fail なら土曜実機検証は **半自動運用にダウングレード** (--auto-launch なしで土曜 AM/PM 両方やる)。

### 1.1 環境チェック

```powershell
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2

# Python 環境
./.venv/Scripts/python.exe -V                       # 3.11.x 確認
./.venv/Scripts/python.exe -c "import pywinauto; print(pywinauto.__version__)"  # 0.6.9 確認
./.venv/Scripts/python.exe -c "import pyttsx3; print(pyttsx3.__file__)"         # import 通る確認
```

- [ ] Python 3.11.x
- [ ] pywinauto 0.6.9 import OK
- [ ] pyttsx3 import OK

### 1.2 テスト全 PASS 確認

```powershell
./.venv/Scripts/python.exe -m pytest ml/tests/test_launcher_no_password.py ml/tests/test_launcher_recovery.py ml/tests/test_runner_session_expired_check.py ml/tests/test_launcher_verified_by.py -v
```

- [ ] **64 tests / 全 PASS** (14 + 23 + 17 + 10)
- [ ] no_password 14 tests = 暗証番号自動化禁止が CI 強制されている確認
- [ ] verified_by 10 tests = whitelist v2 / session_expired_patterns v2 で警告動作確認

### 1.3 TTS 音声テスト (Session 129 動作確認)

```powershell
./.venv/Scripts/python.exe -m ml.target_clicker.runner --say-test "テスト発話。 受付番号 ゼロ ゼロ 四 五。 投票完了"
```

- [ ] スピーカーから日本語発話 (ja-JP voice)
- [ ] 「ゼロ ゼロ 四 五」 が 1 桁ずつ読まれる (Session 129 受付番号 kana 変換動作確認)
- [ ] Microsoft Haruka Desktop or 他 ja-JP voice が使用される

### 1.4 当日プラン読み上げ Dry-run (シズネ 🔴 A 動作確認)

```powershell
# 5/29 時点の selective_bets.json (前回開催分) で読み上げテスト
./.venv/Scripts/python.exe -c @"
from ml.target_clicker.notify import build_daily_plan_text
text = build_daily_plan_text(
    bets_summary=[
        {'race_id': '2026053108010101', 'umaban': 6, 'venue_name': '新潟', 'race_number': 8},
        {'race_id': '2026053106010801', 'umaban': 1, 'venue_name': '京都', 'race_number': 8},
        {'race_id': '2026053106010301', 'umaban': 3, 'venue_name': '京都', 'race_number': 8},
    ],
    total_yen=3000,
)
print(text)
"@
```

- [ ] 「本日の投票プラン。 新潟8R 単勝 6 番、 …」 のような出力
- [ ] 「合計 3 件、 3000円。 暗証番号を入力すると投票を開始します。」 で終わる

### 1.5 ML 推論 + freebudget_bets.json 生成確認 (5/30 当日の前提条件)

5/29 夜 〜 5/30 早朝までに以下が揃っていること:

```powershell
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2

# 5/30 のデータが用意されているか
ls c:/KEIBA-CICD/data3/races/2026/05/30/

# predictions.json が vb_refresh 後の最新オッズで更新済か (generated_at 確認)
./.venv/Scripts/python.exe -c "import json; d=json.load(open('c:/KEIBA-CICD/data3/races/2026/05/30/predictions.json','r',encoding='utf-8')); print('generated_at:', d.get('generated_at')); print('n_races:', len(d.get('races', [])))"

# ★ freebudget_bets.json を生成 (1万円バンクロール / 1/4 Kelly / 1馬上限10%)
./.venv/Scripts/python.exe -m ml.strategies.freebudget --date 2026-05-30 --bankroll 10000

# 生成内容確認
ls c:/KEIBA-CICD/data3/races/2026/05/30/freebudget_bets.json
```

- [ ] `data3/races/2026/05/30/predictions.json` 存在
- [ ] `predictions.json` の `generated_at` が 6h 以内 (= vb_refresh が直前まで動いていた)
- [ ] `freebudget_bets.json` 生成済 (source=`freebudget_kelly_1q`, version=`2.0`)
- [ ] `n_bets` が 0 件でない (0 件なら VB Floor を一切通っていない = ML 出力 or オッズ取得異常を疑う)
- [ ] `n_bets` が 30 件を超えていない (超過なら preset を見直し、 or `--per-bet-cap-pct 0.05` 等で絞る)
- [ ] `total_yen` ≤ `bankroll` (= 切り捨て動作確認)
- [ ] 各 bet の `amount` が 100 ≤ amount ≤ 1000、 100円単位

**★ Session 134 シズネ 🔴-1 必須目視チェック** (5/30 9:00 朝 / runner 起動前):

config.json の `per_race_max_yen=3000` / `per_day_max_yen=10000` と freebudget 出力の整合性を 1 分で確認:

```powershell
# freebudget_bets.json の各 race_id ごとの amount 合計と全体 total_yen を表示
./.venv/Scripts/python.exe -c @"
import json
from collections import defaultdict
p = 'c:/KEIBA-CICD/data3/races/2026/05/30/freebudget_bets.json'
d = json.load(open(p, encoding='utf-8'))
per_race = defaultdict(int)
for b in d['bets']:
    per_race[b['race_id']] += b['amount']
print(f'total: {sum(per_race.values())}円 (per_day_max=10000)')
for rid, amt in per_race.items():
    flag = ' ★OVER' if amt > 3000 else ''
    print(f'  {rid}: {amt}円{flag} (per_race_max=3000)')
"@
```

- [ ] **各 race_id の amount 合計 ≤ 3000 円** (= per_race_max_yen)。 ★OVER 表示があれば
      freebudget を `--per-bet-cap-pct 0.05` で再生成 (1馬上限 500 円 → 同一レース 2 頭で 1000 円以下)
- [ ] **全体 total_yen ≤ 10000 円** (= per_day_max_yen)。 freebudget の truncate ロジックで自動担保されるはずだが目視確認
- [ ] どれかが NG なら **config.json を本番中に弄らない** (シズネ「動的調整なし」 原則)。
      freebudget 側で再生成 or 半自動運用 (selective_vote.bat フォールバック) に降格

不足してれば `keiba-data-prep` skill 走らせて predictions 再生成 → freebudget 再実行。

**5/31 朝の手順 (日跨ぎバンクロール更新)** — シズネ 🔴-3 で改訂:

⚠️ **重要**: 5/31 朝に IPAT サイトを開いた時の残高表示は **使わない**。 5/30 PM の払戻が翌朝までに反映されるタイムラグで、 本来の bankroll より高く見える = それを `--bankroll` に渡すと「動的調整あり」 になる罠。 ✓ 必ず以下の手順:

```powershell
# 例: 5/30 23:59 時点の IPAT 残高 = 9000 円 (スクショ保存済)
./.venv/Scripts/python.exe -m ml.strategies.freebudget --date 2026-05-31 --bankroll 9000

# or オペレーションが面倒なら 10000 円固定 (= 1万円フリー予算を 2 日続ける、 推奨度: シンプルさ ★★)
./.venv/Scripts/python.exe -m ml.strategies.freebudget --date 2026-05-31 --bankroll 10000
```

- [ ] **5/30 23:59 までに IPAT サイトを開いてスクリーンショット保存** (5/30 中の確定払戻まで反映された状態)
- [ ] その時点の表示残高を **メモして 5/31 朝の `--bankroll` に渡す**
- [ ] **5/30 23:59 〜 5/31 朝の間に追加で反映された払戻は 5/31 の bankroll に含めない**
      (含めると「動的調整」 = シズネ「動的調整なし」 原則違反)
- [ ] **「5/31 朝の表示残高」 は使わない** (動的調整の罠を構造的に塞ぐ)
- [ ] 上記運用が面倒なら **5/31 も 10000 円固定** (= 1万円フリー予算を 2 日続ける)
- [ ] 当日中 (5/31 中) は固定バンクロール = シズネ「動的調整なし」 原則維持
- [ ] 「儲かったから 5/31 中に増額」 はやらない (§6.4.b 行動アンチパターン参照)

### 1.6 bankroll 設定確認

```powershell
cat c:/KEIBA-CICD/data3/userdata/bankroll/config.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

- [ ] `limit_mode: "absolute"`
- [ ] `per_day_max_yen` が想定額 (例: 10000) で設定済
- [ ] `per_race_max_yen` も同様
- [ ] race_overrides に古い override が残ってないか確認

### 1.7 当日精神状態 self-check (5/30 朝、 selective_vote.bat 叩く前) — シズネ独自観点

以下 3 つを **声に出して** 確認:

- [ ] 「いま、 selective_bets.json の中身を 1 件以上目で見たか?」 (見てなければ §1.5 やり直し)
- [ ] 「いま、 今日の投資総額を口で言えるか?」 (言えなければ §1.6 bankroll 確認)
- [ ] 「いま、 何かトラブルが起きたら最初に何を確認するか?」 (答えが「ledger と IPAT 履歴」 で出れば OK、 出なければ §6.3 を一度読み返してから始める)

3 つどれかが詰まったら **30 分待つ or コーヒー 1 杯飲んでから** start。 朝の 5 分の遅れより、 寝不足の状態で `--auto-launch` を叩いた事故の方が痛い。

> シズネ原則 5 (「勢いで決めたい発言には立ち止まる」) のセルフサービス化。 寝不足 / 朝食前 / 初回投入の興奮 / 通知音連発による感覚過負荷 — 全部 OOS 当日の現実シナリオ。

---

## 2. 5/30 (土) AM フェーズ — inspect-launch でダイアログ確定

### 2.1 目的

実機 TARGET 起動時のダイアログを 30 秒間 dump して `launch_dialogs.json` (v2) を確定する。 **投票はしない、 観察のみ**。

### 2.2 手順

```powershell
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2

# ① TARGET を手動で完全終了 (タスクマネージャで target_jv.exe 確認)
#    → 既起動チェックの動作を確認するため

# ② inspect-launch (30 秒間ダイアログ収集)
./.venv/Scripts/python.exe -m ml.target_clicker.launcher inspect-launch --duration 30
```

`inspect-launch` 実行と並行して**手動で TARGET を起動**:
1. デスクトップから TARGET frontier JV を起動 (ふくだの普段のショートカット)
2. 出てくる認証ダイアログを **意図的に放置** (自動 dismiss させない)
3. 30 秒経過後、 JSON ファイルが書き出される

### 2.3 確認

```powershell
# 最新の inspect JSON を確認
ls -t c:/KEIBA-CICD/data3/userdata/target_clicker/inspect/launch_*.json | Select-Object -First 1
```

- [ ] JSON 内に visible ダイアログ全件が記録されている
- [ ] title / class / handle / buttons[] / descendants[] が揃っている
- [ ] スクリーンショット (.png) も同フォルダに存在

### 2.4 `launch_dialogs.json` v2 構築

JSON dump から「自動進行して OK な dialogs」 を選んで以下のフォーマットで配置:

```json
{
  "version": "1.0",
  "verified_at": "2026-05-30T09:30:00+09:00",
  "verified_by": "fukuda",
  "target_version": "TARGET frontier JV  Ver6.21  Rev002",
  "dialogs": [
    {
      "title_re": "^TARGET frontier JV$",
      "buttons": ["OK"],
      "purpose": "ライセンス情報確認"
    }
  ]
}
```

配置先: `c:/KEIBA-CICD/data3/userdata/target_clicker/launch_dialogs.json`

- [ ] `verified_by` 必須 (Session 133 🟡-5 で WARNING 出る)
- [ ] `target_version` は実機ウィンドウタイトルからコピー
- [ ] `dialogs[]` に確実に進行 OK なものだけを追加 (迷ったら入れない、 abort された方が安全)

### 2.5 動作確認

```powershell
# v2 スキーマで読まれることを確認
./.venv/Scripts/python.exe -c "from ml.target_clicker.launcher import load_dialog_whitelist_v2; cfg = load_dialog_whitelist_v2(); print(f'source={cfg.source} verified_by={cfg.verified_by} dialogs={len(cfg.dialogs)}')"
```

- [ ] `source=file verified_by=fukuda dialogs=N` (N ≥ 1)
- [ ] WARNING が stderr に出ていない

### 2.6 GO 判定

- ✅ GO: 全項目チェック + dialogs[] が現実的な件数 (1-5 件)
- ❌ NO-GO: inspect-launch がクラッシュ / dialog 0 件 / 想定外の dialog (例: アップデート確認が出る)
  - NO-GO 時は **土曜 PM フェーズには進まない**、 ふくだ手動で TARGET 操作する従来運用に戻す

---

## 3. 5/30 (土) PM フェーズ — 半自動運用 (Session 128 同等)

### 3.1 目的

`--auto-launch` を**使わずに** Session 128 で実証済の半自動運用を回す。 Session 129-133 で追加した「通知 + ledger v2 + selective_loader + 安全弁」 が本番経路で動くか OOS 確認。

### 3.2 手順

```powershell
# ① ふくだが手動で:
#    - TARGET 起動
#    - ライセンス確認 OK
#    - メニュー「ファイル → IPAT で投票する」
#    - 暗証番号入力 → ログイン

# ② IPAT メイン画面到達後、 bat ラッパで投票 (Session 134 推奨経路)
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2/scripts

# 朝イチ: 生成 + 目視チェック (§1.5 のチェックリストを bat が自動表示)
freebudget_gen.bat 2026-05-30 10000

#   ↓ per_race<=3000 / total<=10000 を目視

# 半自動投票 (--confirm)
freebudget_vote.bat 2026-05-30 --confirm
```

bat の中身は runner.py 直叩き (同等):
```powershell
./.venv/Scripts/python.exe -m ml.target_clicker.runner \
    --from-json c:/KEIBA-CICD/data3/races/2026/05/30/freebudget_bets.json \
    --confirm
```

**重要**: `--amount` は省略 (freebudget_bets.json の各 bet に amount フィールドが入っており、 runner.py L162-170 で bet.amount を優先する)。

参考: 半自動の安全弁として **既存 selective_vote.bat 経路も残してある** (Session 128 同等):
```cmd
selective_vote.bat 2026-05-30 100 --confirm    # ← selective_bets.json 経由 (緊急時のフォールバック)
```
ただし 5/30-31 の主経路は **freebudget_bets.json**。 selective 経路を使うと「ML × オッズ EV判定」 ではなく「重賞+1勝穴」 戦略になる点に注意。

### 3.3 観察

- [ ] 投票ダイアログ検出 → click → 受付番号取得 → OK → F10 + はい (一連自動)
- [ ] 受付番号が音声で読み上げられる ("受付番号 ゼロ ゼロ 五 N。 投票完了")
- [ ] `audit_2026-05.jsonl` の最終行に notify_text / notify_spoken が記録される
- [ ] ledger `purchase_ledger/2026-05-30.json` に portfolio + ticket 追記
- [ ] events_2026-05.jsonl に APPROVED / FF_WRITTEN / TARGET_IMPORTED / IPAT_CONFIRMED 4 種
- [ ] TARGET 保存 (F10 + はい) も成功 = `TARGET_SAVE_FAILED` event は出ない

### 3.4 想定外時の対応

| 症状 | 即時アクション | 後追い |
|---|---|---|
| `TARGET_DIALOG_UNKNOWN` event | runner.py が exit 7 で abort、 ふくだ手動で dialog を進めて再投票 | `launch_dialogs.json` に追加要否を後で判断 |
| `IPAT_START_FAILED` event (menu_runner step3 全戦略失敗) | TARGET ウィンドウで手動で「IPAT投票」 をクリック → ダイアログ表示後に再度 selective_vote.bat | inspect-batch で cmd_id 確認、 menu_runner 修正候補 |
| `TARGET_SAVE_FAILED` event | IPAT は既に受付済 = TARGET ウィンドウで F10 + はい を手動押下 (or 無視 = TARGET 履歴のみ未保存) | rollback 不能、 ledger payload の manual_action_required 通り |
| 投票ダイアログ 60 秒 timeout | IPAT 認証画面に戻されていないか確認、 セッション切れの可能性 | Phase 4-C-full 復旧フロー or 手動再ログイン |
| TTS 発話しない | スピーカー / ボリューム確認、 `--no-notify` で投票自体は止めない | Session 134 で notify 経路再調査 |
| OOS 中の意図せぬ PC スリープ / Wi-Fi 切断 | runner.py 強制停止 (Ctrl+C) → 復帰後は IPAT Web で残高目視確認 → 半自動運用に戻る | §6.3 PC スリープ復帰行 + §6.5 (Session 134 整備予定) を参照 |

### 3.5 GO 判定

- ✅ GO: 1 〜 N レース投票完了 + ledger 整合 + 受付番号 IPAT 履歴と一致
  - IPAT サイトで投票履歴を目視確認 (4 桁受付番号と TARGET 履歴の照合)
- ❌ NO-GO: 上記いずれか:
  - 投票後 IPAT 履歴にない受付番号
  - ledger と IPAT 履歴で金額不一致
  - 「TARGET_DIALOG_UNKNOWN」 が 2 回以上

NO-GO 時は **日曜 AM の --auto-launch は中止**、 もう一度半自動で日曜回す。

---

## 4. 5/31 (日) AM フェーズ — `--auto-launch` 本番投入

### 4.1 前提条件

- ✅ 5/30 土曜 AM/PM 両フェーズ GO 判定済
- ✅ `launch_dialogs.json` v2 確定済 (verified_by=fukuda)
- ✅ IPAT 暗証番号は手元 (= ふくだの記憶) 準備済
- ✅ Dry-run で当日プラン読み上げ動作確認済

### 4.2 手順

**5/31 朝の実行順序** (シズネ Session 134 4.6 推奨、 修正B 起動時チェックとの整合):

1. PC 復帰確認 — スリープからの復帰直後は §6.3 PC スリープ復帰行を参照、 IPAT セッション状態が不明なら半自動運用に降格判断
2. **`freebudget_bets.json` 生成** (§1.5 の 5/31 朝の手順、 `--bankroll` 値は **5/30 23:59 スクショ基準**)
3. **生成内容の目視確認** (各 race_id ごとの amount 合計 ≤ 3000円 / total_yen ≤ 10000円、 §1.5 ★Session 134 必須目視チェック参照)
4. **§1.7 当日精神状態 self-check** (声に出して 3 問)
5. `--auto-launch --confirm` 実行 (= 修正B 起動時 SESSION_EXPIRED チェックがここで発火する)

```powershell
# ① ふくだ:
#    - TARGET 完全終了 (タスクマネージャ確認)
#    - PC のサウンド ON、 イヤホンよりスピーカー推奨
#    - 前日 5/30 23:59 残高スクショベースで 5/31 用 freebudget_bets.json 生成済 (§1.5 参照)
#    - 目視チェック + self-check 完了

# ② bat ラッパでフル自動 (Session 134 推奨経路)
cd c:/KEIBA-CICD/_keiba/keiba-cicd-core/keiba-v2/scripts

# 生成 + 目視 (5/30 23:59 残高スクショ基準の bankroll を渡す。 例: 9000)
freebudget_gen.bat 2026-05-31 9000

#   ↓ per_race<=3000 / total<=10000 を目視 + §1.7 self-check

# フル自動投票 (--auto-launch --confirm)
freebudget_vote.bat 2026-05-31 --auto-launch --confirm
```

bat の中身は runner.py 直叩き (同等、 launch/login timeout は bat 内デフォルト):
```powershell
./.venv/Scripts/python.exe -m ml.target_clicker.runner \
    --from-json c:/KEIBA-CICD/data3/races/2026/05/31/freebudget_bets.json \
    --auto-launch \
    --launch-timeout 30 \
    --login-timeout 180 \
    --confirm
```

### 4.3 実行フロー観察 (この順で進む)

1. **Step 0-safety-gate** (Session 133 修正B): 直近 1h SESSION_EXPIRED チェック → なければ進む
2. **Step 0-launch**: TARGET 起動 → 認証ダイアログ自動進行 → 音声「TARGET の起動が完了しました…」
3. **Step 0-ipat-menu**: cmd_id WM_COMMAND で IPAT 連動メニュー起動
4. **Step 0-login-wait**: IPAT ログイン画面検出
5. **★ Step 0-daily-plan** (シズネ 🔴 A 二重認証): 音声「本日の投票プラン。 新潟8R 単勝 6 番、 他 N 件…」
6. **[ふくだ]** 音声を聞いて違和感なし → 暗証番号入力
7. **Step 0-main-wait**: ログイン完了検出
8. **Step 0-precheck** (シズネ 🔴 D Phase 4-C-min): pre-flight session 検証
9. **Step 1-3**: 既存の FF CSV → menu → click 経路 (Session 128 同等)
10. **Step 4**: TARGET 保存 (F10 + はい)
11. **Step 5**: ledger v2 追記

### 4.4 success criteria (Karpathy verify loop)

各レースについて以下が全部観測されたら 1 件 GO カウント:

- [ ] 音声 #1 ("TARGET の起動が完了…")
- [ ] 音声 #2 ("本日の投票プラン…") = シズネ 🔴 A 二重認証
- [ ] 音声 #3 ("IPAT 認証が完了…")
- [ ] 投票ダイアログ自動 click + OK
- [ ] 音声 #4 ("受付番号 …。 投票完了")
- [ ] ledger event 4 種 (FF_WRITTEN / TARGET_IMPORTED / APPROVED / IPAT_CONFIRMED)
- [ ] audit JSONL に raw text + notify_text 記録
- [ ] IPAT サイトで受付番号目視確認一致

**最低 1 レース GO で日曜 PM 継続**。 2 レース以上 GO で「無条件 GO」 判定。

### 4.5 NO-GO 時

- 5/30 半自動運用に戻す
- shizune 呼んでレビュー (`Agent(subagent_type='shizune', prompt=...)`)
- 月初 OFF 練習日 (§1.5) を 6 月初開催日に正式設定

---

## 5. 5/31 (日) PM フェーズ — verify loop 観測 (Phase 4-C-full)

### 5.1 目的

設計書 18 §1.3 success criteria 6 項目目 (verify loop) を **実機 1 件以上観測**する。 セッション切れ → 検知 → 音声 → ledger → audit → recover → RECOVERED event 着地までの end-to-end。

### 5.2 シナリオ (人工的に再現)

セッション切れを意図的に誘発する方法は 2 通り:

#### 方法 A. 自然タイムアウト誘発

1. レース間の空き時間に、 `--auto-launch` 実行
2. 音声「本日の投票プラン…」 後、 暗証番号入力を **60 秒以上放置**
3. IPAT 側でログインがタイムアウト → ログイン画面に戻る or エラーダイアログ
4. ふくだが暗証番号入力 → ログイン → `precheck_ipat_session` が NG
5. → `IPAT_SESSION_EXPIRED` event 記録 + 音声「IPAT セッションが切れました…」 + exit 7

#### 方法 B. 投票後タイムアウト誘発 (上級、 任意)

1. 通常通り投票実行
2. 投票 click 直後にネットワーク (Wi-Fi) を一時切断
3. 「投票終了」 ダイアログが出ない → `result_dialog_timeout`
4. → `IPAT_SESSION_EXPIRED_POSTVOTE` event + `vote_already_clicked=True`
5. 音声「IPAT セッション切れを検知…復旧を試みます」
6. recover_ipat_session 5-step フロー

### 5.3 確認すべき観測 (verify loop end-to-end)

```
[誘発] 暗証番号入力後 60 秒放置 (方法 A)
   ↓
[音声] "IPAT セッションが切れました。 投票を中断しています。 再認証してください。"
   ↓
[ledger] events_2026-05.jsonl に IPAT_SESSION_EXPIRED event 追記
   ↓
[runner.py] exit 7 で停止
   ↓
[ふくだ手動] python -m ml.target_clicker.launcher recover-session
   ↓
[recover] Step 1 (dialog close 多段モーダル対応 / Session 133 🟡-8)
            → Step 2 open_ipat_menu
            → Step 3 wait_login
            → Step 4 ふくだ暗証番号入力 (★ 永続手動)
            → Step 5 wait_main + precheck
   ↓
[音声] "IPAT セッションの再認証に成功しました…ただし未投票分の自動再送はしません…"
   ↓
[ledger] events_2026-05.jsonl に IPAT_SESSION_RECOVERED event 追記 (Session 132 🟡-10 で配線済)
   ↓
[Session 133 修正B 起動時チェックの確認]
   - 直近 1h 内に IPAT_SESSION_EXPIRED_POSTVOTE event があれば
     次に selective_vote.bat --auto-launch を叩いた時に exit 8 で abort
   - 「--ignore-recent-session-expired」 明示するまで進めない
   - これが構造的な二重投票防止
```

### 5.4 観測ログを残す

検証結果を以下に追記:

```
data3/userdata/target_clicker/oos_verification_20260531.md
```

最低限の記録項目:
- 誘発方法 (A or B)
- 各音声の時刻 (秒精度)
- ledger event の id + at
- audit JSONL の対応行
- ふくだの手動アクション (暗証番号入力時刻 / recover-session 実行時刻)
- 結果 (RECOVERED / RECOVERY_FAILED)
- 所要時間 (誘発開始 → RECOVERED まで)

---

## 6. 失敗時 切り戻し SOP

### 6.0 「進めるべきか止めるべきか」 判断つかないときの 3 秒ルール — シズネ独自観点

OOS 中に「これは止めた方がいいのか、 続けた方がいいのか」 と **3 秒以上迷ったら、 即 Ctrl+C で stop**。

判断材料:
- 迷っている = 想定外の状態 = 設計外
- 設計外で「続けた方が早い」 と感じるのは大抵 sunk cost 効果
- 止めて IPAT 残高目視 + ledger 確認 = 失う時間 5 分
- 続けて事故 = 失う金額 数千〜数万円 + 復旧時間 数時間

判断つかない時は shizune を呼ぶ:

```python
Agent(subagent_type='shizune', prompt='''
OOS 中。 状況: [今ターミナルに出ている最後の 10 行コピペ]
ledger 直近: [purchase_ledger/2026-05-3X.json 末尾 30 行コピペ]
IPAT 残高: [目視確認した値]
私の懸念: [自分が「これ大丈夫?」 と感じている点を 1 文]
進めるべきか止めるべきか判断したい。
''')
```

shizune は 1-2 分で「止める」 / 「続けて OK」 / 「もう少し情報集めて」 のいずれかを返す。 迷う時間 30 秒以上 = shizune 呼出のコスト (1-2 分) を上回るので、 呼んだ方が安い。

### 6.1 緊急停止 (Kill Switch 代替)

```powershell
# runner.py を強制停止
taskkill /F /IM python.exe /T   # 危険、 他の python プロセスも止まる

# 安全な方法: Ctrl+C で runner.py を SIGINT
# (Step 1 (FF CSV 書き出し) 後なら ledger は途中まで記録される、 投票はしていない)
```

### 6.2 ふくだが「これは止めた方がいい」 と感じた瞬間の SOP

1. Ctrl+C で runner.py 停止 (or TARGET ウィンドウを×ボタンで閉じる)
2. IPAT サイトで残高 + 投票履歴を目視確認
3. ledger と IPAT の差分を確認:
   ```powershell
   ./.venv/Scripts/python.exe -c "import json; data = json.load(open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/2026-05-30.json')); print(json.dumps(data, ensure_ascii=False, indent=2))"
   ```
4. シズネ呼んで状況レビュー (`Agent(subagent_type='shizune', prompt='OOS で X が起きた、 ledger は Y 状態、 IPAT は Z 状態。 リスク評価して')`)

### 6.3 主要失敗パターン別 SOP

| 症状 | 即時対応 | 後追い対応 |
|---|---|---|
| TARGET 起動失敗 (exit 7, action=launch_failed) | ふくだ手動で TARGET 起動 → 半自動運用 (Session 128 同等) | exe パス検出 (`find_target_exe`) のロジック見直し |
| TARGET_DIALOG_UNKNOWN (exit 7) | TARGET ウィンドウ目視 → 想定外 dialog を手動 close → 再実行 | `launch_dialogs.json` に追加 (verified_by 更新) |
| IPAT_SESSION_EXPIRED (pre-flight, exit 7) | 暗証番号再入力 → IPAT ログイン → 半自動運用に切替 | `precheck_ipat_session` 判定基準見直し |
| IPAT_SESSION_EXPIRED_POSTVOTE (exit 5) | ledger確認 → IPAT 履歴照合 → 必要なら手動で再投票 | recover-session を打つ |
| TARGET_SAVE_FAILED | TARGET ウィンドウで F10 + はい を手動 (or 無視) | rollback 不能、 ledger payload 通り |
| 受付番号取得失敗 | IPAT 投票履歴の最新番号を ledger に手動追記 (将来運用、 現状は audit JSONL の raw text で十分) | result_dialog 取得ロジック見直し |
| TTS 発話しない (`notify_spoken=False`) | 投票自体は継続 (--no-notify 同等)、 ターミナル目視で進行確認 | Session 134 で notify 経路再調査 |
| 起動時 SESSION_EXPIRED チェックで exit 8 | ledger と IPAT 履歴を照合 → 必要なら手動投票 / `--ignore-recent-session-expired` で承認継続 | Session 133 修正B 動作確認 |
| **PC スリープ復帰後の最初の selective_vote.bat** (★ 5/31 朝に必発しうる) | (1) TARGET ウィンドウを × で閉じてから始めるのを推奨 (2) IPAT Web で残高表示が出るか目視 (3) NG なら半自動運用に戻る | 起動時 SESSION_EXPIRED チェック (修正B) がスリープ後初回に高確率で発火することを §6.4.b 認知パターンに記録 |
| **修正B の `--ignore-recent-session-expired` を打つ判断基準** | ledger 直近 `IPAT_SESSION_EXPIRED_POSTVOTE` が「PC スリープによる擬似」 と確信できる場合のみ。 確信なければ 30 分待って自動失効を待つ | 「擬似」 と「本物」 の判別ガイドを Session 134 で 19 §6.5 として整備 |

### 6.4 「絶対に避けるべき」 アンチパターン

- ❌ ledger の手動編集 (audit 整合が崩れる、 SHA256 不一致で警告される)
- ❌ `selective_vote.bat` の連続実行 (idempotency_key で portfolio は重複検知されるが、 IPAT 側で投票内容確認 dialog が二度立ち上がる可能性)
- ❌ `--no-bankroll-check` の常用 (一時的なテスト時のみ)
- ❌ `--ignore-recent-session-expired` を確認なしで指定 (意図しない二重投票)
- ❌ 暗証番号を環境変数 / config に保存 (CI 強制禁止 / `test_launcher_no_password.py` 14 tests で防御)

### 6.4.b 行動アンチパターン (ふくだ本能的衝動への構造的歯止め) — シズネ独自観点

§6.4 は技術的アンチパターンを列挙したが、 **OOS 期間中の真のリスクは「もう一回」 「取り戻し」 等の本能的衝動**。 以下 5 つを構造的に塞ぐ:

- ❌ **OOS 中に「計画外の bets[]」 を追加投票** (= 「もう一回」 衝動)
  → 5/29 夜時点の selective_bets.json を SoT として固定。 追加が必要と感じても 5/31 終了まで触らない。 触りたいなら shizune 呼ぶ。
- ❌ **OOS で負けた直後の「最終レースだけ手動で取り戻す」** (= 「取り戻し」 衝動)
  → 半自動運用にダウングレードしても OK だが、 計画額を上げない。 「マイナス分の取り戻し」 という発想自体が Themis 原則違反。
- ❌ **OOS 1 日 (sample N≤2) で運用パラメータ (amount / max_bets) を上げる** (= 「気が大きくなる」 衝動)
  → 6/6 月初 OFF 練習日まで、 `amount=100` / `max_bets=3` を固定。 パラメータ変更は最低 4 週 (= 4 開催日) の累計データを見てから。
- ❌ **「面倒」 を理由に Session 131/132 シズネ防御 (二重認証ゲート / recover-session 手動 / 通知音) を OFF にする** (= 「面倒くさい」 衝動)
  → 「面倒さ = 構造的安全弁」 (Session 132 学び)。 OFF にしたい衝動が出たら即 shizune 呼ぶ。
- ❌ **通知音が「うるさい」 を理由に `--no-notify` 常用** (= 「観察者疲れ」 衝動)
  → 当日プラン読み上げ = 二重認証ゲート (シズネ 🔴 A)。 外したら内容承認していないのと同じ。 一時的に音量下げる だけにする。
- ❌ **OOS 中に freebudget 引数 (`--bankroll` / `--per-bet-cap-pct` / `--kelly-fraction` / `--preset`) を計画外に変更** (= 「気が大きくなる」 衝動の隠れ経路、 Session 134 シズネ 🔴 追加対応)
  → 5/30 用は §1.5 で生成した freebudget_bets.json を SoT として固定。 パラメータ変更したい衝動が出たら即 shizune 呼ぶ。
  特に「5/30 が 1600円しか使ってないから 5/31 は `--per-bet-cap-pct 0.20` で攻めよう」 は典型的な sample N=1 反応で構造的歯止め対象。

> シズネが入る根本理由 = ブレーキ役。 OOS 中の各 phase で「これをやったら止める」 を明文化することで、 高揚状態 / 落胆状態どちらでも構造的歯止めが利く。

### 6.5 PC スリープ復帰の「擬似」 / 「本物」 判別ガイド (Session 134 整備予定)

§6.3 で参照。 5/30-31 OOS で実機観察したパターンを Session 134 で正式整備。 暫定運用は §6.3 の 2 行 SOP に従う。

### 6.6 kill switch / cooldown の OOS 中の扱い — シズネ独自観点

- [12_KILL_SWITCH_COOLDOWN.md](./12_KILL_SWITCH_COOLDOWN.md) で定義された当日 `emergency_stop` は OOS 中も有効
- 発火条件 (Session 133 時点で実装確認要):
  - `per_day_max_yen` 到達 (config.json 既定値)
  - `per_race_max_yen` 違反 (race_overrides 含む)
  - selective_loader schema 違反
  - 起動時 SESSION_EXPIRED チェック発火 (Session 133 修正B)
- 発火時の挙動:
  - runner.py exit ≥ 5
  - ledger event `KILL_SWITCH_TRIGGERED` ([12 §4.6](./12_KILL_SWITCH_COOLDOWN.md) / [14 §6](./14_LEDGER_SCHEMA.md)) 記録
  - 音声警告
  - 当日中は selective_vote.bat 再実行不可 (実装確認要 — Session 134)
- OOS 中に意図的発火試験 (5/31 PM 推奨):
  - `per_day_max_yen` を 500 円 に一時的に下げて 1 件投票 → 2 件目で発火確認
  - 確認後 元の値に戻す
- ★「もう一回」 衝動 (§6.4.b) と kill switch の関係:
  - kill switch 発火後の「あと 1 レースだけ」 は構造的に不可能 (config 変更が必要)
  - config 変更しようとした瞬間 = 危険サイン = shizune 呼出

---

## 7. OOS 終了後の振り返り (Session 134 準備)

### 7.1 設計検証集計 (OOS の主目的) — シズネ 🔴-3 対応

OOS の本来の目的は「**設計通り動いたかどうか**」 であって「儲かったかどうか」 ではない。 以下 6 集計を必ず実行:

```powershell
# ① Phase 通過率
./.venv/Scripts/python.exe -c "
import json
from collections import Counter
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
counts = Counter(e.get('type') for e in events)
for phase, ok_event, fail_events in [
    ('4-A 起動', 'IPAT_CONFIRMED', ['TARGET_DIALOG_UNKNOWN']),
    ('4-B メニュー', 'IPAT_CONFIRMED', ['IPAT_START_FAILED']),
    ('4-C-min precheck', 'APPROVED', ['IPAT_SESSION_EXPIRED']),
    ('4-C-full 復旧', 'IPAT_SESSION_RECOVERED', ['IPAT_SESSION_RECOVERY_FAILED']),
]:
    ok = counts.get(ok_event, 0)
    fail = sum(counts.get(f, 0) for f in fail_events)
    rate = ok/(ok+fail)*100 if (ok+fail) else 0
    print(f'{phase:18} success={ok:3d} fail={fail:3d}  pass_rate={rate:.1f}%')
"

# ② 失敗系比率
./.venv/Scripts/python.exe -c "
import json
from collections import Counter
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
counts = Counter(e.get('type') for e in events)
success_events = {'APPROVED','IPAT_CONFIRMED','FF_WRITTEN','TARGET_IMPORTED','IPAT_SESSION_RECOVERED'}
failure_events = {'VOTE_FAILED','IPAT_START_FAILED','TARGET_SAVE_FAILED','TARGET_DIALOG_UNKNOWN','IPAT_SESSION_EXPIRED','IPAT_SESSION_EXPIRED_POSTVOTE','IPAT_SESSION_RECOVERY_FAILED'}
n_success = sum(counts.get(t, 0) for t in success_events)
n_failure = sum(counts.get(t, 0) for t in failure_events)
ratio = n_failure/n_success*100 if n_success else 0
print(f'成功系: {n_success} / 失敗系: {n_failure} / 比率: {ratio:.1f}%')
print(f'判定基準: 失敗系/成功系 比率 <= 30% なら設計通り')
"

# ③ verify loop 観測件数 (18 §1.3 success criteria #6)
./.venv/Scripts/python.exe -c "
import json
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
expired_postvote = [e for e in events if e.get('type') == 'IPAT_SESSION_EXPIRED_POSTVOTE']
recovered = [e for e in events if e.get('type') == 'IPAT_SESSION_RECOVERED']
verify_loops = min(len(expired_postvote), len(recovered))
print(f'IPAT_SESSION_EXPIRED_POSTVOTE: {len(expired_postvote)} 件')
print(f'IPAT_SESSION_RECOVERED:        {len(recovered)} 件')
print(f'verify loop 観測 (簡易): {verify_loops} 件 (target: 1 件以上)')
"

# ④ TTS 到達率
./.venv/Scripts/python.exe -c "
import json
audit = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/target_clicker/audit_2026-05.jsonl', encoding='utf-8') if l.strip()]
audit = [a for a in audit if a.get('at', '').startswith('2026-05-3')]
with_notify = [a for a in audit if a.get('notify_text')]
spoken = [a for a in with_notify if a.get('notify_spoken')]
rate = len(spoken)/len(with_notify)*100 if with_notify else 0
print(f'notify_text 発生: {len(with_notify)} 件')
print(f'notify_spoken=True: {len(spoken)} 件')
print(f'TTS 到達率: {rate:.1f}%')
print(f'判定基準: 95% 以上')
"

# ⑤ idempotency 重複検知件数 (= 二重実行の兆候)
./.venv/Scripts/python.exe -c "
import json
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
dups = [e for e in events if e.get('payload', {}).get('action') == 'duplicate']
print(f'idempotency duplicate 検知: {len(dups)} 件')
print(f'判定基準: 0 件 (1 以上は二重実行の兆候、 即 shizune 呼出)')
"

# ⑥ selective_loader スキーマ違反件数
./.venv/Scripts/python.exe -c "
import json
events = [json.loads(l) for l in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8') if l.strip()]
events = [e for e in events if e.get('at', '').startswith('2026-05-3')]
schema_violations = [e for e in events if e.get('type') == 'VOTE_FAILED' and 'schema' in str(e.get('payload', {})).lower()]
print(f'selective_loader 違反: {len(schema_violations)} 件')
print(f'判定基準: 0 件 (Session 129 🔴 J 防御の動作確認)')
"
```

### 7.2 GO/NO-GO 判定確定 (設計検証ベース 9 軸) — シズネ 🔴-3 対応

| 評価軸 | 基準 | OOS 結果 |
|---|---|---|
| Phase 4-A 起動 通過率 | 100% (許容下限 90%) | _ / _ % |
| Phase 4-B IPAT メニュー 通過率 | 100% (許容下限 90%) | _ / _ % |
| Phase 4-C-min precheck false negative | 0 件 | _ 件 |
| Phase 4-C-full 復旧 verify loop 観測 | 1 件以上 | _ 件 |
| ledger event 失敗系/成功系比率 | <= 30% | _ % |
| TTS 到達率 | >= 95% | _ % |
| idempotency duplicate | 0 件 | _ 件 |
| selective_loader schema violation | 0 件 | _ 件 |
| 起動時 SESSION_EXPIRED チェック (修正B) 発火確認 | OOS 中 1 回以上の意図的発火試験 | _ 回 |

→ **全 9 軸 ✅ なら「無条件 GO」**。 1 軸でも NG なら **NO-GO + 原因究明 + Session 134 で修正 + OOS 再実施 (翌週末)**。

### 7.3 ROI 集計 (副次) — 「儲かったかどうか」 は OOS 主評価軸ではない

```powershell
# 2 日間の ledger 集計 (副次)
./.venv/Scripts/python.exe -c "
import json, glob
total_invest = 0
total_payout = 0  # 結果確定後に手動 update
n_tickets = 0
for fp in sorted(glob.glob('c:/KEIBA-CICD/data3/userdata/purchase_ledger/2026-05-3*.json')):
    data = json.load(open(fp, encoding='utf-8'))
    for race in data.get('races', []):
        for p in race.get('portfolios', []):
            for t in p.get('tickets', []):
                total_invest += t.get('total_amount', 0)
                n_tickets += 1
                if t.get('payout'):
                    total_payout += t['payout']
print(f'投資合計: {total_invest}円 / 払戻合計: {total_payout}円 / 件数: {n_tickets}')
print(f'差額: {total_payout - total_invest}円 / ROI: {total_payout/total_invest*100:.1f}%' if total_invest else 'N/A')
"
```

**判定基準なし**。 OOS の主目的は §7.1-§7.2 (設計検証)、 ROI は **OOS 評価軸ではない** (sample N が小さすぎる)。 「儲かったから 翌週 GO」 経路を構造的に塞ぐ。

### 7.4 OOS 知見の文書化

- `launch_dialogs.json` v2 → git commit (verified_by=fukuda + 当日日付)
- `session_expired_patterns.json` v2 → 同上 (誘発時の dialog 構造をスキーマ化)
- 18 §1.3 success criteria 6 項目目に「verify loop 観測済 (2026-05-31, race_id=XXX)」 追記
- Session 134 セッションサマリに OOS 結果 + 改善点を記録
- §6.5 PC スリープ復帰 「擬似 / 本物」 判別ガイドを実機観察から整備

### 7.5 14_LEDGER_SCHEMA 更新の確認

`14_LEDGER_SCHEMA.md` v1.2 (Session 133 で event 30 種化済) の各 event payload が実機通り記録されているか:

```powershell
# 失敗系 event がどれくらい出たか集計
./.venv/Scripts/python.exe -c "
import json
from collections import Counter
counts = Counter()
for line in open('c:/KEIBA-CICD/data3/userdata/purchase_ledger/events_2026-05.jsonl', encoding='utf-8'):
    if not line.strip(): continue
    ev = json.loads(line)
    counts[ev.get('type', 'unknown')] += 1
for typ, n in counts.most_common():
    print(f'{n:5d} {typ}')
"
```

期待値: APPROVED / IPAT_CONFIRMED 等の成功系 >> 失敗系。 失敗系が成功系を上回るなら設計見直しレベル。

### 7.6 Session 134 引き継ぎ事項

- [ ] OOS で発見された運用知見 → 関連設計書に追記
- [ ] **6/6 (土) を月初 OFF 練習日として確定** (OOS 結果に依らず、 [18 §1.5](./18_TARGET_FULL_AUTOMATION.md) に従う)
      → 6/6 朝に半自動運用で 1 レース投票 → 5/30-31 OOS 結果との比較 = 「自動化なしでも回せる筋力」 維持確認
- [ ] §6.5 PC スリープ復帰 判別ガイドの整備 (5/31 AM 実機観察結果ベース)
- [ ] Session 132 残 🟡-5(b) (verified_by 欠落 abort 化) / 🟡-8 (多段モーダル対応、 OOS 観察次第)
- [ ] Phase 4-D (TARGET セッション継続管理の Step 6+) スコープ確認
- [ ] 6 月以降の週次運用 SOP 策定 (土曜 = `--auto-launch` 標準、 月初 = OFF 練習)
- [ ] シズネレビュー (Session 132 残 🟡-3 / 🟡-6 / 🟡-10 確認 / Phase 4-D 設計)
- [ ] **★ freebudget Phase 2 検討** (Session 135+ — ふくだ既存「収支管理機能」 から最新残高自動取得 → 5/30 終了残高を 5/31 朝 `--bankroll` に手動入力する手間を自動化。 さらに将来「IPAT 実残高取得」 をセットでレース間動的更新に拡張)
- [ ] **★ freebudget の n_bets 件数想定をログ化** (5/30-31 で何件出たか、 0件 / 1-5件 / 5-15件 / 15+件 の頻度をベースラインとして記録)

---

## 8. 緊急連絡先 (?)

OOS 中に予期せぬ事態:

- カカシ (技術判断): 本書 + ledger + audit JSONL + git log の確認
- シズネ (リスク判断): `Agent(subagent_type='shizune', prompt='...')` で呼出
- ふくだ最終判断: 「これは止める」 を遠慮なく決める権限

---

> 「土曜 AM = データ取り、 土曜 PM = いつも通り、 日曜 AM = 新機能試運転、 日曜 PM = verify loop 観測」 — 段階的アプローチ。 一気に自動にしないことで、 つまずいても投票が止まらない。 OOS の主目的は「現実とコード想定のズレを 1 個ずつ確定すること」。 6 不明変数を 1 件ずつ潰せば、 月曜には「無条件 GO」 で週次運用に入れる。 — カカシ (Session 133)

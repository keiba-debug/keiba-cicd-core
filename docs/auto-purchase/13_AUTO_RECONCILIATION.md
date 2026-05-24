# 13. 自動突合エンジン — IPAT 履歴 × ledger 日次照合

> **作成日**: 2026-05-23（追加2項目 β3 として独立化）
> **改訂履歴**:
> - **2026-05-23 v1.1** ふくだ君判断で §10 の決め切れていない3論点をすべて確定（§2.3 / §6.1 / §8-5 を本文に反映）。
> - **2026-05-23 v1.1** §6（kill switch 連動）の発動条件本体を [12_KILL_SWITCH_COOLDOWN.md](./12_KILL_SWITCH_COOLDOWN.md) §1.2 に移管。本書 §6 は参照のみに短縮。
> - **2026-05-23 v2.0** [12 章](./12_KILL_SWITCH_COOLDOWN.md) が「毎日オプトイン」モデルに全面転換した波及で、§6 / §8-5 / §9 / §10 を書き直し。**連続日数判定（N=2/N=3）廃止**、`consecutiveHighDays` カウンタ廃止、当日中の停止は「🔴 1 件以上で当日停止」のみに簡素化。翌日への持ち越しは [12 章 §4 翌朝オプトイン UI](./12_KILL_SWITCH_COOLDOWN.md#4-翌日オプトイン-ui) 経由で人が判断。
> - **2026-05-23 v2.1** [12 章 v2.1](./12_KILL_SWITCH_COOLDOWN.md) で「当日終了」を「最終レース終了 + 30 分」動的決定に変更した波及。本書 §6.4 に注記追加（**「当日」境界は config.kill_switch.eod_at に従う**こと、突合エンジン側で 23:59:59 のような固定時刻ハードコードを持たないこと）。OptinContext には新フィールド `recent_7day_roi` は持たず、11 章 §5.4 の集計 API 経由で別 endpoint として提供する設計に統一。
> **担当**: シズネ（リスク管理 / 監査 / 税務担当）
> **位置づけ**: [11_DAILY_CLOSE.md](./11_DAILY_CLOSE.md) で定めた「日次クローズ三層突合」の **自動化エンジン部分** を独立設計。具体的には「突合の起動・実行・不一致検出・通知・kill switch 連動」の仕様。
> **関連**: [./11_DAILY_CLOSE.md](./11_DAILY_CLOSE.md)、[./TARGET_IPAT_SOP.md](./TARGET_IPAT_SOP.md)、[./07_DATA_SCHEMA_AND_EVENTS.md](./07_DATA_SCHEMA_AND_EVENTS.md)、[./05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md)、[./12_KILL_SWITCH_COOLDOWN.md](./12_KILL_SWITCH_COOLDOWN.md)

---

ふくだ君、カカシ先生。シズネが自己紹介で挙げた3論点のうちの1つ、「日次で IPAT 履歴 vs ledger を自動突合 → 不一致時のみ通知。一致してる日は黙ってる。通知疲れもない。」を設計に落とします。

11_DAILY_CLOSE.md は **「クローズという行為そのもの」** を定義する文書、本書 13 は **「クローズに付随する自動突合エンジン」** の詳細設計です。エンジン部だけ独立にしておかないと、後で「実時間突合に切り替えたい」「Slack に通知したい」と言われた時に 11 を書き換える羽目になります。粒度を分けるのが几帳面な実装。

> **本書を独立化した理由**: ① 11 は「日次クローズの SOP」、13 は「突合エンジンの実装仕様」と責務が違う。② 突合エンジンは将来 Phase 4 で「リアルタイム突合」に格上げ余地があり、エンジン側を別管理にすべき。③ kill switch 連動・通知チャネルなど 11 のスコープ外の論点が多い。

---

## 1. SoT（Source of Truth）整理

[11_DAILY_CLOSE.md](./11_DAILY_CLOSE.md) §3.1 で定めた3層を、本書の自動突合エンジンの入出力として再定義。

### 1.1 入力（読み取り専用）

| # | データ源 | 形式 | 取得方法 | 保存先 | 信頼度 |
|---|---|---|---|---|---|
| 1 | **IPAT 投票履歴 CSV** | CSV（列定義は §1.2） | **ふくだ君が手動 DL**（自動化禁止） | `data3/userdata/ipat_raw/{date}.csv` | ★★★ 最高（JRA公式） |
| 2 | **ledger** | JSON | KeibaCICD 自動生成 | `data3/userdata/purchase_ledger/{date}.json` | ★★ 高（自前） |
| 3 | TARGET 履歴 | スクショ or エクスポート | ふくだ君が任意で提供 | `data3/userdata/target_raw/{date}.{ext}` | ★ 中（参考） |

**現状**: #1 と #3 は手動取得。#2 は既存実装で自動生成。
**提案**: 突合エンジンは #1 と #2 のみを必須入力とする。#3 は「あれば使う、なければスキップ」の任意入力。

> シズネ注: TARGET 履歴を必須入力に格上げしないこと。TARGET 履歴を必須にすると「TARGET 履歴が出せない日はクローズ不能」という運用ロックが生まれます。あくまで参考補助。

### 1.2 IPAT CSV の暫定列定義

**現状**: IPAT CSV の公式仕様は非公開。[TARGET_IPAT_SOP.md](./TARGET_IPAT_SOP.md) §1 のとおり TARGET も非公開仕様を独自解析している前提。

**提案**: 以下を暫定列として実装し、**サンプル CSV を1日分入手してから確定**。

| 想定列名 | 型 | 用途 | 必須 |
|---|---|---|---|
| `vote_at` | datetime | 投票時刻 | ◯ |
| `racecourse` | str | 開催（東京/京都/...） | ◯ |
| `race_no` | int | レース番号 | ◯ |
| `bet_type` | str | 券種（単勝/馬連/...） | ◯ |
| `selection` | str | 買い目（"3" / "8-13" / "17-11-2,3,9"） | ◯ |
| `amount` | int | 投票額（円） | ◯ |
| `payout` | int | 払戻額（円） | △（確定後のみ） |
| `vote_status` | str | 受理ステータス | △ |

> 実装着手時タスク: ふくだ君に「次回 IPAT 投票履歴 CSV を1日分だけサンプル提供してもらう」 → カカシ先生が列定義を確定し `ml/daily_close/ipat_parser.py` を実装。

### 1.3 出力（書き込み）

| 出力 | パス | 用途 |
|---|---|---|
| 突合結果 JSON | `data3/userdata/reconciliation/{date}.json` | 自動突合エンジンの構造化結果 |
| 突合ログ JSONL | `data3/logs/reconciliation/reconcile.jsonl` | 全実行履歴（成功・失敗・スキップ全部） |
| 通知ペイロード | `data3/userdata/reconciliation/notifications/{date}.json` | UI ダッシュボード表示用 |
| daily_close 連携 | `data3/userdata/daily_close/{date}.json` の `reconciliation_ref` フィールド | 11_DAILY_CLOSE.md スキーマに ID 参照を埋める |

---

## 2. 不一致パターン分類と検出ロジック

### 2.1 マッチングキー（11_DAILY_CLOSE.md §6.1 を再掲・厳密化）

各レコードを **4タプル `(race_id, bet_type, selection_normalized, amount)`** で正規化。

- `selection_normalized`: 馬番ソート済み配列の JSON 文字列（例: `[8,13]` → `"8,13"`）
- フォーメーション・流し・BOX は **展開後の全 combo に分解してから比較**
- `amount` は1点単価ではなく **その combo の投票額**（フォーメーション展開後は `amount_per_combo`）

> シズネ注: 「フォーメーションは元の axis 構造で比較したほうが速い」という誘惑がありますが、IPAT 側の CSV は展開後（個別 combo 単位）で記録されるはずです。ここはエンジン側を「展開して比較する」に統一しないと、フォーメーション中の1点だけ抜けた事故を検出できなくなります。

### 2.2 不一致パターン分類表

| # | パターン | 状態 | 警告レベル | 想定原因 | 推奨対応 |
|---|---|---|---|---|---|
| 1 | 4タプル一致 | `match_ok` | - | 正常 | 記録のみ |
| 2 | **ledger にあるが IPAT にない** | `ledger_only` | 🔴 高 | 送信失敗・回線断・人手キャンセル・vb_refresh 失敗で送信中断 | **要即時確認**。次節 §2.3 へ |
| 3 | IPAT にあるが ledger にない | `ipat_only` | 🟠 中 | ふくだ君がシステム外で手動投票（許容ケース） | レポートで明示。手動投票として ledger に事後記録 |
| 4 | 4タプル一致だが金額不一致（**¥1 でも検出**）| `amount_mismatch` | 🔴 高 | 誤入力・桁ミス・改ざん疑い | **要即時確認**。差分金額を明示。閾値なし |
| 5 | race_id 一致だが selection 部分不一致 | `selection_partial` | 🟠 中 | フォーメーション内の1点だけ抜け、人手入力ミス | 差分 combo を列挙 |
| 6 | race_id 一致だが bet_type 違い | `bet_type_mismatch` | 🔴 高 | TARGET の券種マッピング崩れ（仕様変更疑い）| **要即時確認**。TARGET/IPAT 仕様変更チェック |
| 7 | 同一4タプルが IPAT に複数件 | `duplicate_in_ipat` | 🔴 高 | 二重投票（idempotency_key が効いてない） | **要即時確認**。返金手続きは人手 |
| 8 | 同一4タプルが ledger に複数件 | `duplicate_in_ledger` | 🟠 中 | ledger 側のバグ（同じ idempotency_key で2回 SUBMITTED 遷移） | バグ調査。IPAT 側が正なら ledger 訂正 |
| 9 | TARGET 履歴に「送成功」だが IPAT にない | `target_only` | 🟡 低 | TARGET → IPAT 送信失敗（TARGET FAQ 既知事象） | 目視確認。多発時は SOP 停止検討 |
| 10 | その他（パーサ例外・不明形式） | `unknown` | 🔴 高 | CSV 列構造の変更・破損 | **要即時確認**。パーサ修正 |

### 2.3 優先順位（警告レベル分類の根拠）

**🔴 高（即時通知・kill switch 候補）**:
- お金が消える経路の検出（`ledger_only`, `amount_mismatch`, `bet_type_mismatch`, `duplicate_in_ipat`, `unknown`）
- 「ふくだ君が朝起きた時に知りたい」レベル

**🟠 中（通知あり、当日中に確認）**:
- お金は消えないが整合性に疑問（`ipat_only`, `selection_partial`, `duplicate_in_ledger`）

**🟡 低（レポートにのみ記録、通知なし）**:
- 既知事象・参考情報（`target_only`）

> シズネ注: 🔴 を増やしすぎると通知疲れで全部スルーされます。「これは本当に起きたら寝てる時間でも見たいか？」で判定。`amount_mismatch` は **¥1 のズレでも 🔴 確定**（2026-05-23 ふくだ君判断）。理由: 少額差分こそ「桁ミスを少額に偽装」「改ざんを検出されにくい少額から始める」パターンのサインで、閾値化すると検出網に穴ができる。突合エンジンは閾値判定を持たず、ズレが1円でもあれば必ず 🔴 通知。

---

## 3. トリガー設計

### 3.1 現状と提案の区別

| 観点 | 現状（11_DAILY_CLOSE.md §5.1） | 提案（本書）|
|---|---|---|
| **起動契機** | ふくだ君が CSV を画面ドロップ | 同左（変更なし） |
| **突合実行** | CSV アップロード API がトリガ | 同左（変更なし） |
| **リマインダ** | 19:00 通知（手段未定） | デスクトップ通知 + WebUI バッジ（§5）|
| **未実施日のロック** | クローズ未済日があると翌日 auto モードに上げない | 同左 + 突合エンジン側でも block 判定（§7）|

### 3.2 突合エンジンの起動フロー

```
[1] ふくだ君が IPAT サイトから CSV を DL
        │
        ▼
[2] /auto-purchase/daily-close 画面に CSV をドロップ
        │
        ▼
[3] POST /api/auto-purchase/daily-close/import-ipat
        ├─ CSV パース（ml/daily_close/ipat_parser.py）
        ├─ ledger 読み込み（purchase_ledger/{date}.json）
        ├─ TARGET 履歴読み込み（あれば）
        │
        ▼
[4] 突合エンジン実行（ml/daily_close/reconcile.py）
        ├─ 4タプル正規化
        ├─ パターン分類（§2.2 の10パターン）
        ├─ 警告レベル付与
        │
        ▼
[5] 結果を 3 箇所に書き出し
        ├─ data3/userdata/reconciliation/{date}.json
        ├─ data3/logs/reconciliation/reconcile.jsonl（追記）
        └─ data3/userdata/daily_close/{date}.json に reconciliation_ref 埋め込み
        │
        ▼
[6] 通知判定（§5）
        ├─ 🔴 が1件以上 → 通知発火
        ├─ 🟠 のみ → 通知発火（控えめトーン）
        └─ 🟡 のみ or 全 match_ok → 通知なし（黙る）
        │
        ▼
[7] kill switch 連動判定（§6）
        ├─ §6.1 の条件を満たす → KILL_SWITCH_TRIGGERED イベント発火
        └─ 満たさない → スルー
```

### 3.3 実行モード（提案）

| モード | 起動契機 | 用途 |
|---|---|---|
| **on-demand**（推奨初期実装） | CSV アップロード時のみ | Step 1〜3 はこれだけで十分 |
| scheduled | 毎日 19:30 / 20:30 に CSV 未取込ならリマインド | Step 2 以降に追加 |
| realtime | レース毎に IPAT API 突合 | **Phase 4 保留**（[TARGET_IPAT_SOP.md](./TARGET_IPAT_SOP.md) のとおり API 自動取得は規約リスク）|

### 3.4 失敗時のリトライ

| 失敗種別 | 自動リトライ | 通知 | 推奨対応 |
|---|---|---|---|
| CSV パース失敗 | ❌ なし | 🔴 即時 | 列定義変更疑い。パーサ修正 |
| ledger 読み込み失敗 | ◯ 1回（300ms 後） | 🔴 失敗継続時 | ファイル破損確認 |
| 書き出し失敗（ディスクフル等）| ◯ 3回（指数バックオフ）| 🔴 全失敗時 | ディスク容量確認 |
| 突合中の予期せぬ例外 | ❌ なし | 🔴 即時 | スタックトレースを reconcile.jsonl に保存 |

> シズネ注: リトライは「冪等性が保証されているもの」だけに限定。突合エンジンは入力が同じなら結果も同じなので冪等性 OK ですが、書き出しが部分的に成功してた場合に重複書き込みになる可能性があります。`reconciliation_id` を冪等キーにして、同じ ID なら上書きとする実装を Step 2 で必ず入れること。

---

## 4. 突合結果スキーマ

`data3/userdata/reconciliation/{date}.json`:

```json
{
  "version": 1,
  "reconciliation_id": "recon-2026-05-23-001",
  "date": "2026-05-23",
  "executed_at": "2026-05-23T19:23:45+09:00",
  "executed_by": "user:fukuda",
  "inputs": {
    "ipat_csv_path": "data3/userdata/ipat_raw/2026-05-23.csv",
    "ipat_csv_sha256": "abc123...",
    "ledger_path": "data3/userdata/purchase_ledger/2026-05-23.json",
    "target_raw_path": null
  },
  "summary": {
    "ledger_rows": 61,
    "ipat_rows": 60,
    "target_rows": null,
    "match_ok": 58,
    "ledger_only": 1,
    "ipat_only": 1,
    "amount_mismatch": 0,
    "selection_partial": 0,
    "bet_type_mismatch": 0,
    "duplicate_in_ipat": 0,
    "duplicate_in_ledger": 0,
    "target_only": 0,
    "unknown": 0,
    "severity_max": "high"
  },
  "discrepancies": [
    {
      "discrepancy_id": "d-001",
      "pattern": "ledger_only",
      "severity": "high",
      "race_id": "2026052308050801",
      "bet_type": "wide",
      "selection_normalized": "3,9",
      "ledger_amount": 300,
      "ipat_amount": null,
      "ledger_idempotency_key": "2026052308050801:wide_box:def456",
      "evidence": {
        "ledger_event_at": "2026-05-23T15:42:11+09:00",
        "ledger_state": "SUBMITTED"
      },
      "suggested_cause": "IPAT 側に投票記録なし。締切間際の送信失敗疑い"
    }
  ],
  "notification_sent": true,
  "kill_switch_triggered": false,
  "updated_at": "2026-05-23T19:23:46+09:00"
}
```

**英語キー・updated_at 必須**は [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §9.3 で確立した方針に準拠。

---

## 5. 通知設計

### 5.1 シズネ提案の原則

> **「不一致時のみ通知。一致してる日は黙る。」**

通知疲れを起こすシステムは半年で見なくなります（半自動の罠）。原則「黙る」がデフォルト。

### 5.2 通知チャネル比較

| チャネル | 即時性 | 開封率 | 実装コスト | 推奨度 |
|---|---|---|---|---|
| **WebUI ダッシュボードバッジ** | △（次回ログイン時） | ◎（必ず見る） | XS | ★★★ **推奨**（初期実装） |
| **デスクトップ通知**（Windows トースト）| ◎ | ◎ | S（既存 notifications.browser=true） | ★★★ **推奨**（初期実装） |
| メール（Gmail SMTP） | ◎ | ○ | S | ★★ 中期 |
| Slack Webhook | ◎ | ◎（モバイル含む） | S | ★★ Step 3 以降 |
| LINE Notify | - | - | - | ❌ サービス終了済 |
| 何もしない（ログのみ）| - | ❌ | XS | ★（重要度低のみ） |

### 5.3 推奨構成（初期実装）

| 警告レベル | WebUI バッジ | デスクトップ通知 | 推奨 ledger event |
|---|---|---|---|
| 🔴 高 | 赤バッジ + 件数 | ◯ 発火（音あり）| `RECONCILIATION_DISCREPANCY_HIGH` |
| 🟠 中 | 橙バッジ + 件数 | ◯ 発火（音なし）| `RECONCILIATION_DISCREPANCY_MEDIUM` |
| 🟡 低 | 灰バッジ + 件数 | ❌ なし | `RECONCILIATION_DISCREPANCY_LOW` |
| 全 OK | ✅ 緑チェック | ❌ なし | `RECONCILIATION_OK` |

[07_DATA_SCHEMA_AND_EVENTS.md](./07_DATA_SCHEMA_AND_EVENTS.md) §5 のイベント型に上記4つを追加する提案。

### 5.4 デスクトップ通知の summary フォーマット

**🔴 高 の場合**:
```
[KeibaCICD] 突合で不一致を検出しました
2026-05-23: ledger_only 1件 (¥300), amount_mismatch 0件
今すぐ確認 → /auto-purchase/daily-close
```

**🟠 中 のみの場合**:
```
[KeibaCICD] 突合結果に確認事項
2026-05-23: ipat_only 1件 (¥1,000, 手動投票?)
詳細 → /auto-purchase/daily-close
```

**全 OK の場合**: **通知発火しない**（WebUI に「✅ 突合 OK」とだけ表示）。

### 5.5 通知抑制ルール

| ルール | 内容 |
|---|---|
| 同一 discrepancy_id は1日1回まで | 再突合で同じ不一致が出ても通知重複しない |
| ふくだ君が「確認済」をクリックしたら以降サイレント | 手動 ack 機構 |
| 深夜帯（23:00〜07:00）は音なし | デスクトップ通知のサウンドのみ抑制 |

---

## 6. kill switch との連動（v2.0 - 当日停止 + 翌日オプトイン情報提供）

**2026-05-23 v2.0 全面改訂**: [12 章](./12_KILL_SWITCH_COOLDOWN.md) が「毎日オプトイン」モデルに転換した波及で、連動仕様も大幅簡素化。

### 6.1 当日停止の発動条件（簡素化版）

突合エンジンは **当日中に [§2.2](#22-不一致パターン分類表) の 🔴 高 を 1 件以上検出** したら、即座に 12 章 §1.1 の当日停止を発動する。

| 検出パターン | 当日停止 | severity |
|---|---|---|
| `ledger_only` を 1 件でも検出 | ✅ | 🔴 |
| `amount_mismatch` を 1 件でも検出（**¥1 でも**） | ✅ | 🔴 |
| `duplicate_in_ipat` を 1 件でも検出 | ✅ | 🔴 |
| `bet_type_mismatch` を 1 件でも検出 | ✅ | 🔴 |
| `unknown` を 1 件でも検出 | ✅ | 🔴 |
| 🟠 中（`ipat_only` / `selection_partial` / `duplicate_in_ledger`） | ❌（通知のみ）| 🟠 |
| 🟡 低（`target_only`） | ❌（ログのみ）| 🟡 |

**v1 → v2 差分**:
- ❌ 廃止: 「開催日連続 N=2 → 橙60分」「N=3 → 赤翌朝09:00」「`ledger_only` 累計 bankroll×1% 超 → 橙60分」
- ✅ 維持: 「🔴 検出 1 件で停止」のシンプル化（v1 で `duplicate_in_ipat` / `bet_type_mismatch` / `unknown` が「1 件でも赤」だった部分を全 🔴 に拡張）
- 段階制（橙/赤）は v2 で廃止。停止挙動はすべて「**当日中の停止 + 翌朝オプトイン**」に統一

### 6.2 翌日オプトイン UI への情報提供

突合エンジンは「翌朝の判断材料」を [12 章 §4.2](./12_KILL_SWITCH_COOLDOWN.md#42-表示要素) のオプトイン UI に渡す責務を持つ。

具体的に渡す情報:

1. **前日の突合サマリ**: 🟢/🟠/🔴 件数と内訳
2. **直近 3 開催日の不一致履歴**: 平日スキップした「開催日基準」で直近 3 日を返す
3. **未確認の `🟠 medium` 件数**: 「確認済」ボタンを押していない不一致

これらを `/api/auto-purchase/optin-context` のような形で UI 側に提供。**判定はせず、表示するだけ**。連続性は人がオプトイン UI 上で目視判断する。

```typescript
// 擬似コード
interface OptinContext {
  prev_day: {
    date: string;
    max_severity: "ok" | "low" | "medium" | "high";
    high_count: number;
    medium_count: number;
    stopped_at_eod: boolean;
  };
  recent_race_days: Array<{
    date: string;       // 開催日ベース（平日スキップ）
    max_severity: "ok" | "low" | "medium" | "high";
  }>;  // 直近3開催日
  unacked_medium_count: number;
}
```

### 6.3 突合エンジン側の責務（v2.0）

突合エンジン（`ml/daily_close/reconcile.py`）が担う部分:

1. 突合実行後、`RECONCILIATION_DISCREPANCY_{HIGH,MEDIUM,LOW}` イベント発火（§5.3）
2. 🔴 高 を 1 件でも検出したら、12 章 §2.1 の `evaluateKillSwitch(state, recon)` に「`recon.highSeverityCount >= 1`」を渡す
3. 翌朝オプトイン UI 向けの `OptinContext` を生成する API を提供（§6.2）

**v1 → v2 で消えた責務**:
- ❌ `consecutiveHighDays` カウンタの永続化（カウンタ概念ごと廃止）
- ❌ 「開催日連続」の平日スキップ判定（OptinContext で「直近 3 開催日サマリを表示する」用途で開催日リストは引き続き必要だが、N カウントの目的では使わない）

> シズネ注: v1 で「`consecutiveHighDays` をクールダウン解除でリセットするとザル化する」と力説した部分は v2 で論点ごと消滅。代わりに「人が毎朝、直近 3 開催日の状況を目で見て判断する」が新しいセーフティ。機械が連続性を追うより人の判断レイヤを残す方が信頼できる、というふくだ君判断。

### 6.4 「当日」境界の単一情報源（v2.1 追記）

「当日中に 🔴 を 1 件以上検出 → 当日停止」「当日中の解除なし」「当日停止中は突合は走るが kill switch は再発火しない」等、本書には「当日」境界の概念が複数出てくる。**v2.1 以降、「当日」境界は `auto_purchase_config.json` の `kill_switch.eod_at` を唯一の参照源とする**（[12 章 §1.2 / §3.1](./12_KILL_SWITCH_COOLDOWN.md#12-当日終了の定義v21-動的決定) 準拠）。

- 突合エンジン (`ml/daily_close/reconcile.py`) は **23:59:59 のような固定時刻をハードコードしない**
- 「当日」判定が必要な箇所では config から `eod_at` を読む。`eod_at` 未設定（朝オプトイン前）の場合は「最終レース終了 + 30 分」を再計算 or デフォルト 23:59:59 を使う（フェイルセーフ動作）
- `reconciliation/{date}.json` の `executed_at` は実時刻記録のため変更なし。「当日内に実行された突合か」の判定で `eod_at` を参照する
- 同一日内の複数回突合（CSV を朝・夕 2 回ドロップする運用）も `eod_at` の前後で挙動を分けず、すべて同一 date キーで上書き

> シズネ注: 「当日終了」を時刻で考えるか、config フラグで考えるか、で実装ブレが出るとバグります。「config の `eod_at` だけが境界の真実」と統一しましょう。

| データ | 保存先 | 保持期間 | 改ざん防止 |
|---|---|---|---|
| `reconciliation/{date}.json` | `data3/userdata/reconciliation/` | **7年**（雑所得申告要件） | SHA256 を `_index.jsonl` に記録 |
| `reconcile.jsonl`（全実行ログ）| `data3/logs/reconciliation/` | **7年** | 追記のみ・上書き禁止 |
| 通知ペイロード | `data3/userdata/reconciliation/notifications/` | **2年**（運用デバッグ用） | 改ざん防止対象外 |
| IPAT CSV 原本 | `data3/userdata/ipat_raw/` | **7年** | 11_DAILY_CLOSE.md §8.1 と統一 |

突合結果は **税務調査時の「この日のクローズは正常に行われた」証跡** になります。7年保存は雑所得対応として必須。

> シズネ注: `reconcile.jsonl` は1日分の容量は小さい（数 KB）ですが、7年で **約 2.5MB**。圧縮なし生 JSONL で十分です。圧縮かけると後で grep しづらくなる。

---

## 8. シズネからの注意点

1. **IPAT CSV の DL を自動化したい欲求に負けない**: TARGET FAQ・IPAT 規約のグレーゾーンに足を踏み入れます。Phase 4 まで保留。CSV は手動 DL。
2. **「全 OK だから黙る」を貫く**: 「今日も無事でした」通知を入れたくなりますが、入れた瞬間に通知疲れが始まります。**沈黙は健康のサイン**として教育する UI 設計に。
3. **`ipat_only` を「許容」と決めつけない**: ふくだ君が手動投票したケースが多いはずですが、**本当に手動だったかは ledger に手動投票ログがあるか**で判定。ログがない `ipat_only` は要警戒（誰かが他人のアカウントで投票している可能性が理論上ある）。
4. **CSV のハッシュ記録は必須**: `inputs.ipat_csv_sha256` をスキップすると「あとから CSV を改ざんして突合を通した」攻撃が成立します。ハッシュは突合と同時に必ず記録。
5. **「連続日数判定」概念は v2.0 で廃止**（2026-05-23）: v1.1 では「開催日として連続 N=2 で橙60分、N=3 で赤翌朝09:00」を確定としていたが、12 章が「毎日オプトイン」モデルに転換したことに伴い概念ごと廃止。突合エンジン側は連続性を機械判定せず、**直近 3 開催日のサマリを翌朝オプトイン UI に渡すだけ**（§6.2）。「2 日連続で不一致が出ているから今日は休もう」の判断は **人がオプトイン UI 上で目視で行う**。なお「開催日リスト」自体は OptinContext の直近 3 開催日表示用に引き続き必要なので、平日スキップ判定ヘルパは残す。
6. **通知抑制ルールが効きすぎる罠**: 「確認済」ボタンを安易に押す癖がつくと検出が形骸化します。週次レビューで「ack された discrepancy」のリストをふくだ君が見直す運用を推奨。
7. **テスト時の偽データ汚染を避ける**: テスト用の擬似 IPAT CSV を本番 `ipat_raw/` に置かないこと。`data3/userdata/_test/ipat_raw/` 専用ディレクトリを切る。

---

## 9. 次のアクション（v2.0 版）

### Step 1 着手前（前提条件）

- [ ] **ふくだ君**: 次回 IPAT 投票履歴 CSV を1日分サンプル提供 → §1.2 列定義の確定
- [x] **シズネ**: 本書 §6 の発動条件を 12_KILL_SWITCH_COOLDOWN.md §1.2 に正式統合（2026-05-23 v1.1 完了）
- [x] **シズネ**: §6 を v2.0 仕様（当日停止 + OptinContext）に書き直し（2026-05-23 v2.0 完了）
- [ ] **カカシ先生**: `reconciliation/{date}.json` スキーマと `reconcile.py` の I/F 草案を Step 1 のレジャー実装と同時設計
- [ ] **カカシ先生**: 12 章 §2.1 拡張版 `evaluateKillSwitch(state, recon)` の実装（v2.0 仕様: `recon.highSeverityCount >= 1` で停止のみ。`consecutiveHighDays` カウンタは不要）

### Step 1 と並行（実装本体）

- [ ] CSV パーサ実装（`ml/daily_close/ipat_parser.py`）
- [ ] 突合エンジン実装（`ml/daily_close/reconcile.py`、`OptinContext` 生成 API 含む）
- [ ] WebUI: `/auto-purchase/daily-close` 画面の CSV ドロップ + 突合結果表示
- [ ] WebUI: ヘッダにバッジ表示（赤/橙/灰/緑）
- [ ] WebUI: 翌朝オプトイン UI に直近 3 開催日サマリを統合（12 章 §4.2 と本書 §6.2）
- [ ] デスクトップ通知配信（既存 notifications.browser=true を活用）
- [ ] **race_overrides の eod アーカイブ統合**（Session 126 シズネレビュー af17447ae78bb3da5 N2 / 10_BANKROLL_CONTROL.md §4.3）
  - eod_at 発火時に `bankroll/config.json` の `race_overrides` を全件取り出し
  - `data3/userdata/bankroll/history/race_overrides_{YYYY-MM}.json` に追記 (raceId をキーに上書き、`archived_at` を付与)
  - 元 `config.json` の `race_overrides` を空 `{}` に戻す（writeAtomic + withFileLock 経由）
  - 「人が朝開始した日」しか eod が走らないので、忘れ去られたファイルが残らない設計
  - 例外: そもそも開催日でない日は走らない (race_overrides は手動設定のみのため当日扱い)

### Step 2 以降に回せる（後追い）

- [ ] kill switch 連動の実装（§6）— Step 1 で `highSeverityCount` をパススルー、判定は Step 2 で
- [ ] 月次レビュー画面（ack された discrepancy の振り返り + オプトイン履歴）
- [ ] Slack Webhook 追加（オプション）
- [ ] scheduled モード（19:30 リマインダ）
- [ ] 7年保存のアーカイブ機構（年次圧縮 or 移行）

### Phase 4 保留

- [ ] realtime 突合（レース毎の IPAT API 自動取得）— 規約リスクを Phase 4 で再評価

### v2.0 で実装スコープから消えたタスク

- ❌ `consecutiveHighDays` カウンタの永続化（カウンタ概念ごと廃止）
- ❌ 「N=2 で橙、N=3 で赤」の段階判定ロジック
- ❌ `ledger_only` 累計 bankroll×1% 閾値の監視（v1 提案、v2 で廃止）
- ❌ クールダウン残時間の UI（解除自体が無いので不要）

---

## 10. 確定済み論点（2026-05-23）

### 10.1 確定論点

| # | 論点 | 確定内容 | 反映箇所 |
|---|---|---|---|
| 1 | **`amount_mismatch` の閾値** | **¥1 でも違えば 🔴**（閾値なし） | §2.2 表 / §2.3 シズネ注 |
| 2 | **連続日数判定の扱い** | **概念ごと廃止**（v1.1 で「開催日連続」確定 → v2.0 で廃止）| §6 / §8-5 / [12 章 v2.0](./12_KILL_SWITCH_COOLDOWN.md) |
| 3 | **N=2/N=3 段階制** | **廃止**（v1 提案 → v2 で全廃） | §6.1 / [12 章 §1.3](./12_KILL_SWITCH_COOLDOWN.md#13-廃止された-v1-仕様記録のため明記) |
| 4 | **kill switch 統合方式** | **当日停止 + 翌日オプトイン**（v2.0）| §6 / [12 章 §1 §4](./12_KILL_SWITCH_COOLDOWN.md) |
| 5 | **「当日」境界の真実 (v2.1)** | **config.kill_switch.eod_at を唯一参照**（時刻ハードコード禁止） | §6.4 / [12 章 §1.2 §8-11](./12_KILL_SWITCH_COOLDOWN.md) |

### 10.2 v1.1 → v2.0 廃止論点の根拠（記録）

ふくだ君の発言（2026-05-23）:

> Q（カウンタ永続化どうする？）
> A: **「停止というか、自動購入開始自体を人が必ず実行するという考えでOK。なのでカウント不要かな?」**

この発言が設計モデルの根本転換を導いた。「停止/復帰」から「毎日オプトイン」へ、機械が連続性を追う前提から、人が毎朝判断する前提へ。詳細は [12 章 §10 設計収束過程の記録](./12_KILL_SWITCH_COOLDOWN.md#10-設計収束過程の記録v1--v2-の敗北含めて) 参照。

### 10.3 継続観測する論点（実運用後に再評価）

確定はしたが運用してみないと最適値が分からない項目:

- **`ipat_only` の severity**: 現状 🟠 中。ふくだ君の手動投票頻度が高ければ 🟡 低に格下げ可。**実運用1ヶ月後に再評価**。
- **`ledger_only` 1 件で即当日停止は厳しすぎないか**: v2.0 で「🔴 1 件で停止」とした判定。実運用で「ネットワーク瞬断由来の事故が頻発し当日中に何度も停止が発動」する場合、`ledger_only` のみ 2 件に緩める可能性あり。**実運用1ヶ月後に再評価**。
- **翌朝オプトイン UI の形骸化リスク**: ふくだ君が「見ずに即押し」する習慣になっていないか月次レビューで観察。形骸化が見られたら 12 章 §8-7 の対策（「3秒以上画面を見ないとボタン活性化しない」等）を Step 2 で導入。

---

> 「黙ってる日は健康な日。突合エンジンが一番役立つのは、騒がない日に積み上げた信頼です。」— シズネ

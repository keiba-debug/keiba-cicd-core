# 05. リスク・コンプライアンス・安全策

> 法的助言ではない。税務・規約は専門家確認を推奨。

## 1. リスク分類

| カテゴリ | 例 | 出典 |
|----------|-----|------|
| 実行系 | IPAT障害、二重投票、誤金額 | 松風 006, 009, operations_arch |
| モデル系 | EV閾値過剰、キャリブレーション崩れ | review §4-1 |
| 資金系 | DD -97%, 追い下げバグ | web-roadmap §11 |
| 人的 | 入金忘れ、承認漏れ | 松風 009 |
| 外部 | TARGET/IPAT仕様変更 | TARGET FAQ |
| 税務 | 雑所得認定、証跡不足 | MJS判例, 国税庁慣行 |

## 2. 実行系 — 自動購入の最大リスク

> 「予測精度100%でも購入できなければ利益はゼロ」（operations_architecture_principles.md）

### 2.1 対策マトリクス

| リスク | 予防 | 検知 | 対応 |
|--------|------|------|------|
| FF未出力 | 冪等キュー、ディスク監視 | API失敗、ファイルなし | リトライ1回→FAILED |
| TARGET未取込 | SOP、UIチェックリスト | STALE（T-5超過） | アラート、手動 |
| IPAT誤入力 | TARGET FAQ: 目視確認 | 人間チェック必須 | 投票前キャンセル |
| 一部レース失敗 | 一括投票注意 | 人間がIPAT結果確認 | ledger手修正 |
| 二重投票 | idempotency_key | 同一キー2回目拒否 | 返金手続は人手 |
| vb_refresh停止 | 連続失敗でモードオフ | 最終refresh > 10分前 | 手動オッズ確認 |

### 2.2 Kill Switch（必須）

```json
{
  "emergency_stop": true,
  "stopped_at": "2026-05-23T12:00:00+09:00",
  "stopped_by": "user",
  "reason": "DD -30% 到達"
}
```

- 保存: `auto_purchase_config.json` + ledger イベント
- 効果: Orchestrator は FF 出力・承認キューを処理しない

> **解除条件**（2026-05-23 v2.0）: **当日中は再開不可**。翌日の自動購入再開は、翌朝のオプトイン UI でふくだ君が前日サマリを見て明示的に「開始する」を押すまで動かない。「段階クールダウン → 自動復帰」モデルは v2.0 で廃止（理由: 機械が連続性を追うより人の判断レイヤを残す方が信頼できる）。詳細は [12_KILL_SWITCH_COOLDOWN.md](./12_KILL_SWITCH_COOLDOWN.md) §1 §4 参照。
>
> **「毎朝 manual スタート」原則**（2026-05-23 v2.1）: 翌朝オプトインで「開始する」を押した直後の `mode` は **必ず `manual` 固定**。`semi` / `auto` への昇格は人が明示的に 2 クリック + 確認ダイアログを経由して行う（[12 章 §4.3.1 §4.4](./12_KILL_SWITCH_COOLDOWN.md#431-モード昇格-ui-v21-新設) 参照）。「開始する」と「auto まで動かす」意思を分離することで、半自動の罠（オプトイン UI を見ずに即押し → 即 auto 投票）を構造的に防ぐ。
>
> **「当日終了」の動的決定**（2026-05-23 v2.1）: `emergency_stop` フラグの自動 clear タイミングは「**最終レース終了 + 30 分**」を動的算出（fallback: スケジュール取得失敗時のみ 23:59:59 JST）。詳細・実装注意点は [12 章 §1.2 §8-11](./12_KILL_SWITCH_COOLDOWN.md#12-当日終了の定義v21-動的決定) 参照。

## 3. 資金・DD — 4層防御（web-roadmap §11 実装化）

| 層 | 条件 | 自動アクション |
|----|------|----------------|
| 1 | bankroll減 | 追い下げ（既存 config） |
| 2 | 常時 | fractional Kelly 0.25 |
| 3a | DD -20% | safety_factor → 0.15 |
| 3b | DD -30% | 新規購入停止勧告 + モード semi→manual 提案 |
| 3c | DD -40% | emergency_stop |
| 4 | bankroll < 初期10% | emergency_stop |

UI: コックピットヘッダに DD% と tier 表示。

## 4. Themis「目隠し」原則

自動購入でも **Orchestrator が馬名で判断しない**。

- 入力: `bets.json` の機械的フィールドのみ
- 禁止: 「有名騎手だから承認」等の UI ショートカットに ML 以外の理由を混ぜない（memo は事後分析用）

## 5. 税務・記録（参考）

### 5.1 記録すべき項目

| 項目 | ソース |
|------|--------|
| 発走日 | race_id |
| 開催・レース | race_id 分解 |
| 券種・買い目 | bets / ledger |
| 投票額 | amount |
| オッズ（判断時点） | confirmed_bets snapshot |
| 払戻 | settle_purchases / mykeibadb |
| 判断根拠 | EV, gap, preset, model_version |
| タイムスタンプ | 各イベント ISO8601 |

### 5.2 ledger の税務価値

- 「いつ・何を根拠に・いくら買おうとしたか」を時系列で残す
- IPAT成否が取れない期間も **意図と計画** の証跡になる
- 改ざん防止: Phase 4 でファイルハッシュ or 追記のみログ（review Phase 4）

### 5.3 雑所得 vs 一時所得

- 継続的・営利・大量購入は雑所得リスク（判例・freee解説参照）
- システムは **税引後EV** を将来組み込み（review Phase 4）— 朝会では方針のみ

> **記録の最終確定は日次クローズで**: ledger / TARGET 履歴 / IPAT 実投票履歴 CSV の三層を毎日突合し、`data3/reports/{date}.md` に差分レポートを残す。雑所得申告の元データはこのクローズ済 `purchases` + IPAT CSV 原本（7年保存）が SoT。詳細は [11_DAILY_CLOSE.md](./11_DAILY_CLOSE.md) 参照。

## 6. セキュリティ

| 項目 | 方針 |
|------|------|
| 認証情報 | リポジトリ外、暗号化ストア |
| Web API | ローカル/VPN のみ（既存 IIS 前提） |
| 監査 | `stopped_by`, `approved_by` を ledger に（Windowsユーザー名可） |
| ログ漏洩 | FF CSV パスはログ可、パスワードは不可 |

## 7. TARGET / IPAT 規約リスク

TARGET FAQ より:

- 非公開仕様の解析利用、予告なく機能停止あり
- 利用は自己責任・同意チェック必須

**運用SOPに含める文言（案）**

1. 毎回 IPAT 画面で買い目・金額確認
2. 一括投票後は IPAT「直前の投票結果」確認
3. 機能不全時は manual モードに切替

## 8. テスト・リリースゲート

| ゲート | 条件 |
|--------|------|
| G0 | ledger スキーマレビュー |
| G1 | 非開催日ドライラン |
| G2 | 100円×1レース本番（人手確認） |
| G3 | 1開催日フル semi モード |
| G4 | API/DLL ルートは別途 PoC ゲート |

## 9. インシデント対応 Runbook（要約）

| 深刻度 | 例 | 手順 |
|--------|-----|------|
| S1 | 意図しない高額投票 | 緊急停止 → IPAT確認 → ledger FIX → 振り返り |
| S2 | FF誤出力 | 停止 → 誤ファイル削除 → TARGET再取込禁止確認 |
| S3 | vb_refresh停止 | manualモード → 手動オッズ → 事後vb_refresh |

## 10. 朝会で合意すべき安全パラメータ（初期値案）

| パラメータ | 初期値 |
|-----------|--------|
| min_minutes_before_post | 7 |
| max_daily_auto_races | 20 |
| max_race_amount | bankroll×2% |
| auto_ff モード | **無効**（フラグで隠す） |
| stale_minutes_after_ff | 5 |

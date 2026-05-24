# 朝会用ブリーフ — 自動購入（2026-05-23）

> 読了目安: **15分**。深掘りは各章ドキュメントへ。

---

## 1. 今日決めたいこと（3つ）

| # | 論点 | 選択肢 | 推奨（事前案） |
|---|------|--------|----------------|
| A | **自動化の定義** | ①完全無人 ②半自動（人が最終投票） ③通知のみ | **②半自動**から開始 |
| B | **実行経路の第一候補** | TARGET IPAT連動 / JRA-IPAT-API / ブラウザ自動化 / 即PAT DLL | **TARGET IPAT連動**（既存FF CSV資産を活かす） |
| C | **最初のMVPスコープ** | 状況UIのみ / JIT Phase1 / 締切10分前FF自動出力 | **状況UI + JIT Phase1**（購入実行はまだ手動でも可） |

---

## 2. 現在地（30秒）

```
[実装済み] ML予測 → bets.json → Web(/predictions, /bankroll) → FF CSV → TARGET手動取込
[人手]     TARGET → IPAT画面で最終「投票」ボタン
[未実装]   IPAT無人投票、購入オーケストレータ、購入実行ログの監査、締切トリガ購入
```

- **vb_refresh**: 5分間隔でオッズ再計算（購入トリガは無し）
- **bankroll/check**: 日上限・レース上限のみ（購入前ガードは部分的）
- **ExecuteTab**: FF CSV出力・買い確定（`confirmed_bets`）はあるが、**投票成否・IPAT状態は見えない**

---

## 3. 外部調査で確定した事実（WEB検索 2026-05-22）

### TARGET IPAT連動（公式FAQ）

- TARGETは IPAT に買い目を**自動入力**できる（[IPAT連動機能設定](https://targetfaq.jra-van.jp/faq/detail?id=473)）
- **最終の「投票」ボタンは必ず人手**（完全無人ではない）
- IPAT仕様は非公開解析のため、**予告なく機能停止・誤入力の可能性**あり → 投票前の目視確認が必須
- 複数レース一括時、一部失敗しても他は通るが、**どのレースが成功したかTARGETに返らない**場合あり

### 代替経路

| 経路 | 概要 | 備考 |
|------|------|------|
| [JRA-IPAT-API](https://www.team-nave.com/system/jp/products/ipatapi/) | 有償クラウドAPI、仕様公開 | マルチPF、SSL。利用制限要確認 |
| [ipathelper_dll](https://github.com/Mikimini9627/ipathelper_dll) | Windows DLL、即PAT操作 | 非公式・メンテリスク |
| Playwright等 | IPAT Web UI操作 | ToS/障害リスク高、松風教訓と相性悪い |

### 税務（参考・法的助言ではない）

- 継続的・営利目的・大量購入 → **雑所得**の判例あり（MJS税務判例PDF等）
- 雑所得なら**外れ馬券も経費**にできる一方、課税範囲が広がる
- 自動購入でも **発走日・レース・投票額・払戻の記録** が重要（国税庁エクセル集計の慣行）

---

## 4. 推奨アーキテクチャ（TO-BE 概要）

松風8モジュールの **L4 Themis（購入決定）** と **L5 購入実行** を分離し、間に **Orchestrator（新規）** を挟む。

```
vb_refresh / predict
    → bets.json + predictions.json
    → Themis（bet_engine + bankroll）  … 既存・拡張
    → Orchestrator（新規）            … 締切スケジュール・承認・FF生成キュー
    → TARGET FF CSV                   … 既存 target-pd-writer
    → [人手 or TARGET IPAT]           … 実行
    → Purchase Ledger（新規）         … 計画/送信/成否/払戻の監査ログ
    → Dashboard（新規）               … /auto-purchase 状況画面
```

**Themis原則を維持**: 馬名・騎手ではなく `確率 × オッズ × bankroll` のみで金額決定（`operations_architecture_principles.md`）。

---

## 5. UI/UX — 見える化の核心（議論用ワイヤー）

新規ページ案: **`/auto-purchase`**（または `/bankroll` に「実行状況」タブ追加）

### 必須表示（1画面で把握）

| ゾーン | 表示内容 |
|--------|----------|
| **ヘッダ** | 本日モード（手動/半自動/停止）、日予算残、DD%、緊急停止ボタン |
| **タイムライン** | 全レースを発走時刻順。各レースの状態バッジ |
| **レース行** | `待機 → EV再計算 → 承認待ち → FF出力済 → TARGET取込待 → IPAT投票待 → 完了/失敗` |
| **アラート** | EV転落、上限超過、vb_refresh遅延、FF出力失敗 |
| **ログ** | 直近50イベント（時刻・race_id・アクション・結果） |

### レース状態（State Machine）

```
SCHEDULED → ODDS_REFRESHED → ELIGIBLE | SKIPPED(ev) | BLOCKED(limit)
  → PENDING_APPROVAL（半自動）
  → FF_QUEUED → FF_WRITTEN → TARGET_IMPORT_MANUAL
  → AWAITING_IPAT_CONFIRM（人手投票待ち）
  → SUBMITTED | FAILED | SETTLED
```

詳細: [04_UI_UX_DESIGN.md](./04_UI_UX_DESIGN.md)

---

## 6. フェーズ案（合意用）

| Phase | 名称 | 成果物 | 購入自動度 |
|-------|------|--------|------------|
| **0** | 見える化MVP | `/auto-purchase` + `purchase_ledger.json` 手動更新 | 0%（記録のみ） |
| **1** | JIT可視化 | web-roadmap §13 Phase1（オッズ乖離・EV転落バッジ） | 0% |
| **2** | 半自動FF | 締切N分前にFF自動生成 + 承認ボタン | 30%（IPATは手） |
| **3** | TARGET連携手順書 | TARGET IPAT連動の運用SOP + 成否確認フロー | 50% |
| **4** | API/DLL検証 | JRA-IPAT-API or 即PATのPoC（別枠・有償判断） | 70–90% |

詳細工数: [06_PHASED_ROADMAP.md](./06_PHASED_ROADMAP.md)

---

## 7. リスク — 止めるべき条件（合意必須）

| レベル | 条件 | アクション |
|--------|------|------------|
| 黄 | DD -20% | Kelly safety 0.15 に自動低下 |
| 橙 | DD -30% | 新規購入停止勧告 |
| 赤 | DD -40% または bankroll < 初期10% | **緊急全停止**（Orchestrator kill switch） |
| 実行 | FF出力後24h以内にIPAT確認なし | 該当レースを `STALE` 警告 |
| 実行 | vb_refresh 2回連続失敗 | 自動購入モード自動オフ |

詳細: [05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md)

---

## 8. 朝会アジェンダ（60分案）

| 時間 | 内容 |
|------|------|
| 0–10分 | 本ブリーフ共有・用語合意（半自動の定義） |
| 10–25分 | 経路Bの選択（TARGET first vs API PoC 並行） |
| 25–40分 | UIゾーン・状態機械のレビュー（04章） |
| 40–50分 | Phase 0–2 のスプリント割当 |
| 50–60分 | エージェント起票（08章のどれを誰が実行するか） |

---

## 9. 議論後の次アクション（テンプレ）

- [ ] Phase 0: `purchase_ledger` スキーマ合意 → API stub
- [ ] Phase 0: `/auto-purchase` ページ骨格（モックデータで可）
- [ ] Phase 1: predictions 画面にオッズ乖離カラム（web-roadmap §13）
- [ ] 運用: TARGET IPAT連動のテスト投票（非本番レースで1件）
- [ ] 検討: JRA-IPAT-API の料金・利用制限の問い合わせ

---

## 10. エージェント起票

実装を並列化する場合は [08_AGENT_DELEGATION_PROMPTS.md](./08_AGENT_DELEGATION_PROMPTS.md) からコピペで依頼可能。

---

## 11. 2026-05-23 朝会後の更新（追記）

朝会の議論を経て、以下の決定事項を別文書として整理しました。本ブリーフの「事前案」を上書きする内容を含むので、必ず以下を参照してください。

| 決定領域 | 参照先 | 主な決定事項 |
|---|---|---|
| **My印体系** | [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §1 | 8段階（◎○▲△Ⅲ穴消?）に確定。印は「順位」でなく「メタ情報」。 |
| **設計思想** | [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §2 | 「俺にはできない買い方を見つける」を北極星に。 |
| **F戦法 / Step ロードマップ** | [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §3 | Step 1（単◎）→ 2（+ワイド）→ 3（+馬連/馬単）→ 4（F完成）。 |
| **賭けスタイル4分類** | [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §4 | **却下**。固定カテゴリなし、事後分類用ラベルに留める。 |
| **シミュ基盤の配置** | [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) §5 | `ml/strategies/` + `ml/sim/ticket_sweep.py`。 |
| **bankroll 制御** | [10_BANKROLL_CONTROL.md](./10_BANKROLL_CONTROL.md) | 絶対額上限・動的調整なし・レース個別上書き対応。 |
| **Phase 1 削除** | [06_PHASED_ROADMAP.md](./06_PHASED_ROADMAP.md) §3 | JIT 可視化は Session 118 で /odds-race に統合済のため削除。 |
| **Step 段階追加** | [06_PHASED_ROADMAP.md](./06_PHASED_ROADMAP.md) §6.5, §11 | Phase（インフラ）× Step（戦略）の2軸マトリクス。 |

§1 のテーブル「今日決めたいこと」のうち、A・B は事前案どおり確定。C（最初のMVP）は「**Phase 0（見える化MVP）+ Step 1（単◎のみ）並走**」に具体化されました。

— 記録: シズネ


# 08. 別エージェント依頼用プロンプト集

> コピペして新規チャット / Task ツールに渡す。パスは `c:\KEIBA-CICD\_keiba\keiba-cicd-core` 基準。

---

## 共通コンテキスト（全プロンプトの先頭に付与）

```
あなたは keiba-cicd-core の実装担当です。
設計の SoT: docs/auto-purchase/ （特に 03, 04, 07）
既存: keiba-v2/web (Next.js), keiba-v2/ml (Python), data3 JSON
制約:
- 最小diff、既存規約に合わせる
- IPAT認証情報をリポジトリにコミットしない
- 半自動がデフォルト（完全無人投票は実装しない）
- 日本語でコミットメッセージ・コメント（必要最小）
読了必須:
- docs/auto-purchase/00_MEETING_BRIEF_20260523.md
- docs/auto-purchase/03_ARCHITECTURE_PROPOSAL.md
- docs/auto-purchase/07_DATA_SCHEMA_AND_EVENTS.md
```

---

## Prompt A: Phase 0 — ledger API + 初期化

```
【タスク】Phase 0: purchase_ledger の API と初期化スクリプト

実装:
1. data3/userdata/purchase_ledger/ と auto_purchase_config.json の読み書き
2. Next.js API:
   - GET /api/auto-purchase/status?date=
   - POST /api/auto-purchase/mode
   - POST /api/auto-purchase/races/[raceId]/approve
   - POST /api/auto-purchase/races/[raceId]/reject
   - POST /api/auto-purchase/races/[raceId]/confirm-ipat
   - POST /api/auto-purchase/races/[raceId]/target-imported
   - POST /api/auto-purchase/emergency-stop
3. Python: ml/purchase_ledger_init.py — predictions + bets から当日 ledger 生成
4. 型定義 web/src/lib/auto-purchase/types.ts（07章準拠）

既存参考:
- web/src/app/api/bankroll/confirmed-bets/route.ts
- web/src/app/api/purchases/[date]/route.ts
- web/src/lib/config.ts (AI_DATA_PATH)

受け入れ:
- 非開催日でも空ledger返却
- approve で state が PENDING→FF_QUEUED（FFはまだ書かなくてよい）
- emergency_stop で mode=stopped

成果物: 実装コード + 簡易動作確認手順を README に追記
```

---

## Prompt B: Phase 0 — コックピット UI

```
【タスク】Phase 0: /auto-purchase コックピットページ

設計: docs/auto-purchase/04_UI_UX_DESIGN.md

実装:
1. web/src/app/auto-purchase/page.tsx
2. コンポーネント: CockpitHeader, NextActionBar, RacePipelineTable, PipelineDots, RaceDetailDrawer, EventLogPanel, EmergencyStopButton
3. hooks: useAutoPurchaseStatus (SWR 30s)
4. bankroll ExecuteTab から「コックピット」リンク

UI:
- shadcn/ui 既存スタイル
- 状態バッジ・6段パイプドット
- 承認/見送り/confirm-ipat ボタン

API: Prompt A のエンドポイントを使用

受け入れ:
- モックなしで status API から描画
- 緊急停止が動作

禁止: FF自動出力、Orchestrator（Phase 2）
```

---

## Prompt C: Phase 1 — JIT 可視化（predictions）

```
【タスク】Phase 1: web-roadmap §13 Phase 1 — オッズ乖離・EV転落UI

設計: keiba-v2/docs/roadmap/web-roadmap.md §13 Phase 1
連携: docs/auto-purchase/04_UI_UX_DESIGN.md §6.1

実装:
1. /predictions の推奨テーブルに「オッズ変動」カラム（予測時比%）
2. ライブ EV < 1.0 で「見送り推奨」バッジ
3. 「あとX%下落でEV<1」閾値（bet-engine.ts の既存計算を拡張）
4. 該当行から /auto-purchase?raceId= へのリンク

データ:
- predictions.json の予測時オッズ vs 最新（オッズAPI or entries）

受け入れ:
- オッズ未更新時は「—」表示でクラッシュしない
```

---

## Prompt D: Phase 2 — Purchase Orchestrator（Python）

```
【タスク】Phase 2: purchase_orchestrator — 締切前FF自動出力

設計: docs/auto-purchase/03_ARCHITECTURE_PROPOSAL.md, 07_DATA_SCHEMA_AND_EVENTS.md

実装:
1. keiba-v2/ml/purchase_orchestrator.py
   - main_tick(): 1分ごとに呼ばれる想定
   - レース post_time - ff_trigger_minutes で FF_QUEUED を処理
2. FF出力: target-pd-writer 相当を Python から呼ぶか、内部HTTPで auto-bet API
3. bankroll ガード: config.json 上限、emergency_stop
4. vb_refresh 連携: last_vb_refresh_at が古いレースは警告イベント
5. scripts/setup_purchase_orchestrator_scheduler.bat

ledger 更新:
- FF_WRITTEN / FAILED / STALE
- idempotency_key で重複防止

受け入れ:
- --dry-run でファイルを書かずログのみ
- semi モードで未承認レースはスキップ

参考: ml/vb_refresh.py, web/src/lib/data/target-pd-writer.ts
```

---

## Prompt E: TARGET IPAT 運用 SOP ドキュメント

```
【タスク】運用ドキュメント TARGET_IPAT_SOP.md

参照:
- TARGET FAQ IPAT連動（WEBで確認済み要点を引用URL付き）
- docs/auto-purchase/02_INTEGRATION_OPTIONS.md
- docs/auto-purchase/05_RISK_COMPLIANCE.md

成果物: docs/auto-purchase/TARGET_IPAT_SOP.md

内容:
1. TARGET 環境設定（IPAT連動）チェックリスト
2. FF CSV 取込手順（既存）
3. IPAT投票手順（最終ボタンは人手）
4. 一括投票失敗時の復旧（IPAT直前の投票結果確認）
5. KeibaCICD コックピットでの完了報告手順
6. トラブルシューティング表

図: mermaid フロー1つ
```

---

## Prompt F: Phase 4 PoC — JRA-IPAT-API 調査のみ

```
【タスク】JRA-IPAT-API の調査レポート（実装しない）

調査:
- https://www.team-nave.com/system/jp/products/ipatapi/
- 料金、利用制限、対応券種、投票照会API
- KeibaCICD bets.json とのマッピング案
- TARGETルートとの比較表

成果物: docs/auto-purchase/09_JRA_IPAT_API_POC_REPORT.md

含める: 推奨/非推奨、Phase 4 ゲート条件、セキュリティ注意
```

---

## Prompt G: 統合テスト・ドライラン

```
【タスク】自動購入 Phase 0–2 のドライラン手順とスモークテスト

実装:
1. docs/auto-purchase/10_DRYRUN_CHECKLIST.md
2. 過去日付（data3 にデータがある日）で ledger_init → status → UI操作の手順
3. 可能なら web 側の最小 Vitest or API route テスト（approve, emergency_stop）

制約: 本番IPATには接続しない

成果物: チェックリスト + あればテストコード
```

---

## 並列実行の推奨順序

| 順 | プロンプト | 依存 |
|----|-----------|------|
| 1 | A | なし |
| 1 | E | なし |
| 2 | B | A（モックAPIで先行可） |
| 2 | C | なし |
| 3 | D | A |
| 4 | G | A,B,D |
| 任意 | F | なし |

---

## レビュー用プロンプト（朝会後）

```
keiba-cicd-core の docs/auto-purchase/ を読み、
Phase 0 実装PRをレビューしてください。

観点:
- ledger スキーマ準拠（07章）
- 安全: emergency_stop, idempotency
- UI: 04章の必須表示
- 既存 bankroll/purchases との整合

差分ファイル一覧を出力し、ブロッカーを優先度付きで列挙。
```

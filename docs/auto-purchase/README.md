# 自動購入（Auto-Purchase）調査・設計パッケージ

> **作成日**: 2026-05-22  
> **目的**: keiba-cicd-core における自動購入の調査・設計・UI/UX・議論準備  
> **想定読者**: 明日の朝会参加者、実装担当エージェント

## ドキュメント一覧

| # | ファイル | 内容 | 朝会での使い方 |
|---|----------|------|----------------|
| 0 | [00_MEETING_BRIEF_20260523.md](./00_MEETING_BRIEF_20260523.md) | **15分で読める要約**・決定事項案・議論アジェンダ | 最初に全員で読む |
| 1 | [01_CURRENT_STATE_ASIS.md](./01_CURRENT_STATE_ASIS.md) | 現状AS-IS・実装済み/未実装ギャップ | 現在地の確認 |
| 2 | [02_INTEGRATION_OPTIONS.md](./02_INTEGRATION_OPTIONS.md) | IPAT連携手段の比較（WEB調査含む） | 技術ルート選択 |
| 3 | [03_ARCHITECTURE_PROPOSAL.md](./03_ARCHITECTURE_PROPOSAL.md) | 松風8モジュール準拠のTO-BE設計 | アーキ合意 |
| 4 | [04_UI_UX_DESIGN.md](./04_UI_UX_DESIGN.md) | 自動購入状況の見える化UI/UX | 画面・体験の合意 |
| 5 | [05_RISK_COMPLIANCE.md](./05_RISK_COMPLIANCE.md) | 実行リスク・税務・安全策 | 止める条件の合意 |
| 6 | [06_PHASED_ROADMAP.md](./06_PHASED_ROADMAP.md) | Phase 0–4・工数感・依存関係 | 何から着手するか |
| 7 | [07_DATA_SCHEMA_AND_EVENTS.md](./07_DATA_SCHEMA_AND_EVENTS.md) | 購入オーケストレーション用JSON・イベント | 実装のデータ契約 |
| 8 | [08_AGENT_DELEGATION_PROMPTS.md](./08_AGENT_DELEGATION_PROMPTS.md) | 別エージェント依頼用プロンプト集 | 並列実装の起票 |
| 9 | [09_MY_MARKS_AND_STRATEGY.md](./09_MY_MARKS_AND_STRATEGY.md) | **My印体系の確定版 / F戦法 / Step 1–4 / シミュ基盤配置**（2026-05-23追加） | 戦略層の意思決定 |
| 10 | [10_BANKROLL_CONTROL.md](./10_BANKROLL_CONTROL.md) | **bankroll 制御方針 / config.json 拡張 / check API 拡張**（2026-05-23追加） | 資金防衛ライン |
| 11 | [11_DAILY_CLOSE.md](./11_DAILY_CLOSE.md) | **日次クローズ / ledger × TARGET履歴 × IPAT 三層突合 / 差分レポート**（2026-05-23追加β1） | 1日の購入の最終確定 |
| 12 | [12_KILL_SWITCH_COOLDOWN.md](./12_KILL_SWITCH_COOLDOWN.md) | **kill switch v2.1: 当日途中停止 + 翌日オプトイン UI（直近7日 ROI スパークライン付き）+ 毎朝 manual 始動 + 「当日終了 = 最終レース+30分」動的決定** | 緊急停止 + 毎朝の人間判断レイヤ |
| 13 | [13_AUTO_RECONCILIATION.md](./13_AUTO_RECONCILIATION.md) | **自動突合エンジン（IPAT × ledger）/ 通知 / kill switch 連動**（2026-05-23 v2.0 で連続日数判定廃止） | 不一致検出・「沈黙はOK」原則 |
| 14 | [14_LEDGER_SCHEMA.md](./14_LEDGER_SCHEMA.md) | **Ledger v2 スキーマ / portfolio_id / raw_legs / 22 イベント全登録 / SHA256 追記台帳**（2026-05-23 v1.1）| 戦略メタ・税務・監査 |
| 15 | [15_STEP2_WIDE_PORTFOLIO.md](./15_STEP2_WIDE_PORTFOLIO.md) | **🚫 廃止 (2026-05-24)**：F戦法機械化軸を捨て「印無視 IPAT 自動投票」へピボット | 設計史として保存 |
| 16 | [16_TARGET_AUTOCLICK.md](./16_TARGET_AUTOCLICK.md) | **TARGET 投票ダイアログ自動押下エンジン (pywinauto)**（2026-05-24 同日に実装+実投票2回成功 0029・0030） | Phase 4 完全自動投票の核心 |

## 関連既存ドキュメント

- `keiba-v2/docs/roadmap/web-roadmap.md` §7-3, §13（自動購入・JIT）
- `keiba-v2/docs/betting_system_design.md`（VB Floor・購入プラン）
- `keiba-v2/docs/ml-experiments/review_ml_accuracy_and_betting_strategy.md` Phase 4
- `docs/knowledge/insights/operations/operations_architecture_principles.md`（松風8モジュール）

## 結論（1行）

**現状は「推奨→FF CSV→人手TARGET→人手IPAT」まで。最短の自動化は TARGET IPAT連動の半自動化＋ KeibaCICD 側のオーケストレーション層と状況ダッシュボードの新設。**

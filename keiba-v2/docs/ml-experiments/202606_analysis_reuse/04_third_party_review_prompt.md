# 04. 第三者レビュー依頼プロンプト（コピペ用）

このドキュメントは、ここまで作成した分析結果・再利用案を  
第三者視点で「レビュー / 議論 / ブレスト / ブラッシュアップ」してもらうための依頼テンプレートです。

---

## A. 統合版プロンプト（推奨）

```text
あなたは、競馬AIプロダクトの「第三者レビュアー」です。
目的は、既存の分析結果と実装アイデアを、実運用で使える形に磨き上げることです。

## 前提
- プロジェクト: KeibaCICD (ML予測 + 最終買い目判断)
- 今回の主眼:
  1) ML本体に直結しないが最終買い目で効く「プラスオプション」
  2) レース表画面での説明可能性・意思決定支援UI
  3) 分析→運用→検証のループ強化

## 対象ドキュメント
- docs/ml-experiments/202606_analysis_reuse/README.md
- docs/ml-experiments/202606_analysis_reuse/01_master_index.md
- docs/ml-experiments/202606_analysis_reuse/02_enhancement_backlog.md
- docs/ml-experiments/202606_analysis_reuse/03_change_log.md
- docs/ml-experiments/202606_ml_plus_options_and_race_ui_ideas.md
- docs/ml-experiments/202606_rpci_ml_bridge_review.md
- docs/ml-experiments/202606_idm_ml_bridge_review.md
- docs/ml-experiments/202606_course_dictionary_ml_bridge_review.md
- docs/ml-experiments/202606_trainer_patterns_ml_bridge_review.md
- docs/ml-experiments/202606_slow_start_ml_bridge_review.md
- docs/ml-experiments/202606_pedigree_ml_bridge_review.md
- docs/ml-experiments/202606_jockey_close_finish_ml_bridge_review.md

## 依頼したいこと
以下を「厳しめの第三者視点」で実施してください。

### 1. レビュー（品質監査）
- 論理破綻、矛盾、過剰な楽観、リーク懸念、運用上の穴を指摘
- 「実装しても効果が薄い/危険」な案を明確化
- 優先順位の妥当性（今やるべきか）を再評価

### 2. 議論（トレードオフ整理）
- 効果 vs コスト
- 短期リターン vs 中長期負債
- 精度改善 vs 運用複雑化
- 説明可能性 vs 実装速度

### 3. ブレスト（代替案の発散）
- 現案より低コストで同等効果が狙える代替案を提案
- 「学習再訓練なしでできる改善」を優先的に提案
- 最終買い目意思決定に効く新しい軽量オプションを提案

### 4. ブラッシュアップ（収束）
- 実行順序を3フェーズ（今週 / 今月 / 来月）で再設計
- `02_enhancement_backlog.md` を置換できるレベルで
  - ID
  - タスク
  - 目的
  - 依存関係
  - 完了条件
  - リスク
  を具体化

## 評価軸（必須）
- AUCだけでなく、`gap>=k` 条件下の ROI / CI / 件数 を主評価にすること
- 小標本・低信頼データには必ずガード（CI, stability, effective_n）を要求
- PIT（時点整合）違反の疑いがある案は、必ず警告を出すこと

## 出力フォーマット（この順）
1) 重大な懸念トップ5（理由付き）
2) 即時採用してよい案トップ5（理由付き）
3) 保留/却下すべき案（理由付き）
4) 改訂版バックログ（表形式）
5) まず1週間でやる実行プラン（3〜5タスク）
6) 追加で確認が必要な論点（質問形式）

## 制約
- 過度に抽象化せず、実装可能な粒度で書く
- 可能なら既存ファイル名・機能名に紐づける
- 日本語で回答する
```

---

## B. 短縮版プロンプト（軽い壁打ち用）

```text
以下の202606系レビュー群を第三者視点で厳しめにレビューしてください。
目的は「最終買い目判断で効くプラスオプション」と「レース表UI改善」を実装可能な形に絞ることです。

対象:
- docs/ml-experiments/202606_analysis_reuse/01_master_index.md
- docs/ml-experiments/202606_analysis_reuse/02_enhancement_backlog.md
- docs/ml-experiments/202606_ml_plus_options_and_race_ui_ideas.md
- 主要レビュー一式（rpcI/idm/course/trainer-patterns/slow-start/pedigree/jockey-close-finish）

やってほしいこと:
1) 危険・弱い案を切る
2) 低コスト高効果案を上位化
3) 1週間で回せる実行計画に再編

必須評価軸:
- `gap>=k` ROI/CI/件数
- PIT整合
- 低信頼データガード（CI/effective_n/stability）

出力:
- 懸念トップ5
- 即採用トップ5
- 改訂バックログ
- 1週間実行プラン
```

---

## C. 使い分けガイド

- しっかりレビューしてもらう: **A. 統合版**
- まず壁打ちで方向だけ見る: **B. 短縮版**


# UI/UX レビュー バックログ（2026-06 / ふくだ当日馬券目線）

> **目的**: 画面増加（page 約42本）を機に、当日に馬券を買うふくだ目線で UI/UX を棚卸し。
> **ソース**: Fable 5 による全画面レビュー → カカシが実コードでファクトチェック（裏取り）した**訂正版**。
> **方針**: 「当日、迷わず・速く・正しく買えるか」最優先。深刻度 P0=損金直結 / P1=判断を著しく遅らせる / P2=不便だが回避可 / P3=見栄え。

---

## 0. 検証サマリー（レポート精度のファクトチェック）

LLM レビューの主要主張を実コードで裏取りした結果。**目玉2件に技術的誤りがあった**ため、そのまま着手せず訂正した。

| レポート主張 | 判定 | 根拠（file:line） |
|---|---|---|
| 「42画面中36画面のタブが"出馬表"のまま / metadata定義は6画面のみ」 | ❌ 誤り | ルート `app/layout.tsx:21` に title template、`analysis/layout→'分析'` 等 section layout 約30本がタイトル供給済。実際に汎用"出馬表"のままは `/`(意図的)・models・changelog・my-bets の実質3枚＋"分析"止まり5枚だけ |
| 「odds-board / odds-race を force-dynamic化しろ」 | ❌ 的外れ | 両画面とも `'use client'` で RT_DATA をクライアント fetch。force-dynamic は無効。鮮度は P0-1 の取得時刻表示で対応 |
| 「オッズの as-of 時刻が本線に出ない」 | ✅ 妥当 | odds-board に取得時刻表示なし（あるのは更新ボタン `odds-board/page.tsx:792` のみ）。remedy が違うだけで指摘自体は正しい |
| 「rating の H1 が"BR分析"（ナビ=レイティング分析）」 | ✅ 正確 → **対応済** | `analysis/rating/page.tsx` H1/パンくず/コメント |
| 「PurchasePlanSection が二重実装」 | ❌ 誤り（深掘りで判明） | 2ファイルは**別物**: race-v2版=レース単位/`/api/purchases`/現役、bankroll版=日単位/`/api/bankroll/plans`/**死蔵**（export コメントアウト・参照ゼロ）。差分980行＝ほぼ別実装。マージ不能。実体は「現役1＋死蔵1が同名」→ **死蔵削除で解決**（P1-2 対応済） |
| 「確定ボタンが購入実行と紛らわしい / 説明なし」 | △ 半分 | `ExecuteTab.tsx:1432` に既にツールチップ `買い確定（推奨から消えても記録残す）` あり。ラベル可視化の改善余地は認める |

**教訓**: LLM レビューは `layout.tsx` を見ず `page.tsx` だけで「36画面」と断定した過大評価。実コード断面の裏取り必須。cf. メモリ `feedback_no_fabricated_tool_results`。

---

## 1. 対応済み（2026-06-13 セッション）

- ✅ **bankroll 配下3画面のタブ名**: `/bankroll`→推奨馬券 / `/bankroll/auto`→自動投票 / `/bankroll/results`→収支管理
- ✅ **rating H1 統一**: `BR分析`→`レイティング分析`（H1・パンくず・コメントの3箇所。`BR統計` 等の単独BRラベルは温存）
- ✅ **タブ未設定8画面に title 付与**（メニュー名に一致）:
  - `/models`→Models / `/changelog`→Changelog / `/my-bets/[raceId]`→My買い目
  - `/analysis/selective-bets`→Selective 候補 / `/analysis/character-sim`→キャラ別シミュレーション
  - `/analysis/jockey-close-finish`→騎手接戦分析 / `/analysis/polaris-segments`→polaris セグメント分析 / `/analysis/specialists/niigata-1000m`→千直

### 対応済み（追加・同セッション後半）

- ✅ **P0-1 オッズ as-of 表示**: `OddsFreshness` 型 + `happyoTimeToMs()`（`rt-data-types.ts`）／O1 の発表時刻 HappyoTime を `getRaceOddsFromRt` が保持（従来は破棄）／`/api/odds/race` が DB時系列=snapshotTime・RT=happyoTime を正確な as-of として返却（OB15速報は `exact:false`＝「速報」表示で正直に）／共通 `OddsFreshnessBadge`（緑/橙/赤・30秒ライブ更新・着順確定レースは警告抑制）を **odds-race / odds-board / ExecuteTab(生成日時ベース)** の3面に配線。force-dynamic 案は不採用（両画面クライアント fetch）
- ✅ **P1-2 PurchasePlanSection**: 検証の結果「二重実装」は誤りで、実体は **現役1（race-v2・レース単位・`/api/purchases`）＋ 死蔵1（bankroll・日単位・export コメントアウト・参照ゼロ・v1→v2 移動の legacy）**。マージ不能かつ不要 → **死蔵 `components/bankroll/PurchasePlanSection.tsx`（666行）を削除** + `bankroll/index.ts` のコメント export 行除去（挙動リスクゼロ）
- ✅ **P1-3 推奨表の行リンク**: `ExecuteTab` 推奨テーブルの「場」セルに **詳細→（races-v2）/ オッズ→（odds-race）** を列数を変えず追加（タスク②のクリック数 3〜4→1）。別タブ遷移で 推奨リストを保持

---

## 2. 却下 / 着手しない（前提が誤り）

- ❌ **odds-board / odds-race の force-dynamic化** — 両画面はクライアント fetch。無効。→ 鮮度は P0-1 で対応
- ❌ **「36画面に metadata 一括付与」** — 事実誤認。残りは上記8画面のみで対応完了

---

## 3. バックログ（訂正版・未着手）

### P0 — 損金直結

| ID | 画面 | 内容 | 規模 | メモ |
|---|---|---|---|---|
| ~~P0-1~~ ✅済 | odds-board / odds-race / 推奨馬券(ExecuteTab) | **オッズ取得時刻（as-of）の表示** | 中 | 実装完了。mtime ではなく **O1 発表時刻 HappyoTime / DB snapshotTime**（=正確な as-of）を採用。OB15速報は時刻無のため「速報」表示で正直に。橙=10分/赤=30分（ExecuteTab は 20/45分）。**残課題**: odds1_tansho に発表時刻列があれば DB-final 速報の正確な as-of を出せる（要スキーマ確認） |

### P1 — 判断を著しく遅らせる / 二重計上リスク

| ID | 画面 | 内容 | 規模 |
|---|---|---|---|
| P1-1 | 推奨/自動投票/レース詳細購入計画 | **「買い」概念の三重化を SoT 統一**（候補→予定→投票/購入→結果）。収支を自動+手動の単一ビューへ。用語（確定/購入済/投票成立/planned）統一 | 大 |
| ~~P1-2~~ ✅済 | PurchasePlanSection | 「二重実装」は誤り＝**死蔵ファイル削除で解決**（§0・§1 参照）。race-v2版が per-race 購入レコードの SoT（`/api/purchases`）＝ P1-1 の SoT 統一で参照すべき正本 | 小 |
| ~~P1-3~~ ✅済 | 推奨馬券(ExecuteTab) | 「場」セルに**詳細→/オッズ→**を列数据え置きで追加。別タブ遷移 | 中 |
| P1-4 | レース詳細(races-v2) | 上部に**判断サマリー固定**（◎○▲ + 単勝オッズ + EV + 推奨買い目）。発走前の高速判断でスクロール削減 | 中（要実機でスクロール量確認） |

### P2 — 不便だが回避可

| ID | 画面 | 内容 | 規模 |
|---|---|---|---|
| P2-1 | ExecuteTab | 確定ボタンの**ラベル可視化**（ツールチップは既存）。購入実行との視覚的分離 | 小 |
| P2-2 | 全画面 | **コンテナ幅の規格化**（max-w-5xl〜8xl 混在 + `className="container"` 併用撤去）。cf. メモリ `web-layout-width-system` | 中 |
| P2-3 | ナビ / demo/* | **本番と実験の隔離**（ナビから `/demo/*` を分離 or「実験」セクション化、demo/cards は nav 非掲載） | 小〜中 |
| P2-4 | 推奨馬券 | 列ヘッダに**凡例ツールチップ**（VBs / ARd / AR / 複EV の意味）。スマホは主要列のみ+詳細展開 | 小 |
| P2-5 | obstacle / ml / formation / changelog 等 | **戻る/パンくず欠落画面**に共通レイアウトで導線強制 | 中 |

### P3 — 見栄え・好み

| ID | 内容 |
|---|---|
| P3-1 | H1 表記揺れ統一（絵文字有無 / 英和混在: ML Report / Formation Analysis vs 和名） |
| P3-2 | 色のみ依存箇所に記号/ラベル併記（市場シグナル/強度/EV、一部実施済） |
| P3-3 | 出馬表カード外部リンクのタップ領域 ≥44px / 半角カナ表記の正規化（要実機） |

---

## 4. 本腰の改善テーマ（中期）

1. **オッズ鮮度を一級市民に**: 「as-of 時刻 + 鮮度状態（最新/N分前/要更新）」を共通コンポーネント化し、オッズ表示全画面に強制適用。EV/買い目に「使ったオッズ時刻」を必ず併記。EV>1.0 で実際に金を張るシステムの土台。
2. **「買い」の単一フロー化**: 推奨確定 / 自動LIVE / 手動購入計画 を1本の購入ライフサイクルに再設計。SoT 統一で二重計上と「どれが本物か」問題を根絶。
3. **IA再編 + デザインシステム化**: `<PageLayout>` / `<AnalysisPageLayout>` でタイトル・幅・戻り導線・H1 様式を強制。幅トークンを用途別2〜3種へ規格化。ナビを「本番（予想→買い→収支）/分析/スペシャリスト/実験/管理」で層化。

---

*記録: 2026-06-13 カカシ。レビュー本文（Fable 5）は別途。本文書が訂正版バックログの正本。*

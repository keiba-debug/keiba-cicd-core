# Backlog: 出走表 購入表示 — TARGET / ledger 重複判定

> 作成: 2026-06-07  
> 関連: `web/src/lib/data/race-purchase-reader.ts`, `RacePurchaseBadgeModal.tsx`, `14_LEDGER_SCHEMA.md`

## 現状 (2026-06-07 時点)

出走表の購入モーダルは **自動投票 (purchase_ledger)** と **TARGET手動 (PDyyyymm.CSV)** を分けて表示。

重複除外は **券種 + 馬番 + 金額** の正規化キー (`betDedupKey`) で実施。

- 券種表記ゆれ: `三連複` ↔ `3連複` を `normalizeBetType` で統一
- 3連複/馬連等: 馬番ソート
- 3連単/馬単: 馬番順序を保持

## 将来宿題: 受付番号 (IPAT receipt) による突合

### なぜやるか

- 自動投票 → TARGET CSV にも載る買い目は、**同一 IPAT 受付**なら receipt が一致する
- 券種表記・馬番表記のゆれに依存せず、**「同じ1票」** を確実に1本化できる
- 金額変更・表記バグに強い

### 前提 / ギャップ

| ソース | 受付番号 | 備考 |
|--------|---------|------|
| purchase_ledger v2 | `ipat_receipt_number` あり | `ledger-reader.ts` で表示済 |
| TARGET PDyyyymm.CSV | **未読み取り** | `target_reader.py` が BetRecord / JSON に含めていない |

**手動のみの買い目** (ledger に無い) は receipt 突合の対象外。引き続き TARGET 側に残す。

### 実装案 (Phase 2)

1. **`target_reader.py`**
   - CSV から受付番号フィールドをパース（フィールド位置要調査）
   - `get_daily_summary` の各 bet に `receipt_number` を追加

2. **`race-purchase-reader.ts`**
   - ledger の全 receipt を Set 化
   - TARGET bet で `receipt_number` が ledger Set に含まれる → **自動重複として除外**
   - receipt 無し / 不一致 → 手動候補（現行の `betDedupKey` フォールバック）

3. **UI**
   - モーダル footnote を「receipt 突合優先」に更新
   - デバッグ用: 除外理由 (receipt / key) を dev のみログ

4. **テスト**
   - 東京9R 型: 自動12点 + 手動単勝1点
   - 三連複/三連単の表記ゆれケース
   - receipt 欠損時フォールバック

### 受け入れ条件

- [ ] 自動投票分が TARGET手動に二重表示されない
- [ ] ledger に無い TARGET 買い目（真の手動）は残る
- [ ] receipt 未実装月は現行 key 方式で退避動作

### 参照

- 出走表 URL 例: `/races-v2/2026-06-07/東京/2026060705030209`
- TARGET 読込: `keiba-v1/KeibaCICD.AI/tools/target_reader.py`
- ledger API settle: `web/src/lib/bankroll/settle-ledger-runner.ts`

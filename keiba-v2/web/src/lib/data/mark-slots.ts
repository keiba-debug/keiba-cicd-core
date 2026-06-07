/**
 * TARGET 馬印スロット(markSet) の「番号 → 意味」単一定義 (SSOT)
 *
 * スロットの意味論はこのファイルだけで管理する。スロット番号を変える時は
 * ここ 1 箇所を直せば web 全体に波及する（数値リテラルの散在を防ぐ）。
 *
 * 物理マッピング（記号↔Shift-JISバイト / markSet↔フォルダ UmaMark{N}）は
 * `target-mark-reader.ts` を正本とする（ここは意味論のみ）。
 *
 * 設計: docs/auto-purchase/26_MARK_SLOT_MAP.md
 *
 * 履歴: Session 143 で AI評価 6→2 / AI購入軸 8→3 に再編。
 *       旧 2-5(VB/ARd/IDM/パドック) と 危(1同居) は廃止（auto-* route 撤去）。
 */

/** 稼働中の印スロット（番号→意味）。4-8 は将来の追加印用に空き。 */
export const MARK_SLOT = {
  /** ふくだ手動印 (◎○▲△Ⅲ穴消)。MY_DATA 直下。 */
  MY: 1,
  /** AI評価印 — KEIBACICD総合 composite(W/P/ADR)。◎○▲△Ⅲ穴。[旧6] */
  AI_EVAL: 2,
  /** AI購入軸 — 買い軸◆ / 相手◇。purchase_ledger・選定起点。[旧8] */
  AI_BUY: 3,
} as const;

export type MarkSlot = (typeof MARK_SLOT)[keyof typeof MARK_SLOT];

/** スロットの表示ラベル（UI 共通）。 */
export const MARK_SLOT_LABEL: Record<number, string> = {
  [MARK_SLOT.MY]: 'My印',
  [MARK_SLOT.AI_EVAL]: 'AI評価',
  [MARK_SLOT.AI_BUY]: 'AI購入',
};

/**
 * 廃止した自動印 route（旧 markSet 2-5 / 危）。
 * route 本体・呼び出しUI は撤去済み。将来 4-8 の空き枠で新印を作る時は
 * MARK_SLOT に追記し、ここには残骸を残さない。
 */
export const DEPRECATED_AUTO_MARK_ROUTES = [
  'auto-vb', // 旧 markSet=2 VB印
  'auto-ard', // 旧 markSet=3 ARd印
  'auto-idm', // 旧 markSet=4 IDM印
  'auto-paddock', // 旧 markSet=5 パドック印
  'auto-danger', // 旧 markSet=1 同居 危印（手動印と衝突していた）
] as const;

/**
 * My印 → 着順別確率テーブル
 *
 * ユーザー定義の印の意味:
 *   ◎: 勝ち期待、上位（1着〜3着まで全部期待）
 *   ○: 連軸2着寄り（頭よりは連軸タイプ、2着の主力）
 *   ▲: 頭も期待、ピンパー寄り（頭期待だが連軸としては○より弱）
 *   △: よくて2着まで（3着には来ない想定）
 *   ★: がんばって3着候補（1着はほぼ無し、3着専用）
 *   穴: 頭も含めて激走期待、ピンパー、ギャンブル
 *   '': 無印（ML予測から借用 → 詳細は ev-calculator）
 *
 * 数値は叩き台。運用調整前提。
 */

export interface PositionalProb {
  p1: number; // 1着確率
  p2: number; // 2着確率
  p3: number; // 3着確率
}

export const MARK_PROBS: Record<string, PositionalProb> = {
  '◎': { p1: 0.35, p2: 0.25, p3: 0.15 },
  '○': { p1: 0.12, p2: 0.28, p3: 0.20 },
  '▲': { p1: 0.18, p2: 0.22, p3: 0.15 },
  '△': { p1: 0.05, p2: 0.15, p3: 0.00 },
  '★': { p1: 0.03, p2: 0.10, p3: 0.22 },
  '穴': { p1: 0.08, p2: 0.08, p3: 0.10 },
};

/** 無印馬で ML 予測も無い場合のフォールバック（参加してるけど期待薄） */
export const NO_MARK_FALLBACK: PositionalProb = {
  p1: 0.02,
  p2: 0.03,
  p3: 0.04,
};

/** 印の表示順序（戦略フィルタ等で使用） */
export const MARK_ORDER: string[] = ['◎', '○', '▲', '△', '★', '穴'];

/** 印カテゴリ判定 */
export function isHeavyMark(mark: string): boolean {
  return mark === '◎';
}
export function isMidMark(mark: string): boolean {
  return mark === '○' || mark === '▲';
}
export function isLightMark(mark: string): boolean {
  return mark === '△' || mark === '★';
}
export function isLongShotMark(mark: string): boolean {
  return mark === '穴';
}
export function isAnyMark(mark: string | undefined | null): boolean {
  return !!mark && MARK_ORDER.includes(mark);
}

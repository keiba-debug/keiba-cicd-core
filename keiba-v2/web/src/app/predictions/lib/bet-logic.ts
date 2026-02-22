import type { ServerBetRecommendation } from '@/lib/data/predictions-reader';

/** 固定設定（minBet, betUnit, defaultBudget） */
export const BET_CONFIG = {
  defaultBudget: 30000,
  minBet: 100,
  betUnit: 100,
} as const;

/** サーバー側プリセットキー */
export type ServerPresetKey = 'win_only' | 'conservative' | 'standard' | 'aggressive';

/** プリセット表示オプション */
export const PRESET_OPTIONS: { key: ServerPresetKey; label: string; description: string }[] = [
  { key: 'win_only', label: '単勝のみ', description: 'Win特化 (推奨)' },
  { key: 'conservative', label: '堅実', description: '単+複 厳選' },
  { key: 'standard', label: '標準', description: '単+複 標準' },
  { key: 'aggressive', label: '攻め', description: '単+複 広め' },
];

/**
 * 予算変更時のrescale
 * サーバーはbaseBudget=30,000円で金額計算済み → ユーザー予算に合わせて比例配分
 */
/** 配分モード */
export type AllocMode = 'kelly' | 'equal';

export function rescaleBudget(
  recs: ServerBetRecommendation[],
  newBudget: number,
  baseBudget: number = 30000,
): ServerBetRecommendation[] {
  if (newBudget === baseBudget) return recs;
  const scale = newBudget / baseBudget;
  return recs.map(r => ({
    ...r,
    win_amount: r.win_amount > 0
      ? Math.max(100, Math.round(r.win_amount * scale / 100) * 100)
      : 0,
    place_amount: r.place_amount > 0
      ? Math.max(100, Math.round(r.place_amount * scale / 100) * 100)
      : 0,
  }));
}

/**
 * 均等配分: 予算をベット数で均等割り（100円単位）
 * 各賭けスロット（単勝/複勝それぞれ1スロット）に同額配分
 */
export function equalDistribute(
  recs: ServerBetRecommendation[],
  budget: number,
): ServerBetRecommendation[] {
  let totalSlots = 0;
  for (const r of recs) {
    if (r.win_amount > 0) totalSlots++;
    if (r.place_amount > 0) totalSlots++;
  }
  if (totalSlots === 0) return recs;

  const perSlot = Math.max(100, Math.floor(budget / totalSlots / 100) * 100);

  return recs.map(r => ({
    ...r,
    win_amount: r.win_amount > 0 ? perSlot : 0,
    place_amount: r.place_amount > 0 ? perSlot : 0,
  }));
}

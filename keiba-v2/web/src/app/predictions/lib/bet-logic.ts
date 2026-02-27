import type { ServerBetRecommendation } from '@/lib/data/predictions-reader';

/** 固定設定（minBet, betUnit, defaultBudget） */
export const BET_CONFIG = {
  defaultBudget: 30000,
  minBet: 100,
  betUnit: 100,
} as const;

/** サーバー側プリセットキー */
export type ServerPresetKey = 'standard' | 'wide' | 'aggressive';

/** プリセット表示オプション */
export const PRESET_OPTIONS: { key: ServerPresetKey; label: string; description: string }[] = [
  { key: 'standard', label: '標準', description: 'EV≥1.5で期待値のある馬を選定（推奨）' },
  { key: 'wide', label: '手広く', description: 'EV条件なしで幅広く買い目を拾う（件数多め）' },
  { key: 'aggressive', label: '厳選', description: 'EV≥1.8の高期待値馬のみに絞る（件数少・ROI重視）' },
];

/** 配分モード */
export type AllocMode = 'kelly' | 'equal';

/**
 * 傾斜配分: 日予算全額を各ベットの元金額比率で按分
 *
 * bet_engine.py が Gap に応じた重み付き金額を生成済み（例: gap大→win_amount=300, gap小→100）
 * これを比率として保持しつつ、合計が日予算と一致するようにスケーリング
 * クロス配分の単複比率も維持される
 */
export function rescaleBudget(
  recs: ServerBetRecommendation[],
  newBudget: number,
): ServerBetRecommendation[] {
  // 実際の合計金額から比例スケール
  const actualTotal = recs.reduce((s, r) => s + r.win_amount + r.place_amount, 0);
  if (actualTotal === 0) return recs;

  const scale = newBudget / actualTotal;

  return recs.map(r => {
    const total = r.win_amount + r.place_amount;
    if (total === 0) return r;

    // 元の単複比率を維持してスケール
    const winRatio = r.win_amount / total;
    const scaledTotal = Math.max(200, Math.round(total * scale / 100) * 100);
    const scaledWin = r.win_amount > 0
      ? Math.max(100, Math.round(scaledTotal * winRatio / 100) * 100)
      : 0;
    const scaledPlace = r.place_amount > 0
      ? Math.max(100, scaledTotal - scaledWin)
      : 0;

    return {
      ...r,
      win_amount: scaledWin,
      place_amount: scaledPlace,
    };
  });
}

/**
 * 均等配分: 日予算を全ベットに均等割り
 * 各ベット内の単複比率はbet_engine.pyのクロス配分を維持
 */
export function equalDistribute(
  recs: ServerBetRecommendation[],
  budget: number,
): ServerBetRecommendation[] {
  if (recs.length === 0) return recs;

  const perBet = Math.max(200, Math.floor(budget / recs.length / 100) * 100);

  return recs.map(r => {
    const total = r.win_amount + r.place_amount;
    if (total === 0) return r;

    // 元の単複比率を維持して均等額に配分
    const winRatio = r.win_amount / total;
    const scaledWin = r.win_amount > 0
      ? Math.max(100, Math.round(perBet * winRatio / 100) * 100)
      : 0;
    const scaledPlace = r.place_amount > 0
      ? Math.max(100, perBet - scaledWin)
      : 0;

    return {
      ...r,
      win_amount: scaledWin,
      place_amount: scaledPlace,
    };
  });
}

import { isTurf, isDirt } from './helpers';
import type { BetStrategyParams, BetPresetKey, BetTypeMode } from './types';

/** 推奨買い目の設定定数（固定値：minBet, betUnit, defaultBudget） */
export const BET_CONFIG = {
  defaultBudget: 30000,
  minBet: 100,
  betUnit: 100,
} as const;

/** プリセット定義 */
export const BET_PRESETS: Record<BetPresetKey, BetStrategyParams> = {
  standard: {
    minGap: 3,
    minGapDanger: 2,
    dangerThreshold: 5,
    kellyCap: 0.10,
    kellyFraction: 0.25,
    minEvThreshold: 1.0,
    betTypeMode: 'auto',
    headRatioThreshold: null,
  },
  place_focus: {
    minGap: 4,
    minGapDanger: 3,
    dangerThreshold: 5,
    kellyCap: 0.10,
    kellyFraction: 0.25,
    minEvThreshold: 1.0,
    betTypeMode: 'place_only',
    headRatioThreshold: null,
  },
  aggressive: {
    minGap: 2,
    minGapDanger: 2,
    dangerThreshold: 5,
    kellyCap: 0.15,
    kellyFraction: 0.25,
    minEvThreshold: 0.9,
    betTypeMode: 'win_focus',
    headRatioThreshold: 0.35,
  },
};

export function getDefaultParams(): BetStrategyParams {
  return { ...BET_PRESETS.standard };
}

/** プリセット表示名 */
export const PRESET_LABELS: Record<BetPresetKey, string> = {
  standard: '標準',
  place_focus: '複勝厳選',
  aggressive: '攻め',
};

/**
 * バックテスト実績データ (v5.4, test=2025-2026, n=3,570 races)
 * Place VB = Model V rank gap ベース, Win = 同gap内の単勝成績
 */
export const BACKTEST_EMPIRICAL = {
  place: [
    { minGap: 2, hitRate: 0.3177, roi: 1.058 },
    { minGap: 3, hitRate: 0.2667, roi: 1.183 },
    { minGap: 4, hitRate: 0.2293, roi: 1.274 },
    { minGap: 5, hitRate: 0.2220, roi: 1.482 },
  ],
  win: [
    { minGap: 2, hitRate: 0.0890, roi: 0.925 },
    { minGap: 3, hitRate: 0.0687, roi: 0.946 },
    { minGap: 4, hitRate: 0.0583, roi: 1.004 },
    { minGap: 5, hitRate: 0.0568, roi: 1.160 },
  ],
} as const;

/** gap レベルに対応するバックテスト実績確率を取得 */
export function getEmpiricalRates(gap: number): { placeHitRate: number; winHitRate: number; placeRoi: number; winRoi: number } {
  const p = [...BACKTEST_EMPIRICAL.place].reverse().find(d => gap >= d.minGap);
  const w = [...BACKTEST_EMPIRICAL.win].reverse().find(d => gap >= d.minGap);
  return {
    placeHitRate: p?.hitRate ?? 0.30,
    winHitRate: w?.hitRate ?? 0.08,
    placeRoi: p?.roi ?? 1.0,
    winRoi: w?.roi ?? 0.9,
  };
}

/**
 * 購入推奨ロジック（バックテスト結果に基づく）
 * mode=auto: 芝→単勝、ダート→複勝（現行ロジック）
 * mode=place_only: 全馬複勝
 * mode=win_focus: auto + 頭向き度が高いダート馬は単勝に昇格
 */
export function getBuyRecommendation(
  trackType: string,
  gap: number,
  valueRank: number,
  odds: number | null,
  mode: BetTypeMode = 'auto',
  headRatio?: number | null,
  headRatioThreshold?: number | null,
): { type: '単勝' | '複勝' | '単複' | null; strength: 'strong' | 'normal' } {
  const o = odds ?? 0;

  // place_only: 全馬複勝
  if (mode === 'place_only') {
    const strength = gap >= 5 ? 'strong' as const : 'normal' as const;
    return { type: '複勝', strength };
  }

  // auto / win_focus 共通: 穴馬トップ評価は単勝
  if (gap >= 5 && o >= 10 && valueRank === 1) {
    return { type: '単勝', strength: 'strong' };
  }

  if (isTurf(trackType)) {
    if (gap >= 5) return { type: '単勝', strength: 'strong' };
    if (gap >= 4) return { type: '単勝', strength: 'normal' };
    return { type: '単勝', strength: 'normal' };
  }

  if (isDirt(trackType)) {
    // win_focus: 頭向き度が閾値以上なら単勝に昇格
    if (mode === 'win_focus' && headRatioThreshold != null && headRatio != null && headRatio >= headRatioThreshold) {
      if (gap >= 5) return { type: '単勝', strength: 'strong' };
      return { type: '単勝', strength: 'normal' };
    }
    if (gap >= 5 && o >= 10) return { type: '単複', strength: 'strong' };
    if (gap >= 5) return { type: '複勝', strength: 'strong' };
    return { type: '複勝', strength: 'normal' };
  }

  return { type: null, strength: 'normal' };
}

/**
 * Kelly Criterion: f* = (b*p - q) / b
 * b = net payout (odds - 1), p = probability, q = 1 - p
 * Returns fractional Kelly (0 if negative = don't bet)
 */
export function calcKellyFraction(prob: number, odds: number): number {
  const b = odds - 1;
  if (b <= 0 || prob <= 0) return 0;
  const f = (b * prob - (1 - prob)) / b;
  return Math.max(0, f);
}

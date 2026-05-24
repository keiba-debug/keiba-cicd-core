/**
 * 買い度判定ロジック + ML予測マージ
 *
 * ML予測の win_ev / place_ev を使って各馬を5段階判定する：
 *   🔥 激アツ (≥1.30) / 💰 買い (≥1.10) / 🟡 想定 (≥0.90) / ⚪ おいしくない (≥0.70) / 🔴 リスク (<0.70)
 */

import type { HorseOdds } from '@/lib/data/rt-data-types';
import type { PredictionEntry, PredictionRace } from '@/lib/data/predictions-reader';

export type BuyZone = 'hot' | 'buy' | 'fair' | 'meh' | 'risk' | 'unknown';

export interface BuyZoneInfo {
  zone: BuyZone;
  icon: string;
  label: string;
  className: string;
}

/** EVから5段階判定 */
export function judgeBuyZone(ev: number | null | undefined): BuyZone {
  if (ev == null || !isFinite(ev)) return 'unknown';
  if (ev >= 1.3) return 'hot';
  if (ev >= 1.1) return 'buy';
  if (ev >= 0.9) return 'fair';
  if (ev >= 0.7) return 'meh';
  return 'risk';
}

export function getBuyZoneDisplay(zone: BuyZone): BuyZoneInfo {
  switch (zone) {
    case 'hot':
      return {
        zone,
        icon: '🔥',
        label: '激アツ',
        className: 'bg-red-500 text-white font-bold',
      };
    case 'buy':
      return {
        zone,
        icon: '💰',
        label: '買い',
        className: 'bg-emerald-500 text-white font-semibold',
      };
    case 'fair':
      return {
        zone,
        icon: '🟡',
        label: '想定',
        className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200',
      };
    case 'meh':
      return {
        zone,
        icon: '⚪',
        label: 'おいしくない',
        className: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
      };
    case 'risk':
      return {
        zone,
        icon: '🔴',
        label: 'リスク',
        className: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
      };
    default:
      return { zone, icon: '', label: '-', className: 'text-gray-300' };
  }
}

/** TARGET印の優先度（◎が最強、消は負値 — ソートで最下部に沈める） */
export function markPriority(mark: string | null | undefined): number {
  switch (mark) {
    case '◎':
      return 6;
    case '○':
      return 5;
    case '▲':
      return 4;
    case '△':
      return 3;
    case 'Ⅲ':
      return 2;
    case '穴':
      return 1;
    case '消':
      return -1;
    default:
      return 0;
  }
}

/** TARGET印の色クラス */
export function getMyMarkColor(mark: string | null | undefined): string {
  switch (mark) {
    case '◎':
      return 'text-red-600 dark:text-red-400 font-bold';
    case '○':
      return 'text-blue-600 dark:text-blue-400 font-bold';
    case '▲':
      return 'text-yellow-600 dark:text-yellow-500 font-semibold';
    case '△':
      return 'text-gray-500 dark:text-gray-400';
    case 'Ⅲ':
      return 'text-purple-600 dark:text-purple-400 font-semibold';
    case '穴':
      return 'text-pink-600 dark:text-pink-400 font-semibold';
    case '消':
      // 切り捨て候補: 無印より薄い + 取り消し線で「外した」感を出す
      return 'text-gray-400 dark:text-gray-600 line-through';
    default:
      return 'text-gray-300';
  }
}

/** market_signal の表示情報 */
export function getMarketSignalDisplay(signal: string | null | undefined): {
  label: string;
  className: string;
} | null {
  if (!signal) return null;
  switch (signal) {
    case 'tetsu_ban':
    case '鉄板':
      return { label: '鉄板', className: 'bg-blue-500 text-white' };
    case 'ana_chuumoku':
    case '穴注目':
      return { label: '穴注目', className: 'bg-purple-500 text-white' };
    case 'myomi':
    case '妙味':
      return { label: '妙味', className: 'bg-emerald-500 text-white' };
    case 'yaya_myomi':
    case 'やや妙味':
      return { label: 'やや妙味', className: 'bg-emerald-300 text-emerald-900' };
    case 'ninki_shisugi':
    case '人気しすぎ':
      return { label: '人気しすぎ', className: 'bg-rose-400 text-white' };
    default:
      return { label: signal, className: 'bg-gray-200 text-gray-700' };
  }
}

/**
 * HorseOdds に ML 予測 + My印 をマージした統合型
 */
export interface EnrichedHorse extends HorseOdds {
  // ML予測
  ml?: PredictionEntry | null;
  winEv?: number | null;
  placeEv?: number | null;
  winProbaCal?: number | null;
  placeProba?: number | null;
  rankW?: number | null;
  rankP?: number | null;
  isVb?: boolean;
  vbGap?: number | null;
  arDeviation?: number | null;
  marketSignal?: string | null;
  // 買い度判定
  winZone: BuyZone;
  placeZone: BuyZone;
  // My印
  myMark1?: string | null;
  myMark2?: string | null;
}

/**
 * HorseOdds[] に ML予測 + My印 をマージして EnrichedHorse[] を返す
 */
export function enrichHorses(
  horses: HorseOdds[],
  predictions: PredictionRace | null | undefined,
  myMarks1: Record<number | string, string>,
  myMarks2: Record<number | string, string>
): EnrichedHorse[] {
  const mlMap = new Map<string, PredictionEntry>();
  if (predictions) {
    for (const e of predictions.entries) {
      mlMap.set(String(e.umaban), e);
    }
  }

  return horses.map((h) => {
    const umaStr = h.umaban.replace(/^0+/, '');
    const umaNum = parseInt(umaStr, 10);
    const ml = mlMap.get(umaStr) ?? mlMap.get(h.umaban) ?? null;

    const winEv = ml?.win_ev ?? null;
    const placeEv = ml?.place_ev ?? null;

    const myMark1 = myMarks1[umaNum] ?? myMarks1[umaStr] ?? null;
    const myMark2 = myMarks2[umaNum] ?? myMarks2[umaStr] ?? null;

    return {
      ...h,
      ml,
      winEv,
      placeEv,
      winProbaCal: ml?.pred_proba_w_cal ?? null,
      placeProba: ml?.pred_proba_p ?? null,
      rankW: ml?.rank_w ?? null,
      rankP: ml?.rank_p ?? null,
      isVb: ml?.is_value_bet ?? false,
      vbGap: ml?.vb_gap ?? null,
      arDeviation: ml?.ar_deviation ?? null,
      marketSignal: ml?.market_signal ?? null,
      winZone: judgeBuyZone(winEv),
      placeZone: judgeBuyZone(placeEv),
      myMark1: myMark1 || null,
      myMark2: myMark2 || null,
    };
  });
}

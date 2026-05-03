/**
 * /api/my-bets/[raceId] レスポンス型
 */

export type BetType =
  | 'tansho'
  | 'fukusho'
  | 'umaren'
  | 'umatan'
  | 'wide'
  | 'sanrenpuku'
  | 'sanrentan';

export interface BetCandidate {
  betType: BetType;
  horses: number[];
  probability: number;
  odds: number;
  ev: number;
  ninki?: number | null;
  marks: string[];
  stake?: number; // strategy.bets only
}

export interface StrategyResult {
  strategyId: string;
  name: string;
  description: string;
  activated: boolean;
  bets: BetCandidate[];
  totalCost: number;
  totalBets: number;
  avgEv: number;
}

export interface MyBetsResponse {
  raceId: string;
  date: string;
  venue: string;
  raceNumber: number;
  raceName: string | null;
  markSet: number;
  horseNames: Record<number, string>;
  horseToMark: Record<number, string>;
  markCounts: Record<string, number>;
  oddsAvailable: {
    tansho: number;
    fukusho: number;
    umaren: number;
    umatan: number;
    wide: number;
    sanrenpuku: number;
    sanrentan: number;
  };
  candidates: {
    total: number;
    topByEv: BetCandidate[];
  };
  strategies: StrategyResult[];
}

export const BET_TYPE_LABEL: Record<BetType, string> = {
  tansho: '単勝',
  fukusho: '複勝',
  umaren: '馬連',
  umatan: '馬単',
  wide: 'ワイド',
  sanrenpuku: '三連複',
  sanrentan: '三連単',
};

/** TARGET FF CSV 券種コード */
export const BET_TYPE_FF_CODE: Record<BetType, number> = {
  tansho: 0,
  fukusho: 1,
  umaren: 3,
  wide: 4,
  umatan: 5,
  sanrenpuku: 6,
  sanrentan: 7,
};

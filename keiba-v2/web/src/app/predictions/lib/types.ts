import type { PredictionRace, PredictionEntry } from '@/lib/data/predictions-reader';

// --- DB Odds types (API response) ---

export interface DbOddsHorse {
  umaban: number;
  winOdds: number | null;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
}

export interface DbOddsResponse {
  raceId: string;
  source: 'timeseries' | 'final' | 'none';
  snapshotTime: string | null;
  horses: DbOddsHorse[];
}

export interface OddsEntry {
  winOdds: number;
  placeOddsMin: number | null;
  placeOddsMax: number | null;
}

export type OddsMap = Record<string, Record<number, OddsEntry>>; // raceId -> umaban -> OddsEntry

// --- DB Results types (API response) ---

export interface DbResultEntry {
  umaban: number;
  finishPosition: number;
  time: string;
  last3f: number;
  confirmedWinOdds: number;
  confirmedPlaceOddsMin: number | null;
  confirmedPlaceOddsMax: number | null;
  ninki: number;
}

export interface DbResultsResponse {
  date: string;
  results: Record<string, DbResultEntry[]>; // raceId → entries
  totalRaces: number;
}

// raceId → umaban → DbResultEntry
export type DbResultsMap = Record<string, Record<number, DbResultEntry>>;

// --- 危険な人気馬 ---

export interface DangerInfo {
  isDanger: boolean;
  dangerScore: number;
  dangerHorse?: {
    umaban: number;
    horseName: string;
    oddsRank: number;
    rankV: number;
  };
}

// --- 危険馬結果一覧 ---

export interface DangerHorseEntry {
  race: PredictionRace;
  entry: PredictionEntry;
  dangerScore: number;    // rank_v - odds_rank
  oddsRank: number;       // 人気順 (1-3)
  rankV: number;          // モデルV順位
}

// --- 推奨買い目 ---

export interface BetRecommendation {
  race: PredictionRace;
  entry: PredictionEntry;
  betType: '単勝' | '複勝' | '単複';
  strength: 'strong' | 'normal';
  winEv: number | null;
  placeEv: number | null;
  kellyWin: number;
  kellyPlace: number;
  betAmountWin: number;
  betAmountPlace: number;
  danger?: DangerInfo;
}

// --- 買い目戦略パラメータ ---

export type BetTypeMode = 'auto' | 'place_only' | 'win_focus';
export type BetPresetKey = 'standard' | 'place_focus' | 'aggressive';

export interface BetStrategyParams {
  minGap: number;
  minGapDanger: number;
  dangerThreshold: number;
  kellyCap: number;
  kellyFraction: number;
  minEvThreshold: number;
  betTypeMode: BetTypeMode;
  headRatioThreshold: number | null;
}

// --- ソート ---

export type SortDir = 'asc' | 'desc';
export interface SortState { key: string; dir: SortDir }

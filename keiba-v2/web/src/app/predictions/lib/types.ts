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

// --- 危険な人気馬 (odds<=8 & ARd<53 & V%<15%) (v5.33) ---

export interface DangerInfo {
  isDanger: boolean;
  dangerHorse?: {
    umaban: number;
    horseName: string;
    oddsRank: number;
    odds: number;
  };
}

// --- 危険馬結果一覧 ---

export interface DangerHorseEntry {
  race: PredictionRace;
  entry: PredictionEntry;
  oddsRank: number;       // 人気順
  odds: number;           // 単勝オッズ
  ard: number;            // AR偏差値
  predV: number;          // V% (好走確率)
}

// --- 推奨買い目（サーバー推奨 + レース/馬コンテキスト表示用） ---

export interface BetRecommendation {
  race: PredictionRace;
  entry: PredictionEntry;
  betType: '単勝' | '複勝' | '単複';
  strength: 'strong' | 'normal';
  winEv: number | null;
  placeEv: number | null;
  kellyFraction: number;   // kelly_capped from server
  betAmountWin: number;
  betAmountPlace: number;
  gap: number;
  winGap: number;
  predictedMargin: number;
  isDanger: boolean;
  danger?: DangerInfo;
}

// --- ソート ---

export type SortDir = 'asc' | 'desc';
export interface SortState { key: string; dir: SortDir }

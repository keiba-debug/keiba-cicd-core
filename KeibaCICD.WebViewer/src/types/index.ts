// 競馬データの型定義

export interface RaceSummary {
  id: string;
  date: string;
  track: string;
  raceNumber: number;
  raceName: string;
  className: string;
  distance: string;
  startTime: string;
  kai?: number;
  nichi?: number;
  filePath: string;
  // ペース分析情報
  paceType?: 'sprint' | 'average' | 'stamina';  // 瞬発/平均/持続
  winnerFirst3f?: number;  // 勝ち馬の前半3F
  winnerLast3f?: number;   // 勝ち馬の後半3F
  paceDiff?: number;       // 前半-後半の差（マイナス=瞬発戦）
  rpci?: number;           // RPCI値 (前半3F/後半3F)*50
}

export interface RaceDetail extends RaceSummary {
  content: string;
  htmlContent: string;
  horses: HorseEntry[];
}

export interface HorseEntry {
  number: number;
  frame: number; // 枠番
  name: string;
  horseId: string;
  jockey: string;
  weight: number;
  age?: string; // 性齢（牡3, 牝4など）
  odds?: number;
  aiIndex?: number;
  rate?: number; // レート
  mark?: string; // 本誌印
  shortComment?: string; // 短評
  trainingComment?: string; // 調教短評
  training?: string; // 調教評価
  // 将来拡張用
  stats?: HorseStats;
  recentResults?: RaceResult[];
}

// 能力値（将来のデータ蓄積用）
export interface HorseStats {
  speed: number; // スピード (0-100)
  stamina: number; // スタミナ (0-100)
  power: number; // 瞬発力 (0-100)
  stability: number; // 安定感 (0-100)
  growth: number; // 成長度 (0-100)
}

// 過去成績（将来のグラフ表示用）
export interface RaceResult {
  date: string;
  track: string;
  distance: string;
  position: number;
  time?: string;
  margin?: string;
}

// カードのレアリティ
export type CardRarity = 'SSR' | 'SR' | 'R' | 'N';

// レアリティ判定関数用
export function getRarity(aiIndex?: number, rate?: number): CardRarity {
  const score = aiIndex || rate || 50;
  if (score >= 57) return 'SSR';
  if (score >= 54) return 'SR';
  if (score >= 51) return 'R';
  return 'N';
}

export interface HorseSummary {
  id: string;
  name: string;
  age: string;
  filePath: string;
}

export interface HorseProfile extends HorseSummary {
  content: string;
  htmlContent: string;
  jockey?: string;
  weight?: number;
  lastRaceDate?: string;
}

export interface DateGroup {
  date: string;
  displayDate: string;
  tracks: TrackGroup[];
}

export interface TrackGroup {
  track: string;
  races: RaceSummary[];
}

export type ViewMode = 'newspaper' | 'card';

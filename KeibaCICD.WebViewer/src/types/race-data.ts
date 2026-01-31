/**
 * 統合レースデータの型定義
 * JSON → 直接表示のための型安全なデータ構造
 */

// ==========================================
// メタ情報
// ==========================================
export interface RaceDataSources {
  seiseki: string;
  syutuba: string;
  cyokyo: string;
  danwa: string;
  nittei: string;
  syoin: string;
  paddok: string;
}

export interface RaceMeta {
  race_id: string;
  data_version: string;
  created_at: string;
  updated_at: string;
  data_sources: RaceDataSources;
}

// ==========================================
// レース情報
// ==========================================
export interface RaceInfo {
  date: string;
  venue: string;
  race_number: number;
  race_name: string;
  grade: string;
  distance: number;
  track: string;         // "芝" | "ダ" | "ダート"
  direction: string;     // "右" | "左"
  weather: string;
  track_condition: string;
  post_time: string;     // 発走予定時刻
  race_condition: string; // "3歳未勝利 牝" など
  start_time?: string;
  start_at?: string;
}

// ==========================================
// 馬データ
// ==========================================
export interface MarksByPerson {
  CPU: string;
  本誌: string;
  My印: string;
  吉田幹?: string;
  林茂徳?: string;
  吉岡哲?: string;
  本紙: string;
  [key: string]: string | undefined;
}

export interface EntryData {
  weight: string;
  weight_diff: string;
  jockey: string;
  jockey_id?: string;
  trainer: string;
  trainer_id?: string;      // 競馬ブック厩舎ID（例: "ｳ011"）
  trainer_link?: string;    // 調教師リンクURL
  trainer_tozai?: string;   // 所属（"美浦" | "栗東"）
  trainer_comment?: string; // 調教師コメントデータ（勝負調教パターンなど）
  owner: string;
  short_comment: string;
  odds: string;
  odds_rank: string;
  ai_index: string;
  ai_rank: string;
  popularity_index: string;
  age: string;           // "牝3", "牡4" など
  sex: string;
  waku: string;          // 枠番
  rating: string;
  horse_weight: string;
  father: string;
  mother: string;
  mother_father: string;
  honshi_mark: string;   // "◎", "○", "▲", "△", ""
  mark_point: number;
  marks_by_person: MarksByPerson;
  aggregate_mark_point: number;
}

export interface TrainingData {
  last_training: string;
  training_times: string[];
  training_course: string;
  evaluation: string;
  trainer_comment: string;
  attack_explanation: string;  // 攻め馬解説
  short_review: string;        // 調教短評
  training_load: string;
  training_rank: string;
  training_arrow: string;      // "↗", "→", "↘"
}

export interface StableComment {
  date: string;
  comment: string;
  condition: string;
  target_race: string;
  trainer: string;
}

export interface RaceResultRawData {
  着順: string;
  My印: string;
  本紙: string;
  枠番: string;
  馬番: string;
  馬名: string;
  性齢: string;
  重量: string;
  騎手: string;
  騎手_2: string;
  タイム: string;
  着差: string;
  通過順位: string;
  "4角位置": string;
  "前半3F": string;
  "上り3F": string;
  単人気: string;
  単勝オッズ: string;
  馬体重: string;
  増減: string;
  厩舎: string;
  interview: string;
  memo: string;
  インタビュー?: string;
  次走へのメモ?: string;
  寸評?: string;
}

export interface RaceResult {
  finish_position: string;
  time: string;
  margin: string;
  last_3f: string;
  passing_orders: string;
  last_corner_position: string;
  first_3f: string;
  sunpyo: string;
  prize_money: number;
  horse_weight: string;
  horse_weight_diff: string;
  raw_data: RaceResultRawData;
}

export interface PreviousRaceInterview {
  jockey: string;
  comment: string;
  interview: string;
  next_race_memo: string;
  finish_position: string;
  previous_race_mention: string;
}

export interface PaddockInfo {
  mark: string;
  mark_score: number;
  comment: string;
  condition: string;
  temperament: string;
  gait: string;
  horse_weight: string;
  weight_change: string;
  evaluator: string;
}

export interface PastPerformances {
  total_races: number;
  wins: number;
  places: number;
  shows: number;
  earnings: number;
  recent_form: unknown[];
}

export interface HistoryFeatures {
  passing_style?: string;
  value_flag?: string;
  last3f_mean_3?: number;
  [key: string]: unknown;
}

export interface HorseEntry {
  horse_number: number;
  horse_name: string;
  horse_id: string;
  entry_data: EntryData;
  training_data: TrainingData | null;
  stable_comment: StableComment | null;
  result: RaceResult | null;
  previous_race_interview: PreviousRaceInterview | null;
  paddock_info: PaddockInfo | null;
  past_performances: PastPerformances;
  history_features: HistoryFeatures | null;
}

// ==========================================
// 分析・予想
// ==========================================
export interface FavoriteHorse {
  horse_number: number;
  horse_name: string;
  odds_rank: number;
}

export interface RaceAnalysis {
  expected_pace: string;
  favorites: FavoriteHorse[];
  training_highlights: string[];
  entry_count: number;
}

export interface TenkaiPositions {
  逃げ: string[];
  好位: string[];
  中位: string[];
  後方: string[];
}

export interface TenkaiData {
  pace: string;           // "H", "M", "S"
  positions: TenkaiPositions;
  description?: string;
}

// ==========================================
// 配当・ラップ
// ==========================================
export interface PayoutEntry {
  type: string;           // "tansho", "fukusho", "wakuren", ...
  combination: string;
  amount: number;
  popularity: string;
}

export interface LapsData {
  lap_times?: string[];
  first_1000m?: string;
  pace?: string;
}

// ==========================================
// 統合レースデータ（ルート）
// ==========================================
export interface IntegratedRaceData {
  meta: RaceMeta;
  race_info: RaceInfo;
  entries: HorseEntry[];
  payouts: PayoutEntry[] | null;
  laps: LapsData | null;
  analysis: RaceAnalysis;
  tenkai_data: TenkaiData | null;
  race_comment: string;
}

// ==========================================
// ヘルパー型
// ==========================================

/** 印のスコアマッピング */
export const MARK_SCORES: Record<string, number> = {
  '◎': 8,
  '○': 5,
  '▲': 3,
  '△': 2,
  '☆': 1,
  '穴': 1,
  '無印': 0,
  '': 0,
  '-': 0,
};

/** 調教矢印の意味 */
export const TRAINING_ARROW_LABELS: Record<string, string> = {
  '↗': '上昇',
  '→': '平行',
  '↘': '下降',
};

/** 競馬場コードマッピング */
export const VENUE_CODE_MAP: Record<string, string> = {
  '01': '札幌',
  '02': '函館',
  '03': '福島',
  '04': '新潟',
  '05': '東京',
  '06': '中山',
  '07': '中京',
  '08': '京都',
  '09': '阪神',
  '10': '小倉',
};

/** トラック種別の日本語変換 */
export function getTrackLabel(track: string): string {
  const trackMap: Record<string, string> = {
    '芝': '芝',
    'ダ': 'ダート',
    'ダート': 'ダート',
  };
  return trackMap[track] || track;
}

/** 着順を数値に変換（比較用） */
export function parseFinishPosition(position: string): number {
  const num = parseInt(position, 10);
  return isNaN(num) ? 999 : num;
}

/** 馬番を丸数字に変換 */
export function toCircleNumber(num: number): string {
  const circles = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';
  if (num >= 1 && num <= 20) {
    return circles[num - 1];
  }
  return String(num);
}

/** 枠番から枠の色を取得 */
export function getWakuColor(waku: string | number): string {
  const wakuNum = typeof waku === 'string' ? parseInt(waku, 10) : waku;
  const colors: Record<number, string> = {
    1: 'bg-white border-gray-400',
    2: 'bg-black text-white',
    3: 'bg-red-600 text-white',
    4: 'bg-blue-600 text-white',
    5: 'bg-yellow-400 text-black',
    6: 'bg-green-600 text-white',
    7: 'bg-orange-500 text-white',
    8: 'bg-pink-400 text-white',
  };
  return colors[wakuNum] || 'bg-gray-200';
}

/** 調教師名をフォーマット（所属を括弧で表示） */
export function formatTrainerName(trainer: string, tozai?: string): string {
  if (!trainer) return '-';
  
  // tozai情報があればそれを使用
  if (tozai) {
    const tozaiShort = tozai === '美浦' ? '美' : tozai === '栗東' ? '栗' : '';
    if (tozaiShort) {
      // 調教師名から所属の接頭辞を除去（例: "美堀内" → "堀内"）
      const nameWithoutPrefix = trainer.replace(/^(美|栗)/, '');
      return `（${tozaiShort}）${nameWithoutPrefix}`;
    }
  }
  
  // tozai情報がない場合は、調教師名から推測
  // 「美堀内」→「（美）堀内」、「栗須貝」→「（栗）須貝」
  if (trainer.startsWith('美')) {
    return `（美）${trainer.substring(1)}`;
  }
  if (trainer.startsWith('栗')) {
    return `（栗）${trainer.substring(1)}`;
  }
  
  // 接頭辞がない場合はそのまま返す
  return trainer;
}

/**
 * 馬名を正規化（調教データマッチング用）
 * 接頭辞（外）（地）（父）などを除去して純粋な馬名を返す
 * 
 * 例:
 * - "(外)ロッシニアーナ" → "ロッシニアーナ"
 * - "（地）ホクショウマサル" → "ホクショウマサル"
 * - "ディープインパクト" → "ディープインパクト"
 */
export function normalizeHorseName(name: string): string {
  if (!name) return '';
  
  // 半角括弧・全角括弧両方に対応
  // (外), (地), (父), (市), [外], [地] などを除去
  return name
    .replace(/^[\(（\[]外[\)）\]]/g, '')
    .replace(/^[\(（\[]地[\)）\]]/g, '')
    .replace(/^[\(（\[]父[\)）\]]/g, '')
    .replace(/^[\(（\[]市[\)）\]]/g, '')
    .replace(/^[\(（\[]抽[\)）\]]/g, '')
    .trim();
}

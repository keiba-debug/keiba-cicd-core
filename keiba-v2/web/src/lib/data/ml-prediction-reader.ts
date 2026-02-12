/**
 * MLリアルタイム予測リーダー（サーバーサイド専用）
 *
 * v4 (data3) → v2 (data2) フォールバック対応。
 * v4: 16桁race_id, entries[].umaban, pred_proba_a/v, rank_v, vb_gap
 * v2: 12桁race_id, horses[].horse_number, pred_proba_accuracy/value, value_rank, gap
 *
 * 呼び出し側は12桁race_idで検索。v4データは race_number+date で照合。
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// --- 型定義（既存互換） ---

export interface MlHorsePrediction {
  horse_number: number;
  horse_name: string;
  pred_proba_accuracy: number;
  pred_proba_value: number;
  value_rank: number;
  odds_rank: number | null;
  odds: number | null;
  gap: number | null;
  is_value_bet: boolean;
}

export interface MlRacePrediction {
  race_id: string;
  date: string;
  venue: string;
  grade: string;
  race_name: string;
  race_number: number;
  entry_count: number;
  horses: MlHorsePrediction[];
}

interface MlPredictionsLive {
  date: string;
  created_at: string;
  races: MlRacePrediction[];
}

// --- v4型定義（内部用） ---

interface V4Entry {
  umaban: number;
  horse_name: string;
  odds: number;
  popularity: number;
  pred_proba_a: number;
  pred_proba_v: number;
  rank_a: number;
  rank_v: number;
  odds_rank: number;
  vb_gap: number;
  is_value_bet: boolean;
  kb_mark: string;
  kb_mark_point: number;
  kb_training_arrow: string;
  kb_rating: number | null;
  kb_comment: string;
}

interface V4Race {
  race_id: string;       // 16桁
  date: string;
  venue_name: string;
  race_number: number;
  distance: number;
  track_type: string;
  num_runners: number;
  entries: V4Entry[];
}

interface V4PredictionsLive {
  version: string;
  created_at: string;
  date: string;
  model_version: string;
  races: V4Race[];
  summary: { total_races: number; total_entries: number; value_bets: number };
}

// --- キャッシュ ---

const V4_PREDICTIONS_PATH = path.join(DATA3_ROOT, 'ml', 'predictions_live.json');

let cachedV4: V4PredictionsLive | null = null;
let cacheTimestampV4 = 0;
const CACHE_TTL = 60 * 1000;

async function loadV4(): Promise<V4PredictionsLive | null> {
  if (cachedV4 && Date.now() - cacheTimestampV4 < CACHE_TTL) {
    return cachedV4;
  }
  try {
    const content = await fs.readFile(V4_PREDICTIONS_PATH, 'utf-8');
    cachedV4 = JSON.parse(content) as V4PredictionsLive;
    cacheTimestampV4 = Date.now();
    return cachedV4;
  } catch {
    return null;
  }
}

/**
 * v4のV4Entryを既存MlHorsePredictionに変換
 */
function convertV4Entry(e: V4Entry): MlHorsePrediction {
  return {
    horse_number: e.umaban,
    horse_name: e.horse_name,
    pred_proba_accuracy: e.pred_proba_a,
    pred_proba_value: e.pred_proba_v,
    value_rank: e.rank_v,
    odds_rank: e.odds_rank,
    odds: e.odds,
    gap: e.vb_gap,
    is_value_bet: e.is_value_bet,
  };
}

/**
 * 12桁race_idからレース番号を抽出（末尾2桁）
 */
function raceNumberFrom12(raceId12: string): number {
  return parseInt(raceId12.slice(-2), 10);
}

/**
 * v4レースを12桁race_idで検索
 * 16桁race_idの末尾2桁 = レース番号で照合
 * 同じレース番号が複数場であり得るため、12桁IDの場所コード部分も照合
 */
function findV4Race(races: V4Race[], raceId12: string): V4Race | undefined {
  const raceNum = raceNumberFrom12(raceId12);
  // 12桁: YYYY KK JJ NN RR → KK=回次(4:5), JJ=場所(6:7), NN=日(8:9)
  const kai12 = raceId12.slice(4, 6);
  const jou12 = raceId12.slice(6, 8);
  const nichi12 = raceId12.slice(8, 10);

  return races.find((r) => {
    if (r.race_number !== raceNum) return false;
    // 16桁: YYYYMMDD JJ KK NN RR → JJ=場所(8:10), KK=回次(10:12), NN=日(12:14)
    const rid = r.race_id;
    const jou16 = rid.slice(8, 10);
    const kai16 = rid.slice(10, 12);
    const nichi16 = rid.slice(12, 14);
    // 12桁のKK(回次)は0埋め2桁 → 16桁のKK(回次)も0埋め2桁
    return kai12 === kai16 && jou12 === jou16 && nichi12 === nichi16;
  });
}

/**
 * 指定レースIDのML予測を取得
 * v4 (data3) → v2 (data2) フォールバック
 * @param raceId 12桁race_id
 * @param raceId16 16桁race_id（v4直接検索用、省略時は12桁から変換を試みる）
 * @returns 馬番 → MlHorsePrediction のマップ（なければ null）
 */
export async function getMlPredictions(
  raceId: string,
  raceId16?: string,
): Promise<Record<number, MlHorsePrediction> | null> {
  // v4 (data3) を優先
  const v4 = await loadV4();
  if (v4) {
    // 16桁race_idが提供されている場合は直接検索
    let race: V4Race | undefined;
    if (raceId16) {
      race = v4.races.find((r) => r.race_id === raceId16);
    }
    // フォールバック: 12桁からの変換検索
    if (!race) {
      race = findV4Race(v4.races, raceId);
    }
    if (race) {
      const map: Record<number, MlHorsePrediction> = {};
      for (const e of race.entries) {
        map[e.umaban] = convertV4Entry(e);
      }
      return map;
    }
  }

  return null;
}

/**
 * ML予測データの日付を取得（表示用）
 */
export async function getMlPredictionDate(): Promise<string | null> {
  const v4 = await loadV4();
  return v4?.date ?? null;
}

/**
 * MLリアルタイム予測リーダー（サーバーサイド専用）
 * predictions_live.json を読み込み、レースID → 馬番 → 予測結果のマップを提供
 */

import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT_DIR } from '@/lib/config';

// --- 型定義 ---

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

// --- キャッシュ ---

const PREDICTIONS_PATH = path.join(
  KEIBA_DATA_ROOT_DIR,
  'target',
  'ml',
  'predictions_live.json'
);

let cachedData: MlPredictionsLive | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 60 * 1000; // 1分（予測は頻繁に更新される可能性がある）

/**
 * ML予測データを読み込む
 */
async function loadPredictions(): Promise<MlPredictionsLive | null> {
  if (cachedData && Date.now() - cacheTimestamp < CACHE_TTL) {
    return cachedData;
  }

  try {
    const content = await fs.readFile(PREDICTIONS_PATH, 'utf-8');
    cachedData = JSON.parse(content) as MlPredictionsLive;
    cacheTimestamp = Date.now();
    return cachedData;
  } catch {
    return null;
  }
}

/**
 * 指定レースIDのML予測を取得
 * @returns 馬番 → MlHorsePrediction のマップ（なければ null）
 */
export async function getMlPredictions(
  raceId: string
): Promise<Record<number, MlHorsePrediction> | null> {
  const data = await loadPredictions();
  if (!data) return null;

  const race = data.races.find((r) => r.race_id === raceId);
  if (!race) return null;

  const map: Record<number, MlHorsePrediction> = {};
  for (const h of race.horses) {
    map[h.horse_number] = h;
  }
  return map;
}

/**
 * ML予測データの日付を取得（表示用）
 */
export async function getMlPredictionDate(): Promise<string | null> {
  const data = await loadPredictions();
  return data?.date ?? null;
}

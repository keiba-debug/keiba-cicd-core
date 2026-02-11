/**
 * v4 MLリアルタイム予測リーダー（data3対応）
 *
 * data3/ml/predictions_live.json (v3形式) を読み込む。
 * keibabook拡張情報（印、rating、コメント）付き。
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// --- 型定義 ---

export interface V4HorsePrediction {
  umaban: number;
  horse_name: string;
  odds: number;
  popularity: number;
  pred_proba_a: number;      // Model A (精度モデル)
  pred_proba_v: number;      // Model B (Valueモデル)
  rank_a: number;
  rank_v: number;
  odds_rank: number;
  vb_gap: number;            // odds_rank - rank_v
  is_value_bet: boolean;     // gap >= 3
  // keibabook拡張
  kb_mark: string;
  kb_mark_point: number;
  kb_training_arrow: string;
  kb_rating: number | null;
  kb_comment: string;
}

export interface V4RacePrediction {
  race_id: string;
  date: string;
  venue_name: string;
  race_number: number;
  distance: number;
  track_type: string;
  num_runners: number;
  entries: V4HorsePrediction[];
}

export interface V4PredictionsSummary {
  total_races: number;
  total_entries: number;
  value_bets: number;
}

interface V4PredictionsLive {
  version: string;
  created_at: string;
  date: string;
  model_version: string;
  races: V4RacePrediction[];
  summary: V4PredictionsSummary;
}

// --- キャッシュ ---

const PREDICTIONS_PATH = path.join(DATA3_ROOT, 'ml', 'predictions_live.json');

let cachedData: V4PredictionsLive | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 60 * 1000; // 1分

async function loadPredictions(): Promise<V4PredictionsLive | null> {
  if (cachedData && Date.now() - cacheTimestamp < CACHE_TTL) {
    return cachedData;
  }

  try {
    const content = await fs.readFile(PREDICTIONS_PATH, 'utf-8');
    cachedData = JSON.parse(content) as V4PredictionsLive;
    cacheTimestamp = Date.now();
    return cachedData;
  } catch {
    return null;
  }
}

/**
 * 指定レースIDのv4 ML予測を取得
 * @returns 馬番 → V4HorsePrediction のマップ
 */
export async function getV4Predictions(
  raceId: string
): Promise<Record<number, V4HorsePrediction> | null> {
  const data = await loadPredictions();
  if (!data) return null;

  const race = data.races.find((r) => r.race_id === raceId);
  if (!race) return null;

  const map: Record<number, V4HorsePrediction> = {};
  for (const h of race.entries) {
    map[h.umaban] = h;
  }
  return map;
}

/**
 * 指定レースIDのv4 ML予測レースデータを取得
 */
export async function getV4RacePrediction(
  raceId: string
): Promise<V4RacePrediction | null> {
  const data = await loadPredictions();
  if (!data) return null;
  return data.races.find((r) => r.race_id === raceId) ?? null;
}

/**
 * v4予測の全レースリストを取得
 */
export async function getV4AllPredictions(): Promise<V4RacePrediction[]> {
  const data = await loadPredictions();
  return data?.races ?? [];
}

/**
 * v4予測の日付・サマリ情報を取得
 */
export async function getV4PredictionInfo(): Promise<{
  date: string;
  created_at: string;
  summary: V4PredictionsSummary;
} | null> {
  const data = await loadPredictions();
  if (!data) return null;
  return {
    date: data.date,
    created_at: data.created_at,
    summary: data.summary,
  };
}

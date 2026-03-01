/**
 * v4 ML予測リーダー（data3対応）
 *
 * races/YYYY/MM/DD/predictions.json を読み込む。
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
  pred_proba_p: number;      // 好走(P)モデル
  rank_p: number;
  odds_rank: number;
  vb_gap: number;            // odds_rank - rank_p
  is_value_bet: boolean;     // gap >= 3
  // Legacy field names (pre-v5.45 JSON)
  pred_proba_a?: number;
  pred_proba_v?: number;
  rank_a?: number;
  rank_v?: number;
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

const archiveCache = new Map<string, { data: V4PredictionsLive; ts: number }>();
const CACHE_TTL = 60 * 1000; // 1分

async function loadPredictions(date: string): Promise<V4PredictionsLive | null> {
  const cached = archiveCache.get(date);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return cached.data;
  }

  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, 'predictions.json');
    const content = await fs.readFile(filePath, 'utf-8');
    const data = JSON.parse(content) as V4PredictionsLive;
    archiveCache.set(date, { data, ts: Date.now() });
    return data;
  } catch {
    return null;
  }
}

/**
 * 指定レースIDのv4 ML予測を取得
 * @returns 馬番 → V4HorsePrediction のマップ
 */
export async function getV4Predictions(
  raceId: string,
  date: string,
): Promise<Record<number, V4HorsePrediction> | null> {
  const data = await loadPredictions(date);
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
  raceId: string,
  date: string,
): Promise<V4RacePrediction | null> {
  const data = await loadPredictions(date);
  if (!data) return null;
  return data.races.find((r) => r.race_id === raceId) ?? null;
}

/**
 * v4予測の全レースリストを取得
 */
export async function getV4AllPredictions(date: string): Promise<V4RacePrediction[]> {
  const data = await loadPredictions(date);
  return data?.races ?? [];
}

/**
 * v4予測の日付・サマリ情報を取得
 */
export async function getV4PredictionInfo(date: string): Promise<{
  date: string;
  created_at: string;
  summary: V4PredictionsSummary;
} | null> {
  const data = await loadPredictions(date);
  if (!data) return null;
  return {
    date: data.date,
    created_at: data.created_at,
    summary: data.summary,
  };
}

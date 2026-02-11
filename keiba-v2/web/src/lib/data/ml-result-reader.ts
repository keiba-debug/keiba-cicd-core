/**
 * ML実験結果リーダー（サーバーサイド専用）
 * v2 → v1 フォールバックで読み込む
 */

import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT_DIR, DATA3_ROOT } from '@/lib/config';

// --- 共通型定義 ---

export interface MlMetrics {
  accuracy: number;
  auc: number;
  precision: number;
  recall: number;
  f1: number;
  log_loss: number;
  best_iteration: number;
  train_size: number;
  test_size: number;
}

export interface FeatureImportanceEntry {
  feature: string;
  label: string;
  importance: number;
}

export interface HitAnalysisEntry {
  top_n: number;
  hit_rate: number;
  hits: number;
  total: number;
}

export interface RoiBetSummary {
  total_bet: number;
  total_return: number;
  roi: number;
  bet_count: number;
  hit_rate?: number;
}

export interface ThresholdEntry {
  threshold: number;
  bet_count: number;
  win_hits: number;
  win_roi: number;
  place_hits: number;
  place_roi: number;
  place_hit_rate: number;
}

export interface RoiAnalysis {
  top1_win: RoiBetSummary;
  top1_place: RoiBetSummary;
  by_threshold: ThresholdEntry[];
}

// --- v2 専用型 ---

export interface HorsePredictionV2 {
  horse_number: number;
  horse_name: string;
  pred_proba_accuracy: number;
  pred_proba_value: number;
  pred_top3: number;
  actual_position: number;
  actual_top3: number;
  odds_rank: number | null;
  odds: number | null;
  value_rank: number;
}

export interface RacePredictionV2 {
  race_id: string;
  date: string;
  venue: string;
  grade: string;
  entry_count: number;
  horses: HorsePredictionV2[];
}

export interface MlModelResult {
  features: string[];
  metrics: MlMetrics;
  feature_importance: FeatureImportanceEntry[];
}

export interface ValueBetGapEntry {
  min_gap: number;
  bet_count: number;
  win_hits: number;
  win_roi: number;
  place_hits: number;
  place_roi: number;
  place_hit_rate: number;
}

export interface ValueBetAnalysis {
  by_rank_gap: ValueBetGapEntry[];
}

export interface RoiAnalysisV2 {
  accuracy_model: RoiAnalysis;
  value_model: RoiAnalysis;
  value_bets: ValueBetAnalysis;
}

export interface ValueBetPick {
  race_id: string;
  date: string;
  venue: string;
  grade: string;
  horse_number: number;
  horse_name: string;
  value_rank: number;
  odds_rank: number;
  gap: number;
  odds: number | null;
  pred_proba_accuracy: number;
  pred_proba_value: number;
  actual_position: number;
  is_top3: number;
}

export interface MlExperimentResultV2 {
  version: '2.0';
  model: string;
  experiment: string;
  created_at: string;
  description: string;
  split: { train: string; test: string };
  models: {
    accuracy: MlModelResult;
    value: MlModelResult;
  };
  hit_analysis: HitAnalysisEntry[];
  roi_analysis: RoiAnalysisV2;
  race_predictions: RacePredictionV2[];
  value_bet_picks?: ValueBetPick[];
}

// --- v1 互換型 ---

export interface HorsePrediction {
  horse_number: number;
  horse_name: string;
  pred_proba: number;
  pred_top3: number;
  actual_position: number;
  actual_top3: number;
  odds_rank: number | null;
  odds: number | null;
}

export interface RacePrediction {
  race_id: string;
  date: string;
  venue: string;
  grade: string;
  entry_count: number;
  horses: HorsePrediction[];
}

export interface MlExperimentResult {
  version: string;
  model: string;
  experiment: string;
  created_at: string;
  description: string;
  split: { train: string; test: string };
  features: string[];
  metrics: MlMetrics;
  feature_importance: FeatureImportanceEntry[];
  hit_analysis: HitAnalysisEntry[];
  roi_analysis: RoiAnalysis;
  race_predictions: RacePrediction[];
}

// --- 統合型（v1 or v2） ---
export type MlResult = MlExperimentResult | MlExperimentResultV2;

export function isV2Result(result: MlResult): result is MlExperimentResultV2 {
  return result.version === '2.0';
}

// --- キャッシュ ---

const ML_RESULT_PATHS = [
  path.join(DATA3_ROOT, 'ml', 'ml_experiment_v3_result.json'),
  path.join(KEIBA_DATA_ROOT_DIR, 'target', 'ml', 'ml_experiment_v2_result.json'),
  path.join(KEIBA_DATA_ROOT_DIR, 'target', 'ml', 'ml_experiment_v1_result.json'),
];

let cachedResult: MlResult | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 5 * 60 * 1000;

/**
 * ML実験結果を読み込む（v2優先、v1フォールバック）
 */
export async function getMlExperimentResult(): Promise<MlResult | null> {
  if (cachedResult && Date.now() - cacheTimestamp < CACHE_TTL) {
    return cachedResult;
  }

  for (const resultPath of ML_RESULT_PATHS) {
    try {
      const content = await fs.readFile(resultPath, 'utf-8');
      cachedResult = JSON.parse(content) as MlResult;
      cacheTimestamp = Date.now();
      return cachedResult;
    } catch {
      // try next path
    }
  }
  return null;
}

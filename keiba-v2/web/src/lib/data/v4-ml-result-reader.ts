/**
 * v4 ML実験結果リーダー（data3対応）
 *
 * data3/ml/ml_experiment_v3_result.json を読み込む。
 * v3 → v2 フォールバック対応。
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// --- 型定義 ---

export interface V4ModelMetrics {
  auc: number;
  accuracy: number;
  log_loss: number;
  best_iteration: number;
  train_size: number;
  test_size: number;
}

export interface V4FeatureImportance {
  feature: string;
  importance: number;
}

export interface V4HitEntry {
  top_n: number;
  hit_rate: number;
  hits: number;
  total: number;
}

export interface V4RoiEntry {
  top1_win_roi: number;
  top1_place_roi: number;
  top1_bets: number;
}

export interface V4ValueBetEntry {
  min_gap: number;
  bet_count: number;
  place_hit_rate: number;
  place_roi: number;
}

export interface V4ModelResult {
  features: string[];
  feature_count: number;
  metrics: V4ModelMetrics;
  feature_importance: V4FeatureImportance[];
}

export interface V4MlExperimentResult {
  version: string;
  experiment: string;
  created_at: string;
  split: { train: string; test: string };
  models: {
    accuracy: V4ModelResult;
    value: V4ModelResult;
  };
  hit_analysis: {
    accuracy: V4HitEntry[];
    value: V4HitEntry[];
  };
  roi_analysis: {
    accuracy: V4RoiEntry;
    value: V4RoiEntry;
  };
  value_bets: {
    by_rank_gap: V4ValueBetEntry[];
  };
}

// --- キャッシュ ---

let cachedResult: V4MlExperimentResult | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 5 * 60 * 1000;

const RESULT_PATHS = [
  path.join(DATA3_ROOT, 'ml', 'ml_experiment_v3_result.json'),
];

/**
 * v4 ML実験結果を読み込む
 */
export async function getV4MlExperimentResult(): Promise<V4MlExperimentResult | null> {
  if (cachedResult && Date.now() - cacheTimestamp < CACHE_TTL) {
    return cachedResult;
  }

  for (const resultPath of RESULT_PATHS) {
    try {
      const content = await fs.readFile(resultPath, 'utf-8');
      cachedResult = JSON.parse(content) as V4MlExperimentResult;
      cacheTimestamp = Date.now();
      return cachedResult;
    } catch {
      // try next
    }
  }
  return null;
}

/**
 * v4モデルメタデータを読み込む
 */
export async function getV4ModelMeta(): Promise<{
  version: string;
  features_all: string[];
  features_value: string[];
  market_features: string[];
  created_at: string;
} | null> {
  try {
    const metaPath = path.join(DATA3_ROOT, 'ml', 'model_meta.json');
    const content = await fs.readFile(metaPath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

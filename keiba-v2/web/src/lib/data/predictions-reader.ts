/**
 * predictions_live.json リーダー
 * predict.py が生成する当日予測データを読み込む
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// --- 型定義 ---

export interface PredictionEntry {
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
  kb_rating: number;
  kb_comment: string;
}

export interface PredictionRace {
  race_id: string;
  date: string;
  venue_name: string;
  race_number: number;
  distance: number;
  track_type: string;
  num_runners: number;
  entries: PredictionEntry[];
}

export interface PredictionsLive {
  version: string;
  created_at: string;
  date: string;
  model_version: string;
  odds_source: string;
  db_odds_coverage: string;
  races: PredictionRace[];
  summary: {
    total_races: number;
    total_entries: number;
    value_bets: number;
  };
}

/**
 * predictions_live.json を読み込む
 */
export function getPredictionsLive(): PredictionsLive | null {
  try {
    const filePath = path.join(DATA3_ROOT, 'ml', 'predictions_live.json');
    if (!fs.existsSync(filePath)) return null;
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content) as PredictionsLive;
  } catch {
    return null;
  }
}

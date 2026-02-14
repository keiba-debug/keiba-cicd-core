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

/**
 * 日別アーカイブ (races/YYYY/MM/DD/predictions.json) を読み込む
 */
export function getPredictionsByDate(date: string): PredictionsLive | null {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const filePath = path.join(DATA3_ROOT, 'races', y, m, d, 'predictions.json');
    if (!fs.existsSync(filePath)) return null;
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content) as PredictionsLive;
  } catch {
    return null;
  }
}

/**
 * predictions.json が存在する日付一覧を返す（降順）
 */
export function getAvailablePredictionDates(): string[] {
  try {
    const racesDir = path.join(DATA3_ROOT, 'races');
    if (!fs.existsSync(racesDir)) return [];
    const dates: string[] = [];

    const years = fs.readdirSync(racesDir).filter(y => /^\d{4}$/.test(y));
    for (const y of years) {
      const yearDir = path.join(racesDir, y);
      const months = fs.readdirSync(yearDir).filter(m => /^\d{2}$/.test(m));
      for (const m of months) {
        const monthDir = path.join(yearDir, m);
        const days = fs.readdirSync(monthDir).filter(d => /^\d{2}$/.test(d));
        for (const d of days) {
          if (fs.existsSync(path.join(monthDir, d, 'predictions.json'))) {
            dates.push(`${y}-${m}-${d}`);
          }
        }
      }
    }

    return dates.sort().reverse();
  } catch {
    return [];
  }
}

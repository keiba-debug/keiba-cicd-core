/**
 * predictions_live.json リーダー
 * predict.py が生成する当日予測データを読み込む
 * + レース結果読み込み（着順・確定オッズ）
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
  // Place predictions (is_top3)
  pred_proba_a: number;   // P(top3) all features
  pred_proba_v: number;   // P(top3) value features
  rank_a: number;
  rank_v: number;
  odds_rank: number;
  vb_gap: number;
  is_value_bet: boolean;
  // Win predictions (is_win) — optional for backward compat
  pred_proba_w?: number;   // P(win) all features
  pred_proba_wv?: number;  // P(win) value features
  rank_w?: number;
  rank_wv?: number;
  win_vb_gap?: number;
  // Place odds from DB
  place_odds_min?: number;
  place_odds_max?: number;
  // EV (期待値)
  win_ev?: number;     // P(win) × 単勝オッズ
  place_ev?: number;   // P(top3) × 複勝オッズ最低値
  // keibabook
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

// --- レース結果 ---

export interface RaceResultEntry {
  umaban: number;
  finish_position: number;  // 0 = 未確定/取消
  time: string;
  last_3f: number;
  odds: number;             // 確定単勝オッズ
}

// raceId → umaban → RaceResultEntry
export type RaceResultsMap = Record<string, Record<number, RaceResultEntry>>;

/**
 * 指定日のレース結果を読み込む
 * race_*.json からfinish_position等を抽出
 */
export function getResultsByDate(date: string): RaceResultsMap {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return {};
    const dayPath = path.join(DATA3_ROOT, 'races', y, m, d);
    if (!fs.existsSync(dayPath)) return {};

    const files = fs.readdirSync(dayPath).filter(f => /^race_\d.*\.json$/.test(f));
    const results: RaceResultsMap = {};

    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(dayPath, file), 'utf-8');
        const data = JSON.parse(content);
        const raceId = data.race_id as string;
        if (!raceId || !data.entries) continue;

        const entries: Record<number, RaceResultEntry> = {};
        let hasResults = false;

        for (const e of data.entries) {
          if (e.finish_position > 0) hasResults = true;
          entries[e.umaban] = {
            umaban: e.umaban,
            finish_position: e.finish_position || 0,
            time: e.time || '',
            last_3f: e.last_3f || 0,
            odds: e.odds || 0,
          };
        }

        if (hasResults) {
          results[raceId] = entries;
        }
      } catch {
        continue;
      }
    }

    return results;
  } catch {
    return {};
  }
}

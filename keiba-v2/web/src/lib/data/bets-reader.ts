/**
 * bets.json リーダー
 *
 * 買い目データを predictions.json とは別ファイルで管理する。
 * Output: races/YYYY/MM/DD/bets.json
 *
 * predictions.json = ML分析のみ
 * bets.json = 買い目推奨 (recommendations, multi_leg, sanrentan_formation)
 */

import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';
import type {
  ServerRecommendations,
  MultiLegRecommendation,
} from './predictions-reader';

export interface BetsData {
  date: string;
  model_version: string;
  bets_generated_at: string;
  budget?: number;
  bankroll?: number;
  recommendations: ServerRecommendations;
  multi_leg_recommendations: MultiLegRecommendation[];
  sanrentan_formation: MultiLegRecommendation[];
}

/**
 * 日別 bets.json を読み込む
 */
export function getBetsByDate(date: string): BetsData | null {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const filePath = path.join(KEIBA_DATA_ROOT, 'races', y, m, d, 'bets.json');

    // synchronous for server component compatibility
    const raw = require('fs').readFileSync(filePath, 'utf-8');
    return JSON.parse(raw) as BetsData;
  } catch {
    return null;
  }
}

/**
 * 日別 bets.json を非同期で読み込む
 */
export async function getBetsByDateAsync(date: string): Promise<BetsData | null> {
  try {
    const [y, m, d] = date.split('-');
    if (!y || !m || !d) return null;
    const filePath = path.join(KEIBA_DATA_ROOT, 'races', y, m, d, 'bets.json');
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw) as BetsData;
  } catch {
    return null;
  }
}

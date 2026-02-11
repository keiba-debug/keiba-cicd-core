/**
 * v4 keibabook拡張データリーダー（data3対応）
 *
 * data3/keibabook/ のkb_ext JSONを読み込む。
 * JRA-VANレースデータの補足情報（印、レーティング、調教、コメント等）。
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// --- 型定義 ---

export interface KbTrainingData {
  short_review: string;
  attack_explanation: string;
  evaluation: string;
  training_load: string;
  training_rank: string;
}

export interface KbStableComment {
  comment: string;
}

export interface KbPreviousInterview {
  interview: string;
  next_race_memo: string;
}

export interface KbEntryExt {
  honshi_mark: string;
  mark_point: number;
  marks_by_person: Record<string, string>;
  aggregate_mark_point: number;
  ai_index: number | null;
  ai_rank: string;
  odds_rank: number;
  rating: number | null;
  short_comment: string;
  training_arrow: string;
  training_arrow_value: number;
  training_data: KbTrainingData;
  stable_comment: KbStableComment;
  sunpyo: string;
  previous_race_interview: KbPreviousInterview;
}

export interface KbTenkaiData {
  pace: string;
  positions: Record<string, string[]>;
}

export interface KbAnalysis {
  expected_pace: string;
}

export interface KbExtData {
  race_id: string;        // 16桁
  race_id_12: string;     // 12桁（元のkeibabook ID）
  date: string;
  entries: Record<string, KbEntryExt>;  // key = umaban
  analysis: KbAnalysis;
  tenkai_data: KbTenkaiData | null;
  race_comment: string;
}

// --- キャッシュ ---

const kbCache = new Map<string, { data: KbExtData | null; ts: number }>();
const CACHE_TTL = 5 * 60 * 1000;

/**
 * 指定レースIDのkeibabook拡張データを読み込む
 */
export function getKbExtData(raceId: string): KbExtData | null {
  const cached = kbCache.get(raceId);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return cached.data;
  }

  if (raceId.length !== 16) {
    kbCache.set(raceId, { data: null, ts: Date.now() });
    return null;
  }

  const year = raceId.slice(0, 4);
  const month = raceId.slice(4, 6);
  const day = raceId.slice(6, 8);

  const filePath = path.join(
    DATA3_ROOT, 'keibabook', year, month, day,
    `kb_ext_${raceId}.json`
  );

  try {
    if (!fs.existsSync(filePath)) {
      kbCache.set(raceId, { data: null, ts: Date.now() });
      return null;
    }
    const content = fs.readFileSync(filePath, 'utf-8');
    const data: KbExtData = JSON.parse(content);
    kbCache.set(raceId, { data, ts: Date.now() });
    return data;
  } catch {
    kbCache.set(raceId, { data: null, ts: Date.now() });
    return null;
  }
}

/**
 * 指定馬番のkeibabook拡張データを取得
 */
export function getKbEntryExt(
  raceId: string, umaban: number
): KbEntryExt | null {
  const kbData = getKbExtData(raceId);
  if (!kbData) return null;
  return kbData.entries[String(umaban)] ?? null;
}

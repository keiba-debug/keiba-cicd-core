/**
 * v4レースデータリーダー（data3対応）
 *
 * JRA-VANネイティブのレースJSON (data3/races/) を読み込む。
 * 16桁race_id体系。
 */

import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

// --- 型定義 ---

export interface V4RaceEntry {
  umaban: number;
  wakuban: number;
  ketto_num: string;
  horse_name: string;
  sex_cd: string;
  age: number;
  jockey_name: string;
  jockey_code: string;
  trainer_name: string;
  trainer_code: string;
  futan: number;
  horse_weight: number;
  horse_weight_diff: string;
  finish_position: number;
  time: string;
  last_3f: string;
  odds: number;
  popularity: number;
  corners: number[];
}

export interface V4RacePace {
  s3: number;
  s4: number;
  l3: number;
  l4: number;
  rpci: number;
  race_trend: string;
}

export interface V4RaceData {
  race_id: string;           // 16桁
  date: string;              // YYYY-MM-DD
  venue_code: string;
  venue_name: string;
  kai: number;
  nichi: number;
  race_number: number;
  distance: number;
  track_type: string;        // "turf" | "dirt"
  track_condition: string;
  num_runners: number;
  pace: V4RacePace | null;
  entries: V4RaceEntry[];
}

// --- キャッシュ ---

const raceCache = new Map<string, { data: V4RaceData; ts: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5分

function parseDateParts(date: string): [string, string, string] | null {
  if (date.includes('-')) {
    const parts = date.split('-');
    if (parts.length === 3) return [parts[0], parts[1], parts[2]];
  } else if (date.length === 8) {
    return [date.slice(0, 4), date.slice(4, 6), date.slice(6, 8)];
  }
  return null;
}

/**
 * race_idからdate部分を抽出（16桁: YYYYMMDD...）
 */
function dateFromRaceId(raceId: string): string | null {
  if (raceId.length !== 16) return null;
  return `${raceId.slice(0, 4)}-${raceId.slice(4, 6)}-${raceId.slice(6, 8)}`;
}

/**
 * 指定レースIDのv4レースデータを読み込む
 */
export function getV4RaceData(raceId: string): V4RaceData | null {
  const cached = raceCache.get(raceId);
  if (cached && Date.now() - cached.ts < CACHE_TTL) {
    return cached.data;
  }

  const date = dateFromRaceId(raceId);
  if (!date) return null;

  const parts = parseDateParts(date);
  if (!parts) return null;

  const filePath = path.join(
    DATA3_ROOT, 'races', parts[0], parts[1], parts[2],
    `race_${raceId}.json`
  );

  try {
    if (!fs.existsSync(filePath)) return null;
    const content = fs.readFileSync(filePath, 'utf-8');
    const data: V4RaceData = JSON.parse(content);
    raceCache.set(raceId, { data, ts: Date.now() });
    return data;
  } catch {
    return null;
  }
}

/**
 * 指定日の全レースデータを取得
 */
export function getV4RacesByDate(date: string): V4RaceData[] {
  const parts = parseDateParts(date);
  if (!parts) return [];

  const dirPath = path.join(DATA3_ROOT, 'races', parts[0], parts[1], parts[2]);

  try {
    if (!fs.existsSync(dirPath)) return [];
    const files = fs.readdirSync(dirPath)
      .filter(f => f.startsWith('race_') && f.endsWith('.json'))
      .sort();

    const races: V4RaceData[] = [];
    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(dirPath, file), 'utf-8');
        races.push(JSON.parse(content));
      } catch { /* skip */ }
    }

    return races.sort((a, b) => {
      if (a.venue_code !== b.venue_code) return a.venue_code.localeCompare(b.venue_code);
      return a.race_number - b.race_number;
    });
  } catch {
    return [];
  }
}

/**
 * 競馬場別にグループ化
 */
export function groupV4RacesByVenue(races: V4RaceData[]): Record<string, V4RaceData[]> {
  const grouped: Record<string, V4RaceData[]> = {};
  for (const race of races) {
    const venue = race.venue_name || '不明';
    if (!grouped[venue]) grouped[venue] = [];
    grouped[venue].push(race);
  }
  for (const venue of Object.keys(grouped)) {
    grouped[venue].sort((a, b) => a.race_number - b.race_number);
  }
  return grouped;
}

/**
 * 日付インデックスを読み込む
 */
export function getV4DateIndex(): Record<string, string[]> | null {
  try {
    const indexPath = path.join(DATA3_ROOT, 'indexes', 'race_date_index.json');
    if (!fs.existsSync(indexPath)) return null;
    const content = fs.readFileSync(indexPath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

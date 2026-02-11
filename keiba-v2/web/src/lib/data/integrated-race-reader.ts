/**
 * 統合レースデータ（JSON）読み込みユーティリティ
 * Markdown経由ではなく、JSONから直接データを取得
 */

import fs from 'fs';
import path from 'path';
import { IntegratedRaceData, HorseEntry, parseFinishPosition } from '@/types/race-data';
import { DATA_ROOT } from '../config';

// Re-export types for convenience
export type { IntegratedRaceData, HorseEntry } from '@/types/race-data';

/**
 * 統合レースデータ（JSON）を読み込む
 */
export async function getIntegratedRaceData(
  date: string,    // "2026-01-24" or "20260124"
  track: string,   // "中山" などの競馬場名（現在は使用しない）
  raceId: string   // "202601050801"
): Promise<IntegratedRaceData | null> {
  try {
    // 日付のフォーマットを統一（YYYY/MM/DDまたはYYYYMMDD → YYYY, MM, DD）
    let year: string, month: string, day: string;
    
    if (date.includes('-')) {
      [year, month, day] = date.split('-');
    } else if (date.includes('/')) {
      [year, month, day] = date.split('/');
    } else {
      // YYYYMMDD形式
      year = date.substring(0, 4);
      month = date.substring(4, 6);
      day = date.substring(6, 8);
    }

    // 統合JSONファイルのパス
    const jsonPath = path.join(
      DATA_ROOT,
      'races',
      year,
      month,
      day,
      'temp',
      `integrated_${raceId}.json`
    );

    if (!fs.existsSync(jsonPath)) {
      console.warn(`[IntegratedRaceReader] ファイルが見つかりません: ${jsonPath}`);
      return null;
    }

    const content = fs.readFileSync(jsonPath, 'utf-8');
    const data: IntegratedRaceData = JSON.parse(content);
    
    return data;
  } catch (error) {
    console.error('[IntegratedRaceReader] データ読み込みエラー:', error);
    return null;
  }
}

/**
 * 指定日の全レースデータを取得
 */
export async function getAllIntegratedRacesByDate(
  date: string    // "2026-01-24" or "20260124"
): Promise<IntegratedRaceData[]> {
  try {
    let year: string, month: string, day: string;
    
    if (date.includes('-')) {
      [year, month, day] = date.split('-');
    } else if (date.includes('/')) {
      [year, month, day] = date.split('/');
    } else {
      year = date.substring(0, 4);
      month = date.substring(4, 6);
      day = date.substring(6, 8);
    }

    const tempDir = path.join(DATA_ROOT, 'races', year, month, day, 'temp');
    
    if (!fs.existsSync(tempDir)) {
      console.warn(`[IntegratedRaceReader] ディレクトリが見つかりません: ${tempDir}`);
      return [];
    }

    const files = fs.readdirSync(tempDir)
      .filter(f => f.startsWith('integrated_') && f.endsWith('.json'));

    const races: IntegratedRaceData[] = [];
    
    for (const file of files) {
      try {
        const filePath = path.join(tempDir, file);
        const content = fs.readFileSync(filePath, 'utf-8');
        const data: IntegratedRaceData = JSON.parse(content);
        races.push(data);
      } catch (e) {
        console.warn(`[IntegratedRaceReader] ファイル読み込みエラー: ${file}`, e);
      }
    }

    // レース番号でソート
    races.sort((a, b) => a.race_info.race_number - b.race_info.race_number);
    
    return races;
  } catch (error) {
    console.error('[IntegratedRaceReader] 一括読み込みエラー:', error);
    return [];
  }
}

/**
 * 競馬場別にレースをグループ化
 */
export function groupRacesByVenue(
  races: IntegratedRaceData[]
): Record<string, IntegratedRaceData[]> {
  const grouped: Record<string, IntegratedRaceData[]> = {};
  
  for (const race of races) {
    const venue = race.race_info.venue || '不明';
    if (!grouped[venue]) {
      grouped[venue] = [];
    }
    grouped[venue].push(race);
  }

  // 各グループ内をレース番号でソート
  for (const venue of Object.keys(grouped)) {
    grouped[venue].sort((a, b) => a.race_info.race_number - b.race_info.race_number);
  }

  return grouped;
}

/**
 * 馬を馬番順にソート
 */
export function sortEntriesByNumber(entries: HorseEntry[]): HorseEntry[] {
  return [...entries].sort((a, b) => a.horse_number - b.horse_number);
}

/**
 * 馬を人気順にソート
 */
export function sortEntriesByOddsRank(entries: HorseEntry[]): HorseEntry[] {
  return [...entries].sort((a, b) => {
    const rankA = parseInt(a.entry_data.odds_rank, 10) || 999;
    const rankB = parseInt(b.entry_data.odds_rank, 10) || 999;
    return rankA - rankB;
  });
}

/**
 * 馬を着順でソート（結果がある場合）
 */
export function sortEntriesByFinishPosition(entries: HorseEntry[]): HorseEntry[] {
  return [...entries].sort((a, b) => {
    const posA = a.result ? parseFinishPosition(a.result.finish_position) : 999;
    const posB = b.result ? parseFinishPosition(b.result.finish_position) : 999;
    return posA - posB;
  });
}

/**
 * 馬を総合印ポイント順にソート
 */
export function sortEntriesByMarkPoint(entries: HorseEntry[]): HorseEntry[] {
  return [...entries].sort((a, b) => {
    const pointA = a.entry_data.aggregate_mark_point || 0;
    const pointB = b.entry_data.aggregate_mark_point || 0;
    return pointB - pointA; // 降順
  });
}

/**
 * レース結果があるかどうかを判定
 */
export function hasRaceResults(data: IntegratedRaceData): boolean {
  return data.entries.some(entry => 
    entry.result && 
    entry.result.finish_position && 
    entry.result.finish_position !== ''
  );
}

/**
 * 上り最速の馬を取得
 */
export function getFastestLast3f(entries: HorseEntry[]): HorseEntry | null {
  const withLast3f = entries.filter(e => 
    e.result?.last_3f && 
    !isNaN(parseFloat(e.result.last_3f))
  );
  
  if (withLast3f.length === 0) return null;
  
  return withLast3f.reduce((fastest, current) => {
    const fastestTime = parseFloat(fastest.result!.last_3f);
    const currentTime = parseFloat(current.result!.last_3f);
    return currentTime < fastestTime ? current : fastest;
  });
}

/**
 * 印の集計を取得
 */
export function getMarkSummary(entry: HorseEntry): {
  mainMark: string;
  totalPoint: number;
  markDetails: Record<string, string | undefined>;
} {
  const markDetails = entry.entry_data.marks_by_person || {};
  const mainMark = entry.entry_data.honshi_mark || '';
  const totalPoint = entry.entry_data.aggregate_mark_point || 0;
  
  return {
    mainMark,
    totalPoint,
    markDetails,
  };
}

/**
 * RPCI基準値データ読み込みユーティリティ
 * サーバーサイドでrace_type_standards.jsonを読み込む
 */

import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT_DIR } from '@/lib/config';
import { 
  getRpciTrend,
  type RpciTrend, 
  type RpciThresholds, 
  type CourseRpciInfo 
} from './rpci-utils';

// 型定義（サーバー側専用）
export interface RpciStats {
  mean: number;
  stdev: number;
  median: number;
  min: number;
  max: number;
}

export interface CourseRpciData {
  sample_count: number;
  rpci: RpciStats;
  thresholds: RpciThresholds;
}

export interface RpciStandardsData {
  metadata: {
    created_at: string;
    source: string;
    description: string;
    calculation: string;
  };
  by_distance_group: Record<string, CourseRpciData>;
  courses: Record<string, CourseRpciData>;
  similar_courses: Record<string, string[]>;
}

// 共通型を再エクスポート
export type { RpciTrend, RpciThresholds, CourseRpciInfo };

// 競馬場名の変換マップ
const TRACK_NAME_MAP: Record<string, string> = {
  '東京': 'Tokyo',
  '中山': 'Nakayama',
  '阪神': 'Hanshin',
  '京都': 'Kyoto',
  '中京': 'Chukyo',
  '新潟': 'Niigata',
  '札幌': 'Sapporo',
  '函館': 'Hakodate',
  '小倉': 'Kokura',
  '福島': 'Fukushima',
};

const TRACK_NAME_REVERSE_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(TRACK_NAME_MAP).map(([k, v]) => [v, k])
);

// トラック種別の変換
const SURFACE_MAP: Record<string, string> = {
  '芝': 'Turf',
  'ダ': 'Dirt',
  'ダート': 'Dirt',
};

const SURFACE_REVERSE_MAP: Record<string, string> = {
  'Turf': '芝',
  'Dirt': 'ダ',
};

// キャッシュ（1分間）
let cachedData: RpciStandardsData | null = null;
let cacheTimestamp: number = 0;
const CACHE_TTL = 60 * 1000; // 1分

/**
 * RPCI基準値データを読み込む
 */
export async function getRpciStandards(): Promise<RpciStandardsData | null> {
  // キャッシュチェック
  if (cachedData && Date.now() - cacheTimestamp < CACHE_TTL) {
    return cachedData;
  }

  try {
    const dataPath = path.join(
      KEIBA_DATA_ROOT_DIR,
      'target',
      'race_type_standards.json'
    );

    const fileContent = await fs.readFile(dataPath, 'utf-8');
    cachedData = JSON.parse(fileContent) as RpciStandardsData;
    cacheTimestamp = Date.now();
    return cachedData;
  } catch (error) {
    console.warn('[RPCI Standards Reader] ファイル読み込み失敗:', error);
    return null;
  }
}

/**
 * コースキーを生成
 * @param venue 競馬場名（日本語）
 * @param track 芝/ダート
 * @param distance 距離（m）
 */
export function buildCourseKey(venue: string, track: string, distance: number): string {
  const venueEn = TRACK_NAME_MAP[venue] || venue;
  
  // トラック種別を判定
  let surfaceEn = 'Turf';
  if (track === 'ダ' || track === 'ダート' || track.includes('ダ')) {
    surfaceEn = 'Dirt';
  } else if (track === '芝' || track.includes('芝')) {
    surfaceEn = 'Turf';
  }

  return `${venueEn}_${surfaceEn}_${distance}m`;
}

/**
 * コース名（日本語）を生成
 */
export function formatCourseNameJa(courseKey: string): string {
  const parts = courseKey.split('_');
  if (parts.length >= 3) {
    const venue = TRACK_NAME_REVERSE_MAP[parts[0]] || parts[0];
    const surface = SURFACE_REVERSE_MAP[parts[1]] || parts[1];
    const distance = parts.slice(2).join('');
    return `${venue}${surface}${distance}`;
  }
  return courseKey;
}

// getRpciTrend は rpci-utils.ts からインポート済み

/**
 * 距離グループを決定
 */
function getDistanceGroup(distance: number): string {
  if (distance <= 1200) return '1200m-';
  if (distance <= 1600) return '1400-1600m';
  if (distance <= 2200) return '1800-2200m';
  return '2400m+';
}

/**
 * レース情報からRPCI基準値情報を取得
 * @param venue 競馬場名（日本語）
 * @param track 芝/ダート
 * @param distance 距離（m）
 */
export async function getCourseRpciInfo(
  venue: string,
  track: string,
  distance: number
): Promise<CourseRpciInfo | null> {
  const data = await getRpciStandards();
  if (!data) return null;

  const courseKey = buildCourseKey(venue, track, distance);
  
  // まずコース別データを探す
  let courseData = data.courses[courseKey];
  
  // 見つからない場合は距離グループから取得
  if (!courseData) {
    const surfaceEn = track.includes('ダ') ? 'Dirt' : 'Turf';
    const distanceGroup = getDistanceGroup(distance);
    const groupKey = `${surfaceEn}_${distanceGroup}`;
    courseData = data.by_distance_group[groupKey];
    
    if (!courseData) return null;
  }

  const { trend, label } = getRpciTrend(courseData.rpci.mean);
  const similarCourses = data.similar_courses[courseKey] || [];

  return {
    courseKey,
    courseName: formatCourseNameJa(courseKey),
    rpciMean: courseData.rpci.mean,
    trend,
    trendLabel: label,
    thresholds: courseData.thresholds,
    similarCourses: similarCourses.map(formatCourseNameJa),
    sampleCount: courseData.sample_count,
  };
}

// 実際のRPCI計算関数は rpci-utils.ts に移動済み
// クライアントコンポーネントからは rpci-utils.ts の calculateActualRpci を使用

/**
 * RPCI基準値データ読み込みユーティリティ
 * サーバーサイドでrace_type_standards.jsonを読み込む
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
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
  weighted_mean?: number;  // 年度重み付け平均（直近2年×2倍）
}

export interface CourseRpciData {
  sample_count: number;
  rpci: RpciStats;
  thresholds: RpciThresholds;
}

export interface RunnerAdjustment {
  rpci_offset: number;
  sample_count: number;
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
  by_baba?: Record<string, CourseRpciData>;                          // 馬場別コース統計
  by_distance_group_baba?: Record<string, CourseRpciData>;           // 馬場別距離グループ
  runner_adjustments?: Record<string, Record<string, RunnerAdjustment>>;  // 頭数別RPCI補正
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
      DATA3_ROOT,
      'analysis',
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
 * 頭数帯を分類
 */
function classifyRunners(n: number): string {
  if (n <= 8) return '少頭数(~8)';
  if (n <= 13) return '中頭数(9-13)';
  return '多頭数(14~)';
}

/**
 * レース情報からRPCI基準値情報を取得
 * @param venue 競馬場名（日本語）
 * @param track 芝/ダート
 * @param distance 距離（m）
 * @param babaCondition 馬場状態（"良" or "稍重以上"）、省略時は全体データ
 * @param numRunners 出走頭数（頭数別補正に使用）、省略時は補正なし
 */
export async function getCourseRpciInfo(
  venue: string,
  track: string,
  distance: number,
  babaCondition?: string,
  numRunners?: number,
): Promise<CourseRpciInfo | null> {
  const data = await getRpciStandards();
  if (!data) return null;

  const courseKey = buildCourseKey(venue, track, distance);
  const surfaceEn = track.includes('ダ') ? 'Dirt' : 'Turf';
  const distanceGroup = getDistanceGroup(distance);

  // 馬場別データを優先的に探す
  let courseData: CourseRpciData | undefined;
  let usedBaba: string | undefined;

  if (babaCondition && data.by_baba) {
    const babaKey = `${courseKey}_${babaCondition}`;
    courseData = data.by_baba[babaKey];
    if (courseData) {
      usedBaba = babaCondition;
    } else if (data.by_distance_group_baba) {
      // コース別馬場データがなければ距離グループ×馬場にフォールバック
      const groupBabaKey = `${surfaceEn}_${distanceGroup}_${babaCondition}`;
      courseData = data.by_distance_group_baba[groupBabaKey];
      if (courseData) usedBaba = babaCondition;
    }
  }

  // 馬場別データが見つからない場合は従来の全体データにフォールバック
  if (!courseData) {
    courseData = data.courses[courseKey];
  }
  if (!courseData) {
    const groupKey = `${surfaceEn}_${distanceGroup}`;
    courseData = data.by_distance_group[groupKey];
    if (!courseData) return null;
  }

  // weighted_mean があればそちらを優先
  const rpciMean = courseData.rpci.weighted_mean ?? courseData.rpci.mean;
  const { trend, label } = getRpciTrend(rpciMean);
  const similarCourses = data.similar_courses[courseKey] || [];

  // 頭数別RPCI補正
  let runnerAdjustment: CourseRpciInfo['runnerAdjustment'];
  if (numRunners && numRunners > 0 && data.runner_adjustments) {
    const groupKey = `${surfaceEn}_${distanceGroup}`;
    const adjustments = data.runner_adjustments[groupKey];
    if (adjustments) {
      const band = classifyRunners(numRunners);
      const adj = adjustments[band];
      if (adj && adj.sample_count >= 30) {
        runnerAdjustment = {
          rpciOffset: adj.rpci_offset,
          sampleCount: adj.sample_count,
          runnerBand: band,
        };
      }
    }
  }

  return {
    courseKey,
    courseName: formatCourseNameJa(courseKey),
    rpciMean,
    trend,
    trendLabel: label,
    thresholds: courseData.thresholds,
    similarCourses: similarCourses.map(formatCourseNameJa),
    sampleCount: courseData.sample_count,
    runnerAdjustment,
    babaCondition: usedBaba,
  };
}

// 実際のRPCI計算関数は rpci-utils.ts に移動済み
// クライアントコンポーネントからは rpci-utils.ts の calculateActualRpci を使用

/**
 * レース傾向インデックス読み込みユーティリティ（サーバーサイド専用）
 * race_trend_index.json を読み込み、レースIDから傾向を取得する
 */

import { promises as fs } from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT_DIR } from '@/lib/config';
import type { RaceTrendType } from './rpci-utils';

// レース傾向インデックスの型定義
interface RaceTrendEntry {
  trend: RaceTrendType;
  rpci: number;
  s3: number;
  l3: number;
  s4?: number;
  l4?: number;
}

export interface RaceTrendIndex {
  metadata: {
    created_at: string;
    version: string;
    source: string;
    years: string;
    description: string;
  };
  races: Record<string, RaceTrendEntry>;
}

// キャッシュ（5分間）
let cachedIndex: RaceTrendIndex | null = null;
let cacheTimestamp: number = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5分

/**
 * レース傾向インデックスを読み込む
 */
export async function getRaceTrendIndex(): Promise<RaceTrendIndex | null> {
  // キャッシュチェック
  if (cachedIndex && Date.now() - cacheTimestamp < CACHE_TTL) {
    return cachedIndex;
  }

  try {
    const dataPath = path.join(
      KEIBA_DATA_ROOT_DIR,
      'target',
      'race_trend_index.json'
    );

    const fileContent = await fs.readFile(dataPath, 'utf-8');
    cachedIndex = JSON.parse(fileContent) as RaceTrendIndex;
    cacheTimestamp = Date.now();
    return cachedIndex;
  } catch {
    // ファイルがない場合はnullを返す（まだ生成されていない可能性）
    return null;
  }
}

/**
 * レースIDから傾向を取得
 * @param index レース傾向インデックス
 * @param raceId TARGET形式のレースID（12桁: year4+jyo2+kai2+nichi2+raceNum2）
 */
export function lookupRaceTrend(
  index: RaceTrendIndex | null,
  raceId: string
): RaceTrendType | undefined {
  if (!index) return undefined;
  return index.races[raceId]?.trend;
}

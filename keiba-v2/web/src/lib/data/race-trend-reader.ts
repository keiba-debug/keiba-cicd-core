/**
 * レース傾向インデックス読み込みユーティリティ（サーバーサイド専用）
 * race_trend_index.json を読み込み、レースIDから傾向を取得する
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import type { RaceTrendType, RaceTrendV2Type } from './rpci-utils';

// レース傾向インデックスの型定義
interface RaceTrendEntry {
  trend: RaceTrendType;     // v1後方互換
  trend_v2?: RaceTrendV2Type;  // v2分類
  rpci: number;
  s3: number;
  l3: number;
  s4?: number;
  l4?: number;
  lap33?: number;           // 33ラップ連続値
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
      DATA3_ROOT,
      'analysis',
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
 * レースIDからv2傾向を取得（v2優先、v1フォールバック）
 * @param index レース傾向インデックス
 * @param raceId JRA-VAN形式のレースID（16桁優先。12桁TARGET形式はフォールバック）
 */
export function lookupRaceTrend(
  index: RaceTrendIndex | null,
  raceId: string
): RaceTrendV2Type | RaceTrendType | undefined {
  if (!index) return undefined;
  const entry = index.races[raceId];
  if (!entry) return undefined;
  return entry.trend_v2 || entry.trend;
}

/**
 * レースIDからv1傾向を取得（後方互換用）
 */
export function lookupRaceTrendV1(
  index: RaceTrendIndex | null,
  raceId: string
): RaceTrendType | undefined {
  if (!index) return undefined;
  return index.races[raceId]?.trend;
}

/**
 * レースIDから33ラップ値を取得
 */
export function lookupLap33(
  index: RaceTrendIndex | null,
  raceId: string
): number | undefined {
  if (!index) return undefined;
  return index.races[raceId]?.lap33;
}

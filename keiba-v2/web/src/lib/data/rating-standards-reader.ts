/**
 * レイティング基準値リーダー
 * サーバーサイド専用
 */

import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';
import type { RatingStandards, GradeStandard } from './rating-utils';

// キャッシュ
let cachedStandards: RatingStandards | null = null;
let cacheTime: number = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5分

/**
 * レイティング基準値ファイルのパス
 */
function getRatingStandardsPath(): string {
  return path.join(
    DATA3_ROOT,
    'analysis',
    'rating_standards.json'
  );
}

/**
 * レイティング基準値を読み込む
 */
export async function getRatingStandards(): Promise<RatingStandards | null> {
  // キャッシュチェック
  if (cachedStandards && Date.now() - cacheTime < CACHE_TTL) {
    return cachedStandards;
  }
  
  try {
    const filePath = getRatingStandardsPath();
    const content = await fs.readFile(filePath, 'utf-8');
    const data = JSON.parse(content);
    
    cachedStandards = data as RatingStandards;
    cacheTime = Date.now();
    
    return cachedStandards;
  } catch (error) {
    console.error('Rating standards read error:', error);
    return null;
  }
}

/**
 * 特定グレードの基準値を取得
 */
export async function getGradeStandard(grade: string): Promise<GradeStandard | null> {
  const standards = await getRatingStandards();
  if (!standards) return null;
  
  return standards.by_grade?.[grade] || null;
}

// Re-export types
export type { RatingStandards, GradeStandard } from './rating-utils';

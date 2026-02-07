/**
 * 調教師インデックス読み込みユーティリティ
 * 
 * trainer_id_index.json から調教師情報を取得
 * - 競馬ブック厩舎ID → JRA-VAN調教師コード
 * - 調教師コメント（勝負調教パターン等）
 */

import fs from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT_DIR } from '@/lib/config';

/**
 * 調教師情報
 */
export interface TrainerInfo {
  keibabookId: string;    // 競馬ブック厩舎ID（例: "ｳ011"）
  jvnCode: string;        // JRA-VAN調教師コード（5桁）
  name: string;           // 調教師名
  tozai: string;          // 所属（"美浦" | "栗東"）
  comment: string;        // 調教師コメント（勝負調教パターン等）
}

// インデックスキャッシュ
let trainerIndexCache: Map<string, TrainerInfo> | null = null;
let cacheLoadedAt: number = 0;
const CACHE_TTL = 60 * 60 * 1000; // 1時間

/**
 * 調教師インデックスを読み込み（キャッシュあり）
 */
function loadTrainerIndex(): Map<string, TrainerInfo> {
  const now = Date.now();
  
  // キャッシュが有効ならそれを返す
  if (trainerIndexCache && (now - cacheLoadedAt) < CACHE_TTL) {
    return trainerIndexCache;
  }
  
  trainerIndexCache = new Map();
  
  try {
    const indexPath = path.join(KEIBA_DATA_ROOT_DIR, 'target', 'trainer_id_index.json');
    
    if (fs.existsSync(indexPath)) {
      const content = fs.readFileSync(indexPath, 'utf-8');
      const data = JSON.parse(content);
      
      for (const [keibabookId, info] of Object.entries(data)) {
        const typedInfo = info as Record<string, string>;
        trainerIndexCache.set(keibabookId, {
          keibabookId,
          jvnCode: typedInfo.jvn_code || '',
          name: typedInfo.name || '',
          tozai: typedInfo.tozai || '',
          comment: typedInfo.comment || '',
        });
      }
      
      console.log(`[TrainerIndex] Loaded ${trainerIndexCache.size} trainers`);
    } else {
      console.log(`[TrainerIndex] Index file not found: ${indexPath}`);
    }
  } catch (e) {
    console.error('[TrainerIndex] Failed to load index:', e);
  }
  
  cacheLoadedAt = now;
  return trainerIndexCache;
}

/**
 * 競馬ブック厩舎IDから調教師情報を取得
 */
export function getTrainerInfo(keibabookId: string): TrainerInfo | null {
  if (!keibabookId) return null;
  
  const index = loadTrainerIndex();
  return index.get(keibabookId) || null;
}

/**
 * 競馬ブック厩舎IDからJRA-VAN調教師コードを取得
 */
export function getTrainerJvnCode(keibabookId: string): string {
  const info = getTrainerInfo(keibabookId);
  return info?.jvnCode || '';
}

/**
 * 競馬ブック厩舎IDから調教師コメントを取得
 */
export function getTrainerComment(keibabookId: string): string {
  const info = getTrainerInfo(keibabookId);
  return info?.comment || '';
}

/**
 * キャッシュをクリア（テスト・デバッグ用）
 */
export function clearTrainerIndexCache(): void {
  trainerIndexCache = null;
  cacheLoadedAt = 0;
}

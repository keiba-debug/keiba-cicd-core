/**
 * システムヘルスチェックAPI
 * GET /api/health
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { PATHS, DATA_ROOT, JV_DATA_ROOT_DIR } from '@/lib/config';
import type {
  HealthResponse,
  IndexHealthCheck,
} from '@/types/data-quality';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const timestamp = new Date().toISOString();
    const warnings: string[] = [];
    const errors: string[] = [];

    // ============================================
    // 1. ディレクトリチェック
    // ============================================

    const keibaDataRoot = {
      path: DATA_ROOT,
      exists: fs.existsSync(DATA_ROOT),
      writable: false,
    };

    if (keibaDataRoot.exists) {
      keibaDataRoot.writable = await checkWritable(DATA_ROOT);
      if (!keibaDataRoot.writable) {
        warnings.push('競馬データルートディレクトリに書き込み権限がありません');
      }
    } else {
      errors.push('競馬データルートディレクトリが存在しません');
    }

    const jvDataRoot = {
      path: JV_DATA_ROOT_DIR,
      exists: fs.existsSync(JV_DATA_ROOT_DIR),
      accessible: false,
    };

    if (jvDataRoot.exists) {
      try {
        fs.readdirSync(JV_DATA_ROOT_DIR);
        jvDataRoot.accessible = true;
      } catch {
        jvDataRoot.accessible = false;
        warnings.push('JRA-VANデータディレクトリにアクセスできません');
      }
    } else {
      errors.push(
        'JRA-VANデータディレクトリが存在しません（ネットワークドライブ未接続の可能性）'
      );
    }

    const racesDir = {
      path: PATHS.races,
      exists: fs.existsSync(PATHS.races),
      dateCount: 0,
    };

    if (racesDir.exists) {
      racesDir.dateCount = await countAvailableDates();
    } else {
      errors.push('レースデータディレクトリが存在しません');
    }

    const cacheDirPath = path.join(DATA_ROOT, 'cache');
    const cacheDir = {
      path: cacheDirPath,
      exists: fs.existsSync(cacheDirPath),
      sizeMB: 0,
    };

    if (cacheDir.exists) {
      cacheDir.sizeMB = await getDirSize(cacheDirPath);
    } else {
      warnings.push('キャッシュディレクトリが存在しません');
    }

    const directoriesStatus = errors.length === 0 ? 'ok' : 'error';

    // ============================================
    // 2. ディスク容量チェック（データサイズ閾値）
    // ============================================

    let racesDataSizeMB = 0;
    let cacheSizeMB = 0;

    if (racesDir.exists) {
      racesDataSizeMB = await getDirSize(PATHS.races);
    }

    if (cacheDir.exists) {
      cacheSizeMB = await getDirSize(cacheDirPath);
    }

    const totalSizeMB = racesDataSizeMB + cacheSizeMB;

    // データサイズ閾値判定（statfs不使用・Windows互換）
    let diskSpaceStatus: 'ok' | 'warning' | 'critical' = 'ok';
    if (totalSizeMB > 10000) {
      // 10GB超
      diskSpaceStatus = 'warning';
      warnings.push('データサイズが10GBを超えています');
    }
    if (totalSizeMB > 50000) {
      // 50GB超
      diskSpaceStatus = 'critical';
      errors.push('データサイズが50GBを超えています');
    }

    // ============================================
    // 3. インデックスヘルスチェック
    // ============================================

    const indexPath = path.join(DATA_ROOT, 'cache', 'race_date_index.json');
    const metaPath = path.join(DATA_ROOT, 'cache', 'race_date_index_meta.json');

    let indexHealth: IndexHealthCheck = {
      status: 'missing',
      details: {
        exists: false,
        dateCount: 0,
        raceCount: 0,
        builtAt: '',
        ageHours: 0,
      },
    };

    if (fs.existsSync(indexPath) && fs.existsSync(metaPath)) {
      try {
        const metaContent = fs.readFileSync(metaPath, 'utf-8');
        const meta = JSON.parse(metaContent) as {
          builtAt?: string;
          dateCount?: number;
          raceCount?: number;
        };
        const builtAt = new Date(meta.builtAt ?? 0);
        const ageHours = (Date.now() - builtAt.getTime()) / (1000 * 60 * 60);

        indexHealth = {
          status: ageHours > 24 ? 'stale' : 'ok',
          details: {
            exists: true,
            dateCount: meta.dateCount ?? 0,
            raceCount: meta.raceCount ?? 0,
            builtAt: meta.builtAt ?? '',
            ageHours: Math.round(ageHours * 10) / 10,
          },
        };

        if (ageHours > 24) {
          warnings.push(
            `インデックスが${Math.floor(ageHours)}時間更新されていません`
          );
        }
      } catch {
        indexHealth.status = 'missing';
        indexHealth.details.exists = false;
        errors.push('インデックスメタデータが破損しています');
      }
    } else {
      warnings.push('レース日付インデックスが存在しません');
    }

    // ============================================
    // 4. メモリチェック
    // ============================================

    const memUsage = process.memoryUsage();
    const usedMB = Math.round(memUsage.rss / 1024 / 1024);
    const heapUsedMB = Math.round(memUsage.heapUsed / 1024 / 1024);
    const heapTotalMB = Math.round(memUsage.heapTotal / 1024 / 1024);

    let memoryStatus: 'ok' | 'warning' = 'ok';
    if (usedMB > 500) {
      memoryStatus = 'warning';
      warnings.push('メモリ使用量が500MBを超えています');
    }

    // ============================================
    // 全体ステータス決定
    // ============================================

    const overallStatus: 'healthy' | 'degraded' | 'unhealthy' =
      errors.length > 0 ? 'unhealthy' : warnings.length > 0 ? 'degraded' : 'healthy';

    const response: HealthResponse = {
      status: overallStatus,
      timestamp,
      checks: {
        directories: {
          status: directoriesStatus,
          details: {
            keibaDataRoot,
            jvDataRoot,
            racesDir,
            cacheDir,
          },
        },
        diskSpace: {
          status: diskSpaceStatus,
          details: {
            racesDataSizeMB,
            cacheSizeMB,
            totalSizeMB,
          },
        },
        indexHealth,
        memory: {
          status: memoryStatus,
          details: {
            usedMB,
            heapUsedMB,
            heapTotalMB,
          },
        },
      },
      warnings,
      errors,
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('[API /health] Error:', error);
    return NextResponse.json(
      { error: '内部エラーが発生しました', details: String(error) },
      { status: 500 }
    );
  }
}

// ============================================
// ヘルパー関数
// ============================================

async function checkWritable(dirPath: string): Promise<boolean> {
  const testFile = path.join(dirPath, '.write_test');
  try {
    fs.writeFileSync(testFile, '');
    fs.unlinkSync(testFile);
    return true;
  } catch {
    return false;
  }
}

async function countAvailableDates(): Promise<number> {
  const indexPath = path.join(DATA_ROOT, 'cache', 'race_date_index.json');
  if (!fs.existsSync(indexPath)) return 0;

  try {
    const content = fs.readFileSync(indexPath, 'utf-8');
    const data = JSON.parse(content) as Record<string, unknown>;
    return Object.keys(data).length;
  } catch {
    return 0;
  }
}

/**
 * ディレクトリサイズを計算（MB単位）
 * Windows互換: statfs は使わず、ファイルサイズを合計
 */
async function getDirSize(dirPath: string): Promise<number> {
  let totalSize = 0;

  const walk = async (dir: string) => {
    try {
      const entries = await fs.promises.readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        try {
          if (entry.isFile()) {
            const stats = await fs.promises.stat(fullPath);
            totalSize += stats.size;
          } else if (entry.isDirectory()) {
            await walk(fullPath);
          }
        } catch {
          // アクセスエラーは無視
        }
      }
    } catch {
      // ディレクトリアクセスエラーは無視
    }
  };

  await walk(dirPath);
  return totalSize / (1024 * 1024); // MB
}

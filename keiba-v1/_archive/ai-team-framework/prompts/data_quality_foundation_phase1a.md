# データ品質基盤 Phase 1a - API実装 開発指示書

**作成日**: 2026-02-01
**対象**: Phase 1a（API実装）
**実装期間**: 1週間（Day 1-5）
**前提**: Windows環境、Node.js、Next.js App Router

---

## 📋 概要

WebViewerに3つの読み取り専用APIを実装します：

1. **GET /api/data/status** - データ状況確認
2. **GET /api/data/validation** - データ検証
3. **GET /api/health** - システムヘルスチェック

**重要な制約**:
- ✅ Windows互換性必須（`statfs`等のUnix専用API禁止）
- ✅ すべてGET専用（POSTなし、ファイルシステムから直接読み取り）
- ✅ 既存の`race_date_index.json`を使用（race_dates.jsonは存在しない）
- ✅ Python Executorチェックなし（WebViewerには存在しない）

---

## 🗂️ 作成するファイル

```
keiba-cicd-core/KeibaCICD.WebViewer/src/
├── app/api/
│   ├── data/
│   │   ├── status/
│   │   │   └── route.ts          # NEW - データ状況API
│   │   └── validation/
│   │       └── route.ts          # NEW - データ検証API
│   └── health/
│       └── route.ts              # NEW - ヘルスチェックAPI
└── types/
    └── data-quality.ts           # NEW - 型定義
```

---

## 📦 Phase 1a-1: 型定義の作成

**ファイル**: `src/types/data-quality.ts`

**実装内容**:

```typescript
// src/types/data-quality.ts

/**
 * データ品質基盤 - 型定義
 *
 * Phase 1a で使用する全ての型定義
 */

// ============================================
// API 1: データ状況 (GET /api/data/status)
// ============================================

export interface DataStatusParams {
  date?: string;        // YYYY-MM-DD (単一日付)
  startDate?: string;   // YYYY-MM-DD (範囲開始)
  endDate?: string;     // YYYY-MM-DD (範囲終了)
}

export interface DataStatusResponse {
  success: true;
  query: {
    type: 'single' | 'range';
    date?: string;
    startDate?: string;
    endDate?: string;
  };
  summary: {
    totalDates: number;
    datesWithData: number;
    datesWithoutData: number;
    coveragePercent: number;
  };
  dates: DateStatus[];
  diskUsage: {
    totalSizeMB: number;
    fileCount: number;
  };
}

export interface DateStatus {
  date: string;
  displayDate: string;
  hasData: boolean;
  tracks: TrackStatus[];
  files: {
    raceInfo: boolean;       // race_info.json
    tempNittei: boolean;     // temp/nittei_*.json
    navigationIndex: boolean; // temp/navigation_index.json
  };
}

export interface TrackStatus {
  track: string;
  raceCount: number;
  hasRaceInfo: boolean;
  hasMdFiles: boolean;
}

// ============================================
// API 2: データ検証 (GET /api/data/validation)
// ============================================

export interface ValidationParams {
  date?: string;
  startDate?: string;
  endDate?: string;
  deep?: boolean;        // 詳細検証モード
}

export interface ValidationResponse {
  success: true;
  query: {
    type: 'single' | 'range';
    date?: string;
    startDate?: string;
    endDate?: string;
    deep: boolean;
  };
  validation: {
    overallStatus: 'healthy' | 'warning' | 'error';
    totalIssues: number;
    criticalIssues: number;
    warnings: number;
  };
  dates: DateValidation[];
}

export interface DateValidation {
  date: string;
  status: 'healthy' | 'warning' | 'error';
  issues: ValidationIssue[];
  checks: {
    raceInfoExists: boolean;
    raceInfoValid: boolean;
    trackDirectories: boolean;
    mdFilesPresent: boolean;
    cacheUpToDate: boolean;
  };
}

export interface ValidationIssue {
  level: 'critical' | 'warning' | 'info';
  type: 'missing_file' | 'incomplete_data' | 'invalid_format' | 'stale_cache';
  message: string;
  details?: string;
}

// ============================================
// API 3: ヘルスチェック (GET /api/health)
// ============================================

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  checks: {
    directories: DirectoryHealthCheck;
    diskSpace: DiskSpaceHealthCheck;
    indexHealth: IndexHealthCheck;
    memory: MemoryHealthCheck;
  };
  warnings: string[];
  errors: string[];
}

export interface DirectoryHealthCheck {
  status: 'ok' | 'error';
  details: {
    keibaDataRoot: {
      path: string;
      exists: boolean;
      writable: boolean;
    };
    jvDataRoot: {
      path: string;
      exists: boolean;
      accessible: boolean;
    };
    racesDir: {
      path: string;
      exists: boolean;
      dateCount: number;
    };
    cacheDir: {
      path: string;
      exists: boolean;
      sizeMB: number;
    };
  };
}

export interface DiskSpaceHealthCheck {
  status: 'ok' | 'warning' | 'critical';
  details: {
    racesDataSizeMB: number;
    cacheSizeMB: number;
    totalSizeMB: number;
  };
}

export interface IndexHealthCheck {
  status: 'ok' | 'stale' | 'missing';
  details: {
    exists: boolean;
    dateCount: number;
    raceCount: number;
    builtAt: string;
    ageHours: number;
  };
}

export interface MemoryHealthCheck {
  status: 'ok' | 'warning';
  details: {
    usedMB: number;
    heapUsedMB: number;
    heapTotalMB: number;
  };
}

// ============================================
// 共通エラーレスポンス
// ============================================

export interface ErrorResponse {
  error: string;
  details?: string;
}
```

**配置先**: `keiba-cicd-core/KeibaCICD.WebViewer/src/types/data-quality.ts`

---

## 📡 Phase 1a-2: API 1 - データ状況API

**ファイル**: `src/app/api/data/status/route.ts`

**実装内容**:

```typescript
/**
 * データ状況API
 * GET /api/data/status?date=YYYY-MM-DD
 * GET /api/data/status?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { PATHS, DATA_ROOT, TRACKS } from '@/lib/config';
import type { DataStatusResponse, DateStatus, TrackStatus } from '@/types/data-quality';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get('date');
    const startDate = searchParams.get('startDate');
    const endDate = searchParams.get('endDate');

    // パラメータバリデーション
    if (!date && (!startDate || !endDate)) {
      return NextResponse.json(
        { error: 'date または startDate と endDate を指定してください' },
        { status: 400 }
      );
    }

    const queryType = date ? 'single' : 'range';
    let targetDates: string[] = [];

    if (queryType === 'single') {
      if (!isValidDateFormat(date!)) {
        return NextResponse.json(
          { error: '日付形式が不正です (YYYY-MM-DD)' },
          { status: 400 }
        );
      }
      targetDates = [date!];
    } else {
      if (!isValidDateFormat(startDate!) || !isValidDateFormat(endDate!)) {
        return NextResponse.json(
          { error: '日付形式が不正です (YYYY-MM-DD)' },
          { status: 400 }
        );
      }
      targetDates = getDateRange(startDate!, endDate!);

      // 最大1年間に制限
      if (targetDates.length > 365) {
        return NextResponse.json(
          { error: '日付範囲が大きすぎます（最大365日）' },
          { status: 400 }
        );
      }
    }

    // 各日付のステータスを取得
    const dateStatuses: DateStatus[] = [];
    for (const targetDate of targetDates) {
      const status = await getDateStatus(targetDate);
      dateStatuses.push(status);
    }

    // サマリー集計
    const datesWithData = dateStatuses.filter(d => d.hasData).length;
    const datesWithoutData = dateStatuses.length - datesWithData;
    const coveragePercent = Math.round((datesWithData / dateStatuses.length) * 100);

    // ディスク使用量計算（全日付分）
    const diskUsage = await calculateDiskUsage(targetDates);

    const response: DataStatusResponse = {
      success: true,
      query: {
        type: queryType,
        date: queryType === 'single' ? date! : undefined,
        startDate: queryType === 'range' ? startDate! : undefined,
        endDate: queryType === 'range' ? endDate! : undefined,
      },
      summary: {
        totalDates: dateStatuses.length,
        datesWithData,
        datesWithoutData,
        coveragePercent,
      },
      dates: dateStatuses,
      diskUsage,
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('[API /data/status] Error:', error);
    return NextResponse.json(
      { error: '内部エラーが発生しました', details: String(error) },
      { status: 500 }
    );
  }
}

// ============================================
// ヘルパー関数
// ============================================

function isValidDateFormat(dateStr: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(dateStr);
}

function getDateRange(start: string, end: string): string[] {
  const dates: string[] = [];
  const startDate = new Date(start);
  const endDate = new Date(end);

  for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    dates.push(`${year}-${month}-${day}`);
  }

  return dates;
}

async function getDateStatus(date: string): Promise<DateStatus> {
  const [year, month, day] = date.split('-');
  const dayPath = path.join(PATHS.races, year, month, day);

  // ディスプレイ用日付
  const displayDate = `${year}年${parseInt(month)}月${parseInt(day)}日`;

  // ディレクトリが存在しない場合
  if (!fs.existsSync(dayPath)) {
    return {
      date,
      displayDate,
      hasData: false,
      tracks: [],
      files: {
        raceInfo: false,
        tempNittei: false,
        navigationIndex: false,
      },
    };
  }

  // ファイル存在確認
  const raceInfoPath = path.join(dayPath, 'race_info.json');
  const tempNitteiPath = path.join(dayPath, 'temp');
  const navigationIndexPath = path.join(dayPath, 'temp', 'navigation_index.json');

  const hasRaceInfo = fs.existsSync(raceInfoPath);
  const hasTempNittei = fs.existsSync(tempNitteiPath) &&
    fs.readdirSync(tempNitteiPath).some(f => f.startsWith('nittei_') && f.endsWith('.json'));
  const hasNavigationIndex = fs.existsSync(navigationIndexPath);

  // 競馬場ディレクトリを取得
  const trackStatuses: TrackStatus[] = [];
  try {
    const entries = fs.readdirSync(dayPath, { withFileTypes: true });
    const trackDirs = entries
      .filter(e => e.isDirectory() && (TRACKS as readonly string[]).includes(e.name))
      .map(e => e.name);

    for (const track of trackDirs) {
      const trackPath = path.join(dayPath, track);
      const mdFiles = fs.readdirSync(trackPath).filter(f => f.endsWith('.md'));

      trackStatuses.push({
        track,
        raceCount: mdFiles.length,
        hasRaceInfo,
        hasMdFiles: mdFiles.length > 0,
      });
    }
  } catch (error) {
    // ディレクトリ読み取りエラーは無視
  }

  const hasData = hasRaceInfo || trackStatuses.length > 0;

  return {
    date,
    displayDate,
    hasData,
    tracks: trackStatuses,
    files: {
      raceInfo: hasRaceInfo,
      tempNittei: hasTempNittei,
      navigationIndex: hasNavigationIndex,
    },
  };
}

async function calculateDiskUsage(dates: string[]): Promise<{ totalSizeMB: number; fileCount: number }> {
  let totalSize = 0;
  let fileCount = 0;

  for (const date of dates) {
    const [year, month, day] = date.split('-');
    const dayPath = path.join(PATHS.races, year, month, day);

    if (!fs.existsSync(dayPath)) continue;

    try {
      const { size, count } = await getDirSizeRecursive(dayPath);
      totalSize += size;
      fileCount += count;
    } catch (error) {
      // ディレクトリアクセスエラーは無視
    }
  }

  return {
    totalSizeMB: totalSize / (1024 * 1024),
    fileCount,
  };
}

/**
 * ディレクトリサイズを再帰的に計算（Windows互換）
 * statfs は使わず、ファイルサイズを合計する
 */
async function getDirSizeRecursive(dirPath: string): Promise<{ size: number; count: number }> {
  let totalSize = 0;
  let totalCount = 0;

  const entries = await fs.promises.readdir(dirPath, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);

    try {
      if (entry.isFile()) {
        const stats = await fs.promises.stat(fullPath);
        totalSize += stats.size;
        totalCount++;
      } else if (entry.isDirectory()) {
        const { size, count } = await getDirSizeRecursive(fullPath);
        totalSize += size;
        totalCount += count;
      }
    } catch (error) {
      // アクセスエラーは無視（権限等）
    }
  }

  return { size: totalSize, count: totalCount };
}
```

**配置先**: `keiba-cicd-core/KeibaCICD.WebViewer/src/app/api/data/status/route.ts`

---

## 🔍 Phase 1a-3: API 2 - データ検証API

**ファイル**: `src/app/api/data/validation/route.ts`

**実装内容**:

```typescript
/**
 * データ検証API
 * GET /api/data/validation?date=YYYY-MM-DD
 * GET /api/data/validation?date=YYYY-MM-DD&deep=true
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { PATHS, DATA_ROOT, TRACKS } from '@/lib/config';
import type { ValidationResponse, DateValidation, ValidationIssue } from '@/types/data-quality';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get('date');
    const startDate = searchParams.get('startDate');
    const endDate = searchParams.get('endDate');
    const deep = searchParams.get('deep') === 'true';

    // パラメータバリデーション
    if (!date && (!startDate || !endDate)) {
      return NextResponse.json(
        { error: 'date または startDate と endDate を指定してください' },
        { status: 400 }
      );
    }

    const queryType = date ? 'single' : 'range';
    let targetDates: string[] = [];

    if (queryType === 'single') {
      if (!isValidDateFormat(date!)) {
        return NextResponse.json(
          { error: '日付形式が不正です (YYYY-MM-DD)' },
          { status: 400 }
        );
      }
      targetDates = [date!];
    } else {
      if (!isValidDateFormat(startDate!) || !isValidDateFormat(endDate!)) {
        return NextResponse.json(
          { error: '日付形式が不正です (YYYY-MM-DD)' },
          { status: 400 }
        );
      }
      targetDates = getDateRange(startDate!, endDate!);

      if (targetDates.length > 365) {
        return NextResponse.json(
          { error: '日付範囲が大きすぎます（最大365日）' },
          { status: 400 }
        );
      }
    }

    // 各日付の検証
    const dateValidations: DateValidation[] = [];
    for (const targetDate of targetDates) {
      const validation = await validateDate(targetDate, deep);
      dateValidations.push(validation);
    }

    // 全体ステータス集計
    const criticalIssues = dateValidations.reduce((sum, d) =>
      sum + d.issues.filter(i => i.level === 'critical').length, 0);
    const warnings = dateValidations.reduce((sum, d) =>
      sum + d.issues.filter(i => i.level === 'warning').length, 0);
    const totalIssues = criticalIssues + warnings;

    const overallStatus =
      criticalIssues > 0 ? 'error' :
      warnings > 0 ? 'warning' :
      'healthy';

    const response: ValidationResponse = {
      success: true,
      query: {
        type: queryType,
        date: queryType === 'single' ? date! : undefined,
        startDate: queryType === 'range' ? startDate! : undefined,
        endDate: queryType === 'range' ? endDate! : undefined,
        deep,
      },
      validation: {
        overallStatus,
        totalIssues,
        criticalIssues,
        warnings,
      },
      dates: dateValidations,
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error('[API /data/validation] Error:', error);
    return NextResponse.json(
      { error: '内部エラーが発生しました', details: String(error) },
      { status: 500 }
    );
  }
}

// ============================================
// ヘルパー関数
// ============================================

function isValidDateFormat(dateStr: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(dateStr);
}

function getDateRange(start: string, end: string): string[] {
  const dates: string[] = [];
  const startDate = new Date(start);
  const endDate = new Date(end);

  for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    dates.push(`${year}-${month}-${day}`);
  }

  return dates;
}

async function validateDate(date: string, deep: boolean): Promise<DateValidation> {
  const [year, month, day] = date.split('-');
  const dayPath = path.join(PATHS.races, year, month, day);

  const issues: ValidationIssue[] = [];
  const checks = {
    raceInfoExists: false,
    raceInfoValid: false,
    trackDirectories: false,
    mdFilesPresent: false,
    cacheUpToDate: false,
  };

  // ディレクトリが存在しない場合
  if (!fs.existsSync(dayPath)) {
    // キャッシュにあるのに実体がない場合は critical
    const cacheHasDate = await checkCacheHasDate(date);
    if (cacheHasDate) {
      issues.push({
        level: 'critical',
        type: 'missing_file',
        message: 'インデックスに存在するが、ディレクトリが見つかりません',
        details: `Path: ${dayPath}`,
      });
    }

    const status = issues.some(i => i.level === 'critical') ? 'error' : 'healthy';
    return { date, status, issues, checks };
  }

  // race_info.json チェック
  const raceInfoPath = path.join(dayPath, 'race_info.json');
  checks.raceInfoExists = fs.existsSync(raceInfoPath);

  if (checks.raceInfoExists) {
    try {
      const content = fs.readFileSync(raceInfoPath, 'utf-8');
      const data = JSON.parse(content);
      checks.raceInfoValid = true;

      // 深度検証: 必須フィールドチェック
      if (deep) {
        if (!data.kaisai_data || typeof data.kaisai_data !== 'object') {
          issues.push({
            level: 'warning',
            type: 'incomplete_data',
            message: 'race_info.json に kaisai_data フィールドがありません',
          });
        }
      }
    } catch (error) {
      checks.raceInfoValid = false;
      issues.push({
        level: 'critical',
        type: 'invalid_format',
        message: 'race_info.json のJSONフォーマットが不正です',
        details: String(error),
      });
    }
  }

  // 競馬場ディレクトリチェック
  const trackDirs = fs.readdirSync(dayPath, { withFileTypes: true })
    .filter(e => e.isDirectory() && (TRACKS as readonly string[]).includes(e.name))
    .map(e => e.name);

  checks.trackDirectories = trackDirs.length > 0;

  // MDファイルチェック
  let totalMdFiles = 0;
  for (const track of trackDirs) {
    const trackPath = path.join(dayPath, track);
    const mdFiles = fs.readdirSync(trackPath).filter(f => f.endsWith('.md'));
    totalMdFiles += mdFiles.length;

    // 深度検証: MDファイルが空でないかチェック
    if (deep && mdFiles.length > 0) {
      for (const mdFile of mdFiles) {
        const mdPath = path.join(trackPath, mdFile);
        const stats = fs.statSync(mdPath);
        if (stats.size === 0) {
          issues.push({
            level: 'warning',
            type: 'incomplete_data',
            message: `空のMDファイル: ${track}/${mdFile}`,
          });
        }
      }
    }
  }

  checks.mdFilesPresent = totalMdFiles > 0;

  // 検証ルール適用

  // Critical: 競馬場ディレクトリがあるのに race_info.json がない
  if (checks.trackDirectories && !checks.raceInfoExists) {
    issues.push({
      level: 'critical',
      type: 'missing_file',
      message: '競馬場ディレクトリが存在しますが、race_info.json がありません',
    });
  }

  // Critical: 競馬場ディレクトリがあるのに MDファイルも race_info.json もない
  if (checks.trackDirectories && !checks.mdFilesPresent && !checks.raceInfoExists) {
    issues.push({
      level: 'critical',
      type: 'incomplete_data',
      message: '競馬場ディレクトリがありますが、MDファイルと race_info.json の両方がありません',
    });
  }

  // Warning: race_info.json があるのに競馬場ディレクトリがない
  if (checks.raceInfoExists && !checks.trackDirectories) {
    issues.push({
      level: 'warning',
      type: 'incomplete_data',
      message: 'race_info.json が存在しますが、競馬場ディレクトリがありません',
    });
  }

  // Warning: MDファイルがあるのに race_info.json がない
  if (checks.mdFilesPresent && !checks.raceInfoExists) {
    issues.push({
      level: 'warning',
      type: 'missing_file',
      message: 'MDファイルが存在しますが、race_info.json がありません',
    });
  }

  // Warning: temp/navigation_index.json がない
  const navigationIndexPath = path.join(dayPath, 'temp', 'navigation_index.json');
  if (checks.mdFilesPresent && !fs.existsSync(navigationIndexPath)) {
    issues.push({
      level: 'warning',
      type: 'missing_file',
      message: 'temp/navigation_index.json がありません',
    });
  }

  // Info: race_info.json のみ存在（未開催レース用として正常）
  if (checks.raceInfoExists && !checks.trackDirectories && !checks.mdFilesPresent) {
    issues.push({
      level: 'info',
      type: 'incomplete_data',
      message: 'race_info.json のみ存在（未開催レース）',
    });
  }

  // キャッシュ鮮度チェック
  checks.cacheUpToDate = await isCacheUpToDate(date);
  if (!checks.cacheUpToDate) {
    issues.push({
      level: 'warning',
      type: 'stale_cache',
      message: 'キャッシュインデックスが最新のデータより古い可能性があります',
    });
  }

  // ステータス決定
  const status =
    issues.some(i => i.level === 'critical') ? 'error' :
    issues.some(i => i.level === 'warning') ? 'warning' :
    'healthy';

  return { date, status, issues, checks };
}

async function checkCacheHasDate(date: string): Promise<boolean> {
  const indexPath = path.join(DATA_ROOT, 'cache', 'race_date_index.json');
  if (!fs.existsSync(indexPath)) return false;

  try {
    const content = fs.readFileSync(indexPath, 'utf-8');
    const data = JSON.parse(content);
    return date in data;
  } catch {
    return false;
  }
}

async function isCacheUpToDate(date: string): Promise<boolean> {
  const metaPath = path.join(DATA_ROOT, 'cache', 'race_date_index_meta.json');
  if (!fs.existsSync(metaPath)) return false;

  try {
    const content = fs.readFileSync(metaPath, 'utf-8');
    const meta = JSON.parse(content);
    const builtAt = new Date(meta.builtAt);
    const now = new Date();
    const ageHours = (now.getTime() - builtAt.getTime()) / (1000 * 60 * 60);

    return ageHours < 1; // 1時間以内なら fresh
  } catch {
    return false;
  }
}
```

**配置先**: `keiba-cicd-core/KeibaCICD.WebViewer/src/app/api/data/validation/route.ts`

---

## 💚 Phase 1a-4: API 3 - ヘルスチェックAPI

**ファイル**: `src/app/api/health/route.ts`

**実装内容**:

```typescript
/**
 * システムヘルスチェックAPI
 * GET /api/health
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { PATHS, DATA_ROOT, JV_DATA_ROOT_DIR } from '@/lib/config';
import type { HealthResponse } from '@/types/data-quality';

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
      errors.push('JRA-VANデータディレクトリが存在しません（ネットワークドライブ未接続の可能性）');
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
    // 2. ディスク容量チェック
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

    // ディスク容量ステータス判定（簡易版）
    let diskSpaceStatus: 'ok' | 'warning' | 'critical' = 'ok';
    if (totalSizeMB > 10000) { // 10GB超
      diskSpaceStatus = 'warning';
      warnings.push('データサイズが10GBを超えています');
    }
    if (totalSizeMB > 50000) { // 50GB超
      diskSpaceStatus = 'critical';
      errors.push('データサイズが50GBを超えています');
    }

    // ============================================
    // 3. インデックスヘルスチェック
    // ============================================

    const indexPath = path.join(DATA_ROOT, 'cache', 'race_date_index.json');
    const metaPath = path.join(DATA_ROOT, 'cache', 'race_date_index_meta.json');

    let indexHealth: any = {
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
        const meta = JSON.parse(metaContent);
        const builtAt = new Date(meta.builtAt);
        const ageHours = (Date.now() - builtAt.getTime()) / (1000 * 60 * 60);

        indexHealth = {
          status: ageHours > 24 ? 'stale' : 'ok',
          details: {
            exists: true,
            dateCount: meta.dateCount || 0,
            raceCount: meta.raceCount || 0,
            builtAt: meta.builtAt,
            ageHours: Math.round(ageHours * 10) / 10,
          },
        };

        if (ageHours > 24) {
          warnings.push(`インデックスが${Math.floor(ageHours)}時間更新されていません`);
        }
      } catch {
        indexHealth.status = 'missing';
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
      errors.length > 0 ? 'unhealthy' :
      warnings.length > 0 ? 'degraded' :
      'healthy';

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
    const data = JSON.parse(content);
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
```

**配置先**: `keiba-cicd-core/KeibaCICD.WebViewer/src/app/api/health/route.ts`

---

## ✅ テスト手順

### 1. 型定義のテスト

```bash
cd keiba-cicd-core/KeibaCICD.WebViewer
npm run build
```

型エラーがないことを確認。

### 2. API動作テスト

WebViewerを起動:

```bash
npm run dev
```

**API 1: データ状況**

```bash
# 単一日付
curl "http://localhost:3000/api/data/status?date=2026-01-31"

# 日付範囲
curl "http://localhost:3000/api/data/status?startDate=2026-01-01&endDate=2026-01-31"
```

**期待結果**:
- ステータスコード 200
- `success: true`
- `summary.coveragePercent` が計算されている
- `diskUsage.totalSizeMB` が0以上

**API 2: データ検証**

```bash
# 基本検証
curl "http://localhost:3000/api/data/validation?date=2026-01-31"

# 詳細検証
curl "http://localhost:3000/api/data/validation?date=2026-01-31&deep=true"
```

**期待結果**:
- ステータスコード 200
- `validation.overallStatus` が healthy/warning/error のいずれか
- `issues` 配列に検出された問題が含まれる

**API 3: ヘルスチェック**

```bash
curl "http://localhost:3000/api/health"
```

**期待結果**:
- ステータスコード 200
- `status` が healthy/degraded/unhealthy のいずれか
- `checks.directories.details` にすべてのパスが含まれる
- `checks.diskSpace.details.totalSizeMB` が計算されている

### 3. エラーハンドリングテスト

```bash
# 不正な日付形式
curl "http://localhost:3000/api/data/status?date=invalid"
# 期待: 400 Bad Request

# パラメータなし
curl "http://localhost:3000/api/data/status"
# 期待: 400 Bad Request

# 大きすぎる範囲
curl "http://localhost:3000/api/data/status?startDate=2020-01-01&endDate=2026-01-31"
# 期待: 400 Bad Request（365日超）
```

### 4. Windows互換性テスト

Windows環境で:

```powershell
# ローカルドライブ（C:\）でディスク容量計算
curl "http://localhost:3000/api/health"

# ネットワークドライブ（Y:\）でデータ読み取り
curl "http://localhost:3000/api/data/status?date=2026-01-31"
```

**確認事項**:
- [ ] `statfs` 等のUnix専用APIが使われていない
- [ ] ファイルパスが `path.join()` で結合されている
- [ ] ネットワークドライブアクセスエラーが適切にハンドリングされる

---

## 📋 完了チェックリスト

### Phase 1a-1: 型定義
- [ ] `src/types/data-quality.ts` 作成完了
- [ ] TypeScriptコンパイルエラーなし
- [ ] すべての型がエクスポートされている

### Phase 1a-2: データ状況API
- [ ] `src/app/api/data/status/route.ts` 作成完了
- [ ] 単一日付クエリが動作する
- [ ] 日付範囲クエリが動作する
- [ ] ディスク使用量が正しく計算される
- [ ] エラーハンドリングが適切

### Phase 1a-3: データ検証API
- [ ] `src/app/api/data/validation/route.ts` 作成完了
- [ ] 基本検証が動作する
- [ ] 詳細検証（deep=true）が動作する
- [ ] すべての検証ルールが実装されている
- [ ] 問題レベル（critical/warning/info）が正しく分類される

### Phase 1a-4: ヘルスチェックAPI
- [ ] `src/app/api/health/route.ts` 作成完了
- [ ] ディレクトリチェックが動作する
- [ ] ディスク容量チェックが動作する（Windows互換）
- [ ] インデックスヘルスチェックが動作する
- [ ] メモリチェックが動作する
- [ ] 全体ステータスが正しく決定される

### Windows互換性
- [ ] すべてのAPIがWindows 10/11で動作する
- [ ] ローカルドライブ（C:\）でディスク計算が動作する
- [ ] ネットワークドライブ（Y:\）でデータ読み取りが動作する
- [ ] Unix専用APIが使われていない

### パフォーマンス
- [ ] /api/data/status が1年分のデータで2秒以内に応答
- [ ] /api/data/validation が1年分のデータで3秒以内に応答（基本）
- [ ] /api/health が1秒以内に応答

---

## 🎯 次のステップ

Phase 1a完了後:

1. **Phase 1b**: UI実装（DataStatusCard、ValidationResultsCard、SystemHealthCard）
2. **Phase 1c**: 統合・テスト・ドキュメント作成

**Phase 1b の開発指示プロンプト**:
- Phase 1a完了後に作成予定
- UI コンポーネントの実装手順
- /admin ページへの統合方法

---

**作成者**: カカシ（AI相談役）
**レビュー**: Phase 1a完了後、カカシがコードレビューを実施
**質問**: 実装中に不明点があれば、カカシに相談してください

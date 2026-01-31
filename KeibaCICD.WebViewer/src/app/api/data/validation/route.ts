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
    const criticalIssues = dateValidations.reduce(
      (sum, d) => sum + d.issues.filter((i) => i.level === 'critical').length,
      0
    );
    const warnings = dateValidations.reduce(
      (sum, d) => sum + d.issues.filter((i) => i.level === 'warning').length,
      0
    );
    const totalIssues = criticalIssues + warnings;

    const overallStatus =
      criticalIssues > 0 ? 'error' : warnings > 0 ? 'warning' : 'healthy';

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

    const status = issues.some((i) => i.level === 'critical') ? 'error' : 'healthy';
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
  const trackDirs = fs
    .readdirSync(dayPath, { withFileTypes: true })
    .filter(
      (e) => e.isDirectory() && (TRACKS as readonly string[]).includes(e.name)
    )
    .map((e) => e.name);

  checks.trackDirectories = trackDirs.length > 0;

  // MDファイルチェック
  let totalMdFiles = 0;
  for (const track of trackDirs) {
    const trackPath = path.join(dayPath, track);
    const mdFiles = fs.readdirSync(trackPath).filter((f) => f.endsWith('.md'));
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

  // ============================================
  // 検証ルール適用（修正版）
  // ============================================

  // ステップ1: 未開催レースパターンを最優先で判定
  const isUnscheduledRace =
    checks.raceInfoExists &&
    !checks.trackDirectories &&
    !checks.mdFilesPresent;

  if (isUnscheduledRace) {
    // 未開催レース: info のみ出す（正常状態）
    issues.push({
      level: 'info',
      type: 'incomplete_data',
      message: 'race_info.json のみ存在（未開催レース）',
    });
  } else {
    // ステップ2: 未開催レース以外の検証ルール

    // Critical: 競馬場ディレクトリがあるのに race_info.json がない
    if (checks.trackDirectories && !checks.raceInfoExists) {
      issues.push({
        level: 'critical',
        type: 'missing_file',
        message: '競馬場ディレクトリが存在しますが、race_info.json がありません',
      });
    }

    // Critical: 競馬場ディレクトリがあるのに MDファイルも race_info.json もない
    if (
      checks.trackDirectories &&
      !checks.mdFilesPresent &&
      !checks.raceInfoExists
    ) {
      issues.push({
        level: 'critical',
        type: 'incomplete_data',
        message:
          '競馬場ディレクトリがありますが、MDファイルと race_info.json の両方がありません',
      });
    }

    // Warning: race_info.json があるのに競馬場ディレクトリがない
    // ※未開催レースは既に除外済み
    if (checks.raceInfoExists && !checks.trackDirectories) {
      issues.push({
        level: 'warning',
        type: 'incomplete_data',
        message:
          'race_info.json が存在しますが、競馬場ディレクトリがありません（異常パターン）',
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
    const navigationIndexPath = path.join(
      dayPath,
      'temp',
      'navigation_index.json'
    );
    if (checks.mdFilesPresent && !fs.existsSync(navigationIndexPath)) {
      issues.push({
        level: 'warning',
        type: 'missing_file',
        message: 'temp/navigation_index.json がありません',
      });
    }
  }

  // ステップ3: キャッシュ鮮度チェック（全パターン共通）
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
    issues.some((i) => i.level === 'critical')
      ? 'error'
      : issues.some((i) => i.level === 'warning')
        ? 'warning'
        : 'healthy';

  return { date, status, issues, checks };
}

async function checkCacheHasDate(date: string): Promise<boolean> {
  const indexPath = path.join(DATA_ROOT, 'cache', 'race_date_index.json');
  if (!fs.existsSync(indexPath)) return false;

  try {
    const content = fs.readFileSync(indexPath, 'utf-8');
    const data = JSON.parse(content) as Record<string, unknown>;
    return date in data;
  } catch {
    return false;
  }
}

async function isCacheUpToDate(_date: string): Promise<boolean> {
  const metaPath = path.join(DATA_ROOT, 'cache', 'race_date_index_meta.json');
  if (!fs.existsSync(metaPath)) return false;

  try {
    const content = fs.readFileSync(metaPath, 'utf-8');
    const meta = JSON.parse(content) as { builtAt?: string };
    const builtAt = new Date(meta.builtAt ?? 0);
    const now = new Date();
    const ageHours = (now.getTime() - builtAt.getTime()) / (1000 * 60 * 60);

    return ageHours < 1; // 1時間以内なら fresh
  } catch {
    return false;
  }
}

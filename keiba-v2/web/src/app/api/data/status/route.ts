/**
 * データ状況API
 * GET /api/data/status?date=YYYY-MM-DD
 * GET /api/data/status?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT, TRACKS } from '@/lib/config';

const RACES_DIR = path.join(DATA3_ROOT, 'races');
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
    const datesWithData = dateStatuses.filter((d) => d.hasData).length;
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
  const dayPath = path.join(RACES_DIR, year, month, day);

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
  const hasTempNittei =
    fs.existsSync(tempNitteiPath) &&
    fs.readdirSync(tempNitteiPath).some((f) => f.startsWith('nittei_') && f.endsWith('.json'));
  const hasNavigationIndex = fs.existsSync(navigationIndexPath);

  // 競馬場ディレクトリを取得
  const trackStatuses: TrackStatus[] = [];
  try {
    const entries = fs.readdirSync(dayPath, { withFileTypes: true });
    const trackDirs = entries
      .filter((e) => e.isDirectory() && (TRACKS as readonly string[]).includes(e.name))
      .map((e) => e.name);

    for (const track of trackDirs) {
      const trackPath = path.join(dayPath, track);
      const mdFiles = fs.readdirSync(trackPath).filter((f) => f.endsWith('.md'));

      trackStatuses.push({
        track,
        raceCount: mdFiles.length,
        hasRaceInfo,
        hasMdFiles: mdFiles.length > 0,
      });
    }
  } catch {
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

async function calculateDiskUsage(
  dates: string[]
): Promise<{ totalSizeMB: number; fileCount: number }> {
  let totalSize = 0;
  let fileCount = 0;

  for (const date of dates) {
    const [year, month, day] = date.split('-');
    const dayPath = path.join(RACES_DIR, year, month, day);

    if (!fs.existsSync(dayPath)) continue;

    try {
      const { size, count } = await getDirSizeRecursive(dayPath);
      totalSize += size;
      fileCount += count;
    } catch {
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
async function getDirSizeRecursive(
  dirPath: string
): Promise<{ size: number; count: number }> {
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
    } catch {
      // アクセスエラーは無視（権限等）
    }
  }

  return { size: totalSize, count: totalCount };
}

/**
 * 時系列オッズ取得API
 *
 * GET /api/odds/timeseries?raceId=2026013105010101
 *
 * RT_DATA から時系列オッズを取得し、変動情報を返す
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  getOddsTimeSeries,
  calculateOddsChanges,
  isRtDataAvailable,
} from '@/lib/data/rt-data-reader';
import {
  getHorseInfoByUmaban,
  lookupHorseInfo,
} from '@/lib/data/race-horse-names';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const raceId = searchParams.get('raceId');

  if (!isRtDataAvailable()) {
    return NextResponse.json(
      {
        error: 'RT_DATA not available',
        hint: '環境変数 JV_DATA_ROOT を設定し、RT_DATA フォルダが存在するか確認してください',
      },
      { status: 503 }
    );
  }

  if (!raceId || raceId.length !== 16) {
    return NextResponse.json(
      {
        error: 'raceId required (16 digits)',
        example: '/api/odds/timeseries?raceId=2026013105010101',
      },
      { status: 400 }
    );
  }

  const timeSeries = getOddsTimeSeries(raceId);
  const changes = calculateOddsChanges(raceId);

  if (timeSeries.length === 0) {
    return NextResponse.json(
      {
        error: 'Time series data not found',
        raceId,
        hint: '時系列スナップショットファイルがありません',
      },
      { status: 404 }
    );
  }

  // 馬名を付与
  const horseInfo = getHorseInfoByUmaban(raceId);
  const changesWithNames = changes.map((c) => {
    const info = lookupHorseInfo(horseInfo, c.umaban);
    return {
      ...c,
      horseName: info?.horseName,
      waku: info?.waku,
    };
  });

  // 最初と最後の時刻
  const firstTime = timeSeries[0]?.timeLabel || '';
  const lastTime = timeSeries[timeSeries.length - 1]?.timeLabel || '';

  return NextResponse.json({
    raceId,
    snapshotCount: timeSeries.length,
    firstTime,
    lastTime,
    timeSeries,
    changes: changesWithNames,
  });
}

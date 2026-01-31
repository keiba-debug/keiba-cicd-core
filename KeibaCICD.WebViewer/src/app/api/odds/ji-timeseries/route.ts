/**
 * JI_2026 時系列オッズ取得API
 *
 * GET /api/odds/ji-timeseries?raceId=2026013105010101
 *
 * JI_2026 (単勝時系列) からオッズの時系列データを取得
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  getJiOddsTimeSeries,
  isRtDataAvailable,
  calculateLastMinuteChanges,
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
        hint: 'JV_DATA_ROOT_DIR を E:\\TFJV に設定してください',
      },
      { status: 503 }
    );
  }

  if (!raceId || raceId.length !== 16) {
    return NextResponse.json(
      {
        error: 'raceId required (16 digits)',
        example: '/api/odds/ji-timeseries?raceId=2026013105010101',
      },
      { status: 400 }
    );
  }

  const timeSeries = getJiOddsTimeSeries(raceId);

  if (timeSeries.length === 0) {
    return NextResponse.json(
      {
        error: 'JI time series data not found',
        raceId,
        hint: 'JI_2026 の JTファイルが存在しないか、レース前です',
      },
      { status: 404 }
    );
  }

  // 馬情報を取得
  const horseInfo = getHorseInfoByUmaban(raceId);
  
  // 全馬番を抽出
  const allUmaban = new Set<string>();
  for (const snapshot of timeSeries) {
    for (const ub of Object.keys(snapshot.odds)) {
      allUmaban.add(ub);
    }
  }

  // 馬情報マップを作成
  const horses = Array.from(allUmaban)
    .sort((a, b) => parseInt(a, 10) - parseInt(b, 10))
    .map((ub) => {
      const info = lookupHorseInfo(horseInfo, ub);
      return {
        umaban: ub,
        horseName: info?.horseName || `${ub}番`,
        waku: info?.waku,
        finishPosition: info?.finishPosition,
      };
    });

  // 時系列データを整形（間引き：最大50件）
  let sampledTimeSeries = timeSeries;
  if (timeSeries.length > 50) {
    const step = Math.ceil(timeSeries.length / 50);
    sampledTimeSeries = timeSeries.filter((_, i) => i % step === 0 || i === timeSeries.length - 1);
  }

  // 直前10分の変動情報
  const lastMinuteChanges = calculateLastMinuteChanges(raceId);

  // 馬情報に直前変動を付与
  const horsesWithChanges = horses.map((h) => {
    const change = lastMinuteChanges.find(
      (c) => c.umaban === h.umaban || c.umaban === h.umaban.replace(/^0+/, '')
    );
    return {
      ...h,
      lastMinute: change || null,
    };
  });

  return NextResponse.json({
    raceId,
    snapshotCount: timeSeries.length,
    sampledCount: sampledTimeSeries.length,
    firstTime: timeSeries[0]?.timeLabel || '',
    lastTime: timeSeries[timeSeries.length - 1]?.timeLabel || '',
    horses: horsesWithChanges,
    timeSeries: sampledTimeSeries,
    lastMinuteChanges,
  });
}

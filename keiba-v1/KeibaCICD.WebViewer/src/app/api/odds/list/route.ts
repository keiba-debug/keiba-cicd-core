/**
 * オッズありレース一覧API
 *
 * GET /api/odds/list?date=20260131
 *
 * 指定日に RT_DATA でオッズがあるレースID一覧を返す
 */

import { NextRequest, NextResponse } from 'next/server';
import { listRacesWithOdds, isRtDataAvailable } from '@/lib/data/rt-data-reader';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const date = searchParams.get('date');

  if (!date || date.length !== 8) {
    return NextResponse.json(
      {
        error: 'date required (YYYYMMDD)',
        example: '/api/odds/list?date=20260131',
      },
      { status: 400 }
    );
  }

  if (!isRtDataAvailable()) {
    return NextResponse.json(
      { error: 'RT_DATA not available', raceIds: [] },
      { status: 503 }
    );
  }

  const raceIds = listRacesWithOdds(date);
  return NextResponse.json({ date, raceIds, count: raceIds.length });
}

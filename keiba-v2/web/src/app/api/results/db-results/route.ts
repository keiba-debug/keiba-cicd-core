/**
 * DB確定成績API
 *
 * GET /api/results/db-results?date=2026-02-14
 *
 * mykeibadb (MySQL) から確定着順 + 確定複勝オッズを取得して返す。
 */

import { NextRequest, NextResponse } from 'next/server';
import { getDbRaceResultsByDate } from '@/lib/data/db-odds';

export async function GET(request: NextRequest) {
  const date = request.nextUrl.searchParams.get('date');

  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json(
      {
        error: 'date required (YYYY-MM-DD)',
        example: '/api/results/db-results?date=2026-02-14',
      },
      { status: 400 }
    );
  }

  const result = await getDbRaceResultsByDate(date);

  return NextResponse.json(result, {
    headers: {
      'Cache-Control': result.totalRaces > 0
        ? 'public, max-age=300'
        : 'public, max-age=30',
    },
  });
}

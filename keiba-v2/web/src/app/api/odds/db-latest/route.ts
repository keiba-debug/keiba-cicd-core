/**
 * DB最新オッズAPI
 *
 * GET /api/odds/db-latest?raceId=2026020806010208
 *
 * mykeibadb (MySQL) から時系列/確定オッズを取得して返す。
 * 時系列オッズがあればそれを、なければ確定オッズにフォールバック。
 */

import { NextRequest, NextResponse } from 'next/server';
import { getDbLatestOdds } from '@/lib/data/db-odds';

export async function GET(request: NextRequest) {
  const raceId = request.nextUrl.searchParams.get('raceId');

  if (!raceId || raceId.length !== 16) {
    return NextResponse.json(
      {
        error: 'raceId required (16-digit)',
        example: '/api/odds/db-latest?raceId=2026020806010208',
      },
      { status: 400 }
    );
  }

  const result = await getDbLatestOdds(raceId);

  return NextResponse.json(result, {
    headers: {
      // レース当日はキャッシュ短め（30秒）、それ以外は長め
      'Cache-Control': result.source === 'timeseries'
        ? 'public, max-age=30'
        : 'public, max-age=300',
    },
  });
}

/**
 * 同日のレースナビゲーション情報
 *
 * GET /api/races/navigation?date=YYYY-MM-DD&track=TRACK[&raceNumber=N]
 * → tracks(全競馬場) / races(現在競馬場のレース一覧) / prevRace / nextRace
 */

import { NextRequest, NextResponse } from 'next/server';
import { getRaceNavigation } from '@/lib/data';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const date = request.nextUrl.searchParams.get('date');
  const track = request.nextUrl.searchParams.get('track');
  const raceNumberParam = request.nextUrl.searchParams.get('raceNumber');

  if (!date || !track) {
    return NextResponse.json(
      { error: 'date and track parameters required' },
      { status: 400 },
    );
  }

  const raceNumber = raceNumberParam ? parseInt(raceNumberParam, 10) : undefined;

  try {
    const nav = await getRaceNavigation(date, track, raceNumber);
    if (!nav) {
      return NextResponse.json({ error: 'navigation not found' }, { status: 404 });
    }
    return NextResponse.json(nav);
  } catch (e) {
    return NextResponse.json(
      { error: (e as Error).message ?? 'unknown error' },
      { status: 500 },
    );
  }
}

/**
 * 競馬開催日一覧API
 *
 * GET /api/race-dates
 * レース一覧画面と同様、race_info.json が存在する日付（競馬開催日）を返す
 */

import { NextResponse } from 'next/server';
import { getAvailableDates } from '@/lib/data';

export async function GET() {
  try {
    const dates = await getAvailableDates();
    return NextResponse.json({
      dates,
      count: dates.length,
    });
  } catch (error) {
    console.error('[RaceDates API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to get race dates', dates: [] },
      { status: 500 }
    );
  }
}

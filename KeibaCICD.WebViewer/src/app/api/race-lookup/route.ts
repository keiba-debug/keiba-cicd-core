import { NextRequest, NextResponse } from 'next/server';
import { lookupRace, lookupRaces, getAllRacesForDate, RaceLookupQuery } from '@/lib/data/race-lookup';

/**
 * レース情報検索API
 * 
 * GET: 単一レース検索
 *   /api/race-lookup?date=2025/11/02&track=東京&raceName=天皇賞
 *   /api/race-lookup?date=2025/11/02&track=東京&raceNumber=11
 *   /api/race-lookup?date=2025/11/02  (指定日の全レース)
 * 
 * POST: 複数レース一括検索
 *   body: { queries: [{ date, track, raceName }, ...] }
 */

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const date = searchParams.get('date');
  const track = searchParams.get('track');
  const raceName = searchParams.get('raceName');
  const raceNumber = searchParams.get('raceNumber');
  
  if (!date) {
    return NextResponse.json({ error: '日付が必要です' }, { status: 400 });
  }
  
  // 日付のみ指定 → その日の全レース
  if (!track) {
    const races = await getAllRacesForDate(date);
    return NextResponse.json({ races });
  }
  
  // 競馬場も指定 → 特定レース検索
  const query: RaceLookupQuery = { date, track };
  if (raceName) {
    query.raceName = raceName;
  }
  if (raceNumber) {
    query.raceNumber = parseInt(raceNumber, 10);
  }
  
  const result = await lookupRace(query);
  
  if (!result) {
    return NextResponse.json({ error: 'レースが見つかりません', query }, { status: 404 });
  }
  
  return NextResponse.json({ race: result });
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const queries = body.queries as RaceLookupQuery[];
    
    if (!Array.isArray(queries)) {
      return NextResponse.json({ error: 'queries配列が必要です' }, { status: 400 });
    }
    
    const results = await lookupRaces(queries);
    
    return NextResponse.json({
      results,
      found: results.filter(r => r !== null).length,
      total: queries.length,
    });
  } catch (error) {
    return NextResponse.json({ error: 'リクエストの解析に失敗しました' }, { status: 400 });
  }
}

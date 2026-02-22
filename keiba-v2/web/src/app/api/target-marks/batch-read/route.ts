/**
 * TARGET馬印 一括読み込みAPI
 *
 * POST: 複数レースの馬印を一度に取得
 * Body: { races: [{ race_id, venue_name }] }
 * Returns: { marks: { [race_id]: { [umaban]: string } } }
 */

import { NextRequest, NextResponse } from 'next/server';
import { getRaceMarks } from '@/lib/data/target-mark-reader';

interface RaceInput {
  race_id: string;
  venue_name: string;
}

/**
 * race_id (16桁 YYYYMMDDJJKKNNRR) からkai, nichiを抽出
 */
function parseRaceId(raceId: string) {
  const year = parseInt(raceId.substring(0, 4), 10);
  const kai = parseInt(raceId.substring(10, 12), 10);
  const nichi = parseInt(raceId.substring(12, 14), 10);
  const raceNumber = parseInt(raceId.substring(14, 16), 10);
  return { year, kai, nichi, raceNumber };
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const races: RaceInput[] = body.races;

    if (!Array.isArray(races) || races.length === 0) {
      return NextResponse.json(
        { error: 'Missing required parameter: races[]' },
        { status: 400 }
      );
    }

    const marks: Record<string, Record<number, string>> = {};

    for (const race of races) {
      const { year, kai, nichi, raceNumber } = parseRaceId(race.race_id);
      const raceMarks = getRaceMarks(year, kai, nichi, raceNumber, race.venue_name, 1);
      if (raceMarks && Object.keys(raceMarks.horseMarks).length > 0) {
        marks[race.race_id] = raceMarks.horseMarks;
      }
    }

    return NextResponse.json({ marks });
  } catch (error) {
    console.error('[target-marks/batch-read] Error:', error);
    return NextResponse.json(
      { error: 'Failed to read marks', details: String(error) },
      { status: 500 }
    );
  }
}

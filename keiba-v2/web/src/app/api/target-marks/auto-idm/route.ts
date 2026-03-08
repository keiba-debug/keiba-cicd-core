/**
 * IDM印一括書込みAPI
 *
 * POST: predictions の jrdb_idm を TARGET馬印4 に一括反映
 * Body: { date?: string }
 */

import { NextRequest, NextResponse } from 'next/server';
import { getPredictionsByDate } from '@/lib/data/predictions-reader';
import { batchWriteHorseMarks } from '@/lib/data/target-mark-reader';

const MARK_SET = 4; // UmaMark4

/** IDM → 2文字マーク（小数点以下切り捨て） */
function idmToMark(idm: number): string {
  const truncated = Math.trunc(idm);
  if (truncated < -9) return '-9';
  if (truncated < 0) return String(truncated); // "-1"〜"-9" = 2 chars
  if (truncated < 10) return ' ' + truncated;
  if (truncated > 99) return '99';
  return String(truncated);
}

export async function POST(request: NextRequest) {
  try {
    let date: string | undefined;
    try {
      const body = await request.json();
      date = body.date;
    } catch {
      // empty body
    }

    const resolvedDate = date || new Date().toISOString().slice(0, 10);
    const predictions = getPredictionsByDate(resolvedDate);

    if (!predictions) {
      return NextResponse.json(
        { error: `${resolvedDate} の予測データが見つかりません` },
        { status: 404 }
      );
    }

    const fileGroups = new Map<string, {
      year: number; kai: number; venue: string;
      ops: Array<{ day: number; raceNumber: number; horseNumber: number; mark: string }>;
    }>();

    let totalRaces = 0;
    let markedHorses = 0;

    for (const race of predictions.races) {
      const raceId = race.race_id;
      if (!raceId || raceId.length < 16) continue;

      const year = parseInt(raceId.slice(0, 4), 10);
      const kai = parseInt(raceId.slice(10, 12), 10);
      const nichi = parseInt(raceId.slice(12, 14), 10);
      const raceNumber = race.race_number;
      const venue = race.venue_name;
      if (!year || !kai || !nichi || !raceNumber || !venue) continue;

      totalRaces++;

      const key = `${year}-${kai}-${venue}`;
      if (!fileGroups.has(key)) {
        fileGroups.set(key, { year, kai, venue, ops: [] });
      }
      const group = fileGroups.get(key)!;

      // 全18頭分クリア
      for (let uma = 1; uma <= 18; uma++) {
        group.ops.push({ day: nichi, raceNumber, horseNumber: uma, mark: '' });
      }

      // IDM書込み
      for (const entry of race.entries) {
        const idm = entry.jrdb_idm;
        if (idm != null) {
          const mark = idmToMark(idm);
          group.ops.push({ day: nichi, raceNumber, horseNumber: entry.umaban, mark });
          markedHorses++;
        }
      }
    }

    for (const group of fileGroups.values()) {
      batchWriteHorseMarks(group.year, group.kai, group.venue, group.ops, MARK_SET);
    }

    return NextResponse.json({
      success: true,
      date: predictions.date,
      summary: { totalRaces, markedHorses, files: fileGroups.size },
    });
  } catch (error) {
    console.error('[auto-idm API] Error:', error);
    return NextResponse.json(
      { error: 'IDM印書込みに失敗しました', details: String(error) },
      { status: 500 }
    );
  }
}

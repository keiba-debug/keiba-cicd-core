/**
 * パドック印一括書込みAPI
 *
 * POST: keibabook kb_ext のパドック印を TARGET馬印5 に一括反映
 * Body: { date?: string }
 * 7R以降のレースのみ対象（パドック印はレース直前に更新される）
 */

import { NextRequest, NextResponse } from 'next/server';
import { getPredictionsByDate } from '@/lib/data/predictions-reader';
import { getKbExtData } from '@/lib/data/v4-keibabook-reader';
import { batchWriteHorseMarks } from '@/lib/data/target-mark-reader';

const MARK_SET = 5; // UmaMark5

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
    let skippedRaces = 0;

    for (const race of predictions.races) {
      const raceId = race.race_id;
      if (!raceId || raceId.length < 16) continue;

      // 7R以降のみ対象
      if (race.race_number < 7) {
        skippedRaces++;
        continue;
      }

      const year = parseInt(raceId.slice(0, 4), 10);
      const kai = parseInt(raceId.slice(10, 12), 10);
      const nichi = parseInt(raceId.slice(12, 14), 10);
      const raceNumber = race.race_number;
      const venue = race.venue_name;
      if (!year || !kai || !nichi || !raceNumber || !venue) continue;

      // kb_ext からパドック情報取得
      const kbExt = getKbExtData(raceId);
      if (!kbExt) continue;

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

      // パドック印書込み
      for (const [umabanStr, entry] of Object.entries(kbExt.entries)) {
        const paddock = entry.paddock_info;
        if (paddock && paddock.mark && paddock.mark.trim()) {
          const umaban = parseInt(umabanStr, 10);
          if (umaban >= 1 && umaban <= 18) {
            group.ops.push({ day: nichi, raceNumber, horseNumber: umaban, mark: paddock.mark });
            markedHorses++;
          }
        }
      }
    }

    for (const group of fileGroups.values()) {
      batchWriteHorseMarks(group.year, group.kai, group.venue, group.ops, MARK_SET);
    }

    return NextResponse.json({
      success: true,
      date: predictions.date,
      summary: {
        totalRaces,
        markedHorses,
        skippedRaces,
        files: fileGroups.size,
        note: '7R以降のみ対象',
      },
    });
  } catch (error) {
    console.error('[auto-paddock API] Error:', error);
    return NextResponse.json(
      { error: 'パドック印書込みに失敗しました', details: String(error) },
      { status: 500 }
    );
  }
}

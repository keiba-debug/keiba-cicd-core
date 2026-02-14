/**
 * VB印一括書込みAPI
 *
 * POST: predictions のVB候補をTARGET馬印2に一括反映
 * Body: { date?: string } — 指定日のアーカイブを使用。省略時はpredictions_live.json
 */

import { NextRequest, NextResponse } from 'next/server';
import { getPredictionsLive, getPredictionsByDate } from '@/lib/data/predictions-reader';
import { writeHorseMark } from '@/lib/data/target-mark-reader';

const MARK_SET = 2; // UmaMark2

/** VB Gap → 印マッピング */
function gapToMark(gap: number): string {
  if (gap >= 5) return '◎';
  if (gap >= 4) return '○';
  if (gap >= 3) return '▲';
  if (gap >= 2) return '△';
  return '';
}

export async function POST(request: NextRequest) {
  try {
    let date: string | undefined;
    try {
      const body = await request.json();
      date = body.date;
    } catch {
      // empty body is fine — use live predictions
    }

    const predictions = date
      ? getPredictionsByDate(date)
      : getPredictionsLive();

    if (!predictions) {
      return NextResponse.json(
        { error: date ? `${date} の予測データが見つかりません` : 'predictions_live.json が見つかりません' },
        { status: 404 }
      );
    }

    const markCounts: Record<string, number> = { '◎': 0, '○': 0, '▲': 0, '△': 0 };
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

      // まず全18頭分をクリア
      for (let uma = 1; uma <= 18; uma++) {
        writeHorseMark(year, kai, nichi, raceNumber, venue, uma, '', MARK_SET);
      }

      // VB候補に印を書込み
      for (const entry of race.entries) {
        const mark = gapToMark(entry.vb_gap);
        if (mark) {
          const success = writeHorseMark(
            year, kai, nichi, raceNumber, venue,
            entry.umaban, mark, MARK_SET
          );
          if (success) {
            markedHorses++;
            markCounts[mark]++;
          }
        }
      }
    }

    return NextResponse.json({
      success: true,
      date: predictions.date,
      summary: {
        totalRaces,
        markedHorses,
        marks: markCounts,
      },
    });
  } catch (error) {
    console.error('[auto-vb API] Error:', error);
    return NextResponse.json(
      { error: 'VB印書込みに失敗しました', details: String(error) },
      { status: 500 }
    );
  }
}

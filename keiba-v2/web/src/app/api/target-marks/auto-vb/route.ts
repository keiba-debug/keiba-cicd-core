/**
 * VB印一括書込みAPI
 *
 * POST: predictions のVB候補をTARGET馬印2に一括反映
 * Body: { date?: string, liveGaps?: Record<raceId, Record<umaban, number>> }
 * liveGaps指定時はリアルタイムオッズ連動のGapを使用。省略時はpredictions_live.jsonのvb_gap。
 *
 * バッチI/O: 同一ファイル(year+kai+venue)への全操作を1回のread/writeで実行。
 * 旧実装では12R×18頭=216回のI/Oが発生し、TARGETのファイル読み込みと
 * 競合して古い印が残る問題があった。
 */

import { NextRequest, NextResponse } from 'next/server';
import { getPredictionsLive, getPredictionsByDate } from '@/lib/data/predictions-reader';
import { batchWriteHorseMarks } from '@/lib/data/target-mark-reader';

const MARK_SET = 2; // UmaMark2

/** VB Gap → 印マッピング（半角2文字: "+5", "10" 等） */
function gapToMark(gap: number): string {
  if (gap < 2) return '';
  if (gap >= 10) return String(gap).slice(0, 2);  // "10", "11", ...
  return '+' + gap;                                // "+2", "+3", ... "+9"
}

/** ファイルキー: 同一DATファイルに書き込むレースをグルーピング */
function fileKey(year: number, kai: number, venue: string): string {
  return `${year}-${kai}-${venue}`;
}

export async function POST(request: NextRequest) {
  try {
    let date: string | undefined;
    let liveGaps: Record<string, Record<number, number>> | undefined;
    try {
      const body = await request.json();
      date = body.date;
      liveGaps = body.liveGaps;
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

    // ファイル別に操作をグルーピング
    const fileGroups = new Map<string, {
      year: number; kai: number; venue: string;
      ops: Array<{ day: number; raceNumber: number; horseNumber: number; mark: string }>;
    }>();

    const markCounts: Record<string, number> = {};
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

      const key = fileKey(year, kai, venue);
      if (!fileGroups.has(key)) {
        fileGroups.set(key, { year, kai, venue, ops: [] });
      }
      const group = fileGroups.get(key)!;

      // 全18頭分をクリア
      for (let uma = 1; uma <= 18; uma++) {
        group.ops.push({ day: nichi, raceNumber, horseNumber: uma, mark: '' });
      }

      // VB候補に印を書込み（liveGaps優先、なければpredictions時点のvb_gap）
      const raceGaps = liveGaps?.[raceId];
      for (const entry of race.entries) {
        const gap = raceGaps?.[entry.umaban] ?? entry.vb_gap;
        const mark = gapToMark(gap);
        if (mark) {
          group.ops.push({ day: nichi, raceNumber, horseNumber: entry.umaban, mark });
          markedHorses++;
          markCounts[mark] = (markCounts[mark] || 0) + 1;
        }
      }
    }

    // ファイル別にバッチ書込み実行（1ファイル=1回のread/write）
    for (const group of fileGroups.values()) {
      batchWriteHorseMarks(group.year, group.kai, group.venue, group.ops, MARK_SET);
    }

    return NextResponse.json({
      success: true,
      date: predictions.date,
      summary: {
        totalRaces,
        markedHorses,
        marks: markCounts,
        files: fileGroups.size,
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

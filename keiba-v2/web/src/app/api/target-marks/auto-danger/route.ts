/**
 * Danger Alert 印一括書込みAPI
 *
 * POST: predictions の危険馬をTARGET馬印1に一括反映
 * Body: { date?: string, dangerHorses: Array<{ raceId: string, umaban: number }>, raceIds?: string[] }
 * raceIds指定時はそのレースのみクリア対象（フィルタ連動）。省略時は全レース。
 *
 * 印: "危" 固定（危険な人気馬）
 */

import { NextRequest, NextResponse } from 'next/server';
import { getPredictionsByDate } from '@/lib/data/predictions-reader';
import { batchWriteHorseMarks } from '@/lib/data/target-mark-reader';

const MARK_SET = 1; // UmaMark1
const DANGER_MARK = '危';

/** ファイルキー: 同一DATファイルに書き込むレースをグルーピング */
function fileKey(year: number, kai: number, venue: string): string {
  return `${year}-${kai}-${venue}`;
}

export async function POST(request: NextRequest) {
  try {
    let date: string | undefined;
    let dangerHorses: Array<{ raceId: string; umaban: number }> = [];
    let raceIdFilter: Set<string> | undefined;
    try {
      const body = await request.json();
      date = body.date;
      dangerHorses = body.dangerHorses ?? [];
      if (Array.isArray(body.raceIds) && body.raceIds.length > 0) {
        raceIdFilter = new Set(body.raceIds as string[]);
      }
    } catch {
      return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
    }

    // dateなし時は今日の日付をデフォルト使用
    const resolvedDate = date || new Date().toISOString().slice(0, 10);
    const predictions = getPredictionsByDate(resolvedDate);

    if (!predictions) {
      return NextResponse.json(
        { error: `${resolvedDate} の予測データが見つかりません` },
        { status: 404 }
      );
    }

    // 危険馬をSetに変換（高速ルックアップ）
    const dangerSet = new Set(dangerHorses.map(d => `${d.raceId}-${d.umaban}`));

    // ファイル別に操作をグルーピング
    const fileGroups = new Map<string, {
      year: number; kai: number; venue: string;
      ops: Array<{ day: number; raceNumber: number; horseNumber: number; mark: string }>;
    }>();

    let totalRaces = 0;
    let markedHorses = 0;

    for (const race of predictions.races) {
      const raceId = race.race_id;
      if (!raceId || raceId.length < 16) continue;
      if (raceIdFilter && !raceIdFilter.has(raceId)) continue;

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

      // 危険馬に印を書込み
      for (const entry of race.entries) {
        if (dangerSet.has(`${raceId}-${entry.umaban}`)) {
          group.ops.push({ day: nichi, raceNumber, horseNumber: entry.umaban, mark: DANGER_MARK });
          markedHorses++;
        }
      }
    }

    // ファイル別にバッチ書込み実行
    for (const group of fileGroups.values()) {
      batchWriteHorseMarks(group.year, group.kai, group.venue, group.ops, MARK_SET);
    }

    return NextResponse.json({
      success: true,
      date: predictions.date,
      summary: {
        totalRaces,
        markedHorses,
        files: fileGroups.size,
      },
    });
  } catch (error) {
    console.error('[auto-danger API] Error:', error);
    return NextResponse.json(
      { error: 'DA印書込みに失敗しました', details: String(error) },
      { status: 500 }
    );
  }
}

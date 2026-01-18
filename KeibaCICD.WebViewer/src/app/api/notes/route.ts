/**
 * ユーザーメモAPI
 * GET /api/notes?date=YYYY-MM-DD&raceId=XXXXXXXXXX
 * POST /api/notes { date, raceId, raceMemo?, horses? }
 */

import { NextRequest, NextResponse } from 'next/server';
import { getRaceNotes, updateRaceMemo, updateHorseMemo } from '@/lib/data/user-notes';

export const runtime = 'nodejs';

/**
 * メモ取得
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get('date');
    const raceId = searchParams.get('raceId');

    if (!date || !raceId) {
      return NextResponse.json(
        { error: 'date と raceId は必須です' },
        { status: 400 }
      );
    }

    const notes = await getRaceNotes(date, raceId);
    return NextResponse.json(notes);
  } catch (error) {
    console.error('GET /api/notes error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

/**
 * メモ保存
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { date, raceId, raceMemo, horseNumber, horseMemo } = body;

    if (!date || !raceId) {
      return NextResponse.json(
        { error: 'date と raceId は必須です' },
        { status: 400 }
      );
    }

    // レースメモの更新
    if (raceMemo !== undefined) {
      await updateRaceMemo(date, raceId, raceMemo);
    }

    // 馬メモの更新
    if (horseNumber !== undefined && horseMemo !== undefined) {
      await updateHorseMemo(date, raceId, horseNumber, horseMemo);
    }

    // 更新後のメモを返す
    const notes = await getRaceNotes(date, raceId);
    return NextResponse.json({ success: true, notes });
  } catch (error) {
    console.error('POST /api/notes error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

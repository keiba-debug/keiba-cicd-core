/**
 * スタートメモAPI
 * GET /api/start-memo?raceId=XXXXXXX - レースのスタートメモを取得
 * POST /api/start-memo { raceId, raceDate, raceName, horseNumber, horseName, memo } - スタートメモを保存
 * DELETE /api/start-memo { raceId, horseNumber } - スタートメモを削除
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  getRaceStartMemos,
  updateHorseStartMemo,
  deleteHorseStartMemo,
  START_MEMO_PRESETS,
} from '@/lib/data/start-memo';

export const runtime = 'nodejs';

/**
 * スタートメモ取得
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const raceId = searchParams.get('raceId');
    const getPresets = searchParams.get('presets');

    // プリセット一覧を返す
    if (getPresets === 'true') {
      return NextResponse.json({ presets: START_MEMO_PRESETS });
    }

    if (!raceId) {
      return NextResponse.json(
        { error: 'raceId は必須です' },
        { status: 400 }
      );
    }

    const memos = await getRaceStartMemos(raceId);
    return NextResponse.json({ memos, presets: START_MEMO_PRESETS });
  } catch (error) {
    console.error('GET /api/start-memo error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

/**
 * スタートメモ保存
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { raceId, raceDate, raceName, horseNumber, horseName, memo } = body;

    if (!raceId || horseNumber === undefined) {
      return NextResponse.json(
        { error: 'raceId と horseNumber は必須です' },
        { status: 400 }
      );
    }

    const success = await updateHorseStartMemo(
      raceId,
      raceDate || '',
      raceName,
      horseNumber,
      horseName || '',
      memo || ''
    );

    if (!success) {
      return NextResponse.json(
        { error: '保存に失敗しました' },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('POST /api/start-memo error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

/**
 * スタートメモ削除
 */
export async function DELETE(request: NextRequest) {
  try {
    const body = await request.json();
    const { raceId, horseNumber } = body;

    if (!raceId || horseNumber === undefined) {
      return NextResponse.json(
        { error: 'raceId と horseNumber は必須です' },
        { status: 400 }
      );
    }

    const success = await deleteHorseStartMemo(raceId, horseNumber);

    if (!success) {
      return NextResponse.json(
        { error: '削除に失敗しました' },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('DELETE /api/start-memo error:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

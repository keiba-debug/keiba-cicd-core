/**
 * My印 v2 (明示消スキーマ) API
 *
 * GET: 指定レースの v2 データを返す (ファイル無しは空オブジェクト相当)
 * PUT: 指定レースの v2 データを上書き保存
 *
 * 設計背景: docs/auto-purchase/09_MY_MARKS_AND_STRATEGY.md §9.3
 */

import { NextRequest, NextResponse } from 'next/server';
import { readMyMarksV2 } from '@/lib/data/my-marks-v2-reader';
import { writeMyMarksV2 } from '@/lib/data/my-marks-v2-writer';

function isValidRaceId(raceId: string): boolean {
  return /^\d{16}$/.test(raceId);
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ raceId: string }> }
) {
  const { raceId } = await params;
  if (!isValidRaceId(raceId)) {
    return NextResponse.json(
      { error: 'Invalid raceId (expected 16-digit string)' },
      { status: 400 }
    );
  }

  try {
    const data = readMyMarksV2(raceId);
    return NextResponse.json({
      success: true,
      data: data ?? {
        race_id: raceId,
        explicit_erase: [],
        explicit_no_mark: [],
        updated_at: '',
        source: 'manual',
      },
      exists: data !== null,
    });
  } catch (e) {
    console.error('[my-marks-v2 API] GET error:', e);
    return NextResponse.json({ error: 'Failed to read', details: String(e) }, { status: 500 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ raceId: string }> }
) {
  const { raceId } = await params;
  if (!isValidRaceId(raceId)) {
    return NextResponse.json(
      { error: 'Invalid raceId (expected 16-digit string)' },
      { status: 400 }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  if (typeof body !== 'object' || body === null) {
    return NextResponse.json({ error: 'Body must be an object' }, { status: 400 });
  }

  const b = body as Record<string, unknown>;

  if (!Array.isArray(b.explicit_erase)) {
    return NextResponse.json(
      { error: 'explicit_erase must be an array of horse numbers (1-18)' },
      { status: 400 }
    );
  }

  try {
    const result = await writeMyMarksV2(raceId, {
      explicit_erase: b.explicit_erase as number[],
      explicit_no_mark: Array.isArray(b.explicit_no_mark) ? (b.explicit_no_mark as number[]) : [],
      source: b.source === 'auto_pruner' || b.source === 'import' ? b.source : 'manual',
    });

    return NextResponse.json({
      success: true,
      data: result.after,
      diff: result.diff,
    });
  } catch (e) {
    console.error('[my-marks-v2 API] PUT error:', e);
    return NextResponse.json({ error: 'Failed to write', details: String(e) }, { status: 500 });
  }
}

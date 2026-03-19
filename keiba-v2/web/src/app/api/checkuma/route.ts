import { NextRequest, NextResponse } from 'next/server';
import {
  readCheckUmaList,
  getCheckUmaMap,
  addCheckUma,
  removeCheckUma,
} from '@/lib/data/target-checkuma-reader';

/**
 * GET /api/checkuma
 *   ?horseIds=id1,id2,...  → 指定馬のチェック状態を返す
 *   (省略時は全件返す)
 */
export async function GET(request: NextRequest) {
  const horseIdsParam = request.nextUrl.searchParams.get('horseIds');

  if (horseIdsParam) {
    const horseIds = horseIdsParam.split(',').filter(Boolean);
    const map = getCheckUmaMap(horseIds);
    const result: Record<string, { month: number; day: number; level: number; comment: string }> = {};
    for (const [id, entry] of map) {
      result[id] = { month: entry.month, day: entry.day, level: entry.level, comment: entry.comment };
    }
    return NextResponse.json({ checkUma: result });
  }

  const entries = readCheckUmaList();
  return NextResponse.json({
    entries,
    total: entries.length,
  });
}

/**
 * POST /api/checkuma
 *   { horseId, level?, comment? }  → チェック馬追加/更新
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { horseId, level = 0, comment = '' } = body;

    if (!horseId || typeof horseId !== 'string' || horseId.length !== 10) {
      return NextResponse.json({ error: 'Invalid horseId (must be 10 digits)' }, { status: 400 });
    }

    const success = addCheckUma(horseId, level, comment);
    if (!success) {
      return NextResponse.json({ error: 'Failed to add check uma' }, { status: 500 });
    }

    return NextResponse.json({ success: true, horseId, level, comment });
  } catch (error) {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }
}

/**
 * DELETE /api/checkuma
 *   { horseId }  → チェック馬削除
 */
export async function DELETE(request: NextRequest) {
  try {
    const body = await request.json();
    const { horseId } = body;

    if (!horseId || typeof horseId !== 'string') {
      return NextResponse.json({ error: 'Invalid horseId' }, { status: 400 });
    }

    const success = removeCheckUma(horseId);
    if (!success) {
      return NextResponse.json({ error: 'Horse not found in check list' }, { status: 404 });
    }

    return NextResponse.json({ success: true, horseId });
  } catch (error) {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }
}

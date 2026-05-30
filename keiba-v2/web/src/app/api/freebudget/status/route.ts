/**
 * GET /api/freebudget/status?date=YYYY-MM-DD (省略時=today)
 *
 * 自動投票スケジューラの当日状態を返す (純 TS、 Python/DB 不要)。
 * SoT = freebudget_scheduler が書く state ファイル。 web は読むだけ。
 */
import { NextRequest, NextResponse } from 'next/server';
import { getSchedulerStatus } from '@/lib/data/freebudget-scheduler-reader';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const date = request.nextUrl.searchParams.get('date') || undefined;
  try {
    const status = getSchedulerStatus(date);
    return NextResponse.json(status);
  } catch (err) {
    return NextResponse.json(
      { error: String(err) },
      { status: 500 },
    );
  }
}

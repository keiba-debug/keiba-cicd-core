/**
 * purchase_ledger に存在する日付一覧
 *
 * GET /api/bankroll/ledger/dates
 */

import { NextResponse } from 'next/server';
import { listLedgerDates } from '@/lib/data/ledger-reader';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const dates = await listLedgerDates();
    // 新しい順
    dates.sort((a, b) => b.localeCompare(a));
    return NextResponse.json({ dates });
  } catch (error) {
    console.error('[LedgerDatesAPI] Error:', error);
    return NextResponse.json(
      { error: 'ledger 日付一覧の取得に失敗しました', message: error instanceof Error ? error.message : String(error) },
      { status: 500 },
    );
  }
}

/**
 * 自動投票 ledger 期間集計 API (Session 136)
 *
 * GET /api/bankroll/ledger/summary?from=2026-05-01&to=2026-05-31
 * GET /api/bankroll/ledger/summary?year=2026&month=5
 * GET /api/bankroll/ledger/summary                    (= 当月)
 *
 * purchase_ledger/{date}.json を期間横断で集計し、 戦略別ROI・日次推移を返す。
 * TARGET CSV では出せない「自動投票だけ・戦略別」の収支がこのエンドポイントの価値。
 */

import { NextRequest, NextResponse } from 'next/server';
import { aggregatePeriod } from '@/lib/data/ledger-reader';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function lastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

export async function GET(request: NextRequest) {
  try {
    const sp = request.nextUrl.searchParams;
    let from = sp.get('from') || '';
    let to = sp.get('to') || '';

    if (!from || !to) {
      const year = sp.get('year');
      const month = sp.get('month');
      if (year && month) {
        const y = parseInt(year, 10);
        const m = parseInt(month, 10);
        const mm = String(m).padStart(2, '0');
        from = `${y}-${mm}-01`;
        to = `${y}-${mm}-${String(lastDayOfMonth(y, m)).padStart(2, '0')}`;
      } else {
        // デフォルト = 当月 (UTC ではなくサーバローカル)
        const now = new Date();
        const y = now.getFullYear();
        const m = now.getMonth() + 1;
        const mm = String(m).padStart(2, '0');
        from = `${y}-${mm}-01`;
        to = `${y}-${mm}-${String(lastDayOfMonth(y, m)).padStart(2, '0')}`;
      }
    }

    const result = await aggregatePeriod(from, to);
    return NextResponse.json(result);
  } catch (error) {
    console.error('[LedgerSummaryAPI] Error:', error);
    return NextResponse.json(
      { error: 'ledger 期間集計の取得に失敗しました', message: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}

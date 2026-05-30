/**
 * 自動投票 ledger 日別詳細 API (Session 136)
 *
 * GET /api/bankroll/ledger/20260530   (YYYYMMDD or YYYY-MM-DD)
 *
 * data3/userdata/purchase_ledger/{YYYY-MM-DD}.json を読み、
 * 戦略別フィールド付きの日別購入・収支データを返す (純 TS, DB/Python 不要)。
 * settle_ledger.py で精算済なら payout/的中/収支が入る。
 */

import { NextRequest, NextResponse } from 'next/server';
import { KEIBA_DATA_ROOT } from '@/lib/config';
import { readLedger, flattenLedger, loadRaceMetaMap, toIsoDate } from '@/lib/data/ledger-reader';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  try {
    const { date } = await params;
    const iso = toIsoDate(date);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
      return NextResponse.json(
        { error: '日付形式が不正です (YYYYMMDD または YYYY-MM-DD)' },
        { status: 400 }
      );
    }

    const ledger = await readLedger(iso);
    if (!ledger) {
      return NextResponse.json({
        date: iso,
        races: [],
        summary: {
          total_bet: 0, total_payout: 0, profit: 0, recovery_rate: 0,
          race_count: 0, bet_count: 0, win_count: 0, settled_count: 0, pending_count: 0,
        },
        by_strategy: [],
        has_data: false,
      });
    }

    const metaMap = await loadRaceMetaMap(iso, KEIBA_DATA_ROOT);
    const result = flattenLedger(ledger, metaMap);
    return NextResponse.json(result);
  } catch (error) {
    console.error('[LedgerDailyAPI] Error:', error);
    return NextResponse.json(
      { error: 'ledger 日別詳細の取得に失敗しました', message: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}

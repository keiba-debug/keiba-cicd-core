/**
 * GET /api/selective-bets?date=YYYY-MM-DD
 *   → 該当日の selective_bets.json を返す (なければ {bets: []})
 *
 * Selective 戦略 (重賞のみ rank_p==1 単勝、BT ROI 203%) の候補馬一覧。
 * Web UI の予測表示でバッジ表示に使う。
 */
import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { KEIBA_DATA_ROOT } from '@/lib/config';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const date = searchParams.get('date');
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: 'date param required (YYYY-MM-DD)' }, { status: 400 });
  }
  const [y, m, d] = date.split('-');
  const filePath = path.join(KEIBA_DATA_ROOT, 'races', y, m, d, 'selective_bets.json');
  if (!fs.existsSync(filePath)) {
    return NextResponse.json({
      strategy: 'selective',
      date,
      n_bets: 0,
      bets: [],
      exists: false,
    });
  }
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    return NextResponse.json({ ...data, date, exists: true });
  } catch (e) {
    return NextResponse.json({ error: `parse failed: ${e}` }, { status: 500 });
  }
}

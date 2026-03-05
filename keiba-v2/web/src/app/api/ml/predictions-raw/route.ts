/**
 * ML predictions.json を直接返す API
 *
 * GET /api/ml/predictions-raw?date=YYYY-MM-DD
 * → races/YYYY/MM/DD/predictions.json の内容をそのまま返す
 */

import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const date = request.nextUrl.searchParams.get('date');
  if (!date) {
    return NextResponse.json({ error: 'date parameter required (YYYY-MM-DD)' }, { status: 400 });
  }

  const parts = date.split('-');
  if (parts.length !== 3) {
    return NextResponse.json({ error: 'Invalid date format. Use YYYY-MM-DD' }, { status: 400 });
  }

  const filePath = path.join(DATA3_ROOT, 'races', parts[0], parts[1], parts[2], 'predictions.json');

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ error: `predictions.json not found for ${date}` }, { status: 404 });
  }

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: 'Failed to read predictions.json', detail: String(err) },
      { status: 500 }
    );
  }
}

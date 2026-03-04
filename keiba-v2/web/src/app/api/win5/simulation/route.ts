/**
 * WIN5 シミュレーション結果 API
 * GET /api/win5/simulation
 *
 * ml/win5_combo_results.json を返す
 */

import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export async function GET() {
  const filePath = path.join(DATA3_ROOT, 'ml', 'win5_combo_results.json');

  if (!fs.existsSync(filePath)) {
    return NextResponse.json(
      { error: 'not_found', message: 'win5_combo_results.json not found. Run: python -m ml.win5_combo_sim' },
      { status: 404 }
    );
  }

  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(raw);
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: 'parse_error' }, { status: 500 });
  }
}

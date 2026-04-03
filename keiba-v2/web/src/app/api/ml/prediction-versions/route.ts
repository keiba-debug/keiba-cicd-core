/**
 * 指定日付で利用可能な predictions バージョン一覧を返す
 *
 * GET /api/ml/prediction-versions?date=YYYY-MM-DD
 * → ["polaris-2.0", "7.1"] (predictions_{version}.json が存在するバージョン)
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
    return NextResponse.json({ error: 'date parameter required' }, { status: 400 });
  }

  const parts = date.split('-');
  if (parts.length !== 3) {
    return NextResponse.json({ error: 'Invalid date format' }, { status: 400 });
  }

  const dayDir = path.join(DATA3_ROOT, 'races', parts[0], parts[1], parts[2]);
  if (!fs.existsSync(dayDir)) {
    return NextResponse.json([]);
  }

  const files = fs.readdirSync(dayDir);
  const versions: string[] = [];
  const pattern = /^predictions_(.+)\.json$/;

  for (const f of files) {
    const m = f.match(pattern);
    if (m) {
      const ver = m[1];
      // 旧形式(タイムスタンプ付き: predictions_v7.1_20260301T101905.json)は除外
      if (ver.includes('_')) continue;
      versions.push(ver);
    }
  }

  // メインのpredictions.jsonのバージョンも取得
  let current: string | null = null;
  const mainPath = path.join(dayDir, 'predictions.json');
  if (fs.existsSync(mainPath)) {
    try {
      const d = JSON.parse(fs.readFileSync(mainPath, 'utf-8'));
      current = d.model_version ?? null;
    } catch { /* ignore */ }
  }

  return NextResponse.json({ current, versions });
}

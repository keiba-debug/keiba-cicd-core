/**
 * 血統分析データ取得API
 * GET: sire_stats_index.json 読み込み
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const DATA_PATH = path.join(
  DATA3_ROOT,
  'indexes',
  'sire_stats_index.json'
);

export async function GET(_request: NextRequest) {
  try {
    await fs.access(DATA_PATH);
    const content = await fs.readFile(DATA_PATH, 'utf-8');
    const data = JSON.parse(content);
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      {
        error: 'not_found',
        message:
          'sire_stats_index.json が見つかりません。python -m builders.build_sire_stats を実行してください。',
      },
      { status: 404 }
    );
  }
}

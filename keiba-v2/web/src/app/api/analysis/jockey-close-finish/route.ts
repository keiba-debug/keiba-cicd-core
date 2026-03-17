/**
 * 騎手接戦分析データ取得API
 * GET: jockey_close_finish.json 読み込み
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const DATA_PATH = path.join(
  DATA3_ROOT,
  'analysis',
  'jockey_close_finish.json'
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
          'jockey_close_finish.json が見つかりません。python -m analysis.jockey_close_finish を実行してください。',
      },
      { status: 404 }
    );
  }
}

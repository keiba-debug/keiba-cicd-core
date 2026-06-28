/**
 * 発信者コメント分析 — 情報量ランキング取得API
 * GET ?role=trainer|jockey
 *   → comment_llm/commenters/_quant_{role}.json (素の配列) を返す
 *
 * データは comment_llm パイプラインの出力。Web側は読み取り専用。
 */

import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const COMMENTERS_DIR = path.join(DATA3_ROOT, 'comment_llm', 'commenters');

export async function GET(request: NextRequest) {
  const role = request.nextUrl.searchParams.get('role') ?? 'trainer';

  if (role !== 'trainer' && role !== 'jockey') {
    return NextResponse.json(
      { error: 'bad_request', message: 'role は trainer または jockey を指定してください。' },
      { status: 400 }
    );
  }

  const dataPath = path.join(COMMENTERS_DIR, `_quant_${role}.json`);

  try {
    const content = await fs.readFile(dataPath, 'utf-8');
    const rows = JSON.parse(content);
    return NextResponse.json({ role, rows });
  } catch {
    return NextResponse.json(
      {
        error: 'not_found',
        message:
          `_quant_${role}.json が見つかりません。` +
          `comment_llm パイプラインで再集計してください: ` +
          `python comment_llm/commenter_quant.py ${role}`,
      },
      { status: 404 }
    );
  }
}

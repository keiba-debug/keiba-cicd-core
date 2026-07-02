/**
 * AIコメント印(ABC)成績 — 集計取得API
 * GET → analysis/comment_mark_performance.json をそのまま返す
 *
 * データは comment_llm パイプライン成果(picks) × 結果 × ML予測 を集計したもの。
 * Web側は読み取り専用（表示専用・買い目には影響しない）。
 * 生成: python -m analysis.comment_mark_performance --since 2026-01-01
 */

import { NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const DATA_PATH = path.join(DATA3_ROOT, 'analysis', 'comment_mark_performance.json');

export async function GET() {
  try {
    const content = await fs.readFile(DATA_PATH, 'utf-8');
    return NextResponse.json(JSON.parse(content));
  } catch {
    return NextResponse.json(
      {
        error: 'not_found',
        message:
          'comment_mark_performance.json が見つかりません。' +
          '集計を実行してください: python -m analysis.comment_mark_performance --since 2026-01-01',
      },
      { status: 404 }
    );
  }
}

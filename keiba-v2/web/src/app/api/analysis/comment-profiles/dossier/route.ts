/**
 * 発信者コメント分析 — ドシエ(LLMプロファイル)取得API
 * GET ?role=trainer|jockey&name=<発信者名>
 *   → comment_llm/commenters/{role}_{name}.json を返す
 *
 * プロファイルは現状 trainer の一部のみ生成済。未生成は 404(=エラーでなく「未生成」扱い)。
 * Web側は読み取り専用。
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
  const rawName = request.nextUrl.searchParams.get('name') ?? '';

  if (role !== 'trainer' && role !== 'jockey') {
    return NextResponse.json(
      { error: 'bad_request', message: 'role は trainer または jockey を指定してください。' },
      { status: 400 }
    );
  }

  // パストラバーサル対策: 区切り文字・親参照を含む name は弾く。
  // 命名規則はファイル名内の '/' → '_' 置換のみを想定。
  if (!rawName || rawName.includes('\\') || rawName.includes('..')) {
    return NextResponse.json(
      { error: 'bad_request', message: 'name が不正です。' },
      { status: 400 }
    );
  }
  const safeName = rawName.replace(/\//g, '_');

  const fileName = `${role}_${safeName}.json`;
  const dataPath = path.join(COMMENTERS_DIR, fileName);

  // 解決後のパスが commenters ディレクトリ内に収まることを最終確認。
  if (path.dirname(path.resolve(dataPath)) !== path.resolve(COMMENTERS_DIR)) {
    return NextResponse.json(
      { error: 'bad_request', message: 'name が不正です。' },
      { status: 400 }
    );
  }

  try {
    const content = await fs.readFile(dataPath, 'utf-8');
    const data = JSON.parse(content);
    return NextResponse.json(data);
  } catch {
    // 未生成 = エラーではなく「プロファイル未生成」。フロントは 404 をその意味で扱う。
    return NextResponse.json(
      {
        error: 'not_generated',
        message: 'この発信者の LLM プロファイルは未生成です。',
      },
      { status: 404 }
    );
  }
}

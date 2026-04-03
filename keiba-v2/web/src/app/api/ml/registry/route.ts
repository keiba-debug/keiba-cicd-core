/**
 * モデルレジストリAPI
 * GET /api/ml/registry → model_registry.json の内容を返す
 */
import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { DATA3_ROOT } from '@/lib/config';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET() {
  const filePath = path.join(DATA3_ROOT, 'ml', 'model_registry.json');
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return NextResponse.json(JSON.parse(content));
  } catch {
    return NextResponse.json({ models: {}, categories: {} });
  }
}

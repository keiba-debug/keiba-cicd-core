import { NextResponse } from 'next/server';
import { getEdgeValidation } from '@/lib/data/edge-validation-reader';

// 毎週 export_edge_validation で更新される JSON を常に最新で返す (静的キャッシュ回避)
export const dynamic = 'force-dynamic';

export async function GET() {
  const result = await getEdgeValidation();
  if (!result) {
    return NextResponse.json(
      { error: 'Edge validation not found. Run: python -m ml.export_edge_validation' },
      { status: 404 },
    );
  }
  return NextResponse.json(result);
}

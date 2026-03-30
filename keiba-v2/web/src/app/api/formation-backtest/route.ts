import { NextRequest, NextResponse } from 'next/server';
import { getFormationBacktest } from '@/lib/data/formation-reader';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const result = await getFormationBacktest(version);
  if (!result) {
    return NextResponse.json(
      { error: 'Formation backtest not found. Run: python -m ml.export_formation_backtest' },
      { status: 404 },
    );
  }
  return NextResponse.json(result);
}

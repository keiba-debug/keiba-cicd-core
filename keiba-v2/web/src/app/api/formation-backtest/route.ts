import { NextResponse } from 'next/server';
import { getFormationBacktest } from '@/lib/data/formation-reader';

export async function GET() {
  const result = await getFormationBacktest();
  if (!result) {
    return NextResponse.json(
      { error: 'Formation backtest not found. Run: python -m ml.export_formation_backtest' },
      { status: 404 },
    );
  }
  return NextResponse.json(result);
}

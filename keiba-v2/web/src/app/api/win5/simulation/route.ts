import { NextRequest, NextResponse } from 'next/server';
import { getWin5SimulationResult } from '@/lib/data/win5-reader';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const result = await getWin5SimulationResult(version);
  if (!result) {
    return NextResponse.json(
      { error: 'not_found', message: 'win5_combo_results.json not found. Run: python -m ml.win5_combo_sim' },
      { status: 404 },
    );
  }
  return NextResponse.json(result);
}

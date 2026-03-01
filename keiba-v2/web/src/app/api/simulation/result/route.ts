import { NextRequest, NextResponse } from 'next/server';
import { getSimulationResult } from '@/lib/data/simulation-reader';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const result = await getSimulationResult(version);
  if (!result) {
    return NextResponse.json({ error: 'Simulation result not found' }, { status: 404 });
  }
  return NextResponse.json(result);
}

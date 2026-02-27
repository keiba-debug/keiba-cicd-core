import { NextResponse } from 'next/server';
import { getSimulationResult } from '@/lib/data/simulation-reader';

export async function GET() {
  const result = await getSimulationResult();
  if (!result) {
    return NextResponse.json({ error: 'Simulation result not found' }, { status: 404 });
  }
  return NextResponse.json(result);
}

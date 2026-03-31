import { NextResponse } from 'next/server';
import { getWin5SimulationVersions } from '@/lib/data/win5-reader';

export async function GET() {
  const versions = await getWin5SimulationVersions();
  return NextResponse.json({ versions });
}

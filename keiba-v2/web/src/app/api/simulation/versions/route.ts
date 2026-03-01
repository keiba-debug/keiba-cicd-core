import { NextResponse } from 'next/server';
import { getSimulationVersions } from '@/lib/data/simulation-reader';

export async function GET() {
  const versions = await getSimulationVersions();
  return NextResponse.json({ versions });
}

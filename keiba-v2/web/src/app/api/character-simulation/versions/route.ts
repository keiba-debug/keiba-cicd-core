import { NextResponse } from 'next/server';
import { getCharacterSimulationVersions } from '@/lib/data/character-simulation-reader';

export async function GET() {
  const versions = await getCharacterSimulationVersions();
  return NextResponse.json({ versions });
}

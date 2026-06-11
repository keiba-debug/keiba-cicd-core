import { NextRequest, NextResponse } from 'next/server';
import { getCharacterSimulation } from '@/lib/data/character-simulation-reader';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const result = await getCharacterSimulation(version);
  if (!result) {
    return NextResponse.json(
      { error: 'Character simulation not found. Run: python -m ml.export_character_simulation' },
      { status: 404 },
    );
  }
  return NextResponse.json(result);
}

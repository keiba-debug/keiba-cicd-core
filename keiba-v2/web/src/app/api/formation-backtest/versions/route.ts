import { NextResponse } from 'next/server';
import { getFormationVersions } from '@/lib/data/formation-reader';

export async function GET() {
  const versions = await getFormationVersions();
  return NextResponse.json({ versions });
}

import { NextResponse } from 'next/server';
import { getMlVersionManifest } from '@/lib/data/version-utils';

export async function GET() {
  const versions = await getMlVersionManifest();
  return NextResponse.json(versions);
}

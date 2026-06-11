import { NextResponse } from 'next/server';
import { getBetTemplateLabVersions } from '@/lib/data/bet-template-lab-reader';

export async function GET() {
  const versions = await getBetTemplateLabVersions();
  return NextResponse.json({ versions });
}

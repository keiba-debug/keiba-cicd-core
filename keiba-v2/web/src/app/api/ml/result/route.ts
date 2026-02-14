import { NextRequest, NextResponse } from 'next/server';
import { getMlExperimentResult } from '@/lib/data/ml-result-reader';

export async function GET(request: NextRequest) {
  const version = request.nextUrl.searchParams.get('version');
  const result = await getMlExperimentResult(version);
  if (!result) {
    return NextResponse.json({ error: 'ML result not found' }, { status: 404 });
  }
  return NextResponse.json(result);
}
